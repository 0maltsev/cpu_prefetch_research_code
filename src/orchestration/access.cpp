#include "cpu_prefetch/orchestration/access.hpp"

#include "cpu_prefetch/workload/deterministic.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <map>
#include <set>
#include <string>
#include <tuple>
#include <utility>
#include <variant>

namespace cpu_prefetch::orchestration {
namespace {

void add(std::vector<protocol::ValidationError>& errors,
         protocol::ErrorCategory category, std::string path, std::string rule,
         std::string message) {
  errors.push_back({category, std::move(path), std::move(rule), std::move(message)});
}

template <typename T>
[[nodiscard]] auto fail(protocol::ErrorCategory category, std::string path,
                        std::string rule, std::string message) -> protocol::Result<T> {
  return protocol::Result<T>::failure(
      {category, std::move(path), std::move(rule), std::move(message)});
}

[[nodiscard]] auto opaque(std::string_view value) noexcept -> bool {
  return !value.empty() && value.find('/') == std::string_view::npos &&
         value.find('\\') == std::string_view::npos;
}

[[nodiscard]] auto candidate_valid(const protocol::H3Candidate& candidate) -> bool {
  const auto candidates = h3_candidates();
  return std::any_of(
      candidates.begin(), candidates.end(), [&](const protocol::H3Candidate& expected) {
        return candidate.package == expected.package &&
               candidate.requested_hardware_state == expected.requested_hardware_state;
      });
}

[[nodiscard]] auto principal_for(protocol::RecordKind kind)
    -> std::optional<AccessPrincipalRole> {
  switch (kind) {
  case protocol::RecordKind::protocol_freeze:
  case protocol::RecordKind::selection_freeze:
    return AccessPrincipalRole::freeze_authority;
  case protocol::RecordKind::validation_unseal:
  case protocol::RecordKind::h1h2_released:
    return AccessPrincipalRole::custodian;
  case protocol::RecordKind::h3_evaluated:
    return AccessPrincipalRole::confirmatory_analyst;
  case protocol::RecordKind::replacement_authorization:
    return AccessPrincipalRole::replacement_authority;
  case protocol::RecordKind::amendment:
    return std::nullopt;
  }
  return std::nullopt;
}

[[nodiscard]] auto protocol_role_for(AccessPrincipalRole role)
    -> std::optional<protocol::AuthorityRole> {
  switch (role) {
  case AccessPrincipalRole::freeze_authority:
    return protocol::AuthorityRole::freeze_authority;
  case AccessPrincipalRole::custodian:
    return protocol::AuthorityRole::validation_custodian;
  case AccessPrincipalRole::confirmatory_analyst:
    return protocol::AuthorityRole::confirmatory_analyst;
  case AccessPrincipalRole::replacement_authority:
    return protocol::AuthorityRole::replacement_authority;
  case AccessPrincipalRole::training_analyst:
  case AccessPrincipalRole::validation_authority:
    return std::nullopt;
  }
  return std::nullopt;
}

[[nodiscard]] auto assignment_for(const AuthorityPolicy& policy,
                                  AccessPrincipalRole role)
    -> const PrincipalAssignment* {
  const auto iterator =
      std::find_if(policy.assignments.begin(), policy.assignments.end(),
                   [role](const PrincipalAssignment& assignment) {
                     return assignment.role == role;
                   });
  return iterator == policy.assignments.end() ? nullptr : &*iterator;
}

[[nodiscard]] auto artifact_for(std::span<const ArtifactAccessRecord> artifacts,
                                const protocol::ArtifactReference& reference)
    -> const ArtifactAccessRecord* {
  const auto iterator =
      std::find_if(artifacts.begin(), artifacts.end(),
                   [&](const auto& record) { return record.artifact == reference; });
  return iterator == artifacts.end() ? nullptr : &*iterator;
}

[[nodiscard]] auto id_in(std::span<const protocol::BlockPlan> blocks,
                         const protocol::BlockId& id) -> const protocol::BlockPlan* {
  const auto iterator =
      std::find_if(blocks.begin(), blocks.end(),
                   [&](const auto& block) { return block.block_id == id; });
  return iterator == blocks.end() ? nullptr : &*iterator;
}

[[nodiscard]] auto role_allowed_for_record(const protocol::FreezeRecord& record,
                                           protocol::BlockRole role) -> bool {
  switch (record.record_kind) {
  case protocol::RecordKind::selection_freeze:
    return role == protocol::BlockRole::h3_train;
  case protocol::RecordKind::validation_unseal:
  case protocol::RecordKind::h3_evaluated:
    return role == protocol::BlockRole::h3_validation;
  case protocol::RecordKind::h1h2_released:
  case protocol::RecordKind::protocol_freeze:
  case protocol::RecordKind::amendment:
    return role == protocol::BlockRole::h3_train ||
           role == protocol::BlockRole::h3_validation ||
           role == protocol::BlockRole::h1h2_supplemental;
  case protocol::RecordKind::replacement_authorization:
    return true;
  }
  return false;
}

[[nodiscard]] auto zero_self_hash_matches(const protocol::FreezeRecord& record)
    -> bool {
  const auto* object = record.source_document.as_object();
  if (object == nullptr || !object->contains("record_sha256")) {
    return false;
  }
  auto zeroed = *object;
  zeroed["record_sha256"] = protocol::json::Value(std::string(64U, '0'));
  const auto canonical =
      protocol::json::canonicalize(protocol::json::Value(std::move(zeroed)));
  if (!canonical) {
    return false;
  }
  const auto* data = reinterpret_cast<const std::byte*>(canonical.value().data());
  const auto digest = workload::sha256(std::span(data, canonical.value().size())).hex();
  return digest == record.record_sha256.hex();
}

[[nodiscard]] auto selection_checksum_matches(const protocol::FreezeRecord& record)
    -> bool {
  if (!record.selection_record_checksum_sha256) {
    return false;
  }
  const auto* object = record.source_document.as_object();
  if (object == nullptr) {
    return false;
  }
  protocol::json::Value::Object payload;
  for (const auto key :
       {std::string_view("h3_selections"), std::string_view("training_input_artifacts"),
        std::string_view("selection_rule_version")}) {
    const auto iterator = object->find(key);
    if (iterator == object->end()) {
      return false;
    }
    payload.emplace(std::string(key), iterator->second);
  }
  const auto canonical =
      protocol::json::canonicalize(protocol::json::Value(std::move(payload)));
  if (!canonical) {
    return false;
  }
  const auto* data = reinterpret_cast<const std::byte*>(canonical.value().data());
  return workload::sha256(std::span(data, canonical.value().size())).hex() ==
         record.selection_record_checksum_sha256->hex();
}

struct UtcTimestamp final {
  std::array<unsigned int, 6> fields{};
  std::string fraction;
};

[[nodiscard]] auto parse_digits(std::string_view value, std::size_t offset,
                                std::size_t count) -> std::optional<unsigned int> {
  unsigned int result = 0U;
  if (offset + count > value.size()) {
    return std::nullopt;
  }
  for (std::size_t index = offset; index < offset + count; ++index) {
    const auto character = static_cast<unsigned char>(value[index]);
    if (std::isdigit(character) == 0) {
      return std::nullopt;
    }
    result = (result * 10U) + static_cast<unsigned int>(value[index] - '0');
  }
  return result;
}

[[nodiscard]] auto leap(unsigned int year) noexcept -> bool {
  return (year % 4U == 0U && year % 100U != 0U) || year % 400U == 0U;
}

[[nodiscard]] auto parse_utc(std::string_view value) -> std::optional<UtcTimestamp> {
  if (value.size() < 20U || value.back() != 'Z' || value[4] != '-' || value[7] != '-' ||
      value[10] != 'T' || value[13] != ':' || value[16] != ':') {
    return std::nullopt;
  }
  UtcTimestamp result;
  const std::array offsets{0U, 5U, 8U, 11U, 14U, 17U};
  const std::array widths{4U, 2U, 2U, 2U, 2U, 2U};
  for (std::size_t index = 0U; index < offsets.size(); ++index) {
    const auto field = parse_digits(value, offsets[index], widths[index]);
    if (!field) {
      return std::nullopt;
    }
    result.fields[index] = *field;
  }
  if (result.fields[1] == 0U || result.fields[1] > 12U || result.fields[3] > 23U ||
      result.fields[4] > 59U || result.fields[5] > 60U) {
    return std::nullopt;
  }
  constexpr std::array days{31U, 28U, 31U, 30U, 31U, 30U, 31U, 31U, 30U, 31U, 30U, 31U};
  auto maximum_day = days[result.fields[1] - 1U];
  if (result.fields[1] == 2U && leap(result.fields[0])) {
    maximum_day = 29U;
  }
  if (result.fields[2] == 0U || result.fields[2] > maximum_day) {
    return std::nullopt;
  }
  if (value.size() > 20U) {
    if (value[19] != '.' || value.size() == 21U) {
      return std::nullopt;
    }
    result.fraction = std::string(value.substr(20U, value.size() - 21U));
    if (result.fraction.empty() ||
        !std::all_of(result.fraction.begin(), result.fraction.end(),
                     [](char digit) { return digit >= '0' && digit <= '9'; })) {
      return std::nullopt;
    }
    while (!result.fraction.empty() && result.fraction.back() == '0') {
      result.fraction.pop_back();
    }
  }
  return result;
}

[[nodiscard]] auto timestamp_less(const UtcTimestamp& left, const UtcTimestamp& right)
    -> bool {
  if (left.fields != right.fields) {
    return left.fields < right.fields;
  }
  const auto size = std::max(left.fraction.size(), right.fraction.size());
  auto left_value = left.fraction;
  auto right_value = right.fraction;
  left_value.resize(size, '0');
  right_value.resize(size, '0');
  return left_value < right_value;
}

[[nodiscard]] auto record_reference(std::span<const protocol::FreezeRecord> records,
                                    std::size_t before,
                                    const protocol::ArtifactReference& reference)
    -> const protocol::FreezeRecord* {
  for (std::size_t index = 0U; index < before; ++index) {
    if (records[index].record_id.value() == reference.artifact_id.value() &&
        records[index].record_sha256 == reference.sha256) {
      return &records[index];
    }
  }
  return nullptr;
}

[[nodiscard]] auto reference_resolves(std::span<const protocol::FreezeRecord> records,
                                      std::size_t before,
                                      std::span<const ArtifactAccessRecord> artifacts,
                                      const protocol::ArtifactReference& reference)
    -> bool {
  return artifact_for(artifacts, reference) != nullptr ||
         record_reference(records, before, reference) != nullptr;
}

[[nodiscard]] auto same_factor(const protocol::RunManifest& run,
                               const protocol::StageACell& cell) noexcept -> bool {
  return run.package == cell.package &&
         run.requested_hardware_state == cell.requested_hardware_state &&
         run.placement == cell.placement &&
         run.working_set_class == cell.working_set_class &&
         run.load_level == cell.load_level;
}

[[nodiscard]] auto
ordered_factor_sequence(const protocol::BlockPlan& block) -> std::vector<
    std::tuple<protocol::QueuePackage, protocol::RequestedHardwareState,
               protocol::Placement, protocol::WorkingSetClass, protocol::LoadLevel>> {
  auto cells = block.cells;
  std::sort(cells.begin(), cells.end(), [](const auto& left, const auto& right) {
    return left.cell_ordinal < right.cell_ordinal;
  });
  std::vector<
      std::tuple<protocol::QueuePackage, protocol::RequestedHardwareState,
                 protocol::Placement, protocol::WorkingSetClass, protocol::LoadLevel>>
      result;
  result.reserve(cells.size());
  for (const auto& cell : cells) {
    result.emplace_back(cell.package, cell.requested_hardware_state, cell.placement,
                        cell.working_set_class, cell.load_level);
  }
  return result;
}

[[nodiscard]] auto decision_u64(const protocol::json::Value::Object& object,
                                std::string_view key) -> std::optional<std::uint64_t> {
  const auto iterator = object.find(key);
  if (iterator == object.end()) {
    return std::nullopt;
  }
  const auto* number = iterator->second.as_number();
  if (number == nullptr) {
    return std::nullopt;
  }
  if (number->kind == protocol::json::Number::Kind::unsigned_integer) {
    return std::get<std::uint64_t>(number->value);
  }
  if (number->kind == protocol::json::Number::Kind::signed_integer) {
    const auto value = std::get<std::int64_t>(number->value);
    return value >= 0 ? std::optional<std::uint64_t>(static_cast<std::uint64_t>(value))
                      : std::nullopt;
  }
  return std::nullopt;
}

[[nodiscard]] auto decision_string(const protocol::json::Value::Object& object,
                                   std::string_view key) -> std::string_view {
  const auto iterator = object.find(key);
  if (iterator == object.end()) {
    return {};
  }
  const auto* value = iterator->second.as_string();
  return value == nullptr ? std::string_view{} : std::string_view(*value);
}

[[nodiscard]] auto decision_strings(const protocol::json::Value::Object& object,
                                    std::string_view key)
    -> std::optional<std::vector<std::string_view>> {
  const auto iterator = object.find(key);
  if (iterator == object.end()) {
    return std::nullopt;
  }
  const auto* array = iterator->second.as_array();
  if (array == nullptr) {
    return std::nullopt;
  }
  std::vector<std::string_view> result;
  result.reserve(array->size());
  for (const auto& item : *array) {
    const auto* value = item.as_string();
    if (value == nullptr) {
      return std::nullopt;
    }
    result.emplace_back(*value);
  }
  return result;
}

[[nodiscard]] auto
exact_strings(const std::optional<std::vector<std::string_view>>& actual,
              std::span<const std::string_view> expected) -> bool {
  return actual && actual->size() == expected.size() &&
         std::equal(actual->begin(), actual->end(), expected.begin());
}

struct TrainingOpenDecision final {
  ProspectiveCounts counts;
  std::string delta_star_artifact_id;
  std::string bootstrap_configuration_artifact_id;
};

[[nodiscard]] auto exact_affected_blocks(const protocol::FreezeRecord& record,
                                         std::span<const protocol::BlockPlan> blocks,
                                         const std::optional<protocol::BlockRole> role)
    -> bool {
  std::set<std::string> expected;
  std::set<std::string> actual;
  for (const auto& block : blocks) {
    const bool replaced =
        std::any_of(blocks.begin(), blocks.end(), [&](const auto& candidate) {
          return candidate.replaces_block_id &&
                 *candidate.replaces_block_id == block.block_id;
        });
    if (!replaced && (!role || block.block_role == *role)) {
      expected.insert(std::string(block.block_id.value()));
    }
  }
  for (const auto& block_id : record.affected_block_ids) {
    actual.insert(std::string(block_id.value()));
  }
  return !expected.empty() && actual == expected &&
         actual.size() == record.affected_block_ids.size();
}

[[nodiscard]] auto counts_equal(const ProspectiveCounts& left,
                                const ProspectiveCounts& right) noexcept -> bool {
  return left.r_h1 == right.r_h1 && left.r_h2 == right.r_h2 && left.r12 == right.r12 &&
         left.rtrain == right.rtrain && left.rval == right.rval &&
         left.rtotal == right.rtotal && left.nruns == right.nruns;
}

[[nodiscard]] auto input_contains(const protocol::FreezeRecord& record,
                                  const protocol::ArtifactReference& reference)
    -> bool {
  return std::any_of(
      record.input_artifacts.begin(), record.input_artifacts.end(),
      [&](const auto& input) {
        return input.artifact == reference &&
               input.access_class != protocol::AccessClass::training_only &&
               input.access_class != protocol::AccessClass::validation_sealed &&
               input.access_class != protocol::AccessClass::validation_unsealed;
      });
}

[[nodiscard]] auto decode_training_open_decision(const protocol::FreezeRecord& record)
    -> protocol::Result<TrainingOpenDecision> {
  if (!record.decision_value) {
    return fail<TrainingOpenDecision>(
        protocol::ErrorCategory::missing_evidence, "$/decision_value",
        "ACCESS-TRAINING-FREEZE-EVIDENCE",
        "TRAINING_OPEN requires the complete prospective precision freeze object");
  }
  const auto* object = record.decision_value->as_object();
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
  const auto h1 = h1_contrast_ids();
  const auto h2 = h2_contrast_ids();
  if (object == nullptr || object->size() != 20U ||
      !exact_strings(decision_strings(*object, "candidate_order"), candidate_order) ||
      !exact_strings(decision_strings(*object, "h3_context_order"), context_order) ||
      !exact_strings(decision_strings(*object, "h1_contrast_ids"), h1) ||
      !exact_strings(decision_strings(*object, "h2_contrast_ids"), h2) ||
      decision_u64(*object, "h3_training_pair_count") != kH3TrainingPairCount ||
      decision_u64(*object, "h3_validation_family_count") != kH3ValidationFamilyCount ||
      decision_u64(*object, "h3_reported_comparison_count") !=
          kH3ReportedComparisonCount ||
      decision_string(*object, "tie_break_rule_id") != kH3SelectionRuleId ||
      !opaque(decision_string(*object, "delta_star_artifact_id")) ||
      !opaque(decision_string(*object, "bootstrap_configuration_artifact_id")) ||
      !opaque(decision_string(*object, "bootstrap_seed_id")) ||
      !opaque(decision_string(*object, "precision_profile_id"))) {
    return fail<TrainingOpenDecision>(
        protocol::ErrorCategory::missing_evidence, "$/decision_value",
        "ACCESS-TRAINING-FREEZE-EVIDENCE",
        "TRAINING_OPEN must freeze candidate/context order, exact families, rules, and "
        "evidence identities");
  }
  const auto schemas = decision_strings(*object, "schema_artifact_ids");
  std::set<std::string_view> schema_ids;
  if (!schemas || schemas->empty() ||
      !std::all_of(schemas->begin(), schemas->end(), [&](const auto value) {
        return opaque(value) && schema_ids.insert(value).second;
      })) {
    return fail<TrainingOpenDecision>(
        protocol::ErrorCategory::missing_evidence,
        "$/decision_value/schema_artifact_ids", "ACCESS-TRAINING-FREEZE-SCHEMAS",
        "TRAINING_OPEN requires nonempty distinct immutable schema identities");
  }
  const auto r_h1 = decision_u64(*object, "r_h1");
  const auto r_h2 = decision_u64(*object, "r_h2");
  const auto r12 = decision_u64(*object, "r12");
  const auto rtrain = decision_u64(*object, "rtrain");
  const auto rval = decision_u64(*object, "rval");
  const auto rtotal = decision_u64(*object, "rtotal");
  const auto nruns = decision_u64(*object, "nruns");
  if (!r_h1 || !r_h2 || !r12 || !rtrain || !rval || !rtotal || !nruns) {
    return fail<TrainingOpenDecision>(
        protocol::ErrorCategory::missing_evidence, "$/decision_value",
        "ACCESS-TRAINING-FREEZE-COUNTS",
        "TRAINING_OPEN requires all seven prospective count fields as exact integers");
  }
  std::set<std::string_view> input_ids;
  for (const auto& input : record.input_artifacts) {
    input_ids.insert(input.artifact.artifact_id.value());
  }
  const auto delta = decision_string(*object, "delta_star_artifact_id");
  const auto bootstrap =
      decision_string(*object, "bootstrap_configuration_artifact_id");
  if (!input_ids.contains(delta) || !input_ids.contains(bootstrap) ||
      !std::all_of(schemas->begin(), schemas->end(),
                   [&](const auto value) { return input_ids.contains(value); })) {
    return fail<TrainingOpenDecision>(
        protocol::ErrorCategory::reference_mismatch, "$/decision_value",
        "ACCESS-TRAINING-FREEZE-INPUTS",
        "every named delta, bootstrap, and schema artifact requires an exact hashed "
        "input reference");
  }
  return protocol::Result<TrainingOpenDecision>::success(
      {{*r_h1, *r_h2, *r12, *rtrain, *rval, *rtotal, *nruns},
       std::string(delta),
       std::string(bootstrap)});
}

} // namespace

auto validate_authority_policy(const AuthorityPolicy& policy,
                               std::span<const ArtifactAccessRecord> artifacts)
    -> std::vector<protocol::ValidationError> {
  std::vector<protocol::ValidationError> errors;
  constexpr std::array required{AccessPrincipalRole::freeze_authority,
                                AccessPrincipalRole::custodian,
                                AccessPrincipalRole::training_analyst,
                                AccessPrincipalRole::validation_authority,
                                AccessPrincipalRole::confirmatory_analyst,
                                AccessPrincipalRole::replacement_authority};
  std::set<AccessPrincipalRole> roles;
  for (std::size_t index = 0U; index < policy.assignments.size(); ++index) {
    const auto& assignment = policy.assignments[index];
    if (!opaque(assignment.authority_id.value()) ||
        !roles.insert(assignment.role).second) {
      add(errors, protocol::ErrorCategory::duplicate_value,
          "$/authority_policy/assignments/" + std::to_string(index),
          "ACCESS-AUTHORITY-ASSIGNMENT",
          "each operational access role requires one opaque authority identity");
    }
  }
  for (const auto role : required) {
    if (!roles.contains(role)) {
      add(errors, protocol::ErrorCategory::missing_evidence,
          "$/authority_policy/assignments", "ACCESS-AUTHORITY-COMPLETE",
          "all six imported access roles require explicit principals");
    }
  }
  if (policy.assignments.size() != required.size()) {
    add(errors, protocol::ErrorCategory::out_of_range, "$/authority_policy/assignments",
        "ACCESS-AUTHORITY-EXACT",
        "the authority registry must contain exactly the six imported access roles");
  }
  for (std::size_t left = 0U; left < policy.assignments.size(); ++left) {
    for (std::size_t right = left + 1U; right < policy.assignments.size(); ++right) {
      const auto& first = policy.assignments[left];
      const auto& second = policy.assignments[right];
      if (first.authority_id != second.authority_id) {
        continue;
      }
      const auto overlap = std::find_if(
          policy.permitted_overlaps.begin(), policy.permitted_overlaps.end(),
          [&](const RoleOverlapAuthorization& candidate) {
            const bool roles_match =
                (candidate.first == first.role && candidate.second == second.role) ||
                (candidate.first == second.role && candidate.second == first.role);
            return roles_match && candidate.authority_id == first.authority_id &&
                   artifact_for(artifacts, candidate.authorization_artifact) != nullptr;
          });
      if (overlap == policy.permitted_overlaps.end()) {
        add(errors, protocol::ErrorCategory::missing_evidence,
            "$/authority_policy/permitted_overlaps", "ACCESS-AUTHORITY-SEGREGATION",
            "one principal may hold multiple roles only with immutable authorization "
            "evidence");
      }
    }
  }
  return errors;
}

auto validate_access_ledger(std::span<const protocol::BlockPlan> blocks,
                            std::span<const protocol::FreezeRecord> records,
                            std::span<const ArtifactAccessRecord> artifacts,
                            const RoleNamespaceRegistry& namespaces,
                            const AuthorityPolicy& authorities) -> AccessLedgerResult {
  AccessLedgerResult result{protocol::AccessState::planned,
                            validate_authority_policy(authorities, artifacts)};
  const auto namespace_errors = validate_role_namespaces(namespaces);
  result.errors.insert(result.errors.end(), namespace_errors.begin(),
                       namespace_errors.end());
  std::set<std::string> block_ids;
  for (const auto& block : blocks) {
    if (!block_ids.insert(std::string(block.block_id.value())).second) {
      add(result.errors, protocol::ErrorCategory::duplicate_value, "$/blocks",
          "ACCESS-BLOCK-UNIQUE", "block identities in an access graph must be unique");
    }
  }
  std::set<std::string> record_ids;
  std::set<std::string> amendment_targets;
  std::optional<UtcTimestamp> previous_timestamp;
  const protocol::Stage4SemanticValidator local;
  for (std::size_t index = 0U; index < records.size(); ++index) {
    const auto& record = records[index];
    const auto path = "$/access_records/" + std::to_string(index);
    const auto local_errors = local.validate(protocol::ProtocolRecord{record});
    result.errors.insert(result.errors.end(), local_errors.begin(), local_errors.end());
    if (!record_ids.insert(std::string(record.record_id.value())).second) {
      add(result.errors, protocol::ErrorCategory::duplicate_value, path + "/record_id",
          "ACCESS-APPEND-ONLY-ID",
          "an append-only access ledger cannot overwrite a record identity");
    }
    if (!zero_self_hash_matches(record)) {
      add(result.errors, protocol::ErrorCategory::invalid_hash, path + "/record_sha256",
          "ACCESS-ZEROSELF-HASH",
          "access record hash must bind its complete canonical source document");
    }
    const auto timestamp = parse_utc(record.created_at_utc);
    if (!timestamp ||
        (previous_timestamp && timestamp_less(*timestamp, *previous_timestamp))) {
      add(result.errors, protocol::ErrorCategory::cross_field, path + "/created_at_utc",
          "ACCESS-CHRONOLOGY",
          "access ledger timestamps must be normalized UTC and nondecreasing");
    }
    if (timestamp) {
      previous_timestamp = timestamp;
    }
    for (const auto& input : record.input_artifacts) {
      if (!reference_resolves(records, index, artifacts, input.artifact)) {
        add(result.errors, protocol::ErrorCategory::reference_mismatch,
            path + "/input_artifacts", "ACCESS-INPUT-RESOLUTION",
            "every access input must resolve to immutable prior or external evidence");
      }
    }
    if (const auto principal = principal_for(record.record_kind)) {
      const auto* assignment = assignment_for(authorities, *principal);
      const auto expected_role = protocol_role_for(*principal);
      if (assignment == nullptr ||
          assignment->authority_id != record.authority.authority_id || !expected_role ||
          record.authority.role != *expected_role) {
        add(result.errors, protocol::ErrorCategory::reference_mismatch,
            path + "/authority", "ACCESS-AUTHORITY-BINDING",
            "record authority must match the frozen operational role assignment");
      }
    }
    for (const auto& block_id : record.affected_block_ids) {
      const auto* block = id_in(blocks, block_id);
      if (block == nullptr || !role_allowed_for_record(record, block->block_role)) {
        add(result.errors, protocol::ErrorCategory::reference_mismatch,
            path + "/affected_block_ids", "ACCESS-AFFECTED-BLOCK-ROLE",
            "affected block must exist and have a role compatible with this "
            "transition");
      }
    }

    if (record.record_kind == protocol::RecordKind::replacement_authorization) {
      // PLANNED -> PLANNED is the state of the new replacement plan, not the
      // global H3 access ledger; replacement authorization never advances it.
      continue;
    }
    if (record.access_state_before != result.final_state) {
      add(result.errors, protocol::ErrorCategory::cross_field,
          path + "/access_state_before", "ACCESS-PREDECESSOR-STATE",
          "access transition must begin at the exact preceding ledger state");
    }
    bool allowed = false;
    if (record.record_kind == protocol::RecordKind::protocol_freeze) {
      allowed =
          (record.access_state_before == protocol::AccessState::planned &&
           record.access_state_after == protocol::AccessState::collected_sealed) ||
          (record.access_state_before == protocol::AccessState::collected_sealed &&
           record.access_state_after == protocol::AccessState::training_open) ||
          (record.access_state_before == protocol::AccessState::h1h2_released &&
           record.access_state_after == protocol::AccessState::archived);
      if (!record.outcome_access_prohibited ||
          record.authority.role != protocol::AuthorityRole::freeze_authority) {
        allowed = false;
      }
      if (record.access_state_after == protocol::AccessState::collected_sealed &&
          !exact_affected_blocks(record, blocks, std::nullopt)) {
        add(result.errors, protocol::ErrorCategory::cross_field,
            path + "/affected_block_ids", "ACCESS-COLLECTION-EXACT-BLOCKS",
            "collection sealing must name the complete frozen common block pool");
        allowed = false;
      }
      if (record.access_state_after == protocol::AccessState::training_open) {
        if (!exact_affected_blocks(record, blocks, protocol::BlockRole::h3_train)) {
          add(result.errors, protocol::ErrorCategory::cross_field,
              path + "/affected_block_ids", "ACCESS-TRAINING-EXACT-BLOCKS",
              "opening training must name exactly every H3_TRAIN block");
          allowed = false;
        }
        const auto decision = decode_training_open_decision(record);
        if (!decision) {
          result.errors.insert(result.errors.end(), decision.errors().begin(),
                               decision.errors().end());
          allowed = false;
        }
      }
      if (record.access_state_after == protocol::AccessState::archived &&
          !exact_affected_blocks(record, blocks, std::nullopt)) {
        add(result.errors, protocol::ErrorCategory::cross_field,
            path + "/affected_block_ids", "ACCESS-ARCHIVE-EXACT-BLOCKS",
            "archival must name the complete frozen common block pool");
        allowed = false;
      }
    } else if (record.record_kind == protocol::RecordKind::selection_freeze) {
      allowed = record.access_state_before == protocol::AccessState::training_open &&
                record.access_state_after == protocol::AccessState::selection_frozen;
      if (!exact_affected_blocks(record, blocks, protocol::BlockRole::h3_train)) {
        add(result.errors, protocol::ErrorCategory::cross_field,
            path + "/affected_block_ids", "ACCESS-SELECTION-EXACT-BLOCKS",
            "selection freeze must name exactly every H3_TRAIN block");
        allowed = false;
      }
      if (!record.selection_rule_version ||
          *record.selection_rule_version != kH3SelectionRuleId) {
        add(result.errors, protocol::ErrorCategory::cross_field,
            path + "/selection_rule_version", "ACCESS-H3-SELECTION-RULE",
            "selection must use arithmetic mean log(p99.9), minimum candidate, and the "
            "frozen candidate-order tie break");
        allowed = false;
      }
      if (!selection_checksum_matches(record)) {
        add(result.errors, protocol::ErrorCategory::invalid_hash,
            path + "/selection_record_checksum_sha256", "ACCESS-SELECTION-PAYLOAD-HASH",
            "selection checksum must bind contexts, candidates, rule, and every "
            "training artifact reference");
        allowed = false;
      }
      const auto contexts = h3_contexts();
      if (record.h3_selections.size() != contexts.size() ||
          !std::all_of(contexts.begin(), contexts.end(), [&](auto context) {
            const auto found = record.h3_selections.find(context);
            return found != record.h3_selections.end() &&
                   candidate_valid(found->second);
          })) {
        add(result.errors, protocol::ErrorCategory::cross_field,
            path + "/h3_selections", "ACCESS-H3-SIX-CONTEXTS",
            "selection must freeze one registered candidate in each stable context");
      }
      for (const auto& training : record.training_input_artifacts) {
        const auto* artifact = artifact_for(artifacts, training);
        const bool exact_input = std::any_of(
            record.input_artifacts.begin(), record.input_artifacts.end(),
            [&](const auto& input) {
              return input.artifact == training &&
                     input.access_class == protocol::AccessClass::training_only;
            });
        if (artifact == nullptr ||
            artifact->access_class != protocol::AccessClass::training_only ||
            !artifact->block_role ||
            *artifact->block_role != protocol::BlockRole::h3_train || !exact_input) {
          add(result.errors, protocol::ErrorCategory::reference_mismatch,
              path + "/training_input_artifacts", "ACCESS-TRAINING-ONLY",
              "selection can consume only named H3 training artifacts");
        }
      }
      const auto training_inputs = static_cast<std::size_t>(std::count_if(
          record.input_artifacts.begin(), record.input_artifacts.end(),
          [](const auto& input) {
            return input.access_class == protocol::AccessClass::training_only;
          }));
      if (training_inputs != record.training_input_artifacts.size()) {
        add(result.errors, protocol::ErrorCategory::reference_mismatch,
            path + "/input_artifacts", "ACCESS-TRAINING-INPUTS-EXACT",
            "selection input hashes must exactly equal the named H3 training "
            "artifacts");
        allowed = false;
      }
    } else if (record.record_kind == protocol::RecordKind::validation_unseal) {
      allowed = record.access_state_before == protocol::AccessState::selection_frozen &&
                record.access_state_after == protocol::AccessState::validation_unsealed;
      if (!exact_affected_blocks(record, blocks, protocol::BlockRole::h3_validation)) {
        add(result.errors, protocol::ErrorCategory::cross_field,
            path + "/affected_block_ids", "ACCESS-UNSEAL-EXACT-BLOCKS",
            "validation unsealing must name exactly every H3_VALIDATION block");
        allowed = false;
      }
      const auto validation_binding =
          std::find_if(namespaces.role_bindings.begin(), namespaces.role_bindings.end(),
                       [](const auto& binding) {
                         return binding.role == protocol::BlockRole::h3_validation;
                       });
      if (!record.validation_namespace_id ||
          validation_binding == namespaces.role_bindings.end() ||
          *record.validation_namespace_id != validation_binding->namespace_id ||
          !record.validation_artifact_ref) {
        add(result.errors, protocol::ErrorCategory::reference_mismatch,
            path + "/validation_namespace_id", "ACCESS-VALIDATION-NAMESPACE",
            "unseal must name the frozen validation role namespace and artifact");
      } else {
        const auto* artifact = artifact_for(artifacts, *record.validation_artifact_ref);
        if (artifact == nullptr ||
            artifact->access_class != protocol::AccessClass::validation_sealed ||
            !artifact->namespace_id ||
            *artifact->namespace_id != *record.validation_namespace_id) {
          add(result.errors, protocol::ErrorCategory::reference_mismatch,
              path + "/validation_artifact_ref", "ACCESS-VALIDATION-SEALED",
              "validation evidence must resolve as sealed in the frozen namespace");
        }
      }
      const auto* validation_authority =
          assignment_for(authorities, AccessPrincipalRole::validation_authority);
      const bool approved =
          validation_authority != nullptr &&
          std::any_of(record.input_artifacts.begin(), record.input_artifacts.end(),
                      [&](const auto& input) {
                        const auto* artifact = artifact_for(artifacts, input.artifact);
                        return artifact != nullptr && artifact->issuing_role &&
                               artifact->issuer_id &&
                               *artifact->issuing_role ==
                                   AccessPrincipalRole::validation_authority &&
                               *artifact->issuer_id ==
                                   validation_authority->authority_id;
                      });
      if (!approved) {
        add(result.errors, protocol::ErrorCategory::missing_evidence,
            path + "/input_artifacts", "ACCESS-VALIDATION-AUTHORITY",
            "validation authority approval must precede custodian unsealing");
      }
      if (!record.selection_record_ref ||
          record_reference(records, index, *record.selection_record_ref) == nullptr) {
        add(result.errors, protocol::ErrorCategory::reference_mismatch,
            path + "/selection_record_ref", "ACCESS-SELECTION-PREDECESSOR",
            "validation unseal must hash-link the earlier selection freeze");
      }
    } else if (record.record_kind == protocol::RecordKind::h3_evaluated) {
      allowed =
          record.access_state_before == protocol::AccessState::validation_unsealed &&
          record.access_state_after == protocol::AccessState::h3_evaluated;
      if (!exact_affected_blocks(record, blocks, protocol::BlockRole::h3_validation)) {
        add(result.errors, protocol::ErrorCategory::cross_field,
            path + "/affected_block_ids", "ACCESS-H3-EVALUATION-EXACT-BLOCKS",
            "H3 evaluation must name exactly every H3_VALIDATION block");
        allowed = false;
      }
      if (!record.selection_record_ref || !record.validation_unseal_record_ref ||
          record_reference(records, index, *record.selection_record_ref) == nullptr ||
          record_reference(records, index, *record.validation_unseal_record_ref) ==
              nullptr ||
          !record.h3_evaluation_artifact_ref ||
          artifact_for(artifacts, *record.h3_evaluation_artifact_ref) == nullptr) {
        add(result.errors, protocol::ErrorCategory::reference_mismatch, path,
            "ACCESS-H3-EVALUATION-LINEAGE",
            "H3 evaluation must link selection, unseal, validation, and evaluation "
            "hashes");
      }
    } else if (record.record_kind == protocol::RecordKind::h1h2_released) {
      allowed = record.access_state_before == protocol::AccessState::h3_evaluated &&
                record.access_state_after == protocol::AccessState::h1h2_released;
      if (!exact_affected_blocks(record, blocks, std::nullopt)) {
        add(result.errors, protocol::ErrorCategory::cross_field,
            path + "/affected_block_ids", "ACCESS-H1H2-EXACT-BLOCKS",
            "H1/H2 release must name the complete common block pool");
        allowed = false;
      }
      if (!record.h3_evaluation_artifact_ref || !record.h3_access_record_ref ||
          artifact_for(artifacts, *record.h3_evaluation_artifact_ref) == nullptr ||
          artifact_for(artifacts, *record.h3_access_record_ref) == nullptr) {
        add(result.errors, protocol::ErrorCategory::reference_mismatch, path,
            "ACCESS-H1H2-SEALED-H3",
            "H1/H2 release requires immutable H3 evaluation and access-audit evidence");
      }
    } else if (record.record_kind == protocol::RecordKind::amendment) {
      allowed = record.access_state_before == record.access_state_after &&
                record.outcome_access_prohibited;
      if (!record.supersedes_id ||
          !amendment_targets.insert(std::string(record.supersedes_id->value()))
               .second) {
        add(result.errors, protocol::ErrorCategory::duplicate_value,
            path + "/supersedes_id", "ACCESS-AMENDMENT-LINEAGE",
            "amendments require one earlier unbranched supersession target");
      } else {
        const auto target = std::find_if(
            records.begin(), records.begin() + static_cast<std::ptrdiff_t>(index),
            [&](const auto& previous) {
              return previous.record_id == *record.supersedes_id;
            });
        const bool prior_hash_named =
            target != records.begin() + static_cast<std::ptrdiff_t>(index) &&
            std::any_of(
                record.prior_authoritative_hashes.begin(),
                record.prior_authoritative_hashes.end(), [&](const auto& reference) {
                  return reference.artifact_id.value() == target->record_id.value() &&
                         reference.sha256 == target->record_sha256;
                });
        if (!prior_hash_named) {
          add(result.errors, protocol::ErrorCategory::reference_mismatch,
              path + "/prior_authoritative_hashes", "ACCESS-AMENDMENT-PREDECESSOR",
              "amendment must name and hash its earlier superseded record");
        }
      }
      if (std::any_of(record.input_artifacts.begin(), record.input_artifacts.end(),
                      [](const auto& input) {
                        return input.access_class ==
                                   protocol::AccessClass::training_only ||
                               input.access_class ==
                                   protocol::AccessClass::validation_unsealed;
                      })) {
        add(result.errors, protocol::ErrorCategory::cross_field,
            path + "/input_artifacts", "ACCESS-AMENDMENT-NO-OUTCOMES",
            "an amendment cannot be selected from training or validation outcomes");
      }
    }
    if (!allowed) {
      add(result.errors, protocol::ErrorCategory::cross_field, path,
          "ACCESS-ILLEGAL-TRANSITION",
          "record kind does not authorize this access-state transition");
    } else {
      result.final_state = record.access_state_after;
    }
  }
  return result;
}

auto authorize_outcome_access(const AccessLedgerResult& ledger,
                              std::span<const protocol::BlockPlan> blocks,
                              const AuthorityPolicy& authorities,
                              const AccessRequest& request) -> protocol::Result<bool> {
  if (!ledger.errors.empty()) {
    return fail<bool>(
        protocol::ErrorCategory::missing_evidence, "$/access_ledger",
        "ACCESS-LEDGER-NOT-VALID",
        "outcome access is denied while the ledger has validation errors");
  }
  const auto* assignment = assignment_for(authorities, request.actor_role);
  const auto* block = id_in(blocks, request.block_id);
  const bool active =
      block != nullptr &&
      std::none_of(blocks.begin(), blocks.end(), [&](const auto& item) {
        return item.replaces_block_id && *item.replaces_block_id == request.block_id;
      });
  if (assignment == nullptr || assignment->authority_id != request.actor_id ||
      block == nullptr || !active) {
    return fail<bool>(
        protocol::ErrorCategory::reference_mismatch, "$/access_request",
        "ACCESS-REQUEST-IDENTITY",
        "actor assignment and active block identity must be frozen and resolvable");
  }
  bool allowed = false;
  if (request.domain == OutcomeDomain::h3_training) {
    allowed = request.actor_role == AccessPrincipalRole::training_analyst &&
              block->block_role == protocol::BlockRole::h3_train &&
              ledger.final_state >= protocol::AccessState::training_open;
  } else if (request.domain == OutcomeDomain::h3_validation) {
    allowed = request.actor_role == AccessPrincipalRole::confirmatory_analyst &&
              block->block_role == protocol::BlockRole::h3_validation &&
              ledger.final_state >= protocol::AccessState::validation_unsealed;
  } else if (request.domain == OutcomeDomain::h1h2) {
    allowed = request.actor_role == AccessPrincipalRole::confirmatory_analyst &&
              ledger.final_state >= protocol::AccessState::h1h2_released;
  }
  if (!allowed) {
    return fail<bool>(
        protocol::ErrorCategory::missing_evidence, "$/access_request",
        "ACCESS-OUTCOME-DENIED",
        "role, block role, or access chronology does not permit this outcome access");
  }
  return protocol::Result<bool>::success(true);
}

auto decide_complete_block_replacement(
    const ReplacementRequest& request,
    std::span<const protocol::BlockPlan> existing_blocks,
    const ReplacementBudget& budget, const RoleNamespaceRegistry& namespaces)
    -> protocol::Result<ReplacementDecision> {
  if (request.replaced_block.platform_id != budget.platform_id ||
      id_in(existing_blocks, request.replaced_block.block_id) == nullptr ||
      !opaque(budget.budget_artifact.artifact_id.value())) {
    return fail<ReplacementDecision>(
        protocol::ErrorCategory::reference_mismatch, "$/replacement",
        "REPLACEMENT-PLATFORM-BUDGET",
        "target block and frozen budget must share an explicit platform");
  }
  const auto replacement_count = static_cast<std::uint64_t>(std::count_if(
      existing_blocks.begin(), existing_blocks.end(),
      [](const auto& block) { return block.replaces_block_id.has_value(); }));
  if (replacement_count >= budget.maximum_replacement_blocks) {
    return protocol::Result<ReplacementDecision>::success(
        {ReplacementDecisionState::study_unresolved,
         std::nullopt,
         {"R_replacement_max is exhausted; collection must stop unresolved"}});
  }
  if (std::any_of(existing_blocks.begin(), existing_blocks.end(),
                  [&](const auto& block) {
                    return block.replaces_block_id &&
                           *block.replaces_block_id == request.replaced_block.block_id;
                  })) {
    return fail<ReplacementDecision>(
        protocol::ErrorCategory::duplicate_value, "$/replacement/replaces_block_id",
        "REPLACEMENT-NO-BRANCH",
        "an incomplete block may have only one direct replacement");
  }
  const auto& run = request.invalid_run;
  const auto& failure = request.failure;
  const bool run_is_required = std::any_of(
      request.replaced_block.cells.begin(), request.replaced_block.cells.end(),
      [&](const auto& cell) { return same_factor(run, cell); });
  const bool failure_named =
      std::find(run.failure_record_ids.begin(), run.failure_record_ids.end(),
                failure.failure_record_id) != run.failure_record_ids.end();
  if (run.stage != protocol::Stage::stage_a ||
      run.block_id != request.replaced_block.block_id ||
      run.block_role != request.replaced_block.block_role ||
      run.validity != protocol::RunValidity::invalid ||
      run.block_completeness != protocol::BlockCompleteness::incomplete ||
      !run_is_required || !failure_named || !failure.run_id ||
      *failure.run_id != run.run_id || !failure.block_id ||
      *failure.block_id != request.replaced_block.block_id ||
      !failure.invalidates_run ||
      failure.block_consequence !=
          protocol::BlockConsequence::original_block_incomplete) {
    return fail<ReplacementDecision>(protocol::ErrorCategory::missing_evidence,
                                     "$/replacement/failure",
                                     "REPLACEMENT-INVALID-REQUIRED-RUN",
                                     "replacement requires a retained invalid required "
                                     "run and matching invalidating failure record");
  }
  const auto& authorization = request.authorization;
  const bool budget_hash_bound = std::any_of(
      authorization.input_artifacts.begin(), authorization.input_artifacts.end(),
      [&](const auto& input_artifact) {
        return input_artifact.artifact == budget.budget_artifact &&
               (input_artifact.access_class == protocol::AccessClass::public_protocol ||
                input_artifact.access_class ==
                    protocol::AccessClass::platform_evidence ||
                input_artifact.access_class == protocol::AccessClass::treatment_blind);
      });
  const auto local_errors = protocol::Stage4SemanticValidator{}.validate(
      protocol::ProtocolRecord{authorization});
  if (!local_errors.empty() || !zero_self_hash_matches(authorization) ||
      authorization.record_kind != protocol::RecordKind::replacement_authorization ||
      authorization.affected_block_ids.size() != 1U ||
      authorization.affected_block_ids.front() != request.replaced_block.block_id ||
      !authorization.replacement ||
      authorization.replacement->original_block_id != request.replaced_block.block_id ||
      authorization.replacement->failure_record_id != failure.failure_record_id ||
      authorization.replacement->replacement_budget_record_id.value() !=
          budget.budget_artifact.artifact_id.value() ||
      !budget_hash_bound) {
    return fail<ReplacementDecision>(protocol::ErrorCategory::reference_mismatch,
                                     "$/replacement/authorization",
                                     "REPLACEMENT-AUTHORIZATION-LINEAGE",
                                     "authorization must name the exact block, invalid "
                                     "failure, and frozen budget hash");
  }
  const auto& authorized = *authorization.replacement;
  if (failure.resolution_status != protocol::ResolutionStatus::replacement_authorized ||
      !failure.replacement_authorization_id ||
      *failure.replacement_authorization_id != authorization.record_id ||
      !failure.replacement_block_id ||
      *failure.replacement_block_id != authorized.replacement_block_id) {
    return fail<ReplacementDecision>(
        protocol::ErrorCategory::reference_mismatch,
        "$/replacement/failure/resolution_status", "REPLACEMENT-FAILURE-AUTHORIZATION",
        "failure resolution must link the exact authorization and replacement block");
  }
  auto input = request.replacement_input;
  const auto generated_id =
      make_block_id(input.platform_id, input.build_id, input.role, input.block_ordinal);
  if (!generated_id || generated_id.value() != authorized.replacement_block_id ||
      input.platform_id != request.replaced_block.platform_id ||
      input.build_id != request.replaced_block.build_id ||
      input.block_ordinal != authorized.replacement_block_ordinal ||
      input.role != authorized.block_role ||
      input.seeds.block_subspace_id != authorized.replacement_seed_subspace_id ||
      !input.replacement ||
      input.replacement->replacement_authorization_id != authorization.record_id ||
      input.replacement->replaced_block_id != request.replaced_block.block_id ||
      input.replacement->replaced_block_ordinal !=
          request.replaced_block.block_ordinal ||
      input.replacement->replaced_block_role != request.replaced_block.block_role ||
      input.replacement->replaced_seed_subspace_id !=
          request.replaced_block.seed_subspace_id) {
    return fail<ReplacementDecision>(protocol::ErrorCategory::reference_mismatch,
                                     "$/replacement/new_plan",
                                     "REPLACEMENT-NEW-BLOCK-BINDING",
                                     "new identity, ordinal, role, seed subspace, and "
                                     "authorization must match exactly");
  }
  if (std::any_of(existing_blocks.begin(), existing_blocks.end(),
                  [&](const auto& block) {
                    return block.block_id == generated_id.value() ||
                           block.block_ordinal == input.block_ordinal ||
                           block.seed_subspace_id == input.seeds.block_subspace_id;
                  })) {
    return fail<ReplacementDecision>(
        protocol::ErrorCategory::duplicate_value, "$/replacement/new_plan",
        "REPLACEMENT-NEW-IDENTITY",
        "replacement ID, ordinal, and seed subspace must all be new");
  }
  const auto generated = generate_block_plan(input, namespaces);
  if (!generated) {
    return protocol::Result<ReplacementDecision>::failure(generated.errors());
  }
  if (generated.value().plan.whole_plot_order ==
          request.replaced_block.whole_plot_order &&
      ordered_factor_sequence(generated.value().plan) ==
          ordered_factor_sequence(request.replaced_block)) {
    return fail<ReplacementDecision>(
        protocol::ErrorCategory::cross_field, "$/replacement/new_plan/cells",
        "REPLACEMENT-NEW-RANDOM-ORDER",
        "replacement must realize a new randomized whole/cell order");
  }
  return protocol::Result<ReplacementDecision>::success(
      {ReplacementDecisionState::authorized, generated.value(), {}});
}

auto Stage14CrossRecordSemanticValidator::validate(
    const protocol::SemanticRecordSet& record_set) const
    -> std::vector<protocol::ValidationError> {
  std::vector<protocol::ValidationError> errors;
  std::vector<protocol::BlockPlan> blocks;
  std::vector<protocol::FreezeRecord> freezes;
  std::vector<protocol::FailureRecord> failures;
  std::vector<protocol::RunManifest> manifests;
  const protocol::Stage4SemanticValidator local;
  for (const auto& record : record_set.records) {
    const auto local_errors = local.validate(record);
    errors.insert(errors.end(), local_errors.begin(), local_errors.end());
    if (const auto* block = std::get_if<protocol::BlockPlan>(&record)) {
      blocks.push_back(*block);
    } else if (const auto* freeze = std::get_if<protocol::FreezeRecord>(&record)) {
      freezes.push_back(*freeze);
    } else if (const auto* failure = std::get_if<protocol::FailureRecord>(&record)) {
      failures.push_back(*failure);
    } else if (const auto* manifest = std::get_if<protocol::RunManifest>(&record)) {
      manifests.push_back(*manifest);
    }
  }
  std::vector<BlockSeedCatalog> active_catalogs;
  std::vector<protocol::BlockPlan> active_blocks;
  std::set<std::string> replaced;
  std::map<std::string, std::size_t> replacement_children;
  for (const auto& block : blocks) {
    if (block.replaces_block_id) {
      replaced.insert(std::string(block.replaces_block_id->value()));
      const auto child_count =
          ++replacement_children[std::string(block.replaces_block_id->value())];
      if (child_count > 1U) {
        add(errors, protocol::ErrorCategory::duplicate_value,
            "$/blocks/replaces_block_id", "REPLACEMENT-NO-BRANCH",
            "an incomplete block may have only one direct replacement");
      }
    }
  }
  std::set<std::string> all_seed_ids;
  for (const auto& block : blocks) {
    const auto catalog = std::find_if(
        seed_catalogs_.begin(), seed_catalogs_.end(), [&](const auto& candidate) {
          return candidate.block_subspace_id == block.seed_subspace_id;
        });
    if (catalog == seed_catalogs_.end()) {
      add(errors, protocol::ErrorCategory::missing_evidence,
          "$/blocks/seed_subspace_id", "BLK-SEED-CATALOG-MISSING",
          "every block requires its immutable role-compatible seed catalog");
      continue;
    }
    const auto block_errors = validate_block_plan(block, *catalog, namespaces_);
    errors.insert(errors.end(), block_errors.begin(), block_errors.end());
    for (const auto* collection : {&catalog->arrival_seed_ids, &catalog->node_seed_ids,
                                   &catalog->event_seed_ids}) {
      for (const auto& seed : *collection) {
        if (!all_seed_ids.insert(std::string(seed.value())).second) {
          add(errors, protocol::ErrorCategory::duplicate_value, "$/seed_catalogs",
              "BLK-POOL-SEED-NO-REUSE",
              "original and replacement block seed subspaces cannot overlap");
        }
      }
    }
    if (!replaced.contains(std::string(block.block_id.value()))) {
      active_blocks.push_back(block);
      active_catalogs.push_back(*catalog);
    }
  }
  if (precision_ && precision_->state == PrecisionState::resolved &&
      precision_->role_counts) {
    const auto pool_errors = validate_block_pool(
        active_blocks, active_catalogs, namespaces_, precision_->role_counts->h3_train,
        precision_->role_counts->h3_validation,
        precision_->role_counts->h1h2_supplemental);
    errors.insert(errors.end(), pool_errors.begin(), pool_errors.end());
  } else {
    add(errors, protocol::ErrorCategory::missing_evidence, "$/precision",
        "BLK-POOL-PRECISION-UNRESOLVED",
        "final common block-pool completeness requires resolved prospective counts");
  }
  const auto ledger =
      validate_access_ledger(blocks, freezes, artifacts_, namespaces_, authorities_);
  errors.insert(errors.end(), ledger.errors.begin(), ledger.errors.end());

  std::vector<const protocol::FreezeRecord*> training_open_records;
  for (const auto& freeze : freezes) {
    if (freeze.record_kind == protocol::RecordKind::protocol_freeze &&
        freeze.access_state_after == protocol::AccessState::training_open) {
      training_open_records.push_back(&freeze);
    }
  }
  if (training_open_records.size() != 1U) {
    add(errors, protocol::ErrorCategory::missing_evidence, "$/access_records",
        "ACCESS-TRAINING-FREEZE-UNIQUE",
        "the common block pool requires exactly one immutable TRAINING_OPEN freeze");
  } else {
    const auto& training_open = *training_open_records.front();
    const auto decision = decode_training_open_decision(training_open);
    if (decision && precision_ && precision_->counts &&
        !counts_equal(decision.value().counts, *precision_->counts)) {
      add(errors, protocol::ErrorCategory::reference_mismatch,
          "$/access_records/decision_value", "ACCESS-PRECISION-FREEZE-COUNTS",
          "TRAINING_OPEN counts must equal the resolved prospective precision plan");
    }
    if (decision && precision_ && precision_->evidence) {
      const auto& evidence = *precision_->evidence;
      const std::array immutable_evidence{
          evidence.delta_star,         evidence.bootstrap_configuration,
          evidence.h1_sizing,          evidence.h2_sizing,
          evidence.h3_training_sizing, evidence.h3_validation_sizing};
      const bool identities_match =
          decision.value().delta_star_artifact_id ==
              evidence.delta_star.artifact_id.value() &&
          decision.value().bootstrap_configuration_artifact_id ==
              evidence.bootstrap_configuration.artifact_id.value();
      const bool hashes_bound =
          std::all_of(immutable_evidence.begin(), immutable_evidence.end(),
                      [&](const auto& reference) {
                        return input_contains(training_open, reference);
                      });
      const bool sources_bound =
          std::all_of(evidence.input_artifacts.begin(), evidence.input_artifacts.end(),
                      [&](const auto& input) {
                        return input_contains(training_open, input.artifact);
                      });
      if (!identities_match || !hashes_bound || !sources_bound) {
        add(errors, protocol::ErrorCategory::reference_mismatch,
            "$/access_records/input_artifacts", "ACCESS-PRECISION-FREEZE-INPUTS",
            "TRAINING_OPEN must hash-bind the exact delta, bootstrap, separate family "
            "sizing, and prospective source evidence");
      }
    }
  }

  if (replacement_budget_) {
    if (artifact_for(artifacts_, replacement_budget_->budget_artifact) == nullptr) {
      add(errors, protocol::ErrorCategory::reference_mismatch,
          "$/replacement_budget/budget_artifact", "REPLACEMENT-BUDGET-EVIDENCE",
          "the frozen replacement budget must resolve by exact artifact ID and "
          "SHA-256");
    }
    const auto replacement_count = static_cast<std::uint64_t>(
        std::count_if(blocks.begin(), blocks.end(), [](const auto& block) {
          return block.replaces_block_id.has_value();
        }));
    if (replacement_count > replacement_budget_->maximum_replacement_blocks) {
      add(errors, protocol::ErrorCategory::out_of_range, "$/replacement_budget",
          "REPLACEMENT-BUDGET-EXCEEDED",
          "replacement count exceeds R_replacement_max and study must remain "
          "unresolved");
    }
  } else if (std::any_of(blocks.begin(), blocks.end(), [](const auto& block) {
               return block.replaces_block_id.has_value();
             })) {
    add(errors, protocol::ErrorCategory::missing_evidence, "$/replacement_budget",
        "REPLACEMENT-BUDGET-MISSING",
        "replacement blocks require a frozen platform budget");
  }
  for (const auto& block : blocks) {
    if (!block.replaces_block_id || !block.replacement_authorization_id) {
      continue;
    }
    const auto original =
        std::find_if(blocks.begin(), blocks.end(), [&](const auto& candidate) {
          return candidate.block_id == *block.replaces_block_id;
        });
    if (original == blocks.end() || !block.replacement_lineage ||
        block.platform_id != original->platform_id ||
        block.build_id != original->build_id ||
        block.block_role != original->block_role ||
        block.block_ordinal == original->block_ordinal ||
        block.seed_subspace_id == original->seed_subspace_id ||
        block.replacement_lineage->replaced_block_ordinal != original->block_ordinal ||
        block.replacement_lineage->replaced_block_role != original->block_role ||
        block.replacement_lineage->replaced_seed_subspace_id !=
            original->seed_subspace_id ||
        (block.whole_plot_order == original->whole_plot_order &&
         ordered_factor_sequence(block) == ordered_factor_sequence(*original))) {
      add(errors, protocol::ErrorCategory::reference_mismatch, "$/replacement_lineage",
          "REPLACEMENT-ORIGINAL-RESOLUTION",
          "replacement lineage must resolve the retained original with the same "
          "platform/build/role and a new ordinal, seed subspace, and randomized order");
      continue;
    }
    const auto authorization =
        std::find_if(freezes.begin(), freezes.end(), [&](const auto& record) {
          return record.record_id == *block.replacement_authorization_id;
        });
    const bool budget_hash_bound =
        authorization != freezes.end() && replacement_budget_ &&
        input_contains(*authorization, replacement_budget_->budget_artifact);
    if (authorization == freezes.end() || !authorization->replacement ||
        authorization->replacement->replacement_block_id != block.block_id ||
        authorization->replacement->original_block_id != *block.replaces_block_id ||
        authorization->replacement->replacement_block_ordinal != block.block_ordinal ||
        authorization->replacement->replacement_seed_subspace_id !=
            block.seed_subspace_id ||
        authorization->replacement->block_role != block.block_role ||
        !replacement_budget_ ||
        authorization->replacement->replacement_budget_record_id.value() !=
            replacement_budget_->budget_artifact.artifact_id.value() ||
        !budget_hash_bound) {
      add(errors, protocol::ErrorCategory::reference_mismatch,
          "$/replacement_authorization_id", "REPLACEMENT-RECORD-RESOLUTION",
          "replacement plan must resolve an authorization naming both block "
          "identities");
      continue;
    }
    const auto failure =
        std::find_if(failures.begin(), failures.end(), [&](const auto& record) {
          return record.failure_record_id ==
                 authorization->replacement->failure_record_id;
        });
    const auto manifest =
        failure == failures.end() || !failure->run_id
            ? manifests.end()
            : std::find_if(manifests.begin(), manifests.end(), [&](const auto& run) {
                return run.run_id == *failure->run_id &&
                       run.validity == protocol::RunValidity::invalid;
              });
    if (failure == failures.end() || manifest == manifests.end() ||
        !failure->invalidates_run || !failure->block_id ||
        *failure->block_id != *block.replaces_block_id ||
        failure->resolution_status !=
            protocol::ResolutionStatus::replacement_authorized ||
        !failure->replacement_authorization_id ||
        *failure->replacement_authorization_id != authorization->record_id ||
        !failure->replacement_block_id ||
        *failure->replacement_block_id != block.block_id) {
      add(errors, protocol::ErrorCategory::missing_evidence,
          "$/replacement/failure_record_id", "REPLACEMENT-INVALID-RUN-RESOLUTION",
          "replacement authorization must resolve a retained invalid required run and "
          "failure");
    }
  }
  return errors;
}

} // namespace cpu_prefetch::orchestration
