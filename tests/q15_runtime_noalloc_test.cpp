#include "cpu_prefetch/platform/q15_runtime.hpp"

#include <gtest/gtest.h>

#include <atomic>
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <new>

namespace {

std::atomic<std::size_t> allocation_count{0U};

} // namespace

void* operator new(std::size_t size) {
  allocation_count.fetch_add(1U, std::memory_order_relaxed);
  if (void* pointer = std::malloc(size); pointer != nullptr) {
    return pointer;
  }
  throw std::bad_alloc();
}

void* operator new[](std::size_t size) { return ::operator new(size); }

void* operator new(std::size_t size, const std::nothrow_t&) noexcept {
  allocation_count.fetch_add(1U, std::memory_order_relaxed);
  return std::malloc(size);
}

void* operator new[](std::size_t size, const std::nothrow_t& tag) noexcept {
  return ::operator new(size, tag);
}

void* operator new(std::size_t size, std::align_val_t alignment) {
  allocation_count.fetch_add(1U, std::memory_order_relaxed);
  void* pointer = nullptr;
  if (posix_memalign(&pointer, static_cast<std::size_t>(alignment), size) == 0) {
    return pointer;
  }
  throw std::bad_alloc();
}

void* operator new[](std::size_t size, std::align_val_t alignment) {
  return ::operator new(size, alignment);
}

void* operator new(std::size_t size, std::align_val_t alignment,
                   const std::nothrow_t&) noexcept {
  allocation_count.fetch_add(1U, std::memory_order_relaxed);
  void* pointer = nullptr;
  return posix_memalign(&pointer, static_cast<std::size_t>(alignment), size) == 0
             ? pointer
             : nullptr;
}

void* operator new[](std::size_t size, std::align_val_t alignment,
                     const std::nothrow_t& tag) noexcept {
  return ::operator new(size, alignment, tag);
}

void operator delete(void* pointer) noexcept { std::free(pointer); }
void operator delete[](void* pointer) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::size_t) noexcept { std::free(pointer); }
void operator delete[](void* pointer, std::size_t) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::align_val_t) noexcept { std::free(pointer); }
void operator delete[](void* pointer, std::align_val_t) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::size_t, std::align_val_t) noexcept {
  std::free(pointer);
}
void operator delete[](void* pointer, std::size_t, std::align_val_t) noexcept {
  std::free(pointer);
}

namespace {

class NoAllocationPerf final : public cpu_prefetch::platform::Q15PerfOperations {
public:
  [[nodiscard]] auto open_event(const cpu_prefetch::platform::Q15PerfEventRequest&)
      -> cpu_prefetch::platform::Result<int> override {
    return cpu_prefetch::platform::Result<int>::success(5);
  }
  [[nodiscard]] auto reset(int) noexcept -> bool override { return true; }
  [[nodiscard]] auto enable(int descriptor) noexcept -> bool override {
    ++enable_count;
    observed_descriptor = descriptor;
    return true;
  }
  [[nodiscard]] auto disable(int descriptor) noexcept -> bool override {
    ++disable_count;
    observed_descriptor = descriptor;
    return true;
  }
  [[nodiscard]] auto read(int) -> cpu_prefetch::platform::Result<
      cpu_prefetch::platform::Q15CounterReading> override {
    return cpu_prefetch::platform::Result<
        cpu_prefetch::platform::Q15CounterReading>::success({1U, 1U, 1U});
  }
  [[nodiscard]] auto close(int) noexcept -> bool override { return true; }

  std::size_t enable_count{0U};
  std::size_t disable_count{0U};
  int observed_descriptor{-1};
};

TEST(Q15CountedRegionNoAllocation,
     RegularAndPointerRegionsAllocateNothingBetweenCounterBoundaries) {
  alignas(4096)
      std::byte buffer[4U * cpu_prefetch::platform::kQ15ProbeCacheLineBytes]{};
  for (std::uint32_t index = 0U; index < 4U; ++index) {
    const auto next = static_cast<std::uint32_t>((index + 1U) % 4U);
    std::memcpy(buffer + (index * cpu_prefetch::platform::kQ15ProbeCacheLineBytes),
                &next, sizeof(next));
  }
  NoAllocationPerf perf;
  const auto before = allocation_count.load(std::memory_order_relaxed);
  const auto regular = cpu_prefetch::platform::cpu_prefetch_q15_regular_counted_region(
      &perf, 19, buffer, 4U);
  const auto pointer = cpu_prefetch::platform::cpu_prefetch_q15_pointer_counted_region(
      &perf, 19, buffer, 4U, 0U);
  const auto after = allocation_count.load(std::memory_order_relaxed);

  EXPECT_TRUE(regular.enabled);
  EXPECT_TRUE(regular.disabled);
  EXPECT_TRUE(pointer.enabled);
  EXPECT_TRUE(pointer.disabled);
  EXPECT_EQ(pointer.retention_value, 0U);
  EXPECT_EQ(perf.enable_count, 2U);
  EXPECT_EQ(perf.disable_count, 2U);
  EXPECT_EQ(perf.observed_descriptor, 19);
  EXPECT_EQ(after, before);
}

} // namespace
