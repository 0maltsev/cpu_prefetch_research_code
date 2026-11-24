#include "cpu_prefetch/calibration/mapped_formal_scheduled_runtime.hpp"
#include "cpu_prefetch/calibration/native_formal_scheduled_capture.hpp"
#include "cpu_prefetch/runner/software_prefetch.hpp"
#include "cpu_prefetch/workload/working_set.hpp"
#include "discovery_backend_test_support.hpp"
#include "worker_stack_test_support.hpp"

#include <gtest/gtest.h>

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
struct Emitter final {
  std::atomic<std::uint64_t> producer{0U}, consumer{0U}, successor{0U};
  void ring_producer_write(const void*) noexcept { producer.fetch_add(1U); }
  void ring_consumer_read(const void*) noexcept { consumer.fetch_add(1U); }
  void successor_header(const void*) noexcept { successor.fetch_add(1U); }
};
struct Observer final {
  auto before_phase(c::ServicePhase) const noexcept -> bool { return true; }
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
      {64U, 64U, test::software_stack_plan().verified_base_page_bytes,
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
template <protocol::QueuePackage Kind> void check_mapped() {
  using Modules = std::array<platform::ThreadTlsModule, 128U>;
  std::array<Modules, 4U> tls{};
  alignas(64) std::array<std::byte, 128U> termination{};
  Clock clock;
  test_support::DiscoveryTestRelax relax;
  Source source;
  const auto input = source.input(Kind);
  using Runtime =
      c::MappedServiceRuntime<Clock, test_support::DiscoveryTestRelax,
                              c::FormalScheduledRuntimePolicy<Kind, Emitter>, Memory,
                              test::SoftwareStackOperations>;
  Runtime runtime{input,
                  {test::software_stack_plan(), test::software_stack_plan()},
                  {{{tls[0U], tls[1U]}}, {{tls[2U], tls[3U]}}},
                  {std::span(termination).first(64U), std::span(termination).last(64U)},
                  clock,
                  relax};
  Observer observer;
  const auto result = runtime.run(observer);
  ASSERT_EQ(result.lifecycle.stop, c::ServiceSessionStop::complete);
  const auto records = runtime.records().mapped_bytes();
  const auto begin = reinterpret_cast<std::uintptr_t>(records.data());
  std::uint64_t consumed = 0U, polls = 0U;
  for (std::size_t phase = 0U; phase < 2U; ++phase) {
    const auto mapped = runtime.preparation().schedule(
        phase == 0U ? c::ServicePhase::warmup : c::ServicePhase::measurement);
    const auto address = reinterpret_cast<std::uintptr_t>(mapped.deadline_ticks.data());
    EXPECT_GE(address, begin);
    EXPECT_LE(address + mapped.deadline_ticks.size_bytes(), begin + records.size());
    EXPECT_NE(mapped.deadline_ticks.data(), input.deadlines[phase].data());
    EXPECT_TRUE(std::equal(mapped.deadline_ticks.begin(), mapped.deadline_ticks.end(),
                           input.deadlines[phase].begin(),
                           input.deadlines[phase].end()));
    EXPECT_EQ(mapped.origin_ticks, input.phases[phase].source_origin_ticks);
    EXPECT_EQ(mapped.horizon_ticks, input.phases[phase].source_horizon_ticks);
    const auto& producer = runtime.preparation().producer_phase(phase == 0U);
    const auto& consumer = runtime.preparation().consumer_phase(phase == 0U);
    EXPECT_EQ(producer.requests, 4U);
    EXPECT_EQ(consumer.last_join.status, c::DiscoveryJoinStatus::exact);
    EXPECT_EQ(producer.accepted, consumer.retained_consumed);
    EXPECT_FALSE(consumer.interval);
    EXPECT_TRUE(result.schedules[phase].mapped_schedule_validated);
    EXPECT_TRUE(result.schedules[phase].all_arrivals_attempted);
    EXPECT_EQ(result.schedules[phase].offered, 4U);
    consumed += consumer.retained_consumed;
    polls += consumer.polls;
  }
  EXPECT_TRUE(runtime.records().evidence().read_only);
  // Mutating the cold caller input after join cannot mutate the executed evidence.
  source.warmup[0U] = 999999U;
  EXPECT_EQ(runtime.preparation().schedule(c::ServicePhase::warmup).deadline_ticks[0U],
            1000U);
  const auto& emitter = runtime.preparation().emitter();
  if constexpr (Kind == protocol::QueuePackage::r1 ||
                Kind == protocol::QueuePackage::r2) {
    EXPECT_EQ(emitter.producer.load(), 8U);
    EXPECT_EQ(emitter.consumer.load(), polls);
  } else if constexpr (Kind == protocol::QueuePackage::l1) {
    EXPECT_EQ(emitter.successor.load(), consumed);
  }
  EXPECT_TRUE(runtime.close());
}
TEST(MappedFormalScheduled, AllFivePackagesExecuteOnlyMappedSchedulesAndDrain) {
  check_mapped<protocol::QueuePackage::r0>();
  check_mapped<protocol::QueuePackage::r1>();
  check_mapped<protocol::QueuePackage::r2>();
  check_mapped<protocol::QueuePackage::l0>();
  check_mapped<protocol::QueuePackage::l1>();
}
TEST(MappedFormalScheduled, OverflowingSourceExtentRejectsBeforeReading) {
  Source source;
  auto input = source.input(protocol::QueuePackage::r0);
  constexpr auto count =
      std::numeric_limits<std::size_t>::max() / sizeof(std::uint64_t) + 1U;
  input.deadlines[1U] = std::span<const std::uint64_t>(source.measured.data(), count);
  input.phases[1U].offered_count = count;
  input.service.session.phases[1U].producer_attempt_limit = count;
  EXPECT_THROW(c::validate_mapped_scheduled_plan(input), std::invalid_argument);
}
TEST(MappedFormalScheduled, SourceMismatchAndUnorderedOrEndpointInputRejectCold) {
  Source source;
  auto input = source.input(protocol::QueuePackage::r0);
  input.phases[1U].offered_count = 5U;
  EXPECT_THROW(c::validate_mapped_scheduled_plan(input), std::invalid_argument);
  input = source.input(protocol::QueuePackage::r0);
  source.measured[1U] = 100000U;
  EXPECT_THROW(c::validate_mapped_scheduled_plan(input), std::invalid_argument);
  source.measured[1U] = 1100000U;
  EXPECT_THROW(c::validate_mapped_scheduled_plan(input), std::invalid_argument);
}
} // namespace
