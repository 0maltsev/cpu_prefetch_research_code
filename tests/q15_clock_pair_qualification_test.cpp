#include <gtest/gtest.h>

#include "cpu_prefetch/qualification/q15_clock_pair_qualification.hpp"

#include <optional>
#include <stdexcept>

namespace {

using cpu_prefetch::qualification::ClockPairQualificationCounts;
using cpu_prefetch::qualification::run_clock_pair_qualification;
using cpu_prefetch::runner::WorkerPair;

template <typename Value>
[[nodiscard]] auto require_optional(const std::optional<Value>& value) -> const Value& {
  if (!value.has_value()) {
    throw std::logic_error("required clock qualification observation is absent");
  }
  return value.value();
}

// These local integration tests require CPUs 0, 1 and 8 in the allowed affinity
// set. CPU availability alone supplies no stand or scientific qualification.
// kQualificationPrimeReadCount/kQualificationDeltaCount/
// kCrossCoreExchangeCountPerWindow/kMinimumCrossCoreWindowStartSpanNanoseconds
// are frozen constants baked directly into evaluate_clock_sequence/
// evaluate_cross_core_direction's own sample-count and window-span checks
// (not parameterized by ClockPairQualificationCounts), so a reduced scale
// here can never make `.passes`, `.prime_count_passes`,
// `.accepted_policy_sample_count`, or `.window_span_passes` true -- this
// test verifies the real, concurrent, real-clock mechanism is correct (zero
// call/timespec failures, zero causal regressions, affinity held throughout,
// and a genuinely bracketed, nonempty clock-offset interval per window),
// not that reduced-scale evidence would satisfy the accepted production
// thresholds. Only a run at kAcceptedClockPairQualificationCounts on the
// accepted stand can do that.
constexpr ClockPairQualificationCounts kReducedCounts{
    /*prime_read_count=*/1'000U,
    /*delta_count=*/5'000U,
    /*window_count=*/3U,
    /*exchanges_per_window=*/200U,
    /*minimum_window_start_span_nanoseconds=*/200'000'000U,
};

TEST(Q15ClockPairQualification,
     RealTwoThreadRunOnNearPairCompletesWithNoFailuresOrRegressions) {
  const auto result = run_clock_pair_qualification(WorkerPair{0U, 1U}, kReducedCounts);

  ASSERT_TRUE(result.producer_pinned);
  ASSERT_TRUE(result.consumer_pinned);
  ASSERT_TRUE(result.complete);

  const auto& producer = require_optional(result.producer_per_core);
  EXPECT_EQ(producer.sequence.regression_count, 0U);
  EXPECT_TRUE(producer.read_status_passes);
  EXPECT_TRUE(producer.affinity_passes);

  const auto& consumer = require_optional(result.consumer_per_core);
  EXPECT_EQ(consumer.sequence.regression_count, 0U);
  EXPECT_TRUE(consumer.read_status_passes);
  EXPECT_TRUE(consumer.affinity_passes);

  const auto& cross_core = require_optional(result.cross_core);
  EXPECT_EQ(cross_core.producer_to_consumer.causal_regressions, 0U);
  EXPECT_EQ(cross_core.consumer_to_producer.causal_regressions, 0U);
  EXPECT_TRUE(cross_core.producer_to_consumer.interval_limits_pass);
  EXPECT_TRUE(cross_core.consumer_to_producer.interval_limits_pass);

  // Frozen thresholds (10,000,000 deltas; 100,000 exchanges per window; a
  // 60-real-second window span) are not met at this reduced scale, so these
  // aggregate accept booleans are expected false here -- see the comment
  // above.
  EXPECT_FALSE(producer.prime_count_passes);
  EXPECT_FALSE(cross_core.producer_to_consumer.accepted_policy_sample_count);
  EXPECT_FALSE(cross_core.producer_to_consumer.window_span_passes);
  EXPECT_FALSE(result.passes);
}

TEST(Q15ClockPairQualification, PinningFailsClosedForACpuOutsideTheAffinityRange) {
  const auto result =
      run_clock_pair_qualification(WorkerPair{0U, 4'000'000U}, kReducedCounts);
  EXPECT_TRUE(result.producer_pinned);
  EXPECT_FALSE(result.consumer_pinned);
  EXPECT_FALSE(result.complete);
  EXPECT_FALSE(result.passes);
}

TEST(Q15ClockPairQualification, RegisteredV5PairCompletesBothCapturePhases) {
  const auto result = run_clock_pair_qualification(WorkerPair{0U, 8U}, kReducedCounts);
  ASSERT_TRUE(result.producer_pinned);
  ASSERT_TRUE(result.consumer_pinned);
  ASSERT_TRUE(result.complete);
  EXPECT_TRUE(require_optional(result.producer_per_core).affinity_passes);
  EXPECT_TRUE(require_optional(result.consumer_per_core).affinity_passes);
  EXPECT_TRUE(require_optional(result.producer_per_core).read_status_passes);
  EXPECT_TRUE(require_optional(result.consumer_per_core).read_status_passes);
  EXPECT_EQ(require_optional(result.producer_per_core).sequence.regression_count, 0U);
  EXPECT_EQ(require_optional(result.consumer_per_core).sequence.regression_count, 0U);
  EXPECT_EQ(require_optional(result.producer_per_core).sequence.delta_count, 5'000U);
  EXPECT_EQ(require_optional(result.consumer_per_core).sequence.delta_count, 5'000U);
  const auto& cross = require_optional(result.cross_core);
  EXPECT_EQ(cross.producer_to_consumer.causal_regressions, 0U);
  EXPECT_EQ(cross.consumer_to_producer.causal_regressions, 0U);
  EXPECT_EQ(cross.producer_to_consumer.exchange_count_per_window, 200U);
  EXPECT_EQ(cross.consumer_to_producer.exchange_count_per_window, 200U);
  EXPECT_FALSE(result.passes);
}

} // namespace
