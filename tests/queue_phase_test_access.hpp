#ifndef CPU_PREFETCH_TESTS_QUEUE_PHASE_TEST_ACCESS_HPP
#define CPU_PREFETCH_TESTS_QUEUE_PHASE_TEST_ACCESS_HPP

#include "cpu_prefetch/queue/linked_spsc.hpp"
#include "cpu_prefetch/queue/ring_spsc.hpp"

namespace cpu_prefetch::queue::testing {

struct QueuePhaseTestAccess final {
  template <typename Observer>
  [[nodiscard]] static EnqueueResult
  ring_enqueue(RingSpscQueue& queue, EventPointer event, Observer& observer) noexcept {
    return queue.try_enqueue_observed(event, observer);
  }

  template <typename Observer>
  [[nodiscard]] static DequeueResult ring_dequeue(RingSpscQueue& queue,
                                                  Observer& observer) noexcept {
    return queue.try_dequeue_observed(observer);
  }

  template <typename Observer>
  [[nodiscard]] static EnqueueResult linked_enqueue(LinkedSpscQueue& queue,
                                                    EventPointer event,
                                                    Observer& observer) noexcept {
    return queue.try_enqueue_observed(event, observer);
  }

  template <typename Observer>
  [[nodiscard]] static DequeueResult linked_dequeue(LinkedSpscQueue& queue,
                                                    Observer& observer) noexcept {
    return queue.try_dequeue_observed(observer);
  }
};

} // namespace cpu_prefetch::queue::testing

#endif // CPU_PREFETCH_TESTS_QUEUE_PHASE_TEST_ACCESS_HPP
