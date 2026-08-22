#include <immintrin.h>
#include <sched.h>

extern "C" [[gnu::noinline]] int cpu_prefetch_runner_relax_mutant() noexcept {
  _mm_pause();
  _mm_pause();
  return ::sched_yield() + 1;
}

int main() { return cpu_prefetch_runner_relax_mutant() == 0 ? 0 : 1; }
