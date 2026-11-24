#include "cpu_prefetch/calibration/scheduled_session.hpp"

namespace cpu_prefetch::calibration {

auto valid_scheduled_plan(const ScheduledSessionPlan& plan) noexcept -> bool {
  if (!valid_service_plan(plan.bounds) ||
      plan.bounds.phases[0U].duration_ticks != 5'000'000'000'000U ||
      plan.phases[0U].schedule_id == plan.phases[1U].schedule_id ||
      plan.phases[0U].namespace_id == plan.phases[1U].namespace_id ||
      plan.phases[1U].offered_count == 0U) {
    return false;
  }
  for (std::size_t index = 0U; index < 2U; ++index) {
    const auto& phase = plan.phases[index];
    const auto bounds = plan.bounds.phases[index];
    if (phase.source_horizon_ticks <= phase.source_origin_ticks ||
        phase.source_horizon_ticks - phase.source_origin_ticks !=
            bounds.duration_ticks ||
        phase.offered_count > bounds.producer_attempt_limit) {
      return false;
    }
  }
  return true;
}

auto scheduled_source_matches(const ScheduledPhasePlan& plan,
                              lifecycle::PreparedScheduleView source) noexcept -> bool {
  if (source.origin_ticks != plan.source_origin_ticks ||
      source.horizon_ticks != plan.source_horizon_ticks ||
      source.deadline_ticks.size() != plan.offered_count ||
      (!source.deadline_ticks.empty() && source.deadline_ticks.data() == nullptr)) {
    return false;
  }
  // Same half-open/nondecreasing grammar as validate_prepared_schedule, with
  // bounded first-error handling: no per-row strings or unbounded error vector.
  std::optional<std::uint64_t> previous;
  for (const auto deadline : source.deadline_ticks) {
    if (deadline < source.origin_ticks || deadline >= source.horizon_ticks ||
        (previous.has_value() && deadline < *previous)) {
      return false;
    }
    previous = deadline;
  }
  return true;
}

} // namespace cpu_prefetch::calibration
