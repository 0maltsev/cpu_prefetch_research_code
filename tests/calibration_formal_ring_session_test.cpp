#include "cpu_prefetch/calibration/formal_ring_session.hpp"
#include "discovery_backend_test_support.hpp"

#include <gtest/gtest.h>

#include <atomic>
#include <limits>
#include <memory>
#include <thread>

namespace {
using namespace cpu_prefetch;
namespace c = calibration;
namespace l = lifecycle;
namespace s = storage;
namespace t = timing;

template <typename T> auto required(const std::optional<T>& value) -> const T& {
  if (!value) {
    throw std::logic_error("required retained test observation absent");
  }
  return *value;
}
struct Capacity final {
  std::uint64_t primary;
  std::uint64_t demand;
  std::size_t queue;
};
thread_local bool consumer_worker = false;

class Clock final {
public:
  auto origin() const noexcept -> t::ClockOrigin { return {0U}; }
  auto read() noexcept -> t::ClockReadResult {
    if (consumer_worker) {
      if (auto* gate = consumer_gate.load(); gate != nullptr) {
        bool finished = false;
        for (std::size_t poll = 0U; poll < 1'000'000U; ++poll) {
          if (gate->arrivals_finished()) {
            finished = true;
            break;
          }
          std::this_thread::yield();
        }
        if (!finished) {
          return {t::ClockReadStatus::call_failed, {0U, 0U}};
        }
      }
    }
    const auto tick = next.fetch_add(1U);
    return {tick == fail_at ? t::ClockReadStatus::call_failed : t::ClockReadStatus::ok,
            {tick, tick * 1000U}};
  }
  std::atomic<l::TerminationControl*> consumer_gate{nullptr};
  std::atomic<std::uint64_t> next{1U};
  std::uint64_t fail_at{std::numeric_limits<std::uint64_t>::max()};
};

struct Phase final {
  protocol::RunId id;
  s::ProducerObservationStream producer_stream;
  s::ConsumerObservationStream consumer_stream;
  queue::detail::AlignedBlock producer_bytes;
  queue::detail::AlignedBlock consumer_bytes;
  c::RingDemandStream producer_demand;
  c::RingDemandStream consumer_demand;
  c::FormalRingProducerPhase producer;
  c::FormalRingConsumerPhase consumer;
  Phase(std::string name, Capacity capacity)
      : id(test_support::discovery_test_run_id(std::move(name))),
        producer_stream(id, capacity.primary), consumer_stream(id, capacity.primary),
        producer_bytes(c::ring_demand_storage_requirements(id, capacity.demand), 64U),
        consumer_bytes(c::ring_demand_storage_requirements(id, capacity.demand), 64U),
        producer_demand(id, c::RingWorker::producer, capacity.demand,
                        {producer_bytes.data(), producer_bytes.size()}),
        consumer_demand(id, c::RingWorker::consumer, capacity.demand,
                        {consumer_bytes.data(), consumer_bytes.size()}),
        producer{producer_demand, producer_stream, s::make_row_layout(id.value()), {}},
        consumer{consumer_demand, consumer_stream, s::make_row_layout(id.value()),
                 {17U},           {17U},           {}} {}
};
struct Preparation final {
  Phase warmup;
  Phase measurement;
  workload::EventArena event_arena{
      {8U, 64U, 4096U, workload::MasterSeed::from_hex(std::string(64U, '0')),
       "formal-ring-software-only"}};
  queue::RingSpscQueue queue;
  std::array<std::thread::id, 2U> owners;
  std::array<unsigned, 2U> prepares{};
  std::array<unsigned, 2U> resets{};
  explicit Preparation(Capacity capacity = {2048U, 4096U, 8U})
      : warmup("formal-warmup", capacity), measurement("formal-measurement", capacity),
        queue({capacity.queue}, {64U}) {}
  auto prepare_producer() -> bool {
    owners[0U] = std::this_thread::get_id();
    return ++prepares[0U] == 1U;
  }
  auto prepare_consumer() -> bool {
    owners[1U] = std::this_thread::get_id();
    return ++prepares[1U] == 1U;
  }
  auto before_measurement_producer() noexcept -> bool {
    ++resets[0U];
    return owners[0U] == std::this_thread::get_id();
  }
  auto before_measurement_consumer() noexcept -> bool {
    ++resets[1U];
    return owners[1U] == std::this_thread::get_id();
  }
  auto producer_phase(bool first) noexcept -> c::FormalRingProducerPhase& {
    return first ? warmup.producer : measurement.producer;
  }
  auto consumer_phase(bool first) noexcept -> c::FormalRingConsumerPhase& {
    return first ? warmup.consumer : measurement.consumer;
  }
  auto ring() noexcept -> queue::RingSpscQueue& { return queue; }
  auto arena() const noexcept -> const workload::EventArena& { return event_arena; }
};
constexpr c::ServiceSessionPlan kPlan{{{{1'000'000U, 2048U, 4096U, 10'000'000U},
                                        {1'000'000U, 2048U, 4096U, 10'000'000U}}},
                                      5'000'000U};
struct Threads final {
  std::array<std::thread, 2U> workers;
  auto start(c::RingWorker role, platform::WorkerEntry entry, void* context) -> bool {
    workers[role == c::RingWorker::producer ? 0U : 1U] = std::thread([=] {
      consumer_worker = role == c::RingWorker::consumer;
      entry(context);
    });
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
struct Fixture final {
  Preparation preparation;
  Clock clock;
  c::ServiceSessionPlan plan{kPlan};
  c::FormalRingSessionBackend<Clock, Preparation> backend{plan, clock, preparation};
  explicit Fixture(Capacity capacity = {2048U, 4096U, 8U}) : preparation(capacity) {
    for (auto& phase : plan.phases) {
      phase.producer_attempt_limit = std::min(capacity.primary, capacity.demand);
      phase.consumer_poll_limit = capacity.demand;
    }
  }
  auto prepare() -> bool {
    return backend.prepare_producer() && backend.prepare_consumer();
  }
  auto capture() noexcept -> decltype(auto) {
    return backend.phase(c::ServicePhase::warmup);
  }
};

TEST(FormalRingSession, PersistentRealCaptureJoinsDrainsAndResetsWithoutChangingArena) {
  Fixture fixture;
  auto& preparation = fixture.preparation;
  const auto content = preparation.arena().content_checksum();
  const auto order = preparation.arena().ordered_index_checksum();
  l::TerminationControl warmup({64U}), measurement({64U});
  c::ServiceSessionStorage storage({warmup, measurement});
  Threads threads;
  Observer observer;
  test_support::DiscoveryTestRelax relax;
  const auto result =
      c::run_formal_ring_session(fixture.backend, relax, observer, threads, storage);
  ASSERT_EQ(result.stop, c::ServiceSessionStop::complete);
  EXPECT_TRUE(result.queue_reset);
  EXPECT_EQ(preparation.prepares, (std::array<unsigned, 2U>{1U, 1U}));
  EXPECT_EQ(preparation.resets, (std::array<unsigned, 2U>{1U, 1U}));
  EXPECT_NE(preparation.owners[0U], preparation.owners[1U]);
  EXPECT_EQ(content, preparation.arena().content_checksum());
  EXPECT_EQ(order, preparation.arena().ordered_index_checksum());
  for (std::size_t index = 0U; index < 2U; ++index) {
    const auto& producer = preparation.producer_phase(index == 0U);
    const auto& consumer = preparation.consumer_phase(index == 0U);
    EXPECT_EQ(consumer.last_join.status, c::DiscoveryJoinStatus::exact);
    EXPECT_EQ(producer.accepted, consumer.consumed);
    EXPECT_EQ(producer.demand.snapshot().row_count, producer.attempted);
    EXPECT_EQ(consumer.demand.snapshot().row_count, consumer.polls);
    EXPECT_EQ(producer.primary.snapshot().completeness,
              s::StreamCompleteness::sealed_complete);
    EXPECT_EQ(consumer.demand.snapshot().completeness,
              s::StreamCompleteness::sealed_complete);
    EXPECT_TRUE(result.phases[index].consumer.drained);
    const auto last =
        c::read_ring_demand_row(consumer.demand.snapshot(), consumer.polls - 1U);
    ASSERT_TRUE(last);
    EXPECT_EQ(required(last).outcome, c::RingAttemptOutcome::empty);
  }
}

TEST(FormalRingSession, ConsumerContinuouslyCapturesThroughDrainAfterProducerDeadline) {
  Fixture fixture;
  l::TerminationControl warmup({64U}), measurement({64U});
  c::ServiceSessionStorage storage({warmup, measurement});
  Threads threads;
  struct GatedObserver final {
    Clock& clock;
    std::array<l::TerminationControl*, 2U> gates;
    auto before_phase(c::ServicePhase phase) noexcept -> bool {
      clock.consumer_gate.store(gates[phase == c::ServicePhase::warmup ? 0U : 1U]);
      return true;
    }
    auto during_phase(c::ServicePhase, c::ServiceWindow,
                      const std::atomic<std::uint32_t>&) const noexcept -> bool {
      return true;
    }
    auto after_phase(c::ServicePhase) const noexcept -> bool { return true; }
  } observer{fixture.clock, {&warmup, &measurement}};
  test_support::DiscoveryTestRelax relax;
  const auto result =
      c::run_formal_ring_session(fixture.backend, relax, observer, threads, storage);
  ASSERT_EQ(result.stop, c::ServiceSessionStop::complete);
  for (std::size_t index = 0U; index < 2U; ++index) {
    const auto& consumer = fixture.preparation.consumer_phase(index == 0U);
    ASSERT_GT(consumer.consumed, 0U);
    EXPECT_EQ(consumer.polls, consumer.consumed + 1U);
    ASSERT_TRUE(result.phases[index].window);
    const auto endpoint = required(result.phases[index].window).producer_deadline_ticks;
    for (std::uint64_t row_index = 0U; row_index < consumer.polls; ++row_index) {
      const auto row = c::read_ring_demand_row(consumer.demand.snapshot(), row_index);
      ASSERT_TRUE(row);
      EXPECT_GE(required(row).before.sample.relative_picoseconds, endpoint);
    }
    EXPECT_EQ(consumer.last_join.status, c::DiscoveryJoinStatus::exact);
  }
}

TEST(FormalRingSession, RetainsFullEmptyAndExactPrimaryDemandBoundaries) {
  Fixture fixture({8U, 8U, 1U});
  ASSERT_TRUE(fixture.prepare());
  auto& capture = fixture.capture();
  EXPECT_EQ(capture.try_consumer_poll(0U).status, l::ConsumerPollStatus::empty);
  EXPECT_EQ(capture.try_producer_attempt({0U, 0U, 0U}).outcome,
            queue::EnqueueResult::accepted);
  EXPECT_EQ(capture.try_producer_attempt({1U, 0U, 1U}).outcome,
            queue::EnqueueResult::full);
  EXPECT_EQ(capture.try_consumer_poll(0U).status, l::ConsumerPollStatus::item);
  const auto p = c::read_ring_demand_row(
      fixture.preparation.warmup.producer_demand.snapshot(), 1U);
  const auto c = c::read_ring_demand_row(
      fixture.preparation.warmup.consumer_demand.snapshot(), 0U);
  ASSERT_TRUE(p);
  ASSERT_TRUE(c);
  EXPECT_EQ(required(p).attempt_ordinal, 1U);
  EXPECT_EQ(required(p).outcome, calibration::RingAttemptOutcome::full);
  EXPECT_EQ(required(p).advancing_ordinal, 0U);
  EXPECT_EQ(required(c).outcome, calibration::RingAttemptOutcome::empty);
  EXPECT_EQ(fixture.preparation.warmup.producer.primary.snapshot().row_count, 2U);
  EXPECT_EQ(fixture.preparation.warmup.consumer.primary.snapshot().row_count, 1U);
  const auto item = c::read_ring_demand_row(
      fixture.preparation.warmup.consumer_demand.snapshot(), 1U);
  ASSERT_TRUE(item);
  EXPECT_EQ(required(item).before.sample.relative_picoseconds,
            required(fixture.preparation.warmup.consumer.current.demand.before)
                .sample.relative_picoseconds);
}

TEST(FormalRingSession, PreAcquireFailureRetainsCurrentWithoutInventingDemand) {
  for (std::uint64_t failure = 1U; failure <= 3U; ++failure) {
    Fixture fixture;
    ASSERT_TRUE(fixture.prepare());
    fixture.clock.fail_at = failure;
    EXPECT_EQ(fixture.capture().try_producer_attempt({0U, 0U, 0U}).status,
              l::AttemptStatus::failure);
    const auto& row = fixture.preparation.warmup.producer;
    EXPECT_EQ(row.demand.snapshot().row_count, 0U);
    EXPECT_FALSE(row.current.capture.operation_performed);
    EXPECT_TRUE(row.current.failed_boundary);
    EXPECT_EQ(row.requests, 1U);
    fixture.backend.finalize_joined();
    EXPECT_EQ(row.primary.snapshot().completeness,
              s::StreamCompleteness::sealed_incomplete);
  }
  Fixture fixture;
  ASSERT_TRUE(fixture.prepare());
  fixture.clock.fail_at = 1U;
  EXPECT_EQ(fixture.capture().try_consumer_poll(0U).status,
            l::ConsumerPollStatus::failure);
  EXPECT_EQ(fixture.preparation.warmup.consumer.demand.snapshot().row_count, 0U);
  EXPECT_FALSE(fixture.preparation.warmup.consumer.current.operation);
}

TEST(FormalRingSession, FailedProducerDemandClocksRetainActualOperationAndStop) {
  for (const auto failure : {4U, 5U}) {
    Fixture fixture;
    ASSERT_TRUE(fixture.prepare());
    fixture.clock.fail_at = failure;
    const auto attempted = fixture.capture().try_producer_attempt({0U, 0U, 0U});
    EXPECT_EQ(attempted.status, l::AttemptStatus::failure);
    EXPECT_EQ(attempted.outcome, queue::EnqueueResult::accepted);
    const auto& phase = fixture.preparation.warmup.producer;
    const auto row = c::read_ring_demand_row(phase.demand.snapshot(), 0U);
    ASSERT_TRUE(row);
    EXPECT_EQ(required(row).outcome, c::RingAttemptOutcome::advanced);
    EXPECT_EQ(failure == 4U ? required(row).before.status : required(row).after.status,
              t::ClockReadStatus::call_failed);
    EXPECT_EQ(phase.accepted, 1U);
    EXPECT_FALSE(phase.current.primary);
    const auto prior_requests = phase.requests;
    EXPECT_EQ(fixture.capture().try_producer_attempt({1U, 0U, 1U}).status,
              l::AttemptStatus::failure);
    EXPECT_EQ(phase.requests, prior_requests);
    EXPECT_EQ(fixture.capture().try_consumer_poll(0U).status,
              l::ConsumerPollStatus::item);
  }
}

TEST(FormalRingSession, ConsumerClockFailureStillRunsImmutableActionAndRetainsDemand) {
  for (const auto offset : {1U, 2U, 3U, 4U, 5U}) {
    Fixture fixture;
    ASSERT_TRUE(fixture.prepare());
    ASSERT_EQ(fixture.capture().try_producer_attempt({0U, 0U, 0U}).status,
              l::AttemptStatus::complete);
    fixture.clock.fail_at = fixture.clock.next.load() + offset;
    EXPECT_EQ(fixture.capture().try_consumer_poll(0U).status,
              l::ConsumerPollStatus::failure);
    const auto& consumer = fixture.preparation.warmup.consumer;
    EXPECT_EQ(consumer.consumed, 1U);
    ASSERT_TRUE(consumer.current.access);
    EXPECT_EQ(required(consumer.current.access).status,
              workload::RecordAccessStatus::valid);
    const auto selected = fixture.preparation.arena().select({0U});
    EXPECT_EQ(consumer.state, workload::mix_consumer_state({17U}, selected.record_index,
                                                           selected.record->payload));
    ASSERT_TRUE(c::read_ring_demand_row(consumer.demand.snapshot(), 0U));
    EXPECT_FALSE(consumer.current.primary);
  }
}

TEST(FormalRingSession, RawCapacityFailureKeepsCommittedPrimaryAndFailedCurrent) {
  Fixture fixture({4U, 1U, 8U});
  ASSERT_TRUE(fixture.prepare());
  ASSERT_EQ(fixture.capture().try_producer_attempt({0U, 0U, 0U}).status,
            l::AttemptStatus::complete);
  EXPECT_EQ(fixture.capture().try_producer_attempt({1U, 0U, 1U}).status,
            l::AttemptStatus::failure);
  auto& row = fixture.preparation.warmup.producer;
  EXPECT_TRUE(row.demand.snapshot().overflowed);
  EXPECT_EQ(row.demand.snapshot().row_count, 1U);
  EXPECT_EQ(row.primary.snapshot().row_count, 2U);
  ASSERT_TRUE(row.current.primary);
  EXPECT_EQ(required(row.current.primary).logical_sequence.value, 1U);
  fixture.backend.finalize_joined();
  EXPECT_EQ(row.primary.snapshot().completeness,
            s::StreamCompleteness::sealed_incomplete);
}

TEST(FormalRingSession, PrimaryCapacityFailureKeepsRawAndActualCurrent) {
  Fixture fixture({1U, 4U, 8U});
  ASSERT_TRUE(fixture.prepare());
  ASSERT_EQ(fixture.capture().try_producer_attempt({0U, 0U, 0U}).status,
            l::AttemptStatus::complete);
  EXPECT_EQ(fixture.capture().try_producer_attempt({1U, 0U, 1U}).status,
            l::AttemptStatus::failure);
  const auto& row = fixture.preparation.warmup.producer;
  EXPECT_EQ(row.demand.snapshot().row_count, 2U);
  EXPECT_TRUE(row.primary.snapshot().overflowed);
  ASSERT_TRUE(row.current.primary);
  EXPECT_EQ(required(row.current.primary).logical_sequence.value, 1U);
}

TEST(FormalRingSession, MeasurementPreparationFailurePreservesCompletedWarmup) {
  Fixture fixture;
  l::TerminationControl warmup({64U}), measurement({64U});
  c::ServiceSessionStorage storage({warmup, measurement});
  Threads threads;
  Observer observer{1};
  test_support::DiscoveryTestRelax relax;
  const auto result =
      c::run_formal_ring_session(fixture.backend, relax, observer, threads, storage);
  ASSERT_EQ(result.stop, c::ServiceSessionStop::observation_failure);
  EXPECT_TRUE(result.phases[0U].validated);
  EXPECT_EQ(fixture.preparation.warmup.producer.primary.snapshot().completeness,
            s::StreamCompleteness::sealed_complete);
  EXPECT_EQ(fixture.preparation.measurement.producer.primary.snapshot().completeness,
            s::StreamCompleteness::sealed_incomplete);
  EXPECT_EQ(fixture.preparation.measurement.consumer.demand.snapshot().row_count, 0U);
}

TEST(FormalRingSession, InvalidPreparedIdentityAndBoundsCannotStartCapture) {
  Fixture fixture;
  fixture.plan.phases[0U].consumer_poll_limit = 4097U;
  EXPECT_TRUE(fixture.backend.prepare_producer());
  EXPECT_FALSE(fixture.backend.prepare_consumer());
  EXPECT_FALSE(fixture.backend.reset_quiescent());
}
} // namespace
