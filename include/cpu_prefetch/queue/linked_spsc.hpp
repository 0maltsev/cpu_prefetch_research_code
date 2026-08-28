#ifndef CPU_PREFETCH_QUEUE_LINKED_SPSC_HPP
#define CPU_PREFETCH_QUEUE_LINKED_SPSC_HPP

#include "cpu_prefetch/queue/common.hpp"

#include <atomic>
#include <cstddef>
#include <span>
#include <vector>

namespace cpu_prefetch::queue {

struct LinkedQuiescentAudit final {
  std::size_t reachable_nodes;
  std::size_t queued_events;
  std::size_t recycler_nodes;
  std::vector<std::size_t> reachable_order;
  std::vector<std::size_t> recycler_order;
  bool chain_acyclic;
  bool tail_reachable;
  bool every_node_owned_once;
  bool recycler_fifo_shape;
  bool positions_in_range;
};

class LinkedSpscQueue final {
public:
  LinkedSpscQueue(QueueCapacity capacity, CacheLineBytes cache_line_bytes,
                  ArenaAlignmentBytes arena_alignment_bytes,
                  std::span<const std::size_t> node_order);
  ~LinkedSpscQueue();

  LinkedSpscQueue(const LinkedSpscQueue&) = delete;
  LinkedSpscQueue& operator=(const LinkedSpscQueue&) = delete;
  LinkedSpscQueue(LinkedSpscQueue&&) = delete;
  LinkedSpscQueue& operator=(LinkedSpscQueue&&) = delete;

  [[nodiscard]] EnqueueResult try_enqueue(EventPointer event) noexcept {
    struct NoopObserver final {
      void after_recycler_obtain() const noexcept {}
    } observer;
    return try_enqueue_observed(event, observer);
  }

  [[nodiscard]] DequeueResult try_dequeue() noexcept {
    struct NoopObserver final {
      void before_recycler_return() const noexcept {}
    } observer;
    struct NoopSuccessorPrefetch final {
      void successor_header(const void*) const noexcept {}
    } prefetch;
    return try_dequeue_observed(observer, prefetch);
  }

  template <typename SuccessorPrefetch>
  [[nodiscard]] DequeueResult
  try_dequeue_with_successor_prefetch(SuccessorPrefetch& prefetch) noexcept {
    static_assert(
        noexcept(prefetch.successor_header(static_cast<const void*>(nullptr))));
    struct NoopObserver final {
      void before_recycler_return() const noexcept {}
    } observer;
    return try_dequeue_observed(observer, prefetch);
  }

  template <typename BoundaryObserver>
  [[nodiscard]] BoundaryEnqueueResult
  try_enqueue_with_boundary_observer(EventPointer event,
                                     BoundaryObserver& observer) noexcept {
    static_assert(noexcept(observer.before_enqueue_publication()));
    struct NoopPhaseObserver final {
      void after_recycler_obtain() const noexcept {}
    } phase_observer;
    return try_enqueue_observed(event, phase_observer, observer);
  }

  template <typename BoundaryObserver>
  [[nodiscard]] BoundaryDequeueResult
  try_dequeue_with_boundary_observer(BoundaryObserver& observer) noexcept {
    static_assert(noexcept(observer.after_dequeue_observation()));
    struct NoopPhaseObserver final {
      void before_recycler_return() const noexcept {}
    } phase_observer;
    struct NoopSuccessorPrefetch final {
      void successor_header(const void*) const noexcept {}
    } prefetch;
    return try_dequeue_observed(phase_observer, observer, prefetch);
  }

  template <typename BoundaryObserver, typename SuccessorPrefetch>
  [[nodiscard]] BoundaryDequeueResult
  try_dequeue_with_boundary_observer(BoundaryObserver& observer,
                                     SuccessorPrefetch& prefetch) noexcept {
    static_assert(noexcept(observer.after_dequeue_observation()));
    static_assert(
        noexcept(prefetch.successor_header(static_cast<const void*>(nullptr))));
    struct NoopPhaseObserver final {
      void before_recycler_return() const noexcept {}
    } phase_observer;
    return try_dequeue_observed(phase_observer, observer, prefetch);
  }

  [[nodiscard]] std::size_t capacity() const noexcept { return capacity_; }
  [[nodiscard]] std::size_t node_stride_bytes() const noexcept {
    return node_stride_bytes_;
  }
  [[nodiscard]] std::size_t node_arena_alignment_bytes() const noexcept {
    return node_arena_alignment_bytes_;
  }
  [[nodiscard]] const void* node_arena_base() const noexcept {
    return node_storage_.data();
  }
  [[nodiscard]] AtomicLockFreeEvidence atomic_lock_free_evidence() const noexcept;
  [[nodiscard]] LayoutEvidence layout_evidence() const noexcept;
  [[nodiscard]] LinkedQuiescentAudit audit_quiescent() const;
  // Controller-only warm-up reset.  The original permutation is restored in
  // place after a complete drain; no allocation or remapping occurs.
  [[nodiscard]] bool reset_quiescent() noexcept;

private:
  friend struct testing::QueuePhaseTestAccess;

  template <typename Observer>
  [[nodiscard]] EnqueueResult try_enqueue_observed(EventPointer event,
                                                   Observer& observer) noexcept {
    static_assert(noexcept(observer.after_recycler_obtain()));
    struct NoopBoundaryObserver final {
      [[nodiscard]] bool before_enqueue_publication() const noexcept { return true; }
    } boundary_observer;
    const auto result = try_enqueue_observed(event, observer, boundary_observer);
    return result.result;
  }

  template <typename PhaseObserver, typename BoundaryObserver>
  [[nodiscard]] BoundaryEnqueueResult
  try_enqueue_observed(EventPointer event, PhaseObserver& phase_observer,
                       BoundaryObserver& boundary_observer) noexcept {
    static_assert(noexcept(phase_observer.after_recycler_obtain()));
    static_assert(noexcept(boundary_observer.before_enqueue_publication()));
    const auto recycler_position = recycler_consumer_->position;
    auto& recycler_slot = recycler_slots_[recycler_position].value;
    auto* node = recycler_slot.load(std::memory_order_acquire);
    if (node == nullptr) {
      return {BoundaryCaptureStatus::complete, EnqueueResult::full};
    }

    recycler_slot.store(nullptr, std::memory_order_release);
    recycler_consumer_->position = next_position(recycler_position);

    phase_observer.after_recycler_obtain();
    node->event = event.get();
    node->next.store(nullptr, std::memory_order_relaxed);
    if (!boundary_observer.before_enqueue_publication()) {
      return {BoundaryCaptureStatus::capture_failed, EnqueueResult::full};
    }
    producer_->tail->next.store(node, std::memory_order_release);
    producer_->tail = node;
    return {BoundaryCaptureStatus::complete, EnqueueResult::accepted};
  }

  template <typename Observer, typename SuccessorPrefetch>
  [[nodiscard]] DequeueResult
  try_dequeue_observed(Observer& observer, SuccessorPrefetch& prefetch) noexcept {
    static_assert(noexcept(observer.before_recycler_return()));
    static_assert(
        noexcept(prefetch.successor_header(static_cast<const void*>(nullptr))));
    struct NoopBoundaryObserver final {
      [[nodiscard]] bool after_dequeue_observation() const noexcept { return true; }
    } boundary_observer;
    const auto result = try_dequeue_observed(observer, boundary_observer, prefetch);
    return result.result;
  }

  template <typename PhaseObserver, typename BoundaryObserver,
            typename SuccessorPrefetch>
  [[nodiscard]] BoundaryDequeueResult
  try_dequeue_observed(PhaseObserver& phase_observer,
                       BoundaryObserver& boundary_observer,
                       SuccessorPrefetch& prefetch) noexcept {
    static_assert(noexcept(phase_observer.before_recycler_return()));
    static_assert(noexcept(boundary_observer.after_dequeue_observation()));
    static_assert(
        noexcept(prefetch.successor_header(static_cast<const void*>(nullptr))));
    auto* old_sentinel = consumer_->head;
    auto* successor = old_sentinel->next.load(std::memory_order_acquire);
    if (successor == nullptr) {
      return {BoundaryCaptureStatus::complete,
              DequeueResult{DequeueStatus::empty, nullptr}};
    }
    if (!boundary_observer.after_dequeue_observation()) {
      return {BoundaryCaptureStatus::capture_failed,
              DequeueResult{DequeueStatus::empty, nullptr}};
    }

    prefetch.successor_header(successor);

    const auto recycler_position = recycler_producer_->position;
    auto& recycler_slot = recycler_slots_[recycler_position].value;
    if (recycler_slot.load(std::memory_order_acquire) != nullptr) {
      return {BoundaryCaptureStatus::complete,
              DequeueResult{DequeueStatus::recycler_invariant_failure, nullptr}};
    }

    const auto* event = successor->event;
    phase_observer.before_recycler_return();
    consumer_->head = successor;
    recycler_slot.store(old_sentinel, std::memory_order_release);
    recycler_producer_->position = next_position(recycler_position);
    return {BoundaryCaptureStatus::complete, DequeueResult{DequeueStatus::item, event}};
  }
  struct Node final {
    std::atomic<Node*> next{nullptr};
    const void* event{nullptr};
    std::size_t arena_index{0};
  };
  static_assert(sizeof(std::atomic<Node*>) == sizeof(Node*));
  static_assert(std::atomic<Node*>::is_always_lock_free);

  struct RecyclerSlot final {
    std::atomic<Node*> value{nullptr};
  };
  static_assert(sizeof(RecyclerSlot) == sizeof(Node*));

  struct ProducerState final {
    Node* tail{nullptr};
  };

  struct ConsumerState final {
    Node* head{nullptr};
  };

  struct RecyclerPosition final {
    std::size_t position{0};
  };

  [[nodiscard]] std::size_t next_position(std::size_t position) const noexcept {
    const auto next = position + 1U;
    return next == capacity_ ? 0U : next;
  }
  [[nodiscard]] Node* node_at(std::size_t index) noexcept;
  [[nodiscard]] const Node* node_at(std::size_t index) const noexcept;
  [[nodiscard]] std::optional<std::size_t> index_of(const Node* node) const noexcept;

  std::size_t capacity_{0};
  std::size_t cache_line_bytes_{0};
  std::size_t node_stride_bytes_{0};
  std::size_t node_arena_alignment_bytes_{0};
  detail::AlignedBlock node_storage_;
  detail::AlignedBlock recycler_storage_;
  detail::AlignedBlock ownership_storage_;
  RecyclerSlot* recycler_slots_{nullptr};
  ProducerState* producer_{nullptr};
  ConsumerState* consumer_{nullptr};
  RecyclerPosition* recycler_producer_{nullptr};
  RecyclerPosition* recycler_consumer_{nullptr};
  std::vector<std::size_t> initial_node_order_;
};

} // namespace cpu_prefetch::queue

#endif // CPU_PREFETCH_QUEUE_LINKED_SPSC_HPP
