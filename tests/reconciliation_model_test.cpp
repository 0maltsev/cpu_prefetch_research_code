#include "cpu_prefetch/reconciliation/reconciliation.hpp"
#include "cpu_prefetch/storage/artifacts.hpp"
#include "cpu_prefetch/storage/raw_observations.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

namespace {

namespace protocol = cpu_prefetch::protocol;
namespace reconciliation = cpu_prefetch::reconciliation;
namespace storage = cpu_prefetch::storage;
namespace workload = cpu_prefetch::workload;

template <typename Identifier> auto identifier(std::string_view value) -> Identifier {
  return std::move(Identifier::parse(std::string(value), "$test/id")).value();
}

auto run_id(std::string value = "synthetic-run") -> protocol::RunId {
  return std::move(protocol::RunId::parse(std::move(value), "$test/run_id")).value();
}

auto artifact_id(std::string value) -> protocol::ArtifactId {
  return std::move(protocol::ArtifactId::parse(std::move(value), "$test/artifact_id"))
      .value();
}

auto zero_hash() -> protocol::Sha256 {
  return std::move(protocol::Sha256::parse(std::string(64U, '0'), "$test/hash"))
      .value();
}

auto protocol_hash(std::span<const std::byte> bytes) -> protocol::Sha256 {
  return std::move(protocol::Sha256::parse(workload::sha256(bytes).hex(), "$test/hash"))
      .value();
}

auto string_bytes(const std::string& text) -> std::span<const std::byte> {
  return std::as_bytes(std::span(text.data(), text.size()));
}

auto self_hashed_document(std::string_view field)
    -> std::pair<protocol::json::Value, protocol::Sha256> {
  protocol::json::Value::Object source;
  source.emplace(std::string(field), protocol::json::Value(std::string(64U, '0')));
  const auto zeroed = protocol::json::canonicalize(protocol::json::Value(source));
  if (!zeroed) {
    throw std::logic_error("synthetic self-hash canonicalization failed");
  }
  const auto digest = protocol_hash(string_bytes(zeroed.value()));
  source[std::string(field)] = protocol::json::Value(digest.hex());
  return {protocol::json::Value(std::move(source)), digest};
}

auto producer(const protocol::RunId& id, std::uint64_t logical_sequence,
              std::uint64_t record_index, bool accepted,
              std::uint64_t accepted_ordinal = 0U) -> protocol::ProducerRecord {
  const auto base = 100U + logical_sequence * 100U;
  return {id,
          logical_sequence,
          record_index,
          base,
          base + 1U,
          base + 2U,
          base + 3U,
          accepted ? std::optional<std::uint64_t>(base + 4U) : std::nullopt,
          base + 5U,
          accepted ? protocol::ProducerOutcome::accepted
                   : protocol::ProducerOutcome::full,
          accepted ? std::optional<std::uint64_t>(accepted_ordinal) : std::nullopt};
}

auto consumer(const protocol::ProducerRecord& accepted, std::uint64_t ordinal)
    -> protocol::ConsumerRecord {
  const auto linearization = accepted.enqueue_attempt_completion - 1U;
  return {accepted.run_id,       ordinal,
          accepted.record_index, linearization + 6U,
          linearization + 10U,   linearization + 11U,
          linearization + 12U};
}

struct FixtureRows final {
  protocol::RunId id{run_id()};
  std::vector<std::uint64_t> mapping{0U, 1U, 0U, 1U};
  std::vector<protocol::ProducerRecord> producers;
  std::vector<protocol::ConsumerRecord> consumers;

  FixtureRows() {
    producers.push_back(producer(id, 0U, 0U, true, 0U));
    producers.push_back(producer(id, 1U, 1U, false));
    producers.push_back(producer(id, 2U, 0U, true, 1U));
    producers.push_back(producer(id, 3U, 1U, true, 2U));
    consumers.push_back(consumer(producers[0], 0U));
    consumers.push_back(consumer(producers[2], 1U));
    consumers.push_back(consumer(producers[3], 2U));
  }
};

auto n_eff(std::uint64_t value) -> protocol::json::Number {
  return {protocol::json::Number::Kind::unsigned_integer, std::to_string(value), value};
}

auto complete_counts(std::uint64_t full, std::uint64_t effective)
    -> protocol::RunCounts {
  constexpr std::uint64_t accepted = 3U;
  const auto offered = accepted + full;
  return {offered, offered, accepted, full, accepted, 0U, accepted, n_eff(effective)};
}

auto has_failure(const reconciliation::ReconciliationResult& result,
                 reconciliation::FailureClass failure) -> bool {
  return std::ranges::any_of(
      result.issues, [&](const auto& issue) { return issue.failure == failure; });
}

TEST(Reconciliation, ExactKthJoinAllowsRepeatingRecordIndices) {
  FixtureRows rows;
  const auto result =
      reconciliation::reconcile(rows.id, rows.producers, rows.consumers, rows.mapping);
  ASSERT_EQ(result.status, protocol::JoinStatus::passed);
  EXPECT_TRUE(result.issues.empty());
  ASSERT_EQ(result.joined_rows.size(), 3U);
  EXPECT_EQ(result.accepted_rows, 3U);
  EXPECT_EQ(result.full_rows, 1U);
  EXPECT_EQ(result.joined_rows[0].record_index, result.joined_rows[1].record_index);
  EXPECT_EQ(result.joined_rows[0].accepted_ordinal, 0U);
  EXPECT_EQ(result.joined_rows[1].accepted_ordinal, 1U);
  EXPECT_EQ(result.joined_rows[2].accepted_ordinal, 2U);
  EXPECT_EQ(result.joined_rows[0].end_to_end_latency,
            result.joined_rows[0].admission_delay +
                result.joined_rows[0].queue_residence +
                result.joined_rows[0].post_dequeue_delivery_interval);
}

TEST(Reconciliation, EmptyScheduleJoinsExactly) {
  const auto id = run_id();
  const auto result = reconciliation::reconcile(id, {}, {}, {});
  EXPECT_EQ(result.status, protocol::JoinStatus::passed);
  EXPECT_TRUE(result.joined_rows.empty());
}

TEST(Reconciliation, LostFirstLastAndInternalConsumerRowsFail) {
  for (const std::size_t erased : std::array<std::size_t, 3>{0U, 1U, 2U}) {
    FixtureRows rows;
    rows.consumers.erase(rows.consumers.begin() + static_cast<std::ptrdiff_t>(erased));
    const auto result = reconciliation::reconcile(rows.id, rows.producers,
                                                  rows.consumers, rows.mapping);
    EXPECT_EQ(result.status, protocol::JoinStatus::failed);
    EXPECT_TRUE(result.joined_rows.empty());
    EXPECT_TRUE(has_failure(result, reconciliation::FailureClass::consumer_count));
  }
}

TEST(Reconciliation, DuplicateAndReorderedObservationsFail) {
  FixtureRows duplicate;
  duplicate.consumers.insert(duplicate.consumers.begin() + 1,
                             duplicate.consumers.front());
  auto result = reconciliation::reconcile(duplicate.id, duplicate.producers,
                                          duplicate.consumers, duplicate.mapping);
  EXPECT_EQ(result.status, protocol::JoinStatus::failed);
  EXPECT_TRUE(has_failure(result, reconciliation::FailureClass::consumer_count));
  EXPECT_TRUE(has_failure(result, reconciliation::FailureClass::consumer_ordinal));

  FixtureRows reordered;
  std::swap(reordered.consumers[0], reordered.consumers[1]);
  result = reconciliation::reconcile(reordered.id, reordered.producers,
                                     reordered.consumers, reordered.mapping);
  EXPECT_EQ(result.status, protocol::JoinStatus::failed);
  EXPECT_TRUE(has_failure(result, reconciliation::FailureClass::consumer_ordinal));

  FixtureRows corrupted;
  corrupted.consumers[2].observed_record_index = 0U;
  result = reconciliation::reconcile(corrupted.id, corrupted.producers,
                                     corrupted.consumers, corrupted.mapping);
  EXPECT_TRUE(has_failure(result, reconciliation::FailureClass::consumer_record_index));
}

TEST(Reconciliation, MalformedProducerOrdinalsAndMappingFail) {
  FixtureRows rows;
  rows.producers[2].accepted_ordinal = 0U;
  rows.producers[3].record_index = 0U;
  const auto result =
      reconciliation::reconcile(rows.id, rows.producers, rows.consumers, rows.mapping);
  EXPECT_EQ(result.status, protocol::JoinStatus::failed);
  EXPECT_TRUE(has_failure(result, reconciliation::FailureClass::accepted_ordinal));
  EXPECT_TRUE(
      has_failure(result, reconciliation::FailureClass::producer_record_mapping));
  EXPECT_TRUE(result.joined_rows.empty());
}

TEST(Reconciliation, WrongRunIdentityAndOutcomeShapeFail) {
  FixtureRows rows;
  const auto other = run_id("other-run");
  rows.producers[0].run_id = other;
  rows.consumers[0].run_id = other;
  rows.producers[1].accepted_ordinal = 7U;
  rows.producers[1].enqueue_linearization = 149U;
  const auto result =
      reconciliation::reconcile(rows.id, rows.producers, rows.consumers, rows.mapping);
  EXPECT_EQ(result.status, protocol::JoinStatus::failed);
  EXPECT_TRUE(has_failure(result, reconciliation::FailureClass::producer_run_identity));
  EXPECT_TRUE(has_failure(result, reconciliation::FailureClass::consumer_run_identity));
  EXPECT_TRUE(
      has_failure(result, reconciliation::FailureClass::producer_outcome_shape));
  EXPECT_TRUE(result.joined_rows.empty());
}

TEST(Reconciliation, ProducerLossAndNoncontiguousLogicalSequenceFail) {
  FixtureRows rows;
  rows.producers.erase(rows.producers.begin() + 1);
  const auto result =
      reconciliation::reconcile(rows.id, rows.producers, rows.consumers, rows.mapping);
  EXPECT_EQ(result.status, protocol::JoinStatus::failed);
  EXPECT_TRUE(has_failure(result, reconciliation::FailureClass::producer_count));
  EXPECT_TRUE(
      has_failure(result, reconciliation::FailureClass::producer_logical_sequence));
  EXPECT_TRUE(result.joined_rows.empty());
}

TEST(Reconciliation, CorruptedTimestampPreventsEveryDerivedRow) {
  FixtureRows rows;
  rows.consumers[2].consumer_action_completion =
      rows.consumers[2].dequeue_completion - 1U;
  const auto result =
      reconciliation::reconcile(rows.id, rows.producers, rows.consumers, rows.mapping);
  EXPECT_EQ(result.status, protocol::JoinStatus::failed);
  EXPECT_TRUE(has_failure(result, reconciliation::FailureClass::timestamp_order));
  EXPECT_TRUE(result.joined_rows.empty());
}

TEST(RunStatus, FullIsValidButFailsOnlyZeroLoss) {
  reconciliation::RunStatusInput input;
  input.lifecycle_state = protocol::LifecycleState::completed;
  input.join_status = protocol::JoinStatus::passed;
  input.counts = complete_counts(1U, 250000U);
  input.block_completeness = {protocol::BlockCompleteness::complete, true};
  input.access_integrity = {protocol::GateStatus::pass, true};
  const auto status = reconciliation::evaluate_run_status(input);
  ASSERT_TRUE(status);
  EXPECT_EQ(status.value().validity, protocol::RunValidity::valid);
  EXPECT_EQ(status.value().count_reconciliation, protocol::GateStatus::pass);
  EXPECT_EQ(status.value().zero_loss, protocol::GateStatus::fail);
  EXPECT_EQ(status.value().effective_tail, protocol::GateStatus::pass);
  ASSERT_EQ(status.value().confirmatory_blockers.size(), 1U);
  EXPECT_EQ(status.value().confirmatory_blockers.front(),
            protocol::ConfirmatoryBlocker::blocked_zero_loss);
  EXPECT_EQ(status.value().confirmatory_estimability,
            protocol::ConfirmatoryEstimability::blocked_zero_loss);
}

TEST(RunStatus, GenuineLowEffectiveCountIsValidAndRetained) {
  reconciliation::RunStatusInput input;
  input.lifecycle_state = protocol::LifecycleState::completed;
  input.join_status = protocol::JoinStatus::passed;
  input.counts = complete_counts(0U, 199999U);
  input.block_completeness = {protocol::BlockCompleteness::complete, true};
  input.access_integrity = {protocol::GateStatus::pass, true};
  const auto status = reconciliation::evaluate_run_status(input);
  ASSERT_TRUE(status);
  EXPECT_EQ(status.value().validity, protocol::RunValidity::valid);
  EXPECT_EQ(status.value().effective_tail, protocol::GateStatus::fail);
  EXPECT_EQ(status.value().confirmatory_estimability,
            protocol::ConfirmatoryEstimability::blocked_effective_tail);
}

TEST(RunStatus, SimultaneousBlockersAreExhaustiveSortedAndNonPriority) {
  reconciliation::RunStatusInput input;
  input.lifecycle_state = protocol::LifecycleState::completed;
  input.join_status = protocol::JoinStatus::failed;
  input.counts = complete_counts(1U, 100U);
  input.invalidating_failure_record_present = true;
  input.block_completeness = {protocol::BlockCompleteness::incomplete, true};
  input.access_integrity = {protocol::GateStatus::fail, true};
  const auto status = reconciliation::evaluate_run_status(input);
  ASSERT_TRUE(status);
  EXPECT_EQ(status.value().validity, protocol::RunValidity::invalid);
  EXPECT_EQ(status.value().confirmatory_estimability,
            protocol::ConfirmatoryEstimability::blocked_multiple);
  const std::vector expected{protocol::ConfirmatoryBlocker::blocked_access_leakage,
                             protocol::ConfirmatoryBlocker::blocked_effective_tail,
                             protocol::ConfirmatoryBlocker::blocked_incomplete_block,
                             protocol::ConfirmatoryBlocker::blocked_invalid_run,
                             protocol::ConfirmatoryBlocker::blocked_zero_loss};
  EXPECT_EQ(status.value().confirmatory_blockers, expected);
}

TEST(RunStatus, Stage14EvidenceMustBeAuthoritativeBeforeFinalDisposition) {
  reconciliation::RunStatusInput input;
  input.lifecycle_state = protocol::LifecycleState::completed;
  input.join_status = protocol::JoinStatus::passed;
  input.counts = complete_counts(0U, 250000U);
  const auto status = reconciliation::evaluate_run_status(input);
  ASSERT_TRUE(status);
  EXPECT_EQ(status.value().validity, protocol::RunValidity::valid);
  EXPECT_EQ(status.value().confirmatory_estimability,
            protocol::ConfirmatoryEstimability::not_evaluated);
  EXPECT_TRUE(status.value().confirmatory_blockers.empty());
}

TEST(RunStatus, InvalidityWithoutFailureEvidenceIsRejected) {
  reconciliation::RunStatusInput input;
  input.lifecycle_state = protocol::LifecycleState::completed;
  input.join_status = protocol::JoinStatus::failed;
  input.counts = complete_counts(0U, 250000U);
  const auto status = reconciliation::evaluate_run_status(input);
  ASSERT_FALSE(status);
  EXPECT_EQ(status.errors().front().rule_id, "REC-INVALID-FAILURE-EVIDENCE");
}

TEST(JoinAudit, PassedAndFailedArtifactsAreMutuallyExclusive) {
  FixtureRows rows;
  const auto passed =
      reconciliation::reconcile(rows.id, rows.producers, rows.consumers, rows.mapping);
  const protocol::ArtifactReference producer_ref{artifact_id("producer"), zero_hash()};
  const protocol::ArtifactReference consumer_ref{artifact_id("consumer"), zero_hash()};
  const protocol::ArtifactReference joined_ref{artifact_id("joined"), zero_hash()};
  auto audit = reconciliation::make_join_audit(
      rows.id, passed, {producer_ref, consumer_ref, joined_ref});
  ASSERT_TRUE(audit);
  EXPECT_NE(audit.value().find(R"("join_status":"PASSED")"), std::string::npos);
  EXPECT_NE(audit.value().find(R"("record_sha256":")"), std::string::npos);

  audit = reconciliation::make_join_audit(rows.id, passed,
                                          {producer_ref, consumer_ref, std::nullopt});
  EXPECT_FALSE(audit);

  rows.consumers.pop_back();
  const auto failed =
      reconciliation::reconcile(rows.id, rows.producers, rows.consumers, rows.mapping);
  audit = reconciliation::make_join_audit(rows.id, failed,
                                          {producer_ref, consumer_ref, std::nullopt});
  ASSERT_TRUE(audit);
  EXPECT_NE(audit.value().find(R"("join_status":"FAILED")"), std::string::npos);
  EXPECT_NE(audit.value().find(R"("joined_artifact":null)"), std::string::npos);
}

TEST(CrossRecordValidation, EmptySyntheticCompletedRunResolvesEveryRelationship) {
  const auto id = run_id("cross-run");
  const std::vector<std::byte> empty;
  const auto empty_sha = workload::sha256(empty).hex();
  const auto empty_protocol_sha = protocol_hash(empty);
  const auto empty_digest = workload::sha256(empty);

  const auto integrity_document = storage::make_phase_integrity_document(
      {"integrity", std::string(id.value()), workload::ConsumerState{0U}, empty_digest,
       empty_digest, empty_digest, empty_digest});
  ASSERT_TRUE(integrity_document);
  const auto integrity_sha =
      std::move(protocol::Sha256::parse(integrity_document.value().sha256,
                                        "$test/integrity_hash"))
          .value();
  const protocol::ArtifactReference integrity_ref{
      identifier<protocol::ArtifactId>("integrity"), integrity_sha};

  auto make_raw = [&](protocol::StreamKind kind, std::string artifact,
                      std::vector<storage::ArtifactRefText> sources = {}) {
    return storage::make_external_raw_envelope(
        {std::move(artifact),
         std::string(id.value()),
         kind,
         "/synthetic",
         0U,
         0U,
         empty_sha,
         {std::string(integrity_ref.artifact_id.value()), integrity_ref.sha256.hex()},
         std::move(sources)});
  };
  auto producer_envelope = make_raw(protocol::StreamKind::producer, "producer");
  auto consumer_envelope = make_raw(protocol::StreamKind::consumer, "consumer");
  ASSERT_TRUE(producer_envelope);
  ASSERT_TRUE(consumer_envelope);
  const protocol::ArtifactReference producer_ref{
      producer_envelope.value().envelope.artifact_id,
      producer_envelope.value().envelope.artifact_sha256};
  const protocol::ArtifactReference consumer_ref{
      consumer_envelope.value().envelope.artifact_id,
      consumer_envelope.value().envelope.artifact_sha256};
  auto joined_envelope = make_raw(
      protocol::StreamKind::joined_derived, "joined",
      {{std::string(producer_ref.artifact_id.value()), producer_ref.sha256.hex()},
       {std::string(consumer_ref.artifact_id.value()), consumer_ref.sha256.hex()}});
  ASSERT_TRUE(joined_envelope);
  const protocol::ArtifactReference joined_ref{
      joined_envelope.value().envelope.artifact_id,
      joined_envelope.value().envelope.artifact_sha256};

  const auto joined = reconciliation::reconcile(id, {}, {}, {});
  const auto audit = reconciliation::make_join_audit(
      id, joined, {producer_ref, consumer_ref, joined_ref});
  ASSERT_TRUE(audit);
  const protocol::ArtifactReference audit_ref{
      identifier<protocol::ArtifactId>("join-audit"),
      protocol_hash(string_bytes(audit.value()))};

  const std::string provenance_text =
      R"({"protocol_version":"2.0.0-pre.1","queue_id":"queue-provenance","schema_version":"cpu-prefetch-queue-provenance/1"})";
  const auto provenance_bytes = string_bytes(provenance_text);
  const protocol::ArtifactReference provenance_ref{
      identifier<protocol::ArtifactId>("provenance"), protocol_hash(provenance_bytes)};
  const protocol::ArtifactReference measurement_ref{
      identifier<protocol::ArtifactId>("measurement-schedule"), empty_protocol_sha};
  const protocol::ArtifactReference warmup_ref{
      identifier<protocol::ArtifactId>("warmup-schedule"), empty_protocol_sha};

  auto schedule =
      [&](std::string_view schedule_name, protocol::ScheduleKind kind,
          const protocol::ArtifactReference& artifact) -> protocol::ScheduleRecord {
    return {protocol::ProtocolVersion::v2_0_0_pre_2,
            protocol::ProtocolVersion::v2_0_0_pre_2,
            identifier<protocol::ScheduleId>(schedule_name),
            kind,
            protocol::ArrivalFamily::poisson_exponential,
            identifier<protocol::NamespaceId>(kind == protocol::ScheduleKind::warmup
                                                  ? "warmup-namespace"
                                                  : "measurement-namespace"),
            {"fixture-rng", "1", identifier<protocol::SeedId>("seed"),
             identifier<protocol::RecordId>("derivation"),
             identifier<protocol::NamespaceId>("parent")},
            "ps",
            protocol::DeadlineEncoding::absolute_integer_ticks,
            0U,
            1U,
            0U,
            {1U, 1U},
            identifier<protocol::RecordId>("overflow"),
            protocol::ExternalScheduleStorage{
                artifact.artifact_id, "/synthetic-schedule", 0U, 0U, artifact.sha256},
            zero_hash(),
            zero_hash(),
            protocol::json::Value(protocol::json::Value::Object{})};
  };
  auto measurement_schedule =
      schedule("measurement", protocol::ScheduleKind::confirmatory, measurement_ref);
  auto warmup_schedule = schedule("warmup", protocol::ScheduleKind::warmup, warmup_ref);

  const protocol::PhaseIntegrityRecord integrity{
      integrity_ref,
      {identifier<protocol::RecordId>(storage::kConsumerMixerRecordId), "1",
       "0000000000000000"},
      {identifier<protocol::RecordId>(storage::kContentChecksumRecordId), "1",
       empty_sha},
      {identifier<protocol::RecordId>(storage::kContentChecksumRecordId), "1",
       empty_sha},
      {identifier<protocol::RecordId>(storage::kOrderedIndexChecksumRecordId), "1",
       empty_sha},
      {identifier<protocol::RecordId>(storage::kAddressDeltaChecksumRecordId), "1",
       empty_sha}};
  protocol::json::Value::Object manifest_source;
  manifest_source.emplace("manifest_sha256",
                          protocol::json::Value(std::string(64U, '0')));
  const auto zeroed_manifest =
      protocol::json::canonicalize(protocol::json::Value(manifest_source));
  ASSERT_TRUE(zeroed_manifest);
  const auto manifest_sha = protocol_hash(string_bytes(zeroed_manifest.value()));
  manifest_source["manifest_sha256"] = protocol::json::Value(manifest_sha.hex());

  protocol::RunManifest manifest{
      protocol::ProtocolVersion::v2_0_0_pre_2,
      protocol::ProtocolVersion::v2_0_0_pre_2,
      id,
      identifier<protocol::PlatformId>("platform"),
      identifier<protocol::BuildId>("build"),
      0U,
      identifier<protocol::RecordId>("queue-provenance"),
      {"paper",
       "implementation",
       zero_hash(),
       "compiler",
       {},
       "stdlib",
       identifier<protocol::RecordId>("dependencies")},
      protocol::Stage::stage_a,
      protocol::RunMode::latency,
      protocol::LifecycleState::completed,
      identifier<protocol::BlockId>("block"),
      protocol::BlockRole::h3_train,
      protocol::QueuePackage::r0,
      protocol::RequestedHardwareState::h0,
      protocol::VerifiedHardwareState::verified_default,
      protocol::Placement::near,
      protocol::WorkingSetClass::l2_resident,
      protocol::LoadLevel::l025,
      1U,
      "PICOSECONDS",
      {measurement_ref, warmup_ref},
      {identifier<protocol::SeedId>("arrival"), std::nullopt,
       identifier<protocol::SeedId>("event"),
       identifier<protocol::SeedId>("warmup-seed"),
       identifier<protocol::RecordId>("seed-derivation")},
      protocol::RunValidity::valid,
      protocol::GateStatus::pass,
      protocol::GateStatus::pass,
      protocol::GateStatus::fail,
      protocol::ConfirmatoryEstimability::not_evaluated,
      {},
      protocol::BlockCompleteness::not_evaluated,
      protocol::JoinStatus::passed,
      protocol::RunCounts{0U, 0U, 0U, 0U, 0U, 0U, 0U, n_eff(0U)},
      integrity,
      {},
      {{producer_ref, protocol::ArtifactRelationship::producer_raw},
       {consumer_ref, protocol::ArtifactRelationship::consumer_raw},
       {audit_ref, protocol::ArtifactRelationship::join_audit},
       {joined_ref, protocol::ArtifactRelationship::joined_derived},
       {integrity_ref, protocol::ArtifactRelationship::phase_integrity_report},
       {measurement_ref, protocol::ArtifactRelationship::schedule},
       {provenance_ref, protocol::ArtifactRelationship::provenance}},
      manifest_sha,
      protocol::json::Value(std::move(manifest_source))};

  std::vector<protocol::ProtocolRecord> records;
  records.emplace_back(measurement_schedule);
  records.emplace_back(warmup_schedule);
  records.emplace_back(producer_envelope.value().envelope);
  records.emplace_back(consumer_envelope.value().envelope);
  records.emplace_back(joined_envelope.value().envelope);
  records.emplace_back(manifest);
  const auto integrity_bytes = string_bytes(integrity_document.value().bytes);
  const auto audit_bytes = string_bytes(audit.value());
  const std::vector<reconciliation::ArtifactBytes> artifacts{
      {producer_ref.artifact_id, empty},
      {consumer_ref.artifact_id, empty},
      {joined_ref.artifact_id, empty},
      {integrity_ref.artifact_id, integrity_bytes},
      {audit_ref.artifact_id, audit_bytes},
      {measurement_ref.artifact_id, empty},
      {warmup_ref.artifact_id, empty},
      {provenance_ref.artifact_id, provenance_bytes}};
  const reconciliation::RunEvidence run_evidence{
      id, std::span<const std::uint64_t>{},
      reconciliation::AuthoritativeBlockCompleteness{},
      reconciliation::AuthoritativeGate{}};
  const std::array evidence{run_evidence};
  reconciliation::Stage12CrossRecordSemanticValidator validator(artifacts, evidence);
  const auto errors = validator.validate({records});
  EXPECT_TRUE(errors.empty()) << (errors.empty() ? ""
                                                 : errors.front().rule_id + ": " +
                                                       errors.front().message);

  auto corrupted_provenance_storage =
      std::vector<std::byte>(provenance_bytes.begin(), provenance_bytes.end());
  corrupted_provenance_storage[0] ^= std::byte{1};
  auto corrupt_artifacts = artifacts;
  corrupt_artifacts.back().bytes = corrupted_provenance_storage;
  reconciliation::Stage12CrossRecordSemanticValidator corrupt_validator(
      corrupt_artifacts, evidence);
  const auto corrupt_errors = corrupt_validator.validate({records});
  EXPECT_TRUE(std::ranges::any_of(corrupt_errors, [](const auto& error) {
    return error.rule_id == "REC-ARTIFACT-HASH";
  }));

  auto missing_envelope_records = records;
  missing_envelope_records.erase(missing_envelope_records.begin() + 3);
  const auto missing_errors = validator.validate({missing_envelope_records});
  EXPECT_TRUE(std::ranges::any_of(missing_errors, [](const auto& error) {
    return error.rule_id == "REC-RAW-ENVELOPE";
  }));

  auto duplicate_artifacts = artifacts;
  duplicate_artifacts.push_back(artifacts.front());
  reconciliation::Stage12CrossRecordSemanticValidator duplicate_validator(
      duplicate_artifacts, evidence);
  const auto duplicate_errors = duplicate_validator.validate({records});
  EXPECT_TRUE(std::ranges::any_of(duplicate_errors, [](const auto& error) {
    return error.rule_id == "REC-DUPLICATE-ARTIFACT-ID";
  }));

  auto wrong_sources = records;
  std::get<protocol::RawObservationEnvelope>(wrong_sources[4]).source_artifacts.clear();
  const auto source_errors = validator.validate({wrong_sources});
  EXPECT_TRUE(std::ranges::any_of(source_errors, [](const auto& error) {
    return error.rule_id == "REC-JOINED-SOURCES";
  }));

  auto mixed_versions = records;
  std::get<protocol::ScheduleRecord>(mixed_versions.front()).protocol_version =
      protocol::ProtocolVersion::v2_0_0_pre_1;
  const auto version_errors = validator.validate({mixed_versions});
  EXPECT_TRUE(std::ranges::any_of(version_errors, [](const auto& error) {
    return error.rule_id == "REC-PRE2-REQUIRED";
  }));

  mixed_versions = records;
  std::get<protocol::ScheduleRecord>(mixed_versions.front()).schema_version =
      protocol::ProtocolVersion::v2_0_0_pre_1;
  const auto schema_version_errors = validator.validate({mixed_versions});
  EXPECT_TRUE(std::ranges::any_of(schema_version_errors, [](const auto& error) {
    return error.rule_id == "REC-PRE2-REQUIRED";
  }));

  const std::array<std::byte, 1> failure_evidence_bytes{std::byte{0x33}};
  const protocol::ArtifactReference failure_evidence_ref{
      identifier<protocol::ArtifactId>("failure-evidence"),
      protocol_hash(failure_evidence_bytes)};
  auto [failure_source, failure_sha] = self_hashed_document("record_sha256");
  protocol::FailureRecord failure{protocol::ProtocolVersion::v2_0_0_pre_2,
                                  protocol::ProtocolVersion::v2_0_0_pre_2,
                                  identifier<protocol::RecordId>("failure"),
                                  identifier<protocol::PlatformId>("platform"),
                                  protocol::Stage::stage_a,
                                  protocol::FailureScope::run,
                                  id,
                                  identifier<protocol::BlockId>("block"),
                                  identifier<protocol::BuildId>("build"),
                                  protocol::FailureCategory::correctness,
                                  protocol::DetectedPhase::pre_run,
                                  "2026-08-21T00:00:00Z",
                                  "synthetic pre-run failure",
                                  true,
                                  protocol::BlockConsequence::original_block_incomplete,
                                  protocol::ResolutionStatus::open,
                                  std::nullopt,
                                  std::nullopt,
                                  std::nullopt,
                                  {failure_evidence_ref},
                                  failure_sha,
                                  std::move(failure_source)};

  auto partial_manifest = manifest;
  partial_manifest.lifecycle_state = protocol::LifecycleState::pre_run_failure;
  partial_manifest.validity = protocol::RunValidity::invalid;
  partial_manifest.count_reconciliation = protocol::GateStatus::not_evaluated;
  partial_manifest.zero_loss_status = protocol::GateStatus::not_evaluated;
  partial_manifest.effective_tail_status = protocol::GateStatus::not_evaluated;
  partial_manifest.confirmatory_estimability =
      protocol::ConfirmatoryEstimability::not_evaluated;
  partial_manifest.confirmatory_blockers.clear();
  partial_manifest.block_completeness = protocol::BlockCompleteness::incomplete;
  partial_manifest.join_status = protocol::JoinStatus::not_attempted;
  partial_manifest.counts.reset();
  partial_manifest.integrity_evidence.reset();
  partial_manifest.failure_record_ids = {failure.failure_record_id};
  partial_manifest.artifact_refs.clear();
  auto [partial_source, partial_sha] = self_hashed_document("manifest_sha256");
  partial_manifest.source_document = std::move(partial_source);
  partial_manifest.manifest_sha256 = partial_sha;

  const std::array<protocol::ProtocolRecord, 4> partial_records{
      measurement_schedule, warmup_schedule, failure, partial_manifest};
  const std::array<reconciliation::ArtifactBytes, 3> partial_artifacts{{
      {measurement_ref.artifact_id, empty},
      {warmup_ref.artifact_id, empty},
      {failure_evidence_ref.artifact_id, failure_evidence_bytes},
  }};
  const reconciliation::RunEvidence partial_run_evidence{
      id,
      std::span<const std::uint64_t>{},
      {protocol::BlockCompleteness::incomplete, true},
      reconciliation::AuthoritativeGate{}};
  const std::array partial_evidence{partial_run_evidence};
  reconciliation::Stage12CrossRecordSemanticValidator partial_validator(
      partial_artifacts, partial_evidence);
  const auto partial_errors = partial_validator.validate({partial_records});
  EXPECT_TRUE(partial_errors.empty())
      << (partial_errors.empty()
              ? ""
              : partial_errors.front().rule_id + ": " + partial_errors.front().message);
}

} // namespace
