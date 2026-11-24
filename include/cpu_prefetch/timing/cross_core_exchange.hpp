#ifndef CPU_PREFETCH_TIMING_CROSS_CORE_EXCHANGE_HPP
#define CPU_PREFETCH_TIMING_CROSS_CORE_EXCHANGE_HPP

#include "cpu_prefetch/queue/common.hpp"
#include "cpu_prefetch/timing/qualification.hpp"

#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <thread>

namespace cpu_prefetch::timing {

inline constexpr std::size_t kCrossCoreExchangeCacheLineBytes = 64U;
inline constexpr std::size_t kCrossCoreExchangeMaximumSpinIterations = 2'000'000'000U;

struct CrossCoreExchangeSpinLimit final {
  std::size_t maximum_iterations{kCrossCoreExchangeMaximumSpinIterations};
};

// Bundles CrossCoreExchangeSlot::wait_for's two timeout knobs into named
// fields rather than two positional same-width integers, so they cannot be
// silently transposed at a call site. Default-constructed, this is exactly
// the original (pre-ADR-0150-fix) spin-only behavior: the full fast spin,
// then an immediate timeout with no wall-clock fallback.
struct CrossCoreExchangeTimeoutPolicy final {
  std::size_t fast_spin_iterations = kCrossCoreExchangeMaximumSpinIterations;
  std::uint64_t max_wait_ticks = 0U;
};

// A minimal lock-free single-slot handoff for one leg of a round-trip clock
// exchange (ADR-0150): unlike a queue, only the most recently published
// (sequence, payload) pair matters, and a reader that has already consumed a
// sequence simply spins for the next one. sequence_ and the two payload
// words live on separate cache lines so publishing never invalidates a
// reader's own last-seen sequence line while it is still spinning on it.
class CrossCoreExchangeSlot final {
public:
  struct Payload final {
    std::uint64_t first;
    std::uint64_t second;
  };

  CrossCoreExchangeSlot() noexcept = default;
  CrossCoreExchangeSlot(const CrossCoreExchangeSlot&) = delete;
  auto operator=(const CrossCoreExchangeSlot&) -> CrossCoreExchangeSlot& = delete;

  void publish(std::uint64_t sequence, std::uint64_t first,
               std::uint64_t second) noexcept {
    first_.store(first, std::memory_order_relaxed);
    second_.store(second, std::memory_order_relaxed);
    sequence_.store(sequence, std::memory_order_release);
  }

  // Busy-spins until `sequence` is observed, bounded by `limit`. Never
  // issues a syscall, so it never perturbs a real, in-flight exchange's
  // measured latency. Returns std::nullopt on timeout with no further
  // fallback -- for callers with no interest in surviving an expected long
  // gap (simple positive/negative unit tests); see the NowFn overload below
  // for the one production code uses.
  [[nodiscard]] auto wait_for(std::uint64_t sequence,
                              CrossCoreExchangeSpinLimit limit = {}) const noexcept
      -> std::optional<Payload> {
    for (std::size_t spins = 0U; spins < limit.maximum_iterations; ++spins) {
      if (sequence_.load(std::memory_order_acquire) == sequence) {
        return Payload{first_.load(std::memory_order_relaxed),
                       second_.load(std::memory_order_relaxed)};
      }
    }
    return std::nullopt;
  }

  // As above (identical fast-spin phase, bounded by
  // `policy.fast_spin_iterations`, production callers pass
  // kCrossCoreExchangeMaximumSpinIterations), but if that spin is exhausted
  // and `policy.max_wait_ticks` is nonzero, falls back to a second, wall-
  // clock-bounded phase: brief real sleeps between short re-checks,
  // measured via the caller's own `now` (the same function used for the
  // exchange's timestamps), until `policy.max_wait_ticks` have elapsed
  // since the fast spin ended. `policy` defaults to a default-constructed
  // CrossCoreExchangeTimeoutPolicy{} (max_wait_ticks=0, no fallback,
  // identical to the overload above) so no existing caller's behavior
  // changes unless it explicitly opts in. The two fields are
  // bundled into one named-field struct, rather than two positional
  // same-width integers, specifically so they cannot be silently
  // transposed at a call site -- exactly the failure mode that would
  // reintroduce the bug this fallback fixes.
  //
  // This exists because a legitimate peer can be genuinely, expectedly
  // not-yet-there for real seconds at a time (ADR-0150's own window-to-
  // window pacing sleeps at accepted scale, up to ~30 real seconds between
  // window starts) -- far longer than kCrossCoreExchangeMaximumSpinIterations
  // survives in real time, which previously caused a real, silent
  // desynchronization: once one side's wait_for timed out here, both sides'
  // unconditionally-incremented local sequence counters permanently drifted
  // apart, and every subsequent exchange for the rest of that direction
  // burned its entire fast-spin budget for nothing. `now` may be a
  // synthetic/mock clock in tests; this phase's real
  // `std::this_thread::sleep_for` calls still happen for real (they cannot
  // be mocked), so tests that do not need this phase should leave `policy`
  // at its default.
  // Constrained to callable clocks. The spin-only overload takes an explicit
  // CrossCoreExchangeSpinLimit, keeping sequence and spin count distinct.
  template <typename NowFn>
    requires requires(NowFn now) { now(); }
  [[nodiscard]] auto wait_for(std::uint64_t sequence, NowFn&& now,
                              CrossCoreExchangeTimeoutPolicy policy = {}) const
      -> std::optional<Payload> {
    if (const auto fast =
            wait_for(sequence, CrossCoreExchangeSpinLimit{policy.fast_spin_iterations});
        fast.has_value()) {
      return fast;
    }
    if (policy.max_wait_ticks == 0U) {
      return std::nullopt;
    }
    const auto start = static_cast<std::uint64_t>(now());
    for (;;) {
      if (static_cast<std::uint64_t>(now()) - start >= policy.max_wait_ticks) {
        return std::nullopt;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      if (sequence_.load(std::memory_order_acquire) == sequence) {
        return Payload{first_.load(std::memory_order_relaxed),
                       second_.load(std::memory_order_relaxed)};
      }
    }
  }

  [[nodiscard]] auto atomic_lock_free_evidence() const noexcept
      -> queue::AtomicLockFreeEvidence;

private:
  alignas(kCrossCoreExchangeCacheLineBytes) std::atomic<std::uint64_t> sequence_{0U};
  alignas(kCrossCoreExchangeCacheLineBytes) std::atomic<std::uint64_t> first_{0U};
  alignas(kCrossCoreExchangeCacheLineBytes) std::atomic<std::uint64_t> second_{0U};
};

// One direction's channel: `forward` carries the initiator's request,
// `backward` carries the responder's reply. A pair of these (one per
// direction) implements ADR-0150's producer_to_consumer/consumer_to_producer
// split without sharing sequence-number state between directions.
struct CrossCoreExchangeChannel final {
  CrossCoreExchangeSlot forward;
  CrossCoreExchangeSlot backward;
};

// Initiator side of one round trip. Produces the same CrossCoreExchangeSample
// shape timing::evaluate_cross_core_direction (timing/qualification.hpp)
// already consumes. `now` is injected (rather than calling
// timing::read_monotonic_raw_absolute() directly) so this is deterministically
// unit-testable with a synthetic clock; production callers pass a real
// nanosecond-reading closure, which also becomes the deadline clock for
// `policy.max_wait_ticks` (see CrossCoreExchangeSlot::wait_for). Returns
// std::nullopt if the responder never answers within `policy`'s bound.
template <typename NowFn>
[[nodiscard]] auto
initiate_cross_core_round_trip(CrossCoreExchangeChannel& channel,
                               std::uint64_t sequence, NowFn&& now,
                               CrossCoreExchangeTimeoutPolicy policy = {})
    -> std::optional<CrossCoreExchangeSample> {
  const auto request_send = now();
  channel.forward.publish(sequence, request_send, 0U);
  const auto reply = channel.backward.wait_for(sequence, now, policy);
  if (!reply.has_value()) {
    return std::nullopt;
  }
  const auto response_receive = now();
  return CrossCoreExchangeSample{request_send, reply->first, reply->second,
                                 response_receive};
}

// Responder side of one round trip: waits for `sequence` to arrive, reads
// its own request_receive timestamp, then immediately reads its own
// response_send timestamp and publishes both back. Returns false on timeout
// (see CrossCoreExchangeSlot::wait_for for what `policy` bounds).
template <typename NowFn>
[[nodiscard]] auto
respond_to_cross_core_round_trip(CrossCoreExchangeChannel& channel,
                                 std::uint64_t sequence, NowFn&& now,
                                 CrossCoreExchangeTimeoutPolicy policy = {}) -> bool {
  const auto arrived = channel.forward.wait_for(sequence, now, policy);
  if (!arrived.has_value()) {
    return false;
  }
  const auto request_receive = now();
  const auto response_send = now();
  channel.backward.publish(sequence, request_receive, response_send);
  return true;
}

} // namespace cpu_prefetch::timing

#endif // CPU_PREFETCH_TIMING_CROSS_CORE_EXCHANGE_HPP
