#include "cpu_prefetch/storage/artifacts.hpp"

#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <array>
#include <iomanip>
#include <set>
#include <sstream>
#include <utility>

namespace cpu_prefetch::storage {
namespace {

using JsonObject = protocol::json::Value::Object;
using JsonArray = protocol::json::Value::Array;

struct ChecksumInput final {
  std::string_view algorithm_record_id;
  std::string_view value_hex;
};

[[nodiscard]] auto string_value(std::string_view value) -> protocol::json::Value {
  return protocol::json::Value(std::string(value));
}

[[nodiscard]] auto uint_value(std::uint64_t value) -> protocol::json::Value {
  return protocol::json::Value(protocol::json::Number{
      protocol::json::Number::Kind::unsigned_integer, std::to_string(value), value});
}

[[nodiscard]] auto artifact_ref_value(const ArtifactRefText& reference)
    -> protocol::json::Value {
  JsonObject object;
  object.emplace("artifact_id", string_value(reference.artifact_id));
  object.emplace("sha256", string_value(reference.sha256));
  return protocol::json::Value(std::move(object));
}

[[nodiscard]] auto checksum_value(const ChecksumInput& input) -> protocol::json::Value {
  JsonObject object;
  object.emplace("algorithm_record_id", string_value(input.algorithm_record_id));
  object.emplace("algorithm_version", string_value(kChecksumAlgorithmVersion));
  object.emplace("value_hex", string_value(input.value_hex));
  return protocol::json::Value(std::move(object));
}

template <typename T>
[[nodiscard]] auto fail(protocol::ErrorCategory category, std::string path,
                        std::string rule, std::string message) -> protocol::Result<T> {
  return protocol::Result<T>::failure(
      {category, std::move(path), std::move(rule), std::move(message)});
}

[[nodiscard]] auto canonical_document(const protocol::json::Value& value)
    -> protocol::Result<CanonicalDocument> {
  auto canonical = protocol::json::canonicalize(value);
  if (!canonical) {
    return protocol::Result<CanonicalDocument>::failure(canonical.errors());
  }
  const auto& bytes = canonical.value();
  const auto digest = workload::sha256(std::span<const std::byte>(
      reinterpret_cast<const std::byte*>(bytes.data()), bytes.size()));
  return protocol::Result<CanonicalDocument>::success({bytes, digest.hex()});
}

[[nodiscard]] auto valid_sha256(std::string_view value) noexcept -> bool {
  if (value.size() != 64U) {
    return false;
  }
  for (const char character : value) {
    if (!((character >= '0' && character <= '9') ||
          (character >= 'a' && character <= 'f'))) {
      return false;
    }
  }
  return true;
}

[[nodiscard]] auto nonempty(std::initializer_list<std::string_view> values) noexcept
    -> bool {
  for (const auto value : values) {
    if (value.empty()) {
      return false;
    }
  }
  return true;
}

[[nodiscard]] auto consumer_state_hex(std::uint64_t value) -> std::string {
  std::ostringstream output;
  output << std::hex << std::nouppercase << std::setfill('0') << std::setw(16) << value;
  return output.str();
}

[[nodiscard]] auto stream_kind_string(protocol::StreamKind kind) noexcept
    -> std::string_view {
  switch (kind) {
  case protocol::StreamKind::producer:
    return "PRODUCER";
  case protocol::StreamKind::consumer:
    return "CONSUMER";
  case protocol::StreamKind::joined_derived:
    return "JOINED_DERIVED";
  }
  return "UNKNOWN";
}

} // namespace

auto make_phase_integrity_document(const PhaseIntegrityInput& input)
    -> protocol::Result<CanonicalDocument> {
  if (!nonempty({input.artifact_id, input.run_id})) {
    return fail<CanonicalDocument>(protocol::ErrorCategory::invalid_id, "$input",
                                   "STO-INTEGRITY-ID",
                                   "integrity artifact and run IDs must be nonempty");
  }
  JsonObject object;
  object.emplace(
      "address_delta_checksum",
      checksum_value({kAddressDeltaChecksumRecordId, input.address_delta.hex()}));
  object.emplace(
      "event_records_post_checksum",
      checksum_value({kContentChecksumRecordId, input.event_records_post.hex()}));
  object.emplace(
      "event_records_pre_checksum",
      checksum_value({kContentChecksumRecordId, input.event_records_pre.hex()}));
  object.emplace(
      "final_consumer_rolling_checksum",
      checksum_value({kConsumerMixerRecordId,
                      consumer_state_hex(input.final_consumer_state.value)}));
  object.emplace(
      "ordered_index_checksum",
      checksum_value({kOrderedIndexChecksumRecordId, input.ordered_index.hex()}));
  object.emplace("artifact_id", string_value(input.artifact_id));
  object.emplace(
      "content_checksum_match",
      protocol::json::Value(input.event_records_pre == input.event_records_post));
  object.emplace("protocol_version", string_value(protocol::kProtocolVersion));
  object.emplace("record_kind", string_value("PHASE_INTEGRITY_REPORT"));
  object.emplace("run_id", string_value(input.run_id));
  object.emplace("schema_version", string_value(kPhaseIntegritySchema));
  return canonical_document(protocol::json::Value(std::move(object)));
}

auto make_external_raw_envelope(const RawEnvelopeInput& input)
    -> protocol::Result<RawEnvelopeDocument> {
  if (!nonempty({input.artifact_id, input.run_id, input.artifact_uri,
                 input.integrity_artifact.artifact_id})) {
    return fail<RawEnvelopeDocument>(
        protocol::ErrorCategory::invalid_id, "$input", "RAW-ENVELOPE-ID",
        "raw artifact, run, URI, and integrity artifact IDs must be nonempty");
  }
  if (!valid_sha256(input.artifact_sha256) ||
      !valid_sha256(input.integrity_artifact.sha256)) {
    return fail<RawEnvelopeDocument>(protocol::ErrorCategory::invalid_hash, "$input",
                                     "RAW-ENVELOPE-SHA256",
                                     "raw and integrity references require SHA-256");
  }
  if (input.stream_kind != protocol::StreamKind::joined_derived &&
      !input.source_artifacts.empty()) {
    return fail<RawEnvelopeDocument>(
        protocol::ErrorCategory::cross_field, "$input/source_artifacts",
        "RAW-ENVELOPE-SOURCES",
        "only joined-derived envelopes may name source artifacts");
  }
  if (input.stream_kind == protocol::StreamKind::joined_derived &&
      input.source_artifacts.size() < 2U) {
    return fail<RawEnvelopeDocument>(
        protocol::ErrorCategory::missing_evidence, "$input/source_artifacts",
        "RAW-ENVELOPE-SOURCES",
        "joined-derived envelopes require at least two source artifacts");
  }
  for (const auto& source : input.source_artifacts) {
    if (!nonempty({source.artifact_id}) || !valid_sha256(source.sha256)) {
      return fail<RawEnvelopeDocument>(
          protocol::ErrorCategory::invalid_hash, "$input/source_artifacts",
          "RAW-ENVELOPE-SOURCE-SHA256", "source artifact reference is invalid");
    }
  }

  JsonObject storage;
  storage.emplace("artifact_uri", string_value(input.artifact_uri));
  storage.emplace("mode", string_value("EXTERNAL_IMMUTABLE_ARTIFACT"));
  JsonObject object;
  object.emplace("artifact_id", string_value(input.artifact_id));
  object.emplace("artifact_sha256", string_value(input.artifact_sha256));
  object.emplace("byte_count", uint_value(input.byte_count));
  object.emplace("compression", string_value(kRawCompression));
  object.emplace("encoding", string_value(kRawEncoding));
  object.emplace("endianness", string_value(kRawEndianness));
  object.emplace("immutable_ordering", protocol::json::Value(true));
  object.emplace("integrity_artifact_ref",
                 artifact_ref_value(input.integrity_artifact));
  object.emplace("logical_row_schema_version",
                 string_value(protocol::kLogicalRowSchemaVersion));
  object.emplace("physical_format_record_id", string_value(kRawFormatId));
  object.emplace("protocol_version", string_value(protocol::kProtocolVersion));
  object.emplace("row_count", uint_value(input.row_count));
  object.emplace("run_id", string_value(input.run_id));
  object.emplace("schema_version", string_value(protocol::kProtocolVersion));
  if (!input.source_artifacts.empty()) {
    JsonArray sources;
    sources.reserve(input.source_artifacts.size());
    for (const auto& source : input.source_artifacts) {
      sources.push_back(artifact_ref_value(source));
    }
    object.emplace("source_artifacts", protocol::json::Value(std::move(sources)));
  }
  object.emplace("storage", protocol::json::Value(std::move(storage)));
  object.emplace("stream_kind", string_value(stream_kind_string(input.stream_kind)));
  object.emplace("time_unit", string_value(kRawTimeUnit));

  auto document = canonical_document(protocol::json::Value(std::move(object)));
  if (!document) {
    return protocol::Result<RawEnvelopeDocument>::failure(document.errors());
  }
  auto loaded = protocol::load_document(protocol::DocumentKind::raw_observation,
                                        document.value().bytes);
  if (!loaded) {
    return protocol::Result<RawEnvelopeDocument>::failure(loaded.errors());
  }
  const auto* envelope = std::get_if<protocol::RawObservationEnvelope>(&loaded.value());
  if (envelope == nullptr) {
    return fail<RawEnvelopeDocument>(
        protocol::ErrorCategory::invalid_type, "$out", "RAW-ENVELOPE-TYPE",
        "raw envelope loader returned another record type");
  }
  return protocol::Result<RawEnvelopeDocument>::success({document.value(), *envelope});
}

auto to_string(CopyFinalizationState state) noexcept -> std::string_view {
  switch (state) {
  case CopyFinalizationState::incomplete:
    return "INCOMPLETE";
  case CopyFinalizationState::sealed_complete:
    return "SEALED_COMPLETE";
  }
  return "UNKNOWN";
}

auto make_copy_ledger_document(const CopyLedgerInput& input)
    -> protocol::Result<CanonicalDocument> {
  if (!nonempty({input.ledger_record_id, input.run_id, input.object_id,
                 input.object_role, input.artifact_id}) ||
      !valid_sha256(input.sha256)) {
    return fail<CanonicalDocument>(protocol::ErrorCategory::invalid_id, "$input",
                                   "STO-LEDGER-IDENTITY",
                                   "copy ledger identity or SHA-256 is invalid");
  }
  if (input.stream_completeness == StreamCompleteness::writing) {
    return fail<CanonicalDocument>(protocol::ErrorCategory::cross_field,
                                   "$input/stream_completeness", "STO-LEDGER-WRITING",
                                   "a writable stream cannot enter the copy ledger");
  }
  std::set<std::string> domain_ids;
  std::size_t verified_count = 0U;
  JsonArray copies;
  copies.reserve(input.copies.size());
  for (const auto& copy : input.copies) {
    if (!nonempty({copy.storage_domain_id, copy.artifact_uri, copy.verified_at}) ||
        !valid_sha256(copy.observed_sha256) ||
        !domain_ids.insert(copy.storage_domain_id).second) {
      return fail<CanonicalDocument>(
          protocol::ErrorCategory::duplicate_value, "$input/copies", "STO-LEDGER-COPY",
          "copy evidence is incomplete or repeats a domain ID");
    }
    if (copy.verified && (!copy.independently_read_back ||
                          copy.observed_byte_count != input.byte_count ||
                          copy.observed_sha256 != input.sha256)) {
      return fail<CanonicalDocument>(protocol::ErrorCategory::reference_mismatch,
                                     "$input/copies", "STO-LEDGER-VERIFIED-IDENTITY",
                                     "a verified copy must be independently read back "
                                     "and exactly match size and SHA-256");
    }
    verified_count += copy.verified ? 1U : 0U;
    JsonObject object;
    object.emplace("artifact_uri", string_value(copy.artifact_uri));
    object.emplace("independently_read_back",
                   protocol::json::Value(copy.independently_read_back));
    object.emplace("observed_byte_count", uint_value(copy.observed_byte_count));
    object.emplace("observed_sha256", string_value(copy.observed_sha256));
    object.emplace("storage_domain_id", string_value(copy.storage_domain_id));
    object.emplace("verification_result",
                   string_value(copy.verified ? "PASS" : "FAIL"));
    object.emplace("verified_at", string_value(copy.verified_at));
    copies.emplace_back(std::move(object));
  }
  if (input.finalization_state == CopyFinalizationState::sealed_complete &&
      (input.stream_completeness != StreamCompleteness::sealed_complete ||
       input.copies.size() != 2U || verified_count != 2U || !input.failures.empty())) {
    return fail<CanonicalDocument>(
        protocol::ErrorCategory::cross_field, "$input/finalization_state",
        "STO-LEDGER-SEAL",
        "sealed complete requires a complete stream and exactly two verified domains");
  }
  if (input.finalization_state == CopyFinalizationState::incomplete &&
      input.failures.empty() &&
      input.stream_completeness == StreamCompleteness::sealed_complete &&
      input.copies.size() == 2U && verified_count == 2U) {
    return fail<CanonicalDocument>(
        protocol::ErrorCategory::cross_field, "$input/finalization_state",
        "STO-LEDGER-INCOMPLETE",
        "a fully verified complete object cannot be mislabeled incomplete");
  }

  JsonArray failures;
  failures.reserve(input.failures.size());
  for (const auto& failure : input.failures) {
    if (failure.empty()) {
      return fail<CanonicalDocument>(protocol::ErrorCategory::invalid_id,
                                     "$input/failures", "STO-LEDGER-FAILURE",
                                     "failure evidence strings must be nonempty");
    }
    failures.push_back(string_value(failure));
  }
  JsonObject object;
  object.emplace("artifact_id", string_value(input.artifact_id));
  object.emplace("byte_count", uint_value(input.byte_count));
  object.emplace("compression", string_value(kRawCompression));
  object.emplace("copies", protocol::json::Value(std::move(copies)));
  object.emplace("failures", protocol::json::Value(std::move(failures)));
  object.emplace("finalization_state",
                 string_value(to_string(input.finalization_state)));
  object.emplace("ledger_record_id", string_value(input.ledger_record_id));
  object.emplace("object_id", string_value(input.object_id));
  object.emplace("object_role", string_value(input.object_role));
  object.emplace("policy_id", string_value(kDurabilityPolicyId));
  object.emplace("protocol_version", string_value(protocol::kProtocolVersion));
  object.emplace("run_id", string_value(input.run_id));
  object.emplace("schema_version", string_value(kCopyLedgerSchema));
  object.emplace("sha256", string_value(input.sha256));
  object.emplace("stream_completeness",
                 string_value(to_string(input.stream_completeness)));
  object.emplace("temporary_copy_count", uint_value(1U));
  object.emplace("required_durable_copy_count", uint_value(2U));
  return canonical_document(protocol::json::Value(std::move(object)));
}

} // namespace cpu_prefetch::storage
