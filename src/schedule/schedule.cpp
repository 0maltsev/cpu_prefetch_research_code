#include "cpu_prefetch/schedule/schedule.hpp"

#include <openssl/evp.h>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <numeric>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

#include "cpu_prefetch/protocol/json.hpp"

namespace cpu_prefetch::schedule {
namespace {

using protocol::ErrorCategory;
using protocol::ValidationError;

void add(std::vector<ValidationError>& errors, ErrorCategory category, std::string path,
         std::string rule, std::string message) {
  errors.push_back({category, std::move(path), std::move(rule), std::move(message)});
}

void append_u64_be(std::vector<std::byte>& output, std::uint64_t value) {
  for (unsigned int shift = 64U; shift != 0U; shift -= 8U) {
    output.push_back(static_cast<std::byte>((value >> (shift - 8U)) & 0xffU));
  }
}

void append_field(std::vector<std::byte>& output, std::span<const std::byte> value) {
  append_u64_be(output, static_cast<std::uint64_t>(value.size()));
  output.insert(output.end(), value.begin(), value.end());
}

void append_string_field(std::vector<std::byte>& output, std::string_view value) {
  append_field(output, std::as_bytes(std::span(value.data(), value.size())));
}

void append_integer_field(std::vector<std::byte>& output, std::uint64_t value) {
  std::array<std::byte, 8> encoded{};
  for (unsigned int index = 0; index < encoded.size(); ++index) {
    const auto shift = static_cast<unsigned int>(56U - (index * 8U));
    encoded[index] = static_cast<std::byte>((value >> shift) & 0xffU);
  }
  append_field(output, encoded);
}

auto sha256_hex(std::span<const std::byte> input) -> std::string {
  std::array<unsigned char, 32> output{};
  std::size_t output_size = 0U;
  const auto success = EVP_Q_digest(
      nullptr, "SHA256", nullptr, reinterpret_cast<const unsigned char*>(input.data()),
      input.size(), output.data(), &output_size);
  if (success != 1 || output_size != output.size()) {
    return {};
  }
  constexpr std::array<char, 16> digits{'0', '1', '2', '3', '4', '5', '6', '7',
                                        '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'};
  std::string result;
  result.reserve(output.size() * 2U);
  for (const auto value : output) {
    result.push_back(digits[value >> 4U]);
    result.push_back(digits[value & 0x0fU]);
  }
  return result;
}

auto decode_u64_be(std::span<const std::byte, 8> input) -> std::uint64_t {
  std::uint64_t result = 0U;
  for (const auto value : input) {
    result = (result << 8U) | std::to_integer<std::uint64_t>(value);
  }
  return result;
}

auto decoded_hash(const protocol::ScheduleRecord& record,
                  std::span<const std::uint64_t> deadlines) -> std::string {
  std::vector<std::byte> preimage;
  const auto field_count = 9U + deadlines.size();
  if (field_count <= std::numeric_limits<std::size_t>::max() / 16U) {
    preimage.reserve(field_count * 16U);
  }
  append_string_field(preimage, "cpu-prefetch/decoded-deadlines-sha256/v1");
  append_string_field(preimage, protocol::kProtocolVersion);
  append_string_field(preimage, kScheduleSuite);
  append_string_field(preimage, kScheduleTimeUnit);
  append_integer_field(preimage, record.origin_ticks);
  append_integer_field(preimage, record.horizon_ticks);
  append_integer_field(preimage, record.nominal_offered_rate.numerator_events);
  append_integer_field(preimage, record.nominal_offered_rate.denominator_ticks);
  append_integer_field(preimage, static_cast<std::uint64_t>(deadlines.size()));
  for (const auto deadline : deadlines) {
    append_integer_field(preimage, deadline);
  }
  return sha256_hex(preimage);
}

auto envelope_hash(const protocol::ScheduleRecord& record)
    -> protocol::Result<std::string> {
  const auto* source = record.source_document.as_object();
  if (source == nullptr) {
    return protocol::Result<std::string>::failure(
        {ErrorCategory::invalid_type, "$out", "SCH-ENVELOPE-OBJECT",
         "schedule source document must be an object"});
  }
  auto zeroed = *source;
  const auto hash = zeroed.find("schedule_sha256");
  if (hash == zeroed.end()) {
    return protocol::Result<std::string>::failure(
        {ErrorCategory::missing_field, "$out/schedule_sha256", "SCH-ENVELOPE-HASH",
         "schedule hash field is missing"});
  }
  hash->second = protocol::json::Value(std::string(64U, '0'));
  const auto canonical =
      protocol::json::canonicalize(protocol::json::Value(std::move(zeroed)));
  if (!canonical) {
    return protocol::Result<std::string>::failure(canonical.errors());
  }
  const auto bytes =
      std::as_bytes(std::span(canonical.value().data(), canonical.value().size()));
  const auto result = sha256_hex(bytes);
  if (result.empty()) {
    return protocol::Result<std::string>::failure({ErrorCategory::missing_evidence,
                                                   "$out/schedule_sha256", "SCH-SHA256",
                                                   "OpenSSL SHA-256 failed"});
  }
  return protocol::Result<std::string>::success(result);
}

auto role_matches_kind(NamespaceRole role, protocol::ScheduleKind kind) -> bool {
  switch (role) {
  case NamespaceRole::warmup:
    return kind == protocol::ScheduleKind::warmup;
  case NamespaceRole::calibration:
    return kind == protocol::ScheduleKind::calibration;
  case NamespaceRole::pilot:
    return kind == protocol::ScheduleKind::pilot;
  case NamespaceRole::h3_train:
  case NamespaceRole::h3_validation:
  case NamespaceRole::h1h2_supplemental:
    return kind == protocol::ScheduleKind::confirmatory;
  case NamespaceRole::diagnostic:
    return kind == protocol::ScheduleKind::diagnostic;
  }
  return false;
}

auto is_confirmatory_role(NamespaceRole role) -> bool {
  return role == NamespaceRole::h3_train || role == NamespaceRole::h3_validation ||
         role == NamespaceRole::h1h2_supplemental;
}

auto same_schedule(const protocol::ScheduleRecord& left,
                   const protocol::ScheduleRecord& right) -> bool {
  return left.schedule_id == right.schedule_id &&
         left.schedule_sha256 == right.schedule_sha256 &&
         left.decoded_deadlines_sha256 == right.decoded_deadlines_sha256 &&
         left.namespace_id == right.namespace_id &&
         left.rng.parent_namespace_id == right.rng.parent_namespace_id &&
         left.rng.seed_id == right.rng.seed_id &&
         left.rng.derivation_record_id == right.rng.derivation_record_id &&
         left.rng.algorithm == right.rng.algorithm &&
         left.rng.version == right.rng.version &&
         left.schedule_kind == right.schedule_kind &&
         left.arrival_family == right.arrival_family &&
         left.time_unit == right.time_unit &&
         left.deadline_encoding == right.deadline_encoding &&
         left.origin_ticks == right.origin_ticks &&
         left.horizon_ticks == right.horizon_ticks &&
         left.offered_count == right.offered_count &&
         left.nominal_offered_rate.numerator_events ==
             right.nominal_offered_rate.numerator_events &&
         left.nominal_offered_rate.denominator_ticks ==
             right.nominal_offered_rate.denominator_ticks;
}

} // namespace

auto validate_derivation_record(const protocol::ScheduleRecord& schedule,
                                std::string_view derivation_record_json)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  const auto parsed = protocol::json::parse(derivation_record_json);
  if (!parsed) {
    return parsed.errors();
  }
  const auto* object = parsed.value().as_object();
  if (object == nullptr) {
    add(errors, ErrorCategory::invalid_type, "$derivation", "SCH-DERIVATION-OBJECT",
        "schedule derivation record must be an object");
    return errors;
  }
  constexpr std::array<std::string_view, 16> expected_fields{"record_schema",
                                                             "protocol_version",
                                                             "record_id",
                                                             "schedule_suite",
                                                             "base_rng_suite",
                                                             "purpose",
                                                             "seed_id",
                                                             "parent_namespace_id",
                                                             "namespace_id",
                                                             "derived_key_u32be_hex",
                                                             "python_version",
                                                             "decimal_version",
                                                             "libmpdec_version",
                                                             "canonicalization_suite",
                                                             "record_hash_profile",
                                                             "record_sha256"};
  for (const auto& [name, value] : *object) {
    static_cast<void>(value);
    if (std::ranges::find(expected_fields, name) == expected_fields.end()) {
      add(errors, ErrorCategory::unknown_field, "$derivation/" + name,
          "SCH-DERIVATION-FIELD", "unknown schedule derivation field");
    }
  }

  auto field = [&](std::string_view name) -> std::string_view {
    const auto position = object->find(name);
    const auto path = "$derivation/" + std::string(name);
    if (position == object->end()) {
      add(errors, ErrorCategory::missing_field, path, "SCH-DERIVATION-FIELD",
          "required schedule derivation field is missing");
      return {};
    }
    const auto* value = position->second.as_string();
    if (value == nullptr) {
      add(errors, ErrorCategory::invalid_type, path, "SCH-DERIVATION-FIELD",
          "schedule derivation fields must be strings");
      return {};
    }
    return *value;
  };

  const auto record_schema = field("record_schema");
  const auto protocol_version = field("protocol_version");
  const auto record_id = field("record_id");
  const auto schedule_suite = field("schedule_suite");
  const auto base_rng_suite = field("base_rng_suite");
  const auto purpose = field("purpose");
  const auto seed_id = field("seed_id");
  const auto parent_namespace_id = field("parent_namespace_id");
  const auto namespace_id = field("namespace_id");
  const auto derived_key = field("derived_key_u32be_hex");
  const auto python_version = field("python_version");
  const auto decimal_version = field("decimal_version");
  const auto libmpdec_version = field("libmpdec_version");
  const auto canonicalization_suite = field("canonicalization_suite");
  const auto hash_profile = field("record_hash_profile");
  const auto declared_hash = field("record_sha256");

  struct ExpectedBinding {
    std::string_view actual;
    std::string_view expected;
    std::string_view name;
    std::string_view rule;
  };
  auto expect = [&](ExpectedBinding binding) {
    if (!binding.actual.empty() && binding.actual != binding.expected) {
      add(errors, ErrorCategory::reference_mismatch,
          "$derivation/" + std::string(binding.name), std::string(binding.rule),
          "schedule derivation value does not match its accepted binding");
    }
  };
  expect({record_schema, kDerivationSchema, "record_schema", "SCH-DERIVATION-SCHEMA"});
  expect({protocol_version, protocol::kProtocolVersion, "protocol_version",
          "SCH-DERIVATION-PROTOCOL"});
  expect({record_id, schedule.rng.derivation_record_id.value(), "record_id",
          "SCH-DERIVATION-RECORD-ID"});
  expect({schedule_suite, kScheduleSuite, "schedule_suite", "SCH-DERIVATION-SUITE"});
  expect({base_rng_suite, "PHILOX4X32-10-HMAC-SHA256-v1", "base_rng_suite",
          "SCH-DERIVATION-BASE-RNG"});
  expect({purpose, "arrival-schedule", "purpose", "SCH-DERIVATION-PURPOSE"});
  expect({seed_id, schedule.rng.seed_id.value(), "seed_id", "SCH-DERIVATION-SEED"});
  expect({parent_namespace_id, schedule.rng.parent_namespace_id.value(),
          "parent_namespace_id", "SCH-DERIVATION-PARENT"});
  expect({namespace_id, schedule.namespace_id.value(), "namespace_id",
          "SCH-DERIVATION-NAMESPACE"});
  expect({canonicalization_suite, protocol::kCanonicalizationSuite,
          "canonicalization_suite", "SCH-DERIVATION-CANONICAL"});
  expect({hash_profile, kDerivationHashProfile, "record_hash_profile",
          "SCH-DERIVATION-HASH-PROFILE"});

  const auto lowercase_hex = [](std::string_view value) {
    return std::ranges::all_of(value, [](char character) {
      return (character >= '0' && character <= '9') ||
             (character >= 'a' && character <= 'f');
    });
  };
  if (derived_key.size() != 16U || !lowercase_hex(derived_key)) {
    add(errors, ErrorCategory::invalid_hash, "$derivation/derived_key_u32be_hex",
        "SCH-DERIVATION-KEY",
        "derived Philox key identity must be 16 lowercase hex digits");
  }
  if (!python_version.starts_with("3.14.") || decimal_version.empty() ||
      libmpdec_version.empty()) {
    add(errors, ErrorCategory::unsupported_version, "$derivation/python_version",
        "SCH-DERIVATION-RUNTIME",
        "derivation must record Python 3.14.x and exact decimal/libmpdec versions");
  }
  if (declared_hash.size() != 64U || !lowercase_hex(declared_hash)) {
    add(errors, ErrorCategory::invalid_hash, "$derivation/record_sha256",
        "SCH-DERIVATION-HASH", "derivation SHA-256 must be lowercase hexadecimal");
  } else {
    auto zeroed = *object;
    zeroed["record_sha256"] = protocol::json::Value(std::string(64U, '0'));
    const auto canonical =
        protocol::json::canonicalize(protocol::json::Value(std::move(zeroed)));
    if (!canonical) {
      errors.insert(errors.end(), canonical.errors().begin(), canonical.errors().end());
    } else {
      const auto bytes =
          std::as_bytes(std::span(canonical.value().data(), canonical.value().size()));
      const auto computed_hash = sha256_hex(bytes);
      if (computed_hash.empty()) {
        add(errors, ErrorCategory::missing_evidence, "$derivation/record_sha256",
            "SCH-SHA256", "OpenSSL SHA-256 failed");
      } else if (computed_hash != declared_hash) {
        add(errors, ErrorCategory::reference_mismatch, "$derivation/record_sha256",
            "SCH-DERIVATION-HASH", "canonical derivation SHA-256 does not match");
      }
    }
  }
  return errors;
}

auto decode_and_validate(const protocol::ScheduleRecord& record,
                         std::span<const std::byte> artifact_bytes,
                         std::string_view derivation_record_json)
    -> protocol::Result<PreparedSchedule> {
  std::vector<ValidationError> errors;
  const auto local_errors =
      protocol::Stage4SemanticValidator{}.validate(protocol::ProtocolRecord{record});
  errors.insert(errors.end(), local_errors.begin(), local_errors.end());
  const auto derivation_errors =
      validate_derivation_record(record, derivation_record_json);
  errors.insert(errors.end(), derivation_errors.begin(), derivation_errors.end());

  if (record.arrival_family != protocol::ArrivalFamily::poisson_exponential) {
    add(errors, ErrorCategory::cross_field, "$out/arrival_family", "SCH-SUITE-FAMILY",
        "ADR-0029 requires POISSON_EXPONENTIAL");
  }
  if (record.rng.algorithm != kScheduleAlgorithm ||
      record.rng.version != kScheduleVersion) {
    add(errors, ErrorCategory::unsupported_version, "$out/rng", "SCH-SUITE-ID",
        "schedule RNG algorithm/version does not identify ADR-0029");
  }
  if (record.time_unit != kScheduleTimeUnit) {
    add(errors, ErrorCategory::invalid_unit, "$out/time_unit", "SCH-TIME-UNIT",
        "ADR-0029 requires picosecond schedule ticks");
  }
  if (record.deadline_encoding != protocol::DeadlineEncoding::absolute_integer_ticks) {
    add(errors, ErrorCategory::unknown_enum, "$out/deadline_encoding",
        "SCH-SUITE-ENCODING", "ADR-0029 requires absolute integer deadlines");
  }
  if (record.overflow_rule_record_id.value() != kScheduleOverflowRule) {
    add(errors, ErrorCategory::reference_mismatch, "$out/overflow_rule_record_id",
        "SCH-OVERFLOW-RULE", "schedule does not bind the accepted overflow rule");
  }
  if (record.nominal_offered_rate.numerator_events == 0U ||
      record.nominal_offered_rate.denominator_ticks == 0U ||
      std::gcd(record.nominal_offered_rate.numerator_events,
               record.nominal_offered_rate.denominator_ticks) != 1U) {
    add(errors, ErrorCategory::cross_field, "$out/nominal_offered_rate",
        "SCH-RATE-CANONICAL", "ADR-0029 requires a positive reduced rational rate");
  }
  if (record.horizon_ticks >
      std::numeric_limits<std::uint64_t>::max() - record.origin_ticks) {
    add(errors, ErrorCategory::out_of_range, "$out/horizon_ticks",
        "SCH-HORIZON-OVERFLOW", "origin plus horizon overflows uint64");
  }
  if (!errors.empty()) {
    return protocol::Result<PreparedSchedule>::failure(std::move(errors));
  }

  std::vector<std::uint64_t> deadlines;
  std::string artifact_hash;
  if (const auto* external =
          std::get_if<protocol::ExternalScheduleStorage>(&record.deadline_storage)) {
    if (record.offered_count > std::numeric_limits<std::uint64_t>::max() / 8U ||
        external->byte_count != record.offered_count * 8U) {
      add(errors, ErrorCategory::out_of_range, "$out/deadline_storage/byte_count",
          "SCH-BYTE-COUNT", "byte_count must equal eight times offered_count");
    }
    if (artifact_bytes.size() != external->byte_count) {
      add(errors, ErrorCategory::cross_field, "$artifact", "SCH-ARTIFACT-SIZE",
          "artifact size does not equal byte_count");
    }
    artifact_hash = sha256_hex(artifact_bytes);
    if (artifact_hash.empty()) {
      add(errors, ErrorCategory::missing_evidence, "$artifact", "SCH-SHA256",
          "OpenSSL SHA-256 failed");
    } else if (artifact_hash != external->artifact_sha256.hex()) {
      add(errors, ErrorCategory::reference_mismatch,
          "$out/deadline_storage/artifact_sha256", "SCH-ARTIFACT-HASH",
          "artifact SHA-256 does not match the envelope");
    }
    if (errors.empty()) {
      deadlines.reserve(static_cast<std::size_t>(record.offered_count));
      for (std::size_t offset = 0; offset < artifact_bytes.size(); offset += 8U) {
        deadlines.push_back(decode_u64_be(
            std::span<const std::byte, 8>(artifact_bytes.subspan(offset, 8U))));
      }
    }
  } else {
    if (!artifact_bytes.empty()) {
      add(errors, ErrorCategory::cross_field, "$artifact", "SCH-INLINE-BYTES",
          "inline test schedules do not accept external bytes");
    }
    deadlines = std::get<protocol::InlineDeadlineStorage>(record.deadline_storage)
                    .deadline_ticks;
  }

  if (!errors.empty()) {
    return protocol::Result<PreparedSchedule>::failure(std::move(errors));
  }
  if (deadlines.size() != record.offered_count) {
    add(errors, ErrorCategory::cross_field, "$out/offered_count", "SCH-DECODED-COUNT",
        "decoded deadline count does not equal offered_count");
  }
  const auto horizon_end = record.origin_ticks + record.horizon_ticks;
  for (std::size_t index = 0; index < deadlines.size(); ++index) {
    const auto path = "$deadlines/" + std::to_string(index);
    if (index != 0U && deadlines[index] < deadlines[index - 1U]) {
      add(errors, ErrorCategory::cross_field, path, "SCH-NONDECREASING",
          "decoded deadlines must be nondecreasing");
    }
    if (deadlines[index] < record.origin_ticks || deadlines[index] >= horizon_end) {
      add(errors, ErrorCategory::cross_field, path, "SCH-HALF-OPEN",
          "decoded deadline is outside [origin, origin+horizon)");
    }
  }

  const auto computed_decoded_hash = decoded_hash(record, deadlines);
  if (computed_decoded_hash.empty()) {
    add(errors, ErrorCategory::missing_evidence, "$out/decoded_deadlines_sha256",
        "SCH-SHA256", "OpenSSL SHA-256 failed");
  } else if (computed_decoded_hash != record.decoded_deadlines_sha256.hex()) {
    add(errors, ErrorCategory::reference_mismatch, "$out/decoded_deadlines_sha256",
        "SCH-DECODED-HASH", "decoded deadline SHA-256 does not match the envelope");
  }
  const auto computed_envelope_hash = envelope_hash(record);
  if (!computed_envelope_hash) {
    errors.insert(errors.end(), computed_envelope_hash.errors().begin(),
                  computed_envelope_hash.errors().end());
  } else if (computed_envelope_hash.value() != record.schedule_sha256.hex()) {
    add(errors, ErrorCategory::reference_mismatch, "$out/schedule_sha256",
        "SCH-ENVELOPE-HASH", "canonical schedule SHA-256 does not match");
  }
  if (!errors.empty()) {
    return protocol::Result<PreparedSchedule>::failure(std::move(errors));
  }
  return protocol::Result<PreparedSchedule>::success(
      PreparedSchedule(std::move(deadlines), std::move(artifact_hash),
                       computed_decoded_hash, computed_envelope_hash.value()));
}

auto validate_schedule_uses(std::span<const ScheduleUse> uses)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  struct NamespaceOwner {
    NamespaceRole role;
    const protocol::ScheduleRecord* schedule;
  };
  std::map<std::string, NamespaceOwner, std::less<>> namespaces;
  std::map<std::string, const ScheduleUse*, std::less<>> families;
  std::string confirmatory_parent;

  for (std::size_t index = 0; index < uses.size(); ++index) {
    const auto path = "$schedule_uses/" + std::to_string(index);
    const auto& use = uses[index];
    if (use.schedule == nullptr) {
      add(errors, ErrorCategory::missing_field, path + "/schedule", "SCH-USE-RECORD",
          "schedule use requires a record");
      continue;
    }
    if (use.treatment_id.empty()) {
      add(errors, ErrorCategory::invalid_id, path + "/treatment_id", "SCH-USE-ID",
          "treatment identity must be explicit");
    }
    if (use.common_schedule_family_id.empty()) {
      add(errors, ErrorCategory::invalid_id, path + "/common_schedule_family_id",
          "SCH-FAMILY-ID", "common schedule family identity must be explicit");
    }
    if (!role_matches_kind(use.namespace_role, use.schedule->schedule_kind)) {
      add(errors, ErrorCategory::cross_field, path + "/namespace_role",
          "SCH-NAMESPACE-ROLE", "namespace role does not match schedule kind");
    }

    const std::string namespace_id(use.schedule->namespace_id.value());
    const auto [namespace_position, inserted] = namespaces.try_emplace(
        namespace_id, NamespaceOwner{use.namespace_role, use.schedule});
    if (!inserted && namespace_position->second.role != use.namespace_role) {
      add(errors, ErrorCategory::duplicate_value, path + "/namespace_role",
          "SCH-NAMESPACE-DISJOINT",
          "distinct lifecycle roles must use disjoint child namespaces");
    } else if (!inserted &&
               !same_schedule(*namespace_position->second.schedule, *use.schedule)) {
      add(errors, ErrorCategory::duplicate_value, path + "/schedule",
          "SCH-NAMESPACE-COLLISION",
          "one child namespace cannot identify different logical schedules");
    }

    if (is_confirmatory_role(use.namespace_role)) {
      const std::string parent(use.schedule->rng.parent_namespace_id.value());
      if (confirmatory_parent.empty()) {
        confirmatory_parent = parent;
      } else if (confirmatory_parent != parent) {
        add(errors, ErrorCategory::reference_mismatch,
            path + "/schedule/rng/parent_namespace_id", "SCH-STAGE-A-PARENT",
            "confirmatory role subspaces must share the common Stage A parent");
      }
    }

    if (!use.common_schedule_family_id.empty()) {
      const auto [family_position, family_inserted] =
          families.try_emplace(use.common_schedule_family_id, &use);
      if (!family_inserted &&
          !same_schedule(*family_position->second->schedule, *use.schedule)) {
        add(errors, ErrorCategory::reference_mismatch, path + "/schedule",
            "SCH-COMMON-FAMILY",
            "matched treatments in one family must use the same logical schedule");
      }
    }
  }
  return errors;
}

} // namespace cpu_prefetch::schedule
