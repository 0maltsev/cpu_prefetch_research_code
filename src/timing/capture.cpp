#include "cpu_prefetch/timing/capture.hpp"

namespace cpu_prefetch::timing {

auto make_producer_record(const protocol::RunId& run_id,
                          const ProducerObservation& observation)
    -> protocol::ProducerRecord {
  return {run_id,
          observation.logical_sequence.value,
          observation.record_index.value,
          observation.scheduled_arrival,
          observation.producer_handle_begin.relative_picoseconds,
          observation.record_lookup_completion.relative_picoseconds,
          observation.enqueue_invocation.relative_picoseconds,
          observation.enqueue_linearization.has_value()
              ? std::optional<std::uint64_t>{observation.enqueue_linearization
                                                 ->relative_picoseconds}
              : std::nullopt,
          observation.enqueue_attempt_completion.relative_picoseconds,
          observation.outcome,
          observation.accepted_ordinal.has_value()
              ? std::optional<std::uint64_t>{observation.accepted_ordinal->value}
              : std::nullopt};
}

auto make_consumer_record(const protocol::RunId& run_id,
                          const ConsumerObservation& observation)
    -> protocol::ConsumerRecord {
  return {run_id,
          observation.consumed_ordinal.value,
          observation.observed_record_index.value,
          observation.dequeue_invocation.relative_picoseconds,
          observation.dequeue_linearization.relative_picoseconds,
          observation.dequeue_completion.relative_picoseconds,
          observation.consumer_action_completion.relative_picoseconds};
}

} // namespace cpu_prefetch::timing
