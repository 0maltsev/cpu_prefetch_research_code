#include "cpu_prefetch/calibration/native_pilot_capture.hpp"
#include "cpu_prefetch/calibration/detail/native_service_envelope.hpp"
#include "cpu_prefetch/runner/software_prefetch.hpp"

namespace cpu_prefetch::calibration {
namespace {
template <protocol::QueuePackage Kind, typename Emitter> struct PilotTraits final {
  using Plan = NativePilotCapturePlan;
  using Layout = NativePilotCaptureLayout;
  using Result = NativePilotCaptureResult;
  using Publication = NativePilotPublication;
  static auto prospective_worker_layout(const Plan& p) -> PilotPrivateLayout {
    return prospective_pilot_private_layout<Kind, Emitter>(p.capture.scheduled);
  }
  static constexpr std::size_t extra_region_count = 2U;
  template <typename Clock, typename Relax>
  using Runtime = MappedServiceRuntime<Clock, Relax, PilotRuntimePolicy<Kind, Emitter>>;
  static auto capture_plan(const Plan& p) noexcept -> const MappedFormalServicePlan& {
    return p.capture.scheduled.service;
  }
  static auto runtime_plan(const Plan& p) noexcept -> const MappedPilotCapturePlan& {
    return p.capture;
  }
  static auto extra_regions(const Plan& p) noexcept { return p.capture.shared.regions; }
  static auto worker_layout(const Plan& p) -> PilotPrivateLayout {
    const auto& v = p.capture.shared;
    validate_pilot_shared_view(p.capture);
    if (p.controls.workers.producer_stack.owner_cpu != v.plan->producer_cpu ||
        p.controls.workers.producer_stack.requested_node != v.plan->shared_node)
      throw std::invalid_argument("pilot worker differs from persistent data owner");
    if (!v.node_pattern.adjacent_fraction_at_most_one_percent ||
        !v.node_pattern.modal_fraction_at_most_one_percent ||
        v.node_pattern.distinct_line_count != v.plan->arena.capacity + 1U ||
        v.node_pattern.shortest_period != v.plan->arena.capacity + 1U)
      throw std::invalid_argument(
          "pilot node address pattern has not passed the frozen gate");
    return mapped_pilot_capture_layout<Kind, Emitter>(p.capture);
  }
  static auto observer_plan(const MappedFormalServicePlan& p) noexcept
      -> DiscoverySessionPlan {
    return {p.session.phases[0U].duration_ticks,
            p.session.phases[1U].duration_ticks,
            0U,
            0U,
            0U,
            0U,
            0U};
  }
  static auto session_stop(const PilotLifecycleResult& p) noexcept
      -> NativeCaptureStop {
    return p.session.lifecycle.stop == ServiceSessionStop::complete
               ? NativeCaptureStop::complete
               : NativeCaptureStop::capture_failed;
  }
  template <typename Clock, typename Relax>
  static auto publish(Publication pub, const Result& r, const Layout& l,
                      NativeCaptureObservationView obs, Runtime<Clock, Relax>& runtime)
      -> bool {
    auto& prep = runtime.preparation();
    NativePilotPublicationView view{r, l, obs, prep.shared_view()};
    if (prep.status(0U) == MappedDiscoveryPreparationStop::ready)
      for (std::size_t i = 0U; i < 2U; ++i) {
        view.producer[i] = &prep.producer_phase(i == 0U);
        view.schedules[i] =
            prep.schedule(i == 0U ? ServicePhase::warmup : ServicePhase::measurement);
      }
    if (prep.status(1U) == MappedDiscoveryPreparationStop::ready)
      for (std::size_t i = 0U; i < 2U; ++i)
        view.consumer[i] = &prep.consumer_phase(i == 0U);
    return pub.publish(pub.context, view);
  }
};
template <typename Emitter, typename F> auto packages(protocol::QueuePackage p, F& f) {
  switch (p) {
  case protocol::QueuePackage::r0:
    return f.template operator()<PilotTraits<protocol::QueuePackage::r0, Emitter>>();
  case protocol::QueuePackage::r1:
    return f.template operator()<PilotTraits<protocol::QueuePackage::r1, Emitter>>();
  case protocol::QueuePackage::r2:
    return f.template operator()<PilotTraits<protocol::QueuePackage::r2, Emitter>>();
  case protocol::QueuePackage::l0:
    return f.template operator()<PilotTraits<protocol::QueuePackage::l0, Emitter>>();
  case protocol::QueuePackage::l1:
    return f.template operator()<PilotTraits<protocol::QueuePackage::l1, Emitter>>();
  default:
    throw std::invalid_argument("unregistered pilot package");
  }
}
template <typename F> auto dispatch(const NativePilotCapturePlan& p, F f) {
  const auto it =
      std::find_if(runner::kSoftwarePrefetchMappings.begin(),
                   runner::kSoftwarePrefetchMappings.end(), [&](const auto& m) {
                     return m.family == p.controls.hardware_identity.family &&
                            m.model == p.controls.hardware_identity.model;
                   });
  if (it == runner::kSoftwarePrefetchMappings.end() ||
      it->mapping_id != p.software_prefetch_mapping_id)
    throw std::invalid_argument(
        "pilot software prefetch mapping is not registered for this model");
  if (it->mapping_id == runner::kSoftwarePrefetchMappingId)
    return packages<runner::X86RetainingPrefetchEmitter>(
        p.capture.scheduled.service.package, f);
  return packages<runner::X86PrefetchT0OnlyEmitter>(p.capture.scheduled.service.package,
                                                    f);
}
} // namespace
auto native_pilot_layout(const NativePilotCapturePlan& p) -> NativePilotCaptureLayout {
  return dispatch(p, [&]<typename T> {
    return native_capture_detail::ServiceEnvelope<T>::make_layout(p).public_layout;
  });
}
auto prospective_native_pilot_layout(const NativePilotCapturePlan& p,
                                     const MappedPilotDataPlan& data)
    -> NativePilotCaptureLayout {
  const auto& v = p.capture.shared;
  if (v.data || v.plan || v.mappings[0U] || v.mappings[1U] || !v.node_order.empty() ||
      !v.regions[0U].mapping.empty() || !v.regions[1U].mapping.empty() ||
      !p.capture.scheduled.deadlines[0U].empty() ||
      !p.capture.scheduled.deadlines[1U].empty())
    throw std::invalid_argument("prospective pilot sizing requires unbound views, not "
                                "live mappings or inline sources");
  const auto& service = p.capture.scheduled.service;
  const auto& arena = service.arena;
  if (arena.capacity != data.arena.capacity ||
      arena.cache_line_bytes != data.arena.cache_line_bytes ||
      arena.base_page_bytes != data.arena.base_page_bytes ||
      arena.master_seed != data.arena.master_seed ||
      arena.seed_namespace != data.arena.seed_namespace ||
      p.controls.workers.producer_stack.owner_cpu != data.producer_cpu ||
      p.controls.workers.producer_stack.requested_node != data.shared_node)
    throw std::invalid_argument("prospective pilot data/worker request differs");
  const bool linked = service.package == protocol::QueuePackage::l0 ||
                      service.package == protocol::QueuePackage::l1;
  if (linked &&
      (!service.linked_order ||
       service.linked_order->master_seed != data.node_order.master_seed ||
       service.linked_order->seed_namespace != data.node_order.seed_namespace ||
       service.linked_order->arena_alignment_bytes !=
           data.node_order.arena_alignment_bytes))
    throw std::invalid_argument("prospective pilot shared node-order request differs");
  const auto shared = mapped_pilot_data_layout(data);
  return dispatch(p, [&]<typename T> {
    return native_capture_detail::ServiceEnvelope<T>::size_layout(
               p, T::prospective_worker_layout(p),
               {shared.records_bytes, shared.queues_bytes})
        .public_layout;
  });
}
auto run_native_pilot_capture(const NativePilotCapturePlan& p,
                              NativePilotPublication publication)
    -> NativePilotCaptureResult {
  return dispatch(p, [&]<typename T> {
    return native_capture_detail::ServiceEnvelope<T>::run(p, publication);
  });
}
} // namespace cpu_prefetch::calibration
