#ifndef CPU_PREFETCH_CALIBRATION_DISCOVERY_CONSUMER_CAPTURE_HPP
#define CPU_PREFETCH_CALIBRATION_DISCOVERY_CONSUMER_CAPTURE_HPP

#include "cpu_prefetch/calibration/calibration.hpp"

namespace cpu_prefetch::calibration {

struct DiscoveryConsumerCapture final {
  RingCaptureResult capture;
  queue::DequeueResult operation;
};

// The backend must apply its ordinary event validation/checksum action to each
// actual item, including when timing or trace retention fails after dequeue.
// Keep the pointer/status separate from the validity of the demand observation.
template <typename Clock>
[[nodiscard]] auto
capture_discovery_consumer_ring_demand(Clock& clock, queue::RingSpscQueue& ring,
                                       RingDemandTrace& trace) noexcept
    -> DiscoveryConsumerCapture {
  static_assert(noexcept(clock.read()));
  struct Observer final {
    Clock& clock;
    timing::ClockReadResult before{timing::ClockReadStatus::call_failed, {0U, 0U}};
    timing::ClockReadResult after{timing::ClockReadStatus::call_failed, {0U, 0U}};
    void before_slot_acquire() noexcept { before = clock.read(); }
    void after_slot_acquire() noexcept { after = clock.read(); }
  } observer{clock};
  const auto operation = ring.try_dequeue_with_slot_demand_observer(observer);
  const auto outcome = operation.status == queue::DequeueStatus::item
                           ? RingAttemptOutcome::advanced
                           : RingAttemptOutcome::empty;
  if (observer.before.status != timing::ClockReadStatus::ok ||
      observer.after.status != timing::ClockReadStatus::ok) {
    return {{RingAttemptOutcome::clock_failure, observer.before.status,
             observer.after.status, outcome},
            operation};
  }
  if (!trace.record(RingWorker::consumer, observer.before.sample.relative_picoseconds,
                    observer.after.sample.relative_picoseconds, outcome)) {
    return {{RingAttemptOutcome::trace_failure, observer.before.status,
             observer.after.status, outcome},
            operation};
  }
  return {{outcome, observer.before.status, observer.after.status, outcome}, operation};
}

} // namespace cpu_prefetch::calibration

#endif
