#include <gtest/gtest.h>

#include "cpu_prefetch/platform/linux_inventory.hpp"
#include "cpu_prefetch/platform/platform.hpp"
#include "cpu_prefetch/protocol/json.hpp"

#include <algorithm>
#include <cstdint>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

using cpu_prefetch::platform::ApplyMode;
using cpu_prefetch::platform::BackendResult;
using cpu_prefetch::platform::Capability;
using cpu_prefetch::platform::CapabilityStatus;
using cpu_prefetch::platform::ControlActuator;
using cpu_prefetch::platform::ControlKind;
using cpu_prefetch::platform::ControlRequest;
using cpu_prefetch::platform::Error;
using cpu_prefetch::platform::ErrorCategory;
using cpu_prefetch::platform::LinuxSnapshot;
using cpu_prefetch::platform::ManifestContext;
using cpu_prefetch::platform::MemoryPolicy;
using cpu_prefetch::platform::PagePolicy;
using cpu_prefetch::platform::PlatformInventory;
using cpu_prefetch::platform::RequestedState;
using cpu_prefetch::platform::Result;
using cpu_prefetch::platform::StateObservation;
using cpu_prefetch::platform::StateVerifier;
using cpu_prefetch::protocol::Placement;
using cpu_prefetch::protocol::RequestedHardwareState;

LinuxSnapshot synthetic_snapshot() {
  LinuxSnapshot snapshot{"snapshot-1", "2026-08-21T00:00:00Z", "fixture-kernel", {}};
  auto& files = snapshot.files;
  files["/proc/cpuinfo"] = "processor : 0\n"
                           "vendor_id : GenuineFixture\n"
                           "model name : Fixture CPU\n"
                           "stepping : 7\n"
                           "microcode : 0x42\n\n";
  files["/proc/meminfo"] = "MemTotal: 1048576 kB\nHugePages_Total: 0\n";
  files["/proc/cmdline"] = "root=fixture ro";
  files["/proc/irq/default_smp_affinity"] = "f";
  files["runtime/base_page_bytes"] = "4096";
  files["/sys/devices/system/cpu/online"] = "0-3";
  files["/sys/devices/system/node/node0/cpulist"] = "0-1";
  files["/sys/devices/system/node/node1/cpulist"] = "2-3";
  files["/sys/devices/system/cpu/smt/active"] = "0";
  files["/sys/devices/system/cpu/smt/control"] = "off";
  files["/sys/devices/system/cpu/isolated"] = "0-3";
  files["/sys/devices/system/cpu/nohz_full"] = "0-3";
  files["/sys/devices/system/cpu/cpuidle/current_driver"] = "none";
  files["/sys/devices/system/cpu/cpuidle/current_governor_ro"] = "none";
  files["/sys/devices/system/cpu/cpufreq/policy0/scaling_governor"] = "performance";
  files["/sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq"] = "3000000";
  files["/sys/devices/system/cpu/cpufreq/boost"] = "0";
  files["/sys/devices/system/clocksource/clocksource0/current_clocksource"] = "tsc";
  files["/sys/kernel/mm/transparent_hugepage/enabled"] = "[never] madvise always";
  files["/sys/class/dmi/id/bios_vendor"] = "Fixture Firmware";
  files["/sys/class/dmi/id/bios_version"] = "1.0";
  files["/sys/class/dmi/id/bios_date"] = "08/21/2026";
  files["/sys/class/dmi/id/product_name"] = "Fixture Stand";

  for (std::uint32_t cpu = 0U; cpu < 4U; ++cpu) {
    const auto root = "/sys/devices/system/cpu/cpu" + std::to_string(cpu);
    files[root + "/topology/core_id"] = std::to_string(cpu % 2U);
    files[root + "/topology/physical_package_id"] = std::to_string(cpu / 2U);
    files[root + "/topology/thread_siblings_list"] = std::to_string(cpu);
    files[root + "/cache/index3/level"] = "3";
    files[root + "/cache/index3/type"] = "Unified";
    files[root + "/cache/index3/shared_cpu_list"] = cpu < 2U ? "0-1" : "2-3";
    files[root + "/cache/index3/size"] = "8M";
    files[root + "/cache/index3/coherency_line_size"] = "64";
  }
  files["/sys/bus/pci/devices/0000:00:18.0/vendor"] = "0x1022";
  files["/sys/bus/pci/devices/0000:00:18.0/device"] = "0xfixture";
  files["/sys/bus/pci/devices/0000:00:18.0/class"] = "0x060000";
  files["/sys/bus/pci/devices/0000:00:18.0/numa_node"] = "0";
  files["/sys/bus/pci/devices/0000:00:18.0/local_cpulist"] = "0-1";
  return snapshot;
}

PlatformInventory inventory() {
  auto parsed = cpu_prefetch::platform::parse_linux_snapshot(synthetic_snapshot());
  if (!parsed) {
    throw std::runtime_error(parsed.errors().front().message);
  }
  return std::move(parsed).value();
}

ControlRequest mutating_control(std::string id, ControlKind kind, std::string value) {
  return {std::move(id),  kind, "fixture-target",    std::move(value),
          true,           true, "platform-operator", "fake-actuator",
          "fake-readback"};
}

ControlRequest observation_control(std::string id, ControlKind kind,
                                   std::string value) {
  return {std::move(id),  kind, "fixture-target", std::move(value), true, false, {}, {},
          "fake-readback"};
}

RequestedState near_request() {
  return {
      "request-1",
      "snapshot-1",
      7U,
      {Placement::near,
       0U,
       1U,
       MemoryPolicy::bind_producer_node,
       {0U},
       MemoryPolicy::bind_worker_local,
       {0U},
       MemoryPolicy::bind_worker_local,
       {0U},
       PagePolicy::verified_base_pages,
       4096U},
      RequestedHardwareState::h1,
      {mutating_control("producer-affinity", ControlKind::producer_affinity, "cpu=0"),
       mutating_control("hardware-prefetch", ControlKind::hardware_prefetch,
                        "H1-fixture-map")}};
}

RequestedState complete_request() {
  auto request = near_request();
  request.controls.push_back(
      mutating_control("consumer-affinity", ControlKind::consumer_affinity, "cpu=1"));
  request.controls.push_back(observation_control(
      "producer-actual", ControlKind::producer_actual_cpu, "cpu=0"));
  request.controls.push_back(observation_control(
      "consumer-actual", ControlKind::consumer_actual_cpu, "cpu=1"));
  request.controls.push_back(mutating_control(
      "shared-memory", ControlKind::shared_memory_policy, "bind-node=0"));
  request.controls.push_back(mutating_control(
      "producer-private", ControlKind::producer_private_memory_policy, "bind-node=0"));
  request.controls.push_back(mutating_control(
      "consumer-private", ControlKind::consumer_private_memory_policy, "bind-node=0"));
  request.controls.push_back(observation_control(
      "shared-residency", ControlKind::shared_page_residency, "node=0"));
  request.controls.push_back(observation_control("private-residency",
                                                 ControlKind::private_page_residency,
                                                 "producer=0,consumer=0"));
  request.controls.push_back(
      mutating_control("base-pages", ControlKind::base_page_state, "4096"));
  request.controls.push_back(
      observation_control("huge-pages", ControlKind::huge_page_state, "not-used"));
  request.controls.push_back(
      mutating_control("governor", ControlKind::governor, "performance"));
  request.controls.push_back(
      mutating_control("frequency", ControlKind::fixed_frequency, "fixture-fixed"));
  request.controls.push_back(
      mutating_control("turbo", ControlKind::turbo, "fixture-off"));
  request.controls.push_back(
      mutating_control("c-state", ControlKind::c_state, "fixture-state"));
  request.controls.push_back(mutating_control("smt", ControlKind::smt, "fixture-off"));
  request.controls.push_back(mutating_control(
      "interrupts", ControlKind::interrupt_routing, "fixture-routing"));
  request.controls.push_back(
      mutating_control("isolation", ControlKind::cpu_isolation, "fixture-isolation"));
  request.controls.push_back(
      observation_control("clock-source", ControlKind::clock_source, "tsc"));
  request.controls.push_back(
      observation_control("microcode", ControlKind::microcode, "0x42"));
  request.controls.push_back(
      observation_control("firmware", ControlKind::firmware, "fixture-firmware"));
  request.controls.push_back(
      observation_control("compiler", ControlKind::compiler, "fixture-compiler"));
  request.controls.push_back(
      observation_control("binary", ControlKind::binary, std::string(64U, '1')));
  request.controls.push_back(
      observation_control("library", ControlKind::library, "openssl=3.fixture"));
  return request;
}

std::vector<Capability> accepted_capabilities(const PlatformInventory& value) {
  auto capabilities = cpu_prefetch::platform::detect_capabilities(value);
  const auto hardware_prefetch = std::find_if(
      capabilities.begin(), capabilities.end(), [](const Capability& capability) {
        return capability.kind == ControlKind::hardware_prefetch;
      });
  hardware_prefetch->status = CapabilityStatus::external_authority_required;
  hardware_prefetch->detection_mechanism = "accepted-fixture-map";
  hardware_prefetch->evidence = "fixture manual and authority evidence";
  return capabilities;
}

std::vector<StateObservation> prior_state(const RequestedState& request) {
  std::vector<StateObservation> output;
  output.reserve(request.controls.size());
  for (const auto& control : request.controls) {
    output.push_back({control.control_id, request.inventory_snapshot_id,
                      request.state_epoch, "prior-" + control.requested_value,
                      "prior-" + control.control_id, "independent-pre-readback"});
  }
  return output;
}

class FakeActuator final : public ControlActuator {
public:
  std::set<std::string, std::less<>> apply_failures;
  std::set<std::string, std::less<>> privilege_failures;
  std::set<std::string, std::less<>> restore_failures;
  std::vector<std::string> applied;
  std::vector<std::string> restored;

  [[nodiscard]] auto backend_id() const -> std::string_view override {
    return "fake-actuator-backend";
  }

  [[nodiscard]] auto apply(const ControlRequest& request) -> BackendResult override {
    applied.push_back(request.control_id);
    const bool privilege_denied = privilege_failures.contains(request.control_id);
    const bool success =
        !apply_failures.contains(request.control_id) && !privilege_denied;
    return {success, "apply-" + request.control_id,
            success ? "fixture applied" : "fixture apply failure",
            privilege_denied ? std::optional{ErrorCategory::privilege_denied}
                             : std::nullopt};
  }

  [[nodiscard]] auto restore(const ControlRequest& request,
                             const StateObservation& prior) -> BackendResult override {
    restored.push_back(request.control_id);
    const bool success = !restore_failures.contains(request.control_id) &&
                         prior.observed_value.has_value();
    return {success, "restore-" + request.control_id,
            success ? "fixture restored" : "fixture restore failure", std::nullopt};
  }
};

class FakeVerifier final : public StateVerifier {
public:
  std::string snapshot_id{"snapshot-1"};
  std::uint64_t state_epoch{7U};
  std::string mechanism{"fake-readback"};
  std::map<std::string, std::optional<std::string>, std::less<>> values;
  std::set<std::string, std::less<>> failures;

  [[nodiscard]] auto backend_id() const -> std::string_view override {
    return "fake-independent-verifier";
  }

  [[nodiscard]] auto readback(const ControlRequest& request)
      -> Result<StateObservation> override {
    if (failures.contains(request.control_id)) {
      return Result<StateObservation>::failure(
          Error{ErrorCategory::missing_evidence, "$fake/readback", "PLT-FAKE-READBACK",
                "scripted readback failure"});
    }
    const auto position = values.find(request.control_id);
    const auto value = position == values.end()
                           ? std::optional<std::string>{request.requested_value}
                           : position->second;
    return Result<StateObservation>::success(
        {request.control_id, snapshot_id, state_epoch, value,
         "verify-" + request.control_id, mechanism});
  }
};

TEST(LinuxTopology, ParsesCpuListsTopologyCachesNumaAndPci) {
  const auto cpus = cpu_prefetch::platform::parse_cpu_list("0-2,5,7-8", "$cpus");
  ASSERT_TRUE(cpus);
  EXPECT_EQ(cpus.value(), (std::vector<std::uint32_t>{0U, 1U, 2U, 5U, 7U, 8U}));
  EXPECT_FALSE(cpu_prefetch::platform::parse_cpu_list("2-1", "$cpus"));
  EXPECT_FALSE(cpu_prefetch::platform::parse_cpu_list("0,0", "$cpus"));

  const auto value = inventory();
  EXPECT_EQ(value.logical_cpus.size(), 4U);
  EXPECT_EQ(value.numa_nodes.size(), 2U);
  EXPECT_EQ(value.cache_domains.size(), 2U);
  EXPECT_EQ(value.pci_devices.size(), 1U);
  EXPECT_EQ(value.cpu.cache_line_bytes, 64U);
  EXPECT_EQ(value.base_page_bytes, 4096U);
  EXPECT_TRUE(value.cache_domains.front().last_level);
}

TEST(PlacementValidation, AcceptsExactNearAndFarAndRejectsImpossiblePairs) {
  const auto value = inventory();
  const auto capabilities = accepted_capabilities(value);
  auto request = near_request();
  EXPECT_TRUE(
      cpu_prefetch::platform::validate_requested_state(value, capabilities, request)
          .empty());

  request.placement.placement = Placement::far;
  request.placement.consumer_cpu = 2U;
  request.placement.consumer_private_nodes = {1U};
  EXPECT_TRUE(
      cpu_prefetch::platform::validate_requested_state(value, capabilities, request)
          .empty());

  request.placement.consumer_cpu = 99U;
  const auto impossible =
      cpu_prefetch::platform::validate_requested_state(value, capabilities, request);
  EXPECT_TRUE(std::any_of(impossible.begin(), impossible.end(), [](const Error& error) {
    return error.category == ErrorCategory::impossible_placement;
  }));
}

TEST(PlacementValidation, RejectsSiblingsNumaMismatchAndStageCPolicies) {
  auto value = inventory();
  const auto capabilities = accepted_capabilities(value);
  auto request = near_request();
  value.logical_cpus[1].core_id = value.logical_cpus[0].core_id;
  value.logical_cpus[1].package_id = value.logical_cpus[0].package_id;
  const auto sibling =
      cpu_prefetch::platform::validate_requested_state(value, capabilities, request);
  EXPECT_TRUE(std::any_of(sibling.begin(), sibling.end(), [](const Error& error) {
    return error.category == ErrorCategory::sibling_conflict;
  }));

  value = inventory();
  request.placement.placement = Placement::far;
  const auto numa =
      cpu_prefetch::platform::validate_requested_state(value, capabilities, request);
  EXPECT_TRUE(std::any_of(numa.begin(), numa.end(), [](const Error& error) {
    return error.category == ErrorCategory::numa_mismatch;
  }));

  request = near_request();
  request.placement.shared_memory_policy = MemoryPolicy::interleave;
  request.placement.page_policy = PagePolicy::transparent_huge_pages;
  const auto stage_c =
      cpu_prefetch::platform::validate_requested_state(value, capabilities, request);
  EXPECT_GE(stage_c.size(), 2U);
}

TEST(CapabilityValidation, FailsClosedForUnresolvedControlAndMissingAuthority) {
  const auto value = inventory();
  auto request = near_request();
  const auto detected = cpu_prefetch::platform::detect_capabilities(value);
  const auto unresolved =
      cpu_prefetch::platform::validate_requested_state(value, detected, request);
  EXPECT_TRUE(std::any_of(unresolved.begin(), unresolved.end(), [](const Error& error) {
    return error.category == ErrorCategory::unsupported_control;
  }));

  auto capabilities = accepted_capabilities(value);
  request.controls.front().authority_id.clear();
  const auto no_authority =
      cpu_prefetch::platform::validate_requested_state(value, capabilities, request);
  EXPECT_TRUE(
      std::any_of(no_authority.begin(), no_authority.end(), [](const Error& error) {
        return error.category == ErrorCategory::privilege_denied;
      }));
}

TEST(ControlFlow, DryRunNeverInvokesActuatorAndNeverClaimsVerification) {
  const auto request = near_request();
  FakeActuator actuator;
  const auto report = cpu_prefetch::platform::apply_requested_state(
      request, prior_state(request), ApplyMode::dry_run, &actuator);
  EXPECT_TRUE(report.complete);
  EXPECT_TRUE(actuator.applied.empty());
  EXPECT_TRUE(actuator.restored.empty());
  EXPECT_TRUE(
      std::all_of(report.steps.begin(), report.steps.end(), [](const auto& step) {
        return step.status == cpu_prefetch::platform::StepStatus::planned;
      }));
}

TEST(ControlFlow, PrivilegeAndPartialApplyFailuresRestoreAndRemainExplicit) {
  auto request = near_request();
  request.controls.insert(
      request.controls.begin() + 1,
      mutating_control("consumer-affinity", ControlKind::consumer_affinity, "cpu=1"));
  FakeActuator denied_actuator;
  denied_actuator.privilege_failures.insert("producer-affinity");
  const auto denied = cpu_prefetch::platform::apply_requested_state(
      request, prior_state(request), ApplyMode::authorized_apply, &denied_actuator);
  EXPECT_FALSE(denied.complete);
  EXPECT_TRUE(
      std::any_of(denied.errors.begin(), denied.errors.end(), [](const Error& error) {
        return error.category == ErrorCategory::privilege_denied;
      }));

  FakeActuator actuator;
  actuator.apply_failures.insert("hardware-prefetch");
  actuator.restore_failures.insert("producer-affinity");
  const auto report = cpu_prefetch::platform::apply_requested_state(
      request, prior_state(request), ApplyMode::authorized_apply, &actuator);
  EXPECT_FALSE(report.complete);
  EXPECT_TRUE(report.restoration.attempted);
  EXPECT_FALSE(report.restoration.complete);
  EXPECT_EQ(actuator.restored,
            (std::vector<std::string>{"consumer-affinity", "producer-affinity"}));
  EXPECT_TRUE(std::any_of(report.restoration.errors.begin(),
                          report.restoration.errors.end(), [](const Error& error) {
                            return error.category == ErrorCategory::restoration_failure;
                          }));
}

TEST(ControlFlow, ApplySuccessIsNotVerificationAndMismatchFailsClosed) {
  const auto request = near_request();
  FakeActuator actuator;
  const auto applied = cpu_prefetch::platform::apply_requested_state(
      request, prior_state(request), ApplyMode::authorized_apply, &actuator);
  ASSERT_TRUE(applied.complete);

  FakeVerifier verifier;
  verifier.values["hardware-prefetch"] = "different-state";
  const auto verified =
      cpu_prefetch::platform::verify_requested_state(request, verifier);
  EXPECT_FALSE(verified.complete);
  EXPECT_FALSE(verified.all_mandatory_match);
  EXPECT_TRUE(std::any_of(
      verified.errors.begin(), verified.errors.end(), [](const Error& error) {
        return error.category == ErrorCategory::verification_mismatch;
      }));
}

TEST(ControlFlow, RejectsStaleAndNonIndependentReadback) {
  const auto request = near_request();
  FakeVerifier verifier;
  verifier.state_epoch = request.state_epoch - 1U;
  auto report = cpu_prefetch::platform::verify_requested_state(request, verifier);
  EXPECT_TRUE(
      std::any_of(report.errors.begin(), report.errors.end(), [](const Error& error) {
        return error.category == ErrorCategory::stale_state;
      }));

  verifier.state_epoch = request.state_epoch;
  verifier.mechanism = "fake-actuator";
  report = cpu_prefetch::platform::verify_requested_state(request, verifier);
  EXPECT_TRUE(
      std::any_of(report.errors.begin(), report.errors.end(), [](const Error& error) {
        return error.category == ErrorCategory::verification_mismatch;
      }));
}

TEST(Manifest, IsCanonicalDeterministicCompleteAndHonestAboutEligibility) {
  const auto value = inventory();
  const auto capabilities = accepted_capabilities(value);
  const auto request = complete_request();
  FakeActuator actuator;
  const auto applied = cpu_prefetch::platform::apply_requested_state(
      request, prior_state(request), ApplyMode::authorized_apply, &actuator);
  FakeVerifier verifier;
  const auto verified =
      cpu_prefetch::platform::verify_requested_state(request, verifier);
  const ManifestContext context{"platform-fixture",
                                "manifest-fixture",
                                "build-fixture",
                                std::string(64U, '1'),
                                {"-O2"},
                                "dynamic",
                                {{"openssl", "3.fixture", std::string(64U, '2')}}};
  const auto first = cpu_prefetch::platform::emit_manifest(context, value, capabilities,
                                                           request, applied, verified);
  ASSERT_TRUE(first);
  EXPECT_TRUE(first.value().eligible);
  EXPECT_EQ(first.value().sha256.size(), 64U);
  const auto parsed = cpu_prefetch::protocol::json::parse(first.value().canonical_json);
  ASSERT_TRUE(parsed);
  const auto canonical = cpu_prefetch::protocol::json::canonicalize(parsed.value());
  ASSERT_TRUE(canonical);
  EXPECT_EQ(canonical.value(), first.value().canonical_json);

  const auto second = cpu_prefetch::platform::emit_manifest(
      context, value, capabilities, request, applied, verified);
  ASSERT_TRUE(second);
  EXPECT_EQ(second.value().canonical_json, first.value().canonical_json);

  auto incomplete_context = context;
  incomplete_context.libraries.clear();
  EXPECT_FALSE(cpu_prefetch::platform::emit_manifest(
      incomplete_context, value, capabilities, request, applied, verified));
}

TEST(Manifest, RetainsPartialFailureWithoutClaimingEligibility) {
  const auto value = inventory();
  const auto capabilities = accepted_capabilities(value);
  const auto request = complete_request();
  FakeActuator actuator;
  const auto dry_run = cpu_prefetch::platform::apply_requested_state(
      request, prior_state(request), ApplyMode::dry_run, &actuator);
  FakeVerifier verifier;
  verifier.failures.insert("hardware-prefetch");
  const auto verified =
      cpu_prefetch::platform::verify_requested_state(request, verifier);
  const ManifestContext context{"platform-fixture",
                                "manifest-failure",
                                "build-fixture",
                                std::string(64U, '1'),
                                {},
                                "dynamic",
                                {{"openssl", "3.fixture", std::string(64U, '2')}}};
  const auto manifest = cpu_prefetch::platform::emit_manifest(
      context, value, capabilities, request, dry_run, verified);
  ASSERT_TRUE(manifest);
  EXPECT_FALSE(manifest.value().eligible);
  EXPECT_NE(manifest.value().canonical_json.find("MISSING_EVIDENCE"),
            std::string::npos);
}

TEST(Manifest, EmitsExactImportedPlatformSchemaWithoutInventingStandValues) {
  const auto value = inventory();
  const cpu_prefetch::platform::ProtocolPlatformContext context{
      "platform-fixture",
      {0U, 1U},
      {0U, 2U},
      "fixture-memory-population-record",
      "fixture-move-pages-and-smaps-record",
      {"-O2"},
      "dynamic",
      {"LINUX-CLOCK-MONOTONIC-RAW-VDSO-PS-v1", "ps", "conversion-record",
       "serialization-record", "acceptance-record"},
      {{{RequestedHardwareState::h0,
         cpu_prefetch::protocol::VerifiedHardwareState::verified_default, "h0-readback",
         "h0-probe", "platform-operator"},
        {RequestedHardwareState::h1,
         cpu_prefetch::protocol::VerifiedHardwareState::verified_changed, "h1-readback",
         "h1-probe", "platform-operator"}}}};
  const auto artifact =
      cpu_prefetch::platform::emit_protocol_platform_record(context, value);
  ASSERT_TRUE(artifact);
  EXPECT_TRUE(artifact.value().hardware_states_verified);
  EXPECT_EQ(artifact.value().record_sha256.size(), 64U);
  const auto loaded = cpu_prefetch::protocol::load_document(
      cpu_prefetch::protocol::DocumentKind::platform, artifact.value().canonical_json);
  ASSERT_TRUE(loaded) << loaded.errors().front().path << ": "
                      << loaded.errors().front().message;
  EXPECT_TRUE(
      std::holds_alternative<cpu_prefetch::protocol::PlatformRecord>(loaded.value()));

  auto invalid_context = context;
  invalid_context.far_core_pair = {0U, 1U};
  EXPECT_FALSE(
      cpu_prefetch::platform::emit_protocol_platform_record(invalid_context, value));
}

TEST(LinuxInventory, DevelopmentHostReadOnlySmoke) {
  const cpu_prefetch::platform::LinuxInventoryProvider provider;
  const auto result =
      provider.collect("development-host-smoke", "2026-08-21T00:00:00Z");
  if (!result) {
    GTEST_SKIP() << "development namespace does not expose complete read-only sysfs: "
                 << result.errors().front().rule_id;
  }
  EXPECT_FALSE(result.value().logical_cpus.empty());
  EXPECT_FALSE(result.value().numa_nodes.empty());
  EXPECT_FALSE(result.value().cache_domains.empty());
}

} // namespace
