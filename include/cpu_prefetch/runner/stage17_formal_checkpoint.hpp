#ifndef CPU_PREFETCH_RUNNER_STAGE17_FORMAL_CHECKPOINT_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_FORMAL_CHECKPOINT_HPP

#include "cpu_prefetch/runner/stage17_fixed_action.hpp"

namespace cpu_prefetch::runner::stage17 {

inline constexpr std::string_view kFormalCheckpointSchema =
    "cpu-prefetch-stage17-formal-capture-checkpoint/1";

// Cold-only receipt tracking. Each successful durable publication is retained
// immediately, even if a later publication or the enclosing writer fails.
class FormalPublicationTrackingSink final : public ArtifactSink {
public:
  FormalPublicationTrackingSink(ArtifactSink& sink,
                                std::vector<ArtifactBinding>& bindings);
  [[nodiscard]] auto publish(ArtifactPayload artifact)
      -> protocol::Result<ArtifactBinding> override;

private:
  ArtifactSink& sink_;
  std::vector<ArtifactBinding>& bindings_;
};

// Cold publication only, after the native capture call and its cleanup return.
// Preserve the original final result even for a failed capture. Publication
// supplies no archive/release authority and does not establish scientific validity.
// The caller must use a durable sink and must not start a codec or another capture
// unless this succeeds and the separate live-quiescence/custody gates pass.
[[nodiscard]] auto
publish_formal_checkpoint(ArtifactSink& sink, FixedAction action,
                          std::string_view plan_sha256,
                          const protocol::json::Value::Object& capture,
                          const protocol::json::Value& native_result_after_cleanup,
                          std::span<const ArtifactBinding> artifacts,
                          bool native_complete) -> protocol::Result<ArtifactBinding>;

} // namespace cpu_prefetch::runner::stage17
#endif
