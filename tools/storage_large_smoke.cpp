#include "cpu_prefetch/storage/raw_observations.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <cstdint>
#include <iostream>
#include <utility>

int main() {
  constexpr std::uint64_t kRows = 200'000U;
  auto parsed =
      cpu_prefetch::protocol::RunId::parse("stage11-large-synthetic", "$smoke/run_id");
  if (!parsed) {
    return 2;
  }
  const auto id = std::move(parsed).value();
  cpu_prefetch::storage::ProducerObservationStream producer(id, kRows);
  cpu_prefetch::storage::ConsumerObservationStream consumer(id, kRows);
  if (!producer.prepare_for_owner() || !consumer.prepare_for_owner()) {
    return 3;
  }
  for (std::uint64_t index = 0U; index < kRows; ++index) {
    const cpu_prefetch::timing::ProducerObservation producer_row{
        cpu_prefetch::workload::LogicalSequence{index},
        cpu_prefetch::workload::RecordIndex{index & 1023U},
        index,
        {index, index},
        {index + 1U, index + 1U},
        {index + 2U, index + 2U},
        cpu_prefetch::timing::ClockSample{index + 3U, index + 3U},
        {index + 4U, index + 4U},
        cpu_prefetch::protocol::ProducerOutcome::accepted,
        cpu_prefetch::workload::AcceptedOrdinal{index}};
    const cpu_prefetch::timing::ConsumerObservation consumer_row{
        cpu_prefetch::workload::AcceptedOrdinal{index},
        cpu_prefetch::workload::RecordIndex{index & 1023U},
        {index + 5U, index + 5U},
        {index + 6U, index + 6U},
        {index + 7U, index + 7U},
        {index + 8U, index + 8U}};
    if (producer.append(producer_row) !=
            cpu_prefetch::storage::AppendStatus::appended ||
        consumer.append(consumer_row) !=
            cpu_prefetch::storage::AppendStatus::appended) {
      return 3;
    }
  }
  if (!producer.seal_complete() || !consumer.seal_complete()) {
    return 4;
  }
  const auto producer_snapshot = producer.snapshot();
  const auto consumer_snapshot = consumer.snapshot();
  if (producer_snapshot.row_count != kRows || consumer_snapshot.row_count != kRows ||
      producer_snapshot.overflowed || consumer_snapshot.overflowed ||
      cpu_prefetch::workload::sha256(producer_snapshot.bytes).hex().size() != 64U ||
      cpu_prefetch::workload::sha256(consumer_snapshot.bytes).hex().size() != 64U) {
    return 5;
  }
  std::cout << "storage-large-smoke: PASS rows=" << kRows
            << " scope=correctness-only-no-performance-claim\n";
  return 0;
}
