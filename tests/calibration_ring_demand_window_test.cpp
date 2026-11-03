#include <gtest/gtest.h>

#include "cpu_prefetch/calibration/ring_demand_window.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

namespace calibration = cpu_prefetch::calibration;
namespace protocol = cpu_prefetch::protocol;
namespace storage = cpu_prefetch::storage;
namespace timing = cpu_prefetch::timing;
using Status = calibration::RingDemandWindowStatus;
using Phase = calibration::RingDemandPhase;
using Worker = calibration::RingWorker;
using Outcome = calibration::RingAttemptOutcome;

auto identity(std::string value = "d212") -> protocol::RunId {
  auto parsed = protocol::RunId::parse(std::move(value), "$test");
  if (!parsed) {
    throw std::logic_error("test identity rejected");
  }
  return std::move(parsed).value();
}

auto sample(std::uint64_t nanoseconds) -> timing::ClockReadResult {
  return {timing::ClockReadStatus::ok, {nanoseconds, (nanoseconds - 100U) * 1000U}};
}

auto window() -> calibration::ServiceIntervalClock {
  return {timing::kClockSuiteId, "PICOSECONDS", 1'000'000'000'000U, 100U,
          sample(110U).sample,   10'000U};
}

struct Attempt final {
  std::uint64_t ordinal;
  Outcome outcome;
  std::uint64_t advancement;
};

auto row(Attempt attempt, std::uint64_t start, std::uint64_t end)
    -> calibration::RingDemandRecord {
  return {attempt.ordinal, attempt.outcome, attempt.advancement, sample(start),
          sample(end)};
}

class Fixture final {
public:
  explicit Fixture(std::initializer_list<calibration::RingDemandRecord> rows,
                   Worker worker = Worker::producer)
      : run_id(identity()), layout(calibration::ring_demand_layout(run_id)) {
    if (rows.size() * layout.row_bytes > bytes.size()) {
      throw std::logic_error("test fixture buffer exceeded");
    }
    calibration::RingDemandStream stream(
        run_id, worker, rows.size(),
        std::span(bytes).first(
            calibration::ring_demand_storage_requirements(run_id, rows.size())));
    if (!stream.prepare_for_owner()) {
      throw std::logic_error("test prepare failed");
    }
    for (const auto& record : rows) {
      if (stream.append(record) != storage::AppendStatus::appended) {
        throw std::logic_error("test append failed");
      }
    }
    if (!stream.seal_complete()) {
      throw std::logic_error("test seal failed");
    }
    snapshot = stream.snapshot();
    demand.fill(999U);
    issue.fill(999U);
  }

  auto classify() -> calibration::RingDemandWindowResult {
    return calibration::classify_ring_demand_window(snapshot, run_id, snapshot.worker,
                                                    Phase::measurement, window(), 1U,
                                                    {demand, issue});
  }

  auto warmup() -> calibration::RingDemandWindowResult {
    return calibration::classify_ring_demand_window(snapshot, run_id, snapshot.worker,
                                                    Phase::warmup, window(),
                                                    std::nullopt, {demand, issue});
  }

  struct Patch final {
    std::size_t word;
    std::uint64_t value;
  };

  void word(std::size_t index, Patch replacement) {
    const auto offset = index * static_cast<std::size_t>(layout.row_bytes) +
                        static_cast<std::size_t>(layout.prefix_bytes) +
                        replacement.word * 8U;
    for (std::size_t byte = 0U; byte < 8U; ++byte) {
      bytes.at(offset + byte) =
          static_cast<std::byte>((replacement.value >> (byte * 8U)) & 255U);
    }
  }

  void expect_untouched() const {
    EXPECT_TRUE(std::all_of(demand.begin(), demand.end(),
                            [](auto value) { return value == 999U; }));
    EXPECT_TRUE(std::all_of(issue.begin(), issue.end(),
                            [](auto value) { return value == 999U; }));
  }

  protocol::RunId run_id;
  calibration::RingDemandLayout layout;
  alignas(64) std::array<std::byte, 4096U> bytes{};
  calibration::RingDemandSnapshot snapshot{};
  std::array<std::uint64_t, 16U> demand{};
  std::array<std::uint64_t, 16U> issue{};
};

TEST(RingDemandWindow, ExactWireBytesAndFailedClockRoundTrip) {
  Fixture data{row({0U, Outcome::advanced, 0U}, 110U, 111U)};
  EXPECT_EQ(data.layout.prefix_bytes, 8U);
  EXPECT_EQ(data.layout.row_bytes, 80U);
  EXPECT_EQ(data.snapshot.format_id, "Q16A-DEMAND-U64LE-LP-RUNID-v1");
  const std::array<unsigned char, 8U> prefix{4U, 0U, 0U, 0U, 'd', '2', '1', '2'};
  for (std::size_t index = 0U; index < prefix.size(); ++index) {
    EXPECT_EQ(data.bytes[index], static_cast<std::byte>(prefix[index]));
  }
  const std::array<std::uint64_t, 9U> words{0U,      0U, 0U,   0U,     110U,
                                            10'000U, 0U, 111U, 11'000U};
  for (std::size_t index = 0U; index < words.size(); ++index) {
    for (std::size_t byte = 0U; byte < 8U; ++byte) {
      EXPECT_EQ(data.bytes[8U + index * 8U + byte],
                static_cast<std::byte>((words[index] >> (byte * 8U)) & 255U));
    }
  }
  auto failed = row({0U, Outcome::full, 0U}, 110U, 111U);
  failed.before.status = timing::ClockReadStatus::call_failed;
  failed.after.status = timing::ClockReadStatus::overflow;
  Fixture evidence{failed};
  const auto decoded = calibration::read_ring_demand_row(evidence.snapshot, 0U);
  if (!decoded.has_value()) {
    FAIL() << "retained failure record did not decode";
    return;
  }
  EXPECT_EQ(decoded->outcome, Outcome::full);
  EXPECT_EQ(decoded->before.status, timing::ClockReadStatus::call_failed);
  EXPECT_EQ(decoded->before.sample.absolute_nanoseconds, 110U);
  EXPECT_EQ(decoded->after.status, timing::ClockReadStatus::overflow);
  EXPECT_EQ(evidence.classify().status, Status::clock_failure);
  evidence.expect_untouched();
}

TEST(RingDemandWindow, HalfOpenStartCrossingBracketAndUninterruptedAdvancePairs) {
  Fixture data{row({0U, Outcome::advanced, 0U}, 110U, 111U),
               row({1U, Outcome::full, 0U}, 112U, 113U),
               row({2U, Outcome::advanced, 1U}, 119U, 121U),
               row({3U, Outcome::advanced, 2U}, 121U, 121U),
               row({4U, Outcome::full, 0U}, 122U, 122U)};
  const auto before = data.bytes;
  const auto result = data.classify();
  ASSERT_EQ(result.status, Status::complete);
  const auto series = result.series;
  if (!series.has_value()) {
    FAIL() << "successful classifier missing series";
    return;
  }
  EXPECT_EQ(series->total_attempts, 5U);
  EXPECT_EQ(series->total_advancements, 3U);
  EXPECT_EQ(series->outside_window_attempts, 2U);
  EXPECT_EQ(series->eligible_advancements, 2U);
  EXPECT_EQ(series->eligible.nonadvancing_count, 1U);
  EXPECT_TRUE(series->inferential_eligible);
  EXPECT_EQ(std::vector(series->eligible.demand_ticks.begin(),
                        series->eligible.demand_ticks.end()),
            (std::vector<std::uint64_t>{1000U, 1000U, 2000U}));
  EXPECT_EQ(std::vector(series->eligible.issue_ticks.begin(),
                        series->eligible.issue_ticks.end()),
            (std::vector<std::uint64_t>{9000U}));
  EXPECT_EQ(data.bytes, before);
}

TEST(RingDemandWindow, ConsumerEmptyDoesNotBreakPairsAndExactEndIsExcluded) {
  Fixture data({row({0U, Outcome::advanced, 0U}, 110U, 111U),
                row({1U, Outcome::empty, 0U}, 111U, 112U),
                row({2U, Outcome::advanced, 1U}, 113U, 114U),
                row({3U, Outcome::advanced, 2U}, 120U, 120U)},
               Worker::consumer);
  const auto result = data.classify();
  ASSERT_EQ(result.status, Status::complete);
  const auto series = result.series;
  if (!series.has_value()) {
    FAIL() << "successful classifier missing series";
    return;
  }
  EXPECT_EQ(series->outside_window_attempts, 1U);
  EXPECT_EQ(series->eligible.demand_ticks.size(), 3U);
  ASSERT_EQ(series->eligible.issue_ticks.size(), 1U);
  EXPECT_EQ(series->eligible.issue_ticks[0U], 3000U);
  EXPECT_EQ(series->eligible.nonadvancing_count, 1U);
}

TEST(RingDemandWindow, WarmupValidatesRawButDoesNotInferOrRequirePositiveSeries) {
  Fixture data{row({0U, Outcome::advanced, 0U}, 110U, 110U),
               row({1U, Outcome::advanced, 1U}, 110U, 110U),
               row({2U, Outcome::full, 0U}, 120U, 120U)};
  const auto result = data.warmup();
  ASSERT_EQ(result.status, Status::complete);
  const auto series = result.series;
  if (!series.has_value()) {
    FAIL() << "raw warmup validation missing totals";
    return;
  }
  EXPECT_FALSE(series->inferential_eligible);
  EXPECT_TRUE(series->eligible.demand_ticks.empty());
  EXPECT_TRUE(series->eligible.issue_ticks.empty());
  EXPECT_EQ(series->eligible_advancements, 0U);
  EXPECT_EQ(series->total_advancements, 2U);
  EXPECT_EQ(series->outside_window_attempts, 1U);
  data.expect_untouched();
  EXPECT_EQ(data.classify().status, Status::nonpositive_demand);
  Fixture empty{};
  EXPECT_EQ(empty.warmup().status, Status::complete);
  EXPECT_EQ(empty.classify().status, Status::insufficient_observations);
}

TEST(RingDemandWindow, ExplicitPhaseAndMinimumContracts) {
  Fixture data{row({0U, Outcome::advanced, 0U}, 110U, 111U),
               row({1U, Outcome::advanced, 1U}, 112U, 113U)};
  for (const auto phase : {Phase::measurement, Phase::warmup}) {
    for (const auto minimum :
         {std::optional<std::uint64_t>{}, std::optional<std::uint64_t>{0U},
          std::optional<std::uint64_t>{1U}}) {
      const auto result = calibration::classify_ring_demand_window(
          data.snapshot, data.run_id, Worker::producer, phase, window(), minimum,
          {data.demand, data.issue});
      const bool valid = (phase == Phase::warmup && !minimum.has_value()) ||
                         (phase == Phase::measurement && minimum == 1U);
      EXPECT_EQ(result.status,
                valid ? Status::complete : Status::invalid_phase_contract);
    }
  }
  const auto insufficient = calibration::classify_ring_demand_window(
      data.snapshot, data.run_id, Worker::producer, Phase::measurement, window(), 2U,
      {data.demand, data.issue});
  EXPECT_EQ(insufficient.status, Status::insufficient_observations);
  EXPECT_FALSE(insufficient.series.has_value());
}

TEST(RingDemandWindow, EligibleZeroIsNotFilteredAndOneAdvanceHasNoIssue) {
  Fixture zero{row({0U, Outcome::advanced, 0U}, 110U, 111U),
               row({1U, Outcome::full, 0U}, 112U, 112U),
               row({2U, Outcome::advanced, 1U}, 113U, 114U)};
  EXPECT_EQ(zero.classify().status, Status::nonpositive_demand);
  zero.expect_untouched();
  Fixture single{row({0U, Outcome::advanced, 0U}, 110U, 111U),
                 row({1U, Outcome::full, 0U}, 112U, 113U),
                 row({2U, Outcome::advanced, 1U}, 120U, 121U)};
  EXPECT_EQ(single.classify().status, Status::insufficient_observations);
  single.expect_untouched();
}

TEST(RingDemandWindow, InvalidExcludedDrainIsNeverDiscarded) {
  for (const auto patch : {Fixture::Patch{0U, 99U},
                           {1U, 2U},
                           {2U, 99U},
                           {3U, 1U},
                           {4U, 1U},
                           {5U, 0U},
                           {6U, 4U},
                           {7U, 99U},
                           {8U, 0U},
                           {1U, 256U},
                           {3U, 256U},
                           {6U, 256U}}) {
    Fixture data{row({0U, Outcome::advanced, 0U}, 110U, 111U),
                 row({1U, Outcome::advanced, 1U}, 112U, 113U),
                 row({2U, Outcome::advanced, 2U}, 120U, 121U)};
    data.word(2U, patch);
    const auto result = data.classify();
    EXPECT_NE(result.status, Status::complete) << patch.word << ':' << patch.value;
    EXPECT_FALSE(result.series.has_value());
    EXPECT_EQ(result.failed_row, 2U);
    data.expect_untouched();
    EXPECT_NE(data.warmup().status, Status::complete);
  }
}

TEST(RingDemandWindow, RejectsPreOriginReversedAndCrossRowClocks) {
  for (const auto times :
       {std::array<std::uint64_t, 2U>{109U, 111U}, {112U, 111U}, {110U, 111U}}) {
    Fixture data{row({0U, Outcome::advanced, 0U}, 110U, 112U),
                 row({1U, Outcome::advanced, 1U}, times[0U], times[1U])};
    const auto expected =
        times[0U] < 110U ? Status::before_measurement_origin : Status::timestamp_order;
    EXPECT_EQ(data.classify().status, expected);
    EXPECT_EQ(data.warmup().status, expected);
    data.expect_untouched();
  }
}

TEST(RingDemandWindow, OrdinalsAndRoleAreCheckedAcrossAllAttempts) {
  for (const auto patch : {Fixture::Patch{0U, 1U}, {2U, 1U}, {1U, 2U}}) {
    Fixture data{row({0U, Outcome::advanced, 0U}, 110U, 111U),
                 row({1U, Outcome::full, 0U}, 112U, 113U),
                 row({2U, Outcome::advanced, 1U}, 114U, 115U)};
    data.word(patch.word == 2U ? 1U : 0U, patch);
    EXPECT_NE(data.classify().status, Status::complete);
    data.expect_untouched();
  }
  Fixture consumer({row({0U, Outcome::full, 0U}, 110U, 111U)}, Worker::consumer);
  EXPECT_EQ(consumer.classify().status, Status::invalid_outcome);
}

TEST(RingDemandWindow, PhysicalShapePrefixPaddingAndIdentityAreMandatory) {
  for (const auto mutation : {0U, 1U, 2U, 3U, 4U, 5U, 6U, 7U}) {
    Fixture data{row({0U, Outcome::advanced, 0U}, 110U, 111U),
                 row({1U, Outcome::advanced, 1U}, 112U, 113U)};
    switch (mutation) {
    case 0U:
      data.bytes[0U] = std::byte{5U};
      break;
    case 1U:
      data.bytes[4U] = std::byte{'x'};
      break;
    case 2U:
      data.snapshot.bytes = data.snapshot.bytes.first(data.snapshot.bytes.size() - 1U);
      break;
    case 3U:
      data.snapshot.bytes =
          std::span(data.bytes).first(data.snapshot.bytes.size() + 1U);
      break;
    case 4U:
      ++data.snapshot.row_bytes;
      break;
    case 5U:
      --data.snapshot.row_capacity;
      break;
    case 6U:
      data.snapshot.row_capacity = std::numeric_limits<std::uint64_t>::max();
      break;
    default:
      data.snapshot.format_id = storage::kRawFormatId;
      break;
    }
    EXPECT_FALSE(calibration::read_ring_demand_row(data.snapshot, 0U).has_value());
    EXPECT_NE(data.classify().status, Status::complete);
    data.expect_untouched();
  }
  const auto id = identity("pad");
  alignas(64) std::array<std::byte, 80U> bytes{};
  calibration::RingDemandStream stream(id, Worker::producer, 1U, bytes);
  ASSERT_TRUE(stream.prepare_for_owner());
  ASSERT_EQ(stream.append(row({0U, Outcome::advanced, 0U}, 110U, 111U)),
            storage::AppendStatus::appended);
  ASSERT_TRUE(stream.seal_complete());
  EXPECT_TRUE(calibration::read_ring_demand_row(stream.snapshot(), 0U).has_value());
  bytes[7U] = std::byte{1U};
  EXPECT_FALSE(calibration::read_ring_demand_row(stream.snapshot(), 0U).has_value());
  Fixture data{};
  EXPECT_EQ(calibration::classify_ring_demand_window(
                data.snapshot, identity("other"), Worker::producer, Phase::measurement,
                window(), 1U, {data.demand, data.issue})
                .status,
            Status::identity_mismatch);
  EXPECT_EQ(calibration::classify_ring_demand_window(
                data.snapshot, data.run_id, Worker::consumer, Phase::measurement,
                window(), 1U, {data.demand, data.issue})
                .status,
            Status::identity_mismatch);
}

TEST(RingDemandWindow, ExplicitClockDomainOriginAndCheckedEndpoints) {
  Fixture data{};
  for (const auto mutation : {0U, 1U, 2U, 3U, 4U, 5U, 6U}) {
    auto clock = window();
    switch (mutation) {
    case 0U:
      clock.clock_suite_id = "other";
      break;
    case 1U:
      clock.time_unit = "NANOSECONDS";
      break;
    case 2U:
      clock.ticks_per_second = 1000U;
      break;
    case 3U:
      clock.duration_ticks = 0U;
      break;
    case 4U:
      ++clock.measurement_origin.relative_picoseconds;
      break;
    case 5U:
      clock.duration_ticks = std::numeric_limits<std::uint64_t>::max();
      break;
    default:
      clock.clock_origin_absolute_nanoseconds = 111U;
      break;
    }
    const auto result = calibration::classify_ring_demand_window(
        data.snapshot, data.run_id, Worker::producer, Phase::warmup, clock,
        std::nullopt, {});
    EXPECT_NE(result.status, Status::complete);
  }
  auto clock = window();
  clock.clock_origin_absolute_nanoseconds =
      std::numeric_limits<std::uint64_t>::max() - 1U;
  clock.measurement_origin = {clock.clock_origin_absolute_nanoseconds, 0U};
  clock.duration_ticks = 2000U;
  EXPECT_EQ(calibration::classify_ring_demand_window(data.snapshot, data.run_id,
                                                     Worker::producer, Phase::warmup,
                                                     clock, std::nullopt, {})
                .status,
            Status::arithmetic_overflow);
  clock.duration_ticks = 1000U;
  EXPECT_EQ(calibration::classify_ring_demand_window(data.snapshot, data.run_id,
                                                     Worker::producer, Phase::warmup,
                                                     clock, std::nullopt, {})
                .status,
            Status::complete);
  clock.duration_ticks = 1001U;
  EXPECT_EQ(calibration::classify_ring_demand_window(data.snapshot, data.run_id,
                                                     Worker::producer, Phase::warmup,
                                                     clock, std::nullopt, {})
                .status,
            Status::arithmetic_overflow);
}

TEST(RingDemandWindow, OutputBudgetsDoNotPartiallyPublishOrOverwriteEvidence) {
  Fixture data{row({0U, Outcome::advanced, 0U}, 110U, 111U),
               row({1U, Outcome::advanced, 1U}, 112U, 113U)};
  for (const auto buffers : {calibration::RingDemandWindowBuffers{{}, data.issue},
                             {data.demand, {}},
                             {data.demand, data.demand}}) {
    const auto result = calibration::classify_ring_demand_window(
        data.snapshot, data.run_id, Worker::producer, Phase::measurement, window(), 1U,
        buffers);
    EXPECT_NE(result.status, Status::complete);
    EXPECT_FALSE(result.series.has_value());
    data.expect_untouched();
  }
  const auto before = data.bytes;
  const auto alias =
      std::span(reinterpret_cast<std::uint64_t*>(data.bytes.data()), 16U);
  EXPECT_EQ(calibration::classify_ring_demand_window(
                data.snapshot, data.run_id, Worker::producer, Phase::measurement,
                window(), 1U, {alias, data.issue})
                .status,
            Status::overlapping_output);
  EXPECT_EQ(data.bytes, before);
}

TEST(RingDemandWindow, PreparationCapacitySealingAndIncompleteEvidence) {
  const auto id = identity();
  alignas(64) std::array<std::byte, 80U> bytes{};
  calibration::RingDemandStream stream(id, Worker::producer, 1U, bytes);
  const auto record = row({0U, Outcome::advanced, 0U}, 110U, 111U);
  EXPECT_EQ(stream.append(record), storage::AppendStatus::stream_unprepared);
  EXPECT_FALSE(stream.seal_complete());
  EXPECT_TRUE(stream.prepare_for_owner());
  EXPECT_FALSE(stream.prepare_for_owner());
  EXPECT_EQ(stream.append(record), storage::AppendStatus::appended);
  const auto original = bytes;
  EXPECT_EQ(stream.append(record), storage::AppendStatus::buffer_overflow);
  EXPECT_EQ(bytes, original);
  EXPECT_TRUE(stream.snapshot().overflowed);
  EXPECT_EQ(stream.snapshot().row_count, 1U);
  EXPECT_FALSE(stream.seal_complete());
  EXPECT_EQ(stream.append(record), storage::AppendStatus::stream_sealed);
  EXPECT_EQ(calibration::classify_ring_demand_window(stream.snapshot(), id,
                                                     Worker::producer, Phase::warmup,
                                                     window(), std::nullopt, {})
                .status,
            Status::stream_incomplete);
  Fixture data{};
  for (const auto completeness : {storage::StreamCompleteness::writing,
                                  storage::StreamCompleteness::sealed_incomplete}) {
    data.snapshot.completeness = completeness;
    EXPECT_EQ(data.warmup().status, Status::stream_incomplete);
  }
  data.snapshot.completeness = storage::StreamCompleteness::sealed_complete;
  data.snapshot.overflowed = true;
  EXPECT_EQ(data.warmup().status, Status::stream_incomplete);
}

TEST(RingDemandWindow, OutputCannotAliasBorrowedFormatOrClockMetadata) {
  Fixture data{row({0U, Outcome::advanced, 0U}, 110U, 111U),
               row({1U, Outcome::advanced, 1U}, 112U, 113U)};
  for (const auto field : {0U, 1U, 2U}) {
    alignas(64) std::array<std::uint64_t, 16U> metadata{};
    const auto text = field == 0U   ? calibration::kRingDemandFormatId
                      : field == 1U ? timing::kClockSuiteId
                                    : storage::kRawTimeUnit;
    auto* characters = reinterpret_cast<char*>(metadata.data());
    std::copy(text.begin(), text.end(), characters);
    const auto before = metadata;
    auto snapshot = data.snapshot;
    auto clock = window();
    const std::string_view borrowed(characters, text.size());
    if (field == 0U) {
      snapshot.format_id = borrowed;
    } else if (field == 1U) {
      clock.clock_suite_id = borrowed;
    } else {
      clock.time_unit = borrowed;
    }
    EXPECT_EQ(calibration::classify_ring_demand_window(
                  snapshot, data.run_id, Worker::producer, Phase::measurement, clock,
                  1U, {metadata, data.issue})
                  .status,
              Status::overlapping_output);
    EXPECT_EQ(metadata, before);
    data.expect_untouched();
  }
}

TEST(RingDemandWindow, SetupRejectsOverflowMisalignmentAndWrongSize) {
  const auto id = identity();
  alignas(64) std::array<std::byte, 128U> bytes{};
  EXPECT_THROW(static_cast<void>(calibration::ring_demand_storage_requirements(
                   id, std::numeric_limits<std::uint64_t>::max())),
               storage::StorageSetupError);
  EXPECT_THROW((calibration::RingDemandStream{id, Worker::producer, 1U, bytes}),
               storage::StorageSetupError);
  EXPECT_THROW((calibration::RingDemandStream{id, Worker::producer, 1U,
                                              std::span(bytes).subspan(1U, 80U)}),
               storage::StorageSetupError);
  calibration::RingDemandStream empty(id, Worker::producer, 0U, {});
  ASSERT_TRUE(empty.prepare_for_owner());
  ASSERT_TRUE(empty.seal_complete());
  EXPECT_EQ(empty.snapshot().row_count, 0U);
  EXPECT_EQ(empty.append(row({0U, Outcome::full, 0U}, 110U, 111U)),
            storage::AppendStatus::stream_sealed);
}

} // namespace
