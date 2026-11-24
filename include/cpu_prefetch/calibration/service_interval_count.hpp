#ifndef CPU_PREFETCH_CALIBRATION_SERVICE_INTERVAL_COUNT_HPP
#define CPU_PREFETCH_CALIBRATION_SERVICE_INTERVAL_COUNT_HPP

#include "cpu_prefetch/storage/raw_observations.hpp"

#include <cstdint>
#include <optional>
#include <string_view>

namespace cpu_prefetch::calibration {

// Explicit observed clock-origin and measurement-barrier bindings. Duration is
// the prospective measurement duration, never the observed drain duration.
struct ServiceIntervalClock final {
  std::string_view clock_suite_id;
  std::string_view time_unit;
  std::uint64_t ticks_per_second;
  std::uint64_t clock_origin_absolute_nanoseconds;
  timing::ClockSample measurement_origin;
  std::uint64_t duration_ticks;
};

enum class ServiceIntervalStatus : std::uint8_t {
  complete,
  identity_mismatch,
  clock_domain_mismatch,
  invalid_duration,
  clock_binding_mismatch,
  arithmetic_overflow,
  stream_incomplete,
  malformed_stream,
  count_mismatch,
  malformed_consumer,
  before_measurement_origin,
  timestamp_order,
};

struct ServiceIntervalCounts final {
  ServiceIntervalClock measurement_window;
  std::uint64_t interval_end_ticks;
  std::uint64_t consumed_count;
  std::uint64_t interval_consumed_count;
  std::uint64_t outside_interval_consumed_count;
};

struct ServiceIntervalResult final {
  ServiceIntervalStatus status;
  // No partial numerator is returned on failure.
  std::optional<ServiceIntervalCounts> counts{};
  std::optional<std::uint64_t> failed_consumer_row{};
};

// Cold path only, after owner quiescence and independent producer/consumer
// reconciliation. This checks the complete consumer stream against that join's
// total, not producer identity/checksum or external artifact admission. It never
// modifies/filters raw bytes or supplies a zero-loss or run-validity decision.
// Every f_i is checked, including outside-window rows. The half-open D211 count
// uses consumer_action_completion, never dequeue/attempt start or drain end.
// Measurement dequeue invocation cannot precede the actual start barrier;
// drained/reset warmup rows must not cross into this measurement-only stream.
// Memory is constant, no allocation/I/O/clock reads occur. Returned string_views
// borrow clock metadata; their backing storage must outlive the result.
[[nodiscard]] auto count_service_interval(const storage::RawStreamSnapshot& consumer,
                                          const storage::RowLayout& layout,
                                          const protocol::RunId& expected_run_id,
                                          std::uint64_t reconciled_total_consumed,
                                          ServiceIntervalClock clock) noexcept
    -> ServiceIntervalResult;

} // namespace cpu_prefetch::calibration

#endif // CPU_PREFETCH_CALIBRATION_SERVICE_INTERVAL_COUNT_HPP
