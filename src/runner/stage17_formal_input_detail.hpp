#ifndef CPU_PREFETCH_RUNNER_STAGE17_FORMAL_INPUT_DETAIL_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_FORMAL_INPUT_DETAIL_HPP
#include "cpu_prefetch/calibration/native_capture_plan.hpp"
#include "cpu_prefetch/protocol/json.hpp"
#include <algorithm>
#include <limits>
#include <set>
#include <stdexcept>
namespace cpu_prefetch::runner::stage17::formal_input_detail {
using Value = protocol::json::Value;
using Object = Value::Object;

inline auto member(const Object& object, std::string_view key) -> const Value& {
  const auto found = object.find(key);
  if (found == object.end()) {
    throw std::invalid_argument("missing native formal ring field: " +
                                std::string(key));
  }
  return found->second;
}
inline auto object(const Object& parent, std::string_view key) -> const Object& {
  const auto* result = member(parent, key).as_object();
  if (result == nullptr) {
    throw std::invalid_argument("native formal ring field is not an object");
  }
  return *result;
}
inline auto array(const Object& parent, std::string_view key, std::size_t count)
    -> const Value::Array& {
  const auto* result = member(parent, key).as_array();
  if (result == nullptr || result->size() != count) {
    throw std::invalid_argument("native formal ring array length differs");
  }
  return *result;
}
inline auto number(const Value& value) -> std::uint64_t {
  const auto* result = value.as_number();
  if (result == nullptr ||
      result->kind != protocol::json::Number::Kind::unsigned_integer) {
    throw std::invalid_argument("native formal ring requires an unsigned integer");
  }
  return std::get<std::uint64_t>(result->value);
}
inline auto number(const Object& parent, std::string_view key) -> std::uint64_t {
  return number(member(parent, key));
}
inline auto word(const Object& parent, std::string_view key) -> std::uint32_t {
  const auto value = number(parent, key);
  if (value > std::numeric_limits<std::uint32_t>::max()) {
    throw std::invalid_argument("native formal ring CPU/node/identity overflows");
  }
  return static_cast<std::uint32_t>(value);
}
inline auto size(const Value& value) -> std::size_t {
  const auto result = number(value);
  if (result > std::numeric_limits<std::size_t>::max()) {
    throw std::invalid_argument("native formal ring size overflows");
  }
  return static_cast<std::size_t>(result);
}
inline auto size(const Object& parent, std::string_view key) -> std::size_t {
  return size(member(parent, key));
}
inline auto text(const Object& parent, std::string_view key) -> const std::string& {
  const auto* result = member(parent, key).as_string();
  if (result == nullptr || result->empty()) {
    throw std::invalid_argument("native formal ring requires nonempty text");
  }
  return *result;
}
inline auto ticks(std::uint64_t nanoseconds) -> std::uint64_t {
  if (nanoseconds == 0U ||
      nanoseconds > std::numeric_limits<std::uint64_t>::max() / 1000U) {
    throw std::invalid_argument(
        "native formal ring nanosecond duration overflows ticks");
  }
  return nanoseconds * 1000U;
}
inline void fields(const Object& value,
                   std::initializer_list<std::string_view> expected) {
  if (value.size() != expected.size()) {
    throw std::invalid_argument("native formal ring field set differs");
  }
  for (const auto field : expected) {
    static_cast<void>(member(value, field));
  }
}
inline auto stack(const Object& value) -> platform::OwnerMappingPlan {
  fields(value, {"bytes", "verified_base_page_bytes", "owner_cpu", "requested_node"});
  return {size(value, "bytes"), size(value, "verified_base_page_bytes"),
          word(value, "owner_cpu"), word(value, "requested_node")};
}
inline auto limit(const Value& value) -> std::optional<std::uint64_t> {
  return value.is_null() ? std::nullopt : std::optional(number(value));
}
inline auto limits(const Value& value) -> calibration::DiscoveryDisturbanceLimits {
  const auto* item = value.as_object();
  if (item == nullptr) {
    throw std::invalid_argument("native formal ring counter limits missing");
  }
  fields(*item, {"minor_faults", "major_faults", "voluntary_switches",
                 "involuntary_switches"});
  return {limit(member(*item, "minor_faults")), limit(member(*item, "major_faults")),
          limit(member(*item, "voluntary_switches")),
          limit(member(*item, "involuntary_switches"))};
}
inline auto run_id(const Object& value) -> protocol::RunId {
  const auto parsed = protocol::RunId::parse(text(value, "run_id"), "$/capture/run_id");
  if (!parsed) {
    throw std::invalid_argument("invalid native formal ring run ID");
  }
  return parsed.value();
}
inline auto opaque_text(const Object& value, std::string_view field)
    -> const std::string& {
  const auto alphanumeric = [](char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
  };
  const auto& id = text(value, field);
  if (id.size() > 256U || !alphanumeric(id.front()) ||
      !std::all_of(id.begin(), id.end(), [&](char c) {
        return alphanumeric(c) || c == '_' || c == '.' || c == ':' || c == '-';
      })) {
    throw std::invalid_argument("formal identity is not a bounded opaque ID");
  }
  return id;
}
inline auto seed_text(const Object& value) -> const std::string& {
  const auto& seed = text(value, "seed_hex");
  if (seed.size() != 64U || !std::all_of(seed.begin(), seed.end(), [](char c) {
        return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
      })) {
    throw std::invalid_argument("formal seed must use canonical lowercase hex");
  }
  return seed;
}
inline void phase_identity(const Object& value) {
  fields(value, {"run_id", "seed_id", "namespace_id", "seed_hex"});
  for (const auto field : {"run_id", "seed_id", "namespace_id"}) {
    static_cast<void>(opaque_text(value, field));
  }
  static_cast<void>(seed_text(value));
}
inline auto parse_controls(const Object& capture, const Object& resources,
                           const Object& monitoring,
                           std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> calibration::NativeCaptureControlPlan {
  const auto& geometry = object(capture, "geometry");
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
        "native formal ring owner geometry differs from declared context");
  }
  const auto& identity = object(monitoring, "hardware_identity");
  fields(identity, {"family", "model"});
  calibration::NativeCaptureControlPlan result{
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
      text(capture, "hardware_state") == "H0" ? protocol::RequestedHardwareState::h0
                                              : protocol::RequestedHardwareState::h1,
      prestate,
      {}};
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
    if (!platform::valid_file_snapshot_plan(plan) || !paths.insert(plan.path).second) {
      throw std::invalid_argument(
          "native environmental source plan is invalid or duplicated");
    }
    result.environment_sources.push_back(plan);
  }
  return result;
}
template <typename Layout>
void check_layout(const Layout& layout, const Object& resources, const Object& budget,
                  bool verify_declared_layout) {
  const auto& expected_regions = array(resources, "region_bytes", 7U);
  if (layout.total_mapping_bytes > number(budget, "memory_bytes")) {
    throw std::invalid_argument(
        "native formal mapping exceeds prospective memory budget");
  }
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
}
} // namespace cpu_prefetch::runner::stage17::formal_input_detail
#endif
