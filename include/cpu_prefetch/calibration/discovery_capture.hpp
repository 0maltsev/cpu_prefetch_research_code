#ifndef CPU_PREFETCH_CALIBRATION_DISCOVERY_CAPTURE_HPP
#define CPU_PREFETCH_CALIBRATION_DISCOVERY_CAPTURE_HPP

#include "cpu_prefetch/calibration/calibration.hpp"

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <limits>
#include <optional>

namespace cpu_prefetch::calibration {

enum class DiscoveryWorkerStop : std::uint8_t {
  fixed_deadline,
  trace_capacity,
  invalid_plan,
  clock_failure,
  clock_reversal,
  capture_failure,
  peer_stopped,
};

struct DiscoveryWorkerWindow final {
  RingWorker worker;
  std::uint64_t origin_ticks;
  std::uint64_t duration_ticks;
  std::uint64_t attempt_capacity;
};

struct DiscoveryWorkerResult final {
  DiscoveryWorkerStop stop;
  std::uint64_t attempts{0U};
  std::uint64_t advanced{0U};
  std::uint64_t full{0U};
  std::uint64_t empty{0U};
  std::optional<std::uint64_t> last_observed_tick{};
  std::optional<RingAttemptOutcome> last_attempt_outcome{};
  std::optional<RingAttemptOutcome> last_operation_outcome{};
  std::optional<timing::ClockReadStatus> last_attempt_before_status{};
  std::optional<timing::ClockReadStatus> last_attempt_after_status{};
  std::optional<timing::ClockReadStatus> failed_clock_status{};
};

template <typename Clock, typename CaptureAttempt>
[[nodiscard]] auto capture_discovery_worker(DiscoveryWorkerWindow window, Clock& clock,
                                            CaptureAttempt& capture_attempt,
                                            std::atomic<bool>& stop_requested) noexcept
    -> DiscoveryWorkerResult {
  static_assert(noexcept(clock.read()));
  static_assert(noexcept(capture_attempt()));
  static_assert(std::atomic<bool>::is_always_lock_free);
  DiscoveryWorkerResult result{DiscoveryWorkerStop::invalid_plan};
  if ((window.worker != RingWorker::producer &&
       window.worker != RingWorker::consumer) ||
      window.duration_ticks == 0U || window.attempt_capacity == 0U ||
      window.origin_ticks >
          std::numeric_limits<std::uint64_t>::max() - window.duration_ticks) {
    stop_requested.store(true, std::memory_order_release);
    return result;
  }
  const auto deadline = window.origin_ticks + window.duration_ticks;
  auto previous_tick = window.origin_ticks;
  for (;;) {
    if (stop_requested.load(std::memory_order_acquire)) {
      result.stop = DiscoveryWorkerStop::peer_stopped;
      return result;
    }
    const auto observed = clock.read();
    if (observed.status != timing::ClockReadStatus::ok) {
      result.stop = DiscoveryWorkerStop::clock_failure;
      result.failed_clock_status = observed.status;
      stop_requested.store(true, std::memory_order_release);
      return result;
    }
    const auto now = observed.sample.relative_picoseconds;
    result.last_observed_tick = now;
    if (now < previous_tick) {
      result.stop = DiscoveryWorkerStop::clock_reversal;
      stop_requested.store(true, std::memory_order_release);
      return result;
    }
    previous_tick = now;
    if (now >= deadline) {
      result.stop = DiscoveryWorkerStop::fixed_deadline;
      return result;
    }
    if (result.attempts == window.attempt_capacity) {
      result.stop = DiscoveryWorkerStop::trace_capacity;
      stop_requested.store(true, std::memory_order_release);
      return result;
    }
    const auto captured = capture_attempt();
    ++result.attempts;
    result.last_attempt_outcome = captured.outcome;
    result.last_operation_outcome = captured.operation_outcome;
    result.last_attempt_before_status = captured.before_status;
    result.last_attempt_after_status = captured.after_status;
    const auto operation = captured.operation_outcome.value_or(captured.outcome);
    bool valid_outcome = captured.outcome == operation;
    if (operation == RingAttemptOutcome::advanced) {
      ++result.advanced;
    } else if (operation == RingAttemptOutcome::full &&
               window.worker == RingWorker::producer) {
      ++result.full;
    } else if (operation == RingAttemptOutcome::empty &&
               window.worker == RingWorker::consumer) {
      ++result.empty;
    } else {
      valid_outcome = false;
    }
    if (!valid_outcome || captured.before_status != timing::ClockReadStatus::ok ||
        captured.after_status != timing::ClockReadStatus::ok) {
      result.stop = DiscoveryWorkerStop::capture_failure;
      if (captured.before_status != timing::ClockReadStatus::ok) {
        result.failed_clock_status = captured.before_status;
      } else if (captured.after_status != timing::ClockReadStatus::ok) {
        result.failed_clock_status = captured.after_status;
      }
      stop_requested.store(true, std::memory_order_release);
      return result;
    }
  }
}

template <typename Clock, typename CaptureAttempt, typename Trace>
[[nodiscard]] auto
capture_prepared_discovery_worker(DiscoveryWorkerWindow window, Clock& clock,
                                  CaptureAttempt& capture_attempt, Trace& trace,
                                  std::atomic<bool>& stop_requested) noexcept
    -> DiscoveryWorkerResult {
  if (!trace.worker_prepared(window.worker) ||
      window.attempt_capacity != trace.attempt_capacity()) {
    stop_requested.store(true, std::memory_order_release);
    return {DiscoveryWorkerStop::invalid_plan};
  }
  const auto series = trace.worker_series(window.worker);
  if (!series.demand_ticks.empty() || !series.issue_ticks.empty()) {
    stop_requested.store(true, std::memory_order_release);
    return {DiscoveryWorkerStop::invalid_plan};
  }
  return capture_discovery_worker(window, clock, capture_attempt, stop_requested);
}

template <typename Trace>
[[nodiscard]] auto validate_quiescent_discovery_trace(RingWorker worker,
                                                      DiscoveryWorkerResult result,
                                                      const Trace& trace) noexcept
    -> DiscoveryWorkerResult {
  if (!trace.worker_prepared(worker)) {
    result.stop = DiscoveryWorkerStop::invalid_plan;
    return result;
  }
  const auto series = trace.worker_series(worker);
  const auto demand = series.demand_ticks;
  const auto issue = series.issue_ticks;
  if (result.stop == DiscoveryWorkerStop::fixed_deadline ||
      result.stop == DiscoveryWorkerStop::trace_capacity ||
      result.stop == DiscoveryWorkerStop::peer_stopped) {
    const auto expected_issues = result.advanced == 0U ? 0U : result.advanced - 1U;
    if (demand.size() != result.attempts || issue.size() != expected_issues ||
        series.nonadvancing_count != result.full + result.empty ||
        std::any_of(demand.begin(), demand.end(),
                    [](auto value) { return value == 0U; }) ||
        std::any_of(issue.begin(), issue.end(),
                    [](auto value) { return value == 0U; })) {
      result.stop = DiscoveryWorkerStop::capture_failure;
    }
  }
  return result;
}

enum class DiscoveryDrainStop : std::uint8_t {
  complete,
  invalid_plan,
  clock_failure,
  clock_reversal,
  fixed_deadline,
  attempt_capacity,
  consumer_failure,
  count_mismatch,
  reset_failure,
};

struct DiscoveryDrainWindow final {
  std::uint64_t origin_ticks;
  std::uint64_t duration_ticks;
  std::uint64_t attempt_capacity;
  std::uint64_t expected_pending;
  bool reset_after_drain;
};

struct DiscoveryDrainResult final {
  DiscoveryDrainStop stop;
  std::uint64_t attempts{0U};
  std::uint64_t dequeued{0U};
  std::optional<std::uint64_t> last_observed_tick{};
  std::optional<timing::ClockReadStatus> failed_clock_status{};
  std::optional<queue::RingQuiescentAudit> final_audit{};
  bool reset_verified{false};
};

// Both capture workers must be quiescent before this consumer-owned drain.
// consume must preserve the ordinary event validation/checksum action.
template <typename Clock, typename Consume>
[[nodiscard]] auto
drain_discovery_ring_quiescent(DiscoveryDrainWindow window, Clock& clock,
                               queue::RingSpscQueue& ring, Consume& consume) noexcept
    -> DiscoveryDrainResult {
  static_assert(noexcept(clock.read()));
  static_assert(noexcept(consume(static_cast<const void*>(nullptr))));
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
    const auto dequeued = ring.try_dequeue();
    ++result.attempts;
    if (dequeued.status == queue::DequeueStatus::item) {
      ++result.dequeued;
      if (!consume(dequeued.event)) {
        result.stop = DiscoveryDrainStop::consumer_failure;
        return result;
      }
      if (result.dequeued > window.expected_pending) {
        result.stop = DiscoveryDrainStop::count_mismatch;
        return result;
      }
      continue;
    }
    result.final_audit = ring.audit_quiescent();
    if (dequeued.status != queue::DequeueStatus::empty ||
        result.dequeued != window.expected_pending ||
        result.final_audit->occupied_slots != 0U ||
        !result.final_audit->positions_in_range) {
      result.stop = DiscoveryDrainStop::count_mismatch;
      return result;
    }
    if (window.reset_after_drain) {
      if (!ring.reset_quiescent()) {
        result.stop = DiscoveryDrainStop::reset_failure;
        return result;
      }
      const auto reset_audit = ring.audit_quiescent();
      result.reset_verified =
          reset_audit.occupied_slots == 0U && reset_audit.positions_in_range &&
          reset_audit.producer_position == 0U && reset_audit.consumer_position == 0U;
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
