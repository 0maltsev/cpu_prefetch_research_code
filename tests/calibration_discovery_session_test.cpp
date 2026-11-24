#include "cpu_prefetch/calibration/discovery_session.hpp"
#include "worker_stack_test_support.hpp"

#include <gtest/gtest.h>

#include <atomic>
#include <limits>
#include <stdexcept>
#include <thread>

namespace {
namespace calibration = cpu_prefetch::calibration;
namespace queue = cpu_prefetch::queue;
namespace timing = cpu_prefetch::timing;

class SessionClock final {
public:
  explicit SessionClock(bool fail_origin = false, std::uint64_t initial_tick = 0U)
      : next_(initial_tick), fail_origin_(fail_origin) {}
  auto read() noexcept -> timing::ClockReadResult {
    const auto tick = next_.fetch_add(1U, std::memory_order_relaxed);
    return (tick == 0U && fail_origin_) ||
                   tick == fail_at_.load(std::memory_order_relaxed)
               ? timing::ClockReadResult{timing::ClockReadStatus::call_failed, {0U, 0U}}
               : timing::ClockReadResult{timing::ClockReadStatus::ok, {0U, tick}};
  }
  void fail_after_one_more_read() noexcept {
    fail_at_.store(next_.load(std::memory_order_relaxed) + 1U,
                   std::memory_order_relaxed);
  }

private:
  std::atomic<std::uint64_t> next_{0U};
  std::atomic<std::uint64_t> fail_at_{std::numeric_limits<std::uint64_t>::max()};
  bool fail_origin_;
};

struct YieldRelax final {
  void relax() const noexcept { std::this_thread::yield(); }
};

struct BackendConfig final {
  bool reject_producer{false};
  bool throw_consumer{false};
  bool reject_warmup{false};
  bool reject_reset{false};
  bool fail_measurement{false};
  std::size_t measurement_capacity{20'000U};
  bool reject_producer_reset{false};
  bool fail_warmup_drain{false};
  bool throw_measurement_validation{false};
};

class RealRingBackend final {
public:
  explicit RealRingBackend(SessionClock& clock, BackendConfig config = {})
      : clock_(clock), config_(config),
        measurement_trace_(config.measurement_capacity) {}
  auto prepare_producer() -> bool {
    producer_thread_ = std::this_thread::get_id();
    return !config_.reject_producer &&
           warmup_trace_.prepare_worker(calibration::RingWorker::producer) &&
           measurement_trace_.prepare_worker(calibration::RingWorker::producer);
  }
  auto prepare_consumer() -> bool {
    consumer_thread_ = std::this_thread::get_id();
    if (config_.throw_consumer) {
      throw std::runtime_error("injected preparation failure");
    }
    return warmup_trace_.prepare_worker(calibration::RingWorker::consumer) &&
           measurement_trace_.prepare_worker(calibration::RingWorker::consumer);
  }
  auto warmup_producer_attempt() noexcept -> calibration::RingCaptureResult {
    return calibration::capture_producer_ring_demand(clock_, ring_, pointer(),
                                                     warmup_trace_);
  }
  auto warmup_consumer_attempt() noexcept -> calibration::RingCaptureResult {
    return calibration::capture_consumer_ring_demand(clock_, ring_, warmup_trace_);
  }
  auto measurement_producer_attempt() noexcept -> calibration::RingCaptureResult {
    return calibration::capture_producer_ring_demand(clock_, ring_, pointer(),
                                                     measurement_trace_);
  }
  auto measurement_consumer_attempt() noexcept -> calibration::RingCaptureResult {
    return calibration::capture_consumer_ring_demand(clock_, ring_, measurement_trace_);
  }
  auto ring() noexcept -> queue::RingSpscQueue& { return ring_; }
  auto consume_warmup_drain(const void* event) const noexcept -> bool {
    return event == &event_ && std::this_thread::get_id() == consumer_thread_;
  }
  auto consume_measurement_drain(const void* event) const noexcept -> bool {
    return event == &event_ && std::this_thread::get_id() == consumer_thread_;
  }
  auto reset_producer() noexcept -> bool {
    producer_reset_on_owner_ = std::this_thread::get_id() == producer_thread_;
    if (config_.fail_measurement) {
      clock_.fail_after_one_more_read();
    }
    return producer_reset_on_owner_ && !config_.reject_producer_reset;
  }
  auto reset_consumer() noexcept -> bool {
    consumer_reset_on_owner_ = std::this_thread::get_id() == consumer_thread_;
    return consumer_reset_on_owner_ && !config_.reject_reset;
  }
  auto validate_warmup(
      const std::array<calibration::DiscoveryWorkerResult, 2U>& workers) const noexcept
      -> bool {
    if (config_.fail_warmup_drain) {
      clock_.fail_after_one_more_read();
    }
    return !config_.reject_warmup && validate(workers, warmup_trace_);
  }
  auto validate_measurement(
      const std::array<calibration::DiscoveryWorkerResult, 2U>& workers) const -> bool {
    if (config_.throw_measurement_validation) {
      throw std::runtime_error("injected post-capture failure");
    }
    return validate(workers, measurement_trace_);
  }
  auto resets_on_owners() const noexcept -> bool {
    return producer_reset_on_owner_ && consumer_reset_on_owner_;
  }
  auto measurement_trace() const noexcept -> const calibration::RingDemandTrace& {
    return measurement_trace_;
  }

private:
  auto pointer() const noexcept -> queue::EventPointer { return event_pointer_; }
  static auto make_pointer(const void* event) -> queue::EventPointer {
    const auto pointer = queue::EventPointer::from(event);
    if (pointer.has_value()) {
      return pointer.value();
    }
    throw std::logic_error("invalid synthetic event pointer");
  }
  static auto
  validate(const std::array<calibration::DiscoveryWorkerResult, 2U>& workers,
           const calibration::RingDemandTrace& trace) noexcept -> bool {
    for (std::size_t index = 0U; index < 2U; ++index) {
      const auto worker = index == 0U ? calibration::RingWorker::producer
                                      : calibration::RingWorker::consumer;
      const auto checked = calibration::validate_quiescent_discovery_trace(
          worker, workers[index], trace);
      if (checked.stop != calibration::DiscoveryWorkerStop::fixed_deadline &&
          checked.stop != calibration::DiscoveryWorkerStop::trace_capacity &&
          checked.stop != calibration::DiscoveryWorkerStop::peer_stopped) {
        return false;
      }
    }
    return true;
  }
  SessionClock& clock_;
  BackendConfig config_;
  int event_{7};
  const queue::EventPointer event_pointer_{make_pointer(&event_)};
  queue::RingSpscQueue ring_{{8U}, {64U}};
  calibration::RingDemandTrace warmup_trace_{20'000U};
  calibration::RingDemandTrace measurement_trace_;
  std::thread::id producer_thread_;
  std::thread::id consumer_thread_;
  bool producer_reset_on_owner_{false};
  bool consumer_reset_on_owner_{false};
};

constexpr calibration::DiscoverySessionPlan kPlan{20'000U, 20'000U, 20'000U,   20'000U,
                                                  1'000U,  9U,      1'000'000U};

TEST(DiscoverySession, PersistentWorkersWarmupDrainResetMeasureAndReconcile) {
  SessionClock clock;
  RealRingBackend backend(clock);
  YieldRelax relax;
  const auto result = calibration::run_discovery_session(kPlan, clock, backend, relax);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::complete);
  EXPECT_TRUE(result.warmup_verified);
  EXPECT_TRUE(result.warmup_drain.reset_verified);
  EXPECT_TRUE(result.measurement_verified);
  EXPECT_TRUE(backend.resets_on_owners());
  EXPECT_TRUE(result.origins[0].has_value());
  EXPECT_TRUE(result.origins[1].has_value());
  EXPECT_EQ(result.warmup[0].advanced,
            result.warmup[1].advanced + result.warmup_drain.dequeued);
  EXPECT_EQ(result.measurement[0].advanced,
            result.measurement[1].advanced + result.measurement_drain.dequeued);
  EXPECT_EQ(backend.measurement_trace().series().producer_demand_ticks.size(),
            result.measurement[0].attempts);
  EXPECT_EQ(backend.ring().audit_quiescent().occupied_slots, 0U);
  for (const auto& phase : result.observations) {
    EXPECT_EQ(phase.before, calibration::DiscoveryObservationStatus::not_configured);
    EXPECT_EQ(phase.during, calibration::DiscoveryObservationStatus::not_configured);
    EXPECT_EQ(phase.after, calibration::DiscoveryObservationStatus::not_configured);
  }
}

TEST(DiscoverySession, CallerStorageRetainsResultsAndRejectsReuseWithoutMutation) {
  SessionClock clock;
  RealRingBackend backend(clock);
  YieldRelax relax;
  calibration::NoDiscoveryControllerObserver observer;
  calibration::StandardDiscoveryThreads threads;
  calibration::DiscoverySessionStorage storage;
  const auto result = calibration::run_discovery_session(kPlan, clock, backend, relax,
                                                         observer, threads, storage);
  ASSERT_EQ(result.stop, calibration::DiscoverySessionStop::complete);
  EXPECT_EQ(storage.result.stop, result.stop);
  EXPECT_EQ(storage.result.origins, result.origins);
  EXPECT_EQ(storage.measurement_finished.load(), 3U);
  EXPECT_EQ(storage.warmup_finished.load(), 3U);
  EXPECT_EQ(storage.measurement_barrier.measurement_origin(), result.origins[1U]);
  const auto rejected = calibration::run_discovery_session(kPlan, clock, backend, relax,
                                                           observer, threads, storage);
  EXPECT_EQ(rejected.stop, calibration::DiscoverySessionStop::storage_already_used);
  EXPECT_EQ(storage.result.stop, calibration::DiscoverySessionStop::complete);
  EXPECT_EQ(storage.result.origins, result.origins);
  EXPECT_EQ(storage.result.measurement[0U].attempts, result.measurement[0U].attempts);
  EXPECT_EQ(rejected.measurement[0U].attempts, 0U);
}

TEST(DiscoverySession, InvalidPlanConsumesItsStorageWithoutStartingWorkers) {
  SessionClock clock;
  RealRingBackend backend(clock);
  YieldRelax relax;
  calibration::NoDiscoveryControllerObserver observer;
  calibration::StandardDiscoveryThreads threads;
  calibration::DiscoverySessionStorage storage;
  auto invalid = kPlan;
  invalid.warmup_duration_ticks = 0U;
  const auto result = calibration::run_discovery_session(invalid, clock, backend, relax,
                                                         observer, threads, storage);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::invalid_plan);
  const auto rejected = calibration::run_discovery_session(kPlan, clock, backend, relax,
                                                           observer, threads, storage);
  EXPECT_EQ(rejected.stop, calibration::DiscoverySessionStop::storage_already_used);
  EXPECT_EQ(storage.result.stop, calibration::DiscoverySessionStop::invalid_plan);
  EXPECT_FALSE(storage.result.origins[0U].has_value());
  EXPECT_EQ(storage.warmup_finished.load(), 0U);
}

TEST(DiscoverySession, MappedWorkersPersistAcrossBothPhases) {
  SessionClock clock;
  RealRingBackend backend(clock);
  YieldRelax relax;
  cpu_prefetch::test::SoftwareStackOperations producer_ops;
  cpu_prefetch::test::SoftwareStackOperations consumer_ops;
  const auto plan = cpu_prefetch::test::software_stack_plan();
  cpu_prefetch::platform::MappedWorkerThread producer(plan, producer_ops);
  cpu_prefetch::platform::MappedWorkerThread consumer(plan, consumer_ops);
  calibration::MappedDiscoveryThreads threads(
      calibration::DiscoveryWorkerStacks{producer, consumer});
  calibration::NoDiscoveryControllerObserver observer;
  const auto result = calibration::run_discovery_session(kPlan, clock, backend, relax,
                                                         observer, threads);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::complete);
  EXPECT_TRUE(backend.resets_on_owners());
  EXPECT_TRUE(producer.prepared());
  EXPECT_TRUE(consumer.prepared());
  EXPECT_EQ(producer.evidence().thread.join, 0);
  EXPECT_EQ(consumer.evidence().thread.join, 0);
  EXPECT_EQ(producer_ops.observations, 2U);
  EXPECT_EQ(consumer_ops.observations, 2U);
}

TEST(DiscoverySession, StackPreparationFailureCancelsBeforeBackendAndPhaseRelease) {
  for (const auto role :
       {calibration::RingWorker::producer, calibration::RingWorker::consumer}) {
    SessionClock clock;
    RealRingBackend backend(clock);
    YieldRelax relax;
    cpu_prefetch::test::SoftwareStackOperations producer_ops;
    cpu_prefetch::test::SoftwareStackOperations consumer_ops;
    auto& failed =
        role == calibration::RingWorker::producer ? producer_ops : consumer_ops;
    failed.failure = cpu_prefetch::test::SoftwareStackOperations::Failure::populate;
    const auto plan = cpu_prefetch::test::software_stack_plan();
    cpu_prefetch::platform::MappedWorkerThread producer(plan, producer_ops);
    cpu_prefetch::platform::MappedWorkerThread consumer(plan, consumer_ops);
    calibration::MappedDiscoveryThreads threads(
        calibration::DiscoveryWorkerStacks{producer, consumer});
    calibration::NoDiscoveryControllerObserver observer;
    const auto result = calibration::run_discovery_session(kPlan, clock, backend, relax,
                                                           observer, threads);
    EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::preparation_failure);
    EXPECT_EQ(result.preparation[role == calibration::RingWorker::producer ? 0U : 1U],
              calibration::DiscoveryPreparationStatus::rejected);
    EXPECT_FALSE(result.origins[0U].has_value());
    EXPECT_FALSE(result.origins[1U].has_value());
    EXPECT_EQ(result.warmup[0U].attempts, 0U);
    EXPECT_EQ(result.warmup[1U].attempts, 0U);
    EXPECT_EQ(producer.evidence().thread.join, 0);
    EXPECT_EQ(consumer.evidence().thread.join, 0);
  }
}

TEST(DiscoverySession, SecondThreadLaunchFailureCancelsAndJoinsFirstWorker) {
  SessionClock clock;
  RealRingBackend backend(clock);
  YieldRelax relax;
  cpu_prefetch::test::SoftwareStackOperations producer_ops;
  cpu_prefetch::test::SoftwareStackOperations consumer_ops;
  const auto plan = cpu_prefetch::test::software_stack_plan();
  auto bad = plan;
  bad.owner_cpu = std::numeric_limits<std::uint32_t>::max();
  cpu_prefetch::platform::MappedWorkerThread producer(plan, producer_ops);
  cpu_prefetch::platform::MappedWorkerThread consumer(bad, consumer_ops);
  calibration::MappedDiscoveryThreads threads(
      calibration::DiscoveryWorkerStacks{producer, consumer});
  calibration::NoDiscoveryControllerObserver observer;
  const auto result = calibration::run_discovery_session(kPlan, clock, backend, relax,
                                                         observer, threads);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::thread_start_failure);
  EXPECT_EQ(producer.evidence().thread.join, 0);
  EXPECT_FALSE(consumer.evidence().thread.create.has_value());
  EXPECT_FALSE(result.origins[0U].has_value());
  EXPECT_FALSE(result.origins[1U].has_value());
  EXPECT_TRUE(producer.release());
}

TEST(DiscoverySession, RejectedOrThrowingPreparationCannotStartEitherPhase) {
  for (const bool throwing : {false, true}) {
    SessionClock clock;
    RealRingBackend backend(clock,
                            {.reject_producer = !throwing, .throw_consumer = throwing});
    YieldRelax relax;
    const auto result =
        calibration::run_discovery_session(kPlan, clock, backend, relax);
    EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::preparation_failure);
    EXPECT_FALSE(result.origins[0].has_value());
    EXPECT_FALSE(result.origins[1].has_value());
    EXPECT_EQ(result.measurement[0].attempts, 0U);
    EXPECT_EQ(result.measurement[1].attempts, 0U);
  }
}

TEST(DiscoverySession, OriginClockFailureCancelsBothPreparedWorkers) {
  SessionClock clock(true);
  RealRingBackend backend(clock);
  YieldRelax relax;
  const auto result = calibration::run_discovery_session(kPlan, clock, backend, relax);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::start_failure);
  EXPECT_EQ(result.origin_status[0], timing::ClockReadStatus::call_failed);
  EXPECT_FALSE(result.origins[0].has_value());
  EXPECT_EQ(result.warmup[0].attempts, 0U);
  EXPECT_EQ(result.warmup[1].attempts, 0U);
}

TEST(DiscoverySession, FailedWarmupValidationOrPrivateResetCannotStartMeasurement) {
  for (const bool reset : {false, true}) {
    SessionClock clock;
    RealRingBackend backend(clock, {.reject_warmup = !reset, .reject_reset = reset});
    YieldRelax relax;
    const auto result =
        calibration::run_discovery_session(kPlan, clock, backend, relax);
    EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::warmup_failure);
    EXPECT_TRUE(result.origins[0].has_value());
    EXPECT_FALSE(result.origins[1].has_value());
    EXPECT_EQ(result.measurement[0].attempts, 0U);
    EXPECT_EQ(result.measurement[1].attempts, 0U);
  }
}

TEST(DiscoverySession, MeasurementClockFailureRetainsWarmupAndFailureEvidence) {
  SessionClock clock;
  RealRingBackend backend(clock, {.fail_measurement = true});
  YieldRelax relax;
  const auto result = calibration::run_discovery_session(kPlan, clock, backend, relax);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::measurement_failure);
  EXPECT_TRUE(result.warmup_verified);
  EXPECT_TRUE(result.measurement[0].failed_clock_status.has_value() ||
              result.measurement[1].failed_clock_status.has_value());
  EXPECT_EQ(result.measurement_drain.stop, calibration::DiscoveryDrainStop::complete);
}

TEST(DiscoverySession, ExhaustedMeasurementCapacityIsRetainedWithoutAnExtension) {
  SessionClock clock;
  RealRingBackend backend(clock, {.measurement_capacity = 1U});
  YieldRelax relax;
  auto plan = kPlan;
  plan.measurement_attempt_capacity = 1U;
  const auto result = calibration::run_discovery_session(plan, clock, backend, relax);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::trace_capacity);
  EXPECT_LE(result.measurement[0].attempts, 1U);
  EXPECT_LE(result.measurement[1].attempts, 1U);
  EXPECT_EQ(result.measurement_drain.stop, calibration::DiscoveryDrainStop::complete);
}

TEST(DiscoverySession, InvalidPlanDoesNotPrepareOrStartWorkers) {
  SessionClock clock;
  RealRingBackend backend(clock);
  YieldRelax relax;
  auto plan = kPlan;
  plan.measurement_duration_ticks = 0U;
  const auto result = calibration::run_discovery_session(plan, clock, backend, relax);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::invalid_plan);
  EXPECT_EQ(result.preparation[0],
            calibration::DiscoveryPreparationStatus::not_started);
  EXPECT_EQ(result.preparation[1],
            calibration::DiscoveryPreparationStatus::not_started);
}

TEST(DiscoverySession, ProducerResetFailureCancelsTheWaitingConsumer) {
  SessionClock clock;
  RealRingBackend backend(clock, {.reject_producer_reset = true});
  YieldRelax relax;
  const auto result = calibration::run_discovery_session(kPlan, clock, backend, relax);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::warmup_failure);
  EXPECT_TRUE(result.warmup_drain.reset_verified);
  EXPECT_FALSE(result.private_reset_verified[0]);
  EXPECT_TRUE(result.private_reset_verified[1]);
  EXPECT_FALSE(result.origins[1].has_value());
}

TEST(DiscoverySession, WarmupDrainClockFailurePreventsResetAndMeasurement) {
  SessionClock clock;
  RealRingBackend backend(clock, {.fail_warmup_drain = true});
  YieldRelax relax;
  const auto result = calibration::run_discovery_session(kPlan, clock, backend, relax);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::warmup_failure);
  EXPECT_EQ(result.warmup_drain.stop, calibration::DiscoveryDrainStop::clock_failure);
  EXPECT_EQ(result.warmup_drain.failed_clock_status,
            timing::ClockReadStatus::call_failed);
  EXPECT_FALSE(result.warmup_drain.reset_verified);
  EXPECT_FALSE(result.origins[1].has_value());
}

TEST(DiscoverySession, OverflowRetainsTheObservedClockWithoutReleasingWorkers) {
  constexpr auto observed = std::numeric_limits<std::uint64_t>::max() - 1U;
  SessionClock clock(false, observed);
  RealRingBackend backend(clock);
  YieldRelax relax;
  const auto result = calibration::run_discovery_session(kPlan, clock, backend, relax);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::start_failure);
  EXPECT_EQ(result.origin_status[0], timing::ClockReadStatus::ok);
  EXPECT_EQ(result.observed_origins[0], observed);
  EXPECT_FALSE(result.origins[0].has_value());
  EXPECT_EQ(result.warmup[0].attempts, 0U);
  EXPECT_EQ(result.warmup[1].attempts, 0U);
}

TEST(DiscoverySession, PostCaptureExceptionJoinsWorkersAndRetainsTheirResults) {
  SessionClock clock;
  RealRingBackend backend(clock, {.throw_measurement_validation = true});
  YieldRelax relax;
  const auto result = calibration::run_discovery_session(kPlan, clock, backend, relax);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::worker_exception);
  EXPECT_TRUE(result.worker_exception[1]);
  EXPECT_TRUE(result.warmup_verified);
  EXPECT_EQ(result.measurement[0].stop,
            calibration::DiscoveryWorkerStop::fixed_deadline);
  EXPECT_EQ(result.measurement[1].stop,
            calibration::DiscoveryWorkerStop::fixed_deadline);
  EXPECT_EQ(result.measurement_drain.stop,
            calibration::DiscoveryDrainStop::invalid_plan);
}

class ControllerObserver final {
public:
  std::array<std::size_t, 6U> calls{};
  std::array<std::uint64_t, 2U> origins{};
  std::array<std::uint64_t, 2U> durations{};
  std::array<std::uint32_t, 2U> completion_masks{};
  std::size_t count{0U};
  std::size_t failed_hook{6U};
  bool throwing{false};
  bool wait_for_completion{true};
  bool controller_only{true};

  auto before_phase(calibration::DiscoverySessionPhase phase) -> bool {
    return observe(phase, 0U);
  }
  auto during_phase(calibration::DiscoverySessionPhase phase,
                    calibration::DiscoveryObservationWindow window,
                    const std::atomic<std::uint32_t>& finished) -> bool {
    const auto index = static_cast<std::size_t>(phase);
    origins[index] = window.origin_ticks;
    durations[index] = window.duration_ticks;
    if (wait_for_completion) {
      for (std::uint64_t poll = 0U; poll < kPlan.barrier_poll_limit; ++poll) {
        if (finished.load(std::memory_order_acquire) == 3U) {
          break;
        }
        std::this_thread::yield();
      }
    }
    completion_masks[index] = finished.load(std::memory_order_acquire);
    return observe(phase, 1U);
  }
  auto after_phase(calibration::DiscoverySessionPhase phase) -> bool {
    return observe(phase, 2U);
  }

private:
  auto observe(calibration::DiscoverySessionPhase phase, std::size_t boundary) -> bool {
    controller_only = controller_only && std::this_thread::get_id() == controller_;
    const auto hook = static_cast<std::size_t>(phase) * 3U + boundary;
    calls[count++] = hook;
    if (throwing && hook == failed_hook) {
      throw std::runtime_error("injected controller observation failure");
    }
    return hook != failed_hook;
  }
  std::thread::id controller_{std::this_thread::get_id()};
};

TEST(DiscoverySession, ControllerObservesBothFixedPhasesAndRetainsActualHookStatus) {
  SessionClock clock;
  RealRingBackend backend(clock);
  YieldRelax relax;
  ControllerObserver observer;
  const auto result =
      calibration::run_discovery_session(kPlan, clock, backend, relax, observer);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::complete);
  EXPECT_TRUE(observer.controller_only);
  EXPECT_EQ(observer.count, 6U);
  EXPECT_EQ(observer.calls, (std::array<std::size_t, 6U>{0U, 1U, 2U, 3U, 4U, 5U}));
  for (std::size_t phase = 0U; phase < 2U; ++phase) {
    EXPECT_EQ(result.observations[phase].before,
              calibration::DiscoveryObservationStatus::accepted);
    EXPECT_EQ(result.observations[phase].during,
              calibration::DiscoveryObservationStatus::accepted);
    EXPECT_EQ(result.observations[phase].after,
              calibration::DiscoveryObservationStatus::accepted);
    EXPECT_EQ(result.origins[phase], observer.origins[phase]);
    EXPECT_EQ(observer.completion_masks[phase], 3U);
  }
  EXPECT_EQ(observer.durations[0U], kPlan.warmup_duration_ticks);
  EXPECT_EQ(observer.durations[1U], kPlan.measurement_duration_ticks);
  EXPECT_TRUE(result.warmup_drain.reset_verified);
  EXPECT_TRUE(backend.resets_on_owners());
}

TEST(DiscoverySession, EveryRejectedOrThrowingObservationBlocksSuccessAndRetainsDrain) {
  for (const bool throwing : {false, true}) {
    for (std::size_t failed_hook = 0U; failed_hook < 6U; ++failed_hook) {
      SessionClock clock;
      RealRingBackend backend(clock);
      YieldRelax relax;
      ControllerObserver observer;
      observer.failed_hook = failed_hook;
      observer.throwing = throwing;
      const auto result =
          calibration::run_discovery_session(kPlan, clock, backend, relax, observer);
      EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::observation_failure);
      EXPECT_TRUE(observer.controller_only);
      const auto& observed = result.observations[failed_hook / 3U];
      const std::array statuses{observed.before, observed.during, observed.after};
      EXPECT_EQ(statuses[failed_hook % 3U],
                throwing ? calibration::DiscoveryObservationStatus::exception
                         : calibration::DiscoveryObservationStatus::rejected);
      if (failed_hook <= 3U) {
        EXPECT_FALSE(result.origins[1U].has_value());
        EXPECT_EQ(result.measurement[0U].attempts, 0U);
        EXPECT_EQ(result.measurement[1U].attempts, 0U);
      }
      if (failed_hook == 0U) {
        EXPECT_FALSE(result.origins[0U].has_value());
        EXPECT_EQ(observer.count, 1U);
        EXPECT_EQ(result.warmup[0U].attempts, 0U);
        EXPECT_EQ(result.warmup[1U].attempts, 0U);
      } else {
        EXPECT_TRUE(result.warmup_verified);
        EXPECT_EQ(result.warmup_drain.stop, calibration::DiscoveryDrainStop::complete);
        EXPECT_EQ(result.warmup[0U].advanced,
                  result.warmup[1U].advanced + result.warmup_drain.dequeued);
        EXPECT_EQ(result.warmup_drain.reset_verified, failed_hook >= 3U);
      }
      if (failed_hook >= 4U) {
        // The failed observation is deliberately reported after both workers
        // have already reached their deadlines. It still invalidates the run.
        EXPECT_EQ(observer.completion_masks[1U], 3U);
        EXPECT_EQ(result.measurement[0U].stop,
                  calibration::DiscoveryWorkerStop::fixed_deadline);
        EXPECT_EQ(result.measurement[1U].stop,
                  calibration::DiscoveryWorkerStop::fixed_deadline);
        EXPECT_TRUE(result.measurement_verified);
        EXPECT_EQ(result.measurement_drain.stop,
                  calibration::DiscoveryDrainStop::complete);
        EXPECT_EQ(result.measurement[0U].advanced,
                  result.measurement[1U].advanced + result.measurement_drain.dequeued);
      }
      EXPECT_EQ(backend.ring().audit_quiescent().occupied_slots, 0U);
    }
  }
}

TEST(DiscoverySession,
     EarlyControllerRejectionStopsCaptureWithoutSkippingBoundedDrain) {
  SessionClock clock;
  RealRingBackend backend(clock);
  YieldRelax relax;
  ControllerObserver observer;
  observer.wait_for_completion = false;
  observer.failed_hook = 4U;
  const auto result =
      calibration::run_discovery_session(kPlan, clock, backend, relax, observer);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::observation_failure);
  EXPECT_TRUE(result.warmup_verified);
  EXPECT_TRUE(result.warmup_drain.reset_verified);
  EXPECT_TRUE(result.origins[1U].has_value());
  EXPECT_EQ(result.measurement_drain.stop, calibration::DiscoveryDrainStop::complete);
  EXPECT_EQ(result.measurement[0U].advanced,
            result.measurement[1U].advanced + result.measurement_drain.dequeued);
  EXPECT_LE(result.measurement[0U].attempts, kPlan.measurement_attempt_capacity);
  EXPECT_LE(result.measurement[1U].attempts, kPlan.measurement_attempt_capacity);
  EXPECT_EQ(backend.ring().audit_quiescent().occupied_slots, 0U);
}

TEST(DiscoverySession, PreparationAndInvalidPlanFailuresDoNotInventObservations) {
  for (const bool invalid_plan : {false, true}) {
    SessionClock clock;
    RealRingBackend backend(clock, {.reject_producer = true});
    YieldRelax relax;
    ControllerObserver observer;
    auto plan = kPlan;
    if (invalid_plan) {
      plan.drain_attempt_capacity = 0U;
    }
    const auto result =
        calibration::run_discovery_session(plan, clock, backend, relax, observer);
    EXPECT_EQ(result.stop,
              invalid_plan ? calibration::DiscoverySessionStop::invalid_plan
                           : calibration::DiscoverySessionStop::preparation_failure);
    EXPECT_EQ(observer.count, 0U);
    for (const auto& phase : result.observations) {
      EXPECT_EQ(phase.before, calibration::DiscoveryObservationStatus::not_started);
      EXPECT_EQ(phase.during, calibration::DiscoveryObservationStatus::not_started);
      EXPECT_EQ(phase.after, calibration::DiscoveryObservationStatus::not_started);
    }
  }
}

} // namespace
