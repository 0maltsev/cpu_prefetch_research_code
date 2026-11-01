#include "cpu_prefetch/calibration/discovery_session.hpp"

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

} // namespace
