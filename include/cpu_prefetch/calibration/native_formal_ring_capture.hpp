#ifndef CPU_PREFETCH_CALIBRATION_NATIVE_FORMAL_RING_CAPTURE_HPP
#define CPU_PREFETCH_CALIBRATION_NATIVE_FORMAL_RING_CAPTURE_HPP

#include "cpu_prefetch/calibration/mapped_formal_ring_runtime.hpp"

namespace cpu_prefetch::calibration {

enum class NativeCaptureStop : std::uint8_t {
  not_started,
  controller_start_failure,
  controller_preparation_failure,
  mapping_failure,
  clock_failure,
  tls_footprint_failure,
  thread_monitor_failure,
  hardware_monitor_failure,
  environment_monitor_failure,
  observation_setup_failure,
  capture_failed,
  publication_failed,
  cleanup_failed,
  exception,
  complete,
};

// Common cold lifetime/evidence shape; each typed lifecycle retains its own
// result. This is not an admission or scientific-validity report.
template <typename Session> struct NativeCaptureResult final {
  NativeCaptureStop stop{NativeCaptureStop::not_started};
  std::optional<Session> session;
  std::optional<timing::AbsoluteClockReadResult> clock_origin;
  platform::OwnerMappingEvidence core_mapping{};
  platform::OwnerMappingEvidence monitor_mapping{};
  platform::WorkerStackEvidence controller_stack{};
  std::optional<std::array<platform::OwnerMappingEvidence, 3U>> worker_mappings;
  std::optional<std::array<platform::WorkerStackEvidence, 2U>> worker_stacks;
  bool publication_attempted{false};
  bool publication_succeeded{false};
};
using NativeFormalRingCaptureResult = NativeCaptureResult<ServiceSessionResult>;

struct NativeFormalRingCaptureLayout final {
  MappedFormalRingLayout workers;
  std::size_t core_bytes;
  std::size_t monitor_bytes;
  std::size_t total_mapping_bytes; // Includes three guard pages.
  std::array<std::size_t, kNativeCaptureRegions> region_bytes;
};

struct NativeCaptureObservationView final {
  std::span<const DiscoveryResidencyRegion> regions;
  std::span<const DiscoveryResidencySample> residency;
  std::span<const DiscoveryControlSample> controls;
  std::array<std::span<const platform::ThreadTlsModule>, 6U> tls_modules;
  std::array<platform::ThreadTlsSnapshot, 6U> tls_snapshots;
  const platform::PrefetchReadbackPreparation& hardware;
  std::array<const platform::ThreadMonitorPreparation*, 2U> thread_preparations;
  std::span<const std::byte> core;
  std::span<const std::byte> monitor_arena;
  std::array<const platform::OwnerMappingEvidence*, 3U> worker_mappings{};
  std::array<const platform::WorkerStackEvidence*, 2U> worker_stacks{};
  std::array<MappedDiscoveryPreparationStop, 2U> worker_preparation{};
  std::array<platform::ThreadMonitorScratch, 2U> thread_preparation_scratch{};
  std::span<const platform::FileSnapshotPreparation> environment_preparations{};
  // Source-major, six retained groups per source, including failures/not-requested.
  std::span<const platform::FileSnapshotSample> environment_samples{};
};

struct NativeFormalRingPublicationView final {
  const NativeFormalRingCaptureResult& result;
  const NativeFormalRingCaptureLayout& layout;
  NativeCaptureObservationView observations;
  std::array<const FormalRingProducerPhase*, 2U> producer{};
  std::array<const FormalRingConsumerPhase*, 2U> consumer{};
  const workload::EventArena* arena{nullptr};
};
struct NativeFormalRingPublication final {
  void* context;
  // Always after worker join, before map release, including failed captures
  // once core construction succeeds. Publish raw snapshots/current failures.
  // No returned pointer survives this synchronous callback.
  bool (*publish)(void*, const NativeFormalRingPublicationView&) noexcept;
};

[[nodiscard]] auto native_formal_ring_layout(const NativeFormalRingCapturePlan& plan)
    -> NativeFormalRingCaptureLayout;
[[nodiscard]] auto
run_native_formal_ring_capture(const NativeFormalRingCapturePlan& plan,
                               NativeFormalRingPublication publication)
    -> NativeFormalRingCaptureResult;

} // namespace cpu_prefetch::calibration
#endif
