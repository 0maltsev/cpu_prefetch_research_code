#ifndef CPU_PREFETCH_WORKLOAD_PACKAGES_HPP
#define CPU_PREFETCH_WORKLOAD_PACKAGES_HPP

#include "cpu_prefetch/protocol/model.hpp"
#include "cpu_prefetch/queue/linked_spsc.hpp"
#include "cpu_prefetch/queue/ring_spsc.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <array>
#include <cstddef>
#include <limits>
#include <string>
#include <utility>

namespace cpu_prefetch::workload {

class CalibratedRingDistance;
struct RingGeometry;

class RingDistance final {
public:
  [[nodiscard]] std::size_t slots() const noexcept { return slots_; }
  [[nodiscard]] std::size_t cache_lines() const noexcept { return cache_lines_; }

private:
  friend RingDistance ring_one_line_distance(const RingGeometry&);
  friend CalibratedRingDistance
  resolve_calibrated_ring_distance(const RingGeometry&, std::size_t, std::string);
  friend class CalibratedRingDistance;
  explicit RingDistance(std::array<std::size_t, 2> values) noexcept
      : slots_(values[0]), cache_lines_(values[1]) {}

  std::size_t slots_;
  std::size_t cache_lines_;
};

class CalibratedRingDistance final {
public:
  [[nodiscard]] const RingDistance& distance() const noexcept { return distance_; }
  [[nodiscard]] std::string_view calibration_evidence_id() const noexcept {
    return calibration_evidence_id_;
  }

private:
  friend CalibratedRingDistance
  resolve_calibrated_ring_distance(const RingGeometry&, std::size_t, std::string);
  CalibratedRingDistance(RingDistance distance, std::string evidence_id)
      : distance_(distance), calibration_evidence_id_(std::move(evidence_id)) {}

  RingDistance distance_;
  std::string calibration_evidence_id_;
};

struct RingGeometry final {
  std::size_t capacity;
  std::size_t cache_line_bytes;
  std::size_t slot_bytes;
};

[[nodiscard]] RingDistance ring_one_line_distance(const RingGeometry& geometry);
[[nodiscard]] CalibratedRingDistance
resolve_calibrated_ring_distance(const RingGeometry& geometry,
                                 std::size_t calibrated_cache_lines,
                                 std::string calibration_evidence_id);

class R0Package final {
public:
  static constexpr protocol::QueuePackage package = protocol::QueuePackage::r0;

  explicit R0Package(queue::RingSpscQueue& queue) noexcept : queue_(queue) {}
  [[nodiscard]] queue::EnqueueResult try_enqueue(queue::EventPointer event) noexcept {
    return queue_.try_enqueue(event);
  }
  [[nodiscard]] queue::DequeueResult try_dequeue() noexcept {
    return queue_.try_dequeue();
  }
  template <typename BoundaryObserver>
  [[nodiscard]] queue::BoundaryEnqueueResult
  try_enqueue_with_boundary_observer(queue::EventPointer event,
                                     BoundaryObserver& observer) noexcept {
    return queue_.try_enqueue_with_boundary_observer(event, observer);
  }
  template <typename BoundaryObserver>
  [[nodiscard]] queue::BoundaryDequeueResult
  try_dequeue_with_boundary_observer(BoundaryObserver& observer) noexcept {
    return queue_.try_dequeue_with_boundary_observer(observer);
  }

private:
  queue::RingSpscQueue& queue_;
};

template <typename PrefetchEmitter> class R1Package final {
public:
  static constexpr protocol::QueuePackage package = protocol::QueuePackage::r1;

  R1Package(queue::RingSpscQueue& queue, PrefetchEmitter& emitter,
            RingDistance distance) noexcept
      : queue_(queue), emitter_(emitter), distance_(distance) {}

  [[nodiscard]] queue::EnqueueResult try_enqueue(queue::EventPointer event) noexcept {
    static_assert(noexcept(std::declval<PrefetchEmitter&>().ring_producer_write(
        static_cast<const void*>(nullptr))));
    emitter_.ring_producer_write(queue_.producer_slot_target(distance_.slots()));
    return queue_.try_enqueue(event);
  }
  [[nodiscard]] queue::DequeueResult try_dequeue() noexcept {
    static_assert(noexcept(std::declval<PrefetchEmitter&>().ring_consumer_read(
        static_cast<const void*>(nullptr))));
    emitter_.ring_consumer_read(queue_.consumer_slot_target(distance_.slots()));
    return queue_.try_dequeue();
  }
  template <typename BoundaryObserver>
  [[nodiscard]] queue::BoundaryEnqueueResult
  try_enqueue_with_boundary_observer(queue::EventPointer event,
                                     BoundaryObserver& observer) noexcept {
    static_assert(noexcept(std::declval<PrefetchEmitter&>().ring_producer_write(
        static_cast<const void*>(nullptr))));
    emitter_.ring_producer_write(queue_.producer_slot_target(distance_.slots()));
    return queue_.try_enqueue_with_boundary_observer(event, observer);
  }
  template <typename BoundaryObserver>
  [[nodiscard]] queue::BoundaryDequeueResult
  try_dequeue_with_boundary_observer(BoundaryObserver& observer) noexcept {
    static_assert(noexcept(std::declval<PrefetchEmitter&>().ring_consumer_read(
        static_cast<const void*>(nullptr))));
    emitter_.ring_consumer_read(queue_.consumer_slot_target(distance_.slots()));
    return queue_.try_dequeue_with_boundary_observer(observer);
  }

private:
  queue::RingSpscQueue& queue_;
  PrefetchEmitter& emitter_;
  RingDistance distance_;
};

template <typename PrefetchEmitter> class R2Package final {
public:
  static constexpr protocol::QueuePackage package = protocol::QueuePackage::r2;

  R2Package(queue::RingSpscQueue& queue, PrefetchEmitter& emitter,
            const CalibratedRingDistance& calibrated_distance) noexcept
      : queue_(queue), emitter_(emitter), distance_(calibrated_distance.distance()) {}

  [[nodiscard]] queue::EnqueueResult try_enqueue(queue::EventPointer event) noexcept {
    static_assert(noexcept(std::declval<PrefetchEmitter&>().ring_producer_write(
        static_cast<const void*>(nullptr))));
    emitter_.ring_producer_write(queue_.producer_slot_target(distance_.slots()));
    return queue_.try_enqueue(event);
  }
  [[nodiscard]] queue::DequeueResult try_dequeue() noexcept {
    static_assert(noexcept(std::declval<PrefetchEmitter&>().ring_consumer_read(
        static_cast<const void*>(nullptr))));
    emitter_.ring_consumer_read(queue_.consumer_slot_target(distance_.slots()));
    return queue_.try_dequeue();
  }
  template <typename BoundaryObserver>
  [[nodiscard]] queue::BoundaryEnqueueResult
  try_enqueue_with_boundary_observer(queue::EventPointer event,
                                     BoundaryObserver& observer) noexcept {
    static_assert(noexcept(std::declval<PrefetchEmitter&>().ring_producer_write(
        static_cast<const void*>(nullptr))));
    emitter_.ring_producer_write(queue_.producer_slot_target(distance_.slots()));
    return queue_.try_enqueue_with_boundary_observer(event, observer);
  }
  template <typename BoundaryObserver>
  [[nodiscard]] queue::BoundaryDequeueResult
  try_dequeue_with_boundary_observer(BoundaryObserver& observer) noexcept {
    static_assert(noexcept(std::declval<PrefetchEmitter&>().ring_consumer_read(
        static_cast<const void*>(nullptr))));
    emitter_.ring_consumer_read(queue_.consumer_slot_target(distance_.slots()));
    return queue_.try_dequeue_with_boundary_observer(observer);
  }

private:
  queue::RingSpscQueue& queue_;
  PrefetchEmitter& emitter_;
  RingDistance distance_;
};

class L0Package final {
public:
  static constexpr protocol::QueuePackage package = protocol::QueuePackage::l0;

  explicit L0Package(queue::LinkedSpscQueue& queue) noexcept : queue_(queue) {}
  [[nodiscard]] queue::EnqueueResult try_enqueue(queue::EventPointer event) noexcept {
    return queue_.try_enqueue(event);
  }
  [[nodiscard]] queue::DequeueResult try_dequeue() noexcept {
    return queue_.try_dequeue();
  }
  template <typename BoundaryObserver>
  [[nodiscard]] queue::BoundaryEnqueueResult
  try_enqueue_with_boundary_observer(queue::EventPointer event,
                                     BoundaryObserver& observer) noexcept {
    return queue_.try_enqueue_with_boundary_observer(event, observer);
  }
  template <typename BoundaryObserver>
  [[nodiscard]] queue::BoundaryDequeueResult
  try_dequeue_with_boundary_observer(BoundaryObserver& observer) noexcept {
    return queue_.try_dequeue_with_boundary_observer(observer);
  }

private:
  queue::LinkedSpscQueue& queue_;
};

template <typename PrefetchEmitter> class L1Package final {
public:
  static constexpr protocol::QueuePackage package = protocol::QueuePackage::l1;

  L1Package(queue::LinkedSpscQueue& queue, PrefetchEmitter& emitter) noexcept
      : queue_(queue), emitter_(emitter) {}
  [[nodiscard]] queue::EnqueueResult try_enqueue(queue::EventPointer event) noexcept {
    return queue_.try_enqueue(event);
  }
  [[nodiscard]] queue::DequeueResult try_dequeue() noexcept {
    return queue_.try_dequeue_with_successor_prefetch(emitter_);
  }
  template <typename BoundaryObserver>
  [[nodiscard]] queue::BoundaryEnqueueResult
  try_enqueue_with_boundary_observer(queue::EventPointer event,
                                     BoundaryObserver& observer) noexcept {
    return queue_.try_enqueue_with_boundary_observer(event, observer);
  }
  template <typename BoundaryObserver>
  [[nodiscard]] queue::BoundaryDequeueResult
  try_dequeue_with_boundary_observer(BoundaryObserver& observer) noexcept {
    return queue_.try_dequeue_with_boundary_observer(observer, emitter_);
  }

private:
  queue::LinkedSpscQueue& queue_;
  PrefetchEmitter& emitter_;
};

static_assert(R0Package::package != L0Package::package);

} // namespace cpu_prefetch::workload

#endif // CPU_PREFETCH_WORKLOAD_PACKAGES_HPP
