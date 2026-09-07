#include <gtest/gtest.h>

#include "cpu_prefetch/orchestration/access.hpp"
#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

namespace {

namespace orchestration = cpu_prefetch::orchestration;
namespace protocol = cpu_prefetch::protocol;
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

auto reference(std::string artifact_id) -> protocol::ArtifactReference {
  return {id<protocol::ArtifactId>(std::move(artifact_id)), sha()};
}

auto has_rule(const std::vector<protocol::ValidationError>& errors,
              std::string_view rule) -> bool {
  return std::any_of(errors.begin(), errors.end(),
                     [&](const auto& error) { return error.rule_id == rule; });
}

template <typename T> auto required(const std::optional<T>& value) -> const T& {
  if (!value.has_value()) {
    throw std::logic_error("required synthetic optional is absent");
  }
  return *value;
}

auto describe_errors(const std::vector<protocol::ValidationError>& errors)
    -> std::string {
  std::string result;
  for (const auto& error : errors) {
    result += error.rule_id + ": " + error.message + "\n";
  }
  return result;
}

auto namespaces() -> orchestration::RoleNamespaceRegistry {
  const auto common = id<protocol::NamespaceId>("stage-a-common-synthetic");
  return {common,
          {{protocol::BlockRole::h3_train,
            id<protocol::NamespaceId>("stage-a-train-synthetic"), common},
           {protocol::BlockRole::h3_validation,
            id<protocol::NamespaceId>("stage-a-validation-synthetic"), common},
           {protocol::BlockRole::h1h2_supplemental,
            id<protocol::NamespaceId>("stage-a-supplemental-synthetic"), common}}};
}

auto role_namespace(protocol::BlockRole role) -> protocol::NamespaceId {
  switch (role) {
  case protocol::BlockRole::h3_train:
    return id<protocol::NamespaceId>("stage-a-train-synthetic");
  case protocol::BlockRole::h3_validation:
    return id<protocol::NamespaceId>("stage-a-validation-synthetic");
  case protocol::BlockRole::h1h2_supplemental:
    return id<protocol::NamespaceId>("stage-a-supplemental-synthetic");
  case protocol::BlockRole::not_applicable:
    break;
  }
  throw std::logic_error("invalid block role");
}

struct CatalogCoordinates final {
  std::uint64_t ordinal;
  std::uint32_t key_offset;
};

auto catalog(protocol::BlockRole role, CatalogCoordinates coordinates)
    -> orchestration::BlockSeedCatalog {
  const auto prefix = "block-" + std::to_string(coordinates.ordinal) + "-";
  orchestration::BlockSeedCatalog result{
      role,
      role_namespace(role),
      id<protocol::NamespaceId>(prefix + "subspace"),
      reference(prefix + "derivation"),
      {{0x10203040U + coordinates.key_offset, 0x50607080U + coordinates.key_offset}},
      {{0x90a0b0c0U + coordinates.key_offset, 0xd0e0f000U + coordinates.key_offset}},
      {{0x31415926U + coordinates.key_offset, 0x27182818U + coordinates.key_offset}},
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

auto generation_input(protocol::BlockRole role, std::uint64_t ordinal,
                      std::uint32_t key_offset = 0U)
    -> orchestration::BlockGenerationInput {
  return {id<protocol::PlatformId>("synthetic-platform"),
          id<protocol::BuildId>("synthetic-build"),
          role,
          ordinal,
          catalog(role, {ordinal, key_offset}),
          std::nullopt};
}

auto generated(protocol::BlockRole role, std::uint64_t ordinal,
               std::uint32_t key_offset = 0U) -> orchestration::GeneratedBlockPlan {
  const auto input = generation_input(role, ordinal, key_offset);
  auto result = orchestration::generate_block_plan(input, namespaces());
  if (!result) {
    throw std::logic_error("synthetic block generation failed: " +
                           result.errors().front().message);
  }
  return std::move(result).value();
}

auto evidence(const std::string& prefix)
    -> orchestration::ProspectivePrecisionEvidence {
  return {reference(prefix + "-delta"),
          reference(prefix + "-bootstrap"),
          reference(prefix + "-h1"),
          reference(prefix + "-h2"),
          reference(prefix + "-train"),
          reference(prefix + "-validation"),
          {{reference(prefix + "-public"), protocol::AccessClass::public_protocol}}};
}

using JsonValue = protocol::json::Value;
using JsonObject = JsonValue::Object;
using JsonArray = JsonValue::Array;

auto string_value(std::string value) -> JsonValue {
  return JsonValue(std::move(value));
}

auto unsigned_value(std::uint64_t value) -> JsonValue {
  return JsonValue(protocol::json::Number{
      protocol::json::Number::Kind::unsigned_integer, std::to_string(value), value});
}

auto reference_value(const protocol::ArtifactReference& value) -> JsonValue {
  JsonObject object;
  object.emplace("artifact_id", string_value(std::string(value.artifact_id.value())));
  object.emplace("sha256", string_value(value.sha256.hex()));
  return JsonValue(std::move(object));
}

auto base_freeze(std::string record_id, std::string kind, std::string authority_id,
                 std::string authority_role, std::string before, std::string after,
                 std::string timestamp) -> JsonObject {
  JsonObject authority;
  authority.emplace("authority_id", string_value(std::move(authority_id)));
  authority.emplace("role", string_value(std::move(authority_role)));
  authority.emplace("attestation", string_value("synthetic Stage 14 fixture"));
  authority.emplace("signature_artifact_id", JsonValue(nullptr));
  JsonObject input;
  input.emplace("artifact_id", string_value("public-input"));
  input.emplace("sha256", string_value(std::string(kZeroHash)));
  input.emplace("access_class", string_value("PUBLIC_PROTOCOL"));
  JsonArray inputs;
  inputs.emplace_back(std::move(input));
  JsonObject object;
  object.emplace("schema_version", string_value("2.0.0-pre.2"));
  object.emplace("protocol_version", string_value("2.0.0-pre.2"));
  object.emplace("record_id", string_value(std::move(record_id)));
  object.emplace("record_kind", string_value(std::move(kind)));
  object.emplace("decision_id", string_value("stage14-synthetic-decision"));
  object.emplace("readiness_boundary",
                 string_value("BLOCKED_BEFORE_CONFIRMATORY_EXECUTION"));
  object.emplace("status", string_value("FROZEN"));
  object.emplace("authorization_status", string_value("AUTHORIZED"));
  object.emplace("created_at_utc", string_value(std::move(timestamp)));
  object.emplace("authority", JsonValue(std::move(authority)));
  object.emplace("access_state_before", string_value(std::move(before)));
  object.emplace("access_state_after", string_value(std::move(after)));
  object.emplace("outcome_access_prohibited", JsonValue(true));
  object.emplace("input_artifacts", JsonValue(std::move(inputs)));
  object.emplace("record_sha256", string_value(std::string(kZeroHash)));
  return object;
}

auto finalize_freeze(JsonObject object) -> protocol::FreezeRecord {
  const auto* kind = object.at("record_kind").as_string();
  if (kind != nullptr && *kind == "SELECTION_FREEZE") {
    JsonObject payload;
    for (const auto key :
         {"h3_selections", "training_input_artifacts", "selection_rule_version"}) {
      payload.emplace(key, object.at(key));
    }
    const auto canonical = protocol::json::canonicalize(JsonValue(std::move(payload)));
    if (!canonical) {
      throw std::logic_error("selection payload canonicalization failed");
    }
    const auto* payload_bytes =
        reinterpret_cast<const std::byte*>(canonical.value().data());
    object["selection_record_checksum_sha256"] = string_value(
        workload::sha256(std::span(payload_bytes, canonical.value().size())).hex());
  }
  object["record_sha256"] = string_value(std::string(kZeroHash));
  auto zero = protocol::json::canonicalize(JsonValue(object));
  if (!zero) {
    throw std::logic_error("freeze zero-self canonicalization failed");
  }
  const auto* bytes = reinterpret_cast<const std::byte*>(zero.value().data());
  object["record_sha256"] =
      string_value(workload::sha256(std::span(bytes, zero.value().size())).hex());
  auto loaded = protocol::load_document(protocol::DocumentKind::freeze_record,
                                        JsonValue(std::move(object)));
  if (!loaded) {
    throw std::logic_error("freeze fixture decode failed: " +
                           loaded.errors().front().message);
  }
  const auto* record = std::get_if<protocol::FreezeRecord>(&loaded.value());
  if (record == nullptr) {
    throw std::logic_error("freeze fixture decoded to the wrong record type");
  }
  return *record;
}

template <typename Record>
auto load_typed(protocol::DocumentKind kind, std::string_view text) -> Record {
  auto loaded = protocol::load_document(kind, text);
  if (!loaded) {
    throw std::logic_error("synthetic protocol fixture decode failed: " +
                           loaded.errors().front().message);
  }
  const auto* record = std::get_if<Record>(&loaded.value());
  if (record == nullptr) {
    throw std::logic_error("synthetic fixture decoded to the wrong record type");
  }
  return *record;
}

auto invalid_run(const protocol::BlockId& block_id) -> protocol::RunManifest {
  std::ostringstream output;
  output
      << R"({"schema_version":"2.0.0-pre.2","protocol_version":"2.0.0-pre.2","run_id":"replacement-run","platform_id":"synthetic-platform","build_id":"synthetic-build","within_cell_ordinal":0,"queue_provenance_id":"queue-provenance","provenance":{"paper_repository_revision":"paper","implementation_repository_revision":"implementation","build_artifact_sha256":")"
      << kZeroHash
      << R"(","compiler_identity":"compiler","compiler_flags":[],"standard_library":"stdlib","dependency_record_id":"dependencies"},"stage":"STAGE_A","run_mode":"LATENCY","lifecycle_state":"PRE_RUN_FAILURE","block_id":")"
      << block_id.value()
      << R"(","block_role":"H3_TRAIN","package":"R0","requested_hardware_state":"H0","verified_hardware_state":"VERIFICATION_FAILED","placement":"NEAR","working_set_class":"L2_RESIDENT","load_level":"L025","capacity_events":64,"time_unit":"candidate_ticks","schedule_refs":{"measurement":{"artifact_id":"measurement-schedule","sha256":")"
      << kZeroHash << R"("},"warmup":{"artifact_id":"warmup-schedule","sha256":")"
      << kZeroHash
      << R"("}},"seed_refs":{"arrival":"arrival","node_order":null,"event_order":"event","warmup":"warmup","derivation_record_id":"derivation"},"validity":"INVALID","count_reconciliation":"NOT_EVALUATED","zero_loss_status":"NOT_EVALUATED","effective_tail_status":"NOT_EVALUATED","confirmatory_estimability":"NOT_EVALUATED","confirmatory_blockers":[],"block_completeness":"INCOMPLETE","join_status":"NOT_ATTEMPTED","failure_record_ids":["replacement-failure"],"artifact_refs":[],"manifest_sha256":")"
      << kZeroHash << R"("})";
  return load_typed<protocol::RunManifest>(protocol::DocumentKind::run_manifest,
                                           output.str());
}

auto invalidating_failure(const protocol::BlockId& block_id,
                          const protocol::BlockId& replacement_id)
    -> protocol::FailureRecord {
  std::ostringstream output;
  output
      << R"({"schema_version":"2.0.0-pre.2","protocol_version":"2.0.0-pre.2","failure_record_id":"replacement-failure","platform_id":"synthetic-platform","stage":"STAGE_A","scope":"RUN","run_id":"replacement-run","block_id":")"
      << block_id.value()
      << R"(","build_id":"synthetic-build","category":"AFFINITY","detected_phase":"PRE_RUN","observed_at_utc":"2026-08-21T00:00:00Z","description":"synthetic invalid required run","invalidates_run":true,"block_consequence":"ORIGINAL_BLOCK_INCOMPLETE","resolution_status":"REPLACEMENT_AUTHORIZED","replacement_authorization_id":"replacement-authorization","replacement_block_id":")"
      << replacement_id.value()
      << R"(","supersedes_id":null,"evidence_refs":[{"artifact_id":"failure-evidence","sha256":")"
      << kZeroHash << R"("}],"record_sha256":")" << kZeroHash << R"("})";
  return load_typed<protocol::FailureRecord>(protocol::DocumentKind::failure_record,
                                             output.str());
}

auto replacement_authorization(const protocol::BlockPlan& original,
                               const orchestration::BlockGenerationInput& replacement)
    -> protocol::FreezeRecord {
  const auto replacement_id =
      orchestration::make_block_id(replacement.platform_id, replacement.build_id,
                                   replacement.role, replacement.block_ordinal);
  if (!replacement_id) {
    throw std::logic_error("replacement ID generation failed");
  }
  auto object = base_freeze("replacement-authorization", "REPLACEMENT_AUTHORIZATION",
                            "replacement-owner", "REPLACEMENT_AUTHORITY", "PLANNED",
                            "PLANNED", "2026-08-21T00:00:01Z");
  object["status"] = string_value("AUTHORIZED");
  object["affected_block_ids"] =
      JsonValue(JsonArray{string_value(std::string(original.block_id.value()))});
  JsonObject lineage;
  lineage.emplace("original_block_id",
                  string_value(std::string(original.block_id.value())));
  lineage.emplace("replacement_block_id",
                  string_value(std::string(replacement_id.value().value())));
  lineage.emplace("replacement_block_ordinal",
                  unsigned_value(replacement.block_ordinal));
  lineage.emplace("block_role", string_value("H3_TRAIN"));
  lineage.emplace(
      "replacement_seed_subspace_id",
      string_value(std::string(replacement.seeds.block_subspace_id.value())));
  lineage.emplace("failure_record_id", string_value("replacement-failure"));
  lineage.emplace("replacement_budget_record_id", string_value("replacement-budget"));
  object["replacement"] = JsonValue(std::move(lineage));
  JsonObject budget_input;
  budget_input.emplace("artifact_id", string_value("replacement-budget"));
  budget_input.emplace("sha256", string_value(std::string(kZeroHash)));
  budget_input.emplace("access_class", string_value("PUBLIC_PROTOCOL"));
  object["input_artifacts"] = JsonValue(JsonArray{JsonValue(std::move(budget_input))});
  return finalize_freeze(std::move(object));
}

auto input_value(const protocol::ArtifactReference& artifact, std::string access_class)
    -> JsonValue {
  JsonObject value;
  value.emplace("artifact_id", string_value(std::string(artifact.artifact_id.value())));
  value.emplace("sha256", string_value(artifact.sha256.hex()));
  value.emplace("access_class", string_value(std::move(access_class)));
  return JsonValue(std::move(value));
}

auto block_ids_value(std::span<const protocol::BlockPlan> blocks,
                     std::optional<protocol::BlockRole> role = std::nullopt)
    -> JsonValue {
  JsonArray result;
  for (const auto& block : blocks) {
    const bool replaced =
        std::any_of(blocks.begin(), blocks.end(), [&](const auto& candidate) {
          return candidate.replaces_block_id &&
                 *candidate.replaces_block_id == block.block_id;
        });
    if (!replaced && (!role || block.block_role == *role)) {
      result.push_back(string_value(std::string(block.block_id.value())));
    }
  }
  return JsonValue(std::move(result));
}

auto string_array(std::span<const std::string_view> values) -> JsonValue {
  JsonArray result;
  result.reserve(values.size());
  for (const auto value : values) {
    result.push_back(string_value(std::string(value)));
  }
  return JsonValue(std::move(result));
}

struct AccessArtifacts final {
  protocol::ArtifactReference training;
  protocol::ArtifactReference validation;
  protocol::ArtifactReference validation_approval;
  protocol::ArtifactReference h3_evaluation;
  protocol::ArtifactReference h3_access;
};

auto make_access_records(
    std::span<const protocol::BlockPlan> blocks, const AccessArtifacts& artifacts,
    std::optional<orchestration::ProspectiveCounts> frozen_counts = std::nullopt,
    std::optional<orchestration::ProspectivePrecisionEvidence> frozen_evidence =
        std::nullopt) -> std::vector<protocol::FreezeRecord> {
  std::vector<protocol::FreezeRecord> result;
  auto collect = base_freeze("access-collect", "PROTOCOL_FREEZE", "freeze-owner",
                             "FREEZE_AUTHORITY", "PLANNED", "COLLECTED_SEALED",
                             "2026-08-21T00:00:00Z");
  collect["affected_block_ids"] = block_ids_value(blocks);
  result.push_back(finalize_freeze(std::move(collect)));

  auto training_open = base_freeze(
      "access-training-open", "PROTOCOL_FREEZE", "freeze-owner", "FREEZE_AUTHORITY",
      "COLLECTED_SEALED", "TRAINING_OPEN", "2026-08-21T00:00:01Z");
  training_open["affected_block_ids"] =
      block_ids_value(blocks, protocol::BlockRole::h3_train);
  const orchestration::ProspectiveCounts counts = frozen_counts.value_or(
      orchestration::ProspectiveCounts{20U, 20U, 20U, 12U, 8U, 20U, 3600U});
  const auto delta =
      frozen_evidence ? frozen_evidence->delta_star : reference("public-input");
  const auto bootstrap = frozen_evidence ? frozen_evidence->bootstrap_configuration
                                         : reference("public-input");
  constexpr std::array candidate_order{
      std::string_view("R0:H0"), std::string_view("R0:H1"), std::string_view("R1:H0"),
      std::string_view("R1:H1"), std::string_view("R2:H0"), std::string_view("R2:H1"),
      std::string_view("L0:H0"), std::string_view("L0:H1"), std::string_view("L1:H0"),
      std::string_view("L1:H1")};
  constexpr std::array context_order{std::string_view("NEAR_L2_L050"),
                                     std::string_view("NEAR_LLC_L050"),
                                     std::string_view("NEAR_BEYOND_LLC_L050"),
                                     std::string_view("FAR_L2_L050"),
                                     std::string_view("FAR_LLC_L050"),
                                     std::string_view("FAR_BEYOND_LLC_L050")};
  const auto h1_contrasts = orchestration::h1_contrast_ids();
  const auto h2_contrasts = orchestration::h2_contrast_ids();
  JsonObject decision;
  decision.emplace("candidate_order", string_array(candidate_order));
  decision.emplace("h3_context_order", string_array(context_order));
  decision.emplace("h1_contrast_ids", string_array(h1_contrasts));
  decision.emplace("h2_contrast_ids", string_array(h2_contrasts));
  decision.emplace("h3_training_pair_count",
                   unsigned_value(orchestration::kH3TrainingPairCount));
  decision.emplace("h3_validation_family_count",
                   unsigned_value(orchestration::kH3ValidationFamilyCount));
  decision.emplace("h3_reported_comparison_count",
                   unsigned_value(orchestration::kH3ReportedComparisonCount));
  decision.emplace("tie_break_rule_id",
                   string_value(std::string(orchestration::kH3SelectionRuleId)));
  decision.emplace("delta_star_artifact_id",
                   string_value(std::string(delta.artifact_id.value())));
  decision.emplace("bootstrap_configuration_artifact_id",
                   string_value(std::string(bootstrap.artifact_id.value())));
  decision.emplace("bootstrap_seed_id", string_value("HYPOTHESIS-BOOTSTRAP-v1"));
  decision.emplace("precision_profile_id", string_value("STAGE-A-PRECISION-v1"));
  decision.emplace("schema_artifact_ids",
                   string_array(std::array{std::string_view("public-input")}));
  decision.emplace("r_h1", unsigned_value(counts.r_h1));
  decision.emplace("r_h2", unsigned_value(counts.r_h2));
  decision.emplace("r12", unsigned_value(counts.r12));
  decision.emplace("rtrain", unsigned_value(counts.rtrain));
  decision.emplace("rval", unsigned_value(counts.rval));
  decision.emplace("rtotal", unsigned_value(counts.rtotal));
  decision.emplace("nruns", unsigned_value(counts.nruns));
  training_open["decision_value"] = JsonValue(std::move(decision));
  JsonArray training_inputs;
  if (frozen_evidence) {
    const std::array evidence_refs{
        frozen_evidence->delta_star,         frozen_evidence->bootstrap_configuration,
        frozen_evidence->h1_sizing,          frozen_evidence->h2_sizing,
        frozen_evidence->h3_training_sizing, frozen_evidence->h3_validation_sizing};
    for (const auto& artifact : evidence_refs) {
      training_inputs.push_back(input_value(artifact, "TREATMENT_BLIND"));
    }
    for (const auto& input : frozen_evidence->input_artifacts) {
      training_inputs.push_back(input_value(input.artifact, "PUBLIC_PROTOCOL"));
    }
  }
  training_inputs.push_back(input_value(reference("public-input"), "PUBLIC_PROTOCOL"));
  training_open["input_artifacts"] = JsonValue(std::move(training_inputs));
  result.push_back(finalize_freeze(std::move(training_open)));

  auto selection = base_freeze("access-selection", "SELECTION_FREEZE", "freeze-owner",
                               "FREEZE_AUTHORITY", "TRAINING_OPEN", "SELECTION_FROZEN",
                               "2026-08-21T00:00:02Z");
  selection["affected_block_ids"] =
      block_ids_value(blocks, protocol::BlockRole::h3_train);
  JsonObject selections;
  for (const auto context : {"NEAR_L2_L050", "NEAR_LLC_L050", "NEAR_BEYOND_LLC_L050",
                             "FAR_L2_L050", "FAR_LLC_L050", "FAR_BEYOND_LLC_L050"}) {
    JsonObject candidate;
    candidate.emplace("package", string_value("R0"));
    candidate.emplace("requested_hardware_state", string_value("H0"));
    selections.emplace(context, JsonValue(std::move(candidate)));
  }
  selection["h3_selections"] = JsonValue(std::move(selections));
  selection["training_input_artifacts"] =
      JsonValue(JsonArray{reference_value(artifacts.training)});
  selection["selection_rule_version"] =
      string_value(std::string(orchestration::kH3SelectionRuleId));
  selection["selection_record_checksum_sha256"] = string_value(std::string(kZeroHash));
  selection["input_artifacts"] =
      JsonValue(JsonArray{input_value(artifacts.training, "TRAINING_ONLY")});
  result.push_back(finalize_freeze(std::move(selection)));

  auto unseal = base_freeze("access-unseal", "VALIDATION_UNSEAL", "custodian",
                            "VALIDATION_CUSTODIAN", "SELECTION_FROZEN",
                            "VALIDATION_UNSEALED", "2026-08-21T00:00:03Z");
  unseal["status"] = string_value("AUTHORIZED");
  unseal["outcome_access_prohibited"] = JsonValue(false);
  unseal["affected_block_ids"] =
      block_ids_value(blocks, protocol::BlockRole::h3_validation);
  unseal["selection_record_ref"] = reference_value(
      {id<protocol::ArtifactId>(std::string(result[2].record_id.value())),
       result[2].record_sha256});
  unseal["validation_namespace_id"] = string_value("stage-a-validation-synthetic");
  unseal["validation_artifact_ref"] = reference_value(artifacts.validation);
  unseal["input_artifacts"] = JsonValue(
      JsonArray{input_value(artifacts.validation_approval, "PUBLIC_PROTOCOL")});
  result.push_back(finalize_freeze(std::move(unseal)));

  auto evaluated = base_freeze("access-h3-evaluated", "H3_EVALUATED", "confirmatory",
                               "CONFIRMATORY_ANALYST", "VALIDATION_UNSEALED",
                               "H3_EVALUATED", "2026-08-21T00:00:04Z");
  evaluated["outcome_access_prohibited"] = JsonValue(false);
  evaluated["affected_block_ids"] =
      block_ids_value(blocks, protocol::BlockRole::h3_validation);
  evaluated["selection_record_ref"] = reference_value(
      {id<protocol::ArtifactId>(std::string(result[2].record_id.value())),
       result[2].record_sha256});
  evaluated["validation_namespace_id"] = string_value("stage-a-validation-synthetic");
  evaluated["validation_artifact_ref"] = reference_value(artifacts.validation);
  evaluated["validation_unseal_record_ref"] = reference_value(
      {id<protocol::ArtifactId>(std::string(result[3].record_id.value())),
       result[3].record_sha256});
  evaluated["h3_evaluation_artifact_ref"] = reference_value(artifacts.h3_evaluation);
  evaluated["input_artifacts"] =
      JsonValue(JsonArray{input_value(artifacts.h3_evaluation, "VALIDATION_UNSEALED")});
  result.push_back(finalize_freeze(std::move(evaluated)));

  auto released = base_freeze("access-h1h2-released", "H1H2_RELEASED", "custodian",
                              "VALIDATION_CUSTODIAN", "H3_EVALUATED", "H1H2_RELEASED",
                              "2026-08-21T00:00:05Z");
  released["outcome_access_prohibited"] = JsonValue(false);
  released["affected_block_ids"] = block_ids_value(blocks);
  released["h3_evaluation_artifact_ref"] = reference_value(artifacts.h3_evaluation);
  released["h3_access_record_ref"] = reference_value(artifacts.h3_access);
  released["input_artifacts"] =
      JsonValue(JsonArray{input_value(artifacts.h3_access, "PUBLIC_PROTOCOL")});
  result.push_back(finalize_freeze(std::move(released)));
  return result;
}

auto authority_policy() -> orchestration::AuthorityPolicy {
  return {{{orchestration::AccessPrincipalRole::freeze_authority,
            id<protocol::AuthorityId>("freeze-owner")},
           {orchestration::AccessPrincipalRole::custodian,
            id<protocol::AuthorityId>("custodian")},
           {orchestration::AccessPrincipalRole::training_analyst,
            id<protocol::AuthorityId>("training")},
           {orchestration::AccessPrincipalRole::validation_authority,
            id<protocol::AuthorityId>("validation-authority")},
           {orchestration::AccessPrincipalRole::confirmatory_analyst,
            id<protocol::AuthorityId>("confirmatory")},
           {orchestration::AccessPrincipalRole::replacement_authority,
            id<protocol::AuthorityId>("replacement-owner")}},
          {}};
}

TEST(Stage14BlockPlan, DeterministicPlanProvesExactFactorialAndSeedSharing) {
  const auto input = generation_input(protocol::BlockRole::h3_train, 0U);
  const auto first = orchestration::generate_block_plan(input, namespaces());
  const auto second = orchestration::generate_block_plan(input, namespaces());
  ASSERT_TRUE(first);
  ASSERT_TRUE(second);
  EXPECT_EQ(first.value().canonical_json, second.value().canonical_json);
  EXPECT_EQ(first.value().plan.cells.size(), orchestration::kStageACellsPerBlock);
  EXPECT_TRUE(
      orchestration::validate_block_plan(first.value().plan, input.seeds, namespaces())
          .empty());
  EXPECT_EQ(orchestration::expected_stage_a_cells().size(), 180U);
  EXPECT_TRUE(std::all_of(first.value().plan.cells.begin(),
                          first.value().plan.cells.end(), [](const auto& cell) {
                            const bool linked =
                                cell.package == protocol::QueuePackage::l0 ||
                                cell.package == protocol::QueuePackage::l1;
                            return linked == cell.node_seed_ref.has_value();
                          }));
}

TEST(Stage14BlockPlan, RejectsEveryStructuralFactorAndOrdinalDefect) {
  const auto input = generation_input(protocol::BlockRole::h3_train, 1U);
  const auto valid = generated(protocol::BlockRole::h3_train, 1U);
  auto missing = valid.plan;
  missing.cells.pop_back();
  EXPECT_TRUE(
      has_rule(orchestration::validate_block_plan(missing, input.seeds, namespaces()),
               "BLK-EXACT-FACTORIAL-PROOF"));

  auto duplicate = valid.plan;
  duplicate.cells.back().package = duplicate.cells.front().package;
  duplicate.cells.back().requested_hardware_state =
      duplicate.cells.front().requested_hardware_state;
  duplicate.cells.back().placement = duplicate.cells.front().placement;
  duplicate.cells.back().working_set_class = duplicate.cells.front().working_set_class;
  duplicate.cells.back().load_level = duplicate.cells.front().load_level;
  EXPECT_TRUE(
      has_rule(orchestration::validate_block_plan(duplicate, input.seeds, namespaces()),
               "BLK-FACTOR-DUPLICATE"));

  auto ordinal = valid.plan;
  ordinal.cells.back().cell_ordinal = ordinal.cells.front().cell_ordinal;
  EXPECT_TRUE(
      has_rule(orchestration::validate_block_plan(ordinal, input.seeds, namespaces()),
               "BLK-CELL-ORDINAL-EXACT"));

  auto plot = valid.plan;
  plot.cells.front().requested_hardware_state = plot.whole_plot_order[1];
  EXPECT_TRUE(
      has_rule(orchestration::validate_block_plan(plot, input.seeds, namespaces()),
               "BLK-WHOLE-PLOT-ORDER"));

  auto seed = valid.plan;
  seed.cells.front().event_seed_ref = id<protocol::SeedId>("wrong-event-seed");
  EXPECT_TRUE(
      has_rule(orchestration::validate_block_plan(seed, input.seeds, namespaces()),
               "BLK-SEED-SHARING"));
}

TEST(Stage14BlockPlan, RejectsRoleNamespaceCollisionsAndPathIdentity) {
  auto registry = namespaces();
  registry.role_bindings[1].namespace_id = registry.role_bindings[0].namespace_id;
  EXPECT_TRUE(has_rule(orchestration::validate_role_namespaces(registry),
                       "BLK-ROLE-NAMESPACE-UNIQUE"));
  auto seeds = catalog(protocol::BlockRole::h3_train, {2U, 0U});
  seeds.arrival_seed_ids[0] = id<protocol::SeedId>("directory/seed");
  const auto errors = orchestration::validate_seed_catalog(seeds, namespaces());
  EXPECT_TRUE(has_rule(errors, "BLK-SEED-OPAQUE"));
  EXPECT_FALSE(orchestration::make_block_id(
      id<protocol::PlatformId>("directory/platform"),
      id<protocol::BuildId>("synthetic-build"), protocol::BlockRole::h3_train, 2U));
  const auto first_build = orchestration::make_block_id(
      id<protocol::PlatformId>("synthetic-platform"),
      id<protocol::BuildId>("synthetic-build-a"), protocol::BlockRole::h3_train, 2U);
  const auto second_build = orchestration::make_block_id(
      id<protocol::PlatformId>("synthetic-platform"),
      id<protocol::BuildId>("synthetic-build-b"), protocol::BlockRole::h3_train, 2U);
  ASSERT_TRUE(first_build);
  ASSERT_TRUE(second_build);
  EXPECT_NE(first_build.value(), second_build.value());
}

TEST(Stage14BlockPlan, PropertySweepPreservesFactorialForFrozenKeys) {
  for (std::uint32_t key = 1U; key <= 32U; ++key) {
    const auto input =
        generation_input(protocol::BlockRole::h3_validation, 100U + key, key * 17U);
    const auto result = orchestration::generate_block_plan(input, namespaces());
    ASSERT_TRUE(result) << key;
    EXPECT_TRUE(orchestration::validate_block_plan(result.value().plan, input.seeds,
                                                   namespaces())
                    .empty())
        << key;
  }
}

TEST(Stage14BlockPlan, PoolEnforcesRolesUniquenessAndCounterbalance) {
  std::vector<protocol::BlockPlan> blocks;
  std::vector<orchestration::BlockSeedCatalog> seeds;
  std::array<std::uint64_t, 2> first_state_counts{};
  std::uint64_t ordinal = 200U;
  while ((first_state_counts[0] == 0U || first_state_counts[1] == 0U) &&
         ordinal < 400U) {
    const auto input = generation_input(protocol::BlockRole::h3_train, ordinal,
                                        static_cast<std::uint32_t>(ordinal));
    const auto result = orchestration::generate_block_plan(input, namespaces());
    ASSERT_TRUE(result);
    const auto index =
        result.value().plan.whole_plot_order[0] == protocol::RequestedHardwareState::h0
            ? 0U
            : 1U;
    if (first_state_counts[index] == 0U) {
      blocks.push_back(result.value().plan);
      seeds.push_back(input.seeds);
      ++first_state_counts[index];
    }
    ++ordinal;
  }
  ASSERT_EQ(blocks.size(), 2U);
  EXPECT_TRUE(
      orchestration::validate_block_pool(blocks, seeds, namespaces(), 2U, 0U, 0U)
          .empty());
  auto duplicate = blocks;
  duplicate[1].block_id = duplicate[0].block_id;
  EXPECT_TRUE(has_rule(
      orchestration::validate_block_pool(duplicate, seeds, namespaces(), 2U, 0U, 0U),
      "BLK-POOL-IDENTITY-UNIQUE"));
}

TEST(Stage14Precision, RegistersExactFamiliesAndPostSelectionReporting) {
  EXPECT_EQ(orchestration::h1_contrast_ids().size(), 7U);
  EXPECT_EQ(orchestration::h2_contrast_ids().size(), 20U);
  EXPECT_EQ(orchestration::h3_training_pairs().size(), 270U);
  EXPECT_EQ(orchestration::h3_validation_family().size(), 540U);
  std::map<protocol::H3Context, protocol::H3Candidate> selections;
  const auto candidates = orchestration::h3_candidates();
  std::size_t index = 0U;
  for (const auto context : orchestration::h3_contexts()) {
    selections.emplace(context, candidates[index++]);
  }
  const auto reported = orchestration::h3_reported_comparisons(selections);
  ASSERT_TRUE(reported);
  EXPECT_EQ(reported.value().size(), 54U);
  selections.erase(selections.begin());
  EXPECT_FALSE(orchestration::h3_reported_comparisons(selections));
}

TEST(Stage14Precision, EnforcesCountsMinimaCeilingAndNoOutcomeSizing) {
  const orchestration::ProspectiveCounts counts{20U, 20U, 20U, 12U, 8U, 20U, 3600U};
  auto valid = orchestration::evaluate_precision_plan({counts, evidence("valid")});
  ASSERT_TRUE(valid);
  ASSERT_EQ(valid.value().state, orchestration::PrecisionState::resolved);
  ASSERT_TRUE(valid.value().role_counts);
  EXPECT_EQ(required(valid.value().role_counts).h1h2_supplemental, 0U);

  auto bad_formula = counts;
  bad_formula.r12 = 21U;
  EXPECT_FALSE(
      orchestration::evaluate_precision_plan({bad_formula, evidence("bad-formula")}));

  auto infeasible = counts;
  infeasible.r_h1 = 31U;
  infeasible.r12 = 31U;
  infeasible.rtotal = 31U;
  infeasible.nruns = 5580U;
  const auto ceiling =
      orchestration::evaluate_precision_plan({infeasible, evidence("ceiling")});
  ASSERT_TRUE(ceiling);
  EXPECT_EQ(ceiling.value().state, orchestration::PrecisionState::infeasible);

  auto outcome_evidence = evidence("outcome");
  outcome_evidence.input_artifacts.front().access_class =
      protocol::AccessClass::training_only;
  EXPECT_FALSE(orchestration::evaluate_precision_plan({counts, outcome_evidence}));
  const auto unresolved =
      orchestration::evaluate_precision_plan({std::nullopt, std::nullopt});
  ASSERT_TRUE(unresolved);
  EXPECT_EQ(unresolved.value().state, orchestration::PrecisionState::not_evaluated);
}

TEST(Stage14Access, EnforcesSealChronologyRolesAndOutcomeBoundaries) {
  const auto train = generated(protocol::BlockRole::h3_train, 500U);
  const auto validation = generated(protocol::BlockRole::h3_validation, 501U);
  const auto supplemental = generated(protocol::BlockRole::h1h2_supplemental, 502U);
  const std::vector blocks{train.plan, validation.plan, supplemental.plan};
  const auto training = reference("training-output");
  const auto validation_artifact = reference("validation-output");
  const auto approval = reference("validation-approval");
  const auto evaluation = reference("h3-evaluation");
  const auto access = reference("h3-access-audit");
  const std::vector<orchestration::ArtifactAccessRecord> artifacts{
      {reference("public-input"), protocol::AccessClass::public_protocol, std::nullopt,
       std::nullopt, std::nullopt, std::nullopt, std::nullopt},
      {training, protocol::AccessClass::training_only, train.plan.block_id,
       train.plan.seed_subspace_id, protocol::BlockRole::h3_train,
       orchestration::AccessPrincipalRole::training_analyst,
       id<protocol::AuthorityId>("training")},
      {validation_artifact, protocol::AccessClass::validation_sealed,
       validation.plan.block_id, role_namespace(protocol::BlockRole::h3_validation),
       protocol::BlockRole::h3_validation, std::nullopt, std::nullopt},
      {approval, protocol::AccessClass::public_protocol, std::nullopt, std::nullopt,
       std::nullopt, orchestration::AccessPrincipalRole::validation_authority,
       id<protocol::AuthorityId>("validation-authority")},
      {evaluation, protocol::AccessClass::validation_unsealed, validation.plan.block_id,
       validation.plan.seed_subspace_id, protocol::BlockRole::h3_validation,
       orchestration::AccessPrincipalRole::confirmatory_analyst,
       id<protocol::AuthorityId>("confirmatory")},
      {access, protocol::AccessClass::public_protocol, std::nullopt, std::nullopt,
       std::nullopt, orchestration::AccessPrincipalRole::confirmatory_analyst,
       id<protocol::AuthorityId>("confirmatory")}};
  const auto records = make_access_records(
      blocks, {training, validation_artifact, approval, evaluation, access});
  const auto policy = authority_policy();
  const auto ledger = orchestration::validate_access_ledger(blocks, records, artifacts,
                                                            namespaces(), policy);
  EXPECT_TRUE(ledger.errors.empty()) << describe_errors(ledger.errors);
  EXPECT_EQ(ledger.final_state, protocol::AccessState::h1h2_released);

  EXPECT_TRUE(orchestration::authorize_outcome_access(
      ledger, blocks, policy,
      {id<protocol::AuthorityId>("training"),
       orchestration::AccessPrincipalRole::training_analyst,
       orchestration::OutcomeDomain::h3_training, train.plan.block_id}));
  EXPECT_TRUE(orchestration::authorize_outcome_access(
      ledger, blocks, policy,
      {id<protocol::AuthorityId>("confirmatory"),
       orchestration::AccessPrincipalRole::confirmatory_analyst,
       orchestration::OutcomeDomain::h3_validation, validation.plan.block_id}));
  EXPECT_FALSE(orchestration::authorize_outcome_access(
      ledger, blocks, policy,
      {id<protocol::AuthorityId>("training"),
       orchestration::AccessPrincipalRole::training_analyst,
       orchestration::OutcomeDomain::h3_validation, validation.plan.block_id}));

  auto reordered = records;
  std::swap(reordered[2], reordered[3]);
  const auto bad_ledger = orchestration::validate_access_ledger(
      blocks, reordered, artifacts, namespaces(), policy);
  EXPECT_TRUE(has_rule(bad_ledger.errors, "ACCESS-PREDECESSOR-STATE"));

  auto missing_context = records;
  missing_context[2].h3_selections.erase(missing_context[2].h3_selections.begin());
  const auto bad_selection = orchestration::validate_access_ledger(
      blocks, missing_context, artifacts, namespaces(), policy);
  EXPECT_TRUE(has_rule(bad_selection.errors, "ACCESS-H3-SIX-CONTEXTS"));

  auto bad_selection_hash = records;
  bad_selection_hash[2].selection_record_checksum_sha256 = sha();
  const auto rejected_hash = orchestration::validate_access_ledger(
      blocks, bad_selection_hash, artifacts, namespaces(), policy);
  EXPECT_TRUE(has_rule(rejected_hash.errors, "ACCESS-SELECTION-PAYLOAD-HASH"));

  auto unbound_training = records;
  unbound_training[2].input_artifacts.clear();
  const auto rejected_training = orchestration::validate_access_ledger(
      blocks, unbound_training, artifacts, namespaces(), policy);
  EXPECT_TRUE(has_rule(rejected_training.errors, "ACCESS-TRAINING-INPUTS-EXACT"));

  auto incomplete_freeze = records;
  incomplete_freeze[1].decision_value = std::nullopt;
  const auto bad_freeze = orchestration::validate_access_ledger(
      blocks, incomplete_freeze, artifacts, namespaces(), policy);
  EXPECT_TRUE(has_rule(bad_freeze.errors, "ACCESS-TRAINING-FREEZE-EVIDENCE"));
}

TEST(Stage14Access, EnforcesAuthoritySegregationAndExplicitOverlapEvidence) {
  auto policy = authority_policy();
  policy.assignments[1].authority_id = policy.assignments[0].authority_id;
  EXPECT_TRUE(has_rule(orchestration::validate_authority_policy(policy, {}),
                       "ACCESS-AUTHORITY-SEGREGATION"));
  const auto overlap = reference("overlap-authorization");
  policy.permitted_overlaps.push_back(
      {orchestration::AccessPrincipalRole::freeze_authority,
       orchestration::AccessPrincipalRole::custodian,
       policy.assignments[0].authority_id, overlap});
  const std::vector artifacts{orchestration::ArtifactAccessRecord{
      overlap, protocol::AccessClass::public_protocol, std::nullopt, std::nullopt,
      std::nullopt, std::nullopt, std::nullopt}};
  EXPECT_TRUE(orchestration::validate_authority_policy(policy, artifacts).empty());
}

TEST(Stage14Replacement, AuthorizesOnlyCompleteRolePreservingNewBlocks) {
  const auto original = generated(protocol::BlockRole::h3_train, 700U, 11U);
  auto replacement_input = generation_input(protocol::BlockRole::h3_train, 701U, 97U);
  replacement_input.replacement = orchestration::ReplacementPlanInput{
      original.plan.block_id, id<protocol::RecordId>("replacement-authorization"),
      original.plan.block_ordinal, original.plan.block_role,
      original.plan.seed_subspace_id};
  const auto authorization =
      replacement_authorization(original.plan, replacement_input);
  const auto replacement_id = orchestration::make_block_id(
      replacement_input.platform_id, replacement_input.build_id, replacement_input.role,
      replacement_input.block_ordinal);
  ASSERT_TRUE(replacement_id);
  const auto run = invalid_run(original.plan.block_id);
  const auto failure =
      invalidating_failure(original.plan.block_id, replacement_id.value());
  const orchestration::ReplacementBudget budget{original.plan.platform_id, 2U,
                                                reference("replacement-budget")};
  const std::vector existing{original.plan};
  const orchestration::ReplacementRequest request{original.plan, run, failure,
                                                  authorization, replacement_input};
  const auto decision = orchestration::decide_complete_block_replacement(
      request, existing, budget, namespaces());
  ASSERT_TRUE(decision) << decision.errors().front().message;
  EXPECT_EQ(decision.value().state,
            orchestration::ReplacementDecisionState::authorized);
  ASSERT_TRUE(decision.value().replacement_plan);
  const auto& replacement = required(decision.value().replacement_plan).plan;
  EXPECT_EQ(replacement.cells.size(), 180U);
  EXPECT_EQ(replacement.block_role, original.plan.block_role);
  EXPECT_EQ(replacement.replaces_block_id, original.plan.block_id);
  const std::vector replacement_graph{original.plan, replacement};
  const orchestration::AccessLedgerResult released{protocol::AccessState::h1h2_released,
                                                   {}};
  const auto policy = authority_policy();
  EXPECT_FALSE(orchestration::authorize_outcome_access(
      released, replacement_graph, policy,
      {id<protocol::AuthorityId>("confirmatory"),
       orchestration::AccessPrincipalRole::confirmatory_analyst,
       orchestration::OutcomeDomain::h1h2, original.plan.block_id}));
  EXPECT_TRUE(orchestration::authorize_outcome_access(
      released, replacement_graph, policy,
      {id<protocol::AuthorityId>("confirmatory"),
       orchestration::AccessPrincipalRole::confirmatory_analyst,
       orchestration::OutcomeDomain::h1h2, replacement.block_id}));
  auto valid_full = run;
  valid_full.validity = protocol::RunValidity::valid;
  valid_full.zero_loss_status = protocol::GateStatus::fail;
  EXPECT_FALSE(orchestration::decide_complete_block_replacement(
      {original.plan, valid_full, failure, authorization, replacement_input}, existing,
      budget, namespaces()));

  auto low_tail = run;
  low_tail.validity = protocol::RunValidity::valid;
  low_tail.effective_tail_status = protocol::GateStatus::fail;
  EXPECT_FALSE(orchestration::decide_complete_block_replacement(
      {original.plan, low_tail, failure, authorization, replacement_input}, existing,
      budget, namespaces()));

  auto wrong_role = replacement_input;
  wrong_role.role = protocol::BlockRole::h3_validation;
  wrong_role.seeds = catalog(protocol::BlockRole::h3_validation, {701U, 97U});
  EXPECT_FALSE(orchestration::decide_complete_block_replacement(
      {original.plan, run, failure, authorization, wrong_role}, existing, budget,
      namespaces()));

  auto wrong_build = replacement_input;
  wrong_build.build_id = id<protocol::BuildId>("different-build");
  EXPECT_FALSE(orchestration::decide_complete_block_replacement(
      {original.plan, run, failure, authorization, wrong_build}, existing, budget,
      namespaces()));
}

TEST(Stage14Replacement, ExhaustedBudgetStopsUnresolvedAndBranchesFail) {
  const auto original = generated(protocol::BlockRole::h3_train, 710U, 13U);
  auto replacement_input = generation_input(protocol::BlockRole::h3_train, 711U, 101U);
  replacement_input.replacement = orchestration::ReplacementPlanInput{
      original.plan.block_id, id<protocol::RecordId>("replacement-authorization"),
      original.plan.block_ordinal, original.plan.block_role,
      original.plan.seed_subspace_id};
  const auto authorization =
      replacement_authorization(original.plan, replacement_input);
  const auto replacement_id = orchestration::make_block_id(
      replacement_input.platform_id, replacement_input.build_id, replacement_input.role,
      replacement_input.block_ordinal);
  ASSERT_TRUE(replacement_id);
  const auto run = invalid_run(original.plan.block_id);
  const auto failure =
      invalidating_failure(original.plan.block_id, replacement_id.value());
  const orchestration::ReplacementRequest request{original.plan, run, failure,
                                                  authorization, replacement_input};

  const std::vector existing{original.plan};
  const orchestration::ReplacementBudget exhausted{original.plan.platform_id, 0U,
                                                   reference("replacement-budget")};
  const auto stopped = orchestration::decide_complete_block_replacement(
      request, existing, exhausted, namespaces());
  ASSERT_TRUE(stopped);
  EXPECT_EQ(stopped.value().state,
            orchestration::ReplacementDecisionState::study_unresolved);
  EXPECT_FALSE(stopped.value().replacement_plan);

  const orchestration::ReplacementBudget budget{original.plan.platform_id, 2U,
                                                reference("replacement-budget")};
  const auto first = orchestration::decide_complete_block_replacement(
      request, existing, budget, namespaces());
  ASSERT_TRUE(first);
  ASSERT_TRUE(first.value().replacement_plan);
  const std::vector branched{original.plan,
                             required(first.value().replacement_plan).plan};
  const auto second = orchestration::decide_complete_block_replacement(
      request, branched, budget, namespaces());
  EXPECT_FALSE(second);
  EXPECT_TRUE(has_rule(second.errors(), "REPLACEMENT-NO-BRANCH"));
}

TEST(Stage14Amendment, RequiresAppendOnlyUnbranchedOutcomeBlindLineage) {
  const auto train = generated(protocol::BlockRole::h3_train, 720U);
  const auto validation = generated(protocol::BlockRole::h3_validation, 721U);
  const auto supplemental = generated(protocol::BlockRole::h1h2_supplemental, 722U);
  const std::vector blocks{train.plan, validation.plan, supplemental.plan};
  const auto training = reference("amend-training-output");
  const auto validation_artifact = reference("amend-validation-output");
  const auto approval = reference("amend-validation-approval");
  const auto evaluation = reference("amend-h3-evaluation");
  const auto access = reference("amend-h3-access");
  const std::vector<orchestration::ArtifactAccessRecord> artifacts{
      {reference("public-input"), protocol::AccessClass::public_protocol, std::nullopt,
       std::nullopt, std::nullopt, std::nullopt, std::nullopt},
      {training, protocol::AccessClass::training_only, train.plan.block_id,
       train.plan.seed_subspace_id, protocol::BlockRole::h3_train,
       orchestration::AccessPrincipalRole::training_analyst,
       id<protocol::AuthorityId>("training")},
      {validation_artifact, protocol::AccessClass::validation_sealed,
       validation.plan.block_id, role_namespace(protocol::BlockRole::h3_validation),
       protocol::BlockRole::h3_validation, std::nullopt, std::nullopt},
      {approval, protocol::AccessClass::public_protocol, std::nullopt, std::nullopt,
       std::nullopt, orchestration::AccessPrincipalRole::validation_authority,
       id<protocol::AuthorityId>("validation-authority")},
      {evaluation, protocol::AccessClass::validation_unsealed, validation.plan.block_id,
       validation.plan.seed_subspace_id, protocol::BlockRole::h3_validation,
       orchestration::AccessPrincipalRole::confirmatory_analyst,
       id<protocol::AuthorityId>("confirmatory")},
      {access, protocol::AccessClass::public_protocol, std::nullopt, std::nullopt,
       std::nullopt, orchestration::AccessPrincipalRole::confirmatory_analyst,
       id<protocol::AuthorityId>("confirmatory")}};
  auto records = make_access_records(
      blocks, {training, validation_artifact, approval, evaluation, access});
  auto amendment =
      base_freeze("access-amendment", "AMENDMENT", "protocol-owner", "PROTOCOL_OWNER",
                  "H1H2_RELEASED", "H1H2_RELEASED", "2026-08-21T00:00:06Z");
  amendment["supersedes_id"] =
      string_value(std::string(records.back().record_id.value()));
  amendment["prior_protocol_version"] = string_value("2.0.0-pre.2");
  amendment["new_protocol_version"] = string_value("2.0.0-pre.3");
  amendment["rationale"] = string_value("synthetic amendment lineage test");
  amendment["affected_documents"] = JsonValue(JsonArray{string_value("PROTOCOL.md")});
  amendment["affected_schema_ids"] =
      JsonValue(JsonArray{string_value("freeze-record.schema.json")});
  amendment["affected_estimands"] = JsonValue(JsonArray{string_value("H1")});
  amendment["affected_contrast_ids"] = JsonValue(JsonArray{});
  amendment["pilot_record_disposition"] = string_value("no pilot records exist");
  amendment["prior_authoritative_hashes"] = JsonValue(JsonArray{reference_value(
      {id<protocol::ArtifactId>(std::string(records.back().record_id.value())),
       records.back().record_sha256})});
  records.push_back(finalize_freeze(amendment));
  const auto policy = authority_policy();
  const auto valid = orchestration::validate_access_ledger(blocks, records, artifacts,
                                                           namespaces(), policy);
  EXPECT_TRUE(valid.errors.empty()) << describe_errors(valid.errors);

  auto branch_object = std::move(amendment);
  branch_object["record_id"] = string_value("access-amendment-branch");
  branch_object["created_at_utc"] = string_value("2026-08-21T00:00:07Z");
  records.push_back(finalize_freeze(std::move(branch_object)));
  const auto branched = orchestration::validate_access_ledger(
      blocks, records, artifacts, namespaces(), policy);
  EXPECT_TRUE(has_rule(branched.errors, "ACCESS-AMENDMENT-LINEAGE"));

  auto outcome = records;
  outcome[6].input_artifacts.front().access_class =
      protocol::AccessClass::training_only;
  const auto leaked = orchestration::validate_access_ledger(blocks, outcome, artifacts,
                                                            namespaces(), policy);
  EXPECT_TRUE(has_rule(leaked.errors, "ACCESS-AMENDMENT-NO-OUTCOMES"));
}

TEST(Stage14CrossRecord, ResolvesCompletePoolAndRejectsMissingSeedEvidence) {
  const std::array role_targets{std::pair{protocol::BlockRole::h3_train, 12U},
                                std::pair{protocol::BlockRole::h3_validation, 8U},
                                std::pair{protocol::BlockRole::h1h2_supplemental, 1U}};
  std::vector<protocol::BlockPlan> blocks;
  std::vector<orchestration::BlockSeedCatalog> catalogs;
  std::uint64_t h0_first = 0U;
  std::uint64_t h1_first = 0U;
  std::uint64_t ordinal = 800U;
  for (const auto& [role, target] : role_targets) {
    std::uint64_t accepted = 0U;
    while (accepted < target && ordinal < 2000U) {
      const auto input =
          generation_input(role, ordinal, static_cast<std::uint32_t>(ordinal));
      const auto plan = orchestration::generate_block_plan(input, namespaces());
      ASSERT_TRUE(plan);
      const auto h0 =
          plan.value().plan.whole_plot_order[0] == protocol::RequestedHardwareState::h0;
      const auto need_h0 = h0_first <= h1_first;
      ++ordinal;
      if (h0 != need_h0) {
        continue;
      }
      blocks.push_back(plan.value().plan);
      catalogs.push_back(input.seeds);
      h0_first += h0 ? 1U : 0U;
      h1_first += h0 ? 0U : 1U;
      ++accepted;
    }
    ASSERT_EQ(accepted, target);
  }
  const orchestration::ProspectiveCounts counts{21U, 20U, 21U, 12U, 8U, 21U, 3780U};
  const auto precision =
      orchestration::evaluate_precision_plan({counts, evidence("cross-record")});
  ASSERT_TRUE(precision);
  ASSERT_EQ(precision.value().state, orchestration::PrecisionState::resolved);

  const auto training = reference("cross-training-output");
  const auto validation = reference("cross-validation-output");
  const auto approval = reference("cross-validation-approval");
  const auto evaluation = reference("cross-h3-evaluation");
  const auto access = reference("cross-h3-access");
  const auto train = std::find_if(blocks.begin(), blocks.end(), [](const auto& block) {
    return block.block_role == protocol::BlockRole::h3_train;
  });
  const auto validation_block =
      std::find_if(blocks.begin(), blocks.end(), [](const auto& block) {
        return block.block_role == protocol::BlockRole::h3_validation;
      });
  ASSERT_NE(train, blocks.end());
  ASSERT_NE(validation_block, blocks.end());
  const std::vector<orchestration::ArtifactAccessRecord> artifacts{
      {reference("public-input"), protocol::AccessClass::public_protocol, std::nullopt,
       std::nullopt, std::nullopt, std::nullopt, std::nullopt},
      {reference("cross-record-public"), protocol::AccessClass::public_protocol,
       std::nullopt, std::nullopt, std::nullopt, std::nullopt, std::nullopt},
      {reference("cross-record-delta"), protocol::AccessClass::treatment_blind,
       std::nullopt, std::nullopt, std::nullopt, std::nullopt, std::nullopt},
      {reference("cross-record-bootstrap"), protocol::AccessClass::treatment_blind,
       std::nullopt, std::nullopt, std::nullopt, std::nullopt, std::nullopt},
      {reference("cross-record-h1"), protocol::AccessClass::treatment_blind,
       std::nullopt, std::nullopt, std::nullopt, std::nullopt, std::nullopt},
      {reference("cross-record-h2"), protocol::AccessClass::treatment_blind,
       std::nullopt, std::nullopt, std::nullopt, std::nullopt, std::nullopt},
      {reference("cross-record-train"), protocol::AccessClass::treatment_blind,
       std::nullopt, std::nullopt, std::nullopt, std::nullopt, std::nullopt},
      {reference("cross-record-validation"), protocol::AccessClass::treatment_blind,
       std::nullopt, std::nullopt, std::nullopt, std::nullopt, std::nullopt},
      {reference("replacement-budget"), protocol::AccessClass::public_protocol,
       std::nullopt, std::nullopt, std::nullopt, std::nullopt, std::nullopt},
      {training, protocol::AccessClass::training_only, train->block_id,
       train->seed_subspace_id, protocol::BlockRole::h3_train,
       orchestration::AccessPrincipalRole::training_analyst,
       id<protocol::AuthorityId>("training")},
      {validation, protocol::AccessClass::validation_sealed, validation_block->block_id,
       role_namespace(protocol::BlockRole::h3_validation),
       protocol::BlockRole::h3_validation, std::nullopt, std::nullopt},
      {approval, protocol::AccessClass::public_protocol, std::nullopt, std::nullopt,
       std::nullopt, orchestration::AccessPrincipalRole::validation_authority,
       id<protocol::AuthorityId>("validation-authority")},
      {evaluation, protocol::AccessClass::validation_unsealed,
       validation_block->block_id, validation_block->seed_subspace_id,
       protocol::BlockRole::h3_validation,
       orchestration::AccessPrincipalRole::confirmatory_analyst,
       id<protocol::AuthorityId>("confirmatory")},
      {access, protocol::AccessClass::public_protocol, std::nullopt, std::nullopt,
       std::nullopt, orchestration::AccessPrincipalRole::confirmatory_analyst,
       id<protocol::AuthorityId>("confirmatory")}};
  const auto freezes =
      make_access_records(blocks, {training, validation, approval, evaluation, access},
                          counts, precision.value().evidence);
  std::vector<protocol::ProtocolRecord> records;
  records.reserve(blocks.size() + freezes.size());
  for (const auto& block : blocks) {
    records.emplace_back(block);
  }
  for (const auto& freeze : freezes) {
    records.emplace_back(freeze);
  }
  const std::optional<orchestration::PrecisionResult> precision_input{
      precision.value()};
  const std::optional<orchestration::ReplacementBudget> budget{
      orchestration::ReplacementBudget{id<protocol::PlatformId>("synthetic-platform"),
                                       2U, reference("replacement-budget")}};
  const auto policy = authority_policy();
  const auto registry = namespaces();
  const orchestration::Stage14CrossRecordSemanticValidator validator{
      registry, catalogs, artifacts, policy, precision_input, budget};
  const auto valid = validator.validate({records});
  EXPECT_TRUE(valid.empty()) << describe_errors(valid);

  const std::span<const orchestration::BlockSeedCatalog> missing_catalogs{
      catalogs.data(), catalogs.size() - 1U};
  const orchestration::Stage14CrossRecordSemanticValidator missing{
      registry, missing_catalogs, artifacts, policy, precision_input, budget};
  const auto invalid = missing.validate({records});
  EXPECT_TRUE(has_rule(invalid, "BLK-SEED-CATALOG-MISSING"));

  auto mismatched_counts = counts;
  mismatched_counts.r_h1 = 20U;
  mismatched_counts.r12 = 20U;
  mismatched_counts.rtotal = 20U;
  mismatched_counts.nruns = 3600U;
  const auto mismatched_freezes =
      make_access_records(blocks, {training, validation, approval, evaluation, access},
                          mismatched_counts, precision.value().evidence);
  std::vector<protocol::ProtocolRecord> mismatched_records;
  mismatched_records.reserve(blocks.size() + mismatched_freezes.size());
  for (const auto& block : blocks) {
    mismatched_records.emplace_back(block);
  }
  for (const auto& freeze : mismatched_freezes) {
    mismatched_records.emplace_back(freeze);
  }
  const auto mismatch = validator.validate({mismatched_records});
  EXPECT_TRUE(has_rule(mismatch, "ACCESS-PRECISION-FREEZE-COUNTS"));
}

} // namespace
