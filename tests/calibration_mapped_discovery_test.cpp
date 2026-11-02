#include "cpu_prefetch/calibration/mapped_discovery_preparation.hpp"
#include "discovery_backend_test_support.hpp"
#include "worker_stack_test_support.hpp"

#include <gtest/gtest.h>

#include <cerrno>

namespace {
using namespace cpu_prefetch;

// Native mappings, affinity, prefault, locking and protection. Binding is
// injected because sandbox NUMA permission is not stand qualification.
struct MemoryOperations final {
  platform::LinuxOwnerMemoryOperations native;
  bool reject_binding{false};
  bool reject_protection{false};
  auto base_page_bytes() noexcept { return native.base_page_bytes(); }
  auto map_private(std::size_t size) noexcept { return native.map_private(size); }
  auto bind_pages(std::span<std::byte>, std::uint32_t) noexcept
      -> platform::LinuxCallResult {
    return reject_binding ? platform::LinuxCallResult{-1, EPERM}
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
    return reject_protection ? platform::LinuxCallResult{-1, EACCES}
                             : native.protect_read_only(bytes);
  }
  auto unlock_pages(std::span<std::byte> bytes) noexcept {
    return native.unlock_pages(bytes);
  }
  auto unmap(std::span<std::byte> bytes) noexcept { return native.unmap(bytes); }
};

auto software_plan() -> calibration::MappedDiscoveryPlan {
  return {{200'000U, 200'000U, 256U, 256U, 1'000'000U, 9U, 1'000'000U},
          {8U, 64U, test::software_stack_plan().verified_base_page_bytes,
           workload::MasterSeed::from_hex(std::string(64U, '0')),
           "mapped-discovery-software"},
          {test_support::discovery_test_run_id("mapped-warmup"),
           test_support::discovery_test_run_id("mapped-measurement")},
          {17U}};
}

struct Fixture final {
  Fixture() : Fixture(software_plan()) {}
  explicit Fixture(calibration::MappedDiscoveryPlan input) : plan(std::move(input)) {}
  calibration::MappedDiscoveryPlan plan;
  calibration::MappedDiscoveryLayout layout{calibration::mapped_discovery_layout(plan)};
  platform::OwnerMappingPlan owner{test::software_stack_plan()};
  MemoryOperations record_ops;
  MemoryOperations producer_ops;
  MemoryOperations consumer_ops;
  platform::OwnerMapping<MemoryOperations> records{
      {layout.records_bytes, owner.verified_base_page_bytes, owner.owner_cpu, 0U},
      record_ops};
  platform::OwnerMapping<MemoryOperations> producer{
      {layout.producer_bytes, owner.verified_base_page_bytes, owner.owner_cpu, 0U},
      producer_ops};
  platform::OwnerMapping<MemoryOperations> consumer{
      {layout.consumer_bytes, owner.verified_base_page_bytes, owner.owner_cpu, 0U},
      consumer_ops};
  test_support::DiscoveryTestRelax relax;
  calibration::MappedDiscoveryPreparation<MemoryOperations,
                                          test_support::DiscoveryTestRelax>
      preparation{plan, {records, producer, consumer}, relax};
  test_support::DiscoveryTestClock clock;
  calibration::DiscoveryRingPhaseBackend<test_support::DiscoveryTestClock,
                                         decltype(preparation)>
      backend{plan.session, clock, preparation};

  auto run() -> calibration::DiscoverySessionResult {
    test::SoftwareStackOperations producer_stack_ops;
    test::SoftwareStackOperations consumer_stack_ops;
    platform::MappedWorkerThread producer_stack(owner, producer_stack_ops);
    platform::MappedWorkerThread consumer_stack(owner, consumer_stack_ops);
    calibration::MappedDiscoveryThreads threads(
        calibration::DiscoveryWorkerStacks{producer_stack, consumer_stack});
    calibration::NoDiscoveryControllerObserver observer;
    return calibration::run_discovery_session(plan.session, clock, backend, relax,
                                              observer, threads);
  }
};

auto contains(std::span<std::byte> region, const void* address) -> bool {
  const auto begin = reinterpret_cast<std::uintptr_t>(region.data());
  const auto value = reinterpret_cast<std::uintptr_t>(address);
  return value >= begin && value < begin + region.size();
}

TEST(MappedDiscovery, RealOwnerMappingsAndStacksCompleteBothPhasesAndExactJoin) {
  Fixture fixture;
  const auto result = fixture.run();
  ASSERT_EQ(result.stop, calibration::DiscoverySessionStop::complete);
  EXPECT_EQ(fixture.preparation.status(0U),
            calibration::MappedDiscoveryPreparationStop::ready);
  EXPECT_EQ(fixture.preparation.status(1U),
            calibration::MappedDiscoveryPreparationStop::ready);
  const auto& records = fixture.records.evidence();
  const auto& producer = fixture.producer.evidence();
  const auto& consumer = fixture.consumer.evidence();
  if (!records.after_touch || !producer.after_touch || !consumer.after_touch ||
      !records.read_only) {
    FAIL() << "missing actual owner/protection facts";
    return;
  }
  EXPECT_EQ(records.after_touch->thread_id.return_value,
            producer.after_touch->thread_id.return_value);
  EXPECT_NE(producer.after_touch->thread_id.return_value,
            consumer.after_touch->thread_id.return_value);
  EXPECT_TRUE(records.read_only->zero_return());
  EXPECT_TRUE(contains(fixture.records.mapped_bytes(),
                       fixture.preparation.arena().storage_address()));
  EXPECT_TRUE(contains(fixture.records.mapped_bytes(),
                       fixture.preparation.arena().record_order().data()));
  EXPECT_TRUE(contains(fixture.producer.mapped_bytes(), &fixture.preparation.arena()));
  EXPECT_TRUE(contains(fixture.producer.mapped_bytes(), &fixture.preparation.ring()));
  for (const bool warmup : {true, false}) {
    const auto& p = fixture.preparation.producer_phase(warmup);
    const auto& c = fixture.preparation.consumer_phase(warmup);
    for (const void* address :
         {static_cast<const void*>(&p), static_cast<const void*>(&p.trace),
          static_cast<const void*>(&p.primary),
          static_cast<const void*>(p.primary.snapshot().bytes.data())}) {
      EXPECT_TRUE(contains(fixture.producer.mapped_bytes(), address));
    }
    for (const void* address :
         {static_cast<const void*>(&c), static_cast<const void*>(&c.trace),
          static_cast<const void*>(&c.primary),
          static_cast<const void*>(c.primary.snapshot().bytes.data()),
          static_cast<const void*>(c.drain_rows.data())}) {
      EXPECT_TRUE(contains(fixture.consumer.mapped_bytes(), address));
    }
    EXPECT_EQ(c.last_join.status, calibration::DiscoveryJoinStatus::exact);
    EXPECT_EQ(p.accepted, c.consumed);
    EXPECT_EQ(p.primary.snapshot().completeness,
              storage::StreamCompleteness::sealed_complete);
    EXPECT_EQ(c.primary.snapshot().completeness,
              storage::StreamCompleteness::sealed_complete);
  }
  EXPECT_EQ(fixture.preparation.ring().audit_quiescent().occupied_slots, 0U);
}

TEST(MappedDiscovery, FailedOwnerMappingOrProtectionCancelsPeerBeforeWarmup) {
  for (std::size_t failure = 0U; failure < 4U; ++failure) {
    Fixture fixture;
    fixture.record_ops.reject_binding = failure == 0U;
    fixture.producer_ops.reject_binding = failure == 1U;
    fixture.consumer_ops.reject_binding = failure == 2U;
    fixture.record_ops.reject_protection = failure == 3U;
    const auto result = fixture.run();
    EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::preparation_failure);
    EXPECT_FALSE(result.origins[0U].has_value());
    EXPECT_FALSE(result.origins[1U].has_value());
    EXPECT_EQ(result.warmup[0U].attempts, 0U);
    EXPECT_EQ(result.warmup[1U].attempts, 0U);
    EXPECT_EQ(fixture.preparation.status(failure == 2U ? 1U : 0U),
              failure == 3U
                  ? calibration::MappedDiscoveryPreparationStop::protection_failure
                  : calibration::MappedDiscoveryPreparationStop::mapping_failure);
  }
}

TEST(MappedDiscovery, AlreadyFailedPeerPreventsNewMappingOrOwnerMutation) {
  Fixture fixture;
  fixture.record_ops.reject_binding = true;
  EXPECT_FALSE(fixture.preparation.prepare_producer());
  EXPECT_FALSE(fixture.preparation.prepare_consumer());
  EXPECT_EQ(fixture.preparation.status(1U),
            calibration::MappedDiscoveryPreparationStop::peer_failure);
  EXPECT_EQ(fixture.consumer.evidence().stop, platform::OwnerMappingStop::not_started);
  EXPECT_FALSE(fixture.consumer.evidence().mapping.has_value());
  EXPECT_FALSE(fixture.consumer.evidence().affinity_request.has_value());
}

TEST(MappedDiscovery, MissingPeerHasFinitePreparationBudgetAndCannotBeRetried) {
  auto plan = software_plan();
  plan.session.barrier_poll_limit = 8U;
  Fixture fixture(std::move(plan));
  bool prepared = true;
  std::thread worker([&] { prepared = fixture.preparation.prepare_producer(); });
  worker.join();
  EXPECT_FALSE(prepared);
  EXPECT_EQ(fixture.preparation.status(0U),
            calibration::MappedDiscoveryPreparationStop::wait_exhausted);
  EXPECT_FALSE(fixture.preparation.prepare_producer());
  EXPECT_EQ(fixture.preparation.status(0U),
            calibration::MappedDiscoveryPreparationStop::wait_exhausted);
  EXPECT_EQ(fixture.preparation.status(1U),
            calibration::MappedDiscoveryPreparationStop::not_started);
}

TEST(MappedDiscovery, CallerCannotChangeFrozenGeometryOrControlsAfterConstruction) {
  Fixture fixture;
  const auto session = fixture.plan.session;
  fixture.plan.session.warmup_attempt_capacity =
      std::numeric_limits<std::uint64_t>::max();
  fixture.plan.session.barrier_poll_limit = 0U;
  fixture.plan.arena.capacity = 1U;
  const auto result = calibration::run_discovery_session(
      session, fixture.clock, fixture.backend, fixture.relax);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::complete);
  EXPECT_EQ(fixture.preparation.arena().capacity(), 8U);
  EXPECT_EQ(fixture.preparation.producer_phase(true).trace.attempt_capacity(), 256U);
}

TEST(MappedDiscovery, LayoutRejectsInvalidOrOverflowingProspectiveInputs) {
  for (std::size_t invalid = 0U; invalid < 7U; ++invalid) {
    auto plan = software_plan();
    switch (invalid) {
    case 0U:
      plan.arena.base_page_bytes = 0U;
      break;
    case 1U:
      plan.arena.cache_line_bytes = 3U;
      break;
    case 2U:
      plan.arena.capacity = std::numeric_limits<std::size_t>::max();
      break;
    case 3U:
      plan.session.warmup_attempt_capacity = std::numeric_limits<std::uint64_t>::max();
      break;
    case 4U:
      plan.session.drain_attempt_capacity = std::numeric_limits<std::uint64_t>::max();
      break;
    case 5U:
      plan.run_ids[1U] = plan.run_ids[0U];
      break;
    default:
      plan.session.barrier_poll_limit = 0U;
      break;
    }
    EXPECT_THROW(static_cast<void>(calibration::mapped_discovery_layout(plan)),
                 std::invalid_argument);
  }
}

TEST(MappedDiscovery, RegionSizeAndProducerHomeMismatchRejectBeforePreparation) {
  Fixture fixture;
  for (const bool wrong_size : {true, false}) {
    auto requested = fixture.producer.evidence().requested;
    if (wrong_size) {
      requested.bytes += fixture.plan.arena.base_page_bytes;
    } else {
      requested.requested_node = 1U;
    }
    platform::OwnerMapping replacement(requested, fixture.producer_ops);
    using Preparation = decltype(fixture.preparation);
    EXPECT_THROW(static_cast<void>(Preparation(
                     fixture.plan, {fixture.records, replacement, fixture.consumer},
                     fixture.relax)),
                 std::invalid_argument);
    EXPECT_EQ(replacement.evidence().stop, platform::OwnerMappingStop::not_started);
  }
}

} // namespace
