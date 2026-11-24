// Standalone cold Q16b sizing caller. No capture, clock or hardware invocation.
// Inputs are declarations; hardware_prestate must be supplied explicitly.
#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/runner/stage17_formal_service_action.hpp"

#include <array>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <sys/resource.h>

namespace {
using namespace cpu_prefetch;
using Value = protocol::json::Value;
using Object = Value::Object;
constexpr std::size_t kInputLimit = 8U * 1024U * 1024U;
void require(bool ok, const char* error) {
  if (!ok) throw std::runtime_error(error);
}
auto integer(std::uint64_t n) -> Value {
  return Value(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                     std::to_string(n), n});
}
auto unsigned_value(const Value& v) -> std::uint64_t {
  const auto* n = v.as_number();
  require(n != nullptr && n->kind == protocol::json::Number::Kind::unsigned_integer,
          "unsigned integer required");
  return std::get<std::uint64_t>(n->value);
}
auto object(const Value& v) -> const Object& {
  require(v.as_object() != nullptr, "object required");
  return *v.as_object();
}
auto identity() -> Object {
  const auto info = foundation::repository_info();
  return {{"schema_version", Value(std::string("software-formal-service-layout/1"))},
          {"execution_authority", Value(false)}, {"software_only", Value(true)},
          {"hardware_observation", Value(false)},
          {"performance_measurement", Value(false)},
          {"phase18_authority", Value(false)},
          {"source_revision", Value(std::string(info.source_revision))},
          {"source_dirty", Value(info.source_dirty)},
          {"compiler", Value(std::string(info.compiler))},
          {"standard_library", Value(std::string(info.standard_library))}};
}
void print(Object output) {
  const auto encoded = protocol::json::canonicalize(Value(std::move(output)));
  require(static_cast<bool>(encoded), "canonical output failed");
  std::cout << encoded.value() << '\n';
}
auto read(const char* path) -> Object {
  std::ifstream input(path, std::ios::binary);
  require(static_cast<bool>(input), "input open failed");
  std::string bytes;
  std::array<char, 65536U> buffer{};
  while (input.read(buffer.data(), static_cast<std::streamsize>(buffer.size())) || input.gcount()) {
    const auto count = static_cast<std::size_t>(input.gcount());
    require(count <= kInputLimit - bytes.size(), "input exceeds 8 MiB");
    bytes.append(buffer.data(), count);
  }
  require(input.eof(), "input read failed");
  const auto parsed = protocol::json::parse(bytes);
  require(static_cast<bool>(parsed), "invalid JSON");
  return object(parsed.value());
}
template <typename T> void valid(const protocol::Result<T>& result) {
  if (!result) {
    for (const auto& error : result.errors()) std::cerr << error.message << '\n';
    throw std::runtime_error("native pure layout/parser rejected input");
  }
}
} // namespace

int main(int argc, char** argv) {
  try {
    // Bounds concern this software utility only; no experimental parameters.
    const rlimit cpu{30U, 30U};
    const rlimit core{0U, 0U};
    require(setrlimit(RLIMIT_CPU, &cpu) == 0 &&
            setrlimit(RLIMIT_CORE, &core) == 0, "software utility limits failed");
    if (argc == 2 && std::string_view(argv[1]) == "--identity") { print(identity()); return 0; }
    require(argc == 3, "usage: sizing --describe|--verify-declared INPUT.json");
    const auto mode = std::string_view(argv[1]);
    require(mode == "--describe" || mode == "--verify-declared", "unknown mode");
    const auto doc = read(argv[2]);
    require(doc.size() == 4U && doc.contains("capture") && doc.contains("resources") &&
            doc.contains("monitoring") && doc.contains("hardware_prestate"), "input field set");
    const auto& capture = object(doc.at("capture"));
    auto resources = object(doc.at("resources"));
    const auto& monitoring = object(doc.at("monitoring"));
    const auto* values = doc.at("hardware_prestate").as_array();
    require(values != nullptr && values->size() == 3U, "explicit three-CPU prestate required");
    std::array<platform::HardwarePrefetchMsrValue, 3U> prestate{};
    for (std::size_t i = 0U; i < prestate.size(); ++i) {
      const auto& row = object((*values)[i]);
      require(row.size() == 2U && row.contains("cpu") && row.contains("value"), "prestate field set");
      const auto cpu_id = unsigned_value(row.at("cpu"));
      require(cpu_id <= std::numeric_limits<std::uint32_t>::max(), "CPU overflow");
      prestate[i] = {static_cast<std::uint32_t>(cpu_id), unsigned_value(row.at("value"))};
    }
    const auto described = runner::stage17::describe_native_formal_service_layout(
        capture, resources, monitoring, prestate);
    valid(described);
    const auto& layout = described.value();
    Value::Array regions;
    for (const auto n : layout.region_bytes) regions.push_back(integer(n));
    Object sizes{{"core_bytes", integer(layout.core_bytes)},
                 {"monitor_bytes", integer(layout.monitor_bytes)},
                 {"total_mapping_bytes", integer(layout.total_mapping_bytes)},
                 {"region_bytes", Value(regions)}};
    if (mode == "--describe") {
      for (const auto& [key, value] : sizes) resources.at(key) = value;
    }
    // The exact live parser must accept the resulting declarations. No run.
    const auto parsed = runner::stage17::parse_native_formal_service_capture(
        capture, resources, monitoring, prestate);
    valid(parsed);
    const auto checked = calibration::native_formal_service_layout(parsed.value());
    require(checked.core_bytes == layout.core_bytes && checked.monitor_bytes == layout.monitor_bytes &&
            checked.total_mapping_bytes == layout.total_mapping_bytes && checked.region_bytes == layout.region_bytes,
            "description/live-parser layout disagreement");
    const auto& workers = layout.workers;
    Object worker_sizes;
    const auto put = [&](const char* key, std::size_t value) {
      worker_sizes.emplace(key, integer(value));
    };
    put("records_bytes", workers.records_bytes);
    put("producer_bytes", workers.producer_bytes);
    put("consumer_bytes", workers.consumer_bytes);
    put("record_order", workers.record_order);
    put("arena_object", workers.arena_object);
    put("queue_object", workers.queue_object);
    put("package_object", workers.package_object);
    put("emitter_object", workers.emitter_object);
    put("slots", workers.slots);
    put("cursors", workers.cursors);
    put("nodes", workers.nodes);
    put("recycler", workers.recycler);
    put("ownership", workers.ownership);
    put("node_input_order", workers.node_input_order);
    put("node_initial_order", workers.node_initial_order);
    put("node_validation", workers.node_validation);
    for (const auto& [name, schedule_values] : std::array{
        std::pair{"schedule_offsets", workers.schedule_offsets},
        std::pair{"schedule_counts", workers.schedule_counts}}) {
      Value::Array values_json;
      for (const auto value : schedule_values) values_json.push_back(integer(value));
      worker_sizes.emplace(name, Value(std::move(values_json)));
    }
    Value ring(nullptr), linked(nullptr);
    if (workers.ring) {
      ring = Value(Object{{"slot_bytes", integer(workers.ring->slot_bytes)},
                          {"cursor_bytes", integer(workers.ring->cursor_bytes)}});
    }
    if (workers.linked) {
      const auto& item = *workers.linked;
      linked = Value(Object{{"node_bytes", integer(item.node_bytes)},
          {"recycler_bytes", integer(item.recycler_bytes)},
          {"ownership_bytes", integer(item.ownership_bytes)},
          {"node_stride_bytes", integer(item.node_stride_bytes)},
          {"order_count", integer(item.order_count)},
          {"validation_bytes", integer(item.validation_bytes)}});
    }
    worker_sizes.emplace("ring", std::move(ring));
    worker_sizes.emplace("linked", std::move(linked));
    Value::Array phases;
    for (const auto& phase : workers.phases) {
      phases.emplace_back(Object{
          {"raw", Value(Object{{"producer_bytes", integer(phase.raw.producer_bytes)},
                                {"consumer_bytes", integer(phase.raw.consumer_bytes)}})},
          {"producer_object", integer(phase.producer_object)},
          {"producer_raw", integer(phase.producer_raw)},
          {"consumer_object", integer(phase.consumer_object)},
          {"consumer_raw", integer(phase.consumer_raw)}});
    }
    worker_sizes.emplace("phases", Value(std::move(phases)));
    auto output = identity();
    output.emplace("workers", Value(std::move(worker_sizes)));
    output.emplace("layout", Value(std::move(sizes)));
    output.emplace("declared_layout_rechecked", Value(true));
    print(std::move(output));
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
