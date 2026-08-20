#ifndef CPU_PREFETCH_TIMING_CAPTURE_HPP
#define CPU_PREFETCH_TIMING_CAPTURE_HPP

#include "cpu_prefetch/protocol/model.hpp"
#include "cpu_prefetch/queue/common.hpp"
#include "cpu_prefetch/timing/clock.hpp"
#include "cpu_prefetch/workload/records.hpp"

#include <cstdint>
#include <optional>

namespace cpu_prefetch::timing {

enum class CaptureStatus : std::uint8_t {
  complete,
  empty,
  clock_failure,
  queue_failure,
  record_failure,
};

enum class TimestampBoundary : std::uint8_t {
  producer_handle_begin,
  record_lookup_completion,
  enqueue_invocation,
  enqueue_linearization,
  enqueue_attempt_completion,
  dequeue_invocation,
  dequeue_linearization,
  dequeue_completion,
  consumer_action_completion,
};

struct ProducerObservation final {
  workload::LogicalSequence logical_sequence;
  workload::RecordIndex record_index;
  std::uint64_t scheduled_arrival;
  ClockSample producer_handle_begin;
  ClockSample record_lookup_completion;
  ClockSample enqueue_invocation;
  std::optional<ClockSample> enqueue_linearization;
  ClockSample enqueue_attempt_completion;
  protocol::ProducerOutcome outcome;
  std::optional<workload::AcceptedOrdinal> accepted_ordinal;
};

struct ConsumerObservation final {
  workload::AcceptedOrdinal consumed_ordinal;
  workload::RecordIndex observed_record_index;
  ClockSample dequeue_invocation;
  ClockSample dequeue_linearization;
  ClockSample dequeue_completion;
  ClockSample consumer_action_completion;
};

struct ProducerCaptureResult final {
  CaptureStatus status;
  std::optional<TimestampBoundary> failed_boundary;
  ClockReadStatus clock_status;
  std::optional<ProducerObservation> observation;
};

struct ConsumerCaptureResult final {
  CaptureStatus status;
  std::optional<TimestampBoundary> failed_boundary;
  ClockReadStatus clock_status;
  workload::RecordAccessStatus record_status;
  std::optional<ConsumerObservation> observation;
};

namespace detail {

[[nodiscard]] inline auto producer_clock_failure(TimestampBoundary boundary,
                                                 ClockReadStatus status) noexcept
    -> ProducerCaptureResult {
  return {CaptureStatus::clock_failure, boundary, status, std::nullopt};
}

[[nodiscard]] inline auto consumer_clock_failure(TimestampBoundary boundary,
                                                 ClockReadStatus status) noexcept
    -> ConsumerCaptureResult {
  return {CaptureStatus::clock_failure, boundary, status,
          workload::RecordAccessStatus::valid, std::nullopt};
}

} // namespace detail

template <typename Clock, typename Package>
[[nodiscard]] auto capture_due_producer_attempt(
    Clock& clock, const workload::EventArena& arena, Package& package,
    workload::LogicalSequence logical_sequence, std::uint64_t scheduled_arrival,
    workload::AcceptedOrdinal candidate_accepted_ordinal) noexcept
    -> ProducerCaptureResult {
  const auto handle_begin = clock.read();
  if (handle_begin.status != ClockReadStatus::ok) {
    return detail::producer_clock_failure(TimestampBoundary::producer_handle_begin,
                                          handle_begin.status);
  }

  const auto selection = arena.select(logical_sequence);
  const auto lookup_completion = clock.read();
  if (lookup_completion.status != ClockReadStatus::ok) {
    return detail::producer_clock_failure(TimestampBoundary::record_lookup_completion,
                                          lookup_completion.status);
  }
  const auto pointer = queue::EventPointer::from(selection.record);
  if (!pointer.has_value()) {
    return {CaptureStatus::record_failure, std::nullopt, ClockReadStatus::ok,
            std::nullopt};
  }

  const auto enqueue_invocation = clock.read();
  if (enqueue_invocation.status != ClockReadStatus::ok) {
    return detail::producer_clock_failure(TimestampBoundary::enqueue_invocation,
                                          enqueue_invocation.status);
  }

  struct BoundaryObserver final {
    Clock& clock;
    ClockReadResult reading{ClockReadStatus::call_failed, {0U, 0U}};

    [[nodiscard]] auto before_enqueue_publication() noexcept -> bool {
      reading = clock.read();
      return reading.status == ClockReadStatus::ok;
    }
  } boundary_observer{clock};

  const auto queue_result =
      package.try_enqueue_with_boundary_observer(*pointer, boundary_observer);
  if (queue_result.status == queue::BoundaryCaptureStatus::capture_failed) {
    return detail::producer_clock_failure(TimestampBoundary::enqueue_linearization,
                                          boundary_observer.reading.status);
  }
  const auto attempt_completion = clock.read();
  if (attempt_completion.status != ClockReadStatus::ok) {
    return detail::producer_clock_failure(TimestampBoundary::enqueue_attempt_completion,
                                          attempt_completion.status);
  }

  const bool accepted = queue_result.result == queue::EnqueueResult::accepted;
  return {CaptureStatus::complete, std::nullopt, ClockReadStatus::ok,
          ProducerObservation{
              logical_sequence, selection.record_index, scheduled_arrival,
              handle_begin.sample, lookup_completion.sample, enqueue_invocation.sample,
              accepted ? std::optional<ClockSample>{boundary_observer.reading.sample}
                       : std::nullopt,
              attempt_completion.sample,
              accepted ? protocol::ProducerOutcome::accepted
                       : protocol::ProducerOutcome::full,
              accepted
                  ? std::optional<workload::AcceptedOrdinal>{candidate_accepted_ordinal}
                  : std::nullopt}};
}

template <typename Clock, typename Package>
[[nodiscard]] auto
capture_dequeue_poll(Clock& clock, const workload::EventArena& arena, Package& package,
                     workload::ConsumerState& consumer_state,
                     workload::AcceptedOrdinal consumed_ordinal) noexcept
    -> ConsumerCaptureResult {
  const auto dequeue_invocation = clock.read();
  if (dequeue_invocation.status != ClockReadStatus::ok) {
    return detail::consumer_clock_failure(TimestampBoundary::dequeue_invocation,
                                          dequeue_invocation.status);
  }

  struct BoundaryObserver final {
    Clock& clock;
    ClockReadResult reading{ClockReadStatus::call_failed, {0U, 0U}};

    [[nodiscard]] auto after_dequeue_observation() noexcept -> bool {
      reading = clock.read();
      return reading.status == ClockReadStatus::ok;
    }
  } boundary_observer{clock};

  const auto queue_result =
      package.try_dequeue_with_boundary_observer(boundary_observer);
  if (queue_result.status == queue::BoundaryCaptureStatus::capture_failed) {
    return detail::consumer_clock_failure(TimestampBoundary::dequeue_linearization,
                                          boundary_observer.reading.status);
  }
  if (queue_result.result.status == queue::DequeueStatus::empty) {
    return {CaptureStatus::empty, std::nullopt, ClockReadStatus::ok,
            workload::RecordAccessStatus::valid, std::nullopt};
  }
  if (queue_result.result.status != queue::DequeueStatus::item) {
    return {CaptureStatus::queue_failure, std::nullopt, ClockReadStatus::ok,
            workload::RecordAccessStatus::valid, std::nullopt};
  }

  const auto dequeue_completion = clock.read();
  if (dequeue_completion.status != ClockReadStatus::ok) {
    return detail::consumer_clock_failure(TimestampBoundary::dequeue_completion,
                                          dequeue_completion.status);
  }

  const auto access = arena.access_and_mix(queue_result.result.event, consumer_state);
  if (access.status != workload::RecordAccessStatus::valid) {
    return {CaptureStatus::record_failure, std::nullopt, ClockReadStatus::ok,
            access.status, std::nullopt};
  }

  const auto action_completion = clock.read();
  if (action_completion.status != ClockReadStatus::ok) {
    return detail::consumer_clock_failure(TimestampBoundary::consumer_action_completion,
                                          action_completion.status);
  }

  return {CaptureStatus::complete, std::nullopt, ClockReadStatus::ok,
          workload::RecordAccessStatus::valid,
          ConsumerObservation{consumed_ordinal, access.record_index,
                              dequeue_invocation.sample,
                              boundary_observer.reading.sample,
                              dequeue_completion.sample, action_completion.sample}};
}

[[nodiscard]] auto make_producer_record(const protocol::RunId& run_id,
                                        const ProducerObservation& observation)
    -> protocol::ProducerRecord;
[[nodiscard]] auto make_consumer_record(const protocol::RunId& run_id,
                                        const ConsumerObservation& observation)
    -> protocol::ConsumerRecord;

} // namespace cpu_prefetch::timing

#endif // CPU_PREFETCH_TIMING_CAPTURE_HPP
