#include "cpu_prefetch/calibration/native_formal_service_capture.hpp"
#include "cpu_prefetch/calibration/detail/native_service_envelope.hpp"
#include "cpu_prefetch/runner/software_prefetch.hpp"

namespace cpu_prefetch::calibration {
namespace {
template <protocol::QueuePackage Kind, typename Emitter> struct ServiceTraits final {
  using Plan = NativeFormalServiceCapturePlan;
  using Layout = NativeFormalServiceCaptureLayout;
  using Result = NativeFormalServiceCaptureResult;
  using Publication = NativeFormalServicePublication;
  template <typename Clock, typename Relax>
  using Runtime =
      MappedServiceRuntime<Clock, Relax, FormalServiceRuntimePolicy<Kind, Emitter>>;
  static auto capture_plan(const Plan& plan) noexcept
      -> const MappedFormalServicePlan& {
    return plan.service;
  }
  static auto runtime_plan(const Plan& plan) noexcept
      -> const MappedFormalServicePlan& {
    return plan.service;
  }
  static auto worker_layout(const Plan& plan) -> MappedFormalServiceLayout {
    return mapped_formal_service_layout<Kind, Emitter>(plan.service);
  }
  static auto observer_plan(const MappedFormalServicePlan& plan) noexcept
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
    NativeFormalServicePublicationView view{result, layout, observations};
    auto& prepared = runtime.preparation();
    if (prepared.status(0U) == MappedDiscoveryPreparationStop::ready) {
      view.arena = &prepared.arena();
      view.node_order = prepared.node_order();
      for (std::size_t index = 0U; index < 2U; ++index)
        view.producer[index] = &prepared.producer_phase(index == 0U);
    }
    if (prepared.status(1U) == MappedDiscoveryPreparationStop::ready) {
      for (std::size_t index = 0U; index < 2U; ++index)
        view.consumer[index] = &prepared.consumer_phase(index == 0U);
    }
    return publication.publish(publication.context, view);
  }
};

template <typename Emitter, typename Function>
auto dispatch_package(protocol::QueuePackage package, Function& function) {
  switch (package) {
  case protocol::QueuePackage::nblfq_mpsc:
  case protocol::QueuePackage::not_applicable:
    break;
  case protocol::QueuePackage::r0:
    return function
        .template operator()<ServiceTraits<protocol::QueuePackage::r0, Emitter>>();
  case protocol::QueuePackage::r1:
    return function
        .template operator()<ServiceTraits<protocol::QueuePackage::r1, Emitter>>();
  case protocol::QueuePackage::r2:
    return function
        .template operator()<ServiceTraits<protocol::QueuePackage::r2, Emitter>>();
  case protocol::QueuePackage::l0:
    return function
        .template operator()<ServiceTraits<protocol::QueuePackage::l0, Emitter>>();
  case protocol::QueuePackage::l1:
    return function
        .template operator()<ServiceTraits<protocol::QueuePackage::l1, Emitter>>();
  }
  throw std::invalid_argument("unregistered formal service package");
}
template <typename Function>
auto dispatch(const NativeFormalServiceCapturePlan& plan, Function function) {
  const auto identity = plan.controls.hardware_identity;
  const auto match = std::find_if(
      runner::kSoftwarePrefetchMappings.begin(),
      runner::kSoftwarePrefetchMappings.end(), [&](const auto& entry) {
        return entry.family == identity.family && entry.model == identity.model;
      });
  if (match == runner::kSoftwarePrefetchMappings.end() ||
      match->mapping_id != plan.software_prefetch_mapping_id) {
    throw std::invalid_argument(
        "formal software mapping does not match accepted model registry");
  }
  // Model selection is cold and explicit. The shared envelope's prepared MSR
  // reader checks actual CPUID against this identity before starting workers.
  if (match->mapping_id == runner::kSoftwarePrefetchMappingId) {
    return dispatch_package<runner::X86RetainingPrefetchEmitter>(plan.service.package,
                                                                 function);
  }
  return dispatch_package<runner::X86PrefetchT0OnlyEmitter>(plan.service.package,
                                                            function);
}
} // namespace

auto native_formal_service_layout(const NativeFormalServiceCapturePlan& plan)
    -> NativeFormalServiceCaptureLayout {
  return dispatch(plan, [&]<typename Traits> {
    return native_capture_detail::ServiceEnvelope<Traits>::make_layout(plan)
        .public_layout;
  });
}
auto run_native_formal_service_capture(const NativeFormalServiceCapturePlan& plan,
                                       NativeFormalServicePublication publication)
    -> NativeFormalServiceCaptureResult {
  if (publication.publish == nullptr)
    throw std::invalid_argument("formal service requires synchronous raw publication");
  return dispatch(plan, [&]<typename Traits> {
    return native_capture_detail::ServiceEnvelope<Traits>::run(plan, publication);
  });
}
} // namespace cpu_prefetch::calibration
