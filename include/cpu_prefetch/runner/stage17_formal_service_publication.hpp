#ifndef CPU_PREFETCH_RUNNER_STAGE17_FORMAL_SERVICE_PUBLICATION_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_FORMAL_SERVICE_PUBLICATION_HPP

#include "cpu_prefetch/calibration/native_formal_service_capture.hpp"
#include "cpu_prefetch/runner/stage17_fixed_action.hpp"

namespace cpu_prefetch::runner::stage17 {

[[nodiscard]] auto formal_service_capture_result_json(
    const calibration::NativeFormalServiceCaptureResult& result)
    -> protocol::json::Value;

// Cold publication of original warmup/measurement primary streams, explicit
// node order and native control evidence, including failed/incomplete captures.
// No demand timestamps or throughput filtering are introduced into the worker.
// D211's cold result is retained separately from full drain consumption; the
// independent validator must recompute it. This does not grant run validity,
// complete a derived-analysis artifact set or infer successful final cleanup.
[[nodiscard]] auto publish_formal_service_capture(
    ArtifactSink& sink, std::size_t capture_ordinal,
    const calibration::NativeFormalServicePublicationView& view)
    -> protocol::Result<std::vector<ArtifactBinding>>;

} // namespace cpu_prefetch::runner::stage17
#endif
