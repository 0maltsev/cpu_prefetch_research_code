#ifndef CPU_PREFETCH_CALIBRATION_DETAIL_SCHEDULED_SESSION_IMPL_HPP
#define CPU_PREFETCH_CALIBRATION_DETAIL_SCHEDULED_SESSION_IMPL_HPP

namespace cpu_prefetch::calibration {

// Same D210 synchronization primitives and owner lifetime, with a distinct
// scheduled producer algorithm. No top-level measurement executor is called:
// it would spawn new workers and lose persistent warmup/reset ownership.
template <typename Clock, typename Backend, typename Preparation, typename Relax,
          typename Observer, typename Threads>
[[nodiscard]] auto
run_scheduled_session(const ScheduledSessionPlan& plan, Clock& clock, Backend& backend,
                      Preparation& preparation, Relax& relax, Observer& observer,
                      Threads& threads, ScheduledSessionStorage& storage)
    -> ScheduledSessionResult {
  static_assert(!Backend::counts_completion_interval,
                "scheduled Q16c must not apply D211 filtering");
  const auto& bounds = plan.bounds;
  auto& common = storage.common;
  std::array<lifecycle::PreparedScheduleView, 2U> mapped_schedules{};
  static_assert(noexcept(clock.read()));
  static_assert(noexcept(clock.origin()));
  static_assert(noexcept(relax.relax()));
  static_assert(std::atomic<ServiceSessionStop>::is_always_lock_free);
  static_assert(std::atomic<bool>::is_always_lock_free);
  static_assert(std::atomic<std::uint32_t>::is_always_lock_free);
  if (!common.claim()) {
    ServiceSessionResult rejected;
    rejected.stop = ServiceSessionStop::storage_already_used;
    return {rejected, {}};
  }
  auto& result = common.result;
  if (!valid_scheduled_plan(plan) || common.arrivals[0U] == nullptr ||
      common.arrivals[1U] == nullptr || common.arrivals[0U] == common.arrivals[1U]) {
    result.stop = ServiceSessionStop::invalid_plan;
    return {result, storage.schedules};
  }
  result.clock_origin = clock.origin();
  for (auto* control : common.arrivals) {
    if (!control->reset_quiescent(true)) {
      result.stop = ServiceSessionStop::preparation_failure;
      return {result, storage.schedules};
    }
  }
  const auto failed = [&]() noexcept {
    return common.failure.load(std::memory_order_acquire) !=
           ServiceSessionStop::not_started;
  };
  const auto fail = [&](ServiceSessionStop reason) noexcept {
    auto expected = ServiceSessionStop::not_started;
    static_cast<void>(common.failure.compare_exchange_strong(
        expected, reason, std::memory_order_acq_rel));
    for (auto& barrier : common.barriers) {
      barrier.cancel();
    }
  };
  const auto wait = [&](const auto& predicate) noexcept {
    for (std::uint64_t poll = 0U; poll < bounds.barrier_poll_limit; ++poll) {
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
          return backend.prepare_producer();
        } else {
          return backend.prepare_consumer();
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
        auto& barrier = common.barriers[phase_index];
        if (barrier.arrive(role) != lifecycle::StartBarrierStatus::ready ||
            barrier.worker_wait(bounds.barrier_poll_limit, [&]() noexcept {
              relax.relax();
            }) != lifecycle::StartBarrierStatus::released) {
          fail(ServiceSessionStop::barrier_failure);
          return;
        }
        const auto window =
            service_window(barrier.measurement_origin(), bounds.phases[phase_index]);
        if (!window) {
          fail(ServiceSessionStop::deadline_overflow);
          return;
        }
        auto& arrivals = *common.arrivals[phase_index];
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
          auto& scheduled = storage.schedules[phase_index];
          const auto source = mapped_schedules[phase_index];
          for (const auto deadline : source.deadline_ticks) {
            if (failed()) {
              break;
            }
            std::uint64_t target = 0U;
            if (!lifecycle::detail::checked_measurement_deadline(
                    {window->origin_ticks, source.origin_ticks, deadline}, target)) {
              fail(ServiceSessionStop::deadline_overflow);
              break;
            }
            scheduled.mapped_last_deadline = target;
            while (!failed()) {
              const auto now = read();
              if (!now) {
                break;
              }
              if (*now >= window->drain_deadline_ticks) {
                fail(ServiceSessionStop::drain_timeout);
                break;
              }
              if (*now >= target) {
                break;
              }
              if (scheduled.producer_wait_polls ==
                  std::numeric_limits<std::uint64_t>::max()) {
                fail(ServiceSessionStop::poll_limit);
                break;
              }
              ++scheduled.producer_wait_polls;
              relax.relax();
            }
            if (failed()) {
              break;
            }
            // The mapped a_i shares the raw clock domain. The immutable source
            // deadline is retained separately; lateness never shifts a_i.
            const auto attempted = capture.try_producer_attempt(
                {report.attempted, target, report.accepted});
            ++report.attempted;
            if (attempted.status != lifecycle::AttemptStatus::complete) {
              fail(ServiceSessionStop::producer_failure);
              break;
            }
            if (attempted.outcome == queue::EnqueueResult::accepted) {
              ++report.accepted;
            } else {
              ++report.full;
            }
          }
          // Spec 5.5: publish immediately after the last scheduled attempt,
          // including a late final attempt. Never wait for the nominal horizon.
          arrivals.publish_arrivals_finished();
          report.arrivals_finished_published = true;
          scheduled.all_arrivals_attempted =
              !failed() && report.attempted == scheduled.offered;
          const auto completed = clock.read();
          scheduled.producer_completion = completed;
          report.last_clock_status = completed.status;
          if (completed.status != timing::ClockReadStatus::ok ||
              completed.sample.relative_picoseconds < previous) {
            fail(ServiceSessionStop::clock_failure);
          } else {
            report.last_observed_tick = completed.sample.relative_picoseconds;
            report.deadline_reached = completed.sample.relative_picoseconds >=
                                      window->producer_deadline_ticks;
            if (completed.sample.relative_picoseconds >= window->drain_deadline_ticks) {
              fail(ServiceSessionStop::drain_timeout);
            }
          }
        } else {
          static_assert(noexcept(capture.try_consumer_poll(std::uint64_t{})));
          auto& report = result.phases[phase_index].consumer;
          // Acquire BEFORE the poll. An empty result is terminal only when its
          // poll follows that acquire, covering a final enqueue racing an earlier
          // empty poll. Drain ends normally, without a nominal-horizon hold.
          while (!failed()) {
            const auto now = read();
            if (!now) {
              break;
            }
            if (*now >= window->drain_deadline_ticks) {
              fail(ServiceSessionStop::drain_timeout);
              break;
            }
            if (report.polls == bounds.phases[phase_index].consumer_poll_limit) {
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
        common.finished[phase_index].fetch_or(1U << index, std::memory_order_acq_rel);
        if (!wait([&]() noexcept {
              return common.proceed[phase_index].load(std::memory_order_acquire);
            })) {
          return;
        }
        if (phase_index == 0U) {
          const bool reset = [&] {
            if constexpr (Role == RingWorker::producer) {
              return backend.reset_producer();
            } else {
              return backend.reset_consumer();
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
        auto& barrier = common.barriers[index];
        if (barrier.controller_wait(bounds.barrier_poll_limit, [&]() noexcept {
              relax.relax();
            }) != lifecycle::StartBarrierStatus::ready) {
          fail(ServiceSessionStop::barrier_failure);
          break;
        }
        if (index == 0U) {
          // Owner preparation constructs both mapped immutable schedules. The
          // release barrier publishes these exact views to both persistent workers.
          for (std::size_t source_index = 0U; source_index < 2U; ++source_index) {
            const auto source_phase =
                source_index == 0U ? ServicePhase::warmup : ServicePhase::measurement;
            mapped_schedules[source_index] = preparation.schedule(source_phase);
            const auto& declared = plan.phases[source_index];
            if (!scheduled_source_matches(declared, mapped_schedules[source_index])) {
              fail(ServiceSessionStop::invalid_plan);
              break;
            }
            auto& evidence = storage.schedules[source_index];
            evidence.offered = declared.offered_count;
            evidence.source_origin_ticks = declared.source_origin_ticks;
            evidence.source_horizon_ticks = declared.source_horizon_ticks;
            evidence.mapped_schedule_validated = true;
          }
          if (failed()) {
            break;
          }
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
            service_window(origin.sample.relative_picoseconds, bounds.phases[index]);
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
                                   std::as_const(common.finished[index]))) {
          fail(ServiceSessionStop::observation_failure);
          break;
        }
        phase_result.during_observed = true;
        if (!wait([&]() noexcept {
              return common.finished[index].load(std::memory_order_acquire) == 3U;
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
        if (!storage.schedules[index].all_arrivals_attempted ||
            phase_result.producer.attempted != storage.schedules[index].offered ||
            !phase_result.consumer.drained ||
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
        common.proceed[index].store(true, std::memory_order_release);
      }
    }
  } catch (...) {
    fail(ServiceSessionStop::exception);
  }
  // No object captured by a worker is destroyed before all started workers join.
  threads.join();
  backend.finalize_joined();
  result.stop = common.failure.load(std::memory_order_acquire);
  if (result.stop == ServiceSessionStop::not_started) {
    result.stop = ServiceSessionStop::complete;
  }
  return {result, storage.schedules};
}

} // namespace cpu_prefetch::calibration

#endif
