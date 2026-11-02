#include "discovery_backend_test_support.hpp"

#include <gtest/gtest.h>

#include <array>
#include <limits>
#include <memory>
#include <span>

namespace {
namespace calibration = cpu_prefetch::calibration;
namespace storage = cpu_prefetch::storage;
namespace support = cpu_prefetch::test_support;

void overwrite_word(std::span<std::byte> bytes, std::size_t offset,
                    std::uint64_t value) {
  for (std::size_t byte = 0U; byte < sizeof(value); ++byte) {
    bytes[offset + byte] = static_cast<std::byte>((value >> (8U * byte)) & 0xffU);
  }
}

TEST(DiscoveryRingBackend, PersistentRealArenaStreamsDrainAndExactSequenceJoin) {
  auto preparation =
      std::make_unique<support::SoftwareOnlyDiscoveryPreparation<20'000U>>();
  support::DiscoveryTestClock clock;
  support::DiscoveryTestRelax relax;
  calibration::DiscoveryRingPhaseBackend backend(support::kDiscoveryTestPlan, clock,
                                                 *preparation);
  const auto result = calibration::run_discovery_session(support::kDiscoveryTestPlan,
                                                         clock, backend, relax);
  ASSERT_EQ(result.stop, calibration::DiscoverySessionStop::complete);
  EXPECT_TRUE(result.warmup_verified);
  EXPECT_TRUE(result.measurement_verified);
  EXPECT_TRUE(result.warmup_drain.reset_verified);
  EXPECT_TRUE(result.private_reset_verified[0U]);
  EXPECT_TRUE(result.private_reset_verified[1U]);
  const auto first = storage::read_prepared_producer_row(
      preparation->warmup.producer_stream.snapshot(), preparation->warmup.layout, 0U);
  if (!first.has_value()) {
    FAIL() << "warmup produced no retained primary row";
    return;
  }
  EXPECT_GT(first->scheduled_arrival, 0U);
  EXPECT_LE(first->scheduled_arrival,
            first->producer_handle_begin.relative_picoseconds);
  for (const auto warmup : {true, false}) {
    auto& producer = preparation->producer_phase(warmup);
    auto& consumer = preparation->consumer_phase(warmup);
    EXPECT_EQ(producer.attempted, producer.accepted + producer.full);
    EXPECT_EQ(producer.accepted, consumer.consumed);
    EXPECT_EQ(producer.primary.snapshot().row_count, producer.attempted);
    EXPECT_EQ(consumer.primary.snapshot().row_count, consumer.consumed);
    EXPECT_EQ(producer.primary.snapshot().completeness,
              storage::StreamCompleteness::sealed_complete);
    EXPECT_EQ(consumer.primary.snapshot().completeness,
              storage::StreamCompleteness::sealed_complete);
    EXPECT_EQ(consumer.last_join.status, calibration::DiscoveryJoinStatus::exact);
    EXPECT_EQ(consumer.last_join.matched, consumer.consumed);
    EXPECT_GE(consumer.drain_requests, 1U);
  }
  EXPECT_EQ(preparation->ring().audit_quiescent().occupied_slots, 0U);
}

TEST(DiscoveryRingBackend, PreparationAndPrivateResetRejectionDoNotReleaseMeasurement) {
  for (const auto reject_preparation : {true, false}) {
    auto preparation =
        std::make_unique<support::SoftwareOnlyDiscoveryPreparation<20'000U>>();
    preparation->reject_producer = reject_preparation;
    preparation->reject_consumer_reset = !reject_preparation;
    support::DiscoveryTestClock clock;
    support::DiscoveryTestRelax relax;
    calibration::DiscoveryRingPhaseBackend backend(support::kDiscoveryTestPlan, clock,
                                                   *preparation);
    const auto result = calibration::run_discovery_session(support::kDiscoveryTestPlan,
                                                           clock, backend, relax);
    EXPECT_NE(result.stop, calibration::DiscoverySessionStop::complete);
    EXPECT_FALSE(result.origins[1U].has_value());
    EXPECT_EQ(preparation->measurement.producer.attempted, 0U);
    EXPECT_EQ(preparation->measurement.consumer.consumed, 0U);
  }
}

TEST(DiscoveryRingBackend, FullAttemptsAndRepeatedIndicesJoinOnlyByActualOrdinals) {
  auto preparation = std::make_unique<support::SoftwareOnlyDiscoveryPreparation<64U>>();
  support::DiscoveryTestClock clock;
  auto plan = support::kDiscoveryTestPlan;
  plan.warmup_attempt_capacity = 64U;
  plan.measurement_attempt_capacity = 64U;
  calibration::DiscoveryRingPhaseBackend backend(plan, clock, *preparation);
  ASSERT_TRUE(backend.prepare_producer());
  ASSERT_TRUE(backend.prepare_consumer());
  for (std::uint64_t logical = 0U; logical < 16U; ++logical) {
    const auto result = backend.warmup_producer_attempt(0U);
    EXPECT_EQ(result.outcome, logical < 8U ? calibration::RingAttemptOutcome::advanced
                                           : calibration::RingAttemptOutcome::full);
  }
  for (unsigned index = 0U; index < 8U; ++index) {
    EXPECT_EQ(backend.warmup_consumer_attempt().outcome,
              calibration::RingAttemptOutcome::advanced);
  }
  for (unsigned index = 0U; index < 8U; ++index) {
    EXPECT_EQ(backend.warmup_producer_attempt(0U).outcome,
              calibration::RingAttemptOutcome::advanced);
    EXPECT_EQ(backend.warmup_consumer_attempt().outcome,
              calibration::RingAttemptOutcome::advanced);
  }
  const auto& p = preparation->warmup.producer;
  const auto& c = preparation->warmup.consumer;
  const auto joined = calibration::reconcile_discovery_primary(
      preparation->arena(), p.primary.snapshot(), p.layout, c.primary.snapshot(),
      c.layout, {24U, 16U, 8U, 16U}, {.initial = c.initial_state, .observed = c.state},
      true);
  EXPECT_EQ(joined.status, calibration::DiscoveryJoinStatus::exact);
  EXPECT_EQ(joined.matched, 16U);
  EXPECT_EQ(preparation->ring().audit_quiescent().occupied_slots, 0U);
}

TEST(DiscoveryRingBackend, ObservedDrainRetainsPrimaryBoundariesBeforeReset) {
  auto preparation = std::make_unique<support::SoftwareOnlyDiscoveryPreparation<64U>>();
  support::DiscoveryTestClock clock;
  auto plan = support::kDiscoveryTestPlan;
  plan.warmup_attempt_capacity = 64U;
  plan.measurement_attempt_capacity = 64U;
  calibration::DiscoveryRingPhaseBackend backend(plan, clock, *preparation);
  ASSERT_TRUE(backend.prepare_producer());
  ASSERT_TRUE(backend.prepare_consumer());
  ASSERT_EQ(backend.warmup_producer_attempt(0U).outcome,
            calibration::RingAttemptOutcome::advanced);
  preparation->warmup.consumer.capture_horizon_complete = true;
  const auto origin = clock.read();
  const auto drained = backend.drain_warmup(
      {origin.sample.relative_picoseconds, 1'000'000U, 9U, 1U, true});
  EXPECT_EQ(drained.stop, calibration::DiscoveryDrainStop::complete);
  EXPECT_EQ(drained.dequeued, 1U);
  EXPECT_TRUE(drained.reset_verified);
  const auto& phase = preparation->warmup;
  ASSERT_EQ(phase.consumer.drain_requests, 2U);
  EXPECT_TRUE(phase.drain_rows[0U].primary.has_value());
  EXPECT_TRUE(phase.drain_rows[0U].dequeue_observation.has_value());
  EXPECT_TRUE(phase.drain_rows[0U].action_completion.has_value());
  EXPECT_FALSE(phase.drain_rows[1U].primary.has_value());
  EXPECT_EQ(phase.consumer_stream.snapshot().row_count, 1U);
  EXPECT_EQ(phase.consumer.last_join.status, calibration::DiscoveryJoinStatus::exact);
}

TEST(DiscoveryRingBackend, FailedFinalChecksumLeavesQueueCursorsWithoutReset) {
  auto preparation = std::make_unique<support::SoftwareOnlyDiscoveryPreparation<64U>>();
  support::DiscoveryTestClock clock;
  auto plan = support::kDiscoveryTestPlan;
  plan.warmup_attempt_capacity = 64U;
  plan.measurement_attempt_capacity = 64U;
  calibration::DiscoveryRingPhaseBackend backend(plan, clock, *preparation);
  ASSERT_TRUE(backend.prepare_producer());
  ASSERT_TRUE(backend.prepare_consumer());
  ASSERT_EQ(backend.warmup_producer_attempt(0U).outcome,
            calibration::RingAttemptOutcome::advanced);
  ASSERT_EQ(backend.warmup_consumer_attempt().outcome,
            calibration::RingAttemptOutcome::advanced);
  preparation->warmup.consumer.state.value ^= 1U;
  const auto origin = clock.read();
  const auto drained = backend.drain_warmup(
      {origin.sample.relative_picoseconds, 1'000'000U, 9U, 0U, true});
  EXPECT_EQ(drained.stop, calibration::DiscoveryDrainStop::consumer_failure);
  EXPECT_FALSE(drained.reset_verified);
  EXPECT_EQ(preparation->warmup.consumer.last_join.status,
            calibration::DiscoveryJoinStatus::checksum_mismatch);
  const auto audit = preparation->ring().audit_quiescent();
  EXPECT_EQ(audit.occupied_slots, 0U);
  EXPECT_EQ(audit.producer_position, 1U);
  EXPECT_EQ(audit.consumer_position, 1U);
  EXPECT_EQ(preparation->warmup.producer_stream.snapshot().completeness,
            storage::StreamCompleteness::sealed_incomplete);
}

TEST(DiscoveryRingBackend, PrefixJoinAllowsOnlyThePendingAcceptedSuffix) {
  auto preparation = std::make_unique<support::SoftwareOnlyDiscoveryPreparation<64U>>();
  support::DiscoveryTestClock clock;
  auto plan = support::kDiscoveryTestPlan;
  plan.warmup_attempt_capacity = 64U;
  plan.measurement_attempt_capacity = 64U;
  calibration::DiscoveryRingPhaseBackend backend(plan, clock, *preparation);
  ASSERT_TRUE(backend.prepare_producer());
  ASSERT_TRUE(backend.prepare_consumer());
  ASSERT_EQ(backend.warmup_producer_attempt(0U).outcome,
            calibration::RingAttemptOutcome::advanced);
  ASSERT_EQ(backend.warmup_producer_attempt(0U).outcome,
            calibration::RingAttemptOutcome::advanced);
  ASSERT_EQ(backend.warmup_consumer_attempt().outcome,
            calibration::RingAttemptOutcome::advanced);
  const auto& phase = preparation->warmup;
  const auto verify = [&](bool drained) {
    return calibration::reconcile_discovery_primary(
        preparation->arena(), phase.producer_stream.snapshot(), phase.layout,
        phase.consumer_stream.snapshot(), phase.layout, {2U, 2U, 0U, 1U},
        {.initial = phase.consumer.initial_state, .observed = phase.consumer.state},
        drained);
  };
  EXPECT_EQ(verify(false).status, calibration::DiscoveryJoinStatus::exact);
  EXPECT_EQ(verify(false).matched, 1U);
  EXPECT_EQ(verify(true).status, calibration::DiscoveryJoinStatus::count_mismatch);
}

TEST(DiscoveryRingBackend, PrimaryMutantsRejectWithoutRenumberingOrHashOnlyMatching) {
  constexpr std::array expected{calibration::DiscoveryJoinStatus::record_mismatch,
                                calibration::DiscoveryJoinStatus::malformed_consumer,
                                calibration::DiscoveryJoinStatus::ordinal_mismatch,
                                calibration::DiscoveryJoinStatus::timestamp_order,
                                calibration::DiscoveryJoinStatus::malformed_producer,
                                calibration::DiscoveryJoinStatus::malformed_producer};
  for (std::size_t mutant = 0U; mutant < expected.size(); ++mutant) {
    SCOPED_TRACE(mutant);
    auto preparation =
        std::make_unique<support::SoftwareOnlyDiscoveryPreparation<64U>>();
    support::DiscoveryTestClock clock;
    auto plan = support::kDiscoveryTestPlan;
    plan.warmup_attempt_capacity = 64U;
    plan.measurement_attempt_capacity = 64U;
    calibration::DiscoveryRingPhaseBackend backend(plan, clock, *preparation);
    ASSERT_TRUE(backend.prepare_producer());
    ASSERT_TRUE(backend.prepare_consumer());
    ASSERT_EQ(backend.warmup_producer_attempt(0U).outcome,
              calibration::RingAttemptOutcome::advanced);
    ASSERT_EQ(backend.warmup_consumer_attempt().outcome,
              calibration::RingAttemptOutcome::advanced);
    auto& phase = preparation->warmup;
    const auto prefix = static_cast<std::size_t>(phase.layout.prefix_bytes);
    switch (mutant) {
    case 0U:
      overwrite_word(phase.consumer_bytes, prefix + 8U,
                     preparation->arena().capacity());
      break;
    case 1U:
      overwrite_word(phase.consumer_bytes, prefix, 1U);
      break;
    case 2U:
      overwrite_word(phase.producer_bytes, prefix + 13U * sizeof(std::uint64_t), 1U);
      break;
    case 3U:
      overwrite_word(phase.consumer_bytes, prefix + 5U * sizeof(std::uint64_t), 0U);
      break;
    case 4U:
      phase.producer_bytes[4U] = std::byte{'X'};
      break;
    case 5U:
      overwrite_word(phase.producer_bytes, prefix + 14U * sizeof(std::uint64_t), 0U);
      break;
    default:
      FAIL() << "unknown mutant";
      return;
    }
    const auto joined = calibration::reconcile_discovery_primary(
        preparation->arena(), phase.producer_stream.snapshot(), phase.layout,
        phase.consumer_stream.snapshot(), phase.layout, {1U, 1U, 0U, 1U},
        {.initial = phase.consumer.initial_state, .observed = phase.consumer.state},
        true);
    EXPECT_EQ(joined.status, expected[mutant]);
  }
}

TEST(DiscoveryRingBackend, EmptyShapeIdentityAndOverflowChecksRemainMandatory) {
  auto preparation = std::make_unique<support::SoftwareOnlyDiscoveryPreparation<64U>>();
  support::DiscoveryTestClock clock;
  auto plan = support::kDiscoveryTestPlan;
  plan.warmup_attempt_capacity = 64U;
  plan.measurement_attempt_capacity = 64U;
  calibration::DiscoveryRingPhaseBackend backend(plan, clock, *preparation);
  ASSERT_TRUE(backend.prepare_producer());
  ASSERT_TRUE(backend.prepare_consumer());
  auto p = preparation->warmup.producer_stream.snapshot();
  auto c = preparation->warmup.consumer_stream.snapshot();
  const auto verify = [&](calibration::DiscoveryJoinCounts counts) {
    return calibration::reconcile_discovery_primary(
        preparation->arena(), p, preparation->warmup.layout, c,
        preparation->warmup.layout, counts, {.initial = {17U}, .observed = {17U}},
        true);
  };
  EXPECT_EQ(verify({0U, 0U, 0U, 0U}).status, calibration::DiscoveryJoinStatus::exact);
  p.stream_kind = cpu_prefetch::protocol::StreamKind::consumer;
  EXPECT_EQ(verify({0U, 0U, 0U, 0U}).status,
            calibration::DiscoveryJoinStatus::malformed_producer);
  p = preparation->warmup.producer_stream.snapshot();
  c.run_id = "a-different-phase";
  EXPECT_EQ(verify({0U, 0U, 0U, 0U}).status,
            calibration::DiscoveryJoinStatus::identity_mismatch);
  c = preparation->warmup.consumer_stream.snapshot();
  EXPECT_EQ(verify({0U, std::numeric_limits<std::uint64_t>::max(), 1U, 0U}).status,
            calibration::DiscoveryJoinStatus::count_mismatch);
}

TEST(DiscoveryRingBackend, DrainClockFailureRetainsActualItemActionAndPartialRow) {
  auto preparation = std::make_unique<support::SoftwareOnlyDiscoveryPreparation<64U>>();
  support::DiscoveryTestClock clock;
  auto plan = support::kDiscoveryTestPlan;
  plan.warmup_attempt_capacity = 64U;
  plan.measurement_attempt_capacity = 64U;
  calibration::DiscoveryRingPhaseBackend backend(plan, clock, *preparation);
  ASSERT_TRUE(backend.prepare_producer());
  ASSERT_TRUE(backend.prepare_consumer());
  ASSERT_EQ(backend.warmup_producer_attempt(0U).outcome,
            calibration::RingAttemptOutcome::advanced);
  const auto origin = clock.read();
  clock.fail_after_reads(5U); // completion fails after outer clock, invocation, acquire
                              // brackets and observation
  const auto drained = backend.drain_warmup(
      {origin.sample.relative_picoseconds, 1'000'000U, 9U, 1U, true});
  EXPECT_EQ(drained.stop, calibration::DiscoveryDrainStop::clock_failure);
  EXPECT_EQ(drained.attempts, 1U);
  EXPECT_EQ(drained.dequeued, 1U);
  EXPECT_FALSE(drained.reset_verified);
  const auto& phase = preparation->warmup;
  EXPECT_EQ(phase.consumer.consumed, 1U);
  ASSERT_EQ(phase.consumer.drain_requests, 1U);
  EXPECT_TRUE(phase.drain_rows[0U].operation.has_value());
  EXPECT_TRUE(phase.drain_rows[0U].access.has_value());
  EXPECT_FALSE(phase.drain_rows[0U].primary.has_value());
  EXPECT_EQ(phase.drain_rows[0U].candidate_consumed_ordinal,
            cpu_prefetch::workload::AcceptedOrdinal{0U});
  const auto selected = preparation->arena().select({0U});
  EXPECT_EQ(phase.consumer.state,
            cpu_prefetch::workload::mix_consumer_state({17U}, selected.record_index,
                                                       selected.record->payload));
  EXPECT_EQ(preparation->ring().audit_quiescent().consumer_position, 1U);
}

TEST(DiscoveryRingBackend, FailedPrimaryPrefixAndLaterDrainKeepRealConsumedOrdinals) {
  auto preparation = std::make_unique<support::SoftwareOnlyDiscoveryPreparation<64U>>();
  support::DiscoveryTestClock clock;
  auto plan = support::kDiscoveryTestPlan;
  plan.warmup_attempt_capacity = 64U;
  plan.measurement_attempt_capacity = 64U;
  calibration::DiscoveryRingPhaseBackend backend(plan, clock, *preparation);
  ASSERT_TRUE(backend.prepare_producer());
  ASSERT_TRUE(backend.prepare_consumer());
  ASSERT_EQ(backend.warmup_producer_attempt(0U).outcome,
            calibration::RingAttemptOutcome::advanced);
  ASSERT_EQ(backend.warmup_producer_attempt(0U).outcome,
            calibration::RingAttemptOutcome::advanced);
  clock.fail_after_reads(4U);
  EXPECT_EQ(backend.warmup_consumer_attempt().outcome,
            calibration::RingAttemptOutcome::clock_failure);
  EXPECT_FALSE(preparation->warmup.consumer.primary_prefix_complete);
  const auto origin = clock.read();
  const auto drained = backend.drain_warmup(
      {origin.sample.relative_picoseconds, 1'000'000U, 9U, 1U, true});
  EXPECT_EQ(drained.stop, calibration::DiscoveryDrainStop::consumer_failure);
  EXPECT_FALSE(drained.reset_verified);
  const auto& phase = preparation->warmup;
  EXPECT_EQ(phase.consumer.consumed, 2U);
  EXPECT_EQ(phase.consumer_stream.snapshot().row_count, 0U);
  EXPECT_EQ(phase.consumer.current.candidate_consumed_ordinal,
            cpu_prefetch::workload::AcceptedOrdinal{0U});
  EXPECT_EQ(phase.drain_rows[0U].candidate_consumed_ordinal,
            cpu_prefetch::workload::AcceptedOrdinal{1U});
  EXPECT_TRUE(phase.drain_rows[0U].primary.has_value());
  EXPECT_EQ(preparation->ring().audit_quiescent().consumer_position, 2U);
}

TEST(DiscoveryRingBackend,
     FiniteTraceExhaustionKeepsIncompleteHorizonAndExactActualData) {
  auto preparation =
      std::make_unique<support::SoftwareOnlyDiscoveryPreparation<20'000U, 1U>>();
  support::DiscoveryTestClock clock;
  support::DiscoveryTestRelax relax;
  auto plan = support::kDiscoveryTestPlan;
  plan.measurement_attempt_capacity = 1U;
  calibration::DiscoveryRingPhaseBackend backend(plan, clock, *preparation);
  const auto result = calibration::run_discovery_session(plan, clock, backend, relax);
  EXPECT_EQ(result.stop, calibration::DiscoverySessionStop::trace_capacity);
  EXPECT_EQ(preparation->measurement.consumer.last_join.status,
            calibration::DiscoveryJoinStatus::exact);
  EXPECT_EQ(preparation->measurement.producer.accepted,
            preparation->measurement.consumer.consumed);
  EXPECT_EQ(preparation->measurement.producer_stream.snapshot().completeness,
            storage::StreamCompleteness::sealed_incomplete);
}

TEST(DiscoveryRingBackend,
     PreparedReaderRejectsGeometryAndTruncationBeforeReadingBody) {
  auto preparation = std::make_unique<support::SoftwareOnlyDiscoveryPreparation<64U>>();
  support::DiscoveryTestClock clock;
  auto plan = support::kDiscoveryTestPlan;
  plan.warmup_attempt_capacity = 64U;
  plan.measurement_attempt_capacity = 64U;
  calibration::DiscoveryRingPhaseBackend backend(plan, clock, *preparation);
  ASSERT_TRUE(backend.prepare_producer());
  ASSERT_TRUE(backend.prepare_consumer());
  ASSERT_EQ(backend.warmup_producer_attempt(0U).outcome,
            calibration::RingAttemptOutcome::advanced);
  const auto original = preparation->warmup.producer_stream.snapshot();
  const auto layout = preparation->warmup.layout;
  for (std::size_t mutant = 0U; mutant < 7U; ++mutant) {
    auto snapshot = original;
    auto modified_layout = layout;
    switch (mutant) {
    case 0U:
      ++snapshot.row_bytes;
      break;
    case 1U:
      snapshot.bytes = snapshot.bytes.first(snapshot.bytes.size() - 1U);
      break;
    case 2U:
      ++snapshot.row_count;
      break;
    case 3U:
      snapshot.row_capacity = 0U;
      break;
    case 4U:
      modified_layout.prefix_bytes += 8U;
      break;
    case 5U:
      ++modified_layout.run_id_bytes;
      break;
    case 6U:
      snapshot.run_id = "";
      break;
    default:
      FAIL() << "unknown mutant";
      return;
    }
    EXPECT_FALSE(
        storage::read_prepared_producer_row(snapshot, modified_layout, 0U).has_value());
  }
  EXPECT_FALSE(storage::read_prepared_producer_row(original, layout, 1U).has_value());
}

TEST(DiscoveryRingBackend, CrossRowClockRegressionCannotPassLocallyOrderedRows) {
  for (const auto corrupt_producer : {true, false}) {
    auto preparation =
        std::make_unique<support::SoftwareOnlyDiscoveryPreparation<64U>>();
    support::DiscoveryTestClock clock;
    auto plan = support::kDiscoveryTestPlan;
    plan.warmup_attempt_capacity = 64U;
    plan.measurement_attempt_capacity = 64U;
    calibration::DiscoveryRingPhaseBackend backend(plan, clock, *preparation);
    ASSERT_TRUE(backend.prepare_producer());
    ASSERT_TRUE(backend.prepare_consumer());
    for (unsigned row = 0U; row < 2U; ++row) {
      ASSERT_EQ(backend.warmup_producer_attempt(0U).outcome,
                calibration::RingAttemptOutcome::advanced);
      ASSERT_EQ(backend.warmup_consumer_attempt().outcome,
                calibration::RingAttemptOutcome::advanced);
    }
    auto& phase = preparation->warmup;
    const auto prefix = static_cast<std::size_t>(phase.layout.prefix_bytes);
    if (corrupt_producer) {
      const auto row_bytes = static_cast<std::size_t>(phase.layout.producer_row_bytes);
      for (std::size_t word = 3U; word <= 12U; ++word) {
        for (std::size_t byte = 0U; byte < sizeof(std::uint64_t); ++byte) {
          phase.producer_bytes[row_bytes + prefix + word * sizeof(std::uint64_t) +
                               byte] =
              phase.producer_bytes[prefix + word * sizeof(std::uint64_t) + byte];
        }
      }
    } else {
      const auto row_bytes = static_cast<std::size_t>(phase.layout.consumer_row_bytes);
      overwrite_word(phase.consumer_bytes,
                     row_bytes + prefix + 2U * sizeof(std::uint64_t), 0U);
      overwrite_word(phase.consumer_bytes,
                     row_bytes + prefix + 3U * sizeof(std::uint64_t), 0U);
    }
    const auto joined = calibration::reconcile_discovery_primary(
        preparation->arena(), phase.producer_stream.snapshot(), phase.layout,
        phase.consumer_stream.snapshot(), phase.layout, {2U, 2U, 0U, 2U},
        {.initial = phase.consumer.initial_state, .observed = phase.consumer.state},
        true);
    EXPECT_EQ(joined.status, calibration::DiscoveryJoinStatus::timestamp_order);
  }
}

} // namespace
