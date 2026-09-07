#include "cpu_prefetch/queue/ring_spsc.hpp"
#include "cpu_prefetch/timing/clock.hpp"

#include <atomic>
#include <cstdint>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>
#include <x86intrin.h>

extern "C" [[gnu::noinline]] long
cpu_prefetch_timing_syscall_mutant(timespec* value) noexcept {
  return ::syscall(SYS_clock_gettime, CLOCK_MONOTONIC_RAW, value);
}

extern "C" [[gnu::noinline]] void cpu_prefetch_timing_hardware_fence_mutant() noexcept {
  std::atomic_thread_fence(std::memory_order_seq_cst);
}

extern "C" [[gnu::noinline]] std::uint64_t
cpu_prefetch_timing_direct_counter_mutant() noexcept {
  unsigned int auxiliary = 0U;
  return __rdtscp(&auxiliary);
}

extern "C" [[gnu::noinline]] int
cpu_prefetch_timing_wrong_clock_mutant(timespec* value) noexcept {
  return ::clock_gettime(CLOCK_MONOTONIC, value);
}

extern "C" [[gnu::noinline]] int
cpu_prefetch_timing_no_compiler_fence_mutant(timespec* value) noexcept {
  return ::clock_gettime(CLOCK_MONOTONIC_RAW, value);
}

extern "C" [[gnu::noinline]] cpu_prefetch::queue::EnqueueResult
cpu_prefetch_timing_p_after_publication_mutant(
    cpu_prefetch::queue::RingSpscQueue* queue,
    cpu_prefetch::queue::EventPointer event) noexcept {
  const auto result = queue->try_enqueue(event);
  static_cast<void>(cpu_prefetch::timing::read_monotonic_raw_absolute());
  return result;
}

extern "C" [[gnu::noinline]] cpu_prefetch::queue::DequeueResult
cpu_prefetch_timing_q_before_observation_mutant(
    cpu_prefetch::queue::RingSpscQueue* queue) noexcept {
  static_cast<void>(cpu_prefetch::timing::read_monotonic_raw_absolute());
  return queue->try_dequeue();
}

int main() { return 0; }
