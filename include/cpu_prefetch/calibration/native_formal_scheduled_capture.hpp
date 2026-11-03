#ifndef CPU_PREFETCH_CALIBRATION_NATIVE_FORMAL_SCHEDULED_CAPTURE_HPP
#define CPU_PREFETCH_CALIBRATION_NATIVE_FORMAL_SCHEDULED_CAPTURE_HPP

#include "cpu_prefetch/calibration/formal_scheduled_plan.hpp"
#include "cpu_prefetch/calibration/native_formal_service_capture.hpp"

namespace cpu_prefetch::calibration {

using NativeFormalScheduledCaptureResult = NativeCaptureResult<ScheduledSessionResult>;
struct NativeFormalScheduledCaptureLayout final {
  MappedFormalServiceLayout workers;
  std::size_t core_bytes;
  std::size_t monitor_bytes;
  std::size_t total_mapping_bytes;
  std::array<std::size_t, kNativeCaptureRegions> region_bytes;
};
struct NativeFormalScheduledPublicationView final {
  const NativeFormalScheduledCaptureResult& result;
  const NativeFormalScheduledCaptureLayout& layout;
  NativeCaptureObservationView observations;
  std::array<const FormalServiceProducerPhase*, 2U> producer{};
  std::array<const FormalServiceConsumerPhase*, 2U> consumer{};
  const workload::EventArena* arena{nullptr};
  std::span<const std::size_t> node_order{};
  // Present only after successful owner preparation. These are the prepared mapped
  // arrays; lifecycle evidence separately states whether execution began. They remain
  // in their original source clock coordinates.
  std::array<std::optional<lifecycle::PreparedScheduleView>, 2U> schedules{};
};
struct NativeFormalScheduledPublication final {
  void* context;
  bool (*publish)(void*, const NativeFormalScheduledPublicationView&) noexcept;
};
[[nodiscard]] auto
native_formal_scheduled_layout(const NativeFormalScheduledCapturePlan& plan)
    -> NativeFormalScheduledCaptureLayout;
[[nodiscard]] auto
run_native_formal_scheduled_capture(const NativeFormalScheduledCapturePlan& plan,
                                    NativeFormalScheduledPublication publication)
    -> NativeFormalScheduledCaptureResult;

} // namespace cpu_prefetch::calibration
#endif
