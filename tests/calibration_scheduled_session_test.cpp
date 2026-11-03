#include "cpu_prefetch/calibration/formal_service_session.hpp"
#include "cpu_prefetch/calibration/scheduled_session.hpp"
#include "cpu_prefetch/workload/packages.hpp"
#include "discovery_backend_test_support.hpp"

#include <gtest/gtest.h>

#include <atomic>
#include <thread>
#include <vector>

namespace {
using namespace cpu_prefetch;
namespace c = calibration;
namespace l = lifecycle;
namespace s = storage;
namespace t = timing;
namespace w = workload;

auto plan() -> c::ScheduledSessionPlan {
  return {{{{{5'000'000'000'000U, 64U, 100'000U, 100'000'000'000U},
             {1000U, 64U, 100'000U, 100'000'000'000U}}},
           5'000'000U},
          {{{1000U, 5'000'000'001'000U, 2U,
             protocol::ScheduleId::parse("warmup-schedule", "$test").value(),
             protocol::NamespaceId::parse("warmup-seed", "$test").value()},
            {7000U, 8000U, 3U,
             protocol::ScheduleId::parse("measurement-schedule", "$test").value(),
             protocol::NamespaceId::parse("measurement-seed", "$test").value()}}}};
}

class Clock final {
public:
  auto origin() const noexcept -> t::ClockOrigin { return {100U}; }
  auto read() noexcept -> t::ClockReadResult {
    const auto value = next.fetch_add(1U);
    return {fail.load() ? t::ClockReadStatus::call_failed : t::ClockReadStatus::ok,
            {100U + value, value * 1000U}};
  }
  std::atomic<std::uint64_t> next{1U};
  std::atomic<bool> fail{false};
};

struct Phase final {
  protocol::RunId id;
  s::ProducerObservationStream producer_stream;
  s::ConsumerObservationStream consumer_stream;
  c::FormalServiceProducerPhase producer;
  c::FormalServiceConsumerPhase consumer;
  explicit Phase(std::string name)
      : id(test_support::discovery_test_run_id(std::move(name))),
        producer_stream(id, 64U), consumer_stream(id, 64U),
        producer{producer_stream, s::make_row_layout(id.value())},
        consumer{consumer_stream, s::make_row_layout(id.value()), {17U}, {17U}} {}
};

template <typename Queue, typename Package> class Preparation final {
public:
  Preparation(Queue& queue, Package& package) : queue_(queue), package_(package) {}
  void bind_plan(const c::ScheduledSessionPlan& input) noexcept { plan_ = &input; }
  auto prepare_producer() noexcept -> bool {
    owners[0U] = std::this_thread::get_id();
    prepared[0U] = true;
    return true;
  }
  auto prepare_consumer() noexcept -> bool {
    owners[1U] = std::this_thread::get_id();
    prepared[1U] = true;
    return true;
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
  auto schedule(c::ServicePhase phase) -> l::PreparedScheduleView {
    if (plan_ == nullptr || !prepared[0U] || !prepared[1U]) {
      throw std::logic_error("schedule accessed before both owners prepared");
    }
    ++schedule_reads;
    const auto index = phase == c::ServicePhase::warmup ? 0U : 1U;
    return {deadlines[index], plan_->phases[index].source_origin_ticks,
            plan_->phases[index].source_horizon_ticks};
  }
  Phase warmup{"scheduled-warmup"};
  Phase measurement{"scheduled-measurement"};
  w::EventArena event_arena{{8U, 64U, 4096U,
                             w::MasterSeed::from_hex(std::string(64U, '0')),
                             "scheduled-software-only"}};
  std::array<std::vector<std::uint64_t>, 2U> deadlines{
      {{1000U, 1000U}, {7000U, 7000U, 7000U}}};
  std::array<std::thread::id, 2U> owners;
  std::array<bool, 2U> prepared{};
  std::array<unsigned, 2U> resets{};
  unsigned schedule_reads{0U};
  bool reject_reset{false};

private:
  Queue& queue_;
  Package& package_;
  const c::ScheduledSessionPlan* plan_{nullptr};
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
  // Software reproduction of mandatory during-observation rejection after
  // workers have finished, not a substitute for actual native observations.
  bool observe_after_finish{false};
  bool fail_clock{false};
  Clock& clock;
  auto before_phase(c::ServicePhase) const noexcept -> bool { return true; }
  auto during_phase(c::ServicePhase, c::ServiceWindow,
                    const std::atomic<std::uint32_t>& finished) const noexcept -> bool {
    if (fail_clock) {
      clock.fail.store(true);
      return false;
    }
    if (observe_after_finish) {
      for (std::uint64_t poll = 0U; poll < 5'000'000U; ++poll) {
        if (finished.load(std::memory_order_acquire) != 0U) {
          return false;
        }
        std::this_thread::yield();
      }
      return false;
    }
    return true;
  }
  auto after_phase(c::ServicePhase) const noexcept -> bool { return true; }
};

template <typename Queue, typename Package> struct Fixture final {
  alignas(64) std::array<std::byte, 64U> warmup_line{};
  alignas(64) std::array<std::byte, 64U> measurement_line{};
  Preparation<Queue, Package> preparation;
  Clock clock;
  Observer observer{false, false, clock};
  Threads threads;
  l::TerminationControl warmup{{64U}, warmup_line};
  l::TerminationControl measurement{{64U}, measurement_line};
  c::ScheduledSessionPlan input{plan()};
  c::FormalServiceSessionBackend<Clock, Preparation<Queue, Package>,
                                 c::FormalCapturePurpose::scheduled>
      backend;
  c::ScheduledSessionStorage storage{{warmup, measurement}};
  test_support::DiscoveryTestRelax relax;
  Fixture(Queue& queue, Package& package)
      : preparation(queue, package), backend(input.bounds, clock, preparation) {
    preparation.bind_plan(input);
  }
  auto run() -> c::ScheduledSessionResult {
    return c::run_scheduled_session(input, clock, backend, preparation, relax, observer,
                                    threads, storage);
  }
};

template <typename Queue, typename Package>
void check_package(Queue& queue, Package& package) {
  ASSERT_TRUE(queue.reset_quiescent());
  Fixture fixture(queue, package);
  const auto& arena = fixture.preparation.arena();
  const auto* address = arena.storage_address();
  const auto content = arena.content_checksum();
  const auto order = arena.ordered_index_checksum();
  const auto result = fixture.run();
  ASSERT_EQ(result.lifecycle.stop, c::ServiceSessionStop::complete);
  EXPECT_EQ(fixture.threads.starts, (std::array<unsigned, 2U>{1U, 1U}));
  EXPECT_EQ(fixture.preparation.resets, (std::array<unsigned, 2U>{1U, 1U}));
  EXPECT_EQ(fixture.preparation.schedule_reads, 2U);
  EXPECT_EQ(arena.storage_address(), address);
  EXPECT_EQ(arena.content_checksum(), content);
  EXPECT_EQ(arena.ordered_index_checksum(), order);
  for (std::size_t index = 0U; index < 2U; ++index) {
    const auto& phase = result.lifecycle.phases[index];
    const auto& evidence = result.schedules[index];
    EXPECT_TRUE(evidence.all_arrivals_attempted);
    EXPECT_TRUE(evidence.mapped_schedule_validated);
    EXPECT_TRUE(phase.producer.arrivals_finished_published);
    EXPECT_TRUE(phase.consumer.drained);
    EXPECT_TRUE(phase.validated);
    EXPECT_EQ(phase.producer.attempted, fixture.input.phases[index].offered_count);
    EXPECT_EQ(phase.producer.accepted + phase.producer.full, phase.producer.attempted);
    EXPECT_EQ(phase.producer.accepted, phase.consumer.consumed);
    const auto& producer = fixture.preparation.producer_phase(index == 0U);
    const auto& consumer = fixture.preparation.consumer_phase(index == 0U);
    EXPECT_EQ(consumer.last_join.status, c::DiscoveryJoinStatus::exact);
    EXPECT_FALSE(consumer.interval.has_value()); // no D211 on Q16c
    for (std::uint64_t row = 0U; row < producer.primary.snapshot().row_count; ++row) {
      const auto parsed = s::read_prepared_producer_row(producer.primary.snapshot(),
                                                        producer.layout, row);
      if (!parsed || !phase.observed_origin) {
        FAIL() << "missing primary row or actual phase origin";
        return;
      }
      EXPECT_EQ(parsed->scheduled_arrival, *phase.observed_origin);
      EXPECT_EQ(parsed->logical_sequence.value, row);
    }
  }
  const auto warmup_done = result.schedules[0U].producer_completion;
  const auto warmup_window = result.lifecycle.phases[0U].window;
  if (!warmup_done || !warmup_window) {
    FAIL() << "missing actual warmup completion/window";
    return;
  }
  EXPECT_LT(warmup_done->sample.relative_picoseconds,
            warmup_window->producer_deadline_ticks);
  EXPECT_FALSE(result.lifecycle.phases[0U].producer.deadline_reached);
  EXPECT_TRUE(
      result.lifecycle.phases[1U].producer.deadline_reached); // attempts were late
}

TEST(ScheduledSession, AllFivePackagesPreserveOneAttemptLateDrainAndNoD211Filter) {
  struct Emitter final {
    void ring_producer_write(const void*) const noexcept {}
    void ring_consumer_read(const void*) const noexcept {}
    void successor_header(const void*) const noexcept {}
  } emitter;
  queue::RingSpscQueue ring{{64U}, {64U}};
  w::R0Package r0(ring);
  check_package(ring, r0);
  w::R1Package r1(ring, emitter, w::ring_one_line_distance({64U, 64U, sizeof(void*)}));
  check_package(ring, r1);
  const auto distance = w::resolve_calibrated_ring_distance(
      {64U, 64U, sizeof(void*)}, 2U, "synthetic-only-distance");
  w::R2Package r2(ring, emitter, distance);
  check_package(ring, r2);
  const std::array<std::size_t, 9U> order{0U, 1U, 2U, 3U, 4U, 5U, 6U, 7U, 8U};
  queue::LinkedSpscQueue linked{{8U}, {64U}, {4096U}, order};
  w::L0Package l0(linked);
  check_package(linked, l0);
  w::L1Package l1(linked, emitter);
  check_package(linked, l1);
}

TEST(ScheduledSession, EmptyMeasurementRejectedBeforePreparingOrStartingWorkers) {
  queue::RingSpscQueue queue{{8U}, {64U}};
  w::R0Package package(queue);
  Fixture fixture(queue, package);
  fixture.input.phases[1U].offered_count = 0U;
  fixture.preparation.deadlines[1U].clear();
  EXPECT_EQ(fixture.run().lifecycle.stop, c::ServiceSessionStop::invalid_plan);
  EXPECT_EQ(fixture.threads.starts, (std::array<unsigned, 2U>{0U, 0U}));
  EXPECT_EQ(fixture.preparation.schedule_reads, 0U);
}

TEST(ScheduledSession, SparseOrEmptyWarmupCannotWaiveMandatoryDuringObservation) {
  for (const bool empty : {false, true}) {
    queue::RingSpscQueue queue{{8U}, {64U}};
    w::R0Package package(queue);
    Fixture fixture(queue, package);
    if (empty) {
      fixture.input.phases[0U].offered_count = 0U;
      fixture.preparation.deadlines[0U].clear();
    }
    EXPECT_TRUE(c::valid_scheduled_plan(fixture.input)); // no invented warmup minimum
    fixture.observer.observe_after_finish = true;
    const auto result = fixture.run();
    EXPECT_EQ(result.lifecycle.stop, c::ServiceSessionStop::observation_failure);
    EXPECT_FALSE(result.lifecycle.phases[1U].released);
    EXPECT_EQ(fixture.preparation.warmup.producer.primary.snapshot().completeness,
              s::StreamCompleteness::sealed_incomplete);
  }
}

TEST(ScheduledSession, ColdMappedSourceMismatchStopsBeforeAnyPhaseRelease) {
  for (const auto mutation : {0U, 1U, 2U, 3U}) {
    queue::RingSpscQueue queue{{8U}, {64U}};
    w::R0Package package(queue);
    Fixture fixture(queue, package);
    switch (mutation) {
    case 0U:
      fixture.preparation.deadlines[1U].pop_back();
      break;
    case 1U:
      fixture.preparation.deadlines[1U][0U] = 6999U;
      break;
    case 2U:
      fixture.preparation.deadlines[1U][0U] = 8000U;
      break;
    default:
      fixture.preparation.deadlines[1U] = {7001U, 7000U, 7000U};
      break;
    }
    const auto result = fixture.run();
    EXPECT_EQ(result.lifecycle.stop, c::ServiceSessionStop::invalid_plan);
    EXPECT_FALSE(result.lifecycle.phases[0U].released);
    EXPECT_EQ(fixture.preparation.warmup.producer.requests, 0U);
  }
}

TEST(ScheduledSession, PlanIdentityBootstrapAndResourceBoundsAreExplicit) {
  const auto original = plan();
  ASSERT_TRUE(c::valid_scheduled_plan(original));
  for (const auto mutation : {0U, 1U, 2U, 3U, 4U}) {
    auto invalid = original;
    switch (mutation) {
    case 0U:
      invalid.phases[1U].schedule_id = invalid.phases[0U].schedule_id;
      break;
    case 1U:
      invalid.phases[1U].namespace_id = invalid.phases[0U].namespace_id;
      break;
    case 2U:
      --invalid.bounds.phases[0U].duration_ticks;
      break;
    case 3U:
      invalid.phases[1U].source_horizon_ticks = invalid.phases[1U].source_origin_ticks;
      break;
    default:
      invalid.bounds.phases[1U].producer_attempt_limit = 2U;
      break;
    }
    EXPECT_FALSE(c::valid_scheduled_plan(invalid));
  }
}

TEST(ScheduledSession, ResetFailureAndStorageReuseNeverStartAnotherMeasurement) {
  queue::RingSpscQueue queue{{8U}, {64U}};
  w::R0Package package(queue);
  Fixture fixture(queue, package);
  fixture.preparation.reject_reset = true;
  const auto result = fixture.run();
  EXPECT_EQ(result.lifecycle.stop, c::ServiceSessionStop::reset_failure);
  EXPECT_TRUE(result.lifecycle.phases[0U].validated);
  EXPECT_FALSE(result.lifecycle.phases[1U].released);
  EXPECT_EQ(fixture.preparation.warmup.producer.primary.snapshot().completeness,
            s::StreamCompleteness::sealed_complete);
  EXPECT_EQ(fixture.run().lifecycle.stop, c::ServiceSessionStop::storage_already_used);
  EXPECT_EQ(fixture.threads.starts, (std::array<unsigned, 2U>{1U, 1U}));
}

TEST(ScheduledSession, CheckedSourceTranslationPreservesHalfOpenDeadlineTies) {
  const auto input = plan();
  const std::array<std::uint64_t, 3U> deadlines{7000U, 7000U, 7999U};
  EXPECT_TRUE(c::scheduled_source_matches(input.phases[1U], {deadlines, 7000U, 8000U}));
  std::uint64_t target = 0U;
  EXPECT_TRUE(l::detail::checked_measurement_deadline({90000U, 7000U, 7999U}, target));
  EXPECT_EQ(target, 90999U);
  EXPECT_FALSE(l::detail::checked_measurement_deadline(
      {std::numeric_limits<std::uint64_t>::max(), 7000U, 7999U}, target));
}

} // namespace
