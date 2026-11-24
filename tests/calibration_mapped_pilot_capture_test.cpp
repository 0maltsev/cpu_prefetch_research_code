#include "cpu_prefetch/calibration/mapped_pilot_capture.hpp"
#include "cpu_prefetch/calibration/native_pilot_capture.hpp"
#include "cpu_prefetch/runner/software_prefetch.hpp"
#include "cpu_prefetch/workload/working_set.hpp"
#include "discovery_backend_test_support.hpp"
#include "worker_stack_test_support.hpp"

#include <gtest/gtest.h>
#include <numeric>
#include <unistd.h>

namespace {
using namespace cpu_prefetch;
namespace c = calibration;
struct Memory final {
  platform::LinuxOwnerMemoryOperations native;
  auto base_page_bytes() noexcept { return native.base_page_bytes(); }
  auto map_private(std::size_t size) noexcept { return native.map_private(size); }
  auto bind_pages(std::span<std::byte>, std::uint32_t) noexcept
      -> platform::LinuxCallResult {
    return {0, 0};
  }
  auto disable_huge_pages(std::span<std::byte> bytes) noexcept {
    return native.disable_huge_pages(bytes);
  }
  auto bind_current_thread(std::uint32_t) noexcept -> platform::LinuxCallResult {
    return {0, 0};
  }
  auto observe_current_thread(std::uint32_t cpu) noexcept {
    return platform::OwnerThreadObservation{
        {0, 0}, {cpu, 0}, {::gettid(), 0}, {0, 0}, 0, 0, 1, true};
  }
  auto lock_pages(std::span<std::byte> bytes) noexcept {
    static_cast<void>(bytes);
    return platform::LinuxCallResult{0, 0};
  }
  auto protect_read_only(std::span<std::byte> bytes) noexcept {
    return native.protect_read_only(bytes);
  }
  auto unlock_pages(std::span<std::byte> bytes) noexcept {
    static_cast<void>(bytes);
    return platform::LinuxCallResult{0, 0};
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
struct Emitter final {
  std::atomic<std::uint64_t> producer{0U}, consumer{0U}, successor{0U};
  void ring_producer_write(const void*) noexcept { producer.fetch_add(1U); }
  void ring_consumer_read(const void*) noexcept { consumer.fetch_add(1U); }
  void successor_header(const void*) noexcept { successor.fetch_add(1U); }
};
struct Observer final {
  bool fail_measurement{false};
  auto before_phase(c::ServicePhase phase) const noexcept -> bool {
    return !fail_measurement || phase != c::ServicePhase::measurement;
  }
  auto during_phase(c::ServicePhase, c::ServiceWindow,
                    const std::atomic<std::uint32_t>&) const noexcept -> bool {
    return true;
  }
  auto after_phase(c::ServicePhase) const noexcept -> bool { return true; }
};
auto plan(protocol::QueuePackage package) -> c::MappedFormalServicePlan {
  c::MappedFormalServicePlan result{
      package,
      {{{{1'000'000U, 2048U, 4096U, 20'000'000U},
         {1'000'000U, 2048U, 4096U, 20'000'000U}}},
       5'000'000U},
      {512U, 64U, test::software_stack_plan().verified_base_page_bytes,
       workload::MasterSeed::from_hex(std::string(64U, '0')), "service-mapped-test"},
      {test_support::discovery_test_run_id("service-warmup"),
       test_support::discovery_test_run_id("service-measured")},
      {17U},
      {{{2048U, 2048U}, {2048U, 2048U}}},
      std::nullopt,
      std::nullopt};
  if (package == protocol::QueuePackage::l0 || package == protocol::QueuePackage::l1) {
    result.linked_order =
        c::FormalLinkedOrderPlan{workload::MasterSeed::from_hex(std::string(64U, '1')),
                                 "service-node-test", result.arena.base_page_bytes};
  } else if (package == protocol::QueuePackage::r1) {
    result.ring_distance = c::FormalRingDistancePlan{1U, ""};
  } else if (package == protocol::QueuePackage::r2) {
    result.ring_distance = c::FormalRingDistancePlan{2U, "software-only-prior-d2"};
  }
  return result;
}

struct Source final {
  std::array<std::uint64_t, 4U> warmup{1000U, 2000U, 2000U, 3000U};
  std::array<std::uint64_t, 4U> measured{101000U, 102000U, 102000U, 103000U};
  auto input(protocol::QueuePackage package) const -> c::MappedFormalScheduledPlan {
    auto service = plan(package);
    service.session.phases[0U].duration_ticks = 5'000'000'000'000U;
    return {std::move(service),
            {{{1000U, 5'000'000'001'000U, warmup.size(),
               protocol::ScheduleId::parse("warmup-schedule", "$test").value(),
               protocol::NamespaceId::parse("warmup-source", "$test").value()},
              {100000U, 1100000U, measured.size(),
               protocol::ScheduleId::parse("measured-schedule", "$test").value(),
               protocol::NamespaceId::parse("measured-source", "$test").value()}}},
            {warmup, measured}};
  }
};
auto data_plan(const c::MappedFormalServicePlan& service, std::uint32_t cpu)
    -> c::MappedPilotDataPlan {
  return {{protocol::Placement::near, protocol::WorkingSetClass::l2_resident},
          service.arena,
          {workload::MasterSeed::from_hex(std::string(64U, '1')), "service-node-test",
           service.arena.base_page_bytes},
          cpu,
          0U};
}
// Synthetic clocks and placement/locking observations; real mmap, read-only
// protection, pthread stacks, TLS discovery, queues and primary streams.
// No native capture, residency, timing or qualification claim is made.
template <protocol::QueuePackage Kind>
void check_mapped(c::MappedPilotData<Memory>& data, bool fail_measurement = false) {
  using Modules = std::array<platform::ThreadTlsModule, 128U>;
  std::array<Modules, 4U> tls{};
  alignas(64) std::array<std::byte, 128U> termination{};
  Clock clock;
  test_support::DiscoveryTestRelax relax;
  Source source;
  const auto input = c::MappedPilotCapturePlan{source.input(Kind), data.view()};
  using Runtime = c::MappedServiceRuntime<Clock, test_support::DiscoveryTestRelax,
                                          c::PilotRuntimePolicy<Kind, Emitter>, Memory,
                                          test::SoftwareStackOperations>;
  auto owner = test::software_stack_plan();
  owner.owner_cpu = input.shared.plan->producer_cpu;
  Runtime runtime{input,
                  {owner, owner},
                  {{{tls[0U], tls[1U]}}, {{tls[2U], tls[3U]}}},
                  {std::span(termination).first(64U), std::span(termination).last(64U)},
                  clock,
                  relax};
  Observer observer{fail_measurement};
  const auto identity = data.view().data->identity();
  const auto checksum = data.view().data->arena().content_checksum();
  const auto result = runtime.run(observer);
  ASSERT_EQ(result.session.lifecycle.stop,
            fail_measurement ? c::ServiceSessionStop::observation_failure
                             : c::ServiceSessionStop::complete);
  EXPECT_TRUE(result.initial_queue_reset);
  for (std::size_t phase = 0U; phase < (fail_measurement ? 1U : 2U); ++phase) {
    const auto mapped = runtime.preparation().schedule(
        phase == 0U ? c::ServicePhase::warmup : c::ServicePhase::measurement);
    EXPECT_NE(mapped.deadline_ticks.data(), input.scheduled.deadlines[phase].data());
    EXPECT_TRUE(std::equal(mapped.deadline_ticks.begin(), mapped.deadline_ticks.end(),
                           input.scheduled.deadlines[phase].begin()));
    const auto& producer = runtime.preparation().producer_phase(phase == 0U);
    const auto& consumer = runtime.preparation().consumer_phase(phase == 0U);
    EXPECT_EQ(producer.requests, 4U);
    EXPECT_EQ(producer.primary.snapshot().completeness,
              storage::StreamCompleteness::sealed_complete);
    EXPECT_EQ(consumer.primary.snapshot().completeness,
              storage::StreamCompleteness::sealed_complete);
    EXPECT_EQ(consumer.last_join.status, c::DiscoveryJoinStatus::exact);
    EXPECT_EQ(producer.accepted, consumer.retained_consumed);
    EXPECT_TRUE(result.session.schedules[phase].mapped_schedule_validated);
    EXPECT_TRUE(result.session.schedules[phase].all_arrivals_attempted);
  }
  EXPECT_TRUE(runtime.records().evidence().read_only.has_value());
  const auto warmup = runtime.preparation().producer_phase(true).primary.snapshot();
  const auto measured = runtime.preparation().producer_phase(false).primary.snapshot();
  EXPECT_NE(warmup.run_id, measured.run_id);
  EXPECT_EQ(warmup.row_count, 4U);
  if (fail_measurement) {
    EXPECT_EQ(measured.row_count, 0U);
  }
  source.warmup[0U] = 999999U;
  EXPECT_EQ(runtime.preparation().schedule(c::ServicePhase::warmup).deadline_ticks[0U],
            1000U);
  EXPECT_FALSE(runtime.run(observer).initial_queue_reset);
  EXPECT_TRUE(runtime.close());
  EXPECT_TRUE(runtime.records().evidence().cleanup_attempted);
  EXPECT_FALSE(data.records_evidence().cleanup_attempted);
  EXPECT_FALSE(data.queues_evidence().cleanup_attempted);
  EXPECT_EQ(data.view().data->identity(), identity);
  EXPECT_EQ(data.view().data->arena().content_checksum(), checksum);
}
TEST(MappedPilotCapture, AllFivePackagesRetainTheSameDataAcrossTenCaptures) {
  c::MappedPilotData<Memory> data(data_plan(plan(protocol::QueuePackage::r0),
                                            test::software_stack_plan().owner_cpu));
  ASSERT_TRUE(data.prepare());
  for (unsigned paired_state = 0U; paired_state < 2U; ++paired_state) {
    check_mapped<protocol::QueuePackage::r0>(data);
    check_mapped<protocol::QueuePackage::r1>(data);
    check_mapped<protocol::QueuePackage::r2>(data);
    check_mapped<protocol::QueuePackage::l0>(data);
    check_mapped<protocol::QueuePackage::l1>(data);
  }
  EXPECT_TRUE(data.release());
}
TEST(MappedPilotCapture, FailedMeasurementRetainsOriginalWarmupAndSharedData) {
  c::MappedPilotData<Memory> data(data_plan(plan(protocol::QueuePackage::r0),
                                            test::software_stack_plan().owner_cpu));
  ASSERT_TRUE(data.prepare());
  check_mapped<protocol::QueuePackage::l1>(data, true);
  EXPECT_TRUE(data.release());
}
TEST(MappedPilotCapture, ChangedSeedLayoutOrReleasedDataRejectCold) {
  Source source;
  c::MappedPilotData<Memory> data(
      data_plan(source.input(protocol::QueuePackage::r0).service, 0U));
  ASSERT_TRUE(data.prepare());
  const c::MappedPilotCapturePlan baseline{source.input(protocol::QueuePackage::r0),
                                           data.view()};
  for (unsigned failure = 0U; failure < 6U; ++failure) {
    auto p = baseline;
    switch (failure) {
    case 0U:
      p.scheduled.service.arena.seed_namespace += "-changed";
      break;
    case 1U:
      p.shared.regions[0U].mapping = p.shared.regions[0U].mapping.subspan(1U);
      break;
    case 2U:
      p.shared.node_order = p.shared.node_order.subspan(1U);
      break;
    case 3U:
      p.shared.data = nullptr;
      break;
    case 4U:
      p.scheduled.phases[0U].offered_count += 1U;
      break;
    default:
      p.scheduled.service.arena.master_seed =
          workload::MasterSeed::from_hex(std::string(64U, 'f'));
      break;
    }
    EXPECT_THROW(
        (c::mapped_pilot_capture_layout<protocol::QueuePackage::r0, Emitter>(p)),
        std::invalid_argument);
  }
  EXPECT_TRUE(data.release());
  EXPECT_THROW(c::validate_pilot_shared_view(baseline), std::invalid_argument);
}
constexpr std::array<platform::HardwarePrefetchMsrValue, 3U> prestate{
    {{0U, 0U}, {1U, 0U}, {8U, 0U}}};
auto native_plan(c::PreparedPilotDataView data, const Source& source)
    -> c::NativePilotCapturePlan {
  auto scheduled = source.input(protocol::QueuePackage::r0);
  // Borrowed source arrays outlive all cold layout checks.
  scheduled.service.arena = data.plan->arena;
  const auto page = data.plan->arena.base_page_bytes;
  c::NativePilotCaptureControlPlan controls{
      {{std::size_t{2U} * 1024U * 1024U, page, 0U, 0U},
       {std::size_t{2U} * 1024U * 1024U, page, 1U, 0U}},
      {std::size_t{2U} * 1024U * 1024U, page, 2U, 0U},
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
  return {{std::move(scheduled), data},
          std::move(controls),
          std::string(runner::kSoftwarePrefetchMappingIdT0Only)};
}
TEST(NativePilotCapture,
     LayoutIncludesBothPersistentMappingsAndRejectsMissingCoverage) {
  auto p = data_plan(plan(protocol::QueuePackage::r0), 0U);
  p.arena.capacity = 4096U;
  c::MappedPilotData<Memory> data(p);
  ASSERT_TRUE(data.prepare());
  Source source;
  auto native = native_plan(data.view(), source);
  const auto layout = c::native_pilot_layout(native);
  EXPECT_EQ(layout.region_bytes.size(), 9U);
  EXPECT_EQ(layout.region_bytes[7U], data.layout().records_bytes);
  EXPECT_EQ(layout.region_bytes[8U], data.layout().queues_bytes);
  EXPECT_EQ(layout.total_mapping_bytes,
            std::accumulate(layout.region_bytes.begin(), layout.region_bytes.end(),
                            std::size_t{0U}) +
                layout.monitor_bytes + 3U * p.arena.base_page_bytes);
  EXPECT_GT(layout.region_bytes[7U], layout.workers.records_bytes);
  for (const auto package : {protocol::QueuePackage::r0, protocol::QueuePackage::r1,
                             protocol::QueuePackage::r2, protocol::QueuePackage::l0,
                             protocol::QueuePackage::l1}) {
    auto paired = native;
    paired.capture.scheduled = source.input(package);
    paired.capture.scheduled.service.arena = p.arena;
    EXPECT_EQ(c::native_pilot_layout(paired).region_bytes[8U], layout.region_bytes[8U]);
  }
  for (const auto region : {7U, 8U}) {
    auto rejected = native;
    rejected.controls.during_page_count[region] = 0U;
    EXPECT_THROW(static_cast<void>(c::native_pilot_layout(rejected)),
                 std::invalid_argument);
  }
  native.capture.shared.node_pattern.adjacent_fraction_at_most_one_percent = false;
  EXPECT_THROW(static_cast<void>(c::native_pilot_layout(native)),
               std::invalid_argument);
}
TEST(NativePilotCapture, ModelMappingAndOwnerDriftRejectBeforeNativeAccess) {
  auto p = data_plan(plan(protocol::QueuePackage::r0), 0U);
  p.arena.capacity = 4096U;
  c::MappedPilotData<Memory> data(p);
  ASSERT_TRUE(data.prepare());
  Source source;
  const auto baseline = native_plan(data.view(), source);
  for (unsigned failure = 0U; failure < 4U; ++failure) {
    auto native = baseline;
    switch (failure) {
    case 0U:
      native.software_prefetch_mapping_id = runner::kSoftwarePrefetchMappingId;
      break;
    case 1U:
      native.controls.workers.producer_stack.owner_cpu = 8U;
      break;
    case 2U:
      native.controls.during_page_count[8U] = std::numeric_limits<std::size_t>::max();
      break;
    default:
      native.controls.control_region_index = 9U;
      break;
    }
    EXPECT_THROW(static_cast<void>(c::native_pilot_layout(native)),
                 std::invalid_argument);
  }
}
} // namespace
