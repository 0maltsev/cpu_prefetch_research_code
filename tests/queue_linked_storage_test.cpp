#include "cpu_prefetch/queue/linked_spsc.hpp"
#include "cpu_prefetch/workload/packages.hpp"
#include "queue_phase_test_access.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cstdlib>
#include <deque>
#include <limits>
#include <memory>
#include <new>
#include <thread>

#ifndef CPU_PREFETCH_LINKED_ALLOCATION_HOOK
#define CPU_PREFETCH_LINKED_ALLOCATION_HOOK 1
#endif

#if CPU_PREFETCH_LINKED_ALLOCATION_HOOK
namespace {
std::atomic<std::size_t> allocations{0U};
std::atomic<std::size_t> deallocations{0U};
void counted_free(void* pointer) noexcept {
  if (pointer != nullptr) {
    deallocations.fetch_add(1U, std::memory_order_relaxed);
  }
  std::free(pointer);
}
} // namespace

// Register this file as a separate executable: allocation replacements measure
// the real borrowed constructor/reset/destructor, not an allocator mock.
void* operator new(std::size_t size) {
  allocations.fetch_add(1U, std::memory_order_relaxed);
  if (void* memory = std::malloc(std::max(size, std::size_t{1U})); memory != nullptr) {
    return memory;
  }
  throw std::bad_alloc();
}
void* operator new[](std::size_t size) { return ::operator new(size); }
void* operator new(std::size_t size, const std::nothrow_t&) noexcept {
  allocations.fetch_add(1U, std::memory_order_relaxed);
  return std::malloc(std::max(size, std::size_t{1U}));
}
void* operator new[](std::size_t size, const std::nothrow_t& tag) noexcept {
  return ::operator new(size, tag);
}
void* operator new(std::size_t size, std::align_val_t alignment) {
  allocations.fetch_add(1U, std::memory_order_relaxed);
  void* memory = nullptr;
  if (posix_memalign(&memory, static_cast<std::size_t>(alignment),
                     std::max(size, std::size_t{1U})) == 0) {
    return memory;
  }
  throw std::bad_alloc();
}
void* operator new[](std::size_t size, std::align_val_t alignment) {
  return ::operator new(size, alignment);
}
void* operator new(std::size_t size, std::align_val_t alignment,
                   const std::nothrow_t&) noexcept {
  allocations.fetch_add(1U, std::memory_order_relaxed);
  void* memory = nullptr;
  return posix_memalign(&memory, static_cast<std::size_t>(alignment),
                        std::max(size, std::size_t{1U})) == 0
             ? memory
             : nullptr;
}
void* operator new[](std::size_t size, std::align_val_t alignment,
                     const std::nothrow_t& tag) noexcept {
  return ::operator new(size, alignment, tag);
}
void operator delete(void* pointer) noexcept { counted_free(pointer); }
void operator delete[](void* pointer) noexcept { counted_free(pointer); }
void operator delete(void* pointer, std::size_t) noexcept { counted_free(pointer); }
void operator delete[](void* pointer, std::size_t) noexcept { counted_free(pointer); }
void operator delete(void* pointer, std::align_val_t) noexcept {
  counted_free(pointer);
}
void operator delete[](void* pointer, std::align_val_t) noexcept {
  counted_free(pointer);
}
void operator delete(void* pointer, std::size_t, std::align_val_t) noexcept {
  counted_free(pointer);
}
void operator delete[](void* pointer, std::size_t, std::align_val_t) noexcept {
  counted_free(pointer);
}
void operator delete(void* pointer, const std::nothrow_t&) noexcept {
  counted_free(pointer);
}
void operator delete[](void* pointer, const std::nothrow_t&) noexcept {
  counted_free(pointer);
}
void operator delete(void* pointer, std::align_val_t, const std::nothrow_t&) noexcept {
  counted_free(pointer);
}
void operator delete[](void* pointer, std::align_val_t,
                       const std::nothrow_t&) noexcept {
  counted_free(pointer);
}
#endif

namespace {
using namespace cpu_prefetch::queue;

struct Storage final {
  alignas(4096U) std::array<std::byte, 4096U> nodes{};
  alignas(64U) std::array<std::byte, 512U> recycler{};
  alignas(64U) std::array<std::byte, 512U> ownership{};
  std::array<std::size_t, 32U> order{};
  std::array<std::byte, 32U> scratch{};
  auto view(std::size_t capacity) -> LinkedStorageView {
    const auto required =
        LinkedSpscQueue::storage_requirements({capacity}, {64U}, {4096U});
    return {std::span(nodes).first(required.node_bytes),
            std::span(recycler).first(required.recycler_bytes),
            std::span(ownership).first(required.ownership_bytes),
            std::span(order).first(required.order_count),
            std::span(scratch).first(required.validation_bytes)};
  }
};

auto event(const void* pointer) -> EventPointer {
  const auto result = EventPointer::from(pointer);
  if (!result.has_value()) {
    throw std::logic_error("null test event");
  }
  return *result;
}

void same_state(const LinkedSpscQueue& left, const LinkedSpscQueue& right) {
  const auto a = left.audit_quiescent();
  const auto b = right.audit_quiescent();
  EXPECT_EQ(a.queued_events, b.queued_events);
  EXPECT_EQ(a.reachable_order, b.reachable_order);
  EXPECT_EQ(a.recycler_order, b.recycler_order);
  EXPECT_TRUE(a.chain_acyclic && b.chain_acyclic);
  EXPECT_TRUE(a.tail_reachable && b.tail_reachable);
  EXPECT_TRUE(a.every_node_owned_once && b.every_node_owned_once);
  EXPECT_TRUE(a.recycler_fifo_shape && b.recycler_fifo_shape);
  EXPECT_TRUE(a.positions_in_range && b.positions_in_range);
}

TEST(LinkedExternalStorage, CheckedRequirementsRetainTheOwnedLayout) {
  const auto required = LinkedSpscQueue::storage_requirements({3U}, {64U}, {4096U});
  EXPECT_EQ(required.order_count, 4U);
  EXPECT_EQ(required.validation_bytes, 4U);
  EXPECT_EQ(required.node_stride_bytes, 64U);
  EXPECT_EQ(required.node_bytes, 256U);
  EXPECT_EQ(required.recycler_bytes, 3U * sizeof(void*));
  EXPECT_EQ(required.ownership_bytes, 256U);
  constexpr std::array<std::size_t, 4U> order{2U, 0U, 3U, 1U};
  LinkedSpscQueue owned({3U}, {64U}, {4096U}, order);
  EXPECT_EQ(owned.layout_evidence().storage_bytes,
            required.node_bytes + required.recycler_bytes + required.ownership_bytes);
}

TEST(LinkedExternalStorage, OwnedAndBorrowedRefineFifoForEverySmallCapacity) {
  for (std::size_t capacity = 1U; capacity <= 8U; ++capacity) {
    std::vector<std::size_t> order(capacity + 1U);
    for (std::size_t index = 0U; index < order.size(); ++index) {
      order[index] = order.size() - 1U - index;
    }
    Storage storage;
    LinkedSpscQueue owned({capacity}, {64U}, {4096U}, order);
    LinkedSpscQueue borrowed({capacity}, {64U}, {4096U}, order, storage.view(capacity));
    std::array<int, 128U> events{};
    std::deque<const void*> model;
    for (std::size_t step = 0U; step < events.size(); ++step) {
      if (step % 11U < 7U) {
        const auto pointer = event(&events[step]);
        const auto expected =
            model.size() == capacity ? EnqueueResult::full : EnqueueResult::accepted;
        EXPECT_EQ(owned.try_enqueue(pointer), expected);
        EXPECT_EQ(borrowed.try_enqueue(pointer), expected);
        if (expected == EnqueueResult::accepted) {
          model.push_back(pointer.get());
        }
      } else {
        const auto a = owned.try_dequeue();
        const auto b = borrowed.try_dequeue();
        EXPECT_EQ(a.status, model.empty() ? DequeueStatus::empty : DequeueStatus::item);
        EXPECT_EQ(b.status, a.status);
        EXPECT_EQ(b.event, a.event);
        if (!model.empty()) {
          EXPECT_EQ(b.event, model.front());
          model.pop_front();
        }
      }
      same_state(owned, borrowed);
    }
    while (!model.empty()) {
      EXPECT_EQ(owned.try_dequeue().event, model.front());
      EXPECT_EQ(borrowed.try_dequeue().event, model.front());
      model.pop_front();
    }
    EXPECT_TRUE(owned.reset_quiescent());
    EXPECT_TRUE(borrowed.reset_quiescent());
    same_state(owned, borrowed);
    EXPECT_EQ(borrowed.node_arena_base(), storage.nodes.data());
    EXPECT_TRUE(borrowed.layout_evidence().bases_aligned);
    EXPECT_TRUE(borrowed.layout_evidence().ownership_lines_separated);
    EXPECT_TRUE(borrowed.atomic_lock_free_evidence().runtime_lock_free);
  }
}

TEST(LinkedExternalStorage, FreezesOrderAndResetPreservesEveryRotation) {
  Storage storage;
  std::array<std::size_t, 4U> input{2U, 0U, 3U, 1U};
  LinkedSpscQueue queue({3U}, {64U}, {4096U}, input, storage.view(3U));
  input.fill(99U);
  storage.scratch.fill(std::byte{0xff});
  int value = 1;
  const auto pointer = event(&value);
  for (std::size_t rotation = 0U; rotation < 4U; ++rotation) {
    for (std::size_t step = 0U; step < rotation; ++step) {
      ASSERT_EQ(queue.try_enqueue(pointer), EnqueueResult::accepted);
      ASSERT_EQ(queue.try_dequeue().event, &value);
    }
#if CPU_PREFETCH_LINKED_ALLOCATION_HOOK
    const auto before = allocations.load();
#endif
    const bool reset = queue.reset_quiescent();
#if CPU_PREFETCH_LINKED_ALLOCATION_HOOK
    const auto after = allocations.load();
    EXPECT_EQ(before, after);
#endif
    EXPECT_TRUE(reset);
    const auto audit = queue.audit_quiescent();
    EXPECT_EQ(audit.reachable_order, (std::vector<std::size_t>{2U}));
    EXPECT_EQ(audit.recycler_order, (std::vector<std::size_t>{0U, 3U, 1U}));
    EXPECT_EQ(queue.node_arena_base(), storage.nodes.data());
  }
}

TEST(LinkedExternalStorage,
     BorrowedConstructionOperationsAndDestructionNeverAllocateOrFree) {
#if !CPU_PREFETCH_LINKED_ALLOCATION_HOOK
  GTEST_SKIP() << "Global allocation replacements conflict with Clang TSan; "
                  "allocation/free counts are untested in this configuration";
#else
  Storage storage;
  constexpr std::array<std::size_t, 4U> order{2U, 0U, 3U, 1U};
  int value = 7;
  const auto pointer = event(&value);
  const auto view = storage.view(3U);
  bool correct = true;
  const auto allocations_before = allocations.load();
  const auto frees_before = deallocations.load();
  for (unsigned repetition = 0U; repetition < 3U; ++repetition) {
    LinkedSpscQueue queue({3U}, {64U}, {4096U}, order, view);
    correct = correct && queue.try_enqueue(pointer) == EnqueueResult::accepted;
    correct = correct && queue.try_dequeue().event == &value;
    correct = correct && queue.reset_quiescent();
  }
  const auto allocations_after = allocations.load();
  const auto frees_after = deallocations.load();
  EXPECT_TRUE(correct);
  EXPECT_EQ(allocations_after, allocations_before);
  EXPECT_EQ(frees_after, frees_before);
  storage.nodes.fill(std::byte{0x7f});
  EXPECT_EQ(storage.nodes.back(), std::byte{0x7f});
#endif
}

TEST(LinkedExternalStorage, CheckedGeometryRejectsInvalidBudgets) {
#if CPU_PREFETCH_LINKED_ALLOCATION_HOOK
  const auto before = allocations.load();
#endif
  const auto required = LinkedSpscQueue::storage_requirements({8U}, {64U}, {4096U});
#if CPU_PREFETCH_LINKED_ALLOCATION_HOOK
  const auto after = allocations.load();
  EXPECT_EQ(before, after);
#endif
  EXPECT_EQ(required.order_count, 9U);
  EXPECT_THROW(
      static_cast<void>(LinkedSpscQueue::storage_requirements({0U}, {64U}, {4096U})),
      QueueSetupError);
  EXPECT_THROW(
      static_cast<void>(LinkedSpscQueue::storage_requirements({1U}, {24U}, {4096U})),
      QueueSetupError);
  EXPECT_THROW(
      static_cast<void>(LinkedSpscQueue::storage_requirements({1U}, {64U}, {32U})),
      QueueSetupError);
  EXPECT_THROW(
      static_cast<void>(LinkedSpscQueue::storage_requirements({1U}, {64U}, {4095U})),
      QueueSetupError);
  EXPECT_THROW(static_cast<void>(LinkedSpscQueue::storage_requirements(
                   {std::numeric_limits<std::size_t>::max()}, {64U}, {4096U})),
               QueueSetupError);
  EXPECT_THROW(static_cast<void>(LinkedSpscQueue::storage_requirements(
                   {std::numeric_limits<std::size_t>::max() / 64U}, {64U}, {4096U})),
               QueueSetupError);
}

TEST(LinkedExternalStorage, RejectsEachWrongExtentBeforeTouchingQueueStorage) {
  constexpr std::array<std::size_t, 4U> order{2U, 0U, 3U, 1U};
  for (unsigned variant = 0U; variant < 6U; ++variant) {
    Storage storage;
    storage.nodes.fill(std::byte{0xa5});
    auto view = storage.view(3U);
    auto input = std::span<const std::size_t>(order);
    switch (variant) {
    case 0U:
      view.nodes = view.nodes.first(view.nodes.size() - 1U);
      break;
    case 1U:
      view.recycler = view.recycler.first(view.recycler.size() - 1U);
      break;
    case 2U:
      view.ownership = view.ownership.first(view.ownership.size() - 1U);
      break;
    case 3U:
      view.initial_order = view.initial_order.first(3U);
      break;
    case 4U:
      view.permutation_scratch = view.permutation_scratch.first(3U);
      break;
    default:
      input = input.first(3U);
      break;
    }
    EXPECT_THROW((LinkedSpscQueue({3U}, {64U}, {4096U}, input, view)), QueueSetupError);
    EXPECT_TRUE(std::ranges::all_of(storage.nodes,
                                    [](auto byte) { return byte == std::byte{0xa5}; }));
  }
}

TEST(LinkedExternalStorage, RejectsUnalignedAndAliasedRanges) {
  constexpr std::array<std::size_t, 4U> order{2U, 0U, 3U, 1U};
  for (unsigned variant = 0U; variant < 10U; ++variant) {
    Storage storage;
    auto view = storage.view(3U);
    auto input = std::span<const std::size_t>(order);
    switch (variant) {
    case 0U:
      view.nodes = {storage.nodes.data() + 1U, view.nodes.size()};
      break;
    case 1U:
      view.recycler = {storage.recycler.data() + 1U, view.recycler.size()};
      break;
    case 2U:
      view.ownership = {storage.ownership.data() + 1U, view.ownership.size()};
      break;
    case 3U:
      view.initial_order = {reinterpret_cast<std::size_t*>(storage.nodes.data() + 1U),
                            4U};
      break;
    case 4U:
      view.recycler = {storage.nodes.data(), view.recycler.size()};
      break;
    case 5U:
      view.ownership = {storage.nodes.data(), view.ownership.size()};
      break;
    case 6U:
      view.recycler = {storage.ownership.data(), view.recycler.size()};
      break;
    case 7U:
      view.initial_order = {reinterpret_cast<std::size_t*>(storage.nodes.data()), 4U};
      break;
    case 8U:
      view.permutation_scratch = std::as_writable_bytes(view.initial_order).first(4U);
      break;
    default:
      input = view.initial_order;
      break;
    }
    EXPECT_THROW((LinkedSpscQueue({3U}, {64U}, {4096U}, input, view)), QueueSetupError);
  }
}

TEST(LinkedExternalStorage, RejectsObjectOverlapAndAddressOverflowBeforeDereference) {
  Storage storage;
  constexpr std::array<std::size_t, 4U> order{2U, 0U, 3U, 1U};
  auto view = storage.view(3U);
  EXPECT_THROW(std::construct_at(
                   reinterpret_cast<LinkedSpscQueue*>(storage.nodes.data()),
                   QueueCapacity{3U}, CacheLineBytes{64U}, ArenaAlignmentBytes{4096U},
                   std::span<const std::size_t>(order), view),
               QueueSetupError);
  const auto address =
      std::numeric_limits<std::uintptr_t>::max() & ~std::uintptr_t{4095U};
  // Exact node geometry exceeds the remaining representable address range.
  const auto required = LinkedSpscQueue::storage_requirements({64U}, {64U}, {4096U});
  std::array<std::size_t, 65U> large_order{};
  std::array<std::size_t, 65U> retained{};
  std::array<std::byte, 65U> scratch{};
  view = {{std::bit_cast<std::byte*>(address), required.node_bytes},
          storage.recycler,
          std::span(storage.ownership).first(required.ownership_bytes),
          retained,
          scratch};
  EXPECT_THROW((LinkedSpscQueue({64U}, {64U}, {4096U}, large_order, view)),
               QueueSetupError);
}

TEST(LinkedExternalStorage, InvalidPermutationDoesNotConstructQueueObjects) {
  for (const auto order : {std::array<std::size_t, 4U>{0U, 1U, 1U, 3U},
                           std::array<std::size_t, 4U>{0U, 1U, 2U, 4U}}) {
    Storage storage;
    storage.nodes.fill(std::byte{0x5a});
    EXPECT_THROW((LinkedSpscQueue({3U}, {64U}, {4096U}, order, storage.view(3U))),
                 QueueSetupError);
    EXPECT_TRUE(std::ranges::all_of(storage.nodes,
                                    [](auto byte) { return byte == std::byte{0x5a}; }));
  }
}

TEST(LinkedExternalStorage, PendingOrCorruptRecyclerRejectsResetWithoutLosingEvent) {
  Storage storage;
  constexpr std::array<std::size_t, 4U> order{2U, 0U, 3U, 1U};
  LinkedSpscQueue queue({3U}, {64U}, {4096U}, order, storage.view(3U));
  int value = 4;
  ASSERT_EQ(queue.try_enqueue(event(&value)), EnqueueResult::accepted);
  EXPECT_FALSE(queue.reset_quiescent());
  EXPECT_EQ(queue.try_dequeue().event, &value);
  ASSERT_TRUE(queue.reset_quiescent());
  cpu_prefetch::queue::testing::QueuePhaseTestAccess::swap_first_linked_recycler_nodes(
      queue);
  EXPECT_FALSE(queue.reset_quiescent());
}

TEST(LinkedExternalStorage, LinkedPackagePrefetchTargetsRemainTheSuccessorHeader) {
  struct Emitter final {
    const void* target{};
    std::size_t calls{};
    void successor_header(const void* pointer) noexcept {
      target = pointer;
      ++calls;
    }
  };
  Storage storage;
  constexpr std::array<std::size_t, 4U> order{2U, 0U, 3U, 1U};
  LinkedSpscQueue queue({3U}, {64U}, {4096U}, order, storage.view(3U));
  Emitter emitter;
  cpu_prefetch::workload::L1Package package(queue, emitter);
  EXPECT_EQ(package.try_dequeue().status, DequeueStatus::empty);
  EXPECT_EQ(emitter.calls, 0U);
  int value = 5;
  for (std::size_t index = 1U; index <= 8U; ++index) {
    ASSERT_EQ(package.try_enqueue(event(&value)), EnqueueResult::accepted);
    ASSERT_EQ(package.try_dequeue().event, &value);
    EXPECT_EQ(emitter.target,
              storage.nodes.data() + order[index % 4U] * queue.node_stride_bytes());
    EXPECT_EQ(emitter.calls, index);
  }
  cpu_prefetch::workload::L0Package plain(queue);
  EXPECT_EQ(plain.try_enqueue(event(&value)), EnqueueResult::accepted);
  EXPECT_EQ(plain.try_dequeue().event, &value);
  EXPECT_EQ(emitter.calls, 8U);
}

TEST(LinkedExternalStorage, TwoThreadsTransferExactFifoAcrossRecyclerWraps) {
  Storage storage;
  constexpr std::array<std::size_t, 4U> order{2U, 0U, 3U, 1U};
  LinkedSpscQueue queue({3U}, {64U}, {4096U}, order, storage.view(3U));
  std::array<std::uint64_t, 1024U> values{};
  std::atomic<bool> failed{false};
  std::thread producer([&] {
    for (auto& value : values) {
      const auto pointer = event(&value);
      while (queue.try_enqueue(pointer) == EnqueueResult::full) {
        if (failed.load()) {
          return;
        }
        std::this_thread::yield();
      }
    }
  });
  std::thread consumer([&] {
    for (auto& value : values) {
      DequeueResult observed{DequeueStatus::empty, nullptr};
      while (observed.status == DequeueStatus::empty) {
        observed = queue.try_dequeue();
        std::this_thread::yield();
      }
      if (observed.status != DequeueStatus::item || observed.event != &value) {
        failed.store(true);
        return;
      }
    }
  });
  producer.join();
  consumer.join();
  EXPECT_FALSE(failed.load());
  EXPECT_TRUE(queue.reset_quiescent());
}
} // namespace
