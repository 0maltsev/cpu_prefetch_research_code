#ifndef CPU_PREFETCH_CALIBRATION_NATIVE_FORMAL_SERVICE_CAPTURE_HPP
#define CPU_PREFETCH_CALIBRATION_NATIVE_FORMAL_SERVICE_CAPTURE_HPP

#include "cpu_prefetch/calibration/mapped_formal_service_preparation.hpp"
#include "cpu_prefetch/calibration/native_formal_ring_capture.hpp"

namespace cpu_prefetch::calibration {

template <protocol::QueuePackage Kind, typename Emitter>
struct FormalServiceRuntimePolicy final {
  using Plan = MappedFormalServicePlan;
  using Layout = MappedFormalServiceLayout;
  using SessionStorage = ServiceSessionStorage;
  using SessionResult = ServiceSessionResult;
  static auto base_plan(const Plan& plan) noexcept -> const Plan& { return plan; }
  static auto base_plan(const Plan&&) -> const Plan& = delete;
  template <typename Operations, typename Relax>
  using Provider = MappedFormalServicePreparation<Kind, Emitter, Operations, Relax>;
  template <typename Clock, typename Preparation>
  using Backend = FormalServiceSessionBackend<Clock, Preparation>;
  static auto layout(const Plan& plan) -> Layout {
    return mapped_formal_service_layout<Kind, Emitter>(plan);
  }
  template <typename Clock, typename Preparation>
  static auto make_backend(const Plan& plan, Clock& clock, Preparation& prep)
      -> Backend<Clock, Preparation> {
    return {plan.session, clock, prep};
  }
  template <typename Clock, typename Preparation, typename Relax, typename Observer,
            typename Threads>
  static auto run(const Plan&, Backend<Clock, Preparation>& backend, Preparation&,
                  Relax& relax, Observer& observer, Threads& threads,
                  ServiceSessionStorage& storage) -> ServiceSessionResult {
    return run_formal_service_session(backend, relax, observer, threads, storage);
  }
};

using NativeFormalServiceCaptureResult = NativeCaptureResult<ServiceSessionResult>;
struct NativeFormalServiceCaptureLayout final {
  MappedFormalServiceLayout workers;
  std::size_t core_bytes;
  std::size_t monitor_bytes;
  std::size_t total_mapping_bytes;
  std::array<std::size_t, kNativeCaptureRegions> region_bytes;
};
struct NativeFormalServicePublicationView final {
  const NativeFormalServiceCaptureResult& result;
  const NativeFormalServiceCaptureLayout& layout;
  NativeCaptureObservationView observations;
  std::array<const FormalServiceProducerPhase*, 2U> producer{};
  std::array<const FormalServiceConsumerPhase*, 2U> consumer{};
  const workload::EventArena* arena{nullptr};
  std::span<const std::size_t> node_order{};
};
struct NativeFormalServicePublication final {
  void* context;
  bool (*publish)(void*, const NativeFormalServicePublicationView&) noexcept;
};
[[nodiscard]] auto
native_formal_service_layout(const NativeFormalServiceCapturePlan& plan)
    -> NativeFormalServiceCaptureLayout;
[[nodiscard]] auto
run_native_formal_service_capture(const NativeFormalServiceCapturePlan& plan,
                                  NativeFormalServicePublication publication)
    -> NativeFormalServiceCaptureResult;
} // namespace cpu_prefetch::calibration
#endif
