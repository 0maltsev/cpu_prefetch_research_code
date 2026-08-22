#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/platform/linux_inventory.hpp"
#include "cpu_prefetch/platform/platform.hpp"
#include "cpu_prefetch/protocol/json.hpp"

#include <algorithm>
#include <cstdint>
#include <exception>
#include <iostream>
#include <set>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace {

using cpu_prefetch::protocol::json::Value;
using JsonArray = Value::Array;
using JsonObject = Value::Object;

[[nodiscard]] auto unsigned_value(std::uint64_t value) -> Value {
  return Value(cpu_prefetch::protocol::json::Number{
      cpu_prefetch::protocol::json::Number::Kind::unsigned_integer,
      std::to_string(value), value});
}

[[nodiscard]] auto string_array(std::span<const std::string> values) -> Value {
  JsonArray output;
  output.reserve(values.size());
  for (const auto& value : values) {
    output.emplace_back(value);
  }
  return Value(std::move(output));
}

[[nodiscard]] auto
inventory_document(const cpu_prefetch::platform::PlatformInventory& inventory)
    -> Value {
  const auto repository = cpu_prefetch::foundation::repository_info();
  const auto capabilities = cpu_prefetch::platform::detect_capabilities(inventory);

  std::set<std::pair<std::uint32_t, std::uint32_t>> physical_cores;
  std::set<std::uint32_t> packages;
  for (const auto& cpu : inventory.logical_cpus) {
    physical_cores.emplace(cpu.package_id, cpu.core_id);
    packages.insert(cpu.package_id);
  }

  JsonArray capability_values;
  capability_values.reserve(capabilities.size());
  for (const auto& capability : capabilities) {
    capability_values.emplace_back(JsonObject{
        {"control_kind",
         Value(std::string(cpu_prefetch::platform::to_string(capability.kind)))},
        {"detection_mechanism", Value(capability.detection_mechanism)},
        {"evidence", Value(capability.evidence)},
        {"kernel_privilege_required", Value(capability.kernel_privilege_required)},
        {"status",
         Value(std::string(cpu_prefetch::platform::to_string(capability.status)))},
    });
  }

  JsonArray observation_values;
  observation_values.reserve(inventory.observations.size());
  for (const auto& observation : inventory.observations) {
    observation_values.emplace_back(JsonObject{
        {"name", Value(observation.name)},
        {"source", Value(observation.source)},
        {"value",
         observation.value.has_value() ? Value(*observation.value) : Value(nullptr)},
    });
  }

  const std::vector<std::string> blockers{
      "AUTHORIZED_PRODUCTION_MEASUREMENT_EXECUTABLE_ABSENT",
      "EXPLICIT_NEAR_AND_FAR_WORKER_PAIRS_UNSELECTED",
      "PRIVILEGED_CONTROL_AUTHORITY_AND_WHITELIST_ABSENT",
      "HARDWARE_PREFETCH_MAPPING_READBACK_AND_PROBES_ABSENT",
      "CLOCK_SELECTED_PAIR_QUALIFICATION_ABSENT",
      "ADDRESS_RESIDENCY_AND_STORAGE_DOMAIN_EVIDENCE_ABSENT",
      "CALIBRATION_AND_PILOT_FREEZE_INPUTS_ABSENT",
  };

  return Value(JsonObject{
      {"base_page_bytes", unsigned_value(inventory.base_page_bytes)},
      {"blockers", string_array(blockers)},
      {"build",
       Value(JsonObject{
           {"compiler", Value(std::string(repository.compiler))},
           {"protocol_version", Value(std::string(repository.protocol_version))},
           {"source_dirty", Value(repository.source_dirty)},
           {"source_revision", Value(std::string(repository.source_revision))},
           {"standard_library", Value(std::string(repository.standard_library))},
       })},
      {"capabilities", Value(std::move(capability_values))},
      {"captured_at_utc", Value(inventory.captured_at_utc)},
      {"cpu",
       Value(JsonObject{
           {"atomic_alignment_bytes",
            unsigned_value(inventory.cpu.atomic_alignment_bytes)},
           {"atomic_width_bits", unsigned_value(inventory.cpu.atomic_width_bits)},
           {"cache_line_bytes", unsigned_value(inventory.cpu.cache_line_bytes)},
           {"microcode", Value(inventory.cpu.microcode)},
           {"model", Value(inventory.cpu.model)},
           {"pointer_atomic_lock_free", Value(inventory.cpu.pointer_atomic_lock_free)},
           {"stepping", Value(inventory.cpu.stepping)},
           {"vendor", Value(inventory.cpu.vendor)},
       })},
      {"observations", Value(std::move(observation_values))},
      {"protocol_version", Value(std::string("2.0.0-pre.2"))},
      {"qualification_state", Value(std::string("INVENTORY_ONLY_NOT_QUALIFIED"))},
      {"schema_version", Value(std::string("cpu-prefetch-stand-preflight/1"))},
      {"snapshot_id", Value(inventory.snapshot_id)},
      {"topology",
       Value(JsonObject{
           {"cache_domains", unsigned_value(inventory.cache_domains.size())},
           {"logical_cpus", unsigned_value(inventory.logical_cpus.size())},
           {"numa_nodes", unsigned_value(inventory.numa_nodes.size())},
           {"packages", unsigned_value(packages.size())},
           {"pci_devices", unsigned_value(inventory.pci_devices.size())},
           {"physical_cores", unsigned_value(physical_cores.size())},
       })},
  });
}

void usage(std::ostream& output) {
  output
      << "Usage:\n"
      << "  cpu_prefetch_preflight --self-test\n"
      << "  cpu_prefetch_preflight --snapshot-id ID --captured-at-utc RFC3339_UTC\n\n"
      << "This tool is read-only. It never applies platform controls and its output "
         "is inventory evidence, not stand qualification.\n";
}

int run(int argc, char** argv) {
  if (argc == 2 && std::string_view(argv[1]) == "--self-test") {
    const auto repository = cpu_prefetch::foundation::repository_info();
    if (repository.protocol_version != "2.0.0-pre.2" ||
        repository.source_revision.empty() || repository.compiler.empty() ||
        repository.standard_library.empty()) {
      std::cerr << "stand-preflight-self-test: FAIL: incomplete build identity\n";
      return 1;
    }
    std::cout << "stand-preflight-self-test: PASS protocol="
              << repository.protocol_version
              << " qualification=INVENTORY_ONLY_NOT_QUALIFIED\n";
    return 0;
  }
  if (argc == 2 &&
      (std::string_view(argv[1]) == "--help" || std::string_view(argv[1]) == "-h")) {
    usage(std::cout);
    return 0;
  }
  if (argc != 5 || std::string_view(argv[1]) != "--snapshot-id" ||
      std::string_view(argv[3]) != "--captured-at-utc") {
    usage(std::cerr);
    return 2;
  }

  const cpu_prefetch::platform::LinuxInventoryProvider provider;
  const auto inventory = provider.collect(argv[2], argv[4]);
  if (!inventory) {
    for (const auto& error : inventory.errors()) {
      std::cerr << cpu_prefetch::platform::to_string(error.category) << ' '
                << error.rule_id << ' ' << error.path << ": " << error.message << '\n';
    }
    return 1;
  }
  const auto canonical =
      cpu_prefetch::protocol::json::canonicalize(inventory_document(inventory.value()));
  if (!canonical) {
    for (const auto& error : canonical.errors()) {
      std::cerr << cpu_prefetch::protocol::to_string(error.category) << ' '
                << error.rule_id << ' ' << error.path << ": " << error.message << '\n';
    }
    return 1;
  }
  std::cout << canonical.value() << '\n';
  return 0;
}

} // namespace

int main(int argc, char** argv) {
  try {
    return run(argc, argv);
  } catch (const std::exception& error) {
    std::cerr << "stand-preflight: FAIL: unhandled exception: " << error.what() << '\n';
  } catch (...) {
    std::cerr << "stand-preflight: FAIL: unhandled non-standard exception\n";
  }
  return 1;
}
