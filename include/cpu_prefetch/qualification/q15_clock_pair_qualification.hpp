#ifndef CPU_PREFETCH_QUALIFICATION_Q15_CLOCK_PAIR_QUALIFICATION_HPP
#define CPU_PREFETCH_QUALIFICATION_Q15_CLOCK_PAIR_QUALIFICATION_HPP

#include "cpu_prefetch/runner/runner.hpp"
#include "cpu_prefetch/timing/qualification.hpp"

#include <cstddef>
#include <cstdint>
#include <optional>

namespace cpu_prefetch::qualification {

// ADR-0150's frozen production repeat scale, one struct so a test can
// substitute a smaller scale without touching the real constants.
struct ClockPairQualificationCounts final {
  std::size_t prime_read_count;
  std::size_t delta_count;
  std::size_t window_count;
  std::size_t exchanges_per_window;
  std::uint64_t minimum_window_start_span_nanoseconds;
};

inline constexpr ClockPairQualificationCounts kAcceptedClockPairQualificationCounts{
    timing::kQualificationPrimeReadCount, timing::kQualificationDeltaCount,
    timing::kCrossCoreWindowCount, timing::kCrossCoreExchangeCountPerWindow,
    timing::kMinimumCrossCoreWindowStartSpanNanoseconds};

struct ClockPairQualificationResult final {
  bool producer_pinned;
  bool consumer_pinned;
  std::optional<timing::PerCoreQualificationEvidence> producer_per_core;
  std::optional<timing::PerCoreQualificationEvidence> consumer_per_core;
  std::optional<timing::CrossCorePairEvidence> cross_core;
  bool complete;
  bool passes;
};

// Runs the full ADR-0150 per-core-then-cross-core clock-pairing measurement
// for one selected producer/consumer CPU pair: each side independently
// samples its own core (prime reads then a timed delta sequence, using the
// accepted timing::read_monotonic_raw_absolute() reader), then the two
// sides run `counts.window_count` windows of round-trip exchanges in each
// direction over cpu_prefetch::timing::cross_core_exchange's primitive,
// paced so each direction's own window start times span at least
// `counts.minimum_window_start_span_nanoseconds`.
//
// `counts` controls repeat scale -- production callers pass
// kAcceptedClockPairQualificationCounts; tests pass a smaller scale to keep
// runtime bounded while still exercising two real pinned OS threads and the
// real accepted clock reader on real hardware. This function performs no
// CPU-family/model check itself: the same separation of mechanism from
// gating that platform::run_q15_probe_pass already uses, so a caller that
// intends the result as real qualification evidence must gate that itself.
[[nodiscard]] auto
run_clock_pair_qualification(runner::WorkerPair pair,
                             const ClockPairQualificationCounts& counts)
    -> ClockPairQualificationResult;

} // namespace cpu_prefetch::qualification

#endif // CPU_PREFETCH_QUALIFICATION_Q15_CLOCK_PAIR_QUALIFICATION_HPP
