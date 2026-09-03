#include "cpu_prefetch/runner/software_prefetch.hpp"

extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_ring_producer_write(const void* address) noexcept {
  cpu_prefetch::runner::X86RetainingPrefetchEmitter{}.ring_producer_write(address);
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_ring_consumer_read(const void* address) noexcept {
  cpu_prefetch::runner::X86RetainingPrefetchEmitter{}.ring_consumer_read(address);
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_successor_header(const void* address) noexcept {
  cpu_prefetch::runner::X86RetainingPrefetchEmitter{}.successor_header(address);
}

int main() {
  int value = 0;
  cpu_prefetch_software_prefetch_ring_producer_write(&value);
  cpu_prefetch_software_prefetch_ring_consumer_read(&value);
  cpu_prefetch_software_prefetch_successor_header(&value);
  return 0;
}
