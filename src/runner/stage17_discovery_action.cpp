#include "cpu_prefetch/runner/stage17_discovery_action.hpp"

#include <limits>
#include <set>
#include <stdexcept>

namespace cpu_prefetch::runner::stage17 {
namespace {
using Value = protocol::json::Value;
using Object = Value::Object;

auto member(const Object& object, std::string_view key) -> const Value& {
  const auto found = object.find(key);
  if (found == object.end()) {
    throw std::invalid_argument("missing native discovery field: " + std::string(key));
  }
  return found->second;
}
auto object(const Object& parent, std::string_view key) -> const Object& {
  const auto* result = member(parent, key).as_object();
  if (result == nullptr) {
    throw std::invalid_argument("native discovery field is not an object");
  }
  return *result;
}
auto array(const Object& parent, std::string_view key, std::size_t count)
    -> const Value::Array& {
  const auto* result = member(parent, key).as_array();
  if (result == nullptr || result->size() != count) {
    throw std::invalid_argument("native discovery array length differs");
  }
  return *result;
}
auto number(const Value& value) -> std::uint64_t {
  const auto* result = value.as_number();
  if (result == nullptr ||
      result->kind != protocol::json::Number::Kind::unsigned_integer) {
    throw std::invalid_argument("native discovery requires an unsigned integer");
  }
  return std::get<std::uint64_t>(result->value);
}
auto number(const Object& parent, std::string_view key) -> std::uint64_t {
  return number(member(parent, key));
}
auto word(const Object& parent, std::string_view key) -> std::uint32_t {
  const auto value = number(parent, key);
  if (value > std::numeric_limits<std::uint32_t>::max()) {
    throw std::invalid_argument("native discovery CPU/node/identity overflows");
  }
  return static_cast<std::uint32_t>(value);
}
auto size(const Value& value) -> std::size_t {
  const auto result = number(value);
  if (result > std::numeric_limits<std::size_t>::max()) {
    throw std::invalid_argument("native discovery size overflows");
  }
  return static_cast<std::size_t>(result);
}
auto size(const Object& parent, std::string_view key) -> std::size_t {
  return size(member(parent, key));
}
auto text(const Object& parent, std::string_view key) -> const std::string& {
  const auto* result = member(parent, key).as_string();
  if (result == nullptr || result->empty()) {
    throw std::invalid_argument("native discovery requires nonempty text");
  }
  return *result;
}
auto ticks(std::uint64_t nanoseconds) -> std::uint64_t {
  if (nanoseconds == 0U ||
      nanoseconds > std::numeric_limits<std::uint64_t>::max() / 1000U) {
    throw std::invalid_argument("native discovery nanosecond duration overflows ticks");
  }
  return nanoseconds * 1000U;
}
void fields(const Object& value, std::initializer_list<std::string_view> expected) {
  if (value.size() != expected.size()) {
    throw std::invalid_argument("native discovery field set differs");
  }
  for (const auto field : expected) {
    static_cast<void>(member(value, field));
  }
}
auto stack(const Object& value) -> platform::OwnerMappingPlan {
  fields(value, {"bytes", "verified_base_page_bytes", "owner_cpu", "requested_node"});
  return {size(value, "bytes"), size(value, "verified_base_page_bytes"),
          word(value, "owner_cpu"), word(value, "requested_node")};
}
auto limit(const Value& value) -> std::optional<std::uint64_t> {
  return value.is_null() ? std::nullopt : std::optional(number(value));
}
auto limits(const Value& value) -> calibration::DiscoveryDisturbanceLimits {
  const auto* item = value.as_object();
  if (item == nullptr) {
    throw std::invalid_argument("native discovery counter limits missing");
  }
  fields(*item, {"minor_faults", "major_faults", "voluntary_switches",
                 "involuntary_switches"});
  return {limit(member(*item, "minor_faults")), limit(member(*item, "major_faults")),
          limit(member(*item, "voluntary_switches")),
          limit(member(*item, "involuntary_switches"))};
}
auto run_id(const Object& value) -> protocol::RunId {
  const auto parsed = protocol::RunId::parse(text(value, "run_id"), "$/capture/run_id");
  if (!parsed) {
    throw std::invalid_argument("invalid native discovery run ID");
  }
  return parsed.value();
}
auto parse_capture(const Object& capture, const Object& resources,
                   const Object& monitoring,
                   std::span<const platform::HardwarePrefetchMsrValue> prestate,
                   bool verify_declared_layout)
    -> protocol::Result<calibration::NativeDiscoveryCapturePlan> {
  try {
    fields(resources,
           {"ordinal", "workers", "controller_stack", "core_bytes", "monitor_bytes",
            "total_mapping_bytes", "region_bytes", "tls_module_capacity",
            "thread_stat_bytes", "thread_status_bytes", "thread_affinity_words",
            "initial_consumer_state"});
    fields(monitoring,
           {"ordinal", "during_first_page", "during_page_count", "during_offset_ticks",
            "observer_wait_poll_limit", "control_region_index", "counter_limits",
            "hardware_identity", "environment_sources"});
    const auto ordinal = number(capture, "ordinal");
    const auto duration = number(capture, "measurement_ns");
    constexpr std::array<std::uint64_t, 3U> durations{100'000'000U, 1'000'000'000U,
                                                      5'000'000'000U};
    constexpr std::array<std::string_view, 3U> classes{"L2_RESIDENT", "LLC_RESIDENT",
                                                       "BEYOND_LLC"};
    if (ordinal >= 36U || number(resources, "ordinal") != ordinal ||
        number(monitoring, "ordinal") != ordinal ||
        number(capture, "context_ordinal") != ordinal / 3U ||
        number(capture, "warmup_ns") != 5'000'000'000U ||
        duration != durations[ordinal % 3U] ||
        text(capture, "hardware_state") != (ordinal < 18U ? "H0" : "H1") ||
        text(capture, "placement") != ((ordinal / 9U) % 2U == 0U ? "NEAR" : "FAR") ||
        text(capture, "working_set_class") != classes[(ordinal / 3U) % 3U]) {
      throw std::invalid_argument(
          "native capture differs from the exact ordered D178 design");
    }
    const auto& geometry = object(capture, "geometry");
    const auto& budget = object(capture, "budget");
    const auto& warmup = object(capture, "warmup");
    const auto& measurement = object(capture, "measurement");
    if (object(capture, "arena_seed") != measurement ||
        text(capture, "seed_use") !=
            "ONE_PERSISTENT_ARENA_MEASUREMENT_SEED_WARMUP_RESERVED_NO_DRAWS" ||
        text(warmup, "run_id") == text(measurement, "run_id") ||
        text(warmup, "namespace_id") == text(measurement, "namespace_id") ||
        text(warmup, "seed_hex") == text(measurement, "seed_hex")) {
      throw std::invalid_argument(
          "native persistent-arena seed or phase identity differs");
    }
    const auto& workers = object(resources, "workers");
    fields(workers, {"producer_stack", "consumer_stack"});
    const auto producer = stack(object(workers, "producer_stack"));
    const auto consumer = stack(object(workers, "consumer_stack"));
    const auto controller = stack(object(resources, "controller_stack"));
    if (producer.owner_cpu != word(geometry, "producer_cpu") ||
        consumer.owner_cpu != word(geometry, "consumer_cpu") ||
        producer.requested_node != word(geometry, "producer_node") ||
        consumer.requested_node != word(geometry, "consumer_node") ||
        producer.owner_cpu == consumer.owner_cpu ||
        controller.owner_cpu == producer.owner_cpu ||
        controller.owner_cpu == consumer.owner_cpu ||
        word(geometry, "shared_node") != producer.requested_node ||
        (producer.requested_node == consumer.requested_node) !=
            (text(capture, "placement") == "NEAR")) {
      throw std::invalid_argument(
          "native capture owner geometry differs from declared context");
    }
    const auto& identity = object(monitoring, "hardware_identity");
    fields(identity, {"family", "model"});
    calibration::NativeDiscoveryCapturePlan result{
        {{ticks(number(capture, "warmup_ns")), ticks(duration),
          number(budget, "warmup_attempt_capacity"),
          number(budget, "measurement_attempt_capacity"),
          ticks(number(budget, "drain_ns")), number(budget, "drain_attempt_capacity"),
          number(budget, "barrier_poll_limit")},
         {size(geometry, "capacity"), size(geometry, "cache_line_bytes"),
          size(geometry, "base_page_bytes"),
          workload::MasterSeed::from_hex(text(measurement, "seed_hex")),
          text(measurement, "namespace_id")},
         {run_id(warmup), run_id(measurement)},
         {number(resources, "initial_consumer_state")}},
        {producer, consumer},
        controller,
        size(resources, "tls_module_capacity"),
        size(resources, "thread_stat_bytes"),
        size(resources, "thread_status_bytes"),
        size(resources, "thread_affinity_words"),
        {},
        {},
        {},
        number(monitoring, "observer_wait_poll_limit"),
        size(monitoring, "control_region_index"),
        {},
        {word(identity, "family"), word(identity, "model")},
        ordinal < 18U ? protocol::RequestedHardwareState::h0
                      : protocol::RequestedHardwareState::h1,
        prestate};
    const auto& first = array(monitoring, "during_first_page", 7U);
    const auto& count = array(monitoring, "during_page_count", 7U);
    const auto& offsets = array(monitoring, "during_offset_ticks", 2U);
    for (std::size_t index = 0U; index < 7U; ++index) {
      result.during_first_page[index] = size(first[index]);
      result.during_page_count[index] = size(count[index]);
    }
    const auto& bounds = array(monitoring, "counter_limits", 2U);
    for (std::size_t phase = 0U; phase < 2U; ++phase) {
      result.during_offset_ticks[phase] = number(offsets[phase]);
      const auto* owners = bounds[phase].as_array();
      if (owners == nullptr || owners->size() != 2U) {
        throw std::invalid_argument("native limits require two owners");
      }
      for (std::size_t role = 0U; role < 2U; ++role) {
        result.counter_limits[phase][role] = limits((*owners)[role]);
      }
    }
    const auto* sources = member(monitoring, "environment_sources").as_array();
    if (sources == nullptr) {
      throw std::invalid_argument("native environmental source list is absent");
    }
    std::set<std::string_view> paths;
    for (const auto& source : *sources) {
      const auto* item = source.as_object();
      if (item == nullptr) {
        throw std::invalid_argument("native environmental source is not an object");
      }
      fields(*item,
             {"path", "byte_capacity", "chunk_bytes", "max_data_reads", "requested"});
      platform::FileSnapshotPlan plan{text(*item, "path"),
                                      size(*item, "byte_capacity"),
                                      size(*item, "chunk_bytes"),
                                      size(*item, "max_data_reads"),
                                      {}};
      const auto& requested = array(*item, "requested", platform::kFileSnapshotGroups);
      for (std::size_t group = 0U; group < requested.size(); ++group) {
        const auto* enabled = requested[group].as_bool();
        if (enabled == nullptr) {
          throw std::invalid_argument(
              "native environmental observation mask is not boolean");
        }
        plan.requested[group] = *enabled;
      }
      if (!platform::valid_file_snapshot_plan(plan) ||
          !paths.insert(plan.path).second) {
        throw std::invalid_argument(
            "native environmental source plan is invalid or duplicated");
      }
      result.environment_sources.push_back(plan);
    }
    const auto layout = calibration::native_discovery_layout(result);
    const auto& expected_regions = array(resources, "region_bytes", 7U);
    if (verify_declared_layout &&
        (layout.core_bytes != size(resources, "core_bytes") ||
         layout.monitor_bytes != size(resources, "monitor_bytes") ||
         layout.total_mapping_bytes != size(resources, "total_mapping_bytes") ||
         layout.total_mapping_bytes > number(budget, "memory_bytes"))) {
      throw std::invalid_argument("native layout differs from admitted sizes/budget");
    }
    for (std::size_t index = 0U; index < 7U; ++index) {
      if (verify_declared_layout &&
          layout.region_bytes[index] != size(expected_regions[index])) {
        throw std::invalid_argument("native region size differs from admitted layout");
      }
    }
    return protocol::Result<calibration::NativeDiscoveryCapturePlan>::success(result);
  } catch (const std::exception& error) {
    return protocol::Result<calibration::NativeDiscoveryCapturePlan>::failure(
        {protocol::ErrorCategory::cross_field, "$/discovery/native_capture",
         "S17-DISCOVERY-NATIVE-PLAN", error.what()});
  }
}
} // namespace

auto parse_native_discovery_capture(
    const Object& capture, const Object& resources, const Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeDiscoveryCapturePlan> {
  return parse_capture(capture, resources, monitoring, prestate, true);
}

auto describe_native_discovery_layout(
    const Object& capture, const Object& resources, const Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeDiscoveryCaptureLayout> {
  const auto parsed = parse_capture(capture, resources, monitoring, prestate, false);
  if (!parsed) {
    return protocol::Result<calibration::NativeDiscoveryCaptureLayout>::failure(
        parsed.errors());
  }
  return protocol::Result<calibration::NativeDiscoveryCaptureLayout>::success(
      calibration::native_discovery_layout(parsed.value()));
}
} // namespace cpu_prefetch::runner::stage17
