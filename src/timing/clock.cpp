#include "cpu_prefetch/timing/clock.hpp"

#include <dlfcn.h>

#include <cstdint>
#include <limits>

namespace cpu_prefetch::timing {

auto absolute_nanoseconds_from_timespec(std::int64_t seconds,
                                        std::int64_t nanoseconds) noexcept
    -> AbsoluteClockReadResult {
  constexpr std::uint64_t nanoseconds_per_second = 1'000'000'000U;
  if (seconds < 0 || nanoseconds < 0 ||
      nanoseconds >= static_cast<std::int64_t>(nanoseconds_per_second)) {
    return {ClockReadStatus::invalid_timespec, 0U};
  }
  const auto unsigned_seconds = static_cast<std::uint64_t>(seconds);
  if (unsigned_seconds >
      std::numeric_limits<std::uint64_t>::max() / nanoseconds_per_second) {
    return {ClockReadStatus::overflow, 0U};
  }
  const auto whole_seconds = unsigned_seconds * nanoseconds_per_second;
  const auto subsecond = static_cast<std::uint64_t>(nanoseconds);
  if (subsecond > std::numeric_limits<std::uint64_t>::max() - whole_seconds) {
    return {ClockReadStatus::overflow, 0U};
  }
  return {ClockReadStatus::ok, whole_seconds + subsecond};
}

auto relative_clock_sample(ClockOrigin origin,
                           std::uint64_t absolute_nanoseconds) noexcept
    -> ClockReadResult {
  constexpr std::uint64_t picoseconds_per_nanosecond = 1000U;
  if (absolute_nanoseconds < origin.absolute_nanoseconds) {
    return {ClockReadStatus::before_origin, {0U, 0U}};
  }
  const auto relative_nanoseconds = absolute_nanoseconds - origin.absolute_nanoseconds;
  if (relative_nanoseconds >
      std::numeric_limits<std::uint64_t>::max() / picoseconds_per_nanosecond) {
    return {ClockReadStatus::overflow, {0U, 0U}};
  }
  return {ClockReadStatus::ok,
          {absolute_nanoseconds, relative_nanoseconds * picoseconds_per_nanosecond}};
}

auto monotonic_raw_resolution() noexcept -> ClockResolutionResult {
  timespec value{};
  if (::clock_getres(CLOCK_MONOTONIC_RAW, &value) != 0) {
    return {ClockReadStatus::call_failed, 0U};
  }
  const auto absolute =
      absolute_nanoseconds_from_timespec(static_cast<std::int64_t>(value.tv_sec),
                                         static_cast<std::int64_t>(value.tv_nsec));
  if (absolute.status != ClockReadStatus::ok) {
    return {absolute.status, 0U};
  }
  constexpr std::uint64_t picoseconds_per_nanosecond = 1000U;
  if (absolute.absolute_nanoseconds >
      std::numeric_limits<std::uint64_t>::max() / picoseconds_per_nanosecond) {
    return {ClockReadStatus::overflow, 0U};
  }
  return {ClockReadStatus::ok,
          absolute.absolute_nanoseconds * picoseconds_per_nanosecond};
}

auto probe_vdso_clock_gettime() noexcept -> VdsoClockEvidence {
  void* handle = ::dlopen("linux-vdso.so.1", RTLD_LAZY | RTLD_LOCAL);
  if (handle == nullptr) {
    return {false, false, false};
  }
  const bool symbol = ::dlsym(handle, "__vdso_clock_gettime") != nullptr;
  const bool versioned =
      ::dlvsym(handle, "__vdso_clock_gettime", "LINUX_2.6") != nullptr;
  static_cast<void>(::dlclose(handle));
  return {true, symbol, versioned};
}

} // namespace cpu_prefetch::timing
