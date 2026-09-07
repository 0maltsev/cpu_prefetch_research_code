#include <gtest/gtest.h>

#include "cpu_prefetch/workload/packages.hpp"
#include "cpu_prefetch/workload/records.hpp"
#include "cpu_prefetch/workload/working_set.hpp"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdlib>
#include <new>

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

struct NoAllocationEmitter final {
  const void* last_target{nullptr};
  void ring_producer_write(const void* target) noexcept { last_target = target; }
  void ring_consumer_read(const void* target) noexcept { last_target = target; }
  void successor_header(const void* target) noexcept { last_target = target; }
};

cpu_prefetch::workload::MasterSeed test_seed() {
  return cpu_prefetch::workload::MasterSeed::from_hex(
      "000102030405060708090a0b0c0d0e0f"
      "101112131415161718191a1b1c1d1e1f");
}

cpu_prefetch::queue::EventPointer required_pointer(const void* pointer) {
  const auto result = cpu_prefetch::queue::EventPointer::from(pointer);
  if (!result.has_value()) {
    std::terminate();
  }
  return *result;
}

TEST(PreparedWorkload, LookupRecordActionAndAllPackageOperationsAllocateNothing) {
  constexpr cpu_prefetch::queue::CacheLineBytes line{64U};
  constexpr cpu_prefetch::queue::ArenaAlignmentBytes page{4096U};
  cpu_prefetch::workload::EventArena arena(
      {64U, line.value, page.value, test_seed(), "no-allocation-test"});
  const cpu_prefetch::workload::NodeOrderPlan node_plan(
      {64U, line.value, line.value, page.value}, test_seed(), "no-allocation-test");

  cpu_prefetch::queue::RingSpscQueue r0_queue({64U}, line);
  cpu_prefetch::queue::RingSpscQueue r1_queue({64U}, line);
  cpu_prefetch::queue::RingSpscQueue r2_queue({64U}, line);
  cpu_prefetch::queue::LinkedSpscQueue l0_queue({64U}, line, page, node_plan.order());
  cpu_prefetch::queue::LinkedSpscQueue l1_queue({64U}, line, page, node_plan.order());
  NoAllocationEmitter emitter;
  cpu_prefetch::workload::R0Package r0(r0_queue);
  cpu_prefetch::workload::R1Package r1(
      r1_queue, emitter,
      cpu_prefetch::workload::ring_one_line_distance({64U, line.value, sizeof(void*)}));
  const auto calibrated = cpu_prefetch::workload::resolve_calibrated_ring_distance(
      {64U, line.value, sizeof(void*)}, 2U, "synthetic-calibration");
  cpu_prefetch::workload::R2Package r2(r2_queue, emitter, calibrated);
  cpu_prefetch::workload::L0Package l0(l0_queue);
  cpu_prefetch::workload::L1Package l1(l1_queue, emitter);
  std::array<cpu_prefetch::workload::ConsumerState, 5> states{
      cpu_prefetch::workload::ConsumerState{1U},
      cpu_prefetch::workload::ConsumerState{1U},
      cpu_prefetch::workload::ConsumerState{1U},
      cpu_prefetch::workload::ConsumerState{1U},
      cpu_prefetch::workload::ConsumerState{1U}};

  const auto before = allocation_count.load(std::memory_order_relaxed);
  for (std::uint64_t sequence = 0U; sequence < 10'000U; ++sequence) {
    const auto selection =
        arena.select(cpu_prefetch::workload::LogicalSequence{sequence});
    const auto pointer = required_pointer(selection.record);
    if (r0.try_enqueue(pointer) != cpu_prefetch::queue::EnqueueResult::accepted ||
        arena.access_and_mix(r0.try_dequeue().event, states[0]).status !=
            cpu_prefetch::workload::RecordAccessStatus::valid ||
        r1.try_enqueue(pointer) != cpu_prefetch::queue::EnqueueResult::accepted ||
        arena.access_and_mix(r1.try_dequeue().event, states[1]).status !=
            cpu_prefetch::workload::RecordAccessStatus::valid ||
        r2.try_enqueue(pointer) != cpu_prefetch::queue::EnqueueResult::accepted ||
        arena.access_and_mix(r2.try_dequeue().event, states[2]).status !=
            cpu_prefetch::workload::RecordAccessStatus::valid ||
        l0.try_enqueue(pointer) != cpu_prefetch::queue::EnqueueResult::accepted ||
        arena.access_and_mix(l0.try_dequeue().event, states[3]).status !=
            cpu_prefetch::workload::RecordAccessStatus::valid ||
        l1.try_enqueue(pointer) != cpu_prefetch::queue::EnqueueResult::accepted ||
        arena.access_and_mix(l1.try_dequeue().event, states[4]).status !=
            cpu_prefetch::workload::RecordAccessStatus::valid) {
      std::terminate();
    }
  }
  const auto after = allocation_count.load(std::memory_order_relaxed);
  EXPECT_EQ(after, before);
  EXPECT_NE(emitter.last_target, nullptr);
}

} // namespace
