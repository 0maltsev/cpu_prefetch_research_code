#include "cpu_prefetch/storage/raw_observations.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <atomic>
#include <cstdint>
#include <thread>
#include <utility>

int main() {
  constexpr std::uint64_t kRows = 100'000U;
  auto parsed =
      cpu_prefetch::protocol::RunId::parse("storage-stress", "$stress/run_id");
  if (!parsed) {
    return 2;
  }
  const auto id = std::move(parsed).value();
  cpu_prefetch::storage::ProducerObservationStream producer(id, kRows);
  cpu_prefetch::storage::ConsumerObservationStream consumer(id, kRows);
  std::atomic<bool> start{false};
  std::atomic<bool> failed{false};
  std::thread producer_thread([&] {
    if (!producer.prepare_for_owner()) {
      failed.store(true, std::memory_order_release);
      return;
    }
    while (!start.load(std::memory_order_acquire)) {
    }
    for (std::uint64_t index = 0U; index < kRows; ++index) {
      const cpu_prefetch::timing::ProducerObservation row{
          cpu_prefetch::workload::LogicalSequence{index},
          cpu_prefetch::workload::RecordIndex{index & 4095U},
          index,
          {index, index},
          {index + 1U, index + 1U},
          {index + 2U, index + 2U},
          cpu_prefetch::timing::ClockSample{index + 3U, index + 3U},
          {index + 4U, index + 4U},
          cpu_prefetch::protocol::ProducerOutcome::accepted,
          cpu_prefetch::workload::AcceptedOrdinal{index}};
      if (producer.append(row) != cpu_prefetch::storage::AppendStatus::appended) {
        failed.store(true, std::memory_order_release);
        return;
      }
      if ((index & 4095U) == 0U) {
        std::this_thread::yield();
      }
    }
  });
  std::thread consumer_thread([&] {
    if (!consumer.prepare_for_owner()) {
      failed.store(true, std::memory_order_release);
      return;
    }
    while (!start.load(std::memory_order_acquire)) {
    }
    for (std::uint64_t index = 0U; index < kRows; ++index) {
      const cpu_prefetch::timing::ConsumerObservation row{
          cpu_prefetch::workload::AcceptedOrdinal{index},
          cpu_prefetch::workload::RecordIndex{index & 4095U},
          {index + 5U, index + 5U},
          {index + 6U, index + 6U},
          {index + 7U, index + 7U},
          {index + 8U, index + 8U}};
      if (consumer.append(row) != cpu_prefetch::storage::AppendStatus::appended) {
        failed.store(true, std::memory_order_release);
        return;
      }
      if ((index & 2047U) == 0U) {
        std::this_thread::yield();
      }
    }
  });
  start.store(true, std::memory_order_release);
  producer_thread.join();
  consumer_thread.join();
  if (failed.load(std::memory_order_acquire) || !producer.seal_complete() ||
      !consumer.seal_complete() || producer.snapshot().row_count != kRows ||
      consumer.snapshot().row_count != kRows ||
      cpu_prefetch::workload::sha256(producer.snapshot().bytes).hex().size() != 64U ||
      cpu_prefetch::workload::sha256(consumer.snapshot().bytes).hex().size() != 64U) {
    return 3;
  }
  return 0;
}
