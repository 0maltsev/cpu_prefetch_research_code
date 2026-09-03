#ifndef CPU_PREFETCH_TIMING_CROSS_CORE_EXCHANGE_HPP
#define CPU_PREFETCH_TIMING_CROSS_CORE_EXCHANGE_HPP

#include "cpu_prefetch/queue/common.hpp"
#include "cpu_prefetch/timing/qualification.hpp"

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <optional>

namespace cpu_prefetch::timing {

inline constexpr std::size_t kCrossCoreExchangeCacheLineBytes = 64U;
inline constexpr std::size_t kCrossCoreExchangeMaximumSpinIterations = 2'000'000'000U;

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

  // Busy-spins until `sequence` is observed, bounded by `max_spins`
  // (production callers pass kCrossCoreExchangeMaximumSpinIterations; tests
  // pass a small bound to exercise the timeout path in bounded time);
  // returns std::nullopt on timeout rather than blocking forever on a
  // wedged peer. Never issues a syscall itself, so it never perturbs the
  // exchange it is timing.
  [[nodiscard]] auto wait_for(
      std::uint64_t sequence,
      std::size_t max_spins = kCrossCoreExchangeMaximumSpinIterations) const noexcept
      -> std::optional<Payload> {
    for (std::size_t spins = 0U; spins < max_spins; ++spins) {
      if (sequence_.load(std::memory_order_acquire) == sequence) {
        return Payload{first_.load(std::memory_order_relaxed),
                       second_.load(std::memory_order_relaxed)};
      }
    }
    return std::nullopt;
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
// nanosecond-reading closure. Returns std::nullopt if the responder never
// answers within the bounded spin.
template <typename NowFn>
[[nodiscard]] auto initiate_cross_core_round_trip(
    CrossCoreExchangeChannel& channel, std::uint64_t sequence, NowFn&& now,
    std::size_t max_spins = kCrossCoreExchangeMaximumSpinIterations)
    -> std::optional<CrossCoreExchangeSample> {
  const auto request_send = now();
  channel.forward.publish(sequence, request_send, 0U);
  const auto reply = channel.backward.wait_for(sequence, max_spins);
  if (!reply.has_value()) {
    return std::nullopt;
  }
  const auto response_receive = now();
  return CrossCoreExchangeSample{request_send, reply->first, reply->second,
                                 response_receive};
}

// Responder side of one round trip: waits for `sequence` to arrive, reads
// its own request_receive timestamp, then immediately reads its own
// response_send timestamp and publishes both back. Returns false on timeout.
template <typename NowFn>
[[nodiscard]] auto respond_to_cross_core_round_trip(
    CrossCoreExchangeChannel& channel, std::uint64_t sequence, NowFn&& now,
    std::size_t max_spins = kCrossCoreExchangeMaximumSpinIterations) -> bool {
  const auto arrived = channel.forward.wait_for(sequence, max_spins);
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
