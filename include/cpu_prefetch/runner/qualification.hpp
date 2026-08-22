#ifndef CPU_PREFETCH_RUNNER_QUALIFICATION_HPP
#define CPU_PREFETCH_RUNNER_QUALIFICATION_HPP

#include "cpu_prefetch/protocol/model.hpp"
#include "cpu_prefetch/runner/runner.hpp"

#include <array>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::runner {

inline constexpr std::string_view kQualificationEvidenceSchemaVersion =
    "cpu-prefetch-qualification-evidence/1";

enum class QualificationEvidenceKind : std::uint8_t {
  selected_pair_clock,
  runtime_atomic_layout,
  actual_cpu_migration,
  address_residency,
  software_prefetch_mapping,
};

[[nodiscard]] auto to_string(QualificationEvidenceKind kind) noexcept
    -> std::string_view;

struct QualificationSource final {
  std::string artifact_id;
  std::string sha256;
};

struct QualificationIdentity final {
  std::string artifact_id;
  std::string stand_id;
  std::string binding_id;
  std::string source_revision;
  std::string binary_sha256;
  std::string captured_at_utc;
  WorkerPair workers;
  std::vector<QualificationSource> sources;
};

struct QualificationArtifact final {
  QualificationEvidenceKind kind;
  bool eligible;
  std::string canonical_json;
};

struct SelectedPairClockInput final {
  std::array<std::uint64_t, 2> prime_read_counts;
  std::array<std::uint64_t, 2> delta_counts;
  std::uint64_t traced_call_count;
  std::uint64_t traced_syscall_count;
  std::uint64_t producer_to_consumer_window_count;
  std::uint64_t consumer_to_producer_window_count;
  std::uint64_t exchanges_per_window;
  bool per_core_evaluator_passed;
  bool cross_core_evaluator_passed;
  bool before_block_repeat;
};

struct RuntimeAtomicLayoutInput final {
  std::uint64_t pointer_atomic_width_bytes;
  std::uint64_t pointer_atomic_alignment_bytes;
  std::uint64_t termination_atomic_width_bytes;
  std::uint64_t termination_atomic_alignment_bytes;
  std::uint64_t cache_line_bytes;
  bool pointer_atomic_runtime_lock_free;
  bool termination_atomic_runtime_lock_free;
  bool queue_layout_passed;
  bool ownership_lines_separated;
  bool termination_dedicated_line;
};

struct ActualCpuMigrationInput final {
  std::uint64_t producer_sample_count;
  std::uint64_t consumer_sample_count;
  std::uint32_t producer_first_cpu;
  std::uint32_t producer_last_cpu;
  std::uint32_t consumer_first_cpu;
  std::uint32_t consumer_last_cpu;
  std::uint64_t producer_migration_count;
  std::uint64_t consumer_migration_count;
  bool producer_singleton_affinity;
  bool consumer_singleton_affinity;
};

struct RegionResidencyInput final {
  std::string region;
  std::uint32_t expected_node;
  std::uint64_t before_page_count;
  std::uint64_t during_page_count;
  std::uint64_t after_page_count;
  std::uint64_t unavailable_page_count;
  std::uint64_t wrong_node_page_count;
  std::uint64_t migrated_page_count;
};

struct AddressResidencyInput final {
  std::string mechanism_id;
  RegionResidencyInput shared_event_and_queue_pages;
  RegionResidencyInput producer_private_pages;
  RegionResidencyInput consumer_private_pages;
};

struct SoftwarePrefetchMappingInput final {
  std::string mapping_id;
  SoftwarePrefetchCapabilityObservation producer_capability;
  SoftwarePrefetchCapabilityObservation consumer_capability;
  bool gcc_codegen_passed;
  bool clang_codegen_passed;
  bool gnu_objdump_passed;
  bool llvm_objdump_passed;
};

[[nodiscard]] auto
make_selected_pair_clock_evidence(const QualificationIdentity& identity,
                                  const SelectedPairClockInput& input)
    -> protocol::Result<QualificationArtifact>;
[[nodiscard]] auto
make_runtime_atomic_layout_evidence(const QualificationIdentity& identity,
                                    const RuntimeAtomicLayoutInput& input)
    -> protocol::Result<QualificationArtifact>;
[[nodiscard]] auto
make_actual_cpu_migration_evidence(const QualificationIdentity& identity,
                                   const ActualCpuMigrationInput& input)
    -> protocol::Result<QualificationArtifact>;
[[nodiscard]] auto
make_address_residency_evidence(const QualificationIdentity& identity,
                                const AddressResidencyInput& input)
    -> protocol::Result<QualificationArtifact>;
[[nodiscard]] auto
make_software_prefetch_mapping_evidence(const QualificationIdentity& identity,
                                        const SoftwarePrefetchMappingInput& input)
    -> protocol::Result<QualificationArtifact>;

} // namespace cpu_prefetch::runner

#endif // CPU_PREFETCH_RUNNER_QUALIFICATION_HPP
