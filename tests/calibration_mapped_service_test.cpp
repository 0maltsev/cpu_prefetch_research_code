#include "cpu_prefetch/calibration/native_formal_service_capture.hpp"
#include "cpu_prefetch/runner/software_prefetch.hpp"
#include "cpu_prefetch/workload/working_set.hpp"
#include "discovery_backend_test_support.hpp"
#include "worker_stack_test_support.hpp"

#include <gtest/gtest.h>

namespace {
using namespace cpu_prefetch;
namespace c = calibration;
template <typename T> auto required(const std::optional<T>& value) -> const T& {
  if (!value.has_value())
    throw std::logic_error("test expected bound optional");
  return *value;
}
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
template <protocol::QueuePackage Kind> void check_mapped_package() {
  using Modules = std::array<platform::ThreadTlsModule, 128U>;
  std::array<Modules, 4U> tls{};
  alignas(64) std::array<std::byte, 128U> termination{};
  Clock clock;
  test_support::DiscoveryTestRelax relax;
  const auto input = plan(Kind);
  using Runtime = c::MappedServiceRuntime<Clock, test_support::DiscoveryTestRelax,
                                          c::FormalServiceRuntimePolicy<Kind, Emitter>,
                                          Memory, test::SoftwareStackOperations>;
  Runtime runtime{input,
                  {test::software_stack_plan(), test::software_stack_plan()},
                  {{{tls[0U], tls[1U]}}, {{tls[2U], tls[3U]}}},
                  {std::span(termination).first(64U), std::span(termination).last(64U)},
                  clock,
                  relax};
  Observer observer;
  const auto result = runtime.run(observer);
  ASSERT_EQ(result.stop, c::ServiceSessionStop::complete);
  std::uint64_t produced = 0U, polled = 0U, consumed = 0U;
  for (std::size_t phase = 0U; phase < 2U; ++phase) {
    auto& producer = runtime.preparation().producer_phase(phase == 0U);
    auto& consumer = runtime.preparation().consumer_phase(phase == 0U);
    EXPECT_EQ(consumer.last_join.status, c::DiscoveryJoinStatus::exact);
    EXPECT_EQ(producer.accepted, consumer.retained_consumed);
    EXPECT_EQ(producer.primary.snapshot().completeness,
              storage::StreamCompleteness::sealed_complete);
    produced += producer.requests;
    polled += consumer.polls;
    consumed += consumer.retained_consumed;
  }
  EXPECT_FALSE(runtime.preparation().consumer_phase(true).interval);
  ASSERT_TRUE(runtime.preparation().consumer_phase(false).interval);
  const auto& emission = runtime.preparation().emitter();
  if constexpr (Kind == protocol::QueuePackage::r1 ||
                Kind == protocol::QueuePackage::r2) {
    EXPECT_EQ(emission.producer.load(), produced);
    EXPECT_EQ(emission.consumer.load(), polled);
    EXPECT_EQ(emission.successor.load(), 0U);
  } else if constexpr (Kind == protocol::QueuePackage::l1) {
    EXPECT_EQ(emission.producer.load(), 0U);
    EXPECT_EQ(emission.consumer.load(), 0U);
    EXPECT_EQ(emission.successor.load(), consumed);
  } else {
    EXPECT_EQ(emission.producer.load(), 0U);
    EXPECT_EQ(emission.consumer.load(), 0U);
    EXPECT_EQ(emission.successor.load(), 0U);
  }
  if constexpr (Kind == protocol::QueuePackage::l0 ||
                Kind == protocol::QueuePackage::l1) {
    const auto order = runtime.preparation().node_order();
    const auto& bound = required(input.linked_order);
    workload::NodeOrderPlan reference(
        {input.arena.capacity, input.arena.cache_line_bytes,
         input.arena.cache_line_bytes, input.arena.base_page_bytes},
        bound.master_seed, bound.seed_namespace);
    EXPECT_TRUE(std::equal(order.begin(), order.end(), reference.order().begin(),
                           reference.order().end()));
    const auto& layout = runtime.preparation().layout();
    ASSERT_TRUE(layout.linked);
    const auto region = runtime.producer_memory().mapped_bytes();
    const auto begin = reinterpret_cast<std::uintptr_t>(region.data());
    const auto ordered = reinterpret_cast<std::uintptr_t>(order.data());
    EXPECT_GE(ordered, begin);
    EXPECT_LE(ordered + order.size_bytes(), begin + region.size());
    EXPECT_EQ(required(layout.linked).order_count, input.arena.capacity + 1U);
    EXPECT_LE(layout.nodes + required(layout.linked).node_bytes, region.size());
    EXPECT_LE(layout.recycler + required(layout.linked).recycler_bytes, region.size());
  }
  EXPECT_TRUE(runtime.close());
  EXPECT_TRUE(runtime.close());
}
TEST(MappedFormalService, R0PreservesMapsAndPrimaryJoin) {
  check_mapped_package<protocol::QueuePackage::r0>();
}
TEST(MappedFormalService, R1KeepsExactTwoSiteVectors) {
  check_mapped_package<protocol::QueuePackage::r1>();
}
TEST(MappedFormalService, R2UsesExplicitPriorDistance) {
  check_mapped_package<protocol::QueuePackage::r2>();
}
TEST(MappedFormalService, L0MapsNodesRecyclerAndBothOrders) {
  check_mapped_package<protocol::QueuePackage::l0>();
}
TEST(MappedFormalService, L1KeepsOneSuccessorSite) {
  check_mapped_package<protocol::QueuePackage::l1>();
}
TEST(MappedFormalService, RejectsWrongPackageDistanceAndLinkedBindingsBeforeMapping) {
  using E = runner::X86PrefetchT0OnlyEmitter;
  auto r2 = plan(protocol::QueuePackage::r2);
  r2.ring_distance.reset();
  EXPECT_THROW(static_cast<void>(
                   c::mapped_formal_service_layout<protocol::QueuePackage::r2, E>(r2)),
               std::invalid_argument);
  auto linked = plan(protocol::QueuePackage::l0);
  linked.linked_order.reset();
  EXPECT_THROW(
      static_cast<void>(
          c::mapped_formal_service_layout<protocol::QueuePackage::l0, E>(linked)),
      std::invalid_argument);
  auto r1 = plan(protocol::QueuePackage::r1);
  r1.ring_distance = c::FormalRingDistancePlan{2U, ""};
  EXPECT_THROW(static_cast<void>(
                   c::mapped_formal_service_layout<protocol::QueuePackage::r1, E>(r1)),
               std::invalid_argument);
}
} // namespace
