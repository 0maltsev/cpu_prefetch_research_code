#ifndef CPU_PREFETCH_CALIBRATION_NATIVE_CAPTURE_PLAN_HPP
#define CPU_PREFETCH_CALIBRATION_NATIVE_CAPTURE_PLAN_HPP

#include "cpu_prefetch/calibration/discovery_control_query.hpp"
#include "cpu_prefetch/calibration/mapped_discovery_runtime.hpp"
#include "cpu_prefetch/calibration/service_session.hpp"
#include "cpu_prefetch/platform/prepared_file_snapshot.hpp"

#include <vector>

namespace cpu_prefetch::calibration {

// Explicit prospective bounds, independent from the session watchdog counts.
// Consumer demand includes every empty/item poll through terminal drain.
struct FormalRingPhaseCapacity final {
  std::uint64_t producer_primary_rows;
  std::uint64_t consumer_primary_rows;
  std::uint64_t producer_demand_rows;
  std::uint64_t consumer_demand_rows;
};

struct MappedFormalRingPlan final {
  ServiceSessionPlan session;
  workload::EventArenaConfig arena;
  std::array<protocol::RunId, 2U> run_ids;
  workload::ConsumerState initial_consumer;
  std::array<FormalRingPhaseCapacity, 2U> capacity;
};

// Shared cold control envelope for typed formal backends. No empirical defaults,
// qualification or execution authority. Seven observed regions: records,
// producer-private, consumer-private, two worker stacks, core and controller
// stack. Monitor scratch is controller-owned and excluded from worker targets.
// All paths/prestate remain live for the synchronous native invocation.
inline constexpr std::size_t kNativeCaptureRegions = 7U;
struct NativeCaptureControlPlan final {
  DiscoveryRuntimePlacement workers;
  platform::OwnerMappingPlan controller_stack;
  std::size_t tls_module_capacity;
  std::size_t thread_stat_bytes;
  std::size_t thread_status_bytes;
  std::size_t thread_affinity_words;
  std::array<std::size_t, kNativeCaptureRegions> during_first_page;
  std::array<std::size_t, kNativeCaptureRegions> during_page_count;
  std::array<std::uint64_t, 2U> during_offset_ticks;
  std::uint64_t observer_wait_poll_limit;
  std::size_t control_region_index;
  std::array<std::array<DiscoveryDisturbanceLimits, 2U>, 2U> counter_limits;
  platform::CpuFamilyModel hardware_identity;
  protocol::RequestedHardwareState hardware_state;
  std::span<const platform::HardwarePrefetchMsrValue> hardware_prestate;
  std::vector<platform::FileSnapshotPlan> environment_sources;
};

struct NativeFormalRingCapturePlan final {
  MappedFormalRingPlan ring;
  NativeCaptureControlPlan controls;
};

} // namespace cpu_prefetch::calibration
#endif
