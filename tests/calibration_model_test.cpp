#include <gtest/gtest.h>

#include "cpu_prefetch/calibration/calibration.hpp"

#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

namespace calibration = cpu_prefetch::calibration;
namespace protocol = cpu_prefetch::protocol;
namespace queue = cpu_prefetch::queue;
namespace timing = cpu_prefetch::timing;

auto run_id(std::string value) -> protocol::RunId {
  auto parsed = protocol::RunId::parse(std::move(value), "$/test/run_id");
  if (!parsed) {
    throw std::logic_error("synthetic run ID is invalid");
  }
  return std::move(parsed).value();
}

auto reference(std::string id = "synthetic-artifact")
    -> calibration::EvidenceReference {
  return {std::move(id), std::string(64U, 'a')};
}

template <typename Value>
[[nodiscard]] auto require_optional(const std::optional<Value>& value) -> const Value& {
  if (!value.has_value()) {
    throw std::logic_error("required synthetic value is absent");
  }
  return value.value();
}

auto context_for(const calibration::ServiceCellKey& key) -> calibration::StageAContext {
  const auto suffix = std::to_string(static_cast<unsigned int>(key.package)) + "-" +
                      std::to_string(static_cast<unsigned int>(key.hardware_state)) +
                      "-" + std::to_string(static_cast<unsigned int>(key.placement)) +
                      "-" + std::to_string(static_cast<unsigned int>(key.working_set));
  return {"synthetic-platform",
          "synthetic-build",
          "queue-" + suffix,
          "consumer-action-v1",
          "placement-" + suffix,
          "capacity-" + suffix,
          "working-set-" + suffix,
          "hardware-state-" + suffix,
          "software-policy-v1",
          "fake-clock-v1",
          1024U};
}

struct ServiceFixture final {
  calibration::ServiceRatePlan plan;
  std::vector<calibration::ServiceRunEvidence> runs;
};

auto service_fixture() -> ServiceFixture {
  ServiceFixture fixture{{"synthetic-service-plan",
                          std::string(calibration::kServiceRateMethodId),
                          "synthetic-service-namespace",
                          {"synthetic independent identically distributed runs"},
                          {{"synthetic-calibration-owner"},
                           reference("synthetic-authority"),
                           reference("synthetic-budget")},
                          {}},
                         {}};
  std::size_t ordinal = 0U;
  for (const auto& key : calibration::required_service_cells()) {
    calibration::ServiceCellPlan cell{key, context_for(key), 100U, 100U, {}};
    for (std::size_t repetition = 0U;
         repetition < calibration::kMinimumValidIndependentRuns; ++repetition) {
      const auto id =
          "service-" + std::to_string(ordinal) + "-" + std::to_string(repetition);
      cell.planned_run_ids.push_back(run_id(id));
      const auto consumed = ordinal == 0U && repetition == 0U ? 80U : 100U;
      fixture.runs.push_back({run_id(id),
                              key,
                              cell.context,
                              protocol::Stage::calibration,
                              protocol::RunMode::service_rate_calibration,
                              protocol::ArrivalFamily::continuous_ready,
                              calibration::CalibrationRunValidity::valid,
                              consumed,
                              100U,
                              100U,
                              {reference(id + "-raw")},
                              reference(id + "-integrity"),
                              std::nullopt});
    }
    fixture.plan.cells.push_back(std::move(cell));
    ++ordinal;
  }
  return fixture;
}

auto ring_stage_context(const calibration::RingContextKey& key,
                        protocol::RequestedHardwareState state)
    -> calibration::StageAContext {
  const auto suffix = std::to_string(static_cast<unsigned int>(key.placement)) + "-" +
                      std::to_string(static_cast<unsigned int>(key.working_set));
  return {"synthetic-platform",
          "synthetic-build",
          "queue-r0-v1",
          "consumer-action-v1",
          "placement-" + suffix,
          "capacity-" + suffix,
          "working-set-" + suffix,
          "hardware-state-" + std::to_string(static_cast<unsigned int>(state)),
          "software-policy-v1",
          "fake-clock-v1",
          1024U};
}

struct RingFixture final {
  calibration::RingDistancePlan plan;
  std::vector<calibration::RingRunEvidence> runs;
};

auto ring_fixture() -> RingFixture {
  RingFixture fixture{{"synthetic-ring-plan",
                       std::string(calibration::kRingDistanceMethodId),
                       "synthetic-ring-namespace",
                       {"synthetic marginal run-level tolerance extremes"},
                       {{"synthetic-calibration-owner"},
                        reference("synthetic-authority"),
                        reference("synthetic-budget")},
                       {}},
                      {}};
  std::size_t context_ordinal = 0U;
  for (const auto& key : calibration::required_ring_contexts()) {
    calibration::RingContextPlan context{key, {1024U, 64U, 8U}, 100U, 2U, {}};
    for (const auto state :
         {protocol::RequestedHardwareState::h0, protocol::RequestedHardwareState::h1}) {
      calibration::RingStatePlan state_plan{state, ring_stage_context(key, state), {}};
      for (std::size_t repetition = 0U;
           repetition < calibration::kMinimumValidIndependentRuns; ++repetition) {
        const auto id = "ring-" + std::to_string(context_ordinal) + "-" +
                        std::to_string(static_cast<unsigned int>(state)) + "-" +
                        std::to_string(repetition);
        state_plan.planned_run_ids.push_back(run_id(id));
        const bool conservative_case = context_ordinal == 0U && repetition == 0U &&
                                       state == protocol::RequestedHardwareState::h0;
        calibration::RingDemandSeries series{conservative_case
                                                 ? std::vector<std::uint64_t>{50U, 100U}
                                                 : std::vector<std::uint64_t>{10U, 17U},
                                             {10U, 20U},
                                             {4U, 5U},
                                             {4U, 6U},
                                             3U,
                                             4U};
        fixture.runs.push_back({run_id(id),
                                key,
                                state_plan.ring_off_context,
                                state,
                                protocol::Stage::calibration,
                                protocol::RunMode::d2_calibration,
                                protocol::QueuePackage::r0,
                                calibration::CalibrationRunValidity::valid,
                                100U,
                                std::move(series),
                                {reference(id + "-raw")},
                                reference(id + "-integrity"),
                                std::nullopt});
      }
      context.states.push_back(std::move(state_plan));
    }
    fixture.plan.contexts.push_back(std::move(context));
    ++context_ordinal;
  }
  return fixture;
}

class SequenceClock final {
public:
  explicit SequenceClock(std::vector<std::uint64_t> values)
      : values_(std::move(values)) {}

  [[nodiscard]] auto read() noexcept -> timing::ClockReadResult {
    if (position_ >= values_.size()) {
      return {timing::ClockReadStatus::call_failed, {0U, 0U}};
    }
    const auto value = values_[position_++];
    return {timing::ClockReadStatus::ok, {value / 1000U, value}};
  }

private:
  std::vector<std::uint64_t> values_;
  std::size_t position_{0U};
};

TEST(CalibrationExactArithmetic, ReducesComparesAndFailsOnOverflow) {
  const auto reduced = calibration::exact_throughput({3U, 100U, 20U});
  ASSERT_TRUE(reduced);
  EXPECT_EQ(reduced.value(), (calibration::ExactRational{15U, 1U}));
  ASSERT_TRUE(calibration::compare({1U, 3U}, {2U, 5U}));
  ASSERT_TRUE(calibration::compare({5U, 7U}, {2U, 3U}));
  ASSERT_TRUE(calibration::compare({6U, 8U}, {3U, 4U}));
  EXPECT_LT(calibration::compare({1U, 3U}, {2U, 5U}).value(), 0);
  EXPECT_GT(calibration::compare({5U, 7U}, {2U, 3U}).value(), 0);
  EXPECT_EQ(calibration::compare({6U, 8U}, {3U, 4U}).value(), 0);
  EXPECT_FALSE(calibration::compare({1U, 0U}, {1U, 1U}));
  const auto product = calibration::multiply({6U, 35U}, {14U, 9U});
  ASSERT_TRUE(product);
  EXPECT_EQ(product.value(), (calibration::ExactRational{4U, 15U}));
  EXPECT_FALSE(
      calibration::exact_throughput({std::numeric_limits<std::uint64_t>::max(),
                                     std::numeric_limits<std::uint64_t>::max(), 1U}));
  for (std::uint64_t left_numerator = 0U; left_numerator < 17U; ++left_numerator) {
    for (std::uint64_t left_denominator = 1U; left_denominator < 17U;
         ++left_denominator) {
      for (std::uint64_t right_numerator = 0U; right_numerator < 17U;
           ++right_numerator) {
        for (std::uint64_t right_denominator = 1U; right_denominator < 17U;
             ++right_denominator) {
          const auto exact_cross_product =
              left_numerator * right_denominator < right_numerator * left_denominator
                  ? -1
                  : (left_numerator * right_denominator >
                             right_numerator * left_denominator
                         ? 1
                         : 0);
          const auto comparison = calibration::compare(
              {left_numerator, left_denominator}, {right_numerator, right_denominator});
          ASSERT_TRUE(comparison);
          EXPECT_EQ(comparison.value(), exact_cross_product);
        }
      }
    }
  }
}

TEST(CalibrationServiceRate, ResolvesExactSixtyCellMinimumAndCandidateLoads) {
  const auto fixture = service_fixture();
  const auto evaluated = calibration::evaluate_service_rate(fixture.plan, fixture.runs);
  ASSERT_TRUE(evaluated);
  EXPECT_EQ(evaluated.value().state, calibration::EvaluationState::resolved);
  ASSERT_TRUE(evaluated.value().mu_ref.has_value());
  EXPECT_EQ(require_optional(evaluated.value().mu_ref),
            (calibration::ExactRational{80U, 1U}));
  EXPECT_EQ(evaluated.value().candidate_loads,
            (std::vector<calibration::ExactRational>{{20U, 1U}, {40U, 1U}, {60U, 1U}}));
  EXPECT_EQ(evaluated.value().cells.size(), calibration::kRequiredServiceCellCount);
  EXPECT_EQ(evaluated.value().cells.front().run_decisions.size(),
            calibration::kMinimumValidIndependentRuns);
  EXPECT_EQ(require_optional(
                evaluated.value().cells.front().run_decisions.front().throughput),
            (calibration::ExactRational{80U, 1U}));
}

TEST(CalibrationServiceRate, InvalidRunIsRetainedButCannotBeToppedUp) {
  auto fixture = service_fixture();
  fixture.runs.front().validity = calibration::CalibrationRunValidity::invalid;
  fixture.runs.front().failure_artifact = reference("synthetic-failure");
  auto evaluated = calibration::evaluate_service_rate(fixture.plan, fixture.runs);
  ASSERT_TRUE(evaluated);
  EXPECT_EQ(evaluated.value().state, calibration::EvaluationState::not_evaluated);
  EXPECT_FALSE(evaluated.value().mu_ref.has_value());
  EXPECT_EQ(evaluated.value().cells.front().run_decisions.front().validity,
            calibration::CalibrationRunValidity::invalid);
  EXPECT_FALSE(
      evaluated.value().cells.front().run_decisions.front().throughput.has_value());

  fixture.runs.push_back(fixture.runs.back());
  fixture.runs.back().run_id = run_id("unplanned-top-up");
  EXPECT_FALSE(calibration::evaluate_service_rate(fixture.plan, fixture.runs));
}

TEST(CalibrationServiceRate, RejectsConfirmatoryOrContextMismatchedEvidence) {
  auto fixture = service_fixture();
  fixture.runs.front().stage = protocol::Stage::stage_a;
  EXPECT_FALSE(calibration::evaluate_service_rate(fixture.plan, fixture.runs));
  fixture = service_fixture();
  fixture.runs.front().context.consumer_action_id = "different-action";
  EXPECT_FALSE(calibration::evaluate_service_rate(fixture.plan, fixture.runs));
  fixture = service_fixture();
  fixture.plan.governance.authority_artifact.sha256 = "not-a-hash";
  EXPECT_FALSE(calibration::evaluate_service_rate(fixture.plan, fixture.runs));
  fixture = service_fixture();
  fixture.plan.governance.owner_ids.push_back("synthetic-calibration-owner");
  EXPECT_FALSE(calibration::evaluate_service_rate(fixture.plan, fixture.runs));
}

TEST(CalibrationRingTrace, BracketsAcquireAndIssuesOnlyForAdvancingOperations) {
  queue::RingSpscQueue ring({1U}, {64U});
  int event = 7;
  const auto pointer = queue::EventPointer::from(&event);
  ASSERT_TRUE(pointer.has_value());
  calibration::RingDemandTrace trace{3U};
  SequenceClock clock({10U, 13U, 20U, 24U, 30U, 35U, 40U, 46U, 50U, 51U, 60U, 62U});
  EXPECT_EQ(calibration::capture_producer_ring_demand(clock, ring,
                                                      require_optional(pointer), trace)
                .outcome,
            calibration::RingAttemptOutcome::advanced);
  EXPECT_EQ(calibration::capture_producer_ring_demand(clock, ring,
                                                      require_optional(pointer), trace)
                .outcome,
            calibration::RingAttemptOutcome::full);
  EXPECT_EQ(calibration::capture_consumer_ring_demand(clock, ring, trace).outcome,
            calibration::RingAttemptOutcome::advanced);
  EXPECT_EQ(calibration::capture_consumer_ring_demand(clock, ring, trace).outcome,
            calibration::RingAttemptOutcome::empty);
  EXPECT_EQ(calibration::capture_producer_ring_demand(clock, ring,
                                                      require_optional(pointer), trace)
                .outcome,
            calibration::RingAttemptOutcome::advanced);
  EXPECT_EQ(calibration::capture_consumer_ring_demand(clock, ring, trace).outcome,
            calibration::RingAttemptOutcome::advanced);
  EXPECT_EQ(trace.series().producer_demand_ticks,
            (std::vector<std::uint64_t>{3U, 4U, 1U}));
  EXPECT_EQ(trace.series().consumer_demand_ticks,
            (std::vector<std::uint64_t>{5U, 6U, 2U}));
  EXPECT_EQ(trace.series().producer_issue_ticks, (std::vector<std::uint64_t>{40U}));
  EXPECT_EQ(trace.series().consumer_issue_ticks, (std::vector<std::uint64_t>{30U}));
  EXPECT_EQ(trace.series().producer_full_count, 1U);
  EXPECT_EQ(trace.series().consumer_empty_count, 1U);
}

TEST(CalibrationRingTrace, ExplicitCapacityFailsWithoutDynamicGrowth) {
  calibration::RingDemandTrace trace{1U};
  EXPECT_TRUE(trace.record(calibration::RingWorker::producer, 10U, 11U,
                           calibration::RingAttemptOutcome::advanced));
  const auto capacity_before_rejection =
      trace.series().producer_demand_ticks.capacity();
  EXPECT_FALSE(trace.record(calibration::RingWorker::producer, 20U, 21U,
                            calibration::RingAttemptOutcome::advanced));
  EXPECT_EQ(trace.series().producer_demand_ticks.capacity(), capacity_before_rejection);
  EXPECT_EQ(trace.series().producer_demand_ticks.size(), 1U);

  queue::RingSpscQueue ring({1U}, {64U});
  int event = 7;
  const auto pointer = queue::EventPointer::from(&event);
  ASSERT_TRUE(pointer.has_value());
  SequenceClock clock({10U, 11U});
  EXPECT_EQ(calibration::capture_producer_ring_demand(clock, ring,
                                                      require_optional(pointer), trace)
                .outcome,
            calibration::RingAttemptOutcome::trace_failure);
  EXPECT_EQ(trace.series().producer_demand_ticks.size(), 1U);
}

TEST(CalibrationRingDistance, UsesConservativeMaxMinAndCommonDistance) {
  const auto fixture = ring_fixture();
  const auto evaluated =
      calibration::evaluate_ring_distance(fixture.plan, fixture.runs);
  ASSERT_TRUE(evaluated);
  EXPECT_EQ(evaluated.value().state, calibration::EvaluationState::resolved);
  ASSERT_EQ(evaluated.value().contexts.size(), calibration::kRequiredRingContextCount);
  EXPECT_EQ(evaluated.value().contexts.front().producer_demand_upper_ticks, 100U);
  EXPECT_EQ(evaluated.value().contexts.front().consumer_demand_upper_ticks, 20U);
  EXPECT_EQ(evaluated.value().contexts.front().producer_issue_lower_ticks, 4U);
  EXPECT_EQ(evaluated.value().contexts.front().consumer_issue_lower_ticks, 4U);
  EXPECT_EQ(evaluated.value().contexts.front().conservative_demand_ticks, 100U);
  EXPECT_EQ(evaluated.value().contexts.front().conservative_issue_ticks, 4U);
  EXPECT_EQ(evaluated.value().contexts.front().d1_slots, 8U);
  EXPECT_EQ(evaluated.value().contexts.front().d2_cache_lines, 4U);
  EXPECT_EQ(evaluated.value().contexts.front().producer_distance_slots, 32U);
  EXPECT_EQ(evaluated.value().contexts.front().consumer_distance_slots, 32U);
  EXPECT_EQ(evaluated.value().contexts.front().run_decisions.size(),
            2U * calibration::kMinimumValidIndependentRuns);
  EXPECT_EQ(evaluated.value().contexts.back().d2_cache_lines, 2U);
}

TEST(CalibrationRingDistance, AppliesQuarterCapAndDetectsCollapse) {
  auto fixture = ring_fixture();
  const auto set_capacity = [&](std::uint64_t capacity) {
    fixture.plan.contexts.front().geometry.capacity =
        static_cast<std::size_t>(capacity);
    for (auto& state : fixture.plan.contexts.front().states) {
      state.ring_off_context.logical_capacity = capacity;
    }
    for (auto& run : fixture.runs) {
      if (run.key == fixture.plan.contexts.front().key) {
        run.ring_off_context.logical_capacity = capacity;
      }
    }
  };
  set_capacity(128U);
  auto evaluated = calibration::evaluate_ring_distance(fixture.plan, fixture.runs);
  ASSERT_TRUE(evaluated);
  EXPECT_EQ(evaluated.value().contexts.front().d2_cache_lines, 4U);

  set_capacity(32U);
  evaluated = calibration::evaluate_ring_distance(fixture.plan, fixture.runs);
  ASSERT_TRUE(evaluated);
  EXPECT_EQ(evaluated.value().state, calibration::EvaluationState::ineligible);
  EXPECT_EQ(evaluated.value().contexts.front().state,
            calibration::EvaluationState::ineligible);
}

TEST(CalibrationRingDistance, InvalidCellAndForbiddenOutcomeFailClosed) {
  auto fixture = ring_fixture();
  fixture.runs.front().validity = calibration::CalibrationRunValidity::invalid;
  fixture.runs.front().failure_artifact = reference("ring-failure");
  auto evaluated = calibration::evaluate_ring_distance(fixture.plan, fixture.runs);
  ASSERT_TRUE(evaluated);
  EXPECT_EQ(evaluated.value().state, calibration::EvaluationState::not_evaluated);
  EXPECT_EQ(evaluated.value().contexts.front().run_decisions.front().validity,
            calibration::CalibrationRunValidity::invalid);

  fixture = ring_fixture();
  fixture.runs.front().stage = protocol::Stage::stage_a;
  EXPECT_FALSE(calibration::evaluate_ring_distance(fixture.plan, fixture.runs));

  fixture = ring_fixture();
  fixture.runs.front().series.producer_issue_ticks.clear();
  EXPECT_FALSE(calibration::evaluate_ring_distance(fixture.plan, fixture.runs));

  fixture = ring_fixture();
  fixture.plan.contexts.front().states.back().ring_off_context.software_policy_id =
      "different-software-policy";
  EXPECT_FALSE(calibration::evaluate_ring_distance(fixture.plan, fixture.runs));
}

TEST(CalibrationRingDistance, InverseEcdfUsesExactCeilingRank) {
  std::vector<std::uint64_t> values;
  for (std::uint64_t value = 1U; value <= 1000U; ++value) {
    values.push_back(value);
  }
  const auto upper = calibration::inverse_ecdf(values, 999U, 1000U);
  const auto lower = calibration::inverse_ecdf(values, 1U, 1000U);
  ASSERT_TRUE(upper);
  ASSERT_TRUE(lower);
  EXPECT_EQ(upper.value(), 999U);
  EXPECT_EQ(lower.value(), 1U);
  EXPECT_FALSE(calibration::inverse_ecdf({}, 999U, 1000U));
}

} // namespace
