#ifndef CPU_PREFETCH_CALIBRATION_FORMAL_SERVICE_PLAN_HPP
#define CPU_PREFETCH_CALIBRATION_FORMAL_SERVICE_PLAN_HPP

#include "cpu_prefetch/calibration/native_capture_plan.hpp"

namespace cpu_prefetch::calibration {
struct FormalServicePhaseCapacity final {
  std::uint64_t producer_primary_rows;
  std::uint64_t consumer_primary_rows;
};
struct FormalLinkedOrderPlan final {
  workload::MasterSeed master_seed;
  std::string seed_namespace;
  std::size_t arena_alignment_bytes;
};
struct FormalRingDistancePlan final {
  std::size_t cache_lines;
  // R1: empty, the registered one-line policy. R2: accepted prior evidence ID.
  std::string calibration_evidence_id;
};
struct MappedFormalServicePlan final {
  protocol::QueuePackage package;
  ServiceSessionPlan session;
  workload::EventArenaConfig arena;
  std::array<protocol::RunId, 2U> run_ids;
  workload::ConsumerState initial_consumer;
  std::array<FormalServicePhaseCapacity, 2U> capacity;
  std::optional<FormalLinkedOrderPlan> linked_order;
  std::optional<FormalRingDistancePlan> ring_distance;
};
struct NativeFormalServiceCapturePlan final {
  MappedFormalServicePlan service;
  NativeCaptureControlPlan controls;
  std::string software_prefetch_mapping_id;
};
} // namespace cpu_prefetch::calibration
#endif
