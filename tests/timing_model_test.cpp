#include <gtest/gtest.h>

#include "cpu_prefetch/queue/linked_spsc.hpp"
#include "cpu_prefetch/queue/ring_spsc.hpp"
#include "cpu_prefetch/timing/capture.hpp"
#include "cpu_prefetch/timing/clock.hpp"
#include "cpu_prefetch/timing/intervals.hpp"
#include "cpu_prefetch/timing/qualification.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"
#include "cpu_prefetch/workload/packages.hpp"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace {

using cpu_prefetch::protocol::ConsumerRecord;
using cpu_prefetch::protocol::ProducerOutcome;
using cpu_prefetch::protocol::ProducerRecord;
using cpu_prefetch::protocol::RunId;
using cpu_prefetch::queue::ArenaAlignmentBytes;
using cpu_prefetch::queue::CacheLineBytes;
using cpu_prefetch::queue::DequeueStatus;
using cpu_prefetch::queue::EnqueueResult;
using cpu_prefetch::queue::EventPointer;
using cpu_prefetch::queue::LinkedSpscQueue;
using cpu_prefetch::queue::QueueCapacity;
using cpu_prefetch::queue::RingSpscQueue;
using cpu_prefetch::timing::CaptureStatus;
using cpu_prefetch::timing::ClockOrigin;
using cpu_prefetch::timing::ClockReadResult;
using cpu_prefetch::timing::ClockReadStatus;
using cpu_prefetch::timing::ClockSample;
using cpu_prefetch::timing::MonotonicRawClock;
using cpu_prefetch::timing::TimestampBoundary;
using cpu_prefetch::workload::AcceptedOrdinal;
using cpu_prefetch::workload::ConsumerState;
using cpu_prefetch::workload::EventArena;
using cpu_prefetch::workload::EventArenaConfig;
using cpu_prefetch::workload::LogicalSequence;
using cpu_prefetch::workload::MasterSeed;
using cpu_prefetch::workload::R0Package;

constexpr CacheLineBytes kLine{64U};
constexpr ArenaAlignmentBytes kPage{4096U};

template <typename Value>
[[nodiscard]] auto require_optional(const std::optional<Value>& value) -> const Value& {
  if (!value.has_value()) {
    throw std::logic_error("required test value is absent");
  }
  return value.value();
}

auto seed() -> MasterSeed {
  return MasterSeed::from_hex("000102030405060708090a0b0c0d0e0f"
                              "101112131415161718191a1b1c1d1e1f");
}

auto run_id(std::string text = "timing-run") -> RunId {
  auto parsed = RunId::parse(std::move(text), "$test/run_id");
  if (!parsed) {
    throw std::logic_error("test run ID is invalid");
  }
  return std::move(parsed).value();
}

class SequenceClock final {
public:
  explicit SequenceClock(std::vector<ClockReadResult> reads)
      : reads_(std::move(reads)) {}

  [[nodiscard]] auto read() noexcept -> ClockReadResult {
    if (position_ >= reads_.size()) {
      return {ClockReadStatus::call_failed, {0U, 0U}};
    }
    return reads_[position_++];
  }

  [[nodiscard]] auto read_count() const noexcept -> std::size_t { return position_; }

private:
  std::vector<ClockReadResult> reads_;
  std::size_t position_{0U};
};

class ConcurrentClock final {
public:
  explicit ConcurrentClock(std::atomic<std::uint64_t>& next) noexcept : next_(next) {}

  [[nodiscard]] auto read() noexcept -> ClockReadResult {
    const auto value = next_.fetch_add(1000U, std::memory_order_relaxed);
    return {ClockReadStatus::ok, {value / 1000U, value}};
  }

private:
  std::atomic<std::uint64_t>& next_;
};

auto good_read(std::uint64_t relative_picoseconds) -> ClockReadResult {
  return {ClockReadStatus::ok, {relative_picoseconds / 1000U, relative_picoseconds}};
}

TEST(TimingClock, TimespecAndRelativeConversionAreExactAndFailClosed) {
  const auto absolute =
      cpu_prefetch::timing::absolute_nanoseconds_from_timespec(7, 123'456'789);
  ASSERT_EQ(absolute.status, ClockReadStatus::ok);
  EXPECT_EQ(absolute.absolute_nanoseconds, 7'123'456'789U);

  EXPECT_EQ(cpu_prefetch::timing::absolute_nanoseconds_from_timespec(-1, 0).status,
            ClockReadStatus::invalid_timespec);
  EXPECT_EQ(
      cpu_prefetch::timing::absolute_nanoseconds_from_timespec(0, 1'000'000'000).status,
      ClockReadStatus::invalid_timespec);
  EXPECT_EQ(cpu_prefetch::timing::absolute_nanoseconds_from_timespec(
                std::numeric_limits<std::int64_t>::max(), 0)
                .status,
            ClockReadStatus::overflow);

  const auto sample = cpu_prefetch::timing::relative_clock_sample(
      ClockOrigin{7'123'000'000U}, 7'123'456'789U);
  ASSERT_EQ(sample.status, ClockReadStatus::ok);
  EXPECT_EQ(sample.sample.absolute_nanoseconds, 7'123'456'789U);
  EXPECT_EQ(sample.sample.relative_picoseconds, 456'789'000U);
  EXPECT_EQ(sample.sample.relative_picoseconds % 1000U, 0U);
  EXPECT_EQ(cpu_prefetch::timing::relative_clock_sample(ClockOrigin{9U}, 8U).status,
            ClockReadStatus::before_origin);

  constexpr auto maximum_convertible_delta =
      std::numeric_limits<std::uint64_t>::max() / 1000U;
  EXPECT_EQ(cpu_prefetch::timing::relative_clock_sample(ClockOrigin{0U},
                                                        maximum_convertible_delta)
                .status,
            ClockReadStatus::ok);
  EXPECT_EQ(cpu_prefetch::timing::relative_clock_sample(ClockOrigin{0U},
                                                        maximum_convertible_delta + 1U)
                .status,
            ClockReadStatus::overflow);
}

TEST(TimingCapture, AcceptedAndFullProducerRowsUseExactReadBoundaries) {
  EventArena arena(EventArenaConfig{2U, 64U, 4096U, seed(), "timing-capture"});
  RingSpscQueue queue(QueueCapacity{1U}, kLine);
  R0Package package(queue);

  SequenceClock accepted_clock({good_read(10'000U), good_read(20'000U),
                                good_read(30'000U), good_read(40'000U),
                                good_read(50'000U)});
  const auto accepted = cpu_prefetch::timing::capture_due_producer_attempt(
      accepted_clock, arena, package, LogicalSequence{0U}, 5'000U, AcceptedOrdinal{7U});
  ASSERT_EQ(accepted.status, CaptureStatus::complete);
  ASSERT_TRUE(accepted.observation.has_value());
  const auto& row = require_optional(accepted.observation);
  EXPECT_EQ(row.scheduled_arrival, 5'000U);
  EXPECT_EQ(row.producer_handle_begin.relative_picoseconds, 10'000U);
  EXPECT_EQ(row.record_lookup_completion.relative_picoseconds, 20'000U);
  EXPECT_EQ(row.enqueue_invocation.relative_picoseconds, 30'000U);
  ASSERT_TRUE(row.enqueue_linearization.has_value());
  EXPECT_EQ(require_optional(row.enqueue_linearization).relative_picoseconds, 40'000U);
  EXPECT_EQ(row.enqueue_attempt_completion.relative_picoseconds, 50'000U);
  EXPECT_EQ(row.outcome, ProducerOutcome::accepted);
  ASSERT_TRUE(row.accepted_ordinal.has_value());
  EXPECT_EQ(require_optional(row.accepted_ordinal).value, 7U);
  EXPECT_EQ(accepted_clock.read_count(), 5U);
  const auto logical = cpu_prefetch::timing::make_producer_record(run_id(), row);
  EXPECT_EQ(logical.enqueue_linearization, 40'000U);
  EXPECT_EQ(require_optional(row.enqueue_linearization).absolute_nanoseconds, 40U);

  SequenceClock full_clock(
      {good_read(60'000U), good_read(70'000U), good_read(80'000U), good_read(90'000U)});
  const auto full = cpu_prefetch::timing::capture_due_producer_attempt(
      full_clock, arena, package, LogicalSequence{1U}, 55'000U, AcceptedOrdinal{8U});
  ASSERT_EQ(full.status, CaptureStatus::complete);
  ASSERT_TRUE(full.observation.has_value());
  const auto& full_row = require_optional(full.observation);
  EXPECT_EQ(full_row.outcome, ProducerOutcome::full);
  EXPECT_FALSE(full_row.enqueue_linearization.has_value());
  EXPECT_FALSE(full_row.accepted_ordinal.has_value());
  EXPECT_EQ(full_clock.read_count(), 4U);
}

TEST(TimingCapture, ReleaseAcquirePublicationCarriesExactBoundariesAcrossThreads) {
  EventArena arena(EventArenaConfig{8U, 64U, 4096U, seed(), "timing-thread"});
  RingSpscQueue queue(QueueCapacity{2U}, kLine);
  R0Package package(queue);
  std::atomic<std::uint64_t> next_timestamp{1000U};
  ConcurrentClock clock(next_timestamp);
  std::atomic<bool> start{false};
  std::optional<cpu_prefetch::timing::ProducerCaptureResult> producer_result;
  std::optional<cpu_prefetch::timing::ConsumerCaptureResult> consumer_result;
  ConsumerState state{0U};

  std::thread producer([&] {
    while (!start.load(std::memory_order_acquire)) {
      std::this_thread::yield();
    }
    producer_result = cpu_prefetch::timing::capture_due_producer_attempt(
        clock, arena, package, LogicalSequence{0U}, 0U, AcceptedOrdinal{0U});
  });
  std::thread consumer([&] {
    while (!start.load(std::memory_order_acquire)) {
      std::this_thread::yield();
    }
    for (std::size_t attempt = 0U; attempt < 100'000U; ++attempt) {
      auto result = cpu_prefetch::timing::capture_dequeue_poll(
          clock, arena, package, state, AcceptedOrdinal{0U});
      if (result.status == CaptureStatus::complete) {
        consumer_result = result;
        return;
      }
    }
  });
  start.store(true, std::memory_order_release);
  producer.join();
  consumer.join();

  ASSERT_TRUE(producer_result.has_value());
  ASSERT_TRUE(consumer_result.has_value());
  const auto& captured_producer = require_optional(producer_result);
  const auto& captured_consumer = require_optional(consumer_result);
  ASSERT_EQ(captured_producer.status, CaptureStatus::complete);
  ASSERT_EQ(captured_consumer.status, CaptureStatus::complete);
  ASSERT_TRUE(captured_producer.observation.has_value());
  ASSERT_TRUE(captured_consumer.observation.has_value());
  const auto& producer_row = require_optional(captured_producer.observation);
  const auto& consumer_row = require_optional(captured_consumer.observation);
  ASSERT_TRUE(producer_row.enqueue_linearization.has_value());
  EXPECT_LE(require_optional(producer_row.enqueue_linearization).relative_picoseconds,
            consumer_row.dequeue_linearization.relative_picoseconds);
  EXPECT_EQ(producer_row.record_index, consumer_row.observed_record_index);
}

TEST(TimingCapture, ConsumerRetainsOnlySuccessfulPollAndCompletesAfterRecordAction) {
  EventArena arena(EventArenaConfig{2U, 64U, 4096U, seed(), "timing-consumer"});
  RingSpscQueue queue(QueueCapacity{1U}, kLine);
  R0Package package(queue);
  const auto selection = arena.select(LogicalSequence{0U});
  const auto pointer = EventPointer::from(selection.record);
  ASSERT_TRUE(pointer.has_value());
  ASSERT_EQ(package.try_enqueue(require_optional(pointer)), EnqueueResult::accepted);

  ConsumerState state{123U};
  SequenceClock clock({good_read(100'000U), good_read(110'000U), good_read(120'000U),
                       good_read(130'000U)});
  const auto captured = cpu_prefetch::timing::capture_dequeue_poll(
      clock, arena, package, state, AcceptedOrdinal{0U});
  ASSERT_EQ(captured.status, CaptureStatus::complete);
  ASSERT_TRUE(captured.observation.has_value());
  const auto& consumer_row = require_optional(captured.observation);
  EXPECT_EQ(consumer_row.observed_record_index, selection.record_index);
  EXPECT_EQ(consumer_row.dequeue_invocation.relative_picoseconds, 100'000U);
  EXPECT_EQ(consumer_row.dequeue_linearization.relative_picoseconds, 110'000U);
  EXPECT_EQ(consumer_row.dequeue_completion.relative_picoseconds, 120'000U);
  EXPECT_EQ(consumer_row.consumer_action_completion.relative_picoseconds, 130'000U);
  EXPECT_NE(state.value, 123U);

  SequenceClock empty_clock({good_read(140'000U)});
  const auto empty = cpu_prefetch::timing::capture_dequeue_poll(
      empty_clock, arena, package, state, AcceptedOrdinal{1U});
  EXPECT_EQ(empty.status, CaptureStatus::empty);
  EXPECT_FALSE(empty.observation.has_value());
  EXPECT_EQ(empty_clock.read_count(), 1U);
}

TEST(TimingCapture, ClockFailureDoesNotPublishOrFabricateAProducerRow) {
  EventArena arena(EventArenaConfig{2U, 64U, 4096U, seed(), "timing-failure"});
  RingSpscQueue queue(QueueCapacity{1U}, kLine);
  R0Package package(queue);
  SequenceClock clock({good_read(10'000U),
                       good_read(20'000U),
                       good_read(30'000U),
                       {ClockReadStatus::call_failed, {0U, 0U}}});

  const auto captured = cpu_prefetch::timing::capture_due_producer_attempt(
      clock, arena, package, LogicalSequence{0U}, 0U, AcceptedOrdinal{0U});
  EXPECT_EQ(captured.status, CaptureStatus::clock_failure);
  EXPECT_EQ(captured.failed_boundary, TimestampBoundary::enqueue_linearization);
  EXPECT_FALSE(captured.observation.has_value());
  EXPECT_EQ(package.try_dequeue().status, DequeueStatus::empty);
}

TEST(TimingIntervals, ExactEquationsAllowTiesAndRejectNegativeOrFullInputs) {
  const auto id = run_id();
  const ProducerRecord producer{
      id, 4U, 2U, 100U, 110U, 120U, 130U, 150U, 160U, ProducerOutcome::accepted, 3U};
  const ConsumerRecord consumer{id, 3U, 2U, 140U, 170U, 180U, 200U};
  const auto joined =
      cpu_prefetch::timing::derive_joined_record(producer, 8U, consumer, 9U);
  ASSERT_TRUE(joined);
  EXPECT_EQ(joined.value().producer_lateness, 10U);
  EXPECT_EQ(joined.value().pointer_lookup_interval, 10U);
  EXPECT_EQ(joined.value().enqueue_service_time, 30U);
  EXPECT_EQ(joined.value().admission_delay, 50U);
  EXPECT_EQ(joined.value().queue_residence, 20U);
  EXPECT_EQ(joined.value().dequeue_service_time, 40U);
  EXPECT_EQ(joined.value().post_dequeue_delivery_interval, 30U);
  EXPECT_EQ(joined.value().consumer_action_interval, 20U);
  EXPECT_EQ(joined.value().end_to_end_latency, 100U);
  EXPECT_EQ(joined.value().admission_delay + joined.value().queue_residence +
                joined.value().post_dequeue_delivery_interval,
            joined.value().end_to_end_latency);

  const ProducerRecord tied{
      id, 0U, 0U, 9U, 9U, 9U, 9U, 9U, 9U, ProducerOutcome::accepted, 0U};
  const ConsumerRecord tied_consumer{id, 0U, 0U, 9U, 9U, 9U, 9U};
  const auto zero =
      cpu_prefetch::timing::derive_joined_record(tied, 0U, tied_consumer, 0U);
  ASSERT_TRUE(zero);
  EXPECT_EQ(zero.value().end_to_end_latency, 0U);

  auto negative_consumer = consumer;
  negative_consumer.dequeue_linearization = 149U;
  const auto negative =
      cpu_prefetch::timing::derive_joined_record(producer, 8U, negative_consumer, 9U);
  ASSERT_FALSE(negative);
  EXPECT_EQ(negative.errors().front().rule_id, "TIM-DERIVE-ORDER");

  auto full = producer;
  full.outcome = ProducerOutcome::full;
  full.enqueue_linearization.reset();
  full.accepted_ordinal.reset();
  const auto no_latency =
      cpu_prefetch::timing::derive_joined_record(full, 8U, consumer, 9U);
  ASSERT_FALSE(no_latency);
  EXPECT_EQ(no_latency.errors().front().rule_id, "TIM-DERIVE-ACCEPTED-ONLY");
}

TEST(TimingIntervals, MaximumTickBoundaryDoesNotWrap) {
  constexpr auto maximum = std::numeric_limits<std::uint64_t>::max();
  const auto id = run_id("maximum-tick-run");
  const ProducerRecord producer{id,
                                0U,
                                0U,
                                maximum - 30U,
                                maximum - 25U,
                                maximum - 20U,
                                maximum - 15U,
                                maximum - 10U,
                                maximum - 5U,
                                ProducerOutcome::accepted,
                                0U};
  const ConsumerRecord consumer{id,           0U,           0U,     maximum - 12U,
                                maximum - 8U, maximum - 4U, maximum};
  const auto joined =
      cpu_prefetch::timing::derive_joined_record(producer, 0U, consumer, 0U);
  ASSERT_TRUE(joined);
  EXPECT_EQ(joined.value().end_to_end_latency, 30U);
  EXPECT_EQ(joined.value().admission_delay + joined.value().queue_residence +
                joined.value().post_dequeue_delivery_interval,
            30U);
}

TEST(TimingQualification, SequenceAndStaticGatesAreExactAndSampleCountAware) {
  const std::array<std::uint64_t, 6> samples{0U, 1000U, 1000U, 3000U, 6000U, 10'000U};
  const auto sequence = cpu_prefetch::timing::evaluate_clock_sequence(samples);
  ASSERT_TRUE(sequence.has_value());
  const auto& sequence_result = require_optional(sequence);
  EXPECT_EQ(sequence_result.delta_count, 5U);
  EXPECT_EQ(sequence_result.regression_count, 0U);
  EXPECT_EQ(sequence_result.equal_count, 1U);
  EXPECT_EQ(sequence_result.maximum_delta_picoseconds, 4'000U);
  EXPECT_FALSE(sequence_result.accepted_policy_sample_count);

  const std::array<std::uint64_t, 5> overhead{5U, 1U, 3U, 2U, 4U};
  const auto diagnostic = cpu_prefetch::timing::characterize_capture_overhead(overhead);
  ASSERT_TRUE(diagnostic.has_value());
  const auto& overhead_result = require_optional(diagnostic);
  EXPECT_EQ(overhead_result.median_picoseconds, 3U);
  EXPECT_FALSE(overhead_result.correction_applied);
  EXPECT_TRUE(overhead_result.primary_timestamps_unchanged);

  const auto static_pass = cpu_prefetch::timing::evaluate_static_clock_evidence(
      {.bare_metal_linux_x86_64 = true,
       .clock_monotonic_raw_supported = true,
       .current_clocksource_tsc = true,
       .no_unstable_clock_report = true,
       .constant_tsc = true,
       .nonstop_tsc = true,
       .invariant_tsc = true,
       .vdso_versioned_symbol = true,
       .glibc_call_path_verified_vdso = true,
       .probe_call_count = 10'000'000U,
       .probe_syscall_count = 0U,
       .probe_failure_count = 0U,
       .no_clocksource_override = true,
       .generated_code_passes = true,
       .resolution_picoseconds = 1000U});
  EXPECT_TRUE(static_pass.passes);

  const auto static_fail = cpu_prefetch::timing::evaluate_static_clock_evidence(
      {.bare_metal_linux_x86_64 = true,
       .clock_monotonic_raw_supported = true,
       .current_clocksource_tsc = true,
       .no_unstable_clock_report = true,
       .constant_tsc = false,
       .nonstop_tsc = true,
       .invariant_tsc = true,
       .vdso_versioned_symbol = true,
       .glibc_call_path_verified_vdso = true,
       .probe_call_count = 10'000'000U,
       .probe_syscall_count = 0U,
       .probe_failure_count = 0U,
       .no_clocksource_override = true,
       .generated_code_passes = true,
       .resolution_picoseconds = 1001U});
  EXPECT_FALSE(static_fail.passes);
  EXPECT_FALSE(static_fail.frequency_invariance_passes);
  EXPECT_FALSE(static_fail.resolution_passes);
}

TEST(TimingQualification, CrossCoreIntervalsRetainHalfPicosecondMidpoints) {
  using cpu_prefetch::timing::CrossCoreExchangeSample;
  const std::array<CrossCoreExchangeSample, 2> first{
      {{100U, 110U, 120U, 130U}, {200U, 210U, 220U, 230U}}};
  const std::array<CrossCoreExchangeSample, 2> second{
      {{300U, 310U, 321U, 332U}, {400U, 410U, 421U, 432U}}};
  const std::array<CrossCoreExchangeSample, 2> third{
      {{500U, 510U, 520U, 530U}, {600U, 610U, 620U, 630U}}};
  const std::array windows{
      cpu_prefetch::timing::CrossCoreWindowInput{0U, first},
      cpu_prefetch::timing::CrossCoreWindowInput{30'000'000'000U, second},
      cpu_prefetch::timing::CrossCoreWindowInput{60'000'000'000U, third}};
  const auto evidence = cpu_prefetch::timing::evaluate_cross_core_direction(windows);
  ASSERT_TRUE(evidence.has_value());
  const auto& direction_evidence = require_optional(evidence);
  EXPECT_TRUE(direction_evidence.limits_pass);
  EXPECT_FALSE(direction_evidence.accepted_policy_sample_count);
  EXPECT_FALSE(direction_evidence.passes);
  EXPECT_EQ(direction_evidence.windows[1].midpoint_twice_picoseconds, -1);
  EXPECT_TRUE(direction_evidence.window_span_passes);

  const auto pair = cpu_prefetch::timing::evaluate_cross_core_pair(
      cpu_prefetch::timing::CrossCorePairInput{windows, windows});
  ASSERT_TRUE(pair.has_value());
  const auto& pair_evidence = require_optional(pair);
  EXPECT_TRUE(pair_evidence.producer_to_consumer.limits_pass);
  EXPECT_TRUE(pair_evidence.consumer_to_producer.limits_pass);
  EXPECT_FALSE(pair_evidence.producer_to_consumer.accepted_policy_sample_count);
  EXPECT_FALSE(pair_evidence.consumer_to_producer.accepted_policy_sample_count);
  EXPECT_FALSE(pair_evidence.passes);

  auto causal_failure = first;
  causal_failure[0].request_receive = 99U;
  const std::array bad_windows{
      cpu_prefetch::timing::CrossCoreWindowInput{0U, causal_failure},
      cpu_prefetch::timing::CrossCoreWindowInput{30'000'000'000U, second},
      cpu_prefetch::timing::CrossCoreWindowInput{60'000'000'000U, third}};
  const auto rejected =
      cpu_prefetch::timing::evaluate_cross_core_direction(bad_windows);
  ASSERT_TRUE(rejected.has_value());
  const auto& rejected_evidence = require_optional(rejected);
  EXPECT_FALSE(rejected_evidence.passes);
  EXPECT_EQ(rejected_evidence.causal_regressions, 1U);
}

TEST(TimingQueueBoundary, PublicationPrecedesReleaseAndObservationPrecedesReuse) {
  std::array<std::uint64_t, 2> events{};
  const auto first = EventPointer::from(&events[0]);
  const auto second = EventPointer::from(&events[1]);
  ASSERT_TRUE(first.has_value());
  ASSERT_TRUE(second.has_value());

  RingSpscQueue ring(QueueCapacity{1U}, kLine);
  struct RingPublish final {
    RingSpscQueue& queue;
    bool saw_empty{false};
    [[nodiscard]] bool before_enqueue_publication() noexcept {
      saw_empty = queue.try_dequeue().status == DequeueStatus::empty;
      return true;
    }
  } ring_publish{ring};
  const auto ring_enqueued =
      ring.try_enqueue_with_boundary_observer(require_optional(first), ring_publish);
  EXPECT_EQ(ring_enqueued.result, EnqueueResult::accepted);
  EXPECT_TRUE(ring_publish.saw_empty);

  struct RingObserve final {
    RingSpscQueue& queue;
    EventPointer next;
    bool saw_full{false};
    [[nodiscard]] bool after_dequeue_observation() noexcept {
      saw_full = queue.try_enqueue(next) == EnqueueResult::full;
      return true;
    }
  } ring_observe{ring, require_optional(second)};
  const auto ring_dequeued = ring.try_dequeue_with_boundary_observer(ring_observe);
  EXPECT_EQ(ring_dequeued.result.status, DequeueStatus::item);
  EXPECT_TRUE(ring_observe.saw_full);

  const std::array<std::size_t, 2> order{1U, 0U};
  LinkedSpscQueue linked(QueueCapacity{1U}, kLine, kPage, order);
  struct LinkedPublish final {
    LinkedSpscQueue& queue;
    bool saw_empty{false};
    [[nodiscard]] bool before_enqueue_publication() noexcept {
      saw_empty = queue.try_dequeue().status == DequeueStatus::empty;
      return true;
    }
  } linked_publish{linked};
  const auto linked_enqueued = linked.try_enqueue_with_boundary_observer(
      require_optional(first), linked_publish);
  EXPECT_EQ(linked_enqueued.result, EnqueueResult::accepted);
  EXPECT_TRUE(linked_publish.saw_empty);

  struct LinkedObserve final {
    LinkedSpscQueue& queue;
    EventPointer next;
    bool saw_full{false};
    [[nodiscard]] bool after_dequeue_observation() noexcept {
      saw_full = queue.try_enqueue(next) == EnqueueResult::full;
      return true;
    }
  } linked_observe{linked, require_optional(second)};
  const auto linked_dequeued =
      linked.try_dequeue_with_boundary_observer(linked_observe);
  EXPECT_EQ(linked_dequeued.result.status, DequeueStatus::item);
  EXPECT_TRUE(linked_observe.saw_full);
}

TEST(TimingQueueBoundary, LinkedObservationPrecedesTreatmentPrefetch) {
  std::uint64_t event = 0U;
  const auto pointer = EventPointer::from(&event);
  ASSERT_TRUE(pointer.has_value());
  const std::array<std::size_t, 2> order{1U, 0U};
  LinkedSpscQueue queue(QueueCapacity{1U}, kLine, kPage, order);
  std::size_t phase = 0U;
  struct Emitter final {
    std::size_t& phase;
    bool observed_after_q{false};
    void successor_header(const void*) noexcept {
      observed_after_q = phase == 1U;
      phase = 2U;
    }
  } emitter{phase};
  cpu_prefetch::workload::L1Package package(queue, emitter);
  ASSERT_EQ(package.try_enqueue(require_optional(pointer)), EnqueueResult::accepted);
  struct Observer final {
    std::size_t& phase;
    [[nodiscard]] bool after_dequeue_observation() noexcept {
      phase = 1U;
      return true;
    }
  } observer{phase};
  const auto result = package.try_dequeue_with_boundary_observer(observer);
  EXPECT_EQ(result.result.status, DequeueStatus::item);
  EXPECT_TRUE(emitter.observed_after_q);
  EXPECT_EQ(phase, 2U);
}

TEST(TimingClock, RealMonotonicRawReaderIsAnEngineeringSmokeOnly) {
  const auto origin = MonotonicRawClock::capture_origin();
  ASSERT_EQ(origin.status, ClockReadStatus::ok);
  MonotonicRawClock clock(ClockOrigin{origin.absolute_nanoseconds});
  std::uint64_t previous = 0U;
  for (std::size_t index = 0; index < 10'000U; ++index) {
    const auto reading = clock.read();
    ASSERT_EQ(reading.status, ClockReadStatus::ok);
    EXPECT_GE(reading.sample.relative_picoseconds, previous);
    EXPECT_EQ(reading.sample.relative_picoseconds % 1000U, 0U);
    previous = reading.sample.relative_picoseconds;
  }
  const auto resolution = cpu_prefetch::timing::monotonic_raw_resolution();
  EXPECT_EQ(resolution.status, ClockReadStatus::ok);
  const auto vdso = cpu_prefetch::timing::probe_vdso_clock_gettime();
  EXPECT_TRUE(vdso.library_opened);
  EXPECT_TRUE(vdso.clock_gettime_symbol_present);
  EXPECT_TRUE(vdso.versioned_symbol_present);
}

} // namespace
