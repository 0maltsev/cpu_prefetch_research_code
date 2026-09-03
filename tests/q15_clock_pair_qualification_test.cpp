#include <gtest/gtest.h>

#include "cpu_prefetch/qualification/q15_clock_pair_qualification.hpp"

namespace {

using cpu_prefetch::qualification::ClockPairQualificationCounts;
using cpu_prefetch::qualification::run_clock_pair_qualification;
using cpu_prefetch::runner::WorkerPair;

// CPUs 0 and 1 are both valid on any machine this test runs on (unlike the
// real FAR pair's CPU 26, which only exists on the accepted Xeon stand).
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

  ASSERT_TRUE(result.producer_per_core.has_value());
  EXPECT_EQ(result.producer_per_core->sequence.regression_count, 0U);
  EXPECT_TRUE(result.producer_per_core->read_status_passes);
  EXPECT_TRUE(result.producer_per_core->affinity_passes);

  ASSERT_TRUE(result.consumer_per_core.has_value());
  EXPECT_EQ(result.consumer_per_core->sequence.regression_count, 0U);
  EXPECT_TRUE(result.consumer_per_core->read_status_passes);
  EXPECT_TRUE(result.consumer_per_core->affinity_passes);

  ASSERT_TRUE(result.cross_core.has_value());
  EXPECT_EQ(result.cross_core->producer_to_consumer.causal_regressions, 0U);
  EXPECT_EQ(result.cross_core->consumer_to_producer.causal_regressions, 0U);
  EXPECT_TRUE(result.cross_core->producer_to_consumer.interval_limits_pass);
  EXPECT_TRUE(result.cross_core->consumer_to_producer.interval_limits_pass);

  // Frozen thresholds (10,000,000 deltas; 100,000 exchanges per window; a
  // 60-real-second window span) are not met at this reduced scale, so these
  // aggregate accept booleans are expected false here -- see the comment
  // above.
  EXPECT_FALSE(result.producer_per_core->prime_count_passes);
  EXPECT_FALSE(result.cross_core->producer_to_consumer.accepted_policy_sample_count);
  EXPECT_FALSE(result.cross_core->producer_to_consumer.window_span_passes);
  EXPECT_FALSE(result.passes);
}

TEST(Q15ClockPairQualification, PinningFailsClosedForACpuOutsideTheFixedQ15Domain) {
  const auto result =
      run_clock_pair_qualification(WorkerPair{0U, 4'000'000U}, kReducedCounts);
  EXPECT_TRUE(result.producer_pinned);
  EXPECT_FALSE(result.consumer_pinned);
  EXPECT_FALSE(result.complete);
  EXPECT_FALSE(result.passes);
}

} // namespace
