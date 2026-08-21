#ifndef CPU_PREFETCH_ANALYSIS_ANALYSIS_HPP
#define CPU_PREFETCH_ANALYSIS_ANALYSIS_HPP

#include "cpu_prefetch/orchestration/access.hpp"
#include "cpu_prefetch/orchestration/block_planning.hpp"
#include "cpu_prefetch/orchestration/precision.hpp"
#include "cpu_prefetch/protocol/model.hpp"
#include "cpu_prefetch/reconciliation/reconciliation.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <cstddef>
#include <cstdint>
#include <map>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::analysis {

inline constexpr std::string_view kAnalysisProfile =
    "STAGE-A-OFFLINE-ANALYSIS-SYNTHETIC-v1";
inline constexpr std::string_view kRunInputSchema = "STAGE15-SYNTHETIC-RUN-INPUT-v1";
inline constexpr std::string_view kReportSchema = "STAGE15-ANALYSIS-REPORT-v1";
inline constexpr std::string_view kSelectionSchema = "STAGE15-H3-SELECTION-RECORD-v1";
inline constexpr std::string_view kBootstrapProfile =
    "COMPLETE-BLOCK-PHILOX4X32-10-MAXT-ICDF95-v1";
inline constexpr std::string_view kSyntheticLatencyEncoding =
    "SYNTHETIC-RLE-LATENCY-TICKS-v1";

enum class AnalysisStage : std::uint8_t {
  artifact_validation,
  reconciliation_verification,
  interval_derivation,
  run_gates,
  run_summaries,
  complete_blocks,
  h3_training,
  selection_freeze,
  validation_unseal,
  h3_validation,
  h3_evaluation,
  h1h2_release,
  h1h2_analysis,
  reporting,
};

enum class FamilyKind : std::uint8_t {
  h1_two_sided,
  h2_two_sided,
  h3_training_standard_error,
  h3_validation_one_sided,
};

enum class InferenceState : std::uint8_t { estimable, blocked };
enum class PracticalConclusion : std::uint8_t {
  practically_lower,
  practically_higher,
  practically_equivalent,
  inconclusive,
};

struct ImmutableArtifact final {
  protocol::ProtocolVersion protocol_version;
  std::string schema_version;
  protocol::ArtifactReference reference;
  std::vector<std::byte> bytes;
  bool finalized;
};

// This compact encoding exists only to create analytically known Stage 15
// fixtures. Production analysis must decode the immutable joined stream.
struct WeightedLatency final {
  std::uint64_t latency_ticks;
  std::uint64_t multiplicity;
  auto operator==(const WeightedLatency&) const -> bool = default;
};

struct RawReconciliationInput final {
  std::vector<protocol::ProducerRecord> producer_rows;
  std::vector<protocol::ConsumerRecord> consumer_rows;
  std::vector<std::uint64_t> expected_record_indices;
};

struct SyntheticDiagnosticSeries final {
  std::vector<WeightedLatency> producer_lateness;
  std::vector<WeightedLatency> enqueue_service;
  std::vector<WeightedLatency> admission_delay;
  std::vector<WeightedLatency> queue_residence;
  std::vector<WeightedLatency> dequeue_service;
  std::vector<WeightedLatency> post_dequeue_delivery;
  std::vector<WeightedLatency> consumer_action;
};

struct SyntheticRunInput final {
  protocol::ProtocolVersion protocol_version;
  std::string schema_version;
  protocol::RunId run_id;
  protocol::BlockId block_id;
  protocol::BlockRole block_role;
  std::uint64_t cell_ordinal;
  protocol::QueuePackage package;
  protocol::RequestedHardwareState hardware_state;
  protocol::Placement placement;
  protocol::WorkingSetClass working_set;
  protocol::LoadLevel load;
  protocol::RunValidity validity;
  std::uint64_t offered_count;
  std::uint64_t attempted_count;
  std::uint64_t accepted_count;
  std::uint64_t full_count;
  std::uint64_t consumed_count;
  std::uint64_t final_occupancy;
  std::uint64_t raw_sample_count;
  std::uint64_t n_eff_p999;
  std::uint64_t measurement_horizon_ticks;
  std::vector<WeightedLatency> end_to_end_latencies;
  SyntheticDiagnosticSeries diagnostics;
  protocol::ArtifactReference manifest_artifact;
  protocol::ArtifactReference joined_artifact;
  protocol::ArtifactReference join_audit_artifact;
  std::optional<protocol::ArtifactReference> failure_artifact;
  std::optional<RawReconciliationInput> raw_reconciliation;
  bool prior_stage12_validation_passed;
};

struct BlockInput final {
  protocol::BlockPlan plan;
  orchestration::BlockSeedCatalog seed_catalog;
  protocol::ArtifactReference plan_artifact;
  bool active_primary;
  bool stage14_cross_record_validation_passed;
  bool replacement_budget_validation_passed;
};

struct ProspectiveCandidate final {
  std::uint64_t complete_block_count;
  std::vector<double> widths;
};

struct ProspectiveFamilyInput final {
  FamilyKind family;
  protocol::ArtifactReference sizing_artifact;
  std::vector<ProspectiveCandidate> candidates;
};

struct ProspectivePrecisionInput final {
  ProspectiveFamilyInput h1;
  ProspectiveFamilyInput h2;
  ProspectiveFamilyInput h3_training;
  ProspectiveFamilyInput h3_validation;
};

struct BootstrapConfiguration final {
  std::string profile;
  std::string rng_algorithm_version;
  protocol::SeedId seed_id;
  workload::PhiloxKey key;
  std::uint64_t replicates;
};

struct SoftwareVersions final {
  std::string implementation_revision;
  std::string compiler;
  std::string standard_library;
};

struct AnalysisConfiguration final {
  protocol::ProtocolVersion protocol_version;
  std::string analysis_profile;
  double delta_star;
  BootstrapConfiguration bootstrap;
  ProspectivePrecisionInput precision;
  orchestration::ProspectiveCounts expected_counts;
  protocol::ArtifactReference configuration_artifact;
  SoftwareVersions software;
};

class OutcomeAccessGrant final {
public:
  [[nodiscard]] static auto
  from_stage14(const orchestration::AccessLedgerResult& ledger,
               orchestration::OutcomeDomain domain,
               std::span<const protocol::BlockPlan> affected_blocks,
               protocol::ArtifactReference access_record)
      -> protocol::Result<OutcomeAccessGrant>;

  [[nodiscard]] auto domain() const noexcept -> orchestration::OutcomeDomain {
    return domain_;
  }
  [[nodiscard]] auto state() const noexcept -> protocol::AccessState { return state_; }
  [[nodiscard]] auto affected_block_ids() const noexcept
      -> std::span<const protocol::BlockId> {
    return affected_block_ids_;
  }
  [[nodiscard]] auto access_record() const noexcept
      -> const protocol::ArtifactReference& {
    return access_record_;
  }

private:
  OutcomeAccessGrant(orchestration::OutcomeDomain domain, protocol::AccessState state,
                     std::vector<protocol::BlockId> affected_block_ids,
                     protocol::ArtifactReference access_record)
      : domain_(domain), state_(state),
        affected_block_ids_(std::move(affected_block_ids)),
        access_record_(std::move(access_record)) {}

  orchestration::OutcomeDomain domain_;
  protocol::AccessState state_;
  std::vector<protocol::BlockId> affected_block_ids_;
  protocol::ArtifactReference access_record_;
};

struct AnalysisInput final {
  orchestration::RoleNamespaceRegistry namespaces;
  std::vector<BlockInput> blocks;
  std::vector<SyntheticRunInput> runs;
  std::vector<ImmutableArtifact> artifacts;
  AnalysisConfiguration configuration;
  OutcomeAccessGrant training_access;
  OutcomeAccessGrant validation_access;
  OutcomeAccessGrant h1h2_access;
};

struct RunQuantiles final {
  std::uint64_t p50;
  std::uint64_t p90;
  std::uint64_t p99;
  std::uint64_t p999;
  std::optional<std::uint64_t> p9999;
  std::uint64_t maximum;
};

struct ExactRatio final {
  std::uint64_t numerator;
  std::uint64_t denominator;
};

struct RunSummary final {
  protocol::RunId run_id;
  protocol::BlockId block_id;
  protocol::BlockRole block_role;
  protocol::QueuePackage package;
  protocol::RequestedHardwareState hardware_state;
  protocol::Placement placement;
  protocol::WorkingSetClass working_set;
  protocol::LoadLevel load;
  protocol::RunValidity validity;
  protocol::GateStatus zero_loss;
  protocol::GateStatus effective_tail;
  protocol::ConfirmatoryEstimability estimability;
  std::vector<protocol::ConfirmatoryBlocker> blockers;
  RunQuantiles quantiles;
  RunQuantiles producer_lateness_quantiles;
  RunQuantiles enqueue_service_quantiles;
  RunQuantiles admission_delay_quantiles;
  RunQuantiles queue_residence_quantiles;
  RunQuantiles dequeue_service_quantiles;
  RunQuantiles post_dequeue_delivery_quantiles;
  RunQuantiles consumer_action_quantiles;
  protocol::ExactRate consumed_throughput;
  ExactRatio full_rate;
  std::uint64_t final_occupancy;
  double log_p999;
};

struct CellResponse final {
  protocol::QueuePackage package;
  protocol::RequestedHardwareState hardware_state;
  protocol::Placement placement;
  protocol::WorkingSetClass working_set;
  protocol::LoadLevel load;
  double log_p999;
};

struct CompleteBlockResponse final {
  protocol::BlockId block_id;
  protocol::BlockRole role;
  std::vector<CellResponse> cells;
};

struct SimultaneousInterval final {
  std::string stable_id;
  double estimate;
  double standard_error;
  double lower;
  double upper;
  PracticalConclusion conclusion;
};

struct MaxTResult final {
  std::string family_id;
  bool one_sided;
  std::uint64_t bootstrap_replicates;
  double critical_value;
  std::vector<SimultaneousInterval> intervals;
};

struct H3SelectionRecord final {
  std::string schema_version;
  std::map<protocol::H3Context, protocol::H3Candidate> selections;
  std::vector<protocol::ArtifactReference> training_sources;
  std::string canonical_json;
  protocol::Sha256 record_sha256;
};

struct H3ValidationResult final {
  InferenceState state;
  std::optional<MaxTResult> comparisons;
  bool all_upper_limits_below_delta;
  std::vector<std::string> blockers;
};

struct StageReceipt final {
  AnalysisStage stage;
  std::string version;
  std::vector<protocol::ArtifactReference> inputs;
};

struct AnalysisOutput final {
  InferenceState state;
  std::vector<RunSummary> run_summaries;
  std::vector<CompleteBlockResponse> primary_blocks;
  std::optional<MaxTResult> h1;
  std::optional<MaxTResult> h2;
  std::optional<H3SelectionRecord> selection;
  std::optional<H3ValidationResult> h3;
  std::vector<StageReceipt> stages;
  std::string machine_report_json;
  std::string human_report_markdown;
  protocol::Sha256 configuration_sha256;
  protocol::Sha256 output_sha256;
};

[[nodiscard]] auto
exact_inverse_ecdf_quantile(std::span<const WeightedLatency> sorted_values,
                            std::uint64_t numerator, std::uint64_t denominator)
    -> protocol::Result<std::uint64_t>;

[[nodiscard]] auto summarize_run(const SyntheticRunInput& run,
                                 std::span<const ImmutableArtifact> artifacts)
    -> protocol::Result<RunSummary>;

[[nodiscard]] auto stage_a_design_rank() -> std::size_t;

[[nodiscard]] auto h1_block_contrasts(const CompleteBlockResponse& block)
    -> protocol::Result<std::vector<double>>;
[[nodiscard]] auto h2_block_contrasts(const CompleteBlockResponse& block)
    -> protocol::Result<std::vector<double>>;

[[nodiscard]] auto
evaluate_prospective_precision(const ProspectivePrecisionInput& input,
                               double delta_star)
    -> protocol::Result<orchestration::ProspectiveCounts>;

[[nodiscard]] auto
two_sided_max_t(std::string family_id, std::span<const std::string_view> stable_ids,
                std::span<const std::vector<double>> complete_block_contrasts,
                const BootstrapConfiguration& bootstrap, double delta_star)
    -> protocol::Result<MaxTResult>;

[[nodiscard]] auto
select_h3_training(std::span<const CompleteBlockResponse> training_blocks,
                   std::span<const protocol::ArtifactReference> training_sources)
    -> protocol::Result<H3SelectionRecord>;

[[nodiscard]] auto
evaluate_h3_validation(std::span<const CompleteBlockResponse> validation_blocks,
                       const H3SelectionRecord& selection,
                       const BootstrapConfiguration& bootstrap, double delta_star)
    -> protocol::Result<H3ValidationResult>;

[[nodiscard]] auto canonical_configuration(const AnalysisConfiguration& configuration)
    -> protocol::Result<std::string>;
[[nodiscard]] auto canonical_synthetic_run(const SyntheticRunInput& run)
    -> protocol::Result<std::string>;
[[nodiscard]] auto
canonical_synthetic_latency_payload(const protocol::RunId& run_id,
                                    std::span<const WeightedLatency> latencies)
    -> protocol::Result<std::string>;

[[nodiscard]] auto run_synthetic_analysis(const AnalysisInput& input)
    -> protocol::Result<AnalysisOutput>;

} // namespace cpu_prefetch::analysis

#endif // CPU_PREFETCH_ANALYSIS_ANALYSIS_HPP
