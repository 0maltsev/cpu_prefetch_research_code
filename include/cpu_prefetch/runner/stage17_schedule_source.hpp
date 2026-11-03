#ifndef CPU_PREFETCH_RUNNER_STAGE17_SCHEDULE_SOURCE_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_SCHEDULE_SOURCE_HPP

#include "cpu_prefetch/protocol/validation.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace cpu_prefetch::runner::stage17 {

// An original accepted-generator u64 big-endian artifact, pinned by the parent
// as a read-only sealed memfd. This does not regenerate a schedule or change its
// source coordinates. The caller separately authenticates provenance/identity.
struct SealedScheduleSourcePlan final {
  std::string artifact_id;
  std::string canonical_sha256;
  std::uint64_t offered_count;
  std::uint64_t source_origin_ticks;
  std::uint64_t source_horizon_ticks;
  // Includes the loaded vector and Result's transient success copy (16*N).
  // The caller also budgets fixed read/hash state and all other retained sources.
  std::uint64_t maximum_vector_bytes;
  std::uint64_t deadline_monotonic_ns;
};

// Cold loading only, before hardware access. Exact size/hash, immutable seals,
// nondecreasing source ticks and [origin,horizon) membership are mandatory.
// Empty schedules are represented by the original empty artifact and its hash.
// Descriptor is borrowed; no offset mutation, close, path lookup or file write.
[[nodiscard]] auto load_sealed_schedule_source(int descriptor,
                                               const SealedScheduleSourcePlan& plan)
    -> protocol::Result<std::vector<std::uint64_t>>;

} // namespace cpu_prefetch::runner::stage17
#endif
