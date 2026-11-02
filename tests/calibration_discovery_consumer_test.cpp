#include "cpu_prefetch/calibration/discovery_consumer_capture.hpp"
#include "cpu_prefetch/workload/records.hpp"

#include <gtest/gtest.h>

#include <stdexcept>
#include <utility>
#include <vector>

namespace {
namespace calibration = cpu_prefetch::calibration;
namespace queue = cpu_prefetch::queue;
namespace timing = cpu_prefetch::timing;
namespace workload = cpu_prefetch::workload;

class SequenceClock final {
public:
  explicit SequenceClock(std::vector<std::uint64_t> ticks) : ticks_(std::move(ticks)) {}
  auto read() noexcept -> timing::ClockReadResult {
    if (position_ == ticks_.size()) {
      return {timing::ClockReadStatus::call_failed, {0U, 0U}};
    }
    return {timing::ClockReadStatus::ok, {0U, ticks_[position_++]}};
  }

private:
  std::vector<std::uint64_t> ticks_;
  std::size_t position_{0U};
};

auto event_pointer(const void* event) -> queue::EventPointer {
  const auto pointer = queue::EventPointer::from(event);
  if (pointer.has_value()) {
    return pointer.value();
  }
  throw std::logic_error("invalid test event pointer");
}

TEST(DiscoveryConsumerCapture, RetainsTheActualImmutableRecordForChecksumAction) {
  workload::EventArena arena({8U, 64U, 4096U,
                              workload::MasterSeed::from_hex(std::string(64U, '0')),
                              "diagnostic-test"});
  const auto selected = arena.select({3U});
  queue::RingSpscQueue ring({8U}, {64U});
  ASSERT_EQ(ring.try_enqueue(event_pointer(selected.record)),
            queue::EnqueueResult::accepted);
  calibration::RingDemandTrace trace(1U);
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::consumer));
  SequenceClock clock({5U, 9U});
  const auto captured =
      calibration::capture_discovery_consumer_ring_demand(clock, ring, trace);
  EXPECT_EQ(captured.capture.outcome, calibration::RingAttemptOutcome::advanced);
  ASSERT_EQ(captured.operation.status, queue::DequeueStatus::item);
  EXPECT_EQ(captured.operation.event, selected.record);
  workload::ConsumerState state{17U};
  const auto access = arena.access_and_mix(captured.operation.event, state);
  EXPECT_EQ(access.status, workload::RecordAccessStatus::valid);
  EXPECT_EQ(access.record_index, selected.record_index);
  EXPECT_EQ(state, workload::mix_consumer_state({17U}, selected.record_index,
                                                selected.record->payload));
  ASSERT_EQ(trace.series().consumer_demand_ticks.size(), 1U);
  EXPECT_EQ(trace.series().consumer_demand_ticks[0], 4U);
}

TEST(DiscoveryConsumerCapture, EmptyPollDoesNotInventAnEvent) {
  queue::RingSpscQueue ring({8U}, {64U});
  calibration::RingDemandTrace trace(1U);
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::consumer));
  SequenceClock clock({5U, 9U});
  const auto captured =
      calibration::capture_discovery_consumer_ring_demand(clock, ring, trace);
  EXPECT_EQ(captured.capture.outcome, calibration::RingAttemptOutcome::empty);
  EXPECT_EQ(captured.operation.status, queue::DequeueStatus::empty);
  EXPECT_EQ(captured.operation.event, nullptr);
  EXPECT_EQ(trace.series().consumer_empty_count, 1U);
}

TEST(DiscoveryConsumerCapture, FailedClockRetainsTheEventAlreadyRemovedFromTheRing) {
  int event{19};
  queue::RingSpscQueue ring({8U}, {64U});
  ASSERT_EQ(ring.try_enqueue(event_pointer(&event)), queue::EnqueueResult::accepted);
  calibration::RingDemandTrace trace(1U);
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::consumer));
  SequenceClock clock({5U});
  const auto captured =
      calibration::capture_discovery_consumer_ring_demand(clock, ring, trace);
  EXPECT_EQ(captured.capture.outcome, calibration::RingAttemptOutcome::clock_failure);
  EXPECT_EQ(captured.capture.operation_outcome,
            calibration::RingAttemptOutcome::advanced);
  EXPECT_EQ(captured.capture.after_status, timing::ClockReadStatus::call_failed);
  EXPECT_EQ(captured.operation.status, queue::DequeueStatus::item);
  EXPECT_EQ(captured.operation.event, &event);
  EXPECT_EQ(ring.audit_quiescent().occupied_slots, 0U);
  EXPECT_TRUE(trace.series().consumer_demand_ticks.empty());
}

TEST(DiscoveryConsumerCapture, ExhaustedTraceRetainsTheSecondActualEvent) {
  int first{17};
  int second{19};
  queue::RingSpscQueue ring({8U}, {64U});
  ASSERT_EQ(ring.try_enqueue(event_pointer(&first)), queue::EnqueueResult::accepted);
  ASSERT_EQ(ring.try_enqueue(event_pointer(&second)), queue::EnqueueResult::accepted);
  calibration::RingDemandTrace trace(1U);
  ASSERT_TRUE(trace.prepare_worker(calibration::RingWorker::consumer));
  SequenceClock clock({5U, 9U, 11U, 13U});
  const auto captured_first =
      calibration::capture_discovery_consumer_ring_demand(clock, ring, trace);
  const auto captured_second =
      calibration::capture_discovery_consumer_ring_demand(clock, ring, trace);
  EXPECT_EQ(captured_first.capture.outcome, calibration::RingAttemptOutcome::advanced);
  EXPECT_EQ(captured_first.operation.event, &first);
  EXPECT_EQ(captured_second.capture.outcome,
            calibration::RingAttemptOutcome::trace_failure);
  EXPECT_EQ(captured_second.capture.operation_outcome,
            calibration::RingAttemptOutcome::advanced);
  EXPECT_EQ(captured_second.operation.status, queue::DequeueStatus::item);
  EXPECT_EQ(captured_second.operation.event, &second);
  EXPECT_EQ(ring.audit_quiescent().occupied_slots, 0U);
  EXPECT_EQ(trace.series().consumer_demand_ticks.size(), 1U);
}
} // namespace
