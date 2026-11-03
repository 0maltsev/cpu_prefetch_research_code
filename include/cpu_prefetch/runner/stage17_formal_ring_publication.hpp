#ifndef CPU_PREFETCH_RUNNER_STAGE17_FORMAL_RING_PUBLICATION_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_FORMAL_RING_PUBLICATION_HPP

#include "cpu_prefetch/calibration/native_formal_ring_capture.hpp"
#include "cpu_prefetch/runner/stage17_fixed_action.hpp"

namespace cpu_prefetch::runner::stage17 {

[[nodiscard]] auto formal_ring_capture_result_json(
    const calibration::NativeFormalRingCaptureResult& result) -> protocol::json::Value;

// Cold, synchronous publication before mappings are released, including failed
// captures. Exactly eight raw streams (two phases, two owners, primary+demand)
// and one control document; unavailable owners retain empty raw artifacts and
// explicit absent snapshots. No scientific filtering, inference or admission.
// The explicit minimum comes from the frozen capture input, never raw counts.
// One raw payload copy at a time; bound that copy and the finite JSON tree/text
// in the prospective publication budget. Sink failure leaves prior artifacts
// retained and is terminal, never an overwrite or automatic retry.
// Actual final cleanup belongs to formal_ring_capture_result_json(returned).
[[nodiscard]] auto
publish_formal_ring_capture(ArtifactSink& sink, std::size_t capture_ordinal,
                            std::uint64_t minimum_observations_per_series,
                            const calibration::NativeFormalRingPublicationView& view)
    -> protocol::Result<std::vector<ArtifactBinding>>;

} // namespace cpu_prefetch::runner::stage17
#endif
