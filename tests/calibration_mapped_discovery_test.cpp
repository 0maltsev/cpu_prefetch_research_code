#include "cpu_prefetch/calibration/mapped_discovery_preparation.hpp"
#include "cpu_prefetch/calibration/mapped_discovery_runtime.hpp"
#include "cpu_prefetch/platform/thread_monitor.hpp"
#include "discovery_backend_test_support.hpp"
#include "worker_stack_test_support.hpp"

#include <gtest/gtest.h>

#include <cerrno>
#include <chrono>

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
    calibration::DiscoverySessionStorage storage;
    return run(storage);
  }
  auto run(calibration::DiscoverySessionStorage& storage)
      -> calibration::DiscoverySessionResult {
    test::SoftwareStackOperations producer_stack_ops;
    test::SoftwareStackOperations consumer_stack_ops;
    platform::MappedWorkerThread producer_stack(owner, producer_stack_ops);
    platform::MappedWorkerThread consumer_stack(owner, consumer_stack_ops);
    calibration::MappedDiscoveryThreads threads(
        calibration::DiscoveryWorkerStacks{producer_stack, consumer_stack});
    calibration::NoDiscoveryControllerObserver observer;
    return calibration::run_discovery_session(plan.session, clock, backend, relax,
                                              observer, threads, storage);
  }
};

struct RuntimeFixture final {
  using Modules = std::array<platform::ThreadTlsModule, 128U>;
  std::array<Modules, 4U> tls{};
  test_support::DiscoveryTestClock clock;
  test_support::DiscoveryTestRelax relax;
  using Runtime = calibration::MappedDiscoveryRuntime<
      test_support::DiscoveryTestClock, test_support::DiscoveryTestRelax,
      MemoryOperations, test::SoftwareStackOperations>;
  Runtime runtime{software_plan(),
                  {test::software_stack_plan(), test::software_stack_plan()},
                  {{{tls[0U], tls[1U]}}, {{tls[2U], tls[3U]}}},
                  clock,
                  relax};
};

auto contains(std::span<std::byte> region, const void* address) -> bool {
  const auto begin = reinterpret_cast<std::uintptr_t>(region.data());
  const auto value = reinterpret_cast<std::uintptr_t>(address);
  return value >= begin && value < begin + region.size();
}

TEST(MappedDiscovery, MappedControllerOwnsContextAndRetainedCoordinationStorage) {
  auto owner = test::software_stack_plan();
  const auto stack_plan = owner;
  using State = calibration::DiscoverySessionStorage;
  const auto objects_offset =
      (sizeof(State) + alignof(Fixture) - 1U) & ~(alignof(Fixture) - 1U);
  const auto page = owner.verified_base_page_bytes;
  owner.bytes = (objects_offset + sizeof(Fixture) + page - 1U) & ~(page - 1U);
  MemoryOperations operations;
  platform::OwnerMapping control_mapping(owner, operations);
  test::SoftwareStackOperations stack_operations;
  platform::MappedWorkerThread controller(stack_plan, stack_operations);
  struct Context final {
    platform::OwnerMapping<MemoryOperations>& mapping;
    platform::MappedWorkerThread<test::SoftwareStackOperations>& controller;
    std::size_t objects_offset;
    State* state{nullptr};
    Fixture* objects{nullptr};
    bool controller_frame_in_stack{false};
    bool exception{false};
    calibration::DiscoverySessionResult returned{};

    static void run(void* pointer) noexcept {
      auto& self = *static_cast<Context*>(pointer);
      try {
        if (!self.controller.prepared() || !self.mapping.prepare()) {
          return;
        }
        self.controller_frame_in_stack =
            contains(self.controller.body(), __builtin_frame_address(0));
        const auto bytes = self.mapping.mapped_bytes();
        self.state = std::construct_at(reinterpret_cast<State*>(bytes.data()));
        self.objects = std::construct_at(
            reinterpret_cast<Fixture*>(bytes.data() + self.objects_offset));
        self.returned = self.objects->run(*self.state);
      } catch (...) {
        self.exception = true;
      }
    }
  } context{control_mapping, controller, objects_offset};
  ASSERT_TRUE(controller.start(&Context::run, &context));
  controller.join();
  const auto destroy_state = [](State* state) { std::destroy_at(state); };
  const auto destroy_objects = [](Fixture* objects) { std::destroy_at(objects); };
  std::unique_ptr<State, decltype(destroy_state)> state(context.state, destroy_state);
  std::unique_ptr<Fixture, decltype(destroy_objects)> objects(context.objects,
                                                              destroy_objects);
  EXPECT_FALSE(context.exception);
  EXPECT_TRUE(context.controller_frame_in_stack);
  ASSERT_NE(state, nullptr);
  ASSERT_NE(objects, nullptr);
  EXPECT_EQ(context.returned.stop, calibration::DiscoverySessionStop::complete);
  EXPECT_EQ(state->result.stop, context.returned.stop);
  EXPECT_EQ(state->result.origins, context.returned.origins);
  const auto bytes = control_mapping.mapped_bytes();
  EXPECT_TRUE(contains(bytes, &objects->preparation));
  EXPECT_TRUE(contains(bytes, &objects->backend));
  EXPECT_TRUE(contains(bytes, &objects->clock));
  EXPECT_TRUE(contains(bytes, &state->result));
  EXPECT_TRUE(contains(bytes, &state->warmup_barrier));
  EXPECT_TRUE(contains(bytes, &state->measurement_stop));
  EXPECT_TRUE(contains(bytes, &state->measurement_finished));
  EXPECT_EQ(state->measurement_finished.load(), 3U);
  EXPECT_EQ(objects->preparation.consumer_phase(false).last_join.status,
            calibration::DiscoveryJoinStatus::exact);
}

TEST(MappedDiscovery, RuntimeCompositionRunsOnMappedControllerAndRetainsOwnerTls) {
  auto plan = test::software_stack_plan();
  MemoryOperations operations;
  const auto page = plan.verified_base_page_bytes;
  auto object_plan = plan;
  object_plan.bytes = (sizeof(RuntimeFixture) + page - 1U) & ~(page - 1U);
  platform::OwnerMapping mapping(object_plan, operations);
  test::SoftwareStackOperations stack_operations;
  platform::MappedWorkerThread controller(plan, stack_operations);
  struct Context final {
    platform::OwnerMapping<MemoryOperations>& mapping;
    platform::MappedWorkerThread<test::SoftwareStackOperations>& controller;
    RuntimeFixture* objects{nullptr};
    bool exception{false};
    calibration::DiscoverySessionResult result{};
    static void run(void* pointer) noexcept {
      auto& self = *static_cast<Context*>(pointer);
      try {
        if (!self.controller.prepared() || !self.mapping.prepare()) {
          return;
        }
        self.objects = std::construct_at(
            reinterpret_cast<RuntimeFixture*>(self.mapping.mapped_bytes().data()));
        calibration::NoDiscoveryControllerObserver observer;
        self.result = self.objects->runtime.run(observer);
      } catch (...) {
        self.exception = true;
      }
    }
  } context{mapping, controller};
  ASSERT_TRUE(controller.start(&Context::run, &context));
  controller.join();
  const auto destroy = [](RuntimeFixture* objects) { std::destroy_at(objects); };
  std::unique_ptr<RuntimeFixture, decltype(destroy)> objects(context.objects, destroy);
  ASSERT_FALSE(context.exception);
  ASSERT_NE(objects, nullptr);
  auto& runtime = objects->runtime;
  EXPECT_EQ(context.result.stop, calibration::DiscoverySessionStop::complete);
  EXPECT_EQ(runtime.session().result.origins, context.result.origins);
  EXPECT_TRUE(contains(mapping.mapped_bytes(), &runtime.session().warmup_barrier));
  for (std::size_t role = 0U; role < 2U; ++role) {
    EXPECT_EQ(runtime.tls_before_warmup()[role].stop,
              platform::ThreadTlsStop::complete);
    EXPECT_TRUE(platform::same_thread_tls(
        runtime.tls_before_warmup()[role], objects->tls[role],
        runtime.tls_before_measurement()[role], objects->tls[role + 2U]));
  }
  EXPECT_NE(runtime.tls_before_warmup()[0U].fs_base,
            runtime.tls_before_warmup()[1U].fs_base);
  for (const auto region : runtime.worker_regions()) {
    EXPECT_FALSE(region.mapping.empty());
    EXPECT_EQ(region.expected_node, plan.requested_node);
  }
  EXPECT_EQ(runtime.preparation().consumer_phase(false).last_join.status,
            calibration::DiscoveryJoinStatus::exact);
  calibration::NoDiscoveryControllerObserver observer;
  EXPECT_EQ(runtime.run(observer).stop,
            calibration::DiscoverySessionStop::storage_already_used);
}

TEST(MappedDiscovery, RuntimeRejectsAliasedTlsStorageAndDisagreedGeometry) {
  RuntimeFixture fixture;
  auto plan = software_plan();
  auto owner = test::software_stack_plan();
  calibration::DiscoveryRuntimeTlsStorage tls{{{fixture.tls[0U], fixture.tls[1U]}},
                                              {{fixture.tls[2U], fixture.tls[3U]}}};
  auto aliased = tls;
  aliased.before_measurement[1U] = aliased.before_warmup[0U];
  EXPECT_THROW((RuntimeFixture::Runtime(plan, {owner, owner}, aliased, fixture.clock,
                                        fixture.relax)),
               std::invalid_argument);
  auto wrong = owner;
  wrong.verified_base_page_bytes *= 2U;
  EXPECT_THROW((RuntimeFixture::Runtime(plan, {owner, wrong}, tls, fixture.clock,
                                        fixture.relax)),
               std::invalid_argument);
}

TEST(MappedDiscovery, RuntimePreservesPreparationFailureWithoutWarmupOrRetry) {
  RuntimeFixture fixture;
  fixture.runtime.mapping_operations(0U).reject_binding = true;
  calibration::NoDiscoveryControllerObserver observer;
  const auto result = fixture.runtime.run(observer);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::preparation_failure);
  EXPECT_FALSE(result.origins[0U].has_value());
  EXPECT_FALSE(fixture.runtime.records().ready());
  EXPECT_EQ(fixture.runtime.run(observer).stop,
            calibration::DiscoverySessionStop::storage_already_used);
}

TEST(MappedDiscovery, RuntimeRetainsWorkersThroughFinalControlReadback) {
  RuntimeFixture fixture;
  struct Scratch final {
    std::array<char, 4096U> before{};
    std::array<char, 8192U> status{};
    std::array<char, 4096U> after{};
    std::array<unsigned long, 16U> mask{};
    auto view() noexcept -> platform::ThreadMonitorScratch {
      return {before, status, after, mask};
    }
  };
  struct Observer final {
    RuntimeFixture::Runtime& runtime;
    std::array<platform::LinuxThreadMonitorOperations, 2U> operations;
    std::array<platform::PreparedThreadMonitor, 2U> monitors{
        platform::PreparedThreadMonitor(operations[0U]),
        platform::PreparedThreadMonitor(operations[1U])};
    std::array<Scratch, 2U> preparation{};
    std::array<std::array<Scratch, 2U>, 2U> scratch{};
    std::array<std::array<platform::ThreadControlSample, 2U>, 2U> samples{};
    auto before_phase(calibration::DiscoverySessionPhase phase) noexcept -> bool {
      if (phase == calibration::DiscoverySessionPhase::measurement) {
        return true;
      }
      for (std::size_t role = 0U; role < 2U; ++role) {
        const auto identity = runtime.tls_before_warmup()[role].thread_before;
        if (!identity.has_value() || !identity->nonnegative_return() ||
            identity->return_value <= 0 ||
            identity->return_value > std::numeric_limits<int>::max() ||
            !monitors[role].prepare(static_cast<int>(identity->return_value),
                                    preparation[role].view())) {
          return false;
        }
      }
      return true;
    }
    auto during_phase(calibration::DiscoverySessionPhase,
                      calibration::DiscoveryObservationWindow,
                      const std::atomic<std::uint32_t>&) const noexcept -> bool {
      return true;
    }
    auto after_phase(calibration::DiscoverySessionPhase phase) noexcept -> bool {
      // Model a delayed controller readback after both capture loops stopped.
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      const auto index = static_cast<std::size_t>(phase);
      bool passed = true;
      for (std::size_t role = 0U; role < 2U; ++role) {
        samples[index][role] = monitors[role].sample(scratch[index][role].view());
        passed = samples[index][role].succeeded() && passed;
      }
      return passed;
    }
  } observer{fixture.runtime, {}};
  const auto result = fixture.runtime.run(observer);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::complete);
  for (const auto& phase : observer.samples) {
    for (const auto& sample : phase) {
      EXPECT_TRUE(sample.succeeded());
    }
  }
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
