#include <gtest/gtest.h>

#include "cpu_prefetch/storage/raw_observations.hpp"

#include <atomic>
#include <cstddef>
#include <cstdlib>
#include <new>
#include <optional>
#include <stdexcept>
#include <string>

namespace {
std::atomic<std::size_t> allocation_count{0U};
}

void* operator new(std::size_t size) {
  allocation_count.fetch_add(1U, std::memory_order_relaxed);
  if (void* memory = std::malloc(size); memory != nullptr) {
    return memory;
  }
  throw std::bad_alloc();
}

void* operator new[](std::size_t size) { return ::operator new(size); }

void* operator new(std::size_t size, const std::nothrow_t&) noexcept {
  allocation_count.fetch_add(1U, std::memory_order_relaxed);
  return std::malloc(size);
}

void* operator new[](std::size_t size, const std::nothrow_t& tag) noexcept {
  return ::operator new(size, tag);
}

void* operator new(std::size_t size, std::align_val_t alignment) {
  allocation_count.fetch_add(1U, std::memory_order_relaxed);
  void* memory = nullptr;
  if (posix_memalign(&memory, static_cast<std::size_t>(alignment), size) == 0) {
    return memory;
  }
  throw std::bad_alloc();
}

void* operator new[](std::size_t size, std::align_val_t alignment) {
  return ::operator new(size, alignment);
}

void* operator new(std::size_t size, std::align_val_t alignment,
                   const std::nothrow_t&) noexcept {
  allocation_count.fetch_add(1U, std::memory_order_relaxed);
  void* memory = nullptr;
  return posix_memalign(&memory, static_cast<std::size_t>(alignment), size) == 0
             ? memory
             : nullptr;
}

void* operator new[](std::size_t size, std::align_val_t alignment,
                     const std::nothrow_t& tag) noexcept {
  return ::operator new(size, alignment, tag);
}

void operator delete(void* pointer) noexcept { std::free(pointer); }
void operator delete[](void* pointer) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::size_t) noexcept { std::free(pointer); }
void operator delete[](void* pointer, std::size_t) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::align_val_t) noexcept { std::free(pointer); }
void operator delete[](void* pointer, std::align_val_t) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::size_t, std::align_val_t) noexcept {
  std::free(pointer);
}
void operator delete[](void* pointer, std::size_t, std::align_val_t) noexcept {
  std::free(pointer);
}
void operator delete(void* pointer, const std::nothrow_t&) noexcept {
  std::free(pointer);
}
void operator delete[](void* pointer, const std::nothrow_t&) noexcept {
  std::free(pointer);
}
void operator delete(void* pointer, std::align_val_t, const std::nothrow_t&) noexcept {
  std::free(pointer);
}
void operator delete[](void* pointer, std::align_val_t,
                       const std::nothrow_t&) noexcept {
  std::free(pointer);
}

namespace {

auto run_id() -> cpu_prefetch::protocol::RunId {
  auto parsed = cpu_prefetch::protocol::RunId::parse("noalloc", "$test/run_id");
  if (!parsed) {
    throw std::logic_error("invalid test run ID");
  }
  return std::move(parsed).value();
}

TEST(StorageHotWriter, ProducerAndConsumerAppendAllocateNothingAfterPreparation) {
  const auto id = run_id();
  cpu_prefetch::storage::ProducerObservationStream producer(id, 1U);
  cpu_prefetch::storage::ConsumerObservationStream consumer(id, 1U);
  ASSERT_TRUE(producer.prepare_for_owner());
  ASSERT_TRUE(consumer.prepare_for_owner());
  const cpu_prefetch::timing::ProducerObservation producer_row{
      cpu_prefetch::workload::LogicalSequence{0U},
      cpu_prefetch::workload::RecordIndex{7U},
      1U,
      {1U, 2U},
      {2U, 3U},
      {3U, 4U},
      cpu_prefetch::timing::ClockSample{4U, 5U},
      {5U, 6U},
      cpu_prefetch::protocol::ProducerOutcome::accepted,
      cpu_prefetch::workload::AcceptedOrdinal{0U}};
  const cpu_prefetch::timing::ConsumerObservation consumer_row{
      cpu_prefetch::workload::AcceptedOrdinal{0U},
      cpu_prefetch::workload::RecordIndex{7U},
      {6U, 7U},
      {7U, 8U},
      {8U, 9U},
      {9U, 10U}};

  const auto before = allocation_count.load(std::memory_order_relaxed);
  const auto producer_status = producer.append(producer_row);
  const auto consumer_status = consumer.append(consumer_row);
  const auto producer_snapshot = producer.snapshot();
  const auto consumer_snapshot = consumer.snapshot();
  const auto after = allocation_count.load(std::memory_order_relaxed);

  EXPECT_EQ(producer_status, cpu_prefetch::storage::AppendStatus::appended);
  EXPECT_EQ(consumer_status, cpu_prefetch::storage::AppendStatus::appended);
  EXPECT_EQ(producer_snapshot.row_count, 1U);
  EXPECT_EQ(consumer_snapshot.row_count, 1U);
  EXPECT_EQ(after, before);
}

} // namespace
