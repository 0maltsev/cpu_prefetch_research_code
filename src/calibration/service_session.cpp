#include "cpu_prefetch/calibration/service_session.hpp"

#include <limits>

namespace cpu_prefetch::calibration {

auto valid_service_plan(const ServiceSessionPlan& plan) noexcept -> bool {
  if (plan.barrier_poll_limit == 0U) {
    return false;
  }
  for (const auto& phase : plan.phases) {
    if (phase.duration_ticks == 0U || phase.producer_attempt_limit == 0U ||
        phase.consumer_poll_limit == 0U || phase.drain_duration_ticks == 0U) {
      return false;
    }
  }
  return true;
}

auto service_window(std::uint64_t origin, ServicePhasePlan plan) noexcept
    -> std::optional<ServiceWindow> {
  constexpr auto maximum = std::numeric_limits<std::uint64_t>::max();
  if (plan.duration_ticks == 0U || plan.drain_duration_ticks == 0U ||
      plan.duration_ticks > maximum - origin) {
    return std::nullopt;
  }
  const auto deadline = origin + plan.duration_ticks;
  if (plan.drain_duration_ticks > maximum - deadline) {
    return std::nullopt;
  }
  return ServiceWindow{origin, plan.duration_ticks, deadline,
                       deadline + plan.drain_duration_ticks};
}

} // namespace cpu_prefetch::calibration
