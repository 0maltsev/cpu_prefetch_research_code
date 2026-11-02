#ifndef CPU_PREFETCH_CALIBRATION_DISCOVERY_OBSERVED_DRAIN_HPP
#define CPU_PREFETCH_CALIBRATION_DISCOVERY_OBSERVED_DRAIN_HPP

#include "cpu_prefetch/calibration/discovery_capture.hpp"

namespace cpu_prefetch::calibration {

struct DiscoveryObservedDrainPoll final {
  RingCaptureResult capture;
  std::optional<queue::DequeueResult> operation;
};

// Poll owns real event capture, ordinary action and caller-owned retention.
// Finish verifies the exact full sequence while both workers are quiescent,
// before a possible logical reset. Neither callback may allocate or throw.
template <typename Clock, typename Poll, typename Finish>
[[nodiscard]] auto drain_discovery_ring_observed(DiscoveryDrainWindow window,
                                                 Clock& clock,
                                                 queue::RingSpscQueue& ring, Poll& poll,
                                                 Finish& finish) noexcept
    -> DiscoveryDrainResult {
  static_assert(noexcept(clock.read()));
  static_assert(noexcept(poll()));
  static_assert(noexcept(finish()));
  DiscoveryDrainResult result{DiscoveryDrainStop::invalid_plan};
  if (window.duration_ticks == 0U || window.attempt_capacity == 0U ||
      window.origin_ticks >
          std::numeric_limits<std::uint64_t>::max() - window.duration_ticks) {
    return result;
  }
  const auto deadline = window.origin_ticks + window.duration_ticks;
  auto previous_tick = window.origin_ticks;
  for (;;) {
    const auto observed = clock.read();
    if (observed.status != timing::ClockReadStatus::ok) {
      result.stop = DiscoveryDrainStop::clock_failure;
      result.failed_clock_status = observed.status;
      return result;
    }
    const auto now = observed.sample.relative_picoseconds;
    result.last_observed_tick = now;
    if (now < previous_tick) {
      result.stop = DiscoveryDrainStop::clock_reversal;
      return result;
    }
    previous_tick = now;
    if (now >= deadline) {
      result.stop = DiscoveryDrainStop::fixed_deadline;
      return result;
    }
    if (result.attempts == window.attempt_capacity) {
      result.stop = DiscoveryDrainStop::attempt_capacity;
      return result;
    }
    const auto captured = poll();
    const auto& capture = captured.capture;
    if (capture.operation_performed) {
      ++result.attempts;
    }
    if (capture.operation_performed && captured.operation.has_value() &&
        captured.operation->status == queue::DequeueStatus::item) {
      ++result.dequeued;
    }
    if (capture.failed_clock_status.has_value()) {
      result.stop = DiscoveryDrainStop::clock_failure;
      result.failed_clock_status = capture.failed_clock_status;
      return result;
    }
    if (capture.before_status.has_value() &&
        capture.before_status != timing::ClockReadStatus::ok) {
      result.stop = DiscoveryDrainStop::clock_failure;
      result.failed_clock_status = capture.before_status;
      return result;
    }
    if (capture.after_status.has_value() &&
        capture.after_status != timing::ClockReadStatus::ok) {
      result.stop = DiscoveryDrainStop::clock_failure;
      result.failed_clock_status = capture.after_status;
      return result;
    }
    if (!capture.operation_performed || !captured.operation.has_value() ||
        capture.before_status != timing::ClockReadStatus::ok ||
        capture.after_status != timing::ClockReadStatus::ok) {
      result.stop = DiscoveryDrainStop::consumer_failure;
      return result;
    }
    const auto operation = *captured.operation;
    const auto expected_outcome = operation.status == queue::DequeueStatus::item
                                      ? RingAttemptOutcome::advanced
                                      : RingAttemptOutcome::empty;
    if (capture.outcome != expected_outcome ||
        capture.operation_outcome != expected_outcome ||
        (operation.status != queue::DequeueStatus::item &&
         operation.status != queue::DequeueStatus::empty)) {
      result.stop = DiscoveryDrainStop::consumer_failure;
      return result;
    }
    if (result.dequeued > window.expected_pending) {
      result.stop = DiscoveryDrainStop::count_mismatch;
      return result;
    }
    if (operation.status == queue::DequeueStatus::item) {
      continue;
    }
    const auto audit = ring.audit_quiescent();
    result.final_audit = audit;
    if (result.dequeued != window.expected_pending || audit.occupied_slots != 0U ||
        !audit.positions_in_range) {
      result.stop = DiscoveryDrainStop::count_mismatch;
      return result;
    }
    if (!finish()) {
      result.stop = DiscoveryDrainStop::consumer_failure;
      return result;
    }
    if (window.reset_after_drain) {
      if (!ring.reset_quiescent()) {
        result.stop = DiscoveryDrainStop::reset_failure;
        return result;
      }
      const auto reset = ring.audit_quiescent();
      result.reset_verified = reset.occupied_slots == 0U && reset.positions_in_range &&
                              reset.producer_position == 0U &&
                              reset.consumer_position == 0U;
      if (!result.reset_verified) {
        result.stop = DiscoveryDrainStop::reset_failure;
        return result;
      }
    }
    result.stop = DiscoveryDrainStop::complete;
    return result;
  }
}

} // namespace cpu_prefetch::calibration

#endif
