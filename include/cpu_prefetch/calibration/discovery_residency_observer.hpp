#ifndef CPU_PREFETCH_CALIBRATION_DISCOVERY_RESIDENCY_OBSERVER_HPP
#define CPU_PREFETCH_CALIBRATION_DISCOVERY_RESIDENCY_OBSERVER_HPP

#include "cpu_prefetch/calibration/discovery_session.hpp"
#include "cpu_prefetch/platform/prepared_residency.hpp"

#include <limits>
#include <span>
#include <stdexcept>

namespace cpu_prefetch::calibration {

enum class DiscoveryResidencyMoment : std::uint8_t { before, during, after };

struct DiscoveryResidencyRegion final {
  std::span<std::byte> mapping;
  std::uint32_t expected_node;
};

struct DiscoveryResidencyControls final {
  std::size_t verified_page_bytes;
  std::uint64_t wait_poll_limit;
};

struct DiscoveryResidencyRequest final {
  DiscoverySessionPhase phase;
  DiscoveryResidencyMoment moment;
  std::size_t region_index;
  std::uint64_t offset_ticks;
};

enum class DiscoveryResidencyStop : std::uint8_t {
  not_started,
  clock_failure,
  clock_regression,
  query_failure,
  wrong_node,
  outside_window,
  workers_finished,
  wait_exhausted,
  sampled,
  control_failure,
};

struct DiscoveryResidencySample final {
  DiscoveryResidencySample(DiscoveryResidencyRequest planned,
                           platform::PreparedPageResidencyQuery& prepared) noexcept
      : request(planned), pages(prepared) {}
  DiscoveryResidencyRequest request;
  platform::PreparedPageResidencyQuery& pages;
  std::optional<timing::ClockReadResult> wait_first;
  std::optional<timing::ClockReadResult> wait_last;
  std::optional<timing::ClockReadResult> begin;
  std::optional<timing::ClockReadResult> end;
  std::optional<platform::PageResidencyQueryResult> query;
  DiscoveryObservationStatus controls{DiscoveryObservationStatus::not_configured};
  std::optional<std::uint64_t> prior_controller_tick;
  std::optional<std::uint32_t> finished_before;
  std::optional<std::uint32_t> finished_after;
  std::uint64_t wait_polls{0U};
  DiscoveryResidencyStop stop{DiscoveryResidencyStop::not_started};
};

// Controller-only, caller-owned observation plan and retained snapshots. Before
// and after queries exhaust each declared region. During queries may cover
// explicitly planned subranges: their addresses remain visible; no full-region
// placement is inferred from a partial sample. Admission must separately bind
// complete live region coverage, monitoring schedules and other control facts.
// Every query has distinct status scratch retained until publication; immutable
// page-address scratch may be shared. No worker data bytes are read or written.
template <typename Clock, typename Query, typename Relax>
class PreparedDiscoveryResidencyObserver final {
public:
  PreparedDiscoveryResidencyObserver(DiscoverySessionPlan plan,
                                     DiscoveryResidencyControls controls,
                                     std::span<const DiscoveryResidencyRegion> regions,
                                     std::span<DiscoveryResidencySample> samples,
                                     Clock& clock, Query& query, Relax& relax)
      : plan_(plan), page_bytes_(controls.verified_page_bytes),
        poll_limit_(controls.wait_poll_limit), regions_(regions), samples_(samples),
        clock_(clock), query_(query), relax_(relax) {
    static_assert(noexcept(clock.read()));
    static_assert(noexcept(relax.relax()));
    validate();
  }
  PreparedDiscoveryResidencyObserver(const PreparedDiscoveryResidencyObserver&) =
      delete;
  auto operator=(const PreparedDiscoveryResidencyObserver&)
      -> PreparedDiscoveryResidencyObserver& = delete;

  [[nodiscard]] auto before_phase(DiscoverySessionPhase phase) noexcept -> bool {
    return enter(phase, DiscoveryResidencyMoment::before) &&
           sample_group(phase, DiscoveryResidencyMoment::before) &&
           controls_complete(phase, DiscoveryResidencyMoment::before);
  }
  [[nodiscard]] auto during_phase(DiscoverySessionPhase phase,
                                  DiscoveryObservationWindow window,
                                  const std::atomic<std::uint32_t>& finished) noexcept
      -> bool {
    if (!enter(phase, DiscoveryResidencyMoment::during) ||
        window.duration_ticks != duration(phase) ||
        window.origin_ticks >
            std::numeric_limits<std::uint64_t>::max() - window.duration_ticks) {
      sequence_rejected_ = true;
      return false;
    }
    windows_[static_cast<std::size_t>(phase)] = window;
    for (auto& sample : samples_) {
      if (sample.request.phase != phase ||
          sample.request.moment != DiscoveryResidencyMoment::during) {
        continue;
      }
      const auto target = window.origin_ticks + sample.request.offset_ticks;
      bool due = false;
      for (std::uint64_t poll = 0U; poll < poll_limit_; ++poll) {
        const auto tick = clock_.read();
        ++sample.wait_polls;
        if (!sample.wait_first.has_value()) {
          sample.wait_first = tick;
        }
        sample.wait_last = tick;
        if (!check_clock(sample, tick)) {
          return false;
        }
        if (tick.sample.relative_picoseconds >=
                window.origin_ticks + window.duration_ticks ||
            tick.sample.relative_picoseconds < window.origin_ticks) {
          sample.stop = DiscoveryResidencyStop::outside_window;
          return false;
        }
        const auto observed_finished = finished.load(std::memory_order_acquire);
        sample.finished_before = observed_finished;
        if (observed_finished != 0U) {
          sample.stop = DiscoveryResidencyStop::workers_finished;
          return false;
        }
        if (tick.sample.relative_picoseconds >= target) {
          sample.begin = tick;
          due = true;
          break;
        }
        relax_.relax();
      }
      if (!due) {
        sample.stop = DiscoveryResidencyStop::wait_exhausted;
        return false;
      }
      const bool passed = observe_pages(sample);
      const auto finished_after = finished.load(std::memory_order_acquire);
      sample.finished_after = finished_after;
      if (!passed) {
        return false;
      }
      if (finished_after != 0U) {
        sample.stop = DiscoveryResidencyStop::workers_finished;
        return false;
      }
      const auto ended = sample.end;
      if (!ended.has_value() || ended->sample.relative_picoseconds >=
                                    window.origin_ticks + window.duration_ticks) {
        sample.stop = DiscoveryResidencyStop::outside_window;
        return false;
      }
    }
    return controls_complete(phase, DiscoveryResidencyMoment::during);
  }
  [[nodiscard]] auto after_phase(DiscoverySessionPhase phase) noexcept -> bool {
    return enter(phase, DiscoveryResidencyMoment::after) &&
           sample_group(phase, DiscoveryResidencyMoment::after) &&
           controls_complete(phase, DiscoveryResidencyMoment::after);
  }
  [[nodiscard]] auto sequence_rejected() const noexcept -> bool {
    return sequence_rejected_;
  }
  [[nodiscard]] auto observed_windows() const noexcept
      -> const std::array<std::optional<DiscoveryObservationWindow>, 2U>& {
    return windows_;
  }

private:
  [[nodiscard]] auto controls_complete(DiscoverySessionPhase phase,
                                       DiscoveryResidencyMoment moment) const noexcept
      -> bool {
    if constexpr (requires { query_.control_group_complete(phase, moment); }) {
      static_assert(noexcept(query_.control_group_complete(phase, moment)));
      return query_.control_group_complete(phase, moment);
    }
    return true;
  }
  struct Range final {
    std::uintptr_t begin;
    std::size_t bytes;
  };
  [[nodiscard]] static auto range(const void* pointer, std::size_t bytes) -> Range {
    const auto begin = reinterpret_cast<std::uintptr_t>(pointer);
    if (begin == 0U || bytes == 0U ||
        bytes > std::numeric_limits<std::uintptr_t>::max() - begin) {
      throw std::invalid_argument("residency observer range is empty or overflows");
    }
    return {begin, bytes};
  }
  [[nodiscard]] static auto overlap(Range first, Range second) noexcept -> bool {
    return first.begin < second.begin + second.bytes &&
           second.begin < first.begin + first.bytes;
  }
  [[nodiscard]] auto duration(DiscoverySessionPhase phase) const noexcept
      -> std::uint64_t {
    return phase == DiscoverySessionPhase::warmup ? plan_.warmup_duration_ticks
                                                  : plan_.measurement_duration_ticks;
  }
  void validate() const {
    if (regions_.empty() || samples_.empty() || page_bytes_ == 0U ||
        (page_bytes_ & (page_bytes_ - 1U)) != 0U || poll_limit_ == 0U ||
        plan_.warmup_duration_ticks == 0U || plan_.measurement_duration_ticks == 0U) {
      throw std::invalid_argument("residency observer requires a finite nonempty plan");
    }
    const auto output = range(samples_.data(), samples_.size_bytes());
    const auto observer = range(this, sizeof(*this));
    const auto descriptors = range(regions_.data(), regions_.size_bytes());
    for (std::size_t region = 0U; region < regions_.size(); ++region) {
      const auto mapping = regions_[region].mapping;
      const auto target = range(mapping.data(), mapping.size());
      if (target.begin % page_bytes_ != 0U || mapping.size() % page_bytes_ != 0U ||
          regions_[region].expected_node >
              static_cast<std::uint32_t>(std::numeric_limits<int>::max()) ||
          overlap(target, output) || overlap(target, observer) ||
          overlap(target, descriptors)) {
        throw std::invalid_argument("residency observer has invalid target geometry");
      }
      for (std::size_t other = 0U; other < region; ++other) {
        const auto prior = regions_[other].mapping;
        if (overlap(target, range(prior.data(), prior.size()))) {
          throw std::invalid_argument("residency observer target regions overlap");
        }
      }
      for (const auto phase :
           {DiscoverySessionPhase::warmup, DiscoverySessionPhase::measurement}) {
        for (const auto moment :
             {DiscoveryResidencyMoment::before, DiscoveryResidencyMoment::during,
              DiscoveryResidencyMoment::after}) {
          std::size_t count = 0U;
          for (const auto& sample : samples_) {
            count += sample.request.region_index == region &&
                             sample.request.phase == phase &&
                             sample.request.moment == moment
                         ? 1U
                         : 0U;
          }
          if (count == 0U ||
              (moment != DiscoveryResidencyMoment::during && count != 1U)) {
            throw std::invalid_argument(
                "every region needs before/during/after coverage");
          }
        }
      }
    }
    for (std::size_t index = 0U; index < samples_.size(); ++index) {
      const auto& sample = samples_[index];
      const auto request = sample.request;
      if (request.region_index >= regions_.size() ||
          request.phase > DiscoverySessionPhase::measurement ||
          request.moment > DiscoveryResidencyMoment::after ||
          sample.stop != DiscoveryResidencyStop::not_started ||
          sample.begin.has_value() || sample.end.has_value() ||
          sample.query.has_value() || sample.wait_first.has_value() ||
          sample.controls != DiscoveryObservationStatus::not_configured ||
          sample.wait_last.has_value() || sample.wait_polls != 0U ||
          sample.prior_controller_tick.has_value() ||
          sample.finished_before.has_value() || sample.finished_after.has_value()) {
        throw std::invalid_argument("residency observer requires fresh valid requests");
      }
      if ((request.moment == DiscoveryResidencyMoment::during &&
           request.offset_ticks >= duration(request.phase)) ||
          (request.moment != DiscoveryResidencyMoment::during &&
           request.offset_ticks != 0U)) {
        throw std::invalid_argument(
            "residency observation offset is outside its phase");
      }
      const auto mapping = regions_[request.region_index].mapping;
      const auto addresses = sample.pages.page_addresses();
      const auto nodes = sample.pages.page_status();
      const auto target = range(mapping.data(), mapping.size());
      if (addresses.empty() || nodes.size() != addresses.size()) {
        throw std::invalid_argument("residency observer query has invalid scratch");
      }
      const auto first = reinterpret_cast<std::uintptr_t>(addresses.front());
      if (first < target.begin || first >= target.begin + target.bytes ||
          first % page_bytes_ != 0U ||
          addresses.size() > (target.begin + target.bytes - first) / page_bytes_ ||
          (request.moment != DiscoveryResidencyMoment::during &&
           (first != target.begin ||
            addresses.size() != mapping.size() / page_bytes_))) {
        throw std::invalid_argument(
            "residency query does not cover its declared range");
      }
      for (std::size_t page = 0U; page < addresses.size(); ++page) {
        if (reinterpret_cast<std::uintptr_t>(addresses[page]) !=
            first + page * page_bytes_) {
          throw std::invalid_argument("residency query page addresses have drifted");
        }
      }
      const auto statuses = range(nodes.data(), nodes.size_bytes());
      const auto pointers =
          range(static_cast<const void*>(addresses.data()), addresses.size_bytes());
      if (overlap(statuses, output) || overlap(pointers, output) ||
          overlap(statuses, observer) || overlap(pointers, observer) ||
          overlap(statuses, descriptors) || overlap(pointers, descriptors) ||
          overlap(statuses, range(&sample.pages, sizeof(sample.pages))) ||
          overlap(pointers, range(&sample.pages, sizeof(sample.pages)))) {
        throw std::invalid_argument("query scratch overlaps retained observations");
      }
      for (const auto& region : regions_) {
        const auto worker = range(region.mapping.data(), region.mapping.size());
        if (overlap(worker, statuses) || overlap(worker, pointers) ||
            overlap(worker, range(&sample.pages, sizeof(sample.pages)))) {
          throw std::invalid_argument("controller scratch overlaps worker regions");
        }
      }
      for (std::size_t prior = 0U; prior < index; ++prior) {
        const auto& other = samples_[prior];
        const auto old = other.request;
        const auto old_nodes = other.pages.page_status();
        const auto old_addresses = other.pages.page_addresses();
        if (overlap(statuses, range(old_nodes.data(), old_nodes.size_bytes())) ||
            overlap(statuses, range(static_cast<const void*>(old_addresses.data()),
                                    old_addresses.size_bytes())) ||
            overlap(pointers, range(old_nodes.data(), old_nodes.size_bytes())) ||
            overlap(statuses, range(&other.pages, sizeof(other.pages))) ||
            overlap(pointers, range(&other.pages, sizeof(other.pages))) ||
            overlap(range(old_nodes.data(), old_nodes.size_bytes()),
                    range(&sample.pages, sizeof(sample.pages))) ||
            overlap(range(static_cast<const void*>(old_addresses.data()),
                          old_addresses.size_bytes()),
                    range(&sample.pages, sizeof(sample.pages)))) {
          throw std::invalid_argument(
              "residency snapshot status scratch aliases another query");
        }
        if (old.phase > request.phase ||
            (old.phase == request.phase && old.moment > request.moment) ||
            (old.phase == request.phase && old.moment == request.moment &&
             (old.offset_ticks > request.offset_ticks ||
              (old.offset_ticks == request.offset_ticks &&
               old.region_index == request.region_index)))) {
          throw std::invalid_argument("residency requests are unordered or duplicated");
        }
      }
    }
  }
  [[nodiscard]] auto enter(DiscoverySessionPhase phase,
                           DiscoveryResidencyMoment moment) noexcept -> bool {
    const auto requested =
        static_cast<std::size_t>(phase) * 3U + static_cast<std::size_t>(moment);
    if (requested != next_hook_ || next_hook_ >= 6U) {
      sequence_rejected_ = true;
      return false;
    }
    ++next_hook_;
    return true;
  }
  [[nodiscard]] auto check_clock(DiscoveryResidencySample& row,
                                 timing::ClockReadResult observed) noexcept -> bool {
    if (observed.status != timing::ClockReadStatus::ok) {
      row.stop = DiscoveryResidencyStop::clock_failure;
      return false;
    }
    row.prior_controller_tick = previous_tick_;
    if (previous_tick_.has_value() &&
        observed.sample.relative_picoseconds < *previous_tick_) {
      row.stop = DiscoveryResidencyStop::clock_regression;
      return false;
    }
    previous_tick_ = observed.sample.relative_picoseconds;
    return true;
  }
  [[nodiscard]] auto observe_pages(DiscoveryResidencySample& row) noexcept -> bool {
    // One prospective schedule drives both controls and residency. A prepared
    // query may retain its independent control observations under this exact
    // request; no second scheduler can silently miss the same during window.
    if constexpr (requires { query_.observe_controls(row.request); }) {
      static_assert(noexcept(query_.observe_controls(row.request)));
      row.controls = query_.observe_controls(row.request);
    }
    const auto queried = row.pages.sample(query_);
    row.query = queried;
    const auto end = clock_.read();
    row.end = end;
    if (!check_clock(row, end)) {
      return false;
    }
    if (!queried.succeeded()) {
      row.stop = DiscoveryResidencyStop::query_failure;
      return false;
    }
    if (!row.pages.all_pages_on(queried,
                                regions_[row.request.region_index].expected_node)) {
      row.stop = DiscoveryResidencyStop::wrong_node;
      return false;
    }
    if (row.controls != DiscoveryObservationStatus::accepted &&
        row.controls != DiscoveryObservationStatus::not_configured) {
      row.stop = DiscoveryResidencyStop::control_failure;
      return false;
    }
    row.stop = DiscoveryResidencyStop::sampled;
    return true;
  }
  [[nodiscard]] auto sample_group(DiscoverySessionPhase phase,
                                  DiscoveryResidencyMoment moment) noexcept -> bool {
    for (auto& row : samples_) {
      if (row.request.phase != phase || row.request.moment != moment) {
        continue;
      }
      const auto begin = clock_.read();
      row.begin = begin;
      if (!check_clock(row, begin) || !observe_pages(row)) {
        return false;
      }
    }
    return true;
  }
  DiscoverySessionPlan plan_;
  std::size_t page_bytes_;
  std::uint64_t poll_limit_;
  std::span<const DiscoveryResidencyRegion> regions_;
  std::span<DiscoveryResidencySample> samples_;
  Clock& clock_;
  Query& query_;
  Relax& relax_;
  std::array<std::optional<DiscoveryObservationWindow>, 2U> windows_{};
  std::optional<std::uint64_t> previous_tick_;
  std::size_t next_hook_{0U};
  bool sequence_rejected_{false};
};

} // namespace cpu_prefetch::calibration

#endif
