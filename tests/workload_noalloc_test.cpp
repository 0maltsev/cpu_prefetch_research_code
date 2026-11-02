#include <gtest/gtest.h>

#include "cpu_prefetch/calibration/caller_owned_trace.hpp"
#include "cpu_prefetch/workload/packages.hpp"
#include "cpu_prefetch/workload/records.hpp"
#include "cpu_prefetch/workload/working_set.hpp"
#include "queue_phase_test_access.hpp"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdlib>
#include <new>
#include <span>
#include <vector>

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

TEST(PreparedWorkload, LinkedWarmStartResetPreservesStorageAndAllocatesNothing) {
  constexpr cpu_prefetch::queue::CacheLineBytes line{64U};
  constexpr cpu_prefetch::queue::ArenaAlignmentBytes page{4096U};
  const std::array<std::size_t, 9U> order{5U, 1U, 8U, 3U, 0U, 7U, 4U, 2U, 6U};
  cpu_prefetch::queue::LinkedSpscQueue queue({8U}, line, page, order);
  const auto* arena_before = queue.node_arena_base();
  const auto layout_before = queue.layout_evidence();
  int event{17};
  const auto pointer = required_pointer(&event);
  for (std::size_t index = 0U; index < 37U; ++index) {
    ASSERT_EQ(queue.try_enqueue(pointer), cpu_prefetch::queue::EnqueueResult::accepted);
    ASSERT_EQ(queue.try_dequeue().event, &event);
  }
  EXPECT_EQ(queue.audit_quiescent().reachable_order,
            std::vector<std::size_t>{order[1U]});
  for (unsigned reset_number = 0U; reset_number < 2U; ++reset_number) {
    const auto before = allocation_count.load(std::memory_order_relaxed);
    const bool reset = queue.reset_quiescent();
    const auto after = allocation_count.load(std::memory_order_relaxed);
    ASSERT_TRUE(reset);
    EXPECT_EQ(after, before) << "logical reset allocated scratch storage";
    EXPECT_EQ(queue.node_arena_base(), arena_before);
    EXPECT_EQ(queue.layout_evidence().storage_bytes, layout_before.storage_bytes);
    const auto audit = queue.audit_quiescent();
    EXPECT_EQ(audit.queued_events, 0U);
    EXPECT_EQ(audit.reachable_order, std::vector<std::size_t>{order[0U]});
    EXPECT_EQ(audit.recycler_order,
              std::vector<std::size_t>(order.begin() + 1, order.end()));
    EXPECT_TRUE(audit.every_node_owned_once);
    EXPECT_TRUE(audit.recycler_fifo_shape);
  }
}

TEST(PreparedWorkload, LinkedResetRejectsPendingEventsWithoutAllocationOrMutation) {
  constexpr cpu_prefetch::queue::CacheLineBytes line{64U};
  constexpr cpu_prefetch::queue::ArenaAlignmentBytes page{4096U};
  const std::array<std::size_t, 9U> order{5U, 1U, 8U, 3U, 0U, 7U, 4U, 2U, 6U};
  cpu_prefetch::queue::LinkedSpscQueue queue({8U}, line, page, order);
  int event{19};
  ASSERT_EQ(queue.try_enqueue(required_pointer(&event)),
            cpu_prefetch::queue::EnqueueResult::accepted);
  const auto before = allocation_count.load(std::memory_order_relaxed);
  const bool reset = queue.reset_quiescent();
  const auto after = allocation_count.load(std::memory_order_relaxed);
  EXPECT_FALSE(reset);
  EXPECT_EQ(after, before) << "rejected logical reset allocated scratch storage";
  const auto consumed = queue.try_dequeue();
  EXPECT_EQ(consumed.status, cpu_prefetch::queue::DequeueStatus::item);
  EXPECT_EQ(consumed.event, &event);
}

TEST(PreparedWorkload, LinkedResetRejectsCorruptCycleWithoutAllocationOrMutation) {
  constexpr cpu_prefetch::queue::CacheLineBytes line{64U};
  constexpr cpu_prefetch::queue::ArenaAlignmentBytes page{4096U};
  const std::array<std::size_t, 9U> order{5U, 1U, 8U, 3U, 0U, 7U, 4U, 2U, 6U};
  cpu_prefetch::queue::LinkedSpscQueue queue({8U}, line, page, order);
  cpu_prefetch::queue::testing::QueuePhaseTestAccess::swap_first_linked_recycler_nodes(
      queue);
  const auto corrupted = queue.audit_quiescent();
  ASSERT_TRUE(corrupted.every_node_owned_once);
  ASSERT_TRUE(corrupted.recycler_fifo_shape);
  const auto before = allocation_count.load(std::memory_order_relaxed);
  const bool reset = queue.reset_quiescent();
  const auto after = allocation_count.load(std::memory_order_relaxed);
  EXPECT_FALSE(reset) << "logical reset concealed a corrupted frozen node cycle";
  EXPECT_EQ(after, before);
  EXPECT_EQ(queue.audit_quiescent().recycler_order, corrupted.recycler_order);
}

TEST(PreparedWorkload, LinkedResetHandlesEverySentinelAndRecyclerRotation) {
  const auto check = [](std::span<const std::size_t> order) {
    constexpr cpu_prefetch::queue::CacheLineBytes line{64U};
    constexpr cpu_prefetch::queue::ArenaAlignmentBytes page{4096U};
    const auto capacity = order.size() - 1U;
    cpu_prefetch::queue::LinkedSpscQueue queue({capacity}, line, page, order);
    int event{23};
    const auto pointer = required_pointer(&event);
    // Consecutive C and C+1 are coprime: these transfer counts cover every
    // pair of recycler-cursor and sentinel-cycle positions independently.
    for (std::size_t transfers = 0U; transfers < capacity * order.size(); ++transfers) {
      for (std::size_t count = 0U; count < transfers; ++count) {
        ASSERT_EQ(queue.try_enqueue(pointer),
                  cpu_prefetch::queue::EnqueueResult::accepted);
        ASSERT_EQ(queue.try_dequeue().event, &event);
      }
      const auto before = allocation_count.load(std::memory_order_relaxed);
      const bool reset = queue.reset_quiescent();
      const auto after = allocation_count.load(std::memory_order_relaxed);
      ASSERT_TRUE(reset) << "transfers=" << transfers;
      EXPECT_EQ(after, before);
      EXPECT_EQ(event, 23);
      const auto audit = queue.audit_quiescent();
      EXPECT_EQ(audit.reachable_order, std::vector<std::size_t>{order[0U]});
      EXPECT_EQ(audit.recycler_order,
                std::vector<std::size_t>(order.begin() + 1, order.end()));
      EXPECT_TRUE(audit.every_node_owned_once);
    }
  };
  const std::array<std::size_t, 2U> one_slot{1U, 0U};
  const std::array<std::size_t, 9U> eight_slots{5U, 1U, 8U, 3U, 0U, 7U, 4U, 2U, 6U};
  check(one_slot);
  check(eight_slots);
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

TEST(WorkloadNoAllocation, CallerOwnedTracePreparationAndRecordingDoNotAllocate) {
  namespace calibration = cpu_prefetch::calibration;
  std::array<std::uint64_t, 64U> producer_demand{};
  std::array<std::uint64_t, 64U> producer_issue{};
  std::array<std::uint64_t, 64U> consumer_demand{};
  std::array<std::uint64_t, 64U> consumer_issue{};
  const auto before = allocation_count.load(std::memory_order_relaxed);
  calibration::CallerOwnedRingDemandWorker producer(calibration::RingWorker::producer,
                                                    producer_demand, producer_issue);
  calibration::CallerOwnedRingDemandWorker consumer(calibration::RingWorker::consumer,
                                                    consumer_demand, consumer_issue);
  calibration::CallerOwnedRingDemandTrace trace(producer, consumer);
  bool ok = trace.prepare_worker(calibration::RingWorker::producer) &&
            trace.prepare_worker(calibration::RingWorker::consumer);
  for (std::uint64_t sequence = 0U; sequence < 64U; ++sequence) {
    for (const auto role :
         {calibration::RingWorker::producer, calibration::RingWorker::consumer}) {
      ok = trace.record(role, 3U * sequence, 3U * sequence + 1U,
                        calibration::RingAttemptOutcome::advanced) &&
           ok;
    }
  }
  const auto after = allocation_count.load(std::memory_order_relaxed);
  EXPECT_TRUE(ok);
  EXPECT_EQ(after, before);
  EXPECT_EQ(trace.worker_series(calibration::RingWorker::producer).issue_ticks.size(),
            63U);
  EXPECT_EQ(trace.worker_series(calibration::RingWorker::consumer).issue_ticks.size(),
            63U);
}

} // namespace
