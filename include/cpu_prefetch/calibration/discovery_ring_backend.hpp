#ifndef CPU_PREFETCH_CALIBRATION_DISCOVERY_RING_BACKEND_HPP
#define CPU_PREFETCH_CALIBRATION_DISCOVERY_RING_BACKEND_HPP

#include "cpu_prefetch/calibration/discovery_event_capture.hpp"
#include "cpu_prefetch/calibration/discovery_observed_drain.hpp"
#include "cpu_prefetch/calibration/discovery_reconciliation.hpp"
#include "cpu_prefetch/calibration/discovery_session.hpp"

namespace cpu_prefetch::calibration {

template <typename Trace> struct DiscoveryProducerPhase final {
  DiscoveryProducerPhase(Trace& demand, storage::ProducerObservationStream& stream,
                         storage::RowLayout row_layout) noexcept
      : trace(demand), primary(stream), layout(row_layout) {}
  DiscoveryProducerPhase(const DiscoveryProducerPhase&) = delete;
  auto operator=(const DiscoveryProducerPhase&) -> DiscoveryProducerPhase& = delete;
  Trace& trace;
  storage::ProducerObservationStream& primary;
  storage::RowLayout layout;
  DiscoveryProducerEventCapture current;
  std::uint64_t attempted{0U};
  std::uint64_t accepted{0U};
  std::uint64_t full{0U};
  std::optional<storage::AppendStatus> last_append;
  bool primary_prefix_complete{true};
};

template <typename Trace> struct DiscoveryConsumerPhase final {
  DiscoveryConsumerPhase(
      Trace& demand, storage::ConsumerObservationStream& stream,
      storage::RowLayout row_layout, workload::ConsumerState initial,
      std::span<DiscoveryConsumerEventCapture> drain_storage) noexcept
      : trace(demand), primary(stream), layout(row_layout), initial_state(initial),
        state(initial), drain_rows(drain_storage) {}
  DiscoveryConsumerPhase(const DiscoveryConsumerPhase&) = delete;
  auto operator=(const DiscoveryConsumerPhase&) -> DiscoveryConsumerPhase& = delete;
  Trace& trace;
  storage::ConsumerObservationStream& primary;
  storage::RowLayout layout;
  workload::ConsumerState initial_state;
  workload::ConsumerState state;
  DiscoveryConsumerEventCapture current;
  std::span<DiscoveryConsumerEventCapture> drain_rows;
  std::size_t drain_requests{0U};
  std::uint64_t consumed{0U};
  std::optional<storage::AppendStatus> last_append;
  DiscoveryJoinResult last_join{DiscoveryJoinStatus::not_evaluated};
  bool primary_prefix_complete{true};
  bool capture_horizon_complete{false};
  bool drain_retention_exhausted{false};
};

// Preparation constructs all storage on its actual owners, bounds/cancels its
// readiness handshake, and establishes the real mapping/affinity facts. It
// exposes immutable arena/ring identity and two persistent owner phase states.
// This composition itself performs no admission or hardware qualification.
template <typename Clock, typename Preparation> class DiscoveryRingPhaseBackend final {
public:
  DiscoveryRingPhaseBackend(DiscoverySessionPlan plan, Clock& clock,
                            Preparation& preparation) noexcept
      : plan_(plan), clock_(clock), preparation_(preparation) {}

  [[nodiscard]] auto prepare_producer() -> bool {
    if (!preparation_.prepare_producer()) {
      return false;
    }
    auto& warmup = preparation_.producer_phase(true);
    auto& measurement = preparation_.producer_phase(false);
    if (warmup.primary.snapshot().run_id == measurement.primary.snapshot().run_id) {
      return false;
    }
    return prepare_producer_phase(warmup, plan_.warmup_attempt_capacity) &&
           prepare_producer_phase(measurement, plan_.measurement_attempt_capacity);
  }
  [[nodiscard]] auto prepare_consumer() -> bool {
    if (!preparation_.prepare_consumer()) {
      return false;
    }
    auto& warmup = preparation_.consumer_phase(true);
    auto& measurement = preparation_.consumer_phase(false);
    if (warmup.primary.snapshot().run_id == measurement.primary.snapshot().run_id ||
        warmup.initial_state != measurement.initial_state) {
      return false;
    }
    return prepare_consumer_phase(warmup, plan_.warmup_attempt_capacity) &&
           prepare_consumer_phase(measurement, plan_.measurement_attempt_capacity);
  }
  [[nodiscard]] auto warmup_producer_attempt(std::uint64_t arrival) noexcept
      -> RingCaptureResult {
    return produce(preparation_.producer_phase(true), arrival);
  }
  [[nodiscard]] auto measurement_producer_attempt(std::uint64_t arrival) noexcept
      -> RingCaptureResult {
    return produce(preparation_.producer_phase(false), arrival);
  }
  [[nodiscard]] auto warmup_consumer_attempt() noexcept -> RingCaptureResult {
    auto& phase = preparation_.consumer_phase(true);
    return consume(phase, phase.trace, phase.current);
  }
  [[nodiscard]] auto measurement_consumer_attempt() noexcept -> RingCaptureResult {
    auto& phase = preparation_.consumer_phase(false);
    return consume(phase, phase.trace, phase.current);
  }
  [[nodiscard]] auto ring() noexcept -> queue::RingSpscQueue& {
    return preparation_.ring();
  }
  [[nodiscard]] auto
  validate_warmup(const std::array<DiscoveryWorkerResult, 2U>& workers) noexcept
      -> bool {
    return validate_capture(true, workers);
  }
  [[nodiscard]] auto
  validate_measurement(const std::array<DiscoveryWorkerResult, 2U>& workers) noexcept
      -> bool {
    return validate_capture(false, workers);
  }
  [[nodiscard]] auto drain_warmup(DiscoveryDrainWindow window) noexcept
      -> DiscoveryDrainResult {
    return drain(true, window);
  }
  [[nodiscard]] auto drain_measurement(DiscoveryDrainWindow window) noexcept
      -> DiscoveryDrainResult {
    return drain(false, window);
  }
  [[nodiscard]] auto reset_producer() noexcept -> bool {
    const auto& state = preparation_.producer_phase(false);
    const auto sample = state.trace.worker_series(RingWorker::producer);
    const bool ready = state.attempted == 0U && state.accepted == 0U &&
                       state.full == 0U && state.primary_prefix_complete &&
                       state.primary.snapshot().row_count == 0U &&
                       state.trace.worker_prepared(RingWorker::producer) &&
                       sample.demand_ticks.empty() && sample.issue_ticks.empty();
    if constexpr (requires { preparation_.before_measurement_producer(); }) {
      static_assert(noexcept(preparation_.before_measurement_producer()));
      return ready && preparation_.before_measurement_producer();
    }
    return ready;
  }
  [[nodiscard]] auto reset_consumer() noexcept -> bool {
    const auto& state = preparation_.consumer_phase(false);
    const auto sample = state.trace.worker_series(RingWorker::consumer);
    const bool ready = state.consumed == 0U && state.state == state.initial_state &&
                       state.primary_prefix_complete && state.drain_requests == 0U &&
                       state.primary.snapshot().row_count == 0U &&
                       state.trace.worker_prepared(RingWorker::consumer) &&
                       sample.demand_ticks.empty() && sample.issue_ticks.empty();
    if constexpr (requires { preparation_.before_measurement_consumer(); }) {
      static_assert(noexcept(preparation_.before_measurement_consumer()));
      return ready && preparation_.before_measurement_consumer();
    }
    return ready;
  }

private:
  [[nodiscard]] static auto empty_primary(const storage::RawStreamSnapshot& snapshot,
                                          const storage::RowLayout& layout,
                                          protocol::StreamKind kind,
                                          std::uint64_t capacity) noexcept -> bool {
    return snapshot.row_count == 0U && snapshot.row_capacity == capacity &&
           snapshot.completeness == storage::StreamCompleteness::writing &&
           !snapshot.overflowed &&
           storage::prepared_primary_stream_shape(snapshot, layout, kind);
  }
  [[nodiscard]] static auto prepare_producer_phase(auto& phase,
                                                   std::uint64_t capacity) noexcept
      -> bool {
    return phase.attempted == 0U && phase.accepted == 0U && phase.full == 0U &&
           phase.primary_prefix_complete &&
           phase.trace.attempt_capacity() == capacity &&
           empty_primary(phase.primary.snapshot(), phase.layout,
                         protocol::StreamKind::producer, capacity) &&
           phase.trace.prepare_worker(RingWorker::producer) &&
           phase.primary.prepare_for_owner();
  }
  [[nodiscard]] auto prepare_consumer_phase(auto& phase,
                                            std::uint64_t capacity) noexcept -> bool {
    return phase.consumed == 0U && phase.state == phase.initial_state &&
           phase.primary_prefix_complete && phase.drain_requests == 0U &&
           phase.drain_rows.size() >= plan_.drain_attempt_capacity &&
           phase.trace.attempt_capacity() == capacity &&
           empty_primary(phase.primary.snapshot(), phase.layout,
                         protocol::StreamKind::consumer, capacity) &&
           phase.trace.prepare_worker(RingWorker::consumer) &&
           phase.primary.prepare_for_owner();
  }
  [[nodiscard]] auto produce(auto& phase, std::uint64_t arrival) noexcept
      -> RingCaptureResult {
    auto captured = capture_discovery_producer_event(
        clock_, preparation_.arena(), preparation_.ring(), phase.trace,
        {phase.attempted}, arrival, {phase.accepted}, phase.current);
    if (captured.operation_performed) {
      ++phase.attempted;
      if (captured.operation_outcome == RingAttemptOutcome::advanced) {
        ++phase.accepted;
      } else if (captured.operation_outcome == RingAttemptOutcome::full) {
        ++phase.full;
      }
      if (phase.current.primary.has_value() && phase.primary_prefix_complete) {
        phase.last_append = phase.primary.append(*phase.current.primary);
        if (phase.last_append != storage::AppendStatus::appended) {
          phase.primary_prefix_complete = false;
          captured.outcome = RingAttemptOutcome::trace_failure;
        }
      } else {
        phase.primary_prefix_complete = false;
      }
    }
    phase.current.capture = captured;
    return captured;
  }
  [[nodiscard]] auto consume(auto& phase, auto& trace,
                             DiscoveryConsumerEventCapture& row) noexcept
      -> RingCaptureResult {
    auto captured = capture_discovery_consumer_event(
        clock_, preparation_.arena(), preparation_.ring(), trace, phase.state,
        {phase.consumed}, row);
    if (captured.operation_performed &&
        captured.operation_outcome == RingAttemptOutcome::advanced) {
      ++phase.consumed;
      if (row.primary.has_value() && phase.primary_prefix_complete) {
        phase.last_append = phase.primary.append(*row.primary);
        if (phase.last_append != storage::AppendStatus::appended) {
          phase.primary_prefix_complete = false;
          captured.outcome = RingAttemptOutcome::trace_failure;
        }
      } else {
        phase.primary_prefix_complete = false;
      }
    }
    row.capture = captured;
    return captured;
  }
  [[nodiscard]] auto join(bool warmup, bool require_drained) noexcept -> bool {
    const auto& producer = preparation_.producer_phase(warmup);
    auto& consumer = preparation_.consumer_phase(warmup);
    consumer.last_join = reconcile_discovery_primary(
        preparation_.arena(), producer.primary.snapshot(), producer.layout,
        consumer.primary.snapshot(), consumer.layout,
        {producer.attempted, producer.accepted, producer.full, consumer.consumed},
        {.initial = consumer.initial_state, .observed = consumer.state},
        require_drained);
    return producer.primary_prefix_complete && consumer.primary_prefix_complete &&
           consumer.last_join.status == DiscoveryJoinStatus::exact;
  }
  [[nodiscard]] auto
  validate_capture(bool warmup,
                   const std::array<DiscoveryWorkerResult, 2U>& workers) noexcept
      -> bool {
    const auto& producer = preparation_.producer_phase(warmup);
    auto& consumer = preparation_.consumer_phase(warmup);
    consumer.capture_horizon_complete =
        workers[0U].stop == DiscoveryWorkerStop::fixed_deadline &&
        workers[1U].stop == DiscoveryWorkerStop::fixed_deadline;
    if (producer.attempted != workers[0U].attempts ||
        producer.accepted != workers[0U].advanced ||
        producer.full != workers[0U].full ||
        consumer.consumed != workers[1U].advanced) {
      return false;
    }
    const auto checked_producer = validate_quiescent_discovery_trace(
        RingWorker::producer, workers[0U], producer.trace);
    const auto checked_consumer = validate_quiescent_discovery_trace(
        RingWorker::consumer, workers[1U], consumer.trace);
    const auto usable = [](DiscoveryWorkerStop stop) noexcept {
      return stop == DiscoveryWorkerStop::fixed_deadline ||
             stop == DiscoveryWorkerStop::trace_capacity ||
             stop == DiscoveryWorkerStop::peer_stopped;
    };
    return usable(checked_producer.stop) && usable(checked_consumer.stop) &&
           join(warmup, false);
  }
  [[nodiscard]] auto drain(bool warmup, DiscoveryDrainWindow window) noexcept
      -> DiscoveryDrainResult {
    auto& producer = preparation_.producer_phase(warmup);
    auto& consumer = preparation_.consumer_phase(warmup);
    struct DrainClockCheck final {
      auto record(RingWorker, std::uint64_t start, std::uint64_t end,
                  RingAttemptOutcome) const noexcept -> bool {
        return end >= start;
      }
    } trace;
    auto poll = [&]() noexcept -> DiscoveryObservedDrainPoll {
      if (consumer.drain_requests >= consumer.drain_rows.size()) {
        consumer.drain_retention_exhausted = true;
        return {{RingAttemptOutcome::trace_failure, std::nullopt, std::nullopt,
                 std::nullopt, false},
                std::nullopt};
      }
      auto& row = consumer.drain_rows[consumer.drain_requests++];
      const auto captured = consume(consumer, trace, row);
      return {captured, row.operation};
    };
    auto finish = [&]() noexcept {
      const bool exact = join(warmup, true);
      if (exact && consumer.capture_horizon_complete) {
        return producer.primary.seal_complete() && consumer.primary.seal_complete();
      }
      producer.primary.seal_incomplete();
      consumer.primary.seal_incomplete();
      return exact;
    };
    auto result = drain_discovery_ring_observed(window, clock_, preparation_.ring(),
                                                poll, finish);
    if (result.stop != DiscoveryDrainStop::complete) {
      producer.primary.seal_incomplete();
      consumer.primary.seal_incomplete();
    }
    return result;
  }
  DiscoverySessionPlan plan_;
  Clock& clock_;
  Preparation& preparation_;
};

} // namespace cpu_prefetch::calibration

#endif
