#include "cpu_prefetch/calibration/formal_service_session.hpp"
#include "cpu_prefetch/workload/packages.hpp"
#include "discovery_backend_test_support.hpp"

#include <gtest/gtest.h>

#include <array>
#include <atomic>
#include <limits>
#include <thread>

namespace {
using namespace cpu_prefetch;
namespace c = calibration;
namespace l = lifecycle;
namespace s = storage;
namespace t = timing;
namespace w = workload;

constexpr c::ServiceSessionPlan kPlan{{{{1'000'000U, 2048U, 8192U, 50'000'000U},
                                        {1'000'000U, 2048U, 8192U, 50'000'000U}}},
                                      5'000'000U};

class Clock final {
public:
  auto origin() const noexcept -> t::ClockOrigin { return {100U}; }
  auto read() noexcept -> t::ClockReadResult {
    const auto tick = next.fetch_add(1U);
    return {tick == fail_at ? t::ClockReadStatus::call_failed : t::ClockReadStatus::ok,
            {100U + tick, tick * 1000U}};
  }
  std::atomic<std::uint64_t> next{1U};
  std::uint64_t fail_at{std::numeric_limits<std::uint64_t>::max()};
};

struct Phase final {
  protocol::RunId id;
  s::ProducerObservationStream producer_raw;
  s::ConsumerObservationStream consumer_raw;
  c::FormalServiceProducerPhase producer;
  c::FormalServiceConsumerPhase consumer;
  Phase(std::string name, std::uint64_t capacity)
      : id(test_support::discovery_test_run_id(std::move(name))),
        producer_raw(id, capacity), consumer_raw(id, capacity),
        producer{producer_raw, s::make_row_layout(id.value())},
        consumer{consumer_raw, s::make_row_layout(id.value()), {17U}, {17U}} {}
};

template <typename Queue, typename Package> class Preparation final {
public:
  Preparation(Queue& queue, Package& package, std::uint64_t capacity)
      : warmup("service-formal-warmup", capacity),
        measurement("service-formal-measurement", capacity), queue_(queue),
        package_(package) {}
  auto prepare_producer() noexcept -> bool {
    owners[0U] = std::this_thread::get_id();
    return ++prepares[0U] == 1U && !reject_prepare;
  }
  auto prepare_consumer() noexcept -> bool {
    owners[1U] = std::this_thread::get_id();
    return ++prepares[1U] == 1U && !reject_prepare;
  }
  auto before_measurement_producer() noexcept -> bool {
    ++resets[0U];
    return owners[0U] == std::this_thread::get_id() && !reject_reset;
  }
  auto before_measurement_consumer() noexcept -> bool {
    ++resets[1U];
    return owners[1U] == std::this_thread::get_id() && !reject_reset;
  }
  auto producer_phase(bool first) noexcept -> c::FormalServiceProducerPhase& {
    return first ? warmup.producer : measurement.producer;
  }
  auto consumer_phase(bool first) noexcept -> c::FormalServiceConsumerPhase& {
    return first ? warmup.consumer : measurement.consumer;
  }
  auto run_id(bool first) const noexcept -> const protocol::RunId& {
    return first ? warmup.id : measurement.id;
  }
  auto queue() noexcept -> Queue& { return queue_; }
  auto package() noexcept -> Package& { return package_; }
  auto arena() const noexcept -> const w::EventArena& { return event_arena; }
  Phase warmup;
  Phase measurement;
  w::EventArena event_arena{{8U, 64U, 4096U,
                             w::MasterSeed::from_hex(std::string(64U, '0')),
                             "service-formal-software-only"}};
  std::array<std::thread::id, 2U> owners;
  std::array<unsigned, 2U> prepares{};
  std::array<unsigned, 2U> resets{};
  bool reject_prepare{false};
  bool reject_reset{false};

private:
  Queue& queue_;
  Package& package_;
};

struct Threads final {
  std::array<std::thread, 2U> workers;
  std::array<unsigned, 2U> starts{};
  auto start(c::RingWorker role, platform::WorkerEntry entry, void* context) -> bool {
    const auto index = role == c::RingWorker::producer ? 0U : 1U;
    ++starts[index];
    workers[index] = std::thread(entry, context);
    return true;
  }
  auto prepared(c::RingWorker) const noexcept -> bool { return true; }
  void join() {
    for (auto& worker : workers) {
      if (worker.joinable()) {
        worker.join();
      }
    }
  }
};

struct Observer final {
  int reject_before{-1};
  auto before_phase(c::ServicePhase phase) const noexcept -> bool {
    return static_cast<int>(phase) != reject_before;
  }
  auto during_phase(c::ServicePhase, c::ServiceWindow,
                    const std::atomic<std::uint32_t>&) const noexcept -> bool {
    return true;
  }
  auto after_phase(c::ServicePhase) const noexcept -> bool { return true; }
};

template <typename Queue, typename Package> struct Fixture final {
  alignas(64) std::array<std::byte, 64U> warmup_line{};
  alignas(64) std::array<std::byte, 64U> measurement_line{};
  Preparation<Queue, Package> preparation;
  Clock clock;
  Threads threads;
  l::TerminationControl warmup{{64U}, warmup_line};
  l::TerminationControl measurement{{64U}, measurement_line};
  c::ServiceSessionPlan plan{kPlan};
  c::FormalServiceSessionBackend<Clock, Preparation<Queue, Package>> backend;
  c::ServiceSessionStorage session{{warmup, measurement}};
  Observer observer;
  test_support::DiscoveryTestRelax relax;
  Fixture(Queue& queue, Package& package, std::uint64_t capacity = 2048U)
      : preparation(queue, package, capacity), backend(plan, clock, preparation) {
    for (auto& phase : plan.phases) {
      phase.producer_attempt_limit = capacity;
    }
  }
  auto run() -> c::ServiceSessionResult {
    return c::run_formal_service_session(backend, relax, observer, threads, session);
  }
  auto prepare() -> bool {
    return backend.prepare_producer() && backend.prepare_consumer();
  }
};

struct Emitter final {
  std::atomic<unsigned> producer{0U}, consumer{0U}, successor{0U};
  void ring_producer_write(const void*) noexcept { producer.fetch_add(1U); }
  void ring_consumer_read(const void*) noexcept { consumer.fetch_add(1U); }
  void successor_header(const void*) noexcept { successor.fetch_add(1U); }
};

template <typename Queue, typename Package>
void check_persistent_package(Queue& queue, Package& package) {
  ASSERT_TRUE(queue.reset_quiescent());
  Fixture fixture(queue, package);
  const auto& arena = fixture.preparation.arena();
  const auto* address = arena.storage_address();
  const auto content = arena.content_checksum();
  const auto order = arena.ordered_index_checksum();
  const auto result = fixture.run();
  ASSERT_EQ(result.stop, c::ServiceSessionStop::complete);
  EXPECT_TRUE(result.queue_reset);
  EXPECT_EQ(fixture.preparation.prepares, (std::array<unsigned, 2U>{1U, 1U}));
  EXPECT_EQ(fixture.preparation.resets, (std::array<unsigned, 2U>{1U, 1U}));
  EXPECT_EQ(fixture.threads.starts, (std::array<unsigned, 2U>{1U, 1U}));
  EXPECT_NE(fixture.preparation.owners[0U], fixture.preparation.owners[1U]);
  EXPECT_EQ(arena.storage_address(), address);
  EXPECT_EQ(arena.content_checksum(), content);
  EXPECT_EQ(arena.ordered_index_checksum(), order);
  for (const bool first : {true, false}) {
    const auto& producer = fixture.preparation.producer_phase(first);
    const auto& consumer = fixture.preparation.consumer_phase(first);
    EXPECT_EQ(consumer.last_join.status, c::DiscoveryJoinStatus::exact);
    EXPECT_EQ(producer.accepted, consumer.retained_consumed);
    EXPECT_EQ(producer.retained_attempts, producer.accepted + producer.full);
    EXPECT_EQ(producer.primary.snapshot().completeness,
              s::StreamCompleteness::sealed_complete);
    EXPECT_EQ(consumer.primary.snapshot().completeness,
              s::StreamCompleteness::sealed_complete);
    EXPECT_EQ(consumer.interval.has_value(), !first);
  }
  const auto interval = fixture.preparation.measurement.consumer.interval;
  if (!interval || !interval->counts) {
    FAIL() << "complete joined measurement missing D211 interval result";
    return;
  }
  EXPECT_EQ(interval->status, c::ServiceIntervalStatus::complete);
  EXPECT_EQ(interval->counts->consumed_count, result.phases[1U].consumer.consumed);
  EXPECT_EQ(interval->counts->consumed_count,
            interval->counts->interval_consumed_count +
                interval->counts->outside_interval_consumed_count);
  EXPECT_EQ(
      interval->counts->measurement_window.measurement_origin.relative_picoseconds,
      result.phases[1U].observed_origin);
  EXPECT_EQ(interval->counts->measurement_window.duration_ticks,
            fixture.plan.phases[1U].duration_ticks);
}

TEST(FormalServiceSession, AllFivePackagesUsePersistentOwnersJoinAndD211Count) {
  Emitter emitter;
  queue::RingSpscQueue ring{{64U}, {64U}};
  w::R0Package r0(ring);
  check_persistent_package(ring, r0);
  w::R1Package r1(ring, emitter, w::ring_one_line_distance({64U, 64U, sizeof(void*)}));
  check_persistent_package(ring, r1);
  const auto distance = w::resolve_calibrated_ring_distance(
      {64U, 64U, sizeof(void*)}, 2U, "synthetic-only-distance");
  w::R2Package r2(ring, emitter, distance);
  check_persistent_package(ring, r2);
  const std::array<std::size_t, 9U> order{0U, 1U, 2U, 3U, 4U, 5U, 6U, 7U, 8U};
  queue::LinkedSpscQueue linked{{8U}, {64U}, {4096U}, order};
  w::L0Package l0(linked);
  check_persistent_package(linked, l0);
  w::L1Package l1(linked, emitter);
  check_persistent_package(linked, l1);
}

template <typename Queue, typename Package>
void check_capture_and_prefetch(Queue& queue, Package& package) {
  ASSERT_TRUE(queue.reset_quiescent());
  Fixture fixture(queue, package);
  ASSERT_TRUE(fixture.prepare());
  auto& phase = fixture.backend.phase(c::ServicePhase::warmup);
  ASSERT_EQ(phase.try_producer_attempt({0U, 0U, 0U}).status,
            l::AttemptStatus::complete);
  ASSERT_EQ(phase.try_producer_attempt({1U, 0U, 1U}).status,
            l::AttemptStatus::complete);
  ASSERT_EQ(phase.try_consumer_poll(0U).status, l::ConsumerPollStatus::item);
  ASSERT_EQ(phase.try_consumer_poll(1U).status, l::ConsumerPollStatus::item);
  EXPECT_EQ(phase.try_consumer_poll(2U).status, l::ConsumerPollStatus::empty);
  const auto& producer = fixture.preparation.warmup.producer;
  const auto& consumer = fixture.preparation.warmup.consumer;
  const auto join = c::reconcile_discovery_primary(
      fixture.preparation.arena(), producer.primary.snapshot(), producer.layout,
      consumer.primary.snapshot(), consumer.layout, {2U, 2U, 0U, 2U},
      {consumer.initial_state, consumer.state}, true);
  EXPECT_EQ(join.status, c::DiscoveryJoinStatus::exact);
  EXPECT_EQ(producer.primary.snapshot().row_count, 2U);
  EXPECT_EQ(consumer.primary.snapshot().row_count, 2U);
  EXPECT_EQ(consumer.empty, 1U);
  fixture.backend.finalize_joined();
  EXPECT_EQ(producer.primary.snapshot().completeness,
            s::StreamCompleteness::sealed_incomplete);
}

TEST(FormalServiceSession, ExistingPrefetchPrimitivesAndPrimaryRowsAreUnchanged) {
  Emitter emitter;
  queue::RingSpscQueue ring{{64U}, {64U}};
  w::R0Package r0(ring);
  check_capture_and_prefetch(ring, r0);
  EXPECT_EQ(emitter.producer.load(), 0U);
  EXPECT_EQ(emitter.consumer.load(), 0U);
  w::R1Package r1(ring, emitter, w::ring_one_line_distance({64U, 64U, sizeof(void*)}));
  check_capture_and_prefetch(ring, r1);
  EXPECT_EQ(emitter.producer.load(), 2U);
  EXPECT_EQ(emitter.consumer.load(), 3U);
  const auto distance = w::resolve_calibrated_ring_distance(
      {64U, 64U, sizeof(void*)}, 2U, "synthetic-only-distance");
  w::R2Package r2(ring, emitter, distance);
  check_capture_and_prefetch(ring, r2);
  EXPECT_EQ(emitter.producer.load(), 4U);
  EXPECT_EQ(emitter.consumer.load(), 6U);
  const std::array<std::size_t, 9U> order{0U, 1U, 2U, 3U, 4U, 5U, 6U, 7U, 8U};
  queue::LinkedSpscQueue linked{{8U}, {64U}, {4096U}, order};
  w::L0Package l0(linked);
  check_capture_and_prefetch(linked, l0);
  EXPECT_EQ(emitter.successor.load(), 0U);
  w::L1Package l1(linked, emitter);
  check_capture_and_prefetch(linked, l1);
  EXPECT_GT(emitter.successor.load(), 0U);
}

auto completed_report(const c::ServiceSessionPlan& plan, c::ServicePhase phase,
                      std::uint64_t attempts) -> c::ServicePhaseResult {
  c::ServicePhaseResult result;
  result.released = true;
  result.origin_status = t::ClockReadStatus::ok;
  result.origin_sample = t::ClockSample{100U, 0U};
  result.observed_origin = 0U;
  result.window =
      c::service_window(0U, plan.phases[phase == c::ServicePhase::warmup ? 0U : 1U]);
  result.producer.attempted = attempts;
  result.producer.accepted = attempts;
  result.producer.deadline_reached = true;
  result.producer.arrivals_finished_published = true;
  result.consumer.consumed = attempts;
  result.consumer.polls = attempts + 1U;
  result.consumer.empty = 1U;
  result.consumer.drained = true;
  return result;
}

TEST(FormalServiceSession,
     ColdIntervalUsesActionCompletionAndKeepsZeroThroughputValid) {
  for (const auto duration : {9000U, 18000U, 18001U}) {
    queue::RingSpscQueue ring{{8U}, {64U}};
    w::R0Package package(ring);
    Fixture fixture(ring, package);
    fixture.plan.phases[1U].duration_ticks = duration;
    ASSERT_TRUE(fixture.prepare());
    auto& phase = fixture.backend.phase(c::ServicePhase::measurement);
    for (std::uint64_t ordinal = 0U; ordinal < 2U; ++ordinal) {
      ASSERT_EQ(phase.try_producer_attempt({ordinal, 0U, ordinal}).status,
                l::AttemptStatus::complete);
      ASSERT_EQ(phase.try_consumer_poll(ordinal).status, l::ConsumerPollStatus::item);
    }
    EXPECT_EQ(phase.try_consumer_poll(2U).status, l::ConsumerPollStatus::empty);
    auto report = completed_report(fixture.plan, c::ServicePhase::measurement, 2U);
    ASSERT_TRUE(
        fixture.backend.validate_quiescent(c::ServicePhase::measurement, report));
    const auto interval = fixture.preparation.measurement.consumer.interval;
    if (!interval || !interval->counts) {
      FAIL() << "missing completed interval";
      return;
    }
    EXPECT_EQ(interval->counts->consumed_count, 2U);
    EXPECT_EQ(interval->counts->interval_consumed_count, duration == 9000U    ? 0U
                                                         : duration == 18000U ? 1U
                                                                              : 2U);
  }
}

TEST(FormalServiceSession,
     ProducerClockFailureRetainsExactCurrentWithoutGuessingOutcome) {
  for (const auto failure : {1U, 4U, 5U}) {
    queue::RingSpscQueue ring{{8U}, {64U}};
    w::R0Package package(ring);
    Fixture fixture(ring, package);
    ASSERT_TRUE(fixture.prepare());
    fixture.clock.fail_at = failure;
    auto& phase = fixture.backend.phase(c::ServicePhase::warmup);
    EXPECT_EQ(phase.try_producer_attempt({0U, 0U, 0U}).status,
              l::AttemptStatus::failure);
    const auto& producer = fixture.preparation.warmup.producer;
    const auto current = producer.current;
    if (!current) {
      FAIL() << "failure current missing";
      return;
    }
    EXPECT_EQ(current->status, t::CaptureStatus::clock_failure);
    EXPECT_EQ(current->clock_status, t::ClockReadStatus::call_failed);
    EXPECT_FALSE(current->observation);
    EXPECT_EQ(producer.requests, 1U);
    EXPECT_EQ(producer.retained_attempts, 0U);
    EXPECT_EQ(producer.accepted, 0U);
    EXPECT_EQ(producer.full, 0U);
    EXPECT_FALSE(producer.last_append);
    EXPECT_EQ(phase.try_producer_attempt({1U, 0U, 0U}).status,
              l::AttemptStatus::failure);
    EXPECT_EQ(producer.requests, 1U);
    fixture.backend.finalize_joined();
    EXPECT_EQ(producer.primary.snapshot().completeness,
              s::StreamCompleteness::sealed_incomplete);
    EXPECT_FALSE(fixture.preparation.measurement.consumer.interval);
  }
}

TEST(FormalServiceSession, ExistingConsumerClockFailureBeforeChecksumIsPreserved) {
  queue::RingSpscQueue ring{{8U}, {64U}};
  w::R0Package package(ring);
  Fixture fixture(ring, package);
  ASSERT_TRUE(fixture.prepare());
  auto& phase = fixture.backend.phase(c::ServicePhase::warmup);
  ASSERT_EQ(phase.try_producer_attempt({0U, 0U, 0U}).status,
            l::AttemptStatus::complete);
  fixture.clock.fail_at = fixture.clock.next.load() + 2U; // dequeue completion
  EXPECT_EQ(phase.try_consumer_poll(0U).status, l::ConsumerPollStatus::failure);
  const auto& consumer = fixture.preparation.warmup.consumer;
  const auto current = consumer.current;
  if (!current) {
    FAIL() << "failed consumer current missing";
    return;
  }
  EXPECT_EQ(current->failed_boundary, t::TimestampBoundary::dequeue_completion);
  EXPECT_FALSE(current->observation);
  EXPECT_EQ(consumer.retained_consumed, 0U);
  EXPECT_EQ(consumer.state, consumer.initial_state);
  EXPECT_EQ(ring.try_dequeue().status, queue::DequeueStatus::empty);
  fixture.backend.finalize_joined();
  EXPECT_EQ(consumer.primary.snapshot().completeness,
            s::StreamCompleteness::sealed_incomplete);
}

TEST(FormalServiceSession, AppendFailurePreservesIndependentCurrentAndPrimaryPrefix) {
  queue::RingSpscQueue ring{{8U}, {64U}};
  w::R0Package package(ring);
  Fixture fixture(ring, package, 1U);
  ASSERT_TRUE(fixture.prepare());
  auto& phase = fixture.backend.phase(c::ServicePhase::warmup);
  ASSERT_EQ(phase.try_producer_attempt({0U, 0U, 0U}).status,
            l::AttemptStatus::complete);
  ASSERT_EQ(phase.try_consumer_poll(0U).status, l::ConsumerPollStatus::item);
  EXPECT_EQ(phase.try_producer_attempt({1U, 0U, 1U}).status, l::AttemptStatus::failure);
  EXPECT_EQ(phase.try_consumer_poll(1U).status, l::ConsumerPollStatus::failure);
  const auto& producer = fixture.preparation.warmup.producer;
  const auto& consumer = fixture.preparation.warmup.consumer;
  EXPECT_EQ(producer.last_append, s::AppendStatus::buffer_overflow);
  EXPECT_EQ(consumer.last_append, s::AppendStatus::buffer_overflow);
  EXPECT_EQ(producer.primary.snapshot().row_count, 1U);
  EXPECT_EQ(consumer.primary.snapshot().row_count, 1U);
  EXPECT_EQ(producer.retained_attempts, 1U);
  EXPECT_EQ(consumer.retained_consumed, 1U);
  const auto producer_current = producer.current;
  const auto consumer_current = consumer.current;
  if (!producer_current || !consumer_current || !producer_current->observation ||
      !consumer_current->observation) {
    FAIL() << "complete failed-append observations not retained";
    return;
  }
  EXPECT_EQ(producer_current->observation->logical_sequence.value, 1U);
  EXPECT_EQ(consumer_current->observation->consumed_ordinal.value, 1U);
}

TEST(FormalServiceSession, FailedWarmupResetPreventsMeasurementAndKeepsWarmupBytes) {
  queue::RingSpscQueue ring{{8U}, {64U}};
  w::R0Package package(ring);
  Fixture fixture(ring, package);
  fixture.preparation.reject_reset = true;
  const auto result = fixture.run();
  EXPECT_EQ(result.stop, c::ServiceSessionStop::reset_failure);
  EXPECT_TRUE(result.phases[0U].validated);
  EXPECT_FALSE(result.phases[1U].released);
  EXPECT_EQ(fixture.preparation.warmup.producer.primary.snapshot().completeness,
            s::StreamCompleteness::sealed_complete);
  EXPECT_EQ(fixture.preparation.measurement.producer.primary.snapshot().completeness,
            s::StreamCompleteness::sealed_incomplete);
  EXPECT_FALSE(fixture.preparation.measurement.consumer.interval);
}

TEST(FormalServiceSession, FailedObservationPreventsColdIntervalClaim) {
  queue::RingSpscQueue ring{{8U}, {64U}};
  w::R0Package package(ring);
  Fixture fixture(ring, package);
  fixture.observer.reject_before = 1;
  const auto result = fixture.run();
  EXPECT_EQ(result.stop, c::ServiceSessionStop::observation_failure);
  EXPECT_FALSE(result.phases[1U].released);
  EXPECT_FALSE(fixture.preparation.measurement.consumer.interval);
}

TEST(FormalServiceSession, FailedJoinAndMalformedOriginNeverProduceIntervalCount) {
  for (const bool corrupt_checksum : {false, true}) {
    queue::RingSpscQueue ring{{8U}, {64U}};
    w::R0Package package(ring);
    Fixture fixture(ring, package);
    ASSERT_TRUE(fixture.prepare());
    auto& phase = fixture.backend.phase(c::ServicePhase::measurement);
    ASSERT_EQ(phase.try_producer_attempt({0U, 0U, 0U}).status,
              l::AttemptStatus::complete);
    ASSERT_EQ(phase.try_consumer_poll(0U).status, l::ConsumerPollStatus::item);
    ASSERT_EQ(phase.try_consumer_poll(1U).status, l::ConsumerPollStatus::empty);
    auto report = completed_report(fixture.plan, c::ServicePhase::measurement, 1U);
    if (corrupt_checksum) {
      fixture.preparation.measurement.consumer.state.value ^= 1U;
    } else {
      if (!report.origin_sample.has_value()) {
        FAIL() << "test report is missing the origin";
        return;
      }
      report.origin_sample->absolute_nanoseconds += 1U;
    }
    EXPECT_FALSE(
        fixture.backend.validate_quiescent(c::ServicePhase::measurement, report));
    const auto interval = fixture.preparation.measurement.consumer.interval;
    if (interval) {
      EXPECT_NE(interval->status, c::ServiceIntervalStatus::complete);
      EXPECT_FALSE(interval->counts);
    }
  }
}

TEST(FormalServiceSession, RejectsDirtyPhaseStateAndBoundsBeforeCapture) {
  queue::RingSpscQueue ring{{8U}, {64U}};
  w::R0Package package(ring);
  Fixture fixture(ring, package);
  fixture.preparation.measurement.producer.requests = 1U;
  EXPECT_FALSE(fixture.backend.prepare_producer());
  EXPECT_FALSE(fixture.backend.reset_quiescent());
  EXPECT_EQ(fixture.preparation.measurement.producer.primary.snapshot().row_count, 0U);
  Fixture small(ring, package, 1U);
  small.plan.phases[0U].producer_attempt_limit = 2U;
  EXPECT_FALSE(small.backend.prepare_producer());
}

} // namespace
