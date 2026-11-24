#ifndef CPU_PREFETCH_RUNNER_STAGE17_FORMAL_SCHEDULED_PUBLICATION_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_FORMAL_SCHEDULED_PUBLICATION_HPP
#include "cpu_prefetch/calibration/native_formal_scheduled_capture.hpp"
#include "cpu_prefetch/runner/stage17_fixed_action.hpp"
namespace cpu_prefetch::runner::stage17 {
[[nodiscard]] auto formal_scheduled_capture_result_json(
    const calibration::NativeFormalScheduledCaptureResult& result)
    -> protocol::json::Value;
// Cold original P/C for both phases, two mapped source schedules, node order,
// and complete control evidence. A prepared schedule is not evidence of execution.
// prospective_capture is the exact admitted capture JSON; deadline arrays are
// omitted from its metadata copy because actual mapped vectors are separate raw.
// This retains partial failure prefixes, grants no validity/authority, and does
// not create a joined-derived latency product. Budget one payload copy at a time
// plus bounded JSON/canonicalization; final cleanup belongs to the returned result.
[[nodiscard]] auto publish_formal_scheduled_capture(
    ArtifactSink& sink, std::size_t capture_ordinal,
    const protocol::json::Value::Object& prospective_capture,
    const calibration::NativeFormalScheduledPublicationView& view)
    -> protocol::Result<std::vector<ArtifactBinding>>;
} // namespace cpu_prefetch::runner::stage17
#endif
