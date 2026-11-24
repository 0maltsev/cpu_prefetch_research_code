#ifndef CPU_PREFETCH_RUNNER_STAGE17_FORMAL_FAMILY_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_FORMAL_FAMILY_HPP

#include "cpu_prefetch/runner/stage17_fixed_action.hpp"

#include <optional>

namespace cpu_prefetch::runner::stage17 {

struct FormalCaptureBudget final {
  std::uint64_t watchdog_ns;
  std::uint64_t memory_bytes;
  std::uint64_t metadata_output_bytes;
  std::uint64_t max_output_bytes;
};
struct FormalStorageBudget final {
  std::string program_id;
  std::string implementation_profile_sha256;
  std::string program_scope_sha256;
  std::uint64_t broker_address_space_bytes;
  std::uint64_t per_capture_archive_ns;
  std::uint64_t archive_staging_bytes;
  std::uint64_t capture_workspace_overhead_bytes;
  std::uint64_t checkpoint_bytes;
  std::uint64_t analysis_capture_workspace_bytes;
};
struct FormalFamilyBudget final {
  std::vector<FormalCaptureBudget> captures;
  std::uint64_t watchdog_ns;
  std::uint64_t memory_bytes;
  std::uint64_t metadata_output_bytes;
  std::uint64_t max_output_bytes;
  std::uint64_t required_free_disk_bytes;
  std::optional<FormalStorageBudget> storage;
};

// Pure cold family check, before hardware access. Native capture parsers must
// separately validate every layout and monitoring input before any invocation.
// A valid declaration is not resource availability, qualification or authority.
[[nodiscard]] auto validate_formal_family(FixedAction action,
                                          const protocol::json::Value::Object& plan,
                                          std::string_view expected_source_revision)
    -> protocol::Result<FormalFamilyBudget>;

} // namespace cpu_prefetch::runner::stage17
#endif
