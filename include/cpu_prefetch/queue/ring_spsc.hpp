#ifndef CPU_PREFETCH_QUEUE_RING_SPSC_HPP
#define CPU_PREFETCH_QUEUE_RING_SPSC_HPP

#include "cpu_prefetch/queue/common.hpp"

#include <atomic>
#include <cstddef>

namespace cpu_prefetch::queue {

struct RingQuiescentAudit final {
  std::size_t occupied_slots;
  std::size_t producer_position;
  std::size_t consumer_position;
  bool positions_in_range;
};

class RingSpscQueue final {
public:
  RingSpscQueue(QueueCapacity capacity, CacheLineBytes cache_line_bytes);
  ~RingSpscQueue();

  RingSpscQueue(const RingSpscQueue&) = delete;
  RingSpscQueue& operator=(const RingSpscQueue&) = delete;
  RingSpscQueue(RingSpscQueue&&) = delete;
  RingSpscQueue& operator=(RingSpscQueue&&) = delete;

  [[nodiscard]] EnqueueResult try_enqueue(EventPointer event) noexcept {
    struct NoopObserver final {
      void before_slot_publication() const noexcept {}
    } observer;
    return try_enqueue_observed(event, observer);
  }

  [[nodiscard]] DequeueResult try_dequeue() noexcept {
    struct NoopObserver final {
      void before_slot_reuse_release() const noexcept {}
    } observer;
    return try_dequeue_observed(observer);
  }

  [[nodiscard]] std::size_t capacity() const noexcept { return capacity_; }
  [[nodiscard]] AtomicLockFreeEvidence atomic_lock_free_evidence() const noexcept;
  [[nodiscard]] LayoutEvidence layout_evidence() const noexcept;
  [[nodiscard]] RingQuiescentAudit audit_quiescent() const noexcept;
  [[nodiscard]] const void*
  producer_slot_target(std::size_t distance_slots) const noexcept {
    return &slots_[position_at_distance(producer_->position,
                                        SlotOffset{distance_slots})]
                .value;
  }
  [[nodiscard]] const void*
  consumer_slot_target(std::size_t distance_slots) const noexcept {
    return &slots_[position_at_distance(consumer_->position,
                                        SlotOffset{distance_slots})]
                .value;
  }

private:
  friend struct testing::QueuePhaseTestAccess;

  template <typename Observer>
  [[nodiscard]] EnqueueResult try_enqueue_observed(EventPointer event,
                                                   Observer& observer) noexcept {
    static_assert(noexcept(observer.before_slot_publication()));
    const auto position = producer_->position;
    auto& slot = slots_[position].value;
    if (slot.load(std::memory_order_acquire) != nullptr) {
      return EnqueueResult::full;
    }

    observer.before_slot_publication();
    slot.store(event.get(), std::memory_order_release);
    producer_->position = next_position(position);
    return EnqueueResult::accepted;
  }

  template <typename Observer>
  [[nodiscard]] DequeueResult try_dequeue_observed(Observer& observer) noexcept {
    static_assert(noexcept(observer.before_slot_reuse_release()));
    const auto position = consumer_->position;
    auto& slot = slots_[position].value;
    const auto* event = slot.load(std::memory_order_acquire);
    if (event == nullptr) {
      return {DequeueStatus::empty, nullptr};
    }

    observer.before_slot_reuse_release();
    slot.store(nullptr, std::memory_order_release);
    consumer_->position = next_position(position);
    return {DequeueStatus::item, event};
  }
  struct Slot final {
    std::atomic<const void*> value{nullptr};
  };
  static_assert(sizeof(Slot) == sizeof(const void*));

  struct CursorState final {
    std::size_t position{0};
  };

  struct SlotOffset final {
    std::size_t value;
  };

  [[nodiscard]] std::size_t next_position(std::size_t position) const noexcept {
    const auto next = position + 1U;
    return next == capacity_ ? 0U : next;
  }

  [[nodiscard]] std::size_t position_at_distance(std::size_t position,
                                                 SlotOffset distance) const noexcept {
    const auto reduced = distance.value % capacity_;
    if (reduced == 0U) {
      return position;
    }
    const auto until_wrap = capacity_ - position;
    return reduced < until_wrap ? position + reduced : reduced - until_wrap;
  }

  std::size_t capacity_{0};
  std::size_t cache_line_bytes_{0};
  detail::AlignedBlock slot_storage_;
  detail::AlignedBlock cursor_storage_;
  Slot* slots_{nullptr};
  CursorState* producer_{nullptr};
  CursorState* consumer_{nullptr};
};

} // namespace cpu_prefetch::queue

#endif // CPU_PREFETCH_QUEUE_RING_SPSC_HPP
