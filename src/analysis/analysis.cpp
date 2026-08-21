#include "cpu_prefetch/analysis/analysis.hpp"

#include "cpu_prefetch/protocol/json.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <iomanip>
#include <limits>
#include <map>
#include <numeric>
#include <set>
#include <sstream>
#include <tuple>
#include <utility>

namespace cpu_prefetch::analysis {
namespace {

using JsonArray = protocol::json::Value::Array;
using JsonObject = protocol::json::Value::Object;

template <typename T>
[[nodiscard]] auto fail(protocol::ErrorCategory category, std::string path,
                        std::string rule, std::string message) -> protocol::Result<T> {
  return protocol::Result<T>::failure(
      {category, std::move(path), std::move(rule), std::move(message)});
}

void add(std::vector<protocol::ValidationError>& errors,
         protocol::ErrorCategory category, std::string path, std::string rule,
         std::string message) {
  errors.push_back({category, std::move(path), std::move(rule), std::move(message)});
}

[[nodiscard]] auto unsigned_value(std::uint64_t value) -> protocol::json::Value {
  return protocol::json::Value(protocol::json::Number{
      protocol::json::Number::Kind::unsigned_integer, std::to_string(value), value});
}

[[nodiscard]] auto string_value(std::string value) -> protocol::json::Value {
  return protocol::json::Value(std::move(value));
}

[[nodiscard]] auto bool_value(bool value) -> protocol::json::Value {
  return protocol::json::Value(value);
}

[[nodiscard]] auto canonical(JsonObject object) -> protocol::Result<std::string> {
  return protocol::json::canonicalize(protocol::json::Value(std::move(object)));
}

[[nodiscard]] auto sha_text(std::string_view text) -> protocol::Sha256 {
  const auto bytes = std::span<const std::byte>(
      reinterpret_cast<const std::byte*>(text.data()), text.size());
  const auto digest = workload::sha256(bytes).hex();
  auto parsed = protocol::Sha256::parse(digest, "$/analysis/sha256");
  return std::move(parsed).value();
}

[[nodiscard]] auto artifact_value(const protocol::ArtifactReference& reference)
    -> protocol::json::Value {
  JsonObject object;
  object.emplace("artifact_id",
                 string_value(std::string(reference.artifact_id.value())));
  object.emplace("sha256", string_value(reference.sha256.hex()));
  return protocol::json::Value(std::move(object));
}

[[nodiscard]] auto weighted_values(std::span<const WeightedLatency> values)
    -> protocol::json::Value {
  JsonArray result;
  for (const auto& value : values) {
    JsonObject row;
    row.emplace("latency_ticks", unsigned_value(value.latency_ticks));
    row.emplace("multiplicity", unsigned_value(value.multiplicity));
    result.emplace_back(protocol::json::Value(std::move(row)));
  }
  return protocol::json::Value(std::move(result));
}

[[nodiscard]] auto float_bits(double value) -> std::string {
  std::ostringstream output;
  output << std::hex << std::setfill('0') << std::setw(16)
         << std::bit_cast<std::uint64_t>(value);
  return output.str();
}

[[nodiscard]] auto protocol_name(protocol::ProtocolVersion version)
    -> std::string_view {
  switch (version) {
  case protocol::ProtocolVersion::v2_0_0_pre_1:
    return protocol::kPreviousProtocolVersion;
  case protocol::ProtocolVersion::v2_0_0_pre_2:
    return protocol::kProtocolVersion;
  }
  return {};
}

[[nodiscard]] auto package_name(protocol::QueuePackage package) -> std::string_view {
  switch (package) {
  case protocol::QueuePackage::r0:
    return "R0";
  case protocol::QueuePackage::r1:
    return "R1";
  case protocol::QueuePackage::r2:
    return "R2";
  case protocol::QueuePackage::l0:
    return "L0";
  case protocol::QueuePackage::l1:
    return "L1";
  case protocol::QueuePackage::nblfq_mpsc:
    return "NBLFQ_MPSC";
  case protocol::QueuePackage::not_applicable:
    return "NOT_APPLICABLE";
  }
  return {};
}

[[nodiscard]] auto hardware_name(protocol::RequestedHardwareState state)
    -> std::string_view {
  switch (state) {
  case protocol::RequestedHardwareState::h0:
    return "H0";
  case protocol::RequestedHardwareState::h1:
    return "H1";
  case protocol::RequestedHardwareState::not_applicable:
    return "NOT_APPLICABLE";
  }
  return {};
}

[[nodiscard]] auto role_name(protocol::BlockRole role) -> std::string_view {
  switch (role) {
  case protocol::BlockRole::h3_train:
    return "H3_TRAIN";
  case protocol::BlockRole::h3_validation:
    return "H3_VALIDATION";
  case protocol::BlockRole::h1h2_supplemental:
    return "H1H2_SUPPLEMENTAL";
  case protocol::BlockRole::not_applicable:
    return "NOT_APPLICABLE";
  }
  return {};
}

[[nodiscard]] auto context_name(protocol::H3Context context) -> std::string_view {
  switch (context) {
  case protocol::H3Context::near_l2_l050:
    return "NEAR_L2_L050";
  case protocol::H3Context::near_llc_l050:
    return "NEAR_LLC_L050";
  case protocol::H3Context::near_beyond_llc_l050:
    return "NEAR_BEYOND_LLC_L050";
  case protocol::H3Context::far_l2_l050:
    return "FAR_L2_L050";
  case protocol::H3Context::far_llc_l050:
    return "FAR_LLC_L050";
  case protocol::H3Context::far_beyond_llc_l050:
    return "FAR_BEYOND_LLC_L050";
  }
  return {};
}

[[nodiscard]] auto stage_name(AnalysisStage stage) -> std::string_view {
  switch (stage) {
  case AnalysisStage::artifact_validation:
    return "ARTIFACT_VALIDATION";
  case AnalysisStage::reconciliation_verification:
    return "RECONCILIATION_VERIFICATION";
  case AnalysisStage::interval_derivation:
    return "INTERVAL_DERIVATION";
  case AnalysisStage::run_gates:
    return "RUN_GATES";
  case AnalysisStage::run_summaries:
    return "RUN_SUMMARIES";
  case AnalysisStage::complete_blocks:
    return "COMPLETE_BLOCKS";
  case AnalysisStage::h3_training:
    return "H3_TRAINING";
  case AnalysisStage::selection_freeze:
    return "SELECTION_FREEZE";
  case AnalysisStage::validation_unseal:
    return "VALIDATION_UNSEAL";
  case AnalysisStage::h3_validation:
    return "H3_VALIDATION";
  case AnalysisStage::h3_evaluation:
    return "H3_EVALUATION";
  case AnalysisStage::h1h2_release:
    return "H1H2_RELEASE";
  case AnalysisStage::h1h2_analysis:
    return "H1H2_ANALYSIS";
  case AnalysisStage::reporting:
    return "REPORTING";
  }
  return {};
}

[[nodiscard]] auto conclusion_name(PracticalConclusion conclusion) -> std::string_view {
  switch (conclusion) {
  case PracticalConclusion::practically_lower:
    return "PRACTICALLY_LOWER";
  case PracticalConclusion::practically_higher:
    return "PRACTICALLY_HIGHER";
  case PracticalConclusion::practically_equivalent:
    return "PRACTICALLY_EQUIVALENT";
  case PracticalConclusion::inconclusive:
    return "INCONCLUSIVE";
  }
  return {};
}

[[nodiscard]] auto candidate_name(const protocol::H3Candidate& candidate)
    -> std::string {
  return std::string(package_name(candidate.package)) + "-" +
         std::string(hardware_name(candidate.requested_hardware_state));
}

[[nodiscard]] auto find_artifact(std::span<const ImmutableArtifact> artifacts,
                                 std::string_view id) -> const ImmutableArtifact* {
  const auto iterator =
      std::find_if(artifacts.begin(), artifacts.end(), [&](const auto& artifact) {
        return artifact.reference.artifact_id.value() == id;
      });
  return iterator == artifacts.end() ? nullptr : &*iterator;
}

[[nodiscard]] auto artifact_bytes_equal(const ImmutableArtifact& artifact,
                                        std::string_view expected) -> bool {
  return artifact.bytes.size() == expected.size() &&
         std::equal(artifact.bytes.begin(), artifact.bytes.end(), expected.begin(),
                    [](std::byte left, char right) {
                      return std::to_integer<unsigned char>(left) ==
                             static_cast<unsigned char>(right);
                    });
}

[[nodiscard]] auto verify_artifact(const ImmutableArtifact& artifact) -> bool {
  return artifact.finalized &&
         workload::sha256(artifact.bytes).hex() == artifact.reference.sha256.hex();
}

[[nodiscard]] auto access_rank(protocol::AccessState state) -> std::uint8_t {
  return static_cast<std::uint8_t>(state);
}

[[nodiscard]] auto required_access_state(orchestration::OutcomeDomain domain)
    -> protocol::AccessState {
  switch (domain) {
  case orchestration::OutcomeDomain::h3_training:
    return protocol::AccessState::training_open;
  case orchestration::OutcomeDomain::h3_validation:
    return protocol::AccessState::validation_unsealed;
  case orchestration::OutcomeDomain::h1h2:
    return protocol::AccessState::h1h2_released;
  }
  return protocol::AccessState::archived;
}

[[nodiscard]] auto required_role(orchestration::OutcomeDomain domain,
                                 protocol::BlockRole role) -> bool {
  switch (domain) {
  case orchestration::OutcomeDomain::h3_training:
    return role == protocol::BlockRole::h3_train;
  case orchestration::OutcomeDomain::h3_validation:
    return role == protocol::BlockRole::h3_validation;
  case orchestration::OutcomeDomain::h1h2:
    return role != protocol::BlockRole::not_applicable;
  }
  return false;
}

[[nodiscard]] auto checked_sum(std::span<const WeightedLatency> values)
    -> std::optional<std::uint64_t> {
  std::uint64_t sum = 0U;
  for (const auto& value : values) {
    if (value.multiplicity > std::numeric_limits<std::uint64_t>::max() - sum) {
      return std::nullopt;
    }
    sum += value.multiplicity;
  }
  return sum;
}

[[nodiscard]] auto cell_key(protocol::QueuePackage package,
                            protocol::RequestedHardwareState hardware,
                            protocol::Placement placement,
                            protocol::WorkingSetClass working_set,
                            protocol::LoadLevel load) {
  return std::tuple{package, hardware, placement, working_set, load};
}

[[nodiscard]] auto cell_map(const CompleteBlockResponse& block)
    -> protocol::Result<std::map<
        std::tuple<protocol::QueuePackage, protocol::RequestedHardwareState,
                   protocol::Placement, protocol::WorkingSetClass, protocol::LoadLevel>,
        double>> {
  if (block.cells.size() != orchestration::kStageACellsPerBlock) {
    return fail<std::map<
        std::tuple<protocol::QueuePackage, protocol::RequestedHardwareState,
                   protocol::Placement, protocol::WorkingSetClass, protocol::LoadLevel>,
        double>>(protocol::ErrorCategory::cross_field, "$/analysis/block/cells",
                 "ANALYSIS-EXACT-180",
                 "complete-block response must contain exactly 180 cells");
  }
  std::map<
      std::tuple<protocol::QueuePackage, protocol::RequestedHardwareState,
                 protocol::Placement, protocol::WorkingSetClass, protocol::LoadLevel>,
      double>
      result;
  for (const auto& cell : block.cells) {
    if (!std::isfinite(cell.log_p999) ||
        !result
             .emplace(cell_key(cell.package, cell.hardware_state, cell.placement,
                               cell.working_set, cell.load),
                      cell.log_p999)
             .second) {
      return fail<decltype(result)>(protocol::ErrorCategory::duplicate_value,
                                    "$/analysis/block/cells", "ANALYSIS-CELL-UNIQUE",
                                    "cell responses must be finite and unique");
    }
  }
  if (result.size() != orchestration::kStageACellsPerBlock) {
    return fail<decltype(result)>(protocol::ErrorCategory::cross_field,
                                  "$/analysis/block/cells", "ANALYSIS-CELL-PRODUCT",
                                  "cell responses do not form the Stage A product");
  }
  return protocol::Result<decltype(result)>::success(result);
}

using CellMap = std::map<
    std::tuple<protocol::QueuePackage, protocol::RequestedHardwareState,
               protocol::Placement, protocol::WorkingSetClass, protocol::LoadLevel>,
    double>;

[[nodiscard]] auto value_at(const CellMap& values, protocol::QueuePackage package,
                            protocol::RequestedHardwareState hardware,
                            protocol::Placement placement,
                            protocol::WorkingSetClass working_set,
                            protocol::LoadLevel load) -> double {
  return values.at(cell_key(package, hardware, placement, working_set, load));
}

[[nodiscard]] auto software_effect(const CellMap& values,
                                   protocol::QueuePackage package,
                                   protocol::Placement placement,
                                   protocol::WorkingSetClass working_set,
                                   protocol::LoadLevel load) -> double {
  const auto baseline = package == protocol::QueuePackage::l1
                            ? protocol::QueuePackage::l0
                            : protocol::QueuePackage::r0;
  double sum = 0.0;
  for (const auto hardware :
       {protocol::RequestedHardwareState::h0, protocol::RequestedHardwareState::h1}) {
    sum += value_at(values, package, hardware, placement, working_set, load) -
           value_at(values, baseline, hardware, placement, working_set, load);
  }
  return sum / 2.0;
}

[[nodiscard]] auto hardware_effect(const CellMap& values,
                                   protocol::QueuePackage package,
                                   protocol::Placement placement,
                                   protocol::WorkingSetClass working_set,
                                   protocol::LoadLevel load) -> double {
  return value_at(values, package, protocol::RequestedHardwareState::h1, placement,
                  working_set, load) -
         value_at(values, package, protocol::RequestedHardwareState::h0, placement,
                  working_set, load);
}

[[nodiscard]] auto context_value(const CellMap& values, std::string_view suffix,
                                 protocol::Placement placement,
                                 protocol::WorkingSetClass working_set,
                                 protocol::LoadLevel load) -> double {
  if (suffix == "H") {
    double sum = 0.0;
    for (const auto package : {protocol::QueuePackage::r0, protocol::QueuePackage::r1,
                               protocol::QueuePackage::r2, protocol::QueuePackage::l0,
                               protocol::QueuePackage::l1}) {
      sum += hardware_effect(values, package, placement, working_set, load);
    }
    return sum / 5.0;
  }
  if (suffix == "R1") {
    return software_effect(values, protocol::QueuePackage::r1, placement, working_set,
                           load);
  }
  if (suffix == "R2") {
    return software_effect(values, protocol::QueuePackage::r2, placement, working_set,
                           load);
  }
  return software_effect(values, protocol::QueuePackage::l1, placement, working_set,
                         load);
}

struct H2OperatorKey {
  std::string_view operation;
  std::string_view package_suffix;
};

[[nodiscard]] auto h2_operator(const CellMap& values, H2OperatorKey key) -> double {
  constexpr std::array placements{protocol::Placement::near, protocol::Placement::far};
  constexpr std::array working_sets{protocol::WorkingSetClass::l2_resident,
                                    protocol::WorkingSetClass::llc_resident,
                                    protocol::WorkingSetClass::beyond_llc};
  constexpr std::array loads{protocol::LoadLevel::l025, protocol::LoadLevel::l050,
                             protocol::LoadLevel::l075};
  double sum = 0.0;
  std::size_t count = 0U;
  if (key.operation == "P") {
    for (const auto working_set : working_sets) {
      for (const auto load : loads) {
        sum += context_value(values, key.package_suffix, protocol::Placement::far,
                             working_set, load) -
               context_value(values, key.package_suffix, protocol::Placement::near,
                             working_set, load);
        ++count;
      }
    }
  } else if (key.operation == "W12" || key.operation == "W23") {
    const auto left = key.operation == "W12" ? protocol::WorkingSetClass::llc_resident
                                             : protocol::WorkingSetClass::beyond_llc;
    const auto right = key.operation == "W12" ? protocol::WorkingSetClass::l2_resident
                                              : protocol::WorkingSetClass::llc_resident;
    for (const auto placement : placements) {
      for (const auto load : loads) {
        sum += context_value(values, key.package_suffix, placement, left, load) -
               context_value(values, key.package_suffix, placement, right, load);
        ++count;
      }
    }
  } else {
    const auto left =
        key.operation == "A12" ? protocol::LoadLevel::l050 : protocol::LoadLevel::l075;
    const auto right =
        key.operation == "A12" ? protocol::LoadLevel::l025 : protocol::LoadLevel::l050;
    for (const auto placement : placements) {
      for (const auto working_set : working_sets) {
        sum += context_value(values, key.package_suffix, placement, working_set, left) -
               context_value(values, key.package_suffix, placement, working_set, right);
        ++count;
      }
    }
  }
  return sum / static_cast<double>(count);
}

[[nodiscard]] auto mean_vector(std::span<const std::vector<double>> values)
    -> std::vector<double> {
  std::vector<double> result(values.front().size(), 0.0);
  for (const auto& vector : values) {
    for (std::size_t index = 0U; index < result.size(); ++index) {
      result[index] += vector[index];
    }
  }
  for (auto& value : result) {
    value /= static_cast<double>(values.size());
  }
  return result;
}

[[nodiscard]] auto bounded_draw(const workload::DeterministicStream& stream,
                                std::uint64_t bound, std::uint64_t& draw_ordinal)
    -> protocol::Result<std::uint64_t> {
  if (bound == 0U) {
    return fail<std::uint64_t>(protocol::ErrorCategory::out_of_range,
                               "$/bootstrap/bound", "ANALYSIS-BOOTSTRAP-BOUND",
                               "bootstrap block count must be positive");
  }
  const auto threshold = (0U - bound) % bound;
  while (true) {
    if (draw_ordinal == std::numeric_limits<std::uint64_t>::max()) {
      return fail<std::uint64_t>(
          protocol::ErrorCategory::out_of_range, "$/bootstrap/draw_ordinal",
          "ANALYSIS-BOOTSTRAP-DRAW-OVERFLOW", "bootstrap draw ordinal exhausted");
    }
    const auto draw = stream.draw(draw_ordinal++);
    if (draw >= threshold) {
      return protocol::Result<std::uint64_t>::success(draw % bound);
    }
  }
}

[[nodiscard]] auto
bootstrap_vectors(std::span<const std::vector<double>> complete_block_vectors,
                  const BootstrapConfiguration& bootstrap)
    -> protocol::Result<std::vector<std::vector<double>>> {
  if (complete_block_vectors.size() < 2U || bootstrap.replicates < 2U ||
      bootstrap.profile != kBootstrapProfile ||
      bootstrap.rng_algorithm_version != workload::kDeterministicSuite ||
      bootstrap.seed_id.value().empty()) {
    return fail<std::vector<std::vector<double>>>(
        protocol::ErrorCategory::missing_evidence, "$/bootstrap",
        "ANALYSIS-BOOTSTRAP-CONTRACT",
        "complete-block bootstrap requires at least two blocks/replicates and the "
        "accepted explicit Philox profile, algorithm, and seed identity");
  }
  const auto width = complete_block_vectors.front().size();
  if (width == 0U ||
      !std::all_of(complete_block_vectors.begin(), complete_block_vectors.end(),
                   [&](const auto& value) { return value.size() == width; })) {
    return fail<std::vector<std::vector<double>>>(
        protocol::ErrorCategory::cross_field, "$/bootstrap/contrasts",
        "ANALYSIS-BOOTSTRAP-WIDTH",
        "every complete block must provide the same nonempty contrast vector");
  }
  workload::DeterministicStream stream(bootstrap.key);
  std::uint64_t draw_ordinal = 0U;
  std::vector<std::vector<double>> result;
  result.reserve(static_cast<std::size_t>(bootstrap.replicates));
  for (std::uint64_t replicate = 0U; replicate < bootstrap.replicates; ++replicate) {
    std::vector<double> estimate(width, 0.0);
    for (std::size_t draw_index = 0U; draw_index < complete_block_vectors.size();
         ++draw_index) {
      auto selected = bounded_draw(stream, complete_block_vectors.size(), draw_ordinal);
      if (!selected) {
        return protocol::Result<std::vector<std::vector<double>>>::failure(
            selected.errors());
      }
      const auto& block = complete_block_vectors[selected.value()];
      for (std::size_t column = 0U; column < width; ++column) {
        estimate[column] += block[column];
      }
    }
    for (auto& value : estimate) {
      value /= static_cast<double>(complete_block_vectors.size());
    }
    result.push_back(std::move(estimate));
  }
  return protocol::Result<std::vector<std::vector<double>>>::success(result);
}

[[nodiscard]] auto
standard_errors(std::span<const std::vector<double>> bootstrap_estimates)
    -> std::vector<double> {
  const auto means = mean_vector(bootstrap_estimates);
  std::vector<double> result(means.size(), 0.0);
  for (const auto& estimate : bootstrap_estimates) {
    for (std::size_t index = 0U; index < means.size(); ++index) {
      const auto difference = estimate[index] - means[index];
      result[index] += difference * difference;
    }
  }
  for (auto& value : result) {
    value = std::sqrt(value / static_cast<double>(bootstrap_estimates.size() - 1U));
  }
  return result;
}

[[nodiscard]] auto empirical_p95(std::vector<double> values)
    -> protocol::Result<double> {
  if (values.empty() || !std::all_of(values.begin(), values.end(), [](double value) {
        return std::isfinite(value);
      })) {
    return fail<double>(protocol::ErrorCategory::cross_field, "$/bootstrap/statistics",
                        "ANALYSIS-MAXT-FINITE",
                        "bootstrap statistics must be nonempty and finite");
  }
  std::sort(values.begin(), values.end());
  const auto rank = (95U * values.size() + 99U) / 100U;
  return protocol::Result<double>::success(values[rank - 1U]);
}

[[nodiscard]] auto classify(double lower, double upper, double delta)
    -> PracticalConclusion {
  if (upper < -delta) {
    return PracticalConclusion::practically_lower;
  }
  if (lower > delta) {
    return PracticalConclusion::practically_higher;
  }
  if (lower > -delta && upper < delta) {
    return PracticalConclusion::practically_equivalent;
  }
  return PracticalConclusion::inconclusive;
}

[[nodiscard]] auto max_t(std::string family_id,
                         std::span<const std::string_view> stable_ids,
                         std::span<const std::vector<double>> complete_block_contrasts,
                         const BootstrapConfiguration& bootstrap, double delta_star,
                         bool one_sided) -> protocol::Result<MaxTResult> {
  if (!(std::isfinite(delta_star) && delta_star > 0.0) || stable_ids.empty() ||
      complete_block_contrasts.empty() ||
      complete_block_contrasts.front().size() != stable_ids.size()) {
    return fail<MaxTResult>(protocol::ErrorCategory::cross_field, "$/analysis/max_t",
                            "ANALYSIS-MAXT-INPUT",
                            "max-T requires a positive bound and the exact family");
  }
  auto bootstrap_result = bootstrap_vectors(complete_block_contrasts, bootstrap);
  if (!bootstrap_result) {
    return protocol::Result<MaxTResult>::failure(bootstrap_result.errors());
  }
  const auto original = mean_vector(complete_block_contrasts);
  const auto errors = standard_errors(bootstrap_result.value());
  std::vector<double> statistics;
  statistics.reserve(bootstrap_result.value().size());
  for (const auto& estimate : bootstrap_result.value()) {
    double maximum = 0.0;
    for (std::size_t index = 0U; index < original.size(); ++index) {
      const auto deviation = estimate[index] - original[index];
      double standardized = 0.0;
      if (errors[index] == 0.0) {
        if (deviation != 0.0) {
          return fail<MaxTResult>(
              protocol::ErrorCategory::cross_field, "$/analysis/max_t",
              "ANALYSIS-MAXT-ZERO-SE",
              "a nonzero bootstrap deviation cannot have zero standard error");
        }
      } else {
        standardized = deviation / errors[index];
      }
      maximum = std::max(maximum, one_sided ? standardized : std::abs(standardized));
    }
    statistics.push_back(maximum);
  }
  auto critical = empirical_p95(std::move(statistics));
  if (!critical) {
    return protocol::Result<MaxTResult>::failure(critical.errors());
  }
  std::vector<SimultaneousInterval> intervals;
  intervals.reserve(original.size());
  for (std::size_t index = 0U; index < original.size(); ++index) {
    const auto half_width = critical.value() * errors[index];
    const auto lower = one_sided ? -std::numeric_limits<double>::infinity()
                                 : original[index] - half_width;
    const auto upper = original[index] + half_width;
    intervals.push_back({std::string(stable_ids[index]), original[index], errors[index],
                         lower, upper,
                         one_sided ? PracticalConclusion::inconclusive
                                   : classify(lower, upper, delta_star)});
  }
  return protocol::Result<MaxTResult>::success({std::move(family_id), one_sided,
                                                bootstrap.replicates, critical.value(),
                                                std::move(intervals)});
}

[[nodiscard]] auto h3_value(const CompleteBlockResponse& block,
                            protocol::H3Context context,
                            const protocol::H3Candidate& candidate)
    -> protocol::Result<double> {
  const auto values = cell_map(block);
  if (!values) {
    return protocol::Result<double>::failure(values.errors());
  }
  protocol::Placement placement = protocol::Placement::near;
  protocol::WorkingSetClass working_set = protocol::WorkingSetClass::l2_resident;
  switch (context) {
  case protocol::H3Context::near_l2_l050:
    break;
  case protocol::H3Context::near_llc_l050:
    working_set = protocol::WorkingSetClass::llc_resident;
    break;
  case protocol::H3Context::near_beyond_llc_l050:
    working_set = protocol::WorkingSetClass::beyond_llc;
    break;
  case protocol::H3Context::far_l2_l050:
    placement = protocol::Placement::far;
    break;
  case protocol::H3Context::far_llc_l050:
    placement = protocol::Placement::far;
    working_set = protocol::WorkingSetClass::llc_resident;
    break;
  case protocol::H3Context::far_beyond_llc_l050:
    placement = protocol::Placement::far;
    working_set = protocol::WorkingSetClass::beyond_llc;
    break;
  }
  return protocol::Result<double>::success(
      value_at(values.value(), candidate.package, candidate.requested_hardware_state,
               placement, working_set, protocol::LoadLevel::l050));
}

[[nodiscard]] auto family_expected_width(FamilyKind family) -> std::size_t {
  switch (family) {
  case FamilyKind::h1_two_sided:
    return orchestration::kH1ContrastCount;
  case FamilyKind::h2_two_sided:
    return orchestration::kH2ContrastCount;
  case FamilyKind::h3_training_standard_error:
    return orchestration::kH3TrainingPairCount;
  case FamilyKind::h3_validation_one_sided:
    return orchestration::kH3ValidationFamilyCount;
  }
  return 0U;
}

[[nodiscard]] auto family_minimum(FamilyKind family) -> std::uint64_t {
  switch (family) {
  case FamilyKind::h1_two_sided:
  case FamilyKind::h2_two_sided:
    return 20U;
  case FamilyKind::h3_training_standard_error:
    return 12U;
  case FamilyKind::h3_validation_one_sided:
    return 8U;
  }
  return 0U;
}

[[nodiscard]] auto select_prospective_count(const ProspectiveFamilyInput& input,
                                            FamilyKind expected, double delta_star)
    -> protocol::Result<std::uint64_t> {
  if (input.family != expected || input.candidates.empty() ||
      input.sizing_artifact.artifact_id.value().empty()) {
    return fail<std::uint64_t>(
        protocol::ErrorCategory::missing_evidence, "$/precision",
        "ANALYSIS-PRECISION-EVIDENCE",
        "each registered precision family requires prospective immutable evidence");
  }
  const auto expected_width = family_expected_width(expected);
  const auto minimum = family_minimum(expected);
  std::uint64_t previous = 0U;
  std::optional<std::uint64_t> selected;
  for (const auto& candidate : input.candidates) {
    if (candidate.complete_block_count <= previous ||
        candidate.complete_block_count < minimum ||
        candidate.widths.size() != expected_width ||
        !std::all_of(
            candidate.widths.begin(), candidate.widths.end(),
            [](double value) { return std::isfinite(value) && value >= 0.0; })) {
      return fail<std::uint64_t>(
          protocol::ErrorCategory::cross_field, "$/precision/candidates",
          "ANALYSIS-PRECISION-CURVE",
          "candidate counts must increase and contain the exact finite family");
    }
    previous = candidate.complete_block_count;
    const auto largest =
        *std::max_element(candidate.widths.begin(), candidate.widths.end());
    if (!selected && largest <= delta_star / 2.0) {
      selected = candidate.complete_block_count;
    }
  }
  if (!selected) {
    return fail<std::uint64_t>(
        protocol::ErrorCategory::missing_evidence, "$/precision/candidates",
        "ANALYSIS-PRECISION-UNRESOLVED",
        "no prospectively evaluated count satisfies delta_star/2");
  }
  if ((expected == FamilyKind::h1_two_sided || expected == FamilyKind::h2_two_sided) &&
      *selected > 30U) {
    return fail<std::uint64_t>(protocol::ErrorCategory::out_of_range,
                               "$/precision/candidates", "ANALYSIS-H1H2-CEILING",
                               "H1/H2 prospective count exceeds the go/no-go ceiling");
  }
  return protocol::Result<std::uint64_t>::success(*selected);
}

[[nodiscard]] auto same_counts(const orchestration::ProspectiveCounts& left,
                               const orchestration::ProspectiveCounts& right) -> bool {
  return left.r_h1 == right.r_h1 && left.r_h2 == right.r_h2 && left.r12 == right.r12 &&
         left.rtrain == right.rtrain && left.rval == right.rval &&
         left.rtotal == right.rtotal && left.nruns == right.nruns;
}

[[nodiscard]] auto block_ids(std::span<const BlockInput> blocks,
                             protocol::BlockRole role, bool active_only)
    -> std::vector<protocol::BlockId> {
  std::vector<protocol::BlockId> result;
  for (const auto& block : blocks) {
    if ((!active_only || block.active_primary) && block.plan.block_role == role) {
      result.push_back(block.plan.block_id);
    }
  }
  return result;
}

[[nodiscard]] auto exact_id_set(std::span<const protocol::BlockId> actual,
                                std::span<const protocol::BlockId> expected) -> bool {
  std::set<std::string> left;
  std::set<std::string> right;
  for (const auto& value : actual) {
    left.emplace(value.value());
  }
  for (const auto& value : expected) {
    right.emplace(value.value());
  }
  return left.size() == actual.size() && right.size() == expected.size() &&
         left == right;
}

[[nodiscard]] auto validate_grant(const OutcomeAccessGrant& grant,
                                  orchestration::OutcomeDomain expected_domain,
                                  std::span<const protocol::BlockId> expected_blocks,
                                  std::span<const ImmutableArtifact> artifacts)
    -> std::vector<protocol::ValidationError> {
  std::vector<protocol::ValidationError> errors;
  if (grant.domain() != expected_domain ||
      access_rank(grant.state()) <
          access_rank(required_access_state(expected_domain))) {
    add(errors, protocol::ErrorCategory::missing_evidence, "$/access",
        "ANALYSIS-ACCESS-STATE", "outcome domain is not authorized at this state");
  }
  if (!exact_id_set(grant.affected_block_ids(), expected_blocks)) {
    add(errors, protocol::ErrorCategory::cross_field, "$/access/affected_blocks",
        "ANALYSIS-ACCESS-EXACT-BLOCKS",
        "access grant must name exactly the applicable active blocks");
  }
  const auto* artifact =
      find_artifact(artifacts, grant.access_record().artifact_id.value());
  if (artifact == nullptr || artifact->reference != grant.access_record() ||
      !verify_artifact(*artifact)) {
    add(errors, protocol::ErrorCategory::missing_evidence, "$/access/record",
        "ANALYSIS-ACCESS-HASH",
        "access grant must resolve to finalized checksum-valid evidence");
  }
  return errors;
}

[[nodiscard]] auto build_machine_report(
    const AnalysisConfiguration& configuration, InferenceState state,
    std::span<const RunSummary> summaries,
    std::span<const CompleteBlockResponse> blocks, const std::optional<MaxTResult>& h1,
    const std::optional<MaxTResult>& h2,
    const std::optional<H3SelectionRecord>& selection,
    const std::optional<H3ValidationResult>& h3,
    std::span<const ImmutableArtifact> artifacts, std::span<const StageReceipt> stages,
    const protocol::Sha256& configuration_hash, std::string_view output_hash)
    -> protocol::Result<std::string> {
  JsonObject root;
  root.emplace("analysis_profile", string_value(configuration.analysis_profile));
  root.emplace("configuration_sha256", string_value(configuration_hash.hex()));
  root.emplace("evidence_class", string_value("SYNTHETIC_KNOWN_ANSWER_ONLY"));
  root.emplace(
      "inference_state",
      string_value(state == InferenceState::estimable ? "ESTIMABLE" : "BLOCKED"));
  root.emplace("protocol_version", string_value(std::string(
                                       protocol_name(configuration.protocol_version))));
  root.emplace("report_schema", string_value(std::string(kReportSchema)));
  root.emplace("output_sha256", string_value(std::string(output_hash)));
  root.emplace("run_summary_count", unsigned_value(summaries.size()));
  root.emplace("primary_complete_block_count", unsigned_value(blocks.size()));
  JsonObject software;
  software.emplace("compiler", string_value(configuration.software.compiler));
  software.emplace("implementation_revision",
                   string_value(configuration.software.implementation_revision));
  software.emplace("standard_library",
                   string_value(configuration.software.standard_library));
  root.emplace("software", protocol::json::Value(std::move(software)));

  JsonArray sources;
  std::vector<const ImmutableArtifact*> sorted;
  sorted.reserve(artifacts.size());
  for (const auto& artifact : artifacts) {
    sorted.push_back(&artifact);
  }
  std::sort(sorted.begin(), sorted.end(), [](const auto* left, const auto* right) {
    return left->reference.artifact_id.value() < right->reference.artifact_id.value();
  });
  for (const auto* artifact : sorted) {
    sources.emplace_back(artifact_value(artifact->reference));
  }
  root.emplace("input_artifacts", protocol::json::Value(std::move(sources)));

  auto family_value = [](const MaxTResult& family) {
    JsonObject object;
    object.emplace("family_id", string_value(family.family_id));
    object.emplace("one_sided", bool_value(family.one_sided));
    object.emplace("critical_value_binary64",
                   string_value(float_bits(family.critical_value)));
    object.emplace("bootstrap_replicates", unsigned_value(family.bootstrap_replicates));
    JsonArray intervals;
    for (const auto& interval : family.intervals) {
      JsonObject row;
      row.emplace("stable_id", string_value(interval.stable_id));
      row.emplace("estimate_binary64", string_value(float_bits(interval.estimate)));
      row.emplace("standard_error_binary64",
                  string_value(float_bits(interval.standard_error)));
      if (std::isfinite(interval.lower)) {
        row.emplace("lower_binary64", string_value(float_bits(interval.lower)));
      } else {
        row.emplace("lower_binary64", string_value("NEGATIVE_INFINITY"));
      }
      row.emplace("upper_binary64", string_value(float_bits(interval.upper)));
      row.emplace("conclusion",
                  string_value(std::string(conclusion_name(interval.conclusion))));
      intervals.emplace_back(protocol::json::Value(std::move(row)));
    }
    object.emplace("intervals", protocol::json::Value(std::move(intervals)));
    return protocol::json::Value(std::move(object));
  };
  root.emplace("h1", h1 ? family_value(*h1) : protocol::json::Value(nullptr));
  root.emplace("h2", h2 ? family_value(*h2) : protocol::json::Value(nullptr));
  if (selection) {
    JsonObject value;
    value.emplace("record_sha256", string_value(selection->record_sha256.hex()));
    value.emplace("schema_version", string_value(selection->schema_version));
    root.emplace("h3_selection", protocol::json::Value(std::move(value)));
  } else {
    root.emplace("h3_selection", protocol::json::Value(nullptr));
  }
  if (h3 && h3->comparisons) {
    JsonObject value;
    value.emplace("all_upper_limits_below_delta",
                  bool_value(h3->all_upper_limits_below_delta));
    value.emplace("comparisons", family_value(*h3->comparisons));
    root.emplace("h3_validation", protocol::json::Value(std::move(value)));
  } else {
    root.emplace("h3_validation", protocol::json::Value(nullptr));
  }
  JsonObject sensitivity;
  sensitivity.emplace("classification", string_value("NON_PRIMARY_DIAGNOSTIC"));
  sensitivity.emplace("outputs", protocol::json::Value(JsonArray{}));
  root.emplace("sensitivity_diagnostics",
               protocol::json::Value(std::move(sensitivity)));
  JsonArray stage_values;
  for (const auto& receipt : stages) {
    JsonObject value;
    value.emplace("stage", string_value(std::string(stage_name(receipt.stage))));
    value.emplace("version", string_value(receipt.version));
    value.emplace("input_count", unsigned_value(receipt.inputs.size()));
    stage_values.emplace_back(protocol::json::Value(std::move(value)));
  }
  root.emplace("stages", protocol::json::Value(std::move(stage_values)));
  return canonical(std::move(root));
}

[[nodiscard]] auto build_human_report(InferenceState state, std::size_t run_count,
                                      std::size_t block_count,
                                      const std::optional<MaxTResult>& h1,
                                      const std::optional<MaxTResult>& h2,
                                      const std::optional<H3ValidationResult>& h3)
    -> std::string {
  std::ostringstream output;
  output << "# Synthetic Stage 15 known-answer report\n\n"
         << "**SYNTHETIC FIXTURE ONLY — THIS DOCUMENT CONTAINS NO EMPIRICAL "
            "FINDINGS.**\n\n"
         << "Analysis state: "
         << (state == InferenceState::estimable ? "ESTIMABLE" : "BLOCKED")
         << "\n\nValidated synthetic run summaries: " << run_count
         << "\n\nActive complete blocks: " << block_count << "\n\n"
         << "H1 family: " << (h1 ? "7 registered intervals" : "not evaluated")
         << "\n\nH2 family: " << (h2 ? "20 registered intervals" : "not evaluated")
         << "\n\n"
         << "H3 validation: "
         << (h3 && h3->comparisons ? "54 registered upper limits" : "not evaluated")
         << "\n\nSensitivity and diagnostic outputs are non-primary and are not "
            "interpreted as treatment evidence.\n";
  return output.str();
}

} // namespace

auto OutcomeAccessGrant::from_stage14(
    const orchestration::AccessLedgerResult& ledger,
    orchestration::OutcomeDomain domain,
    std::span<const protocol::BlockPlan> affected_blocks,
    protocol::ArtifactReference access_record) -> protocol::Result<OutcomeAccessGrant> {
  if (!ledger.errors.empty() ||
      access_rank(ledger.final_state) < access_rank(required_access_state(domain)) ||
      affected_blocks.empty() || access_record.artifact_id.value().empty()) {
    return fail<OutcomeAccessGrant>(
        protocol::ErrorCategory::missing_evidence, "$/access", "ANALYSIS-STAGE14-GRANT",
        "a passing Stage 14 ledger at the required state and affected blocks are "
        "required");
  }
  std::vector<protocol::BlockId> ids;
  std::set<std::string> unique;
  ids.reserve(affected_blocks.size());
  for (const auto& block : affected_blocks) {
    if (!required_role(domain, block.block_role) ||
        !unique.emplace(block.block_id.value()).second) {
      return fail<OutcomeAccessGrant>(
          protocol::ErrorCategory::cross_field, "$/access/affected_blocks",
          "ANALYSIS-STAGE14-GRANT-BLOCKS",
          "grant blocks must be unique and role-compatible with the outcome domain");
    }
    ids.push_back(block.block_id);
  }
  return protocol::Result<OutcomeAccessGrant>::success(OutcomeAccessGrant(
      domain, ledger.final_state, std::move(ids), std::move(access_record)));
}

auto exact_inverse_ecdf_quantile(std::span<const WeightedLatency> sorted_values,
                                 std::uint64_t numerator, std::uint64_t denominator)
    -> protocol::Result<std::uint64_t> {
  if (sorted_values.empty() || numerator == 0U || denominator == 0U ||
      numerator > denominator) {
    return fail<std::uint64_t>(protocol::ErrorCategory::out_of_range, "$/quantile",
                               "ANALYSIS-QUANTILE-P",
                               "quantile probability and sample must be nonempty");
  }
  const auto count = checked_sum(sorted_values);
  if (!count || *count == 0U) {
    return fail<std::uint64_t>(protocol::ErrorCategory::out_of_range,
                               "$/quantile/sample", "ANALYSIS-QUANTILE-COUNT",
                               "quantile multiplicities overflow or sum to zero");
  }
  std::uint64_t previous_value = 0U;
  bool first = true;
  for (const auto& value : sorted_values) {
    if (value.multiplicity == 0U || (!first && value.latency_ticks <= previous_value)) {
      return fail<std::uint64_t>(
          protocol::ErrorCategory::cross_field, "$/quantile/sample",
          "ANALYSIS-QUANTILE-SORTED",
          "synthetic RLE values must be strictly increasing with positive counts");
    }
    previous_value = value.latency_ticks;
    first = false;
  }
  const auto quotient = *count / denominator;
  const auto remainder = *count % denominator;
  if (quotient > std::numeric_limits<std::uint64_t>::max() / numerator ||
      remainder > std::numeric_limits<std::uint64_t>::max() / numerator) {
    return fail<std::uint64_t>(protocol::ErrorCategory::out_of_range, "$/quantile/rank",
                               "ANALYSIS-QUANTILE-OVERFLOW",
                               "quantile rank arithmetic overflows u64");
  }
  std::uint64_t rank = quotient * numerator;
  const auto remainder_product = remainder * numerator;
  const auto extra = remainder_product / denominator +
                     (remainder_product % denominator == 0U ? 0U : 1U);
  if (rank > std::numeric_limits<std::uint64_t>::max() - extra) {
    return fail<std::uint64_t>(protocol::ErrorCategory::out_of_range, "$/quantile/rank",
                               "ANALYSIS-QUANTILE-OVERFLOW",
                               "quantile rank arithmetic overflows u64");
  }
  rank += extra;
  std::uint64_t cumulative = 0U;
  for (const auto& value : sorted_values) {
    cumulative += value.multiplicity;
    if (cumulative >= rank) {
      return protocol::Result<std::uint64_t>::success(value.latency_ticks);
    }
  }
  return fail<std::uint64_t>(protocol::ErrorCategory::cross_field, "$/quantile/rank",
                             "ANALYSIS-QUANTILE-INTERNAL",
                             "quantile rank was not found");
}

auto canonical_synthetic_latency_payload(const protocol::RunId& run_id,
                                         std::span<const WeightedLatency> latencies)
    -> protocol::Result<std::string> {
  JsonObject object;
  object.emplace("encoding", string_value(std::string(kSyntheticLatencyEncoding)));
  object.emplace("run_id", string_value(std::string(run_id.value())));
  JsonArray values;
  for (const auto& latency : latencies) {
    JsonObject value;
    value.emplace("latency_ticks", unsigned_value(latency.latency_ticks));
    value.emplace("multiplicity", unsigned_value(latency.multiplicity));
    values.emplace_back(protocol::json::Value(std::move(value)));
  }
  object.emplace("values", protocol::json::Value(std::move(values)));
  return canonical(std::move(object));
}

auto canonical_synthetic_run(const SyntheticRunInput& run)
    -> protocol::Result<std::string> {
  JsonObject object;
  object.emplace("accepted_count", unsigned_value(run.accepted_count));
  object.emplace("attempted_count", unsigned_value(run.attempted_count));
  object.emplace("block_id", string_value(std::string(run.block_id.value())));
  object.emplace("block_role", string_value(std::string(role_name(run.block_role))));
  object.emplace("cell_ordinal", unsigned_value(run.cell_ordinal));
  object.emplace("consumed_count", unsigned_value(run.consumed_count));
  object.emplace("failure_artifact", run.failure_artifact
                                         ? artifact_value(*run.failure_artifact)
                                         : protocol::json::Value(nullptr));
  object.emplace("final_occupancy", unsigned_value(run.final_occupancy));
  object.emplace("full_count", unsigned_value(run.full_count));
  object.emplace("hardware_state",
                 string_value(std::string(hardware_name(run.hardware_state))));
  object.emplace("join_audit_artifact", artifact_value(run.join_audit_artifact));
  object.emplace("joined_artifact", artifact_value(run.joined_artifact));
  object.emplace("load", unsigned_value(static_cast<std::uint64_t>(run.load)));
  object.emplace("manifest_artifact_id",
                 string_value(std::string(run.manifest_artifact.artifact_id.value())));
  object.emplace("n_eff_p999", unsigned_value(run.n_eff_p999));
  object.emplace("measurement_horizon_ticks",
                 unsigned_value(run.measurement_horizon_ticks));
  object.emplace("offered_count", unsigned_value(run.offered_count));
  object.emplace("package", string_value(std::string(package_name(run.package))));
  object.emplace("placement",
                 unsigned_value(static_cast<std::uint64_t>(run.placement)));
  object.emplace("prior_stage12_validation_passed",
                 bool_value(run.prior_stage12_validation_passed));
  object.emplace("protocol_version",
                 string_value(std::string(protocol_name(run.protocol_version))));
  object.emplace("raw_reconciliation_present",
                 bool_value(run.raw_reconciliation.has_value()));
  object.emplace("raw_sample_count", unsigned_value(run.raw_sample_count));
  object.emplace("run_id", string_value(std::string(run.run_id.value())));
  object.emplace("schema_version", string_value(run.schema_version));
  object.emplace("validity",
                 string_value(run.validity == protocol::RunValidity::valid ? "VALID"
                              : run.validity == protocol::RunValidity::invalid
                                  ? "INVALID"
                                  : "NOT_EVALUATED"));
  object.emplace("working_set",
                 unsigned_value(static_cast<std::uint64_t>(run.working_set)));
  JsonObject diagnostics;
  diagnostics.emplace("admission_delay",
                      weighted_values(run.diagnostics.admission_delay));
  diagnostics.emplace("consumer_action",
                      weighted_values(run.diagnostics.consumer_action));
  diagnostics.emplace("dequeue_service",
                      weighted_values(run.diagnostics.dequeue_service));
  diagnostics.emplace("enqueue_service",
                      weighted_values(run.diagnostics.enqueue_service));
  diagnostics.emplace("post_dequeue_delivery",
                      weighted_values(run.diagnostics.post_dequeue_delivery));
  diagnostics.emplace("producer_lateness",
                      weighted_values(run.diagnostics.producer_lateness));
  diagnostics.emplace("queue_residence",
                      weighted_values(run.diagnostics.queue_residence));
  object.emplace("diagnostics", protocol::json::Value(std::move(diagnostics)));
  return canonical(std::move(object));
}

auto summarize_run(const SyntheticRunInput& run,
                   std::span<const ImmutableArtifact> artifacts)
    -> protocol::Result<RunSummary> {
  std::vector<protocol::ValidationError> errors;
  if (run.protocol_version != protocol::ProtocolVersion::v2_0_0_pre_2 ||
      run.schema_version != kRunInputSchema) {
    add(errors, protocol::ErrorCategory::unsupported_version, "$/run/version",
        "ANALYSIS-RUN-VERSION",
        "Stage 15 accepts only the pre.2 synthetic run-input schema");
  }
  const auto* manifest =
      find_artifact(artifacts, run.manifest_artifact.artifact_id.value());
  const auto* joined =
      find_artifact(artifacts, run.joined_artifact.artifact_id.value());
  const auto* audit =
      find_artifact(artifacts, run.join_audit_artifact.artifact_id.value());
  const auto canonical_run = canonical_synthetic_run(run);
  const auto canonical_latency =
      canonical_synthetic_latency_payload(run.run_id, run.end_to_end_latencies);
  if (!canonical_run || manifest == nullptr ||
      manifest->reference != run.manifest_artifact || !verify_artifact(*manifest) ||
      !artifact_bytes_equal(*manifest, canonical_run ? canonical_run.value()
                                                     : std::string_view{})) {
    add(errors, protocol::ErrorCategory::invalid_hash, "$/run/manifest_artifact",
        "ANALYSIS-MANIFEST-HASH",
        "run projection must equal its finalized immutable manifest artifact");
  }
  if (!canonical_latency || joined == nullptr ||
      joined->reference != run.joined_artifact || !verify_artifact(*joined) ||
      !artifact_bytes_equal(*joined, canonical_latency ? canonical_latency.value()
                                                       : std::string_view{})) {
    add(errors, protocol::ErrorCategory::invalid_hash, "$/run/joined_artifact",
        "ANALYSIS-JOINED-HASH",
        "synthetic latency payload must equal its finalized immutable artifact");
  }
  if (audit == nullptr || audit->reference != run.join_audit_artifact ||
      !verify_artifact(*audit)) {
    add(errors, protocol::ErrorCategory::missing_evidence, "$/run/join_audit_artifact",
        "ANALYSIS-JOIN-AUDIT", "a finalized checksum-valid join audit is required");
  }
  if (run.validity == protocol::RunValidity::invalid) {
    if (!run.failure_artifact) {
      add(errors, protocol::ErrorCategory::missing_evidence, "$/run/failure_artifact",
          "ANALYSIS-INVALID-FAILURE",
          "an invalid run requires retained failure evidence");
    } else {
      const auto* failure =
          find_artifact(artifacts, run.failure_artifact->artifact_id.value());
      if (failure == nullptr || failure->reference != *run.failure_artifact ||
          !verify_artifact(*failure)) {
        add(errors, protocol::ErrorCategory::invalid_hash, "$/run/failure_artifact",
            "ANALYSIS-FAILURE-HASH",
            "failure evidence must resolve and pass its checksum");
      }
    }
  } else if (run.failure_artifact) {
    add(errors, protocol::ErrorCategory::cross_field, "$/run/failure_artifact",
        "ANALYSIS-VALID-NO-FAILURE",
        "a valid synthetic run cannot carry invalidating failure evidence");
  }
  if (run.offered_count != run.attempted_count ||
      run.accepted_count > std::numeric_limits<std::uint64_t>::max() - run.full_count ||
      run.attempted_count != run.accepted_count + run.full_count ||
      run.consumed_count != run.accepted_count || run.final_occupancy != 0U ||
      run.raw_sample_count != run.accepted_count ||
      run.n_eff_p999 > run.raw_sample_count) {
    add(errors, protocol::ErrorCategory::cross_field, "$/run/counts",
        "ANALYSIS-COUNT-GATES",
        "run counts, zero occupancy, raw count, and N_eff must reconcile exactly");
  }
  const auto multiplicity = checked_sum(run.end_to_end_latencies);
  if (!multiplicity || *multiplicity != run.raw_sample_count) {
    add(errors, protocol::ErrorCategory::cross_field, "$/run/latencies",
        "ANALYSIS-LATENCY-COUNT",
        "synthetic latency multiplicity must equal the accepted raw count");
  }
  if (run.measurement_horizon_ticks == 0U) {
    add(errors, protocol::ErrorCategory::out_of_range,
        "$/run/measurement_horizon_ticks", "ANALYSIS-HORIZON-POSITIVE",
        "diagnostic throughput requires a positive frozen horizon");
  }
  const std::array diagnostic_counts{
      std::pair{std::span<const WeightedLatency>(run.diagnostics.producer_lateness),
                run.attempted_count},
      std::pair{std::span<const WeightedLatency>(run.diagnostics.enqueue_service),
                run.attempted_count},
      std::pair{std::span<const WeightedLatency>(run.diagnostics.admission_delay),
                run.accepted_count},
      std::pair{std::span<const WeightedLatency>(run.diagnostics.queue_residence),
                run.accepted_count},
      std::pair{std::span<const WeightedLatency>(run.diagnostics.dequeue_service),
                run.accepted_count},
      std::pair{std::span<const WeightedLatency>(run.diagnostics.post_dequeue_delivery),
                run.accepted_count},
      std::pair{std::span<const WeightedLatency>(run.diagnostics.consumer_action),
                run.accepted_count}};
  for (const auto& [series, expected_count] : diagnostic_counts) {
    const auto count = checked_sum(series);
    if (!count || *count != expected_count) {
      add(errors, protocol::ErrorCategory::cross_field, "$/run/diagnostics",
          "ANALYSIS-DIAGNOSTIC-COUNT",
          "producer diagnostics require attempted rows and accepted diagnostics "
          "require joined rows");
      break;
    }
  }
  if (run.raw_reconciliation) {
    const auto reconciled =
        reconciliation::reconcile(run.run_id, run.raw_reconciliation->producer_rows,
                                  run.raw_reconciliation->consumer_rows,
                                  run.raw_reconciliation->expected_record_indices);
    if (reconciled.status != protocol::JoinStatus::passed ||
        reconciled.joined_rows.size() != run.accepted_count) {
      add(errors, protocol::ErrorCategory::cross_field, "$/run/raw_reconciliation",
          "ANALYSIS-RECONCILIATION-EXACT",
          "raw observations must pass exact Stage 12 reconciliation");
    } else {
      std::map<std::uint64_t, std::uint64_t> observed;
      for (const auto& row : reconciled.joined_rows) {
        ++observed[row.end_to_end_latency];
      }
      std::map<std::uint64_t, std::uint64_t> encoded;
      for (const auto& value : run.end_to_end_latencies) {
        encoded.emplace(value.latency_ticks, value.multiplicity);
      }
      if (observed != encoded) {
        add(errors, protocol::ErrorCategory::reference_mismatch, "$/run/latencies",
            "ANALYSIS-INTERVALS-EXACT",
            "encoded latencies must equal exact joined derived intervals");
      }
    }
  } else if (!run.prior_stage12_validation_passed) {
    add(errors, protocol::ErrorCategory::missing_evidence,
        "$/run/prior_stage12_validation_passed", "ANALYSIS-PRIOR-JOIN",
        "run requires exact reconciliation or immutable prior Stage 12 proof");
  }
  if (run.validity == protocol::RunValidity::not_evaluated) {
    add(errors, protocol::ErrorCategory::missing_evidence, "$/run/validity",
        "ANALYSIS-VALIDITY-EVALUATED",
        "analysis cannot consume a run whose validity is not evaluated");
  }
  if (!errors.empty()) {
    return protocol::Result<RunSummary>::failure(std::move(errors));
  }
  auto p50 = exact_inverse_ecdf_quantile(run.end_to_end_latencies, 1U, 2U);
  auto p90 = exact_inverse_ecdf_quantile(run.end_to_end_latencies, 9U, 10U);
  auto p99 = exact_inverse_ecdf_quantile(run.end_to_end_latencies, 99U, 100U);
  auto p999 = exact_inverse_ecdf_quantile(run.end_to_end_latencies, 999U, 1000U);
  if (!p50 || !p90 || !p99 || !p999 || p999.value() == 0U) {
    return fail<RunSummary>(protocol::ErrorCategory::out_of_range, "$/run/latencies",
                            "ANALYSIS-QUANTILES",
                            "registered quantiles require positive latency values");
  }
  std::optional<std::uint64_t> p9999;
  if (run.n_eff_p999 >= 2'000'000U) {
    auto value = exact_inverse_ecdf_quantile(run.end_to_end_latencies, 9'999U, 10'000U);
    if (!value) {
      return protocol::Result<RunSummary>::failure(value.errors());
    }
    p9999 = value.value();
  }
  auto summarize_diagnostic =
      [&](std::span<const WeightedLatency> values) -> protocol::Result<RunQuantiles> {
    auto d50 = exact_inverse_ecdf_quantile(values, 1U, 2U);
    auto d90 = exact_inverse_ecdf_quantile(values, 9U, 10U);
    auto d99 = exact_inverse_ecdf_quantile(values, 99U, 100U);
    auto d999 = exact_inverse_ecdf_quantile(values, 999U, 1000U);
    if (!d50 || !d90 || !d99 || !d999) {
      return fail<RunQuantiles>(protocol::ErrorCategory::cross_field,
                                "$/run/diagnostics", "ANALYSIS-DIAGNOSTIC-QUANTILES",
                                "diagnostic series must support registered quantiles");
    }
    return protocol::Result<RunQuantiles>::success(
        {d50.value(), d90.value(), d99.value(), d999.value(), std::nullopt,
         values.back().latency_ticks});
  };
  auto lateness = summarize_diagnostic(run.diagnostics.producer_lateness);
  auto enqueue = summarize_diagnostic(run.diagnostics.enqueue_service);
  auto admission = summarize_diagnostic(run.diagnostics.admission_delay);
  auto residence = summarize_diagnostic(run.diagnostics.queue_residence);
  auto dequeue = summarize_diagnostic(run.diagnostics.dequeue_service);
  auto delivery = summarize_diagnostic(run.diagnostics.post_dequeue_delivery);
  auto action = summarize_diagnostic(run.diagnostics.consumer_action);
  if (!lateness || !enqueue || !admission || !residence || !dequeue || !delivery ||
      !action) {
    return fail<RunSummary>(protocol::ErrorCategory::cross_field, "$/run/diagnostics",
                            "ANALYSIS-DIAGNOSTIC-QUANTILES",
                            "all registered diagnostic series are required");
  }
  const auto zero_loss =
      run.full_count == 0U ? protocol::GateStatus::pass : protocol::GateStatus::fail;
  const auto tail = run.n_eff_p999 >= 200'000U ? protocol::GateStatus::pass
                                               : protocol::GateStatus::fail;
  std::vector<protocol::ConfirmatoryBlocker> blockers;
  if (tail == protocol::GateStatus::fail) {
    blockers.push_back(protocol::ConfirmatoryBlocker::blocked_effective_tail);
  }
  if (run.validity == protocol::RunValidity::invalid) {
    blockers.push_back(protocol::ConfirmatoryBlocker::blocked_invalid_run);
  }
  if (zero_loss == protocol::GateStatus::fail) {
    blockers.push_back(protocol::ConfirmatoryBlocker::blocked_zero_loss);
  }
  std::sort(blockers.begin(), blockers.end());
  protocol::ConfirmatoryEstimability estimability =
      protocol::ConfirmatoryEstimability::estimable;
  if (blockers.size() > 1U) {
    estimability = protocol::ConfirmatoryEstimability::blocked_multiple;
  } else if (!blockers.empty()) {
    switch (blockers.front()) {
    case protocol::ConfirmatoryBlocker::blocked_effective_tail:
      estimability = protocol::ConfirmatoryEstimability::blocked_effective_tail;
      break;
    case protocol::ConfirmatoryBlocker::blocked_invalid_run:
      estimability = protocol::ConfirmatoryEstimability::blocked_invalid_run;
      break;
    case protocol::ConfirmatoryBlocker::blocked_zero_loss:
      estimability = protocol::ConfirmatoryEstimability::blocked_zero_loss;
      break;
    case protocol::ConfirmatoryBlocker::blocked_access_leakage:
    case protocol::ConfirmatoryBlocker::blocked_incomplete_block:
      estimability = protocol::ConfirmatoryEstimability::blocked_multiple;
      break;
    }
  }
  return protocol::Result<RunSummary>::success(
      {run.run_id,
       run.block_id,
       run.block_role,
       run.package,
       run.hardware_state,
       run.placement,
       run.working_set,
       run.load,
       run.validity,
       zero_loss,
       tail,
       estimability,
       std::move(blockers),
       {p50.value(), p90.value(), p99.value(), p999.value(), p9999,
        run.end_to_end_latencies.back().latency_ticks},
       lateness.value(),
       enqueue.value(),
       admission.value(),
       residence.value(),
       dequeue.value(),
       delivery.value(),
       action.value(),
       {run.consumed_count, run.measurement_horizon_ticks},
       {run.full_count, run.attempted_count},
       run.final_occupancy,
       std::log(static_cast<double>(p999.value()))});
}

auto stage_a_design_rank() -> std::size_t {
  std::vector<std::vector<double>> matrix;
  matrix.reserve(orchestration::kStageACellsPerBlock);
  for (const auto& [package, hardware, placement, working_set, load] :
       orchestration::expected_stage_a_cells()) {
    const double q =
        package == protocol::QueuePackage::l0 || package == protocol::QueuePackage::l1
            ? 1.0
            : 0.0;
    const double xr1 = package == protocol::QueuePackage::r1 ? 1.0 : 0.0;
    const double xr2 = package == protocol::QueuePackage::r2 ? 1.0 : 0.0;
    const double xl1 = package == protocol::QueuePackage::l1 ? 1.0 : 0.0;
    const double h = hardware == protocol::RequestedHardwareState::h0 ? -0.5 : 0.5;
    const double p = placement == protocol::Placement::near ? -0.5 : 0.5;
    const std::array<double, 2> w{
        working_set == protocol::WorkingSetClass::l2_resident  ? 1.0
        : working_set == protocol::WorkingSetClass::beyond_llc ? -1.0
                                                               : 0.0,
        working_set == protocol::WorkingSetClass::llc_resident ? 1.0
        : working_set == protocol::WorkingSetClass::beyond_llc ? -1.0
                                                               : 0.0};
    const std::array<double, 2> a{load == protocol::LoadLevel::l025   ? 1.0
                                  : load == protocol::LoadLevel::l075 ? -1.0
                                                                      : 0.0,
                                  load == protocol::LoadLevel::l050   ? 1.0
                                  : load == protocol::LoadLevel::l075 ? -1.0
                                                                      : 0.0};
    const std::array context{p, w[0], w[1], a[0], a[1]};
    std::vector<double> row{1.0, q, xr1, xr2, xl1, h};
    row.insert(row.end(), context.begin(), context.end());
    for (const auto value : context) {
      row.push_back(q * value);
    }
    row.push_back(q * h);
    row.push_back(xr1 * h);
    row.push_back(xr2 * h);
    row.push_back(xl1 * h);
    for (const auto value : context) {
      row.push_back(h * value);
    }
    for (const auto software : {xr1, xr2, xl1}) {
      for (const auto value : context) {
        row.push_back(software * value);
      }
    }
    matrix.push_back(std::move(row));
  }
  std::size_t rank = 0U;
  const auto columns = matrix.front().size();
  for (std::size_t column = 0U; column < columns && rank < matrix.size(); ++column) {
    auto pivot = rank;
    for (std::size_t row = rank + 1U; row < matrix.size(); ++row) {
      if (std::abs(matrix[row][column]) > std::abs(matrix[pivot][column])) {
        pivot = row;
      }
    }
    if (std::abs(matrix[pivot][column]) < 1.0e-12) {
      continue;
    }
    std::swap(matrix[pivot], matrix[rank]);
    const auto divisor = matrix[rank][column];
    for (std::size_t value = column; value < columns; ++value) {
      matrix[rank][value] /= divisor;
    }
    for (std::size_t row = 0U; row < matrix.size(); ++row) {
      if (row == rank) {
        continue;
      }
      const auto factor = matrix[row][column];
      for (std::size_t value = column; value < columns; ++value) {
        matrix[row][value] -= factor * matrix[rank][value];
      }
    }
    ++rank;
  }
  return rank;
}

auto h1_block_contrasts(const CompleteBlockResponse& block)
    -> protocol::Result<std::vector<double>> {
  auto values = cell_map(block);
  if (!values) {
    return protocol::Result<std::vector<double>>::failure(values.errors());
  }
  constexpr std::array placements{protocol::Placement::near, protocol::Placement::far};
  constexpr std::array working_sets{protocol::WorkingSetClass::l2_resident,
                                    protocol::WorkingSetClass::llc_resident,
                                    protocol::WorkingSetClass::beyond_llc};
  constexpr std::array loads{protocol::LoadLevel::l025, protocol::LoadLevel::l050,
                             protocol::LoadLevel::l075};
  std::vector<double> result(7U, 0.0);
  for (const auto placement : placements) {
    for (const auto working_set : working_sets) {
      for (const auto load : loads) {
        const auto er1 = software_effect(values.value(), protocol::QueuePackage::r1,
                                         placement, working_set, load);
        const auto er2 = software_effect(values.value(), protocol::QueuePackage::r2,
                                         placement, working_set, load);
        const auto el1 = software_effect(values.value(), protocol::QueuePackage::l1,
                                         placement, working_set, load);
        result[0] += er1 - el1;
        result[1] += er2 - el1;
        result[2] += hardware_effect(values.value(), protocol::QueuePackage::l0,
                                     placement, working_set, load) -
                     hardware_effect(values.value(), protocol::QueuePackage::r0,
                                     placement, working_set, load);
        result[3] += hardware_effect(values.value(), protocol::QueuePackage::r1,
                                     placement, working_set, load) -
                     hardware_effect(values.value(), protocol::QueuePackage::r0,
                                     placement, working_set, load);
        result[4] += hardware_effect(values.value(), protocol::QueuePackage::r2,
                                     placement, working_set, load) -
                     hardware_effect(values.value(), protocol::QueuePackage::r0,
                                     placement, working_set, load);
        result[5] += hardware_effect(values.value(), protocol::QueuePackage::l1,
                                     placement, working_set, load) -
                     hardware_effect(values.value(), protocol::QueuePackage::l0,
                                     placement, working_set, load);
        result[6] += er2 - er1;
      }
    }
  }
  for (auto& value : result) {
    value /= 18.0;
  }
  return protocol::Result<std::vector<double>>::success(result);
}

auto h2_block_contrasts(const CompleteBlockResponse& block)
    -> protocol::Result<std::vector<double>> {
  auto values = cell_map(block);
  if (!values) {
    return protocol::Result<std::vector<double>>::failure(values.errors());
  }
  constexpr std::array operators{"P", "W12", "W23", "A12", "A23"};
  constexpr std::array suffixes{"H", "R1", "R2", "L1"};
  std::vector<double> result;
  result.reserve(orchestration::kH2ContrastCount);
  for (const auto op : operators) {
    for (const auto suffix : suffixes) {
      result.push_back(h2_operator(values.value(), {op, suffix}));
    }
  }
  return protocol::Result<std::vector<double>>::success(result);
}

auto evaluate_prospective_precision(const ProspectivePrecisionInput& input,
                                    double delta_star)
    -> protocol::Result<orchestration::ProspectiveCounts> {
  if (!(std::isfinite(delta_star) && delta_star > 0.0)) {
    return fail<orchestration::ProspectiveCounts>(
        protocol::ErrorCategory::out_of_range, "$/precision/delta_star",
        "ANALYSIS-DELTA-STAR", "delta_star must be explicit, finite, and positive");
  }
  auto h1 = select_prospective_count(input.h1, FamilyKind::h1_two_sided, delta_star);
  auto h2 = select_prospective_count(input.h2, FamilyKind::h2_two_sided, delta_star);
  auto train = select_prospective_count(
      input.h3_training, FamilyKind::h3_training_standard_error, delta_star);
  auto validation = select_prospective_count(
      input.h3_validation, FamilyKind::h3_validation_one_sided, delta_star);
  if (!h1 || !h2 || !train || !validation) {
    std::vector<protocol::ValidationError> errors;
    for (const auto* result : {&h1, &h2, &train, &validation}) {
      errors.insert(errors.end(), result->errors().begin(), result->errors().end());
    }
    return protocol::Result<orchestration::ProspectiveCounts>::failure(
        std::move(errors));
  }
  const auto r12 = std::max(h1.value(), h2.value());
  if (train.value() > std::numeric_limits<std::uint64_t>::max() - validation.value()) {
    return fail<orchestration::ProspectiveCounts>(
        protocol::ErrorCategory::out_of_range, "$/precision",
        "ANALYSIS-PRECISION-OVERFLOW", "Rtrain+Rval overflows u64");
  }
  const auto rtotal = std::max(r12, train.value() + validation.value());
  if (rtotal >
      std::numeric_limits<std::uint64_t>::max() / orchestration::kStageACellsPerBlock) {
    return fail<orchestration::ProspectiveCounts>(
        protocol::ErrorCategory::out_of_range, "$/precision",
        "ANALYSIS-PRECISION-OVERFLOW", "180*Rtotal overflows u64");
  }
  return protocol::Result<orchestration::ProspectiveCounts>::success(
      {h1.value(), h2.value(), r12, train.value(), validation.value(), rtotal,
       rtotal * orchestration::kStageACellsPerBlock});
}

auto two_sided_max_t(std::string family_id,
                     std::span<const std::string_view> stable_ids,
                     std::span<const std::vector<double>> complete_block_contrasts,
                     const BootstrapConfiguration& bootstrap, double delta_star)
    -> protocol::Result<MaxTResult> {
  return max_t(std::move(family_id), stable_ids, complete_block_contrasts, bootstrap,
               delta_star, false);
}

auto select_h3_training(std::span<const CompleteBlockResponse> training_blocks,
                        std::span<const protocol::ArtifactReference> training_sources)
    -> protocol::Result<H3SelectionRecord> {
  if (training_blocks.size() < 12U || training_sources.empty() ||
      !std::all_of(training_blocks.begin(), training_blocks.end(),
                   [](const auto& block) {
                     return block.role == protocol::BlockRole::h3_train;
                   })) {
    return fail<H3SelectionRecord>(
        protocol::ErrorCategory::missing_evidence, "$/h3/training",
        "ANALYSIS-H3-TRAINING-BLOCKS",
        "H3 selection requires at least 12 complete training-role blocks");
  }
  std::map<protocol::H3Context, protocol::H3Candidate> selections;
  const auto candidates = orchestration::h3_candidates();
  for (const auto context : orchestration::h3_contexts()) {
    bool first = true;
    double selected_mean = 0.0;
    protocol::H3Candidate selected = candidates.front();
    for (const auto& candidate : candidates) {
      double sum = 0.0;
      for (const auto& block : training_blocks) {
        auto value = h3_value(block, context, candidate);
        if (!value) {
          return protocol::Result<H3SelectionRecord>::failure(value.errors());
        }
        sum += value.value();
      }
      const auto mean = sum / static_cast<double>(training_blocks.size());
      if (first || mean < selected_mean) {
        first = false;
        selected_mean = mean;
        selected = candidate;
      }
    }
    selections.emplace(context, selected);
  }
  JsonObject root;
  root.emplace("protocol_version",
               string_value(std::string(protocol::kProtocolVersion)));
  root.emplace("schema_version", string_value(std::string(kSelectionSchema)));
  root.emplace("selection_rule_version",
               string_value(std::string(orchestration::kH3SelectionRuleId)));
  JsonObject selected_values;
  for (const auto& [context, candidate] : selections) {
    selected_values.emplace(std::string(context_name(context)),
                            string_value(candidate_name(candidate)));
  }
  root.emplace("selections", protocol::json::Value(std::move(selected_values)));
  JsonArray sources;
  std::vector<protocol::ArtifactReference> sorted(training_sources.begin(),
                                                  training_sources.end());
  std::sort(sorted.begin(), sorted.end(), [](const auto& left, const auto& right) {
    return left.artifact_id.value() < right.artifact_id.value();
  });
  for (const auto& source : sorted) {
    sources.emplace_back(artifact_value(source));
  }
  root.emplace("training_sources", protocol::json::Value(std::move(sources)));
  root.emplace("record_sha256", string_value(std::string(64U, '0')));
  auto zero_self = canonical(root);
  if (!zero_self) {
    return protocol::Result<H3SelectionRecord>::failure(zero_self.errors());
  }
  const auto digest = sha_text(zero_self.value());
  root["record_sha256"] = string_value(digest.hex());
  auto final = canonical(std::move(root));
  if (!final) {
    return protocol::Result<H3SelectionRecord>::failure(final.errors());
  }
  return protocol::Result<H3SelectionRecord>::success(
      {std::string(kSelectionSchema), std::move(selections), std::move(sorted),
       std::move(final).value(), digest});
}

auto evaluate_h3_validation(std::span<const CompleteBlockResponse> validation_blocks,
                            const H3SelectionRecord& selection,
                            const BootstrapConfiguration& bootstrap, double delta_star)
    -> protocol::Result<H3ValidationResult> {
  if (validation_blocks.size() < 8U ||
      !std::all_of(validation_blocks.begin(), validation_blocks.end(),
                   [](const auto& block) {
                     return block.role == protocol::BlockRole::h3_validation;
                   })) {
    return fail<H3ValidationResult>(
        protocol::ErrorCategory::missing_evidence, "$/h3/validation",
        "ANALYSIS-H3-VALIDATION-BLOCKS",
        "H3 validation requires at least eight complete validation-role blocks");
  }
  auto comparisons = orchestration::h3_reported_comparisons(selection.selections);
  if (!comparisons) {
    return protocol::Result<H3ValidationResult>::failure(comparisons.errors());
  }
  std::vector<std::string> ids_storage;
  ids_storage.reserve(comparisons.value().size());
  for (const auto& comparison : comparisons.value()) {
    ids_storage.push_back(std::string(context_name(comparison.context)) + ":" +
                          candidate_name(comparison.left) + "-MINUS-" +
                          candidate_name(comparison.right));
  }
  std::vector<std::string_view> ids;
  ids.reserve(ids_storage.size());
  for (const auto& value : ids_storage) {
    ids.push_back(value);
  }
  std::vector<std::vector<double>> block_differences;
  block_differences.reserve(validation_blocks.size());
  for (const auto& block : validation_blocks) {
    std::vector<double> differences;
    differences.reserve(comparisons.value().size());
    for (const auto& comparison : comparisons.value()) {
      auto left = h3_value(block, comparison.context, comparison.left);
      auto right = h3_value(block, comparison.context, comparison.right);
      if (!left || !right) {
        return fail<H3ValidationResult>(
            protocol::ErrorCategory::cross_field, "$/h3/validation/cells",
            "ANALYSIS-H3-VALIDATION-CELLS",
            "every selected and alternative validation cell is required");
      }
      differences.push_back(left.value() - right.value());
    }
    block_differences.push_back(std::move(differences));
  }
  auto result = max_t("H3-SELECTED-54-ONE-SIDED", ids, block_differences, bootstrap,
                      delta_star, true);
  if (!result) {
    return protocol::Result<H3ValidationResult>::failure(result.errors());
  }
  const auto passes =
      std::all_of(result.value().intervals.begin(), result.value().intervals.end(),
                  [&](const auto& interval) { return interval.upper < delta_star; });
  return protocol::Result<H3ValidationResult>::success(
      {InferenceState::estimable, std::move(result).value(), passes, {}});
}

auto canonical_configuration(const AnalysisConfiguration& configuration)
    -> protocol::Result<std::string> {
  JsonObject root;
  root.emplace("analysis_profile", string_value(configuration.analysis_profile));
  JsonObject bootstrap;
  bootstrap.emplace("key0", unsigned_value(configuration.bootstrap.key.words[0]));
  bootstrap.emplace("key1", unsigned_value(configuration.bootstrap.key.words[1]));
  bootstrap.emplace("profile", string_value(configuration.bootstrap.profile));
  bootstrap.emplace("replicates", unsigned_value(configuration.bootstrap.replicates));
  bootstrap.emplace("rng_algorithm_version",
                    string_value(configuration.bootstrap.rng_algorithm_version));
  bootstrap.emplace("seed_id",
                    string_value(std::string(configuration.bootstrap.seed_id.value())));
  root.emplace("bootstrap", protocol::json::Value(std::move(bootstrap)));
  root.emplace("configuration_artifact_id",
               string_value(std::string(
                   configuration.configuration_artifact.artifact_id.value())));
  root.emplace("delta_star_binary64",
               string_value(float_bits(configuration.delta_star)));
  JsonObject counts;
  counts.emplace("nruns", unsigned_value(configuration.expected_counts.nruns));
  counts.emplace("r12", unsigned_value(configuration.expected_counts.r12));
  counts.emplace("r_h1", unsigned_value(configuration.expected_counts.r_h1));
  counts.emplace("r_h2", unsigned_value(configuration.expected_counts.r_h2));
  counts.emplace("rtrain", unsigned_value(configuration.expected_counts.rtrain));
  counts.emplace("rtotal", unsigned_value(configuration.expected_counts.rtotal));
  counts.emplace("rval", unsigned_value(configuration.expected_counts.rval));
  root.emplace("expected_counts", protocol::json::Value(std::move(counts)));
  root.emplace("protocol_version", string_value(std::string(
                                       protocol_name(configuration.protocol_version))));
  JsonObject software;
  software.emplace("compiler", string_value(configuration.software.compiler));
  software.emplace("implementation_revision",
                   string_value(configuration.software.implementation_revision));
  software.emplace("standard_library",
                   string_value(configuration.software.standard_library));
  root.emplace("software", protocol::json::Value(std::move(software)));
  JsonArray sizing;
  for (const auto* family :
       {&configuration.precision.h1, &configuration.precision.h2,
        &configuration.precision.h3_training, &configuration.precision.h3_validation}) {
    sizing.emplace_back(artifact_value(family->sizing_artifact));
  }
  root.emplace("sizing_artifacts", protocol::json::Value(std::move(sizing)));
  return canonical(std::move(root));
}

auto run_synthetic_analysis(const AnalysisInput& input)
    -> protocol::Result<AnalysisOutput> {
  std::vector<protocol::ValidationError> errors;
  if (input.configuration.protocol_version != protocol::ProtocolVersion::v2_0_0_pre_2 ||
      input.configuration.analysis_profile != kAnalysisProfile ||
      input.configuration.bootstrap.profile != kBootstrapProfile ||
      input.configuration.bootstrap.rng_algorithm_version !=
          workload::kDeterministicSuite ||
      input.configuration.bootstrap.replicates < 2U ||
      input.configuration.software.implementation_revision.empty() ||
      input.configuration.software.compiler.empty() ||
      input.configuration.software.standard_library.empty()) {
    add(errors, protocol::ErrorCategory::missing_evidence, "$/configuration",
        "ANALYSIS-CONFIGURATION",
        "the versioned analysis, software, and bootstrap configuration is mandatory");
  }
  std::set<std::string> artifact_ids;
  for (std::size_t index = 0U; index < input.artifacts.size(); ++index) {
    const auto& artifact = input.artifacts[index];
    if (artifact.protocol_version != protocol::ProtocolVersion::v2_0_0_pre_2) {
      add(errors, protocol::ErrorCategory::unsupported_version,
          "$/artifacts/" + std::to_string(index), "ANALYSIS-MIXED-VERSION",
          "mixed protocol versions are forbidden");
    }
    if (!artifact_ids.emplace(artifact.reference.artifact_id.value()).second) {
      add(errors, protocol::ErrorCategory::duplicate_value,
          "$/artifacts/" + std::to_string(index), "ANALYSIS-ARTIFACT-UNIQUE",
          "artifact IDs must be globally unique");
    }
    if (!verify_artifact(artifact)) {
      add(errors, protocol::ErrorCategory::invalid_hash,
          "$/artifacts/" + std::to_string(index), "ANALYSIS-ARTIFACT-HASH",
          "every consumed artifact must be finalized and checksum-valid");
    }
  }
  auto config_bytes = canonical_configuration(input.configuration);
  const auto* config_artifact = find_artifact(
      input.artifacts, input.configuration.configuration_artifact.artifact_id.value());
  if (!config_bytes || config_artifact == nullptr ||
      config_artifact->reference != input.configuration.configuration_artifact ||
      !artifact_bytes_equal(*config_artifact,
                            config_bytes ? config_bytes.value() : std::string_view{})) {
    add(errors, protocol::ErrorCategory::invalid_hash, "$/configuration/artifact",
        "ANALYSIS-CONFIG-HASH",
        "configuration fields must equal the immutable configuration artifact");
  }
  auto precision = evaluate_prospective_precision(input.configuration.precision,
                                                  input.configuration.delta_star);
  if (!precision) {
    errors.insert(errors.end(), precision.errors().begin(), precision.errors().end());
  } else if (!same_counts(precision.value(), input.configuration.expected_counts)) {
    add(errors, protocol::ErrorCategory::cross_field, "$/configuration/expected_counts",
        "ANALYSIS-PRECISION-COUNTS",
        "expected counts must equal the prospective family calculations");
  }
  for (const auto* family :
       {&input.configuration.precision.h1, &input.configuration.precision.h2,
        &input.configuration.precision.h3_training,
        &input.configuration.precision.h3_validation}) {
    const auto* sizing =
        find_artifact(input.artifacts, family->sizing_artifact.artifact_id.value());
    if (sizing == nullptr || sizing->reference != family->sizing_artifact ||
        !verify_artifact(*sizing)) {
      add(errors, protocol::ErrorCategory::missing_evidence,
          "$/configuration/precision", "ANALYSIS-SIZING-HASH",
          "every prospective precision family must resolve immutable sizing evidence");
    }
  }
  if (stage_a_design_rank() != 40U) {
    add(errors, protocol::ErrorCategory::cross_field, "$/analysis/design",
        "ANALYSIS-DESIGN-RANK", "the frozen 40-column Stage A design is not full rank");
  }

  std::set<std::string> block_ids_seen;
  std::set<std::string> active_replaced_ids;
  std::set<std::string> platform_ids;
  std::set<std::string> build_ids;
  std::map<protocol::BlockRole, std::uint64_t> active_role_counts;
  for (std::size_t index = 0U; index < input.blocks.size(); ++index) {
    const auto& block = input.blocks[index];
    const auto base = "$/blocks/" + std::to_string(index);
    if (!block_ids_seen.emplace(block.plan.block_id.value()).second) {
      add(errors, protocol::ErrorCategory::duplicate_value, base + "/block_id",
          "ANALYSIS-BLOCK-ID-UNIQUE", "block IDs must be unique");
    }
    platform_ids.emplace(block.plan.platform_id.value());
    build_ids.emplace(block.plan.build_id.value());
    if (!block.stage14_cross_record_validation_passed) {
      add(errors, protocol::ErrorCategory::missing_evidence, base,
          "ANALYSIS-STAGE14-PROOF",
          "every block requires a passing Stage 14 cross-record proof");
    }
    const auto plan_errors = orchestration::validate_block_plan(
        block.plan, block.seed_catalog, input.namespaces);
    errors.insert(errors.end(), plan_errors.begin(), plan_errors.end());
    const auto* plan_artifact =
        find_artifact(input.artifacts, block.plan_artifact.artifact_id.value());
    if (plan_artifact == nullptr || plan_artifact->reference != block.plan_artifact ||
        !verify_artifact(*plan_artifact)) {
      add(errors, protocol::ErrorCategory::invalid_hash, base + "/plan_artifact",
          "ANALYSIS-PLAN-HASH",
          "block plan artifact must resolve and pass its checksum");
    }
    if (block.plan.replaces_block_id) {
      if (!block.replacement_budget_validation_passed) {
        add(errors, protocol::ErrorCategory::missing_evidence, base,
            "ANALYSIS-REPLACEMENT-BUDGET",
            "an active replacement requires passing frozen-budget evidence");
      }
      if (!active_replaced_ids.emplace(block.plan.replaces_block_id->value()).second) {
        add(errors, protocol::ErrorCategory::duplicate_value, base,
            "ANALYSIS-REPLACEMENT-BRANCH",
            "multiple replacements of one original block are forbidden");
      }
    }
    if (block.active_primary) {
      ++active_role_counts[block.plan.block_role];
    }
  }
  if (platform_ids.size() != 1U || build_ids.size() != 1U) {
    add(errors, protocol::ErrorCategory::cross_field, "$/blocks",
        "ANALYSIS-PLATFORM-CONDITIONED",
        "one analysis invocation is conditioned on exactly one platform and build; "
        "mixed-platform random effects require a separately frozen profile");
  }
  for (const auto& block : input.blocks) {
    if (block.plan.replaces_block_id) {
      const auto original = std::find_if(
          input.blocks.begin(), input.blocks.end(), [&](const auto& candidate) {
            return candidate.plan.block_id == *block.plan.replaces_block_id;
          });
      if (original == input.blocks.end() || original->active_primary ||
          !block.active_primary || original->plan.block_role != block.plan.block_role ||
          original->plan.platform_id != block.plan.platform_id ||
          original->plan.build_id != block.plan.build_id) {
        add(errors, protocol::ErrorCategory::cross_field, "$/blocks/replacement",
            "ANALYSIS-REPLACEMENT-LINEAGE",
            "active replacement must supersede one retained inactive original "
            "with the same role/platform/build");
      }
    }
  }
  if (precision) {
    const auto expected_train = precision.value().rtrain;
    const auto expected_validation = precision.value().rval;
    const auto train_validation = expected_train + expected_validation;
    const auto expected_supplemental = precision.value().r12 > train_validation
                                           ? precision.value().r12 - train_validation
                                           : 0U;
    if (active_role_counts[protocol::BlockRole::h3_train] != expected_train ||
        active_role_counts[protocol::BlockRole::h3_validation] != expected_validation ||
        active_role_counts[protocol::BlockRole::h1h2_supplemental] !=
            expected_supplemental) {
      add(errors, protocol::ErrorCategory::cross_field, "$/blocks/roles",
          "ANALYSIS-BLOCK-ROLE-COUNTS",
          "active block roles must equal Rtrain/Rval/R12-derived counts");
    }
  }

  const auto train_ids = block_ids(input.blocks, protocol::BlockRole::h3_train, true);
  const auto validation_ids =
      block_ids(input.blocks, protocol::BlockRole::h3_validation, true);
  std::vector<protocol::BlockId> all_active_ids;
  for (const auto& block : input.blocks) {
    if (block.active_primary) {
      all_active_ids.push_back(block.plan.block_id);
    }
  }
  for (const auto& grant_errors :
       {validate_grant(input.training_access, orchestration::OutcomeDomain::h3_training,
                       train_ids, input.artifacts),
        validate_grant(input.validation_access,
                       orchestration::OutcomeDomain::h3_validation, validation_ids,
                       input.artifacts),
        validate_grant(input.h1h2_access, orchestration::OutcomeDomain::h1h2,
                       all_active_ids, input.artifacts)}) {
    errors.insert(errors.end(), grant_errors.begin(), grant_errors.end());
  }

  std::set<std::string> run_ids;
  std::map<std::string, std::vector<const SyntheticRunInput*>> runs_by_block;
  for (std::size_t index = 0U; index < input.runs.size(); ++index) {
    const auto& run = input.runs[index];
    if (!run_ids.emplace(run.run_id.value()).second) {
      add(errors, protocol::ErrorCategory::duplicate_value,
          "$/runs/" + std::to_string(index) + "/run_id", "ANALYSIS-RUN-ID-UNIQUE",
          "run IDs must be unique and cannot encode filtering aliases");
    }
    runs_by_block[std::string(run.block_id.value())].push_back(&run);
  }
  for (const auto& block : input.blocks) {
    const auto iterator = runs_by_block.find(std::string(block.plan.block_id.value()));
    if (iterator == runs_by_block.end() ||
        iterator->second.size() != orchestration::kStageACellsPerBlock) {
      add(errors, protocol::ErrorCategory::missing_evidence, "$/runs",
          "ANALYSIS-NO-FILTERING",
          "every retained original/replacement block requires exactly 180 run "
          "records; cell filtering is forbidden");
      continue;
    }
    std::set<std::uint64_t> ordinals;
    for (const auto* run : iterator->second) {
      if (run->protocol_version != block.plan.protocol_version ||
          run->block_role != block.plan.block_role ||
          !ordinals.emplace(run->cell_ordinal).second ||
          run->cell_ordinal >= block.plan.cells.size()) {
        add(errors, protocol::ErrorCategory::cross_field, "$/runs",
            "ANALYSIS-RUN-PLAN-BINDING",
            "run version, role, and unique cell ordinal must match its block plan");
        continue;
      }
      const auto& cell = block.plan.cells[run->cell_ordinal];
      if (cell.cell_ordinal != run->cell_ordinal || cell.package != run->package ||
          cell.requested_hardware_state != run->hardware_state ||
          cell.placement != run->placement ||
          cell.working_set_class != run->working_set || cell.load_level != run->load) {
        add(errors, protocol::ErrorCategory::cross_field, "$/runs",
            "ANALYSIS-NO-CELL-REPLACEMENT",
            "run factors must match the exact planned cell; cell-level repair is "
            "forbidden");
      }
    }
    if (block.plan.replaces_block_id) {
      const auto original_runs =
          runs_by_block.find(std::string(block.plan.replaces_block_id->value()));
      if (original_runs == runs_by_block.end() ||
          !std::any_of(original_runs->second.begin(), original_runs->second.end(),
                       [](const auto* run) {
                         return run->validity == protocol::RunValidity::invalid;
                       })) {
        add(errors, protocol::ErrorCategory::missing_evidence, "$/blocks/replacement",
            "ANALYSIS-REPLACEMENT-INVALID-RUN",
            "a replacement requires a retained invalid required run in the "
            "original block");
      }
    }
  }
  if (!errors.empty()) {
    return protocol::Result<AnalysisOutput>::failure(std::move(errors));
  }

  std::vector<RunSummary> summaries;
  summaries.reserve(input.runs.size());
  std::vector<protocol::ValidationError> summary_errors;
  for (const auto& run : input.runs) {
    auto summary = summarize_run(run, input.artifacts);
    if (!summary) {
      summary_errors.insert(summary_errors.end(), summary.errors().begin(),
                            summary.errors().end());
    } else {
      summaries.push_back(std::move(summary).value());
    }
  }
  if (!summary_errors.empty()) {
    return protocol::Result<AnalysisOutput>::failure(std::move(summary_errors));
  }

  bool gate_blocked = false;
  for (const auto& block : input.blocks) {
    const auto& block_runs = runs_by_block.at(std::string(block.plan.block_id.value()));
    const auto has_invalid =
        std::any_of(block_runs.begin(), block_runs.end(), [](const auto* run) {
          return run->validity == protocol::RunValidity::invalid;
        });
    if (block.active_primary && has_invalid) {
      return fail<AnalysisOutput>(
          protocol::ErrorCategory::cross_field, "$/blocks/active",
          "ANALYSIS-INCOMPLETE-BLOCK",
          "an active primary block contains an invalid run; only an authorized "
          "complete replacement may supersede it");
    }
    if (block.active_primary &&
        std::any_of(block_runs.begin(), block_runs.end(), [](const auto* run) {
          return run->full_count != 0U || run->n_eff_p999 < 200'000U;
        })) {
      gate_blocked = true;
    }
  }

  std::vector<CompleteBlockResponse> primary_blocks;
  primary_blocks.reserve(all_active_ids.size());
  for (const auto& block : input.blocks) {
    if (!block.active_primary) {
      continue;
    }
    CompleteBlockResponse response{block.plan.block_id, block.plan.block_role, {}};
    response.cells.reserve(orchestration::kStageACellsPerBlock);
    const auto& block_runs = runs_by_block.at(std::string(block.plan.block_id.value()));
    for (const auto* run : block_runs) {
      const auto iterator =
          std::find_if(summaries.begin(), summaries.end(), [&](const auto& summary) {
            return summary.run_id == run->run_id;
          });
      response.cells.push_back({run->package, run->hardware_state, run->placement,
                                run->working_set, run->load, iterator->log_p999});
    }
    primary_blocks.push_back(std::move(response));
  }

  std::vector<StageReceipt> stages;
  stages.push_back({AnalysisStage::artifact_validation, "v1", {}});
  stages.push_back({AnalysisStage::reconciliation_verification, "v1", {}});
  stages.push_back({AnalysisStage::interval_derivation, "v1", {}});
  stages.push_back({AnalysisStage::run_gates, "v1", {}});
  stages.push_back({AnalysisStage::run_summaries, "v1", {}});
  stages.push_back({AnalysisStage::complete_blocks, "v1", {}});

  std::optional<H3SelectionRecord> selection;
  std::optional<H3ValidationResult> h3;
  std::optional<MaxTResult> h1;
  std::optional<MaxTResult> h2;
  auto state = gate_blocked ? InferenceState::blocked : InferenceState::estimable;
  if (!gate_blocked) {
    std::vector<CompleteBlockResponse> training_blocks;
    std::vector<CompleteBlockResponse> validation_blocks;
    for (const auto& block : primary_blocks) {
      if (block.role == protocol::BlockRole::h3_train) {
        training_blocks.push_back(block);
      } else if (block.role == protocol::BlockRole::h3_validation) {
        validation_blocks.push_back(block);
      }
    }
    std::set<std::string> active_training_block_ids;
    for (const auto& block : training_blocks) {
      active_training_block_ids.emplace(block.block_id.value());
    }
    std::vector<protocol::ArtifactReference> training_sources;
    for (const auto& run : input.runs) {
      if (run.block_role == protocol::BlockRole::h3_train &&
          run.load == protocol::LoadLevel::l050 &&
          active_training_block_ids.contains(std::string(run.block_id.value()))) {
        training_sources.push_back(run.joined_artifact);
      }
    }
    auto selected = select_h3_training(training_blocks, training_sources);
    if (!selected) {
      return protocol::Result<AnalysisOutput>::failure(selected.errors());
    }
    selection = std::move(selected).value();
    stages.push_back({AnalysisStage::h3_training, "v1", training_sources});
    stages.push_back({AnalysisStage::selection_freeze, "v1", training_sources});
    stages.push_back({AnalysisStage::validation_unseal,
                      "v1",
                      {input.validation_access.access_record()}});
    auto evaluated = evaluate_h3_validation(validation_blocks, *selection,
                                            input.configuration.bootstrap,
                                            input.configuration.delta_star);
    if (!evaluated) {
      return protocol::Result<AnalysisOutput>::failure(evaluated.errors());
    }
    h3 = std::move(evaluated).value();
    stages.push_back({AnalysisStage::h3_validation, "v1", {}});
    stages.push_back({AnalysisStage::h3_evaluation, "v1", {}});
    stages.push_back(
        {AnalysisStage::h1h2_release, "v1", {input.h1h2_access.access_record()}});

    std::vector<std::vector<double>> h1_vectors;
    std::vector<std::vector<double>> h2_vectors;
    h1_vectors.reserve(primary_blocks.size());
    h2_vectors.reserve(primary_blocks.size());
    for (const auto& block : primary_blocks) {
      auto h1_vector = h1_block_contrasts(block);
      auto h2_vector = h2_block_contrasts(block);
      if (!h1_vector || !h2_vector) {
        return fail<AnalysisOutput>(protocol::ErrorCategory::cross_field,
                                    "$/analysis/contrasts", "ANALYSIS-CONTRAST-CELLS",
                                    "registered contrasts require all exact cells");
      }
      h1_vectors.push_back(std::move(h1_vector).value());
      h2_vectors.push_back(std::move(h2_vector).value());
    }
    const auto h1_ids = orchestration::h1_contrast_ids();
    const auto h2_ids = orchestration::h2_contrast_ids();
    auto h1_result =
        two_sided_max_t("H1-SEVEN-TWO-SIDED", h1_ids, h1_vectors,
                        input.configuration.bootstrap, input.configuration.delta_star);
    auto h2_result =
        two_sided_max_t("H2-TWENTY-TWO-SIDED", h2_ids, h2_vectors,
                        input.configuration.bootstrap, input.configuration.delta_star);
    if (!h1_result || !h2_result) {
      return fail<AnalysisOutput>(protocol::ErrorCategory::cross_field,
                                  "$/analysis/max_t", "ANALYSIS-MAXT",
                                  "separate H1 and H2 max-T families must both pass");
    }
    h1 = std::move(h1_result).value();
    h2 = std::move(h2_result).value();
    stages.push_back({AnalysisStage::h1h2_analysis, "v1", {}});
  }

  stages.push_back({AnalysisStage::reporting, "v1", {}});
  const auto configuration_hash = sha_text(config_bytes.value());
  auto zero_self = build_machine_report(
      input.configuration, state, summaries, primary_blocks, h1, h2, selection, h3,
      input.artifacts, stages, configuration_hash, std::string(64U, '0'));
  if (!zero_self) {
    return protocol::Result<AnalysisOutput>::failure(zero_self.errors());
  }
  const auto output_hash = sha_text(zero_self.value());
  auto machine = build_machine_report(
      input.configuration, state, summaries, primary_blocks, h1, h2, selection, h3,
      input.artifacts, stages, configuration_hash, output_hash.hex());
  if (!machine) {
    return protocol::Result<AnalysisOutput>::failure(machine.errors());
  }
  auto human =
      build_human_report(state, summaries.size(), primary_blocks.size(), h1, h2, h3);
  return protocol::Result<AnalysisOutput>::success(
      {state, std::move(summaries), std::move(primary_blocks), std::move(h1),
       std::move(h2), std::move(selection), std::move(h3), std::move(stages),
       std::move(machine).value(), std::move(human), configuration_hash, output_hash});
}

} // namespace cpu_prefetch::analysis
