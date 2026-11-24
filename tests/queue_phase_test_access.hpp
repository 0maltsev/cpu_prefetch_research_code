#ifndef CPU_PREFETCH_TESTS_QUEUE_PHASE_TEST_ACCESS_HPP
#define CPU_PREFETCH_TESTS_QUEUE_PHASE_TEST_ACCESS_HPP

#include "cpu_prefetch/queue/linked_spsc.hpp"
#include "cpu_prefetch/queue/ring_spsc.hpp"

namespace cpu_prefetch::queue::testing {

struct QueuePhaseTestAccess final {
  // Inject an otherwise unique/full recycler whose order violates its frozen
  // cycle. This is a correctness-failure fixture, never an operational action.
  static void swap_first_linked_recycler_nodes(LinkedSpscQueue& queue) noexcept {
    auto* first = queue.recycler_slots_[0U].value.load(std::memory_order_relaxed);
    auto* second = queue.recycler_slots_[1U].value.load(std::memory_order_relaxed);
    queue.recycler_slots_[0U].value.store(second, std::memory_order_relaxed);
    queue.recycler_slots_[1U].value.store(first, std::memory_order_relaxed);
  }

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
    struct NoopSuccessorPrefetch final {
      void successor_header(const void*) const noexcept {}
    } prefetch;
    return queue.try_dequeue_observed(observer, prefetch);
  }
};

} // namespace cpu_prefetch::queue::testing

#endif // CPU_PREFETCH_TESTS_QUEUE_PHASE_TEST_ACCESS_HPP
