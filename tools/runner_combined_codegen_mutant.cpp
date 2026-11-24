#include <cstddef>
#include <cstdlib>
#include <sched.h>

extern "C" [[gnu::noinline]] auto
cpu_prefetch_combined_forbidden_mutant(std::size_t bytes) noexcept -> void* {
  auto* allocation = std::malloc(bytes);
  static_cast<void>(::sched_yield());
  return allocation;
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_combined_wrong_write_prefetch_mutant(const void* address) noexcept {
  asm volatile("prefetcht0 %0" : : "m"(*static_cast<const char*>(address)));
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_combined_wrong_read_prefetch_mutant(const void* address) noexcept {
  asm volatile("prefetchw %0" : : "m"(*static_cast<const char*>(address)));
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_combined_duplicate_read_prefetch_mutant(const void* address) noexcept {
  asm volatile("prefetcht0 %0" : : "m"(*static_cast<const char*>(address)));
  asm volatile("prefetcht0 %0" : : "m"(*static_cast<const char*>(address)));
}

// ADR-0175: the T0-only mapping's own producer role must still be PREFETCHT0
// (it never issues PREFETCHW at all); this mutant wrongly emits PREFETCHW,
// mirroring cpu_prefetch_combined_wrong_write_prefetch_mutant's own role for
// the original mapping.
extern "C" [[gnu::noinline]] void
cpu_prefetch_combined_wrong_producer_t0only_mutant(const void* address) noexcept {
  asm volatile("prefetchw %0" : : "m"(*static_cast<const char*>(address)));
}

int main() {
  auto* value = cpu_prefetch_combined_forbidden_mutant(8U);
  cpu_prefetch_combined_wrong_write_prefetch_mutant(value);
  cpu_prefetch_combined_wrong_read_prefetch_mutant(value);
  cpu_prefetch_combined_duplicate_read_prefetch_mutant(value);
  cpu_prefetch_combined_wrong_producer_t0only_mutant(value);
  std::free(value);
  return 0;
}
