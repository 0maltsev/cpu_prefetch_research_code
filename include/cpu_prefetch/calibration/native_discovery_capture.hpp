#ifndef CPU_PREFETCH_CALIBRATION_NATIVE_DISCOVERY_CAPTURE_HPP
#define CPU_PREFETCH_CALIBRATION_NATIVE_DISCOVERY_CAPTURE_HPP

#include "cpu_prefetch/calibration/discovery_control_query.hpp"
#include "cpu_prefetch/calibration/mapped_discovery_runtime.hpp"
#include "cpu_prefetch/platform/prepared_file_snapshot.hpp"

#include <vector>

namespace cpu_prefetch::calibration {

// records, producer-private, consumer-private, producer-stack, consumer-stack,
// runtime core/TLS output, controller-stack. Monitor arena is separately owned
// controller scratch, deliberately excluded from these residency targets.
inline constexpr std::size_t kNativeDiscoveryRegions = 7U;
inline constexpr std::size_t kNativeDiscoveryObservations =
    6U * kNativeDiscoveryRegions;

struct NativeDiscoveryCapturePlan final {
  MappedDiscoveryPlan discovery;
  DiscoveryRuntimePlacement workers;
  platform::OwnerMappingPlan controller_stack;
  std::size_t tls_module_capacity;
  std::size_t thread_stat_bytes;
  std::size_t thread_status_bytes;
  std::size_t thread_affinity_words;
  std::array<std::size_t, kNativeDiscoveryRegions> during_first_page;
  std::array<std::size_t, kNativeDiscoveryRegions> during_page_count;
  std::array<std::uint64_t, 2U> during_offset_ticks;
  std::uint64_t observer_wait_poll_limit;
  std::size_t control_region_index;
  std::array<std::array<DiscoveryDisturbanceLimits, 2U>, 2U> counter_limits;
  platform::CpuFamilyModel hardware_identity;
  protocol::RequestedHardwareState hardware_state;
  std::span<const platform::HardwarePrefetchMsrValue> hardware_prestate;
  // Cold plan only. Paths remain borrowed until the synchronous call returns;
  // native preparation freezes copies and all six retained outputs in monitor memory.
  std::vector<platform::FileSnapshotPlan> environment_sources{};
};

struct NativeDiscoveryCaptureLayout final {
  MappedDiscoveryLayout workers;
  std::size_t core_bytes;
  std::size_t monitor_bytes;
  std::size_t total_mapping_bytes; // Includes three guard pages.
  std::array<std::size_t, kNativeDiscoveryRegions> region_bytes;
};

enum class NativeDiscoveryCaptureStop : std::uint8_t {
  not_started,
  controller_start_failure,
  controller_preparation_failure,
  mapping_failure,
  clock_failure,
  tls_footprint_failure,
  thread_monitor_failure,
  hardware_monitor_failure,
  observation_setup_failure,
  capture_failed,
  publication_failed,
  cleanup_failed,
  exception,
  complete,
  environment_monitor_failure,
  trace_capacity,
};

struct NativeDiscoveryCaptureResult final {
  NativeDiscoveryCaptureStop stop{NativeDiscoveryCaptureStop::not_started};
  std::optional<DiscoverySessionResult> session;
  std::optional<timing::AbsoluteClockReadResult> clock_origin;
  platform::OwnerMappingEvidence core_mapping{};
  platform::OwnerMappingEvidence monitor_mapping{};
  platform::WorkerStackEvidence controller_stack{};
  std::optional<std::array<platform::OwnerMappingEvidence, 3U>> worker_mappings;
  std::optional<std::array<platform::WorkerStackEvidence, 2U>> worker_stacks;
  bool publication_attempted{false};
  bool publication_succeeded{false};
};

struct NativeDiscoveryPublicationView final {
  const NativeDiscoveryCaptureResult& result;
  const NativeDiscoveryCaptureLayout& layout;
  std::span<const DiscoveryResidencyRegion> regions;
  std::span<const DiscoveryResidencySample> residency;
  std::span<const DiscoveryControlSample> controls;
  std::array<std::span<const platform::ThreadTlsModule>, 6U> tls_modules;
  std::array<platform::ThreadTlsSnapshot, 6U> tls_snapshots;
  const platform::PrefetchReadbackPreparation& hardware;
  std::array<const platform::ThreadMonitorPreparation*, 2U> thread_preparations;
  std::array<const MappedProducerPhase*, 2U> producer;
  std::array<const MappedConsumerPhase*, 2U> consumer;
  std::span<const std::byte> core;
  std::span<const std::byte> monitor_arena;
  const workload::EventArena* arena{nullptr};
  std::array<const platform::OwnerMappingEvidence*, 3U> worker_mappings{};
  std::array<const platform::WorkerStackEvidence*, 2U> worker_stacks{};
  std::array<MappedDiscoveryPreparationStop, 2U> worker_preparation{};
  std::array<platform::ThreadMonitorScratch, 2U> thread_preparation_scratch{};
  // Preparation per source; samples ordered source*6 + phase*3 + moment.
  // Includes failed/unrequested observations. Raw delivery is not page-policy
  // or environmental validity; an independent validator must parse these bytes.
  std::span<const platform::FileSnapshotPreparation> environment_preparations{};
  std::span<const platform::FileSnapshotSample> environment_samples{};
};

namespace native_discovery_detail {

// Software-only classification seam. Trace exhaustion is retained insufficient
// data only after measurement and every mandatory session observation finished.
// Subsequent native cleanup/publication can still replace this provisional stop.
[[nodiscard]] auto session_stop(const DiscoverySessionResult& session) noexcept
    -> NativeDiscoveryCaptureStop;
[[nodiscard]] auto after_cleanup(NativeDiscoveryCaptureStop stop, bool succeeded,
                                 NativeDiscoveryCaptureStop failure) noexcept
    -> NativeDiscoveryCaptureStop;

// No additional scheduler: the existing observer brackets controls, then these
// non-atomic raw reads, then page queries with its actual clock observations.
// The template seam permits software tests without native hardware access.
template <typename Controls> class EnvironmentQuery final {
public:
  EnvironmentQuery(Controls& controls,
                   std::span<platform::PreparedFileSnapshot> sources) noexcept
      : controls_(controls), sources_(sources) {}

  auto observe_controls(DiscoveryResidencyRequest request) noexcept
      -> DiscoveryObservationStatus {
    const auto control = controls_.observe_controls(request);
    if (control == DiscoveryObservationStatus::not_configured ||
        request.phase > DiscoverySessionPhase::measurement ||
        request.moment > DiscoveryResidencyMoment::after) {
      return control;
    }
    const auto group = static_cast<std::size_t>(request.phase) * 3U +
                       static_cast<std::size_t>(request.moment);
    if (attempted_[group]) {
      return DiscoveryObservationStatus::rejected;
    }
    attempted_[group] = true;
    bool complete = true;
    // Sample every source even when controls or an earlier source failed.
    for (auto& source : sources_) {
      const auto observed = source.sample(group);
      if (observed != platform::FileSnapshotStop::complete &&
          observed != platform::FileSnapshotStop::not_requested) {
        complete = false;
      }
    }
    complete_[group] = complete && control == DiscoveryObservationStatus::accepted;
    return complete_[group] ? DiscoveryObservationStatus::accepted
                            : DiscoveryObservationStatus::rejected;
  }
  auto control_group_complete(DiscoverySessionPhase phase,
                              DiscoveryResidencyMoment moment) const noexcept -> bool {
    if (phase > DiscoverySessionPhase::measurement ||
        moment > DiscoveryResidencyMoment::after) {
      return false;
    }
    const auto group =
        static_cast<std::size_t>(phase) * 3U + static_cast<std::size_t>(moment);
    return attempted_[group] && complete_[group] &&
           controls_.control_group_complete(phase, moment);
  }
  auto query_pages(std::span<void* const> addresses, std::span<int> nodes) noexcept
      -> platform::PageResidencyQueryResult {
    return controls_.query_pages(addresses, nodes);
  }

private:
  Controls& controls_;
  std::span<platform::PreparedFileSnapshot> sources_;
  std::array<bool, platform::kFileSnapshotGroups> attempted_{};
  std::array<bool, platform::kFileSnapshotGroups> complete_{};
};

} // namespace native_discovery_detail

struct NativeDiscoveryPublication final {
  void* context;
  // Synchronous, after workers join, before any capture mapping is released.
  // Return false on publication failure. Copy/persist needed data in this call;
  // no pointer/span in the view survives it. Called for failed captures too
  // once core construction succeeds; phases may be null on partial preparation.
  bool (*publish)(void*, const NativeDiscoveryPublicationView&) noexcept;
};

// Pure checked arithmetic; rejects invalid geometry, finite budgets and offsets
// before any mapping or native hardware access. Allocating cold validation may
// throw invalid_argument/overflow_error. No platform-dependent defaults.
[[nodiscard]] auto native_discovery_layout(const NativeDiscoveryCapturePlan& plan)
    -> NativeDiscoveryCaptureLayout;

// Read-only TLS coverage check, also exposed for deterministic verification.
// Accepts only allocated PT_TLS payloads and FS base inside this owner's stack.
// Does NOT establish the complete TCB/DTV/allocator footprint or NUMA residency.
[[nodiscard]] auto
native_discovery_tls_covered(const platform::ThreadTlsSnapshot& snapshot,
                             std::span<const platform::ThreadTlsModule> modules,
                             std::span<const std::byte> owner_stack) noexcept -> bool;

// Actual native R0 composition: MonotonicRawClock, X86PauseRelax, native owner
// mappings/stacks, residency/thread/MSR observers. No admission bypass, fake
// switch, MSR writes, restoration, CLI or execution authority. Caller supplies
// admitted immutable seed/prestate/plan bindings and an outer watchdog. The
// same arena/order persists across both phases; this adds no arrival process.
[[nodiscard]] auto run_native_discovery_capture(const NativeDiscoveryCapturePlan& plan,
                                                NativeDiscoveryPublication publication)
    -> NativeDiscoveryCaptureResult;

} // namespace cpu_prefetch::calibration

#endif
