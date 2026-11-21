#ifndef CPU_PREFETCH_RUNNER_STAGE17_S180_WORKER_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_S180_WORKER_HPP
#include "cpu_prefetch/runner/stage17_s180_input.hpp"

namespace cpu_prefetch::runner::stage17 {
inline constexpr std::string_view kS180WorkerRole = "STAGE17_S180_NATIVE_WORKER";
inline constexpr std::string_view kS180WorkerProfile = "STAGE17-S180-NATIVE-WORKER-v1";
struct S180ExecutableIdentity final {
  std::string sha256;
  std::uint64_t size_bytes;
};
[[nodiscard]] auto inspect_s180_executable()
    -> protocol::Result<S180ExecutableIdentity>;
struct S180EpochWindow final {
  std::uint64_t issued_at_epoch_seconds, expires_at_epoch_seconds;
  std::uint64_t observed_epoch_seconds, remaining_monotonic_ns;
};
// Whole-second epoch readings cannot prove coverage of their missing fraction.
[[nodiscard]] auto s180_epoch_authority_covers_window(S180EpochWindow) noexcept -> bool;
// Production constructs only LinuxS180WorkerOperations. Software tests link a
// distinct implementation; no CLI/environment/plugin can select that backend.
class S180WorkerOperations {
public:
  virtual ~S180WorkerOperations() = default;
  virtual auto synthetic_test_only() const noexcept -> bool = 0;
  virtual auto execute(const S180SessionInput&, const S180SessionAuthority&,
                       S180ArchiveSink&) -> protocol::Result<ActionOutcome> = 0;
};
class LinuxS180WorkerOperations final : public S180WorkerOperations {
public:
  auto synthetic_test_only() const noexcept -> bool override { return false; }
  auto execute(const S180SessionInput&, const S180SessionAuthority&, S180ArchiveSink&)
      -> protocol::Result<ActionOutcome> override;
};
// Internal, inherited sealed-FD entry. The qualified parent authenticates the
// signed scoped admission before constructing the context. This worker binds
// that exact context to actual executable/source, parent channel, output root,
// request/plan/prerequisites, boot and non-resetting operational window.
auto run_s180_session_worker(int argc, char** argv, S180WorkerOperations&) -> int;
} // namespace cpu_prefetch::runner::stage17
#endif
