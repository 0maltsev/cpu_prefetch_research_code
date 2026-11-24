#include "cpu_prefetch/calibration/native_formal_ring_capture.hpp"
#include "discovery_backend_test_support.hpp"
#include "worker_stack_test_support.hpp"

#include <gtest/gtest.h>

#include <numeric>

namespace {
using namespace cpu_prefetch;
namespace c = calibration;

struct MemoryOperations final {
  platform::LinuxOwnerMemoryOperations native;
  bool reject{false};
  auto base_page_bytes() noexcept { return native.base_page_bytes(); }
  auto map_private(std::size_t size) noexcept { return native.map_private(size); }
  auto bind_pages(std::span<std::byte>, std::uint32_t) noexcept
      -> platform::LinuxCallResult {
    return reject ? platform::LinuxCallResult{-1, EPERM}
                  : platform::LinuxCallResult{0, 0};
  }
  auto disable_huge_pages(std::span<std::byte> bytes) noexcept {
    return native.disable_huge_pages(bytes);
  }
  auto bind_current_thread(std::uint32_t cpu) noexcept {
    return native.bind_current_thread(cpu);
  }
  auto observe_current_thread(std::uint32_t cpu) noexcept {
    return native.observe_current_thread(cpu);
  }
  auto lock_pages(std::span<std::byte> bytes) noexcept {
    return native.lock_pages(bytes);
  }
  auto protect_read_only(std::span<std::byte> bytes) noexcept {
    return native.protect_read_only(bytes);
  }
  auto unlock_pages(std::span<std::byte> bytes) noexcept {
    return native.unlock_pages(bytes);
  }
  auto unmap(std::span<std::byte> bytes) noexcept { return native.unmap(bytes); }
};
struct Clock final {
  std::atomic<std::uint64_t> next{1U};
  auto origin() const noexcept -> timing::ClockOrigin { return {0U}; }
  auto read() noexcept -> timing::ClockReadResult {
    const auto tick = next.fetch_add(1U);
    return {timing::ClockReadStatus::ok, {tick, tick * 1000U}};
  }
};
struct Observer final {
  auto before_phase(c::ServicePhase) const noexcept -> bool { return true; }
  auto during_phase(c::ServicePhase, c::ServiceWindow,
                    const std::atomic<std::uint32_t>&) const noexcept -> bool {
    return true;
  }
  auto after_phase(c::ServicePhase) const noexcept -> bool { return true; }
};
auto software_plan() -> c::MappedFormalRingPlan {
  return {{{{{100'000U, 256U, 512U, 10'000'000U}, {100'000U, 256U, 512U, 10'000'000U}}},
           5'000'000U},
          {8U, 64U, test::software_stack_plan().verified_base_page_bytes,
           workload::MasterSeed::from_hex(std::string(64U, '0')), "formal-mapped-test"},
          {test_support::discovery_test_run_id("formal-native-w"),
           test_support::discovery_test_run_id("formal-native-m")},
          {17U},
          {{{256U, 256U, 256U, 512U}, {256U, 256U, 256U, 512U}}}};
}
struct Fixture final {
  using Modules = std::array<platform::ThreadTlsModule, 128U>;
  std::array<Modules, 4U> tls{};
  alignas(64) std::array<std::byte, 128U> termination{};
  Clock clock;
  test_support::DiscoveryTestRelax relax;
  using Runtime =
      c::MappedFormalRingRuntime<Clock, test_support::DiscoveryTestRelax,
                                 MemoryOperations, test::SoftwareStackOperations>;
  Runtime runtime{software_plan(),
                  {test::software_stack_plan(), test::software_stack_plan()},
                  {{{tls[0U], tls[1U]}}, {{tls[2U], tls[3U]}}},
                  {std::span(termination).first(64U), std::span(termination).last(64U)},
                  clock,
                  relax};
};
constexpr std::array<platform::HardwarePrefetchMsrValue, 3U> prestate{
    {{0U, 0U}, {1U, 0U}, {8U, 0U}}};
auto native_plan() -> c::NativeFormalRingCapturePlan {
  auto ring = software_plan();
  ring.session.phases[0U].duration_ticks = 5'000'000'000'000U;
  c::NativeCaptureControlPlan controls{
      {{std::size_t{2U} * 1024U * 1024U, 4096U, 0U, 0U},
       {std::size_t{2U} * 1024U * 1024U, 4096U, 1U, 0U}},
      {std::size_t{2U} * 1024U * 1024U, 4096U, 2U, 0U},
      32U,
      4096U,
      16384U,
      128U,
      {},
      {},
      {10U, 10U},
      1'000'000U,
      0U,
      {},
      {platform::kIntelFamily6, platform::kIntelModel3E},
      protocol::RequestedHardwareState::h0,
      prestate,
      {}};
  controls.during_page_count.fill(1U);
  return {std::move(ring), std::move(controls)};
}

TEST(NativeFormalRing, MappedOwnersKeepRawStreamsAndJoinBeforeRelease) {
  Fixture fixture;
  Observer observer;
  const auto result = fixture.runtime.run(observer);
  ASSERT_EQ(result.stop, c::ServiceSessionStop::complete);
  const auto regions = fixture.runtime.worker_regions();
  for (const auto region : regions) {
    EXPECT_FALSE(region.mapping.empty());
  }
  for (std::size_t phase = 0U; phase < 2U; ++phase) {
    auto& producer = fixture.runtime.preparation().producer_phase(phase == 0U);
    auto& consumer = fixture.runtime.preparation().consumer_phase(phase == 0U);
    EXPECT_EQ(producer.primary.snapshot().completeness,
              storage::StreamCompleteness::sealed_complete);
    EXPECT_EQ(consumer.last_join.status, c::DiscoveryJoinStatus::exact);
    EXPECT_EQ(producer.accepted, consumer.consumed);
    EXPECT_EQ(consumer.demand.snapshot().row_count, consumer.polls);
  }
  EXPECT_TRUE(fixture.runtime.close());
  EXPECT_TRUE(fixture.runtime.close());
  EXPECT_EQ(fixture.runtime.run(observer).stop, c::ServiceSessionStop::not_started);
}
TEST(NativeFormalRing, OwnerPreparationFailureRetainsRejectedSessionAndCleanup) {
  Fixture fixture;
  fixture.runtime.mapping_operations(1U).reject = true;
  Observer observer;
  const auto result = fixture.runtime.run(observer);
  EXPECT_EQ(result.stop, c::ServiceSessionStop::preparation_failure);
  EXPECT_FALSE(result.phases[0U].released);
  EXPECT_TRUE(fixture.runtime.close());
}
TEST(NativeFormalRing, ExactLayoutChargesIndependentRawCapacitiesAndBorrowedControls) {
  auto plan = native_plan();
  const auto layout = c::native_formal_ring_layout(plan);
  const auto workers = c::mapped_formal_ring_layout(plan.ring);
  EXPECT_EQ(layout.workers.records_bytes, workers.records_bytes);
  EXPECT_EQ(layout.total_mapping_bytes,
            std::accumulate(layout.region_bytes.begin(), layout.region_bytes.end(),
                            std::size_t{0U}) +
                layout.monitor_bytes + 3U * plan.ring.arena.base_page_bytes);
  plan.ring.capacity[1U].consumer_demand_rows *= 2U;
  EXPECT_GT(c::native_formal_ring_layout(plan).workers.consumer_bytes,
            workers.consumer_bytes);
  EXPECT_EQ(c::native_formal_ring_layout(plan).workers.producer_bytes,
            workers.producer_bytes);
}
TEST(NativeFormalRing, InvalidBoundsRejectBeforeHardwareOrPublication) {
  for (unsigned failure = 0U; failure < 5U; ++failure) {
    auto plan = native_plan();
    switch (failure) {
    case 0U:
      plan.ring.capacity[0U].consumer_demand_rows = 1U;
      break;
    case 1U:
      plan.controls.controller_stack.owner_cpu = 0U;
      break;
    case 2U:
      plan.controls.during_page_count[0U] = std::numeric_limits<std::size_t>::max();
      break;
    case 3U:
      plan.ring.run_ids[1U] = plan.ring.run_ids[0U];
      break;
    default:
      plan.ring.capacity[1U].producer_demand_rows =
          std::numeric_limits<std::uint64_t>::max();
      break;
    }
    EXPECT_THROW(static_cast<void>(c::native_formal_ring_layout(plan)), std::exception);
  }
  EXPECT_THROW(static_cast<void>(c::run_native_formal_ring_capture(native_plan(),
                                                                   {nullptr, nullptr})),
               std::invalid_argument);
}
} // namespace
