#include "cpu_prefetch/orchestration/precision.hpp"

#include "cpu_prefetch/orchestration/block_planning.hpp"

#include <algorithm>
#include <array>
#include <limits>
#include <set>
#include <string>
#include <utility>

namespace cpu_prefetch::orchestration {
namespace {

template <typename T>
[[nodiscard]] auto fail(protocol::ErrorCategory category, std::string path,
                        std::string rule, std::string message) -> protocol::Result<T> {
  return protocol::Result<T>::failure(
      {category, std::move(path), std::move(rule), std::move(message)});
}

[[nodiscard]] auto candidate_equal(const protocol::H3Candidate& left,
                                   const protocol::H3Candidate& right) noexcept
    -> bool {
  return left.package == right.package &&
         left.requested_hardware_state == right.requested_hardware_state;
}

[[nodiscard]] auto candidate_valid(const protocol::H3Candidate& candidate) -> bool {
  const auto candidates = h3_candidates();
  return std::any_of(candidates.begin(), candidates.end(),
                     [&](const protocol::H3Candidate& expected) {
                       return candidate_equal(candidate, expected);
                     });
}

[[nodiscard]] auto opaque(std::string_view value) noexcept -> bool {
  return !value.empty() && value.find('/') == std::string_view::npos &&
         value.find('\\') == std::string_view::npos;
}

[[nodiscard]] auto evidence_valid(const protocol::ArtifactReference& evidence) -> bool {
  return opaque(evidence.artifact_id.value());
}

} // namespace

auto h1_contrast_ids() -> std::vector<std::string_view> {
  return {"H1-SW-R1", "H1-SW-R2", "H1-HQ", "H1-HS-R1",
          "H1-HS-R2", "H1-HS-L1", "H1-R12"};
}

auto h2_contrast_ids() -> std::vector<std::string_view> {
  return {"H2-P-H",    "H2-P-R1",   "H2-P-R2",   "H2-P-L1",   "H2-W12-H",
          "H2-W12-R1", "H2-W12-R2", "H2-W12-L1", "H2-W23-H",  "H2-W23-R1",
          "H2-W23-R2", "H2-W23-L1", "H2-A12-H",  "H2-A12-R1", "H2-A12-R2",
          "H2-A12-L1", "H2-A23-H",  "H2-A23-R1", "H2-A23-R2", "H2-A23-L1"};
}

auto h3_contexts() -> std::vector<protocol::H3Context> {
  return {protocol::H3Context::near_l2_l050,
          protocol::H3Context::near_llc_l050,
          protocol::H3Context::near_beyond_llc_l050,
          protocol::H3Context::far_l2_l050,
          protocol::H3Context::far_llc_l050,
          protocol::H3Context::far_beyond_llc_l050};
}

auto h3_candidates() -> std::vector<protocol::H3Candidate> {
  constexpr std::array packages{protocol::QueuePackage::r0, protocol::QueuePackage::r1,
                                protocol::QueuePackage::r2, protocol::QueuePackage::l0,
                                protocol::QueuePackage::l1};
  constexpr std::array states{protocol::RequestedHardwareState::h0,
                              protocol::RequestedHardwareState::h1};
  std::vector<protocol::H3Candidate> result;
  result.reserve(kH3CandidateCount);
  for (const auto package : packages) {
    for (const auto state : states) {
      result.push_back({package, state});
    }
  }
  return result;
}

auto h3_training_pairs() -> std::vector<H3Comparison> {
  const auto contexts = h3_contexts();
  const auto candidates = h3_candidates();
  std::vector<H3Comparison> result;
  result.reserve(kH3TrainingPairCount);
  for (const auto context : contexts) {
    for (std::size_t left = 0U; left < candidates.size(); ++left) {
      for (std::size_t right = left + 1U; right < candidates.size(); ++right) {
        result.push_back({context, candidates[left], candidates[right]});
      }
    }
  }
  return result;
}

auto h3_validation_family() -> std::vector<H3Comparison> {
  const auto contexts = h3_contexts();
  const auto candidates = h3_candidates();
  std::vector<H3Comparison> result;
  result.reserve(kH3ValidationFamilyCount);
  for (const auto context : contexts) {
    for (std::size_t left = 0U; left < candidates.size(); ++left) {
      for (std::size_t right = 0U; right < candidates.size(); ++right) {
        if (left != right) {
          result.push_back({context, candidates[left], candidates[right]});
        }
      }
    }
  }
  return result;
}

auto h3_reported_comparisons(
    const std::map<protocol::H3Context, protocol::H3Candidate>& selections)
    -> protocol::Result<std::vector<H3Comparison>> {
  const auto contexts = h3_contexts();
  const auto candidates = h3_candidates();
  if (selections.size() != contexts.size() ||
      !std::all_of(contexts.begin(), contexts.end(), [&](auto context) {
        const auto iterator = selections.find(context);
        return iterator != selections.end() && candidate_valid(iterator->second);
      })) {
    return fail<std::vector<H3Comparison>>(
        protocol::ErrorCategory::cross_field, "$/h3_selections",
        "H3-EXACT-SIX-SELECTIONS",
        "reporting requires one registered candidate for each of six stable contexts");
  }
  std::vector<H3Comparison> result;
  result.reserve(kH3ReportedComparisonCount);
  for (const auto context : contexts) {
    const auto& selected = selections.at(context);
    for (const auto& alternative : candidates) {
      if (!candidate_equal(selected, alternative)) {
        result.push_back({context, selected, alternative});
      }
    }
  }
  return protocol::Result<std::vector<H3Comparison>>::success(result);
}

auto evaluate_precision_plan(const PrecisionPlanInput& input)
    -> protocol::Result<PrecisionResult> {
  if (!input.counts || !input.evidence) {
    return protocol::Result<PrecisionResult>::success(
        {PrecisionState::not_evaluated,
         std::nullopt,
         std::nullopt,
         std::nullopt,
         {"prospective precision counts and immutable evidence are required"}});
  }
  const auto& counts = *input.counts;
  const auto& evidence = *input.evidence;
  const std::array references{
      evidence.delta_star,         evidence.bootstrap_configuration,
      evidence.h1_sizing,          evidence.h2_sizing,
      evidence.h3_training_sizing, evidence.h3_validation_sizing};
  std::set<std::string> reference_ids;
  if (!std::all_of(references.begin(), references.end(), [&](const auto& value) {
        return evidence_valid(value) &&
               reference_ids.insert(std::string(value.artifact_id.value())).second;
      })) {
    return fail<PrecisionResult>(protocol::ErrorCategory::missing_evidence,
                                 "$/precision/evidence", "PRECISION-EVIDENCE-EXACT",
                                 "delta, bootstrap, separate H1/H2, and separate H3 "
                                 "sizing evidence must be distinct and immutable");
  }
  if (evidence.input_artifacts.empty()) {
    return fail<PrecisionResult>(
        protocol::ErrorCategory::missing_evidence, "$/precision/input_artifacts",
        "PRECISION-PROSPECTIVE-SOURCES",
        "prospective sizing must name treatment-blind input evidence");
  }
  for (std::size_t index = 0U; index < evidence.input_artifacts.size(); ++index) {
    const auto& source = evidence.input_artifacts[index];
    if (!evidence_valid(source.artifact) ||
        (source.access_class != protocol::AccessClass::treatment_blind &&
         source.access_class != protocol::AccessClass::public_protocol &&
         source.access_class != protocol::AccessClass::platform_evidence)) {
      return fail<PrecisionResult>(protocol::ErrorCategory::cross_field,
                                   "$/precision/input_artifacts/" +
                                       std::to_string(index),
                                   "PRECISION-NO-OUTCOME-ACCESS",
                                   "training, validation, or unsealed outcomes cannot "
                                   "size any precision family");
    }
  }
  if (counts.r_h1 < 20U || counts.r_h2 < 20U || counts.rtrain < 12U ||
      counts.rval < 8U) {
    return fail<PrecisionResult>(
        protocol::ErrorCategory::out_of_range, "$/precision/counts", "PRECISION-MINIMA",
        "H1/H2 require at least 20 blocks, H3 training 12, and validation 8");
  }
  if (counts.r12 != std::max(counts.r_h1, counts.r_h2)) {
    return fail<PrecisionResult>(
        protocol::ErrorCategory::cross_field, "$/precision/counts/r12", "PRECISION-R12",
        "R12 must equal max(R_H1,R_H2) with separate families");
  }
  if (counts.rtrain > std::numeric_limits<std::uint64_t>::max() - counts.rval) {
    return fail<PrecisionResult>(protocol::ErrorCategory::out_of_range,
                                 "$/precision/counts", "PRECISION-COUNT-OVERFLOW",
                                 "Rtrain+Rval overflows u64");
  }
  const auto train_and_validation = counts.rtrain + counts.rval;
  const auto expected_total = std::max(counts.r12, train_and_validation);
  if (counts.rtotal != expected_total) {
    return fail<PrecisionResult>(
        protocol::ErrorCategory::cross_field, "$/precision/counts/rtotal",
        "PRECISION-RTOTAL",
        "Rtotal must equal max(R12,Rtrain+Rval) without outcome-based resizing");
  }
  if (counts.rtotal >
          std::numeric_limits<std::uint64_t>::max() / kStageACellsPerBlock ||
      counts.nruns != counts.rtotal * kStageACellsPerBlock) {
    return fail<PrecisionResult>(protocol::ErrorCategory::cross_field,
                                 "$/precision/counts/nruns", "PRECISION-NRUNS",
                                 "Nruns must equal checked 180*Rtotal");
  }
  const RoleCounts roles{
      counts.rtrain, counts.rval,
      counts.r12 > train_and_validation ? counts.r12 - train_and_validation : 0U};
  if (counts.r_h1 > 30U || counts.r_h2 > 30U) {
    return protocol::Result<PrecisionResult>::success(
        {PrecisionState::infeasible,
         counts,
         roles,
         evidence,
         {"an H1 or H2 requirement exceeds the frozen go/no-go ceiling of 30"}});
  }
  if (h1_contrast_ids().size() != kH1ContrastCount ||
      h2_contrast_ids().size() != kH2ContrastCount ||
      h3_training_pairs().size() != kH3TrainingPairCount ||
      h3_validation_family().size() != kH3ValidationFamilyCount) {
    return fail<PrecisionResult>(
        protocol::ErrorCategory::cross_field, "$/precision/registries",
        "PRECISION-REGISTRY-INTERNAL", "registered family cardinality is inconsistent");
  }
  return protocol::Result<PrecisionResult>::success(
      {PrecisionState::resolved, counts, roles, evidence, {}});
}

} // namespace cpu_prefetch::orchestration
