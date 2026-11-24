#ifndef CPU_PREFETCH_CALIBRATION_SCHEDULED_SESSION_HPP
#define CPU_PREFETCH_CALIBRATION_SCHEDULED_SESSION_HPP

#include "cpu_prefetch/calibration/service_session.hpp"

namespace cpu_prefetch::calibration {

struct ScheduledPhasePlan final {
  // Source endpoint follows PreparedScheduleView, not an elapsed duration.
  std::uint64_t source_origin_ticks;
  std::uint64_t source_horizon_ticks;
  std::uint64_t offered_count;
  protocol::ScheduleId schedule_id;
  protocol::NamespaceId namespace_id;
};

struct ScheduledSessionPlan final {
  ServiceSessionPlan bounds;
  std::array<ScheduledPhasePlan, 2U> phases;
};

struct ScheduledPhaseEvidence final {
  std::uint64_t offered{0U};
  std::uint64_t source_origin_ticks{0U};
  std::uint64_t source_horizon_ticks{0U};
  std::uint64_t producer_wait_polls{0U};
  std::optional<std::uint64_t> mapped_last_deadline{};
  std::optional<timing::ClockReadResult> producer_completion{};
  bool mapped_schedule_validated{false};
  bool all_arrivals_attempted{false};
};

struct ScheduledSessionResult final {
  ServiceSessionResult lifecycle;
  std::array<ScheduledPhaseEvidence, 2U> schedules;
};

struct ScheduledSessionStorage final {
  explicit ScheduledSessionStorage(ServiceTerminationControls controls) noexcept
      : common(controls) {}
  ServiceSessionStorage common;
  std::array<ScheduledPhaseEvidence, 2U> schedules;
};

// Pure prospective checks. Bootstrap warmup's *schedule* horizon is exactly
// five seconds; it is not a claim of five seconds of active worker execution.
// D036 rejects zero-offered measurement. There is no warmup minimum-count rule.
[[nodiscard]] auto valid_scheduled_plan(const ScheduledSessionPlan& plan) noexcept
    -> bool;
[[nodiscard]] auto
scheduled_source_matches(const ScheduledPhasePlan& plan,
                         lifecycle::PreparedScheduleView source) noexcept -> bool;

// Definition below uses the existing D210 owner preparation, start barriers,
// termination controls, parked reset, clock checkpoints and observer seams.
// Backend must statically disable D211 interval counting. Preparation additionally
// exposes schedule(ServicePhase) -> PreparedScheduleView, from its actual mapped
// immutable arrays AFTER owners have prepared. Both schedules are checked before
// the first phase is released; no parent-heap schedule is executed as a substitute.
// Existing capture helpers receive the translated logical deadline in the same
// clock domain as their timestamps: actual_origin + (source_deadline-source_origin).
// Publish arrivals_finished immediately after the final scheduled attempt;
// no extra horizon hold. Late arrivals still get their one attempt, within the
// explicit failure/watchdog bounds. All mandatory observations remain mandatory.
template <typename Clock, typename Backend, typename Preparation, typename Relax,
          typename Observer, typename Threads>
[[nodiscard]] auto
run_scheduled_session(const ScheduledSessionPlan& plan, Clock& clock, Backend& backend,
                      Preparation& preparation, Relax& relax, Observer& observer,
                      Threads& threads, ScheduledSessionStorage& storage)
    -> ScheduledSessionResult;

} // namespace cpu_prefetch::calibration

#include "cpu_prefetch/calibration/detail/scheduled_session_impl.hpp"

#endif // CPU_PREFETCH_CALIBRATION_SCHEDULED_SESSION_HPP
