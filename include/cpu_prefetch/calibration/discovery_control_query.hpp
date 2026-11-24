#ifndef CPU_PREFETCH_CALIBRATION_DISCOVERY_CONTROL_QUERY_HPP
#define CPU_PREFETCH_CALIBRATION_DISCOVERY_CONTROL_QUERY_HPP

#include "cpu_prefetch/calibration/discovery_residency_observer.hpp"
#include "cpu_prefetch/platform/prepared_prefetch_readback.hpp"
#include "cpu_prefetch/platform/thread_monitor.hpp"

namespace cpu_prefetch::calibration {

struct DiscoveryDisturbanceLimits final {
  std::optional<std::uint64_t> minor_faults;
  std::optional<std::uint64_t> major_faults;
  std::optional<std::uint64_t> voluntary_switches;
  std::optional<std::uint64_t> involuntary_switches;
};

struct DiscoveryControlPlan final {
  std::array<std::uint32_t, 2U> cpus;
  std::array<int, 2U> observed_owner_ids;
  std::array<std::array<DiscoveryDisturbanceLimits, 2U>, 2U> limits;
  protocol::RequestedHardwareState hardware_state;
};

enum class DiscoveryControlStop : std::uint8_t {
  not_started,
  thread_read_failure,
  owner_mismatch,
  counter_regression,
  disturbance_limit,
  hardware_failure,
  sampled,
};

struct DiscoveryControlSample final {
  DiscoveryResidencyRequest request;
  std::array<platform::ThreadMonitorScratch, 2U> scratch;
  std::array<std::optional<platform::ThreadControlSample>, 2U> workers{};
  platform::PrefetchReadbackSample hardware{};
  bool attempted{false};
  DiscoveryControlStop stop{DiscoveryControlStop::not_started};
};

// Exactly one admitted control group for each phase/moment, attached to an
// explicit residency request. Other residency rows do not invent extra control
// observations. The outer residency observer brackets the entire group in time.
// Null disturbance limits are explicitly unenforced, not observed zeroes or
// substituted defaults. This adapter never chooses prospective limits.
template <typename PageQuery = platform::LinuxPageResidencyQuery,
          typename ThreadMonitor = platform::PreparedThreadMonitor,
          typename PrefetchMonitor = platform::PreparedPrefetchReadback>
class DiscoveryControlQuery final {
public:
  DiscoveryControlQuery(DiscoveryControlPlan plan,
                        std::array<ThreadMonitor*, 2U> owners,
                        PrefetchMonitor& hardware, PageQuery& pages,
                        std::span<DiscoveryControlSample, 6U> samples)
      : plan_(plan), owners_(owners), hardware_(hardware), pages_(pages),
        samples_(samples) {
    if (owners_[0U] == nullptr || owners_[1U] == nullptr ||
        owners_[0U] == owners_[1U] || plan_.observed_owner_ids[0U] <= 0 ||
        plan_.observed_owner_ids[1U] <= 0 ||
        plan_.observed_owner_ids[0U] == plan_.observed_owner_ids[1U] ||
        (plan_.hardware_state != protocol::RequestedHardwareState::h0 &&
         plan_.hardware_state != protocol::RequestedHardwareState::h1)) {
      throw std::invalid_argument("control query requires two actual owner identities");
    }
    struct Range final {
      std::uintptr_t begin;
      std::size_t bytes;
    };
    std::array<Range, 49U> ranges{};
    ranges[0U] = {reinterpret_cast<std::uintptr_t>(samples_.data()),
                  samples_.size_bytes()};
    std::size_t next = 1U;
    for (std::size_t index = 0U; index < samples_.size(); ++index) {
      const auto& sample = samples_[index];
      if (static_cast<std::size_t>(sample.request.phase) != index / 3U ||
          static_cast<std::size_t>(sample.request.moment) != index % 3U ||
          sample.attempted || sample.stop != DiscoveryControlStop::not_started ||
          sample.workers[0U].has_value() || sample.workers[1U].has_value() ||
          sample.hardware.attempted) {
        throw std::invalid_argument("control query requires fresh ordered groups");
      }
      for (const auto scratch : sample.scratch) {
        if (scratch.affinity.size() >
            std::numeric_limits<std::size_t>::max() / sizeof(unsigned long)) {
          throw std::invalid_argument("control mask extent overflows");
        }
        ranges[next++] = {reinterpret_cast<std::uintptr_t>(scratch.stat_before.data()),
                          scratch.stat_before.size()};
        ranges[next++] = {reinterpret_cast<std::uintptr_t>(scratch.status.data()),
                          scratch.status.size()};
        ranges[next++] = {reinterpret_cast<std::uintptr_t>(scratch.stat_after.data()),
                          scratch.stat_after.size()};
        ranges[next++] = {reinterpret_cast<std::uintptr_t>(scratch.affinity.data()),
                          scratch.affinity.size_bytes()};
      }
    }
    for (std::size_t index = 0U; index < ranges.size(); ++index) {
      const auto current = ranges[index];
      if (current.begin == 0U || current.bytes == 0U ||
          current.bytes > std::numeric_limits<std::uintptr_t>::max() - current.begin) {
        throw std::invalid_argument("control scratch is empty or overflows");
      }
      for (std::size_t prior = 0U; prior < index; ++prior) {
        const auto other = ranges[prior];
        if (current.begin < other.begin + other.bytes &&
            other.begin < current.begin + current.bytes) {
          throw std::invalid_argument("retained control scratch aliases");
        }
      }
    }
  }

  auto observe_controls(DiscoveryResidencyRequest request) noexcept
      -> DiscoveryObservationStatus {
    if (request.phase > DiscoverySessionPhase::measurement ||
        request.moment > DiscoveryResidencyMoment::after) {
      return DiscoveryObservationStatus::rejected;
    }
    const auto index = static_cast<std::size_t>(request.phase) * 3U +
                       static_cast<std::size_t>(request.moment);
    if (index >= samples_.size()) {
      return DiscoveryObservationStatus::rejected;
    }
    auto& row = samples_[index];
    if (row.request.region_index != request.region_index ||
        row.request.offset_ticks != request.offset_ticks) {
      return DiscoveryObservationStatus::not_configured;
    }
    if (row.attempted) {
      return DiscoveryObservationStatus::rejected;
    }
    row.attempted = true;
    row.stop = DiscoveryControlStop::sampled;
    for (std::size_t role = 0U; role < 2U; ++role) {
      row.workers[role] = owners_[role]->sample(row.scratch[role]);
      const auto status = check_owner(index, role);
      if (status != DiscoveryControlStop::sampled &&
          row.stop == DiscoveryControlStop::sampled) {
        row.stop = status;
      }
    }
    const bool hardware_ok = hardware_.sample(plan_.hardware_state, row.hardware);
    if (!hardware_ok && row.stop == DiscoveryControlStop::sampled) {
      row.stop = DiscoveryControlStop::hardware_failure;
    }
    return row.stop == DiscoveryControlStop::sampled
               ? DiscoveryObservationStatus::accepted
               : DiscoveryObservationStatus::rejected;
  }
  auto control_group_complete(DiscoverySessionPhase phase,
                              DiscoveryResidencyMoment moment) const noexcept -> bool {
    if (phase > DiscoverySessionPhase::measurement ||
        moment > DiscoveryResidencyMoment::after) {
      return false;
    }
    const auto index =
        static_cast<std::size_t>(phase) * 3U + static_cast<std::size_t>(moment);
    return index < samples_.size() && samples_[index].attempted &&
           samples_[index].stop == DiscoveryControlStop::sampled;
  }
  auto query_pages(std::span<void* const> addresses, std::span<int> nodes) noexcept
      -> platform::PageResidencyQueryResult {
    return pages_.query_pages(addresses, nodes);
  }

private:
  auto check_owner(std::size_t index, std::size_t role) const noexcept
      -> DiscoveryControlStop {
    const auto observed = samples_[index].workers[role];
    if (!observed.has_value() || !observed->succeeded() ||
        !observed->stat_before.has_value() || !observed->stat_after.has_value() ||
        !observed->status.has_value()) {
      return DiscoveryControlStop::thread_read_failure;
    }
    const auto first = *observed->stat_before;
    const auto last = *observed->stat_after;
    const auto status = *observed->status;
    if (first.task_id != plan_.observed_owner_ids[role] ||
        last.task_id != first.task_id || status.task_id != first.task_id ||
        first.start_time_ticks != last.start_time_ticks || first.last_cpu < 0 ||
        last.last_cpu < 0 ||
        static_cast<std::uint32_t>(first.last_cpu) != plan_.cpus[role] ||
        static_cast<std::uint32_t>(last.last_cpu) != plan_.cpus[role] ||
        observed->affinity_cpu_count != 1U ||
        observed->singleton_affinity_cpu != plan_.cpus[role]) {
      return DiscoveryControlStop::owner_mismatch;
    }
    const auto baseline = samples_[(index / 3U) * 3U].workers[role];
    if (!baseline.has_value() || !baseline->succeeded() ||
        !baseline->stat_before.has_value() || !baseline->status.has_value()) {
      return DiscoveryControlStop::thread_read_failure;
    }
    const auto begin = *baseline->stat_before;
    const auto begin_status = *baseline->status;
    if (first.start_time_ticks != begin.start_time_ticks ||
        first.task_id != begin.task_id ||
        status.thread_group_id != begin_status.thread_group_id) {
      return DiscoveryControlStop::owner_mismatch;
    }
    if (first.minor_faults < begin.minor_faults ||
        last.minor_faults < first.minor_faults ||
        first.major_faults < begin.major_faults ||
        last.major_faults < first.major_faults ||
        status.voluntary_context_switches < begin_status.voluntary_context_switches ||
        status.involuntary_context_switches <
            begin_status.involuntary_context_switches) {
      return DiscoveryControlStop::counter_regression;
    }
    if (index % 3U != 0U) {
      const auto previous = samples_[index - 1U].workers[role];
      if (!previous.has_value() || !previous->succeeded() ||
          !previous->stat_after.has_value() || !previous->status.has_value()) {
        return DiscoveryControlStop::thread_read_failure;
      }
      if (first.minor_faults < previous->stat_after->minor_faults ||
          first.major_faults < previous->stat_after->major_faults ||
          status.voluntary_context_switches <
              previous->status->voluntary_context_switches ||
          status.involuntary_context_switches <
              previous->status->involuntary_context_switches) {
        return DiscoveryControlStop::counter_regression;
      }
    }
    const auto limit = plan_.limits[index / 3U][role];
    const auto exceeds = [](std::uint64_t delta,
                            std::optional<std::uint64_t> bound) noexcept {
      return bound.has_value() && delta > *bound;
    };
    if (exceeds(last.minor_faults - begin.minor_faults, limit.minor_faults) ||
        exceeds(last.major_faults - begin.major_faults, limit.major_faults) ||
        exceeds(status.voluntary_context_switches -
                    begin_status.voluntary_context_switches,
                limit.voluntary_switches) ||
        exceeds(status.involuntary_context_switches -
                    begin_status.involuntary_context_switches,
                limit.involuntary_switches)) {
      return DiscoveryControlStop::disturbance_limit;
    }
    return DiscoveryControlStop::sampled;
  }
  const DiscoveryControlPlan plan_;
  const std::array<ThreadMonitor*, 2U> owners_;
  PrefetchMonitor& hardware_;
  PageQuery& pages_;
  std::span<DiscoveryControlSample, 6U> samples_;
};

} // namespace cpu_prefetch::calibration

#endif
