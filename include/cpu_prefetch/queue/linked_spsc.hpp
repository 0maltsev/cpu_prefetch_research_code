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
    return try_dequeue_observed(observer);
  }

  [[nodiscard]] std::size_t capacity() const noexcept { return capacity_; }
  [[nodiscard]] std::size_t node_stride_bytes() const noexcept {
    return node_stride_bytes_;
  }
  [[nodiscard]] AtomicLockFreeEvidence atomic_lock_free_evidence() const noexcept;
  [[nodiscard]] LayoutEvidence layout_evidence() const noexcept;
  [[nodiscard]] LinkedQuiescentAudit audit_quiescent() const;

private:
  friend struct testing::QueuePhaseTestAccess;

  template <typename Observer>
  [[nodiscard]] EnqueueResult try_enqueue_observed(EventPointer event,
                                                   Observer& observer) noexcept {
    static_assert(noexcept(observer.after_recycler_obtain()));
    const auto recycler_position = recycler_consumer_->position;
    auto& recycler_slot = recycler_slots_[recycler_position].value;
    auto* node = recycler_slot.load(std::memory_order_acquire);
    if (node == nullptr) {
      return EnqueueResult::full;
    }

    recycler_slot.store(nullptr, std::memory_order_release);
    recycler_consumer_->position = next_position(recycler_position);

    observer.after_recycler_obtain();
    node->event = event.get();
    node->next.store(nullptr, std::memory_order_relaxed);
    producer_->tail->next.store(node, std::memory_order_release);
    producer_->tail = node;
    return EnqueueResult::accepted;
  }

  template <typename Observer>
  [[nodiscard]] DequeueResult try_dequeue_observed(Observer& observer) noexcept {
    static_assert(noexcept(observer.before_recycler_return()));
    auto* old_sentinel = consumer_->head;
    auto* successor = old_sentinel->next.load(std::memory_order_acquire);
    if (successor == nullptr) {
      return {DequeueStatus::empty, nullptr};
    }

    const auto recycler_position = recycler_producer_->position;
    auto& recycler_slot = recycler_slots_[recycler_position].value;
    if (recycler_slot.load(std::memory_order_acquire) != nullptr) {
      return {DequeueStatus::recycler_invariant_failure, nullptr};
    }

    const auto* event = successor->event;
    observer.before_recycler_return();
    consumer_->head = successor;
    recycler_slot.store(old_sentinel, std::memory_order_release);
    recycler_producer_->position = next_position(recycler_position);
    return {DequeueStatus::item, event};
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
  detail::AlignedBlock node_storage_;
  detail::AlignedBlock recycler_storage_;
  detail::AlignedBlock ownership_storage_;
  RecyclerSlot* recycler_slots_{nullptr};
  ProducerState* producer_{nullptr};
  ConsumerState* consumer_{nullptr};
  RecyclerPosition* recycler_producer_{nullptr};
  RecyclerPosition* recycler_consumer_{nullptr};
};

} // namespace cpu_prefetch::queue

#endif // CPU_PREFETCH_QUEUE_LINKED_SPSC_HPP
