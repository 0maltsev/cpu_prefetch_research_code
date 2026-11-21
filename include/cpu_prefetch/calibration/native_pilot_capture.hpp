#ifndef CPU_PREFETCH_CALIBRATION_NATIVE_PILOT_CAPTURE_HPP
#define CPU_PREFETCH_CALIBRATION_NATIVE_PILOT_CAPTURE_HPP
#include "cpu_prefetch/calibration/mapped_pilot_capture.hpp"
#include "cpu_prefetch/calibration/native_formal_ring_capture.hpp"

namespace cpu_prefetch::calibration {
inline constexpr std::size_t kNativePilotCaptureRegions = 9U;
struct NativePilotCaptureControlPlan final {
  DiscoveryRuntimePlacement workers;
  platform::OwnerMappingPlan controller_stack;
  std::size_t tls_module_capacity;
  std::size_t thread_stat_bytes;
  std::size_t thread_status_bytes;
  std::size_t thread_affinity_words;
  std::array<std::size_t, kNativePilotCaptureRegions> during_first_page;
  std::array<std::size_t, kNativePilotCaptureRegions> during_page_count;
  std::array<std::uint64_t, 2U> during_offset_ticks;
  std::uint64_t observer_wait_poll_limit;
  std::size_t control_region_index;
  std::array<std::array<DiscoveryDisturbanceLimits, 2U>, 2U> counter_limits;
  platform::CpuFamilyModel hardware_identity;
  protocol::RequestedHardwareState hardware_state;
  std::span<const platform::HardwarePrefetchMsrValue> hardware_prestate;
  std::vector<platform::FileSnapshotPlan> environment_sources;
};
struct NativePilotCapturePlan final {
  MappedPilotCapturePlan capture;
  NativePilotCaptureControlPlan controls;
  std::string software_prefetch_mapping_id;
};
using NativePilotCaptureResult = NativeCaptureResult<PilotLifecycleResult>;
struct NativePilotCaptureLayout final {
  PilotPrivateLayout workers;
  std::size_t core_bytes, monitor_bytes, total_mapping_bytes;
  std::array<std::size_t, kNativePilotCaptureRegions> region_bytes;
};
struct NativePilotPublicationView final {
  const NativePilotCaptureResult& result;
  const NativePilotCaptureLayout& layout;
  NativeCaptureObservationView observations;
  PreparedPilotDataView shared;
  std::array<const FormalServiceProducerPhase*, 2U> producer{};
  std::array<const FormalServiceConsumerPhase*, 2U> consumer{};
  std::array<std::optional<lifecycle::PreparedScheduleView>, 2U> schedules{};
};
struct NativePilotPublication final {
  void* context;
  bool (*publish)(void*, const NativePilotPublicationView&) noexcept;
};
[[nodiscard]] auto native_pilot_layout(const NativePilotCapturePlan&)
    -> NativePilotCaptureLayout;
// Size from explicit declared metadata only. No live view, memory mapping,
// source-vector allocation, address-pattern verification or hardware claim.
[[nodiscard]] auto prospective_native_pilot_layout(const NativePilotCapturePlan&,
                                                   const MappedPilotDataPlan&)
    -> NativePilotCaptureLayout;
[[nodiscard]] auto run_native_pilot_capture(const NativePilotCapturePlan&,
                                            NativePilotPublication)
    -> NativePilotCaptureResult;
} // namespace cpu_prefetch::calibration
#endif
