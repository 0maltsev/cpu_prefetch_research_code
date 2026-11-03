#include "cpu_prefetch/runner/stage17_formal_service_action.hpp"

#include "stage17_formal_input_detail.hpp"

namespace cpu_prefetch::runner::stage17 {
namespace {
using namespace formal_input_detail;
auto parse_capture(const Object& capture, const Object& resources,
                   const Object& monitoring,
                   std::span<const platform::HardwarePrefetchMsrValue> prestate,
                   bool verify_declared_layout)
    -> protocol::Result<calibration::NativeFormalServiceCapturePlan> {
  try {
    fields(capture, {"schema_version",    "ordinal",
                     "cell_ordinal",      "repetition_ordinal",
                     "method_id",         "package",
                     "hardware_state",    "placement",
                     "working_set_class", "warmup_ns",
                     "measurement_ns",    "software_prefetch_mapping_id",
                     "linked_order",      "ring_distance",
                     "geometry",          "warmup",
                     "measurement",       "arena_seed",
                     "seed_use",          "budget"});
    fields(resources,
           {"ordinal", "workers", "controller_stack", "core_bytes", "monitor_bytes",
            "total_mapping_bytes", "region_bytes", "tls_module_capacity",
            "thread_stat_bytes", "thread_status_bytes", "thread_affinity_words",
            "initial_consumer_state", "phase_capacity"});
    fields(monitoring,
           {"ordinal", "during_first_page", "during_page_count", "during_offset_ticks",
            "observer_wait_poll_limit", "control_region_index", "counter_limits",
            "hardware_identity", "environment_sources"});
    const auto ordinal = number(capture, "ordinal");
    const auto cell = number(capture, "cell_ordinal");
    const auto context = cell % 12U;
    constexpr std::array packages{
        protocol::QueuePackage::r0, protocol::QueuePackage::r1,
        protocol::QueuePackage::r2, protocol::QueuePackage::l0,
        protocol::QueuePackage::l1};
    constexpr std::array<std::string_view, 5U> names{"R0", "R1", "R2", "L0", "L1"};
    static_cast<void>(number(capture, "repetition_ordinal"));
    constexpr std::array<std::string_view, 3U> classes{"L2_RESIDENT", "LLC_RESIDENT",
                                                       "BEYOND_LLC"};
    if (text(capture, "schema_version") !=
            "cpu-prefetch-stage17-formal-service-capture/1" ||
        text(capture, "method_id") != calibration::kServiceRateMethodId ||
        cell >= 60U || text(capture, "package") != names[cell / 12U] ||
        number(resources, "ordinal") != ordinal ||
        number(monitoring, "ordinal") != ordinal ||
        number(capture, "warmup_ns") != 5'000'000'000U ||
        text(capture, "hardware_state") != (context < 6U ? "H0" : "H1") ||
        text(capture, "placement") != ((context / 3U) % 2U == 0U ? "NEAR" : "FAR") ||
        text(capture, "working_set_class") != classes[context % 3U]) {
      throw std::invalid_argument("native formal service identity/context differs");
    }
    const auto& geometry = object(capture, "geometry");
    fields(geometry, {"capacity", "cache_line_bytes", "base_page_bytes", "producer_cpu",
                      "consumer_cpu", "producer_node", "consumer_node", "shared_node"});
    const auto& budget = object(capture, "budget");
    fields(budget, {"phases", "barrier_poll_limit", "memory_bytes"});
    const auto& phases = array(budget, "phases", 2U);
    const auto& capacities = array(resources, "phase_capacity", 2U);
    calibration::ServiceSessionPlan session{{}, number(budget, "barrier_poll_limit")};
    std::array<calibration::FormalServicePhaseCapacity, 2U> capacity{};
    for (std::size_t i = 0U; i < 2U; ++i) {
      const auto* phase = phases[i].as_object();
      const auto* rows = capacities[i].as_object();
      if (phase == nullptr || rows == nullptr) {
        throw std::invalid_argument("formal phase bounds must be objects");
      }
      fields(*phase, {"producer_attempt_limit", "consumer_poll_limit", "drain_ns"});
      fields(*rows, {"producer_primary_rows", "consumer_primary_rows"});
      session.phases[i] = {
          ticks(number(capture, i == 0U ? "warmup_ns" : "measurement_ns")),
          number(*phase, "producer_attempt_limit"),
          number(*phase, "consumer_poll_limit"), ticks(number(*phase, "drain_ns"))};
      capacity[i] = {number(*rows, "producer_primary_rows"),
                     number(*rows, "consumer_primary_rows")};
    }
    if (!calibration::valid_service_plan(session)) {
      throw std::invalid_argument("invalid formal service phase bounds");
    }
    const auto& warmup = object(capture, "warmup");
    const auto& measurement = object(capture, "measurement");
    phase_identity(warmup);
    phase_identity(measurement);
    static_cast<void>(workload::MasterSeed::from_hex(text(warmup, "seed_hex")));
    if (object(capture, "arena_seed") != measurement ||
        text(capture, "seed_use") !=
            "ONE_PERSISTENT_ARENA_MEASUREMENT_SEED_WARMUP_RESERVED_NO_DRAWS" ||
        text(warmup, "run_id") == text(measurement, "run_id") ||
        text(warmup, "seed_id") == text(measurement, "seed_id") ||
        text(warmup, "namespace_id") == text(measurement, "namespace_id") ||
        text(warmup, "seed_hex") == text(measurement, "seed_hex")) {
      throw std::invalid_argument(
          "native persistent-arena seed or phase identity differs");
    }
    std::optional<calibration::FormalLinkedOrderPlan> linked;
    if (!member(capture, "linked_order").is_null()) {
      const auto& item = object(capture, "linked_order");
      fields(item, {"seed_id", "seed_hex", "namespace_id", "arena_alignment_bytes"});
      static_cast<void>(opaque_text(item, "seed_id"));
      linked.emplace(workload::MasterSeed::from_hex(seed_text(item)),
                     opaque_text(item, "namespace_id"),
                     size(item, "arena_alignment_bytes"));
    }
    std::optional<calibration::FormalRingDistancePlan> distance;
    if (!member(capture, "ring_distance").is_null()) {
      const auto& item = object(capture, "ring_distance");
      fields(item, {"cache_lines", "calibration_evidence_id"});
      const auto* evidence = member(item, "calibration_evidence_id").as_string();
      if (evidence == nullptr)
        throw std::invalid_argument("ring distance evidence must be a string");
      if (!evidence->empty())
        static_cast<void>(opaque_text(item, "calibration_evidence_id"));
      distance.emplace(size(item, "cache_lines"), *evidence);
    }
    calibration::NativeFormalServiceCapturePlan result{
        {packages[cell / 12U],
         session,
         {size(geometry, "capacity"), size(geometry, "cache_line_bytes"),
          size(geometry, "base_page_bytes"),
          workload::MasterSeed::from_hex(text(measurement, "seed_hex")),
          text(measurement, "namespace_id")},
         {run_id(warmup), run_id(measurement)},
         {number(resources, "initial_consumer_state")},
         capacity,
         std::move(linked),
         std::move(distance)},
        parse_controls(capture, resources, monitoring, prestate),
        opaque_text(capture, "software_prefetch_mapping_id")};
    const auto layout = calibration::native_formal_service_layout(result);
    check_layout(layout, resources, budget, verify_declared_layout);
    return protocol::Result<calibration::NativeFormalServiceCapturePlan>::success(
        result);
  } catch (const std::exception& error) {
    return protocol::Result<calibration::NativeFormalServiceCapturePlan>::failure(
        {protocol::ErrorCategory::cross_field, "$/formal/service_capture",
         "S17-FORMAL-SERVICE-PLAN", error.what()});
  }
}
} // namespace

auto parse_native_formal_service_capture(
    const Object& capture, const Object& resources, const Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeFormalServiceCapturePlan> {
  return parse_capture(capture, resources, monitoring, prestate, true);
}

auto describe_native_formal_service_layout(
    const Object& capture, const Object& resources, const Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeFormalServiceCaptureLayout> {
  const auto parsed = parse_capture(capture, resources, monitoring, prestate, false);
  if (!parsed) {
    return protocol::Result<calibration::NativeFormalServiceCaptureLayout>::failure(
        parsed.errors());
  }
  return protocol::Result<calibration::NativeFormalServiceCaptureLayout>::success(
      calibration::native_formal_service_layout(parsed.value()));
}
} // namespace cpu_prefetch::runner::stage17
