#ifndef CPU_PREFETCH_ORCHESTRATION_PRECISION_HPP
#define CPU_PREFETCH_ORCHESTRATION_PRECISION_HPP

#include "cpu_prefetch/protocol/model.hpp"

#include <cstddef>
#include <cstdint>
#include <map>
#include <optional>
#include <string_view>
#include <vector>

namespace cpu_prefetch::orchestration {

inline constexpr std::size_t kH1ContrastCount = 7U;
inline constexpr std::size_t kH2ContrastCount = 20U;
inline constexpr std::size_t kH3ContextCount = 6U;
inline constexpr std::size_t kH3CandidateCount = 10U;
inline constexpr std::size_t kH3TrainingPairCount = 270U;
inline constexpr std::size_t kH3ValidationFamilyCount = 540U;
inline constexpr std::size_t kH3ReportedComparisonCount = 54U;
inline constexpr std::string_view kH3SelectionRuleId =
    "H3-MEAN-LOG-P999-MIN-CANDIDATE-ORDER-v1";

enum class PrecisionState : std::uint8_t {
  not_evaluated,
  resolved,
  infeasible,
};

struct ProspectiveCounts final {
  std::uint64_t r_h1;
  std::uint64_t r_h2;
  std::uint64_t r12;
  std::uint64_t rtrain;
  std::uint64_t rval;
  std::uint64_t rtotal;
  std::uint64_t nruns;
};

struct ProspectivePrecisionEvidence final {
  protocol::ArtifactReference delta_star;
  protocol::ArtifactReference bootstrap_configuration;
  protocol::ArtifactReference h1_sizing;
  protocol::ArtifactReference h2_sizing;
  protocol::ArtifactReference h3_training_sizing;
  protocol::ArtifactReference h3_validation_sizing;
  std::vector<protocol::AccessInputArtifact> input_artifacts;
};

struct PrecisionPlanInput final {
  std::optional<ProspectiveCounts> counts;
  std::optional<ProspectivePrecisionEvidence> evidence;
};

struct RoleCounts final {
  std::uint64_t h3_train;
  std::uint64_t h3_validation;
  std::uint64_t h1h2_supplemental;
};

struct PrecisionResult final {
  PrecisionState state;
  std::optional<ProspectiveCounts> counts;
  std::optional<RoleCounts> role_counts;
  std::optional<ProspectivePrecisionEvidence> evidence;
  std::vector<std::string> blockers;
};

struct H3Comparison final {
  protocol::H3Context context;
  protocol::H3Candidate left;
  protocol::H3Candidate right;
};

[[nodiscard]] auto h1_contrast_ids() -> std::vector<std::string_view>;
[[nodiscard]] auto h2_contrast_ids() -> std::vector<std::string_view>;
[[nodiscard]] auto h3_contexts() -> std::vector<protocol::H3Context>;
[[nodiscard]] auto h3_candidates() -> std::vector<protocol::H3Candidate>;
[[nodiscard]] auto h3_training_pairs() -> std::vector<H3Comparison>;
[[nodiscard]] auto h3_validation_family() -> std::vector<H3Comparison>;
[[nodiscard]] auto h3_reported_comparisons(
    const std::map<protocol::H3Context, protocol::H3Candidate>& selections)
    -> protocol::Result<std::vector<H3Comparison>>;

[[nodiscard]] auto evaluate_precision_plan(const PrecisionPlanInput& input)
    -> protocol::Result<PrecisionResult>;

} // namespace cpu_prefetch::orchestration

#endif // CPU_PREFETCH_ORCHESTRATION_PRECISION_HPP
