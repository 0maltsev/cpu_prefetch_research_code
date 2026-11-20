#ifndef CPU_PREFETCH_RUNNER_STAGE17_S180_PUBLICATION_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_S180_PUBLICATION_HPP
#include "cpu_prefetch/calibration/native_pilot_capture.hpp"
#include "cpu_prefetch/runner/stage17_fixed_action.hpp"
namespace cpu_prefetch::runner::stage17 {
inline constexpr std::string_view kS180MethodId = "STAGE17-PILOT-S180-DESCRIPTIVE-v1";
inline constexpr std::string_view kS180ControlSchema =
    "cpu-prefetch-stage17-s180-capture-control/1";
[[nodiscard]] auto
s180_capture_result_json(const calibration::NativePilotCaptureResult&)
    -> protocol::json::Value;
// Cold synchronous publication before private cleanup. Retains original P/C
// for both phases, actual mapped sources/order and all nine-region controls.
// Does not establish validity, archive custody or final family cleanup.
[[nodiscard]] auto
publish_s180_capture(ArtifactSink&, std::size_t execution_ordinal,
                     const protocol::json::Value::Object& prospective_capture,
                     const calibration::NativePilotPublicationView&)
    -> protocol::Result<std::vector<ArtifactBinding>>;
} // namespace cpu_prefetch::runner::stage17
#endif
