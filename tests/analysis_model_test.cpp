#include <gtest/gtest.h>

#include "cpu_prefetch/analysis/analysis.hpp"
#include "cpu_prefetch/protocol/json.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

namespace analysis = cpu_prefetch::analysis;
namespace orchestration = cpu_prefetch::orchestration;
namespace protocol = cpu_prefetch::protocol;
namespace reconciliation = cpu_prefetch::reconciliation;
namespace workload = cpu_prefetch::workload;

constexpr std::string_view kZeroHash =
    "0000000000000000000000000000000000000000000000000000000000000000";

template <typename Identifier> auto id(std::string value) -> Identifier {
  auto parsed = Identifier::parse(std::move(value), "$/test/id");
  if (!parsed) {
    throw std::logic_error("invalid synthetic identifier");
  }
  return std::move(parsed).value();
}

auto sha(std::string_view value = kZeroHash) -> protocol::Sha256 {
  auto parsed = protocol::Sha256::parse(value, "$/test/sha256");
  if (!parsed) {
    throw std::logic_error("invalid synthetic digest");
  }
  return std::move(parsed).value();
}

auto bytes(std::string_view value) -> std::vector<std::byte> {
  std::vector<std::byte> result;
  result.reserve(value.size());
  for (const auto character : value) {
    result.push_back(static_cast<std::byte>(static_cast<unsigned char>(character)));
  }
  return result;
}

auto add_artifact(
    std::vector<analysis::ImmutableArtifact>& artifacts,
    std::string_view artifact_id, // NOLINT(bugprone-easily-swappable-parameters)
    std::string_view schema, std::string_view contents) -> protocol::ArtifactReference {
  const auto payload = bytes(contents);
  const auto digest = workload::sha256(payload).hex();
  const protocol::ArtifactReference reference{
      id<protocol::ArtifactId>(std::string(artifact_id)), sha(digest)};
  artifacts.push_back({protocol::ProtocolVersion::v2_0_0_pre_2, std::string(schema),
                       reference, payload, true});
  return reference;
}

auto artifact_by_id(std::vector<analysis::ImmutableArtifact>& artifacts,
                    std::string_view artifact_id) -> analysis::ImmutableArtifact& {
  const auto iterator =
      std::find_if(artifacts.begin(), artifacts.end(), [&](const auto& artifact) {
        return artifact.reference.artifact_id.value() == artifact_id;
      });
  if (iterator == artifacts.end()) {
    throw std::logic_error("synthetic artifact not found");
  }
  return *iterator;
}

auto has_rule(const std::vector<protocol::ValidationError>& errors,
              std::string_view rule) -> bool {
  return std::any_of(errors.begin(), errors.end(),
                     [&](const auto& error) { return error.rule_id == rule; });
}

auto namespaces() -> orchestration::RoleNamespaceRegistry {
  const auto common = id<protocol::NamespaceId>("analysis-stage-a-common");
  return {common,
          {{protocol::BlockRole::h3_train,
            id<protocol::NamespaceId>("analysis-stage-a-train"), common},
           {protocol::BlockRole::h3_validation,
            id<protocol::NamespaceId>("analysis-stage-a-validation"), common},
           {protocol::BlockRole::h1h2_supplemental,
            id<protocol::NamespaceId>("analysis-stage-a-supplemental"), common}}};
}

auto role_namespace(protocol::BlockRole role) -> protocol::NamespaceId {
  switch (role) {
  case protocol::BlockRole::h3_train:
    return id<protocol::NamespaceId>("analysis-stage-a-train");
  case protocol::BlockRole::h3_validation:
    return id<protocol::NamespaceId>("analysis-stage-a-validation");
  case protocol::BlockRole::h1h2_supplemental:
    return id<protocol::NamespaceId>("analysis-stage-a-supplemental");
  case protocol::BlockRole::not_applicable:
    break;
  }
  throw std::logic_error("invalid synthetic block role");
}

// Ordinal selects identity while key_offset selects deterministic synthetic bytes.
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
auto make_catalog(protocol::BlockRole role, std::uint64_t ordinal,
                  std::uint32_t key_offset,
                  const protocol::ArtifactReference& derivation)
    -> orchestration::BlockSeedCatalog {
  const auto prefix = "analysis-block-" + std::to_string(ordinal) + "-";
  orchestration::BlockSeedCatalog result{
      role,
      role_namespace(role),
      id<protocol::NamespaceId>(prefix + "subspace"),
      derivation,
      {{0x10203040U + key_offset, 0x50607080U + key_offset}},
      {{0x90a0b0c0U + key_offset, 0xd0e0f000U + key_offset}},
      {{0x31415926U + key_offset, 0x27182818U + key_offset}},
      {},
      {},
      {}};
  for (std::size_t index = 0U; index < orchestration::kArrivalSeedCountPerBlock;
       ++index) {
    result.arrival_seed_ids.push_back(
        id<protocol::SeedId>(prefix + "arrival-" + std::to_string(index)));
  }
  for (std::size_t index = 0U; index < orchestration::kArenaSeedCountPerBlock;
       ++index) {
    result.node_seed_ids.push_back(
        id<protocol::SeedId>(prefix + "node-" + std::to_string(index)));
    result.event_seed_ids.push_back(
        id<protocol::SeedId>(prefix + "event-" + std::to_string(index)));
  }
  return result;
}

auto package_index(protocol::QueuePackage package) -> std::uint64_t {
  switch (package) {
  case protocol::QueuePackage::r0:
    return 0U;
  case protocol::QueuePackage::r1:
    return 1U;
  case protocol::QueuePackage::r2:
    return 2U;
  case protocol::QueuePackage::l0:
    return 3U;
  case protocol::QueuePackage::l1:
    return 4U;
  case protocol::QueuePackage::nblfq_mpsc:
  case protocol::QueuePackage::not_applicable:
    break;
  }
  throw std::logic_error("invalid Stage A package");
}

auto latency_for(const protocol::StageACell& cell, std::uint64_t block_ordinal)
    -> std::uint64_t {
  const auto candidate =
      package_index(cell.package) * 2U +
      (cell.requested_hardware_state == protocol::RequestedHardwareState::h1 ? 1U : 0U);
  const auto context = static_cast<std::uint64_t>(cell.placement) +
                       static_cast<std::uint64_t>(cell.working_set_class) +
                       static_cast<std::uint64_t>(cell.load_level);
  const auto magnitude = static_cast<std::int64_t>((candidate % 3U) + 1U);
  const auto noise = block_ordinal % 2U == 0U ? magnitude : -magnitude;
  const auto exponent =
      static_cast<std::int64_t>(22U + (2U * candidate) + context) + noise;
  if (exponent <= 0 || exponent >= 63) {
    throw std::logic_error("synthetic latency exponent is out of range");
  }
  return std::uint64_t{1U} << static_cast<unsigned int>(exponent);
}

auto refresh_run(analysis::SyntheticRunInput& run,
                 std::vector<analysis::ImmutableArtifact>& artifacts) -> void {
  auto latency = analysis::canonical_synthetic_latency_payload(
      run.run_id, run.end_to_end_latencies);
  ASSERT_TRUE(latency) << latency.errors().front().message;
  auto& joined = artifact_by_id(artifacts, run.joined_artifact.artifact_id.value());
  joined.bytes = bytes(latency.value());
  joined.reference.sha256 = sha(workload::sha256(joined.bytes).hex());
  run.joined_artifact = joined.reference;

  auto manifest = analysis::canonical_synthetic_run(run);
  ASSERT_TRUE(manifest) << manifest.errors().front().message;
  auto& manifest_artifact =
      artifact_by_id(artifacts, run.manifest_artifact.artifact_id.value());
  manifest_artifact.bytes = bytes(manifest.value());
  manifest_artifact.reference.sha256 =
      sha(workload::sha256(manifest_artifact.bytes).hex());
  run.manifest_artifact = manifest_artifact.reference;
}

auto make_run(const protocol::BlockPlan& block, const protocol::StageACell& cell,
              std::uint64_t block_ordinal,
              std::vector<analysis::ImmutableArtifact>& artifacts)
    -> analysis::SyntheticRunInput {
  const auto prefix = "analysis-run-" + std::to_string(block_ordinal) + "-" +
                      std::to_string(cell.cell_ordinal);
  const auto run_id = id<protocol::RunId>(prefix);
  analysis::SyntheticRunInput run{
      protocol::ProtocolVersion::v2_0_0_pre_2,
      std::string(analysis::kRunInputSchema),
      run_id,
      block.block_id,
      block.block_role,
      cell.cell_ordinal,
      cell.package,
      cell.requested_hardware_state,
      cell.placement,
      cell.working_set_class,
      cell.load_level,
      protocol::RunValidity::valid,
      200'000U,
      200'000U,
      200'000U,
      0U,
      200'000U,
      0U,
      200'000U,
      200'000U,
      1'000'000U,
      {{latency_for(cell, block_ordinal), 200'000U}},
      {{{3U, 200'000U}},
       {{2U, 200'000U}},
       {{5U, 200'000U}},
       {{7U, 200'000U}},
       {{2U, 200'000U}},
       {{11U, 200'000U}},
       {{3U, 200'000U}}},
      {id<protocol::ArtifactId>(prefix + "-manifest"), sha()},
      {id<protocol::ArtifactId>(prefix + "-joined"), sha()},
      {id<protocol::ArtifactId>(prefix + "-join-audit"), sha()},
      std::nullopt,
      std::nullopt,
      true};
  auto latency = analysis::canonical_synthetic_latency_payload(
      run.run_id, run.end_to_end_latencies);
  if (!latency) {
    throw std::logic_error("synthetic latency canonicalization failed");
  }
  run.joined_artifact = add_artifact(artifacts, prefix + "-joined",
                                     "STAGE12-JOINED-SYNTHETIC-v1", latency.value());
  run.join_audit_artifact =
      add_artifact(artifacts, prefix + "-join-audit", "JOIN-AUDIT-v1",
                   "passed synthetic Stage 12 join: " + prefix);
  auto manifest = analysis::canonical_synthetic_run(run);
  if (!manifest) {
    throw std::logic_error("synthetic run canonicalization failed");
  }
  run.manifest_artifact =
      add_artifact(artifacts, prefix + "-manifest",
                   std::string(analysis::kRunInputSchema), manifest.value());
  return run;
}

auto precision_family(analysis::FamilyKind family, std::uint64_t count,
                      std::size_t width, const protocol::ArtifactReference& artifact)
    -> analysis::ProspectiveFamilyInput {
  return {family, artifact, {{count, std::vector<double>(width, 0.20)}}};
}

struct Fixture final {
  analysis::AnalysisInput input;
};

auto build_fixture(bool with_replacement = false) -> Fixture {
  auto registry = namespaces();
  std::vector<analysis::ImmutableArtifact> artifacts;
  std::vector<analysis::BlockInput> blocks;
  std::vector<protocol::BlockPlan> plans;
  std::vector<analysis::SyntheticRunInput> runs;

  for (std::uint64_t ordinal = 0U; ordinal < 20U; ++ordinal) {
    const auto role = ordinal < 12U ? protocol::BlockRole::h3_train
                                    : protocol::BlockRole::h3_validation;
    const auto derivation = add_artifact(
        artifacts, "analysis-block-" + std::to_string(ordinal) + "-derivation",
        "BLOCK-SEED-DERIVATION-v1", "synthetic prospective seed derivation");
    auto catalog =
        make_catalog(role, ordinal, static_cast<std::uint32_t>(ordinal), derivation);
    orchestration::BlockGenerationInput generation{
        id<protocol::PlatformId>("analysis-synthetic-platform"),
        id<protocol::BuildId>("analysis-synthetic-build"),
        role,
        ordinal,
        catalog,
        std::nullopt};
    auto generated = orchestration::generate_block_plan(generation, registry);
    if (!generated) {
      throw std::logic_error("synthetic block generation failed");
    }
    const auto plan_ref =
        add_artifact(artifacts, "analysis-block-plan-" + std::to_string(ordinal),
                     "BLOCK-PLAN-2.0.0-pre.2", generated.value().canonical_json);
    plans.push_back(generated.value().plan);
    blocks.push_back(
        {generated.value().plan, std::move(catalog), plan_ref, true, true, true});
  }

  std::optional<std::size_t> replacement_index;
  if (with_replacement) {
    blocks.front().active_primary = false;
    const auto ordinal = std::uint64_t{20U};
    const auto derivation = add_artifact(artifacts, "analysis-block-20-derivation",
                                         "BLOCK-SEED-DERIVATION-v1",
                                         "synthetic replacement seed derivation");
    auto catalog =
        make_catalog(protocol::BlockRole::h3_train, ordinal, 200U, derivation);
    orchestration::ReplacementPlanInput replacement{
        blocks.front().plan.block_id,
        id<protocol::RecordId>("analysis-replacement-authorization"),
        blocks.front().plan.block_ordinal, blocks.front().plan.block_role,
        blocks.front().plan.seed_subspace_id};
    orchestration::BlockGenerationInput generation{
        id<protocol::PlatformId>("analysis-synthetic-platform"),
        id<protocol::BuildId>("analysis-synthetic-build"),
        protocol::BlockRole::h3_train,
        ordinal,
        catalog,
        replacement};
    auto generated = orchestration::generate_block_plan(generation, registry);
    if (!generated) {
      throw std::logic_error("synthetic replacement generation failed");
    }
    const auto plan_ref =
        add_artifact(artifacts, "analysis-block-plan-20", "BLOCK-PLAN-2.0.0-pre.2",
                     generated.value().canonical_json);
    replacement_index = blocks.size();
    plans.push_back(generated.value().plan);
    blocks.push_back(
        {generated.value().plan, std::move(catalog), plan_ref, true, true, true});
  }

  for (const auto& block : blocks) {
    for (const auto& cell : block.plan.cells) {
      runs.push_back(make_run(block.plan, cell, block.plan.block_ordinal, artifacts));
    }
  }
  if (with_replacement) {
    auto& failed = runs.front();
    failed.validity = protocol::RunValidity::invalid;
    failed.failure_artifact = add_artifact(
        artifacts, "analysis-original-invalid-failure", "FAILURE-RECORD-v1",
        "synthetic invalid required run retained for complete replacement");
    refresh_run(failed, artifacts);
    if (!replacement_index) {
      throw std::logic_error("replacement index missing");
    }
  }

  const auto h1_sizing =
      add_artifact(artifacts, "analysis-h1-sizing", "PROSPECTIVE-PRECISION-v1",
                   "synthetic known H1 prospective widths");
  const auto h2_sizing =
      add_artifact(artifacts, "analysis-h2-sizing", "PROSPECTIVE-PRECISION-v1",
                   "synthetic known H2 prospective widths");
  const auto train_sizing =
      add_artifact(artifacts, "analysis-h3-training-sizing", "PROSPECTIVE-PRECISION-v1",
                   "synthetic known 270-family prospective standard errors");
  const auto validation_sizing = add_artifact(
      artifacts, "analysis-h3-validation-sizing", "PROSPECTIVE-PRECISION-v1",
      "synthetic known 540-family prospective half widths");
  analysis::ProspectivePrecisionInput precision{
      precision_family(analysis::FamilyKind::h1_two_sided, 20U,
                       orchestration::kH1ContrastCount, h1_sizing),
      precision_family(analysis::FamilyKind::h2_two_sided, 20U,
                       orchestration::kH2ContrastCount, h2_sizing),
      precision_family(analysis::FamilyKind::h3_training_standard_error, 12U,
                       orchestration::kH3TrainingPairCount, train_sizing),
      precision_family(analysis::FamilyKind::h3_validation_one_sided, 8U,
                       orchestration::kH3ValidationFamilyCount, validation_sizing)};
  analysis::AnalysisConfiguration configuration{
      protocol::ProtocolVersion::v2_0_0_pre_2,
      std::string(analysis::kAnalysisProfile),
      0.5,
      {std::string(analysis::kBootstrapProfile),
       std::string(workload::kDeterministicSuite),
       id<protocol::SeedId>("analysis-bootstrap-seed"),
       {{0x12345678U, 0x9abcdef0U}},
       199U},
      std::move(precision),
      {20U, 20U, 20U, 12U, 8U, 20U, 3'600U},
      {id<protocol::ArtifactId>("analysis-configuration"), sha()},
      {"synthetic-stage15-revision", "synthetic-test-compiler",
       "synthetic-test-standard-library"}};
  auto config_bytes = analysis::canonical_configuration(configuration);
  if (!config_bytes) {
    throw std::logic_error("synthetic configuration canonicalization failed");
  }
  configuration.configuration_artifact =
      add_artifact(artifacts, "analysis-configuration", "STAGE15-ANALYSIS-CONFIG-v1",
                   config_bytes.value());

  const auto training_access =
      add_artifact(artifacts, "analysis-training-access", "STAGE14-ACCESS-GATE-v1",
                   "synthetic validated training access chronology");
  const auto validation_access =
      add_artifact(artifacts, "analysis-validation-access", "STAGE14-ACCESS-GATE-v1",
                   "synthetic validated validation unseal chronology");
  const auto h1h2_access =
      add_artifact(artifacts, "analysis-h1h2-access", "STAGE14-ACCESS-GATE-v1",
                   "synthetic validated H1/H2 release chronology");
  orchestration::AccessLedgerResult ledger{protocol::AccessState::h1h2_released, {}};
  std::vector<protocol::BlockPlan> active_plans;
  std::vector<protocol::BlockPlan> training_plans;
  std::vector<protocol::BlockPlan> validation_plans;
  for (const auto& block : blocks) {
    if (!block.active_primary) {
      continue;
    }
    active_plans.push_back(block.plan);
    if (block.plan.block_role == protocol::BlockRole::h3_train) {
      training_plans.push_back(block.plan);
    } else if (block.plan.block_role == protocol::BlockRole::h3_validation) {
      validation_plans.push_back(block.plan);
    }
  }
  auto training_grant = analysis::OutcomeAccessGrant::from_stage14(
      ledger, orchestration::OutcomeDomain::h3_training, training_plans,
      training_access);
  auto validation_grant = analysis::OutcomeAccessGrant::from_stage14(
      ledger, orchestration::OutcomeDomain::h3_validation, validation_plans,
      validation_access);
  auto h1h2_grant = analysis::OutcomeAccessGrant::from_stage14(
      ledger, orchestration::OutcomeDomain::h1h2, active_plans, h1h2_access);
  if (!training_grant || !validation_grant || !h1h2_grant) {
    throw std::logic_error("synthetic access grant construction failed");
  }
  return {{std::move(registry), std::move(blocks), std::move(runs),
           std::move(artifacts), std::move(configuration), training_grant.value(),
           validation_grant.value(), h1h2_grant.value()}};
}

auto base_fixture() -> const Fixture& {
  static const auto fixture = build_fixture(false);
  return fixture;
}

auto replacement_fixture() -> const Fixture& {
  static const auto fixture = build_fixture(true);
  return fixture;
}

} // namespace

TEST(AnalysisQuantile, UsesExactInverseEcdfAndRetainsTies) {
  const std::vector<analysis::WeightedLatency> values{{10U, 2U}, {20U, 2U}, {90U, 1U}};
  auto median = analysis::exact_inverse_ecdf_quantile(values, 1U, 2U);
  auto p90 = analysis::exact_inverse_ecdf_quantile(values, 9U, 10U);
  ASSERT_TRUE(median);
  ASSERT_TRUE(p90);
  EXPECT_EQ(median.value(), 20U);
  EXPECT_EQ(p90.value(), 90U);

  const std::vector<analysis::WeightedLatency> duplicate{{10U, 1U}, {10U, 1U}};
  auto invalid = analysis::exact_inverse_ecdf_quantile(duplicate, 1U, 2U);
  ASSERT_FALSE(invalid);
  EXPECT_TRUE(has_rule(invalid.errors(), "ANALYSIS-QUANTILE-SORTED"));
}

TEST(AnalysisDesign, FrozenModelIsFullRankAndContrastRegistriesAreExact) {
  EXPECT_EQ(analysis::stage_a_design_rank(), 40U);
  EXPECT_EQ(orchestration::h1_contrast_ids().size(), 7U);
  EXPECT_EQ(orchestration::h2_contrast_ids().size(), 20U);
}

TEST(AnalysisPrecision, SelectsOnlyFromCompleteProspectiveFamilies) {
  auto input = base_fixture().input.configuration.precision;
  auto counts = analysis::evaluate_prospective_precision(input, 0.5);
  ASSERT_TRUE(counts);
  EXPECT_EQ(counts.value().r_h1, 20U);
  EXPECT_EQ(counts.value().r_h2, 20U);
  EXPECT_EQ(counts.value().rtrain, 12U);
  EXPECT_EQ(counts.value().rval, 8U);
  EXPECT_EQ(counts.value().rtotal, 20U);
  EXPECT_EQ(counts.value().nruns, 3'600U);

  input.h1.candidates.front().widths.pop_back();
  auto malformed = analysis::evaluate_prospective_precision(input, 0.5);
  ASSERT_FALSE(malformed);
  EXPECT_TRUE(has_rule(malformed.errors(), "ANALYSIS-PRECISION-CURVE"));
}

TEST(AnalysisMaxT, SeparatesNullAndKnownShiftFamiliesByCompleteBlock) {
  analysis::BootstrapConfiguration bootstrap{std::string(analysis::kBootstrapProfile),
                                             std::string(workload::kDeterministicSuite),
                                             id<protocol::SeedId>("max-t-known-answer"),
                                             {{0x11111111U, 0x22222222U}},
                                             199U};
  const auto ids = orchestration::h1_contrast_ids();
  std::vector<std::vector<double>> null_blocks;
  std::vector<std::vector<double>> shifted_blocks;
  for (std::size_t block = 0U; block < 20U; ++block) {
    const auto sign = block % 2U == 0U ? 1.0 : -1.0;
    std::vector<double> null_row;
    std::vector<double> shifted_row;
    for (std::size_t contrast = 0U; contrast < ids.size(); ++contrast) {
      const auto noise = sign * 0.001 * static_cast<double>(contrast + 1U);
      null_row.push_back(noise);
      shifted_row.push_back(2.0 + noise);
    }
    null_blocks.push_back(std::move(null_row));
    shifted_blocks.push_back(std::move(shifted_row));
  }
  auto null_result =
      analysis::two_sided_max_t("H1-SEVEN-TWO-SIDED", ids, null_blocks, bootstrap, 1.0);
  auto shifted_result = analysis::two_sided_max_t("H1-SEVEN-TWO-SIDED", ids,
                                                  shifted_blocks, bootstrap, 1.0);
  ASSERT_TRUE(null_result);
  ASSERT_TRUE(shifted_result);
  EXPECT_EQ(null_result.value().intervals.size(), 7U);
  EXPECT_TRUE(std::all_of(
      null_result.value().intervals.begin(), null_result.value().intervals.end(),
      [](const auto& row) {
        return row.conclusion == analysis::PracticalConclusion::practically_equivalent;
      }));
  EXPECT_TRUE(std::all_of(shifted_result.value().intervals.begin(),
                          shifted_result.value().intervals.end(), [](const auto& row) {
                            return row.conclusion ==
                                   analysis::PracticalConclusion::practically_higher;
                          }));
}

TEST(AnalysisH3, ExactTrainingTiesUseRegisteredCandidateOrder) {
  std::vector<analysis::CompleteBlockResponse> blocks;
  for (std::uint64_t ordinal = 0U; ordinal < 12U; ++ordinal) {
    analysis::CompleteBlockResponse block{
        id<protocol::BlockId>("tie-block-" + std::to_string(ordinal)),
        protocol::BlockRole::h3_train,
        {}};
    for (const auto& [package, hardware, placement, working_set, load] :
         orchestration::expected_stage_a_cells()) {
      block.cells.push_back({package, hardware, placement, working_set, load,
                             5.0 + (ordinal % 2U == 0U ? 0.1 : -0.1)});
    }
    blocks.push_back(std::move(block));
  }
  const std::vector sources{protocol::ArtifactReference{
      id<protocol::ArtifactId>("tie-training-source"), sha()}};
  auto selection = analysis::select_h3_training(blocks, sources);
  ASSERT_TRUE(selection);
  ASSERT_EQ(selection.value().selections.size(), 6U);
  for (const auto& [context, candidate] : selection.value().selections) {
    static_cast<void>(context);
    EXPECT_EQ(candidate.package, protocol::QueuePackage::r0);
    EXPECT_EQ(candidate.requested_hardware_state, protocol::RequestedHardwareState::h0);
  }
}

TEST(AnalysisPipeline, CompleteSyntheticKnownShiftIsDeterministicAndByteStable) {
  const auto& input = base_fixture().input;
  auto first = analysis::run_synthetic_analysis(input);
  auto second = analysis::run_synthetic_analysis(input);
  ASSERT_TRUE(first) << first.errors().front().message;
  ASSERT_TRUE(second) << second.errors().front().message;
  const auto& output = first.value();
  EXPECT_EQ(output.state, analysis::InferenceState::estimable);
  if (!output.h1.has_value()) {
    FAIL() << "estimable synthetic result is missing H1";
    return;
  }
  if (!output.h2.has_value()) {
    FAIL() << "estimable synthetic result is missing H2";
    return;
  }
  if (!output.selection.has_value()) {
    FAIL() << "estimable synthetic result is missing selection";
    return;
  }
  if (!output.h3.has_value()) {
    FAIL() << "estimable synthetic result is missing H3";
    return;
  }
  if (!output.h3.value().comparisons.has_value()) {
    FAIL() << "estimable synthetic result is missing a required family";
    return;
  }
  const auto& h1 = output.h1.value();
  const auto& h2 = output.h2.value();
  const auto& selection = output.selection.value();
  const auto& h3_comparisons = output.h3.value().comparisons.value();
  EXPECT_EQ(h1.intervals.size(), 7U);
  EXPECT_EQ(h2.intervals.size(), 20U);
  EXPECT_EQ(h3_comparisons.intervals.size(), 54U);
  const auto r12 =
      std::find_if(h1.intervals.begin(), h1.intervals.end(),
                   [](const auto& row) { return row.stable_id == "H1-R12"; });
  ASSERT_NE(r12, h1.intervals.end());
  EXPECT_NEAR(r12->estimate, 4.0 * std::log(2.0), 1.0e-12);
  for (const auto& [context, candidate] : selection.selections) {
    static_cast<void>(context);
    EXPECT_EQ(candidate.package, protocol::QueuePackage::r0);
    EXPECT_EQ(candidate.requested_hardware_state, protocol::RequestedHardwareState::h0);
  }
  EXPECT_EQ(first.value().machine_report_json, second.value().machine_report_json);
  EXPECT_EQ(first.value().output_sha256, second.value().output_sha256);
  EXPECT_NE(first.value().human_report_markdown.find("SYNTHETIC FIXTURE ONLY"),
            std::string::npos);
  EXPECT_NE(first.value().machine_report_json.find(
                "\"evidence_class\":\"SYNTHETIC_KNOWN_ANSWER_ONLY\""),
            std::string::npos);
  EXPECT_NE(first.value().machine_report_json.find(
                "\"classification\":\"NON_PRIMARY_DIAGNOSTIC\""),
            std::string::npos);
  EXPECT_TRUE(protocol::json::parse(first.value().machine_report_json));
}

TEST(AnalysisPipeline, RejectsMixedVersionsAndFailedChecksums) {
  auto mixed = base_fixture().input;
  mixed.artifacts.front().protocol_version = protocol::ProtocolVersion::v2_0_0_pre_1;
  auto mixed_result = analysis::run_synthetic_analysis(mixed);
  ASSERT_FALSE(mixed_result);
  EXPECT_TRUE(has_rule(mixed_result.errors(), "ANALYSIS-MIXED-VERSION"));

  auto corrupt = base_fixture().input;
  corrupt.artifacts.front().bytes.front() ^= std::byte{0x01};
  auto corrupt_result = analysis::run_synthetic_analysis(corrupt);
  ASSERT_FALSE(corrupt_result);
  EXPECT_TRUE(has_rule(corrupt_result.errors(), "ANALYSIS-ARTIFACT-HASH"));
}

TEST(AnalysisPipeline, RejectsMissingCellsCellRepairAndInvalidJoinEvidence) {
  auto missing = base_fixture().input;
  missing.runs.pop_back();
  auto missing_result = analysis::run_synthetic_analysis(missing);
  ASSERT_FALSE(missing_result);
  EXPECT_TRUE(has_rule(missing_result.errors(), "ANALYSIS-NO-FILTERING"));

  auto repaired = base_fixture().input;
  repaired.runs.front().package = protocol::QueuePackage::l1;
  auto repaired_result = analysis::run_synthetic_analysis(repaired);
  ASSERT_FALSE(repaired_result);
  EXPECT_TRUE(has_rule(repaired_result.errors(), "ANALYSIS-NO-CELL-REPLACEMENT"));

  auto invalid_join = base_fixture().input;
  invalid_join.runs.front().prior_stage12_validation_passed = false;
  refresh_run(invalid_join.runs.front(), invalid_join.artifacts);
  auto invalid_join_result = analysis::run_synthetic_analysis(invalid_join);
  ASSERT_FALSE(invalid_join_result);
  EXPECT_TRUE(has_rule(invalid_join_result.errors(), "ANALYSIS-PRIOR-JOIN"));
}

TEST(AnalysisPipeline, ValidFullAndLowEffectiveTailAreRetainedButBlockInference) {
  auto full = base_fixture().input;
  auto& full_run = full.runs.front();
  full_run.offered_count = 200'001U;
  full_run.attempted_count = 200'001U;
  full_run.full_count = 1U;
  full_run.diagnostics.producer_lateness.front().multiplicity = 200'001U;
  full_run.diagnostics.enqueue_service.front().multiplicity = 200'001U;
  refresh_run(full_run, full.artifacts);
  auto full_result = analysis::run_synthetic_analysis(full);
  ASSERT_TRUE(full_result) << full_result.errors().front().message;
  EXPECT_EQ(full_result.value().state, analysis::InferenceState::blocked);
  EXPECT_EQ(full_result.value().run_summaries.front().validity,
            protocol::RunValidity::valid);
  EXPECT_EQ(full_result.value().run_summaries.front().zero_loss,
            protocol::GateStatus::fail);
  EXPECT_FALSE(full_result.value().h1);

  auto low_tail = base_fixture().input;
  low_tail.runs.front().n_eff_p999 = 199'999U;
  refresh_run(low_tail.runs.front(), low_tail.artifacts);
  auto low_result = analysis::run_synthetic_analysis(low_tail);
  ASSERT_TRUE(low_result) << low_result.errors().front().message;
  EXPECT_EQ(low_result.value().state, analysis::InferenceState::blocked);
  EXPECT_EQ(low_result.value().run_summaries.front().validity,
            protocol::RunValidity::valid);
  EXPECT_EQ(low_result.value().run_summaries.front().effective_tail,
            protocol::GateStatus::fail);
}

TEST(AnalysisPipeline, IncompleteActiveBlockIsRefused) {
  auto incomplete = base_fixture().input;
  auto& run = incomplete.runs.front();
  run.validity = protocol::RunValidity::invalid;
  run.failure_artifact =
      add_artifact(incomplete.artifacts, "analysis-incomplete-failure",
                   "FAILURE-RECORD-v1", "synthetic invalid run without replacement");
  refresh_run(run, incomplete.artifacts);
  auto result = analysis::run_synthetic_analysis(incomplete);
  ASSERT_FALSE(result);
  EXPECT_TRUE(has_rule(result.errors(), "ANALYSIS-INCOMPLETE-BLOCK"));
}

TEST(AnalysisPipeline, CompleteReplacementIsAcceptedAndBudgetFailureIsRefused) {
  const auto& replacement = replacement_fixture().input;
  auto accepted = analysis::run_synthetic_analysis(replacement);
  ASSERT_TRUE(accepted) << accepted.errors().front().message;
  const auto& accepted_output = accepted.value();
  EXPECT_EQ(accepted_output.primary_blocks.size(), 20U);
  EXPECT_EQ(accepted_output.run_summaries.size(), 21U * 180U);
  if (!accepted_output.selection.has_value()) {
    FAIL() << "replacement fixture did not produce H3 selection";
    return;
  }
  const auto& training_sources = accepted_output.selection.value().training_sources;
  EXPECT_EQ(training_sources.size(), 12U * 60U);
  for (const auto& source : training_sources) {
    EXPECT_EQ(source.artifact_id.value().find("analysis-run-0-"),
              std::string_view::npos);
  }

  auto exhausted = replacement;
  const auto replacement_block = std::find_if(
      exhausted.blocks.begin(), exhausted.blocks.end(),
      [](const auto& block) { return block.plan.replaces_block_id.has_value(); });
  ASSERT_NE(replacement_block, exhausted.blocks.end());
  replacement_block->replacement_budget_validation_passed = false;
  auto denied = analysis::run_synthetic_analysis(exhausted);
  ASSERT_FALSE(denied);
  EXPECT_TRUE(has_rule(denied.errors(), "ANALYSIS-REPLACEMENT-BUDGET"));
}

TEST(AnalysisAccess, SealedOrIncompleteStage14LedgerCannotMintAReadGrant) {
  const auto& block = base_fixture().input.blocks.front().plan;
  const std::vector blocks{block};
  orchestration::AccessLedgerResult sealed{protocol::AccessState::collected_sealed, {}};
  auto grant = analysis::OutcomeAccessGrant::from_stage14(
      sealed, orchestration::OutcomeDomain::h3_validation, blocks,
      protocol::ArtifactReference{id<protocol::ArtifactId>("sealed-access"), sha()});
  ASSERT_FALSE(grant);
  EXPECT_TRUE(has_rule(grant.errors(), "ANALYSIS-STAGE14-GRANT"));
}

TEST(AnalysisRun, RawRowsAreReconciledAndDerivedIntervalsCheckedExactly) {
  std::vector<analysis::ImmutableArtifact> artifacts;
  const auto run_id = id<protocol::RunId>("raw-analysis-run");
  const protocol::ProducerRecord producer{
      run_id, 0U, 7U, 1U, 2U, 3U, 4U, 5U, 6U, protocol::ProducerOutcome::accepted, 0U};
  const protocol::ConsumerRecord consumer{run_id, 0U, 7U, 7U, 8U, 9U, 10U};
  analysis::SyntheticRunInput run{
      protocol::ProtocolVersion::v2_0_0_pre_2,
      std::string(analysis::kRunInputSchema),
      run_id,
      id<protocol::BlockId>("raw-analysis-block"),
      protocol::BlockRole::h3_train,
      0U,
      protocol::QueuePackage::r0,
      protocol::RequestedHardwareState::h0,
      protocol::Placement::near,
      protocol::WorkingSetClass::l2_resident,
      protocol::LoadLevel::l050,
      protocol::RunValidity::valid,
      1U,
      1U,
      1U,
      0U,
      1U,
      0U,
      1U,
      1U,
      100U,
      {{9U, 1U}},
      {{{1U, 1U}},
       {{2U, 1U}},
       {{4U, 1U}},
       {{3U, 1U}},
       {{2U, 1U}},
       {{2U, 1U}},
       {{1U, 1U}}},
      {id<protocol::ArtifactId>("raw-analysis-manifest"), sha()},
      {id<protocol::ArtifactId>("raw-analysis-joined"), sha()},
      {id<protocol::ArtifactId>("raw-analysis-audit"), sha()},
      std::nullopt,
      analysis::RawReconciliationInput{{producer}, {consumer}, {7U}},
      false};
  auto latency = analysis::canonical_synthetic_latency_payload(
      run.run_id, run.end_to_end_latencies);
  ASSERT_TRUE(latency);
  run.joined_artifact = add_artifact(artifacts, "raw-analysis-joined",
                                     "STAGE12-JOINED-SYNTHETIC-v1", latency.value());
  run.join_audit_artifact = add_artifact(artifacts, "raw-analysis-audit",
                                         "JOIN-AUDIT-v1", "passed exact raw join");
  auto manifest = analysis::canonical_synthetic_run(run);
  ASSERT_TRUE(manifest);
  run.manifest_artifact =
      add_artifact(artifacts, "raw-analysis-manifest",
                   std::string(analysis::kRunInputSchema), manifest.value());
  auto summary = analysis::summarize_run(run, artifacts);
  ASSERT_TRUE(summary) << summary.errors().front().message;
  EXPECT_EQ(summary.value().quantiles.p999, 9U);
  EXPECT_EQ(summary.value().effective_tail, protocol::GateStatus::fail);

  run.end_to_end_latencies.front().latency_ticks = 8U;
  refresh_run(run, artifacts);
  auto corrupt = analysis::summarize_run(run, artifacts);
  ASSERT_FALSE(corrupt);
  EXPECT_TRUE(has_rule(corrupt.errors(), "ANALYSIS-INTERVALS-EXACT"));
}
