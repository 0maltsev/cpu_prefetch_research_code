#include "cpu_prefetch/calibration/discovery_capture.hpp"

#include <gtest/gtest.h>

#include <array>
#include <atomic>
#include <limits>
#include <stdexcept>
#include <thread>
#include <utility>
#include <vector>

namespace {

namespace calibration = cpu_prefetch::calibration;
namespace queue = cpu_prefetch::queue;
namespace timing = cpu_prefetch::timing;

class SequenceClock final {
public:
  explicit SequenceClock(std::vector<std::uint64_t> values)
      : values_(std::move(values)) {}
  [[nodiscard]] auto read() noexcept -> timing::ClockReadResult {
    if (position_ == values_.size()) {
      return {timing::ClockReadStatus::call_failed, {0U, 0U}};
    }
    return {timing::ClockReadStatus::ok, {0U, values_[position_++]}};
  }

private:
  std::vector<std::uint64_t> values_;
  std::size_t position_{0U};
};

class AtomicClock final {
public:
  [[nodiscard]] auto read() noexcept -> timing::ClockReadResult {
    return {timing::ClockReadStatus::ok,
            {0U, ticks_.fetch_add(1U, std::memory_order_relaxed)}};
  }

private:
  std::atomic<std::uint64_t> ticks_{0U};
};

struct SuccessfulAttempt final {
  std::uint64_t calls{0U};
  [[nodiscard]] auto operator()() noexcept -> calibration::RingCaptureResult {
    ++calls;
    return {calibration::RingAttemptOutcome::advanced, timing::ClockReadStatus::ok,
            timing::ClockReadStatus::ok};
  }
};

[[nodiscard]] auto event_pointer_for(const void* value) -> queue::EventPointer {
  const auto pointer = queue::EventPointer::from(value);
  if (pointer.has_value()) {
    return pointer.value();
  }
  throw std::logic_error("synthetic event pointer is invalid");
}

TEST(DiscoveryCaptureWindow, StopsAtDeadlineWithoutRequestingAnotherAttempt) {
  SequenceClock clock({5U, 7U, 9U});
  SuccessfulAttempt attempt;
  std::atomic<bool> stop{false};
  const auto result = calibration::capture_discovery_worker(
      {calibration::RingWorker::producer, 5U, 4U, 100U}, clock, attempt, stop);
  EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::fixed_deadline);
  EXPECT_EQ(result.attempts, 2U);
  EXPECT_EQ(result.advanced, 2U);
  EXPECT_EQ(result.last_observed_tick, 9U);
  EXPECT_EQ(attempt.calls, 2U);
  EXPECT_FALSE(stop.load());
}

TEST(DiscoveryCaptureWindow, AlreadyExpiredWindowMakesNoAttempt) {
  SequenceClock clock({10U});
  SuccessfulAttempt attempt;
  std::atomic<bool> stop{false};
  const auto result = calibration::capture_discovery_worker(
      {calibration::RingWorker::consumer, 0U, 10U, 100U}, clock, attempt, stop);
  EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::fixed_deadline);
  EXPECT_EQ(attempt.calls, 0U);
}

TEST(DiscoveryCaptureWindow, TraceCapacityStopsBeforeAnOverflowingAttempt) {
  SequenceClock clock({0U, 1U, 2U});
  SuccessfulAttempt attempt;
  std::atomic<bool> stop{false};
  const auto result = calibration::capture_discovery_worker(
      {calibration::RingWorker::producer, 0U, 100U, 2U}, clock, attempt, stop);
  EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::trace_capacity);
  EXPECT_EQ(attempt.calls, 2U);
  EXPECT_TRUE(stop.load());
}

TEST(DiscoveryCaptureWindow, DeadlineWinsWhenTraceIsExactlyFullAtHorizon) {
  SequenceClock clock({0U, 1U, 10U});
  SuccessfulAttempt attempt;
  std::atomic<bool> stop{false};
  const auto result = calibration::capture_discovery_worker(
      {calibration::RingWorker::producer, 0U, 10U, 2U}, clock, attempt, stop);
  EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::fixed_deadline);
  EXPECT_EQ(attempt.calls, 2U);
  EXPECT_FALSE(stop.load());
}

TEST(DiscoveryCaptureWindow, InvalidAndOverflowingPlansFailBeforeClockOrQueueWork) {
  constexpr auto maximum = std::numeric_limits<std::uint64_t>::max();
  const std::array plans{
      calibration::DiscoveryWorkerWindow{calibration::RingWorker::producer, 0U, 0U, 1U},
      calibration::DiscoveryWorkerWindow{calibration::RingWorker::producer, 0U, 1U, 0U},
      calibration::DiscoveryWorkerWindow{calibration::RingWorker::producer, maximum, 1U,
                                         1U},
  };
  for (const auto plan : plans) {
    SequenceClock clock({});
    SuccessfulAttempt attempt;
    std::atomic<bool> stop{false};
    const auto result =
        calibration::capture_discovery_worker(plan, clock, attempt, stop);
    EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::invalid_plan);
    EXPECT_EQ(attempt.calls, 0U);
    EXPECT_FALSE(result.last_observed_tick.has_value());
    EXPECT_TRUE(stop.load());
  }
}

TEST(DiscoveryCaptureWindow, ClockFailureRetainsPartialCountsAndTheActualStatus) {
  SequenceClock clock({0U});
  SuccessfulAttempt attempt;
  std::atomic<bool> stop{false};
  const auto result = calibration::capture_discovery_worker(
      {calibration::RingWorker::producer, 0U, 10U, 100U}, clock, attempt, stop);
  EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::clock_failure);
  EXPECT_EQ(result.attempts, 1U);
  EXPECT_EQ(result.last_observed_tick, 0U);
  EXPECT_EQ(result.failed_clock_status, timing::ClockReadStatus::call_failed);
  EXPECT_TRUE(stop.load());
}

TEST(DiscoveryCaptureWindow, BackwardOrBeforeOriginClockStopsWithoutAnotherAttempt) {
  for (const auto& values :
       {std::vector<std::uint64_t>{5U, 4U}, std::vector<std::uint64_t>{4U}}) {
    SequenceClock clock(values);
    SuccessfulAttempt attempt;
    std::atomic<bool> stop{false};
    const auto result = calibration::capture_discovery_worker(
        {calibration::RingWorker::producer, 5U, 10U, 100U}, clock, attempt, stop);
    EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::clock_reversal);
    EXPECT_LE(attempt.calls, 1U);
    EXPECT_EQ(result.last_observed_tick, 4U);
    EXPECT_TRUE(stop.load());
  }
}

TEST(DiscoveryCaptureWindow, CancellationDoesNotFabricateClockEvidence) {
  SequenceClock clock({});
  SuccessfulAttempt attempt;
  std::atomic<bool> stop{true};
  const auto result = calibration::capture_discovery_worker(
      {calibration::RingWorker::consumer, 0U, 10U, 100U}, clock, attempt, stop);
  EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::peer_stopped);
  EXPECT_EQ(attempt.calls, 0U);
  EXPECT_FALSE(result.last_observed_tick.has_value());
  EXPECT_FALSE(result.last_attempt_before_status.has_value());
  EXPECT_FALSE(result.last_attempt_after_status.has_value());
}

TEST(DiscoveryCaptureWindow, CaptureFailureAndWrongWorkerOutcomeStopPeers) {
  for (const auto outcome : {calibration::RingAttemptOutcome::advanced,
                             calibration::RingAttemptOutcome::clock_failure,
                             calibration::RingAttemptOutcome::trace_failure,
                             calibration::RingAttemptOutcome::empty}) {
    SequenceClock clock({0U});
    std::atomic<bool> stop{false};
    auto attempt = [outcome]() noexcept -> calibration::RingCaptureResult {
      return {outcome, timing::ClockReadStatus::ok,
              timing::ClockReadStatus::call_failed};
    };
    const auto result = calibration::capture_discovery_worker(
        {calibration::RingWorker::producer, 0U, 10U, 100U}, clock, attempt, stop);
    EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::capture_failure);
    EXPECT_EQ(result.attempts, 1U);
    EXPECT_EQ(result.last_attempt_outcome, outcome);
    EXPECT_EQ(result.last_attempt_before_status, timing::ClockReadStatus::ok);
    EXPECT_EQ(result.last_attempt_after_status, timing::ClockReadStatus::call_failed);
    EXPECT_EQ(result.failed_clock_status, timing::ClockReadStatus::call_failed);
    EXPECT_TRUE(stop.load());
  }
}

TEST(DiscoveryCaptureWindow, RealRingTraceRetainsFullAttemptsWithoutGrowingStorage) {
  queue::RingSpscQueue ring({1U}, {64U});
  int event = 7;
  const auto event_pointer = event_pointer_for(&event);
  calibration::RingDemandTrace trace{10U};
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::producer));
  const auto capacity_before = trace.series().producer_demand_ticks.capacity();
  SequenceClock clock({0U, 1U, 2U, 3U, 4U, 5U, 6U, 7U, 8U, 9U});
  std::atomic<bool> stop{false};
  auto attempt = [&]() noexcept {
    return calibration::capture_producer_ring_demand(clock, ring, event_pointer, trace);
  };
  const auto result = calibration::capture_prepared_discovery_worker(
      {calibration::RingWorker::producer, 0U, 7U, 10U}, clock, attempt, trace, stop);
  EXPECT_EQ(calibration::validate_quiescent_discovery_trace(
                calibration::RingWorker::producer, result, trace)
                .stop,
            calibration::DiscoveryWorkerStop::fixed_deadline);
  EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::fixed_deadline);
  EXPECT_EQ(result.attempts, 3U);
  EXPECT_EQ(result.advanced, 1U);
  EXPECT_EQ(result.full, 2U);
  EXPECT_EQ(trace.series().producer_full_count, 2U);
  EXPECT_EQ(trace.series().producer_demand_ticks,
            (std::vector<std::uint64_t>{1U, 1U, 1U}));
  EXPECT_EQ(trace.series().producer_demand_ticks.capacity(), capacity_before);
  EXPECT_EQ(ring.try_dequeue().event, &event);
}

TEST(DiscoveryCaptureWindow, PreparationTouchesOnlyOwnerBuffersAndCannotEraseData) {
  calibration::RingDemandTrace trace{8U};
  const auto capacity_before = trace.series().producer_demand_ticks.capacity();
  EXPECT_FALSE(trace.worker_prepared(calibration::RingWorker::producer));
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::producer));
  EXPECT_TRUE(trace.worker_prepared(calibration::RingWorker::producer));
  EXPECT_FALSE(trace.worker_prepared(calibration::RingWorker::consumer));
  EXPECT_EQ(trace.series().producer_demand_ticks.capacity(), capacity_before);
  EXPECT_TRUE(trace.series().producer_demand_ticks.empty());
  EXPECT_FALSE(trace.prepare_worker(calibration::RingWorker::producer));
  ASSERT_TRUE(trace.record(calibration::RingWorker::consumer, 1U, 2U,
                           calibration::RingAttemptOutcome::advanced));
  EXPECT_FALSE(trace.prepare_worker(calibration::RingWorker::consumer));
  EXPECT_EQ(trace.series().consumer_demand_ticks.size(), 1U);
}

TEST(DiscoveryCaptureWindow, UnpreparedOrMismatchedTraceCannotStart) {
  for (const bool prepare : {false, true}) {
    calibration::RingDemandTrace trace{8U};
    if (prepare) {
      ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::producer));
    }
    SequenceClock clock({});
    SuccessfulAttempt attempt;
    std::atomic<bool> stop{false};
    const auto capacity = prepare ? 7U : 8U;
    const auto result = calibration::capture_prepared_discovery_worker(
        {calibration::RingWorker::producer, 0U, 10U, capacity}, clock, attempt, trace,
        stop);
    EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::invalid_plan);
    EXPECT_EQ(attempt.calls, 0U);
    EXPECT_FALSE(result.last_observed_tick.has_value());
  }
}

TEST(DiscoveryCaptureWindow, ClaimedAttemptsWithoutMatchingTraceFailClosed) {
  calibration::RingDemandTrace trace{8U};
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::producer));
  SequenceClock clock({0U, 10U});
  SuccessfulAttempt attempt;
  std::atomic<bool> stop{false};
  const auto result = calibration::capture_prepared_discovery_worker(
      {calibration::RingWorker::producer, 0U, 10U, 8U}, clock, attempt, trace, stop);
  EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::fixed_deadline);
  EXPECT_EQ(calibration::validate_quiescent_discovery_trace(
                calibration::RingWorker::producer, result, trace)
                .stop,
            calibration::DiscoveryWorkerStop::capture_failure);
  EXPECT_EQ(result.attempts, 1U);
  EXPECT_FALSE(stop.load());
}

TEST(DiscoveryCaptureWindow, NonpositiveObservationsFailWithoutDeletingTheirEvidence) {
  for (const bool zero_demand : {true, false}) {
    calibration::RingDemandTrace trace{4U};
    ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::producer));
    SequenceClock clock(zero_demand ? std::vector<std::uint64_t>{0U, 10U}
                                    : std::vector<std::uint64_t>{0U, 1U, 10U});
    std::atomic<bool> stop{false};
    auto attempt = [&]() noexcept -> calibration::RingCaptureResult {
      const auto recorded =
          trace.record(calibration::RingWorker::producer, 5U, zero_demand ? 5U : 6U,
                       calibration::RingAttemptOutcome::advanced);
      return {recorded ? calibration::RingAttemptOutcome::advanced
                       : calibration::RingAttemptOutcome::trace_failure,
              timing::ClockReadStatus::ok, timing::ClockReadStatus::ok};
    };
    const auto result = calibration::capture_prepared_discovery_worker(
        {calibration::RingWorker::producer, 0U, 10U, 4U}, clock, attempt, trace, stop);
    EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::fixed_deadline);
    EXPECT_EQ(calibration::validate_quiescent_discovery_trace(
                  calibration::RingWorker::producer, result, trace)
                  .stop,
              calibration::DiscoveryWorkerStop::capture_failure);
    EXPECT_EQ(result.advanced, zero_demand ? 1U : 2U);
    EXPECT_FALSE(stop.load());
    if (zero_demand) {
      EXPECT_EQ(trace.series().producer_demand_ticks, (std::vector<std::uint64_t>{0U}));
    } else {
      EXPECT_EQ(trace.series().producer_issue_ticks, (std::vector<std::uint64_t>{0U}));
    }
  }
}

TEST(DiscoveryCaptureWindow, ConcurrentRealQueueWorkersStopAndReconcileAfterDrain) {
  queue::RingSpscQueue ring({64U}, {64U});
  int event = 7;
  const auto event_pointer = event_pointer_for(&event);
  calibration::RingDemandTrace trace{50'000U};
  AtomicClock clock;
  std::atomic<bool> stop{false};
  calibration::DiscoveryWorkerResult producer_result{
      calibration::DiscoveryWorkerStop::invalid_plan};
  calibration::DiscoveryWorkerResult consumer_result{
      calibration::DiscoveryWorkerStop::invalid_plan};
  std::thread producer([&] {
    if (!trace.prepare_worker(calibration::RingWorker::producer)) {
      stop.store(true);
      return;
    }
    auto attempt = [&]() noexcept {
      return calibration::capture_producer_ring_demand(clock, ring, event_pointer,
                                                       trace);
    };
    producer_result = calibration::capture_prepared_discovery_worker(
        {calibration::RingWorker::producer, 0U, 10'000U, 50'000U}, clock, attempt,
        trace, stop);
  });
  std::thread consumer([&] {
    if (!trace.prepare_worker(calibration::RingWorker::consumer)) {
      stop.store(true);
      return;
    }
    auto attempt = [&]() noexcept {
      return calibration::capture_consumer_ring_demand(clock, ring, trace);
    };
    consumer_result = calibration::capture_prepared_discovery_worker(
        {calibration::RingWorker::consumer, 0U, 10'000U, 50'000U}, clock, attempt,
        trace, stop);
  });
  producer.join();
  consumer.join();
  producer_result = calibration::validate_quiescent_discovery_trace(
      calibration::RingWorker::producer, producer_result, trace);
  consumer_result = calibration::validate_quiescent_discovery_trace(
      calibration::RingWorker::consumer, consumer_result, trace);
  EXPECT_EQ(producer_result.stop, calibration::DiscoveryWorkerStop::fixed_deadline);
  EXPECT_EQ(consumer_result.stop, calibration::DiscoveryWorkerStop::fixed_deadline);
  std::uint64_t drained = 0U;
  while (ring.try_dequeue().status == queue::DequeueStatus::item) {
    ++drained;
  }
  EXPECT_EQ(producer_result.advanced, consumer_result.advanced + drained);
  EXPECT_EQ(trace.series().producer_demand_ticks.size(), producer_result.attempts);
  EXPECT_EQ(trace.series().consumer_demand_ticks.size(), consumer_result.attempts);
  EXPECT_EQ(ring.audit_quiescent().occupied_slots, 0U);
  EXPECT_TRUE(ring.reset_quiescent());
}

} // namespace
