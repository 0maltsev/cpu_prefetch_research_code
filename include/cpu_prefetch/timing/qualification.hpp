#ifndef CPU_PREFETCH_TIMING_QUALIFICATION_HPP
#define CPU_PREFETCH_TIMING_QUALIFICATION_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <vector>

namespace cpu_prefetch::timing {

inline constexpr std::size_t kQualificationPrimeReadCount = 100'000U;
inline constexpr std::size_t kQualificationDeltaCount = 10'000'000U;
inline constexpr std::size_t kCrossCoreExchangeCountPerWindow = 100'000U;
inline constexpr std::size_t kCrossCoreWindowCount = 3U;
inline constexpr std::uint64_t kMinimumCrossCoreWindowStartSpanNanoseconds =
    60'000'000'000U;

struct ClockSequenceEvidence final {
  std::size_t delta_count;
  std::size_t regression_count;
  std::size_t equal_count;
  std::uint64_t p999_delta_picoseconds;
  std::uint64_t p99999_delta_picoseconds;
  std::uint64_t maximum_delta_picoseconds;
  bool accepted_policy_sample_count;
  bool limits_pass;
  bool passes;
};

[[nodiscard]] auto
evaluate_clock_sequence(std::span<const std::uint64_t> timestamps_picoseconds)
    -> std::optional<ClockSequenceEvidence>;

struct StaticClockEvidenceInput final {
  bool bare_metal_linux_x86_64;
  bool clock_monotonic_raw_supported;
  bool current_clocksource_tsc;
  bool no_unstable_clock_report;
  bool constant_tsc;
  bool nonstop_tsc;
  bool invariant_tsc;
  bool vdso_versioned_symbol;
  bool glibc_call_path_verified_vdso;
  std::uint64_t probe_call_count;
  std::uint64_t probe_syscall_count;
  std::uint64_t probe_failure_count;
  bool no_clocksource_override;
  bool generated_code_passes;
  std::uint64_t resolution_picoseconds;
};

struct StaticClockEvidence final {
  bool platform_passes;
  bool source_passes;
  bool frequency_invariance_passes;
  bool vdso_symbol_passes;
  bool vdso_execution_passes;
  bool generated_code_passes;
  bool resolution_passes;
  bool passes;
};

[[nodiscard]] auto
evaluate_static_clock_evidence(const StaticClockEvidenceInput& input) noexcept
    -> StaticClockEvidence;

struct PerCoreQualificationInput final {
  std::span<const std::uint64_t> timestamps_picoseconds;
  std::size_t prime_read_count;
  std::size_t call_failure_count;
  std::size_t invalid_timespec_count;
  bool singleton_affinity;
  bool selected_cpu_online;
  bool affinity_readback_matches;
  bool sched_getcpu_matches_before_and_after;
};

struct PerCoreQualificationEvidence final {
  ClockSequenceEvidence sequence;
  bool prime_count_passes;
  bool read_status_passes;
  bool affinity_passes;
  bool passes;
};

[[nodiscard]] auto
evaluate_per_core_qualification(const PerCoreQualificationInput& input)
    -> std::optional<PerCoreQualificationEvidence>;

struct CaptureOverheadDiagnostic final {
  std::size_t sample_count;
  std::uint64_t minimum_picoseconds;
  std::uint64_t median_picoseconds;
  std::uint64_t p999_picoseconds;
  std::uint64_t p99999_picoseconds;
  std::uint64_t maximum_picoseconds;
  bool correction_applied;
  bool primary_timestamps_unchanged;
};

[[nodiscard]] auto characterize_capture_overhead(
    std::span<const std::uint64_t> duration_samples_picoseconds)
    -> std::optional<CaptureOverheadDiagnostic>;

struct CrossCoreExchangeSample final {
  std::uint64_t request_send;
  std::uint64_t request_receive;
  std::uint64_t response_send;
  std::uint64_t response_receive;
};

struct CrossCoreWindowInput final {
  std::uint64_t start_absolute_nanoseconds;
  std::span<const CrossCoreExchangeSample> exchanges;
};

struct CrossCoreWindowEvidence final {
  std::int64_t lower_picoseconds;
  std::int64_t upper_picoseconds;
  std::uint64_t width_picoseconds;
  std::int64_t midpoint_twice_picoseconds;
  bool interval_nonempty;
  bool bounds_pass;
  bool width_pass;
};

struct CrossCoreDirectionEvidence final {
  std::array<CrossCoreWindowEvidence, kCrossCoreWindowCount> windows;
  std::size_t exchange_count_per_window;
  std::size_t causal_regressions;
  std::uint64_t midpoint_range_twice_picoseconds;
  bool accepted_policy_sample_count;
  bool window_span_passes;
  bool interval_limits_pass;
  bool midpoint_drift_passes;
  bool limits_pass;
  bool passes;
};

[[nodiscard]] auto
evaluate_cross_core_direction(std::span<const CrossCoreWindowInput> windows)
    -> std::optional<CrossCoreDirectionEvidence>;

struct CrossCorePairEvidence final {
  CrossCoreDirectionEvidence producer_to_consumer;
  CrossCoreDirectionEvidence consumer_to_producer;
  bool passes;
};

struct CrossCorePairInput final {
  std::span<const CrossCoreWindowInput> producer_to_consumer;
  std::span<const CrossCoreWindowInput> consumer_to_producer;
};

[[nodiscard]] auto evaluate_cross_core_pair(const CrossCorePairInput& input)
    -> std::optional<CrossCorePairEvidence>;

} // namespace cpu_prefetch::timing

#endif // CPU_PREFETCH_TIMING_QUALIFICATION_HPP
