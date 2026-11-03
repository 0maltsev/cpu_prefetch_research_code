#include "cpu_prefetch/runner/stage17_formal_checkpoint.hpp"

#include "stage17_formal_input_detail.hpp"

#include <algorithm>
#include <set>
#include <stdexcept>

namespace cpu_prefetch::runner::stage17 {
namespace {
using Value = protocol::json::Value;
using Object = Value::Object;
namespace input = formal_input_detail;
auto text(std::string_view value) -> Value { return Value(std::string(value)); }
auto number(std::uint64_t value) -> Value {
  return Value(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                      std::to_string(value), value});
}
void require(bool condition, std::string_view message) {
  if (!condition)
    throw std::invalid_argument(std::string(message));
}
auto hash(std::string_view value) -> bool {
  return value.size() == 64U && std::ranges::all_of(value, [](char c) {
           return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
         });
}
} // namespace

FormalPublicationTrackingSink::FormalPublicationTrackingSink(
    ArtifactSink& sink, std::vector<ArtifactBinding>& bindings)
    : sink_(sink), bindings_(bindings) {}

auto FormalPublicationTrackingSink::publish(ArtifactPayload artifact)
    -> protocol::Result<ArtifactBinding> {
  // Allocate the tracking slot before the durable write. Moving its returned
  // binding cannot allocate; even a later result-copy failure keeps this fact.
  bindings_.reserve(bindings_.size() + 1U);
  auto result = sink_.publish(std::move(artifact));
  if (!result)
    return result;
  bindings_.push_back(std::move(result.value()));
  return protocol::Result<ArtifactBinding>::success(bindings_.back());
}

auto publish_formal_checkpoint(ArtifactSink& sink, FixedAction action,
                               std::string_view plan_sha256, const Object& capture,
                               const Value& native_result_after_cleanup,
                               std::span<const ArtifactBinding> artifacts,
                               bool native_complete)
    -> protocol::Result<ArtifactBinding> {
  try {
    require(action == FixedAction::q16a || action == FixedAction::q16b ||
                action == FixedAction::q16c,
            "checkpoint requires a formal calibration action");
    require(hash(plan_sha256), "checkpoint plan hash is malformed");
    const auto ordinal = input::number(capture, "ordinal");
    const auto& warmup = input::text(input::object(capture, "warmup"), "run_id");
    const auto& measurement =
        input::text(input::object(capture, "measurement"), "run_id");
    const auto& state = input::text(capture, "hardware_state");
    require(!warmup.empty() && !measurement.empty() && warmup != measurement &&
                (state == "H0" || state == "H1"),
            "checkpoint capture identities differ from the native contract");
    const auto* final = native_result_after_cleanup.as_object();
    require(final != nullptr, "checkpoint final native result is absent");
    const auto stop = input::number(*final, "stop");
    require(stop <= 14U, "checkpoint native stop is unknown");
    const auto attempted = final->find("publication_attempted");
    const auto succeeded = final->find("publication_succeeded");
    require(attempted != final->end() && succeeded != final->end() &&
                attempted->second.as_bool() != nullptr &&
                succeeded->second.as_bool() != nullptr,
            "checkpoint publication facts are absent");
    const auto expected_count = action == FixedAction::q16a   ? 9U
                                : action == FixedAction::q16b ? 6U
                                                              : 8U;
    const bool complete = stop == 14U && *attempted->second.as_bool() &&
                          *succeeded->second.as_bool() &&
                          artifacts.size() == expected_count;
    require(native_complete == complete, "checkpoint completion claim differs");
    Value::Array references;
    std::set<std::string> names;
    for (const auto& binding : artifacts) {
      require(!binding.file_name.empty() && binding.file_name != "." &&
                  binding.file_name != ".." &&
                  binding.file_name.find('/') == std::string::npos &&
                  binding.file_name.find('\0') == std::string::npos &&
                  names.insert(binding.file_name).second && hash(binding.sha256),
              "checkpoint artifact binding is unsafe or duplicated");
      references.emplace_back(Object{{"file_name", text(binding.file_name)},
                                     {"size_bytes", number(binding.size_bytes)},
                                     {"sha256", text(binding.sha256)}});
    }
    const auto encoded = protocol::json::canonicalize(Value(Object{
        {"schema_version", text(kFormalCheckpointSchema)},
        {"action_id", text(to_string(action))},
        {"plan_sha256", text(plan_sha256)},
        {"capture_ordinal", number(ordinal)},
        {"capture_identity", Value(Object{{"warmup_run_id", text(warmup)},
                                          {"measurement_run_id", text(measurement)},
                                          {"hardware_state", text(state)}})},
        {"native_result_after_cleanup", native_result_after_cleanup},
        {"artifacts", Value(std::move(references))},
        {"native_complete", Value(native_complete)},
        {"scientific_validity", text("NOT_ASSESSED")},
        {"execution_authority", Value(false)}}));
    if (!encoded)
      return protocol::Result<ArtifactBinding>::failure(encoded.errors());
    const auto& raw = encoded.value();
    const auto* begin = reinterpret_cast<const std::byte*>(raw.data());
    return sink.publish(
        {"FORMAL_CAPTURE_FINAL_CHECKPOINT", std::string(kFormalCheckpointSchema),
         "application/json",
         "formal-capture-" + std::to_string(ordinal) + "-final-checkpoint.json",
         std::vector<std::byte>(begin, begin + raw.size())});
  } catch (const std::exception& exception) {
    return protocol::Result<ArtifactBinding>::failure(
        {protocol::ErrorCategory::cross_field, "$/formal/checkpoint",
         "S17-FORMAL-CHECKPOINT", exception.what()});
  }
}
} // namespace cpu_prefetch::runner::stage17
