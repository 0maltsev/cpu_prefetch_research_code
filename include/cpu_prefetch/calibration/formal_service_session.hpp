#ifndef CPU_PREFETCH_CALIBRATION_FORMAL_SERVICE_SESSION_HPP
#define CPU_PREFETCH_CALIBRATION_FORMAL_SERVICE_SESSION_HPP

#include "cpu_prefetch/calibration/discovery_reconciliation.hpp"
#include "cpu_prefetch/calibration/service_interval_count.hpp"
#include "cpu_prefetch/calibration/service_session.hpp"

#include <type_traits>
#include <utility>

namespace cpu_prefetch::calibration {

enum class FormalCapturePurpose : std::uint8_t { service_rate, scheduled };

struct FormalServiceProducerPhase final {
  storage::ProducerObservationStream& primary;
  storage::RowLayout layout;
  std::optional<timing::ProducerCaptureResult> current{};
  std::optional<storage::AppendStatus> last_append{};
  std::uint64_t requests{0U};
  std::uint64_t retained_attempts{0U};
  std::uint64_t accepted{0U};
  std::uint64_t full{0U};
  bool stopped{false};
};

struct FormalServiceConsumerPhase final {
  storage::ConsumerObservationStream& primary;
  storage::RowLayout layout;
  workload::ConsumerState initial_state;
  workload::ConsumerState state;
  std::optional<timing::ConsumerCaptureResult> current{};
  std::optional<storage::AppendStatus> last_append{};
  std::uint64_t polls{0U};
  std::uint64_t retained_consumed{0U};
  std::uint64_t empty{0U};
  DiscoveryJoinResult last_join{DiscoveryJoinStatus::not_evaluated};
  // Measurement only, after a full primary join and sealed complete streams.
  // Total retained_consumed remains separate from the D211 interval numerator.
  std::optional<ServiceIntervalResult> interval{};
  bool stopped{false};
};

// Preparation supplies owner-local warmup/measurement states, the same arena,
// statically typed package() and queue(), run_id(bool), prepare_producer/consumer(),
// and before_measurement_producer/consumer() owner-private reset/readback callbacks.
// All objects/maps/order survive warmup drain, parked reset and measurement.
// One typed instantiation selects the package before capture; no hot switch.
// Capture primitives are unchanged, including failure semantics: when they
// supply no observation, no outcome/actual operation total is reconstructed.
// Requests/polls count invocations; accepted/full/consumed describe retained
// primary prefixes. Failed phases are ineligible even if a queue operation
// happened before the failure. The exact current failure survives until publish.
template <typename Clock, typename Preparation,
          FormalCapturePurpose Purpose = FormalCapturePurpose::service_rate>
class FormalServiceSessionBackend final {
public:
  static constexpr bool counts_completion_interval =
      Purpose == FormalCapturePurpose::service_rate;
  static_assert(Purpose == FormalCapturePurpose::service_rate ||
                Purpose == FormalCapturePurpose::scheduled);
  using Package = std::remove_cvref_t<decltype(std::declval<Preparation&>().package())>;
  static constexpr protocol::QueuePackage package_kind = Package::package;
  static_assert(package_kind == protocol::QueuePackage::r0 ||
                package_kind == protocol::QueuePackage::r1 ||
                package_kind == protocol::QueuePackage::r2 ||
                package_kind == protocol::QueuePackage::l0 ||
                package_kind == protocol::QueuePackage::l1);

  FormalServiceSessionBackend(const ServiceSessionPlan& plan, Clock& clock,
                              Preparation& preparation) noexcept
      : plan_(plan), clock_(clock), preparation_(preparation),
        phases_{{Phase{*this, true}, Phase{*this, false}}} {}
  FormalServiceSessionBackend(const FormalServiceSessionBackend&) = delete;
  auto operator=(const FormalServiceSessionBackend&)
      -> FormalServiceSessionBackend& = delete;

  class Phase final {
  public:
    Phase(FormalServiceSessionBackend& owner, bool warmup) noexcept
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
    FormalServiceSessionBackend& owner_;
    bool warmup_;
  };

  auto plan() const noexcept -> const ServiceSessionPlan& { return plan_; }
  auto clock() noexcept -> Clock& { return clock_; }
  // The returned typed capture seam also fits the existing scheduled executor;
  // Q16c still requires a separate persistent scheduled lifecycle driver.
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
    if (&warmup == &measurement || &warmup.primary == &measurement.primary ||
        warmup.primary.snapshot().run_id == measurement.primary.snapshot().run_id) {
      return false;
    }
    for (std::size_t index = 0U; index < 2U; ++index) {
      auto& row = preparation_.producer_phase(index == 0U);
      if (!producer_fresh(row) ||
          row.primary.snapshot().run_id != preparation_.run_id(index == 0U).value() ||
          !empty_primary(row, protocol::StreamKind::producer,
                         plan_.phases[index].producer_attempt_limit) ||
          !row.primary.prepare_for_owner()) {
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
    if (&warmup == &measurement || &warmup.primary == &measurement.primary ||
        warmup.primary.snapshot().run_id == measurement.primary.snapshot().run_id ||
        warmup.initial_state != measurement.initial_state) {
      return false;
    }
    for (std::size_t index = 0U; index < 2U; ++index) {
      auto& row = preparation_.consumer_phase(index == 0U);
      if (!consumer_fresh(row) ||
          row.primary.snapshot().run_id != preparation_.run_id(index == 0U).value() ||
          !empty_primary(row, protocol::StreamKind::consumer,
                         plan_.phases[index].producer_attempt_limit) ||
          !row.primary.prepare_for_owner()) {
        return false;
      }
    }
    return true;
  }
  auto reset_producer() noexcept -> bool {
    const auto& row = preparation_.producer_phase(false);
    return producer_fresh(row) && row.primary.snapshot().row_count == 0U &&
           preparation_.before_measurement_producer();
  }
  auto reset_consumer() noexcept -> bool {
    const auto& row = preparation_.consumer_phase(false);
    return consumer_fresh(row) && row.primary.snapshot().row_count == 0U &&
           preparation_.before_measurement_consumer();
  }
  auto reset_quiescent() noexcept -> bool {
    return validated_[0U] && preparation_.queue().reset_quiescent();
  }
  auto validate_quiescent(ServicePhase selected,
                          const ServicePhaseResult& result) noexcept -> bool {
    if (selected != ServicePhase::warmup && selected != ServicePhase::measurement) {
      return false;
    }
    const auto index = selected == ServicePhase::warmup ? 0U : 1U;
    auto& producer = preparation_.producer_phase(index == 0U);
    auto& consumer = preparation_.consumer_phase(index == 0U);
    if (!result.released || !result.origin_sample || !result.window ||
        result.origin_status != timing::ClockReadStatus::ok ||
        result.observed_origin != result.origin_sample->relative_picoseconds ||
        result.window->origin_ticks != result.origin_sample->relative_picoseconds ||
        result.window->duration_ticks != plan_.phases[index].duration_ticks ||
        (counts_completion_interval && !result.producer.deadline_reached) ||
        !result.producer.arrivals_finished_published || !result.consumer.drained ||
        producer.stopped || consumer.stopped ||
        producer.requests != producer.retained_attempts ||
        producer.retained_attempts != result.producer.attempted ||
        producer.accepted != result.producer.accepted ||
        producer.full != result.producer.full ||
        consumer.polls != result.consumer.polls ||
        consumer.retained_consumed != result.consumer.consumed ||
        consumer.empty != result.consumer.empty) {
      return false;
    }
    consumer.last_join = reconcile_discovery_primary(
        preparation_.arena(), producer.primary.snapshot(), producer.layout,
        consumer.primary.snapshot(), consumer.layout,
        {producer.retained_attempts, producer.accepted, producer.full,
         consumer.retained_consumed},
        {consumer.initial_state, consumer.state}, true);
    if (consumer.last_join.status != DiscoveryJoinStatus::exact) {
      return false;
    }
    const bool producer_sealed = producer.primary.seal_complete();
    const bool consumer_sealed = consumer.primary.seal_complete();
    if (!producer_sealed || !consumer_sealed) {
      return false;
    }
    if constexpr (counts_completion_interval) {
      if (selected == ServicePhase::measurement) {
        // These constants name the accepted exact clock domain, not a platform
        // estimate or an empirical duration/default. The duration is the plan's.
        const ServiceIntervalClock geometry{
            timing::kClockSuiteId, storage::kRawTimeUnit,
            1'000'000'000'000U,    clock_.origin().absolute_nanoseconds,
            *result.origin_sample, plan_.phases[index].duration_ticks};
        // The primary stream owns a validated RunId; retain its typed identity
        // from Preparation rather than parsing/allocating inside this callback.
        consumer.interval = count_service_interval(
            consumer.primary.snapshot(), consumer.layout, preparation_.run_id(false),
            consumer.retained_consumed, geometry);
        if (consumer.interval->status != ServiceIntervalStatus::complete) {
          return false;
        }
      }
    }
    validated_[index] = true;
    return true;
  }
  // Always after owner join, including preparation/capture/observer failure.
  // A previously completed warmup remains retained. Complete bytes whose cold
  // interval validation failed remain complete bytes but scientifically ineligible.
  void finalize_joined() noexcept {
    for (std::size_t index = 0U; index < 2U; ++index) {
      if (validated_[index]) {
        continue;
      }
      if (available_[0U]) {
        preparation_.producer_phase(index == 0U).primary.seal_incomplete();
      }
      if (available_[1U]) {
        preparation_.consumer_phase(index == 0U).primary.seal_incomplete();
      }
    }
  }

private:
  static auto producer_fresh(const FormalServiceProducerPhase& row) noexcept -> bool {
    return row.requests == 0U && row.retained_attempts == 0U && row.accepted == 0U &&
           row.full == 0U && !row.current && !row.last_append && !row.stopped;
  }
  static auto consumer_fresh(const FormalServiceConsumerPhase& row) noexcept -> bool {
    return row.polls == 0U && row.retained_consumed == 0U && row.empty == 0U &&
           row.state == row.initial_state && !row.current && !row.last_append &&
           !row.interval &&
           row.last_join.status == DiscoveryJoinStatus::not_evaluated && !row.stopped;
  }
  static auto empty_primary(const auto& row, protocol::StreamKind kind,
                            std::uint64_t minimum_capacity) noexcept -> bool {
    const auto snapshot = row.primary.snapshot();
    return snapshot.row_count == 0U && snapshot.row_capacity >= minimum_capacity &&
           snapshot.completeness == storage::StreamCompleteness::writing &&
           !snapshot.overflowed &&
           storage::prepared_primary_stream_shape(snapshot, row.layout, kind);
  }
  auto produce(FormalServiceProducerPhase& phase,
               lifecycle::ProducerAttempt attempt) noexcept
      -> lifecycle::ProducerAttemptResult {
    if (phase.stopped || attempt.logical_sequence != phase.requests ||
        attempt.candidate_accepted_ordinal != phase.accepted) {
      return {lifecycle::AttemptStatus::failure, queue::EnqueueResult::full};
    }
    phase.current = timing::capture_due_producer_attempt(
        clock_, preparation_.arena(), preparation_.package(),
        workload::LogicalSequence{attempt.logical_sequence}, attempt.scheduled_deadline,
        workload::AcceptedOrdinal{attempt.candidate_accepted_ordinal});
    ++phase.requests;
    phase.last_append.reset();
    const auto& captured = *phase.current;
    if (captured.status != timing::CaptureStatus::complete || !captured.observation) {
      phase.stopped = true;
      return {lifecycle::AttemptStatus::failure, queue::EnqueueResult::full};
    }
    const auto& observation = *captured.observation;
    const bool accepted = observation.outcome == protocol::ProducerOutcome::accepted;
    phase.last_append = phase.primary.append(observation);
    if (phase.last_append != storage::AppendStatus::appended) {
      phase.stopped = true;
      return {lifecycle::AttemptStatus::failure,
              accepted ? queue::EnqueueResult::accepted : queue::EnqueueResult::full};
    }
    ++phase.retained_attempts;
    if (accepted) {
      ++phase.accepted;
    } else {
      ++phase.full;
    }
    return {lifecycle::AttemptStatus::complete,
            accepted ? queue::EnqueueResult::accepted : queue::EnqueueResult::full};
  }
  auto consume(FormalServiceConsumerPhase& phase, std::uint64_t ordinal) noexcept
      -> lifecycle::ConsumerPollResult {
    if (phase.stopped || ordinal != phase.retained_consumed) {
      return {lifecycle::ConsumerPollStatus::failure};
    }
    phase.current = timing::capture_dequeue_poll(clock_, preparation_.arena(),
                                                 preparation_.package(), phase.state,
                                                 workload::AcceptedOrdinal{ordinal});
    ++phase.polls;
    phase.last_append.reset();
    const auto& captured = *phase.current;
    if (captured.status == timing::CaptureStatus::empty) {
      ++phase.empty;
      return {lifecycle::ConsumerPollStatus::empty};
    }
    if (captured.status != timing::CaptureStatus::complete || !captured.observation) {
      phase.stopped = true;
      return {lifecycle::ConsumerPollStatus::failure};
    }
    phase.last_append = phase.primary.append(*captured.observation);
    if (phase.last_append != storage::AppendStatus::appended) {
      phase.stopped = true;
      return {lifecycle::ConsumerPollStatus::failure};
    }
    ++phase.retained_consumed;
    return {lifecycle::ConsumerPollStatus::item};
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
run_formal_service_session(FormalServiceSessionBackend<Clock, Preparation>& backend,
                           Relax& relax, Observer& observer, Threads& threads,
                           ServiceSessionStorage& storage) -> ServiceSessionResult {
  const auto result = run_service_session(backend.plan(), backend.clock(), backend,
                                          backend, relax, observer, threads, storage);
  backend.finalize_joined();
  return result;
}

} // namespace cpu_prefetch::calibration

#endif // CPU_PREFETCH_CALIBRATION_FORMAL_SERVICE_SESSION_HPP
