#include "cpu_prefetch/calibration/service_session.hpp"
#include "cpu_prefetch/storage/capture_backend.hpp"
#include "cpu_prefetch/workload/packages.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cstdlib>
#include <limits>
#include <memory>
#include <new>
#include <stdexcept>
#include <thread>

#ifndef CPU_PREFETCH_SERVICE_ALLOCATION_HOOK
#define CPU_PREFETCH_SERVICE_ALLOCATION_HOOK 1
#endif

#if CPU_PREFETCH_SERVICE_ALLOCATION_HOOK
namespace {
std::atomic<std::size_t> allocations{0U};
thread_local bool watch_allocations = false;
std::atomic<std::size_t> deallocations{0U};
void counted_free(void* pointer) noexcept {
  if (pointer != nullptr) {
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

#if !CPU_PREFETCH_SERVICE_ALLOCATION_HOOK
namespace {
thread_local bool watch_allocations = false;
}
#endif

namespace {
namespace c = cpu_prefetch::calibration;
namespace l = cpu_prefetch::lifecycle;
namespace q = cpu_prefetch::queue;
namespace w = cpu_prefetch::workload;
namespace s = cpu_prefetch::storage;
namespace t = cpu_prefetch::timing;

constexpr c::ServiceSessionPlan kPlan{{{{20'000U, 30'000U, 300'000U, 1'000'000U},
                                        {20'000U, 30'000U, 300'000U, 1'000'000U}}},
                                      5'000'000U};
class Clock final {
public:
  auto origin() const noexcept -> t::ClockOrigin { return {0U}; }
  auto read() noexcept -> t::ClockReadResult {
    const auto now = next.fetch_add(1U, std::memory_order_relaxed);
    return {fail.load(std::memory_order_relaxed) ? t::ClockReadStatus::call_failed
                                                 : t::ClockReadStatus::ok,
            {0U, now}};
  }
  std::atomic<std::uint64_t> next{1U};
  std::atomic<bool> fail{false};
};
struct Relax final {
  void relax() const noexcept { std::this_thread::yield(); }
};
class Threads final {
public:
  bool reject_consumer{false};
  std::array<std::thread, 2U> owners;
  std::array<unsigned, 2U> starts{};
  auto start(c::RingWorker role, cpu_prefetch::platform::WorkerEntry entry,
             void* context) -> bool {
    const auto index = role == c::RingWorker::producer ? 0U : 1U;
    ++starts[index];
    if (index == 1U && reject_consumer) {
      return false;
    }
    owners[index] = std::thread([entry, context] {
      entry(context);
      watch_allocations = false;
    });
    return true;
  }
  auto prepared(c::RingWorker) const noexcept -> bool { return true; }
  void join() {
    for (auto& thread : owners) {
      if (thread.joinable()) {
        thread.join();
      }
    }
  }
};
struct Observer final {
  int reject_before{-1};
  int reject_during{-1};
  int reject_after{-1};
  std::array<unsigned, 2U> before{}, during{}, after{};
  auto before_phase(c::ServicePhase phase) -> bool {
    const auto i = static_cast<unsigned>(phase);
    ++before[i];
    return static_cast<int>(i) != reject_before;
  }
  auto during_phase(c::ServicePhase phase, c::ServiceWindow,
                    const std::atomic<std::uint32_t>&) -> bool {
    const auto i = static_cast<unsigned>(phase);
    ++during[i];
    return static_cast<int>(i) != reject_during;
  }
  auto after_phase(c::ServicePhase phase) -> bool {
    const auto i = static_cast<unsigned>(phase);
    ++after[i];
    return static_cast<int>(i) != reject_after;
  }
};
struct Emitter final {
  std::atomic<unsigned> producer{0U}, consumer{0U}, successor{0U};
  void ring_producer_write(const void*) noexcept { producer.fetch_add(1U); }
  void ring_consumer_read(const void*) noexcept { consumer.fetch_add(1U); }
  void successor_header(const void*) noexcept { successor.fetch_add(1U); }
};
auto run_id(const char* value) -> cpu_prefetch::protocol::RunId {
  return cpu_prefetch::protocol::RunId::parse(value, "$test").value();
}
struct Phase final {
  s::ProducerObservationStream producer;
  s::ConsumerObservationStream consumer;
  w::ConsumerState checksum{0U};
  explicit Phase(const char* id)
      : producer(run_id(id), 30'000U), consumer(run_id(id), 30'000U) {}
};
struct Faults final {
  bool prepare{false};
  bool prepare_exception{false};
  bool validation{false};
  bool queue_reset{false};
  bool producer_reset{false};
  bool consumer_reset{false};
};

template <typename Queue, typename Package> class Backend final {
public:
  Backend(Clock& clock, Queue& queue, Package& package, w::EventArena& arena,
          Faults faults = {})
      : warmup("service-warmup"), measurement("service-measurement"),
        warmup_capture(clock, arena, package, warmup.checksum, warmup.producer,
                       warmup.consumer),
        measurement_capture(clock, arena, package, measurement.checksum,
                            measurement.producer, measurement.consumer),
        queue_(queue), arena_(arena), faults_(faults),
        arena_address_(arena.storage_address()),
        initial_hash_(arena.content_checksum()) {}
  auto phase(c::ServicePhase phase) noexcept
      -> s::CapturingObservationBackend<Clock, Package>& {
    return phase == c::ServicePhase::warmup ? warmup_capture : measurement_capture;
  }
  auto prepare_producer() -> bool {
    owner[0U] = std::this_thread::get_id();
    ++prepared[0U];
    const bool ready =
        warmup.producer.prepare_for_owner() && measurement.producer.prepare_for_owner();
    watch_allocations = true;
    return ready && !faults_.prepare;
  }
  auto prepare_consumer() -> bool {
    owner[1U] = std::this_thread::get_id();
    ++prepared[1U];
    if (faults_.prepare_exception) {
      throw std::runtime_error("cold preparation exception");
    }
    const bool ready =
        warmup.consumer.prepare_for_owner() && measurement.consumer.prepare_for_owner();
    watch_allocations = true;
    return ready;
  }
  auto reset_producer() noexcept -> bool {
    ++reset[0U];
    return owner[0U] == std::this_thread::get_id() && !faults_.producer_reset;
  }
  auto reset_consumer() noexcept -> bool {
    ++reset[1U];
    measurement.checksum = {0U};
    return owner[1U] == std::this_thread::get_id() && !faults_.consumer_reset;
  }
  auto reset_quiescent() -> bool {
    ++queue_resets;
    watch_allocations = true;
    const bool good = queue_.reset_quiescent();
    watch_allocations = false;
    if constexpr (requires { queue_.audit_quiescent().recycler_order; }) {
      const auto audit = queue_.audit_quiescent();
      reset_shape = audit.queued_events == 0U &&
                    audit.reachable_order == std::vector<std::size_t>{0U} &&
                    audit.recycler_order ==
                        std::vector<std::size_t>{1U, 2U, 3U, 4U, 5U, 6U, 7U, 8U};
    } else {
      reset_shape = queue_.audit_quiescent().occupied_slots == 0U;
    }
    return good && reset_shape && !faults_.queue_reset;
  }
  auto validate_quiescent(c::ServicePhase phase, const c::ServicePhaseResult& result)
      -> bool {
    auto& data = phase == c::ServicePhase::warmup ? warmup : measurement;
    return !faults_.validation && arena_.storage_address() == arena_address_ &&
           arena_.content_checksum() == initial_hash_ &&
           data.producer.snapshot().row_count == result.producer.attempted &&
           data.consumer.snapshot().row_count == result.consumer.consumed;
  }
  Phase warmup, measurement;
  s::CapturingObservationBackend<Clock, Package> warmup_capture, measurement_capture;
  std::array<std::thread::id, 2U> owner;
  std::array<unsigned, 2U> prepared{}, reset{};
  unsigned queue_resets{0U};
  bool reset_shape{false};

private:
  Queue& queue_;
  w::EventArena& arena_;
  Faults faults_;
  const std::byte* arena_address_;
  w::Sha256Digest initial_hash_;
};

struct Fixture final {
  Clock clock;
  Relax relax;
  Observer observer;
  Threads threads;
  l::TerminationControl warmup_arrivals{{64U}}, measurement_arrivals{{64U}};
  c::ServiceSessionStorage storage{
      {.warmup = warmup_arrivals, .measurement = measurement_arrivals}};
  w::EventArena arena{{8U, 64U, 4096U, w::MasterSeed::from_hex(std::string(64U, '0')),
                       "service-synthetic"}};
  q::RingSpscQueue ring{{8U}, {64U}};
  w::R0Package package{ring};
  template <typename B>
  auto run(B& backend, c::ServiceSessionPlan plan = kPlan) -> c::ServiceSessionResult {
    return c::run_service_session(plan, clock, backend, backend, relax, observer,
                                  threads, storage);
  }
};

template <typename Queue, typename Package>
void check_package(Queue& queue, Package& package) {
#if CPU_PREFETCH_SERVICE_ALLOCATION_HOOK
  const auto allocations_before = allocations.load();
#endif
  ASSERT_TRUE(queue.reset_quiescent());
  auto fixture = std::make_unique<Fixture>();
  Backend backend(fixture->clock, queue, package, fixture->arena);
  const auto result = fixture->run(backend);
  ASSERT_EQ(result.stop, c::ServiceSessionStop::complete);
  EXPECT_EQ(backend.prepared, (std::array<unsigned, 2U>{1U, 1U}));
  EXPECT_EQ(backend.reset, (std::array<unsigned, 2U>{1U, 1U}));
  EXPECT_NE(backend.owner[0U], backend.owner[1U]);
  EXPECT_EQ(fixture->threads.starts, (std::array<unsigned, 2U>{1U, 1U}));
  EXPECT_TRUE(result.queue_reset && backend.reset_shape);
  EXPECT_TRUE(result.private_reset[0U] && result.private_reset[1U]);
  const auto warmup_window = result.phases[0U].window;
  const auto measurement_window = result.phases[1U].window;
  if (!warmup_window || !measurement_window) {
    FAIL() << "missing phase origin";
    return;
  }
  EXPECT_GT(measurement_window->origin_ticks, warmup_window->producer_deadline_ticks);
  for (const auto& phase : result.phases) {
    EXPECT_TRUE(phase.validated && phase.producer.deadline_reached &&
                phase.consumer.drained);
    EXPECT_EQ(phase.producer.attempted, phase.producer.accepted + phase.producer.full);
    EXPECT_EQ(phase.producer.accepted, phase.consumer.consumed);
  }
  for (auto* phase : {&backend.warmup, &backend.measurement}) {
    const auto layout = s::make_row_layout(phase->producer.snapshot().run_id);
    w::ConsumerState expected_checksum{0U};
    for (std::uint64_t i = 0U; i < phase->producer.snapshot().row_count; ++i) {
      const auto row =
          s::read_prepared_producer_row(phase->producer.snapshot(), layout, i);
      if (!row.has_value()) {
        FAIL() << "missing retained producer row";
        return;
      }
      EXPECT_EQ(row->logical_sequence.value, i);
      if (row->outcome == cpu_prefetch::protocol::ProducerOutcome::accepted) {
        const auto selected = fixture->arena.select(row->logical_sequence);
        EXPECT_EQ(
            fixture->arena.access_and_mix(selected.record, expected_checksum).status,
            w::RecordAccessStatus::valid);
      }
    }
    EXPECT_EQ(phase->checksum.value, expected_checksum.value);
  }
#if CPU_PREFETCH_SERVICE_ALLOCATION_HOOK
  EXPECT_EQ(allocations.load(), allocations_before);
#endif
}

TEST(ServiceSession, BorrowedTerminationConstructionDoesNotAllocate) {
#if CPU_PREFETCH_SERVICE_ALLOCATION_HOOK
  alignas(64) std::array<std::byte, 64U> bytes{};
  const auto before = allocations.load();
  watch_allocations = true;
  {
    l::TerminationControl control({64U}, bytes);
    control.publish_arrivals_finished();
  }
  watch_allocations = false;
  EXPECT_EQ(allocations.load(), before);
#else
  GTEST_SKIP()
      << "Clang TSan does not support the allocation replacement instrumentation";
#endif
}

TEST(ServiceSession, AllFiveActualPackagesPersistAcrossWarmupResetAndMeasurement) {
  Emitter emitter;
  q::RingSpscQueue ring{{64U}, {64U}};
  w::R0Package r0(ring);
  check_package(ring, r0);
  w::R1Package r1(ring, emitter, w::ring_one_line_distance({64U, 64U, sizeof(void*)}));
  check_package(ring, r1);
  const auto distance = w::resolve_calibrated_ring_distance({64U, 64U, sizeof(void*)},
                                                            2U, "synthetic-distance");
  w::R2Package r2(ring, emitter, distance);
  check_package(ring, r2);
  const std::array<std::size_t, 9U> order{0U, 1U, 2U, 3U, 4U, 5U, 6U, 7U, 8U};
  q::LinkedSpscQueue linked{{8U}, {64U}, {4096U}, order};
  w::L0Package l0(linked);
  check_package(linked, l0);
  w::L1Package l1(linked, emitter);
  check_package(linked, l1);
}

TEST(ServiceSession, NoHotOrLogicalResetAllocation) {
#if CPU_PREFETCH_SERVICE_ALLOCATION_HOOK
  const auto before = allocations.load();
  q::RingSpscQueue queue{{8U}, {64U}};
  w::R0Package package(queue);
  check_package(queue, package);
  EXPECT_EQ(allocations.load(), before);
#else
  GTEST_SKIP()
      << "Global allocation replacements unsupported by accepted Clang TSan runtime";
#endif
}

TEST(ServiceSession, PreparationFailureOrExceptionNeverStartsWarmup) {
  for (const bool exception : {false, true}) {
    Fixture f;
    Faults faults;
    faults.prepare = !exception;
    faults.prepare_exception = exception;
    Backend backend(f.clock, f.ring, f.package, f.arena, faults);
    const auto result = f.run(backend);
    EXPECT_NE(result.stop, c::ServiceSessionStop::complete);
    EXPECT_FALSE(result.phases[0U].window.has_value());
    EXPECT_EQ(backend.queue_resets, 0U);
  }
}
TEST(ServiceSession, ValidationAndEveryResetFailurePreventMeasurement) {
  for (unsigned choice = 0U; choice < 4U; ++choice) {
    Fixture f;
    Faults faults;
    faults.validation = choice == 0U;
    faults.queue_reset = choice == 1U;
    faults.producer_reset = choice == 2U;
    faults.consumer_reset = choice == 3U;
    Backend backend(f.clock, f.ring, f.package, f.arena, faults);
    const auto result = f.run(backend);
    EXPECT_NE(result.stop, c::ServiceSessionStop::complete);
    EXPECT_FALSE(result.phases[1U].window.has_value());
    EXPECT_EQ(backend.measurement.producer.snapshot().row_count, 0U);
  }
}
TEST(ServiceSession, ObservationFailuresCancelBeforeNextPhase) {
  for (unsigned hook = 0U; hook < 3U; ++hook) {
    Fixture f;
    f.observer.reject_before = hook == 0U ? 0 : -1;
    f.observer.reject_during = hook == 1U ? 0 : -1;
    f.observer.reject_after = hook == 2U ? 0 : -1;
    Backend backend(f.clock, f.ring, f.package, f.arena);
    const auto result = f.run(backend);
    EXPECT_EQ(result.stop, c::ServiceSessionStop::observation_failure);
    EXPECT_FALSE(result.phases[1U].window.has_value());
  }
}
TEST(ServiceSession, SecondThreadStartFailureJoinsFirstWithoutCapture) {
  Fixture f;
  f.threads.reject_consumer = true;
  Backend backend(f.clock, f.ring, f.package, f.arena);
  const auto result = f.run(backend);
  EXPECT_EQ(result.stop, c::ServiceSessionStop::thread_start_failure);
  EXPECT_FALSE(f.threads.owners[0U].joinable());
  EXPECT_FALSE(result.phases[0U].window.has_value());
}
TEST(ServiceSession, InvalidBoundsAndOneShotStorageCannotLaunchWorkers) {
  Fixture f;
  Backend backend(f.clock, f.ring, f.package, f.arena);
  auto plan = kPlan;
  plan.phases[0U].duration_ticks = 0U;
  EXPECT_EQ(f.run(backend, plan).stop, c::ServiceSessionStop::invalid_plan);
  EXPECT_EQ(f.run(backend).stop, c::ServiceSessionStop::storage_already_used);
  EXPECT_EQ(f.threads.starts, (std::array<unsigned, 2U>{0U, 0U}));
}
TEST(ServiceSession, ClockFailureAndOverflowCannotReleaseWarmup) {
  for (const bool overflow : {false, true}) {
    Fixture f;
    f.clock.fail.store(!overflow);
    if (overflow) {
      f.clock.next.store(std::numeric_limits<std::uint64_t>::max() - 1U);
    }
    Backend backend(f.clock, f.ring, f.package, f.arena);
    const auto result = f.run(backend);
    EXPECT_EQ(result.stop, overflow ? c::ServiceSessionStop::deadline_overflow
                                    : c::ServiceSessionStop::clock_failure);
    EXPECT_FALSE(result.phases[0U].window.has_value());
  }
}
TEST(ServiceSession, AttemptAndPollLimitsFailWithoutExtendingWarmup) {
  for (const bool producer : {false, true}) {
    Fixture f;
    Backend backend(f.clock, f.ring, f.package, f.arena);
    auto plan = kPlan;
    plan.phases[0U].duration_ticks = 1'000'000'000U;
    if (producer) {
      plan.phases[0U].producer_attempt_limit = 1U;
    } else {
      plan.phases[0U].consumer_poll_limit = 1U;
    }
    const auto result = f.run(backend, plan);
    EXPECT_EQ(result.stop, producer ? c::ServiceSessionStop::attempt_limit
                                    : c::ServiceSessionStop::poll_limit);
    EXPECT_FALSE(result.phases[1U].window.has_value());
  }
}
// Deterministically force an empty poll to linearize BEFORE the final enqueue
// but return AFTER arrivals_finished. No hardware or statistical endpoint rule.
struct LastEnqueueCapture final {
  Clock& clock;
  l::TerminationControl& arrivals;
  std::atomic<bool> empty_entered{false};
  std::atomic<bool> available{false};
  bool timeout{false};
  unsigned terminal_fault{0U};
  auto try_producer_attempt(l::ProducerAttempt) noexcept -> l::ProducerAttemptResult {
    for (unsigned n = 0U; n < 1'000'000U; ++n) {
      if (empty_entered.load(std::memory_order_acquire)) {
        available.store(true, std::memory_order_release);
        clock.next.fetch_add(20'000U, std::memory_order_relaxed);
        return {l::AttemptStatus::complete, q::EnqueueResult::accepted};
      }
      std::this_thread::yield();
    }
    return {l::AttemptStatus::failure, q::EnqueueResult::full};
  }
  auto try_consumer_poll(std::uint64_t) noexcept -> l::ConsumerPollResult {
    if (!empty_entered.exchange(true, std::memory_order_acq_rel)) {
      for (unsigned n = 0U; n < 1'000'000U; ++n) {
        if (arrivals.arrivals_finished()) {
          if (timeout) {
            clock.next.fetch_add(1'000'000U, std::memory_order_relaxed);
          }
          return {l::ConsumerPollStatus::empty};
        }
        std::this_thread::yield();
      }
      return {l::ConsumerPollStatus::failure};
    }
    if (available.exchange(false, std::memory_order_acq_rel)) {
      return {l::ConsumerPollStatus::item};
    }
    if (terminal_fault == 1U) {
      clock.next.fetch_add(1'000'000U, std::memory_order_relaxed);
    } else if (terminal_fault == 2U) {
      clock.fail.store(true, std::memory_order_relaxed);
    } else if (terminal_fault == 3U) {
      clock.next.store(0U, std::memory_order_relaxed);
    }
    return {l::ConsumerPollStatus::empty};
  }
};
struct LastEnqueueBackend final {
  LastEnqueueCapture warmup, measurement;
  bool regress_after_reset{false};
  auto phase(c::ServicePhase p) noexcept -> LastEnqueueCapture& {
    return p == c::ServicePhase::warmup ? warmup : measurement;
  }
  auto prepare_producer() const noexcept -> bool { return true; }
  auto prepare_consumer() const noexcept -> bool { return true; }
  auto reset_producer() const noexcept -> bool { return true; }
  auto reset_consumer() const noexcept -> bool { return true; }
  auto reset_quiescent() const noexcept -> bool {
    if (regress_after_reset) {
      warmup.clock.next.store(20'002U, std::memory_order_relaxed);
    }
    return !warmup.available.load();
  }
  auto validate_quiescent(c::ServicePhase,
                          const c::ServicePhaseResult& result) const noexcept -> bool {
    return result.producer.accepted == 1U && result.consumer.consumed == 1U;
  }
};
TEST(ServiceSession, FinalEnqueueRacingEarlierEmptyPollIsConsumedDuringDrain) {
  Fixture f;
  LastEnqueueBackend backend{{f.clock, f.warmup_arrivals},
                             {f.clock, f.measurement_arrivals}};
  const auto result = f.run(backend);
  ASSERT_EQ(result.stop, c::ServiceSessionStop::complete);
  for (const auto& phase : result.phases) {
    EXPECT_TRUE(phase.released);
    EXPECT_EQ(phase.consumer.consumed, 1U);
    if (!phase.consumer.last_observed_tick || !phase.window) {
      FAIL() << "missing phase clock observations";
      return;
    }
    EXPECT_GT(*phase.consumer.last_observed_tick,
              phase.window->producer_deadline_ticks);
    EXPECT_EQ(phase.window->duration_ticks, 20'000U);
  }
  if (!result.clock_origin) {
    FAIL() << "missing common clock origin";
    return;
  }
  EXPECT_EQ(result.clock_origin->absolute_nanoseconds, 0U);
}
TEST(ServiceSession, DrainTimeoutRetainsIncompleteWarmupAndPreventsMeasurement) {
  Fixture f;
  LastEnqueueBackend backend{{f.clock, f.warmup_arrivals},
                             {f.clock, f.measurement_arrivals}};
  backend.warmup.timeout = true;
  const auto result = f.run(backend);
  EXPECT_EQ(result.stop, c::ServiceSessionStop::drain_timeout);
  EXPECT_FALSE(result.phases[0U].consumer.drained);
  EXPECT_FALSE(result.phases[1U].released);
}

TEST(ServiceSession, TerminalEmptyPollCannotPassAfterDeadlineOrClockFailure) {
  for (unsigned fault = 1U; fault <= 3U; ++fault) {
    Fixture f;
    LastEnqueueBackend backend{{f.clock, f.warmup_arrivals},
                               {f.clock, f.measurement_arrivals}};
    backend.measurement.terminal_fault = fault;
    const auto result = f.run(backend);
    EXPECT_EQ(result.stop, fault == 1U ? c::ServiceSessionStop::drain_timeout
                                       : c::ServiceSessionStop::clock_failure);
    EXPECT_FALSE(result.phases[1U].consumer.drained);
    EXPECT_FALSE(result.phases[1U].validated);
  }
}
TEST(ServiceSession, MeasurementOriginCannotRegressBehindCompletedWarmupDrain) {
  Fixture f;
  LastEnqueueBackend backend{{f.clock, f.warmup_arrivals},
                             {f.clock, f.measurement_arrivals}};
  backend.regress_after_reset = true;
  const auto result = f.run(backend);
  EXPECT_EQ(result.stop, c::ServiceSessionStop::clock_failure);
  EXPECT_TRUE(result.phases[0U].consumer.drained);
  EXPECT_FALSE(result.phases[1U].released);
}
TEST(ServiceSession, CheckedWindowDoesNotInventDefaultsOrOverflow) {
  EXPECT_FALSE(c::service_window(0U, {0U, 1U, 1U, 1U}).has_value());
  EXPECT_FALSE(c::service_window(std::numeric_limits<std::uint64_t>::max() - 2U,
                                 {1U, 1U, 1U, 2U})
                   .has_value());
  const auto window = c::service_window(7U, {3U, 1U, 1U, 5U});
  if (!window) {
    FAIL() << "valid window rejected";
    return;
  }
  EXPECT_EQ(window->producer_deadline_ticks, 10U);
  EXPECT_EQ(window->drain_deadline_ticks, 15U);
}
} // namespace
