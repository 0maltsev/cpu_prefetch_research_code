#ifndef CPU_PREFETCH_RUNNER_STAGE17_DISCOVERY_PUBLICATION_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_DISCOVERY_PUBLICATION_HPP

#include "cpu_prefetch/calibration/native_discovery_capture.hpp"
#include "cpu_prefetch/runner/stage17_fixed_action.hpp"

namespace cpu_prefetch::runner::stage17 {

// Cold serialization of the supplied snapshot, including all cleanup results.
// Invoke with the returned native result for final evidence; this does not
// infer successful cleanup from a stop code or fill absent observations.
[[nodiscard]] auto
discovery_capture_result_json(const calibration::NativeDiscoveryCaptureResult& result)
    -> protocol::json::Value;

// Cold publication only, while the native capture's mappings remain alive.
// Primary bytes keep their existing codec. Demand vectors use unsigned u64
// little endian with explicit counts/offsets in the control document. The sink
// owns create-exclusive persistence and hashing. This does not admit evidence.
// Exactly seven artifacts, including empty raw payloads for absent phase owners;
// availability and each owner's independent run ID/completeness are explicit.
// Demand order is producer demand, producer issue, consumer demand, consumer
// issue; each vector has its own count/byte offset. Only observed read bytes
// are serialized; null denotes an unobserved value, never numeric zero.
// Environmental paths and retained contents are byte arrays, with no UTF-8
// assumption. Samples retain source-major six-group indices, actual read and
// EOF-probe results, partial prefixes and explicit unattempted states. Raw I/O
// delivery establishes no sensor, page-policy or environmental validity.
//
// Cold heap budget: one primary copy at a time; demand reserves exactly eight
// times the sum of the four retained vector lengths (no growth copies). The
// sink takes ownership and must independently budget any retained payloads.
// JSON tree space scales with retained page/control/TLS/drain rows and the
// captured environmental bytes/read records (one JSON integer per byte); canonical
// text and its final byte copy coexist with that tree transiently. Arena hash
// checks additionally use at most O(capacity) permutation/delta scratch from
// the existing workload API. Caller admits these finite extents beforehand;
// this function is not a watchdog or an allocation-budget enforcement layer.
// On sink failure, prior artifacts remain in sink custody; no retry or rollback.
// The control document observes cleanup only before publication returns. Final
// native cleanup and publication success belong to the returned native result.
[[nodiscard]] auto
publish_discovery_capture(ArtifactSink& sink, std::size_t capture_ordinal,
                          const calibration::NativeDiscoveryPublicationView& view)
    -> protocol::Result<std::vector<ArtifactBinding>>;

} // namespace cpu_prefetch::runner::stage17

#endif
