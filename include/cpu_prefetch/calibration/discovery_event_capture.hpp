#ifndef CPU_PREFETCH_CALIBRATION_DISCOVERY_EVENT_CAPTURE_HPP
#define CPU_PREFETCH_CALIBRATION_DISCOVERY_EVENT_CAPTURE_HPP

#include "cpu_prefetch/calibration/calibration.hpp"
#include "cpu_prefetch/timing/capture.hpp"

namespace cpu_prefetch::calibration {

enum class DiscoveryCaptureBoundary : std::uint8_t {
  producer_handle_begin,
  record_lookup_completion,
  enqueue_invocation,
  producer_demand_before,
  producer_demand_after,
  enqueue_publication,
  enqueue_completion,
  dequeue_invocation,
  consumer_demand_before,
  consumer_demand_after,
  dequeue_observation,
  dequeue_completion,
  consumer_action_completion,
};

struct DiscoveryDemandObservation final {
  std::optional<timing::ClockReadResult> before;
  std::optional<timing::ClockReadResult> after;
};

struct DiscoveryProducerAttemptIdentity final {
  workload::LogicalSequence logical_sequence;
  std::uint64_t scheduled_arrival;
  workload::AcceptedOrdinal candidate_accepted_ordinal;
};

struct DiscoveryProducerEventCapture final {
  RingCaptureResult capture{RingAttemptOutcome::trace_failure, std::nullopt,
                            std::nullopt, std::nullopt, false};
  std::optional<DiscoveryCaptureBoundary> failed_boundary;
  std::optional<DiscoveryProducerAttemptIdentity> requested_attempt;
  std::optional<workload::EventSelection> selected;
  std::optional<timing::ClockReadResult> handle_begin;
  std::optional<timing::ClockReadResult> lookup_completion;
  std::optional<timing::ClockReadResult> enqueue_invocation;
  DiscoveryDemandObservation demand;
  std::optional<timing::ClockReadResult> enqueue_publication;
  std::optional<timing::ClockReadResult> enqueue_completion;
  std::optional<timing::ProducerObservation> primary;
};

struct DiscoveryConsumerEventCapture final {
  RingCaptureResult capture{RingAttemptOutcome::trace_failure, std::nullopt,
                            std::nullopt, std::nullopt, false};
  std::optional<DiscoveryCaptureBoundary> failed_boundary;
  std::optional<workload::AcceptedOrdinal> candidate_consumed_ordinal;
  std::optional<timing::ClockReadResult> dequeue_invocation;
  DiscoveryDemandObservation demand;
  std::optional<timing::ClockReadResult> dequeue_observation;
  std::optional<queue::DequeueResult> operation;
  std::optional<timing::ClockReadResult> dequeue_completion;
  std::optional<workload::RecordAccessResult> access;
  std::optional<timing::ClockReadResult> action_completion;
  std::optional<timing::ConsumerObservation> primary;
};

namespace detail {

template <typename Row>
[[nodiscard]] auto discovery_clock_ok(Row& row, timing::ClockReadResult reading,
                                      DiscoveryCaptureBoundary boundary) noexcept
    -> bool {
  if (reading.status == timing::ClockReadStatus::ok) {
    return true;
  }
  row.capture.outcome = RingAttemptOutcome::clock_failure;
  if (!row.failed_boundary.has_value()) {
    row.failed_boundary = boundary;
    row.capture.failed_clock_status = reading.status;
  }
  return false;
}

template <typename Clock> struct DiscoveryDemandObserver final {
  Clock& clock;
  DiscoveryDemandObservation& observation;
  void before_slot_acquire() noexcept { observation.before = clock.read(); }
  void after_slot_acquire() noexcept { observation.after = clock.read(); }
};

template <typename Row, typename Trace>
void finish_discovery_demand(Row& row, Trace& trace, RingWorker role,
                             RingAttemptOutcome operation) noexcept {
  row.capture.operation_performed = true;
  row.capture.operation_outcome = operation;
  row.capture.outcome = operation;
  if (row.demand.before.has_value()) {
    row.capture.before_status = row.demand.before->status;
  }
  if (row.demand.after.has_value()) {
    row.capture.after_status = row.demand.after->status;
  }
  if (!row.demand.before.has_value() || !row.demand.after.has_value()) {
    row.capture.outcome = RingAttemptOutcome::trace_failure;
    return;
  }
  const auto before = *row.demand.before;
  const auto after = *row.demand.after;
  const bool before_ok = discovery_clock_ok(
      row, before,
      role == RingWorker::producer ? DiscoveryCaptureBoundary::producer_demand_before
                                   : DiscoveryCaptureBoundary::consumer_demand_before);
  const bool after_ok = discovery_clock_ok(
      row, after,
      role == RingWorker::producer ? DiscoveryCaptureBoundary::producer_demand_after
                                   : DiscoveryCaptureBoundary::consumer_demand_after);
  if (before_ok && after_ok &&
      !trace.record(role, before.sample.relative_picoseconds,
                    after.sample.relative_picoseconds, operation)) {
    row.capture.outcome = RingAttemptOutcome::trace_failure;
  }
}

} // namespace detail

// The caller supplies persistent worker-local current-row storage. Partial
// readings remain available after failure, separate from a complete primary row.
template <typename Clock, typename Trace>
[[nodiscard]] auto capture_discovery_producer_event(
    Clock& clock, const workload::EventArena& arena, queue::RingSpscQueue& ring,
    Trace& trace, workload::LogicalSequence sequence, std::uint64_t scheduled_arrival,
    workload::AcceptedOrdinal ordinal, DiscoveryProducerEventCapture& row) noexcept
    -> RingCaptureResult {
  static_assert(noexcept(clock.read()));
  const auto handle_begin = clock.read();
  row = {};
  row.requested_attempt =
      DiscoveryProducerAttemptIdentity{sequence, scheduled_arrival, ordinal};
  row.handle_begin = handle_begin;
  if (!detail::discovery_clock_ok(row, handle_begin,
                                  DiscoveryCaptureBoundary::producer_handle_begin)) {
    return row.capture;
  }
  const auto selection = arena.select(sequence);
  row.selected = selection;
  const auto lookup_completion = clock.read();
  row.lookup_completion = lookup_completion;
  if (!detail::discovery_clock_ok(row, lookup_completion,
                                  DiscoveryCaptureBoundary::record_lookup_completion)) {
    return row.capture;
  }
  const auto pointer = queue::EventPointer::from(selection.record);
  if (!pointer.has_value()) {
    row.capture.outcome = RingAttemptOutcome::record_failure;
    return row.capture;
  }
  const auto invocation = clock.read();
  row.enqueue_invocation = invocation;
  if (!detail::discovery_clock_ok(row, invocation,
                                  DiscoveryCaptureBoundary::enqueue_invocation)) {
    return row.capture;
  }
  detail::DiscoveryDemandObserver<Clock> demand{clock, row.demand};
  struct Boundary final {
    Clock& clock;
    DiscoveryProducerEventCapture& row;
    auto before_enqueue_publication() noexcept -> bool {
      row.enqueue_publication = clock.read();
      return true;
    }
  } boundary{clock, row};
  const auto operation =
      ring.try_enqueue_with_demand_and_boundary_observers(*pointer, demand, boundary);
  const auto completion = clock.read();
  row.enqueue_completion = completion;
  const bool accepted = operation.result == queue::EnqueueResult::accepted;
  detail::finish_discovery_demand(row, trace, RingWorker::producer,
                                  accepted ? RingAttemptOutcome::advanced
                                           : RingAttemptOutcome::full);
  std::optional<timing::ClockSample> publication;
  if (row.enqueue_publication.has_value()) {
    const auto observed_publication = *row.enqueue_publication;
    publication = observed_publication.sample;
    (void)detail::discovery_clock_ok(row, observed_publication,
                                     DiscoveryCaptureBoundary::enqueue_publication);
  }
  if (accepted && !publication.has_value()) {
    row.capture.outcome = RingAttemptOutcome::trace_failure;
    return row.capture;
  }
  (void)detail::discovery_clock_ok(row, completion,
                                   DiscoveryCaptureBoundary::enqueue_completion);
  if (!row.capture.failed_clock_status.has_value()) {
    row.primary = timing::ProducerObservation{
        sequence,
        selection.record_index,
        scheduled_arrival,
        handle_begin.sample,
        lookup_completion.sample,
        invocation.sample,
        publication,
        completion.sample,
        accepted ? protocol::ProducerOutcome::accepted
                 : protocol::ProducerOutcome::full,
        accepted ? std::optional<workload::AcceptedOrdinal>{ordinal} : std::nullopt};
  }
  return row.capture;
}

template <typename Clock, typename Trace>
[[nodiscard]] auto capture_discovery_consumer_event(
    Clock& clock, const workload::EventArena& arena, queue::RingSpscQueue& ring,
    Trace& trace, workload::ConsumerState& state, workload::AcceptedOrdinal ordinal,
    DiscoveryConsumerEventCapture& row) noexcept -> RingCaptureResult {
  static_assert(noexcept(clock.read()));
  const auto invocation = clock.read();
  row = {};
  row.candidate_consumed_ordinal = ordinal;
  row.dequeue_invocation = invocation;
  if (!detail::discovery_clock_ok(row, invocation,
                                  DiscoveryCaptureBoundary::dequeue_invocation)) {
    return row.capture;
  }
  detail::DiscoveryDemandObserver<Clock> demand{clock, row.demand};
  struct Boundary final {
    Clock& clock;
    DiscoveryConsumerEventCapture& row;
    auto after_dequeue_observation() noexcept -> bool {
      row.dequeue_observation = clock.read();
      return true;
    }
  } boundary{clock, row};
  const auto operation =
      ring.try_dequeue_with_demand_and_boundary_observers(demand, boundary).result;
  row.operation = operation;
  if (operation.status == queue::DequeueStatus::empty) {
    detail::finish_discovery_demand(row, trace, RingWorker::consumer,
                                    RingAttemptOutcome::empty);
    return row.capture;
  }
  const auto completion = clock.read();
  row.dequeue_completion = completion;
  // An actual item always receives the ordinary action, even after clock failure.
  const auto access = arena.access_and_mix(operation.event, state);
  row.access = access;
  const auto action_completion = clock.read();
  row.action_completion = action_completion;
  detail::finish_discovery_demand(row, trace, RingWorker::consumer,
                                  RingAttemptOutcome::advanced);
  if (!row.dequeue_observation.has_value()) {
    row.capture.outcome = RingAttemptOutcome::trace_failure;
    return row.capture;
  }
  const auto observation = *row.dequeue_observation;
  (void)detail::discovery_clock_ok(row, observation,
                                   DiscoveryCaptureBoundary::dequeue_observation);
  (void)detail::discovery_clock_ok(row, completion,
                                   DiscoveryCaptureBoundary::dequeue_completion);
  (void)detail::discovery_clock_ok(
      row, action_completion, DiscoveryCaptureBoundary::consumer_action_completion);
  if (access.status != workload::RecordAccessStatus::valid) {
    if (!row.capture.failed_clock_status.has_value()) {
      row.capture.outcome = RingAttemptOutcome::record_failure;
    }
  } else if (!row.capture.failed_clock_status.has_value()) {
    row.primary =
        timing::ConsumerObservation{ordinal,           access.record_index,
                                    invocation.sample, observation.sample,
                                    completion.sample, action_completion.sample};
  }
  return row.capture;
}

} // namespace cpu_prefetch::calibration

#endif
