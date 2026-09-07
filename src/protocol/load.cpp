#include "cpu_prefetch/protocol/model.hpp"

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

namespace cpu_prefetch::protocol {
namespace {

using namespace std::string_view_literals;

using Object = json::Value::Object;
using Array = json::Value::Array;

class LoadFailure final : public std::exception {
public:
  explicit LoadFailure(ValidationError error) { errors_.push_back(std::move(error)); }
  explicit LoadFailure(std::vector<ValidationError> errors)
      : errors_(std::move(errors)) {}
  [[nodiscard]] auto errors() const -> const std::vector<ValidationError>& {
    return errors_;
  }
  [[nodiscard]] auto what() const noexcept -> const char* override {
    return "protocol load failure";
  }

private:
  std::vector<ValidationError> errors_;
};

[[noreturn]] void fail(ErrorCategory category, std::string path, std::string rule,
                       std::string message) {
  throw LoadFailure({category, std::move(path), std::move(rule), std::move(message)});
}

template <typename T> auto take(Result<T> result) -> T {
  if (!result) {
    throw LoadFailure(result.errors());
  }
  return std::move(result).value();
}

auto object_of(const json::Value& value, std::string_view path) -> const Object& {
  const auto* object = value.as_object();
  if (object == nullptr) {
    fail(ErrorCategory::invalid_type, std::string(path), "SCHEMA-TYPE",
         "expected object");
  }
  return *object;
}

auto array_of(const json::Value& value, std::string_view path) -> const Array& {
  const auto* array = value.as_array();
  if (array == nullptr) {
    fail(ErrorCategory::invalid_type, std::string(path), "SCHEMA-TYPE",
         "expected array");
  }
  return *array;
}

auto required(const Object& object, std::string_view key, std::string_view path)
    -> const json::Value& {
  const auto iterator = object.find(key);
  if (iterator == object.end()) {
    fail(ErrorCategory::missing_field, std::string(path) + "/" + std::string(key),
         "SCHEMA-REQUIRED", "required field is missing");
  }
  return iterator->second;
}

auto optional(const Object& object, std::string_view key) -> const json::Value* {
  const auto iterator = object.find(key);
  return iterator == object.end() ? nullptr : &iterator->second;
}

void reject_unknown(const Object& object,
                    std::initializer_list<std::string_view> allowed,
                    const std::string& path) {
  const std::set<std::string_view> accepted(allowed.begin(), allowed.end());
  for (const auto& [key, value] : object) {
    static_cast<void>(value);
    if (!accepted.contains(key)) {
      std::string field_path = path;
      field_path.push_back('/');
      field_path.append(key);
      fail(ErrorCategory::unknown_field, std::move(field_path), "SCHEMA-ADDITIONAL",
           "unknown field is not permitted by the versioned schema");
    }
  }
}

auto string_of(const json::Value& value, const std::string& path,
               bool allow_empty = false) -> std::string {
  const auto* string = value.as_string();
  if (string == nullptr) {
    fail(ErrorCategory::invalid_type, path, "SCHEMA-TYPE", "expected string");
  }
  if (!allow_empty && string->empty()) {
    fail(ErrorCategory::invalid_id, path, "SCHEMA-MIN-LENGTH",
         "string must not be empty");
  }
  return *string;
}

auto string_field(const Object& object, std::string_view key, const std::string& path,
                  bool allow_empty = false) -> std::string {
  return string_of(required(object, key, path), path + "/" + std::string(key),
                   allow_empty);
}

auto unit_field(const Object& object, std::string_view key, const std::string& path)
    -> std::string {
  const std::string field_path = path + "/" + std::string(key);
  auto unit = string_of(required(object, key, path), field_path, true);
  if (unit.empty()) {
    fail(ErrorCategory::invalid_unit, field_path, "DAT-TIME-UNIT",
         "unit must be present explicitly and must not be empty");
  }
  return unit;
}

auto bool_field(const Object& object, std::string_view key, const std::string& path)
    -> bool {
  const auto* value = required(object, key, path).as_bool();
  if (value == nullptr) {
    fail(ErrorCategory::invalid_type, path + "/" + std::string(key), "SCHEMA-TYPE",
         "expected boolean");
  }
  return *value;
}

auto uint_of(const json::Value& value, const std::string& path) -> std::uint64_t {
  const auto* number = value.as_number();
  if (number == nullptr || number->kind == json::Number::Kind::binary64) {
    fail(ErrorCategory::invalid_type, path, "SCHEMA-INTEGER", "expected exact integer");
  }
  if (number->kind == json::Number::Kind::signed_integer) {
    const auto signed_value = std::get<std::int64_t>(number->value);
    if (signed_value < 0) {
      fail(ErrorCategory::out_of_range, path, "SCHEMA-MINIMUM",
           "integer must be nonnegative");
    }
    return static_cast<std::uint64_t>(signed_value);
  }
  return std::get<std::uint64_t>(number->value);
}

auto uint_field(const Object& object, std::string_view key, const std::string& path)
    -> std::uint64_t {
  return uint_of(required(object, key, path), path + "/" + std::string(key));
}

auto number_of(const json::Value& value, const std::string& path) -> double {
  const auto* number = value.as_number();
  if (number == nullptr) {
    fail(ErrorCategory::invalid_type, path, "SCHEMA-NUMBER", "expected number");
  }
  if (number->kind == json::Number::Kind::signed_integer) {
    return static_cast<double>(std::get<std::int64_t>(number->value));
  }
  if (number->kind == json::Number::Kind::unsigned_integer) {
    return static_cast<double>(std::get<std::uint64_t>(number->value));
  }
  return std::get<double>(number->value);
}

auto exact_number_of(const json::Value& value, const std::string& path)
    -> json::Number {
  const auto* number = value.as_number();
  if (number == nullptr) {
    fail(ErrorCategory::invalid_type, path, "SCHEMA-NUMBER", "expected number");
  }
  return *number;
}

template <typename Tag>
auto id_field(const Object& object, std::string_view key, const std::string& path)
    -> Identifier<Tag> {
  const std::string field_path = path + "/" + std::string(key);
  return take(Identifier<Tag>::parse(string_of(required(object, key, path), field_path),
                                     field_path));
}

template <typename Tag>
auto optional_nullable_id(const Object& object, std::string_view key,
                          const std::string& path) -> std::optional<Identifier<Tag>> {
  const auto* value = optional(object, key);
  if (value == nullptr || value->is_null()) {
    return std::nullopt;
  }
  const std::string field_path = path + "/" + std::string(key);
  return take(Identifier<Tag>::parse(string_of(*value, field_path), field_path));
}

auto version_field(const Object& object, std::string_view key, const std::string& path)
    -> ProtocolVersion {
  const std::string field_path = path + "/" + std::string(key);
  return take(parse_protocol_version(string_of(required(object, key, path), field_path),
                                     field_path));
}

auto sha_field(const Object& object, std::string_view key, const std::string& path)
    -> Sha256 {
  const std::string field_path = path + "/" + std::string(key);
  return take(
      Sha256::parse(string_of(required(object, key, path), field_path), field_path));
}

template <typename Enum, std::size_t Size>
auto enum_value(const json::Value& value, const std::string& path, std::string rule,
                const std::array<std::pair<std::string_view, Enum>, Size>& entries)
    -> Enum {
  const std::string text = string_of(value, path);
  for (const auto& [name, enum_value] : entries) {
    if (name == text) {
      return enum_value;
    }
  }
  fail(ErrorCategory::unknown_enum, path, std::move(rule),
       "unknown enum value: " + text);
}

template <typename Enum, std::size_t Size>
auto enum_field(const Object& object, std::string_view key, const std::string& path,
                std::string rule,
                const std::array<std::pair<std::string_view, Enum>, Size>& entries)
    -> Enum {
  return enum_value(required(object, key, path), path + "/" + std::string(key),
                    std::move(rule), entries);
}

auto string_array(const json::Value& value, const std::string& path,
                  bool require_nonempty) -> std::vector<std::string> {
  const auto& array = array_of(value, path);
  if (require_nonempty && array.empty()) {
    fail(ErrorCategory::out_of_range, path, "SCHEMA-MIN-ITEMS",
         "array must contain at least one item");
  }
  std::vector<std::string> result;
  result.reserve(array.size());
  for (std::size_t index = 0; index < array.size(); ++index) {
    result.push_back(string_of(array[index], path + "/" + std::to_string(index)));
  }
  return result;
}

auto artifact_reference(const json::Value& value, const std::string& path)
    -> ArtifactReference {
  const auto& object = object_of(value, path);
  reject_unknown(object, {"artifact_id", "sha256"}, path);
  return {id_field<ArtifactIdTag>(object, "artifact_id", path),
          sha_field(object, "sha256", path)};
}

auto artifact_reference_array(const json::Value& value, const std::string& path,
                              bool require_nonempty = false)
    -> std::vector<ArtifactReference> {
  const auto& array = array_of(value, path);
  if (require_nonempty && array.empty()) {
    fail(ErrorCategory::out_of_range, path, "SCHEMA-MIN-ITEMS",
         "artifact reference array must not be empty");
  }
  std::vector<ArtifactReference> result;
  result.reserve(array.size());
  for (std::size_t index = 0; index < array.size(); ++index) {
    result.push_back(
        artifact_reference(array[index], path + "/" + std::to_string(index)));
  }
  return result;
}

auto load_schedule(const json::Value& document) -> ScheduleRecord {
  const auto& object = object_of(document, "$out");
  reject_unknown(object,
                 {"schema_version", "protocol_version", "schedule_id", "schedule_kind",
                  "arrival_family", "namespace_id", "rng", "time_unit",
                  "deadline_encoding", "origin_ticks", "horizon_ticks",
                  "inclusion_boundary", "offered_count", "nominal_offered_rate",
                  "overflow_rule_record_id", "immutable_ordering", "deadline_storage",
                  "decoded_deadlines_sha256", "schedule_sha256"},
                 "$out");
  constexpr std::array schedule_kinds{
      std::pair{"WARMUP"sv, ScheduleKind::warmup},
      std::pair{"CALIBRATION"sv, ScheduleKind::calibration},
      std::pair{"PILOT"sv, ScheduleKind::pilot},
      std::pair{"CONFIRMATORY"sv, ScheduleKind::confirmatory},
      std::pair{"DIAGNOSTIC"sv, ScheduleKind::diagnostic},
      std::pair{"STAGE_B"sv, ScheduleKind::stage_b},
      std::pair{"STAGE_C"sv, ScheduleKind::stage_c}};
  constexpr std::array arrival_families{
      std::pair{"POISSON_EXPONENTIAL"sv, ArrivalFamily::poisson_exponential},
      std::pair{"CONTINUOUS_READY"sv, ArrivalFamily::continuous_ready},
      std::pair{"PREDECLARED_BURST"sv, ArrivalFamily::predeclared_burst},
      std::pair{"PREDECLARED_OTHER"sv, ArrivalFamily::predeclared_other}};
  constexpr std::array deadline_encodings{
      std::pair{"ABSOLUTE_INTEGER_TICKS"sv, DeadlineEncoding::absolute_integer_ticks},
      std::pair{"DELTA_INTEGER_TICKS"sv, DeadlineEncoding::delta_integer_ticks}};

  const auto& rng_object = object_of(required(object, "rng", "$out"), "$out/rng");
  reject_unknown(rng_object,
                 {"algorithm", "version", "seed_id", "derivation_record_id",
                  "parent_namespace_id"},
                 "$out/rng");
  RngMetadata rng{
      string_field(rng_object, "algorithm", "$out/rng"),
      string_field(rng_object, "version", "$out/rng"),
      id_field<SeedIdTag>(rng_object, "seed_id", "$out/rng"),
      id_field<RecordIdTag>(rng_object, "derivation_record_id", "$out/rng"),
      id_field<NamespaceIdTag>(rng_object, "parent_namespace_id", "$out/rng")};

  const auto& boundary = object_of(required(object, "inclusion_boundary", "$out"),
                                   "$out/inclusion_boundary");
  reject_unknown(boundary, {"start_inclusive", "end_exclusive"},
                 "$out/inclusion_boundary");
  if (!bool_field(boundary, "start_inclusive", "$out/inclusion_boundary") ||
      !bool_field(boundary, "end_exclusive", "$out/inclusion_boundary")) {
    fail(ErrorCategory::cross_field, "$out/inclusion_boundary", "SCH-HALF-OPEN",
         "the protocol requires an inclusive origin and exclusive end");
  }
  if (!bool_field(object, "immutable_ordering", "$out")) {
    fail(ErrorCategory::cross_field, "$out/immutable_ordering", "SCH-IMMUTABLE",
         "schedule ordering must be immutable");
  }

  const auto& rate = object_of(required(object, "nominal_offered_rate", "$out"),
                               "$out/nominal_offered_rate");
  reject_unknown(rate, {"numerator_events", "denominator_ticks"},
                 "$out/nominal_offered_rate");
  ExactRate exact_rate{
      uint_field(rate, "numerator_events", "$out/nominal_offered_rate"),
      uint_field(rate, "denominator_ticks", "$out/nominal_offered_rate")};
  if (exact_rate.denominator_ticks == 0) {
    fail(ErrorCategory::out_of_range, "$out/nominal_offered_rate/denominator_ticks",
         "SCH-RATE-DENOMINATOR", "exact rate denominator must be positive");
  }

  const auto& storage =
      object_of(required(object, "deadline_storage", "$out"), "$out/deadline_storage");
  const auto mode = string_field(storage, "mode", "$out/deadline_storage");
  std::variant<ExternalScheduleStorage, InlineDeadlineStorage> typed_storage{
      InlineDeadlineStorage{}};
  if (mode == "EXTERNAL_IMMUTABLE_ARTIFACT") {
    reject_unknown(storage,
                   {"mode", "artifact_id", "artifact_uri", "row_count", "byte_count",
                    "artifact_sha256"},
                   "$out/deadline_storage");
    typed_storage = ExternalScheduleStorage{
        id_field<ArtifactIdTag>(storage, "artifact_id", "$out/deadline_storage"),
        string_field(storage, "artifact_uri", "$out/deadline_storage"),
        uint_field(storage, "row_count", "$out/deadline_storage"),
        uint_field(storage, "byte_count", "$out/deadline_storage"),
        sha_field(storage, "artifact_sha256", "$out/deadline_storage")};
  } else if (mode == "INLINE_TEST_ONLY") {
    reject_unknown(storage, {"mode", "deadline_ticks"}, "$out/deadline_storage");
    const auto& ticks =
        array_of(required(storage, "deadline_ticks", "$out/deadline_storage"),
                 "$out/deadline_storage/deadline_ticks");
    std::vector<std::uint64_t> deadlines;
    deadlines.reserve(ticks.size());
    for (std::size_t index = 0; index < ticks.size(); ++index) {
      deadlines.push_back(
          uint_of(ticks[index],
                  "$out/deadline_storage/deadline_ticks/" + std::to_string(index)));
    }
    typed_storage = InlineDeadlineStorage{std::move(deadlines)};
  } else {
    fail(ErrorCategory::unknown_enum, "$out/deadline_storage/mode", "DAT-STORAGE-MODE",
         "unknown storage mode: " + mode);
  }

  const auto time_unit = unit_field(object, "time_unit", "$out");
  return {version_field(object, "schema_version", "$out"),
          version_field(object, "protocol_version", "$out"),
          id_field<ScheduleIdTag>(object, "schedule_id", "$out"),
          enum_field(object, "schedule_kind", "$out", "SCH-KIND", schedule_kinds),
          enum_field(object, "arrival_family", "$out", "SCH-ARRIVAL", arrival_families),
          id_field<NamespaceIdTag>(object, "namespace_id", "$out"),
          std::move(rng),
          time_unit,
          enum_field(object, "deadline_encoding", "$out", "SCH-ENCODING",
                     deadline_encodings),
          uint_field(object, "origin_ticks", "$out"),
          uint_field(object, "horizon_ticks", "$out"),
          uint_field(object, "offered_count", "$out"),
          exact_rate,
          id_field<RecordIdTag>(object, "overflow_rule_record_id", "$out"),
          std::move(typed_storage),
          sha_field(object, "decoded_deadlines_sha256", "$out"),
          sha_field(object, "schedule_sha256", "$out"),
          document};
}

auto producer_row(const json::Value& value, const std::string& path) -> ProducerRecord {
  const auto& object = object_of(value, path);
  reject_unknown(object,
                 {"run_id", "logical_sequence", "record_index", "scheduled_arrival",
                  "producer_handle_begin", "record_lookup_completion",
                  "enqueue_invocation", "enqueue_linearization",
                  "enqueue_attempt_completion", "attempted", "outcome",
                  "accepted_ordinal"},
                 path);
  if (!bool_field(object, "attempted", path)) {
    fail(ErrorCategory::cross_field, path + "/attempted", "RAW-ATTEMPTED",
         "producer rows always represent an attempted enqueue");
  }
  constexpr std::array outcomes{std::pair{"ACCEPTED"sv, ProducerOutcome::accepted},
                                std::pair{"FULL"sv, ProducerOutcome::full}};
  const auto outcome = enum_field(object, "outcome", path, "RAW-OUTCOME", outcomes);
  std::optional<std::uint64_t> linearization;
  if (const auto* field = optional(object, "enqueue_linearization")) {
    linearization = uint_of(*field, path + "/enqueue_linearization");
  }
  std::optional<std::uint64_t> accepted_ordinal;
  if (const auto* field = optional(object, "accepted_ordinal")) {
    accepted_ordinal = uint_of(*field, path + "/accepted_ordinal");
  }
  if (outcome == ProducerOutcome::accepted && (!linearization || !accepted_ordinal)) {
    fail(ErrorCategory::missing_field, path, "RAW-ACCEPTED-FIELDS",
         "accepted rows require enqueue_linearization and accepted_ordinal");
  }
  if (outcome == ProducerOutcome::full && (linearization || accepted_ordinal)) {
    fail(ErrorCategory::cross_field, path, "RAW-FULL-FIELDS",
         "FULL rows must not contain a linearization timestamp or accepted ordinal");
  }
  return {id_field<RunIdTag>(object, "run_id", path),
          uint_field(object, "logical_sequence", path),
          uint_field(object, "record_index", path),
          uint_field(object, "scheduled_arrival", path),
          uint_field(object, "producer_handle_begin", path),
          uint_field(object, "record_lookup_completion", path),
          uint_field(object, "enqueue_invocation", path),
          linearization,
          uint_field(object, "enqueue_attempt_completion", path),
          outcome,
          accepted_ordinal};
}

auto consumer_row(const json::Value& value, const std::string& path) -> ConsumerRecord {
  const auto& object = object_of(value, path);
  reject_unknown(object,
                 {"run_id", "consumed_ordinal", "observed_record_index",
                  "dequeue_invocation", "dequeue_linearization", "dequeue_completion",
                  "consumer_action_completion"},
                 path);
  return {id_field<RunIdTag>(object, "run_id", path),
          uint_field(object, "consumed_ordinal", path),
          uint_field(object, "observed_record_index", path),
          uint_field(object, "dequeue_invocation", path),
          uint_field(object, "dequeue_linearization", path),
          uint_field(object, "dequeue_completion", path),
          uint_field(object, "consumer_action_completion", path)};
}

auto joined_row(const json::Value& value, const std::string& path) -> JoinedRecord {
  const auto& object = object_of(value, path);
  reject_unknown(object,
                 {"run_id",
                  "accepted_ordinal",
                  "logical_sequence",
                  "record_index",
                  "producer_row_ordinal",
                  "consumer_row_ordinal",
                  "scheduled_arrival",
                  "producer_handle_begin",
                  "record_lookup_completion",
                  "enqueue_invocation",
                  "enqueue_linearization",
                  "enqueue_attempt_completion",
                  "dequeue_invocation",
                  "dequeue_linearization",
                  "dequeue_completion",
                  "consumer_action_completion",
                  "producer_lateness",
                  "pointer_lookup_interval",
                  "enqueue_service_time",
                  "admission_delay",
                  "queue_residence",
                  "dequeue_service_time",
                  "post_dequeue_delivery_interval",
                  "consumer_action_interval",
                  "end_to_end_latency"},
                 path);
  return {id_field<RunIdTag>(object, "run_id", path),
          uint_field(object, "accepted_ordinal", path),
          uint_field(object, "logical_sequence", path),
          uint_field(object, "record_index", path),
          uint_field(object, "producer_row_ordinal", path),
          uint_field(object, "consumer_row_ordinal", path),
          uint_field(object, "scheduled_arrival", path),
          uint_field(object, "producer_handle_begin", path),
          uint_field(object, "record_lookup_completion", path),
          uint_field(object, "enqueue_invocation", path),
          uint_field(object, "enqueue_linearization", path),
          uint_field(object, "enqueue_attempt_completion", path),
          uint_field(object, "dequeue_invocation", path),
          uint_field(object, "dequeue_linearization", path),
          uint_field(object, "dequeue_completion", path),
          uint_field(object, "consumer_action_completion", path),
          uint_field(object, "producer_lateness", path),
          uint_field(object, "pointer_lookup_interval", path),
          uint_field(object, "enqueue_service_time", path),
          uint_field(object, "admission_delay", path),
          uint_field(object, "queue_residence", path),
          uint_field(object, "dequeue_service_time", path),
          uint_field(object, "post_dequeue_delivery_interval", path),
          uint_field(object, "consumer_action_interval", path),
          uint_field(object, "end_to_end_latency", path)};
}

auto load_raw(const json::Value& document) -> RawObservationEnvelope {
  const auto& object = object_of(document, "$out");
  reject_unknown(object,
                 {"schema_version", "protocol_version", "artifact_id", "run_id",
                  "stream_kind", "logical_row_schema_version",
                  "physical_format_record_id", "encoding", "time_unit", "endianness",
                  "compression", "row_count", "byte_count", "immutable_ordering",
                  "storage", "source_artifacts", "integrity_artifact_ref",
                  "artifact_sha256"},
                 "$out");
  constexpr std::array kinds{std::pair{"PRODUCER"sv, StreamKind::producer},
                             std::pair{"CONSUMER"sv, StreamKind::consumer},
                             std::pair{"JOINED_DERIVED"sv, StreamKind::joined_derived}};
  constexpr std::array byte_orders{
      std::pair{"LITTLE_ENDIAN"sv, Endianness::little_endian},
      std::pair{"BIG_ENDIAN"sv, Endianness::big_endian},
      std::pair{"NOT_APPLICABLE"sv, Endianness::not_applicable}};
  const auto kind = enum_field(object, "stream_kind", "$out", "DAT-STREAM-KIND", kinds);
  if (!bool_field(object, "immutable_ordering", "$out")) {
    fail(ErrorCategory::cross_field, "$out/immutable_ordering", "DAT-IMMUTABLE-ORDER",
         "raw observation order must be immutable");
  }
  const auto& storage = object_of(required(object, "storage", "$out"), "$out/storage");
  const auto mode = string_field(storage, "mode", "$out/storage");
  std::variant<ExternalStorage, InlineObservationRows> typed_storage;
  if (mode == "EXTERNAL_IMMUTABLE_ARTIFACT") {
    reject_unknown(storage, {"mode", "artifact_uri"}, "$out/storage");
    typed_storage =
        ExternalStorage{string_field(storage, "artifact_uri", "$out/storage")};
  } else if (mode == "INLINE_TEST_ONLY") {
    reject_unknown(storage, {"mode", "inline_rows"}, "$out/storage");
    const auto& rows = array_of(required(storage, "inline_rows", "$out/storage"),
                                "$out/storage/inline_rows");
    if (kind == StreamKind::producer) {
      std::vector<ProducerRecord> result;
      result.reserve(rows.size());
      for (std::size_t index = 0; index < rows.size(); ++index) {
        result.push_back(producer_row(rows[index], "$out/storage/inline_rows/" +
                                                       std::to_string(index)));
      }
      typed_storage = InlineObservationRows{std::move(result)};
    } else if (kind == StreamKind::consumer) {
      std::vector<ConsumerRecord> result;
      result.reserve(rows.size());
      for (std::size_t index = 0; index < rows.size(); ++index) {
        result.push_back(consumer_row(rows[index], "$out/storage/inline_rows/" +
                                                       std::to_string(index)));
      }
      typed_storage = InlineObservationRows{std::move(result)};
    } else {
      std::vector<JoinedRecord> result;
      result.reserve(rows.size());
      for (std::size_t index = 0; index < rows.size(); ++index) {
        result.push_back(joined_row(rows[index], "$out/storage/inline_rows/" +
                                                     std::to_string(index)));
      }
      typed_storage = InlineObservationRows{std::move(result)};
    }
  } else {
    fail(ErrorCategory::unknown_enum, "$out/storage/mode", "DAT-STORAGE-MODE",
         "unknown storage mode: " + mode);
  }

  std::vector<ArtifactReference> sources;
  if (const auto* value = optional(object, "source_artifacts")) {
    sources = artifact_reference_array(*value, "$out/source_artifacts");
  }
  if (kind == StreamKind::joined_derived && sources.size() < 2) {
    fail(ErrorCategory::missing_evidence, "$out/source_artifacts", "DAT-JOIN-SOURCES",
         "joined streams require at least two source artifacts");
  }
  return {version_field(object, "schema_version", "$out"),
          version_field(object, "protocol_version", "$out"),
          id_field<ArtifactIdTag>(object, "artifact_id", "$out"),
          id_field<RunIdTag>(object, "run_id", "$out"),
          kind,
          version_field(object, "logical_row_schema_version", "$out"),
          id_field<RecordIdTag>(object, "physical_format_record_id", "$out"),
          string_field(object, "encoding", "$out"),
          unit_field(object, "time_unit", "$out"),
          enum_field(object, "endianness", "$out", "DAT-ENDIANNESS", byte_orders),
          string_field(object, "compression", "$out"),
          uint_field(object, "row_count", "$out"),
          uint_field(object, "byte_count", "$out"),
          std::move(typed_storage),
          std::move(sources),
          artifact_reference(required(object, "integrity_artifact_ref", "$out"),
                             "$out/integrity_artifact_ref"),
          sha_field(object, "artifact_sha256", "$out"),
          document};
}

auto checksum_evidence(const json::Value& value, const std::string& path)
    -> ChecksumEvidence {
  const auto& object = object_of(value, path);
  reject_unknown(object, {"algorithm_record_id", "algorithm_version", "value_hex"},
                 path);
  const auto checksum = string_field(object, "value_hex", path);
  for (char character : checksum) {
    if (!((character >= '0' && character <= '9') ||
          (character >= 'a' && character <= 'f'))) {
      fail(ErrorCategory::invalid_hash, path + "/value_hex", "DAT-CHECKSUM-HEX",
           "checksum value must be nonempty lowercase hexadecimal");
    }
  }
  return {id_field<RecordIdTag>(object, "algorithm_record_id", path),
          string_field(object, "algorithm_version", path), checksum};
}

auto phase_integrity(const json::Value& value, const std::string& path)
    -> PhaseIntegrityRecord {
  const auto& object = object_of(value, path);
  reject_unknown(object,
                 {"report_artifact", "final_consumer_rolling_checksum",
                  "event_records_pre_checksum", "event_records_post_checksum",
                  "ordered_index_checksum", "address_delta_checksum"},
                 path);
  return {artifact_reference(required(object, "report_artifact", path),
                             path + "/report_artifact"),
          checksum_evidence(required(object, "final_consumer_rolling_checksum", path),
                            path + "/final_consumer_rolling_checksum"),
          checksum_evidence(required(object, "event_records_pre_checksum", path),
                            path + "/event_records_pre_checksum"),
          checksum_evidence(required(object, "event_records_post_checksum", path),
                            path + "/event_records_post_checksum"),
          checksum_evidence(required(object, "ordered_index_checksum", path),
                            path + "/ordered_index_checksum"),
          checksum_evidence(required(object, "address_delta_checksum", path),
                            path + "/address_delta_checksum")};
}

auto run_counts(const json::Value& value, const std::string& path) -> RunCounts {
  const auto& object = object_of(value, path);
  reject_unknown(object,
                 {"offered", "attempted", "accepted", "full", "consumed",
                  "final_occupancy", "raw_sample_count", "n_eff_p999"},
                 path);
  const auto optional_uint = [&](std::string_view key) -> std::optional<std::uint64_t> {
    const auto* field = optional(object, key);
    return field == nullptr
               ? std::nullopt
               : std::optional{uint_of(*field, path + "/" + std::string(key))};
  };
  std::optional<json::Number> effective;
  if (const auto* field = optional(object, "n_eff_p999");
      field != nullptr && !field->is_null()) {
    effective = exact_number_of(*field, path + "/n_eff_p999");
    if (number_of(*field, path + "/n_eff_p999") < 0.0) {
      fail(ErrorCategory::out_of_range, path + "/n_eff_p999", "SCHEMA-MINIMUM",
           "effective tail count must be nonnegative");
    }
  }
  return {optional_uint("offered"),          optional_uint("attempted"),
          optional_uint("accepted"),         optional_uint("full"),
          optional_uint("consumed"),         optional_uint("final_occupancy"),
          optional_uint("raw_sample_count"), effective};
}

auto run_provenance(const json::Value& value, const std::string& path)
    -> RunProvenance {
  const auto& object = object_of(value, path);
  reject_unknown(object,
                 {"paper_repository_revision", "implementation_repository_revision",
                  "build_artifact_sha256", "compiler_identity", "compiler_flags",
                  "standard_library", "dependency_record_id"},
                 path);
  return {string_field(object, "paper_repository_revision", path),
          string_field(object, "implementation_repository_revision", path),
          sha_field(object, "build_artifact_sha256", path),
          string_field(object, "compiler_identity", path),
          string_array(required(object, "compiler_flags", path),
                       path + "/compiler_flags", false),
          string_field(object, "standard_library", path),
          id_field<RecordIdTag>(object, "dependency_record_id", path)};
}

auto run_schedule_refs(const json::Value& value, const std::string& path)
    -> RunScheduleReferences {
  const auto& object = object_of(value, path);
  reject_unknown(object, {"measurement", "warmup"}, path);
  return {
      artifact_reference(required(object, "measurement", path), path + "/measurement"),
      artifact_reference(required(object, "warmup", path), path + "/warmup")};
}

auto run_seed_refs(const json::Value& value, const std::string& path)
    -> RunSeedReferences {
  const auto& object = object_of(value, path);
  reject_unknown(
      object,
      {"arrival", "node_order", "event_order", "warmup", "derivation_record_id"}, path);
  return {id_field<SeedIdTag>(object, "arrival", path),
          optional_nullable_id<SeedIdTag>(object, "node_order", path),
          id_field<SeedIdTag>(object, "event_order", path),
          id_field<SeedIdTag>(object, "warmup", path),
          id_field<RecordIdTag>(object, "derivation_record_id", path)};
}

auto typed_artifact(const json::Value& value, const std::string& path)
    -> TypedArtifactReference {
  const auto& object = object_of(value, path);
  reject_unknown(object, {"artifact_id", "relationship", "sha256"}, path);
  constexpr std::array relationships{
      std::pair{"PRODUCER_RAW"sv, ArtifactRelationship::producer_raw},
      std::pair{"CONSUMER_RAW"sv, ArtifactRelationship::consumer_raw},
      std::pair{"JOIN_AUDIT"sv, ArtifactRelationship::join_audit},
      std::pair{"JOINED_DERIVED"sv, ArtifactRelationship::joined_derived},
      std::pair{"PHASE_INTEGRITY_REPORT"sv,
                ArtifactRelationship::phase_integrity_report},
      std::pair{"SCHEDULE"sv, ArtifactRelationship::schedule},
      std::pair{"COUNTER"sv, ArtifactRelationship::counter},
      std::pair{"DERIVED"sv, ArtifactRelationship::derived},
      std::pair{"PROVENANCE"sv, ArtifactRelationship::provenance},
      std::pair{"FAILURE_EVIDENCE"sv, ArtifactRelationship::failure_evidence}};
  return {{id_field<ArtifactIdTag>(object, "artifact_id", path),
           sha_field(object, "sha256", path)},
          enum_field(object, "relationship", path, "DAT-ARTIFACT-RELATIONSHIP",
                     relationships)};
}

auto load_manifest(const json::Value& document) -> RunManifest {
  const auto& object = object_of(document, "$out");
  reject_unknown(object,
                 {"schema_version",
                  "protocol_version",
                  "run_id",
                  "platform_id",
                  "build_id",
                  "within_cell_ordinal",
                  "queue_provenance_id",
                  "provenance",
                  "stage",
                  "run_mode",
                  "lifecycle_state",
                  "block_id",
                  "block_role",
                  "package",
                  "requested_hardware_state",
                  "verified_hardware_state",
                  "placement",
                  "working_set_class",
                  "load_level",
                  "capacity_events",
                  "time_unit",
                  "schedule_refs",
                  "seed_refs",
                  "validity",
                  "count_reconciliation",
                  "zero_loss_status",
                  "effective_tail_status",
                  "confirmatory_estimability",
                  "confirmatory_blockers",
                  "block_completeness",
                  "join_status",
                  "counts",
                  "integrity_evidence",
                  "failure_record_ids",
                  "artifact_refs",
                  "manifest_sha256"},
                 "$out");

  const auto schema_version = version_field(object, "schema_version", "$out");
  const auto protocol_version = version_field(object, "protocol_version", "$out");
  if (schema_version != protocol_version) {
    fail(ErrorCategory::unsupported_version, "$out/protocol_version", "GOV-004",
         "schema_version and protocol_version must identify the same snapshot");
  }

  const auto stage =
      take(parse_stage(string_field(object, "stage", "$out"), "$out/stage"));
  const auto mode =
      take(parse_run_mode(string_field(object, "run_mode", "$out"), "$out/run_mode"));
  const auto lifecycle = take(parse_lifecycle_state(
      string_field(object, "lifecycle_state", "$out"), "$out/lifecycle_state"));
  const auto role = take(
      parse_block_role(string_field(object, "block_role", "$out"), "$out/block_role"));
  const auto package = take(
      parse_queue_package(string_field(object, "package", "$out"), "$out/package"));
  const auto requested_state = take(parse_requested_hardware_state(
      string_field(object, "requested_hardware_state", "$out"),
      "$out/requested_hardware_state"));
  const auto verified_state = take(parse_verified_hardware_state(
      string_field(object, "verified_hardware_state", "$out"),
      "$out/verified_hardware_state"));
  const auto placement = take(
      parse_placement(string_field(object, "placement", "$out"), "$out/placement"));
  const auto working_set = take(parse_working_set_class(
      string_field(object, "working_set_class", "$out"), "$out/working_set_class"));
  const auto load = take(
      parse_load_level(string_field(object, "load_level", "$out"), "$out/load_level"));
  const auto validity = take(
      parse_run_validity(string_field(object, "validity", "$out"), "$out/validity"));
  const auto count_reconciliation =
      take(parse_gate_status(string_field(object, "count_reconciliation", "$out"),
                             "$out/count_reconciliation"));
  const auto zero_loss = take(parse_gate_status(
      string_field(object, "zero_loss_status", "$out"), "$out/zero_loss_status"));
  const auto effective_tail =
      take(parse_gate_status(string_field(object, "effective_tail_status", "$out"),
                             "$out/effective_tail_status"));
  const auto estimability = take(parse_confirmatory_estimability(
      string_field(object, "confirmatory_estimability", "$out"),
      "$out/confirmatory_estimability"));
  std::vector<ConfirmatoryBlocker> confirmatory_blockers;
  const auto* blocker_value = optional(object, "confirmatory_blockers");
  if (protocol_version == ProtocolVersion::v2_0_0_pre_2) {
    if (blocker_value == nullptr) {
      fail(ErrorCategory::missing_field, "$out/confirmatory_blockers",
           "SCHEMA-REQUIRED",
           "2.0.0-pre.2 requires the exhaustive confirmatory blocker array");
    }
    const auto& blocker_array = array_of(*blocker_value, "$out/confirmatory_blockers");
    confirmatory_blockers.reserve(blocker_array.size());
    for (std::size_t index = 0; index < blocker_array.size(); ++index) {
      const auto path = "$out/confirmatory_blockers/" + std::to_string(index);
      confirmatory_blockers.push_back(take(
          parse_confirmatory_blocker(string_of(blocker_array[index], path), path)));
    }
  } else if (blocker_value != nullptr) {
    fail(ErrorCategory::unknown_field, "$out/confirmatory_blockers",
         "SCHEMA-ADDITIONAL", "2.0.0-pre.1 does not contain confirmatory_blockers");
  }
  const auto completeness = take(parse_block_completeness(
      string_field(object, "block_completeness", "$out"), "$out/block_completeness"));
  const auto join = take(parse_join_status(string_field(object, "join_status", "$out"),
                                           "$out/join_status"));

  std::optional<RunCounts> counts;
  if (const auto* value = optional(object, "counts")) {
    counts = run_counts(*value, "$out/counts");
  }
  std::optional<PhaseIntegrityRecord> integrity;
  if (const auto* value = optional(object, "integrity_evidence")) {
    integrity = phase_integrity(*value, "$out/integrity_evidence");
  }
  std::vector<RecordId> failures;
  const auto& failure_array = array_of(required(object, "failure_record_ids", "$out"),
                                       "$out/failure_record_ids");
  failures.reserve(failure_array.size());
  for (std::size_t index = 0; index < failure_array.size(); ++index) {
    const auto path = "$out/failure_record_ids/" + std::to_string(index);
    failures.push_back(
        take(RecordId::parse(string_of(failure_array[index], path), path)));
  }
  std::vector<TypedArtifactReference> artifacts;
  const auto& artifact_array =
      array_of(required(object, "artifact_refs", "$out"), "$out/artifact_refs");
  artifacts.reserve(artifact_array.size());
  for (std::size_t index = 0; index < artifact_array.size(); ++index) {
    artifacts.push_back(typed_artifact(artifact_array[index],
                                       "$out/artifact_refs/" + std::to_string(index)));
  }
  const std::string time_unit = unit_field(object, "time_unit", "$out");
  return {schema_version,
          protocol_version,
          id_field<RunIdTag>(object, "run_id", "$out"),
          id_field<PlatformIdTag>(object, "platform_id", "$out"),
          id_field<BuildIdTag>(object, "build_id", "$out"),
          uint_field(object, "within_cell_ordinal", "$out"),
          id_field<RecordIdTag>(object, "queue_provenance_id", "$out"),
          run_provenance(required(object, "provenance", "$out"), "$out/provenance"),
          stage,
          mode,
          lifecycle,
          id_field<BlockIdTag>(object, "block_id", "$out"),
          role,
          package,
          requested_state,
          verified_state,
          placement,
          working_set,
          load,
          uint_field(object, "capacity_events", "$out"),
          time_unit,
          run_schedule_refs(required(object, "schedule_refs", "$out"),
                            "$out/schedule_refs"),
          run_seed_refs(required(object, "seed_refs", "$out"), "$out/seed_refs"),
          validity,
          count_reconciliation,
          zero_loss,
          effective_tail,
          estimability,
          std::move(confirmatory_blockers),
          completeness,
          join,
          std::move(counts),
          std::move(integrity),
          std::move(failures),
          std::move(artifacts),
          sha_field(object, "manifest_sha256", "$out"),
          document};
}

auto load_block_plan(const json::Value& document) -> BlockPlan {
  const auto& object = object_of(document, "$out");
  reject_unknown(object,
                 {"schema_version", "protocol_version", "block_id", "platform_id",
                  "build_id", "stage", "block_role", "block_ordinal",
                  "seed_subspace_id", "replaces_block_id",
                  "replacement_authorization_id", "replacement_lineage",
                  "whole_plot_order", "cells", "access_state", "plan_sha256"},
                 "$out");
  const auto stage =
      take(parse_stage(string_field(object, "stage", "$out"), "$out/stage"));
  if (stage != Stage::stage_a) {
    fail(ErrorCategory::cross_field, "$out/stage", "BLK-STAGE-A",
         "block plans in this schema are Stage A only");
  }
  const auto role = take(
      parse_block_role(string_field(object, "block_role", "$out"), "$out/block_role"));
  if (role == BlockRole::not_applicable) {
    fail(ErrorCategory::unknown_enum, "$out/block_role", "BLK-ROLE",
         "Stage A block role cannot be NOT_APPLICABLE");
  }
  auto replaces = optional_nullable_id<BlockIdTag>(object, "replaces_block_id", "$out");
  auto authorization =
      optional_nullable_id<RecordIdTag>(object, "replacement_authorization_id", "$out");
  std::optional<ReplacementLineage> lineage;
  if (const auto* value = optional(object, "replacement_lineage");
      value != nullptr && !value->is_null()) {
    const auto& lineage_object = object_of(*value, "$out/replacement_lineage");
    reject_unknown(
        lineage_object,
        {"replaced_block_ordinal", "replaced_block_role", "replaced_seed_subspace_id"},
        "$out/replacement_lineage");
    lineage = ReplacementLineage{
        uint_field(lineage_object, "replaced_block_ordinal",
                   "$out/replacement_lineage"),
        take(parse_block_role(string_field(lineage_object, "replaced_block_role",
                                           "$out/replacement_lineage"),
                              "$out/replacement_lineage/replaced_block_role")),
        id_field<NamespaceIdTag>(lineage_object, "replaced_seed_subspace_id",
                                 "$out/replacement_lineage")};
  }
  if (replaces.has_value() != authorization.has_value() ||
      replaces.has_value() != lineage.has_value()) {
    fail(ErrorCategory::cross_field, "$out/replaces_block_id", "BLK-REPLACEMENT-SHAPE",
         "replacement identity, authorization, and lineage must be all null or all "
         "present");
  }

  const auto& plots =
      array_of(required(object, "whole_plot_order", "$out"), "$out/whole_plot_order");
  if (plots.size() != 2) {
    fail(ErrorCategory::out_of_range, "$out/whole_plot_order", "BLK-WHOLE-PLOTS",
         "whole_plot_order must contain exactly two states");
  }
  std::array<RequestedHardwareState, 2> whole_plot_order{
      take(parse_requested_hardware_state(
          string_of(plots[0], "$out/whole_plot_order/0"), "$out/whole_plot_order/0")),
      take(parse_requested_hardware_state(
          string_of(plots[1], "$out/whole_plot_order/1"), "$out/whole_plot_order/1"))};

  const auto& cell_array = array_of(required(object, "cells", "$out"), "$out/cells");
  std::vector<StageACell> cells;
  cells.reserve(cell_array.size());
  for (std::size_t index = 0; index < cell_array.size(); ++index) {
    const std::string path = "$out/cells/" + std::to_string(index);
    const auto& cell = object_of(cell_array[index], path);
    reject_unknown(cell,
                   {"cell_ordinal", "package", "requested_hardware_state", "placement",
                    "working_set_class", "load_level", "arrival_seed_ref",
                    "node_seed_ref", "event_seed_ref"},
                   path);
    cells.push_back(
        {uint_field(cell, "cell_ordinal", path),
         take(parse_queue_package(string_field(cell, "package", path),
                                  path + "/package")),
         take(parse_requested_hardware_state(
             string_field(cell, "requested_hardware_state", path),
             path + "/requested_hardware_state")),
         take(parse_placement(string_field(cell, "placement", path),
                              path + "/placement")),
         take(parse_working_set_class(string_field(cell, "working_set_class", path),
                                      path + "/working_set_class")),
         take(parse_load_level(string_field(cell, "load_level", path),
                               path + "/load_level")),
         id_field<SeedIdTag>(cell, "arrival_seed_ref", path),
         optional_nullable_id<SeedIdTag>(cell, "node_seed_ref", path),
         id_field<SeedIdTag>(cell, "event_seed_ref", path)});
  }

  return {version_field(object, "schema_version", "$out"),
          version_field(object, "protocol_version", "$out"),
          id_field<BlockIdTag>(object, "block_id", "$out"),
          id_field<PlatformIdTag>(object, "platform_id", "$out"),
          id_field<BuildIdTag>(object, "build_id", "$out"),
          stage,
          role,
          uint_field(object, "block_ordinal", "$out"),
          id_field<NamespaceIdTag>(object, "seed_subspace_id", "$out"),
          std::move(replaces),
          std::move(authorization),
          std::move(lineage),
          whole_plot_order,
          std::move(cells),
          take(parse_access_state(string_field(object, "access_state", "$out"),
                                  "$out/access_state")),
          sha_field(object, "plan_sha256", "$out"),
          document};
}

auto load_failure(const json::Value& document) -> FailureRecord {
  const auto& object = object_of(document, "$out");
  reject_unknown(object,
                 {"schema_version",
                  "protocol_version",
                  "failure_record_id",
                  "platform_id",
                  "stage",
                  "scope",
                  "run_id",
                  "block_id",
                  "build_id",
                  "category",
                  "detected_phase",
                  "observed_at_utc",
                  "description",
                  "invalidates_run",
                  "block_consequence",
                  "resolution_status",
                  "replacement_authorization_id",
                  "replacement_block_id",
                  "supersedes_id",
                  "evidence_refs",
                  "record_sha256"},
                 "$out");
  constexpr std::array scopes{std::pair{"RUN"sv, FailureScope::run},
                              std::pair{"BLOCK"sv, FailureScope::block},
                              std::pair{"PLATFORM"sv, FailureScope::platform},
                              std::pair{"BUILD"sv, FailureScope::build},
                              std::pair{"PROTOCOL"sv, FailureScope::protocol},
                              std::pair{"ACCESS"sv, FailureScope::access}};
  constexpr std::array categories{
      std::pair{"CORRECTNESS"sv, FailureCategory::correctness},
      std::pair{"COUNT_RECONCILIATION"sv, FailureCategory::count_reconciliation},
      std::pair{"CLOCK"sv, FailureCategory::clock},
      std::pair{"AFFINITY"sv, FailureCategory::affinity},
      std::pair{"NUMA"sv, FailureCategory::numa},
      std::pair{"HARDWARE_STATE"sv, FailureCategory::hardware_state},
      std::pair{"PROCESS_INTERRUPTION"sv, FailureCategory::process_interruption},
      std::pair{"SAMPLE_LOSS"sv, FailureCategory::sample_loss},
      std::pair{"BUFFER_OVERFLOW"sv, FailureCategory::buffer_overflow},
      std::pair{"CORRUPT_OUTPUT"sv, FailureCategory::corrupt_output},
      std::pair{"MANIFEST"sv, FailureCategory::manifest},
      std::pair{"ADDRESS_PATTERN"sv, FailureCategory::address_pattern},
      std::pair{"PHASE_RESET"sv, FailureCategory::phase_reset},
      std::pair{"ENVIRONMENT"sv, FailureCategory::environment},
      std::pair{"ACCESS_LEAKAGE"sv, FailureCategory::access_leakage},
      std::pair{"OTHER_MEASUREMENT"sv, FailureCategory::other_measurement}};
  constexpr std::array phases{std::pair{"PRE_RUN"sv, DetectedPhase::pre_run},
                              std::pair{"WARMUP"sv, DetectedPhase::warmup},
                              std::pair{"RESET"sv, DetectedPhase::reset},
                              std::pair{"MEASUREMENT"sv, DetectedPhase::measurement},
                              std::pair{"DRAIN"sv, DetectedPhase::drain},
                              std::pair{"POST_RUN"sv, DetectedPhase::post_run},
                              std::pair{"ANALYSIS"sv, DetectedPhase::analysis},
                              std::pair{"ACCESS_AUDIT"sv, DetectedPhase::access_audit}};
  constexpr std::array consequences{
      std::pair{"NONE"sv, BlockConsequence::none},
      std::pair{"ORIGINAL_BLOCK_INCOMPLETE"sv,
                BlockConsequence::original_block_incomplete},
      std::pair{"STUDY_UNRESOLVED"sv, BlockConsequence::study_unresolved},
      std::pair{"NOT_APPLICABLE"sv, BlockConsequence::not_applicable}};
  constexpr std::array resolutions{
      std::pair{"OPEN"sv, ResolutionStatus::open},
      std::pair{"RETAINED_DIAGNOSTIC_ONLY"sv,
                ResolutionStatus::retained_diagnostic_only},
      std::pair{"REPLACEMENT_AUTHORIZED"sv, ResolutionStatus::replacement_authorized},
      std::pair{"REPLACEMENT_DENIED"sv, ResolutionStatus::replacement_denied},
      std::pair{"RESOLVED_BEFORE_MEASUREMENT"sv,
                ResolutionStatus::resolved_before_measurement},
      std::pair{"STUDY_STOPPED"sv, ResolutionStatus::study_stopped}};
  const auto scope = enum_field(object, "scope", "$out", "FAIL-SCOPE", scopes);
  const auto run_id = optional_nullable_id<RunIdTag>(object, "run_id", "$out");
  const auto block_id = optional_nullable_id<BlockIdTag>(object, "block_id", "$out");
  if (scope == FailureScope::run && (!run_id || !block_id)) {
    fail(ErrorCategory::missing_field, "$out/run_id", "FAIL-RUN-IDENTITY",
         "run-scoped failures require both run_id and block_id");
  }
  const auto status =
      enum_field(object, "resolution_status", "$out", "FAIL-RESOLUTION", resolutions);
  auto replacement_auth =
      optional_nullable_id<RecordIdTag>(object, "replacement_authorization_id", "$out");
  auto replacement_block =
      optional_nullable_id<BlockIdTag>(object, "replacement_block_id", "$out");
  if (status == ResolutionStatus::replacement_authorized &&
      (!replacement_auth || !replacement_block)) {
    fail(ErrorCategory::missing_field, "$out/replacement_authorization_id",
         "FAIL-REPLACEMENT-EVIDENCE",
         "authorized replacement requires authorization and replacement block IDs");
  }
  return {version_field(object, "schema_version", "$out"),
          version_field(object, "protocol_version", "$out"),
          id_field<RecordIdTag>(object, "failure_record_id", "$out"),
          id_field<PlatformIdTag>(object, "platform_id", "$out"),
          take(parse_stage(string_field(object, "stage", "$out"), "$out/stage")),
          scope,
          run_id,
          block_id,
          optional_nullable_id<BuildIdTag>(object, "build_id", "$out"),
          enum_field(object, "category", "$out", "FAIL-CATEGORY", categories),
          enum_field(object, "detected_phase", "$out", "FAIL-PHASE", phases),
          string_field(object, "observed_at_utc", "$out"),
          string_field(object, "description", "$out"),
          bool_field(object, "invalidates_run", "$out"),
          enum_field(object, "block_consequence", "$out", "FAIL-BLOCK-CONSEQUENCE",
                     consequences),
          status,
          std::move(replacement_auth),
          std::move(replacement_block),
          optional_nullable_id<RecordIdTag>(object, "supersedes_id", "$out"),
          artifact_reference_array(required(object, "evidence_refs", "$out"),
                                   "$out/evidence_refs", true),
          sha_field(object, "record_sha256", "$out"),
          document};
}

auto optional_artifact_ref(const Object& object, std::string_view key,
                           const std::string& path)
    -> std::optional<ArtifactReference> {
  const auto* value = optional(object, key);
  if (value == nullptr) {
    return std::nullopt;
  }
  return artifact_reference(*value, path + "/" + std::string(key));
}

auto optional_string(const Object& object, std::string_view key,
                     const std::string& path, bool nullable = false)
    -> std::optional<std::string> {
  const auto* value = optional(object, key);
  if (value == nullptr || (nullable && value->is_null())) {
    return std::nullopt;
  }
  return string_of(*value, path + "/" + std::string(key), true);
}

auto load_freeze(const json::Value& document) -> FreezeRecord {
  const auto& object = object_of(document, "$out");
  reject_unknown(object,
                 {"schema_version",
                  "protocol_version",
                  "record_id",
                  "record_kind",
                  "decision_id",
                  "readiness_boundary",
                  "status",
                  "authorization_status",
                  "created_at_utc",
                  "authority",
                  "decision_value",
                  "rationale",
                  "access_state_before",
                  "access_state_after",
                  "affected_block_ids",
                  "h3_selections",
                  "training_input_artifacts",
                  "selection_rule_version",
                  "selection_record_checksum_sha256",
                  "selection_record_ref",
                  "validation_namespace_id",
                  "validation_artifact_ref",
                  "validation_unseal_record_ref",
                  "h3_evaluation_artifact_ref",
                  "h3_access_record_ref",
                  "replacement",
                  "supersedes_id",
                  "prior_protocol_version",
                  "new_protocol_version",
                  "affected_documents",
                  "affected_schema_ids",
                  "affected_estimands",
                  "affected_contrast_ids",
                  "pilot_record_disposition",
                  "prior_authoritative_hashes",
                  "outcome_access_prohibited",
                  "input_artifacts",
                  "record_sha256"},
                 "$out");
  constexpr std::array record_kinds{
      std::pair{"PROTOCOL_FREEZE"sv, RecordKind::protocol_freeze},
      std::pair{"SELECTION_FREEZE"sv, RecordKind::selection_freeze},
      std::pair{"VALIDATION_UNSEAL"sv, RecordKind::validation_unseal},
      std::pair{"H3_EVALUATED"sv, RecordKind::h3_evaluated},
      std::pair{"H1H2_RELEASED"sv, RecordKind::h1h2_released},
      std::pair{"REPLACEMENT_AUTHORIZATION"sv, RecordKind::replacement_authorization},
      std::pair{"AMENDMENT"sv, RecordKind::amendment}};
  constexpr std::array boundaries{
      std::pair{"READY_FOR_IMPLEMENTATION"sv,
                ReadinessBoundary::ready_for_implementation},
      std::pair{"BLOCKED_BEFORE_IMPLEMENTATION"sv,
                ReadinessBoundary::blocked_before_implementation},
      std::pair{"BLOCKED_BEFORE_PILOT"sv, ReadinessBoundary::blocked_before_pilot},
      std::pair{"BLOCKED_BEFORE_CONFIRMATORY_EXECUTION"sv,
                ReadinessBoundary::blocked_before_confirmatory_execution},
      std::pair{"SUBMISSION_ONLY"sv, ReadinessBoundary::submission_only}};
  constexpr std::array statuses{std::pair{"OPEN"sv, FreezeStatus::open},
                                std::pair{"FROZEN"sv, FreezeStatus::frozen},
                                std::pair{"AUTHORIZED"sv, FreezeStatus::authorized},
                                std::pair{"REJECTED"sv, FreezeStatus::rejected},
                                std::pair{"SUPERSEDED"sv, FreezeStatus::superseded}};
  constexpr std::array authorization_statuses{
      std::pair{"NOT_APPLICABLE"sv, AuthorizationStatus::not_applicable},
      std::pair{"PENDING"sv, AuthorizationStatus::pending},
      std::pair{"AUTHORIZED"sv, AuthorizationStatus::authorized},
      std::pair{"REJECTED"sv, AuthorizationStatus::rejected}};
  constexpr std::array authority_roles{
      std::pair{"PROTOCOL_OWNER"sv, AuthorityRole::protocol_owner},
      std::pair{"FREEZE_AUTHORITY"sv, AuthorityRole::freeze_authority},
      std::pair{"VALIDATION_CUSTODIAN"sv, AuthorityRole::validation_custodian},
      std::pair{"CONFIRMATORY_ANALYST"sv, AuthorityRole::confirmatory_analyst},
      std::pair{"REPLACEMENT_AUTHORITY"sv, AuthorityRole::replacement_authority},
      std::pair{"PLATFORM_OPERATOR"sv, AuthorityRole::platform_operator},
      std::pair{"AUTHOR"sv, AuthorityRole::author}};
  constexpr std::array access_classes{
      std::pair{"TREATMENT_BLIND"sv, AccessClass::treatment_blind},
      std::pair{"TRAINING_ONLY"sv, AccessClass::training_only},
      std::pair{"VALIDATION_SEALED"sv, AccessClass::validation_sealed},
      std::pair{"VALIDATION_UNSEALED"sv, AccessClass::validation_unsealed},
      std::pair{"PUBLIC_PROTOCOL"sv, AccessClass::public_protocol},
      std::pair{"PLATFORM_EVIDENCE"sv, AccessClass::platform_evidence}};

  const auto kind =
      enum_field(object, "record_kind", "$out", "ACC-RECORD-KIND", record_kinds);
  const auto& authority_object =
      object_of(required(object, "authority", "$out"), "$out/authority");
  reject_unknown(authority_object,
                 {"authority_id", "role", "attestation", "signature_artifact_id"},
                 "$out/authority");
  Authority authority{
      id_field<AuthorityIdTag>(authority_object, "authority_id", "$out/authority"),
      enum_field(authority_object, "role", "$out/authority", "ACC-AUTHORITY-ROLE",
                 authority_roles),
      string_field(authority_object, "attestation", "$out/authority"),
      optional_nullable_id<ArtifactIdTag>(authority_object, "signature_artifact_id",
                                          "$out/authority")};

  std::vector<BlockId> affected_blocks;
  if (const auto* value = optional(object, "affected_block_ids")) {
    const auto& array = array_of(*value, "$out/affected_block_ids");
    affected_blocks.reserve(array.size());
    for (std::size_t index = 0; index < array.size(); ++index) {
      const auto path = "$out/affected_block_ids/" + std::to_string(index);
      affected_blocks.push_back(
          take(BlockId::parse(string_of(array[index], path), path)));
    }
  }

  const std::array<std::pair<std::string_view, H3Context>, 6> context_names{
      std::pair{"NEAR_L2_L050"sv, H3Context::near_l2_l050},
      std::pair{"NEAR_LLC_L050"sv, H3Context::near_llc_l050},
      std::pair{"NEAR_BEYOND_LLC_L050"sv, H3Context::near_beyond_llc_l050},
      std::pair{"FAR_L2_L050"sv, H3Context::far_l2_l050},
      std::pair{"FAR_LLC_L050"sv, H3Context::far_llc_l050},
      std::pair{"FAR_BEYOND_LLC_L050"sv, H3Context::far_beyond_llc_l050}};
  std::map<H3Context, H3Candidate> selections;
  if (const auto* value = optional(object, "h3_selections")) {
    const auto& selection_object = object_of(*value, "$out/h3_selections");
    reject_unknown(selection_object,
                   {"NEAR_L2_L050", "NEAR_LLC_L050", "NEAR_BEYOND_LLC_L050",
                    "FAR_L2_L050", "FAR_LLC_L050", "FAR_BEYOND_LLC_L050"},
                   "$out/h3_selections");
    for (const auto& [name, context] : context_names) {
      const std::string path = "$out/h3_selections/" + std::string(name);
      const auto& candidate =
          object_of(required(selection_object, name, "$out/h3_selections"), path);
      reject_unknown(candidate, {"package", "requested_hardware_state"}, path);
      auto package = take(parse_queue_package(string_field(candidate, "package", path),
                                              path + "/package"));
      auto state = take(parse_requested_hardware_state(
          string_field(candidate, "requested_hardware_state", path),
          path + "/requested_hardware_state"));
      if (package == QueuePackage::nblfq_mpsc ||
          package == QueuePackage::not_applicable ||
          state == RequestedHardwareState::not_applicable) {
        fail(ErrorCategory::unknown_enum, path, "ACC-H3-CANDIDATE",
             "H3 candidate must be one of the ten Stage A package/state candidates");
      }
      selections.emplace(context, H3Candidate{package, state});
    }
  }

  std::vector<ArtifactReference> training_inputs;
  if (const auto* value = optional(object, "training_input_artifacts")) {
    training_inputs =
        artifact_reference_array(*value, "$out/training_input_artifacts", true);
  }
  std::optional<Sha256> selection_checksum;
  if (optional(object, "selection_record_checksum_sha256") != nullptr) {
    selection_checksum = sha_field(object, "selection_record_checksum_sha256", "$out");
  }
  std::optional<ReplacementAuthorization> replacement;
  if (const auto* value = optional(object, "replacement")) {
    const auto& replacement_object = object_of(*value, "$out/replacement");
    reject_unknown(replacement_object,
                   {"original_block_id", "replacement_block_id",
                    "replacement_block_ordinal", "block_role",
                    "replacement_seed_subspace_id", "failure_record_id",
                    "replacement_budget_record_id"},
                   "$out/replacement");
    replacement = ReplacementAuthorization{
        id_field<BlockIdTag>(replacement_object, "original_block_id",
                             "$out/replacement"),
        id_field<BlockIdTag>(replacement_object, "replacement_block_id",
                             "$out/replacement"),
        uint_field(replacement_object, "replacement_block_ordinal", "$out/replacement"),
        take(parse_block_role(
            string_field(replacement_object, "block_role", "$out/replacement"),
            "$out/replacement/block_role")),
        id_field<NamespaceIdTag>(replacement_object, "replacement_seed_subspace_id",
                                 "$out/replacement"),
        id_field<RecordIdTag>(replacement_object, "failure_record_id",
                              "$out/replacement"),
        id_field<RecordIdTag>(replacement_object, "replacement_budget_record_id",
                              "$out/replacement")};
  }

  auto optional_string_array = [&](std::string_view key, bool require_nonempty) {
    const auto* value = optional(object, key);
    return value == nullptr
               ? std::vector<std::string>{}
               : string_array(*value, "$out/" + std::string(key), require_nonempty);
  };
  std::vector<ArtifactReference> prior_hashes;
  if (const auto* value = optional(object, "prior_authoritative_hashes")) {
    prior_hashes =
        artifact_reference_array(*value, "$out/prior_authoritative_hashes", true);
  }
  std::vector<AccessInputArtifact> inputs;
  const auto& input_array =
      array_of(required(object, "input_artifacts", "$out"), "$out/input_artifacts");
  if (input_array.empty()) {
    fail(ErrorCategory::out_of_range, "$out/input_artifacts", "SCHEMA-MIN-ITEMS",
         "freeze record requires at least one input artifact");
  }
  inputs.reserve(input_array.size());
  for (std::size_t index = 0; index < input_array.size(); ++index) {
    const auto path = "$out/input_artifacts/" + std::to_string(index);
    const auto& item = object_of(input_array[index], path);
    reject_unknown(item, {"artifact_id", "sha256", "access_class"}, path);
    inputs.push_back(
        {{id_field<ArtifactIdTag>(item, "artifact_id", path),
          sha_field(item, "sha256", path)},
         enum_field(item, "access_class", path, "ACC-ACCESS-CLASS", access_classes)});
  }

  std::optional<json::Value> decision_value;
  if (const auto* value = optional(object, "decision_value")) {
    decision_value = *value;
  }
  return {
      version_field(object, "schema_version", "$out"),
      version_field(object, "protocol_version", "$out"),
      id_field<RecordIdTag>(object, "record_id", "$out"),
      kind,
      string_field(object, "decision_id", "$out"),
      enum_field(object, "readiness_boundary", "$out", "ACC-READINESS", boundaries),
      enum_field(object, "status", "$out", "ACC-STATUS", statuses),
      enum_field(object, "authorization_status", "$out", "ACC-AUTHORIZATION",
                 authorization_statuses),
      string_field(object, "created_at_utc", "$out"),
      std::move(authority),
      std::move(decision_value),
      optional_string(object, "rationale", "$out"),
      take(parse_access_state(string_field(object, "access_state_before", "$out"),
                              "$out/access_state_before")),
      take(parse_access_state(string_field(object, "access_state_after", "$out"),
                              "$out/access_state_after")),
      bool_field(object, "outcome_access_prohibited", "$out"),
      std::move(affected_blocks),
      std::move(selections),
      std::move(training_inputs),
      optional_string(object, "selection_rule_version", "$out"),
      selection_checksum,
      optional_artifact_ref(object, "selection_record_ref", "$out"),
      optional_nullable_id<NamespaceIdTag>(object, "validation_namespace_id", "$out"),
      optional_artifact_ref(object, "validation_artifact_ref", "$out"),
      optional_artifact_ref(object, "validation_unseal_record_ref", "$out"),
      optional_artifact_ref(object, "h3_evaluation_artifact_ref", "$out"),
      optional_artifact_ref(object, "h3_access_record_ref", "$out"),
      std::move(replacement),
      optional_nullable_id<RecordIdTag>(object, "supersedes_id", "$out"),
      optional_string(object, "prior_protocol_version", "$out", true),
      optional_string(object, "new_protocol_version", "$out", true),
      optional_string_array("affected_documents", true),
      optional_string_array("affected_schema_ids", true),
      optional_string_array("affected_estimands", true),
      optional_string_array("affected_contrast_ids", false),
      optional_string(object, "pilot_record_disposition", "$out"),
      std::move(prior_hashes),
      std::move(inputs),
      sha_field(object, "record_sha256", "$out"),
      document};
}

auto load_platform(const json::Value& document) -> PlatformRecord {
  const auto& object = object_of(document, "$out");
  reject_unknown(object,
                 {"schema_version", "protocol_version", "platform_id", "cpu",
                  "topology", "memory", "software", "clock", "hardware_prefetch_states",
                  "record_sha256"},
                 "$out");
  const auto& cpu = object_of(required(object, "cpu", "$out"), "$out/cpu");
  reject_unknown(cpu,
                 {"vendor", "model", "stepping", "microcode", "cache_line_bytes",
                  "atomic_width_bits", "atomic_alignment_bytes"},
                 "$out/cpu");
  PlatformCpu typed_cpu{string_field(cpu, "vendor", "$out/cpu"),
                        string_field(cpu, "model", "$out/cpu"),
                        string_field(cpu, "stepping", "$out/cpu"),
                        string_field(cpu, "microcode", "$out/cpu"),
                        uint_field(cpu, "cache_line_bytes", "$out/cpu"),
                        uint_field(cpu, "atomic_width_bits", "$out/cpu"),
                        uint_field(cpu, "atomic_alignment_bytes", "$out/cpu")};

  const auto& topology =
      object_of(required(object, "topology", "$out"), "$out/topology");
  reject_unknown(topology,
                 {"sockets", "numa_nodes", "physical_cores", "smt_enabled",
                  "cache_domains", "near_core_pair", "far_core_pair"},
                 "$out/topology");
  const auto pair = [&](std::string_view key) {
    const auto& values = array_of(required(topology, key, "$out/topology"),
                                  "$out/topology/" + std::string(key));
    if (values.size() != 2) {
      fail(ErrorCategory::out_of_range, "$out/topology/" + std::string(key),
           "PLATFORM-CORE-PAIR", "core pair requires exactly two CPU identifiers");
    }
    return std::array<std::uint64_t, 2>{
        uint_of(values[0], "$out/topology/" + std::string(key) + "/0"),
        uint_of(values[1], "$out/topology/" + std::string(key) + "/1")};
  };
  PlatformTopology typed_topology{
      uint_field(topology, "sockets", "$out/topology"),
      uint_field(topology, "numa_nodes", "$out/topology"),
      uint_field(topology, "physical_cores", "$out/topology"),
      bool_field(topology, "smt_enabled", "$out/topology"),
      string_array(required(topology, "cache_domains", "$out/topology"),
                   "$out/topology/cache_domains", true),
      pair("near_core_pair"),
      pair("far_core_pair")};

  const auto& memory = object_of(required(object, "memory", "$out"), "$out/memory");
  reject_unknown(memory,
                 {"population", "base_page_bytes", "residency_verification_method"},
                 "$out/memory");
  PlatformMemory typed_memory{
      string_field(memory, "population", "$out/memory"),
      uint_field(memory, "base_page_bytes", "$out/memory"),
      string_field(memory, "residency_verification_method", "$out/memory")};

  const auto& software =
      object_of(required(object, "software", "$out"), "$out/software");
  reject_unknown(software,
                 {"operating_system", "kernel", "compiler", "standard_library",
                  "language_standard", "flags", "link_mode"},
                 "$out/software");
  PlatformSoftware typed_software{
      string_field(software, "operating_system", "$out/software"),
      string_field(software, "kernel", "$out/software"),
      string_field(software, "compiler", "$out/software"),
      string_field(software, "standard_library", "$out/software"),
      string_field(software, "language_standard", "$out/software"),
      string_array(required(software, "flags", "$out/software"), "$out/software/flags",
                   false),
      string_field(software, "link_mode", "$out/software")};

  const auto& clock = object_of(required(object, "clock", "$out"), "$out/clock");
  reject_unknown(clock,
                 {"source", "time_unit", "conversion_record_id",
                  "serialization_record_id", "acceptance_record_id"},
                 "$out/clock");
  PlatformClock typed_clock{
      string_field(clock, "source", "$out/clock"),
      unit_field(clock, "time_unit", "$out/clock"),
      id_field<RecordIdTag>(clock, "conversion_record_id", "$out/clock"),
      id_field<RecordIdTag>(clock, "serialization_record_id", "$out/clock"),
      id_field<RecordIdTag>(clock, "acceptance_record_id", "$out/clock")};

  const auto& hardware_states =
      array_of(required(object, "hardware_prefetch_states", "$out"),
               "$out/hardware_prefetch_states");
  if (hardware_states.size() < 2) {
    fail(ErrorCategory::out_of_range, "$out/hardware_prefetch_states",
         "HWP-STATE-COUNT",
         "platform record requires at least two requested hardware states");
  }
  std::vector<RequestedAndVerifiedHardwareState> typed_states;
  typed_states.reserve(hardware_states.size());
  for (std::size_t index = 0; index < hardware_states.size(); ++index) {
    const auto path = "$out/hardware_prefetch_states/" + std::to_string(index);
    const auto& state = object_of(hardware_states[index], path);
    reject_unknown(state,
                   {"requested", "verified", "readback_artifact_id",
                    "behavioral_probe_artifact_id", "privileged_authority_id"},
                   path);
    typed_states.push_back(
        {take(parse_requested_hardware_state(string_field(state, "requested", path),
                                             path + "/requested")),
         take(parse_verified_hardware_state(string_field(state, "verified", path),
                                            path + "/verified")),
         id_field<ArtifactIdTag>(state, "readback_artifact_id", path),
         id_field<ArtifactIdTag>(state, "behavioral_probe_artifact_id", path),
         id_field<AuthorityIdTag>(state, "privileged_authority_id", path)});
  }
  return {version_field(object, "schema_version", "$out"),
          version_field(object, "protocol_version", "$out"),
          id_field<PlatformIdTag>(object, "platform_id", "$out"),
          std::move(typed_cpu),
          std::move(typed_topology),
          std::move(typed_memory),
          std::move(typed_software),
          std::move(typed_clock),
          std::move(typed_states),
          sha_field(object, "record_sha256", "$out"),
          document};
}

} // namespace

auto load_document(DocumentKind kind, std::string_view json_text)
    -> Result<ProtocolRecord> {
  auto parsed = json::parse(json_text);
  if (!parsed) {
    return Result<ProtocolRecord>::failure(parsed.errors());
  }
  return load_document(kind, parsed.value());
}

auto load_document(DocumentKind kind, const json::Value& document)
    -> Result<ProtocolRecord> {
  try {
    switch (kind) {
    case DocumentKind::platform:
      return Result<ProtocolRecord>::success(ProtocolRecord{load_platform(document)});
    case DocumentKind::schedule:
      return Result<ProtocolRecord>::success(ProtocolRecord{load_schedule(document)});
    case DocumentKind::raw_observation:
      return Result<ProtocolRecord>::success(ProtocolRecord{load_raw(document)});
    case DocumentKind::run_manifest:
      return Result<ProtocolRecord>::success(ProtocolRecord{load_manifest(document)});
    case DocumentKind::block_plan:
      return Result<ProtocolRecord>::success(ProtocolRecord{load_block_plan(document)});
    case DocumentKind::failure_record:
      return Result<ProtocolRecord>::success(ProtocolRecord{load_failure(document)});
    case DocumentKind::freeze_record:
      return Result<ProtocolRecord>::success(ProtocolRecord{load_freeze(document)});
    }
  } catch (const LoadFailure& failure) {
    return Result<ProtocolRecord>::failure(failure.errors());
  }
  return Result<ProtocolRecord>::failure(
      {ErrorCategory::unknown_enum, "$", "DAT-DOCUMENT-KIND", "unknown document kind"});
}

auto amendment_view(const FreezeRecord& record) -> Result<AmendmentRecord> {
  if (record.record_kind != RecordKind::amendment || !record.supersedes_id ||
      !record.prior_protocol_version || !record.new_protocol_version ||
      record.affected_documents.empty() || record.affected_schema_ids.empty() ||
      record.affected_estimands.empty() || record.prior_authoritative_hashes.empty()) {
    return Result<AmendmentRecord>::failure(
        {ErrorCategory::missing_evidence, "$out", "GOV-AMENDMENT-SHAPE",
         "amendment view requires every protocol amendment evidence field"});
  }
  return Result<AmendmentRecord>::success(
      {record.record_id, *record.supersedes_id, *record.prior_protocol_version,
       *record.new_protocol_version, record.affected_documents,
       record.affected_schema_ids, record.affected_estimands,
       record.affected_contrast_ids, record.prior_authoritative_hashes,
       record.record_sha256});
}

auto source_document(const ProtocolRecord& record) -> const json::Value& {
  return std::visit(
      [](const auto& typed) -> const json::Value& { return typed.source_document; },
      record);
}

auto ScientificConfiguration::load(DocumentKind kind, std::string_view text)
    -> Result<ScientificConfiguration> {
  auto record = load_document(kind, text);
  if (!record) {
    return Result<ScientificConfiguration>::failure(record.errors());
  }
  Stage4SemanticValidator validator;
  auto errors = validator.validate(record.value());
  if (!errors.empty()) {
    return Result<ScientificConfiguration>::failure(std::move(errors));
  }
  return Result<ScientificConfiguration>::success(
      ScientificConfiguration(std::move(record).value()));
}

} // namespace cpu_prefetch::protocol
