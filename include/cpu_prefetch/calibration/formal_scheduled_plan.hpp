#ifndef CPU_PREFETCH_CALIBRATION_FORMAL_SCHEDULED_PLAN_HPP
#define CPU_PREFETCH_CALIBRATION_FORMAL_SCHEDULED_PLAN_HPP

#include "cpu_prefetch/calibration/formal_service_plan.hpp"
#include "cpu_prefetch/calibration/scheduled_session.hpp"

namespace cpu_prefetch::calibration {

// Borrowed cold input must remain live through native capture. Owner preparation
// copies both arrays into the declared immutable records mapping; workers never
// execute these parent-owned spans. Source endpoints and IDs are explicit.
struct MappedFormalScheduledPlan final {
  MappedFormalServicePlan service;
  std::array<ScheduledPhasePlan, 2U> phases;
  std::array<std::span<const std::uint64_t>, 2U> deadlines;
};
struct NativeFormalScheduledCapturePlan final {
  MappedFormalScheduledPlan scheduled;
  NativeCaptureControlPlan controls;
  std::string software_prefetch_mapping_id;
};

} // namespace cpu_prefetch::calibration
#endif
