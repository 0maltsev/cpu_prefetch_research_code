#ifndef CPU_PREFETCH_PLATFORM_THREAD_TLS_HPP
#define CPU_PREFETCH_PLATFORM_THREAD_TLS_HPP

#include "cpu_prefetch/platform/owner_mapping.hpp"

namespace cpu_prefetch::platform {

struct ThreadTlsModule final {
  std::uintptr_t image_base{0U};
  std::size_t module_id{0U};
  std::uintptr_t address{0U};
  std::size_t bytes{0U};
  auto operator==(const ThreadTlsModule&) const -> bool = default;
};

enum class ThreadTlsStop : std::uint8_t {
  invalid_storage,
  identity_failure,
  unsupported_loader_abi,
  loader_changed,
  invalid_module,
  capacity_exhausted,
  complete,
};

struct ThreadTlsSnapshot final {
  ThreadTlsStop stop{ThreadTlsStop::invalid_storage};
  std::optional<LinuxCallResult> thread_before;
  std::optional<LinuxCallResult> thread_after;
  std::optional<LinuxCallResult> fs_read;
  std::optional<std::uintptr_t> fs_base;
  std::optional<std::uint64_t> loader_adds;
  std::optional<std::uint64_t> loader_subs;
  std::optional<int> iteration_return;
  std::size_t visited_objects{0U};
  std::size_t used{0U};
};

// Cold owner-thread observation only: the loader walk may acquire loader locks.
// Caller provides finite, disjoint output for each retained snapshot. No retry,
// allocation of missing TLS, page mutation, or inference of NUMA placement.
// Null addresses explicitly mean TLS not allocated in the calling thread.
// These PT_TLS payloads and FS base do NOT describe the complete libc thread
// control block, dynamic thread vector, allocator state or process footprint.
[[nodiscard]] auto observe_thread_tls(std::span<ThreadTlsModule> output) noexcept
    -> ThreadTlsSnapshot;

// Compare complete cold snapshots of the same live owner and loader generation.
// This does not qualify placement, exclude intervening mutations, or establish
// that all listed payloads are allocated; callers must check their actual ranges.
[[nodiscard]] auto
same_thread_tls(const ThreadTlsSnapshot& before,
                std::span<const ThreadTlsModule> before_modules,
                const ThreadTlsSnapshot& after,
                std::span<const ThreadTlsModule> after_modules) noexcept -> bool;

} // namespace cpu_prefetch::platform

#endif
