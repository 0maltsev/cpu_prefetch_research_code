#include "cpu_prefetch/calibration/pilot_scheduled_capture.hpp"
#include "discovery_backend_test_support.hpp"

#include <gtest/gtest.h>

#include <atomic>
#include <cstdlib>
#include <memory>
#include <new>
#include <thread>

#ifndef CPU_PREFETCH_PILOT_ALLOCATION_HOOK
#define CPU_PREFETCH_PILOT_ALLOCATION_HOOK 1
#endif

#if CPU_PREFETCH_PILOT_ALLOCATION_HOOK
namespace {
std::atomic<std::size_t> allocations{0U};
thread_local bool watch_allocations = false;
std::atomic<std::size_t> deallocations{0U};
void counted_free(void* pointer) noexcept {
  if (pointer != nullptr && watch_allocations) {
    deallocations.fetch_add(1U, std::memory_order_relaxed);
  }
  std::free(pointer);
}
} // namespace

// Separate executable: count worker allocations only after cold preparation.
void* operator new(std::size_t size) {
  if (watch_allocations) {
    allocations.fetch_add(1U, std::memory_order_relaxed);
  }
  if (void* memory = std::malloc(std::max(size, std::size_t{1U})); memory != nullptr) {
    return memory;
  }
  throw std::bad_alloc();
}
void* operator new[](std::size_t size) { return ::operator new(size); }
void* operator new(std::size_t size, const std::nothrow_t&) noexcept {
  if (watch_allocations) {
    allocations.fetch_add(1U, std::memory_order_relaxed);
  }
  return std::malloc(std::max(size, std::size_t{1U}));
}
void* operator new[](std::size_t size, const std::nothrow_t& tag) noexcept {
  return ::operator new(size, tag);
}
void* operator new(std::size_t size, std::align_val_t alignment) {
  if (watch_allocations) {
    allocations.fetch_add(1U, std::memory_order_relaxed);
  }
  void* memory = nullptr;
  if (posix_memalign(&memory, static_cast<std::size_t>(alignment),
                     std::max(size, std::size_t{1U})) == 0) {
    return memory;
  }
  throw std::bad_alloc();
}
void* operator new[](std::size_t size, std::align_val_t alignment) {
  return ::operator new(size, alignment);
}
void* operator new(std::size_t size, std::align_val_t alignment,
                   const std::nothrow_t&) noexcept {
  if (watch_allocations) {
    allocations.fetch_add(1U, std::memory_order_relaxed);
  }
  void* memory = nullptr;
  return posix_memalign(&memory, static_cast<std::size_t>(alignment),
                        std::max(size, std::size_t{1U})) == 0
             ? memory
             : nullptr;
}
void* operator new[](std::size_t size, std::align_val_t alignment,
                     const std::nothrow_t& tag) noexcept {
  return ::operator new(size, alignment, tag);
}
void operator delete(void* pointer) noexcept { counted_free(pointer); }
void operator delete[](void* pointer) noexcept { counted_free(pointer); }
void operator delete(void* pointer, std::size_t) noexcept { counted_free(pointer); }
void operator delete[](void* pointer, std::size_t) noexcept { counted_free(pointer); }
void operator delete(void* pointer, std::align_val_t) noexcept {
  counted_free(pointer);
}
void operator delete[](void* pointer, std::align_val_t) noexcept {
  counted_free(pointer);
}
void operator delete(void* pointer, std::size_t, std::align_val_t) noexcept {
  counted_free(pointer);
}
void operator delete[](void* pointer, std::size_t, std::align_val_t) noexcept {
  counted_free(pointer);
}
void operator delete(void* pointer, const std::nothrow_t&) noexcept {
  counted_free(pointer);
}
void operator delete[](void* pointer, const std::nothrow_t&) noexcept {
  counted_free(pointer);
}
void operator delete(void* pointer, std::align_val_t, const std::nothrow_t&) noexcept {
  counted_free(pointer);
}
void operator delete[](void* pointer, std::align_val_t,
                       const std::nothrow_t&) noexcept {
  counted_free(pointer);
}
#endif

#if !CPU_PREFETCH_PILOT_ALLOCATION_HOOK
namespace {
thread_local bool watch_allocations = false;
}
#endif

namespace {
using namespace cpu_prefetch;
namespace c = calibration;
namespace w = workload;
namespace s = storage;
namespace l = lifecycle;

struct Shared final {
  w::EventArena arena{
      {64U, 64U, 4096U, w::MasterSeed::from_hex(std::string(64U, 'a')), "pilot-test"}};
  queue::RingSpscQueue ring{{64U}, {64U}};
  const std::array<std::size_t, 65U> order = [] {
    std::array<std::size_t, 65U> result{};
    for (std::size_t i = 0U; i < result.size(); ++i)
      result[i] = (i * 17U) % result.size();
    return result;
  }();
  queue::LinkedSpscQueue linked{{64U}, {64U}, {4096U}, order};
  c::PilotSharedData data;
  explicit Shared(c::PilotContextKey key = {protocol::Placement::near,
                                            protocol::WorkingSetClass::l2_resident})
      : data(key, arena, ring, linked) {}
};

struct Phase final {
  protocol::RunId id;
  s::RawStreamStorageRequirements size;
  queue::detail::AlignedBlock producer_bytes, consumer_bytes;
  s::ProducerObservationStream producer;
  s::ConsumerObservationStream consumer;
  c::FormalServiceProducerPhase produced;
  c::FormalServiceConsumerPhase consumed;
  explicit Phase(std::string name)
      : id(test_support::discovery_test_run_id(std::move(name))),
        size(s::raw_stream_storage_requirements(id, 128U, 128U)),
        producer_bytes(size.producer_bytes, 64U),
        consumer_bytes(size.consumer_bytes, 64U),
        producer(id, 128U, {producer_bytes.data(), size.producer_bytes}),
        consumer(id, 128U, {consumer_bytes.data(), size.consumer_bytes}),
        produced{producer, s::make_row_layout(id.value())},
        consumed{consumer, s::make_row_layout(id.value()), {17U}, {17U}} {}
};

struct Owners final {
  std::array<std::thread::id, 2U> threads;
  std::array<unsigned, 2U> resets{};
  bool reject_reset{false};
  auto prepare_producer() noexcept -> bool {
    watch_allocations = true;
    threads[0U] = std::this_thread::get_id();
    return true;
  }
  auto prepare_consumer() noexcept -> bool {
    watch_allocations = true;
    threads[1U] = std::this_thread::get_id();
    return true;
  }
  auto before_measurement_producer() noexcept -> bool {
    ++resets[0U];
    return !reject_reset && threads[0U] == std::this_thread::get_id();
  }
  auto before_measurement_consumer() noexcept -> bool {
    ++resets[1U];
    return !reject_reset && threads[1U] == std::this_thread::get_id();
  }
};

struct Clock final {
  std::atomic<std::uint64_t> next{1U};
  auto origin() const noexcept -> timing::ClockOrigin { return {0U}; }
  auto read() noexcept -> timing::ClockReadResult {
    const auto value = next.fetch_add(1U);
    return {timing::ClockReadStatus::ok, {value, value * 1000U}};
  }
};

struct Threads final {
  std::array<std::thread, 2U> threads;
  std::array<unsigned, 2U> starts{};
  auto start(c::RingWorker role, platform::WorkerEntry entry, void* context) -> bool {
    const auto index = role == c::RingWorker::producer ? 0U : 1U;
    ++starts[index];
    threads[index] = std::thread([entry, context] {
      entry(context);
      watch_allocations = false;
    });
    return true;
  }
  auto prepared(c::RingWorker) const noexcept -> bool { return true; }
  void join() {
    for (auto& thread : threads)
      if (thread.joinable())
        thread.join();
  }
};

struct Emitter final {
  std::atomic<unsigned> attempts{0U};
  bool gate_consumer{false};
  void ring_producer_write(const void*) noexcept { attempts.fetch_add(1U); }
  void ring_consumer_read(const void*) noexcept {
    if (gate_consumer) {
      for (unsigned poll = 0U; poll < 10'000'000U && attempts.load() < 66U; ++poll)
        std::this_thread::yield();
    }
  }
  void successor_header(const void*) noexcept {}
};

struct Observer final {
  Emitter& emitter;
  bool reject_measurement{false};
  auto before_phase(c::ServicePhase phase) noexcept -> bool {
    watch_allocations = true;
    emitter.attempts.store(0U);
    return !reject_measurement || phase != c::ServicePhase::measurement;
  }
  auto during_phase(c::ServicePhase, c::ServiceWindow,
                    const std::atomic<std::uint32_t>&) const noexcept -> bool {
    return true;
  }
  auto after_phase(c::ServicePhase phase) const noexcept -> bool {
    if (phase == c::ServicePhase::measurement)
      watch_allocations = false;
    return true;
  }
};

struct Input final {
  Phase warmup{"pilot-test-warmup"}, measurement{"pilot-test-measurement"};
  std::array<protocol::RunId, 2U> ids{warmup.id, measurement.id};
  const std::array<std::uint64_t, 96U> zero{};
  c::ServiceSessionPlan bounds{
      {{{5'000'000'000'000U, 128U, 1'000'000U, 100'000'000'000U},
        {1'000'000'000'000U, 128U, 1'000'000U, 100'000'000'000U}}},
      10'000'000U};
  std::array<c::ScheduledPhasePlan, 2U> phases{
      {{0U, 5'000'000'000'000U, zero.size(),
        protocol::ScheduleId::parse("pilot-warmup", "$test").value(),
        protocol::NamespaceId::parse("pilot-warmup-seed", "$test").value()},
       {0U, 1'000'000'000'000U, zero.size(),
        protocol::ScheduleId::parse("pilot-measurement", "$test").value(),
        protocol::NamespaceId::parse("pilot-measurement-seed", "$test").value()}}};
  c::ScheduledSessionPlan plan{bounds, phases};
  // The two immutable sources are separate even when their test values coincide.
  const std::array<std::uint64_t, 96U> measurement_zero{};
  auto sources() const -> std::array<l::PreparedScheduleView, 2U> {
    return {
        {{zero, 0U, 5'000'000'000'000U}, {measurement_zero, 0U, 1'000'000'000'000U}}};
  }
  auto buffers() -> c::PilotPhaseBuffers {
    return {{{&warmup.produced, &measurement.produced}},
            {{&warmup.consumed, &measurement.consumed}}};
  }
};

template <protocol::QueuePackage Kind>
auto run(Shared& shared, Input& input, Owners& owners, Emitter& emitter,
         Observer& observer) -> c::PilotScheduledCaptureResult {
  using Preparation = c::PilotScheduledPreparation<Kind, Emitter, Owners>;
  const auto distance = w::resolve_calibrated_ring_distance({64U, 64U, sizeof(void*)},
                                                            2U, "software-only-Q16a");
  Preparation preparation(shared.data, input.plan, input.ids, input.buffers(),
                          input.sources(), owners, emitter, &distance);
  Clock clock;
  Threads threads;
  test_support::DiscoveryTestRelax relax;
  alignas(64) std::array<std::byte, 128U> lines{};
  l::TerminationControl warmup{{64U}, std::span(lines).first(64U)};
  l::TerminationControl measurement{{64U}, std::span(lines).last(64U)};
  c::ScheduledSessionStorage storage{{warmup, measurement}};
  auto result = c::run_pilot_scheduled_capture(input.plan, clock, preparation, relax,
                                               observer, threads, storage);
  watch_allocations = false;
  EXPECT_EQ(threads.starts, (std::array<unsigned, 2U>{1U, 1U}));
  return result;
}

template <protocol::QueuePackage Kind> void check_package(Shared& shared) {
  Input input;
  Owners owners;
  Emitter emitter;
  Observer observer{emitter};
  const auto* arena = shared.arena.storage_address();
  const auto* nodes = shared.linked.node_arena_base();
  const auto content = shared.arena.content_checksum();
  const auto result = run<Kind>(shared, input, owners, emitter, observer);
  ASSERT_EQ(result.session.lifecycle.stop, c::ServiceSessionStop::complete);
  EXPECT_TRUE(result.initial_queue_reset);
  EXPECT_EQ(owners.resets, (std::array<unsigned, 2U>{1U, 1U}));
  EXPECT_EQ(shared.arena.storage_address(), arena);
  EXPECT_EQ(shared.linked.node_arena_base(), nodes);
  EXPECT_EQ(shared.arena.content_checksum(), content);
  for (std::size_t index = 0U; index < 2U; ++index) {
    const auto& raw = result.raw[index];
    EXPECT_EQ(raw.producer.completeness, s::StreamCompleteness::sealed_complete);
    EXPECT_EQ(raw.consumer.completeness, s::StreamCompleteness::sealed_complete);
    EXPECT_EQ(raw.producer.row_count, 96U);
    EXPECT_EQ(raw.producer.row_count,
              result.session.lifecycle.phases[index].producer.attempted);
    EXPECT_EQ(raw.consumer.row_count,
              result.session.lifecycle.phases[index].consumer.consumed);
    EXPECT_EQ(raw.run_id, input.ids[index].value());
    EXPECT_EQ(raw.producer.bytes.data(), index == 0U
                                             ? input.warmup.producer_bytes.data()
                                             : input.measurement.producer_bytes.data());
  }
  EXPECT_NE(result.raw[0U].producer.bytes.data(), result.raw[1U].producer.bytes.data());
  EXPECT_NE(result.raw[0U].run_id, result.raw[1U].run_id);
}

TEST(PilotScheduledCapture, AllFiveTreatmentsRetainBothPhasesInTheSameContext) {
  Shared shared;
  check_package<protocol::QueuePackage::r0>(shared);
  check_package<protocol::QueuePackage::r1>(shared);
  check_package<protocol::QueuePackage::r2>(shared);
  check_package<protocol::QueuePackage::l0>(shared);
  check_package<protocol::QueuePackage::l1>(shared);
}

TEST(PilotScheduledCapture, MeasurementObservationFailureKeepsCompletedWarmupBytes) {
  Shared shared;
  Input input;
  Owners owners;
  Emitter emitter;
  Observer observer{emitter, true};
  const auto result =
      run<protocol::QueuePackage::r0>(shared, input, owners, emitter, observer);
  EXPECT_EQ(result.session.lifecycle.stop, c::ServiceSessionStop::observation_failure);
  EXPECT_EQ(result.raw[0U].producer.completeness,
            s::StreamCompleteness::sealed_complete);
  EXPECT_EQ(result.raw[0U].producer.row_count, 96U);
  EXPECT_EQ(result.raw[1U].producer.completeness,
            s::StreamCompleteness::sealed_incomplete);
  EXPECT_EQ(result.raw[1U].producer.row_count, 0U);
}

TEST(PilotScheduledCapture, RejectedOwnerResetKeepsWarmupAndDoesNotReleaseMeasurement) {
  Shared shared;
  Input input;
  Owners owners;
  owners.reject_reset = true;
  Emitter emitter;
  Observer observer{emitter};
  const auto result =
      run<protocol::QueuePackage::r0>(shared, input, owners, emitter, observer);
  EXPECT_EQ(result.session.lifecycle.stop, c::ServiceSessionStop::reset_failure);
  EXPECT_FALSE(result.session.lifecycle.phases[1U].released);
  EXPECT_EQ(result.raw[0U].producer.completeness,
            s::StreamCompleteness::sealed_complete);
}

TEST(PilotScheduledCapture, FullOutcomesRemainReconciledInBothRetainedPhases) {
  Shared shared;
  Input input;
  Owners owners;
  Emitter emitter;
  emitter.gate_consumer = true;
  Observer observer{emitter};
  const auto result =
      run<protocol::QueuePackage::r1>(shared, input, owners, emitter, observer);
  ASSERT_EQ(result.session.lifecycle.stop, c::ServiceSessionStop::complete);
  for (std::size_t phase = 0U; phase < 2U; ++phase) {
    const auto& p = result.session.lifecycle.phases[phase];
    EXPECT_GT(p.producer.full, 0U);
    EXPECT_EQ(p.producer.accepted + p.producer.full, 96U);
    EXPECT_EQ(p.producer.accepted, p.consumer.consumed);
    EXPECT_EQ(result.raw[phase].producer.row_count, 96U);
  }
}

TEST(PilotScheduledCapture, AliasedWarmupAndMeasurementStorageIsRejectedBeforeWorkers) {
  Shared shared;
  Input input;
  Owners owners;
  Emitter emitter;
  using Preparation =
      c::PilotScheduledPreparation<protocol::QueuePackage::r0, Emitter, Owners>;
  auto buffers = input.buffers();
  buffers.producer[1U] = buffers.producer[0U];
  EXPECT_THROW((Preparation{shared.data, input.plan, input.ids, buffers,
                            input.sources(), owners, emitter}),
               std::invalid_argument);
  auto sources = input.sources();
  sources[0U].deadline_ticks = {
      reinterpret_cast<const std::uint64_t*>(input.warmup.producer_bytes.data()),
      input.zero.size()};
  EXPECT_THROW((Preparation{shared.data, input.plan, input.ids, input.buffers(),
                            sources, owners, emitter}),
               std::invalid_argument);
  std::array<std::byte, 96U * sizeof(std::uint64_t) + 8U> unaligned{};
  sources = input.sources();
  sources[0U].deadline_ticks = {
      reinterpret_cast<const std::uint64_t*>(unaligned.data() + 1U), input.zero.size()};
  EXPECT_THROW((Preparation{shared.data, input.plan, input.ids, input.buffers(),
                            sources, owners, emitter}),
               std::invalid_argument);
}

TEST(PilotSharedData, ExactlySixPlacementWorkingSetContextsWithNoLoadOrTreatmentKey) {
  c::PilotContextRegistry registry;
  std::array<std::unique_ptr<Shared>, 6U> data;
  std::size_t index = 0U;
  for (const auto placement : {protocol::Placement::near, protocol::Placement::far}) {
    for (const auto working : {protocol::WorkingSetClass::l2_resident,
                               protocol::WorkingSetClass::llc_resident,
                               protocol::WorkingSetClass::beyond_llc}) {
      data[index] = std::make_unique<Shared>(c::PilotContextKey{placement, working});
      ASSERT_TRUE(registry.bind(data[index]->data));
      EXPECT_EQ(registry.find({placement, working}), &data[index]->data);
      EXPECT_TRUE(registry.bind(data[index]->data));
      ++index;
    }
  }
  EXPECT_TRUE(registry.complete());
  EXPECT_EQ(registry.size(), 6U);
  Shared replacement;
  EXPECT_FALSE(registry.bind(replacement.data));
  EXPECT_EQ(registry.find({protocol::Placement::stage_c_other,
                           protocol::WorkingSetClass::l2_resident}),
            nullptr);
}

TEST(PilotScheduledCapture,
     NoAllocationOrReleaseFromPreparedOwnersThroughResetAndMeasurement) {
#if CPU_PREFETCH_PILOT_ALLOCATION_HOOK
  Shared shared;
  const auto allocated = allocations.load();
  const auto freed = deallocations.load();
  check_package<protocol::QueuePackage::r0>(shared);
  check_package<protocol::QueuePackage::r1>(shared);
  check_package<protocol::QueuePackage::r2>(shared);
  check_package<protocol::QueuePackage::l0>(shared);
  check_package<protocol::QueuePackage::l1>(shared);
  EXPECT_EQ(allocations.load(), allocated);
  EXPECT_EQ(deallocations.load(), freed);
#else
  GTEST_SKIP()
      << "Clang TSan owns allocation interceptors; other matrices prove this gate";
#endif
}

TEST(PilotScheduledCapture,
     BadPreparedSourceReleasesNeitherPhaseAndRetainsIncompleteEvidence) {
  Shared shared;
  Input input;
  Owners owners;
  Emitter emitter;
  Observer observer{emitter};
  auto measured = input.measurement_zero;
  measured.back() = 1'000'000'000'000U; // excluded endpoint
  auto sources = input.sources();
  sources[1U].deadline_ticks = measured;
  using Preparation =
      c::PilotScheduledPreparation<protocol::QueuePackage::r0, Emitter, Owners>;
  Preparation preparation(shared.data, input.plan, input.ids, input.buffers(), sources,
                          owners, emitter);
  EXPECT_THROW(static_cast<void>(preparation.schedule(c::ServicePhase::warmup)),
               std::logic_error);
  Clock clock;
  Threads threads;
  test_support::DiscoveryTestRelax relax;
  l::TerminationControl warmup{{64U}}, measurement{{64U}};
  c::ScheduledSessionStorage storage{{warmup, measurement}};
  const auto result = c::run_pilot_scheduled_capture(input.plan, clock, preparation,
                                                     relax, observer, threads, storage);
  watch_allocations = false;
  EXPECT_EQ(result.session.lifecycle.stop, c::ServiceSessionStop::invalid_plan);
  EXPECT_FALSE(result.session.lifecycle.phases[0U].released);
  EXPECT_FALSE(result.session.lifecycle.phases[1U].released);
  for (const auto& raw : result.raw) {
    EXPECT_EQ(raw.producer.completeness, s::StreamCompleteness::sealed_incomplete);
    EXPECT_EQ(raw.consumer.completeness, s::StreamCompleteness::sealed_incomplete);
    EXPECT_EQ(raw.producer.row_count, 0U);
  }
}

TEST(PilotScheduledCapture,
     UsedSessionStorageRejectsAnotherCaptureWithoutOverwritingWarmup) {
  Shared shared;
  Input input;
  Owners owners;
  Emitter emitter;
  Observer observer{emitter};
  using Preparation =
      c::PilotScheduledPreparation<protocol::QueuePackage::r0, Emitter, Owners>;
  Preparation preparation(shared.data, input.plan, input.ids, input.buffers(),
                          input.sources(), owners, emitter);
  Clock clock;
  Threads threads;
  test_support::DiscoveryTestRelax relax;
  l::TerminationControl warmup{{64U}}, measurement{{64U}};
  c::ScheduledSessionStorage storage{{warmup, measurement}};
  const auto first = c::run_pilot_scheduled_capture(input.plan, clock, preparation,
                                                    relax, observer, threads, storage);
  watch_allocations = false;
  ASSERT_EQ(first.session.lifecycle.stop, c::ServiceSessionStop::complete);
  const std::vector<std::byte> original(first.raw[0U].producer.bytes.begin(),
                                        first.raw[0U].producer.bytes.end());
  const auto event = queue::EventPointer::from(shared.arena.select({0U}).record);
  if (!event) {
    FAIL() << "software fixture event pointer is invalid";
    return;
  }
  ASSERT_EQ(shared.ring.try_enqueue(*event), queue::EnqueueResult::accepted);
  const auto again = c::run_pilot_scheduled_capture(input.plan, clock, preparation,
                                                    relax, observer, threads, storage);
  EXPECT_EQ(again.session.lifecycle.stop, c::ServiceSessionStop::storage_already_used);
  EXPECT_EQ(threads.starts, (std::array<unsigned, 2U>{1U, 1U}));
  EXPECT_EQ(original, std::vector<std::byte>(again.raw[0U].producer.bytes.begin(),
                                             again.raw[0U].producer.bytes.end()));
  EXPECT_EQ(shared.ring.try_dequeue().event, event->get());
}

TEST(PilotScheduledCapture, R2RequiresDistanceForThisSharedGeometry) {
  Shared shared;
  Input input;
  Owners owners;
  Emitter emitter;
  using Preparation =
      c::PilotScheduledPreparation<protocol::QueuePackage::r2, Emitter, Owners>;
  EXPECT_THROW((Preparation{shared.data, input.plan, input.ids, input.buffers(),
                            input.sources(), owners, emitter}),
               std::invalid_argument);
  const auto incompatible = w::resolve_calibrated_ring_distance(
      {128U, 128U, sizeof(void*)}, 2U, "incompatible-software-fixture");
  EXPECT_THROW((Preparation{shared.data, input.plan, input.ids, input.buffers(),
                            input.sources(), owners, emitter, &incompatible}),
               std::invalid_argument);
}

TEST(PilotSharedData, RegistryRejectsPartiallyOverlappingArenasAtDifferentBases) {
  queue::detail::AlignedBlock bytes(12'288U, 4096U);
  const auto seed = w::MasterSeed::from_hex(std::string(64U, 'b'));
  w::EventArena a({128U, 64U, 4096U, seed, "overlap-a"}, {bytes.data(), 8192U});
  w::EventArena b({128U, 64U, 4096U, seed, "overlap-b"}, {bytes.data() + 4096U, 8192U});
  queue::RingSpscQueue r1({128U}, {64U}), r2({128U}, {64U});
  std::array<std::size_t, 129U> order{};
  for (std::size_t i = 0U; i < order.size(); ++i)
    order[i] = i;
  queue::LinkedSpscQueue l1({128U}, {64U}, {4096U}, order),
      l2({128U}, {64U}, {4096U}, order);
  c::PilotSharedData first(
      {protocol::Placement::near, protocol::WorkingSetClass::l2_resident}, a, r1, l1);
  c::PilotSharedData second(
      {protocol::Placement::far, protocol::WorkingSetClass::l2_resident}, b, r2, l2);
  c::PilotContextRegistry registry;
  ASSERT_TRUE(registry.bind(first));
  EXPECT_FALSE(registry.bind(second));
}
TEST(PilotScheduledCapture, UndrainedPriorDataBlocksWarmupWithoutDiscardingTheEvent) {
  Shared shared;
  Input input;
  Owners owners;
  Emitter emitter;
  Observer observer{emitter};
  const auto event = queue::EventPointer::from(shared.arena.select({0U}).record);
  if (!event) {
    FAIL() << "software fixture event pointer is invalid";
    return;
  }
  ASSERT_EQ(shared.ring.try_enqueue(*event), queue::EnqueueResult::accepted);
  const auto result =
      run<protocol::QueuePackage::r0>(shared, input, owners, emitter, observer);
  EXPECT_FALSE(result.initial_queue_reset);
  EXPECT_FALSE(result.session.lifecycle.phases[0U].released);
  EXPECT_EQ(result.session.lifecycle.stop, c::ServiceSessionStop::observation_failure);
  EXPECT_EQ(result.raw[0U].producer.row_count, 0U);
  EXPECT_EQ(result.raw[0U].producer.completeness,
            s::StreamCompleteness::sealed_incomplete);
  EXPECT_EQ(shared.ring.try_dequeue().event, event->get());
}

} // namespace
