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

extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_t0_ring_producer_write(const void* address) noexcept {
  cpu_prefetch::runner::X86PrefetchT0OnlyEmitter{}.ring_producer_write(address);
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_t0_ring_consumer_read(const void* address) noexcept {
  cpu_prefetch::runner::X86PrefetchT0OnlyEmitter{}.ring_consumer_read(address);
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_software_prefetch_t0_successor_header(const void* address) noexcept {
  cpu_prefetch::runner::X86PrefetchT0OnlyEmitter{}.successor_header(address);
}

int main(int argc, char** argv) {
  int value = 0;
  if (argc == 2 && std::string_view(argv[1]) == "--t0-only-software-self-test") {
    cpu_prefetch_software_prefetch_t0_ring_producer_write(&value);
    cpu_prefetch_software_prefetch_t0_ring_consumer_read(&value);
    cpu_prefetch_software_prefetch_t0_successor_header(&value);
    return 0;
  }
  if (argc != 1) {
    return 2;
  }
  cpu_prefetch_software_prefetch_ring_producer_write(&value);
  cpu_prefetch_software_prefetch_ring_consumer_read(&value);
  cpu_prefetch_software_prefetch_successor_header(&value);
  return 0;
}
