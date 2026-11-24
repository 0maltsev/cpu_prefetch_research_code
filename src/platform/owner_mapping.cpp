#include "cpu_prefetch/platform/owner_mapping.hpp"

#include <cerrno>
#include <limits>
#include <linux/mempolicy.h>
#include <sched.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <unistd.h>

namespace cpu_prefetch::platform {
namespace {

[[nodiscard]] auto observed_call(std::int64_t value) noexcept -> LinuxCallResult {
  return {value, value < 0 ? errno : 0};
}

[[nodiscard]] auto invalid_range(std::span<std::byte> bytes) noexcept -> bool {
  const auto begin = reinterpret_cast<std::uintptr_t>(bytes.data());
  return bytes.empty() || begin == 0U ||
         bytes.size() > std::numeric_limits<std::uintptr_t>::max() - begin;
}

} // namespace

auto linux_owner_binding_request(std::span<std::byte> bytes,
                                 std::uint32_t node) noexcept
    -> std::optional<LinuxOwnerBindingRequest> {
  if (invalid_range(bytes) || node >= std::numeric_limits<unsigned long>::digits) {
    return std::nullopt;
  }
  // Linux get_nodes() decrements the syscall maxnode before importing bits.
  // Include every bit of the one-word mask, including node 0 and its top bit.
  return LinuxOwnerBindingRequest{bytes, 1UL << node,
                                  std::numeric_limits<unsigned long>::digits + 1UL, 0UL,
                                  MPOL_BIND};
}

auto LinuxOwnerMemoryOperations::base_page_bytes() const noexcept -> LinuxCallResult {
  errno = 0;
  return observed_call(::sysconf(_SC_PAGESIZE));
}

auto LinuxOwnerMemoryOperations::map_private(std::size_t bytes) const noexcept
    -> LinuxMappingResult {
  if (bytes == 0U ||
      bytes > static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max())) {
    return {nullptr, EINVAL};
  }
  void* mapped = ::mmap(nullptr, bytes, PROT_READ | PROT_WRITE,
                        MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  if (mapped == MAP_FAILED) {
    return {nullptr, errno};
  }
  return {static_cast<std::byte*>(mapped), 0};
}

auto LinuxOwnerMemoryOperations::bind_pages(std::span<std::byte> bytes,
                                            std::uint32_t node) const noexcept
    -> LinuxCallResult {
  const auto request = linux_owner_binding_request(bytes, node);
  if (!request.has_value()) {
    return {-1, EINVAL};
  }
  return observed_call(::syscall(
      SYS_mbind, request->bytes.data(), request->bytes.size(), request->policy,
      &request->node_mask, request->max_node, request->flags));
}

auto LinuxOwnerMemoryOperations::disable_huge_pages(
    std::span<std::byte> bytes) const noexcept -> LinuxCallResult {
  if (invalid_range(bytes)) {
    return {-1, EINVAL};
  }
  return observed_call(::madvise(bytes.data(), bytes.size(), MADV_NOHUGEPAGE));
}

auto LinuxOwnerMemoryOperations::bind_current_thread(std::uint32_t cpu) const noexcept
    -> LinuxCallResult {
  if (cpu >= CPU_SETSIZE) {
    return {-1, EINVAL};
  }
  cpu_set_t requested;
  CPU_ZERO(&requested);
  CPU_SET(cpu, &requested);
  return observed_call(::sched_setaffinity(0, sizeof(requested), &requested));
}

auto LinuxOwnerMemoryOperations::observe_current_thread(
    std::uint32_t requested_cpu) const noexcept -> OwnerThreadObservation {
  cpu_set_t affinity;
  CPU_ZERO(&affinity);
  const auto affinity_result =
      observed_call(::sched_getaffinity(0, sizeof(affinity), &affinity));
  const auto current_cpu = observed_call(::sched_getcpu());
  const auto thread_id = observed_call(::syscall(SYS_gettid));
  ::rusage usage{};
  const auto faults = observed_call(::getrusage(RUSAGE_THREAD, &usage));
  return {affinity_result,
          current_cpu,
          thread_id,
          faults,
          usage.ru_minflt,
          usage.ru_majflt,
          affinity_result.zero_return() ? CPU_COUNT(&affinity) : 0,
          affinity_result.zero_return() && requested_cpu < CPU_SETSIZE &&
              CPU_ISSET(requested_cpu, &affinity) != 0};
}

auto LinuxOwnerMemoryOperations::lock_pages(std::span<std::byte> bytes) const noexcept
    -> LinuxCallResult {
  if (invalid_range(bytes)) {
    return {-1, EINVAL};
  }
  return observed_call(::mlock(bytes.data(), bytes.size()));
}

auto LinuxOwnerMemoryOperations::protect_read_only(
    std::span<std::byte> bytes) const noexcept -> LinuxCallResult {
  if (invalid_range(bytes)) {
    return {-1, EINVAL};
  }
  return observed_call(::mprotect(bytes.data(), bytes.size(), PROT_READ));
}

auto LinuxOwnerMemoryOperations::protect_no_access(
    std::span<std::byte> bytes) const noexcept -> LinuxCallResult {
  if (invalid_range(bytes)) {
    return {-1, EINVAL};
  }
  return observed_call(::mprotect(bytes.data(), bytes.size(), PROT_NONE));
}

auto LinuxOwnerMemoryOperations::populate_write(
    std::span<std::byte> bytes) const noexcept -> LinuxCallResult {
  if (invalid_range(bytes)) {
    return {-1, EINVAL};
  }
  return observed_call(::madvise(bytes.data(), bytes.size(), MADV_POPULATE_WRITE));
}

auto LinuxOwnerMemoryOperations::minimum_thread_stack_bytes() const noexcept
    -> LinuxCallResult {
  errno = 0;
  return observed_call(::sysconf(_SC_THREAD_STACK_MIN));
}

auto LinuxOwnerMemoryOperations::unlock_pages(std::span<std::byte> bytes) const noexcept
    -> LinuxCallResult {
  if (invalid_range(bytes)) {
    return {-1, EINVAL};
  }
  return observed_call(::munlock(bytes.data(), bytes.size()));
}

auto LinuxOwnerMemoryOperations::unmap(std::span<std::byte> bytes) const noexcept
    -> LinuxCallResult {
  if (invalid_range(bytes)) {
    return {-1, EINVAL};
  }
  return observed_call(::munmap(bytes.data(), bytes.size()));
}

} // namespace cpu_prefetch::platform
