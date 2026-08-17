#include <gtest/gtest.h>

#include "cpu_prefetch/queue/adapters.hpp"
#include "queue_phase_test_access.hpp"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <limits>
#include <stdexcept>
#include <thread>
#include <type_traits>
#include <vector>

namespace {

using cpu_prefetch::queue::ArenaAlignmentBytes;
using cpu_prefetch::queue::CacheLineBytes;
using cpu_prefetch::queue::DequeueStatus;
using cpu_prefetch::queue::EnqueueResult;
using cpu_prefetch::queue::EventPointer;
using cpu_prefetch::queue::LinkedQueueAdapter;
using cpu_prefetch::queue::LinkedSpscQueue;
using cpu_prefetch::queue::QueueCapacity;
using cpu_prefetch::queue::QueueSetupError;
using cpu_prefetch::queue::RingQueueAdapter;
using cpu_prefetch::queue::RingSpscQueue;

constexpr CacheLineBytes kSyntheticCacheLine{64U};
constexpr ArenaAlignmentBytes kSyntheticPage{4096U};

EventPointer event_pointer(const void* value) {
  const auto event = EventPointer::from(value);
  if (!event.has_value()) {
    throw std::logic_error("test event pointer unexpectedly null");
  }
  return *event;
}

template <typename Adapter>
void check_sequential_model(Adapter& adapter, std::size_t capacity,
                            const std::vector<std::uint8_t>& actions) {
  std::vector<std::uint64_t> events(actions.size() + 1U);
  std::deque<const void*> model;
  std::size_t next_event = 0;
  for (const auto action : actions) {
    if ((action & 1U) == 0U) {
      const auto* pointer = &events[next_event++];
      const auto result = adapter.try_enqueue(event_pointer(pointer));
      if (model.size() == capacity) {
        EXPECT_EQ(result, EnqueueResult::full);
      } else {
        EXPECT_EQ(result, EnqueueResult::accepted);
        model.push_back(pointer);
      }
      continue;
    }

    const auto result = adapter.try_dequeue();
    if (model.empty()) {
      EXPECT_EQ(result.status, DequeueStatus::empty);
      EXPECT_EQ(result.event, nullptr);
    } else {
      EXPECT_EQ(result.status, DequeueStatus::item);
      EXPECT_EQ(result.event, model.front());
      model.pop_front();
    }
  }
}

enum class SequenceFault : std::uint8_t {
  none,
  omission,
  duplicate,
  corruption_or_reorder,
};

SequenceFault audit_sequence(const std::vector<const void*>& expected,
                             const std::vector<const void*>& observed) {
  if (observed.size() < expected.size()) {
    return SequenceFault::omission;
  }
  if (observed.size() > expected.size()) {
    return SequenceFault::duplicate;
  }
  for (std::size_t index = 0; index < expected.size(); ++index) {
    if (expected[index] != observed[index]) {
      return SequenceFault::corruption_or_reorder;
    }
  }
  return SequenceFault::none;
}

TEST(QueueInput, NullCannotBecomeAStageAEventPointer) {
  EXPECT_FALSE(EventPointer::from(nullptr).has_value());
  std::uint64_t value = 1;
  ASSERT_TRUE(EventPointer::from(&value).has_value());
}

TEST(RingSpsc, EmptyFullFifoAndCapacityBoundaries) {
  RingSpscQueue queue(QueueCapacity{3U}, kSyntheticCacheLine);
  RingQueueAdapter adapter(queue);
  std::array<std::uint64_t, 4> events{11U, 22U, 33U, 44U};

  EXPECT_EQ(adapter.try_dequeue().status, DequeueStatus::empty);
  EXPECT_EQ(adapter.try_enqueue(event_pointer(&events[0])), EnqueueResult::accepted);
  EXPECT_EQ(adapter.try_enqueue(event_pointer(&events[1])), EnqueueResult::accepted);
  EXPECT_EQ(adapter.try_enqueue(event_pointer(&events[2])), EnqueueResult::accepted);
  EXPECT_EQ(adapter.try_enqueue(event_pointer(&events[3])), EnqueueResult::full);

  for (std::size_t index = 0; index < 3U; ++index) {
    const auto result = adapter.try_dequeue();
    EXPECT_EQ(result.status, DequeueStatus::item);
    EXPECT_EQ(result.event, &events[index]);
  }
  EXPECT_EQ(adapter.try_dequeue().status, DequeueStatus::empty);
  const auto audit = queue.audit_quiescent();
  EXPECT_EQ(audit.occupied_slots, 0U);
  EXPECT_TRUE(audit.positions_in_range);
}

TEST(RingSpsc, WrapAndRepeatedRecordIndicesDoNotUseMonotonicCounters) {
  RingSpscQueue queue(QueueCapacity{3U}, kSyntheticCacheLine);
  RingQueueAdapter adapter(queue);
  std::array<std::uint64_t, 5> records{};

  for (std::size_t sequence = 0; sequence < 200'000U; ++sequence) {
    auto* record = &records[sequence % records.size()];
    ASSERT_EQ(adapter.try_enqueue(event_pointer(record)), EnqueueResult::accepted);
    const auto result = adapter.try_dequeue();
    ASSERT_EQ(result.status, DequeueStatus::item);
    ASSERT_EQ(result.event, record);
  }

  const auto audit = queue.audit_quiescent();
  EXPECT_TRUE(audit.positions_in_range);
  EXPECT_LT(audit.producer_position, queue.capacity());
  EXPECT_LT(audit.consumer_position, queue.capacity());
}

TEST(LinkedSpsc, EmptyFullFifoAndExclusiveNodeOwnership) {
  const std::array<std::size_t, 4> order{2U, 0U, 3U, 1U};
  LinkedSpscQueue queue(QueueCapacity{3U}, kSyntheticCacheLine, kSyntheticPage, order);
  LinkedQueueAdapter adapter(queue);
  std::array<std::uint64_t, 4> events{11U, 22U, 33U, 44U};

  EXPECT_EQ(adapter.try_dequeue().status, DequeueStatus::empty);
  EXPECT_EQ(adapter.try_enqueue(event_pointer(&events[0])), EnqueueResult::accepted);
  EXPECT_EQ(adapter.try_enqueue(event_pointer(&events[1])), EnqueueResult::accepted);
  EXPECT_EQ(adapter.try_enqueue(event_pointer(&events[2])), EnqueueResult::accepted);
  EXPECT_EQ(adapter.try_enqueue(event_pointer(&events[3])), EnqueueResult::full);

  auto full_audit = queue.audit_quiescent();
  EXPECT_EQ(full_audit.queued_events, 3U);
  EXPECT_EQ(full_audit.recycler_nodes, 0U);
  EXPECT_TRUE(full_audit.chain_acyclic);
  EXPECT_TRUE(full_audit.tail_reachable);
  EXPECT_TRUE(full_audit.every_node_owned_once);

  for (std::size_t index = 0; index < 3U; ++index) {
    const auto result = adapter.try_dequeue();
    EXPECT_EQ(result.status, DequeueStatus::item);
    EXPECT_EQ(result.event, &events[index]);
  }
  EXPECT_EQ(adapter.try_dequeue().status, DequeueStatus::empty);

  const auto empty_audit = queue.audit_quiescent();
  EXPECT_EQ(empty_audit.queued_events, 0U);
  EXPECT_EQ(empty_audit.recycler_nodes, 3U);
  EXPECT_TRUE(empty_audit.chain_acyclic);
  EXPECT_TRUE(empty_audit.tail_reachable);
  EXPECT_TRUE(empty_audit.every_node_owned_once);
  EXPECT_TRUE(empty_audit.recycler_fifo_shape);
}

TEST(LinkedSpsc, FixedArenaRepeatsTheExactCapacityPlusOneNodeCycle) {
  const std::array<std::size_t, 4> order{2U, 0U, 3U, 1U};
  const std::array<std::size_t, 4> expected_cycle{0U, 3U, 1U, 2U};
  LinkedSpscQueue queue(QueueCapacity{3U}, kSyntheticCacheLine, kSyntheticPage, order);
  LinkedQueueAdapter adapter(queue);
  std::uint64_t event = 9U;

  for (std::size_t step = 0; step < 40U; ++step) {
    ASSERT_EQ(adapter.try_enqueue(event_pointer(&event)), EnqueueResult::accepted);
    const auto occupied = queue.audit_quiescent();
    ASSERT_EQ(occupied.reachable_order.size(), 2U);
    EXPECT_EQ(occupied.reachable_order.back(),
              expected_cycle[step % expected_cycle.size()]);
    ASSERT_EQ(adapter.try_dequeue().status, DequeueStatus::item);
    const auto empty = queue.audit_quiescent();
    EXPECT_TRUE(empty.every_node_owned_once);
    EXPECT_TRUE(empty.recycler_fifo_shape);
  }
}

TEST(QueueModel, DeterministicRandomHistoryRefinesBoundedFifo) {
  std::vector<std::uint8_t> actions;
  actions.reserve(10'000U);
  std::uint64_t state = 0x9e3779b97f4a7c15ULL;
  for (std::size_t index = 0; index < 10'000U; ++index) {
    state = (state * 6364136223846793005ULL) + 1442695040888963407ULL;
    actions.push_back(static_cast<std::uint8_t>(state >> 56U));
  }

  RingSpscQueue ring(QueueCapacity{7U}, kSyntheticCacheLine);
  RingQueueAdapter ring_adapter(ring);
  check_sequential_model(ring_adapter, ring.capacity(), actions);

  const std::array<std::size_t, 8> order{4U, 1U, 7U, 0U, 6U, 3U, 2U, 5U};
  LinkedSpscQueue linked(QueueCapacity{7U}, kSyntheticCacheLine, kSyntheticPage, order);
  LinkedQueueAdapter linked_adapter(linked);
  check_sequential_model(linked_adapter, linked.capacity(), actions);
  EXPECT_TRUE(linked.audit_quiescent().every_node_owned_once);
}

TEST(QueueOperations, OneAttemptRetainsFullWithoutInternalRetry) {
  RingSpscQueue ring(QueueCapacity{2U}, kSyntheticCacheLine);
  RingQueueAdapter adapter(ring);
  std::array<std::uint64_t, 5> arrivals{};
  std::array<EnqueueResult, 5> outcomes{};

  for (std::size_t index = 0; index < arrivals.size(); ++index) {
    outcomes[index] = adapter.try_enqueue(event_pointer(&arrivals[index]));
  }

  EXPECT_EQ(outcomes[0], EnqueueResult::accepted);
  EXPECT_EQ(outcomes[1], EnqueueResult::accepted);
  EXPECT_EQ(outcomes[2], EnqueueResult::full);
  EXPECT_EQ(outcomes[3], EnqueueResult::full);
  EXPECT_EQ(outcomes[4], EnqueueResult::full);
}

TEST(QueueProgress, RingOtherWorkerMayBeSuspendedAtEachHandoffPhase) {
  RingSpscQueue queue(QueueCapacity{1U}, kSyntheticCacheLine);
  RingQueueAdapter adapter(queue);
  std::array<std::uint64_t, 2> events{};
  std::atomic<bool> phase_reached{false};
  std::atomic<bool> resume{false};

  struct PublishObserver final {
    std::atomic<bool>& phase_reached;
    std::atomic<bool>& resume;
    void before_slot_publication() const noexcept {
      phase_reached.store(true, std::memory_order_release);
      while (!resume.load(std::memory_order_acquire)) {
      }
    }
  } publish_observer{phase_reached, resume};

  std::thread producer([&] {
    EXPECT_EQ(cpu_prefetch::queue::testing::QueuePhaseTestAccess::ring_enqueue(
                  queue, event_pointer(&events[0]), publish_observer),
              EnqueueResult::accepted);
  });
  while (!phase_reached.load(std::memory_order_acquire)) {
  }
  EXPECT_EQ(adapter.try_dequeue().status, DequeueStatus::empty);
  resume.store(true, std::memory_order_release);
  producer.join();

  phase_reached.store(false, std::memory_order_relaxed);
  resume.store(false, std::memory_order_relaxed);
  struct ReuseObserver final {
    std::atomic<bool>& phase_reached;
    std::atomic<bool>& resume;
    void before_slot_reuse_release() const noexcept {
      phase_reached.store(true, std::memory_order_release);
      while (!resume.load(std::memory_order_acquire)) {
      }
    }
  } reuse_observer{phase_reached, resume};

  std::thread consumer([&] {
    const auto result =
        cpu_prefetch::queue::testing::QueuePhaseTestAccess::ring_dequeue(
            queue, reuse_observer);
    EXPECT_EQ(result.status, DequeueStatus::item);
    EXPECT_EQ(result.event, &events[0]);
  });
  while (!phase_reached.load(std::memory_order_acquire)) {
  }
  EXPECT_EQ(adapter.try_enqueue(event_pointer(&events[1])), EnqueueResult::full);
  resume.store(true, std::memory_order_release);
  consumer.join();
  EXPECT_EQ(adapter.try_enqueue(event_pointer(&events[1])), EnqueueResult::accepted);
  EXPECT_EQ(adapter.try_dequeue().event, &events[1]);
}

TEST(QueueProgress, LinkedSuspensionCannotPrematurelyRecycleAReachableNode) {
  const std::array<std::size_t, 3> order{2U, 0U, 1U};
  LinkedSpscQueue queue(QueueCapacity{2U}, kSyntheticCacheLine, kSyntheticPage, order);
  LinkedQueueAdapter adapter(queue);
  std::array<std::uint64_t, 3> events{};
  std::atomic<bool> phase_reached{false};
  std::atomic<bool> resume{false};

  struct ObtainObserver final {
    std::atomic<bool>& phase_reached;
    std::atomic<bool>& resume;
    void after_recycler_obtain() const noexcept {
      phase_reached.store(true, std::memory_order_release);
      while (!resume.load(std::memory_order_acquire)) {
      }
    }
  } obtain_observer{phase_reached, resume};

  std::thread producer([&] {
    EXPECT_EQ(cpu_prefetch::queue::testing::QueuePhaseTestAccess::linked_enqueue(
                  queue, event_pointer(&events[0]), obtain_observer),
              EnqueueResult::accepted);
  });
  while (!phase_reached.load(std::memory_order_acquire)) {
  }
  EXPECT_EQ(adapter.try_dequeue().status, DequeueStatus::empty);
  resume.store(true, std::memory_order_release);
  producer.join();

  phase_reached.store(false, std::memory_order_relaxed);
  resume.store(false, std::memory_order_relaxed);
  struct ReturnObserver final {
    std::atomic<bool>& phase_reached;
    std::atomic<bool>& resume;
    void before_recycler_return() const noexcept {
      phase_reached.store(true, std::memory_order_release);
      while (!resume.load(std::memory_order_acquire)) {
      }
    }
  } return_observer{phase_reached, resume};

  std::thread consumer([&] {
    const auto result =
        cpu_prefetch::queue::testing::QueuePhaseTestAccess::linked_dequeue(
            queue, return_observer);
    EXPECT_EQ(result.status, DequeueStatus::item);
    EXPECT_EQ(result.event, &events[0]);
  });
  while (!phase_reached.load(std::memory_order_acquire)) {
  }
  EXPECT_EQ(adapter.try_enqueue(event_pointer(&events[1])), EnqueueResult::accepted);
  EXPECT_EQ(adapter.try_enqueue(event_pointer(&events[2])), EnqueueResult::full);
  resume.store(true, std::memory_order_release);
  consumer.join();

  const auto next = adapter.try_dequeue();
  EXPECT_EQ(next.status, DequeueStatus::item);
  EXPECT_EQ(next.event, &events[1]);
  const auto audit = queue.audit_quiescent();
  EXPECT_TRUE(audit.chain_acyclic);
  EXPECT_TRUE(audit.tail_reachable);
  EXPECT_TRUE(audit.every_node_owned_once);
}

TEST(QueueLayout, RequiredPointerAtomicsAreLockFreeAndOwnershipIsSeparated) {
  RingSpscQueue ring(QueueCapacity{8U}, kSyntheticCacheLine);
  const auto ring_atomic = ring.atomic_lock_free_evidence();
  const auto ring_layout = ring.layout_evidence();
  EXPECT_EQ(ring_atomic.abi_pointer_width_bytes,
            ring_atomic.atomic_pointer_width_bytes);
  EXPECT_TRUE(ring_atomic.always_lock_free);
  EXPECT_TRUE(ring_atomic.runtime_lock_free);
  EXPECT_TRUE(ring_layout.bases_aligned);
  EXPECT_TRUE(ring_layout.ownership_lines_separated);

  const std::array<std::size_t, 9> order{5U, 1U, 8U, 3U, 0U, 7U, 4U, 2U, 6U};
  LinkedSpscQueue linked(QueueCapacity{8U}, kSyntheticCacheLine, kSyntheticPage, order);
  const auto linked_atomic = linked.atomic_lock_free_evidence();
  const auto linked_layout = linked.layout_evidence();
  EXPECT_EQ(linked_atomic.abi_pointer_width_bytes,
            linked_atomic.atomic_pointer_width_bytes);
  EXPECT_TRUE(linked_atomic.always_lock_free);
  EXPECT_TRUE(linked_atomic.runtime_lock_free);
  EXPECT_TRUE(linked_layout.bases_aligned);
  EXPECT_TRUE(linked_layout.ownership_lines_separated);
  EXPECT_EQ(linked.node_stride_bytes() % kSyntheticCacheLine.value, 0U);
  EXPECT_EQ(linked.node_arena_alignment_bytes(), kSyntheticPage.value);
  EXPECT_EQ(reinterpret_cast<std::uintptr_t>(linked.node_arena_base()) %
                kSyntheticPage.value,
            0U);
}

TEST(QueueSetup, InvalidCapacityLineSizeAndNodeOrdersFailBeforeOperations) {
  EXPECT_THROW((RingSpscQueue{QueueCapacity{0U}, kSyntheticCacheLine}),
               QueueSetupError);
  EXPECT_THROW((RingSpscQueue{QueueCapacity{4U}, CacheLineBytes{48U}}),
               QueueSetupError);
  EXPECT_THROW((RingSpscQueue{QueueCapacity{std::numeric_limits<std::size_t>::max()},
                              kSyntheticCacheLine}),
               QueueSetupError);

  const std::array<std::size_t, 3> too_short{0U, 1U, 2U};
  EXPECT_THROW((LinkedSpscQueue{QueueCapacity{3U}, kSyntheticCacheLine, kSyntheticPage,
                                too_short}),
               QueueSetupError);
  const std::array<std::size_t, 4> duplicate{0U, 1U, 1U, 3U};
  EXPECT_THROW((LinkedSpscQueue{QueueCapacity{3U}, kSyntheticCacheLine, kSyntheticPage,
                                duplicate}),
               QueueSetupError);
  const std::array<std::size_t, 4> out_of_range{0U, 1U, 2U, 4U};
  EXPECT_THROW((LinkedSpscQueue{QueueCapacity{3U}, kSyntheticCacheLine, kSyntheticPage,
                                out_of_range}),
               QueueSetupError);
  const std::array<std::size_t, 4> valid{0U, 1U, 2U, 3U};
  EXPECT_THROW((LinkedSpscQueue{QueueCapacity{3U}, kSyntheticCacheLine,
                                ArenaAlignmentBytes{32U}, valid}),
               QueueSetupError);
}

TEST(QueueAudit, DuplicateOmissionCorruptionAndReorderingAreDetected) {
  std::array<std::uint64_t, 4> records{};
  const std::vector<const void*> expected{&records[0], &records[1], &records[2]};
  EXPECT_EQ(audit_sequence(expected, expected), SequenceFault::none);
  EXPECT_EQ(audit_sequence(expected, {&records[0], &records[1]}),
            SequenceFault::omission);
  EXPECT_EQ(
      audit_sequence(expected, {&records[0], &records[1], &records[2], &records[2]}),
      SequenceFault::duplicate);
  EXPECT_EQ(audit_sequence(expected, {&records[0], &records[2], &records[1]}),
            SequenceFault::corruption_or_reorder);
  EXPECT_EQ(audit_sequence(expected, {&records[0], &records[1], &records[3]}),
            SequenceFault::corruption_or_reorder);
}

static_assert(noexcept(
    std::declval<RingQueueAdapter&>().try_enqueue(std::declval<EventPointer>())));
static_assert(noexcept(std::declval<RingQueueAdapter&>().try_dequeue()));
static_assert(noexcept(
    std::declval<LinkedQueueAdapter&>().try_enqueue(std::declval<EventPointer>())));
static_assert(noexcept(std::declval<LinkedQueueAdapter&>().try_dequeue()));
static_assert(!std::is_polymorphic_v<RingQueueAdapter>);
static_assert(!std::is_polymorphic_v<LinkedQueueAdapter>);

} // namespace
