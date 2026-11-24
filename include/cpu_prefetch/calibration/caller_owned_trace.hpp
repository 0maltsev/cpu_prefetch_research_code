#ifndef CPU_PREFETCH_CALIBRATION_CALLER_OWNED_TRACE_HPP
#define CPU_PREFETCH_CALIBRATION_CALLER_OWNED_TRACE_HPP

#include "cpu_prefetch/calibration/calibration.hpp"

#include <array>
#include <limits>
#include <stdexcept>

namespace cpu_prefetch::calibration {

// The caller owns the live typed buffers AND this object's storage. Construct
// and prepare it on its worker in that worker's dedicated mapped region.
// No other thread may inspect or change this state during capture.
class CallerOwnedRingDemandWorker final {
public:
  CallerOwnedRingDemandWorker(RingWorker worker, std::span<std::uint64_t> demand,
                              std::span<std::uint64_t> issue)
      : worker_(worker), demand_(demand), issue_(issue) {
    if ((worker != RingWorker::producer && worker != RingWorker::consumer) ||
        demand.empty() || demand.size() != issue.size() ||
        demand.size() >
            std::numeric_limits<std::size_t>::max() / sizeof(std::uint64_t)) {
      throw std::invalid_argument(
          "caller-owned trace requires valid role and equal nonzero buffers");
    }
  }
  CallerOwnedRingDemandWorker(const CallerOwnedRingDemandWorker&) = delete;
  auto operator=(const CallerOwnedRingDemandWorker&)
      -> CallerOwnedRingDemandWorker& = delete;

private:
  friend class CallerOwnedRingDemandTrace;
  [[nodiscard]] auto prepare() noexcept -> bool {
    if (prepared_ || demand_count_ != 0U || issue_count_ != 0U) {
      return false;
    }
    for (auto buffer : {demand_, issue_}) {
      for (auto& value : buffer) {
        volatile std::uint64_t* touched = &value;
        *touched = 0U;
      }
    }
    prepared_ = true;
    return true;
  }
  [[nodiscard]] auto record(std::uint64_t start, std::uint64_t end,
                            RingAttemptOutcome outcome) noexcept -> bool {
    if (!prepared_ || end < start || demand_count_ == demand_.size() ||
        (outcome != RingAttemptOutcome::advanced &&
         !(outcome == RingAttemptOutcome::full && worker_ == RingWorker::producer) &&
         !(outcome == RingAttemptOutcome::empty && worker_ == RingWorker::consumer))) {
      return false;
    }
    if (outcome == RingAttemptOutcome::advanced && previous_advance_.has_value() &&
        (start < *previous_advance_ || issue_count_ == issue_.size())) {
      return false;
    }
    demand_[demand_count_++] = end - start;
    if (outcome != RingAttemptOutcome::advanced) {
      ++nonadvancing_count_;
      return true;
    }
    if (previous_advance_.has_value()) {
      issue_[issue_count_++] = start - *previous_advance_;
    }
    previous_advance_ = start;
    return true;
  }
  [[nodiscard]] auto view() const noexcept -> RingWorkerDemandView {
    return {demand_.first(demand_count_), issue_.first(issue_count_),
            nonadvancing_count_};
  }

  RingWorker worker_;
  std::span<std::uint64_t> demand_;
  std::span<std::uint64_t> issue_;
  std::size_t demand_count_{0U};
  std::size_t issue_count_{0U};
  std::uint64_t nonadvancing_count_{0U};
  std::optional<std::uint64_t> previous_advance_;
  bool prepared_{false};
};

// A facade over two independently placed worker states. All six regions
// (two states and four buffers) must be disjoint. Construction checks their
// geometry, not their page residency or execution authority.
class CallerOwnedRingDemandTrace final {
public:
  CallerOwnedRingDemandTrace(CallerOwnedRingDemandWorker& producer,
                             CallerOwnedRingDemandWorker& consumer)
      : producer_(producer), consumer_(consumer), capacity_(producer.demand_.size()) {
    if (producer.worker_ != RingWorker::producer ||
        consumer.worker_ != RingWorker::consumer ||
        capacity_ != consumer.demand_.size()) {
      throw std::invalid_argument(
          "caller-owned trace requires matching producer and consumer buffers");
    }
    struct Range final {
      std::uintptr_t begin;
      std::size_t bytes;
    };
    const std::array ranges{
        Range{reinterpret_cast<std::uintptr_t>(&producer), sizeof(producer)},
        Range{reinterpret_cast<std::uintptr_t>(&consumer), sizeof(consumer)},
        Range{reinterpret_cast<std::uintptr_t>(producer.demand_.data()),
              producer.demand_.size_bytes()},
        Range{reinterpret_cast<std::uintptr_t>(producer.issue_.data()),
              producer.issue_.size_bytes()},
        Range{reinterpret_cast<std::uintptr_t>(consumer.demand_.data()),
              consumer.demand_.size_bytes()},
        Range{reinterpret_cast<std::uintptr_t>(consumer.issue_.data()),
              consumer.issue_.size_bytes()}};
    for (std::size_t index = 0U; index < ranges.size(); ++index) {
      const auto range = ranges[index];
      if (range.begin == 0U ||
          range.bytes > std::numeric_limits<std::uintptr_t>::max() - range.begin) {
        throw std::invalid_argument("caller-owned trace address range overflows");
      }
      for (std::size_t other = 0U; other < index; ++other) {
        const auto prior = ranges[other];
        if (range.begin < prior.begin + prior.bytes &&
            prior.begin < range.begin + range.bytes) {
          throw std::invalid_argument("caller-owned trace regions overlap");
        }
      }
    }
  }
  [[nodiscard]] auto prepare_worker(RingWorker worker) noexcept -> bool {
    auto* state = worker_state(worker);
    return state != nullptr && state->prepare();
  }
  [[nodiscard]] auto worker_prepared(RingWorker worker) const noexcept -> bool {
    const auto* state = worker_state(worker);
    return state != nullptr && state->prepared_;
  }
  [[nodiscard]] auto attempt_capacity() const noexcept -> std::size_t {
    return capacity_;
  }
  [[nodiscard]] auto record(RingWorker worker, std::uint64_t start, std::uint64_t end,
                            RingAttemptOutcome outcome) noexcept -> bool {
    auto* state = worker_state(worker);
    return state != nullptr && state->record(start, end, outcome);
  }
  [[nodiscard]] auto worker_series(RingWorker worker) const noexcept
      -> RingWorkerDemandView {
    const auto* state = worker_state(worker);
    return state == nullptr ? RingWorkerDemandView{} : state->view();
  }

private:
  [[nodiscard]] auto worker_state(RingWorker worker) const noexcept
      -> CallerOwnedRingDemandWorker* {
    return worker == RingWorker::producer   ? &producer_
           : worker == RingWorker::consumer ? &consumer_
                                            : nullptr;
  }
  CallerOwnedRingDemandWorker& producer_;
  CallerOwnedRingDemandWorker& consumer_;
  std::size_t capacity_;
};

} // namespace cpu_prefetch::calibration

#endif
