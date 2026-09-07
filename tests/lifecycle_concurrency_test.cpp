#include <gtest/gtest.h>

#include "cpu_prefetch/lifecycle/executor.hpp"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <thread>
#include <vector>

namespace {

using cpu_prefetch::lifecycle::AttemptStatus;
using cpu_prefetch::lifecycle::ConsumerPollResult;
using cpu_prefetch::lifecycle::ConsumerPollStatus;
using cpu_prefetch::lifecycle::ExecutionFailurePhase;
using cpu_prefetch::lifecycle::ExecutionFailureReason;
using cpu_prefetch::lifecycle::ExecutionLimits;
using cpu_prefetch::lifecycle::PreparedScheduleView;
using cpu_prefetch::lifecycle::ProducerAttempt;
using cpu_prefetch::lifecycle::ProducerAttemptResult;
using cpu_prefetch::lifecycle::StartBarrierStatus;
using cpu_prefetch::lifecycle::TerminationControl;
using cpu_prefetch::lifecycle::TickRead;
using cpu_prefetch::lifecycle::WorkerRole;
using cpu_prefetch::lifecycle::WorkerStartBarrier;
using cpu_prefetch::queue::CacheLineBytes;
using cpu_prefetch::queue::EnqueueResult;

constexpr CacheLineBytes kFixtureCacheLine{64U};
constexpr std::uint64_t kNever = std::numeric_limits<std::uint64_t>::max();

struct StepClockConfig final {
  std::uint64_t initial{0U};
  std::uint64_t step{1U};
  std::uint64_t fail_at{kNever};
};

class AtomicStepClock final {
public:
  explicit AtomicStepClock(StepClockConfig config = {}) noexcept
      : next_(config.initial), step_(config.step), fail_at_(config.fail_at) {}

  [[nodiscard]] auto read_ticks() noexcept -> TickRead {
    const auto ordinal = reads_.fetch_add(1U, std::memory_order_relaxed);
    if (ordinal == fail_at_) {
      return {false, 0U};
    }
    return {true, next_.fetch_add(step_, std::memory_order_relaxed)};
  }

private:
  std::atomic<std::uint64_t> next_;
  const std::uint64_t step_;
  const std::uint64_t fail_at_;
  std::atomic<std::uint64_t> reads_{0U};
};

class YieldRelax final {
public:
  void relax() noexcept {
    calls_.fetch_add(1U, std::memory_order_relaxed);
    std::this_thread::yield();
  }

  [[nodiscard]] auto calls() const noexcept -> std::uint64_t {
    return calls_.load(std::memory_order_relaxed);
  }

private:
  std::atomic<std::uint64_t> calls_{0U};
};

class FixedFakeBackend final {
public:
  static constexpr std::size_t kMaximumItems = 1024U;

  struct Config final {
    std::size_t capacity;
    std::uint64_t expected_attempts;
    bool hold_consumer_until_all_attempts{false};
  };

  explicit FixedFakeBackend(Config config) noexcept
      : capacity_(config.capacity), expected_attempts_(config.expected_attempts),
        hold_consumer_(config.hold_consumer_until_all_attempts) {}

  [[nodiscard]] auto try_producer_attempt(ProducerAttempt attempt) noexcept
      -> ProducerAttemptResult {
    const auto call = producer_calls_.fetch_add(1U, std::memory_order_acq_rel);
    producer_logical_sequences_[call % kMaximumItems] = attempt.logical_sequence;
    producer_deadlines_[call % kMaximumItems] = attempt.scheduled_deadline;
    if (call == fail_producer_call_) {
      return {AttemptStatus::failure, EnqueueResult::full};
    }
    if (capacity_ == 0U) {
      return {AttemptStatus::complete, EnqueueResult::full};
    }
    const auto head = head_.load(std::memory_order_relaxed);
    const auto tail = tail_.load(std::memory_order_acquire);
    if (head - tail >= capacity_) {
      return {AttemptStatus::complete, EnqueueResult::full};
    }
    items_[head % kMaximumItems] = attempt.candidate_accepted_ordinal;
    head_.store(head + 1U, std::memory_order_release);
    return {AttemptStatus::complete, EnqueueResult::accepted};
  }

  [[nodiscard]] auto try_consumer_poll(std::uint64_t candidate_ordinal) noexcept
      -> ConsumerPollResult {
    consumer_calls_.fetch_add(1U, std::memory_order_relaxed);
    if (fail_when_finished_ != nullptr && fail_when_finished_->arrivals_finished()) {
      return {ConsumerPollStatus::failure};
    }
    if (always_item_when_finished_ != nullptr &&
        always_item_when_finished_->arrivals_finished()) {
      return {ConsumerPollStatus::item};
    }
    if (consumer_calls_.load(std::memory_order_relaxed) == fail_consumer_call_) {
      return {ConsumerPollStatus::failure};
    }
    if (hold_consumer_ &&
        producer_calls_.load(std::memory_order_acquire) < expected_attempts_) {
      return {ConsumerPollStatus::empty};
    }
    const auto tail = tail_.load(std::memory_order_relaxed);
    const auto head = head_.load(std::memory_order_acquire);
    if (tail == head) {
      return {ConsumerPollStatus::empty};
    }
    const auto value = items_[tail % kMaximumItems];
    if (value != candidate_ordinal) {
      corruption_.store(true, std::memory_order_relaxed);
      return {ConsumerPollStatus::failure};
    }
    consumed_[candidate_ordinal % kMaximumItems] = value;
    tail_.store(tail + 1U, std::memory_order_release);
    return {ConsumerPollStatus::item};
  }

  void fail_producer_at(std::uint64_t call) noexcept { fail_producer_call_ = call; }
  void fail_consumer_at(std::uint64_t call) noexcept { fail_consumer_call_ = call; }
  void fail_after_termination(const TerminationControl& termination) noexcept {
    fail_when_finished_ = &termination;
  }
  void return_items_after_termination(const TerminationControl& termination) noexcept {
    always_item_when_finished_ = &termination;
  }

  [[nodiscard]] auto producer_calls() const noexcept -> std::uint64_t {
    return producer_calls_.load(std::memory_order_acquire);
  }
  [[nodiscard]] auto corruption() const noexcept -> bool {
    return corruption_.load(std::memory_order_relaxed);
  }
  [[nodiscard]] auto producer_logical_sequence(std::size_t index) const noexcept
      -> std::uint64_t {
    return producer_logical_sequences_[index];
  }

private:
  const std::size_t capacity_;
  const std::uint64_t expected_attempts_;
  const bool hold_consumer_;
  std::array<std::uint64_t, kMaximumItems> items_{};
  std::array<std::uint64_t, kMaximumItems> producer_logical_sequences_{};
  std::array<std::uint64_t, kMaximumItems> producer_deadlines_{};
  std::array<std::uint64_t, kMaximumItems> consumed_{};
  std::atomic<std::uint64_t> head_{0U};
  std::atomic<std::uint64_t> tail_{0U};
  std::atomic<std::uint64_t> producer_calls_{0U};
  std::atomic<std::uint64_t> consumer_calls_{0U};
  std::atomic<bool> corruption_{false};
  std::uint64_t fail_producer_call_{kNever};
  std::uint64_t fail_consumer_call_{kNever};
  const TerminationControl* fail_when_finished_{nullptr};
  const TerminationControl* always_item_when_finished_{nullptr};
};

auto limits() -> ExecutionLimits {
  // Explicit test-fixture limits only. They are not platform defaults.
  return {10'000'000U, 10'000'000U, 10'000U, 10'000'000U, 10'000U};
}

TEST(LifecycleConcurrency, TerminationPublicationIsReleaseAcquireAndDedicated) {
  TerminationControl termination(kFixtureCacheLine);
  const auto evidence = termination.evidence();
  EXPECT_EQ(evidence.value_width_bytes, 4U);
  EXPECT_EQ(evidence.atomic_width_bytes, 4U);
  EXPECT_TRUE(evidence.always_lock_free);
  EXPECT_TRUE(evidence.runtime_lock_free);
  EXPECT_TRUE(evidence.dedicated_cache_line);

  for (std::uint64_t iteration = 1U; iteration <= 100U; ++iteration) {
    ASSERT_TRUE(termination.reset_quiescent(true));
    std::uint64_t published_payload = 0U;
    std::uint64_t observed_payload = 0U;
    std::thread consumer([&] {
      while (!termination.arrivals_finished()) {
        std::this_thread::yield();
      }
      observed_payload = published_payload;
    });
    published_payload = iteration;
    termination.publish_arrivals_finished();
    consumer.join();
    EXPECT_EQ(observed_payload, iteration);
  }
  EXPECT_FALSE(termination.reset_quiescent(false));
}

TEST(LifecycleConcurrency, StartBarrierPublishesOneExplicitMeasurementOrigin) {
  WorkerStartBarrier barrier;
  YieldRelax relax;
  std::atomic<bool> consumer_may_arrive{false};
  std::uint64_t producer_origin = 0U;
  std::uint64_t consumer_origin = 0U;

  std::thread producer([&] {
    ASSERT_EQ(barrier.arrive(WorkerRole::producer), StartBarrierStatus::ready);
    ASSERT_EQ(barrier.worker_wait(1'000'000U, [&] { relax.relax(); }),
              StartBarrierStatus::released);
    producer_origin = barrier.measurement_origin();
  });
  std::thread consumer([&] {
    while (!consumer_may_arrive.load(std::memory_order_acquire)) {
      std::this_thread::yield();
    }
    ASSERT_EQ(barrier.arrive(WorkerRole::consumer), StartBarrierStatus::ready);
    ASSERT_EQ(barrier.worker_wait(1'000'000U, [&] { relax.relax(); }),
              StartBarrierStatus::released);
    consumer_origin = barrier.measurement_origin();
  });

  EXPECT_FALSE(barrier.all_workers_ready());
  consumer_may_arrive.store(true, std::memory_order_release);
  ASSERT_EQ(barrier.controller_wait(1'000'000U, [&] { relax.relax(); }),
            StartBarrierStatus::ready);
  ASSERT_EQ(barrier.release_with_measurement_origin(987'654U),
            StartBarrierStatus::released);
  producer.join();
  consumer.join();
  EXPECT_EQ(producer_origin, 987'654U);
  EXPECT_EQ(consumer_origin, 987'654U);
}

TEST(LifecycleConcurrency, BacklogDrainsAfterProducerCompletionWithoutLoss) {
  constexpr std::array<std::uint64_t, 6U> deadlines{0U, 1U, 2U, 3U, 4U, 5U};
  TerminationControl termination(kFixtureCacheLine);
  FixedFakeBackend backend({16U, deadlines.size(), true});
  AtomicStepClock clock;
  YieldRelax relax;
  auto test_limits = limits();

  const auto report = cpu_prefetch::lifecycle::execute_measurement(
      PreparedScheduleView{deadlines, 0U, 6U}, clock, backend, termination, test_limits,
      relax);
  EXPECT_EQ(report.failure_phase, ExecutionFailurePhase::none);
  EXPECT_EQ(report.offered, deadlines.size());
  EXPECT_EQ(report.attempted, deadlines.size());
  EXPECT_EQ(report.accepted, deadlines.size());
  EXPECT_EQ(report.full, 0U);
  EXPECT_EQ(report.consumed, deadlines.size());
  EXPECT_TRUE(report.producer_completed);
  EXPECT_TRUE(report.consumer_drained);
  EXPECT_TRUE(report.arrivals_finished_published);
  EXPECT_GT(report.drain_polls, 0U);
  EXPECT_FALSE(backend.corruption());
}

TEST(LifecycleConcurrency, EmptyScheduleCompletesAndDrains) {
  const std::array<std::uint64_t, 0U> deadlines{};
  TerminationControl termination(kFixtureCacheLine);
  FixedFakeBackend backend({1U, 0U});
  AtomicStepClock clock;
  YieldRelax relax;
  const auto report = cpu_prefetch::lifecycle::execute_measurement(
      PreparedScheduleView{deadlines, 0U, 1U}, clock, backend, termination, limits(),
      relax);
  EXPECT_EQ(report.failure_phase, ExecutionFailurePhase::none);
  EXPECT_EQ(report.offered, 0U);
  EXPECT_EQ(report.attempted, 0U);
  EXPECT_EQ(report.consumed, 0U);
  EXPECT_TRUE(report.producer_completed);
  EXPECT_TRUE(report.consumer_drained);
}

TEST(LifecycleConcurrency, FullGetsExactlyOneAttemptAndIsNotAFailure) {
  constexpr std::array<std::uint64_t, 5U> deadlines{0U, 0U, 1U, 2U, 3U};
  TerminationControl termination(kFixtureCacheLine);
  FixedFakeBackend backend({0U, deadlines.size()});
  AtomicStepClock clock;
  YieldRelax relax;
  const auto report = cpu_prefetch::lifecycle::execute_measurement(
      PreparedScheduleView{deadlines, 0U, 4U}, clock, backend, termination, limits(),
      relax);
  EXPECT_EQ(report.failure_phase, ExecutionFailurePhase::none);
  EXPECT_EQ(backend.producer_calls(), deadlines.size());
  EXPECT_EQ(report.attempted, deadlines.size());
  EXPECT_EQ(report.full, deadlines.size());
  EXPECT_EQ(report.accepted, 0U);
  EXPECT_EQ(report.consumed, 0U);
  for (std::size_t index = 0U; index < deadlines.size(); ++index) {
    EXPECT_EQ(backend.producer_logical_sequence(index), index);
  }
}

TEST(LifecycleConcurrency, ProducerFailurePreservesPartialCountsWithoutRetry) {
  constexpr std::array<std::uint64_t, 4U> deadlines{0U, 1U, 2U, 3U};
  TerminationControl termination(kFixtureCacheLine);
  FixedFakeBackend backend({8U, deadlines.size()});
  backend.fail_producer_at(2U);
  AtomicStepClock clock;
  YieldRelax relax;
  const auto report = cpu_prefetch::lifecycle::execute_measurement(
      PreparedScheduleView{deadlines, 0U, 4U}, clock, backend, termination, limits(),
      relax);
  EXPECT_EQ(report.failure_phase, ExecutionFailurePhase::measurement);
  EXPECT_EQ(report.failure_reason, ExecutionFailureReason::producer_attempt);
  EXPECT_EQ(report.attempted, 3U);
  EXPECT_EQ(backend.producer_calls(), 3U);
  EXPECT_TRUE(report.arrivals_finished_published);
  EXPECT_TRUE(report.cancellation_requested);
}

TEST(LifecycleConcurrency, ProducerWaitWatchdogCancelsWithoutAnAttempt) {
  constexpr std::array<std::uint64_t, 1U> deadlines{5U};
  TerminationControl termination(kFixtureCacheLine);
  FixedFakeBackend backend({1U, deadlines.size()});
  AtomicStepClock clock({.step = 0U});
  YieldRelax relax;
  auto test_limits = limits();
  test_limits.producer_due_poll_limit_per_arrival = 8U;
  const auto report = cpu_prefetch::lifecycle::execute_measurement(
      PreparedScheduleView{deadlines, 0U, 6U}, clock, backend, termination, test_limits,
      relax);
  EXPECT_EQ(report.failure_phase, ExecutionFailurePhase::measurement);
  EXPECT_EQ(report.failure_reason, ExecutionFailureReason::producer_wait_watchdog);
  EXPECT_EQ(report.attempted, 0U);
  EXPECT_EQ(backend.producer_calls(), 0U);
}

TEST(LifecycleConcurrency, InvalidPreparedInputFailsBeforeWorkersStart) {
  constexpr std::array<std::uint64_t, 1U> deadline_at_horizon{1U};
  TerminationControl termination(kFixtureCacheLine);
  FixedFakeBackend backend({1U, deadline_at_horizon.size()});
  AtomicStepClock clock;
  YieldRelax relax;
  auto report = cpu_prefetch::lifecycle::execute_measurement(
      PreparedScheduleView{deadline_at_horizon, 0U, 1U}, clock, backend, termination,
      limits(), relax);
  EXPECT_EQ(report.failure_phase, ExecutionFailurePhase::pre_run);
  EXPECT_EQ(report.failure_reason, ExecutionFailureReason::invalid_schedule);
  EXPECT_EQ(backend.producer_calls(), 0U);

  const std::array<std::uint64_t, 0U> empty{};
  auto invalid_limits = limits();
  invalid_limits.drain_poll_limit = 0U;
  report = cpu_prefetch::lifecycle::execute_measurement(
      PreparedScheduleView{empty, 0U, 1U}, clock, backend, termination, invalid_limits,
      relax);
  EXPECT_EQ(report.failure_phase, ExecutionFailurePhase::pre_run);
  EXPECT_EQ(report.failure_reason, ExecutionFailureReason::invalid_limits);
}

TEST(LifecycleConcurrency, ConsumerFailureRemainsPrimaryWhenProducerIsCancelled) {
  constexpr std::array<std::uint64_t, 1U> deadlines{100U};
  TerminationControl termination(kFixtureCacheLine);
  FixedFakeBackend backend({1U, deadlines.size()});
  backend.fail_consumer_at(1U);
  AtomicStepClock clock({.step = 0U});
  YieldRelax relax;
  const auto report = cpu_prefetch::lifecycle::execute_measurement(
      PreparedScheduleView{deadlines, 0U, 101U}, clock, backend, termination, limits(),
      relax);
  EXPECT_EQ(report.failure_phase, ExecutionFailurePhase::measurement);
  EXPECT_EQ(report.failure_reason, ExecutionFailureReason::consumer_poll);
  EXPECT_TRUE(report.cancellation_requested);
  EXPECT_EQ(backend.producer_calls(), 0U);
}

TEST(LifecycleConcurrency, DrainFailureAndWatchdogAreDistinctFromMeasurement) {
  {
    constexpr std::array<std::uint64_t, 1U> deadlines{0U};
    TerminationControl termination(kFixtureCacheLine);
    FixedFakeBackend backend({1U, deadlines.size(), true});
    backend.fail_after_termination(termination);
    AtomicStepClock clock;
    YieldRelax relax;
    const auto report = cpu_prefetch::lifecycle::execute_measurement(
        PreparedScheduleView{deadlines, 0U, 1U}, clock, backend, termination, limits(),
        relax);
    EXPECT_EQ(report.failure_phase, ExecutionFailurePhase::drain);
    EXPECT_EQ(report.failure_reason, ExecutionFailureReason::consumer_poll);
  }
  {
    const std::array<std::uint64_t, 0U> deadlines{};
    TerminationControl termination(kFixtureCacheLine);
    FixedFakeBackend backend({1U, 0U});
    backend.return_items_after_termination(termination);
    AtomicStepClock clock;
    YieldRelax relax;
    auto test_limits = limits();
    test_limits.drain_poll_limit = 5U;
    const auto report = cpu_prefetch::lifecycle::execute_measurement(
        PreparedScheduleView{deadlines, 0U, 1U}, clock, backend, termination,
        test_limits, relax);
    EXPECT_EQ(report.failure_phase, ExecutionFailurePhase::drain);
    EXPECT_EQ(report.failure_reason, ExecutionFailureReason::drain_watchdog);
    EXPECT_EQ(report.drain_polls, 6U);
  }
}

TEST(LifecycleConcurrency, StartClockFailureCancelsBothWorkers) {
  const std::array<std::uint64_t, 0U> deadlines{};
  TerminationControl termination(kFixtureCacheLine);
  FixedFakeBackend backend({1U, 0U});
  AtomicStepClock clock({.fail_at = 0U});
  YieldRelax relax;
  const auto report = cpu_prefetch::lifecycle::execute_measurement(
      PreparedScheduleView{deadlines, 0U, 1U}, clock, backend, termination, limits(),
      relax);
  EXPECT_EQ(report.failure_phase, ExecutionFailurePhase::start_barrier);
  EXPECT_EQ(report.failure_reason, ExecutionFailureReason::clock_read);
  EXPECT_TRUE(report.cancellation_requested);
  EXPECT_EQ(report.attempted, 0U);
}

TEST(LifecycleConcurrency, RandomizedDeterministicStressHasNoDuplicateOrOmission) {
  std::uint64_t state = 0x9e3779b97f4a7c15ULL;
  for (std::uint64_t iteration = 0U; iteration < 100U; ++iteration) {
    state ^= state << 7U;
    state ^= state >> 9U;
    const auto count = std::size_t{1U + (state % 64U)};
    std::vector<std::uint64_t> deadlines(count);
    for (std::size_t index = 0U; index < count; ++index) {
      deadlines[index] = index / 3U;
    }
    TerminationControl termination(kFixtureCacheLine);
    FixedFakeBackend backend({count, count, (iteration % 2U) == 0U});
    AtomicStepClock clock;
    YieldRelax relax;
    const auto report = cpu_prefetch::lifecycle::execute_measurement(
        PreparedScheduleView{deadlines, 0U, deadlines.back() + 1U}, clock, backend,
        termination, limits(), relax);
    ASSERT_EQ(report.failure_phase, ExecutionFailurePhase::none) << iteration;
    EXPECT_EQ(report.attempted, count);
    EXPECT_EQ(report.accepted, count);
    EXPECT_EQ(report.consumed, count);
    EXPECT_FALSE(backend.corruption());
  }
}

} // namespace
