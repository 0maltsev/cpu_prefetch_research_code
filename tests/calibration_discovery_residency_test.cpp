#include "cpu_prefetch/calibration/discovery_residency_observer.hpp"
#include "discovery_backend_test_support.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cerrno>
#include <memory>

namespace {
namespace calibration = cpu_prefetch::calibration;
namespace platform = cpu_prefetch::platform;
namespace timing = cpu_prefetch::timing;
using Phase = calibration::DiscoverySessionPhase;
using Moment = calibration::DiscoveryResidencyMoment;
using Stop = calibration::DiscoveryResidencyStop;

class Clock final {
public:
  std::uint64_t next_tick{1U};
  std::uint64_t reads{0U};
  std::optional<std::uint64_t> failed_read;
  auto read() noexcept -> timing::ClockReadResult {
    ++reads;
    const auto tick = next_tick++;
    return {failed_read == reads ? timing::ClockReadStatus::call_failed
                                 : timing::ClockReadStatus::ok,
            {tick, tick}};
  }
};

struct Query final {
  platform::PageResidencyQueryResult result{0, 0};
  std::size_t calls{0U};
  std::size_t writes{2U};
  int node{1};
  Clock* clock{nullptr};
  std::optional<std::uint64_t> end_tick;
  std::atomic<std::uint32_t>* finish{nullptr};
  auto query_pages(std::span<void* const>, std::span<int> nodes) noexcept
      -> platform::PageResidencyQueryResult {
    ++calls;
    std::fill_n(nodes.begin(), std::min(writes, nodes.size()), node);
    if (clock != nullptr && end_tick.has_value()) {
      clock->next_tick = *end_tick;
    }
    if (finish != nullptr) {
      finish->store(3U, std::memory_order_release);
    }
    return result;
  }
};

struct Relax final {
  std::uint64_t polls{0U};
  void relax() noexcept { ++polls; }
};

constexpr calibration::DiscoverySessionPlan kPlan{100U, 100U, 8U, 8U, 20U, 8U, 1000U};

struct Fixture final {
  alignas(4096) std::array<std::byte, 8192U> mapping{};
  std::array<std::array<void*, 2U>, 6U> addresses{};
  std::array<std::array<int, 2U>, 6U> nodes{};
  std::array<platform::PreparedPageResidencyQuery, 6U> queries{
      make_query(0U), make_query(1U), make_query(2U),
      make_query(3U), make_query(4U), make_query(5U)};
  std::array<calibration::DiscoveryResidencyRegion, 1U> regions{{{mapping, 1U}}};
  std::array<calibration::DiscoveryResidencySample, 6U> samples{
      calibration::DiscoveryResidencySample{{Phase::warmup, Moment::before, 0U, 0U},
                                            queries[0U]},
      calibration::DiscoveryResidencySample{{Phase::warmup, Moment::during, 0U, 5U},
                                            queries[1U]},
      calibration::DiscoveryResidencySample{{Phase::warmup, Moment::after, 0U, 0U},
                                            queries[2U]},
      calibration::DiscoveryResidencySample{
          {Phase::measurement, Moment::before, 0U, 0U}, queries[3U]},
      calibration::DiscoveryResidencySample{
          {Phase::measurement, Moment::during, 0U, 5U}, queries[4U]},
      calibration::DiscoveryResidencySample{{Phase::measurement, Moment::after, 0U, 0U},
                                            queries[5U]}};
  Clock clock;
  Query query;
  Relax relax;
  std::atomic<std::uint32_t> finished{0U};

  auto observer() {
    return calibration::PreparedDiscoveryResidencyObserver(
        kPlan, calibration::DiscoveryResidencyControls{4096U, 10U}, regions, samples,
        clock, query, relax);
  }

private:
  auto make_query(std::size_t index) -> platform::PreparedPageResidencyQuery {
    const bool during = index == 1U || index == 4U;
    return {during ? std::span(mapping).subspan(4096U) : std::span(mapping), 4096U,
            std::span(addresses[index]).first(during ? 1U : 2U),
            std::span(nodes[index]).first(during ? 1U : 2U)};
  }
};

TEST(DiscoveryResidency, KeepsEveryRawSnapshotAndExplicitPartialDuringCoverage) {
  Fixture fixture;
  auto observer = fixture.observer();
  ASSERT_TRUE(observer.before_phase(Phase::warmup));
  fixture.clock.next_tick = 13U;
  ASSERT_TRUE(observer.during_phase(Phase::warmup, {10U, 100U}, fixture.finished));
  EXPECT_EQ(fixture.relax.polls, 2U);
  fixture.clock.next_tick = 120U;
  ASSERT_TRUE(observer.after_phase(Phase::warmup));
  ASSERT_TRUE(observer.before_phase(Phase::measurement));
  fixture.clock.next_tick = 135U;
  ASSERT_TRUE(
      observer.during_phase(Phase::measurement, {130U, 100U}, fixture.finished));
  fixture.clock.next_tick = 240U;
  ASSERT_TRUE(observer.after_phase(Phase::measurement));
  EXPECT_EQ(fixture.query.calls, 6U);
  for (const auto& row : fixture.samples) {
    EXPECT_EQ(row.stop, Stop::sampled);
    EXPECT_TRUE(row.query.has_value());
    EXPECT_TRUE(row.begin.has_value());
    EXPECT_TRUE(row.end.has_value());
    const bool during = row.request.moment == Moment::during;
    EXPECT_EQ(row.pages.page_status().size(), during ? 1U : 2U);
    EXPECT_EQ(row.pages.page_addresses().front(),
              fixture.mapping.data() + (during ? 4096U : 0U));
    EXPECT_TRUE(std::all_of(row.pages.page_status().begin(),
                            row.pages.page_status().end(),
                            [](int node) { return node == 1; }));
  }
  EXPECT_FALSE(observer.sequence_rejected());
  EXPECT_FALSE(observer.before_phase(Phase::warmup));
  EXPECT_TRUE(observer.sequence_rejected());
  EXPECT_EQ(fixture.query.calls, 6U);
}

TEST(DiscoveryResidency, BadPlansCannotMutateOutputOrHideMissingCoverage) {
  for (unsigned mutant = 0U; mutant < 7U; ++mutant) {
    Fixture fixture;
    switch (mutant) {
    case 0U:
      fixture.samples[1U].request.offset_ticks = 100U;
      break;
    case 1U:
      fixture.samples[1U].request.region_index = 1U;
      break;
    case 2U:
      fixture.samples[1U].request.moment = Moment::before;
      break;
    case 3U:
      fixture.samples[0U].request.phase = Phase::measurement;
      break;
    case 4U:
      fixture.addresses[0U][1U] = fixture.mapping.data();
      break;
    case 5U:
      fixture.regions[0U].expected_node = std::numeric_limits<std::uint32_t>::max();
      break;
    case 6U:
      fixture.samples[1U].wait_polls = 1U;
      break;
    default:
      FAIL();
      return;
    }
    EXPECT_THROW(static_cast<void>(fixture.observer()), std::invalid_argument);
    EXPECT_EQ(fixture.query.calls, 0U);
    for (const auto& row : fixture.samples) {
      EXPECT_EQ(row.stop, Stop::not_started);
      EXPECT_FALSE(row.query.has_value());
      EXPECT_TRUE(std::all_of(row.pages.page_status().begin(),
                              row.pages.page_status().end(),
                              [](int node) { return node == -1; }));
    }
  }
}

TEST(DiscoveryResidency, QueryAliasAndPartialPreRunCoverageAreRejected) {
  Fixture fixture;
  platform::PreparedPageResidencyQuery aliased(
      fixture.mapping, 4096U, fixture.addresses[0U], fixture.nodes[0U]);
  const auto original = fixture.samples[3U].request;
  std::destroy_at(&fixture.samples[3U]);
  std::construct_at(&fixture.samples[3U], original, aliased);
  EXPECT_THROW(static_cast<void>(fixture.observer()), std::invalid_argument);
  std::destroy_at(&fixture.samples[3U]);
  std::construct_at(&fixture.samples[3U], original, fixture.queries[3U]);
  const auto first = fixture.samples[0U].request;
  std::destroy_at(&fixture.samples[0U]);
  std::construct_at(&fixture.samples[0U], first, fixture.queries[1U]);
  EXPECT_THROW(static_cast<void>(fixture.observer()), std::invalid_argument);
}

TEST(DiscoveryResidency,
     FailedQueryKeepsErrnoStatusesAndIndependentEarlierAndLaterSnapshots) {
  Fixture fixture;
  auto observer = fixture.observer();
  ASSERT_TRUE(observer.before_phase(Phase::warmup));
  fixture.clock.next_tick = 15U;
  fixture.query.result = {-1, EPERM};
  fixture.query.writes = 0U;
  EXPECT_FALSE(observer.during_phase(Phase::warmup, {10U, 100U}, fixture.finished));
  EXPECT_EQ(fixture.samples[1U].stop, Stop::query_failure);
  EXPECT_EQ(fixture.nodes[0U], (std::array<int, 2U>{1, 1}));
  EXPECT_EQ(fixture.nodes[1U][0U], -1);
  const auto result = fixture.samples[1U].query;
  if (!result.has_value()) {
    FAIL();
    return;
  }
  EXPECT_EQ(result->syscall_return, -1);
  EXPECT_EQ(result->error_number, EPERM);
  fixture.query.result = {0, 0};
  fixture.query.writes = 2U;
  fixture.clock.next_tick = 120U;
  EXPECT_TRUE(observer.after_phase(Phase::warmup));
  EXPECT_EQ(fixture.nodes[2U], (std::array<int, 2U>{1, 1}));
  EXPECT_EQ(fixture.nodes[1U][0U], -1);
}

TEST(DiscoveryResidency, WrongNodeAndUnwrittenPageStatusCannotPass) {
  for (const bool partial : {false, true}) {
    Fixture fixture;
    auto observer = fixture.observer();
    fixture.query.node = partial ? 1 : 0;
    fixture.query.writes = partial ? 1U : 2U;
    EXPECT_FALSE(observer.before_phase(Phase::warmup));
    EXPECT_EQ(fixture.samples[0U].stop, Stop::wrong_node);
    EXPECT_TRUE(fixture.samples[0U].query.has_value());
    EXPECT_EQ(fixture.samples[1U].stop, Stop::not_started);
  }
}

TEST(DiscoveryResidency, EveryClockFailureAndClockRegressionRemainActualPartialFacts) {
  for (const std::uint64_t failed_read : {1U, 2U, 3U, 4U}) {
    Fixture fixture;
    auto observer = fixture.observer();
    fixture.clock.failed_read = failed_read;
    if (failed_read <= 2U) {
      EXPECT_FALSE(observer.before_phase(Phase::warmup));
      EXPECT_EQ(fixture.samples[0U].stop, Stop::clock_failure);
      EXPECT_EQ(fixture.query.calls, failed_read == 2U ? 1U : 0U);
    } else {
      ASSERT_TRUE(observer.before_phase(Phase::warmup));
      fixture.clock.next_tick = 15U;
      EXPECT_FALSE(observer.during_phase(Phase::warmup, {10U, 100U}, fixture.finished));
      EXPECT_EQ(fixture.samples[1U].stop, Stop::clock_failure);
      EXPECT_EQ(fixture.query.calls, failed_read == 4U ? 2U : 1U);
    }
  }
  Fixture fixture;
  auto observer = fixture.observer();
  ASSERT_TRUE(observer.before_phase(Phase::warmup));
  fixture.clock.next_tick = 1U;
  EXPECT_FALSE(observer.during_phase(Phase::warmup, {10U, 100U}, fixture.finished));
  EXPECT_EQ(fixture.samples[1U].stop, Stop::clock_regression);
  EXPECT_EQ(fixture.samples[1U].prior_controller_tick, 2U);
  EXPECT_EQ(fixture.query.calls, 1U);
}

TEST(DiscoveryResidency, LateObservationAndLateQueryCannotMasqueradeAsDuringCapture) {
  for (const bool query_overrun : {false, true}) {
    Fixture fixture;
    auto observer = fixture.observer();
    ASSERT_TRUE(observer.before_phase(Phase::warmup));
    fixture.clock.next_tick = query_overrun ? 15U : 110U;
    fixture.query.clock = &fixture.clock;
    fixture.query.end_tick = 110U;
    EXPECT_FALSE(observer.during_phase(Phase::warmup, {10U, 100U}, fixture.finished));
    EXPECT_EQ(fixture.samples[1U].stop, Stop::outside_window);
    EXPECT_EQ(fixture.samples[1U].query.has_value(), query_overrun);
    EXPECT_EQ(fixture.query.calls, query_overrun ? 2U : 1U);
  }
}

TEST(DiscoveryResidency, WorkerCompletionBeforeOrDuringQueryIsRetainedAndRejected) {
  for (const bool during_query : {false, true}) {
    Fixture fixture;
    auto observer = fixture.observer();
    ASSERT_TRUE(observer.before_phase(Phase::warmup));
    fixture.clock.next_tick = 15U;
    if (during_query) {
      fixture.query.finish = &fixture.finished;
    } else {
      fixture.finished.store(1U, std::memory_order_release);
    }
    EXPECT_FALSE(observer.during_phase(Phase::warmup, {10U, 100U}, fixture.finished));
    EXPECT_EQ(fixture.samples[1U].stop, Stop::workers_finished);
    EXPECT_EQ(fixture.samples[1U].query.has_value(), during_query);
    EXPECT_EQ(fixture.samples[1U].finished_before, during_query ? 0U : 1U);
  }
}

TEST(DiscoveryResidency,
     FiniteWaitExhaustionRetainsLastClockWithoutSamplingOrExtending) {
  Fixture fixture;
  fixture.samples[1U].request.offset_ticks = 90U;
  auto observer = fixture.observer();
  ASSERT_TRUE(observer.before_phase(Phase::warmup));
  fixture.clock.next_tick = 15U;
  EXPECT_FALSE(observer.during_phase(Phase::warmup, {10U, 100U}, fixture.finished));
  EXPECT_EQ(fixture.samples[1U].stop, Stop::wait_exhausted);
  EXPECT_EQ(fixture.samples[1U].wait_polls, 10U);
  EXPECT_EQ(fixture.query.calls, 1U);
}

TEST(DiscoveryResidency, EveryDeclaredRegionRequiresCompletePhaseCoverage) {
  Fixture fixture;
  alignas(4096) std::array<std::byte, 4096U> second{};
  const std::array regions{fixture.regions[0U],
                           calibration::DiscoveryResidencyRegion{second, 0U}};
  EXPECT_THROW((calibration::PreparedDiscoveryResidencyObserver(
                   kPlan, calibration::DiscoveryResidencyControls{4096U, 10U}, regions,
                   fixture.samples, fixture.clock, fixture.query, fixture.relax)),
               std::invalid_argument);
  EXPECT_EQ(fixture.query.calls, 0U);
  EXPECT_EQ(fixture.samples[0U].stop, Stop::not_started);
}

TEST(DiscoveryResidency, WrongPageReadbackBlocksRealSessionBeforeAnyQueueAttempt) {
  namespace support = cpu_prefetch::test_support;
  Fixture fixture;
  fixture.query.node = 0;
  auto preparation =
      std::make_unique<support::SoftwareOnlyDiscoveryPreparation<20'000U>>();
  support::DiscoveryTestClock clock;
  support::DiscoveryTestRelax relax;
  calibration::DiscoveryRingPhaseBackend backend(support::kDiscoveryTestPlan, clock,
                                                 *preparation);
  calibration::PreparedDiscoveryResidencyObserver observer(
      support::kDiscoveryTestPlan, calibration::DiscoveryResidencyControls{4096U, 10U},
      fixture.regions, fixture.samples, clock, fixture.query, relax);
  const auto result = calibration::run_discovery_session(
      support::kDiscoveryTestPlan, clock, backend, relax, observer);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::observation_failure);
  EXPECT_EQ(fixture.samples[0U].stop, Stop::wrong_node);
  EXPECT_EQ(fixture.query.calls, 1U);
  EXPECT_FALSE(result.origins[0U].has_value());
  EXPECT_FALSE(result.origins[1U].has_value());
  EXPECT_EQ(preparation->producer_phase(true).attempted, 0U);
  EXPECT_EQ(preparation->consumer_phase(true).consumed, 0U);
  EXPECT_EQ(fixture.samples[1U].stop, Stop::not_started);
}

struct ControlledQuery final {
  Query& pages;
  Clock& clock;
  calibration::DiscoveryObservationStatus status{
      calibration::DiscoveryObservationStatus::accepted};
  std::optional<calibration::DiscoveryResidencyRequest> observed;
  std::optional<std::uint64_t> advance_to;
  std::size_t controls{0U};
  bool group_complete{true};
  auto control_group_complete(Phase, Moment) const noexcept -> bool {
    return group_complete;
  }
  auto observe_controls(calibration::DiscoveryResidencyRequest request) noexcept
      -> calibration::DiscoveryObservationStatus {
    ++controls;
    observed = request;
    if (advance_to.has_value()) {
      clock.next_tick = *advance_to;
    }
    return status;
  }
  auto query_pages(std::span<void* const> addresses, std::span<int> nodes) noexcept
      -> platform::PageResidencyQueryResult {
    return pages.query_pages(addresses, nodes);
  }
};

TEST(DiscoveryResidency, ControlsShareExactRequestAndRetainIndependentPageEvidence) {
  for (const auto status : {calibration::DiscoveryObservationStatus::accepted,
                            calibration::DiscoveryObservationStatus::rejected}) {
    Fixture fixture;
    ControlledQuery query{fixture.query, fixture.clock, status, {}, {}};
    calibration::PreparedDiscoveryResidencyObserver observer(
        kPlan, calibration::DiscoveryResidencyControls{4096U, 10U}, fixture.regions,
        fixture.samples, fixture.clock, query, fixture.relax);
    EXPECT_EQ(observer.before_phase(Phase::warmup),
              status == calibration::DiscoveryObservationStatus::accepted);
    EXPECT_EQ(query.controls, 1U);
    EXPECT_EQ(fixture.query.calls, 1U);
    const auto observed = query.observed;
    ASSERT_TRUE(observed.has_value());
    if (observed.has_value()) {
      EXPECT_EQ(observed->moment, Moment::before);
      EXPECT_EQ(observed->phase, Phase::warmup);
      EXPECT_EQ(observed->region_index, 0U);
    }
    EXPECT_EQ(fixture.samples[0U].controls, status);
    EXPECT_TRUE(fixture.samples[0U].query.has_value());
    EXPECT_TRUE(fixture.samples[0U].end.has_value());
    EXPECT_EQ(fixture.samples[0U].stop,
              status == calibration::DiscoveryObservationStatus::accepted
                  ? Stop::sampled
                  : Stop::control_failure);
  }
}

TEST(DiscoveryResidency, ControlTimeIsIncludedInTheDuringWindowCheck) {
  Fixture fixture;
  ControlledQuery query{fixture.query,
                        fixture.clock,
                        calibration::DiscoveryObservationStatus::accepted,
                        {},
                        {}};
  calibration::PreparedDiscoveryResidencyObserver observer(
      kPlan, calibration::DiscoveryResidencyControls{4096U, 10U}, fixture.regions,
      fixture.samples, fixture.clock, query, fixture.relax);
  ASSERT_TRUE(observer.before_phase(Phase::warmup));
  fixture.clock.next_tick = 15U;
  query.advance_to = 110U;
  EXPECT_FALSE(observer.during_phase(Phase::warmup, {10U, 100U}, fixture.finished));
  EXPECT_EQ(fixture.samples[1U].controls,
            calibration::DiscoveryObservationStatus::accepted);
  EXPECT_TRUE(fixture.samples[1U].query.has_value());
  EXPECT_EQ(fixture.samples[1U].stop, Stop::outside_window);
  EXPECT_EQ(query.controls, 2U);
}

TEST(DiscoveryResidency, PriorControlResultCannotBeReusedAsFreshEvidence) {
  Fixture fixture;
  fixture.samples[0U].controls = calibration::DiscoveryObservationStatus::accepted;
  EXPECT_THROW(static_cast<void>(fixture.observer()), std::invalid_argument);
  EXPECT_EQ(fixture.query.calls, 0U);
}

TEST(DiscoveryResidency, MissingMandatoryControlGroupPreventsPhaseAcceptance) {
  for (const auto missing : {Moment::before, Moment::during, Moment::after}) {
    Fixture fixture;
    ControlledQuery query{fixture.query,
                          fixture.clock,
                          calibration::DiscoveryObservationStatus::not_configured,
                          {},
                          {}};
    calibration::PreparedDiscoveryResidencyObserver observer(
        kPlan, calibration::DiscoveryResidencyControls{4096U, 10U}, fixture.regions,
        fixture.samples, fixture.clock, query, fixture.relax);
    query.group_complete = missing != Moment::before;
    EXPECT_EQ(observer.before_phase(Phase::warmup), missing != Moment::before);
    if (missing == Moment::before) {
      continue;
    }
    fixture.clock.next_tick = 15U;
    query.group_complete = missing != Moment::during;
    EXPECT_EQ(observer.during_phase(Phase::warmup, {10U, 100U}, fixture.finished),
              missing != Moment::during);
    if (missing == Moment::during) {
      continue;
    }
    fixture.clock.next_tick = 120U;
    query.group_complete = false;
    EXPECT_FALSE(observer.after_phase(Phase::warmup));
  }
}

} // namespace
