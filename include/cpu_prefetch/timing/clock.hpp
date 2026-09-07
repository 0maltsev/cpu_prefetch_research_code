#ifndef CPU_PREFETCH_TIMING_CLOCK_HPP
#define CPU_PREFETCH_TIMING_CLOCK_HPP

#include <atomic>
#include <cstdint>
#include <limits>
#include <string_view>
#include <time.h>

namespace cpu_prefetch::timing {

inline constexpr std::string_view kClockSuiteId =
    "LINUX-CLOCK-MONOTONIC-RAW-VDSO-PS-v1";
inline constexpr std::string_view kBoundaryPolicyId =
    "TIMESTAMP-BOUNDARIES-BRACKETED-LMRV1";
inline constexpr std::string_view kQualificationPolicyId = "CLOCK-QUAL-LMRV1";
inline constexpr std::string_view kOverheadPolicyId = "CLOCK-OVERHEAD-UNCORRECTED-v1";
inline constexpr std::string_view kLogicalTimeUnit = "PICOSECONDS";

enum class ClockReadStatus : std::uint8_t {
  ok,
  call_failed,
  invalid_timespec,
  before_origin,
  overflow,
};

struct ClockOrigin final {
  std::uint64_t absolute_nanoseconds;
};

struct AbsoluteClockReadResult final {
  ClockReadStatus status;
  std::uint64_t absolute_nanoseconds;
};

struct ClockSample final {
  std::uint64_t absolute_nanoseconds;
  std::uint64_t relative_picoseconds;
};

struct ClockReadResult final {
  ClockReadStatus status;
  ClockSample sample;
};

struct ClockResolutionResult final {
  ClockReadStatus status;
  std::uint64_t resolution_picoseconds;
};

struct VdsoClockEvidence final {
  bool library_opened;
  bool clock_gettime_symbol_present;
  bool versioned_symbol_present;
};

[[nodiscard]] auto absolute_nanoseconds_from_timespec(std::int64_t seconds,
                                                      std::int64_t nanoseconds) noexcept
    -> AbsoluteClockReadResult;
[[nodiscard]] auto relative_clock_sample(ClockOrigin origin,
                                         std::uint64_t absolute_nanoseconds) noexcept
    -> ClockReadResult;
[[nodiscard]] auto monotonic_raw_resolution() noexcept -> ClockResolutionResult;
[[nodiscard]] auto probe_vdso_clock_gettime() noexcept -> VdsoClockEvidence;

[[nodiscard]] inline auto read_monotonic_raw_absolute() noexcept
    -> AbsoluteClockReadResult {
  timespec value{};
  std::atomic_signal_fence(std::memory_order_seq_cst);
  const auto result = ::clock_gettime(CLOCK_MONOTONIC_RAW, &value);
  std::atomic_signal_fence(std::memory_order_seq_cst);
  if (result != 0) {
    return {ClockReadStatus::call_failed, 0U};
  }
  return absolute_nanoseconds_from_timespec(static_cast<std::int64_t>(value.tv_sec),
                                            static_cast<std::int64_t>(value.tv_nsec));
}

class MonotonicRawClock final {
public:
  explicit MonotonicRawClock(ClockOrigin origin) noexcept : origin_(origin) {}

  [[nodiscard]] static auto capture_origin() noexcept -> AbsoluteClockReadResult {
    return read_monotonic_raw_absolute();
  }

  [[nodiscard]] inline auto read() const noexcept -> ClockReadResult {
    const auto absolute = read_monotonic_raw_absolute();
    if (absolute.status != ClockReadStatus::ok) {
      return {absolute.status, {0U, 0U}};
    }
    return relative_clock_sample(origin_, absolute.absolute_nanoseconds);
  }

  [[nodiscard]] auto origin() const noexcept -> ClockOrigin { return origin_; }

private:
  ClockOrigin origin_;
};

static_assert(std::atomic<std::uint64_t>::is_always_lock_free);

} // namespace cpu_prefetch::timing

#endif // CPU_PREFETCH_TIMING_CLOCK_HPP
