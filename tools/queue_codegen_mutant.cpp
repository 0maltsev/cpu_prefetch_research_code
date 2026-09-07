#include "cpu_prefetch/queue/adapters.hpp"

#include <atomic>

namespace {
std::atomic<unsigned int> forbidden_observer_calls{0U};
}

extern "C" [[gnu::noinline]] void cpu_prefetch_forbidden_observer() noexcept {
  forbidden_observer_calls.fetch_add(1U, std::memory_order_seq_cst);
}

extern "C" [[gnu::noinline]] cpu_prefetch::queue::EnqueueResult
cpu_prefetch_ring_try_enqueue_mutant(cpu_prefetch::queue::RingQueueAdapter* adapter,
                                     cpu_prefetch::queue::EventPointer event) noexcept {
  const auto result = adapter->try_enqueue(event);
  cpu_prefetch_forbidden_observer();
  return result;
}

int main() { return 0; }
