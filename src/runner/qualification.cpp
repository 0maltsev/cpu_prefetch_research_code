#include "cpu_prefetch/runner/qualification.hpp"

#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/timing/qualification.hpp"

#include <algorithm>
#include <set>
#include <utility>

namespace cpu_prefetch::runner {
namespace {

using JsonObject = protocol::json::Value::Object;
using JsonArray = protocol::json::Value::Array;

[[nodiscard]] auto error(protocol::ErrorCategory category, std::string path,
                         std::string rule, std::string message)
    -> protocol::ValidationError {
  return {category, std::move(path), std::move(rule), std::move(message)};
}

[[nodiscard]] auto uint_value(std::uint64_t value) -> protocol::json::Value {
  return protocol::json::Value(protocol::json::Number{
      protocol::json::Number::Kind::unsigned_integer, std::to_string(value), value});
}

[[nodiscard]] auto valid_identity(const QualificationIdentity& identity)
    -> std::vector<protocol::ValidationError> {
  std::vector<protocol::ValidationError> errors;
  const auto require = [&](std::string_view value, std::string path) {
    if (value.empty()) {
      errors.push_back(error(protocol::ErrorCategory::missing_field, std::move(path),
                             "QUAL-IDENTITY",
                             "qualification identity field must be nonempty"));
    }
  };
  require(identity.artifact_id, "$/artifact_id");
  require(identity.stand_id, "$/stand_id");
  require(identity.binding_id, "$/binding_id");
  require(identity.source_revision, "$/source_revision");
  require(identity.captured_at_utc, "$/captured_at_utc");
  if (!protocol::Sha256::parse(identity.binary_sha256, "$/binary_sha256")) {
    errors.push_back(error(protocol::ErrorCategory::invalid_hash, "$/binary_sha256",
                           "QUAL-BINARY-HASH",
                           "binary SHA-256 must be lowercase hexadecimal"));
  }
  if (identity.workers != kNearWorkerPair && identity.workers != kFarWorkerPair) {
    errors.push_back(error(protocol::ErrorCategory::reference_mismatch, "$/workers",
                           "QUAL-PAIR",
                           "qualification must use one accepted Q13 pair"));
  }
  std::set<std::string> source_ids;
  if (identity.sources.empty()) {
    errors.push_back(error(protocol::ErrorCategory::missing_evidence, "$/sources",
                           "QUAL-SOURCES",
                           "at least one immutable source reference is required"));
  }
  for (std::size_t index = 0U; index < identity.sources.size(); ++index) {
    const auto& source = identity.sources[index];
    const auto path = "$/sources/" + std::to_string(index);
    if (source.artifact_id.empty() || !source_ids.insert(source.artifact_id).second) {
      errors.push_back(error(protocol::ErrorCategory::duplicate_value,
                             path + "/artifact_id", "QUAL-SOURCE-ID",
                             "source artifact IDs must be nonempty and unique"));
    }
    if (!protocol::Sha256::parse(source.sha256, path + "/sha256")) {
      errors.push_back(error(protocol::ErrorCategory::invalid_hash, path + "/sha256",
                             "QUAL-SOURCE-HASH",
                             "source SHA-256 must be lowercase hexadecimal"));
    }
  }
  return errors;
}

[[nodiscard]] auto source_json(std::span<const QualificationSource> sources)
    -> protocol::json::Value {
  JsonArray values;
  values.reserve(sources.size());
  for (const auto& source : sources) {
    values.emplace_back(JsonObject{
        {"artifact_id", protocol::json::Value(source.artifact_id)},
        {"sha256", protocol::json::Value(source.sha256)},
    });
  }
  return protocol::json::Value(std::move(values));
}

[[nodiscard]] auto region_json(const RegionResidencyInput& region)
    -> protocol::json::Value {
  return protocol::json::Value(JsonObject{
      {"after_page_count", uint_value(region.after_page_count)},
      {"before_page_count", uint_value(region.before_page_count)},
      {"during_page_count", uint_value(region.during_page_count)},
      {"expected_node", uint_value(region.expected_node)},
      {"migrated_page_count", uint_value(region.migrated_page_count)},
      {"region", protocol::json::Value(region.region)},
      {"unavailable_page_count", uint_value(region.unavailable_page_count)},
      {"wrong_node_page_count", uint_value(region.wrong_node_page_count)},
  });
}

[[nodiscard]] auto region_passes(const RegionResidencyInput& region) noexcept -> bool {
  return !region.region.empty() && region.before_page_count != 0U &&
         region.before_page_count == region.during_page_count &&
         region.before_page_count == region.after_page_count &&
         region.unavailable_page_count == 0U && region.wrong_node_page_count == 0U &&
         region.migrated_page_count == 0U;
}

[[nodiscard]] auto make_artifact(const QualificationIdentity& identity,
                                 QualificationEvidenceKind kind, bool eligible,
                                 protocol::json::Value details)
    -> protocol::Result<QualificationArtifact> {
  auto errors = valid_identity(identity);
  if (!errors.empty()) {
    return protocol::Result<QualificationArtifact>::failure(std::move(errors));
  }
  const auto document = protocol::json::Value(JsonObject{
      {"artifact_id", protocol::json::Value(identity.artifact_id)},
      {"binary_sha256", protocol::json::Value(identity.binary_sha256)},
      {"binding_id", protocol::json::Value(identity.binding_id)},
      {"captured_at_utc", protocol::json::Value(identity.captured_at_utc)},
      {"consumer_cpu", uint_value(identity.workers.consumer_cpu)},
      {"details", std::move(details)},
      {"eligible", protocol::json::Value(eligible)},
      {"kind", protocol::json::Value(std::string(to_string(kind)))},
      {"producer_cpu", uint_value(identity.workers.producer_cpu)},
      {"protocol_version",
       protocol::json::Value(std::string(protocol::kProtocolVersion))},
      {"schema_version",
       protocol::json::Value(std::string(kQualificationEvidenceSchemaVersion))},
      {"source_revision", protocol::json::Value(identity.source_revision)},
      {"sources", source_json(identity.sources)},
      {"stand_id", protocol::json::Value(identity.stand_id)},
  });
  const auto canonical = protocol::json::canonicalize(document);
  if (!canonical) {
    return protocol::Result<QualificationArtifact>::failure(canonical.errors());
  }
  return protocol::Result<QualificationArtifact>::success(
      {kind, eligible, canonical.value()});
}

} // namespace

auto to_string(QualificationEvidenceKind kind) noexcept -> std::string_view {
  switch (kind) {
  case QualificationEvidenceKind::selected_pair_clock:
    return "SELECTED_PAIR_CLOCK";
  case QualificationEvidenceKind::runtime_atomic_layout:
    return "RUNTIME_ATOMIC_LAYOUT";
  case QualificationEvidenceKind::actual_cpu_migration:
    return "ACTUAL_CPU_MIGRATION";
  case QualificationEvidenceKind::address_residency:
    return "ADDRESS_RESIDENCY";
  case QualificationEvidenceKind::software_prefetch_mapping:
    return "SOFTWARE_PREFETCH_MAPPING";
  }
  return "UNKNOWN";
}

auto make_selected_pair_clock_evidence(const QualificationIdentity& identity,
                                       const SelectedPairClockInput& input)
    -> protocol::Result<QualificationArtifact> {
  const bool counts_pass =
      std::all_of(input.prime_read_counts.begin(), input.prime_read_counts.end(),
                  [](std::uint64_t value) {
                    return value == timing::kQualificationPrimeReadCount;
                  }) &&
      std::all_of(input.delta_counts.begin(), input.delta_counts.end(),
                  [](std::uint64_t value) {
                    return value == timing::kQualificationDeltaCount;
                  }) &&
      input.traced_call_count == timing::kQualificationDeltaCount &&
      input.traced_syscall_count == 0U &&
      input.producer_to_consumer_window_count == timing::kCrossCoreWindowCount &&
      input.consumer_to_producer_window_count == timing::kCrossCoreWindowCount &&
      input.exchanges_per_window == timing::kCrossCoreExchangeCountPerWindow;
  const bool eligible = counts_pass && input.per_core_evaluator_passed &&
                        input.cross_core_evaluator_passed && input.before_block_repeat;
  return make_artifact(
      identity, QualificationEvidenceKind::selected_pair_clock, eligible,
      protocol::json::Value(JsonObject{
          {"before_block_repeat", protocol::json::Value(input.before_block_repeat)},
          {"consumer_delta_count", uint_value(input.delta_counts[1])},
          {"consumer_prime_read_count", uint_value(input.prime_read_counts[1])},
          {"consumer_to_producer_window_count",
           uint_value(input.consumer_to_producer_window_count)},
          {"cross_core_evaluator_passed",
           protocol::json::Value(input.cross_core_evaluator_passed)},
          {"exchanges_per_window", uint_value(input.exchanges_per_window)},
          {"per_core_evaluator_passed",
           protocol::json::Value(input.per_core_evaluator_passed)},
          {"producer_delta_count", uint_value(input.delta_counts[0])},
          {"producer_prime_read_count", uint_value(input.prime_read_counts[0])},
          {"producer_to_consumer_window_count",
           uint_value(input.producer_to_consumer_window_count)},
          {"traced_call_count", uint_value(input.traced_call_count)},
          {"traced_syscall_count", uint_value(input.traced_syscall_count)},
      }));
}

auto make_runtime_atomic_layout_evidence(const QualificationIdentity& identity,
                                         const RuntimeAtomicLayoutInput& input)
    -> protocol::Result<QualificationArtifact> {
  const bool eligible =
      input.pointer_atomic_width_bytes == sizeof(void*) &&
      input.pointer_atomic_alignment_bytes >= alignof(void*) &&
      input.termination_atomic_width_bytes == sizeof(std::uint32_t) &&
      input.termination_atomic_alignment_bytes >= alignof(std::uint32_t) &&
      input.cache_line_bytes != 0U && input.pointer_atomic_runtime_lock_free &&
      input.termination_atomic_runtime_lock_free && input.queue_layout_passed &&
      input.ownership_lines_separated && input.termination_dedicated_line;
  return make_artifact(
      identity, QualificationEvidenceKind::runtime_atomic_layout, eligible,
      protocol::json::Value(JsonObject{
          {"cache_line_bytes", uint_value(input.cache_line_bytes)},
          {"ownership_lines_separated",
           protocol::json::Value(input.ownership_lines_separated)},
          {"pointer_atomic_alignment_bytes",
           uint_value(input.pointer_atomic_alignment_bytes)},
          {"pointer_atomic_runtime_lock_free",
           protocol::json::Value(input.pointer_atomic_runtime_lock_free)},
          {"pointer_atomic_width_bytes", uint_value(input.pointer_atomic_width_bytes)},
          {"queue_layout_passed", protocol::json::Value(input.queue_layout_passed)},
          {"termination_atomic_alignment_bytes",
           uint_value(input.termination_atomic_alignment_bytes)},
          {"termination_atomic_runtime_lock_free",
           protocol::json::Value(input.termination_atomic_runtime_lock_free)},
          {"termination_atomic_width_bytes",
           uint_value(input.termination_atomic_width_bytes)},
          {"termination_dedicated_line",
           protocol::json::Value(input.termination_dedicated_line)},
      }));
}

auto make_actual_cpu_migration_evidence(const QualificationIdentity& identity,
                                        const ActualCpuMigrationInput& input)
    -> protocol::Result<QualificationArtifact> {
  const bool eligible =
      input.producer_sample_count != 0U && input.consumer_sample_count != 0U &&
      input.producer_first_cpu == identity.workers.producer_cpu &&
      input.producer_last_cpu == identity.workers.producer_cpu &&
      input.consumer_first_cpu == identity.workers.consumer_cpu &&
      input.consumer_last_cpu == identity.workers.consumer_cpu &&
      input.producer_migration_count == 0U && input.consumer_migration_count == 0U &&
      input.producer_singleton_affinity && input.consumer_singleton_affinity;
  return make_artifact(
      identity, QualificationEvidenceKind::actual_cpu_migration, eligible,
      protocol::json::Value(JsonObject{
          {"consumer_first_cpu", uint_value(input.consumer_first_cpu)},
          {"consumer_last_cpu", uint_value(input.consumer_last_cpu)},
          {"consumer_migration_count", uint_value(input.consumer_migration_count)},
          {"consumer_sample_count", uint_value(input.consumer_sample_count)},
          {"consumer_singleton_affinity",
           protocol::json::Value(input.consumer_singleton_affinity)},
          {"producer_first_cpu", uint_value(input.producer_first_cpu)},
          {"producer_last_cpu", uint_value(input.producer_last_cpu)},
          {"producer_migration_count", uint_value(input.producer_migration_count)},
          {"producer_sample_count", uint_value(input.producer_sample_count)},
          {"producer_singleton_affinity",
           protocol::json::Value(input.producer_singleton_affinity)},
      }));
}

auto make_address_residency_evidence(const QualificationIdentity& identity,
                                     const AddressResidencyInput& input)
    -> protocol::Result<QualificationArtifact> {
  const bool eligible = !input.mechanism_id.empty() &&
                        region_passes(input.shared_event_and_queue_pages) &&
                        region_passes(input.producer_private_pages) &&
                        region_passes(input.consumer_private_pages);
  return make_artifact(
      identity, QualificationEvidenceKind::address_residency, eligible,
      protocol::json::Value(JsonObject{
          {"consumer_private_pages", region_json(input.consumer_private_pages)},
          {"mechanism_id", protocol::json::Value(input.mechanism_id)},
          {"producer_private_pages", region_json(input.producer_private_pages)},
          {"shared_event_and_queue_pages",
           region_json(input.shared_event_and_queue_pages)},
      }));
}

auto make_software_prefetch_mapping_evidence(const QualificationIdentity& identity,
                                             const SoftwarePrefetchMappingInput& input)
    -> protocol::Result<QualificationArtifact> {
  const bool eligible = input.mapping_id == kSoftwarePrefetchMappingId &&
                        input.producer_capability.passes() &&
                        input.consumer_capability.passes() &&
                        input.gcc_codegen_passed && input.clang_codegen_passed &&
                        input.gnu_objdump_passed && input.llvm_objdump_passed;
  return make_artifact(
      identity, QualificationEvidenceKind::software_prefetch_mapping, eligible,
      protocol::json::Value(JsonObject{
          {"clang_codegen_passed", protocol::json::Value(input.clang_codegen_passed)},
          {"consumer_extended_leaf_ecx",
           uint_value(input.consumer_capability.extended_leaf_ecx)},
          {"consumer_maximum_extended_leaf",
           uint_value(input.consumer_capability.maximum_extended_leaf)},
          {"consumer_prfchw_supported",
           protocol::json::Value(input.consumer_capability.prfchw_supported)},
          {"gcc_codegen_passed", protocol::json::Value(input.gcc_codegen_passed)},
          {"gnu_objdump_passed", protocol::json::Value(input.gnu_objdump_passed)},
          {"linked_consumer_instruction",
           protocol::json::Value(std::string("PREFETCHT0"))},
          {"llvm_objdump_passed", protocol::json::Value(input.llvm_objdump_passed)},
          {"mapping_id", protocol::json::Value(input.mapping_id)},
          {"producer_extended_leaf_ecx",
           uint_value(input.producer_capability.extended_leaf_ecx)},
          {"producer_maximum_extended_leaf",
           uint_value(input.producer_capability.maximum_extended_leaf)},
          {"producer_prfchw_supported",
           protocol::json::Value(input.producer_capability.prfchw_supported)},
          {"ring_consumer_instruction",
           protocol::json::Value(std::string("PREFETCHT0"))},
          {"ring_producer_instruction",
           protocol::json::Value(std::string("PREFETCHW"))},
      }));
}

} // namespace cpu_prefetch::runner
