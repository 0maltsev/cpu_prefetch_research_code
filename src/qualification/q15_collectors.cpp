#include "cpu_prefetch/qualification/q15_collectors.hpp"

#include "cpu_prefetch/lifecycle/runtime.hpp"
#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/queue/linked_spsc.hpp"
#include "cpu_prefetch/queue/ring_spsc.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <set>
#include <utility>

namespace cpu_prefetch::qualification {
namespace {

using JsonArray = protocol::json::Value::Array;
using JsonObject = protocol::json::Value::Object;

[[nodiscard]] auto validation_error(protocol::ErrorCategory category, std::string path,
                                    std::string rule, std::string message)
    -> protocol::ValidationError {
  return {category, std::move(path), std::move(rule), std::move(message)};
}

[[nodiscard]] auto uint_value(std::uint64_t value) -> protocol::json::Value {
  return protocol::json::Value(protocol::json::Number{
      protocol::json::Number::Kind::unsigned_integer, std::to_string(value), value});
}

[[nodiscard]] auto source_json(std::span<const runner::QualificationSource> sources)
    -> protocol::json::Value {
  JsonArray result;
  result.reserve(sources.size());
  for (const auto& source : sources) {
    result.emplace_back(
        JsonObject{{"artifact_id", protocol::json::Value(source.artifact_id)},
                   {"sha256", protocol::json::Value(source.sha256)}});
  }
  return protocol::json::Value(std::move(result));
}

[[nodiscard]] auto valid_identity(const runner::QualificationIdentity& identity)
    -> std::vector<protocol::ValidationError> {
  std::vector<protocol::ValidationError> errors;
  if (identity.artifact_id.empty() || identity.stand_id.empty() ||
      identity.binding_id.empty() || identity.source_revision.empty() ||
      identity.captured_at_utc.empty()) {
    errors.push_back(validation_error(protocol::ErrorCategory::missing_field,
                                      "$/identity", "Q15-COLLECTOR-IDENTITY",
                                      "collector identity fields must be complete"));
  }
  if (!protocol::Sha256::parse(identity.binary_sha256, "$/binary_sha256")) {
    errors.push_back(validation_error(protocol::ErrorCategory::invalid_hash,
                                      "$/binary_sha256", "Q15-COLLECTOR-BINARY",
                                      "binary SHA-256 must be lowercase hexadecimal"));
  }
  if (identity.workers != runner::kNearWorkerPair &&
      identity.workers != runner::kFarWorkerPair) {
    errors.push_back(validation_error(protocol::ErrorCategory::reference_mismatch,
                                      "$/workers", "Q15-COLLECTOR-PAIR",
                                      "collector requires one accepted Q13 pair"));
  }
  std::set<std::string> identifiers;
  if (identity.sources.empty()) {
    errors.push_back(validation_error(protocol::ErrorCategory::missing_evidence,
                                      "$/sources", "Q15-COLLECTOR-SOURCES",
                                      "at least one immutable source is required"));
  }
  for (const auto& source : identity.sources) {
    if (source.artifact_id.empty() || !identifiers.insert(source.artifact_id).second ||
        !protocol::Sha256::parse(source.sha256, "$/sources/sha256")) {
      errors.push_back(validation_error(protocol::ErrorCategory::reference_mismatch,
                                        "$/sources", "Q15-COLLECTOR-SOURCE",
                                        "source IDs must be unique with valid hashes"));
    }
  }
  return errors;
}

[[nodiscard]] auto contract(Q15CollectorKind kind) -> const Q15CollectorContract& {
  return *std::find_if(kQ15CollectorContracts.begin(), kQ15CollectorContracts.end(),
                       [kind](const auto& item) { return item.kind == kind; });
}

[[nodiscard]] auto make_artifact(const runner::QualificationIdentity& identity,
                                 Q15CollectorKind kind, bool complete, bool eligible,
                                 protocol::json::Value details)
    -> protocol::Result<Q15CollectorArtifact> {
  auto errors = valid_identity(identity);
  if (!errors.empty()) {
    return protocol::Result<Q15CollectorArtifact>::failure(std::move(errors));
  }
  const auto& selected = contract(kind);
  const protocol::json::Value document(JsonObject{
      {"artifact_id", protocol::json::Value(identity.artifact_id)},
      {"binary_sha256", protocol::json::Value(identity.binary_sha256)},
      {"binding_id", protocol::json::Value(identity.binding_id)},
      {"captured_at_utc", protocol::json::Value(identity.captured_at_utc)},
      {"collector_id", protocol::json::Value(std::string(selected.collector_id))},
      {"complete", protocol::json::Value(complete)},
      {"consumer_cpu", uint_value(identity.workers.consumer_cpu)},
      {"details", std::move(details)},
      {"eligible", protocol::json::Value(complete && eligible)},
      {"evidence_kind", protocol::json::Value(std::string(selected.evidence_kind))},
      {"producer_cpu", uint_value(identity.workers.producer_cpu)},
      {"protocol_version",
       protocol::json::Value(std::string(protocol::kProtocolVersion))},
      {"schema_version",
       protocol::json::Value(std::string(kQ15CollectorEvidenceSchemaVersion))},
      {"source_revision", protocol::json::Value(identity.source_revision)},
      {"sources", source_json(identity.sources)},
      {"stand_id", protocol::json::Value(identity.stand_id)},
  });
  const auto canonical = protocol::json::canonicalize(document);
  if (!canonical) {
    return protocol::Result<Q15CollectorArtifact>::failure(canonical.errors());
  }
  return protocol::Result<Q15CollectorArtifact>::success(
      {kind, std::string(selected.collector_id), complete, complete && eligible,
       canonical.value()});
}

[[nodiscard]] auto string_member(const protocol::json::Value::Object& object,
                                 std::string_view name) -> const std::string* {
  const auto found = object.find(name);
  return found == object.end() ? nullptr : found->second.as_string();
}

[[nodiscard]] auto object_member(const protocol::json::Value::Object& object,
                                 std::string_view name)
    -> const protocol::json::Value::Object* {
  const auto found = object.find(name);
  return found == object.end() ? nullptr : found->second.as_object();
}

struct CodegenReportAssessment final {
  bool complete;
  bool passes;
  std::string binary_sha256;
  std::string document_sha256;
};

[[nodiscard]] auto text_sha256(std::string_view text) -> std::string {
  return workload::sha256(
             std::span<const std::byte>(reinterpret_cast<const std::byte*>(text.data()),
                                        text.size()))
      .hex();
}

[[nodiscard]] auto assess_codegen_report(std::string_view document)
    -> CodegenReportAssessment {
  const auto parsed = protocol::json::parse(document);
  if (!parsed || parsed.value().as_object() == nullptr) {
    return {false, false, {}, text_sha256(document)};
  }
  const auto& root = *parsed.value().as_object();
  const auto* schema = string_member(root, "schema_version");
  const auto* mapping = string_member(root, "software_prefetch_mapping_id");
  const auto* status = string_member(root, "status");
  const auto* binary = string_member(root, "binary_sha256");
  const auto* tools = object_member(root, "tools");
  const auto* source = object_member(root, "source_contract");
  const auto missing = root.find("missing_tools");
  const bool complete = schema != nullptr && mapping != nullptr && status != nullptr &&
                        binary != nullptr && tools != nullptr && source != nullptr &&
                        missing != root.end() && missing->second.as_array() != nullptr;
  if (!complete) {
    return {false, false, {}, text_sha256(document)};
  }
  const auto* gnu = object_member(*tools, "GNU_OBJDUMP");
  const auto* llvm = object_member(*tools, "LLVM_OBJDUMP");
  const auto* source_status = string_member(*source, "status");
  const auto* source_mapping = string_member(*source, "mapping_id");
  const bool passes =
      *schema == "cpu-prefetch-runner-combined-codegen/2" &&
      *mapping == runner::kSoftwarePrefetchMappingId && *status == "PASS" &&
      protocol::Sha256::parse(*binary, "$/binary_sha256") &&
      missing->second.as_array()->empty() && gnu != nullptr && llvm != nullptr &&
      string_member(*gnu, "status") != nullptr &&
      *string_member(*gnu, "status") == "PASS" &&
      string_member(*llvm, "status") != nullptr &&
      *string_member(*llvm, "status") == "PASS" && source_status != nullptr &&
      *source_status == "PASS" && source_mapping != nullptr &&
      *source_mapping == runner::kSoftwarePrefetchMappingId;
  return {true, passes, *binary, text_sha256(document)};
}

[[nodiscard]] auto residency_details(const Q15RegionResidencySeries& region)
    -> protocol::json::Value {
  const auto page_count = region.before.page_nodes.size();
  std::uint64_t unavailable = 0U;
  std::uint64_t wrong_node = 0U;
  std::uint64_t migrated = 0U;
  const bool equal_counts = page_count != 0U &&
                            region.during.page_nodes.size() == page_count &&
                            region.after.page_nodes.size() == page_count;
  const auto inspect = [&](std::span<const std::int32_t> nodes) {
    for (const auto node : nodes) {
      unavailable += node < 0 ? 1U : 0U;
      wrong_node +=
          node >= 0 && static_cast<std::uint32_t>(node) != region.expected_node ? 1U
                                                                                : 0U;
    }
  };
  inspect(region.before.page_nodes);
  inspect(region.during.page_nodes);
  inspect(region.after.page_nodes);
  if (equal_counts) {
    for (std::size_t index = 0U; index < page_count; ++index) {
      migrated +=
          region.before.page_nodes[index] != region.during.page_nodes[index] ||
                  region.during.page_nodes[index] != region.after.page_nodes[index]
              ? 1U
              : 0U;
    }
  }
  return protocol::json::Value(JsonObject{
      {"after_page_count", uint_value(region.after.page_nodes.size())},
      {"before_page_count", uint_value(region.before.page_nodes.size())},
      {"during_page_count", uint_value(region.during.page_nodes.size())},
      {"expected_node", uint_value(region.expected_node)},
      {"migrated_page_count", uint_value(migrated)},
      {"region", protocol::json::Value(region.region)},
      {"unavailable_page_count", uint_value(unavailable)},
      {"wrong_node_page_count", uint_value(wrong_node)},
  });
}

[[nodiscard]] auto region_passes(const Q15RegionResidencySeries& region) -> bool {
  const auto expected_pages = region.before.page_nodes.size();
  if (!region.before.passes(region.expected_node, expected_pages) ||
      !region.during.passes(region.expected_node, expected_pages) ||
      !region.after.passes(region.expected_node, expected_pages)) {
    return false;
  }
  for (std::size_t index = 0U; index < expected_pages; ++index) {
    if (region.before.page_nodes[index] != region.during.page_nodes[index] ||
        region.during.page_nodes[index] != region.after.page_nodes[index]) {
      return false;
    }
  }
  return true;
}

} // namespace

auto q15_collector_registry() noexcept -> std::span<const Q15CollectorContract> {
  return kQ15CollectorContracts;
}

auto collect_q15_clock(const runner::QualificationIdentity& identity,
                       const Q15ClockRawObservation& observation)
    -> protocol::Result<Q15CollectorArtifact> {
  const auto static_evidence =
      timing::evaluate_static_clock_evidence(observation.static_observation);
  const auto producer =
      timing::evaluate_per_core_qualification(observation.per_core[0]);
  const auto consumer =
      timing::evaluate_per_core_qualification(observation.per_core[1]);
  const auto pair = timing::evaluate_cross_core_pair(observation.cross_core);
  const bool complete =
      producer.has_value() && consumer.has_value() && pair.has_value();
  const bool before_block_repeat =
      observation.capture_completed_monotonic_nanoseconds != 0U &&
      observation.block_repeat_not_before_monotonic_nanoseconds != 0U &&
      observation.capture_completed_monotonic_nanoseconds <
          observation.block_repeat_not_before_monotonic_nanoseconds;
  const bool eligible = complete && static_evidence.passes && producer->passes &&
                        consumer->passes && pair->passes && before_block_repeat;
  return make_artifact(
      identity, Q15CollectorKind::clock, complete, eligible,
      protocol::json::Value(JsonObject{
          {"before_block_repeat", protocol::json::Value(before_block_repeat)},
          {"block_repeat_not_before_monotonic_nanoseconds",
           uint_value(observation.block_repeat_not_before_monotonic_nanoseconds)},
          {"capture_completed_monotonic_nanoseconds",
           uint_value(observation.capture_completed_monotonic_nanoseconds)},
          {"consumer_delta_count",
           uint_value(consumer ? consumer->sequence.delta_count : 0U)},
          {"consumer_passed",
           protocol::json::Value(consumer.has_value() && consumer->passes)},
          {"cross_core_passed",
           protocol::json::Value(pair.has_value() && pair->passes)},
          {"diagnostic_correction_applied", protocol::json::Value(false)},
          {"producer_delta_count",
           uint_value(producer ? producer->sequence.delta_count : 0U)},
          {"producer_passed",
           protocol::json::Value(producer.has_value() && producer->passes)},
          {"static_passed", protocol::json::Value(static_evidence.passes)},
      }));
}

auto collect_q15_atomic_layout(const runner::QualificationIdentity& identity,
                               std::size_t cache_line_bytes)
    -> protocol::Result<Q15CollectorArtifact> {
  try {
    queue::RingSpscQueue ring(queue::QueueCapacity{8U},
                              queue::CacheLineBytes{cache_line_bytes});
    const std::array<std::size_t, 9U> order{5U, 1U, 8U, 3U, 0U, 7U, 4U, 2U, 6U};
    queue::LinkedSpscQueue linked(
        queue::QueueCapacity{8U}, queue::CacheLineBytes{cache_line_bytes},
        queue::ArenaAlignmentBytes{platform::kQ15ProbeBasePageBytes}, order);
    lifecycle::TerminationControl termination(queue::CacheLineBytes{cache_line_bytes});
    const auto ring_atomic = ring.atomic_lock_free_evidence();
    const auto linked_atomic = linked.atomic_lock_free_evidence();
    const auto ring_layout = ring.layout_evidence();
    const auto linked_layout = linked.layout_evidence();
    const auto termination_evidence = termination.evidence();
    const bool eligible =
        cache_line_bytes == platform::kQ15ProbeCacheLineBytes &&
        ring_atomic.abi_pointer_width_bytes == sizeof(void*) &&
        linked_atomic.abi_pointer_width_bytes == sizeof(void*) &&
        ring_atomic.atomic_pointer_width_bytes == sizeof(void*) &&
        linked_atomic.atomic_pointer_width_bytes == sizeof(void*) &&
        ring_atomic.runtime_lock_free && linked_atomic.runtime_lock_free &&
        ring_layout.bases_aligned && linked_layout.bases_aligned &&
        ring_layout.ownership_lines_separated &&
        linked_layout.ownership_lines_separated &&
        termination_evidence.value_width_bytes == sizeof(std::uint32_t) &&
        termination_evidence.runtime_lock_free &&
        termination_evidence.dedicated_cache_line;
    return make_artifact(
        identity, Q15CollectorKind::atomic_layout, true, eligible,
        protocol::json::Value(JsonObject{
            {"cache_line_bytes", uint_value(cache_line_bytes)},
            {"linked_bases_aligned",
             protocol::json::Value(linked_layout.bases_aligned)},
            {"linked_ownership_lines_separated",
             protocol::json::Value(linked_layout.ownership_lines_separated)},
            {"linked_pointer_runtime_lock_free",
             protocol::json::Value(linked_atomic.runtime_lock_free)},
            {"pointer_abi_width_bytes", uint_value(sizeof(void*))},
            {"ring_bases_aligned", protocol::json::Value(ring_layout.bases_aligned)},
            {"ring_ownership_lines_separated",
             protocol::json::Value(ring_layout.ownership_lines_separated)},
            {"ring_pointer_runtime_lock_free",
             protocol::json::Value(ring_atomic.runtime_lock_free)},
            {"termination_atomic_alignment_bytes",
             uint_value(termination_evidence.atomic_alignment_bytes)},
            {"termination_atomic_width_bytes",
             uint_value(termination_evidence.atomic_width_bytes)},
            {"termination_dedicated_line",
             protocol::json::Value(termination_evidence.dedicated_cache_line)},
            {"termination_runtime_lock_free",
             protocol::json::Value(termination_evidence.runtime_lock_free)},
        }));
  } catch (const std::exception& exception) {
    return protocol::Result<Q15CollectorArtifact>::failure(
        validation_error(protocol::ErrorCategory::cross_field, "$/atomic_layout",
                         "Q15-COLLECTOR-ATOMIC-CONSTRUCT", exception.what()));
  }
}

auto collect_q15_actual_cpu_migration(const runner::QualificationIdentity& identity,
                                      const Q15CpuSampleSeries& producer,
                                      const Q15CpuSampleSeries& consumer)
    -> protocol::Result<Q15CollectorArtifact> {
  const auto migration_count = [](std::span<const std::uint32_t> values) {
    std::uint64_t count = 0U;
    for (std::size_t index = 1U; index < values.size(); ++index) {
      count += values[index] != values[index - 1U] ? 1U : 0U;
    }
    return count;
  };
  const auto producer_migrations = migration_count(producer.operation_entry_exit_cpus);
  const auto consumer_migrations = migration_count(consumer.operation_entry_exit_cpus);
  const bool complete = producer.operation_entry_exit_cpus.size() >= 2U &&
                        consumer.operation_entry_exit_cpus.size() >= 2U;
  const auto matches = [](const Q15CpuSampleSeries& series) {
    return std::all_of(
        series.operation_entry_exit_cpus.begin(),
        series.operation_entry_exit_cpus.end(),
        [&series](std::uint32_t cpu) { return cpu == series.expected_cpu; });
  };
  const bool eligible = complete && producer.singleton_affinity_readback &&
                        consumer.singleton_affinity_readback && matches(producer) &&
                        matches(consumer) && producer_migrations == 0U &&
                        consumer_migrations == 0U;
  return make_artifact(
      identity, Q15CollectorKind::actual_cpu_migration, complete, eligible,
      protocol::json::Value(JsonObject{
          {"consumer_expected_cpu", uint_value(consumer.expected_cpu)},
          {"consumer_migration_count", uint_value(consumer_migrations)},
          {"consumer_sample_count",
           uint_value(consumer.operation_entry_exit_cpus.size())},
          {"consumer_singleton_affinity",
           protocol::json::Value(consumer.singleton_affinity_readback)},
          {"producer_expected_cpu", uint_value(producer.expected_cpu)},
          {"producer_migration_count", uint_value(producer_migrations)},
          {"producer_sample_count",
           uint_value(producer.operation_entry_exit_cpus.size())},
          {"producer_singleton_affinity",
           protocol::json::Value(producer.singleton_affinity_readback)},
      }));
}

auto collect_q15_address_residency(const runner::QualificationIdentity& identity,
                                   std::span<const Q15RegionResidencySeries> regions)
    -> protocol::Result<Q15CollectorArtifact> {
  const std::set<std::string> expected{"CONSUMER_PRIVATE", "PRODUCER_PRIVATE",
                                       "SHARED_EVENT_AND_QUEUE"};
  std::set<std::string> observed;
  JsonArray details;
  bool eligible = regions.size() == expected.size();
  for (const auto& region : regions) {
    observed.insert(region.region);
    eligible = region_passes(region) && eligible;
    details.emplace_back(residency_details(region));
  }
  const bool complete = regions.size() == expected.size() && observed == expected;
  return make_artifact(
      identity, Q15CollectorKind::address_residency, complete, complete && eligible,
      protocol::json::Value(JsonObject{
          {"mechanism_id", protocol::json::Value(std::string(
                               "MOVE_PAGES-ALL-PAGES-BEFORE-DURING-AFTER-v1"))},
          {"regions", protocol::json::Value(std::move(details))},
      }));
}

auto collect_q15_software_prefetch(
    const runner::QualificationIdentity& identity,
    platform::Q15PlatformOperations& platform_operations,
    runner::CurrentCpuSoftwarePrefetchCapabilityBackend& capability_backend,
    const Q15SoftwarePrefetchReports& reports)
    -> protocol::Result<Q15CollectorArtifact> {
  JsonArray capabilities;
  bool observations_complete = true;
  bool capabilities_pass = true;
  for (const auto cpu : platform::kHardwarePrefetchControlCpus) {
    const auto bound = platform_operations.bind_current_thread(cpu);
    const auto affinity = platform_operations.singleton_affinity_matches(cpu);
    const auto actual = platform_operations.current_cpu();
    if (!bound.succeeded || !affinity || !affinity.value() || !actual ||
        actual.value() != cpu) {
      observations_complete = false;
      capabilities_pass = false;
      continue;
    }
    const auto observation = capability_backend.observe();
    capabilities_pass = observation.passes() && capabilities_pass;
    capabilities.emplace_back(JsonObject{
        {"cpu", uint_value(cpu)},
        {"extended_leaf_ecx", uint_value(observation.extended_leaf_ecx)},
        {"maximum_extended_leaf", uint_value(observation.maximum_extended_leaf)},
        {"prfchw_supported", protocol::json::Value(observation.prfchw_supported)},
    });
  }
  const auto gcc = assess_codegen_report(reports.gcc_report_json);
  const auto clang = assess_codegen_report(reports.clang_report_json);
  const bool distinct_reports = gcc.document_sha256 != clang.document_sha256 &&
                                gcc.binary_sha256 != clang.binary_sha256;
  const bool complete = observations_complete && gcc.complete && clang.complete;
  const bool eligible =
      complete && capabilities_pass && gcc.passes && clang.passes && distinct_reports;
  return make_artifact(
      identity, Q15CollectorKind::software_prefetch, complete, eligible,
      protocol::json::Value(JsonObject{
          {"capabilities", protocol::json::Value(std::move(capabilities))},
          {"clang_binary_sha256", protocol::json::Value(clang.binary_sha256)},
          {"clang_report_sha256", protocol::json::Value(clang.document_sha256)},
          {"distinct_compiler_reports", protocol::json::Value(distinct_reports)},
          {"gcc_binary_sha256", protocol::json::Value(gcc.binary_sha256)},
          {"gcc_report_sha256", protocol::json::Value(gcc.document_sha256)},
          {"mapping_id",
           protocol::json::Value(std::string(runner::kSoftwarePrefetchMappingId))},
      }));
}

auto collect_q15_msr_prestate(const runner::QualificationIdentity& identity,
                              platform::HardwarePrefetchMsrBackend& reader)
    -> protocol::Result<Q15CollectorArtifact> {
  JsonArray values;
  bool complete = !reader.backend_id().empty();
  for (const auto cpu : platform::kHardwarePrefetchControlCpus) {
    const auto value = reader.read(cpu);
    if (!value) {
      complete = false;
      continue;
    }
    values.emplace_back(JsonObject{{"cpu", uint_value(cpu)},
                                   {"complete_value", uint_value(value.value())}});
  }
  return make_artifact(
      identity, Q15CollectorKind::msr_prestate, complete, complete,
      protocol::json::Value(JsonObject{
          {"backend_id", protocol::json::Value(std::string(reader.backend_id()))},
          {"mapping_id",
           protocol::json::Value(std::string(platform::kHardwarePrefetchMappingId))},
          {"requested_state_copied_to_verified", protocol::json::Value(false)},
          {"values", protocol::json::Value(std::move(values))},
      }));
}

auto collect_q15_msr_readback(const runner::QualificationIdentity& identity,
                              platform::HardwarePrefetchMsrBackend& independent_reader,
                              std::uint32_t cpu, std::uint64_t expected_complete_value,
                              Q15MsrReadbackPhase phase,
                              std::string_view writer_identity,
                              std::string_view auditor_identity)
    -> protocol::Result<Q15CollectorArtifact> {
  const bool selected = std::find(platform::kHardwarePrefetchControlCpus.begin(),
                                  platform::kHardwarePrefetchControlCpus.end(),
                                  cpu) != platform::kHardwarePrefetchControlCpus.end();
  const auto observed =
      selected ? independent_reader.read(cpu)
               : platform::Result<std::uint64_t>::failure(
                     {platform::ErrorCategory::invalid_request, "$q15_readback",
                      "Q15-READBACK-CPU", "CPU is outside fixed Q15 domain"});
  const bool identities_complete = !writer_identity.empty() &&
                                   !auditor_identity.empty() &&
                                   writer_identity != auditor_identity;
  const bool complete = selected && !independent_reader.backend_id().empty() &&
                        observed.has_value() && identities_complete;
  const bool eligible = complete && observed.value() == expected_complete_value;
  return make_artifact(
      identity, Q15CollectorKind::msr_readback, complete, eligible,
      protocol::json::Value(JsonObject{
          {"auditor_identity", protocol::json::Value(std::string(auditor_identity))},
          {"backend_id",
           protocol::json::Value(std::string(independent_reader.backend_id()))},
          {"cpu", uint_value(cpu)},
          {"expected_complete_value", uint_value(expected_complete_value)},
          {"observed_complete_value", uint_value(observed ? observed.value() : 0U)},
          {"phase",
           protocol::json::Value(std::string(
               phase == Q15MsrReadbackPhase::h1_apply ? "H1_APPLY" : "H0_RESTORE"))},
          {"writer_identity", protocol::json::Value(std::string(writer_identity))},
      }));
}

} // namespace cpu_prefetch::qualification
