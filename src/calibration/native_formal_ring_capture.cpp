#include "cpu_prefetch/calibration/detail/native_service_envelope.hpp"

namespace cpu_prefetch::calibration {
namespace {
struct RingTraits final {
  using Plan = NativeFormalRingCapturePlan;
  using Layout = NativeFormalRingCaptureLayout;
  using Result = NativeFormalRingCaptureResult;
  using Publication = NativeFormalRingPublication;
  template <typename Clock, typename Relax>
  using Runtime = MappedFormalRingRuntime<Clock, Relax>;
  static auto capture_plan(const Plan& plan) noexcept -> const MappedFormalRingPlan& {
    return plan.ring;
  }
  static auto runtime_plan(const Plan& plan) noexcept -> const MappedFormalRingPlan& {
    return plan.ring;
  }
  static auto worker_layout(const Plan& plan) -> MappedFormalRingLayout {
    return mapped_formal_ring_layout(plan.ring);
  }
  // The residency scheduler reads only these two durations. Remaining fields
  // are not an executable diagnostic plan and are never passed to its lifecycle.
  static auto observer_plan(const MappedFormalRingPlan& plan) noexcept
      -> DiscoverySessionPlan {
    return {plan.session.phases[0U].duration_ticks,
            plan.session.phases[1U].duration_ticks,
            0U,
            0U,
            0U,
            0U,
            0U};
  }
  static auto session_stop(const ServiceSessionResult& result) noexcept
      -> NativeCaptureStop {
    return result.stop == ServiceSessionStop::complete
               ? NativeCaptureStop::complete
               : NativeCaptureStop::capture_failed;
  }
  template <typename Clock, typename Relax>
  static auto publish(Publication publication, const Result& result,
                      const Layout& layout, NativeCaptureObservationView observations,
                      Runtime<Clock, Relax>& runtime) -> bool {
    NativeFormalRingPublicationView view{result, layout, observations};
    auto& prepared = runtime.preparation();
    if (prepared.status(0U) == MappedDiscoveryPreparationStop::ready) {
      view.arena = &prepared.arena();
      for (std::size_t phase = 0U; phase < 2U; ++phase) {
        view.producer[phase] = &prepared.producer_phase(phase == 0U);
      }
    }
    if (prepared.status(1U) == MappedDiscoveryPreparationStop::ready) {
      for (std::size_t phase = 0U; phase < 2U; ++phase) {
        view.consumer[phase] = &prepared.consumer_phase(phase == 0U);
      }
    }
    return publication.publish(publication.context, view);
  }
};
using Envelope = native_capture_detail::ServiceEnvelope<RingTraits>;
} // namespace

auto native_formal_ring_layout(const NativeFormalRingCapturePlan& plan)
    -> NativeFormalRingCaptureLayout {
  return Envelope::make_layout(plan).public_layout;
}
auto run_native_formal_ring_capture(const NativeFormalRingCapturePlan& plan,
                                    NativeFormalRingPublication publication)
    -> NativeFormalRingCaptureResult {
  return Envelope::run(plan, publication);
}
} // namespace cpu_prefetch::calibration
