#include "cpu_prefetch/qualification/q15_clock_pair_qualification.hpp"

#include "cpu_prefetch/platform/q15_runtime.hpp"
#include "cpu_prefetch/timing/clock.hpp"
#include "cpu_prefetch/timing/cross_core_exchange.hpp"

#include <chrono>
#include <thread>
#include <vector>

namespace cpu_prefetch::qualification {
namespace {

struct PerCoreCapture final {
  bool pinned;
  std::optional<timing::PerCoreQualificationEvidence> evidence;
};

[[nodiscard]] auto capture_per_core(std::uint32_t cpu,
                                    const ClockPairQualificationCounts& counts)
    -> PerCoreCapture {
  platform::LinuxQ15PlatformOperations operations;
  const auto bound = operations.bind_current_thread(cpu);
  if (!bound.succeeded) {
    return {false, std::nullopt};
  }
  const auto affinity_before = operations.singleton_affinity_matches(cpu);
  const auto cpu_before = operations.current_cpu();
  if (!affinity_before || !affinity_before.value() || !cpu_before ||
      cpu_before.value() != cpu) {
    return {true, std::nullopt};
  }

  std::size_t call_failures = 0U;
  std::size_t invalid_timespecs = 0U;
  for (std::size_t index = 0U; index < counts.prime_read_count; ++index) {
    if (timing::read_monotonic_raw_absolute().status != timing::ClockReadStatus::ok) {
      ++call_failures;
    }
  }

  const auto origin = timing::MonotonicRawClock::capture_origin();
  if (origin.status != timing::ClockReadStatus::ok) {
    return {true, std::nullopt};
  }
  timing::MonotonicRawClock clock({origin.absolute_nanoseconds});
  std::vector<std::uint64_t> timestamps;
  timestamps.reserve(counts.delta_count + 1U);
  for (std::size_t index = 0U; index <= counts.delta_count; ++index) {
    const auto reading = clock.read();
    switch (reading.status) {
    case timing::ClockReadStatus::ok:
      timestamps.push_back(reading.sample.relative_picoseconds);
      break;
    case timing::ClockReadStatus::call_failed:
      ++call_failures;
      timestamps.push_back(timestamps.empty() ? 0U : timestamps.back());
      break;
    default:
      ++invalid_timespecs;
      timestamps.push_back(timestamps.empty() ? 0U : timestamps.back());
      break;
    }
  }

  const auto affinity_after = operations.singleton_affinity_matches(cpu);
  const auto cpu_after = operations.current_cpu();
  const bool affinity_held =
      affinity_after && affinity_after.value() && cpu_after && cpu_after.value() == cpu;

  const timing::PerCoreQualificationInput input{
      timestamps,        counts.prime_read_count, call_failures,
      invalid_timespecs, affinity_held,           true,
      affinity_held,     affinity_held,
  };
  return {true, timing::evaluate_per_core_qualification(input)};
}

[[nodiscard]] auto now_absolute_nanoseconds() -> std::uint64_t {
  const auto reading = timing::read_monotonic_raw_absolute();
  return reading.status == timing::ClockReadStatus::ok ? reading.absolute_nanoseconds
                                                       : 0U;
}

// Owns one direction's captured windows. CrossCoreWindowInput itself only
// spans this storage, so callers must keep a DirectionCapture alive for as
// long as any CrossCoreWindowInput built from it is used.
struct DirectionCapture final {
  std::vector<std::uint64_t> starts;
  std::vector<std::vector<timing::CrossCoreExchangeSample>> exchanges;

  [[nodiscard]] auto windows() const -> std::vector<timing::CrossCoreWindowInput> {
    std::vector<timing::CrossCoreWindowInput> result;
    result.reserve(starts.size());
    for (std::size_t window = 0U; window < starts.size(); ++window) {
      result.push_back(timing::CrossCoreWindowInput{starts[window], exchanges[window]});
    }
    return result;
  }
};

// One direction's windows: the initiator side of `channel`, paired with a
// concurrent run_direction_responder call on the other thread, coordinated
// only via the channel's atomics.
[[nodiscard]] auto run_direction_initiator(timing::CrossCoreExchangeChannel& channel,
                                           const ClockPairQualificationCounts& counts)
    -> DirectionCapture {
  DirectionCapture capture{
      std::vector<std::uint64_t>(counts.window_count),
      std::vector<std::vector<timing::CrossCoreExchangeSample>>(counts.window_count)};
  const auto phase_start = now_absolute_nanoseconds();
  const auto spacing =
      counts.window_count > 1U
          ? counts.minimum_window_start_span_nanoseconds / (counts.window_count - 1U)
          : 0U;
  std::uint64_t sequence = 0U;
  for (std::size_t window = 0U; window < counts.window_count; ++window) {
    const auto target = phase_start + static_cast<std::uint64_t>(window) * spacing;
    while (now_absolute_nanoseconds() < target) {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    capture.starts[window] = now_absolute_nanoseconds();
    capture.exchanges[window].reserve(counts.exchanges_per_window);
    for (std::size_t index = 0U; index < counts.exchanges_per_window; ++index) {
      ++sequence;
      // max_wait_ticks = the real span this same counts value paces windows
      // over: the initiator itself can legitimately be asleep, mid-pacing,
      // for close to that long between window starts, and the responder
      // side (below) must survive waiting through exactly that real gap
      // without desynchronizing -- see CrossCoreExchangeSlot::wait_for.
      const auto sample = timing::initiate_cross_core_round_trip(
          channel, sequence, now_absolute_nanoseconds,
          timing::CrossCoreExchangeTimeoutPolicy{
              timing::kCrossCoreExchangeMaximumSpinIterations,
              counts.minimum_window_start_span_nanoseconds});
      capture.exchanges[window].push_back(
          sample.value_or(timing::CrossCoreExchangeSample{0U, 0U, 0U, 0U}));
    }
  }
  return capture;
}

void run_direction_responder(timing::CrossCoreExchangeChannel& channel,
                             const ClockPairQualificationCounts& counts) {
  const auto total = counts.window_count * counts.exchanges_per_window;
  for (std::uint64_t sequence = 1U; sequence <= total; ++sequence) {
    // See the matching comment in run_direction_initiator: this side has no
    // pacing schedule of its own, so it must be able to wait out the
    // initiator's real inter-window sleeps too.
    static_cast<void>(timing::respond_to_cross_core_round_trip(
        channel, sequence, now_absolute_nanoseconds,
        timing::CrossCoreExchangeTimeoutPolicy{
            timing::kCrossCoreExchangeMaximumSpinIterations,
            counts.minimum_window_start_span_nanoseconds}));
  }
}

} // namespace

auto run_clock_pair_qualification(runner::WorkerPair pair,
                                  const ClockPairQualificationCounts& counts)
    -> ClockPairQualificationResult {
  ClockPairQualificationResult result{};

  std::optional<PerCoreCapture> producer_capture;
  std::optional<PerCoreCapture> consumer_capture;
  std::atomic<bool> per_core_start{false};
  std::thread producer_per_core([&] {
    while (!per_core_start.load(std::memory_order_acquire)) {
      std::this_thread::yield();
    }
    producer_capture = capture_per_core(pair.producer_cpu, counts);
  });
  std::thread consumer_per_core([&] {
    while (!per_core_start.load(std::memory_order_acquire)) {
      std::this_thread::yield();
    }
    consumer_capture = capture_per_core(pair.consumer_cpu, counts);
  });
  per_core_start.store(true, std::memory_order_release);
  producer_per_core.join();
  consumer_per_core.join();

  result.producer_pinned = producer_capture.has_value() && producer_capture->pinned;
  result.consumer_pinned = consumer_capture.has_value() && consumer_capture->pinned;
  result.producer_per_core =
      producer_capture.has_value() ? producer_capture->evidence : std::nullopt;
  result.consumer_per_core =
      consumer_capture.has_value() ? consumer_capture->evidence : std::nullopt;
  if (!result.producer_pinned || !result.consumer_pinned) {
    result.complete = false;
    result.passes = false;
    return result;
  }

  timing::CrossCoreExchangeChannel producer_to_consumer_channel;
  timing::CrossCoreExchangeChannel consumer_to_producer_channel;
  std::optional<DirectionCapture> producer_to_consumer_capture;
  std::optional<DirectionCapture> consumer_to_producer_capture;
  std::atomic<bool> cross_core_start{false};

  std::thread producer_side([&] {
    while (!cross_core_start.load(std::memory_order_acquire)) {
      std::this_thread::yield();
    }
    platform::LinuxQ15PlatformOperations operations;
    if (!operations.bind_current_thread(pair.producer_cpu).succeeded) {
      return;
    }
    producer_to_consumer_capture =
        run_direction_initiator(producer_to_consumer_channel, counts);
    run_direction_responder(consumer_to_producer_channel, counts);
  });
  std::thread consumer_side([&] {
    while (!cross_core_start.load(std::memory_order_acquire)) {
      std::this_thread::yield();
    }
    platform::LinuxQ15PlatformOperations operations;
    if (!operations.bind_current_thread(pair.consumer_cpu).succeeded) {
      return;
    }
    run_direction_responder(producer_to_consumer_channel, counts);
    consumer_to_producer_capture =
        run_direction_initiator(consumer_to_producer_channel, counts);
  });
  cross_core_start.store(true, std::memory_order_release);
  producer_side.join();
  consumer_side.join();

  if (!producer_to_consumer_capture.has_value() ||
      !consumer_to_producer_capture.has_value()) {
    result.complete = false;
    result.passes = false;
    return result;
  }
  const auto producer_to_consumer_windows = producer_to_consumer_capture->windows();
  const auto consumer_to_producer_windows = consumer_to_producer_capture->windows();
  const timing::CrossCorePairInput cross_core_input{producer_to_consumer_windows,
                                                    consumer_to_producer_windows};
  result.cross_core = timing::evaluate_cross_core_pair(cross_core_input);
  result.complete = result.producer_per_core.has_value() &&
                    result.consumer_per_core.has_value() &&
                    result.cross_core.has_value();
  result.passes = result.complete && result.producer_per_core->passes &&
                  result.consumer_per_core->passes && result.cross_core->passes;
  return result;
}

} // namespace cpu_prefetch::qualification
