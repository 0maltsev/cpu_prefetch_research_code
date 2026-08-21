#ifndef CPU_PREFETCH_STORAGE_CAPTURE_BACKEND_HPP
#define CPU_PREFETCH_STORAGE_CAPTURE_BACKEND_HPP

#include "cpu_prefetch/lifecycle/executor.hpp"
#include "cpu_prefetch/storage/raw_observations.hpp"
#include "cpu_prefetch/timing/capture.hpp"

namespace cpu_prefetch::storage {

// Statically bound Stage 10 backend specialization. Producer and consumer
// calls touch different prepared streams; the only shared state is the
// already-qualified queue/package and immutable event arena. A capture is not
// reported complete until its entire fixed row has been committed.
template <typename CaptureClock, typename Package>
class CapturingObservationBackend final {
public:
  CapturingObservationBackend(CaptureClock& clock, const workload::EventArena& arena,
                              Package& package, workload::ConsumerState& consumer_state,
                              ProducerObservationStream& producer_stream,
                              ConsumerObservationStream& consumer_stream) noexcept
      : clock_(clock), arena_(arena), package_(package),
        consumer_state_(consumer_state), producer_stream_(producer_stream),
        consumer_stream_(consumer_stream) {}

  [[nodiscard]] auto try_producer_attempt(lifecycle::ProducerAttempt attempt) noexcept
      -> lifecycle::ProducerAttemptResult {
    const auto captured = timing::capture_due_producer_attempt(
        clock_, arena_, package_, workload::LogicalSequence{attempt.logical_sequence},
        attempt.scheduled_deadline,
        workload::AcceptedOrdinal{attempt.candidate_accepted_ordinal});
    if (captured.status != timing::CaptureStatus::complete ||
        !captured.observation.has_value()) {
      return {lifecycle::AttemptStatus::failure, queue::EnqueueResult::full};
    }
    const auto append_status = producer_stream_.append(*captured.observation);
    if (append_status != AppendStatus::appended) {
      return {lifecycle::AttemptStatus::failure,
              captured.observation->outcome == protocol::ProducerOutcome::accepted
                  ? queue::EnqueueResult::accepted
                  : queue::EnqueueResult::full};
    }
    return {lifecycle::AttemptStatus::complete,
            captured.observation->outcome == protocol::ProducerOutcome::accepted
                ? queue::EnqueueResult::accepted
                : queue::EnqueueResult::full};
  }

  [[nodiscard]] auto
  try_consumer_poll(std::uint64_t candidate_consumed_ordinal) noexcept
      -> lifecycle::ConsumerPollResult {
    const auto captured = timing::capture_dequeue_poll(
        clock_, arena_, package_, consumer_state_,
        workload::AcceptedOrdinal{candidate_consumed_ordinal});
    if (captured.status == timing::CaptureStatus::empty) {
      return {lifecycle::ConsumerPollStatus::empty};
    }
    if (captured.status != timing::CaptureStatus::complete ||
        !captured.observation.has_value() ||
        consumer_stream_.append(*captured.observation) != AppendStatus::appended) {
      return {lifecycle::ConsumerPollStatus::failure};
    }
    return {lifecycle::ConsumerPollStatus::item};
  }

private:
  CaptureClock& clock_;
  const workload::EventArena& arena_;
  Package& package_;
  workload::ConsumerState& consumer_state_;
  ProducerObservationStream& producer_stream_;
  ConsumerObservationStream& consumer_stream_;
};

} // namespace cpu_prefetch::storage

#endif // CPU_PREFETCH_STORAGE_CAPTURE_BACKEND_HPP
