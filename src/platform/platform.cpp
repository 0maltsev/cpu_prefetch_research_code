#include "cpu_prefetch/platform/platform.hpp"

#include "cpu_prefetch/workload/deterministic.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <set>
#include <sstream>
#include <utility>

namespace cpu_prefetch::platform {
namespace {

using JsonArray = protocol::json::Value::Array;
using JsonObject = protocol::json::Value::Object;

[[nodiscard]] auto make_error(ErrorCategory category, std::string path,
                              std::string rule_id, std::string message) -> Error {
  return {category, std::move(path), std::move(rule_id), std::move(message)};
}

[[nodiscard]] auto uint_value(std::uint64_t value) -> protocol::json::Value {
  return protocol::json::Value(protocol::json::Number{
      protocol::json::Number::Kind::unsigned_integer, std::to_string(value), value});
}

[[nodiscard]] auto int_value(std::int64_t value) -> protocol::json::Value {
  return protocol::json::Value(protocol::json::Number{
      protocol::json::Number::Kind::signed_integer, std::to_string(value), value});
}

[[nodiscard]] auto string_array(std::span<const std::string> values)
    -> protocol::json::Value {
  JsonArray output;
  output.reserve(values.size());
  for (const auto& value : values) {
    output.emplace_back(value);
  }
  return protocol::json::Value(std::move(output));
}

[[nodiscard]] auto uint_array(std::span<const std::uint32_t> values)
    -> protocol::json::Value {
  JsonArray output;
  output.reserve(values.size());
  for (const auto value : values) {
    output.push_back(uint_value(value));
  }
  return protocol::json::Value(std::move(output));
}

[[nodiscard]] auto find_cpu(const PlatformInventory& inventory, std::uint32_t id)
    -> const LogicalCpu* {
  const auto iterator =
      std::find_if(inventory.logical_cpus.begin(), inventory.logical_cpus.end(),
                   [id](const LogicalCpu& cpu) { return cpu.logical_id == id; });
  return iterator == inventory.logical_cpus.end() ? nullptr : &*iterator;
}

[[nodiscard]] auto contains(std::span<const std::uint32_t> values, std::uint32_t value)
    -> bool {
  return std::find(values.begin(), values.end(), value) != values.end();
}

[[nodiscard]] auto same_last_level_cache(const PlatformInventory& inventory,
                                         const LogicalCpu& left,
                                         const LogicalCpu& right) -> bool {
  return std::any_of(inventory.cache_domains.begin(), inventory.cache_domains.end(),
                     [&left, &right](const CacheDomain& domain) {
                       return domain.last_level &&
                              contains(domain.shared_cpus, left.logical_id) &&
                              contains(domain.shared_cpus, right.logical_id);
                     });
}

[[nodiscard]] auto capability_for(std::span<const Capability> capabilities,
                                  ControlKind kind) -> const Capability* {
  const auto iterator = std::find_if(
      capabilities.begin(), capabilities.end(),
      [kind](const Capability& capability) { return capability.kind == kind; });
  return iterator == capabilities.end() ? nullptr : &*iterator;
}

[[nodiscard]] auto observation_for(std::span<const StateObservation> observations,
                                   std::string_view control_id)
    -> const StateObservation* {
  const auto iterator = std::find_if(observations.begin(), observations.end(),
                                     [control_id](const StateObservation& observation) {
                                       return observation.control_id == control_id;
                                     });
  return iterator == observations.end() ? nullptr : &*iterator;
}

[[nodiscard]] auto has_observation(const PlatformInventory& inventory,
                                   std::string_view name) -> bool {
  return std::any_of(inventory.observations.begin(), inventory.observations.end(),
                     [name](const EvidenceValue& observation) {
                       return observation.name == name && observation.value.has_value();
                     });
}

[[nodiscard]] auto control_json(const ControlRequest& request)
    -> protocol::json::Value {
  return protocol::json::Value(JsonObject{
      {"actuation_mechanism", protocol::json::Value(request.actuation_mechanism)},
      {"authority_id", protocol::json::Value(request.authority_id)},
      {"control_id", protocol::json::Value(request.control_id)},
      {"kind", protocol::json::Value(std::string(to_string(request.kind)))},
      {"mandatory", protocol::json::Value(request.mandatory)},
      {"mutating", protocol::json::Value(request.mutating)},
      {"requested_value", protocol::json::Value(request.requested_value)},
      {"target", protocol::json::Value(request.target)},
      {"verification_mechanism", protocol::json::Value(request.verification_mechanism)},
  });
}

[[nodiscard]] auto step_json(const ApplyStep& step) -> protocol::json::Value {
  return protocol::json::Value(JsonObject{
      {"control_id", protocol::json::Value(step.control_id)},
      {"detail", protocol::json::Value(step.detail)},
      {"evidence_id", protocol::json::Value(step.evidence_id)},
      {"status", protocol::json::Value(std::string(to_string(step.status)))},
  });
}

[[nodiscard]] auto error_json(const Error& error) -> protocol::json::Value {
  return protocol::json::Value(JsonObject{
      {"category", protocol::json::Value(std::string(to_string(error.category)))},
      {"message", protocol::json::Value(error.message)},
      {"path", protocol::json::Value(error.path)},
      {"rule_id", protocol::json::Value(error.rule_id)},
  });
}

[[nodiscard]] auto sha256_text(std::string_view value) -> std::string {
  return workload::sha256(std::as_bytes(std::span(value.data(), value.size()))).hex();
}

void require_text(std::vector<Error>& errors, std::string_view value, std::string path,
                  std::string rule_id) {
  if (value.empty()) {
    errors.push_back(make_error(ErrorCategory::manifest_incomplete, std::move(path),
                                std::move(rule_id), "required value is empty"));
  }
}

[[nodiscard]] auto valid_sha256(std::string_view value) -> bool {
  return value.size() == 64U &&
         std::all_of(value.begin(), value.end(), [](char character) {
           return (character >= '0' && character <= '9') ||
                  (character >= 'a' && character <= 'f');
         });
}

[[nodiscard]] auto prefetch_error(ErrorCategory category, std::string rule,
                                  std::string message) -> Error {
  return make_error(category, "$hardware_prefetch", std::move(rule),
                    std::move(message));
}

[[nodiscard]] auto find_msr_value(std::span<const HardwarePrefetchMsrValue> values,
                                  std::uint32_t cpu)
    -> const HardwarePrefetchMsrValue* {
  const auto position =
      std::find_if(values.begin(), values.end(),
                   [cpu](const auto& value) { return value.cpu == cpu; });
  return position == values.end() ? nullptr : &*position;
}

} // namespace

auto make_hardware_prefetch_plan(CpuFamilyModel identity,
                                 protocol::RequestedHardwareState requested_state,
                                 std::span<const HardwarePrefetchMsrValue> prestate)
    -> Result<HardwarePrefetchPlan> {
  std::vector<Error> errors;
  if (identity.family != kIntelFamily6 || identity.model != kIntelModel55) {
    errors.push_back(prefetch_error(
        ErrorCategory::unsupported_control, "HWP-CPUID-06_55H",
        "hardware-prefetch mapping is restricted to CPUID family 06 model 55H"));
  }
  if (requested_state != protocol::RequestedHardwareState::h0 &&
      requested_state != protocol::RequestedHardwareState::h1) {
    errors.push_back(prefetch_error(ErrorCategory::invalid_request, "HWP-STATE",
                                    "only registered H0 and H1 are accepted"));
  }
  if (prestate.size() != kHardwarePrefetchControlCpus.size()) {
    errors.push_back(
        prefetch_error(ErrorCategory::missing_evidence, "HWP-PRESTATE-COUNT",
                       "complete 64-bit prestate is required for CPUs 0, 1, and 26"));
  }
  for (const auto cpu : kHardwarePrefetchControlCpus) {
    const auto matches = static_cast<std::size_t>(
        std::count_if(prestate.begin(), prestate.end(),
                      [cpu](const auto& value) { return value.cpu == cpu; }));
    if (matches != 1U) {
      errors.push_back(
          prefetch_error(ErrorCategory::missing_evidence, "HWP-PRESTATE-CPU-UNIQUE",
                         "each selected CPU must have exactly one complete prestate"));
    }
  }
  for (const auto& value : prestate) {
    if (std::find(kHardwarePrefetchControlCpus.begin(),
                  kHardwarePrefetchControlCpus.end(),
                  value.cpu) == kHardwarePrefetchControlCpus.end()) {
      errors.push_back(prefetch_error(ErrorCategory::invalid_request,
                                      "HWP-CPU-WHITELIST",
                                      "prestate contains a CPU outside 0, 1, and 26"));
    }
  }
  if (!errors.empty()) {
    return Result<HardwarePrefetchPlan>::failure(std::move(errors));
  }

  HardwarePrefetchPlan plan{
      requested_state,
      std::vector<HardwarePrefetchMsrValue>(prestate.begin(), prestate.end()),
      {},
      requested_state == protocol::RequestedHardwareState::h1};
  plan.requested.reserve(kHardwarePrefetchControlCpus.size());
  for (const auto cpu : kHardwarePrefetchControlCpus) {
    const auto* prior = find_msr_value(prestate, cpu);
    const auto requested = requested_state == protocol::RequestedHardwareState::h1
                               ? prior->value | kHardwarePrefetchDisableMask
                               : prior->value;
    if (requested_state == protocol::RequestedHardwareState::h1 &&
        requested == prior->value) {
      errors.push_back(prefetch_error(
          ErrorCategory::unsupported_control, "HWP-H0-H1-COLLAPSE",
          "H1 cannot differ from the observed H0 prestate on one selected CPU"));
    }
    plan.requested.push_back({cpu, requested});
  }
  if (!errors.empty()) {
    return Result<HardwarePrefetchPlan>::failure(std::move(errors));
  }
  return Result<HardwarePrefetchPlan>::success(std::move(plan));
}

auto qualify_hardware_prefetch_plan(const HardwarePrefetchPlan& plan,
                                    HardwarePrefetchMsrBackend& writer,
                                    HardwarePrefetchMsrBackend& independent_verifier,
                                    HardwarePrefetchProbeInput probes)
    -> HardwarePrefetchTransactionReport {
  HardwarePrefetchTransactionReport report{};
  const auto add_error = [&](ErrorCategory category, std::string rule,
                             std::string message) {
    report.errors.push_back(
        prefetch_error(category, std::move(rule), std::move(message)));
  };
  if (writer.backend_id().empty() || independent_verifier.backend_id().empty() ||
      writer.backend_id() == independent_verifier.backend_id()) {
    add_error(ErrorCategory::invalid_request, "HWP-INDEPENDENT-VERIFY",
              "writer and verifier must be distinct named backends");
    return report;
  }
  const auto validated = make_hardware_prefetch_plan(
      {kIntelFamily6, kIntelModel55}, plan.requested_state, plan.prestate);
  if (!validated || plan.requested != validated.value().requested ||
      plan.mutating != validated.value().mutating) {
    add_error(ErrorCategory::invalid_request, "HWP-PLAN-EXACT",
              "transaction plan must equal the narrow accepted mapping");
    return report;
  }

  std::vector<std::uint32_t> written;
  bool apply_ok = true;
  for (const auto& requested : plan.requested) {
    if (plan.mutating) {
      const auto write = writer.write(requested.cpu, requested.value);
      if (!write.succeeded) {
        add_error(write.failure_category.value_or(ErrorCategory::apply_failure),
                  "HWP-APPLY", "authorized exact H1 write failed");
        apply_ok = false;
        break;
      }
      written.push_back(requested.cpu);
    }
    const auto observed = independent_verifier.read(requested.cpu);
    if (!observed || observed.value() != requested.value) {
      add_error(ErrorCategory::verification_mismatch, "HWP-READBACK",
                "independent complete-value readback did not match request");
      apply_ok = false;
      break;
    }
    report.apply_readback.push_back({requested.cpu, observed.value()});
  }
  report.applied = apply_ok && (!plan.mutating ||
                                written.size() == kHardwarePrefetchControlCpus.size());
  report.verified =
      apply_ok && report.apply_readback.size() == kHardwarePrefetchControlCpus.size();
  report.probes_passed =
      report.verified && probes.regular_stream_passed && probes.pointer_stream_passed;
  if (report.verified && !report.probes_passed) {
    add_error(ErrorCategory::verification_mismatch, "HWP-PROBES",
              "regular and pointer-stream probes must both pass");
  }

  if (!plan.mutating) {
    report.restored = true;
    return report;
  }

  bool restoration_ok = true;
  for (auto position = written.rbegin(); position != written.rend(); ++position) {
    const auto* prior = find_msr_value(plan.prestate, *position);
    const auto restored = writer.write(*position, prior->value);
    if (!restored.succeeded) {
      restoration_ok = false;
      add_error(ErrorCategory::restoration_failure, "HWP-RESTORE-WRITE",
                "exact complete-value restoration write failed");
      continue;
    }
    const auto observed = independent_verifier.read(*position);
    if (!observed || observed.value() != prior->value) {
      restoration_ok = false;
      add_error(ErrorCategory::restoration_failure, "HWP-RESTORE-READBACK",
                "independent restoration readback did not match prestate");
      continue;
    }
    report.restore_readback.push_back({*position, observed.value()});
  }
  report.restored = restoration_ok && report.restore_readback.size() == written.size();
  report.quarantined = !report.restored;
  return report;
}

auto to_string(ErrorCategory category) -> std::string_view {
  switch (category) {
  case ErrorCategory::parse_error:
    return "PARSE_ERROR";
  case ErrorCategory::missing_evidence:
    return "MISSING_EVIDENCE";
  case ErrorCategory::invalid_request:
    return "INVALID_REQUEST";
  case ErrorCategory::impossible_placement:
    return "IMPOSSIBLE_PLACEMENT";
  case ErrorCategory::sibling_conflict:
    return "SIBLING_CONFLICT";
  case ErrorCategory::numa_mismatch:
    return "NUMA_MISMATCH";
  case ErrorCategory::unsupported_control:
    return "UNSUPPORTED_CONTROL";
  case ErrorCategory::privilege_denied:
    return "PRIVILEGE_DENIED";
  case ErrorCategory::apply_failure:
    return "APPLY_FAILURE";
  case ErrorCategory::verification_mismatch:
    return "VERIFICATION_MISMATCH";
  case ErrorCategory::restoration_failure:
    return "RESTORATION_FAILURE";
  case ErrorCategory::stale_state:
    return "STALE_STATE";
  case ErrorCategory::manifest_incomplete:
    return "MANIFEST_INCOMPLETE";
  case ErrorCategory::io_error:
    return "IO_ERROR";
  }
  return "UNKNOWN";
}

auto to_string(ControlKind kind) -> std::string_view {
  switch (kind) {
  case ControlKind::producer_affinity:
    return "PRODUCER_AFFINITY";
  case ControlKind::consumer_affinity:
    return "CONSUMER_AFFINITY";
  case ControlKind::producer_actual_cpu:
    return "PRODUCER_ACTUAL_CPU";
  case ControlKind::consumer_actual_cpu:
    return "CONSUMER_ACTUAL_CPU";
  case ControlKind::shared_memory_policy:
    return "SHARED_MEMORY_POLICY";
  case ControlKind::producer_private_memory_policy:
    return "PRODUCER_PRIVATE_MEMORY_POLICY";
  case ControlKind::consumer_private_memory_policy:
    return "CONSUMER_PRIVATE_MEMORY_POLICY";
  case ControlKind::shared_page_residency:
    return "SHARED_PAGE_RESIDENCY";
  case ControlKind::private_page_residency:
    return "PRIVATE_PAGE_RESIDENCY";
  case ControlKind::base_page_state:
    return "BASE_PAGE_STATE";
  case ControlKind::huge_page_state:
    return "HUGE_PAGE_STATE";
  case ControlKind::governor:
    return "GOVERNOR";
  case ControlKind::fixed_frequency:
    return "FIXED_FREQUENCY";
  case ControlKind::turbo:
    return "TURBO";
  case ControlKind::c_state:
    return "C_STATE";
  case ControlKind::smt:
    return "SMT";
  case ControlKind::interrupt_routing:
    return "INTERRUPT_ROUTING";
  case ControlKind::cpu_isolation:
    return "CPU_ISOLATION";
  case ControlKind::hardware_prefetch:
    return "HARDWARE_PREFETCH";
  case ControlKind::clock_source:
    return "CLOCK_SOURCE";
  case ControlKind::microcode:
    return "MICROCODE";
  case ControlKind::firmware:
    return "FIRMWARE";
  case ControlKind::compiler:
    return "COMPILER";
  case ControlKind::binary:
    return "BINARY";
  case ControlKind::library:
    return "LIBRARY";
  }
  return "UNKNOWN";
}

auto to_string(CapabilityStatus status) -> std::string_view {
  switch (status) {
  case CapabilityStatus::read_only:
    return "READ_ONLY";
  case CapabilityStatus::external_authority_required:
    return "EXTERNAL_AUTHORITY_REQUIRED";
  case CapabilityStatus::unavailable:
    return "UNAVAILABLE";
  case CapabilityStatus::mapping_unresolved:
    return "MAPPING_UNRESOLVED";
  }
  return "UNKNOWN";
}

auto to_string(MemoryPolicy policy) -> std::string_view {
  switch (policy) {
  case MemoryPolicy::bind_producer_node:
    return "BIND_PRODUCER_NODE";
  case MemoryPolicy::bind_worker_local:
    return "BIND_WORKER_LOCAL";
  case MemoryPolicy::interleave:
    return "INTERLEAVE";
  case MemoryPolicy::consumer_local:
    return "CONSUMER_LOCAL";
  case MemoryPolicy::replicated:
    return "REPLICATED";
  case MemoryPolicy::migrated:
    return "MIGRATED";
  }
  return "UNKNOWN";
}

auto to_string(PagePolicy policy) -> std::string_view {
  switch (policy) {
  case PagePolicy::verified_base_pages:
    return "VERIFIED_BASE_PAGES";
  case PagePolicy::explicit_huge_pages:
    return "EXPLICIT_HUGE_PAGES";
  case PagePolicy::transparent_huge_pages:
    return "TRANSPARENT_HUGE_PAGES";
  }
  return "UNKNOWN";
}

auto to_string(ApplyMode mode) -> std::string_view {
  switch (mode) {
  case ApplyMode::dry_run:
    return "DRY_RUN";
  case ApplyMode::authorized_apply:
    return "AUTHORIZED_APPLY";
  }
  return "UNKNOWN";
}

auto to_string(StepStatus status) -> std::string_view {
  switch (status) {
  case StepStatus::planned:
    return "PLANNED";
  case StepStatus::applied:
    return "APPLIED";
  case StepStatus::apply_failed:
    return "APPLY_FAILED";
  case StepStatus::verified:
    return "VERIFIED";
  case StepStatus::verification_failed:
    return "VERIFICATION_FAILED";
  case StepStatus::stale:
    return "STALE";
  case StepStatus::restored:
    return "RESTORED";
  case StepStatus::restoration_failed:
    return "RESTORATION_FAILED";
  }
  return "UNKNOWN";
}

auto detect_capabilities(const PlatformInventory& inventory)
    -> std::vector<Capability> {
  const bool has_numa = !inventory.numa_nodes.empty();
  const bool has_cpufreq = has_observation(inventory, "cpufreq");
  const bool has_turbo = has_observation(inventory, "turbo");
  const bool has_cpuidle = has_observation(inventory, "cpuidle");
  const bool has_smt = has_observation(inventory, "smt");
  const bool has_interrupt = has_observation(inventory, "interrupt_affinity");
  const bool has_isolation = has_observation(inventory, "cpu_isolation");
  const bool has_clock = has_observation(inventory, "clock_source");
  const bool has_firmware = has_observation(inventory, "firmware");
  const bool has_huge_pages = has_observation(inventory, "huge_pages");

  const auto read_only = [](ControlKind kind, std::string mechanism,
                            std::string evidence) {
    return Capability{kind, CapabilityStatus::read_only, std::move(mechanism),
                      std::move(evidence), false};
  };
  const auto external = [](ControlKind kind, std::string mechanism,
                           std::string evidence, bool privilege) {
    return Capability{kind, CapabilityStatus::external_authority_required,
                      std::move(mechanism), std::move(evidence), privilege};
  };
  const auto conditional = [](ControlKind kind, bool available, std::string mechanism,
                              std::string evidence, bool privilege) {
    return Capability{kind,
                      available ? CapabilityStatus::external_authority_required
                                : CapabilityStatus::unavailable,
                      std::move(mechanism), std::move(evidence), privilege};
  };

  std::vector<Capability> output{
      external(ControlKind::producer_affinity, "sched_setaffinity",
               "Linux affinity API; role authorization remains mandatory", false),
      external(ControlKind::consumer_affinity, "sched_setaffinity",
               "Linux affinity API; role authorization remains mandatory", false),
      read_only(ControlKind::producer_actual_cpu, "sched_getcpu+affinity-readback",
                "independent worker observation required"),
      read_only(ControlKind::consumer_actual_cpu, "sched_getcpu+affinity-readback",
                "independent worker observation required"),
      conditional(ControlKind::shared_memory_policy, has_numa, "mbind-or-set_mempolicy",
                  "NUMA topology is readable", false),
      conditional(ControlKind::producer_private_memory_policy, has_numa,
                  "mbind-or-set_mempolicy", "NUMA topology is readable", false),
      conditional(ControlKind::consumer_private_memory_policy, has_numa,
                  "mbind-or-set_mempolicy", "NUMA topology is readable", false),
      read_only(ControlKind::shared_page_residency, "move_pages+procfs",
                "address-specific before/during/after evidence required"),
      read_only(ControlKind::private_page_residency, "move_pages+procfs",
                "address-specific before/during/after evidence required"),
      external(ControlKind::base_page_state, "allocation-policy+smaps-readback",
               "base page size inventoried; address-specific readback required", false),
      conditional(ControlKind::huge_page_state, has_huge_pages, "sysfs+smaps-readback",
                  "huge-page state observation", true),
      conditional(ControlKind::governor, has_cpufreq, "cpufreq-sysfs",
                  "cpufreq policy files", true),
      conditional(ControlKind::fixed_frequency, has_cpufreq, "cpufreq-sysfs",
                  "cpufreq min/max policy files", true),
      conditional(ControlKind::turbo, has_turbo, "platform-turbo-sysfs",
                  "vendor-neutral mechanism not assumed", true),
      conditional(ControlKind::c_state, has_cpuidle, "cpuidle-sysfs",
                  "cpuidle driver/governor observation", true),
      conditional(ControlKind::smt, has_smt, "smt-sysfs", "SMT state is readable",
                  true),
      conditional(ControlKind::interrupt_routing, has_interrupt, "procfs-irq",
                  "IRQ affinity is readable", true),
      conditional(ControlKind::cpu_isolation, has_isolation, "sysfs+kernel-cmdline",
                  "isolation/nohz observations", true),
      {ControlKind::hardware_prefetch, CapabilityStatus::mapping_unresolved,
       "vendor-specific-unresolved",
       "exact manual, field map, authority, readback, probes, and rollback absent",
       true},
      {ControlKind::clock_source,
       has_clock ? CapabilityStatus::read_only : CapabilityStatus::unavailable,
       "clocksource-sysfs", "current clocksource observation", false},
      read_only(ControlKind::microcode, "proc-cpuinfo", "microcode observation"),
      {ControlKind::firmware,
       has_firmware ? CapabilityStatus::read_only : CapabilityStatus::unavailable,
       "dmi-sysfs", "firmware observation", false},
      read_only(ControlKind::compiler, "build-metadata", "compiled identity"),
      read_only(ControlKind::binary, "sha256-artifact",
                "caller-supplied artifact hash"),
      read_only(ControlKind::library, "dependency-manifest",
                "caller-supplied dependency provenance"),
  };
  return output;
}

auto validate_requested_state(const PlatformInventory& inventory,
                              std::span<const Capability> capabilities,
                              const RequestedState& request) -> std::vector<Error> {
  std::vector<Error> errors;
  if (request.request_id.empty()) {
    errors.push_back(make_error(ErrorCategory::invalid_request, "$request/request_id",
                                "PLT-REQUEST-ID", "request ID must not be empty"));
  }
  if (request.inventory_snapshot_id != inventory.snapshot_id) {
    errors.push_back(make_error(
        ErrorCategory::stale_state, "$request/inventory_snapshot_id",
        "PLT-SNAPSHOT-BINDING", "request is not bound to this inventory snapshot"));
  }
  if (request.hardware_prefetch_state ==
      protocol::RequestedHardwareState::not_applicable) {
    errors.push_back(make_error(ErrorCategory::invalid_request,
                                "$request/hardware_prefetch_state", "PLT-HWPF-STATE",
                                "Stage A requires an explicit H0 or H1 request"));
  }

  const auto* producer = find_cpu(inventory, request.placement.producer_cpu);
  const auto* consumer = find_cpu(inventory, request.placement.consumer_cpu);
  if (producer == nullptr || consumer == nullptr || !producer->online ||
      !consumer->online || producer->logical_id == consumer->logical_id) {
    errors.push_back(make_error(ErrorCategory::impossible_placement,
                                "$request/placement", "PLT-CPU-ELIGIBILITY",
                                "producer and consumer must be distinct online CPUs"));
  } else {
    const bool siblings = (producer->package_id == consumer->package_id &&
                           producer->core_id == consumer->core_id) ||
                          contains(producer->thread_siblings, consumer->logical_id) ||
                          contains(consumer->thread_siblings, producer->logical_id);
    if (siblings) {
      errors.push_back(make_error(
          ErrorCategory::sibling_conflict, "$request/placement", "PLT-NON-SMT-PAIR",
          "producer and consumer resolve to one physical core"));
    }
    if (request.placement.placement == protocol::Placement::near) {
      if (producer->numa_node != consumer->numa_node ||
          !same_last_level_cache(inventory, *producer, *consumer)) {
        errors.push_back(make_error(
            ErrorCategory::numa_mismatch, "$request/placement", "PLT-NEAR",
            "NEAR requires one NUMA node and a shared last-level cache domain"));
      }
    } else if (request.placement.placement == protocol::Placement::far) {
      if (producer->numa_node == consumer->numa_node) {
        errors.push_back(make_error(ErrorCategory::numa_mismatch, "$request/placement",
                                    "PLT-FAR",
                                    "FAR requires CPUs in different NUMA nodes"));
      }
    } else {
      errors.push_back(make_error(
          ErrorCategory::invalid_request, "$request/placement/placement",
          "PLT-STAGE-A-PLACEMENT", "only NEAR and FAR are Stage A placements"));
    }

    const auto singleton_node = [](std::span<const std::uint32_t> nodes,
                                   std::uint32_t expected) {
      return nodes.size() == 1U && nodes.front() == expected;
    };
    if (request.placement.shared_memory_policy != MemoryPolicy::bind_producer_node ||
        !singleton_node(request.placement.shared_memory_nodes, producer->numa_node)) {
      errors.push_back(make_error(
          ErrorCategory::numa_mismatch, "$request/placement/shared_memory",
          "PLT-PRODUCER-HOME",
          "Stage A shared queue, nodes, records, and schedule must be producer-home"));
    }
    if (request.placement.producer_private_memory_policy !=
            MemoryPolicy::bind_worker_local ||
        !singleton_node(request.placement.producer_private_nodes,
                        producer->numa_node)) {
      errors.push_back(make_error(
          ErrorCategory::numa_mismatch, "$request/placement/producer_private_memory",
          "PLT-PRODUCER-PRIVATE", "producer-private buffers must be producer-local"));
    }
    if (request.placement.consumer_private_memory_policy !=
            MemoryPolicy::bind_worker_local ||
        !singleton_node(request.placement.consumer_private_nodes,
                        consumer->numa_node)) {
      errors.push_back(make_error(
          ErrorCategory::numa_mismatch, "$request/placement/consumer_private_memory",
          "PLT-CONSUMER-PRIVATE", "consumer-private buffers must be consumer-local"));
    }
  }

  if (request.placement.page_policy != PagePolicy::verified_base_pages ||
      request.placement.requested_page_bytes != inventory.base_page_bytes) {
    errors.push_back(make_error(
        ErrorCategory::invalid_request, "$request/placement/page_policy",
        "PLT-STAGE-A-PAGES",
        "Stage A requires the explicitly inventoried base-page policy; huge-page "
        "treatments are Stage C"));
  }

  std::set<std::string, std::less<>> control_ids;
  bool has_hardware_prefetch = false;
  for (const auto& control : request.controls) {
    const auto path = "$request/controls/" + control.control_id;
    if (control.control_id.empty() || control.target.empty() ||
        control.requested_value.empty() || control.verification_mechanism.empty()) {
      errors.push_back(
          make_error(ErrorCategory::invalid_request, path, "PLT-CONTROL-FIELDS",
                     "control identity, target, value, and readback are required"));
    }
    if (!control_ids.insert(control.control_id).second) {
      errors.push_back(make_error(ErrorCategory::invalid_request, path,
                                  "PLT-CONTROL-UNIQUE",
                                  "control IDs must be unique within a request"));
    }
    if (control.mutating &&
        (control.authority_id.empty() || control.actuation_mechanism.empty())) {
      errors.push_back(make_error(
          ErrorCategory::privilege_denied, path, "PLT-AUTHORITY",
          "a mutating control requires explicit authority and actuation mechanism"));
    }
    if (control.mutating &&
        control.actuation_mechanism == control.verification_mechanism) {
      errors.push_back(make_error(
          ErrorCategory::invalid_request, path, "PLT-INDEPENDENT-READBACK",
          "actuation and verification mechanisms must be independently identified"));
    }
    const auto* capability = capability_for(capabilities, control.kind);
    if (capability == nullptr || capability->status == CapabilityStatus::unavailable ||
        capability->status == CapabilityStatus::mapping_unresolved ||
        (control.mutating && capability->status == CapabilityStatus::read_only)) {
      errors.push_back(
          make_error(ErrorCategory::unsupported_control, path, "PLT-CAPABILITY",
                     "requested control lacks an established applicable capability"));
    }
    has_hardware_prefetch =
        has_hardware_prefetch || control.kind == ControlKind::hardware_prefetch;
  }
  if (!has_hardware_prefetch) {
    errors.push_back(make_error(
        ErrorCategory::missing_evidence, "$request/controls", "PLT-HWPF-CONTROL",
        "H0/H1 requires an explicit hardware-prefetch control"));
  }
  return errors;
}

auto restore_platform_state(std::span<const ControlRequest> applied_controls,
                            std::span<const StateObservation> prior_state,
                            ControlActuator& actuator) -> RestorationReport {
  RestorationReport report{!applied_controls.empty(), true, {}, {}};
  for (auto iterator = applied_controls.rbegin(); iterator != applied_controls.rend();
       ++iterator) {
    const auto* prior = observation_for(prior_state, iterator->control_id);
    if (prior == nullptr || !prior->observed_value.has_value()) {
      report.complete = false;
      report.steps.push_back({iterator->control_id,
                              StepStatus::restoration_failed,
                              {},
                              "pre-state evidence is missing"});
      report.errors.push_back(make_error(ErrorCategory::restoration_failure,
                                         "$restore/" + iterator->control_id,
                                         "PLT-RESTORE-PRESTATE",
                                         "cannot restore a changed control without its "
                                         "independently recorded pre-state"));
      continue;
    }
    const auto result = actuator.restore(*iterator, *prior);
    report.steps.push_back(
        {iterator->control_id,
         result.succeeded ? StepStatus::restored : StepStatus::restoration_failed,
         result.evidence_id, result.detail});
    if (!result.succeeded) {
      report.complete = false;
      report.errors.push_back(make_error(
          ErrorCategory::restoration_failure, "$restore/" + iterator->control_id,
          "PLT-RESTORE-FAILED", "the actuator did not restore the recorded pre-state"));
    }
  }
  return report;
}

auto apply_requested_state(const RequestedState& request,
                           std::span<const StateObservation> prior_state,
                           ApplyMode mode, ControlActuator* actuator) -> ApplyReport {
  ApplyReport report{mode, true, {}, {false, true, {}, {}}, {}};
  if (mode == ApplyMode::dry_run) {
    for (const auto& control : request.controls) {
      report.steps.push_back(
          {control.control_id,
           StepStatus::planned,
           {},
           control.mutating ? "mutation not executed" : "observation-only control"});
    }
    return report;
  }
  if (actuator == nullptr || actuator->backend_id().empty()) {
    report.complete = false;
    report.errors.push_back(make_error(
        ErrorCategory::privilege_denied, "$apply", "PLT-ACTUATOR-AUTHORITY",
        "authorized apply requires an explicitly identified actuator backend"));
    return report;
  }

  std::vector<ControlRequest> applied;
  for (const auto& control : request.controls) {
    if (!control.mutating) {
      report.steps.push_back(
          {control.control_id, StepStatus::planned, {}, "observation-only control"});
      continue;
    }
    if (observation_for(prior_state, control.control_id) == nullptr) {
      report.complete = false;
      report.steps.push_back({control.control_id,
                              StepStatus::apply_failed,
                              {},
                              "pre-state evidence is missing"});
      report.errors.push_back(
          make_error(ErrorCategory::missing_evidence, "$apply/" + control.control_id,
                     "PLT-APPLY-PRESTATE",
                     "mutation is forbidden without fresh pre-state evidence"));
      report.restoration = restore_platform_state(applied, prior_state, *actuator);
      return report;
    }
    const auto result = actuator->apply(control);
    report.steps.push_back(
        {control.control_id,
         result.succeeded ? StepStatus::applied : StepStatus::apply_failed,
         result.evidence_id, result.detail});
    if (!result.succeeded) {
      report.complete = false;
      report.errors.push_back(
          make_error(result.failure_category.value_or(ErrorCategory::apply_failure),
                     "$apply/" + control.control_id, "PLT-APPLY-FAILED",
                     "actuator reported a failed control operation"));
      report.restoration = restore_platform_state(applied, prior_state, *actuator);
      return report;
    }
    applied.push_back(control);
  }
  return report;
}

auto verify_requested_state(const RequestedState& request, StateVerifier& verifier)
    -> VerificationReport {
  VerificationReport report{true, true, {}, {}, {}};
  for (const auto& control : request.controls) {
    auto result = verifier.readback(control);
    if (!result) {
      report.complete = false;
      report.all_mandatory_match = report.all_mandatory_match && !control.mandatory;
      report.steps.push_back({control.control_id,
                              StepStatus::verification_failed,
                              {},
                              "readback unavailable"});
      report.errors.insert(report.errors.end(), result.errors().begin(),
                           result.errors().end());
      continue;
    }
    auto observation = std::move(result).value();
    const bool stale =
        observation.inventory_snapshot_id != request.inventory_snapshot_id ||
        observation.state_epoch != request.state_epoch;
    const bool independent =
        observation.mechanism_id == control.verification_mechanism &&
        (!control.mutating || observation.mechanism_id != control.actuation_mechanism);
    const bool matched = observation.observed_value.has_value() &&
                         *observation.observed_value == control.requested_value;
    StepStatus status = StepStatus::verified;
    if (stale) {
      status = StepStatus::stale;
      report.errors.push_back(
          make_error(ErrorCategory::stale_state, "$verify/" + control.control_id,
                     "PLT-VERIFY-FRESHNESS",
                     "readback is bound to a different snapshot or epoch"));
    } else if (!independent || !matched || observation.evidence_id.empty()) {
      status = StepStatus::verification_failed;
      report.errors.push_back(make_error(
          ErrorCategory::verification_mismatch, "$verify/" + control.control_id,
          "PLT-VERIFY-MATCH",
          "fresh independent readback does not exactly match the requested value"));
    }
    if (status != StepStatus::verified) {
      report.complete = false;
      report.all_mandatory_match = report.all_mandatory_match && !control.mandatory;
    }
    report.steps.push_back({control.control_id, status, observation.evidence_id,
                            status == StepStatus::verified
                                ? "fresh independent exact match"
                                : "verification rejected"});
    report.observations.push_back(std::move(observation));
  }
  return report;
}

auto emit_manifest(const ManifestContext& context, const PlatformInventory& inventory,
                   std::span<const Capability> capabilities,
                   const RequestedState& request, const ApplyReport& apply_report,
                   const VerificationReport& verification_report)
    -> Result<ManifestArtifact> {
  std::vector<Error> errors;
  auto state_errors = validate_requested_state(inventory, capabilities, request);
  constexpr std::array<ControlKind, 24> required_control_kinds{
      ControlKind::producer_affinity,
      ControlKind::consumer_affinity,
      ControlKind::producer_actual_cpu,
      ControlKind::consumer_actual_cpu,
      ControlKind::shared_memory_policy,
      ControlKind::producer_private_memory_policy,
      ControlKind::consumer_private_memory_policy,
      ControlKind::shared_page_residency,
      ControlKind::private_page_residency,
      ControlKind::base_page_state,
      ControlKind::huge_page_state,
      ControlKind::governor,
      ControlKind::fixed_frequency,
      ControlKind::turbo,
      ControlKind::c_state,
      ControlKind::smt,
      ControlKind::interrupt_routing,
      ControlKind::cpu_isolation,
      ControlKind::hardware_prefetch,
      ControlKind::clock_source,
      ControlKind::microcode,
      ControlKind::firmware,
      ControlKind::compiler,
      ControlKind::binary,
  };
  for (const auto kind : required_control_kinds) {
    const bool present = std::any_of(request.controls.begin(), request.controls.end(),
                                     [kind](const ControlRequest& control) {
                                       return control.kind == kind && control.mandatory;
                                     });
    if (!present) {
      state_errors.push_back(make_error(
          ErrorCategory::missing_evidence, "$manifest/request/controls",
          "PLT-MANIFEST-REQUIRED-CONTROL",
          "mandatory platform control is absent: " + std::string(to_string(kind))));
    }
  }
  const bool has_library_control =
      std::any_of(request.controls.begin(), request.controls.end(),
                  [](const ControlRequest& control) {
                    return control.kind == ControlKind::library && control.mandatory;
                  });
  if (!has_library_control) {
    state_errors.push_back(
        make_error(ErrorCategory::missing_evidence, "$manifest/request/controls",
                   "PLT-MANIFEST-REQUIRED-CONTROL",
                   "at least one mandatory library-provenance control is required"));
  }
  require_text(errors, context.platform_id, "$manifest/platform_id", "PLT-MANIFEST-ID");
  require_text(errors, context.manifest_id, "$manifest/manifest_id", "PLT-MANIFEST-ID");
  require_text(errors, context.build_id, "$manifest/build_id", "PLT-MANIFEST-BUILD");
  require_text(errors, context.link_mode, "$manifest/link_mode", "PLT-MANIFEST-LINK");
  require_text(errors, inventory.snapshot_id, "$manifest/inventory/snapshot_id",
               "PLT-MANIFEST-SNAPSHOT");
  require_text(errors, inventory.captured_at_utc, "$manifest/inventory/captured_at_utc",
               "PLT-MANIFEST-TIME");
  if (!valid_sha256(context.binary_sha256)) {
    errors.push_back(
        make_error(ErrorCategory::manifest_incomplete, "$manifest/binary_sha256",
                   "PLT-MANIFEST-BINARY",
                   "binary SHA-256 must be 64 lowercase hexadecimal digits"));
  }
  if (context.libraries.empty()) {
    errors.push_back(make_error(ErrorCategory::manifest_incomplete,
                                "$manifest/libraries", "PLT-MANIFEST-LIBRARIES",
                                "relevant library provenance must not be empty"));
  }
  for (const auto& library : context.libraries) {
    if (library.name.empty() || library.version.empty() ||
        !valid_sha256(library.artifact_sha256)) {
      errors.push_back(make_error(ErrorCategory::manifest_incomplete,
                                  "$manifest/libraries", "PLT-MANIFEST-LIBRARY",
                                  "each library needs name, version, and SHA-256"));
    }
  }
  if (inventory.logical_cpus.empty() || inventory.cache_domains.empty() ||
      inventory.numa_nodes.empty() || inventory.cpu.vendor.empty() ||
      inventory.cpu.model.empty() || inventory.cpu.microcode.empty() ||
      inventory.software.kernel.empty() || !has_observation(inventory, "firmware")) {
    errors.push_back(
        make_error(ErrorCategory::manifest_incomplete, "$manifest/inventory",
                   "PLT-MANIFEST-INVENTORY",
                   "CPU, cache, NUMA, microcode, and kernel inventory are mandatory"));
  }
  if (request.inventory_snapshot_id != inventory.snapshot_id) {
    errors.push_back(make_error(
        ErrorCategory::stale_state, "$manifest/request/inventory_snapshot_id",
        "PLT-MANIFEST-BINDING", "manifest request and inventory snapshot differ"));
  }
  if (apply_report.steps.size() != request.controls.size() ||
      verification_report.steps.size() != request.controls.size()) {
    errors.push_back(make_error(
        ErrorCategory::manifest_incomplete, "$manifest/control_results",
        "PLT-MANIFEST-CONTROLS",
        "every requested control needs separate apply/plan and verification records"));
  }
  if (!errors.empty()) {
    return Result<ManifestArtifact>::failure(std::move(errors));
  }

  JsonArray logical_cpus;
  for (const auto& cpu : inventory.logical_cpus) {
    logical_cpus.emplace_back(JsonObject{
        {"cache_domains", string_array(cpu.cache_domains)},
        {"core_id", uint_value(cpu.core_id)},
        {"logical_id", uint_value(cpu.logical_id)},
        {"numa_node", uint_value(cpu.numa_node)},
        {"online", protocol::json::Value(cpu.online)},
        {"package_id", uint_value(cpu.package_id)},
        {"thread_siblings", uint_array(cpu.thread_siblings)},
    });
  }
  JsonArray cache_domains;
  for (const auto& cache : inventory.cache_domains) {
    cache_domains.emplace_back(JsonObject{
        {"domain_id", protocol::json::Value(cache.domain_id)},
        {"kind", protocol::json::Value(cache.kind)},
        {"last_level", protocol::json::Value(cache.last_level)},
        {"level", uint_value(cache.level)},
        {"shared_cpus", uint_array(cache.shared_cpus)},
        {"size_bytes", uint_value(cache.size_bytes)},
    });
  }
  JsonArray numa_nodes;
  for (const auto& node : inventory.numa_nodes) {
    numa_nodes.emplace_back(JsonObject{
        {"logical_cpus", uint_array(node.logical_cpus)},
        {"node_id", uint_value(node.node_id)},
    });
  }
  JsonArray pci_devices;
  for (const auto& device : inventory.pci_devices) {
    pci_devices.emplace_back(JsonObject{
        {"address", protocol::json::Value(device.address)},
        {"class", protocol::json::Value(device.device_class)},
        {"device", protocol::json::Value(device.device)},
        {"local_cpus", uint_array(device.local_cpus)},
        {"numa_node", device.numa_node.has_value() ? int_value(*device.numa_node)
                                                   : protocol::json::Value(nullptr)},
        {"vendor", protocol::json::Value(device.vendor)},
    });
  }
  JsonArray observations;
  for (const auto& observation : inventory.observations) {
    observations.emplace_back(JsonObject{
        {"name", protocol::json::Value(observation.name)},
        {"source", protocol::json::Value(observation.source)},
        {"value", observation.value.has_value()
                      ? protocol::json::Value(*observation.value)
                      : protocol::json::Value(nullptr)},
    });
  }
  JsonArray capability_values;
  for (const auto& capability : capabilities) {
    capability_values.emplace_back(JsonObject{
        {"detection_mechanism", protocol::json::Value(capability.detection_mechanism)},
        {"evidence", protocol::json::Value(capability.evidence)},
        {"kernel_privilege_required",
         protocol::json::Value(capability.kernel_privilege_required)},
        {"kind", protocol::json::Value(std::string(to_string(capability.kind)))},
        {"status", protocol::json::Value(std::string(to_string(capability.status)))},
    });
  }
  JsonArray controls;
  for (const auto& control : request.controls) {
    controls.push_back(control_json(control));
  }
  JsonArray apply_steps;
  for (const auto& step : apply_report.steps) {
    apply_steps.push_back(step_json(step));
  }
  JsonArray restoration_steps;
  for (const auto& step : apply_report.restoration.steps) {
    restoration_steps.push_back(step_json(step));
  }
  JsonArray verification_steps;
  for (const auto& step : verification_report.steps) {
    verification_steps.push_back(step_json(step));
  }
  JsonArray verification_observations;
  for (const auto& observation : verification_report.observations) {
    verification_observations.emplace_back(JsonObject{
        {"control_id", protocol::json::Value(observation.control_id)},
        {"evidence_id", protocol::json::Value(observation.evidence_id)},
        {"inventory_snapshot_id",
         protocol::json::Value(observation.inventory_snapshot_id)},
        {"mechanism_id", protocol::json::Value(observation.mechanism_id)},
        {"observed_value", observation.observed_value.has_value()
                               ? protocol::json::Value(*observation.observed_value)
                               : protocol::json::Value(nullptr)},
        {"state_epoch", uint_value(observation.state_epoch)},
    });
  }
  JsonArray all_errors;
  for (const auto& error : apply_report.errors) {
    all_errors.push_back(error_json(error));
  }
  for (const auto& error : apply_report.restoration.errors) {
    all_errors.push_back(error_json(error));
  }
  for (const auto& error : verification_report.errors) {
    all_errors.push_back(error_json(error));
  }
  for (const auto& error : state_errors) {
    all_errors.push_back(error_json(error));
  }
  JsonArray libraries;
  for (const auto& library : context.libraries) {
    libraries.emplace_back(JsonObject{
        {"artifact_sha256", protocol::json::Value(library.artifact_sha256)},
        {"name", protocol::json::Value(library.name)},
        {"version", protocol::json::Value(library.version)},
    });
  }

  const bool eligible =
      apply_report.mode == ApplyMode::authorized_apply && state_errors.empty() &&
      apply_report.complete && !apply_report.restoration.attempted &&
      verification_report.complete && verification_report.all_mandatory_match;
  JsonObject root{
      {"apply",
       protocol::json::Value(JsonObject{
           {"complete", protocol::json::Value(apply_report.complete)},
           {"mode", protocol::json::Value(std::string(to_string(apply_report.mode)))},
           {"steps", protocol::json::Value(std::move(apply_steps))},
       })},
      {"build_id", protocol::json::Value(context.build_id)},
      {"capabilities", protocol::json::Value(std::move(capability_values))},
      {"compiler_flags", string_array(context.compiler_flags)},
      {"control_errors", protocol::json::Value(std::move(all_errors))},
      {"eligible", protocol::json::Value(eligible)},
      {"evidence_version",
       protocol::json::Value(std::string(kPlatformEvidenceVersion))},
      {"inventory",
       protocol::json::Value(JsonObject{
           {"base_page_bytes", uint_value(inventory.base_page_bytes)},
           {"cache_domains", protocol::json::Value(std::move(cache_domains))},
           {"captured_at_utc", protocol::json::Value(inventory.captured_at_utc)},
           {"cpu",
            protocol::json::Value(JsonObject{
                {"atomic_alignment_bytes",
                 uint_value(inventory.cpu.atomic_alignment_bytes)},
                {"atomic_width_bits", uint_value(inventory.cpu.atomic_width_bits)},
                {"cache_line_bytes", uint_value(inventory.cpu.cache_line_bytes)},
                {"microcode", protocol::json::Value(inventory.cpu.microcode)},
                {"model", protocol::json::Value(inventory.cpu.model)},
                {"pointer_atomic_lock_free",
                 protocol::json::Value(inventory.cpu.pointer_atomic_lock_free)},
                {"stepping", protocol::json::Value(inventory.cpu.stepping)},
                {"vendor", protocol::json::Value(inventory.cpu.vendor)},
            })},
           {"logical_cpus", protocol::json::Value(std::move(logical_cpus))},
           {"numa_nodes", protocol::json::Value(std::move(numa_nodes))},
           {"observations", protocol::json::Value(std::move(observations))},
           {"pci_devices", protocol::json::Value(std::move(pci_devices))},
           {"snapshot_id", protocol::json::Value(inventory.snapshot_id)},
           {"software",
            protocol::json::Value(JsonObject{
                {"compiler", protocol::json::Value(inventory.software.compiler)},
                {"kernel", protocol::json::Value(inventory.software.kernel)},
                {"language_standard",
                 protocol::json::Value(inventory.software.language_standard)},
                {"operating_system",
                 protocol::json::Value(inventory.software.operating_system)},
                {"standard_library",
                 protocol::json::Value(inventory.software.standard_library)},
            })},
       })},
      {"libraries", protocol::json::Value(std::move(libraries))},
      {"link_mode", protocol::json::Value(context.link_mode)},
      {"manifest_id", protocol::json::Value(context.manifest_id)},
      {"manifest_sha256", protocol::json::Value(std::string(64U, '0'))},
      {"platform_id", protocol::json::Value(context.platform_id)},
      {"protocol_version",
       protocol::json::Value(std::string(protocol::kProtocolVersion))},
      {"request",
       protocol::json::Value(JsonObject{
           {"controls", protocol::json::Value(std::move(controls))},
           {"hardware_prefetch_state",
            protocol::json::Value(std::string(
                request.hardware_prefetch_state == protocol::RequestedHardwareState::h0
                    ? "H0"
                    : "H1"))},
           {"inventory_snapshot_id",
            protocol::json::Value(request.inventory_snapshot_id)},
           {"placement",
            protocol::json::Value(JsonObject{
                {"consumer_cpu", uint_value(request.placement.consumer_cpu)},
                {"consumer_private_memory_policy",
                 protocol::json::Value(std::string(
                     to_string(request.placement.consumer_private_memory_policy)))},
                {"consumer_private_nodes",
                 uint_array(request.placement.consumer_private_nodes)},
                {"page_policy", protocol::json::Value(std::string(
                                    to_string(request.placement.page_policy)))},
                {"placement",
                 protocol::json::Value(std::string(request.placement.placement ==
                                                           protocol::Placement::near
                                                       ? "NEAR"
                                                       : "FAR"))},
                {"producer_cpu", uint_value(request.placement.producer_cpu)},
                {"producer_private_memory_policy",
                 protocol::json::Value(std::string(
                     to_string(request.placement.producer_private_memory_policy)))},
                {"producer_private_nodes",
                 uint_array(request.placement.producer_private_nodes)},
                {"requested_page_bytes",
                 uint_value(request.placement.requested_page_bytes)},
                {"shared_memory_nodes",
                 uint_array(request.placement.shared_memory_nodes)},
                {"shared_memory_policy", protocol::json::Value(std::string(to_string(
                                             request.placement.shared_memory_policy)))},
            })},
           {"request_id", protocol::json::Value(request.request_id)},
           {"state_epoch", uint_value(request.state_epoch)},
       })},
      {"restoration",
       protocol::json::Value(JsonObject{
           {"attempted", protocol::json::Value(apply_report.restoration.attempted)},
           {"complete", protocol::json::Value(apply_report.restoration.complete)},
           {"steps", protocol::json::Value(std::move(restoration_steps))},
       })},
      {"schema_version",
       protocol::json::Value(std::string(protocol::kProtocolVersion))},
      {"verification",
       protocol::json::Value(JsonObject{
           {"all_mandatory_match",
            protocol::json::Value(verification_report.all_mandatory_match)},
           {"complete", protocol::json::Value(verification_report.complete)},
           {"observations",
            protocol::json::Value(std::move(verification_observations))},
           {"steps", protocol::json::Value(std::move(verification_steps))},
       })},
  };
  const auto zeroed = protocol::json::canonicalize(protocol::json::Value(root));
  if (!zeroed) {
    return Result<ManifestArtifact>::failure(
        make_error(ErrorCategory::manifest_incomplete, "$manifest",
                   "PLT-MANIFEST-CANONICAL", "canonical serialization failed"));
  }
  const auto record_hash = sha256_text(zeroed.value());
  root["manifest_sha256"] = protocol::json::Value(record_hash);
  const auto canonical = protocol::json::canonicalize(protocol::json::Value(root));
  if (!canonical) {
    return Result<ManifestArtifact>::failure(
        make_error(ErrorCategory::manifest_incomplete, "$manifest",
                   "PLT-MANIFEST-CANONICAL", "canonical serialization failed"));
  }
  return Result<ManifestArtifact>::success(
      ManifestArtifact{canonical.value(), record_hash, eligible});
}

auto emit_protocol_platform_record(const ProtocolPlatformContext& context,
                                   const PlatformInventory& inventory)
    -> Result<ProtocolPlatformArtifact> {
  std::vector<Error> errors;
  require_text(errors, context.platform_id, "$platform/platform_id", "PLT-PROTOCOL-ID");
  require_text(errors, context.memory_population, "$platform/memory/population",
               "PLT-PROTOCOL-MEMORY");
  require_text(errors, context.residency_verification_method,
               "$platform/memory/residency_verification_method",
               "PLT-PROTOCOL-RESIDENCY");
  require_text(errors, context.link_mode, "$platform/software/link_mode",
               "PLT-PROTOCOL-LINK");
  require_text(errors, context.clock.source, "$platform/clock/source",
               "PLT-PROTOCOL-CLOCK");
  require_text(errors, context.clock.time_unit, "$platform/clock/time_unit",
               "PLT-PROTOCOL-CLOCK");
  require_text(errors, context.clock.conversion_record_id,
               "$platform/clock/conversion_record_id", "PLT-PROTOCOL-CLOCK");
  require_text(errors, context.clock.serialization_record_id,
               "$platform/clock/serialization_record_id", "PLT-PROTOCOL-CLOCK");
  require_text(errors, context.clock.acceptance_record_id,
               "$platform/clock/acceptance_record_id", "PLT-PROTOCOL-CLOCK");

  const auto* near_left = find_cpu(inventory, context.near_core_pair[0]);
  const auto* near_right = find_cpu(inventory, context.near_core_pair[1]);
  if (near_left == nullptr || near_right == nullptr ||
      near_left->logical_id == near_right->logical_id ||
      near_left->numa_node != near_right->numa_node ||
      (near_left->package_id == near_right->package_id &&
       near_left->core_id == near_right->core_id) ||
      !same_last_level_cache(inventory, *near_left, *near_right)) {
    errors.push_back(
        make_error(ErrorCategory::impossible_placement,
                   "$platform/topology/near_core_pair", "PLT-PROTOCOL-NEAR",
                   "near pair must be distinct physical cores in one NUMA/LLC domain"));
  }
  const auto* far_left = find_cpu(inventory, context.far_core_pair[0]);
  const auto* far_right = find_cpu(inventory, context.far_core_pair[1]);
  if (far_left == nullptr || far_right == nullptr ||
      far_left->logical_id == far_right->logical_id ||
      far_left->numa_node == far_right->numa_node ||
      (far_left->package_id == far_right->package_id &&
       far_left->core_id == far_right->core_id)) {
    errors.push_back(
        make_error(ErrorCategory::impossible_placement,
                   "$platform/topology/far_core_pair", "PLT-PROTOCOL-FAR",
                   "far pair must be distinct physical cores in different NUMA nodes"));
  }

  bool saw_h0 = false;
  bool saw_h1 = false;
  for (std::size_t index = 0U; index < context.hardware_prefetch_states.size();
       ++index) {
    const auto& state = context.hardware_prefetch_states[index];
    saw_h0 = saw_h0 || state.requested == protocol::RequestedHardwareState::h0;
    saw_h1 = saw_h1 || state.requested == protocol::RequestedHardwareState::h1;
    const auto path = "$platform/hardware_prefetch_states/" + std::to_string(index);
    if (state.requested == protocol::RequestedHardwareState::not_applicable ||
        state.verified == protocol::VerifiedHardwareState::not_applicable ||
        state.readback_artifact_id.empty() ||
        state.behavioral_probe_artifact_id.empty() ||
        state.privileged_authority_id.empty()) {
      errors.push_back(make_error(
          ErrorCategory::manifest_incomplete, path, "PLT-PROTOCOL-HWPF",
          "each H0/H1 state needs explicit verification disposition and evidence IDs"));
    }
  }
  if (!saw_h0 || !saw_h1) {
    errors.push_back(make_error(
        ErrorCategory::manifest_incomplete, "$platform/hardware_prefetch_states",
        "PLT-PROTOCOL-HWPF-PAIR", "platform record requires one H0 and one H1 state"));
  }
  if (inventory.cpu.vendor.empty() || inventory.cpu.model.empty() ||
      inventory.cpu.stepping.empty() || inventory.cpu.microcode.empty() ||
      inventory.logical_cpus.size() < 2U || inventory.cache_domains.empty() ||
      inventory.numa_nodes.empty()) {
    errors.push_back(make_error(ErrorCategory::manifest_incomplete,
                                "$platform/inventory", "PLT-PROTOCOL-INVENTORY",
                                "imported platform fields require complete inventory"));
  }
  if (!errors.empty()) {
    return Result<ProtocolPlatformArtifact>::failure(std::move(errors));
  }

  std::set<std::pair<std::uint32_t, std::uint32_t>> physical_cores;
  std::set<std::uint32_t> packages;
  bool smt_enabled = false;
  for (const auto& cpu : inventory.logical_cpus) {
    physical_cores.emplace(cpu.package_id, cpu.core_id);
    packages.insert(cpu.package_id);
    smt_enabled = smt_enabled || cpu.thread_siblings.size() > 1U;
  }
  std::vector<std::string> cache_ids;
  cache_ids.reserve(inventory.cache_domains.size());
  for (const auto& cache : inventory.cache_domains) {
    cache_ids.push_back(cache.domain_id);
  }

  const auto verified_text = [](protocol::VerifiedHardwareState state) {
    switch (state) {
    case protocol::VerifiedHardwareState::verified_default:
      return "VERIFIED_DEFAULT";
    case protocol::VerifiedHardwareState::verified_changed:
      return "VERIFIED_CHANGED";
    case protocol::VerifiedHardwareState::verification_failed:
      return "VERIFICATION_FAILED";
    case protocol::VerifiedHardwareState::unknown:
      return "UNKNOWN";
    case protocol::VerifiedHardwareState::not_applicable:
      break;
    }
    return "UNKNOWN";
  };
  JsonArray hardware_states;
  for (const auto& state : context.hardware_prefetch_states) {
    hardware_states.emplace_back(JsonObject{
        {"behavioral_probe_artifact_id",
         protocol::json::Value(state.behavioral_probe_artifact_id)},
        {"privileged_authority_id",
         protocol::json::Value(state.privileged_authority_id)},
        {"readback_artifact_id", protocol::json::Value(state.readback_artifact_id)},
        {"requested",
         protocol::json::Value(std::string(
             state.requested == protocol::RequestedHardwareState::h0 ? "H0" : "H1"))},
        {"verified", protocol::json::Value(std::string(verified_text(state.verified)))},
    });
  }
  const auto pair_value = [](const std::array<std::uint32_t, 2>& pair) {
    return protocol::json::Value(JsonArray{uint_value(pair[0]), uint_value(pair[1])});
  };
  JsonObject root{
      {"clock", protocol::json::Value(JsonObject{
                    {"acceptance_record_id",
                     protocol::json::Value(context.clock.acceptance_record_id)},
                    {"conversion_record_id",
                     protocol::json::Value(context.clock.conversion_record_id)},
                    {"serialization_record_id",
                     protocol::json::Value(context.clock.serialization_record_id)},
                    {"source", protocol::json::Value(context.clock.source)},
                    {"time_unit", protocol::json::Value(context.clock.time_unit)},
                })},
      {"cpu",
       protocol::json::Value(JsonObject{
           {"atomic_alignment_bytes", uint_value(inventory.cpu.atomic_alignment_bytes)},
           {"atomic_width_bits", uint_value(inventory.cpu.atomic_width_bits)},
           {"cache_line_bytes", uint_value(inventory.cpu.cache_line_bytes)},
           {"microcode", protocol::json::Value(inventory.cpu.microcode)},
           {"model", protocol::json::Value(inventory.cpu.model)},
           {"stepping", protocol::json::Value(inventory.cpu.stepping)},
           {"vendor", protocol::json::Value(inventory.cpu.vendor)},
       })},
      {"hardware_prefetch_states", protocol::json::Value(std::move(hardware_states))},
      {"memory", protocol::json::Value(JsonObject{
                     {"base_page_bytes", uint_value(inventory.base_page_bytes)},
                     {"population", protocol::json::Value(context.memory_population)},
                     {"residency_verification_method",
                      protocol::json::Value(context.residency_verification_method)},
                 })},
      {"platform_id", protocol::json::Value(context.platform_id)},
      {"protocol_version",
       protocol::json::Value(std::string(protocol::kProtocolVersion))},
      {"record_sha256", protocol::json::Value(std::string(64U, '0'))},
      {"schema_version",
       protocol::json::Value(std::string(protocol::kProtocolVersion))},
      {"software", protocol::json::Value(JsonObject{
                       {"compiler", protocol::json::Value(inventory.software.compiler)},
                       {"flags", string_array(context.compiler_flags)},
                       {"kernel", protocol::json::Value(inventory.software.kernel)},
                       {"language_standard",
                        protocol::json::Value(inventory.software.language_standard)},
                       {"link_mode", protocol::json::Value(context.link_mode)},
                       {"operating_system",
                        protocol::json::Value(inventory.software.operating_system)},
                       {"standard_library",
                        protocol::json::Value(inventory.software.standard_library)},
                   })},
      {"topology", protocol::json::Value(JsonObject{
                       {"cache_domains", string_array(cache_ids)},
                       {"far_core_pair", pair_value(context.far_core_pair)},
                       {"near_core_pair", pair_value(context.near_core_pair)},
                       {"numa_nodes", uint_value(inventory.numa_nodes.size())},
                       {"physical_cores", uint_value(physical_cores.size())},
                       {"smt_enabled", protocol::json::Value(smt_enabled)},
                       {"sockets", uint_value(packages.size())},
                   })},
  };
  const auto zeroed = protocol::json::canonicalize(protocol::json::Value(root));
  if (!zeroed) {
    return Result<ProtocolPlatformArtifact>::failure(make_error(
        ErrorCategory::manifest_incomplete, "$platform", "PLT-PROTOCOL-CANONICAL",
        "canonical protocol-platform serialization failed"));
  }
  const auto record_hash = sha256_text(zeroed.value());
  root["record_sha256"] = protocol::json::Value(record_hash);
  const auto canonical = protocol::json::canonicalize(protocol::json::Value(root));
  if (!canonical) {
    return Result<ProtocolPlatformArtifact>::failure(make_error(
        ErrorCategory::manifest_incomplete, "$platform", "PLT-PROTOCOL-CANONICAL",
        "canonical protocol-platform serialization failed"));
  }
  const bool hardware_states_verified = std::all_of(
      context.hardware_prefetch_states.begin(), context.hardware_prefetch_states.end(),
      [](const HardwarePrefetchEvidence& state) {
        return (state.requested == protocol::RequestedHardwareState::h0 &&
                state.verified == protocol::VerifiedHardwareState::verified_default) ||
               (state.requested == protocol::RequestedHardwareState::h1 &&
                state.verified == protocol::VerifiedHardwareState::verified_changed);
      });
  return Result<ProtocolPlatformArtifact>::success(
      {canonical.value(), record_hash, hardware_states_verified});
}

} // namespace cpu_prefetch::platform
