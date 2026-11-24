#include "cpu_prefetch/calibration/discovery_control_query.hpp"

#include <gtest/gtest.h>

#include <memory>

namespace {
namespace calibration = cpu_prefetch::calibration;
namespace platform = cpu_prefetch::platform;
using Phase = calibration::DiscoverySessionPhase;
using Moment = calibration::DiscoveryResidencyMoment;
using Status = calibration::DiscoveryObservationStatus;
using Stop = calibration::DiscoveryControlStop;

struct Monitor final {
  int tid;
  std::uint32_t cpu;
  std::uint64_t faults{10U};
  std::uint64_t switches{20U};
  std::uint64_t calls{0U};
  std::size_t affinity_count{1U};
  bool fail{false};
  auto sample(platform::ThreadMonitorScratch scratch) noexcept
      -> platform::ThreadControlSample {
    ++calls;
    platform::ThreadControlSample result{};
    result.stat_before = platform::ThreadStatObservation{
        tid, 'R', 123U, faults, 0U, static_cast<int>(cpu)};
    result.stat_after = result.stat_before;
    result.status = platform::ThreadStatusObservation{tid, 101, switches, 0U};
    result.affinity_mask = scratch.affinity;
    result.affinity_cpu_count = affinity_count;
    result.singleton_affinity_cpu = cpu;
    result.stop = fail ? platform::ThreadMonitorStop::file_read_failure
                       : platform::ThreadMonitorStop::sampled;
    return result;
  }
};

struct Hardware final {
  std::size_t calls{0U};
  bool accepted{true};
  auto sample(cpu_prefetch::protocol::RequestedHardwareState state,
              platform::PrefetchReadbackSample& result) noexcept -> bool {
    ++calls;
    result.attempted = true;
    result.requested_state = state;
    result.stop = accepted ? platform::PrefetchReadbackStop::sampled
                           : platform::PrefetchReadbackStop::value_mismatch;
    return accepted;
  }
};

struct Pages final {
  std::size_t calls{0U};
  auto query_pages(std::span<void* const>, std::span<int> nodes) noexcept
      -> platform::PageResidencyQueryResult {
    ++calls;
    for (auto& node : nodes) {
      node = 3;
    }
    return {0, 0};
  }
};

struct Scratch final {
  std::array<char, 64U> before{};
  std::array<char, 64U> status{};
  std::array<char, 64U> after{};
  std::array<unsigned long, 2U> affinity{};
  auto span() noexcept -> platform::ThreadMonitorScratch {
    return {before, status, after, affinity};
  }
};

struct Fixture final {
  std::array<std::array<Scratch, 2U>, 6U> scratch{};
  std::array<calibration::DiscoveryControlSample, 6U> samples{};
  calibration::DiscoveryControlPlan plan{
      {2U, 8U}, {111, 222}, {}, cpu_prefetch::protocol::RequestedHardwareState::h0};
  Monitor producer{111, 2U};
  Monitor consumer{222, 8U};
  Hardware hardware;
  Pages pages;

  Fixture() {
    for (std::size_t index = 0U; index < samples.size(); ++index) {
      samples[index].request = {static_cast<Phase>(index / 3U),
                                static_cast<Moment>(index % 3U), 0U,
                                index % 3U == 1U ? 50U : 0U};
      samples[index].scratch = {scratch[index][0U].span(), scratch[index][1U].span()};
    }
  }
  auto query() {
    return calibration::DiscoveryControlQuery<Pages, Monitor, Hardware>{
        plan, {&producer, &consumer}, hardware, pages, samples};
  }
};

TEST(DiscoveryControls, RetainsSixScheduledGroupsAndIndependentPageQuery) {
  Fixture fixture;
  auto query = fixture.query();
  for (const auto& row : fixture.samples) {
    EXPECT_FALSE(query.control_group_complete(row.request.phase, row.request.moment));
    EXPECT_EQ(query.observe_controls(row.request), Status::accepted);
    EXPECT_TRUE(query.control_group_complete(row.request.phase, row.request.moment));
    ASSERT_TRUE(row.workers[0U].has_value());
    ASSERT_TRUE(row.workers[1U].has_value());
    EXPECT_TRUE(row.hardware.succeeded());
  }
  EXPECT_EQ(fixture.producer.calls, 6U);
  EXPECT_EQ(fixture.consumer.calls, 6U);
  EXPECT_EQ(fixture.hardware.calls, 6U);
  std::array<int, 1U> nodes{};
  const auto result = query.query_pages({}, nodes);
  EXPECT_EQ(result.syscall_return, 0);
  EXPECT_EQ(nodes[0U], 3);
  EXPECT_EQ(fixture.pages.calls, 1U);
}

TEST(DiscoveryControls, MissingScheduledRequestIsNotCompleteAndReuseIsRejected) {
  Fixture fixture;
  auto query = fixture.query();
  auto request = fixture.samples[0U].request;
  request.region_index = 1U;
  EXPECT_EQ(query.observe_controls(request), Status::not_configured);
  EXPECT_EQ(fixture.producer.calls, 0U);
  EXPECT_FALSE(query.control_group_complete(Phase::warmup, Moment::before));
  EXPECT_EQ(query.observe_controls(fixture.samples[0U].request), Status::accepted);
  EXPECT_EQ(query.observe_controls(fixture.samples[0U].request), Status::rejected);
  EXPECT_EQ(fixture.producer.calls, 1U);
  EXPECT_EQ(fixture.samples[0U].stop, Stop::sampled);
}

TEST(DiscoveryControls, InvalidEnumsCannotAliasAnotherGroup) {
  Fixture fixture;
  auto query = fixture.query();
  auto request = fixture.samples[0U].request;
  // Deliberately exercise the public boundary's invalid-enum rejection.
  // NOLINTNEXTLINE(clang-analyzer-optin.core.EnumCastOutOfRange)
  request.moment = static_cast<Moment>(3U);
  EXPECT_EQ(query.observe_controls(request), Status::rejected);
  EXPECT_FALSE(query.control_group_complete(request.phase, request.moment));
  EXPECT_EQ(fixture.producer.calls, 0U);
  fixture.plan.hardware_state =
      cpu_prefetch::protocol::RequestedHardwareState::not_applicable;
  EXPECT_THROW(static_cast<void>(fixture.query()), std::invalid_argument);
}

TEST(DiscoveryControls, FailedOwnerStillRetainsOtherOwnerAndHardware) {
  Fixture fixture;
  fixture.producer.fail = true;
  fixture.hardware.accepted = false;
  auto query = fixture.query();
  EXPECT_EQ(query.observe_controls(fixture.samples[0U].request), Status::rejected);
  EXPECT_EQ(fixture.samples[0U].stop, Stop::thread_read_failure);
  const auto other = fixture.samples[0U].workers[1U];
  ASSERT_TRUE(other.has_value());
  if (other.has_value()) {
    EXPECT_TRUE(other->succeeded());
  }
  EXPECT_EQ(fixture.hardware.calls, 1U);
  EXPECT_EQ(fixture.samples[0U].hardware.stop,
            platform::PrefetchReadbackStop::value_mismatch);
}

TEST(DiscoveryControls, RejectsWrongCpuAffinityAndIdentity) {
  for (const auto variant : {0, 1, 2}) {
    Fixture fixture;
    if (variant == 0) {
      fixture.producer.cpu = 4U;
    }
    if (variant == 1) {
      fixture.producer.affinity_count = 2U;
    }
    if (variant == 2) {
      fixture.producer.tid = 333;
    }
    auto query = fixture.query();
    EXPECT_EQ(query.observe_controls(fixture.samples[0U].request), Status::rejected);
    EXPECT_EQ(fixture.samples[0U].stop, Stop::owner_mismatch);
  }
}

TEST(DiscoveryControls, RejectsHardwareMismatchWithoutLosingThreadFacts) {
  Fixture fixture;
  fixture.hardware.accepted = false;
  auto query = fixture.query();
  EXPECT_EQ(query.observe_controls(fixture.samples[0U].request), Status::rejected);
  EXPECT_EQ(fixture.samples[0U].stop, Stop::hardware_failure);
  const auto owner = fixture.samples[0U].workers[0U];
  ASSERT_TRUE(owner.has_value());
  if (owner.has_value()) {
    EXPECT_TRUE(owner->succeeded());
  }
}

TEST(DiscoveryControls, UsesExplicitPhaseLimitsAndRetainsUnboundedObservations) {
  Fixture fixture;
  fixture.plan.limits[1U][0U].minor_faults = 0U;
  auto query = fixture.query();
  for (std::size_t index = 0U; index < 4U; ++index) {
    fixture.producer.faults += 5U;
    EXPECT_EQ(query.observe_controls(fixture.samples[index].request), Status::accepted);
  }
  ++fixture.producer.faults;
  EXPECT_EQ(query.observe_controls(fixture.samples[4U].request), Status::rejected);
  EXPECT_EQ(fixture.samples[4U].stop, Stop::disturbance_limit);
  const auto owner = fixture.samples[4U].workers[0U];
  ASSERT_TRUE(owner.has_value());
  if (owner.has_value()) {
    const auto observed = owner->stat_after;
    ASSERT_TRUE(observed.has_value());
    if (observed.has_value()) {
      EXPECT_EQ(observed->minor_faults, 31U);
    }
  }
}

TEST(DiscoveryControls, RejectsCounterRegressionAgainstMostRecentGroup) {
  for (const bool faults : {false, true}) {
    Fixture fixture;
    auto query = fixture.query();
    ASSERT_EQ(query.observe_controls(fixture.samples[0U].request), Status::accepted);
    fixture.producer.faults = 15U;
    fixture.producer.switches = 25U;
    ASSERT_EQ(query.observe_controls(fixture.samples[1U].request), Status::accepted);
    if (faults) {
      fixture.producer.faults = 14U;
    } else {
      fixture.producer.switches = 24U;
    }
    EXPECT_EQ(query.observe_controls(fixture.samples[2U].request), Status::rejected);
    EXPECT_EQ(fixture.samples[2U].stop, Stop::counter_regression);
  }
}

TEST(DiscoveryControls, RejectsAliasedScratchAndPriorEvidenceBeforeSampling) {
  for (const auto variant : {0, 1, 2, 3}) {
    Fixture fixture;
    if (variant == 0) {
      fixture.samples[1U].scratch[0U] = fixture.samples[0U].scratch[0U];
    }
    if (variant == 1) {
      fixture.samples[0U].attempted = true;
    }
    if (variant == 2) {
      fixture.samples[0U].scratch[0U].stat_after = {};
    }
    if (variant == 3) {
      fixture.samples[0U].request.phase = Phase::measurement;
    }
    EXPECT_THROW(static_cast<void>(fixture.query()), std::invalid_argument);
    EXPECT_EQ(fixture.producer.calls, 0U);
  }
}
} // namespace
