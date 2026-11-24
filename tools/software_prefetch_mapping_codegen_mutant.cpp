extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_ring_producer_write_mutant(
    const void* address) noexcept {
  asm volatile("prefetcht0 %0" : : "m"(*static_cast<const char*>(address)));
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_ring_consumer_read_mutant(const void* address) noexcept {
  asm volatile("prefetchw %0" : : "m"(*static_cast<const char*>(address)));
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_t0_producer_wrong(const void* address) noexcept {
  asm volatile("prefetchw %0" : : "m"(*static_cast<const char*>(address)));
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_t0_consumer_wrong(const void* address) noexcept {
  asm volatile("prefetchw %0" : : "m"(*static_cast<const char*>(address)));
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_t0_successor_wrong(const void* address) noexcept {
  asm volatile("prefetchw %0" : : "m"(*static_cast<const char*>(address)));
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_t0_duplicate(const void* address) noexcept {
  asm volatile("prefetcht0 %0\n\tprefetcht0 %0"
               :
               : "m"(*static_cast<const char*>(address)));
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_t0_missing(const void* address) noexcept {
  asm volatile("" : : "r"(address));
}

int main() {
  int value = 0;
  cpu_prefetch_software_prefetch_ring_producer_write_mutant(&value);
  cpu_prefetch_software_prefetch_ring_consumer_read_mutant(&value);
  return 0;
}
