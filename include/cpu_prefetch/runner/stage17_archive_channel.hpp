#ifndef CPU_PREFETCH_RUNNER_STAGE17_ARCHIVE_CHANNEL_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_ARCHIVE_CHANNEL_HPP

#include "cpu_prefetch/runner/stage17_fixed_action.hpp"

#include <time.h>

namespace cpu_prefetch::runner::stage17 {

struct FormalArchiveChannelContext final {
  int descriptor;
  int controller_pid;
  std::string request_sha256;
  std::string program_scope_sha256;
};

struct FormalArchiveAbsoluteDeadline final {
  std::uint64_t monotonic_ns;
};

// Cold process guard, armed before checkpoint publication. A kernel-delivered
// SIGKILL bounds even blocking fsync/read without adding a worker thread. One
// active guard per native process; do not fork while owning this guard. The
// parent must retain/reap the failed worker and apply its existing restoration.
class FormalArchiveDeadline final {
public:
  explicit FormalArchiveDeadline(FormalArchiveAbsoluteDeadline absolute);
  ~FormalArchiveDeadline() noexcept;
  FormalArchiveDeadline(const FormalArchiveDeadline&) = delete;
  auto operator=(const FormalArchiveDeadline&) -> FormalArchiveDeadline& = delete;
  FormalArchiveDeadline(FormalArchiveDeadline&&) = delete;
  auto operator=(FormalArchiveDeadline&&) -> FormalArchiveDeadline& = delete;

private:
  timer_t timer_{};
};

struct FormalArchiveExchangeLimits final {
  std::uint64_t ordinal;
  std::uint64_t deadline_monotonic_ns;
};

[[nodiscard]] auto
validate_formal_archive_channel(const FormalArchiveChannelContext& channel)
    -> protocol::Result<bool>;

// Cold synchronous exchange with the parent-owned AF_UNIX/SOCK_SEQPACKET
// endpoint. The caller has already durably published the original checkpoint.
// No native capture can proceed until this exact bound acknowledgement returns.
// The descriptor is borrowed, and this function never opens data or runs codecs.
[[nodiscard]] auto exchange_formal_archive_checkpoint(
    const FormalArchiveChannelContext& channel, const ArtifactBinding& checkpoint,
    FormalArchiveExchangeLimits limits) -> protocol::Result<ArtifactBinding>;

} // namespace cpu_prefetch::runner::stage17
#endif
