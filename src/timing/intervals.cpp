#include "cpu_prefetch/timing/intervals.hpp"

#include <array>
#include <string_view>

namespace cpu_prefetch::timing {
namespace {

auto failure(std::string_view rule_id, std::string_view message)
    -> protocol::Result<protocol::JoinedRecord> {
  return protocol::Result<protocol::JoinedRecord>::failure(
      {protocol::ErrorCategory::cross_field, "$joined", std::string(rule_id),
       std::string(message)});
}

[[nodiscard]] constexpr auto
nondecreasing(std::initializer_list<std::uint64_t> values) noexcept -> bool {
  if (values.size() < 2U) {
    return true;
  }
  auto current = values.begin();
  auto previous = *current;
  ++current;
  for (; current != values.end(); ++current) {
    if (*current < previous) {
      return false;
    }
    previous = *current;
  }
  return true;
}

} // namespace

auto derive_joined_record(const protocol::ProducerRecord& producer,
                          std::uint64_t producer_row_ordinal,
                          const protocol::ConsumerRecord& consumer,
                          std::uint64_t consumer_row_ordinal)
    -> protocol::Result<protocol::JoinedRecord> {
  if (producer.outcome != protocol::ProducerOutcome::accepted ||
      !producer.enqueue_linearization.has_value() ||
      !producer.accepted_ordinal.has_value()) {
    return failure("TIM-DERIVE-ACCEPTED-ONLY",
                   "only a complete ACCEPTED producer row has latency fields");
  }
  if (producer.run_id != consumer.run_id ||
      *producer.accepted_ordinal != consumer.consumed_ordinal ||
      producer.record_index != consumer.observed_record_index) {
    return failure("TIM-DERIVE-IDENTITY",
                   "run identity, accepted ordinal, and record index must match");
  }

  const auto enqueue_linearization = *producer.enqueue_linearization;
  if (!nondecreasing({producer.scheduled_arrival, producer.producer_handle_begin,
                      producer.record_lookup_completion, producer.enqueue_invocation,
                      enqueue_linearization, producer.enqueue_attempt_completion}) ||
      !nondecreasing({consumer.dequeue_invocation, consumer.dequeue_linearization,
                      consumer.dequeue_completion,
                      consumer.consumer_action_completion}) ||
      consumer.dequeue_linearization < enqueue_linearization) {
    return failure("TIM-DERIVE-ORDER",
                   "timestamp boundaries violate their required partial order");
  }

  const auto producer_lateness =
      producer.producer_handle_begin - producer.scheduled_arrival;
  const auto pointer_lookup_interval =
      producer.record_lookup_completion - producer.producer_handle_begin;
  const auto enqueue_service_time =
      producer.enqueue_attempt_completion - producer.enqueue_invocation;
  const auto admission_delay = enqueue_linearization - producer.scheduled_arrival;
  const auto queue_residence = consumer.dequeue_linearization - enqueue_linearization;
  const auto dequeue_service_time =
      consumer.dequeue_completion - consumer.dequeue_invocation;
  const auto post_dequeue_delivery_interval =
      consumer.consumer_action_completion - consumer.dequeue_linearization;
  const auto consumer_action_interval =
      consumer.consumer_action_completion - consumer.dequeue_completion;
  const auto end_to_end_latency =
      consumer.consumer_action_completion - producer.scheduled_arrival;

  if (admission_delay > end_to_end_latency ||
      queue_residence > end_to_end_latency - admission_delay ||
      post_dequeue_delivery_interval !=
          end_to_end_latency - admission_delay - queue_residence) {
    return failure("TIM-DERIVE-ADDITIVE",
                   "additive end-to-end components do not reconcile exactly");
  }

  return protocol::Result<protocol::JoinedRecord>::success(
      {producer.run_id,
       *producer.accepted_ordinal,
       producer.logical_sequence,
       producer.record_index,
       producer_row_ordinal,
       consumer_row_ordinal,
       producer.scheduled_arrival,
       producer.producer_handle_begin,
       producer.record_lookup_completion,
       producer.enqueue_invocation,
       enqueue_linearization,
       producer.enqueue_attempt_completion,
       consumer.dequeue_invocation,
       consumer.dequeue_linearization,
       consumer.dequeue_completion,
       consumer.consumer_action_completion,
       producer_lateness,
       pointer_lookup_interval,
       enqueue_service_time,
       admission_delay,
       queue_residence,
       dequeue_service_time,
       post_dequeue_delivery_interval,
       consumer_action_interval,
       end_to_end_latency});
}

} // namespace cpu_prefetch::timing
