#include "cpu_prefetch/calibration/discovery_capture.hpp"
#include "cpu_prefetch/calibration/discovery_event_capture.hpp"

#include <gtest/gtest.h>

#include <array>
#include <atomic>
#include <limits>
#include <optional>
#include <stdexcept>

namespace {
namespace calibration = cpu_prefetch::calibration;
namespace queue = cpu_prefetch::queue;
namespace timing = cpu_prefetch::timing;
namespace workload = cpu_prefetch::workload;

template <typename Value>
auto required(const std::optional<Value>& value) -> const Value& {
  if (!value.has_value()) {
    throw std::logic_error("required test observation is absent");
  }
  return *value;
}

class ControlledClock final {
public:
  explicit ControlledClock(
      std::size_t fail_at = std::numeric_limits<std::size_t>::max())
      : fail_at_(fail_at) {}
  auto read() noexcept -> timing::ClockReadResult {
    const auto call = calls_++;
    return {call == fail_at_ ? timing::ClockReadStatus::call_failed
                             : timing::ClockReadStatus::ok,
            {0U, 10U * (call + 1U)}};
  }

private:
  std::size_t fail_at_;
  std::size_t calls_{0U};
};

auto make_arena() -> workload::EventArena {
  return workload::EventArena({8U, 64U, 4096U,
                               workload::MasterSeed::from_hex(std::string(64U, '0')),
                               "discovery-event-test"});
}

auto pointer_for(const void* event) -> queue::EventPointer {
  const auto pointer = queue::EventPointer::from(event);
  if (!pointer.has_value()) {
    throw std::logic_error("invalid test pointer");
  }
  return *pointer;
}

TEST(DiscoveryEventCapture, RetainsExactPrimaryBoundariesAndSameAcquireDemand) {
  auto arena = make_arena();
  queue::RingSpscQueue ring({8U}, {64U});
  calibration::RingDemandTrace trace(4U);
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::producer));
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::consumer));
  ControlledClock clock;
  calibration::DiscoveryProducerEventCapture producer;
  const auto produced = calibration::capture_discovery_producer_event(
      clock, arena, ring, trace, {19U}, 7U, {3U}, producer);
  ASSERT_EQ(produced.outcome, calibration::RingAttemptOutcome::advanced);
  ASSERT_TRUE(producer.primary.has_value());
  const auto& p = required(producer.primary);
  EXPECT_EQ(p.logical_sequence.value, 19U);
  EXPECT_EQ(p.record_index, arena.select({19U}).record_index);
  EXPECT_EQ(p.scheduled_arrival, 7U);
  EXPECT_EQ(p.producer_handle_begin.relative_picoseconds, 10U);
  EXPECT_EQ(p.record_lookup_completion.relative_picoseconds, 20U);
  EXPECT_EQ(p.enqueue_invocation.relative_picoseconds, 30U);
  ASSERT_TRUE(p.enqueue_linearization.has_value());
  EXPECT_EQ(required(p.enqueue_linearization).relative_picoseconds, 60U);
  EXPECT_EQ(p.enqueue_attempt_completion.relative_picoseconds, 70U);
  ASSERT_TRUE(p.accepted_ordinal.has_value());
  EXPECT_EQ(required(p.accepted_ordinal).value, 3U);
  EXPECT_EQ(required(producer.demand.before).sample.relative_picoseconds, 40U);
  EXPECT_EQ(required(producer.demand.after).sample.relative_picoseconds, 50U);
  calibration::DiscoveryConsumerEventCapture consumer;
  workload::ConsumerState state{17U};
  const auto consumed = calibration::capture_discovery_consumer_event(
      clock, arena, ring, trace, state, {3U}, consumer);
  ASSERT_EQ(consumed.outcome, calibration::RingAttemptOutcome::advanced);
  ASSERT_TRUE(consumer.primary.has_value());
  const auto& c = required(consumer.primary);
  EXPECT_EQ(c.consumed_ordinal.value, 3U);
  EXPECT_EQ(c.observed_record_index, p.record_index);
  EXPECT_EQ(c.dequeue_invocation.relative_picoseconds, 80U);
  EXPECT_EQ(required(consumer.demand.before).sample.relative_picoseconds, 90U);
  EXPECT_EQ(required(consumer.demand.after).sample.relative_picoseconds, 100U);
  EXPECT_EQ(c.dequeue_linearization.relative_picoseconds, 110U);
  EXPECT_EQ(c.dequeue_completion.relative_picoseconds, 120U);
  EXPECT_EQ(c.consumer_action_completion.relative_picoseconds, 130U);
  EXPECT_EQ(state,
            workload::mix_consumer_state({17U}, p.record_index,
                                         required(producer.selected).record->payload));
  EXPECT_EQ(trace.series().producer_demand_ticks, (std::vector<std::uint64_t>{10U}));
  EXPECT_EQ(trace.series().consumer_demand_ticks, (std::vector<std::uint64_t>{10U}));
}

TEST(DiscoveryEventCapture, FullAndEmptyKeepActualOutcomesWithoutInventedBoundaries) {
  auto arena = make_arena();
  queue::RingSpscQueue ring({1U}, {64U});
  calibration::RingDemandTrace trace(4U);
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::producer));
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::consumer));
  ControlledClock clock;
  calibration::DiscoveryProducerEventCapture producer;
  ASSERT_EQ(calibration::capture_discovery_producer_event(clock, arena, ring, trace,
                                                          {0U}, 0U, {0U}, producer)
                .outcome,
            calibration::RingAttemptOutcome::advanced);
  const auto full = calibration::capture_discovery_producer_event(
      clock, arena, ring, trace, {1U}, 0U, {1U}, producer);
  EXPECT_EQ(full.operation_outcome, calibration::RingAttemptOutcome::full);
  ASSERT_TRUE(producer.primary.has_value());
  EXPECT_EQ(required(producer.primary).outcome,
            cpu_prefetch::protocol::ProducerOutcome::full);
  EXPECT_FALSE(required(producer.primary).accepted_ordinal.has_value());
  EXPECT_FALSE(required(producer.primary).enqueue_linearization.has_value());
  EXPECT_FALSE(producer.enqueue_publication.has_value());
  workload::ConsumerState state{17U};
  calibration::DiscoveryConsumerEventCapture consumer;
  ASSERT_EQ(calibration::capture_discovery_consumer_event(clock, arena, ring, trace,
                                                          state, {0U}, consumer)
                .outcome,
            calibration::RingAttemptOutcome::advanced);
  const auto prior = state;
  EXPECT_EQ(calibration::capture_discovery_consumer_event(clock, arena, ring, trace,
                                                          state, {1U}, consumer)
                .outcome,
            calibration::RingAttemptOutcome::empty);
  EXPECT_TRUE(consumer.operation.has_value());
  EXPECT_FALSE(consumer.dequeue_observation.has_value());
  EXPECT_FALSE(consumer.dequeue_completion.has_value());
  EXPECT_FALSE(consumer.action_completion.has_value());
  EXPECT_FALSE(consumer.access.has_value());
  EXPECT_FALSE(consumer.primary.has_value());
  EXPECT_EQ(state, prior);
  EXPECT_EQ(trace.series().producer_full_count, 1U);
  EXPECT_EQ(trace.series().consumer_empty_count, 1U);
}

TEST(DiscoveryEventCapture, EveryProducerClockFailureRetainsItsActualOperationState) {
  constexpr std::array boundaries{
      calibration::DiscoveryCaptureBoundary::producer_handle_begin,
      calibration::DiscoveryCaptureBoundary::record_lookup_completion,
      calibration::DiscoveryCaptureBoundary::enqueue_invocation,
      calibration::DiscoveryCaptureBoundary::producer_demand_before,
      calibration::DiscoveryCaptureBoundary::producer_demand_after,
      calibration::DiscoveryCaptureBoundary::enqueue_publication,
      calibration::DiscoveryCaptureBoundary::enqueue_completion};
  for (std::size_t failure = 0U; failure < 7U; ++failure) {
    SCOPED_TRACE(failure);
    auto arena = make_arena();
    queue::RingSpscQueue ring({8U}, {64U});
    calibration::RingDemandTrace trace(4U);
    ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::producer));
    ControlledClock clock(failure);
    calibration::DiscoveryProducerEventCapture row;
    const auto result = calibration::capture_discovery_producer_event(
        clock, arena, ring, trace, {0U}, 0U, {0U}, row);
    EXPECT_EQ(result.outcome, calibration::RingAttemptOutcome::clock_failure);
    EXPECT_EQ(result.failed_clock_status, timing::ClockReadStatus::call_failed);
    EXPECT_EQ(row.failed_boundary, boundaries[failure]);
    EXPECT_FALSE(row.primary.has_value());
    EXPECT_EQ(result.operation_performed, failure >= 3U);
    EXPECT_EQ(ring.audit_quiescent().occupied_slots, failure >= 3U ? 1U : 0U);
    if (failure < 3U) {
      EXPECT_FALSE(row.demand.before.has_value());
      EXPECT_FALSE(row.demand.after.has_value());
      EXPECT_FALSE(result.operation_outcome.has_value());
      EXPECT_FALSE(result.before_status.has_value());
      EXPECT_FALSE(result.after_status.has_value());
    } else {
      EXPECT_EQ(result.operation_outcome, calibration::RingAttemptOutcome::advanced);
      EXPECT_TRUE(row.demand.before.has_value());
      EXPECT_TRUE(row.demand.after.has_value());
    }
  }
}

TEST(DiscoveryEventCapture,
     EveryConsumerClockFailureStillActsOnAnActualDequeuedRecord) {
  constexpr std::array boundaries{
      calibration::DiscoveryCaptureBoundary::dequeue_invocation,
      calibration::DiscoveryCaptureBoundary::consumer_demand_before,
      calibration::DiscoveryCaptureBoundary::consumer_demand_after,
      calibration::DiscoveryCaptureBoundary::dequeue_observation,
      calibration::DiscoveryCaptureBoundary::dequeue_completion,
      calibration::DiscoveryCaptureBoundary::consumer_action_completion};
  for (std::size_t failure = 0U; failure < 6U; ++failure) {
    SCOPED_TRACE(failure);
    auto arena = make_arena();
    const auto selected = arena.select({0U});
    queue::RingSpscQueue ring({8U}, {64U});
    ASSERT_EQ(ring.try_enqueue(pointer_for(selected.record)),
              queue::EnqueueResult::accepted);
    calibration::RingDemandTrace trace(4U);
    ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::consumer));
    ControlledClock clock(failure);
    workload::ConsumerState state{17U};
    calibration::DiscoveryConsumerEventCapture row;
    const auto result = calibration::capture_discovery_consumer_event(
        clock, arena, ring, trace, state, {0U}, row);
    EXPECT_EQ(result.outcome, calibration::RingAttemptOutcome::clock_failure);
    EXPECT_EQ(result.failed_clock_status, timing::ClockReadStatus::call_failed);
    EXPECT_EQ(row.failed_boundary, boundaries[failure]);
    EXPECT_FALSE(row.primary.has_value());
    EXPECT_EQ(result.operation_performed, failure != 0U);
    if (failure == 0U) {
      EXPECT_FALSE(row.operation.has_value());
      EXPECT_FALSE(row.access.has_value());
      EXPECT_EQ(state, workload::ConsumerState{17U});
      EXPECT_EQ(ring.audit_quiescent().occupied_slots, 1U);
    } else {
      EXPECT_EQ(result.operation_outcome, calibration::RingAttemptOutcome::advanced);
      ASSERT_TRUE(row.operation.has_value());
      EXPECT_EQ(required(row.operation).event, selected.record);
      ASSERT_TRUE(row.access.has_value());
      EXPECT_EQ(required(row.access).status, workload::RecordAccessStatus::valid);
      EXPECT_EQ(state, workload::mix_consumer_state({17U}, selected.record_index,
                                                    selected.record->payload));
      EXPECT_EQ(ring.audit_quiescent().occupied_slots, 0U);
    }
  }
}

TEST(DiscoveryEventCapture,
     PreOperationFailureDoesNotCountAnAttemptOrReuseOldClockFacts) {
  for (const auto failure : {0U, 7U}) {
    auto arena = make_arena();
    queue::RingSpscQueue ring({8U}, {64U});
    calibration::RingDemandTrace trace(8U);
    ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::producer));
    ControlledClock clock(failure);
    ControlledClock window_clock;
    calibration::DiscoveryProducerEventCapture row;
    auto attempt = [&]() noexcept {
      return calibration::capture_discovery_producer_event(clock, arena, ring, trace,
                                                           {0U}, 0U, {0U}, row);
    };
    std::atomic<bool> stop{false};
    const auto result = calibration::capture_discovery_worker(
        {calibration::RingWorker::producer, 0U, 1000U, 8U}, window_clock, attempt,
        stop);
    EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::capture_failure);
    EXPECT_EQ(result.attempts, failure == 0U ? 0U : 1U);
    EXPECT_EQ(result.advanced, result.attempts);
    EXPECT_FALSE(result.last_operation_outcome.has_value());
    EXPECT_FALSE(result.last_attempt_before_status.has_value());
    EXPECT_FALSE(result.last_attempt_after_status.has_value());
    EXPECT_EQ(result.failed_clock_status, timing::ClockReadStatus::call_failed);
    EXPECT_TRUE(stop.load());
  }
}

TEST(DiscoveryEventCapture, WorkerRetainsCountsAndOuterClockFailureAfterQueueAdvance) {
  for (const auto role :
       {calibration::RingWorker::producer, calibration::RingWorker::consumer}) {
    auto arena = make_arena();
    const auto selected = arena.select({0U});
    queue::RingSpscQueue ring({8U}, {64U});
    if (role == calibration::RingWorker::consumer) {
      ASSERT_EQ(ring.try_enqueue(pointer_for(selected.record)),
                queue::EnqueueResult::accepted);
    }
    calibration::RingDemandTrace trace(8U);
    ASSERT_TRUE(trace.prepare_worker(role));
    ControlledClock clock(role == calibration::RingWorker::producer ? 5U : 4U);
    ControlledClock window_clock;
    calibration::DiscoveryProducerEventCapture producer;
    calibration::DiscoveryConsumerEventCapture consumer;
    workload::ConsumerState state{17U};
    auto attempt = [&]() noexcept {
      return role == calibration::RingWorker::producer
                 ? calibration::capture_discovery_producer_event(
                       clock, arena, ring, trace, {0U}, 0U, {0U}, producer)
                 : calibration::capture_discovery_consumer_event(
                       clock, arena, ring, trace, state, {0U}, consumer);
    };
    std::atomic<bool> stop{false};
    const auto result = calibration::capture_discovery_worker(
        {role, 0U, 1000U, 8U}, window_clock, attempt, stop);
    EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::capture_failure);
    EXPECT_EQ(result.attempts, 1U);
    EXPECT_EQ(result.advanced, 1U);
    EXPECT_EQ(result.last_operation_outcome, calibration::RingAttemptOutcome::advanced);
    EXPECT_EQ(result.last_attempt_before_status, timing::ClockReadStatus::ok);
    EXPECT_EQ(result.last_attempt_after_status, timing::ClockReadStatus::ok);
    EXPECT_EQ(result.failed_clock_status, timing::ClockReadStatus::call_failed);
    EXPECT_TRUE(stop.load());
  }
}

TEST(DiscoveryEventCapture, TraceExhaustionRetainsPrimaryRowsAndOrdinaryAction) {
  auto arena = make_arena();
  queue::RingSpscQueue ring({8U}, {64U});
  calibration::RingDemandTrace trace(1U);
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::producer));
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::consumer));
  ControlledClock clock;
  calibration::DiscoveryProducerEventCapture producer;
  calibration::DiscoveryConsumerEventCapture consumer;
  workload::ConsumerState state{17U};
  workload::ConsumerState expected{17U};
  for (std::uint64_t sequence = 0U; sequence < 2U; ++sequence) {
    const auto expected_outcome = sequence == 0U
                                      ? calibration::RingAttemptOutcome::advanced
                                      : calibration::RingAttemptOutcome::trace_failure;
    EXPECT_EQ(calibration::capture_discovery_producer_event(
                  clock, arena, ring, trace, {sequence}, 0U, {sequence}, producer)
                  .outcome,
              expected_outcome);
    ASSERT_TRUE(producer.primary.has_value());
    EXPECT_EQ(calibration::capture_discovery_consumer_event(clock, arena, ring, trace,
                                                            state, {sequence}, consumer)
                  .outcome,
              expected_outcome);
    ASSERT_TRUE(consumer.primary.has_value());
    EXPECT_EQ(required(producer.primary).record_index,
              required(consumer.primary).observed_record_index);
    const auto selected = arena.select({sequence});
    expected = workload::mix_consumer_state(expected, selected.record_index,
                                            selected.record->payload);
  }
  EXPECT_EQ(state, expected);
  EXPECT_EQ(ring.audit_quiescent().occupied_slots, 0U);
  EXPECT_EQ(trace.series().producer_demand_ticks.size(), 1U);
  EXPECT_EQ(trace.series().consumer_demand_ticks.size(), 1U);
}

TEST(DiscoveryEventCapture, InvalidDequeuedPointerIsAnExplicitRecordFailure) {
  auto arena = make_arena();
  queue::RingSpscQueue ring({8U}, {64U});
  int outside = 71;
  ASSERT_EQ(ring.try_enqueue(pointer_for(&outside)), queue::EnqueueResult::accepted);
  calibration::RingDemandTrace trace(4U);
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::consumer));
  ControlledClock clock;
  workload::ConsumerState state{17U};
  calibration::DiscoveryConsumerEventCapture row;
  const auto result = calibration::capture_discovery_consumer_event(
      clock, arena, ring, trace, state, {0U}, row);
  EXPECT_EQ(result.outcome, calibration::RingAttemptOutcome::record_failure);
  EXPECT_EQ(result.operation_outcome, calibration::RingAttemptOutcome::advanced);
  EXPECT_TRUE(result.operation_performed);
  EXPECT_FALSE(result.failed_clock_status.has_value());
  ASSERT_TRUE(row.access.has_value());
  EXPECT_EQ(required(row.access).status, workload::RecordAccessStatus::outside_arena);
  EXPECT_EQ(state, workload::ConsumerState{17U});
  EXPECT_FALSE(row.primary.has_value());
  EXPECT_EQ(ring.audit_quiescent().occupied_slots, 0U);
  EXPECT_FALSE(trace.record(calibration::RingWorker::consumer, 80U, 90U,
                            calibration::RingAttemptOutcome::record_failure));
  EXPECT_EQ(trace.series().consumer_demand_ticks.size(), 1U);
}

} // namespace
