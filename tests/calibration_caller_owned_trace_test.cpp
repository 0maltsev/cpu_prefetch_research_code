#include "cpu_prefetch/calibration/caller_owned_trace.hpp"
#include "cpu_prefetch/calibration/discovery_capture.hpp"
#include "cpu_prefetch/calibration/discovery_consumer_capture.hpp"
#include "cpu_prefetch/workload/records.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <stdexcept>
#include <thread>

namespace {
namespace calibration = cpu_prefetch::calibration;
namespace queue = cpu_prefetch::queue;
namespace timing = cpu_prefetch::timing;
namespace workload = cpu_prefetch::workload;
using calibration::CallerOwnedRingDemandTrace;
using calibration::CallerOwnedRingDemandWorker;
using calibration::RingAttemptOutcome;
using calibration::RingWorker;

template <std::size_t Capacity> struct TraceStorage final {
  std::array<std::uint64_t, Capacity> producer_demand{};
  std::array<std::uint64_t, Capacity> producer_issue{};
  std::array<std::uint64_t, Capacity> consumer_demand{};
  std::array<std::uint64_t, Capacity> consumer_issue{};
  CallerOwnedRingDemandWorker producer{RingWorker::producer, producer_demand,
                                       producer_issue};
  CallerOwnedRingDemandWorker consumer{RingWorker::consumer, consumer_demand,
                                       consumer_issue};
  CallerOwnedRingDemandTrace trace{producer, consumer};
};

class IncrementingClock final {
public:
  [[nodiscard]] auto read() noexcept -> timing::ClockReadResult {
    return {timing::ClockReadStatus::ok, {0U, tick_++}};
  }

private:
  std::uint64_t tick_{0U};
};

auto pointer_for(const void* event) -> queue::EventPointer {
  const auto pointer = queue::EventPointer::from(event);
  if (!pointer.has_value()) {
    throw std::logic_error("invalid test event");
  }
  return *pointer;
}

TEST(CallerOwnedDemandTrace, MatchesExistingDemandAndAdvancingIssueDefinitions) {
  TraceStorage<8U> storage;
  calibration::RingDemandTrace owned(8U);
  for (const auto role : {RingWorker::producer, RingWorker::consumer}) {
    ASSERT_TRUE(storage.trace.prepare_worker(role));
    ASSERT_TRUE(owned.prepare_worker(role));
    const auto nonadvance = role == RingWorker::producer ? RingAttemptOutcome::full
                                                         : RingAttemptOutcome::empty;
    const std::array outcomes{nonadvance, RingAttemptOutcome::advanced, nonadvance,
                              RingAttemptOutcome::advanced,
                              RingAttemptOutcome::advanced};
    for (std::size_t i = 0U; i < outcomes.size(); ++i) {
      const auto start = 10U + 10U * i;
      ASSERT_TRUE(storage.trace.record(role, start, start + i + 1U, outcomes[i]));
      ASSERT_TRUE(owned.record(role, start, start + i + 1U, outcomes[i]));
    }
    const auto actual = storage.trace.worker_series(role);
    const auto expected = owned.worker_series(role);
    EXPECT_TRUE(std::ranges::equal(actual.demand_ticks, expected.demand_ticks));
    EXPECT_TRUE(std::ranges::equal(actual.issue_ticks, expected.issue_ticks));
    EXPECT_EQ(actual.nonadvancing_count, 2U);
    ASSERT_EQ(actual.issue_ticks.size(), 2U);
    EXPECT_EQ(actual.issue_ticks[0U], 20U);
    EXPECT_EQ(actual.issue_ticks[1U], 10U);
    EXPECT_EQ(actual.demand_ticks.data(), role == RingWorker::producer
                                              ? storage.producer_demand.data()
                                              : storage.consumer_demand.data());
  }
}

TEST(CallerOwnedDemandTrace, RejectsBadGeometryBeforeTouchingSampleStorage) {
  std::array<std::uint64_t, 8U> first;
  std::array<std::uint64_t, 8U> second;
  std::array<std::uint64_t, 8U> third;
  first.fill(71U);
  second.fill(73U);
  third.fill(79U);
  const std::span<std::uint64_t> a(first);
  const std::span<std::uint64_t> b(second);
  EXPECT_THROW((CallerOwnedRingDemandWorker(RingWorker::producer, {}, {})),
               std::invalid_argument);
  EXPECT_THROW((CallerOwnedRingDemandWorker(RingWorker::producer, a, b.first(7U))),
               std::invalid_argument);
  CallerOwnedRingDemandWorker producer(RingWorker::producer, a, b);
  CallerOwnedRingDemandWorker wrong_role(RingWorker::producer, a, b);
  EXPECT_THROW((CallerOwnedRingDemandTrace(producer, wrong_role)),
               std::invalid_argument);
  CallerOwnedRingDemandWorker overlapping(RingWorker::consumer, b, third);
  EXPECT_THROW((CallerOwnedRingDemandTrace(producer, overlapping)),
               std::invalid_argument);
  CallerOwnedRingDemandWorker internally_overlapping(RingWorker::consumer, third,
                                                     third);
  EXPECT_THROW((CallerOwnedRingDemandTrace(producer, internally_overlapping)),
               std::invalid_argument);
  EXPECT_TRUE(std::ranges::all_of(first, [](auto value) { return value == 71U; }));
  EXPECT_TRUE(std::ranges::all_of(second, [](auto value) { return value == 73U; }));
  EXPECT_TRUE(std::ranges::all_of(third, [](auto value) { return value == 79U; }));
}

TEST(CallerOwnedDemandTrace, PreparationAndFailuresPreserveIndependentPartialState) {
  TraceStorage<3U> storage;
  storage.consumer_demand.fill(97U);
  storage.consumer_issue.fill(101U);
  EXPECT_FALSE(
      storage.trace.record(RingWorker::producer, 1U, 2U, RingAttemptOutcome::advanced));
  ASSERT_TRUE(storage.trace.prepare_worker(RingWorker::producer));
  EXPECT_FALSE(storage.trace.worker_prepared(RingWorker::consumer));
  EXPECT_EQ(storage.consumer_demand[0U], 97U);
  EXPECT_EQ(storage.consumer_issue[0U], 101U);
  ASSERT_TRUE(storage.trace.record(RingWorker::producer, 10U, 12U,
                                   RingAttemptOutcome::advanced));
  for (const auto outcome :
       {RingAttemptOutcome::advanced, RingAttemptOutcome::empty,
        RingAttemptOutcome::clock_failure, RingAttemptOutcome::trace_failure}) {
    EXPECT_FALSE(storage.trace.record(RingWorker::producer, 9U, 11U, outcome));
  }
  EXPECT_FALSE(
      storage.trace.record(RingWorker::producer, 13U, 12U, RingAttemptOutcome::full));
  EXPECT_FALSE(storage.trace.prepare_worker(RingWorker::producer));
  const auto partial = storage.trace.worker_series(RingWorker::producer);
  ASSERT_EQ(partial.demand_ticks.size(), 1U);
  EXPECT_EQ(partial.demand_ticks[0U], 2U);
  EXPECT_TRUE(partial.issue_ticks.empty());
  EXPECT_EQ(partial.nonadvancing_count, 0U);
  ASSERT_TRUE(storage.trace.prepare_worker(RingWorker::consumer));
  EXPECT_EQ(storage.consumer_demand[0U], 0U);
  EXPECT_EQ(storage.consumer_issue[0U], 0U);
}

TEST(CallerOwnedDemandTrace, ExhaustionDoesNotWriteOrGrowBuffers) {
  TraceStorage<2U> storage;
  ASSERT_TRUE(storage.trace.prepare_worker(RingWorker::producer));
  ASSERT_TRUE(storage.trace.record(RingWorker::producer, 10U, 12U,
                                   RingAttemptOutcome::advanced));
  ASSERT_TRUE(
      storage.trace.record(RingWorker::producer, 20U, 25U, RingAttemptOutcome::full));
  const auto demand = storage.producer_demand;
  const auto issue = storage.producer_issue;
  EXPECT_FALSE(storage.trace.record(RingWorker::producer, 30U, 32U,
                                    RingAttemptOutcome::advanced));
  EXPECT_EQ(storage.producer_demand, demand);
  EXPECT_EQ(storage.producer_issue, issue);
  EXPECT_EQ(storage.trace.worker_series(RingWorker::producer).nonadvancing_count, 1U);
  EXPECT_TRUE(storage.trace.worker_series(RingWorker::consumer).demand_ticks.empty());
}

TEST(CallerOwnedDemandTrace, RealCapturePreservesEventActionAndFailedTraceDequeue) {
  TraceStorage<2U> storage;
  ASSERT_TRUE(storage.trace.prepare_worker(RingWorker::producer));
  ASSERT_TRUE(storage.trace.prepare_worker(RingWorker::consumer));
  workload::EventArena arena({8U, 64U, 4096U,
                              workload::MasterSeed::from_hex(std::string(64U, '0')),
                              "caller-owned-trace-test"});
  queue::RingSpscQueue ring({8U}, {64U});
  IncrementingClock clock;
  workload::ConsumerState actual{17U};
  workload::ConsumerState expected{17U};
  for (std::uint64_t sequence = 0U; sequence < 3U; ++sequence) {
    const auto event = arena.select({sequence});
    // The third call deliberately exceeds the trace limit after the real enqueue.
    const auto produced = calibration::capture_producer_ring_demand(
        clock, ring, pointer_for(event.record), storage.trace);
    EXPECT_EQ(produced.operation_outcome, RingAttemptOutcome::advanced);
    EXPECT_EQ(produced.outcome, sequence < 2U ? RingAttemptOutcome::advanced
                                              : RingAttemptOutcome::trace_failure);
    const auto consumed =
        calibration::capture_discovery_consumer_ring_demand(clock, ring, storage.trace);
    EXPECT_EQ(consumed.capture.operation_outcome, RingAttemptOutcome::advanced);
    EXPECT_EQ(consumed.capture.outcome, sequence < 2U
                                            ? RingAttemptOutcome::advanced
                                            : RingAttemptOutcome::trace_failure);
    ASSERT_EQ(consumed.operation.event, event.record);
    EXPECT_EQ(arena.access_and_mix(consumed.operation.event, actual).status,
              workload::RecordAccessStatus::valid);
    expected = workload::mix_consumer_state(expected, event.record_index,
                                            event.record->payload);
  }
  EXPECT_EQ(actual, expected);
  EXPECT_EQ(ring.audit_quiescent().occupied_slots, 0U);
  EXPECT_EQ(storage.trace.worker_series(RingWorker::consumer).demand_ticks.size(), 2U);
}

TEST(CallerOwnedDemandTrace, PreparedWindowAndValidatorUseTheSameCallerBuffers) {
  TraceStorage<8U> storage;
  ASSERT_TRUE(storage.trace.prepare_worker(RingWorker::producer));
  queue::RingSpscQueue ring({8U}, {64U});
  IncrementingClock clock;
  int event = 19;
  const auto pointer = pointer_for(&event);
  auto attempt = [&]() noexcept {
    return calibration::capture_producer_ring_demand(clock, ring, pointer,
                                                     storage.trace);
  };
  std::atomic<bool> stop{false};
  const auto result = calibration::capture_prepared_discovery_worker(
      {RingWorker::producer, 0U, 9U, 8U}, clock, attempt, storage.trace, stop);
  EXPECT_EQ(result.stop, calibration::DiscoveryWorkerStop::fixed_deadline);
  EXPECT_EQ(result.attempts, 3U);
  EXPECT_EQ(result.advanced, 3U);
  EXPECT_EQ(calibration::validate_quiescent_discovery_trace(RingWorker::producer,
                                                            result, storage.trace)
                .stop,
            calibration::DiscoveryWorkerStop::fixed_deadline);
  EXPECT_TRUE(storage.trace.worker_series(RingWorker::consumer).demand_ticks.empty());
  const auto rejected = calibration::capture_prepared_discovery_worker(
      {RingWorker::producer, 9U, 9U, 8U}, clock, attempt, storage.trace, stop);
  EXPECT_EQ(rejected.stop, calibration::DiscoveryWorkerStop::invalid_plan);
}

TEST(CallerOwnedDemandTrace, ConcurrentOwnerPreparationAndRecordingRemainIndependent) {
  TraceStorage<2000U> storage;
  std::array<bool, 2U> passed{};
  const auto record = [&](RingWorker role, std::size_t index) {
    bool ok = storage.trace.prepare_worker(role);
    for (std::uint64_t sequence = 0U; sequence < 2000U; ++sequence) {
      ok = storage.trace.record(role, 3U * sequence, 3U * sequence + 1U,
                                RingAttemptOutcome::advanced) &&
           ok;
      // Reading one's own view must not inspect the other role's mutable counts.
      ok = storage.trace.worker_series(role).demand_ticks.size() == sequence + 1U && ok;
    }
    passed[index] = ok;
  };
  std::thread producer(record, RingWorker::producer, 0U);
  std::thread consumer(record, RingWorker::consumer, 1U);
  producer.join();
  consumer.join();
  EXPECT_TRUE(passed[0U]);
  EXPECT_TRUE(passed[1U]);
  for (const auto role : {RingWorker::producer, RingWorker::consumer}) {
    const auto series = storage.trace.worker_series(role);
    EXPECT_EQ(series.demand_ticks.size(), 2000U);
    EXPECT_EQ(series.issue_ticks.size(), 1999U);
    EXPECT_TRUE(std::ranges::all_of(series.demand_ticks,
                                    [](auto value) { return value == 1U; }));
    EXPECT_TRUE(std::ranges::all_of(series.issue_ticks,
                                    [](auto value) { return value == 3U; }));
  }
}

} // namespace
