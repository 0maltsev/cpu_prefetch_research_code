#ifndef CPU_PREFETCH_CALIBRATION_MAPPED_FORMAL_SCHEDULED_RUNTIME_HPP
#define CPU_PREFETCH_CALIBRATION_MAPPED_FORMAL_SCHEDULED_RUNTIME_HPP

#include "cpu_prefetch/calibration/mapped_formal_ring_runtime.hpp"
#include "cpu_prefetch/calibration/mapped_formal_scheduled_preparation.hpp"

namespace cpu_prefetch::calibration {

template <protocol::QueuePackage Kind, typename Emitter>
struct FormalScheduledRuntimePolicy final {
  using Plan = MappedFormalScheduledPlan;
  using Layout = MappedFormalServiceLayout;
  using SessionStorage = ScheduledSessionStorage;
  using SessionResult = ScheduledSessionResult;
  template <typename Operations, typename Relax>
  using Provider = MappedFormalScheduledPreparation<Kind, Emitter, Operations, Relax>;
  template <typename Clock, typename Preparation>
  using Backend =
      FormalServiceSessionBackend<Clock, Preparation, FormalCapturePurpose::scheduled>;
  static auto base_plan(const Plan& plan) noexcept -> const MappedFormalServicePlan& {
    return plan.service;
  }
  static auto layout(const Plan& plan) -> Layout {
    return mapped_formal_scheduled_layout<Kind, Emitter>(plan);
  }
  template <typename Clock, typename Preparation>
  static auto make_backend(const Plan& plan, Clock& clock, Preparation& preparation)
      -> Backend<Clock, Preparation> {
    return {plan.service.session, clock, preparation};
  }
  template <typename Clock, typename Preparation, typename Relax, typename Observer,
            typename Threads>
  static auto run(const Plan& plan, Backend<Clock, Preparation>& backend,
                  Preparation& preparation, Relax& relax, Observer& observer,
                  Threads& threads, SessionStorage& storage) -> SessionResult {
    return run_scheduled_session({plan.service.session, plan.phases}, backend.clock(),
                                 backend, preparation, relax, observer, threads,
                                 storage);
  }
};

} // namespace cpu_prefetch::calibration
#endif
