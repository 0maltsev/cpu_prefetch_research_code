#ifndef CPU_PREFETCH_LIFECYCLE_EXECUTOR_HPP
#define CPU_PREFETCH_LIFECYCLE_EXECUTOR_HPP

#include <atomic>
#include <cstdint>
#include <limits>
#include <thread>

#include "cpu_prefetch/lifecycle/runtime.hpp"
#include "cpu_prefetch/queue/common.hpp"

namespace cpu_prefetch::lifecycle {

// These small result types are the Stage 10 seam between the controller and
// the Stage 8 capture path. A production backend must capture and retain the
// full producer/consumer observations before returning complete.
struct TickRead final {
  bool ok;
  std::uint64_t ticks;
};

enum class AttemptStatus : std::uint8_t { complete, failure };

struct ProducerAttemptResult final {
  AttemptStatus status;
  queue::EnqueueResult outcome;
};

struct ProducerAttempt final {
  std::uint64_t logical_sequence;
  std::uint64_t scheduled_deadline;
  std::uint64_t candidate_accepted_ordinal;
};

enum class ConsumerPollStatus : std::uint8_t { item, empty, failure };

struct ConsumerPollResult final {
  ConsumerPollStatus status;
};

struct ExecutionLimits final {
  std::uint64_t controller_start_poll_limit;
  std::uint64_t worker_start_poll_limit;
  std::uint64_t producer_due_poll_limit_per_arrival;
  std::uint64_t consumer_empty_poll_limit_before_finish;
  std::uint64_t drain_poll_limit;
};

enum class ExecutionFailurePhase : std::uint8_t {
  none,
  pre_run,
  start_barrier,
  measurement,
  drain,
};

enum class ExecutionFailureReason : std::uint8_t {
  none,
  invalid_schedule,
  invalid_limits,
  worker_preparation,
  termination_reset,
  start_watchdog,
  clock_read,
  deadline_overflow,
  producer_wait_watchdog,
  producer_attempt,
  consumer_poll,
  consumer_wait_watchdog,
  drain_watchdog,
  cancelled,
};

struct MeasurementExecutionReport final {
  ExecutionFailurePhase failure_phase;
  ExecutionFailureReason failure_reason;
  std::uint64_t measurement_origin_ticks;
  std::uint64_t offered;
  std::uint64_t attempted;
  std::uint64_t accepted;
  std::uint64_t full;
  std::uint64_t consumed;
  std::uint64_t producer_wait_polls;
  std::uint64_t consumer_empty_polls;
  std::uint64_t drain_polls;
  bool producer_completed;
  bool consumer_drained;
  bool arrivals_finished_published;
  bool cancellation_requested;
};

namespace detail {

struct DeadlineMapping final {
  std::uint64_t measurement_origin;
  std::uint64_t schedule_origin;
  std::uint64_t schedule_deadline;
};

struct ProducerWorkerState final {
  ExecutionFailureReason failure{ExecutionFailureReason::none};
  std::uint64_t attempted{0U};
  std::uint64_t accepted{0U};
  std::uint64_t full{0U};
  std::uint64_t wait_polls{0U};
  bool completed{false};
  bool arrivals_finished_published{false};
};

struct ConsumerWorkerState final {
  ExecutionFailureReason failure{ExecutionFailureReason::none};
  ExecutionFailurePhase failure_phase{ExecutionFailurePhase::none};
  std::uint64_t consumed{0U};
  std::uint64_t empty_polls{0U};
  std::uint64_t drain_polls{0U};
  bool drained{false};
};

[[nodiscard]] inline auto failure_report(ExecutionFailurePhase phase,
                                         ExecutionFailureReason reason,
                                         std::uint64_t offered) noexcept
    -> MeasurementExecutionReport {
  return {phase, reason, 0U, offered, 0U,    0U,    0U,   0U,
          0U,    0U,     0U, false,   false, false, false};
}

[[nodiscard]] inline auto checked_measurement_deadline(DeadlineMapping mapping,
                                                       std::uint64_t& target) noexcept
    -> bool {
  const auto offset = mapping.schedule_deadline - mapping.schedule_origin;
  if (offset > std::numeric_limits<std::uint64_t>::max() - mapping.measurement_origin) {
    return false;
  }
  target = mapping.measurement_origin + offset;
  return true;
}

} // namespace detail

// Contract for Backend:
//   try_producer_attempt(ProducerAttempt) -> ProducerAttemptResult
//   try_consumer_poll(candidate_consumed_ordinal) -> ConsumerPollResult
// Each call performs and retains one complete Stage 8 observation. Backend
// storage must be fully prepared before this function is called.
//
// Contract for Clock: read_ticks() -> TickRead. Contract for Relax: relax().
// Backend and Relax are concurrently used by one producer and one consumer;
// their implementations must preserve that SPSC/thread-safe contract.
// The production Relax mapping remains a platform-qualified input; this
// generic controller never chooses an instruction or scheduler operation.
// Contract for Preparation:
//   prepare_producer() noexcept -> bool
//   prepare_consumer() noexcept -> bool
// Both calls execute in their owner worker before that worker arrives at the
// start barrier. They may bind/read back affinity and first-touch private
// storage, but they cannot begin measurement or fabricate qualification.
template <typename Clock, typename Backend, typename Relax, typename Preparation>
[[nodiscard]] auto
execute_measurement_with_preparation(PreparedScheduleView schedule, Clock& clock,
                                     Backend& backend, TerminationControl& termination,
                                     const ExecutionLimits& limits, Relax& relax,
                                     Preparation& preparation)
    -> MeasurementExecutionReport {
  const auto schedule_errors = validate_prepared_schedule(schedule);
  if (!schedule_errors.empty()) {
    return detail::failure_report(ExecutionFailurePhase::pre_run,
                                  ExecutionFailureReason::invalid_schedule,
                                  schedule.deadline_ticks.size());
  }
  if (limits.controller_start_poll_limit == 0U ||
      limits.worker_start_poll_limit == 0U ||
      limits.producer_due_poll_limit_per_arrival == 0U ||
      limits.consumer_empty_poll_limit_before_finish == 0U ||
      limits.drain_poll_limit == 0U) {
    return detail::failure_report(ExecutionFailurePhase::pre_run,
                                  ExecutionFailureReason::invalid_limits,
                                  schedule.deadline_ticks.size());
  }
  if (!termination.reset_quiescent(true)) {
    return detail::failure_report(ExecutionFailurePhase::start_barrier,
                                  ExecutionFailureReason::termination_reset,
                                  schedule.deadline_ticks.size());
  }

  WorkerStartBarrier barrier;
  std::atomic<bool> cancellation{false};
  std::atomic<bool> producer_failed{false};
  std::atomic<bool> preparation_failed{false};

  MeasurementExecutionReport report{
      ExecutionFailurePhase::none,
      ExecutionFailureReason::none,
      0U,
      schedule.deadline_ticks.size(),
      0U,
      0U,
      0U,
      0U,
      0U,
      0U,
      0U,
      false,
      false,
      false,
      false,
  };

  // Each worker updates only a stack-local state while measurement is active.
  // It publishes one complete state to its controller-owned slot when exiting;
  // the controller reads those slots only after join. This avoids a shared
  // writable report cache line in the producer/consumer loops.
  detail::ProducerWorkerState producer_state;
  detail::ConsumerWorkerState consumer_state;

  std::thread producer([&] {
    producer_state = [&]() noexcept {
      detail::ProducerWorkerState local;
      if (!preparation.prepare_producer()) {
        local.failure = ExecutionFailureReason::worker_preparation;
        producer_failed.store(true, std::memory_order_release);
        preparation_failed.store(true, std::memory_order_release);
        cancellation.store(true, std::memory_order_release);
        barrier.cancel();
        termination.publish_arrivals_finished();
        local.arrivals_finished_published = true;
        return local;
      }
      if (barrier.arrive(WorkerRole::producer) != StartBarrierStatus::ready) {
        local.failure = ExecutionFailureReason::cancelled;
        producer_failed.store(true, std::memory_order_release);
        return local;
      }
      if (barrier.worker_wait(limits.worker_start_poll_limit, [&] { relax.relax(); }) !=
          StartBarrierStatus::released) {
        local.failure = ExecutionFailureReason::start_watchdog;
        producer_failed.store(true, std::memory_order_release);
        return local;
      }

      const auto measurement_origin = barrier.measurement_origin();
      std::uint64_t accepted_ordinal = 0U;
      std::uint64_t logical_sequence = 0U;
      for (const auto schedule_deadline : schedule.deadline_ticks) {
        if (cancellation.load(std::memory_order_acquire)) {
          local.failure = ExecutionFailureReason::cancelled;
          break;
        }
        std::uint64_t target = 0U;
        if (!detail::checked_measurement_deadline(
                {measurement_origin, schedule.origin_ticks, schedule_deadline},
                target)) {
          local.failure = ExecutionFailureReason::deadline_overflow;
          break;
        }

        bool due = false;
        for (std::uint64_t poll = 0U; poll < limits.producer_due_poll_limit_per_arrival;
             ++poll) {
          if (cancellation.load(std::memory_order_acquire)) {
            local.failure = ExecutionFailureReason::cancelled;
            break;
          }
          const auto reading = clock.read_ticks();
          if (!reading.ok) {
            local.failure = ExecutionFailureReason::clock_read;
            break;
          }
          if (reading.ticks >= target) {
            due = true;
            break;
          }
          ++local.wait_polls;
          relax.relax();
        }
        if (local.failure != ExecutionFailureReason::none) {
          break;
        }
        if (!due) {
          local.failure = ExecutionFailureReason::producer_wait_watchdog;
          break;
        }

        // Exactly one call corresponds to this logical arrival. There is no
        // retry branch after FULL or after any other result.
        const auto attempt = backend.try_producer_attempt(
            {logical_sequence, schedule_deadline, accepted_ordinal});
        ++local.attempted;
        if (attempt.status != AttemptStatus::complete) {
          local.failure = ExecutionFailureReason::producer_attempt;
          break;
        }
        if (attempt.outcome == queue::EnqueueResult::accepted) {
          ++local.accepted;
          ++accepted_ordinal;
        } else {
          ++local.full;
        }
        ++logical_sequence;
      }

      if (local.failure != ExecutionFailureReason::none) {
        producer_failed.store(true, std::memory_order_release);
        cancellation.store(true, std::memory_order_release);
      } else {
        local.completed = true;
      }
      termination.publish_arrivals_finished();
      local.arrivals_finished_published = true;
      return local;
    }();
  });

  std::thread consumer([&] {
    consumer_state = [&]() noexcept {
      detail::ConsumerWorkerState local;
      if (!preparation.prepare_consumer()) {
        local.failure = ExecutionFailureReason::worker_preparation;
        local.failure_phase = ExecutionFailurePhase::pre_run;
        preparation_failed.store(true, std::memory_order_release);
        cancellation.store(true, std::memory_order_release);
        barrier.cancel();
        return local;
      }
      if (barrier.arrive(WorkerRole::consumer) != StartBarrierStatus::ready) {
        local.failure = ExecutionFailureReason::cancelled;
        local.failure_phase = ExecutionFailurePhase::start_barrier;
        cancellation.store(true, std::memory_order_release);
        return local;
      }
      if (barrier.worker_wait(limits.worker_start_poll_limit, [&] { relax.relax(); }) !=
          StartBarrierStatus::released) {
        local.failure = ExecutionFailureReason::start_watchdog;
        local.failure_phase = ExecutionFailurePhase::start_barrier;
        cancellation.store(true, std::memory_order_release);
        return local;
      }

      std::uint64_t candidate_consumed_ordinal = 0U;
      std::uint64_t empty_before_finish = 0U;
      while (true) {
        const bool finished = termination.arrivals_finished();
        if (finished && producer_failed.load(std::memory_order_acquire)) {
          break;
        }
        const auto poll = backend.try_consumer_poll(candidate_consumed_ordinal);
        if (finished) {
          ++local.drain_polls;
          if (local.drain_polls > limits.drain_poll_limit) {
            local.failure = ExecutionFailureReason::drain_watchdog;
            local.failure_phase = ExecutionFailurePhase::drain;
            cancellation.store(true, std::memory_order_release);
            break;
          }
        }
        if (poll.status == ConsumerPollStatus::item) {
          ++local.consumed;
          ++candidate_consumed_ordinal;
          empty_before_finish = 0U;
          continue;
        }
        if (poll.status == ConsumerPollStatus::failure) {
          local.failure = ExecutionFailureReason::consumer_poll;
          // Publication can race the poll boundary. A second acquire assigns
          // a failure observed after producer publication to DRAIN rather than
          // misclassifying it as an in-measurement failure.
          local.failure_phase = (finished || termination.arrivals_finished())
                                    ? ExecutionFailurePhase::drain
                                    : ExecutionFailurePhase::measurement;
          cancellation.store(true, std::memory_order_release);
          break;
        }
        if (finished) {
          local.drained = true;
          break;
        }
        ++empty_before_finish;
        ++local.empty_polls;
        if (empty_before_finish >= limits.consumer_empty_poll_limit_before_finish) {
          local.failure = ExecutionFailureReason::consumer_wait_watchdog;
          local.failure_phase = ExecutionFailurePhase::measurement;
          cancellation.store(true, std::memory_order_release);
          break;
        }
        relax.relax();
      }
      return local;
    }();
  });

  const auto barrier_status = barrier.controller_wait(
      limits.controller_start_poll_limit, [&] { relax.relax(); });
  if (barrier_status != StartBarrierStatus::ready) {
    cancellation.store(true, std::memory_order_release);
    barrier.cancel();
    producer.join();
    consumer.join();
    const bool failed_preparation = preparation_failed.load(std::memory_order_acquire);
    report.failure_phase = failed_preparation ? ExecutionFailurePhase::pre_run
                                              : ExecutionFailurePhase::start_barrier;
    report.failure_reason = failed_preparation
                                ? ExecutionFailureReason::worker_preparation
                                : ExecutionFailureReason::start_watchdog;
    report.cancellation_requested = true;
    return report;
  }
  const auto origin_reading = clock.read_ticks();
  if (!origin_reading.ok || barrier.release_with_measurement_origin(
                                origin_reading.ticks) != StartBarrierStatus::released) {
    cancellation.store(true, std::memory_order_release);
    barrier.cancel();
    producer.join();
    consumer.join();
    report.failure_phase = ExecutionFailurePhase::start_barrier;
    report.failure_reason = origin_reading.ok ? ExecutionFailureReason::start_watchdog
                                              : ExecutionFailureReason::clock_read;
    report.cancellation_requested = true;
    return report;
  }
  report.measurement_origin_ticks = origin_reading.ticks;

  producer.join();
  consumer.join();
  report.cancellation_requested = cancellation.load(std::memory_order_acquire);
  report.attempted = producer_state.attempted;
  report.accepted = producer_state.accepted;
  report.full = producer_state.full;
  report.producer_wait_polls = producer_state.wait_polls;
  report.producer_completed = producer_state.completed;
  report.arrivals_finished_published = producer_state.arrivals_finished_published;
  report.consumed = consumer_state.consumed;
  report.consumer_empty_polls = consumer_state.empty_polls;
  report.drain_polls = consumer_state.drain_polls;
  report.consumer_drained = consumer_state.drained;

  if (producer_state.failure != ExecutionFailureReason::none &&
      !(producer_state.failure == ExecutionFailureReason::cancelled &&
        consumer_state.failure != ExecutionFailureReason::none)) {
    report.failure_phase =
        producer_state.failure == ExecutionFailureReason::start_watchdog
            ? ExecutionFailurePhase::start_barrier
            : ExecutionFailurePhase::measurement;
    report.failure_reason = producer_state.failure;
  } else if (consumer_state.failure != ExecutionFailureReason::none) {
    report.failure_phase = consumer_state.failure_phase;
    report.failure_reason = consumer_state.failure;
  }
  return report;
}

class NoopWorkerPreparation final {
public:
  [[nodiscard]] auto prepare_producer() const noexcept -> bool { return true; }
  [[nodiscard]] auto prepare_consumer() const noexcept -> bool { return true; }
};

template <typename Clock, typename Backend, typename Relax>
[[nodiscard]] auto execute_measurement(PreparedScheduleView schedule, Clock& clock,
                                       Backend& backend,
                                       TerminationControl& termination,
                                       const ExecutionLimits& limits, Relax& relax)
    -> MeasurementExecutionReport {
  NoopWorkerPreparation preparation;
  return execute_measurement_with_preparation(schedule, clock, backend, termination,
                                              limits, relax, preparation);
}

} // namespace cpu_prefetch::lifecycle

#endif // CPU_PREFETCH_LIFECYCLE_EXECUTOR_HPP
