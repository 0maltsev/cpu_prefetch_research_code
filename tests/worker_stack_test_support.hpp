#ifndef CPU_PREFETCH_TESTS_WORKER_STACK_TEST_SUPPORT_HPP
#define CPU_PREFETCH_TESTS_WORKER_STACK_TEST_SUPPORT_HPP

#include "cpu_prefetch/platform/worker_stack.hpp"

#include <array>
#include <cerrno>
#include <sched.h>

namespace cpu_prefetch::test {

// Real native mapping, guarding, pthread affinity, owner readback, writable
// prefault and locking. Only mbind is injected: these tests make NO NUMA claim.
struct SoftwareStackOperations final {
  platform::LinuxOwnerMemoryOperations native;
  enum class Failure : std::uint8_t {
    none,
    bind,
    no_huge,
    guard,
    observe,
    populate,
    lock,
    after
  };
  Failure failure{Failure::none};
  std::size_t observations{0U};
  std::array<int, 8U> calls{};
  std::size_t call_count{0U};
  bool live_bytes_preserved{false};
  auto base_page_bytes() noexcept { return native.base_page_bytes(); }
  auto minimum_thread_stack_bytes() noexcept {
    return native.minimum_thread_stack_bytes();
  }
  auto map_private(std::size_t size) noexcept { return native.map_private(size); }
  auto bind_pages(std::span<std::byte>, std::uint32_t) noexcept
      -> platform::LinuxCallResult {
    calls[call_count++] = 1;
    return failure == Failure::bind ? platform::LinuxCallResult{-1, EPERM}
                                    : platform::LinuxCallResult{0, 0};
  }
  auto disable_huge_pages(std::span<std::byte> bytes) noexcept {
    calls[call_count++] = 2;
    return failure == Failure::no_huge ? platform::LinuxCallResult{-1, EINVAL}
                                       : native.disable_huge_pages(bytes);
  }
  auto protect_no_access(std::span<std::byte> bytes) noexcept {
    calls[call_count++] = 3;
    return failure == Failure::guard ? platform::LinuxCallResult{-1, EACCES}
                                     : native.protect_no_access(bytes);
  }
  auto observe_current_thread(std::uint32_t cpu) noexcept {
    calls[call_count++] = 4;
    ++observations;
    auto result = native.observe_current_thread(cpu);
    if (failure == Failure::observe ||
        (failure == Failure::after && observations == 2U)) {
      result.affinity = {-1, EACCES};
    }
    return result;
  }
  auto populate_write(std::span<std::byte> bytes) noexcept {
    calls[call_count++] = 5;
    // Volatile witnesses occupy live frames across the real syscall.
    volatile std::uint64_t witness[1024U];
    for (std::size_t index = 0U; index < 1024U; ++index) {
      witness[index] = 0x91a276baU + index;
    }
    const auto result = failure == Failure::populate
                            ? platform::LinuxCallResult{-1, EINVAL}
                            : native.populate_write(bytes);
    live_bytes_preserved = true;
    for (std::size_t index = 0U; index < 1024U; ++index) {
      live_bytes_preserved =
          live_bytes_preserved && witness[index] == 0x91a276baU + index;
    }
    return result;
  }
  auto lock_pages(std::span<std::byte> bytes) noexcept {
    calls[call_count++] = 6;
    return failure == Failure::lock ? platform::LinuxCallResult{-1, ENOMEM}
                                    : native.lock_pages(bytes);
  }
  auto unlock_pages(std::span<std::byte> bytes) noexcept {
    return native.unlock_pages(bytes);
  }
  auto unmap(std::span<std::byte> bytes) noexcept { return native.unmap(bytes); }
};

inline auto software_stack_plan() -> platform::OwnerMappingPlan {
  platform::LinuxOwnerMemoryOperations native;
  const auto page = native.base_page_bytes();
  const auto cpu = ::sched_getcpu();
  // Test-only stack capacity, not a prospective experimental resource budget.
  return {std::size_t{2U} * 1024U * 1024U, static_cast<std::size_t>(page.return_value),
          static_cast<std::uint32_t>(cpu), 0U};
}

} // namespace cpu_prefetch::test

#endif
