#include "cpu_prefetch/platform/prepared_residency.hpp"

#include <cerrno>
#include <sys/syscall.h>
#include <unistd.h>

namespace cpu_prefetch::platform {

auto LinuxPageResidencyQuery::query_pages(std::span<void* const> pages,
                                          std::span<int> status) const noexcept
    -> PageResidencyQueryResult {
  if (pages.empty() || pages.size() != status.size()) {
    return {-1, EINVAL};
  }
  const auto result = ::syscall(SYS_move_pages, 0, pages.size(), pages.data(), nullptr,
                                status.data(), 0);
  const auto saved_errno = result < 0 ? errno : 0;
  return {result, saved_errno};
}

} // namespace cpu_prefetch::platform
