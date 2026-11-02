#ifndef CPU_PREFETCH_CALIBRATION_DISCOVERY_SESSION_HPP
#define CPU_PREFETCH_CALIBRATION_DISCOVERY_SESSION_HPP

#include "cpu_prefetch/calibration/discovery_capture.hpp"
#include "cpu_prefetch/calibration/discovery_thread_launcher.hpp"
#include "cpu_prefetch/lifecycle/runtime.hpp"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <thread>
#include <type_traits>
#include <utility>

namespace cpu_prefetch::calibration {

struct DiscoverySessionPlan final {
  std::uint64_t warmup_duration_ticks;
  std::uint64_t measurement_duration_ticks;
  std::uint64_t warmup_attempt_capacity;
  std::uint64_t measurement_attempt_capacity;
  std::uint64_t drain_duration_ticks;
  std::uint64_t drain_attempt_capacity;
  std::uint64_t barrier_poll_limit;
};

enum class DiscoverySessionStop : std::uint8_t {
  invalid_plan,
  preparation_failure,
  start_failure,
  worker_exception,
  thread_start_failure,
  warmup_failure,
  measurement_failure,
  drain_failure,
  trace_capacity,
  complete,
  observation_failure,
};

enum class DiscoveryPreparationStatus : std::uint8_t {
  not_started,
  ready,
  rejected,
  exception,
};

enum class DiscoverySessionPhase : std::uint8_t { warmup, measurement };

enum class DiscoveryObservationStatus : std::uint8_t {
  not_started,
  not_configured,
  accepted,
  rejected,
  exception,
};

struct DiscoveryPhaseObservations final {
  DiscoveryObservationStatus before{DiscoveryObservationStatus::not_started};
  DiscoveryObservationStatus during{DiscoveryObservationStatus::not_started};
  DiscoveryObservationStatus after{DiscoveryObservationStatus::not_started};
};

struct DiscoveryObservationWindow final {
  std::uint64_t origin_ticks;
  std::uint64_t duration_ticks;
};

// Legacy software-only sessions do not imply that platform monitoring passed.
// A qualified live action must supply its explicit, finite controller observer.
struct NoDiscoveryControllerObserver final {
  auto before_phase(DiscoverySessionPhase) const noexcept -> bool { return true; }
  auto during_phase(DiscoverySessionPhase, DiscoveryObservationWindow,
                    const std::atomic<std::uint32_t>&) const noexcept -> bool {
    return true;
  }
  auto after_phase(DiscoverySessionPhase) const noexcept -> bool { return true; }
};

struct DiscoverySessionResult final {
  DiscoverySessionStop stop{DiscoverySessionStop::invalid_plan};
  std::array<DiscoveryPreparationStatus, 2U> preparation{};
  std::array<bool, 2U> worker_exception{};
  std::array<bool, 2U> private_reset_verified{};
  std::array<DiscoveryWorkerResult, 2U> warmup{
      DiscoveryWorkerResult{DiscoveryWorkerStop::invalid_plan},
      DiscoveryWorkerResult{DiscoveryWorkerStop::invalid_plan}};
  std::array<DiscoveryWorkerResult, 2U> measurement{
      DiscoveryWorkerResult{DiscoveryWorkerStop::invalid_plan},
      DiscoveryWorkerResult{DiscoveryWorkerStop::invalid_plan}};
  DiscoveryDrainResult warmup_drain{DiscoveryDrainStop::invalid_plan};
  DiscoveryDrainResult measurement_drain{DiscoveryDrainStop::invalid_plan};
  std::array<std::optional<std::uint64_t>, 2U> origins{};
  std::array<std::optional<std::uint64_t>, 2U> observed_origins{};
  std::array<std::optional<timing::ClockReadStatus>, 2U> origin_status{};
  std::array<DiscoveryPhaseObservations, 2U> observations{};
  bool warmup_verified{false};
  bool measurement_verified{false};
};

// This coordinates already-frozen controls, not run admission. Backend owns
// prepared persistent storage, owner-thread binding/prefaulting, actual event
// validation/checksum actions, and private logical reset. Clock and Relax must
// support concurrent use. Capture callbacks must not allocate, block, or throw.
// Observer runs on the controller only: before release, during the fixed phase,
// and after both workers stop but before validation/drain/reset. Its own frozen
// schedule and retained page/status/timestamp scratch must be finite. The during
// hook receives the released origin/duration and a read-only completion mask;
// it must not access mutable worker observations. No observation grants admission.
template <typename Clock, typename Backend, typename Relax, typename Observer,
          typename Threads>
[[nodiscard]] auto run_discovery_session(DiscoverySessionPlan plan, Clock& clock,
                                         Backend& backend, Relax& relax,
                                         Observer& observer, Threads& threads)
    -> DiscoverySessionResult {
  static_assert(noexcept(clock.read()));
  static_assert(noexcept(relax.relax()));
  DiscoverySessionResult result;
  if (plan.warmup_duration_ticks == 0U || plan.measurement_duration_ticks == 0U ||
      plan.warmup_attempt_capacity == 0U || plan.measurement_attempt_capacity == 0U ||
      plan.drain_duration_ticks == 0U || plan.drain_attempt_capacity == 0U ||
      plan.barrier_poll_limit == 0U) {
    return result;
  }
  lifecycle::WorkerStartBarrier warmup_barrier;
  lifecycle::WorkerStartBarrier measurement_barrier;
  std::atomic<bool> fatal{false};
  std::atomic<bool> warmup_stop{false};
  std::atomic<bool> measurement_stop{false};
  std::atomic<std::uint32_t> warmup_finished{0U};
  std::atomic<std::uint32_t> measurement_finished{0U};
  std::atomic<bool> warmup_reset_ready{false};
  std::array<std::atomic<bool>, 2U> observations_finished{};
  std::array<std::atomic<bool>, 2U> observations_accepted{};
  const auto cancel = [&]() noexcept {
    fatal.store(true, std::memory_order_release);
    warmup_stop.store(true, std::memory_order_release);
    measurement_stop.store(true, std::memory_order_release);
    warmup_barrier.cancel();
    measurement_barrier.cancel();
  };
  const auto wait = [&](const auto& predicate) noexcept {
    for (std::uint64_t poll = 0U; poll < plan.barrier_poll_limit; ++poll) {
      if (fatal.load(std::memory_order_acquire)) {
        return false;
      }
      if (predicate()) {
        return true;
      }
      relax.relax();
    }
    cancel();
    return false;
  };
  const auto drain = [&](const auto& workers, bool warmup) {
    if (workers[0].advanced < workers[1].advanced) {
      return DiscoveryDrainResult{DiscoveryDrainStop::count_mismatch};
    }
    const auto origin = clock.read();
    if (origin.status != timing::ClockReadStatus::ok) {
      DiscoveryDrainResult failure{DiscoveryDrainStop::clock_failure};
      failure.failed_clock_status = origin.status;
      return failure;
    }
    const DiscoveryDrainWindow window{
        origin.sample.relative_picoseconds, plan.drain_duration_ticks,
        plan.drain_attempt_capacity, workers[0].advanced - workers[1].advanced,
        warmup && result.warmup_verified &&
            observations_accepted[0U].load(std::memory_order_acquire)};
    if constexpr (requires {
                    backend.drain_warmup(window);
                    backend.drain_measurement(window);
                  }) {
      return warmup ? backend.drain_warmup(window) : backend.drain_measurement(window);
    } else {
      static_assert(
          noexcept(backend.consume_warmup_drain(static_cast<const void*>(nullptr))));
      static_assert(noexcept(
          backend.consume_measurement_drain(static_cast<const void*>(nullptr))));
      auto consume = [&](const void* event) noexcept {
        return warmup ? backend.consume_warmup_drain(event)
                      : backend.consume_measurement_drain(event);
      };
      return drain_discovery_ring_quiescent(window, clock, backend.ring(), consume);
    }
  };
  auto worker = [&]<RingWorker Role>() noexcept {
    constexpr std::size_t index = Role == RingWorker::producer ? 0U : 1U;
    constexpr auto role = Role == RingWorker::producer
                              ? lifecycle::WorkerRole::producer
                              : lifecycle::WorkerRole::consumer;
    constexpr auto bit = std::uint32_t{1U} << index;
    try {
      const bool prepared = [&] {
        if (!threads.prepared(Role)) {
          return false;
        }
        if constexpr (Role == RingWorker::producer) {
          return backend.prepare_producer();
        } else {
          return backend.prepare_consumer();
        }
      }();
      result.preparation[index] = prepared ? DiscoveryPreparationStatus::ready
                                           : DiscoveryPreparationStatus::rejected;
      if (!prepared ||
          warmup_barrier.arrive(role) != lifecycle::StartBarrierStatus::ready ||
          warmup_barrier.worker_wait(plan.barrier_poll_limit, [&]() noexcept {
            relax.relax();
          }) != lifecycle::StartBarrierStatus::released) {
        cancel();
        return;
      }
      auto warmup_attempt = [&](std::uint64_t observed_tick) noexcept {
        if constexpr (Role == RingWorker::producer) {
          if constexpr (requires { backend.warmup_producer_attempt(observed_tick); }) {
            static_assert(noexcept(backend.warmup_producer_attempt(observed_tick)));
            return backend.warmup_producer_attempt(observed_tick);
          } else {
            static_assert(noexcept(backend.warmup_producer_attempt()));
            return backend.warmup_producer_attempt();
          }
        } else {
          static_assert(noexcept(backend.warmup_consumer_attempt()));
          return backend.warmup_consumer_attempt();
        }
      };
      result.warmup[index] = capture_discovery_worker(
          {Role, warmup_barrier.measurement_origin(), plan.warmup_duration_ticks,
           plan.warmup_attempt_capacity},
          clock, warmup_attempt, warmup_stop);
      warmup_finished.fetch_or(bit, std::memory_order_acq_rel);
      if constexpr (Role == RingWorker::consumer) {
        if (!wait([&]() noexcept {
              return warmup_finished.load(std::memory_order_acquire) == 3U &&
                     observations_finished[0U].load(std::memory_order_acquire);
            })) {
          return;
        }
        result.warmup_verified =
            result.warmup[0].stop == DiscoveryWorkerStop::fixed_deadline &&
            result.warmup[1].stop == DiscoveryWorkerStop::fixed_deadline &&
            backend.validate_warmup(std::as_const(result.warmup));
        result.warmup_drain = drain(result.warmup, true);
        if (!result.warmup_verified ||
            !observations_accepted[0U].load(std::memory_order_acquire) ||
            result.warmup_drain.stop != DiscoveryDrainStop::complete ||
            !result.warmup_drain.reset_verified) {
          cancel();
          return;
        }
        result.private_reset_verified[index] = backend.reset_consumer();
        if (!result.private_reset_verified[index]) {
          cancel();
          return;
        }
        warmup_reset_ready.store(true, std::memory_order_release);
      } else {
        if (!wait([&]() noexcept {
              return warmup_reset_ready.load(std::memory_order_acquire);
            })) {
          cancel();
          return;
        }
        result.private_reset_verified[index] = backend.reset_producer();
        if (!result.private_reset_verified[index]) {
          cancel();
          return;
        }
      }
      if (measurement_barrier.arrive(role) != lifecycle::StartBarrierStatus::ready ||
          measurement_barrier.worker_wait(plan.barrier_poll_limit, [&]() noexcept {
            relax.relax();
          }) != lifecycle::StartBarrierStatus::released) {
        cancel();
        return;
      }
      auto measurement_attempt = [&](std::uint64_t observed_tick) noexcept {
        if constexpr (Role == RingWorker::producer) {
          if constexpr (requires {
                          backend.measurement_producer_attempt(observed_tick);
                        }) {
            static_assert(
                noexcept(backend.measurement_producer_attempt(observed_tick)));
            return backend.measurement_producer_attempt(observed_tick);
          } else {
            static_assert(noexcept(backend.measurement_producer_attempt()));
            return backend.measurement_producer_attempt();
          }
        } else {
          static_assert(noexcept(backend.measurement_consumer_attempt()));
          return backend.measurement_consumer_attempt();
        }
      };
      result.measurement[index] = capture_discovery_worker(
          {Role, measurement_barrier.measurement_origin(),
           plan.measurement_duration_ticks, plan.measurement_attempt_capacity},
          clock, measurement_attempt, measurement_stop);
      measurement_finished.fetch_or(bit, std::memory_order_acq_rel);
      if constexpr (Role == RingWorker::consumer) {
        if (!wait([&]() noexcept {
              return measurement_finished.load(std::memory_order_acquire) == 3U &&
                     observations_finished[1U].load(std::memory_order_acquire);
            })) {
          return;
        }
        result.measurement_verified =
            backend.validate_measurement(std::as_const(result.measurement));
        result.measurement_drain = drain(result.measurement, false);
      }
    } catch (...) {
      if (result.preparation[index] == DiscoveryPreparationStatus::not_started) {
        result.preparation[index] = DiscoveryPreparationStatus::exception;
      }
      result.worker_exception[index] = true;
      cancel();
    }
  };
  const auto join = [&] { threads.join(); };
  try {
    const auto producer_entry = +[](void* context) noexcept {
      static_cast<decltype(worker)*>(context)
          ->template operator()<RingWorker::producer>();
    };
    const auto consumer_entry = +[](void* context) noexcept {
      static_cast<decltype(worker)*>(context)
          ->template operator()<RingWorker::consumer>();
    };
    if (!threads.start(RingWorker::producer, producer_entry, &worker) ||
        !threads.start(RingWorker::consumer, consumer_entry, &worker)) {
      cancel();
      join();
      result.stop = DiscoverySessionStop::thread_start_failure;
      return result;
    }
  } catch (...) {
    cancel();
    join();
    result.stop = DiscoverySessionStop::thread_start_failure;
    return result;
  }
  const auto observe = [&](auto&& callback) noexcept {
    if constexpr (std::is_same_v<Observer, NoDiscoveryControllerObserver>) {
      return DiscoveryObservationStatus::not_configured;
    } else {
      try {
        return callback() ? DiscoveryObservationStatus::accepted
                          : DiscoveryObservationStatus::rejected;
      } catch (...) {
        return DiscoveryObservationStatus::exception;
      }
    }
  };
  const auto accepted = [](DiscoveryObservationStatus status) noexcept {
    return status == DiscoveryObservationStatus::accepted ||
           status == DiscoveryObservationStatus::not_configured;
  };
  const auto release = [&](auto& barrier, DiscoverySessionPhase phase,
                           std::uint64_t duration) {
    const auto phase_index = static_cast<std::size_t>(phase);
    if (barrier.controller_wait(plan.barrier_poll_limit, [&]() noexcept {
          relax.relax();
        }) != lifecycle::StartBarrierStatus::ready) {
      cancel();
      return false;
    }
    auto& before = result.observations[phase_index].before;
    before = observe([&] { return observer.before_phase(phase); });
    if (!accepted(before)) {
      cancel();
      return false;
    }
    const auto origin = clock.read();
    result.origin_status[phase_index] = origin.status;
    if (origin.status == timing::ClockReadStatus::ok) {
      result.observed_origins[phase_index] = origin.sample.relative_picoseconds;
    }
    if (origin.status != timing::ClockReadStatus::ok ||
        origin.sample.relative_picoseconds >
            std::numeric_limits<std::uint64_t>::max() - duration) {
      cancel();
      return false;
    }
    if (barrier.release_with_measurement_origin(origin.sample.relative_picoseconds) !=
        lifecycle::StartBarrierStatus::released) {
      cancel();
      return false;
    }
    result.origins[phase_index] = origin.sample.relative_picoseconds;
    return true;
  };
  const auto monitor = [&](DiscoverySessionPhase phase, std::uint64_t duration,
                           const auto& finished, auto& phase_stop) {
    const auto index = static_cast<std::size_t>(phase);
    auto& observed = result.observations[index];
    if (!result.origins[index].has_value()) {
      return false;
    }
    const auto origin = *result.origins[index];
    observed.during = observe([&] {
      return observer.during_phase(
          phase,
          DiscoveryObservationWindow{.origin_ticks = origin,
                                     .duration_ticks = duration},
          finished);
    });
    if (!accepted(observed.during)) {
      // Stop capture, not the consumer's bounded drain. Full cancellation here
      // would lose real pending events and skip the final sequence audit.
      phase_stop.store(true, std::memory_order_release);
    }
    if (!wait([&]() noexcept {
          return finished.load(std::memory_order_acquire) == 3U;
        })) {
      return false;
    }
    observed.after = observe([&] { return observer.after_phase(phase); });
    const bool passed = accepted(observed.during) && accepted(observed.after);
    observations_accepted[index].store(passed, std::memory_order_release);
    observations_finished[index].store(true, std::memory_order_release);
    return passed;
  };
  const bool started =
      release(warmup_barrier, DiscoverySessionPhase::warmup,
              plan.warmup_duration_ticks) &&
      monitor(DiscoverySessionPhase::warmup, plan.warmup_duration_ticks,
              warmup_finished, warmup_stop) &&
      release(measurement_barrier, DiscoverySessionPhase::measurement,
              plan.measurement_duration_ticks) &&
      monitor(DiscoverySessionPhase::measurement, plan.measurement_duration_ticks,
              measurement_finished, measurement_stop);
  join();
  bool observation_failed = false;
  for (const auto& phase : result.observations) {
    for (const auto status : {phase.before, phase.during, phase.after}) {
      observation_failed = observation_failed ||
                           status == DiscoveryObservationStatus::rejected ||
                           status == DiscoveryObservationStatus::exception;
    }
  }
  result.stop = DiscoverySessionStop::measurement_failure;
  if (result.preparation[0] != DiscoveryPreparationStatus::ready ||
      result.preparation[1] != DiscoveryPreparationStatus::ready) {
    result.stop = DiscoverySessionStop::preparation_failure;
  } else if (result.worker_exception[0] || result.worker_exception[1]) {
    result.stop = DiscoverySessionStop::worker_exception;
  } else if (observation_failed) {
    result.stop = DiscoverySessionStop::observation_failure;
  } else if (!result.warmup_verified || !result.warmup_drain.reset_verified ||
             !result.private_reset_verified[0] || !result.private_reset_verified[1]) {
    result.stop = result.origins[0] ? DiscoverySessionStop::warmup_failure
                                    : DiscoverySessionStop::start_failure;
  } else if (!started) {
    result.stop = DiscoverySessionStop::start_failure;
  } else if (result.measurement_verified) {
    if (result.measurement_drain.stop != DiscoveryDrainStop::complete) {
      result.stop = DiscoverySessionStop::drain_failure;
    } else if (result.measurement[0].stop == DiscoveryWorkerStop::fixed_deadline &&
               result.measurement[1].stop == DiscoveryWorkerStop::fixed_deadline) {
      result.stop = DiscoverySessionStop::complete;
    } else if ((result.measurement[0].stop == DiscoveryWorkerStop::trace_capacity &&
                (result.measurement[1].stop == DiscoveryWorkerStop::peer_stopped ||
                 result.measurement[1].stop == DiscoveryWorkerStop::trace_capacity ||
                 result.measurement[1].stop == DiscoveryWorkerStop::fixed_deadline)) ||
               (result.measurement[1].stop == DiscoveryWorkerStop::trace_capacity &&
                (result.measurement[0].stop == DiscoveryWorkerStop::peer_stopped ||
                 result.measurement[0].stop == DiscoveryWorkerStop::trace_capacity ||
                 result.measurement[0].stop == DiscoveryWorkerStop::fixed_deadline))) {
      result.stop = DiscoverySessionStop::trace_capacity;
    }
  }
  return result;
}

template <typename Clock, typename Backend, typename Relax, typename Observer>
[[nodiscard]] auto run_discovery_session(DiscoverySessionPlan plan, Clock& clock,
                                         Backend& backend, Relax& relax,
                                         Observer& observer) -> DiscoverySessionResult {
  StandardDiscoveryThreads threads;
  return run_discovery_session(plan, clock, backend, relax, observer, threads);
}

template <typename Clock, typename Backend, typename Relax>
[[nodiscard]] auto run_discovery_session(DiscoverySessionPlan plan, Clock& clock,
                                         Backend& backend, Relax& relax)
    -> DiscoverySessionResult {
  NoDiscoveryControllerObserver observer;
  return run_discovery_session(plan, clock, backend, relax, observer);
}

} // namespace cpu_prefetch::calibration

#endif
