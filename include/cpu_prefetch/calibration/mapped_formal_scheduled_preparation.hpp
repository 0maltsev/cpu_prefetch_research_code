#ifndef CPU_PREFETCH_CALIBRATION_MAPPED_FORMAL_SCHEDULED_PREPARATION_HPP
#define CPU_PREFETCH_CALIBRATION_MAPPED_FORMAL_SCHEDULED_PREPARATION_HPP

#include "cpu_prefetch/calibration/formal_scheduled_plan.hpp"
#include "cpu_prefetch/calibration/mapped_formal_service_preparation.hpp"

namespace cpu_prefetch::calibration {

inline void validate_mapped_scheduled_plan(const MappedFormalScheduledPlan& plan) {
  if (!valid_scheduled_plan({plan.service.session, plan.phases})) {
    throw std::invalid_argument("invalid mapped scheduled lifecycle plan");
  }
  for (std::size_t index = 0U; index < plan.phases.size(); ++index) {
    const auto& phase = plan.phases[index];
    const auto source = plan.deadlines[index];
    const auto address = reinterpret_cast<std::uintptr_t>(source.data());
    if (source.size() >
            static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max()) /
                sizeof(std::uint64_t) ||
        (!source.empty() &&
         (address == 0U || address % alignof(std::uint64_t) != 0U ||
          source.size_bytes() >
              std::numeric_limits<std::uintptr_t>::max() - address))) {
      throw std::invalid_argument("scheduled source extent is not representable");
    }
    if (!scheduled_source_matches(phase,
                                  {plan.deadlines[index], phase.source_origin_ticks,
                                   phase.source_horizon_ticks})) {
      throw std::invalid_argument("scheduled source disagrees with bound metadata");
    }
  }
}

template <protocol::QueuePackage Kind, typename Emitter>
[[nodiscard]] auto mapped_formal_scheduled_layout(const MappedFormalScheduledPlan& plan)
    -> MappedFormalServiceLayout {
  validate_mapped_scheduled_plan(plan);
  return mapped_formal_service_layout<Kind, Emitter>(plan.service, plan.deadlines);
}

// The service provider owns the same queue, package, primary streams and data
// maps. Only its cold immutable-record tail gains the two source arrays.
template <protocol::QueuePackage Kind, typename Emitter, typename Operations,
          typename Relax>
class MappedFormalScheduledPreparation final {
public:
  MappedFormalScheduledPreparation(const MappedFormalScheduledPlan& plan,
                                   MappedDiscoveryRegions<Operations> regions,
                                   Relax& relax)
      : plan_(plan), prepared_(checked_plan(plan), regions, relax, plan.deadlines) {}
  auto prepare_producer() noexcept -> bool { return prepared_.prepare_producer(); }
  auto prepare_consumer() noexcept -> bool { return prepared_.prepare_consumer(); }
  auto producer_phase(bool warmup) noexcept -> decltype(auto) {
    return prepared_.producer_phase(warmup);
  }
  auto consumer_phase(bool warmup) noexcept -> decltype(auto) {
    return prepared_.consumer_phase(warmup);
  }
  auto arena() const noexcept -> const workload::EventArena& {
    return prepared_.arena();
  }
  auto queue() noexcept -> decltype(auto) { return prepared_.queue(); }
  auto package() noexcept -> decltype(auto) { return prepared_.package(); }
  auto emitter() const noexcept -> const Emitter& { return prepared_.emitter(); }
  auto status(std::size_t worker) const -> MappedDiscoveryPreparationStop {
    return prepared_.status(worker);
  }
  auto node_order() const noexcept -> std::span<const std::size_t> {
    return prepared_.node_order();
  }
  auto schedule(ServicePhase phase) const noexcept -> lifecycle::PreparedScheduleView {
    const auto index = phase == ServicePhase::warmup ? 0U : 1U;
    const auto& source = plan_.phases[index];
    return {prepared_.schedule_deadlines(index), source.source_origin_ticks,
            source.source_horizon_ticks};
  }

private:
  static auto checked_plan(const MappedFormalScheduledPlan& plan)
      -> const MappedFormalServicePlan& {
    validate_mapped_scheduled_plan(plan);
    return plan.service;
  }
  const MappedFormalScheduledPlan& plan_;
  MappedFormalServicePreparation<Kind, Emitter, Operations, Relax> prepared_;
};

} // namespace cpu_prefetch::calibration
#endif
