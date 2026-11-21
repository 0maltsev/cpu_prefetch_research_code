#include "cpu_prefetch/runner/stage17_s180_channel_sink.hpp"
#include <algorithm>
#include <chrono>
namespace cpu_prefetch::runner::stage17 {
S180ChannelSink::S180ChannelSink(ArtifactSink& sink,
                                 FormalArchiveChannelContext channel,
                                 std::array<std::uint64_t, 180U> archive_ns,
                                 std::uint64_t receipt_bytes)
    : output_(sink), channel_(std::move(channel)), archive_ns_(archive_ns),
      maximum_receipt_bytes_(receipt_bytes) {
  if (!validate_formal_archive_channel(channel_) || receipt_bytes == 0U ||
      std::any_of(archive_ns.begin(), archive_ns.end(), [](auto n) { return n == 0U; }))
    throw std::invalid_argument(
        "S180 channel peer/scope or prospective limits are invalid");
}
auto S180ChannelSink::publish(ArtifactPayload artifact)
    -> protocol::Result<ArtifactBinding> {
  return output_.publish(std::move(artifact));
}
auto S180ChannelSink::has_archive_checkpoint() const noexcept -> bool {
  return !failed_ && ordinal_ < archive_ns_.size();
}
auto S180ChannelSink::s180_program_scope_sha256() const noexcept -> std::string_view {
  return channel_.program_scope_sha256;
}
auto S180ChannelSink::archive_checkpoint(const ArtifactBinding& checkpoint,
                                         std::uint64_t deadline)
    -> protocol::Result<ArtifactBinding> {
  const auto fail = [&](const char* message) {
    failed_ = true;
    return protocol::Result<ArtifactBinding>::failure(
        {protocol::ErrorCategory::cross_field, "$/s180/archive-channel",
         "S17-S180-CHANNEL", message});
  };
  if (!has_archive_checkpoint())
    return fail("S180 channel stopped or family exhausted");
  const auto now = std::chrono::duration_cast<std::chrono::nanoseconds>(
                       std::chrono::steady_clock::now().time_since_epoch())
                       .count();
  if (now < 0 || deadline <= static_cast<std::uint64_t>(now) ||
      deadline - static_cast<std::uint64_t>(now) > archive_ns_[ordinal_])
    return fail("S180 archive deadline exceeds this prospective interval");
  auto result =
      exchange_s180_archive_checkpoint(channel_, checkpoint, {ordinal_, deadline});
  if (!result) {
    failed_ = true;
    return result;
  }
  if (result.value().size_bytes > maximum_receipt_bytes_)
    return fail("S180 custody receipt exceeds declared bound");
  ++ordinal_;
  return result;
}
} // namespace cpu_prefetch::runner::stage17
