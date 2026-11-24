#ifndef CPU_PREFETCH_CALIBRATION_FORMAL_RING_SESSION_HPP
#define CPU_PREFETCH_CALIBRATION_FORMAL_RING_SESSION_HPP

#include "cpu_prefetch/calibration/discovery_event_capture.hpp"
#include "cpu_prefetch/calibration/discovery_reconciliation.hpp"
#include "cpu_prefetch/calibration/ring_demand_window.hpp"
#include "cpu_prefetch/calibration/service_session.hpp"

namespace cpu_prefetch::calibration {

struct FormalRingProducerPhase final {
  RingDemandStream& demand;
  storage::ProducerObservationStream& primary;
  storage::RowLayout layout;
  DiscoveryProducerEventCapture current;
  std::uint64_t requests{0U};
  std::uint64_t attempted{0U};
  std::uint64_t accepted{0U};
  std::uint64_t full{0U};
  std::optional<storage::AppendStatus> last_demand_append{};
  std::optional<storage::AppendStatus> last_primary_append{};
  bool primary_prefix_complete{true};
  bool stopped{false};
};

struct FormalRingConsumerPhase final {
  RingDemandStream& demand;
  storage::ConsumerObservationStream& primary;
  storage::RowLayout layout;
  workload::ConsumerState initial_state;
  workload::ConsumerState state;
  DiscoveryConsumerEventCapture current;
  std::uint64_t polls{0U};
  std::uint64_t consumed{0U};
  std::uint64_t empty{0U};
  std::optional<storage::AppendStatus> last_demand_append{};
  std::optional<storage::AppendStatus> last_primary_append{};
  DiscoveryJoinResult last_join{DiscoveryJoinStatus::not_evaluated};
  bool primary_prefix_complete{true};
  bool stopped{false};
};

// Preparation owns two persistent phase states, arena and R0 ring. Its owner
// methods construct/prepare the actual storage; before_measurement_* performs
// only owner-private reset/readback. Same arena/order, workers and maps survive.
// Raw demand has no hot window selection: every performed acquire, including
// FULL/empty and drain, is retained. A failed call leaves its complete current
// capture untouched until publication. No demand row is invented for a call
// that failed before its acquire. Failed clock samples are retained verbatim.
// The caller publishes only after join and keeps every referenced object live.
template <typename Clock, typename Preparation> class FormalRingSessionBackend final {
public:
  FormalRingSessionBackend(const ServiceSessionPlan& plan, Clock& clock,
                           Preparation& preparation) noexcept
      : plan_(plan), clock_(clock), preparation_(preparation),
        phases_{{Phase{*this, true}, Phase{*this, false}}} {}

  class Phase final {
  public:
    Phase(FormalRingSessionBackend& owner, bool warmup) noexcept
        : owner_(owner), warmup_(warmup) {}
    auto try_producer_attempt(lifecycle::ProducerAttempt attempt) noexcept
        -> lifecycle::ProducerAttemptResult {
      return owner_.produce(owner_.preparation_.producer_phase(warmup_), attempt);
    }
    auto try_consumer_poll(std::uint64_t ordinal) noexcept
        -> lifecycle::ConsumerPollResult {
      return owner_.consume(owner_.preparation_.consumer_phase(warmup_), ordinal);
    }

  private:
    FormalRingSessionBackend& owner_;
    bool warmup_;
  };

  auto plan() const noexcept -> const ServiceSessionPlan& { return plan_; }
  auto clock() noexcept -> Clock& { return clock_; }
  auto phase(ServicePhase selected) noexcept -> Phase& {
    return phases_[selected == ServicePhase::warmup ? 0U : 1U];
  }
  auto prepare_producer() -> bool {
    if (!valid_service_plan(plan_) || !preparation_.prepare_producer()) {
      return false;
    }
    available_[0U] = true;
    auto& warmup = preparation_.producer_phase(true);
    auto& measurement = preparation_.producer_phase(false);
    if (&warmup == &measurement || &warmup.demand == &measurement.demand ||
        &warmup.primary == &measurement.primary ||
        warmup.primary.snapshot().run_id == measurement.primary.snapshot().run_id) {
      return false;
    }
    for (std::size_t index = 0U; index < 2U; ++index) {
      auto& row = preparation_.producer_phase(index == 0U);
      if (row.requests != 0U || row.attempted != 0U || row.accepted != 0U ||
          row.full != 0U || !row.primary_prefix_complete ||
          !empty_streams(row, RingWorker::producer,
                         plan_.phases[index].producer_attempt_limit) ||
          !row.demand.prepare_for_owner() || !row.primary.prepare_for_owner()) {
        return false;
      }
    }
    return true;
  }
  auto prepare_consumer() -> bool {
    if (!valid_service_plan(plan_) || !preparation_.prepare_consumer()) {
      return false;
    }
    available_[1U] = true;
    auto& warmup = preparation_.consumer_phase(true);
    auto& measurement = preparation_.consumer_phase(false);
    if (&warmup == &measurement || &warmup.demand == &measurement.demand ||
        &warmup.primary == &measurement.primary ||
        warmup.primary.snapshot().run_id == measurement.primary.snapshot().run_id ||
        warmup.initial_state != measurement.initial_state) {
      return false;
    }
    for (std::size_t index = 0U; index < 2U; ++index) {
      auto& row = preparation_.consumer_phase(index == 0U);
      if (row.polls != 0U || row.consumed != 0U || row.empty != 0U ||
          row.state != row.initial_state || !row.primary_prefix_complete ||
          !empty_streams(row, RingWorker::consumer,
                         plan_.phases[index].consumer_poll_limit) ||
          row.primary.snapshot().row_capacity <
              plan_.phases[index].producer_attempt_limit ||
          !row.demand.prepare_for_owner() || !row.primary.prepare_for_owner()) {
        return false;
      }
    }
    return true;
  }
  auto reset_producer() noexcept -> bool {
    const auto& row = preparation_.producer_phase(false);
    return row.requests == 0U && row.attempted == 0U && row.accepted == 0U &&
           row.full == 0U && row.primary_prefix_complete &&
           row.demand.snapshot().row_count == 0U &&
           row.primary.snapshot().row_count == 0U &&
           preparation_.before_measurement_producer();
  }
  auto reset_consumer() noexcept -> bool {
    const auto& row = preparation_.consumer_phase(false);
    return row.polls == 0U && row.consumed == 0U && row.empty == 0U &&
           row.state == row.initial_state && row.primary_prefix_complete &&
           row.demand.snapshot().row_count == 0U &&
           row.primary.snapshot().row_count == 0U &&
           preparation_.before_measurement_consumer();
  }
  auto reset_quiescent() noexcept -> bool {
    return validated_[0U] && preparation_.ring().reset_quiescent();
  }
  auto validate_quiescent(ServicePhase selected,
                          const ServicePhaseResult& result) noexcept -> bool {
    const auto index = selected == ServicePhase::warmup ? 0U : 1U;
    auto& producer = preparation_.producer_phase(index == 0U);
    auto& consumer = preparation_.consumer_phase(index == 0U);
    consumer.last_join = reconcile_discovery_primary(
        preparation_.arena(), producer.primary.snapshot(), producer.layout,
        consumer.primary.snapshot(), consumer.layout,
        {producer.attempted, producer.accepted, producer.full, consumer.consumed},
        {consumer.initial_state, consumer.state}, true);
    if (!result.producer.deadline_reached ||
        !result.producer.arrivals_finished_published || !result.consumer.drained ||
        producer.requests != result.producer.attempted ||
        producer.attempted != result.producer.attempted ||
        producer.accepted != result.producer.accepted ||
        producer.full != result.producer.full ||
        consumer.polls != result.consumer.polls ||
        consumer.consumed != result.consumer.consumed ||
        consumer.empty != result.consumer.empty ||
        producer.demand.snapshot().row_count != producer.attempted ||
        consumer.demand.snapshot().row_count != consumer.polls ||
        !producer.primary_prefix_complete || !consumer.primary_prefix_complete ||
        consumer.last_join.status != DiscoveryJoinStatus::exact) {
      return false;
    }
    // Seal all four independently: do not hide a later stream's failure.
    const bool p = producer.primary.seal_complete();
    const bool c = consumer.primary.seal_complete();
    const bool pd = producer.demand.seal_complete();
    const bool cd = consumer.demand.seal_complete();
    validated_[index] = p && c && pd && cd;
    return validated_[index];
  }
  // Always call after run_service_session returns, including preparation,
  // clock, observer and retention failure. Successful warmup remains intact.
  void finalize_joined() noexcept {
    for (std::size_t index = 0U; index < 2U; ++index) {
      if (validated_[index]) {
        continue;
      }
      if (available_[0U]) {
        auto& row = preparation_.producer_phase(index == 0U);
        row.primary.seal_incomplete();
        row.demand.seal_incomplete();
      }
      if (available_[1U]) {
        auto& row = preparation_.consumer_phase(index == 0U);
        row.primary.seal_incomplete();
        row.demand.seal_incomplete();
      }
    }
  }

private:
  static auto empty_streams(const auto& row, RingWorker role,
                            std::uint64_t limit) noexcept -> bool {
    const auto primary = row.primary.snapshot();
    const auto demand = row.demand.snapshot();
    const auto kind = role == RingWorker::producer ? protocol::StreamKind::producer
                                                   : protocol::StreamKind::consumer;
    return demand.worker == role && demand.run_id == primary.run_id &&
           demand.row_count == 0U && demand.row_capacity >= limit &&
           demand.completeness == storage::StreamCompleteness::writing &&
           !demand.overflowed && primary.row_count == 0U &&
           primary.completeness == storage::StreamCompleteness::writing &&
           !primary.overflowed &&
           (role != RingWorker::producer || primary.row_capacity >= limit) &&
           storage::prepared_primary_stream_shape(primary, row.layout, kind);
  }
  struct BracketCheck final {
    auto record(RingWorker, std::uint64_t before, std::uint64_t after,
                RingAttemptOutcome) const noexcept -> bool {
      return after >= before;
    }
  };
  static void retain_demand(auto& phase, RingCaptureResult& captured,
                            std::uint64_t attempt, std::uint64_t ordinal) noexcept {
    const auto& demand = phase.current.demand;
    if (!captured.operation_performed) {
      return;
    }
    if (!captured.operation_outcome || !demand.before || !demand.after) {
      captured.outcome = RingAttemptOutcome::trace_failure;
      return;
    }
    phase.last_demand_append = phase.demand.append(
        {attempt, *captured.operation_outcome,
         *captured.operation_outcome == RingAttemptOutcome::advanced ? ordinal : 0U,
         *demand.before, *demand.after});
    if (phase.last_demand_append != storage::AppendStatus::appended) {
      captured.outcome = RingAttemptOutcome::trace_failure;
    }
  }
  auto produce(FormalRingProducerPhase& phase,
               lifecycle::ProducerAttempt attempt) noexcept
      -> lifecycle::ProducerAttemptResult {
    if (phase.stopped || attempt.logical_sequence != phase.requests ||
        attempt.candidate_accepted_ordinal != phase.accepted) {
      return {lifecycle::AttemptStatus::failure, queue::EnqueueResult::full};
    }
    BracketCheck trace;
    auto captured = capture_discovery_producer_event(
        clock_, preparation_.arena(), preparation_.ring(), trace,
        {attempt.logical_sequence}, attempt.scheduled_deadline,
        {attempt.candidate_accepted_ordinal}, phase.current);
    retain_demand(phase, captured, phase.requests, phase.accepted);
    ++phase.requests;
    if (captured.operation_performed) {
      ++phase.attempted;
      if (captured.operation_outcome == RingAttemptOutcome::advanced) {
        ++phase.accepted;
      } else if (captured.operation_outcome == RingAttemptOutcome::full) {
        ++phase.full;
      }
      if (phase.current.primary && phase.primary_prefix_complete) {
        phase.last_primary_append = phase.primary.append(*phase.current.primary);
        if (phase.last_primary_append != storage::AppendStatus::appended) {
          phase.primary_prefix_complete = false;
          captured.outcome = RingAttemptOutcome::trace_failure;
        }
      } else {
        phase.primary_prefix_complete = false;
      }
    }
    phase.current.capture = captured;
    phase.stopped = captured.outcome != RingAttemptOutcome::advanced &&
                    captured.outcome != RingAttemptOutcome::full;
    return {captured.outcome == RingAttemptOutcome::advanced ||
                    captured.outcome == RingAttemptOutcome::full
                ? lifecycle::AttemptStatus::complete
                : lifecycle::AttemptStatus::failure,
            captured.operation_outcome == RingAttemptOutcome::advanced
                ? queue::EnqueueResult::accepted
                : queue::EnqueueResult::full};
  }
  auto consume(FormalRingConsumerPhase& phase, std::uint64_t ordinal) noexcept
      -> lifecycle::ConsumerPollResult {
    if (phase.stopped || ordinal != phase.consumed) {
      return {lifecycle::ConsumerPollStatus::failure};
    }
    BracketCheck trace;
    auto captured = capture_discovery_consumer_event(
        clock_, preparation_.arena(), preparation_.ring(), trace, phase.state,
        {ordinal}, phase.current);
    retain_demand(phase, captured, phase.polls, phase.consumed);
    ++phase.polls;
    if (captured.operation_performed &&
        captured.operation_outcome == RingAttemptOutcome::advanced) {
      ++phase.consumed;
      if (phase.current.primary && phase.primary_prefix_complete) {
        phase.last_primary_append = phase.primary.append(*phase.current.primary);
        if (phase.last_primary_append != storage::AppendStatus::appended) {
          phase.primary_prefix_complete = false;
          captured.outcome = RingAttemptOutcome::trace_failure;
        }
      } else {
        phase.primary_prefix_complete = false;
      }
    } else if (captured.operation_performed &&
               captured.operation_outcome == RingAttemptOutcome::empty) {
      ++phase.empty;
    }
    phase.current.capture = captured;
    phase.stopped = captured.outcome != RingAttemptOutcome::advanced &&
                    captured.outcome != RingAttemptOutcome::empty;
    return {captured.outcome == RingAttemptOutcome::advanced
                ? lifecycle::ConsumerPollStatus::item
            : captured.outcome == RingAttemptOutcome::empty
                ? lifecycle::ConsumerPollStatus::empty
                : lifecycle::ConsumerPollStatus::failure};
  }
  const ServiceSessionPlan& plan_;
  Clock& clock_;
  Preparation& preparation_;
  std::array<Phase, 2U> phases_;
  std::array<bool, 2U> available_{};
  std::array<bool, 2U> validated_{};
};

template <typename Clock, typename Preparation, typename Relax, typename Observer,
          typename Threads>
[[nodiscard]] auto
run_formal_ring_session(FormalRingSessionBackend<Clock, Preparation>& backend,
                        Relax& relax, Observer& observer, Threads& threads,
                        ServiceSessionStorage& storage) -> ServiceSessionResult {
  const auto result = run_service_session(backend.plan(), backend.clock(), backend,
                                          backend, relax, observer, threads, storage);
  backend.finalize_joined();
  return result;
}

} // namespace cpu_prefetch::calibration
#endif
