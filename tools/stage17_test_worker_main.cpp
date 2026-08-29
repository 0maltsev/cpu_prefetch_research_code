#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/runner/runner.hpp"
#include "cpu_prefetch/runner/stage17_fixed_action.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <exception>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <tuple>
#include <utility>
#include <vector>

#if defined(__SANITIZE_ADDRESS__)
extern "C" const char* __asan_default_options() { return "detect_leaks=0"; }
#elif defined(__has_feature)
#if __has_feature(address_sanitizer)
extern "C" const char* __asan_default_options() { return "detect_leaks=0"; }
#endif
#endif

namespace {

using namespace std::string_view_literals;

using cpu_prefetch::protocol::ErrorCategory;
using cpu_prefetch::protocol::Result;
using cpu_prefetch::protocol::ValidationError;
using cpu_prefetch::runner::stage17::ActionOutcome;
using cpu_prefetch::runner::stage17::ArtifactPayload;
using cpu_prefetch::runner::stage17::ArtifactSink;
using cpu_prefetch::runner::stage17::FixedAction;
using cpu_prefetch::runner::stage17::FixedActionOperations;

using JsonArray = cpu_prefetch::protocol::json::Value::Array;
using JsonObject = cpu_prefetch::protocol::json::Value::Object;
using JsonValue = cpu_prefetch::protocol::json::Value;

[[nodiscard]] auto string_value(std::string_view value) -> JsonValue {
  return JsonValue(std::string(value));
}

[[nodiscard]] auto uint_value(std::uint64_t value) -> JsonValue {
  return JsonValue(cpu_prefetch::protocol::json::Number{
      cpu_prefetch::protocol::json::Number::Kind::unsigned_integer,
      std::to_string(value), value});
}

[[nodiscard]] auto member(const JsonObject& object, std::string_view key)
    -> const JsonValue* {
  const auto found = object.find(key);
  return found == object.end() ? nullptr : &found->second;
}

[[nodiscard]] auto string_member(const JsonObject& object, std::string_view key)
    -> const std::string* {
  const auto* value = member(object, key);
  return value == nullptr ? nullptr : value->as_string();
}

[[nodiscard]] auto uint_member(const JsonObject& object, std::string_view key)
    -> std::optional<std::uint64_t> {
  const auto* value = member(object, key);
  const auto* number = value == nullptr ? nullptr : value->as_number();
  if (number == nullptr ||
      number->kind != cpu_prefetch::protocol::json::Number::Kind::unsigned_integer) {
    return std::nullopt;
  }
  return std::get<std::uint64_t>(number->value);
}

[[nodiscard]] auto encoded(JsonObject object) -> std::vector<std::byte> {
  const auto canonical =
      cpu_prefetch::protocol::json::canonicalize(JsonValue(std::move(object)));
  if (!canonical) {
    throw std::runtime_error("synthetic typed fixture serialization failed");
  }
  std::vector<std::byte> result(canonical.value().size());
  std::memcpy(result.data(), canonical.value().data(), result.size());
  return result;
}

[[nodiscard]] auto publish(ArtifactSink& sink, std::string role, std::string schema,
                           std::string media, std::string name,
                           std::vector<std::byte> payload)
    -> Result<cpu_prefetch::runner::stage17::ArtifactBinding> {
  return sink.publish({std::move(role), std::move(schema), std::move(media),
                       std::move(name), std::move(payload)});
}

[[nodiscard]] auto fake_hash(char character) -> std::string {
  return std::string(64U, character);
}

void append_u32(std::vector<std::byte>& output, std::uint32_t value) {
  for (std::uint32_t shift = 0U; shift < 32U; shift += 8U) {
    output.push_back(static_cast<std::byte>((value >> shift) & 0xffU));
  }
}

void append_u64(std::vector<std::byte>& output, std::uint64_t value) {
  for (std::uint32_t shift = 0U; shift < 64U; shift += 8U) {
    output.push_back(static_cast<std::byte>((value >> shift) & 0xffU));
  }
}

void append_prefix(std::vector<std::byte>& output, std::string_view run_id) {
  append_u32(output, static_cast<std::uint32_t>(run_id.size()));
  for (const auto value : run_id) {
    output.push_back(static_cast<std::byte>(value));
  }
  while ((output.size() % 8U) != 0U) {
    output.push_back(std::byte{0});
  }
}

[[nodiscard]] auto synthetic_raw_rows(std::string_view run_id, std::uint64_t count)
    -> std::array<std::vector<std::byte>, 3U> {
  std::array<std::vector<std::byte>, 3U> result;
  for (std::uint64_t logical = 0U; logical < count; ++logical) {
    const auto base = logical * 100U;
    append_prefix(result[0], run_id);
    for (const auto value : std::array<std::uint64_t, 15U>{
             logical, logical % 2U, base, 0U, base + 1U, 0U, base + 2U, 0U, base + 3U,
             0U, base + 4U, 0U, base + 5U, logical, 15U}) {
      append_u64(result[0], value);
    }
    append_prefix(result[1], run_id);
    for (const auto value :
         std::array<std::uint64_t, 10U>{logical, logical % 2U, 0U, base + 6U, 0U,
                                        base + 7U, 0U, base + 8U, 0U, base + 9U}) {
      append_u64(result[1], value);
    }
    append_prefix(result[2], run_id);
    for (const auto value : std::array<std::uint64_t, 24U>{
             logical,   logical,   logical % 2U, logical,   logical,   base,
             base + 1U, base + 2U, base + 3U,    base + 4U, base + 5U, base + 6U,
             base + 7U, base + 8U, base + 9U,    1U,        1U,        2U,
             4U,        3U,        2U,           2U,        1U,        9U}) {
      append_u64(result[2], value);
    }
  }
  return result;
}

[[nodiscard]] auto msr_values(std::string_view value) -> JsonArray {
  JsonArray result;
  for (const auto cpu : {0U, 1U, 26U}) {
    result.emplace_back(JsonObject{{"cpu", uint_value(cpu)},
                                   {"complete_value_hex", string_value(value)}});
  }
  return result;
}

[[nodiscard]] auto
publish_calibration_hardware(FixedAction action, const JsonObject& inputs,
                             std::size_t run_count, ArtifactSink& sink)
    -> Result<cpu_prefetch::runner::stage17::ArtifactBinding> {
  const auto* plan = string_member(inputs, "plan_sha256");
  const auto* value = member(inputs, "hardware_control");
  const auto* control = value == nullptr ? nullptr : value->as_object();
  const auto* q15w =
      control == nullptr ? nullptr : string_member(*control, "q15_w_result_sha256");
  if (plan == nullptr || q15w == nullptr) {
    return Result<cpu_prefetch::runner::stage17::ArtifactBinding>::failure(
        ValidationError{ErrorCategory::cross_field, "$/action_inputs/hardware_control",
                        "S17-TEST-Q16-HARDWARE",
                        "synthetic calibration hardware binding is absent"});
  }
  const auto action_id = std::string(cpu_prefetch::runner::stage17::to_string(action));
  return publish(
      sink, "STAGE17_CALIBRATION_HARDWARE_STATE",
      "cpu-prefetch-stage17-calibration-hardware-state/1", "application/json",
      "stage17-" + action_id + "-hardware-state-v1.json",
      encoded({
          {"schema_version",
           string_value("cpu-prefetch-stage17-calibration-hardware-state/1")},
          {"action_id", string_value(action_id)},
          {"plan_sha256", string_value(*plan)},
          {"mapping_id", string_value("INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1")},
          {"q15_w_result_sha256", string_value(*q15w)},
          {"whole_plot_order",
           JsonValue(JsonArray{string_value("H0"), string_value("H1")})},
          {"apply_readback", JsonValue(msr_values("000000000000000f"))},
          {"restore_readback", JsonValue(msr_values("0000000000000000"))},
          {"run_count", uint_value(run_count)},
          {"restoration_verified", JsonValue(true)},
          {"phase18_authority", JsonValue(false)},
      }));
}

[[nodiscard]] auto run_payloads(FixedAction action, const JsonObject& run,
                                const std::string& prefix, ArtifactSink& sink)
    -> Result<std::vector<cpu_prefetch::runner::stage17::ArtifactBinding>> {
  const auto* run_id = string_member(run, "run_id");
  const auto* plan = string_member(run, "plan_sha256");
  const auto* schedule = string_member(run, "schedule_sha256");
  const auto* seed = string_member(run, "seed_id");
  const auto* admission = string_member(run, "runner_admission_sha256");
  const auto* package = string_member(run, "package");
  const auto offered = uint_member(run, "offered_count");
  if (run_id == nullptr || plan == nullptr || schedule == nullptr || seed == nullptr ||
      admission == nullptr || package == nullptr || !offered || *offered == 0U) {
    return Result<std::vector<cpu_prefetch::runner::stage17::ArtifactBinding>>::failure(
        ValidationError{ErrorCategory::cross_field, "$/action_inputs", "S17-TEST-RUN",
                        "synthetic run fixture is incomplete"});
  }
  if ((action == FixedAction::blinded_pilot || action == FixedAction::q16b ||
       action == FixedAction::q16c) &&
      (member(run, "cell_ordinal") == nullptr ||
       member(run, "repetition_ordinal") == nullptr ||
       member(run, "hardware_state") == nullptr ||
       member(run, "placement") == nullptr ||
       member(run, "working_set_class") == nullptr ||
       ((action == FixedAction::blinded_pilot || action == FixedAction::q16c) &&
        member(run, "load_level") == nullptr))) {
    return Result<std::vector<cpu_prefetch::runner::stage17::ArtifactBinding>>::failure(
        ValidationError{ErrorCategory::cross_field, "$/action_inputs",
                        "S17-TEST-RUN-FACTORS",
                        "synthetic pilot run lacks exact factor bindings"});
  }
  const std::string producer = prefix + "producer-raw-v1.bin";
  const std::string consumer = prefix + "consumer-raw-v1.bin";
  const std::string joined = prefix + "joined-raw-v1.bin";
  const auto summary_role = action == FixedAction::q16b ? "Q16B_SERVICE_RATE_CAPTURE"
                            : action == FixedAction::q16c
                                ? "Q16C_ZERO_LOSS_FEASIBILITY_CAPTURE"
                                : "STAGE17_BLINDED_PILOT_RUN";
  const auto summary_schema =
      action == FixedAction::q16b   ? "cpu-prefetch-stage17-q16b-output/3"
      : action == FixedAction::q16c ? "cpu-prefetch-stage17-q16c-output/3"
                                    : "cpu-prefetch-stage17-blinded-pilot-run/3";
  std::vector<ArtifactPayload> payloads;
  auto raw = synthetic_raw_rows(*run_id, *offered);
  const auto producer_sha = cpu_prefetch::workload::sha256(raw[0]).hex();
  const auto consumer_sha = cpu_prefetch::workload::sha256(raw[1]).hex();
  const auto joined_sha = cpu_prefetch::workload::sha256(raw[2]).hex();
  payloads.push_back({"PRODUCER_RAW_OBSERVATIONS", "RAW-OBS-U64LE-LP-RUNID-v1",
                      "application/octet-stream", producer, raw[0]});
  payloads.push_back({"CONSUMER_RAW_OBSERVATIONS", "RAW-OBS-U64LE-LP-RUNID-v1",
                      "application/octet-stream", consumer, raw[1]});
  payloads.push_back(
      {"PHASE_INTEGRITY", "cpu-prefetch-phase-integrity-report/2", "application/json",
       prefix + "phase-integrity-v2.json",
       encoded({
           {"schema_version", string_value("cpu-prefetch-phase-integrity-report/2")},
           {"protocol_version", string_value("2.0.0-pre.3")},
           {"record_kind", string_value("PHASE_INTEGRITY_REPORT")},
           {"artifact_id", string_value(prefix + "phase-integrity")},
           {"run_id", string_value(*run_id)},
           {"final_consumer_rolling_checksum",
            JsonValue(
                JsonObject{{"algorithm_record_id",
                            string_value("cpu-prefetch/consumer-mix64-adr0027/v1")},
                           {"algorithm_version", string_value("1")},
                           {"value_hex", string_value("0000000000000011")}})},
           {"event_records_pre_checksum",
            JsonValue(JsonObject{{"algorithm_record_id", string_value("SHA-256")},
                                 {"algorithm_version", string_value("1")},
                                 {"value_hex", string_value(producer_sha)}})},
           {"event_records_post_checksum",
            JsonValue(JsonObject{{"algorithm_record_id", string_value("SHA-256")},
                                 {"algorithm_version", string_value("1")},
                                 {"value_hex", string_value(producer_sha)}})},
           {"ordered_index_checksum",
            JsonValue(JsonObject{{"algorithm_record_id", string_value("SHA-256")},
                                 {"algorithm_version", string_value("1")},
                                 {"value_hex", string_value(producer_sha)}})},
           {"address_delta_checksum",
            JsonValue(JsonObject{{"algorithm_record_id", string_value("SHA-256")},
                                 {"algorithm_version", string_value("1")},
                                 {"value_hex", string_value(producer_sha)}})},
           {"content_checksum_match", JsonValue(true)},
       })});
  for (const auto& [role, name] :
       std::array<std::pair<std::string_view, std::string>, 2U>{
           std::pair{"PRODUCER_RAW_ENVELOPE"sv, prefix + "producer-envelope-v1.json"},
           std::pair{"CONSUMER_RAW_ENVELOPE"sv,
                     prefix + "consumer-envelope-v1.json"}}) {
    payloads.push_back(
        {std::string(role), "2.0.0-pre.3", "application/json", name,
         encoded({{"schema_version", string_value("synthetic-envelope/1")},
                  {"run_id", string_value(*run_id)},
                  {"synthetic_test_only", JsonValue(true)}})});
  }
  payloads.push_back({"JOINED_RAW_OBSERVATIONS", "RAW-OBS-U64LE-LP-RUNID-v1",
                      "application/octet-stream", joined, raw[2]});
  payloads.push_back({"JOINED_RAW_ENVELOPE", "2.0.0-pre.3", "application/json",
                      prefix + "joined-envelope-v1.json",
                      encoded({{"schema_version", string_value("synthetic-envelope/1")},
                               {"run_id", string_value(*run_id)},
                               {"synthetic_test_only", JsonValue(true)}})});
  const auto* placement = string_member(run, "placement");
  const auto consumer_cpu = placement != nullptr && *placement == "FAR" ? 26U : 1U;
  payloads.push_back(
      {"JOIN_AUDIT", "cpu-prefetch-stage17-join-audit/3", "application/json",
       prefix + "join-audit-v3.json",
       encoded({{"schema_version", string_value("cpu-prefetch-stage17-join-audit/3")},
                {"run_id", string_value(*run_id)},
                {"producer_raw_sha256", string_value(producer_sha)},
                {"consumer_raw_sha256", string_value(consumer_sha)},
                {"joined_raw_sha256", string_value(joined_sha)},
                {"producer_rows", uint_value(*offered)},
                {"accepted_rows", uint_value(*offered)},
                {"full_rows", uint_value(0U)},
                {"consumer_rows", uint_value(*offered)},
                {"join_status", string_value("PASSED")},
                {"record_index_is_event_identity", JsonValue(false)}})});
  JsonArray page_nodes{uint_value(0U)};
  payloads.push_back(
      {"PAGE_RESIDENCY_PROVENANCE", "cpu-prefetch-stage17-page-residency/3",
       "application/json", prefix + "page-residency-v3.json",
       encoded(
           {{"schema_version", string_value("cpu-prefetch-stage17-page-residency/3")},
            {"run_id", string_value(*run_id)},
            {"expected_numa_node", uint_value(0U)},
            {"before_page_nodes", JsonValue(page_nodes)},
            {"during_page_nodes", JsonValue(page_nodes)},
            {"after_page_nodes", JsonValue(page_nodes)},
            {"producer_cpu", uint_value(0U)},
            {"consumer_cpu", uint_value(consumer_cpu)},
            {"producer_migrated", JsonValue(false)},
            {"consumer_migrated", JsonValue(false)},
            {"verified", JsonValue(true)}})});
  payloads.push_back(
      {summary_role, summary_schema, "application/json", prefix + "run-summary-v3.json",
       encoded(
           {{"schema_version", string_value(summary_schema)},
            {"run_id", string_value(*run_id)},
            {"plan_sha256", string_value(*plan)},
            {"schedule_sha256", string_value(*schedule)},
            {"seed_id", string_value(*seed)},
            {"runner_admission_sha256", string_value(*admission)},
            {"package", string_value(*package)},
            {"cell_ordinal", action != FixedAction::q16a
                                 ? JsonValue(*member(run, "cell_ordinal"))
                                 : JsonValue(nullptr)},
            {"repetition_ordinal", action != FixedAction::q16a
                                       ? JsonValue(*member(run, "repetition_ordinal"))
                                       : JsonValue(nullptr)},
            {"hardware_state", action != FixedAction::q16a
                                   ? JsonValue(*member(run, "hardware_state"))
                                   : JsonValue(nullptr)},
            {"placement", action != FixedAction::q16a
                              ? JsonValue(*member(run, "placement"))
                              : JsonValue(nullptr)},
            {"working_set_class", action != FixedAction::q16a
                                      ? JsonValue(*member(run, "working_set_class"))
                                      : JsonValue(nullptr)},
            {"load_level",
             (action == FixedAction::blinded_pilot || action == FixedAction::q16c)
                 ? JsonValue(*member(run, "load_level"))
                 : JsonValue(nullptr)},
            {"planned_attempt_capacity", uint_value(*offered)},
            {"offered_count", uint_value(*offered)},
            {"accepted_count", uint_value(*offered)},
            {"full_count", uint_value(0U)},
            {"consumed_count", uint_value(*offered)},
            {"final_consumer_checksum", uint_value(17U)},
            {"zero_loss", JsonValue(true)},
            {"join_status", string_value("PASSED")},
            {"warmup_reset_verified", JsonValue(true)},
            {"treatment_blind", JsonValue(true)},
            {"confirmatory_outcomes_accessed", JsonValue(false)},
            {"complete", JsonValue(true)}})});
  std::vector<cpu_prefetch::runner::stage17::ArtifactBinding> result;
  for (auto& payload : payloads) {
    auto item = sink.publish(std::move(payload));
    if (!item) {
      return Result<std::vector<cpu_prefetch::runner::stage17::ArtifactBinding>>::
          failure(item.errors());
    }
    result.push_back(std::move(item.value()));
  }
  return Result<std::vector<cpu_prefetch::runner::stage17::ArtifactBinding>>::success(
      result);
}

class TestLinkedOperations final : public FixedActionOperations {
public:
  [[nodiscard]] auto
  execute(FixedAction action,
          const cpu_prefetch::protocol::json::Value::Object& action_inputs,
          ArtifactSink& sink) -> Result<ActionOutcome> override {
    const auto hash = fake_hash('a');
    if (action == FixedAction::q15_r) {
      const auto* authorization = string_member(action_inputs, "authorization_sha256");
      const auto* qualification = string_member(action_inputs, "qualification_id");
      const auto* attempt = string_member(action_inputs, "attempt_id");
      const auto* session = string_member(action_inputs, "session_id");
      if (authorization == nullptr || qualification == nullptr || attempt == nullptr ||
          session == nullptr) {
        return Result<ActionOutcome>::failure(ValidationError{
            ErrorCategory::cross_field, "$/action_inputs", "S17-TEST-Q15R-LINEAGE",
            "test-linked Q15-R requires exact signed lineage"});
      }
      auto artifact = publish(
          sink, "Q15_R_READ_ONLY_PRESTATE", "cpu-prefetch-stage17-q15-r-output/3",
          "application/json", "q15-r-output-v3.json",
          encoded(
              {{"schema_version", string_value("cpu-prefetch-stage17-q15-r-output/3")},
               {"qualification_id", string_value(*qualification)},
               {"authorization_sha256", string_value(*authorization)},
               {"attempt_id", string_value(*attempt)},
               {"session_id", string_value(*session)},
               {"cpu_family", uint_value(6U)},
               {"cpu_model", uint_value(85U)},
               {"mapping_id", string_value("INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1")},
               {"prestate", JsonValue(msr_values("0000000000000000"))},
               {"buffer_size_bytes", uint_value(4096U)},
               {"buffer_content_sha256", string_value(hash)},
               {"regular_probe",
                JsonValue(JsonObject{{"counter_value", uint_value(1U)},
                                     {"minor_faults", uint_value(0U)},
                                     {"major_faults", uint_value(0U)},
                                     {"cpu_verified", JsonValue(true)},
                                     {"residency_verified", JsonValue(true)},
                                     {"integrity_verified", JsonValue(true)}})},
               {"pointer_probe",
                JsonValue(JsonObject{{"counter_value", uint_value(1U)},
                                     {"minor_faults", uint_value(0U)},
                                     {"major_faults", uint_value(0U)},
                                     {"cpu_verified", JsonValue(true)},
                                     {"residency_verified", JsonValue(true)},
                                     {"integrity_verified", JsonValue(true)}})},
               {"pointer_atomic_lock_free", JsonValue(true)},
               {"queue_layout_passed", JsonValue(true)},
               {"termination_atomic_lock_free", JsonValue(true)},
               {"read_only", JsonValue(true)},
               {"complete", JsonValue(true)}}));
      if (!artifact) {
        return Result<ActionOutcome>::failure(artifact.errors());
      }
      return Result<ActionOutcome>::success(
          {{std::move(artifact.value())}, false, false, "Q15_R_SESSION_WAITING"});
    }
    if (action == FixedAction::q15_w) {
      const auto* authorization = string_member(action_inputs, "authorization_sha256");
      const auto* attempt = string_member(action_inputs, "q15_r_attempt_sha256");
      const auto* result = string_member(action_inputs, "q15_r_result_sha256");
      const auto* session = string_member(action_inputs, "session_id");
      if (authorization == nullptr || attempt == nullptr || result == nullptr ||
          session == nullptr) {
        return Result<ActionOutcome>::failure(ValidationError{
            ErrorCategory::cross_field, "$/action_inputs", "S17-TEST-Q15W-LINEAGE",
            "test-linked Q15-W requires exact Q15-R lineage"});
      }
      auto artifact = publish(
          sink, "Q15_W_TRANSACTION", "cpu-prefetch-stage17-q15-w-output/3",
          "application/json", "q15-w-output-v3.json",
          encoded(
              {{"schema_version", string_value("cpu-prefetch-stage17-q15-w-output/3")},
               {"authorization_sha256", string_value(*authorization)},
               {"q15_r_attempt_sha256", string_value(*attempt)},
               {"q15_r_result_sha256", string_value(*result)},
               {"session_id", string_value(*session)},
               {"live_prestate_matches", JsonValue(true)},
               {"apply_readback", JsonValue(msr_values("000000000000000f"))},
               {"regular_probe",
                JsonValue(JsonObject{{"counter_value", uint_value(1U)},
                                     {"accepted", JsonValue(true)},
                                     {"integrity_verified", JsonValue(true)}})},
               {"pointer_probe",
                JsonValue(JsonObject{{"counter_value", uint_value(1U)},
                                     {"accepted", JsonValue(true)},
                                     {"integrity_verified", JsonValue(true)}})},
               {"restore_readback", JsonValue(msr_values("0000000000000000"))},
               {"restoration_verified", JsonValue(true)},
               {"quarantine_operation",
                JsonValue(
                    JsonObject{{"performed", JsonValue(false)},
                               {"reason", string_value("RESTORATION_VERIFIED")}})},
               {"complete", JsonValue(true)}}));
      if (!artifact) {
        return Result<ActionOutcome>::failure(artifact.errors());
      }
      return Result<ActionOutcome>::success(
          {{std::move(artifact.value())}, true, false, "Q15_W_RESTORED_COMPLETE"});
    }
    if (action == FixedAction::q16a) {
      const auto* captures_value = member(action_inputs, "captures");
      const auto* captures =
          captures_value == nullptr ? nullptr : captures_value->as_array();
      if (captures == nullptr || captures->empty()) {
        return Result<ActionOutcome>::failure(ValidationError{
            ErrorCategory::cross_field, "$/action_inputs/captures",
            "S17-TEST-Q16A-CAPTURES", "synthetic Q16a capture family is absent"});
      }
      std::vector<cpu_prefetch::runner::stage17::ArtifactBinding> all;
      for (const auto& capture_value : *captures) {
        const auto* capture = capture_value.as_object();
        const auto context = capture == nullptr
                                 ? std::optional<std::uint64_t>{}
                                 : uint_member(*capture, "context_ordinal");
        const auto repetition = capture == nullptr
                                    ? std::optional<std::uint64_t>{}
                                    : uint_member(*capture, "repetition_ordinal");
        const auto* plan = capture == nullptr
                               ? nullptr
                               : string_member(*capture, "calibration_plan_sha256");
        const auto* seed =
            capture == nullptr ? nullptr : string_member(*capture, "seed_id");
        const auto* state =
            capture == nullptr ? nullptr : string_member(*capture, "hardware_state");
        const auto* placement =
            capture == nullptr ? nullptr : string_member(*capture, "placement");
        const auto* working_set =
            capture == nullptr ? nullptr : string_member(*capture, "working_set_class");
        if (!context || !repetition || plan == nullptr || seed == nullptr ||
            state == nullptr || placement == nullptr || working_set == nullptr) {
          return Result<ActionOutcome>::failure(ValidationError{
              ErrorCategory::cross_field, "$/action_inputs/captures",
              "S17-TEST-Q16A-CAPTURE", "synthetic Q16a capture is incomplete"});
        }
        std::ostringstream prefix;
        prefix << "q16a-c" << std::setw(2) << std::setfill('0') << *context << "-r"
               << std::setw(3) << *repetition << '-';
        auto output = publish(
            sink, "Q16A_RING_DISTANCE_CAPTURE", "cpu-prefetch-stage17-q16a-output/3",
            "application/json", prefix.str() + "output-v3.json",
            encoded({
                {"schema_version", string_value("cpu-prefetch-stage17-q16a-output/3")},
                {"calibration_plan_sha256", string_value(*plan)},
                {"seed_id", string_value(*seed)},
                {"context_ordinal", uint_value(*context)},
                {"repetition_ordinal", uint_value(*repetition)},
                {"hardware_state", string_value(*state)},
                {"placement", string_value(*placement)},
                {"working_set_class", string_value(*working_set)},
                {"sample_count", uint_value(1U)},
                {"producer_demand_count", uint_value(1U)},
                {"consumer_demand_count", uint_value(1U)},
                {"producer_issue_count", uint_value(0U)},
                {"consumer_issue_count", uint_value(0U)},
                {"producer_full_count", uint_value(0U)},
                {"consumer_empty_count", uint_value(0U)},
                {"ring_off", JsonValue(true)},
                {"confirmatory_outcomes_accessed", JsonValue(false)},
                {"complete", JsonValue(true)},
            }));
        auto trace = publish(
            sink, "Q16A_RING_DEMAND_TRACE", "cpu-prefetch-stage17-q16a-trace/3",
            "application/json", prefix.str() + "trace-v3.json",
            encoded({
                {"schema_version", string_value("cpu-prefetch-stage17-q16a-trace/3")},
                {"calibration_plan_sha256", string_value(*plan)},
                {"seed_id", string_value(*seed)},
                {"context_ordinal", uint_value(*context)},
                {"repetition_ordinal", uint_value(*repetition)},
                {"hardware_state", string_value(*state)},
                {"placement", string_value(*placement)},
                {"working_set_class", string_value(*working_set)},
                {"producer_demand_ticks", JsonValue(JsonArray{uint_value(1U)})},
                {"consumer_demand_ticks", JsonValue(JsonArray{uint_value(1U)})},
                {"producer_issue_ticks", JsonValue(JsonArray{})},
                {"consumer_issue_ticks", JsonValue(JsonArray{})},
                {"producer_full_count", uint_value(0U)},
                {"consumer_empty_count", uint_value(0U)},
                {"ring_off", JsonValue(true)},
                {"confirmatory_outcomes_accessed", JsonValue(false)},
            }));
        if (!output || !trace) {
          return Result<ActionOutcome>::failure(!output ? output.errors()
                                                        : trace.errors());
        }
        all.push_back(std::move(output.value()));
        all.push_back(std::move(trace.value()));
      }
      auto hardware =
          publish_calibration_hardware(action, action_inputs, captures->size(), sink);
      if (!hardware) {
        return Result<ActionOutcome>::failure(hardware.errors());
      }
      all.push_back(std::move(hardware.value()));
      return Result<ActionOutcome>::success(
          {std::move(all), true, false, "Q16A_CAPTURE_COMPLETE"});
    }
    if (action == FixedAction::q16b || action == FixedAction::q16c) {
      const auto* runs_value = member(action_inputs, "runs");
      const auto* runs = runs_value == nullptr ? nullptr : runs_value->as_array();
      if (runs == nullptr || runs->empty()) {
        return Result<ActionOutcome>::failure(
            ValidationError{ErrorCategory::cross_field, "$/action_inputs/runs",
                            "S17-TEST-Q16-RUNS", "synthetic Q16 run family is absent"});
      }
      std::vector<cpu_prefetch::runner::stage17::ArtifactBinding> all;
      for (std::size_t index = 0; index < runs->size(); ++index) {
        const auto* run = (*runs)[index].as_object();
        if (run == nullptr) {
          return Result<ActionOutcome>::failure(ValidationError{
              ErrorCategory::cross_field, "$/action_inputs/runs", "S17-TEST-Q16-RUN",
              "synthetic Q16 run is not an object"});
        }
        std::ostringstream prefix;
        prefix << (action == FixedAction::q16b ? "q16b-r" : "q16c-r") << std::setw(5)
               << std::setfill('0') << index << '-';
        auto artifacts = run_payloads(action, *run, prefix.str(), sink);
        if (!artifacts) {
          return Result<ActionOutcome>::failure(artifacts.errors());
        }
        all.insert(all.end(), std::make_move_iterator(artifacts.value().begin()),
                   std::make_move_iterator(artifacts.value().end()));
      }
      auto hardware =
          publish_calibration_hardware(action, action_inputs, runs->size(), sink);
      if (!hardware) {
        return Result<ActionOutcome>::failure(hardware.errors());
      }
      all.push_back(std::move(hardware.value()));
      return Result<ActionOutcome>::success(
          {std::move(all), true, false, "CALIBRATION_CAPTURE_COMPLETE"});
    }
    const auto* plan_value = member(action_inputs, "pilot_plan");
    const auto* plan = plan_value == nullptr ? nullptr : plan_value->as_object();
    const auto* cells_value = plan == nullptr ? nullptr : member(*plan, "cells");
    const auto* cells = cells_value == nullptr ? nullptr : cells_value->as_array();
    const auto* plan_sha = string_member(action_inputs, "plan_sha256");
    if (cells == nullptr || cells->size() != 180U || plan_sha == nullptr) {
      return Result<ActionOutcome>::failure(ValidationError{
          ErrorCategory::cross_field, "$/action_inputs/pilot_plan",
          "S17-TEST-PILOT-MATRIX", "test-linked pilot requires all 180 cells"});
    }
    std::vector<cpu_prefetch::runner::stage17::ArtifactBinding> artifacts;
    for (const auto& cell_value : *cells) {
      const auto* cell = cell_value.as_object();
      const auto ordinal = cell == nullptr ? std::optional<std::uint64_t>{}
                                           : uint_member(*cell, "cell_ordinal");
      const auto* runs_value = cell == nullptr ? nullptr : member(*cell, "runs");
      const auto* runs = runs_value == nullptr ? nullptr : runs_value->as_array();
      if (!ordinal || runs == nullptr || runs->empty()) {
        return Result<ActionOutcome>::failure(ValidationError{
            ErrorCategory::cross_field, "$/action_inputs/pilot_plan/cells",
            "S17-TEST-PILOT-CELL", "synthetic pilot cell is incomplete"});
      }
      for (std::size_t repetition = 0U; repetition < runs->size(); ++repetition) {
        const auto* run = (*runs)[repetition].as_object();
        if (run == nullptr) {
          throw std::runtime_error("synthetic pilot run is not an object");
        }
        std::ostringstream prefix;
        prefix << "pilot-c" << std::setw(3) << std::setfill('0') << *ordinal << "-r"
               << std::setw(3) << repetition << '-';
        auto materialized_run = *run;
        if (member(materialized_run, "plan_sha256") != nullptr) {
          return Result<ActionOutcome>::failure(ValidationError{
              ErrorCategory::cross_field,
              "$/action_inputs/pilot_plan/cells/runs/plan_sha256",
              "S17-TEST-PILOT-SELF-HASH",
              "pilot plan rows must not embed the enclosing plan hash"});
        }
        materialized_run.emplace("plan_sha256", string_value(*plan_sha));
        auto group = run_payloads(action, materialized_run, prefix.str(), sink);
        if (!group) {
          return Result<ActionOutcome>::failure(group.errors());
        }
        artifacts.insert(artifacts.end(),
                         std::make_move_iterator(group.value().begin()),
                         std::make_move_iterator(group.value().end()));
      }
    }
    JsonArray index;
    for (const auto& item : artifacts) {
      index.emplace_back(
          JsonObject{{"role", string_value(item.role)},
                     {"schema_identity", string_value(item.schema_identity)},
                     {"file_name", string_value(item.file_name)},
                     {"size_bytes", uint_value(item.size_bytes)},
                     {"sha256", string_value(item.sha256)}});
    }
    const auto* hardware_value = member(*plan, "hardware_control");
    const auto* hardware =
        hardware_value == nullptr ? nullptr : hardware_value->as_object();
    const auto* q15w_hash =
        hardware == nullptr ? nullptr : string_member(*hardware, "q15_w_result_sha256");
    const auto* whole_value = member(*plan, "whole_plot_order");
    const auto* whole = whole_value == nullptr ? nullptr : whole_value->as_array();
    if (q15w_hash == nullptr || whole == nullptr || whole->size() != 2U) {
      return Result<ActionOutcome>::failure(ValidationError{
          ErrorCategory::cross_field, "$/action_inputs/pilot_plan/hardware_control",
          "S17-TEST-PILOT-HARDWARE",
          "synthetic pilot requires exact hardware-control lineage"});
    }
    auto hardware_artifact =
        publish(sink, "STAGE17_PILOT_HARDWARE_STATE",
                "cpu-prefetch-stage17-pilot-hardware-state/1", "application/json",
                "stage17-pilot-hardware-state-v1.json",
                encoded({
                    {"schema_version",
                     string_value("cpu-prefetch-stage17-pilot-hardware-state/1")},
                    {"mapping_id", string_value("INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1")},
                    {"q15_w_result_sha256", string_value(*q15w_hash)},
                    {"whole_plot_order", JsonValue(*whole)},
                    {"apply_readback", JsonValue(msr_values("000000000000000f"))},
                    {"restore_readback", JsonValue(msr_values("0000000000000000"))},
                    {"cell_count", uint_value(180U)},
                    {"restoration_verified", JsonValue(true)},
                    {"phase18_authority", JsonValue(false)},
                }));
    if (!hardware_artifact) {
      return Result<ActionOutcome>::failure(hardware_artifact.errors());
    }
    index.emplace_back(JsonObject{
        {"role", string_value(hardware_artifact.value().role)},
        {"schema_identity", string_value(hardware_artifact.value().schema_identity)},
        {"file_name", string_value(hardware_artifact.value().file_name)},
        {"size_bytes", uint_value(hardware_artifact.value().size_bytes)},
        {"sha256", string_value(hardware_artifact.value().sha256)},
    });
    artifacts.push_back(std::move(hardware_artifact.value()));
    const auto repetitions = uint_member(*plan, "repetitions_per_cell").value_or(0U);
    const auto* plan_id = string_member(*plan, "plan_id");
    auto manifest = publish(
        sink, "SEALED_PILOT_ARTIFACT_MANIFEST",
        "cpu-prefetch-stage17-sealed-pilot-artifact-manifest/3", "application/json",
        "stage17-sealed-pilot-manifest-v3.json",
        encoded(
            {{"schema_version",
              string_value("cpu-prefetch-stage17-sealed-pilot-artifact-manifest/3")},
             {"plan_id", string_value(plan_id == nullptr ? "SYNTHETIC" : *plan_id)},
             {"plan_sha256", string_value(*plan_sha)},
             {"cell_count", uint_value(180U)},
             {"repetitions_per_cell", uint_value(repetitions)},
             {"run_count", uint_value(180U * repetitions)},
             {"artifact_count", uint_value(artifacts.size())},
             {"artifacts", JsonValue(std::move(index))},
             {"treatment_blind", JsonValue(true)},
             {"confirmatory_outcomes_accessed", JsonValue(false)},
             {"sealed", JsonValue(true)},
             {"phase18_authority", JsonValue(false)}}));
    if (!manifest) {
      return Result<ActionOutcome>::failure(manifest.errors());
    }
    artifacts.push_back(std::move(manifest.value()));
    return Result<ActionOutcome>::success(
        {std::move(artifacts), true, false, "PILOT_COMPLETE_SEALED"});
  }

  [[nodiscard]] auto execute_pilot_session(
      const JsonObject& action_inputs, ArtifactSink& sink,
      const cpu_prefetch::runner::stage17::PilotSessionAuthority& authority)
      -> Result<ActionOutcome> override {
    const auto* plan_value = member(action_inputs, "pilot_plan");
    const auto* plan = plan_value == nullptr ? nullptr : plan_value->as_object();
    const auto* plan_sha = string_member(action_inputs, "plan_sha256");
    const auto* cells_value = plan == nullptr ? nullptr : member(*plan, "cells");
    const auto* cells = cells_value == nullptr ? nullptr : cells_value->as_array();
    const auto repetitions = plan == nullptr
                                 ? std::optional<std::uint64_t>{}
                                 : uint_member(*plan, "repetitions_per_cell");
    const auto* plan_id = plan == nullptr ? nullptr : string_member(*plan, "plan_id");
    const auto* hardware_value =
        plan == nullptr ? nullptr : member(*plan, "hardware_control");
    const auto* hardware =
        hardware_value == nullptr ? nullptr : hardware_value->as_object();
    const auto* q15w =
        hardware == nullptr ? nullptr : string_member(*hardware, "q15_w_result_sha256");
    const auto* orders_value =
        plan == nullptr ? nullptr : member(*plan, "whole_plot_orders");
    const auto* orders = orders_value == nullptr ? nullptr : orders_value->as_array();
    if (plan == nullptr || plan_sha == nullptr || plan_id == nullptr ||
        cells == nullptr || cells->size() != 180U || !repetitions ||
        *repetitions == 0U || q15w == nullptr || orders == nullptr ||
        orders->size() != *repetitions) {
      return Result<ActionOutcome>::failure(ValidationError{
          ErrorCategory::cross_field, "$/action_inputs/pilot_plan",
          "S17-TEST-PILOT-SESSION", "synthetic pilot session plan is incomplete"});
    }
    struct Entry final {
      JsonObject run;
      std::uint64_t repetition;
      std::uint64_t execution;
    };
    std::vector<Entry> run_order;
    for (const auto& cell_value : *cells) {
      const auto* cell = cell_value.as_object();
      const auto* runs_value = cell == nullptr ? nullptr : member(*cell, "runs");
      const auto* runs = runs_value == nullptr ? nullptr : runs_value->as_array();
      if (runs == nullptr || runs->size() != *repetitions) {
        return Result<ActionOutcome>::failure(ValidationError{
            ErrorCategory::cross_field, "$/action_inputs/pilot_plan/cells",
            "S17-TEST-PILOT-RUNS", "synthetic repeated pilot cell is incomplete"});
      }
      for (const auto& run_value : *runs) {
        const auto* run = run_value.as_object();
        const auto repetition = run == nullptr
                                    ? std::optional<std::uint64_t>{}
                                    : uint_member(*run, "repetition_ordinal");
        const auto execution = run == nullptr ? std::optional<std::uint64_t>{}
                                              : uint_member(*run, "execution_ordinal");
        if (run == nullptr || !repetition || !execution) {
          return Result<ActionOutcome>::failure(ValidationError{
              ErrorCategory::cross_field, "$/action_inputs/pilot_plan/cells/runs",
              "S17-TEST-PILOT-ORDER", "synthetic run order is absent"});
        }
        run_order.push_back({*run, *repetition, *execution});
      }
    }
    std::ranges::sort(run_order, [](const auto& left, const auto& right) {
      return std::tie(left.repetition, left.execution) <
             std::tie(right.repetition, right.execution);
    });
    if (run_order.size() != 180U * *repetitions) {
      return Result<ActionOutcome>::failure(
          ValidationError{ErrorCategory::cross_field, "$/action_inputs/pilot_plan",
                          "S17-TEST-PILOT-COUNT", "synthetic pilot run count drifted"});
    }
    auto artifact_json = [](const auto& item, bool include_schema) {
      JsonObject value{{"role", string_value(item.role)},
                       {"file_name", string_value(item.file_name)},
                       {"size_bytes", uint_value(item.size_bytes)},
                       {"sha256", string_value(item.sha256)}};
      if (include_schema) {
        value.emplace("schema_identity", string_value(item.schema_identity));
      }
      return JsonValue(std::move(value));
    };
    std::vector<cpu_prefetch::runner::stage17::ArtifactBinding> artifacts;
    JsonArray attempt_hashes;
    JsonArray completion_hashes;
    for (const auto& entry : run_order) {
      const auto* run_id = string_member(entry.run, "run_id");
      if (run_id == nullptr) {
        throw std::runtime_error("synthetic pilot run identity is absent");
      }
      std::ostringstream prefix_builder;
      prefix_builder << "pilot-b" << std::setw(3) << std::setfill('0')
                     << entry.repetition << "-e" << std::setw(3) << entry.execution
                     << '-';
      const auto prefix = prefix_builder.str();
      const auto attempt_id = authority.session_id + ":" + *run_id + ":attempt-1";
      auto attempt = publish(
          sink, "STAGE17_PILOT_RUN_ATTEMPT", "cpu-prefetch-stage17-pilot-run-attempt/1",
          "application/json", prefix + "attempt-v1.json",
          encoded({
              {"schema_version",
               string_value("cpu-prefetch-stage17-pilot-run-attempt/1")},
              {"session_id", string_value(authority.session_id)},
              {"attempt_id", string_value(attempt_id)},
              {"run_id", string_value(*run_id)},
              {"plan_sha256", string_value(*plan_sha)},
              {"authorization_sha256", string_value(authority.authorization_sha256)},
              {"cell_ordinal", JsonValue(*member(entry.run, "cell_ordinal"))},
              {"repetition_ordinal", uint_value(entry.repetition)},
              {"execution_ordinal", uint_value(entry.execution)},
              {"started_at_utc", string_value("2030-01-01T00:00:00.000000Z")},
              {"deadline_seconds", uint_value(180U)},
              {"one_attempt", JsonValue(true)},
              {"retry_allowed", JsonValue(false)},
              {"marker_durable", JsonValue(true)},
              {"synthetic_test_only", JsonValue(true)},
              {"phase18_authority", JsonValue(false)},
          }));
      if (!attempt) {
        return Result<ActionOutcome>::failure(attempt.errors());
      }
      attempt_hashes.push_back(string_value(attempt.value().sha256));
      artifacts.push_back(attempt.value());
      auto materialized = entry.run;
      materialized.emplace("plan_sha256", string_value(*plan_sha));
      auto run_artifacts =
          run_payloads(FixedAction::blinded_pilot, materialized, prefix, sink);
      if (!run_artifacts) {
        return Result<ActionOutcome>::failure(run_artifacts.errors());
      }
      JsonArray run_index;
      for (const auto& item : run_artifacts.value()) {
        run_index.push_back(artifact_json(item, false));
        artifacts.push_back(item);
      }
      auto completion =
          publish(sink, "STAGE17_PILOT_RUN_COMPLETION",
                  "cpu-prefetch-stage17-pilot-run-completion/1", "application/json",
                  prefix + "completion-v1.json",
                  encoded({
                      {"schema_version",
                       string_value("cpu-prefetch-stage17-pilot-run-completion/1")},
                      {"session_id", string_value(authority.session_id)},
                      {"attempt_id", string_value(attempt_id)},
                      {"run_id", string_value(*run_id)},
                      {"attempt_sha256", string_value(attempt.value().sha256)},
                      {"artifact_bindings", JsonValue(std::move(run_index))},
                      {"completed_at_utc", string_value("2030-01-01T00:00:00.000001Z")},
                      {"duration_ns", uint_value(1U)},
                      {"terminal_state", string_value("RUN_COMPLETED")},
                      {"restoration_boundary_pending", JsonValue(true)},
                      {"synthetic_test_only", JsonValue(true)},
                      {"phase18_authority", JsonValue(false)},
                  }));
      if (!completion) {
        return Result<ActionOutcome>::failure(completion.errors());
      }
      completion_hashes.push_back(string_value(completion.value().sha256));
      artifacts.push_back(completion.value());
    }
    auto hardware_artifact =
        publish(sink, "STAGE17_PILOT_HARDWARE_STATE",
                "cpu-prefetch-stage17-pilot-hardware-state/2", "application/json",
                "stage17-pilot-hardware-state-v2.json",
                encoded({
                    {"schema_version",
                     string_value("cpu-prefetch-stage17-pilot-hardware-state/2")},
                    {"mapping_id", string_value("INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1")},
                    {"q15_w_result_sha256", string_value(*q15w)},
                    {"whole_plot_orders", JsonValue(*orders)},
                    {"apply_readback", JsonValue(msr_values("000000000000000f"))},
                    {"restore_readback", JsonValue(msr_values("0000000000000000"))},
                    {"cell_count", uint_value(180U)},
                    {"run_count", uint_value(run_order.size())},
                    {"restoration_verified", JsonValue(true)},
                    {"phase18_authority", JsonValue(false)},
                }));
    if (!hardware_artifact) {
      return Result<ActionOutcome>::failure(hardware_artifact.errors());
    }
    artifacts.push_back(hardware_artifact.value());
    JsonArray manifest_index;
    for (const auto& item : artifacts) {
      manifest_index.push_back(artifact_json(item, true));
    }
    auto manifest = publish(
        sink, "SEALED_PILOT_ARTIFACT_MANIFEST",
        "cpu-prefetch-stage17-sealed-pilot-artifact-manifest/4", "application/json",
        "stage17-sealed-pilot-manifest-v4.json",
        encoded({
            {"schema_version",
             string_value("cpu-prefetch-stage17-sealed-pilot-artifact-manifest/4")},
            {"session_id", string_value(authority.session_id)},
            {"authorization_sha256", string_value(authority.authorization_sha256)},
            {"plan_id", string_value(*plan_id)},
            {"plan_sha256", string_value(*plan_sha)},
            {"cell_count", uint_value(180U)},
            {"repetitions_per_cell", uint_value(*repetitions)},
            {"run_count", uint_value(run_order.size())},
            {"artifact_count", uint_value(artifacts.size())},
            {"artifacts", JsonValue(std::move(manifest_index))},
            {"run_attempt_sha256s", JsonValue(attempt_hashes)},
            {"run_completion_sha256s", JsonValue(completion_hashes)},
            {"treatment_blind", JsonValue(true)},
            {"confirmatory_outcomes_accessed", JsonValue(false)},
            {"sealed", JsonValue(true)},
            {"synthetic_test_only", JsonValue(true)},
            {"phase18_authority", JsonValue(false)},
        }));
    if (!manifest) {
      return Result<ActionOutcome>::failure(manifest.errors());
    }
    artifacts.push_back(manifest.value());
    auto file_ref = [](const auto& item) {
      return JsonValue(JsonObject{{"file_name", string_value(item.file_name)},
                                  {"size_bytes", uint_value(item.size_bytes)},
                                  {"sha256", string_value(item.sha256)}});
    };
    auto session = publish(
        sink, "STAGE17_PILOT_SESSION_COMPLETION",
        "cpu-prefetch-stage17-pilot-session-completion/1", "application/json",
        "stage17-pilot-session-completion-v1.json",
        encoded({
            {"schema_version",
             string_value("cpu-prefetch-stage17-pilot-session-completion/1")},
            {"session_id", string_value(authority.session_id)},
            {"authorization_id", string_value(authority.authorization_id)},
            {"authorization_sha256", string_value(authority.authorization_sha256)},
            {"request_sha256", string_value(authority.request_sha256)},
            {"plan_id", string_value(*plan_id)},
            {"plan_sha256", string_value(*plan_sha)},
            {"stand_id", string_value(authority.stand_id)},
            {"run_count", uint_value(run_order.size())},
            {"run_attempt_sha256s", JsonValue(attempt_hashes)},
            {"run_completion_sha256s", JsonValue(completion_hashes)},
            {"sealed_manifest", file_ref(manifest.value())},
            {"hardware_state", file_ref(hardware_artifact.value())},
            {"started_at_utc", string_value("2030-01-01T00:00:00.000000Z")},
            {"completed_at_utc", string_value("2030-01-01T00:00:01.000000Z")},
            {"terminal_state", string_value("PILOT_SESSION_COMPLETE_SEALED")},
            {"all_runs_complete", JsonValue(true)},
            {"restoration_verified", JsonValue(true)},
            {"quarantined", JsonValue(false)},
            {"synthetic_test_only", JsonValue(true)},
            {"phase18_authority", JsonValue(false)},
        }));
    if (!session) {
      return Result<ActionOutcome>::failure(session.errors());
    }
    artifacts.push_back(session.value());
    return Result<ActionOutcome>::success(
        {std::move(artifacts), true, false, "PILOT_SESSION_COMPLETE_SEALED"});
  }

  [[nodiscard]] auto synthetic_test_only() const noexcept -> bool override {
    return true;
  }
};

} // namespace

int main(int argc, char** argv) {
  try {
    if (argc == 2 && std::string_view(argv[1]) == "--stage17-runtime-identity-v4") {
      const auto repository = cpu_prefetch::foundation::repository_info();
      const auto binary_sha256 =
          cpu_prefetch::runner::stage17::self_executable_sha256();
      if (!binary_sha256) {
        throw std::runtime_error("test worker cannot hash its executable");
      }
      std::cout << "{\"binary_sha256\":\"" << binary_sha256.value()
                << "\",\"protocol_version\":\"" << repository.protocol_version
                << "\",\"role\":\""
                << cpu_prefetch::runner::stage17::kFixedActionWorkerRole
                << "\",\"runtime_profile\":\""
                << cpu_prefetch::runner::stage17::kFixedActionRuntimeProfile
                << "\",\"source_dirty\":"
                << (repository.source_dirty ? "true" : "false")
                << ",\"source_revision\":\"" << repository.source_revision
                << "\",\"supported_actions\":[\"Q15-R\",\"Q15-W\",\"Q16a\","
                   "\"Q16b\",\"Q16c\",\"STAGE17-BLINDED-PILOT\"],"
                   "\"synthetic_test_only\":true}\n";
      return 0;
    }
    TestLinkedOperations operations;
    if (argc >= 2 && std::string_view(argv[1]) == "--execute-stage17-q15-session-v1") {
      return cpu_prefetch::runner::stage17::run_test_q15_phase_session_worker(
          argc, argv, operations);
    }
    if (argc >= 2 &&
        std::string_view(argv[1]) == "--execute-stage17-pilot-session-v1") {
      return cpu_prefetch::runner::stage17::run_pilot_session_worker(argc, argv,
                                                                     operations);
    }
    return cpu_prefetch::runner::stage17::run_fixed_action_worker(argc, argv,
                                                                  operations);
  } catch (const std::exception& exception) {
    std::cerr << "stage17-test-worker: FAIL: " << exception.what() << '\n';
  } catch (...) {
    std::cerr << "stage17-test-worker: FAIL: non-standard exception\n";
  }
  return 1;
}
