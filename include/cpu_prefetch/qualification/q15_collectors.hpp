#ifndef CPU_PREFETCH_QUALIFICATION_Q15_COLLECTORS_HPP
#define CPU_PREFETCH_QUALIFICATION_Q15_COLLECTORS_HPP

#include "cpu_prefetch/platform/q15_runtime.hpp"
#include "cpu_prefetch/runner/qualification.hpp"
#include "cpu_prefetch/timing/qualification.hpp"

#include <array>
#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::qualification {

inline constexpr std::string_view kQ15CollectorEvidenceSchemaVersion =
    "cpu-prefetch-q15-collector-evidence/1";

enum class Q15CollectorKind : std::uint8_t {
  clock,
  atomic_layout,
  actual_cpu_migration,
  address_residency,
  software_prefetch,
  msr_prestate,
  msr_readback,
};

struct Q15CollectorContract final {
  Q15CollectorKind kind;
  std::string_view collector_id;
  std::string_view evidence_kind;
};

inline constexpr std::array<Q15CollectorContract, 7U> kQ15CollectorContracts{{
    {Q15CollectorKind::clock, "Q15-CLOCK-COLLECTOR-v1", "SELECTED_PAIR_CLOCK"},
    {Q15CollectorKind::atomic_layout, "Q15-ATOMIC-LAYOUT-COLLECTOR-v1",
     "RUNTIME_ATOMIC_LAYOUT"},
    {Q15CollectorKind::actual_cpu_migration, "Q15-ACTUAL-CPU-MIGRATION-COLLECTOR-v1",
     "ACTUAL_CPU_MIGRATION"},
    {Q15CollectorKind::address_residency, "Q15-ADDRESS-RESIDENCY-COLLECTOR-v1",
     "ADDRESS_RESIDENCY"},
    {Q15CollectorKind::software_prefetch, "Q15-SOFTWARE-PREFETCH-COLLECTOR-v1",
     "SOFTWARE_PREFETCH_MAPPING"},
    {Q15CollectorKind::msr_prestate, "Q15-MSR-PRESTATE-COLLECTOR-v1",
     "HARDWARE_PREFETCH_PRESTATE"},
    {Q15CollectorKind::msr_readback, "Q15-MSR-READBACK-COLLECTOR-v1",
     "HARDWARE_PREFETCH_READBACK"},
}};

// Non-inline registry seam used by the qualification executable self-test so
// the complete collector implementation is linked into the no-authority tool.
[[nodiscard]] auto q15_collector_registry() noexcept
    -> std::span<const Q15CollectorContract>;

struct Q15CollectorArtifact final {
  Q15CollectorKind kind;
  std::string collector_id;
  bool complete;
  bool eligible;
  std::string canonical_json;
};

struct Q15ClockRawObservation final {
  timing::StaticClockEvidenceInput static_observation;
  std::array<timing::PerCoreQualificationInput, 2U> per_core;
  timing::CrossCorePairInput cross_core;
  std::uint64_t capture_completed_monotonic_nanoseconds;
  std::uint64_t block_repeat_not_before_monotonic_nanoseconds;
};

[[nodiscard]] auto collect_q15_clock(const runner::QualificationIdentity& identity,
                                     const Q15ClockRawObservation& observation)
    -> protocol::Result<Q15CollectorArtifact>;

// Directly constructs and inspects the linked queue, ring queue, and
// termination publication layouts. No caller-supplied pass boolean exists.
[[nodiscard]] auto
collect_q15_atomic_layout(const runner::QualificationIdentity& identity,
                          std::size_t cache_line_bytes)
    -> protocol::Result<Q15CollectorArtifact>;

struct Q15CpuSampleSeries final {
  std::uint32_t expected_cpu;
  bool singleton_affinity_readback;
  std::span<const std::uint32_t> operation_entry_exit_cpus;
};

[[nodiscard]] auto collect_q15_actual_cpu_migration(
    const runner::QualificationIdentity& identity, const Q15CpuSampleSeries& producer,
    const Q15CpuSampleSeries& consumer) -> protocol::Result<Q15CollectorArtifact>;

struct Q15RegionResidencySeries final {
  std::string region;
  std::uint32_t expected_node;
  platform::Q15ResidencySnapshot before;
  platform::Q15ResidencySnapshot during;
  platform::Q15ResidencySnapshot after;
};

[[nodiscard]] auto
collect_q15_address_residency(const runner::QualificationIdentity& identity,
                              std::span<const Q15RegionResidencySeries> regions)
    -> protocol::Result<Q15CollectorArtifact>;

struct Q15SoftwarePrefetchReports final {
  std::string_view gcc_report_json;
  std::string_view clang_report_json;
};

[[nodiscard]] auto collect_q15_software_prefetch(
    const runner::QualificationIdentity& identity,
    platform::Q15PlatformOperations& platform_operations,
    runner::CurrentCpuSoftwarePrefetchCapabilityBackend& capability_backend,
    const Q15SoftwarePrefetchReports& reports)
    -> protocol::Result<Q15CollectorArtifact>;

[[nodiscard]] auto
collect_q15_msr_prestate(const runner::QualificationIdentity& identity,
                         platform::HardwarePrefetchMsrBackend& reader)
    -> protocol::Result<Q15CollectorArtifact>;

enum class Q15MsrReadbackPhase : std::uint8_t { h1_apply, h0_restore };

[[nodiscard]] auto
collect_q15_msr_readback(const runner::QualificationIdentity& identity,
                         platform::HardwarePrefetchMsrBackend& independent_reader,
                         std::uint32_t cpu, std::uint64_t expected_complete_value,
                         Q15MsrReadbackPhase phase, std::string_view writer_identity,
                         std::string_view auditor_identity)
    -> protocol::Result<Q15CollectorArtifact>;

} // namespace cpu_prefetch::qualification

#endif // CPU_PREFETCH_QUALIFICATION_Q15_COLLECTORS_HPP
