#ifndef CPU_PREFETCH_CALIBRATION_SERVICE_SESSION_HPP
#define CPU_PREFETCH_CALIBRATION_SERVICE_SESSION_HPP

#include "cpu_prefetch/calibration/discovery_thread_launcher.hpp"
#include "cpu_prefetch/lifecycle/executor.hpp"
#include "cpu_prefetch/timing/clock.hpp"

#include <array>
#include <atomic>
#include <cstdint>
#include <optional>
#include <utility>

namespace cpu_prefetch::calibration {

enum class ServicePhase : std::uint8_t { warmup, measurement };
struct ServicePhasePlan final {
  std::uint64_t duration_ticks;
  std::uint64_t producer_attempt_limit;
  std::uint64_t consumer_poll_limit;
  std::uint64_t drain_duration_ticks;
};
struct ServiceSessionPlan final {
  std::array<ServicePhasePlan, 2U> phases;
  std::uint64_t barrier_poll_limit;
};
struct ServiceWindow final {
  std::uint64_t origin_ticks;
  std::uint64_t duration_ticks;
  std::uint64_t producer_deadline_ticks;
  std::uint64_t drain_deadline_ticks;
};
[[nodiscard]] auto valid_service_plan(const ServiceSessionPlan& plan) noexcept -> bool;
[[nodiscard]] auto service_window(std::uint64_t origin, ServicePhasePlan plan) noexcept
    -> std::optional<ServiceWindow>;

enum class ServiceSessionStop : std::uint8_t {
  not_started,
  complete,
  invalid_plan,
  storage_already_used,
  preparation_failure,
  thread_start_failure,
  barrier_failure,
  clock_failure,
  deadline_overflow,
  producer_failure,
  consumer_failure,
  attempt_limit,
  poll_limit,
  drain_timeout,
  validation_failure,
  reset_failure,
  observation_failure,
  exception,
};
struct ServiceProducerResult final {
  std::optional<timing::ClockReadStatus> last_clock_status;
  std::optional<std::uint64_t> last_observed_tick;
  std::uint64_t attempted{0U};
  std::uint64_t accepted{0U};
  std::uint64_t full{0U};
  bool deadline_reached{false};
  bool arrivals_finished_published{false};
};
struct ServiceConsumerResult final {
  std::optional<timing::ClockReadStatus> last_clock_status;
  std::optional<std::uint64_t> last_observed_tick;
  // Total through drain, NEVER an interval-throughput numerator.
  std::uint64_t consumed{0U};
  std::uint64_t polls{0U};
  std::uint64_t empty{0U};
  bool drained{false};
};
struct ServicePhaseResult final {
  std::optional<timing::ClockReadStatus> origin_status;
  std::optional<std::uint64_t> observed_origin;
  std::optional<timing::ClockSample> origin_sample;
  std::optional<timing::ClockReadResult> drain_checkpoint;
  std::optional<ServiceWindow> window;
  ServiceProducerResult producer;
  ServiceConsumerResult consumer;
  bool released{false};
  bool before_observed{false};
  bool during_observed{false};
  bool after_observed{false};
  bool validated{false};
};
struct ServiceSessionResult final {
  ServiceSessionStop stop{ServiceSessionStop::not_started};
  std::optional<timing::ClockOrigin> clock_origin;
  std::array<bool, 2U> prepared{};
  std::array<bool, 2U> private_reset{};
  bool queue_reset{false};
  std::array<ServicePhaseResult, 2U> phases;
};

// Caller owns all storage and its placement. Two existing dedicated-line
// termination controls must outlive the session. This object allocates nothing;
// construction of those controls is cold and is not placement qualification.
// Inspect results only after run returns. Never reuse/reset this storage.
struct ServiceTerminationControls final {
  lifecycle::TerminationControl& warmup;
  lifecycle::TerminationControl& measurement;
};

class ServiceSessionStorage final {
public:
  explicit ServiceSessionStorage(ServiceTerminationControls controls) noexcept
      : arrivals{&controls.warmup, &controls.measurement} {}
  [[nodiscard]] auto claim() noexcept -> bool {
    return !claimed_.exchange(true, std::memory_order_acq_rel);
  }
  std::array<lifecycle::TerminationControl*, 2U> arrivals;
  std::array<lifecycle::WorkerStartBarrier, 2U> barriers;
  std::array<std::atomic<std::uint32_t>, 2U> finished{};
  std::array<std::atomic<bool>, 2U> proceed{};
  std::atomic<ServiceSessionStop> failure{ServiceSessionStop::not_started};
  ServiceSessionResult result;

private:
  std::atomic<bool> claimed_{false};
};

// Backend::phase(ServicePhase) returns the preconstructed capture backend:
// try_producer_attempt(ProducerAttempt), try_consumer_poll(ordinal), both noexcept.
// These retain the actual package's observations/checksum action. Selection is
// outside the hot loop; no virtual dispatch or package selection is added here.
// Backend::validate_quiescent(phase, result) and reset_quiescent() run on the
// controller only with BOTH workers parked. Reset must preserve storage/order.
// Preparation prepares each owner once and resets owner-private logical state
// on that SAME worker (prepare_producer/consumer, reset_producer/consumer).
// Clock::read(), origin() and Relax::relax() are noexcept. Clock reads are
// concurrently usable. Both phase backends MUST use this SAME clock instance
// and its unchanged origin: retained ticks are relative picoseconds.
// Observer before_phase/after_phase run with parked workers. during_phase gets
// the window and an acquire-readable finished mask; it must be finite and must
// not read mutable worker reports. Its failures cancel; it grants no validity.
// Threads uses the existing start(RingWorker, WorkerEntry, void*)/prepared/join
// seam. Successful starts MUST be joinable; join must reap before returning.
// Every callback must obey its allocation/I/O/placement contract. This core
// supplies no admission, empirical limits, interval numerator or endpoint rule.
template <typename Clock, typename Backend, typename Preparation, typename Relax,
          typename Observer, typename Threads>
[[nodiscard]] auto run_service_session(const ServiceSessionPlan& plan, Clock& clock,
                                       Backend& backend, Preparation& preparation,
                                       Relax& relax, Observer& observer,
                                       Threads& threads, ServiceSessionStorage& storage)
    -> ServiceSessionResult {
  static_assert(noexcept(clock.read()));
  static_assert(noexcept(clock.origin()));
  static_assert(noexcept(relax.relax()));
  static_assert(std::atomic<ServiceSessionStop>::is_always_lock_free);
  static_assert(std::atomic<bool>::is_always_lock_free);
  static_assert(std::atomic<std::uint32_t>::is_always_lock_free);
  if (!storage.claim()) {
    ServiceSessionResult rejected;
    rejected.stop = ServiceSessionStop::storage_already_used;
    return rejected;
  }
  auto& result = storage.result;
  if (!valid_service_plan(plan) || storage.arrivals[0U] == nullptr ||
      storage.arrivals[1U] == nullptr || storage.arrivals[0U] == storage.arrivals[1U]) {
    result.stop = ServiceSessionStop::invalid_plan;
    return result;
  }
  result.clock_origin = clock.origin();
  for (auto* control : storage.arrivals) {
    if (!control->reset_quiescent(true)) {
      result.stop = ServiceSessionStop::preparation_failure;
      return result;
    }
  }
  const auto failed = [&]() noexcept {
    return storage.failure.load(std::memory_order_acquire) !=
           ServiceSessionStop::not_started;
  };
  const auto fail = [&](ServiceSessionStop reason) noexcept {
    auto expected = ServiceSessionStop::not_started;
    static_cast<void>(storage.failure.compare_exchange_strong(
        expected, reason, std::memory_order_acq_rel));
    for (auto& barrier : storage.barriers) {
      barrier.cancel();
    }
  };
  const auto wait = [&](const auto& predicate) noexcept {
    for (std::uint64_t poll = 0U; poll < plan.barrier_poll_limit; ++poll) {
      if (failed()) {
        return false;
      }
      if (predicate()) {
        return true;
      }
      relax.relax();
    }
    fail(ServiceSessionStop::barrier_failure);
    return false;
  };
  auto worker = [&]<RingWorker Role>() noexcept {
    constexpr auto index = Role == RingWorker::producer ? 0U : 1U;
    constexpr auto role = Role == RingWorker::producer
                              ? lifecycle::WorkerRole::producer
                              : lifecycle::WorkerRole::consumer;
    try {
      const bool prepared = [&] {
        if constexpr (Role == RingWorker::producer) {
          return preparation.prepare_producer();
        } else {
          return preparation.prepare_consumer();
        }
      }();
      result.prepared[index] = prepared && threads.prepared(Role);
      if (!result.prepared[index]) {
        fail(ServiceSessionStop::preparation_failure);
        return;
      }
      for (std::size_t phase_index = 0U; phase_index < 2U; ++phase_index) {
        const auto phase =
            phase_index == 0U ? ServicePhase::warmup : ServicePhase::measurement;
        auto& capture = backend.phase(phase);
        auto& barrier = storage.barriers[phase_index];
        if (barrier.arrive(role) != lifecycle::StartBarrierStatus::ready ||
            barrier.worker_wait(plan.barrier_poll_limit, [&]() noexcept {
              relax.relax();
            }) != lifecycle::StartBarrierStatus::released) {
          fail(ServiceSessionStop::barrier_failure);
          return;
        }
        const auto window =
            service_window(barrier.measurement_origin(), plan.phases[phase_index]);
        if (!window) {
          fail(ServiceSessionStop::deadline_overflow);
          return;
        }
        auto& arrivals = *storage.arrivals[phase_index];
        auto previous = window->origin_ticks;
        const auto read = [&]() noexcept -> std::optional<std::uint64_t> {
          const auto observed = clock.read();
          const auto record = [&](auto& report) noexcept {
            report.last_clock_status = observed.status;
            if (observed.status == timing::ClockReadStatus::ok) {
              report.last_observed_tick = observed.sample.relative_picoseconds;
            }
          };
          if constexpr (Role == RingWorker::producer) {
            record(result.phases[phase_index].producer);
          } else {
            record(result.phases[phase_index].consumer);
          }
          if (observed.status != timing::ClockReadStatus::ok ||
              observed.sample.relative_picoseconds < previous) {
            fail(ServiceSessionStop::clock_failure);
            return std::nullopt;
          }
          previous = observed.sample.relative_picoseconds;
          return previous;
        };
        if constexpr (Role == RingWorker::producer) {
          static_assert(
              noexcept(capture.try_producer_attempt(lifecycle::ProducerAttempt{})));
          auto& report = result.phases[phase_index].producer;
          while (!failed()) {
            const auto now = read();
            if (!now) {
              break;
            }
            if (*now >= window->producer_deadline_ticks) {
              report.deadline_reached = true;
              break;
            }
            if (report.attempted == plan.phases[phase_index].producer_attempt_limit) {
              fail(ServiceSessionStop::attempt_limit);
              break;
            }
            const auto attempt =
                capture.try_producer_attempt({report.attempted, *now, report.accepted});
            ++report.attempted;
            if (attempt.status != lifecycle::AttemptStatus::complete) {
              fail(ServiceSessionStop::producer_failure);
              break;
            }
            if (attempt.outcome == queue::EnqueueResult::accepted) {
              ++report.accepted;
            } else {
              ++report.full;
            }
          }
          arrivals.publish_arrivals_finished();
          report.arrivals_finished_published = true;
        } else {
          static_assert(noexcept(capture.try_consumer_poll(std::uint64_t{})));
          auto& report = result.phases[phase_index].consumer;
          // Acquire BEFORE the poll. An empty result is terminal only when its
          // poll follows that acquire, covering a final enqueue racing an earlier
          // empty poll. Consumption continues through the producer deadline.
          while (!failed()) {
            const auto now = read();
            if (!now) {
              break;
            }
            if (*now >= window->drain_deadline_ticks) {
              fail(ServiceSessionStop::drain_timeout);
              break;
            }
            if (report.polls == plan.phases[phase_index].consumer_poll_limit) {
              fail(ServiceSessionStop::poll_limit);
              break;
            }
            const bool finished = arrivals.arrivals_finished();
            const auto polled = capture.try_consumer_poll(report.consumed);
            ++report.polls;
            if (polled.status == lifecycle::ConsumerPollStatus::item) {
              ++report.consumed;
            } else if (polled.status == lifecycle::ConsumerPollStatus::failure) {
              fail(ServiceSessionStop::consumer_failure);
              break;
            } else {
              ++report.empty;
              if (finished) {
                // The terminal poll itself can cross the deadline or observe a
                // clock fault. This read is outside the backend's brackets.
                const auto completed = read();
                if (!completed) {
                  break;
                }
                if (*completed >= window->drain_deadline_ticks) {
                  fail(ServiceSessionStop::drain_timeout);
                  break;
                }
                report.drained = true;
                break;
              }
              relax.relax();
            }
          }
        }
        storage.finished[phase_index].fetch_or(1U << index, std::memory_order_acq_rel);
        if (!wait([&]() noexcept {
              return storage.proceed[phase_index].load(std::memory_order_acquire);
            })) {
          return;
        }
        if (phase_index == 0U) {
          const bool reset = [&] {
            if constexpr (Role == RingWorker::producer) {
              return preparation.reset_producer();
            } else {
              return preparation.reset_consumer();
            }
          }();
          result.private_reset[index] = reset;
          if (!reset) {
            fail(ServiceSessionStop::reset_failure);
            return;
          }
        }
      }
    } catch (...) {
      fail(ServiceSessionStop::exception);
    }
  };
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
      fail(ServiceSessionStop::thread_start_failure);
    } else {
      std::optional<std::uint64_t> previous_checkpoint;
      for (std::size_t index = 0U; index < 2U && !failed(); ++index) {
        const auto phase =
            index == 0U ? ServicePhase::warmup : ServicePhase::measurement;
        auto& phase_result = result.phases[index];
        auto& barrier = storage.barriers[index];
        if (barrier.controller_wait(plan.barrier_poll_limit, [&]() noexcept {
              relax.relax();
            }) != lifecycle::StartBarrierStatus::ready) {
          fail(ServiceSessionStop::barrier_failure);
          break;
        }
        if (!observer.before_phase(phase)) {
          fail(ServiceSessionStop::observation_failure);
          break;
        }
        phase_result.before_observed = true;
        if (clock.origin().absolute_nanoseconds !=
            result.clock_origin->absolute_nanoseconds) {
          fail(ServiceSessionStop::clock_failure);
          break;
        }
        const auto origin = clock.read();
        phase_result.origin_status = origin.status;
        if (origin.status == timing::ClockReadStatus::ok) {
          phase_result.observed_origin = origin.sample.relative_picoseconds;
          phase_result.origin_sample = origin.sample;
        }
        if (origin.status != timing::ClockReadStatus::ok ||
            (previous_checkpoint &&
             origin.sample.relative_picoseconds < *previous_checkpoint)) {
          fail(ServiceSessionStop::clock_failure);
          break;
        }
        phase_result.window =
            service_window(origin.sample.relative_picoseconds, plan.phases[index]);
        if (!phase_result.window) {
          fail(ServiceSessionStop::deadline_overflow);
          break;
        }
        if (barrier.release_with_measurement_origin(
                phase_result.window->origin_ticks) !=
            lifecycle::StartBarrierStatus::released) {
          fail(ServiceSessionStop::barrier_failure);
          break;
        }
        phase_result.released = true;
        if (!observer.during_phase(phase, *phase_result.window,
                                   std::as_const(storage.finished[index]))) {
          fail(ServiceSessionStop::observation_failure);
          break;
        }
        phase_result.during_observed = true;
        if (!wait([&]() noexcept {
              return storage.finished[index].load(std::memory_order_acquire) == 3U;
            })) {
          break;
        }
        if (!observer.after_phase(phase)) {
          fail(ServiceSessionStop::observation_failure);
          break;
        }
        phase_result.after_observed = true;
        const auto checkpoint = clock.read();
        phase_result.drain_checkpoint = checkpoint;
        const auto producer_tick = phase_result.producer.last_observed_tick;
        const auto consumer_tick = phase_result.consumer.last_observed_tick;
        if (clock.origin().absolute_nanoseconds !=
                result.clock_origin->absolute_nanoseconds ||
            checkpoint.status != timing::ClockReadStatus::ok || !producer_tick ||
            !consumer_tick || checkpoint.sample.relative_picoseconds < *producer_tick ||
            checkpoint.sample.relative_picoseconds < *consumer_tick) {
          fail(ServiceSessionStop::clock_failure);
          break;
        }
        // Cold monitoring may finish after the drain deadline; that deadline
        // applies to consumer completion, verified by its terminal postpoll read.
        previous_checkpoint = checkpoint.sample.relative_picoseconds;
        if (!phase_result.producer.deadline_reached || !phase_result.consumer.drained ||
            phase_result.producer.accepted != phase_result.consumer.consumed ||
            !backend.validate_quiescent(phase, std::as_const(phase_result))) {
          fail(ServiceSessionStop::validation_failure);
          break;
        }
        phase_result.validated = true;
        if (index == 0U) {
          result.queue_reset = backend.reset_quiescent();
          if (!result.queue_reset) {
            fail(ServiceSessionStop::reset_failure);
            break;
          }
        }
        storage.proceed[index].store(true, std::memory_order_release);
      }
    }
  } catch (...) {
    fail(ServiceSessionStop::exception);
  }
  // No object captured by a worker is destroyed before all started workers join.
  threads.join();
  result.stop = storage.failure.load(std::memory_order_acquire);
  if (result.stop == ServiceSessionStop::not_started) {
    result.stop = ServiceSessionStop::complete;
  }
  return result;
}

} // namespace cpu_prefetch::calibration
#endif
