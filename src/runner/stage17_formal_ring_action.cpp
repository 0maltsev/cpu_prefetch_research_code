#include "cpu_prefetch/runner/stage17_formal_ring_action.hpp"

#include "stage17_formal_input_detail.hpp"

namespace cpu_prefetch::runner::stage17 {
namespace {
using namespace formal_input_detail;
auto parse_capture(const Object& capture, const Object& resources,
                   const Object& monitoring,
                   std::span<const platform::HardwarePrefetchMsrValue> prestate,
                   bool verify_declared_layout)
    -> protocol::Result<calibration::NativeFormalRingCapturePlan> {
  try {
    fields(capture,
           {"schema_version", "ordinal", "context_ordinal", "repetition_ordinal",
            "method_id", "package", "hardware_state", "placement", "working_set_class",
            "warmup_ns", "measurement_ns", "minimum_observations_per_series",
            "geometry", "warmup", "measurement", "arena_seed", "seed_use", "budget"});
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
    const auto context = number(capture, "context_ordinal");
    static_cast<void>(number(capture, "repetition_ordinal"));
    constexpr std::array<std::string_view, 3U> classes{"L2_RESIDENT", "LLC_RESIDENT",
                                                       "BEYOND_LLC"};
    if (text(capture, "schema_version") !=
            "cpu-prefetch-stage17-formal-ring-capture/1" ||
        text(capture, "method_id") != calibration::kRingDistanceWindowMethodId ||
        text(capture, "package") != "R0" || context >= 12U ||
        number(resources, "ordinal") != ordinal ||
        number(monitoring, "ordinal") != ordinal ||
        number(capture, "warmup_ns") != 5'000'000'000U ||
        number(capture, "minimum_observations_per_series") == 0U ||
        text(capture, "hardware_state") != (context < 6U ? "H0" : "H1") ||
        text(capture, "placement") != ((context / 3U) % 2U == 0U ? "NEAR" : "FAR") ||
        text(capture, "working_set_class") != classes[context % 3U]) {
      throw std::invalid_argument("native formal ring identity/context differs");
    }
    const auto& geometry = object(capture, "geometry");
    fields(geometry, {"capacity", "cache_line_bytes", "base_page_bytes", "producer_cpu",
                      "consumer_cpu", "producer_node", "consumer_node", "shared_node"});
    const auto& budget = object(capture, "budget");
    fields(budget, {"phases", "barrier_poll_limit", "memory_bytes"});
    const auto& phases = array(budget, "phases", 2U);
    const auto& capacities = array(resources, "phase_capacity", 2U);
    calibration::ServiceSessionPlan session{{}, number(budget, "barrier_poll_limit")};
    std::array<calibration::FormalRingPhaseCapacity, 2U> capacity{};
    for (std::size_t i = 0U; i < 2U; ++i) {
      const auto* phase = phases[i].as_object();
      const auto* rows = capacities[i].as_object();
      if (phase == nullptr || rows == nullptr) {
        throw std::invalid_argument("formal phase bounds must be objects");
      }
      fields(*phase, {"producer_attempt_limit", "consumer_poll_limit", "drain_ns"});
      fields(*rows, {"producer_primary_rows", "consumer_primary_rows",
                     "producer_demand_rows", "consumer_demand_rows"});
      session.phases[i] = {
          ticks(number(capture, i == 0U ? "warmup_ns" : "measurement_ns")),
          number(*phase, "producer_attempt_limit"),
          number(*phase, "consumer_poll_limit"), ticks(number(*phase, "drain_ns"))};
      capacity[i] = {number(*rows, "producer_primary_rows"),
                     number(*rows, "consumer_primary_rows"),
                     number(*rows, "producer_demand_rows"),
                     number(*rows, "consumer_demand_rows")};
    }
    const auto minimum = number(capture, "minimum_observations_per_series");
    if (!calibration::valid_service_plan(session) ||
        minimum >= session.phases[1U].producer_attempt_limit ||
        minimum >= session.phases[1U].consumer_poll_limit) {
      throw std::invalid_argument(
          "formal phase limits cannot support required issue observations");
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
    calibration::NativeFormalRingCapturePlan result{
        {session,
         {size(geometry, "capacity"), size(geometry, "cache_line_bytes"),
          size(geometry, "base_page_bytes"),
          workload::MasterSeed::from_hex(text(measurement, "seed_hex")),
          text(measurement, "namespace_id")},
         {run_id(warmup), run_id(measurement)},
         {number(resources, "initial_consumer_state")},
         capacity},
        parse_controls(capture, resources, monitoring, prestate)};
    const auto layout = calibration::native_formal_ring_layout(result);
    check_layout(layout, resources, budget, verify_declared_layout);
    return protocol::Result<calibration::NativeFormalRingCapturePlan>::success(result);
  } catch (const std::exception& error) {
    return protocol::Result<calibration::NativeFormalRingCapturePlan>::failure(
        {protocol::ErrorCategory::cross_field, "$/formal/ring_capture",
         "S17-FORMAL-RING-PLAN", error.what()});
  }
}
} // namespace

auto parse_native_formal_ring_capture(
    const Object& capture, const Object& resources, const Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeFormalRingCapturePlan> {
  return parse_capture(capture, resources, monitoring, prestate, true);
}

auto describe_native_formal_ring_layout(
    const Object& capture, const Object& resources, const Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeFormalRingCaptureLayout> {
  const auto parsed = parse_capture(capture, resources, monitoring, prestate, false);
  if (!parsed) {
    return protocol::Result<calibration::NativeFormalRingCaptureLayout>::failure(
        parsed.errors());
  }
  return protocol::Result<calibration::NativeFormalRingCaptureLayout>::success(
      calibration::native_formal_ring_layout(parsed.value()));
}
} // namespace cpu_prefetch::runner::stage17
