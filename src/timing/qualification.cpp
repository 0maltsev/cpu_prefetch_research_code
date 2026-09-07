#include "cpu_prefetch/timing/qualification.hpp"

#include <algorithm>
#include <limits>

namespace cpu_prefetch::timing {
namespace {

[[nodiscard]] auto inverse_ecdf(std::vector<std::uint64_t> values,
                                std::size_t numerator, std::size_t denominator)
    -> std::uint64_t {
  std::sort(values.begin(), values.end());
  const auto count = values.size();
  const auto quotient = count / denominator;
  const auto remainder = count % denominator;
  const auto rank =
      quotient * numerator + (remainder * numerator + denominator - 1U) / denominator;
  return values[rank - 1U];
}

[[nodiscard]] auto signed_difference(std::uint64_t left, std::uint64_t right,
                                     std::int64_t& output) noexcept -> bool {
  constexpr auto maximum =
      static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max());
  if (left >= right) {
    const auto difference = left - right;
    if (difference > maximum) {
      return false;
    }
    output = static_cast<std::int64_t>(difference);
    return true;
  }
  const auto difference = right - left;
  if (difference > maximum) {
    return false;
  }
  output = -static_cast<std::int64_t>(difference);
  return true;
}

[[nodiscard]] auto interval_width(std::int64_t lower, std::int64_t upper) noexcept
    -> std::uint64_t {
  if (lower >= 0) {
    return static_cast<std::uint64_t>(upper - lower);
  }
  if (upper < 0) {
    return static_cast<std::uint64_t>(-(lower + 1)) -
           static_cast<std::uint64_t>(-(upper + 1));
  }
  return static_cast<std::uint64_t>(-(lower + 1)) + 1U +
         static_cast<std::uint64_t>(upper);
}

[[nodiscard]] auto checked_sum(std::int64_t left, std::int64_t right,
                               std::int64_t& output) noexcept -> bool {
  if ((right > 0 && left > std::numeric_limits<std::int64_t>::max() - right) ||
      (right < 0 && left < std::numeric_limits<std::int64_t>::min() - right)) {
    return false;
  }
  output = left + right;
  return true;
}

} // namespace

auto evaluate_clock_sequence(std::span<const std::uint64_t> timestamps_picoseconds)
    -> std::optional<ClockSequenceEvidence> {
  if (timestamps_picoseconds.size() < 2U) {
    return std::nullopt;
  }
  std::vector<std::uint64_t> deltas;
  deltas.reserve(timestamps_picoseconds.size() - 1U);
  std::size_t regressions = 0U;
  std::size_t equals = 0U;
  for (std::size_t index = 1U; index < timestamps_picoseconds.size(); ++index) {
    const auto previous = timestamps_picoseconds[index - 1U];
    const auto current = timestamps_picoseconds[index];
    if (current < previous) {
      ++regressions;
      deltas.push_back(0U);
      continue;
    }
    const auto delta = current - previous;
    equals += delta == 0U ? 1U : 0U;
    deltas.push_back(delta);
  }

  const auto p999 = inverse_ecdf(deltas, 999U, 1000U);
  const auto p99999 = inverse_ecdf(deltas, 99'999U, 100'000U);
  const auto maximum = *std::max_element(deltas.begin(), deltas.end());
  const bool sample_count = deltas.size() == kQualificationDeltaCount;
  const bool limits =
      regressions == 0U && equals <= 10U && p999 <= 1'000'000U && p99999 <= 10'000'000U;
  return ClockSequenceEvidence{deltas.size(), regressions, equals,
                               p999,          p99999,      maximum,
                               sample_count,  limits,      sample_count && limits};
}

auto evaluate_static_clock_evidence(const StaticClockEvidenceInput& input) noexcept
    -> StaticClockEvidence {
  const bool platform =
      input.bare_metal_linux_x86_64 && input.clock_monotonic_raw_supported;
  const bool source = input.current_clocksource_tsc && input.no_unstable_clock_report &&
                      input.no_clocksource_override;
  const bool frequency = input.constant_tsc && input.nonstop_tsc && input.invariant_tsc;
  const bool resolution = input.resolution_picoseconds <= 1000U;
  const bool vdso_execution =
      input.glibc_call_path_verified_vdso && input.probe_call_count == 10'000'000U &&
      input.probe_syscall_count == 0U && input.probe_failure_count == 0U;
  return {platform,
          source,
          frequency,
          input.vdso_versioned_symbol,
          vdso_execution,
          input.generated_code_passes,
          resolution,
          platform && source && frequency && input.vdso_versioned_symbol &&
              vdso_execution && input.generated_code_passes && resolution};
}

auto evaluate_per_core_qualification(const PerCoreQualificationInput& input)
    -> std::optional<PerCoreQualificationEvidence> {
  const auto sequence = evaluate_clock_sequence(input.timestamps_picoseconds);
  if (!sequence.has_value()) {
    return std::nullopt;
  }
  const bool prime = input.prime_read_count == kQualificationPrimeReadCount;
  const bool status =
      input.call_failure_count == 0U && input.invalid_timespec_count == 0U;
  const bool affinity = input.singleton_affinity && input.selected_cpu_online &&
                        input.affinity_readback_matches &&
                        input.sched_getcpu_matches_before_and_after;
  return PerCoreQualificationEvidence{*sequence, prime, status, affinity,
                                      prime && status && affinity && sequence->passes};
}

auto characterize_capture_overhead(
    std::span<const std::uint64_t> duration_samples_picoseconds)
    -> std::optional<CaptureOverheadDiagnostic> {
  if (duration_samples_picoseconds.empty()) {
    return std::nullopt;
  }
  std::vector<std::uint64_t> values(duration_samples_picoseconds.begin(),
                                    duration_samples_picoseconds.end());
  const auto minimum = *std::min_element(values.begin(), values.end());
  const auto maximum = *std::max_element(values.begin(), values.end());
  return CaptureOverheadDiagnostic{values.size(),
                                   minimum,
                                   inverse_ecdf(values, 1U, 2U),
                                   inverse_ecdf(values, 999U, 1000U),
                                   inverse_ecdf(values, 99'999U, 100'000U),
                                   maximum,
                                   false,
                                   true};
}

auto evaluate_cross_core_direction(std::span<const CrossCoreWindowInput> windows)
    -> std::optional<CrossCoreDirectionEvidence> {
  if (windows.size() != kCrossCoreWindowCount) {
    return std::nullopt;
  }
  const auto exchange_count = windows.front().exchanges.size();
  if (exchange_count == 0U ||
      std::any_of(windows.begin(), windows.end(),
                  [exchange_count](const CrossCoreWindowInput& window) {
                    return window.exchanges.size() != exchange_count;
                  })) {
    return std::nullopt;
  }

  CrossCoreDirectionEvidence evidence{};
  evidence.exchange_count_per_window = exchange_count;
  bool arithmetic_valid = true;
  for (std::size_t window_index = 0U; window_index < windows.size(); ++window_index) {
    auto lower = std::numeric_limits<std::int64_t>::min();
    auto upper = std::numeric_limits<std::int64_t>::max();
    for (const auto& exchange : windows[window_index].exchanges) {
      evidence.causal_regressions +=
          exchange.request_receive < exchange.request_send ? 1U : 0U;
      evidence.causal_regressions +=
          exchange.response_receive < exchange.response_send ? 1U : 0U;
      std::int64_t sample_lower = 0;
      std::int64_t sample_upper = 0;
      arithmetic_valid = signed_difference(exchange.response_send,
                                           exchange.response_receive, sample_lower) &&
                         signed_difference(exchange.request_receive,
                                           exchange.request_send, sample_upper) &&
                         arithmetic_valid;
      lower = std::max(lower, sample_lower);
      upper = std::min(upper, sample_upper);
    }
    const bool nonempty = arithmetic_valid && lower <= upper;
    const auto width = nonempty ? interval_width(lower, upper)
                                : std::numeric_limits<std::uint64_t>::max();
    const bool bounds = nonempty && lower >= -100'000 && upper <= 100'000;
    const bool width_pass = nonempty && width <= 200'000U;
    std::int64_t midpoint_twice = 0;
    arithmetic_valid =
        (!nonempty || checked_sum(lower, upper, midpoint_twice)) && arithmetic_valid;
    evidence.windows[window_index] = {lower,    upper,  width,     midpoint_twice,
                                      nonempty, bounds, width_pass};
  }

  evidence.accepted_policy_sample_count =
      exchange_count == kCrossCoreExchangeCountPerWindow;
  evidence.window_span_passes = windows.back().start_absolute_nanoseconds >=
                                    windows.front().start_absolute_nanoseconds &&
                                windows.back().start_absolute_nanoseconds -
                                        windows.front().start_absolute_nanoseconds >=
                                    kMinimumCrossCoreWindowStartSpanNanoseconds;
  evidence.interval_limits_pass = std::all_of(
      evidence.windows.begin(), evidence.windows.end(),
      [](const CrossCoreWindowEvidence& window) {
        return window.interval_nonempty && window.bounds_pass && window.width_pass;
      });
  const auto [minimum_midpoint, maximum_midpoint] = std::minmax_element(
      evidence.windows.begin(), evidence.windows.end(),
      [](const CrossCoreWindowEvidence& left, const CrossCoreWindowEvidence& right) {
        return left.midpoint_twice_picoseconds < right.midpoint_twice_picoseconds;
      });
  evidence.midpoint_range_twice_picoseconds =
      interval_width(minimum_midpoint->midpoint_twice_picoseconds,
                     maximum_midpoint->midpoint_twice_picoseconds);
  evidence.midpoint_drift_passes = evidence.midpoint_range_twice_picoseconds <= 100'000;
  evidence.limits_pass = arithmetic_valid && evidence.causal_regressions == 0U &&
                         evidence.window_span_passes && evidence.interval_limits_pass &&
                         evidence.midpoint_drift_passes;
  evidence.passes = evidence.accepted_policy_sample_count && evidence.limits_pass;
  return evidence;
}

auto evaluate_cross_core_pair(const CrossCorePairInput& input)
    -> std::optional<CrossCorePairEvidence> {
  const auto forward = evaluate_cross_core_direction(input.producer_to_consumer);
  const auto reverse = evaluate_cross_core_direction(input.consumer_to_producer);
  if (!forward.has_value() || !reverse.has_value()) {
    return std::nullopt;
  }
  return CrossCorePairEvidence{*forward, *reverse, forward->passes && reverse->passes};
}

} // namespace cpu_prefetch::timing
