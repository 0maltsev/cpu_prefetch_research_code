#include "cpu_prefetch/runner/stage17_formal_service_action.hpp"

#include "cpu_prefetch/runner/software_prefetch.hpp"
#include <gtest/gtest.h>

#include <limits>

namespace {
using namespace cpu_prefetch;
using Object = protocol::json::Value::Object;
using Value = protocol::json::Value;

auto value(std::uint64_t integer) -> Value {
  return Value(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                      std::to_string(integer), integer});
}
auto object(std::string_view input) -> Object {
  auto parsed = protocol::json::parse(input);
  if (!parsed || parsed.value().as_object() == nullptr) {
    throw std::logic_error("test JSON invalid");
  }
  return *parsed.value().as_object();
}
constexpr std::array<platform::HardwarePrefetchMsrValue, 3U> kPrestate{
    {{0U, 0x1230U}, {1U, 0x4562U}, {8U, 0x7894U}}};

struct Fixture final {
  Object capture{object(
      R"({"schema_version":"cpu-prefetch-stage17-formal-service-capture/1",
    "method_id":"SERVICE-RATE-NP-LTL95C95-MIN-v1","package":"R0",
    "ordinal":0,"cell_ordinal":0,"repetition_ordinal":0,"linked_order":null,"ring_distance":null,"hardware_state":"H0","placement":"NEAR",
    "working_set_class":"L2_RESIDENT","warmup_ns":5000000000,"measurement_ns":100000000,
    "seed_use":"ONE_PERSISTENT_ARENA_MEASUREMENT_SEED_WARMUP_RESERVED_NO_DRAWS",
    "geometry":{"capacity":512,"cache_line_bytes":64,"base_page_bytes":4096,
      "producer_cpu":0,"consumer_cpu":1,"producer_node":0,"consumer_node":0,"shared_node":0},
    "budget":{"phases":[
      {"producer_attempt_limit":200000,"consumer_poll_limit":200000,"drain_ns":1000000000},
      {"producer_attempt_limit":200000,"consumer_poll_limit":200000,"drain_ns":1000000000}],
      "barrier_poll_limit":1000000,"memory_bytes":1073741824}})")};
  Object resources{object(R"({"ordinal":0,"workers":{
    "producer_stack":{"bytes":2097152,"verified_base_page_bytes":4096,"owner_cpu":0,"requested_node":0},
    "consumer_stack":{"bytes":2097152,"verified_base_page_bytes":4096,"owner_cpu":1,"requested_node":0}},
    "controller_stack":{"bytes":2097152,"verified_base_page_bytes":4096,"owner_cpu":2,"requested_node":0},
    "core_bytes":1,"monitor_bytes":1,"total_mapping_bytes":1,"region_bytes":[1,1,1,1,1,1,1],
    "tls_module_capacity":32,"thread_stat_bytes":4096,"thread_status_bytes":16384,
    "thread_affinity_words":128,"initial_consumer_state":17})")};
  Object monitoring{object(R"({"ordinal":0,"during_first_page":[0,0,0,0,0,0,0],
    "during_page_count":[1,1,1,1,1,1,1],"during_offset_ticks":[1000000,1000000],
    "observer_wait_poll_limit":1000000,"control_region_index":0,
    "counter_limits":[[],[]],"hardware_identity":{"family":6,"model":62},"environment_sources":[]})")};
  Fixture() {
    const Object warmup{{"run_id", Value(std::string("native-warmup"))},
                        {"seed_id", Value(std::string("warmup-seed"))},
                        {"namespace_id", Value(std::string("warmup-namespace"))},
                        {"seed_hex", Value(std::string(64U, '0'))}};
    const Object measured{{"run_id", Value(std::string("native-measurement"))},
                          {"seed_id", Value(std::string("measurement-seed"))},
                          {"namespace_id", Value(std::string("measurement-namespace"))},
                          {"seed_hex", Value(std::string(64U, '1'))}};
    capture.emplace("software_prefetch_mapping_id",
                    Value(std::string(runner::kSoftwarePrefetchMappingIdT0Only)));
    capture.emplace("warmup", Value(warmup));
    capture.emplace("measurement", Value(measured));
    capture.emplace("arena_seed", Value(measured));
    const auto limits = object(
        R"({"minor_faults":null,"major_faults":0,"voluntary_switches":null,"involuntary_switches":null})");
    monitoring.at("counter_limits") =
        Value(Value::Array{Value(Value::Array{Value(limits), Value(limits)}),
                           Value(Value::Array{Value(limits), Value(limits)})});
    const auto rows =
        object(R"({"producer_primary_rows":200000,"consumer_primary_rows":200000})");
    resources.emplace("phase_capacity", Value(Value::Array{Value(rows), Value(rows)}));
    refresh_layout();
  }
  auto parse() const {
    return runner::stage17::parse_native_formal_service_capture(capture, resources,
                                                                monitoring, kPrestate);
  }
  void refresh_layout() {
    const auto described = runner::stage17::describe_native_formal_service_layout(
        capture, resources, monitoring, kPrestate);
    if (!described) {
      throw std::logic_error("invalid test prospective layout");
    }
    const auto& layout = described.value();
    resources.at("core_bytes") = value(layout.core_bytes);
    resources.at("monitor_bytes") = value(layout.monitor_bytes);
    resources.at("total_mapping_bytes") = value(layout.total_mapping_bytes);
    Value::Array sizes;
    for (const auto bytes : layout.region_bytes) {
      sizes.push_back(value(bytes));
    }
    resources.at("region_bytes") = Value(std::move(sizes));
  }
  void configure_cell(std::uint64_t cell) {
    const auto context = cell % 12U;
    constexpr std::array<std::string_view, 5U> packages{"R0", "R1", "R2", "L0", "L1"};
    capture.at("package") = Value(std::string(packages[cell / 12U]));
    capture.at("ring_distance") = Value();
    capture.at("linked_order") = Value();
    if (cell / 12U == 1U || cell / 12U == 2U) {
      capture.at("ring_distance") = Value(
          Object{{"cache_lines", value(cell / 12U == 1U ? 1U : 3U)},
                 {"calibration_evidence_id",
                  Value(std::string(cell / 12U == 1U ? "" : "accepted-distance"))}});
    }
    if (cell / 12U >= 3U) {
      capture.at("linked_order") =
          Value(Object{{"seed_id", Value(std::string("node-seed"))},
                       {"seed_hex", Value(std::string(64U, '2'))},
                       {"namespace_id", Value(std::string("node-namespace"))},
                       {"arena_alignment_bytes", value(4096U)}});
    }
    const bool far = (context / 3U) % 2U != 0U;
    const std::array<std::string, 3U> classes{"L2_RESIDENT", "LLC_RESIDENT",
                                              "BEYOND_LLC"};
    capture.at("cell_ordinal") = value(cell);
    capture.at("hardware_state") = Value(std::string(context < 6U ? "H0" : "H1"));
    capture.at("placement") = Value(std::string(far ? "FAR" : "NEAR"));
    capture.at("working_set_class") = Value(classes[context % 3U]);
    auto geometry = *capture.at("geometry").as_object();
    geometry.at("consumer_cpu") = value(far ? 8U : 1U);
    geometry.at("consumer_node") = value(far ? 1U : 0U);
    capture.at("geometry") = Value(std::move(geometry));
    auto workers = *resources.at("workers").as_object();
    auto consumer = *workers.at("consumer_stack").as_object();
    consumer.at("owner_cpu") = value(far ? 8U : 1U);
    consumer.at("requested_node") = value(far ? 1U : 0U);
    workers.at("consumer_stack") = Value(std::move(consumer));
    resources.at("workers") = Value(std::move(workers));
    refresh_layout();
  }
};

TEST(FormalServiceNativeInput, CoversSixtyCellsAndBothPhaseBounds) {
  for (std::uint64_t cell = 0U; cell < 60U; ++cell) {
    Fixture f;
    f.configure_cell(cell);
    const auto parsed = f.parse();
    ASSERT_TRUE(parsed);
    EXPECT_EQ(parsed.value().service.session.phases[0U].duration_ticks,
              5'000'000'000'000U);
    EXPECT_EQ(parsed.value().service.session.phases[1U].duration_ticks,
              100'000'000'000U);
    EXPECT_EQ(parsed.value().controls.workers.consumer_stack.owner_cpu,
              (cell % 12U) / 3U % 2U == 0U ? 1U : 8U);
  }
}
TEST(FormalServiceNativeInput, RequiresExactPackageCellAndMethod) {
  Fixture f;
  f.capture.at("package") = Value(std::string("L1"));
  EXPECT_FALSE(f.parse());
  Fixture method;
  method.capture.at("method_id") = Value(std::string("wrong"));
  EXPECT_FALSE(method.parse());
  Fixture ordinal;
  ordinal.capture.at("cell_ordinal") = value(60U);
  EXPECT_FALSE(ordinal.parse());
}
TEST(FormalServiceNativeInput, RequiresAcceptedSoftwareMappingForDeclaredModel) {
  Fixture f;
  f.capture.at("software_prefetch_mapping_id") = Value(std::string("unknown-mapping"));
  EXPECT_FALSE(f.parse());
  f.capture.at("software_prefetch_mapping_id") =
      Value(std::string(runner::kSoftwarePrefetchMappingId));
  EXPECT_FALSE(f.parse());
}
TEST(FormalServiceNativeInput, RequiresLinkedSeedAndRejectsItForRing) {
  Fixture f;
  f.configure_cell(36U);
  f.capture.at("linked_order") = Value();
  EXPECT_FALSE(f.parse());
  Fixture linked;
  linked.configure_cell(36U);
  Fixture ring;
  ring.capture.at("linked_order") = linked.capture.at("linked_order");
  EXPECT_FALSE(ring.parse());
}
TEST(FormalServiceNativeInput, RequiresR1OneLineAndR2ExplicitEvidence) {
  Fixture one;
  one.configure_cell(12U);
  one.capture.at("ring_distance") = Value(Object{
      {"cache_lines", value(2U)}, {"calibration_evidence_id", Value(std::string())}});
  EXPECT_FALSE(one.parse());
  Fixture calibrated;
  calibrated.configure_cell(24U);
  calibrated.capture.at("ring_distance") = Value(Object{
      {"cache_lines", value(3U)}, {"calibration_evidence_id", Value(std::string())}});
  EXPECT_FALSE(calibrated.parse());
  Fixture off;
  off.capture.at("ring_distance") = one.capture.at("ring_distance");
  EXPECT_FALSE(off.parse());
}
TEST(FormalServiceNativeInput, RejectsStaleLayoutAndUncoveredCapacity) {
  Fixture f;
  f.resources.at("total_mapping_bytes") = value(1U);
  EXPECT_FALSE(f.parse());
  Fixture small;
  auto capacities = *small.resources.at("phase_capacity").as_array();
  auto rows = *capacities[1U].as_object();
  rows.at("consumer_primary_rows") = value(1U);
  capacities[1U] = Value(std::move(rows));
  small.resources.at("phase_capacity") = Value(std::move(capacities));
  EXPECT_FALSE(small.parse());
}
TEST(FormalServiceNativeInput, RejectsWindowOverflowAndMissingWarmup) {
  Fixture f;
  f.capture.at("warmup_ns") = value(0U);
  EXPECT_FALSE(f.parse());
  Fixture overflow;
  overflow.capture.at("measurement_ns") =
      value(std::numeric_limits<std::uint64_t>::max());
  EXPECT_FALSE(overflow.parse());
}
TEST(FormalServiceNativeInput, RejectsNoncanonicalSeedAndReusedPhaseIdentity) {
  Fixture f;
  auto identity = *f.capture.at("warmup").as_object();
  identity.at("seed_hex") = Value(std::string(64U, 'A'));
  f.capture.at("warmup") = Value(std::move(identity));
  EXPECT_FALSE(f.parse());
  Fixture reuse;
  reuse.capture.at("warmup") = reuse.capture.at("measurement");
  EXPECT_FALSE(reuse.parse());
}
} // namespace
