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

  template <typename BoundaryObserver>
  [[nodiscard]] BoundaryEnqueueResult
  try_enqueue_with_boundary_observer(EventPointer event,
                                     BoundaryObserver& observer) noexcept {
    static_assert(noexcept(observer.before_enqueue_publication()));
    struct NoopPhaseObserver final {
      void before_slot_publication() const noexcept {}
    } phase_observer;
    return try_enqueue_observed(event, phase_observer, observer);
  }

  template <typename BoundaryObserver>
  [[nodiscard]] BoundaryDequeueResult
  try_dequeue_with_boundary_observer(BoundaryObserver& observer) noexcept {
    static_assert(noexcept(observer.after_dequeue_observation()));
    struct NoopPhaseObserver final {
      void before_slot_reuse_release() const noexcept {}
    } phase_observer;
    return try_dequeue_observed(phase_observer, observer);
  }

  // Calibration-only seam around the exact acquire load which determines
  // whether this operation can advance. The observer must not block, throw,
  // allocate, or alter the queue's release/acquire algorithm.
  template <typename DemandObserver>
  [[nodiscard]] EnqueueResult
  try_enqueue_with_slot_demand_observer(EventPointer event,
                                        DemandObserver& observer) noexcept {
    static_assert(noexcept(observer.before_slot_acquire()));
    static_assert(noexcept(observer.after_slot_acquire()));
    struct NoopPhaseObserver final {
      void before_slot_publication() const noexcept {}
    } phase_observer;
    struct NoopBoundaryObserver final {
      [[nodiscard]] bool before_enqueue_publication() const noexcept { return true; }
    } boundary_observer;
    return try_enqueue_observed(event, phase_observer, boundary_observer, observer)
        .result;
  }

  template <typename DemandObserver>
  [[nodiscard]] DequeueResult
  try_dequeue_with_slot_demand_observer(DemandObserver& observer) noexcept {
    static_assert(noexcept(observer.before_slot_acquire()));
    static_assert(noexcept(observer.after_slot_acquire()));
    struct NoopPhaseObserver final {
      void before_slot_reuse_release() const noexcept {}
    } phase_observer;
    struct NoopBoundaryObserver final {
      [[nodiscard]] bool after_dequeue_observation() const noexcept { return true; }
    } boundary_observer;
    return try_dequeue_observed(phase_observer, boundary_observer, observer).result;
  }

  [[nodiscard]] std::size_t capacity() const noexcept { return capacity_; }
  [[nodiscard]] AtomicLockFreeEvidence atomic_lock_free_evidence() const noexcept;
  [[nodiscard]] LayoutEvidence layout_evidence() const noexcept;
  [[nodiscard]] RingQuiescentAudit audit_quiescent() const noexcept;
  // Controller-only warm-up reset.  It is valid only after a complete drain;
  // no allocation, remapping, or queue operation may overlap this call.
  [[nodiscard]] bool reset_quiescent() noexcept;
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
    struct NoopDemandObserver final {
      void before_slot_acquire() const noexcept {}
      void after_slot_acquire() const noexcept {}
    } demand_observer;
    return try_enqueue_observed(event, phase_observer, boundary_observer,
                                demand_observer);
  }

  template <typename PhaseObserver, typename BoundaryObserver, typename DemandObserver>
  [[nodiscard]] BoundaryEnqueueResult
  try_enqueue_observed(EventPointer event, PhaseObserver& phase_observer,
                       BoundaryObserver& boundary_observer,
                       DemandObserver& demand_observer) noexcept {
    static_assert(noexcept(phase_observer.before_slot_publication()));
    static_assert(noexcept(boundary_observer.before_enqueue_publication()));
    static_assert(noexcept(demand_observer.before_slot_acquire()));
    static_assert(noexcept(demand_observer.after_slot_acquire()));
    const auto position = producer_->position;
    auto& slot = slots_[position].value;
    demand_observer.before_slot_acquire();
    const auto* observed = slot.load(std::memory_order_acquire);
    demand_observer.after_slot_acquire();
    if (observed != nullptr) {
      return {BoundaryCaptureStatus::complete, EnqueueResult::full};
    }

    phase_observer.before_slot_publication();
    if (!boundary_observer.before_enqueue_publication()) {
      return {BoundaryCaptureStatus::capture_failed, EnqueueResult::full};
    }
    slot.store(event.get(), std::memory_order_release);
    producer_->position = next_position(position);
    return {BoundaryCaptureStatus::complete, EnqueueResult::accepted};
  }

  template <typename Observer>
  [[nodiscard]] DequeueResult try_dequeue_observed(Observer& observer) noexcept {
    static_assert(noexcept(observer.before_slot_reuse_release()));
    struct NoopBoundaryObserver final {
      [[nodiscard]] bool after_dequeue_observation() const noexcept { return true; }
    } boundary_observer;
    const auto result = try_dequeue_observed(observer, boundary_observer);
    return result.result;
  }

  template <typename PhaseObserver, typename BoundaryObserver>
  [[nodiscard]] BoundaryDequeueResult
  try_dequeue_observed(PhaseObserver& phase_observer,
                       BoundaryObserver& boundary_observer) noexcept {
    struct NoopDemandObserver final {
      void before_slot_acquire() const noexcept {}
      void after_slot_acquire() const noexcept {}
    } demand_observer;
    return try_dequeue_observed(phase_observer, boundary_observer, demand_observer);
  }

  template <typename PhaseObserver, typename BoundaryObserver, typename DemandObserver>
  [[nodiscard]] BoundaryDequeueResult
  try_dequeue_observed(PhaseObserver& phase_observer,
                       BoundaryObserver& boundary_observer,
                       DemandObserver& demand_observer) noexcept {
    static_assert(noexcept(phase_observer.before_slot_reuse_release()));
    static_assert(noexcept(boundary_observer.after_dequeue_observation()));
    static_assert(noexcept(demand_observer.before_slot_acquire()));
    static_assert(noexcept(demand_observer.after_slot_acquire()));
    const auto position = consumer_->position;
    auto& slot = slots_[position].value;
    demand_observer.before_slot_acquire();
    const auto* event = slot.load(std::memory_order_acquire);
    demand_observer.after_slot_acquire();
    if (event == nullptr) {
      return {BoundaryCaptureStatus::complete,
              DequeueResult{DequeueStatus::empty, nullptr}};
    }

    if (!boundary_observer.after_dequeue_observation()) {
      return {BoundaryCaptureStatus::capture_failed,
              DequeueResult{DequeueStatus::empty, nullptr}};
    }
    phase_observer.before_slot_reuse_release();
    slot.store(nullptr, std::memory_order_release);
    consumer_->position = next_position(position);
    return {BoundaryCaptureStatus::complete, DequeueResult{DequeueStatus::item, event}};
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
