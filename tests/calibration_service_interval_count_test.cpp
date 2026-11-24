#include <gtest/gtest.h>

#include "cpu_prefetch/calibration/service_interval_count.hpp"

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
using Status = calibration::ServiceIntervalStatus;

auto run_id(std::string text = "interval") -> protocol::RunId {
  auto result = protocol::RunId::parse(std::move(text), "$test/run_id");
  if (!result) {
    throw std::logic_error("invalid test identity");
  }
  return std::move(result).value();
}

auto sample(std::uint64_t nanoseconds) -> timing::ClockSample {
  return {nanoseconds, (nanoseconds - 100U) * 1000U};
}

auto window() -> calibration::ServiceIntervalClock {
  return {timing::kClockSuiteId, "PICOSECONDS", 1'000'000'000'000U, 100U,
          sample(110U),          10'000U};
}

auto row(std::uint64_t ordinal, std::uint64_t begin, std::uint64_t end)
    -> timing::ConsumerObservation {
  return {{ordinal}, {7U}, sample(begin), sample(begin), sample(begin), sample(end)};
}

class Fixture final {
public:
  explicit Fixture(std::initializer_list<timing::ConsumerObservation> observations)
      : identity(run_id()), layout(storage::make_row_layout(identity.value())) {
    storage::ConsumerObservationStream stream(identity, observations.size());
    if (!stream.prepare_for_owner()) {
      throw std::logic_error("test stream preparation failed");
    }
    for (const auto& observation : observations) {
      if (stream.append(observation) != storage::AppendStatus::appended) {
        throw std::logic_error("test stream append failed");
      }
    }
    if (!stream.seal_complete()) {
      throw std::logic_error("test stream sealing failed");
    }
    snapshot = stream.snapshot();
    bytes.assign(snapshot.bytes.begin(), snapshot.bytes.end());
    snapshot.bytes = bytes;
    snapshot.run_id = identity.value();
  }

  auto count(calibration::ServiceIntervalClock clock = window()) const
      -> calibration::ServiceIntervalResult {
    return calibration::count_service_interval(snapshot, layout, identity,
                                               snapshot.row_count, clock);
  }

  struct WordPatch final {
    std::size_t index;
    std::uint64_t value;
  };

  void word(std::size_t row_index, WordPatch replacement) {
    const auto offset =
        row_index * static_cast<std::size_t>(layout.consumer_row_bytes) +
        static_cast<std::size_t>(layout.prefix_bytes) + replacement.index * 8U;
    for (std::size_t index = 0U; index < 8U; ++index) {
      bytes.at(offset + index) =
          static_cast<std::byte>((replacement.value >> (index * 8U)) & 0xffU);
    }
  }

  protocol::RunId identity;
  storage::RowLayout layout;
  storage::RawStreamSnapshot snapshot{};
  std::vector<std::byte> bytes;
};

TEST(ServiceIntervalCount, HalfOpenBoundariesCrossingAndDrainRetainEveryRow) {
  const Fixture data{row(0U, 110U, 110U), row(1U, 118U, 119U), row(2U, 119U, 120U),
                     row(3U, 121U, 130U)};
  const auto original = data.bytes;
  const auto result = data.count();
  ASSERT_EQ(result.status, Status::complete);
  const auto result_counts = result.counts;
  if (!result_counts.has_value()) {
    FAIL() << "successful counter did not return counts";
    return;
  }
  EXPECT_EQ(result_counts->consumed_count, 4U);
  EXPECT_EQ(result_counts->interval_consumed_count, 2U);
  EXPECT_EQ(result_counts->outside_interval_consumed_count, 2U);
  EXPECT_EQ(result_counts->interval_end_ticks, 20'000U);
  EXPECT_EQ(result_counts->measurement_window.measurement_origin.absolute_nanoseconds,
            110U);
  EXPECT_EQ(result_counts->measurement_window.measurement_origin.relative_picoseconds,
            10'000U);
  EXPECT_EQ(result_counts->measurement_window.clock_origin_absolute_nanoseconds, 100U);
  EXPECT_EQ(result_counts->measurement_window.duration_ticks, 10'000U);
  EXPECT_EQ(result_counts->measurement_window.ticks_per_second, 1'000'000'000'000U);
  EXPECT_EQ(result_counts->measurement_window.time_unit, "PICOSECONDS");
  EXPECT_EQ(result_counts->measurement_window.clock_suite_id, timing::kClockSuiteId);
  EXPECT_FALSE(result.failed_consumer_row.has_value());
  EXPECT_EQ(data.bytes, original);
}

TEST(ServiceIntervalCount, RejectsPreOriginAndCrossingStartMeasurementRows) {
  for (const auto completion : {109U, 110U, 111U}) {
    const Fixture data{row(0U, 109U, completion)};
    const auto result = data.count();
    EXPECT_EQ(result.status, Status::before_measurement_origin) << completion;
    EXPECT_FALSE(result.counts.has_value());
    EXPECT_EQ(result.failed_consumer_row, 0U);
  }
}

TEST(ServiceIntervalCount, EmptyAndAllOutsideHaveValidZeroNumerator) {
  const Fixture empty{};
  const auto zero = empty.count();
  ASSERT_EQ(zero.status, Status::complete);
  const auto zero_counts = zero.counts;
  if (!zero_counts.has_value()) {
    FAIL() << "successful counter did not return counts";
    return;
  }
  EXPECT_EQ(zero_counts->consumed_count, 0U);
  EXPECT_EQ(zero_counts->interval_consumed_count, 0U);
  EXPECT_EQ(zero_counts->outside_interval_consumed_count, 0U);
  const Fixture drained{row(0U, 119U, 120U), row(1U, 121U, 130U)};
  const auto outside = drained.count();
  ASSERT_EQ(outside.status, Status::complete);
  const auto outside_counts = outside.counts;
  if (!outside_counts.has_value()) {
    FAIL() << "successful counter did not return counts";
    return;
  }
  EXPECT_EQ(outside_counts->interval_consumed_count, 0U);
  EXPECT_EQ(outside_counts->outside_interval_consumed_count, 2U);
  EXPECT_EQ(outside_counts->consumed_count, 2U);
}

TEST(ServiceIntervalCount, EqualClocksAndExactNonNanosecondDuration) {
  const Fixture data{row(0U, 110U, 110U), row(1U, 110U, 110U), row(2U, 111U, 111U)};
  auto clock = window();
  clock.duration_ticks = 1U;
  const auto result = data.count(clock);
  ASSERT_EQ(result.status, Status::complete);
  const auto result_counts = result.counts;
  if (!result_counts.has_value()) {
    FAIL() << "successful counter did not return counts";
    return;
  }
  EXPECT_EQ(result_counts->interval_consumed_count, 2U);
  EXPECT_EQ(result_counts->outside_interval_consumed_count, 1U);
  EXPECT_EQ(result_counts->interval_end_ticks, 10'001U);
}

TEST(ServiceIntervalCount, RejectsWrongRunAndOrdinalWithoutPartialCount) {
  Fixture data{row(0U, 110U, 111U), row(1U, 111U, 112U)};
  EXPECT_EQ(calibration::count_service_interval(data.snapshot, data.layout,
                                                run_id("another"), 2U, window())
                .status,
            Status::identity_mismatch);
  data.word(1U, {0U, 0U});
  const auto result = data.count();
  EXPECT_EQ(result.status, Status::malformed_consumer);
  EXPECT_FALSE(result.counts.has_value());
  EXPECT_EQ(result.failed_consumer_row, 1U);
}

TEST(ServiceIntervalCount, RejectsLiteralRunLengthAndPaddingCorruption) {
  for (const auto index : {0U, 4U, 15U}) {
    Fixture data{row(0U, 110U, 111U)};
    data.bytes[index] ^= std::byte{1};
    EXPECT_EQ(data.count().status, Status::malformed_consumer) << index;
  }
}

TEST(ServiceIntervalCount, RejectsTruncatedExtraBytesAndMalformedLayout) {
  Fixture data{row(0U, 110U, 111U)};
  data.snapshot.bytes =
      std::span<const std::byte>(data.bytes).first(data.bytes.size() - 1U);
  EXPECT_EQ(data.count().status, Status::malformed_stream);
  data.bytes.push_back(std::byte{0});
  data.snapshot.bytes = data.bytes;
  EXPECT_EQ(data.count().status, Status::malformed_stream);
  data.bytes.pop_back();
  data.snapshot.bytes = data.bytes;
  ++data.layout.prefix_bytes;
  EXPECT_EQ(data.count().status, Status::malformed_stream);
  --data.layout.prefix_bytes;
  data.snapshot.stream_kind = protocol::StreamKind::producer;
  EXPECT_EQ(data.count().status, Status::malformed_stream);
}

TEST(ServiceIntervalCount, RequiresCompleteUnoverflowedStreamAndReconciledTotal) {
  Fixture data{row(0U, 110U, 111U)};
  EXPECT_EQ(calibration::count_service_interval(data.snapshot, data.layout,
                                                data.identity, 2U, window())
                .status,
            Status::count_mismatch);
  for (const auto state : {storage::StreamCompleteness::writing,
                           storage::StreamCompleteness::sealed_incomplete}) {
    data.snapshot.completeness = state;
    EXPECT_EQ(data.count().status, Status::stream_incomplete);
  }
  data.snapshot.completeness = storage::StreamCompleteness::sealed_complete;
  data.snapshot.overflowed = true;
  EXPECT_EQ(data.count().status, Status::stream_incomplete);
  data.snapshot.overflowed = false;
  data.snapshot.row_count = std::numeric_limits<std::uint64_t>::max();
  data.snapshot.row_capacity = data.snapshot.row_count;
  EXPECT_EQ(data.count().status, Status::malformed_stream);
}

TEST(ServiceIntervalCount, RejectsWrongClockDomainUnitAndScale) {
  const Fixture data{};
  auto clock = window();
  clock.clock_suite_id = "TSC";
  EXPECT_EQ(data.count(clock).status, Status::clock_domain_mismatch);
  clock = window();
  clock.time_unit = "NANOSECONDS";
  EXPECT_EQ(data.count(clock).status, Status::clock_domain_mismatch);
  clock = window();
  clock.ticks_per_second = 1'000'000'000U;
  EXPECT_EQ(data.count(clock).status, Status::clock_domain_mismatch);
  clock = window();
  clock.duration_ticks = 0U;
  EXPECT_EQ(data.count(clock).status, Status::invalid_duration);
}

TEST(ServiceIntervalCount, RejectsOriginMismatchAndCheckedClockConversionOverflow) {
  const Fixture data{};
  auto clock = window();
  ++clock.measurement_origin.relative_picoseconds;
  EXPECT_EQ(data.count(clock).status, Status::clock_binding_mismatch);
  clock = window();
  clock.clock_origin_absolute_nanoseconds = 111U;
  EXPECT_EQ(data.count(clock).status, Status::clock_binding_mismatch);
  clock = window();
  clock.measurement_origin.absolute_nanoseconds =
      std::numeric_limits<std::uint64_t>::max();
  EXPECT_EQ(data.count(clock).status, Status::arithmetic_overflow);
  clock = window();
  clock.duration_ticks = std::numeric_limits<std::uint64_t>::max();
  EXPECT_EQ(data.count(clock).status, Status::arithmetic_overflow);
}

TEST(ServiceIntervalCount, RejectsUnrepresentableAbsoluteEndpointEvenForEmptyStream) {
  const Fixture data{};
  auto clock = window();
  const auto origin = std::numeric_limits<std::uint64_t>::max() - 1U;
  clock.clock_origin_absolute_nanoseconds = origin;
  clock.measurement_origin = {origin, 0U};
  clock.duration_ticks = 2000U;
  const auto overflow = data.count(clock);
  EXPECT_EQ(overflow.status, Status::arithmetic_overflow);
  EXPECT_FALSE(overflow.counts.has_value());
  clock.duration_ticks = 1000U;
  EXPECT_EQ(data.count(clock).status, Status::complete);
  // A subnanosecond endpoint still needs its first at/after-end clock sample.
  clock.duration_ticks = 1001U;
  EXPECT_EQ(data.count(clock).status, Status::arithmetic_overflow);
  clock.clock_origin_absolute_nanoseconds = 0U;
  clock.measurement_origin = {0U, 0U};
  clock.duration_ticks = std::numeric_limits<std::uint64_t>::max();
  EXPECT_EQ(data.count(clock).status, Status::complete);
}

TEST(ServiceIntervalCount, ValidatesEveryTimestampIncludingOutsideIntervalRows) {
  for (const auto relative_word : {3U, 5U, 7U, 9U}) {
    Fixture data{row(0U, 121U, 130U)};
    data.word(0U, {relative_word, 1U});
    const auto result = data.count();
    EXPECT_EQ(result.status, Status::clock_binding_mismatch) << relative_word;
    EXPECT_FALSE(result.counts.has_value());
    EXPECT_EQ(result.failed_consumer_row, 0U);
  }
  Fixture before_origin{row(0U, 110U, 111U)};
  before_origin.word(0U, {2U, 99U});
  EXPECT_EQ(before_origin.count().status, Status::clock_binding_mismatch);
  Fixture overflow{row(0U, 110U, 111U)};
  overflow.word(0U, {8U, std::numeric_limits<std::uint64_t>::max()});
  EXPECT_EQ(overflow.count().status, Status::arithmetic_overflow);
}

TEST(ServiceIntervalCount, RejectsWithinAndAcrossRowTimestampReversal) {
  const Fixture within{row(0U, 112U, 111U)};
  EXPECT_EQ(within.count().status, Status::timestamp_order);
  const Fixture across{row(0U, 110U, 112U), row(1U, 111U, 113U)};
  const auto result = across.count();
  EXPECT_EQ(result.status, Status::timestamp_order);
  EXPECT_FALSE(result.counts.has_value());
  EXPECT_EQ(result.failed_consumer_row, 1U);
  Fixture middle{row(0U, 110U, 114U)};
  middle.word(0U, {4U, 112U});
  middle.word(0U, {5U, 12'000U});
  EXPECT_EQ(middle.count().status, Status::timestamp_order);
}

} // namespace
