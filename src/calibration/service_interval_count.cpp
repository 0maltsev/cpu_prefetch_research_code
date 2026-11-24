#include "cpu_prefetch/calibration/service_interval_count.hpp"

#include <array>
#include <limits>

namespace cpu_prefetch::calibration {
namespace {

[[nodiscard]] auto check_sample(timing::ClockOrigin origin,
                                timing::ClockSample sample) noexcept
    -> ServiceIntervalStatus {
  const auto recomputed =
      timing::relative_clock_sample(origin, sample.absolute_nanoseconds);
  if (recomputed.status == timing::ClockReadStatus::overflow) {
    return ServiceIntervalStatus::arithmetic_overflow;
  }
  if (recomputed.status != timing::ClockReadStatus::ok ||
      recomputed.sample.relative_picoseconds != sample.relative_picoseconds) {
    return ServiceIntervalStatus::clock_binding_mismatch;
  }
  return ServiceIntervalStatus::complete;
}

[[nodiscard]] auto ordered(timing::ClockSample before,
                           timing::ClockSample after) noexcept -> bool {
  return before.absolute_nanoseconds <= after.absolute_nanoseconds &&
         before.relative_picoseconds <= after.relative_picoseconds;
}

} // namespace

auto count_service_interval(const storage::RawStreamSnapshot& consumer,
                            const storage::RowLayout& layout,
                            const protocol::RunId& expected_run_id,
                            std::uint64_t reconciled_total_consumed,
                            ServiceIntervalClock clock) noexcept
    -> ServiceIntervalResult {
  constexpr std::uint64_t picoseconds_per_second = 1'000'000'000'000U;
  if (consumer.run_id != expected_run_id.value()) {
    return {ServiceIntervalStatus::identity_mismatch};
  }
  if (clock.clock_suite_id != timing::kClockSuiteId ||
      clock.time_unit != storage::kRawTimeUnit ||
      clock.ticks_per_second != picoseconds_per_second) {
    return {ServiceIntervalStatus::clock_domain_mismatch};
  }
  if (clock.duration_ticks == 0U) {
    return {ServiceIntervalStatus::invalid_duration};
  }
  const auto origin_status =
      check_sample({clock.clock_origin_absolute_nanoseconds}, clock.measurement_origin);
  if (origin_status != ServiceIntervalStatus::complete) {
    return {origin_status};
  }
  const auto begin = clock.measurement_origin.relative_picoseconds;
  if (clock.duration_ticks > std::numeric_limits<std::uint64_t>::max() - begin) {
    return {ServiceIntervalStatus::arithmetic_overflow};
  }
  const auto end = begin + clock.duration_ticks;
  // The first possible nanosecond sample at/after the exclusive ps endpoint
  // must fit the same uint64 absolute clock domain. Avoid end + 999 overflow.
  const auto end_nanoseconds = end / 1000U + (end % 1000U == 0U ? 0U : 1U);
  if (end_nanoseconds > std::numeric_limits<std::uint64_t>::max() -
                            clock.clock_origin_absolute_nanoseconds) {
    return {ServiceIntervalStatus::arithmetic_overflow};
  }
  if (consumer.completeness != storage::StreamCompleteness::sealed_complete ||
      consumer.overflowed) {
    return {ServiceIntervalStatus::stream_incomplete};
  }
  if (!storage::prepared_primary_stream_shape(consumer, layout,
                                              protocol::StreamKind::consumer)) {
    return {ServiceIntervalStatus::malformed_stream};
  }
  if (consumer.row_count != reconciled_total_consumed) {
    return {ServiceIntervalStatus::count_mismatch};
  }
  ServiceIntervalCounts counts{clock, end, consumer.row_count, 0U, 0U};
  std::optional<timing::ClockSample> previous_completion;
  for (std::uint64_t index = 0U; index < consumer.row_count; ++index) {
    const auto row = storage::read_prepared_consumer_row(consumer, layout, index);
    if (!row.has_value()) {
      return {ServiceIntervalStatus::malformed_consumer, std::nullopt, index};
    }
    const std::array samples{row->dequeue_invocation, row->dequeue_linearization,
                             row->dequeue_completion, row->consumer_action_completion};
    for (const auto sample : samples) {
      const auto status =
          check_sample({clock.clock_origin_absolute_nanoseconds}, sample);
      if (status != ServiceIntervalStatus::complete) {
        return {status, std::nullopt, index};
      }
    }
    if (row->dequeue_invocation.relative_picoseconds < begin) {
      return {ServiceIntervalStatus::before_measurement_origin, std::nullopt, index};
    }
    if ((previous_completion.has_value() &&
         !ordered(*previous_completion, samples[0U])) ||
        !ordered(samples[0U], samples[1U]) || !ordered(samples[1U], samples[2U]) ||
        !ordered(samples[2U], samples[3U])) {
      return {ServiceIntervalStatus::timestamp_order, std::nullopt, index};
    }
    const auto completion = row->consumer_action_completion.relative_picoseconds;
    if (begin <= completion && completion < end) {
      ++counts.interval_consumed_count;
    } else {
      ++counts.outside_interval_consumed_count;
    }
    previous_completion = row->consumer_action_completion;
  }
  // Each row increments exactly one counter, so neither increment nor the
  // partition total can overflow the already shape-checked uint64 row count.
  return {ServiceIntervalStatus::complete, counts};
}

} // namespace cpu_prefetch::calibration
