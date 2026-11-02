#ifndef CPU_PREFETCH_CALIBRATION_DISCOVERY_RECONCILIATION_HPP
#define CPU_PREFETCH_CALIBRATION_DISCOVERY_RECONCILIATION_HPP

#include "cpu_prefetch/storage/raw_observations.hpp"

#include <limits>

namespace cpu_prefetch::calibration {

enum class DiscoveryJoinStatus : std::uint8_t {
  not_evaluated,
  exact,
  identity_mismatch,
  count_mismatch,
  malformed_producer,
  malformed_consumer,
  record_mismatch,
  ordinal_mismatch,
  timestamp_order,
  checksum_mismatch,
};

struct DiscoveryJoinCounts final {
  std::uint64_t attempted;
  std::uint64_t accepted;
  std::uint64_t full;
  std::uint64_t consumed;
};

struct DiscoveryChecksumWitness final {
  workload::ConsumerState initial;
  workload::ConsumerState observed;
};

struct DiscoveryJoinResult final {
  DiscoveryJoinStatus status;
  std::uint64_t matched{0U};
  std::optional<std::uint64_t> failed_producer_row{};
};

namespace detail {
[[nodiscard]] inline auto discovery_clock_order(timing::ClockSample first,
                                                timing::ClockSample second) noexcept
    -> bool {
  return first.absolute_nanoseconds <= second.absolute_nanoseconds &&
         first.relative_picoseconds <= second.relative_picoseconds;
}
} // namespace detail

// Both stream owners must be quiescent. This checks an exact consumed prefix,
// or the full drained sequence. Completeness/eligibility and external custody
// remain separate gates; no pooled statistic or hash-only join is performed.
[[nodiscard]] inline auto reconcile_discovery_primary(
    const workload::EventArena& arena, const storage::RawStreamSnapshot& producer,
    const storage::RowLayout& producer_layout,
    const storage::RawStreamSnapshot& consumer,
    const storage::RowLayout& consumer_layout, DiscoveryJoinCounts counts,
    DiscoveryChecksumWitness checksum, bool require_drained) noexcept
    -> DiscoveryJoinResult {
  DiscoveryJoinResult result{DiscoveryJoinStatus::identity_mismatch};
  if (producer.run_id.empty() || producer.run_id != consumer.run_id) {
    return result;
  }
  if (!storage::prepared_primary_stream_shape(producer, producer_layout,
                                              protocol::StreamKind::producer)) {
    result.status = DiscoveryJoinStatus::malformed_producer;
    return result;
  }
  if (!storage::prepared_primary_stream_shape(consumer, consumer_layout,
                                              protocol::StreamKind::consumer)) {
    result.status = DiscoveryJoinStatus::malformed_consumer;
    return result;
  }
  result.status = DiscoveryJoinStatus::count_mismatch;
  if (counts.full > std::numeric_limits<std::uint64_t>::max() - counts.accepted ||
      counts.attempted != counts.accepted + counts.full ||
      producer.row_count != counts.attempted || consumer.row_count != counts.consumed ||
      counts.consumed > counts.accepted ||
      (require_drained && counts.consumed != counts.accepted)) {
    return result;
  }
  auto expected_state = checksum.initial;
  std::optional<timing::ClockSample> previous_producer_completion;
  std::optional<timing::ClockSample> previous_consumer_action;
  std::optional<std::uint64_t> previous_arrival;
  std::uint64_t accepted = 0U;
  std::uint64_t full = 0U;
  for (std::uint64_t index = 0U; index < producer.row_count; ++index) {
    result.failed_producer_row = index;
    const auto parsed =
        storage::read_prepared_producer_row(producer, producer_layout, index);
    if (!parsed.has_value()) {
      result.status = DiscoveryJoinStatus::malformed_producer;
      return result;
    }
    const auto row = *parsed;
    const auto selected = arena.select(row.logical_sequence);
    if (row.record_index.value >= arena.capacity() ||
        row.record_index != selected.record_index || selected.record == nullptr) {
      result.status = DiscoveryJoinStatus::record_mismatch;
      return result;
    }
    if ((previous_arrival.has_value() && row.scheduled_arrival < *previous_arrival) ||
        (previous_producer_completion.has_value() &&
         !detail::discovery_clock_order(*previous_producer_completion,
                                        row.producer_handle_begin)) ||
        row.scheduled_arrival > row.producer_handle_begin.relative_picoseconds ||
        !detail::discovery_clock_order(row.producer_handle_begin,
                                       row.record_lookup_completion) ||
        !detail::discovery_clock_order(row.record_lookup_completion,
                                       row.enqueue_invocation) ||
        !detail::discovery_clock_order(row.enqueue_invocation,
                                       row.enqueue_attempt_completion)) {
      result.status = DiscoveryJoinStatus::timestamp_order;
      return result;
    }
    previous_arrival = row.scheduled_arrival;
    previous_producer_completion = row.enqueue_attempt_completion;
    if (row.outcome == protocol::ProducerOutcome::full) {
      ++full;
      continue;
    }
    if (!row.accepted_ordinal.has_value() || !row.enqueue_linearization.has_value()) {
      result.status = DiscoveryJoinStatus::malformed_producer;
      return result;
    }
    const auto ordinal = *row.accepted_ordinal;
    const auto publication = *row.enqueue_linearization;
    if (ordinal.value != accepted) {
      result.status = DiscoveryJoinStatus::ordinal_mismatch;
      return result;
    }
    if (!detail::discovery_clock_order(row.enqueue_invocation, publication) ||
        !detail::discovery_clock_order(publication, row.enqueue_attempt_completion)) {
      result.status = DiscoveryJoinStatus::timestamp_order;
      return result;
    }
    if (accepted < consumer.row_count) {
      const auto parsed_consumer =
          storage::read_prepared_consumer_row(consumer, consumer_layout, accepted);
      if (!parsed_consumer.has_value()) {
        result.status = DiscoveryJoinStatus::malformed_consumer;
        return result;
      }
      const auto consumed = *parsed_consumer;
      if (consumed.consumed_ordinal != ordinal ||
          consumed.observed_record_index != row.record_index) {
        result.status = DiscoveryJoinStatus::record_mismatch;
        return result;
      }
      if ((previous_consumer_action.has_value() &&
           !detail::discovery_clock_order(*previous_consumer_action,
                                          consumed.dequeue_invocation)) ||
          !detail::discovery_clock_order(consumed.dequeue_invocation,
                                         consumed.dequeue_linearization) ||
          !detail::discovery_clock_order(consumed.dequeue_linearization,
                                         consumed.dequeue_completion) ||
          !detail::discovery_clock_order(consumed.dequeue_completion,
                                         consumed.consumer_action_completion) ||
          !detail::discovery_clock_order(publication, consumed.dequeue_linearization)) {
        result.status = DiscoveryJoinStatus::timestamp_order;
        return result;
      }
      const auto& record = *selected.record;
      if (record.record_index != row.record_index.value) {
        result.status = DiscoveryJoinStatus::record_mismatch;
        return result;
      }
      expected_state = workload::mix_consumer_state(expected_state, row.record_index,
                                                    record.payload);
      previous_consumer_action = consumed.consumer_action_completion;
      ++result.matched;
    }
    ++accepted;
  }
  result.failed_producer_row.reset();
  if (accepted != counts.accepted || full != counts.full) {
    result.status = DiscoveryJoinStatus::count_mismatch;
  } else if (expected_state != checksum.observed) {
    result.status = DiscoveryJoinStatus::checksum_mismatch;
  } else {
    result.status = DiscoveryJoinStatus::exact;
  }
  return result;
}

} // namespace cpu_prefetch::calibration

#endif
