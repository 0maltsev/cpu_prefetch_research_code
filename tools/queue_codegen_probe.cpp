#include "cpu_prefetch/queue/adapters.hpp"

extern "C" [[gnu::noinline]] cpu_prefetch::queue::EnqueueResult
cpu_prefetch_ring_try_enqueue(cpu_prefetch::queue::RingQueueAdapter* adapter,
                              cpu_prefetch::queue::EventPointer event) noexcept {
  return adapter->try_enqueue(event);
}

extern "C" [[gnu::noinline]] cpu_prefetch::queue::DequeueResult
cpu_prefetch_ring_try_dequeue(cpu_prefetch::queue::RingQueueAdapter* adapter) noexcept {
  return adapter->try_dequeue();
}

extern "C" [[gnu::noinline]] cpu_prefetch::queue::EnqueueResult
cpu_prefetch_linked_try_enqueue(cpu_prefetch::queue::LinkedQueueAdapter* adapter,
                                cpu_prefetch::queue::EventPointer event) noexcept {
  return adapter->try_enqueue(event);
}

extern "C" [[gnu::noinline]] cpu_prefetch::queue::DequeueResult
cpu_prefetch_linked_try_dequeue(
    cpu_prefetch::queue::LinkedQueueAdapter* adapter) noexcept {
  return adapter->try_dequeue();
}

int main() { return 0; }
