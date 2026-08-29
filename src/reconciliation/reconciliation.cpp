#include "cpu_prefetch/reconciliation/reconciliation.hpp"

#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/storage/raw_observations.hpp"
#include "cpu_prefetch/timing/intervals.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <span>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
#include <variant>
#include <vector>

namespace cpu_prefetch::reconciliation {
namespace {

using protocol::ErrorCategory;
using protocol::ValidationError;
using JsonArray = protocol::json::Value::Array;
using JsonObject = protocol::json::Value::Object;

template <typename T>
auto failure(ErrorCategory category, std::string path, std::string rule,
             std::string message) -> protocol::Result<T> {
  return protocol::Result<T>::failure(
      {category, std::move(path), std::move(rule), std::move(message)});
}

auto uint_value(std::uint64_t value) -> protocol::json::Value {
  return protocol::json::Value(protocol::json::Number{
      protocol::json::Number::Kind::unsigned_integer, std::to_string(value), value});
}

auto string_value(std::string_view value) -> protocol::json::Value {
  return protocol::json::Value(std::string(value));
}

auto artifact_value(const protocol::ArtifactReference& reference)
    -> protocol::json::Value {
  JsonObject object;
  object.emplace("artifact_id", string_value(reference.artifact_id.value()));
  object.emplace("sha256", string_value(reference.sha256.hex()));
  return protocol::json::Value(std::move(object));
}

auto n_eff_at_least_threshold(const protocol::json::Number& number) -> bool {
  if (number.kind == protocol::json::Number::Kind::signed_integer) {
    return std::get<std::int64_t>(number.value) >= 200000;
  }
  if (number.kind == protocol::json::Number::Kind::unsigned_integer) {
    return std::get<std::uint64_t>(number.value) >= 200000U;
  }
  return std::get<double>(number.value) >= 200000.0;
}

auto complete_count_identities(const protocol::RunCounts& counts) -> bool {
  if (!counts.offered || !counts.attempted || !counts.accepted || !counts.full ||
      !counts.consumed || !counts.final_occupancy || !counts.raw_sample_count ||
      !counts.n_eff_p999) {
    return false;
  }
  if (*counts.accepted > std::numeric_limits<std::uint64_t>::max() - *counts.full) {
    return false;
  }
  return *counts.offered == *counts.attempted &&
         *counts.attempted == *counts.accepted + *counts.full &&
         *counts.consumed == *counts.accepted && *counts.final_occupancy == 0U &&
         *counts.raw_sample_count == *counts.accepted;
}

auto summary_for(std::span<const protocol::ConfirmatoryBlocker> blockers)
    -> protocol::ConfirmatoryEstimability {
  using Blocker = protocol::ConfirmatoryBlocker;
  using Summary = protocol::ConfirmatoryEstimability;
  if (blockers.empty()) {
    return Summary::estimable;
  }
  if (blockers.size() > 1U) {
    return Summary::blocked_multiple;
  }
  switch (blockers.front()) {
  case Blocker::blocked_access_leakage:
    return Summary::blocked_access_leakage;
  case Blocker::blocked_effective_tail:
    return Summary::blocked_effective_tail;
  case Blocker::blocked_incomplete_block:
    return Summary::blocked_incomplete_block;
  case Blocker::blocked_invalid_run:
    return Summary::blocked_invalid_run;
  case Blocker::blocked_zero_loss:
    return Summary::blocked_zero_loss;
  }
  return Summary::not_evaluated;
}

auto protocol_version_of(const protocol::ProtocolRecord& record)
    -> protocol::ProtocolVersion {
  return std::visit([](const auto& value) { return value.protocol_version; }, record);
}

auto schema_version_of(const protocol::ProtocolRecord& record)
    -> protocol::ProtocolVersion {
  return std::visit([](const auto& value) { return value.schema_version; }, record);
}

auto find_artifact(std::span<const ArtifactBytes> artifacts,
                   std::string_view artifact_id) -> const ArtifactBytes* {
  const auto found = std::ranges::find_if(artifacts, [&](const auto& artifact) {
    return artifact.artifact_id.value() == artifact_id;
  });
  return found == artifacts.end() ? nullptr : &*found;
}

auto find_evidence(std::span<const RunEvidence> evidence, std::string_view run_id)
    -> const RunEvidence* {
  const auto found = std::ranges::find_if(
      evidence, [&](const auto& item) { return item.run_id.value() == run_id; });
  return found == evidence.end() ? nullptr : &*found;
}

auto parse_artifact_json(const ArtifactBytes& artifact)
    -> protocol::Result<protocol::json::Value> {
  const auto* data = reinterpret_cast<const char*>(artifact.bytes.data());
  return protocol::json::parse(std::string_view(data, artifact.bytes.size()));
}

auto member(const JsonObject& object, std::string_view name)
    -> const protocol::json::Value* {
  const auto found = object.find(name);
  return found == object.end() ? nullptr : &found->second;
}

auto string_member(const JsonObject& object, std::string_view name)
    -> std::string_view {
  const auto* value = member(object, name);
  const auto* text = value == nullptr ? nullptr : value->as_string();
  return text == nullptr ? std::string_view{} : std::string_view(*text);
}

auto uint_member(const JsonObject& object, std::string_view name)
    -> std::optional<std::uint64_t> {
  const auto* value = member(object, name);
  const auto* number = value == nullptr ? nullptr : value->as_number();
  if (number == nullptr) {
    return std::nullopt;
  }
  if (number->kind == protocol::json::Number::Kind::unsigned_integer) {
    return std::get<std::uint64_t>(number->value);
  }
  if (number->kind == protocol::json::Number::Kind::signed_integer) {
    const auto signed_value = std::get<std::int64_t>(number->value);
    if (signed_value >= 0) {
      return static_cast<std::uint64_t>(signed_value);
    }
  }
  return std::nullopt;
}

auto zero_self_hash_matches(const protocol::json::Value& document,
                            std::string_view field) -> bool {
  const auto* source = document.as_object();
  if (source == nullptr) {
    return false;
  }
  const auto declared = string_member(*source, field);
  if (declared.size() != 64U) {
    return false;
  }
  auto zeroed = *source;
  zeroed[std::string(field)] = string_value(std::string(64U, '0'));
  const auto canonical =
      protocol::json::canonicalize(protocol::json::Value(std::move(zeroed)));
  if (!canonical) {
    return false;
  }
  const auto bytes =
      std::as_bytes(std::span(canonical.value().data(), canonical.value().size()));
  return workload::sha256(bytes).hex() == declared;
}

auto json_artifact_matches(const protocol::json::Value& value,
                           const protocol::ArtifactReference& expected) -> bool {
  const auto* object = value.as_object();
  return object != nullptr &&
         string_member(*object, "artifact_id") == expected.artifact_id.value() &&
         string_member(*object, "sha256") == expected.sha256.hex();
}

auto checksum_matches(const protocol::json::Value& value,
                      const protocol::ChecksumEvidence& expected) -> bool {
  const auto* object = value.as_object();
  return object != nullptr &&
         string_member(*object, "algorithm_record_id") ==
             expected.algorithm_record_id.value() &&
         string_member(*object, "algorithm_version") == expected.algorithm_version &&
         string_member(*object, "value_hex") == expected.value_hex;
}

void add(std::vector<ValidationError>& errors, ErrorCategory category, std::string path,
         std::string rule, std::string message) {
  errors.push_back({category, std::move(path), std::move(rule), std::move(message)});
}

template <typename Row>
auto inline_rows(const storage::DecodedRawStream& stream) -> const std::vector<Row>* {
  return std::get_if<std::vector<Row>>(&stream.rows);
}

auto same_joined_row(const protocol::JoinedRecord& left,
                     const protocol::JoinedRecord& right) -> bool {
  return left.run_id == right.run_id &&
         left.accepted_ordinal == right.accepted_ordinal &&
         left.logical_sequence == right.logical_sequence &&
         left.record_index == right.record_index &&
         left.producer_row_ordinal == right.producer_row_ordinal &&
         left.consumer_row_ordinal == right.consumer_row_ordinal &&
         left.scheduled_arrival == right.scheduled_arrival &&
         left.producer_handle_begin == right.producer_handle_begin &&
         left.record_lookup_completion == right.record_lookup_completion &&
         left.enqueue_invocation == right.enqueue_invocation &&
         left.enqueue_linearization == right.enqueue_linearization &&
         left.enqueue_attempt_completion == right.enqueue_attempt_completion &&
         left.dequeue_invocation == right.dequeue_invocation &&
         left.dequeue_linearization == right.dequeue_linearization &&
         left.dequeue_completion == right.dequeue_completion &&
         left.consumer_action_completion == right.consumer_action_completion &&
         left.producer_lateness == right.producer_lateness &&
         left.pointer_lookup_interval == right.pointer_lookup_interval &&
         left.enqueue_service_time == right.enqueue_service_time &&
         left.admission_delay == right.admission_delay &&
         left.queue_residence == right.queue_residence &&
         left.dequeue_service_time == right.dequeue_service_time &&
         left.post_dequeue_delivery_interval == right.post_dequeue_delivery_interval &&
         left.consumer_action_interval == right.consumer_action_interval &&
         left.end_to_end_latency == right.end_to_end_latency;
}

} // namespace

auto to_string(FailureClass failure) noexcept -> std::string_view {
  switch (failure) {
  case FailureClass::producer_count:
    return "PRODUCER_COUNT";
  case FailureClass::producer_run_identity:
    return "PRODUCER_RUN_IDENTITY";
  case FailureClass::producer_logical_sequence:
    return "PRODUCER_LOGICAL_SEQUENCE";
  case FailureClass::producer_record_mapping:
    return "PRODUCER_RECORD_MAPPING";
  case FailureClass::producer_outcome_shape:
    return "PRODUCER_OUTCOME_SHAPE";
  case FailureClass::accepted_ordinal:
    return "ACCEPTED_ORDINAL";
  case FailureClass::consumer_count:
    return "CONSUMER_COUNT";
  case FailureClass::consumer_run_identity:
    return "CONSUMER_RUN_IDENTITY";
  case FailureClass::consumer_ordinal:
    return "CONSUMER_ORDINAL";
  case FailureClass::consumer_record_index:
    return "CONSUMER_RECORD_INDEX";
  case FailureClass::timestamp_order:
    return "TIMESTAMP_ORDER";
  }
  return "UNKNOWN";
}

auto reconcile(const protocol::RunId& run_id,
               std::span<const protocol::ProducerRecord> producer_rows,
               std::span<const protocol::ConsumerRecord> consumer_rows,
               std::span<const std::uint64_t> expected_record_indices)
    -> ReconciliationResult {
  ReconciliationResult result;
  result.status = protocol::JoinStatus::failed;
  result.producer_rows = static_cast<std::uint64_t>(producer_rows.size());
  result.consumer_rows = static_cast<std::uint64_t>(consumer_rows.size());
  auto issue = [&](FailureClass failure_class, ErrorCategory category, std::string path,
                   std::string rule, std::string message) {
    result.issues.push_back(
        {failure_class,
         {category, std::move(path), std::move(rule), std::move(message)}});
  };

  if (producer_rows.size() != expected_record_indices.size()) {
    issue(FailureClass::producer_count, ErrorCategory::reference_mismatch,
          "$reconciliation/producer_rows", "REC-PRODUCER-MAPPING-COUNT",
          "producer row count differs from the immutable record-index mapping");
  }

  std::vector<const protocol::ProducerRecord*> accepted;
  accepted.reserve(producer_rows.size());
  std::uint64_t next_accepted = 0U;
  for (std::size_t index = 0U; index < producer_rows.size(); ++index) {
    const auto& row = producer_rows[index];
    const auto path = "$reconciliation/producer/" + std::to_string(index);
    if (row.run_id != run_id) {
      issue(FailureClass::producer_run_identity, ErrorCategory::reference_mismatch,
            path + "/run_id", "REC-PRODUCER-RUN-ID",
            "producer row run identity differs from the reconciled run");
    }
    if (row.logical_sequence != index) {
      issue(FailureClass::producer_logical_sequence, ErrorCategory::cross_field,
            path + "/logical_sequence", "REC-LOGICAL-SEQUENCE",
            "producer logical sequence must be contiguous in stream order");
    }
    if (index < expected_record_indices.size() &&
        row.record_index != expected_record_indices[index]) {
      issue(FailureClass::producer_record_mapping, ErrorCategory::reference_mismatch,
            path + "/record_index", "REC-RECORD-MAPPING",
            "record index disagrees with the outcome-independent Stage 6 mapping");
    }
    if (row.outcome == protocol::ProducerOutcome::accepted) {
      if (!row.accepted_ordinal || !row.enqueue_linearization) {
        issue(FailureClass::producer_outcome_shape, ErrorCategory::missing_field, path,
              "REC-ACCEPTED-SHAPE",
              "ACCEPTED requires accepted ordinal and enqueue linearization");
      } else {
        if (*row.accepted_ordinal != next_accepted) {
          issue(FailureClass::accepted_ordinal, ErrorCategory::cross_field,
                path + "/accepted_ordinal", "REC-ACCEPTED-ORDINAL",
                "accepted ordinals must be contiguous in producer logical order");
        }
        ++next_accepted;
        accepted.push_back(&row);
      }
    } else {
      ++result.full_rows;
      if (row.accepted_ordinal || row.enqueue_linearization) {
        issue(FailureClass::producer_outcome_shape, ErrorCategory::cross_field, path,
              "REC-FULL-SHAPE",
              "FULL cannot contain accepted ordinal or enqueue linearization");
      }
    }
  }
  result.accepted_rows = static_cast<std::uint64_t>(accepted.size());

  if (consumer_rows.size() != accepted.size()) {
    issue(FailureClass::consumer_count, ErrorCategory::cross_field,
          "$reconciliation/consumer_rows", "REC-CONSUMER-COUNT",
          "consumer count must equal the accepted producer count");
  }
  const auto paired = std::min(consumer_rows.size(), accepted.size());
  for (std::size_t index = 0U; index < paired; ++index) {
    const auto& consumer = consumer_rows[index];
    const auto& producer = *accepted[index];
    const auto path = "$reconciliation/consumer/" + std::to_string(index);
    if (consumer.run_id != run_id) {
      issue(FailureClass::consumer_run_identity, ErrorCategory::reference_mismatch,
            path + "/run_id", "REC-CONSUMER-RUN-ID",
            "consumer row run identity differs from the reconciled run");
    }
    if (consumer.consumed_ordinal != index || !producer.accepted_ordinal ||
        consumer.consumed_ordinal != *producer.accepted_ordinal) {
      issue(FailureClass::consumer_ordinal, ErrorCategory::cross_field,
            path + "/consumed_ordinal", "REC-KTH-ORDINAL",
            "the k-th consumer row must match the k-th accepted producer row");
    }
    if (consumer.observed_record_index != producer.record_index) {
      issue(FailureClass::consumer_record_index, ErrorCategory::reference_mismatch,
            path + "/observed_record_index", "REC-KTH-RECORD-INDEX",
            "consumer record index must match its accepted producer event");
    }
  }

  // Derived intervals are deliberately unreachable until the complete exact
  // join audit above has passed.
  if (!result.issues.empty()) {
    return result;
  }
  result.joined_rows.reserve(accepted.size());
  for (std::size_t index = 0U; index < accepted.size(); ++index) {
    auto joined = timing::derive_joined_record(
        *accepted[index],
        static_cast<std::uint64_t>(accepted[index] - producer_rows.data()),
        consumer_rows[index], index);
    if (!joined) {
      for (const auto& error : joined.errors()) {
        result.issues.push_back({FailureClass::timestamp_order, error});
      }
    } else {
      result.joined_rows.push_back(std::move(joined).value());
    }
  }
  if (!result.issues.empty()) {
    result.joined_rows.clear();
    return result;
  }
  result.status = protocol::JoinStatus::passed;
  return result;
}

auto evaluate_run_status(const RunStatusInput& input) -> protocol::Result<RunStatus> {
  RunStatus output;
  output.join_status = input.join_status;
  output.block_completeness = input.block_completeness.status;
  switch (input.lifecycle_state) {
  case protocol::LifecycleState::completed:
    output.lifecycle_completion = LifecycleCompletion::complete;
    break;
  case protocol::LifecycleState::pre_run_failure:
  case protocol::LifecycleState::warmup_failure:
  case protocol::LifecycleState::reset_failure:
  case protocol::LifecycleState::measurement_failure:
  case protocol::LifecycleState::drain_failure:
    output.lifecycle_completion = LifecycleCompletion::incomplete;
    output.validity = protocol::RunValidity::invalid;
    break;
  case protocol::LifecycleState::planned:
  case protocol::LifecycleState::measurement_started:
    return protocol::Result<RunStatus>::success(output);
  }

  if (output.lifecycle_completion == LifecycleCompletion::complete) {
    if (!input.counts) {
      return failure<RunStatus>(ErrorCategory::missing_evidence, "$status/counts",
                                "REC-STATUS-COUNTS",
                                "completed lifecycle requires complete counts");
    }
    const auto exact_counts = complete_count_identities(*input.counts);
    output.count_reconciliation =
        exact_counts && input.join_status == protocol::JoinStatus::passed
            ? protocol::GateStatus::pass
            : protocol::GateStatus::fail;
    output.validity = output.count_reconciliation == protocol::GateStatus::pass
                          ? protocol::RunValidity::valid
                          : protocol::RunValidity::invalid;
    if (input.counts->full) {
      output.zero_loss = *input.counts->full == 0U ? protocol::GateStatus::pass
                                                   : protocol::GateStatus::fail;
    }
    if (input.counts->n_eff_p999) {
      output.effective_tail = n_eff_at_least_threshold(*input.counts->n_eff_p999)
                                  ? protocol::GateStatus::pass
                                  : protocol::GateStatus::fail;
    }
  }

  if (output.validity == protocol::RunValidity::invalid &&
      !input.invalidating_failure_record_present) {
    return failure<RunStatus>(ErrorCategory::missing_evidence,
                              "$status/failure_record_ids",
                              "REC-INVALID-FAILURE-EVIDENCE",
                              "INVALID requires an invalidating failure record");
  }

  if (input.stage != protocol::Stage::stage_a) {
    output.confirmatory_estimability =
        protocol::ConfirmatoryEstimability::not_applicable;
    return protocol::Result<RunStatus>::success(output);
  }

  const bool run_gates_authoritative =
      output.lifecycle_completion != LifecycleCompletion::not_evaluated &&
      output.validity != protocol::RunValidity::not_evaluated &&
      output.zero_loss != protocol::GateStatus::not_evaluated &&
      output.effective_tail != protocol::GateStatus::not_evaluated;
  if (!run_gates_authoritative || !input.block_completeness.authoritative ||
      !input.access_integrity.authoritative) {
    output.confirmatory_estimability =
        protocol::ConfirmatoryEstimability::not_evaluated;
    return protocol::Result<RunStatus>::success(output);
  }

  if (input.access_integrity.status == protocol::GateStatus::fail) {
    output.confirmatory_blockers.push_back(
        protocol::ConfirmatoryBlocker::blocked_access_leakage);
  }
  if (output.effective_tail == protocol::GateStatus::fail) {
    output.confirmatory_blockers.push_back(
        protocol::ConfirmatoryBlocker::blocked_effective_tail);
  }
  if (input.block_completeness.status == protocol::BlockCompleteness::incomplete) {
    output.confirmatory_blockers.push_back(
        protocol::ConfirmatoryBlocker::blocked_incomplete_block);
  }
  if (output.validity == protocol::RunValidity::invalid) {
    output.confirmatory_blockers.push_back(
        protocol::ConfirmatoryBlocker::blocked_invalid_run);
  }
  if (output.zero_loss == protocol::GateStatus::fail) {
    output.confirmatory_blockers.push_back(
        protocol::ConfirmatoryBlocker::blocked_zero_loss);
  }
  output.confirmatory_estimability = summary_for(output.confirmatory_blockers);
  return protocol::Result<RunStatus>::success(output);
}

auto make_join_audit(const protocol::RunId& run_id, const ReconciliationResult& result,
                     const JoinAuditInput& artifacts) -> protocol::Result<std::string> {
  if (result.status == protocol::JoinStatus::not_attempted) {
    return failure<std::string>(ErrorCategory::cross_field, "$audit/join_status",
                                "REC-AUDIT-FINAL",
                                "join audit requires PASSED or FAILED status");
  }
  if ((result.status == protocol::JoinStatus::passed) !=
      artifacts.joined_artifact.has_value()) {
    return failure<std::string>(ErrorCategory::cross_field, "$audit/joined_artifact",
                                "REC-AUDIT-JOINED",
                                "passed audit requires joined artifact; failed audit "
                                "forbids it");
  }
  if ((result.status == protocol::JoinStatus::passed && !result.issues.empty()) ||
      (result.status == protocol::JoinStatus::failed && result.issues.empty())) {
    return failure<std::string>(ErrorCategory::cross_field, "$audit/issues",
                                "REC-AUDIT-ISSUES",
                                "audit issue cardinality disagrees with join status");
  }

  JsonArray sources;
  sources.push_back(artifact_value(artifacts.producer_source));
  sources.push_back(artifact_value(artifacts.consumer_source));
  JsonArray issues;
  for (const auto& issue : result.issues) {
    JsonObject object;
    object.emplace("failure_class", string_value(to_string(issue.failure)));
    object.emplace("category", string_value(protocol::to_string(issue.error.category)));
    object.emplace("path", string_value(issue.error.path));
    object.emplace("rule_id", string_value(issue.error.rule_id));
    object.emplace("message", string_value(issue.error.message));
    issues.emplace_back(std::move(object));
  }
  JsonObject object;
  object.emplace("schema_version", string_value("cpu-prefetch-join-audit/1"));
  object.emplace("protocol_version", string_value(protocol::kProtocolVersion));
  object.emplace("run_id", string_value(run_id.value()));
  object.emplace("join_status",
                 string_value(result.status == protocol::JoinStatus::passed
                                  ? "PASSED"
                                  : "FAILED"));
  object.emplace("producer_rows", uint_value(result.producer_rows));
  object.emplace("accepted_rows", uint_value(result.accepted_rows));
  object.emplace("full_rows", uint_value(result.full_rows));
  object.emplace("consumer_rows", uint_value(result.consumer_rows));
  object.emplace("source_artifacts", protocol::json::Value(std::move(sources)));
  object.emplace("issues", protocol::json::Value(std::move(issues)));
  object.emplace("joined_artifact", artifacts.joined_artifact
                                        ? artifact_value(*artifacts.joined_artifact)
                                        : protocol::json::Value(nullptr));
  object.emplace("record_sha256", string_value(std::string(64U, '0')));
  const auto zeroed = protocol::json::Value(object);
  const auto canonical_zero = protocol::json::canonicalize(zeroed);
  if (!canonical_zero) {
    return protocol::Result<std::string>::failure(canonical_zero.errors());
  }
  const auto bytes = std::as_bytes(
      std::span(canonical_zero.value().data(), canonical_zero.value().size()));
  object["record_sha256"] = string_value(workload::sha256(bytes).hex());
  return protocol::json::canonicalize(protocol::json::Value(std::move(object)));
}

auto Stage12CrossRecordSemanticValidator::validate(
    const protocol::SemanticRecordSet& record_set) const
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  const protocol::Stage4SemanticValidator local;
  for (const auto& record : record_set.records) {
    auto local_errors = local.validate(record);
    errors.insert(errors.end(), local_errors.begin(), local_errors.end());
    if (protocol_version_of(record) != schema_version_of(record) ||
        protocol_version_of(record) == protocol::ProtocolVersion::v2_0_0_pre_1) {
      add(errors, ErrorCategory::unsupported_version, "$records/protocol_version",
          "REC-PRE2-REQUIRED",
          "Stage 12 final semantics require matching protocol/schema pre.2 or pre.3");
    }
  }

  std::set<std::string> artifact_ids;
  for (const auto& artifact : artifacts_) {
    if (!artifact_ids.emplace(artifact.artifact_id.value()).second) {
      add(errors, ErrorCategory::duplicate_value, "$artifacts",
          "REC-DUPLICATE-ARTIFACT-ID", "artifact IDs must be unique");
    }
  }

  std::vector<const protocol::RawObservationEnvelope*> raw_envelopes;
  std::vector<const protocol::ScheduleRecord*> schedules;
  std::vector<const protocol::FailureRecord*> failures;
  std::vector<const protocol::RunManifest*> manifests;
  for (const auto& record : record_set.records) {
    std::visit(
        [&](const auto& value) {
          using Value = std::decay_t<decltype(value)>;
          if constexpr (std::is_same_v<Value, protocol::RawObservationEnvelope>) {
            raw_envelopes.push_back(&value);
          } else if constexpr (std::is_same_v<Value, protocol::ScheduleRecord>) {
            schedules.push_back(&value);
          } else if constexpr (std::is_same_v<Value, protocol::FailureRecord>) {
            failures.push_back(&value);
          } else if constexpr (std::is_same_v<Value, protocol::RunManifest>) {
            manifests.push_back(&value);
          }
        },
        record);
  }

  const auto reject_duplicate = [&](const auto& values, auto key, std::string_view path,
                                    std::string_view rule, std::string_view message) {
    std::set<std::string> seen;
    for (const auto* value : values) {
      if (!seen.emplace(std::string(key(*value))).second) {
        add(errors, ErrorCategory::duplicate_value, std::string(path),
            std::string(rule), std::string(message));
      }
    }
  };
  reject_duplicate(
      raw_envelopes, [](const auto& value) { return value.artifact_id.value(); },
      "$records/raw_observation", "REC-DUPLICATE-RAW-ENVELOPE",
      "raw-envelope artifact IDs must be unique in a record graph");
  reject_duplicate(
      schedules, [](const auto& value) { return value.schedule_id.value(); },
      "$records/schedule", "REC-DUPLICATE-SCHEDULE-ID",
      "schedule IDs must be unique in a record graph");
  reject_duplicate(
      failures, [](const auto& value) { return value.failure_record_id.value(); },
      "$records/failure", "REC-DUPLICATE-FAILURE-ID",
      "failure record IDs must be unique in a record graph");
  reject_duplicate(
      manifests, [](const auto& value) { return value.run_id.value(); },
      "$records/run_manifest", "REC-DUPLICATE-RUN-MANIFEST",
      "each run identity can have only one manifest in a record graph");
  std::set<std::string> evidence_run_ids;
  for (const auto& value : evidence_) {
    if (!evidence_run_ids.emplace(value.run_id.value()).second) {
      add(errors, ErrorCategory::duplicate_value, "$evidence",
          "REC-DUPLICATE-RUN-EVIDENCE",
          "each run identity can have only one injected evidence record");
    }
  }

  for (const auto* failure_record : failures) {
    const auto* object = failure_record->source_document.as_object();
    if (object == nullptr ||
        string_member(*object, "record_sha256") !=
            failure_record->record_sha256.hex() ||
        !zero_self_hash_matches(failure_record->source_document, "record_sha256")) {
      add(errors, ErrorCategory::invalid_hash, "$records/failure/record_sha256",
          "REC-FAILURE-SELF-HASH",
          "typed and source failure SHA-256 must agree with its zero-self digest");
    }
    for (const auto& evidence_reference : failure_record->evidence_refs) {
      const auto* bytes =
          find_artifact(artifacts_, evidence_reference.artifact_id.value());
      if (bytes == nullptr ||
          workload::sha256(bytes->bytes).hex() != evidence_reference.sha256.hex()) {
        add(errors, ErrorCategory::invalid_hash, "$records/failure/evidence_refs",
            "REC-FAILURE-EVIDENCE-HASH",
            "failure evidence must resolve to exact immutable bytes");
      }
    }
  }

  for (const auto* manifest : manifests) {
    const auto base = "$runs/" + std::string(manifest->run_id.value());
    const auto* run_evidence = find_evidence(evidence_, manifest->run_id.value());
    const auto* manifest_object = manifest->source_document.as_object();
    if (manifest_object == nullptr ||
        string_member(*manifest_object, "manifest_sha256") !=
            manifest->manifest_sha256.hex() ||
        !zero_self_hash_matches(manifest->source_document, "manifest_sha256")) {
      add(errors, ErrorCategory::invalid_hash, base + "/manifest_sha256",
          "REC-MANIFEST-SELF-HASH",
          "typed and source manifest SHA-256 must agree with the JCS-I64-v1 "
          "zero-self digest");
    }
    std::set<protocol::ArtifactRelationship> seen_relationships;
    for (const auto& reference : manifest->artifact_refs) {
      if (!seen_relationships.emplace(reference.relationship).second) {
        add(errors, ErrorCategory::duplicate_value, base + "/artifact_refs",
            "REC-DUPLICATE-RELATIONSHIP",
            "a run manifest can name each artifact relationship only once");
      }
      const auto* artifact =
          find_artifact(artifacts_, reference.artifact.artifact_id.value());
      if (artifact == nullptr) {
        add(errors, ErrorCategory::missing_evidence, base + "/artifact_refs",
            "REC-ARTIFACT-MISSING", "manifest artifact bytes are unavailable");
      } else if (workload::sha256(artifact->bytes).hex() !=
                 reference.artifact.sha256.hex()) {
        add(errors, ErrorCategory::invalid_hash, base + "/artifact_refs",
            "REC-ARTIFACT-HASH", "artifact bytes do not match the manifest SHA-256");
      }
    }

    bool invalidating_failure = false;
    for (const auto& failure_id : manifest->failure_record_ids) {
      const auto found = std::ranges::find_if(failures, [&](const auto* failure) {
        return failure->failure_record_id.value() == failure_id.value();
      });
      if (found == failures.end() || !(*found)->run_id ||
          (*found)->run_id->value() != manifest->run_id.value()) {
        add(errors, ErrorCategory::reference_mismatch, base + "/failure_record_ids",
            "REC-FAILURE-RELATION", "failure reference does not resolve to this run");
      } else {
        invalidating_failure = invalidating_failure || (*found)->invalidates_run;
      }
    }

    auto relationship = [&](protocol::ArtifactRelationship wanted)
        -> const protocol::TypedArtifactReference* {
      const auto found =
          std::ranges::find_if(manifest->artifact_refs, [&](const auto& reference) {
            return reference.relationship == wanted;
          });
      return found == manifest->artifact_refs.end() ? nullptr : &*found;
    };
    auto raw_for = [&](const protocol::TypedArtifactReference* reference)
        -> const protocol::RawObservationEnvelope* {
      if (reference == nullptr) {
        return nullptr;
      }
      const auto found = std::ranges::find_if(raw_envelopes, [&](const auto* envelope) {
        return envelope->artifact_id.value() == reference->artifact.artifact_id.value();
      });
      return found == raw_envelopes.end() ? nullptr : *found;
    };

    const auto* producer_ref =
        relationship(protocol::ArtifactRelationship::producer_raw);
    const auto* consumer_ref =
        relationship(protocol::ArtifactRelationship::consumer_raw);
    const auto* audit_ref = relationship(protocol::ArtifactRelationship::join_audit);
    const auto* joined_ref =
        relationship(protocol::ArtifactRelationship::joined_derived);
    const auto* integrity_ref =
        relationship(protocol::ArtifactRelationship::phase_integrity_report);
    const auto* provenance_ref =
        relationship(protocol::ArtifactRelationship::provenance);
    const auto* producer_envelope = raw_for(producer_ref);
    const auto* consumer_envelope = raw_for(consumer_ref);
    const auto* joined_envelope = raw_for(joined_ref);
    const auto require_raw_envelope = [&](const protocol::TypedArtifactReference* ref,
                                          const protocol::RawObservationEnvelope*
                                              envelope,
                                          std::string_view name) {
      if (ref != nullptr && envelope == nullptr) {
        add(errors, ErrorCategory::missing_evidence,
            base + "/artifact_refs/" + std::string(name), "REC-RAW-ENVELOPE",
            "raw artifact relationship does not resolve to a typed envelope record");
      }
    };
    require_raw_envelope(producer_ref, producer_envelope, "producer_raw");
    require_raw_envelope(consumer_ref, consumer_envelope, "consumer_raw");
    require_raw_envelope(joined_ref, joined_envelope, "joined_derived");

    if (provenance_ref != nullptr) {
      const auto* provenance_bytes =
          find_artifact(artifacts_, provenance_ref->artifact.artifact_id.value());
      if (provenance_bytes != nullptr) {
        const auto document = parse_artifact_json(*provenance_bytes);
        const auto* object = document ? document.value().as_object() : nullptr;
        if (object == nullptr ||
            string_member(*object, "schema_version") !=
                "cpu-prefetch-queue-provenance/1" ||
            string_member(*object, "protocol_version") !=
                protocol::kOldestReadableProtocolVersion ||
            string_member(*object, "queue_id") !=
                manifest->queue_provenance_id.value()) {
          add(errors, ErrorCategory::reference_mismatch, base + "/provenance",
              "REC-QUEUE-PROVENANCE",
              "queue provenance identity and accepted historical suite must match");
        }
      }
    }

    std::optional<storage::DecodedRawStream> producer_decoded;
    std::optional<storage::DecodedRawStream> consumer_decoded;
    std::optional<storage::DecodedRawStream> joined_decoded;
    auto decode = [&](const protocol::RawObservationEnvelope* envelope,
                      const protocol::TypedArtifactReference* reference,
                      std::optional<storage::DecodedRawStream>& output) {
      if (envelope == nullptr || reference == nullptr) {
        return;
      }
      const auto* bytes =
          find_artifact(artifacts_, reference->artifact.artifact_id.value());
      if (bytes == nullptr) {
        return;
      }
      auto decoded = storage::decode_external_raw(*envelope, bytes->bytes);
      if (!decoded) {
        errors.insert(errors.end(), decoded.errors().begin(), decoded.errors().end());
      } else {
        output = std::move(decoded).value();
      }
    };
    decode(producer_envelope, producer_ref, producer_decoded);
    decode(consumer_envelope, consumer_ref, consumer_decoded);
    decode(joined_envelope, joined_ref, joined_decoded);

    if (audit_ref != nullptr) {
      const auto* audit_bytes =
          find_artifact(artifacts_, audit_ref->artifact.artifact_id.value());
      if (audit_bytes != nullptr) {
        const auto document = parse_artifact_json(*audit_bytes);
        if (!document || document.value().as_object() == nullptr) {
          add(errors, ErrorCategory::parse_error, base + "/join_audit",
              "REC-AUDIT-JSON", "join audit is not a valid JSON object");
        } else {
          const auto& object = *document.value().as_object();
          const auto expected_status =
              manifest->join_status == protocol::JoinStatus::passed ? "PASSED"
                                                                    : "FAILED";
          const auto* sources_value = member(object, "source_artifacts");
          const auto* sources =
              sources_value == nullptr ? nullptr : sources_value->as_array();
          const auto* joined_value = member(object, "joined_artifact");
          const auto producer_count = uint_member(object, "producer_rows");
          const auto accepted_count = uint_member(object, "accepted_rows");
          const auto full_count = uint_member(object, "full_rows");
          const auto consumer_count = uint_member(object, "consumer_rows");
          const bool audit_counts_valid =
              producer_count && accepted_count && full_count && consumer_count &&
              *accepted_count <=
                  std::numeric_limits<std::uint64_t>::max() - *full_count &&
              *producer_count == *accepted_count + *full_count;
          const bool sources_match =
              producer_ref != nullptr && consumer_ref != nullptr &&
              sources != nullptr && sources->size() == 2U &&
              json_artifact_matches((*sources)[0], producer_ref->artifact) &&
              json_artifact_matches((*sources)[1], consumer_ref->artifact);
          const bool joined_matches =
              manifest->join_status == protocol::JoinStatus::passed
                  ? joined_ref != nullptr && joined_value != nullptr &&
                        json_artifact_matches(*joined_value, joined_ref->artifact)
                  : joined_value != nullptr && joined_value->is_null();
          if (string_member(object, "schema_version") != "cpu-prefetch-join-audit/1" ||
              string_member(object, "protocol_version") != protocol::kProtocolVersion ||
              string_member(object, "run_id") != manifest->run_id.value() ||
              string_member(object, "join_status") != expected_status ||
              !sources_match || !joined_matches || !audit_counts_valid ||
              !zero_self_hash_matches(document.value(), "record_sha256")) {
            add(errors, ErrorCategory::reference_mismatch, base + "/join_audit",
                "REC-AUDIT-CONTENT",
                "join audit version, identity, status, sources, or self-hash "
                "disagrees with the manifest");
          }
        }
      }
    }

    if (manifest->integrity_evidence && integrity_ref != nullptr) {
      if (manifest->integrity_evidence->report_artifact != integrity_ref->artifact) {
        add(errors, ErrorCategory::reference_mismatch,
            base + "/integrity_evidence/report_artifact", "REC-INTEGRITY-REFERENCE",
            "integrity evidence and artifact relationship disagree");
      }
      const auto* report_bytes =
          find_artifact(artifacts_, integrity_ref->artifact.artifact_id.value());
      if (report_bytes != nullptr) {
        const auto document = parse_artifact_json(*report_bytes);
        const auto* object = document ? document.value().as_object() : nullptr;
        const auto* content_match_value =
            object == nullptr ? nullptr : member(*object, "content_checksum_match");
        const auto* content_match =
            content_match_value == nullptr ? nullptr : content_match_value->as_bool();
        const auto& expected = *manifest->integrity_evidence;
        const std::array checks{
            std::pair{"final_consumer_rolling_checksum",
                      &expected.final_consumer_rolling_checksum},
            std::pair{"event_records_pre_checksum",
                      &expected.event_records_pre_checksum},
            std::pair{"event_records_post_checksum",
                      &expected.event_records_post_checksum},
            std::pair{"ordered_index_checksum", &expected.ordered_index_checksum},
            std::pair{"address_delta_checksum", &expected.address_delta_checksum}};
        bool checks_match = object != nullptr;
        for (const auto& [name, checksum] : checks) {
          const auto* value = object == nullptr ? nullptr : member(*object, name);
          checks_match =
              checks_match && value != nullptr && checksum_matches(*value, *checksum);
        }
        if (object == nullptr ||
            string_member(*object, "protocol_version") != protocol::kProtocolVersion ||
            string_member(*object, "artifact_id") !=
                integrity_ref->artifact.artifact_id.value() ||
            string_member(*object, "run_id") != manifest->run_id.value() ||
            content_match == nullptr || !*content_match || !checks_match) {
          add(errors, ErrorCategory::reference_mismatch, base + "/integrity_evidence",
              "REC-INTEGRITY-CONTENT",
              "phase/integrity report identity or checksum evidence disagrees");
        }
      }
      for (const auto* envelope :
           std::array{producer_envelope, consumer_envelope, joined_envelope}) {
        if (envelope != nullptr &&
            envelope->integrity_artifact_ref != integrity_ref->artifact) {
          add(errors, ErrorCategory::reference_mismatch,
              base + "/raw/integrity_artifact_ref", "REC-RAW-INTEGRITY",
              "raw envelope does not reference the manifest integrity report");
        }
      }
    }

    std::optional<ReconciliationResult> reconciled;
    if (producer_decoded && consumer_decoded) {
      const auto* producer =
          inline_rows<storage::DecodedProducerRow>(*producer_decoded);
      const auto* consumer =
          inline_rows<storage::DecodedConsumerRow>(*consumer_decoded);
      if (producer != nullptr && consumer != nullptr) {
        std::vector<protocol::ProducerRecord> logical_producer;
        std::vector<protocol::ConsumerRecord> logical_consumer;
        logical_producer.reserve(producer->size());
        logical_consumer.reserve(consumer->size());
        for (const auto& row : *producer) {
          logical_producer.push_back(
              timing::make_producer_record(manifest->run_id, row.observation));
        }
        for (const auto& row : *consumer) {
          logical_consumer.push_back(
              timing::make_consumer_record(manifest->run_id, row.observation));
        }
        if (run_evidence == nullptr) {
          add(errors, ErrorCategory::missing_evidence, base + "/record_mapping",
              "REC-STAGE6-MAPPING",
              "exact reconciliation requires immutable Stage 6 record mapping");
        } else {
          reconciled = reconcile(manifest->run_id, logical_producer, logical_consumer,
                                 run_evidence->expected_record_indices);
          if (reconciled->status != manifest->join_status) {
            add(errors, ErrorCategory::cross_field, base + "/join_status",
                "REC-JOIN-STATUS", "manifest join status disagrees with exact join");
          }
          for (const auto& issue : reconciled->issues) {
            errors.push_back(issue.error);
          }
        }
      }
    }

    if (reconciled && reconciled->status == protocol::JoinStatus::passed) {
      const auto* rows = joined_decoded
                             ? inline_rows<protocol::JoinedRecord>(*joined_decoded)
                             : nullptr;
      if (rows == nullptr || rows->size() != reconciled->joined_rows.size() ||
          !std::ranges::equal(*rows, reconciled->joined_rows, same_joined_row)) {
        add(errors, ErrorCategory::reference_mismatch, base + "/joined_derived",
            "REC-JOINED-EXACT",
            "joined artifact is absent or differs from exact post-run derivation");
      }
      if (joined_envelope != nullptr && producer_ref != nullptr &&
          consumer_ref != nullptr) {
        const std::array expected{producer_ref->artifact, consumer_ref->artifact};
        if (joined_envelope->source_artifacts.size() != expected.size() ||
            !std::ranges::equal(joined_envelope->source_artifacts, expected)) {
          add(errors, ErrorCategory::reference_mismatch,
              base + "/joined_derived/source_artifacts", "REC-JOINED-SOURCES",
              "joined envelope must name producer then consumer raw artifacts");
        }
      }
      if (manifest->counts) {
        const auto& counts = *manifest->counts;
        if (!counts.attempted || !counts.accepted || !counts.full || !counts.consumed ||
            !counts.raw_sample_count ||
            *counts.attempted != reconciled->producer_rows ||
            *counts.accepted != reconciled->accepted_rows ||
            *counts.full != reconciled->full_rows ||
            *counts.consumed != reconciled->consumer_rows ||
            *counts.raw_sample_count != reconciled->joined_rows.size()) {
          add(errors, ErrorCategory::cross_field, base + "/counts", "REC-RAW-COUNTS",
              "manifest counts disagree with reconciled raw and joined rows");
        }
      }
    }

    if (reconciled && audit_ref != nullptr && producer_ref != nullptr &&
        consumer_ref != nullptr) {
      const auto* actual =
          find_artifact(artifacts_, audit_ref->artifact.artifact_id.value());
      const auto expected = make_join_audit(
          manifest->run_id, *reconciled,
          {producer_ref->artifact, consumer_ref->artifact,
           reconciled->status == protocol::JoinStatus::passed && joined_ref != nullptr
               ? std::optional<protocol::ArtifactReference>(joined_ref->artifact)
               : std::nullopt});
      const auto actual_text =
          actual == nullptr
              ? std::string_view{}
              : std::string_view(reinterpret_cast<const char*>(actual->bytes.data()),
                                 actual->bytes.size());
      if (!expected || actual_text != expected.value()) {
        add(errors, ErrorCategory::reference_mismatch, base + "/join_audit",
            "REC-AUDIT-EXACT",
            "join audit must exactly equal the independently regenerated audit");
      }
    }

    auto schedule_for = [&](const protocol::ArtifactReference& reference)
        -> const protocol::ScheduleRecord* {
      const auto found = std::ranges::find_if(schedules, [&](const auto* schedule) {
        const auto* external =
            std::get_if<protocol::ExternalScheduleStorage>(&schedule->deadline_storage);
        return external != nullptr && external->artifact_id == reference.artifact_id &&
               external->artifact_sha256 == reference.sha256;
      });
      return found == schedules.end() ? nullptr : *found;
    };
    const auto* measurement_schedule =
        schedule_for(manifest->schedule_refs.measurement);
    const auto* warmup_schedule = schedule_for(manifest->schedule_refs.warmup);
    for (const auto* schedule_reference : std::array{
             &manifest->schedule_refs.measurement, &manifest->schedule_refs.warmup}) {
      const auto* bytes =
          find_artifact(artifacts_, schedule_reference->artifact_id.value());
      if (bytes == nullptr ||
          workload::sha256(bytes->bytes).hex() != schedule_reference->sha256.hex()) {
        add(errors, ErrorCategory::invalid_hash, base + "/schedule_refs",
            "REC-SCHEDULE-ARTIFACT",
            "schedule reference does not resolve to exact immutable bytes");
      }
    }
    if (manifest->lifecycle_state == protocol::LifecycleState::completed &&
        (measurement_schedule == nullptr || warmup_schedule == nullptr)) {
      add(errors, ErrorCategory::missing_evidence, base + "/schedule_refs",
          "REC-SCHEDULE-RELATION",
          "completed run schedule references must resolve to exact schedule records");
    }
    if (manifest->counts && manifest->counts->offered &&
        measurement_schedule != nullptr &&
        *manifest->counts->offered != measurement_schedule->offered_count) {
      add(errors, ErrorCategory::cross_field, base + "/counts/offered",
          "REC-SCHEDULE-COUNT",
          "manifest offered count differs from the frozen measurement schedule");
    }

    RunStatusInput status_input{
        manifest->stage,
        manifest->lifecycle_state,
        manifest->join_status,
        manifest->counts,
        invalidating_failure,
        run_evidence != nullptr ? run_evidence->block_completeness
                                : AuthoritativeBlockCompleteness{},
        run_evidence != nullptr ? run_evidence->access_integrity : AuthoritativeGate{}};
    const auto evaluated = evaluate_run_status(status_input);
    if (!evaluated) {
      errors.insert(errors.end(), evaluated.errors().begin(), evaluated.errors().end());
    } else {
      const auto& status = evaluated.value();
      if (manifest->validity != status.validity ||
          manifest->count_reconciliation != status.count_reconciliation ||
          manifest->zero_loss_status != status.zero_loss ||
          manifest->effective_tail_status != status.effective_tail ||
          manifest->block_completeness != status.block_completeness ||
          manifest->confirmatory_estimability != status.confirmatory_estimability ||
          manifest->confirmatory_blockers != status.confirmatory_blockers) {
        add(errors, ErrorCategory::cross_field, base + "/status",
            "REC-INDEPENDENT-GATES",
            "manifest independent run gates disagree with Stage 12 evaluation");
      }
    }
  }
  return errors;
}

} // namespace cpu_prefetch::reconciliation
