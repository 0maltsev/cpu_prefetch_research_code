#ifndef CPU_PREFETCH_QUEUE_ADAPTERS_HPP
#define CPU_PREFETCH_QUEUE_ADAPTERS_HPP

#include "cpu_prefetch/queue/linked_spsc.hpp"
#include "cpu_prefetch/queue/ring_spsc.hpp"

#include <cstdint>

namespace cpu_prefetch::queue {

enum class QueueFamily : std::uint8_t {
  ring_spsc,
  linked_spsc_with_recycler,
};

class RingQueueAdapter final {
public:
  static constexpr QueueFamily family = QueueFamily::ring_spsc;

  explicit RingQueueAdapter(RingSpscQueue& queue) noexcept : queue_(queue) {}

  [[nodiscard]] EnqueueResult try_enqueue(EventPointer event) noexcept {
    return queue_.try_enqueue(event);
  }
  [[nodiscard]] DequeueResult try_dequeue() noexcept { return queue_.try_dequeue(); }

  [[nodiscard]] RingSpscQueue& ring_queue() noexcept { return queue_; }

private:
  RingSpscQueue& queue_;
};

class LinkedQueueAdapter final {
public:
  static constexpr QueueFamily family = QueueFamily::linked_spsc_with_recycler;

  explicit LinkedQueueAdapter(LinkedSpscQueue& queue) noexcept : queue_(queue) {}

  [[nodiscard]] EnqueueResult try_enqueue(EventPointer event) noexcept {
    return queue_.try_enqueue(event);
  }
  [[nodiscard]] DequeueResult try_dequeue() noexcept { return queue_.try_dequeue(); }

  [[nodiscard]] LinkedSpscQueue& linked_queue() noexcept { return queue_; }

private:
  LinkedSpscQueue& queue_;
};

static_assert(RingQueueAdapter::family != LinkedQueueAdapter::family);

} // namespace cpu_prefetch::queue

#endif // CPU_PREFETCH_QUEUE_ADAPTERS_HPP
