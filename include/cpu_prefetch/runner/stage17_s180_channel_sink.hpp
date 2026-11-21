#ifndef CPU_PREFETCH_RUNNER_STAGE17_S180_CHANNEL_SINK_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_S180_CHANNEL_SINK_HPP
#include "cpu_prefetch/runner/stage17_archive_channel.hpp"
#include "cpu_prefetch/runner/stage17_s180_session.hpp"
namespace cpu_prefetch::runner::stage17 {
// Construct only after authenticated parent/context and output-directory checks.
// The underlying sink must publish durably; this bridge neither runs a codec nor
// fabricates custody. Failed transport latches, but final failure publication is
// still delegated so original evidence can be retained.
class S180ChannelSink final : public S180ArchiveSink {
public:
  S180ChannelSink(ArtifactSink&, FormalArchiveChannelContext,
                  std::array<std::uint64_t, 180U> archive_ns,
                  std::uint64_t maximum_receipt_bytes);
  auto publish(ArtifactPayload) -> protocol::Result<ArtifactBinding> override;
  auto has_archive_checkpoint() const noexcept -> bool override;
  auto s180_program_scope_sha256() const noexcept -> std::string_view override;
  auto archive_checkpoint(const ArtifactBinding&, std::uint64_t deadline_monotonic_ns)
      -> protocol::Result<ArtifactBinding> override;

private:
  ArtifactSink& output_;
  FormalArchiveChannelContext channel_;
  const std::array<std::uint64_t, 180U> archive_ns_;
  const std::uint64_t maximum_receipt_bytes_;
  std::size_t ordinal_{0U};
  bool failed_{false};
};
} // namespace cpu_prefetch::runner::stage17
#endif
