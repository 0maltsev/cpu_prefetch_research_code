#include "cpu_prefetch/qualification/q15_collectors.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

constexpr std::string_view kHash =
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

[[nodiscard]] auto identity() -> cpu_prefetch::runner::QualificationIdentity {
  return {"collector-artifact",
          "stand",
          "binding",
          "revision",
          std::string(kHash),
          "2026-08-24T00:00:00Z",
          cpu_prefetch::runner::kNearWorkerPair,
          {{"source", std::string(kHash)}}};
}

[[nodiscard]] auto backend_success(std::string evidence)
    -> cpu_prefetch::platform::BackendResult {
  return {true, std::move(evidence), "complete", std::nullopt};
}

class CapabilityPlatform final : public cpu_prefetch::platform::Q15PlatformOperations {
public:
  [[nodiscard]] auto bind_current_thread(std::uint32_t cpu)
      -> cpu_prefetch::platform::BackendResult override {
    current = cpu;
    observed.push_back(cpu);
    return backend_success("fake-affinity");
  }
  [[nodiscard]] auto singleton_affinity_matches(std::uint32_t cpu)
      -> cpu_prefetch::platform::Result<bool> override {
    return cpu_prefetch::platform::Result<bool>::success(cpu == current);
  }
  [[nodiscard]] auto current_cpu()
      -> cpu_prefetch::platform::Result<std::uint32_t> override {
    return cpu_prefetch::platform::Result<std::uint32_t>::success(current);
  }
  [[nodiscard]] auto map_private_anonymous(std::size_t)
      -> cpu_prefetch::platform::Result<std::byte*> override {
    return cpu_prefetch::platform::Result<std::byte*>::failure(
        {cpu_prefetch::platform::ErrorCategory::invalid_request, "$fake", "UNUSED",
         "unused"});
  }
  [[nodiscard]] auto bind_memory(const cpu_prefetch::platform::Q15MemoryBindingRequest&)
      -> cpu_prefetch::platform::BackendResult override {
    return {
        false, {}, "unused", cpu_prefetch::platform::ErrorCategory::invalid_request};
  }
  [[nodiscard]] auto disable_transparent_huge_pages(std::byte*, std::size_t)
      -> cpu_prefetch::platform::BackendResult override {
    return {
        false, {}, "unused", cpu_prefetch::platform::ErrorCategory::invalid_request};
  }
  [[nodiscard]] auto query_residency(std::byte*, std::size_t, std::size_t)
      -> cpu_prefetch::platform::Result<
          cpu_prefetch::platform::Q15ResidencySnapshot> override {
    return cpu_prefetch::platform::
        Result<cpu_prefetch::platform::Q15ResidencySnapshot>::failure(
            {cpu_prefetch::platform::ErrorCategory::invalid_request, "$fake", "UNUSED",
             "unused"});
  }
  [[nodiscard]] auto thread_faults() -> cpu_prefetch::platform::Result<
      cpu_prefetch::platform::Q15ThreadFaults> override {
    return cpu_prefetch::platform::Result<cpu_prefetch::platform::Q15ThreadFaults>::
        failure({cpu_prefetch::platform::ErrorCategory::invalid_request, "$fake",
                 "UNUSED", "unused"});
  }
  [[nodiscard]] auto monotonic_raw_nanoseconds()
      -> cpu_prefetch::platform::Result<std::uint64_t> override {
    return cpu_prefetch::platform::Result<std::uint64_t>::failure(
        {cpu_prefetch::platform::ErrorCategory::invalid_request, "$fake", "UNUSED",
         "unused"});
  }
  [[nodiscard]] auto unmap(std::byte*, std::size_t)
      -> cpu_prefetch::platform::BackendResult override {
    return {
        false, {}, "unused", cpu_prefetch::platform::ErrorCategory::invalid_request};
  }

  std::uint32_t current{0U};
  std::vector<std::uint32_t> observed;
};

class CapabilityBackend final
    : public cpu_prefetch::runner::CurrentCpuSoftwarePrefetchCapabilityBackend {
public:
  [[nodiscard]] auto observe() noexcept
      -> cpu_prefetch::runner::SoftwarePrefetchCapabilityObservation override {
    ++count;
    return {0x80000001U, 0x100U, true};
  }
  std::size_t count{0U};
};

class FakeMsr final : public cpu_prefetch::platform::HardwarePrefetchMsrBackend {
public:
  [[nodiscard]] auto backend_id() const -> std::string_view override {
    return "FAKE-INDEPENDENT-READER";
  }
  [[nodiscard]] auto read(std::uint32_t cpu)
      -> cpu_prefetch::platform::Result<std::uint64_t> override {
    reads.push_back(cpu);
    if (fail_cpu == cpu) {
      return cpu_prefetch::platform::Result<std::uint64_t>::failure(
          {cpu_prefetch::platform::ErrorCategory::io_error, "$fake", "FAKE-READ",
           "injected"});
    }
    return cpu_prefetch::platform::Result<std::uint64_t>::success(
        values[cpu == 0U ? 0U : (cpu == 1U ? 1U : 2U)]);
  }
  [[nodiscard]] auto write(std::uint32_t, std::uint64_t)
      -> cpu_prefetch::platform::BackendResult override {
    return {false,
            {},
            "read only",
            cpu_prefetch::platform::ErrorCategory::privilege_denied};
  }

  std::array<std::uint64_t, 3U> values{0x10U, 0x20U, 0x30U};
  std::uint32_t fail_cpu{99U};
  std::vector<std::uint32_t> reads;
};

[[nodiscard]] auto report(char digit) -> std::string {
  const std::string hash(64U, digit);
  return std::string("{") + R"("binary_sha256":")" + hash +
         R"(","missing_tools":[],"schema_version":"cpu-prefetch-runner-combined-codegen/2","software_prefetch_mapping_id":"X86-64-PREFETCHW-PREFETCHT0-v1","source_contract":{"mapping_id":"X86-64-PREFETCHW-PREFETCHT0-v1","status":"PASS"},"status":"PASS","tools":{"GNU_OBJDUMP":{"status":"PASS"},"LLVM_OBJDUMP":{"status":"PASS"}}})";
}

TEST(Q15Collectors, RegistryHasExactlySevenStableDistinctContracts) {
  std::vector<std::string_view> ids;
  ids.reserve(cpu_prefetch::qualification::kQ15CollectorContracts.size());
  for (const auto& item : cpu_prefetch::qualification::kQ15CollectorContracts) {
    ids.push_back(item.collector_id);
  }
  EXPECT_EQ(ids.size(), 7U);
  std::sort(ids.begin(), ids.end());
  EXPECT_EQ(std::adjacent_find(ids.begin(), ids.end()), ids.end());
}

TEST(Q15Collectors, AtomicLayoutIsObservedFromActualLinkedTypes) {
  const auto accepted =
      cpu_prefetch::qualification::collect_q15_atomic_layout(identity(), 64U);
  ASSERT_TRUE(accepted.has_value());
  EXPECT_TRUE(accepted.value().complete);
  EXPECT_TRUE(accepted.value().eligible);
  EXPECT_NE(accepted.value().canonical_json.find("ring_pointer_runtime_lock_free"),
            std::string::npos);

  const auto wrong_line =
      cpu_prefetch::qualification::collect_q15_atomic_layout(identity(), 128U);
  ASSERT_TRUE(wrong_line.has_value());
  EXPECT_TRUE(wrong_line.value().complete);
  EXPECT_FALSE(wrong_line.value().eligible);
}

TEST(Q15Collectors, MigrationAndResidencyDeriveFailuresFromRawSamples) {
  const std::array<std::uint32_t, 4U> producer{0U, 0U, 0U, 0U};
  const std::array<std::uint32_t, 4U> consumer{1U, 1U, 1U, 1U};
  auto migration = cpu_prefetch::qualification::collect_q15_actual_cpu_migration(
      identity(), {0U, true, producer}, {1U, true, consumer});
  ASSERT_TRUE(migration.has_value());
  EXPECT_TRUE(migration.value().eligible);

  const std::array<std::uint32_t, 4U> migrated{1U, 1U, 0U, 1U};
  migration = cpu_prefetch::qualification::collect_q15_actual_cpu_migration(
      identity(), {0U, true, producer}, {1U, true, migrated});
  ASSERT_TRUE(migration.has_value());
  EXPECT_FALSE(migration.value().eligible);

  const cpu_prefetch::platform::Q15ResidencySnapshot local{{0, 0, 0}};
  std::array<cpu_prefetch::qualification::Q15RegionResidencySeries, 3U> regions{{
      {"SHARED_EVENT_AND_QUEUE", 0U, local, local, local},
      {"PRODUCER_PRIVATE", 0U, local, local, local},
      {"CONSUMER_PRIVATE", 0U, local, local, local},
  }};
  auto residency =
      cpu_prefetch::qualification::collect_q15_address_residency(identity(), regions);
  ASSERT_TRUE(residency.has_value());
  EXPECT_TRUE(residency.value().eligible);

  regions[2].after.page_nodes[1] = 1;
  residency =
      cpu_prefetch::qualification::collect_q15_address_residency(identity(), regions);
  ASSERT_TRUE(residency.has_value());
  EXPECT_FALSE(residency.value().eligible);
}

TEST(Q15Collectors, SoftwarePrefetchReadsEveryFixedCpuAndDistinctReports) {
  CapabilityPlatform platform;
  CapabilityBackend capability;
  const auto gcc = report('1');
  const auto clang = report('2');
  auto artifact = cpu_prefetch::qualification::collect_q15_software_prefetch(
      identity(), platform, capability, {gcc, clang});
  ASSERT_TRUE(artifact.has_value());
  EXPECT_TRUE(artifact.value().complete);
  EXPECT_TRUE(artifact.value().eligible);
  EXPECT_EQ((std::vector<std::uint32_t>{0U, 1U, 26U}), platform.observed);
  EXPECT_EQ(capability.count, 3U);

  CapabilityPlatform duplicate_platform;
  CapabilityBackend duplicate_capability;
  artifact = cpu_prefetch::qualification::collect_q15_software_prefetch(
      identity(), duplicate_platform, duplicate_capability, {gcc, gcc});
  ASSERT_TRUE(artifact.has_value());
  EXPECT_FALSE(artifact.value().eligible);
}

TEST(Q15Collectors, MsrPrestateAndReadbackUseBackendObservationsNotRequestedState) {
  FakeMsr msr;
  auto prestate =
      cpu_prefetch::qualification::collect_q15_msr_prestate(identity(), msr);
  ASSERT_TRUE(prestate.has_value());
  EXPECT_TRUE(prestate.value().complete);
  EXPECT_TRUE(prestate.value().eligible);
  EXPECT_EQ((std::vector<std::uint32_t>{0U, 1U, 26U}), msr.reads);

  auto readback = cpu_prefetch::qualification::collect_q15_msr_readback(
      identity(), msr, 1U, 0x20U,
      cpu_prefetch::qualification::Q15MsrReadbackPhase::h1_apply, "writer", "auditor");
  ASSERT_TRUE(readback.has_value());
  EXPECT_TRUE(readback.value().eligible);

  readback = cpu_prefetch::qualification::collect_q15_msr_readback(
      identity(), msr, 1U, 0x21U,
      cpu_prefetch::qualification::Q15MsrReadbackPhase::h1_apply, "same", "same");
  ASSERT_TRUE(readback.has_value());
  EXPECT_FALSE(readback.value().complete);
  EXPECT_FALSE(readback.value().eligible);

  msr.fail_cpu = 26U;
  prestate = cpu_prefetch::qualification::collect_q15_msr_prestate(identity(), msr);
  ASSERT_TRUE(prestate.has_value());
  EXPECT_FALSE(prestate.value().complete);
  EXPECT_FALSE(prestate.value().eligible);
}

TEST(Q15Collectors, ClockEligibilityComesFromRawEvaluatorOutputs) {
  using namespace cpu_prefetch::timing;
  std::vector<std::uint64_t> producer(kQualificationDeltaCount + 1U);
  std::vector<std::uint64_t> consumer(kQualificationDeltaCount + 1U);
  for (std::size_t index = 0U; index < producer.size(); ++index) {
    producer[index] = static_cast<std::uint64_t>(index) * 1000U;
    consumer[index] = static_cast<std::uint64_t>(index) * 1000U;
  }
  std::vector<CrossCoreExchangeSample> exchanges(kCrossCoreExchangeCountPerWindow,
                                                 {100U, 110U, 120U, 130U});
  const std::array<CrossCoreWindowInput, 3U> windows{
      {{0U, exchanges}, {30'000'000'000U, exchanges}, {60'000'000'000U, exchanges}}};
  const StaticClockEvidenceInput static_input{
      true, true, true, true, true, true, true, true, true, kQualificationDeltaCount,
      0U,   0U,   true, true, 1000U};
  const PerCoreQualificationInput producer_input{
      producer, kQualificationPrimeReadCount, 0U, 0U, true, true, true, true};
  const PerCoreQualificationInput consumer_input{
      consumer, kQualificationPrimeReadCount, 0U, 0U, true, true, true, true};
  auto clock = cpu_prefetch::qualification::collect_q15_clock(
      identity(),
      {static_input, {producer_input, consumer_input}, {windows, windows}, 90U, 100U});
  ASSERT_TRUE(clock.has_value());
  EXPECT_TRUE(clock.value().complete);
  EXPECT_TRUE(clock.value().eligible);

  const std::array<std::uint64_t, 1U> incomplete{0U};
  const PerCoreQualificationInput incomplete_input{
      incomplete, kQualificationPrimeReadCount, 0U, 0U, true, true, true, true};
  clock = cpu_prefetch::qualification::collect_q15_clock(
      identity(), {static_input,
                   {incomplete_input, consumer_input},
                   {windows, windows},
                   90U,
                   100U});
  ASSERT_TRUE(clock.has_value());
  EXPECT_FALSE(clock.value().complete);
  EXPECT_FALSE(clock.value().eligible);

  clock = cpu_prefetch::qualification::collect_q15_clock(
      identity(),
      {static_input, {producer_input, consumer_input}, {windows, windows}, 100U, 90U});
  ASSERT_TRUE(clock.has_value());
  EXPECT_TRUE(clock.value().complete);
  EXPECT_FALSE(clock.value().eligible);
}

} // namespace
