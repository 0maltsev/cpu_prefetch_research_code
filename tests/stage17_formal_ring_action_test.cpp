#include "cpu_prefetch/runner/stage17_formal_ring_action.hpp"

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
      R"({"schema_version":"cpu-prefetch-stage17-formal-ring-capture/1",
    "method_id":"RING-D2-RUNTAIL-LTL95C95-WINDOW-v2","package":"R0",
    "ordinal":0,"context_ordinal":0,"repetition_ordinal":0,"minimum_observations_per_series":100,"hardware_state":"H0","placement":"NEAR",
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
    capture.emplace("warmup", Value(warmup));
    capture.emplace("measurement", Value(measured));
    capture.emplace("arena_seed", Value(measured));
    const auto limits = object(
        R"({"minor_faults":null,"major_faults":0,"voluntary_switches":null,"involuntary_switches":null})");
    monitoring.at("counter_limits") =
        Value(Value::Array{Value(Value::Array{Value(limits), Value(limits)}),
                           Value(Value::Array{Value(limits), Value(limits)})});
    const auto rows =
        object(R"({"producer_primary_rows":200000,"consumer_primary_rows":200000,
        "producer_demand_rows":200000,"consumer_demand_rows":200000})");
    resources.emplace("phase_capacity", Value(Value::Array{Value(rows), Value(rows)}));
    refresh_layout();
  }
  auto parse() const {
    return runner::stage17::parse_native_formal_ring_capture(capture, resources,
                                                             monitoring, kPrestate);
  }
  void refresh_layout() {
    const auto described = runner::stage17::describe_native_formal_ring_layout(
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
  void configure_context(std::uint64_t context) {
    const bool far = (context / 3U) % 2U != 0U;
    const std::array<std::string, 3U> classes{"L2_RESIDENT", "LLC_RESIDENT",
                                              "BEYOND_LLC"};
    capture.at("context_ordinal") = value(context);
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

TEST(FormalRingNativeInput, ResolvesExplicitWindowAndBothPhaseBounds) {
  Fixture fixture;
  const auto parsed = fixture.parse();
  ASSERT_TRUE(parsed);
  EXPECT_EQ(parsed.value().ring.session.phases[0U].duration_ticks, 5'000'000'000'000U);
  EXPECT_EQ(parsed.value().ring.session.phases[1U].duration_ticks, 100'000'000'000U);
  EXPECT_EQ(parsed.value().ring.session.phases[1U].consumer_poll_limit, 200000U);
  EXPECT_EQ(parsed.value().ring.capacity[0U].producer_demand_rows, 200000U);
  EXPECT_EQ(parsed.value().controls.hardware_prestate.data(), kPrestate.data());
  EXPECT_EQ(parsed.value().ring.arena.seed_namespace, "measurement-namespace");
}
TEST(FormalRingNativeInput, CoversTwelveContextsWithoutInventingFarCpu) {
  for (std::uint64_t context = 0U; context < 12U; ++context) {
    Fixture fixture;
    fixture.configure_context(context);
    const auto parsed = fixture.parse();
    ASSERT_TRUE(parsed);
    EXPECT_EQ(parsed.value().controls.workers.consumer_stack.owner_cpu,
              (context / 3U) % 2U == 0U ? 1U : 8U);
  }
}
TEST(FormalRingNativeInput, RejectsWrongMethodPackageWarmupAndFactorLabels) {
  for (const auto field :
       {"method_id", "package", "hardware_state", "placement", "working_set_class"}) {
    Fixture fixture;
    fixture.capture.at(field) = Value(std::string("wrong"));
    EXPECT_FALSE(fixture.parse());
  }
  Fixture fixture;
  fixture.capture.at("warmup_ns") = value(1U);
  EXPECT_FALSE(fixture.parse());
  fixture.capture.at("warmup_ns") = value(5'000'000'000U);
  fixture.capture.at("context_ordinal") = value(12U);
  EXPECT_FALSE(fixture.parse());
}
TEST(FormalRingNativeInput, RejectsIncompleteOrAdditionalFields) {
  Fixture fixture;
  fixture.capture.erase("measurement_ns");
  EXPECT_FALSE(fixture.parse());
  Fixture extra;
  extra.capture.emplace("sample_count", value(100000U));
  EXPECT_FALSE(extra.parse());
  Fixture resources;
  resources.resources.emplace("unknown", value(1U));
  EXPECT_FALSE(resources.parse());
}
TEST(FormalRingNativeInput, RejectsMissingWindowMinimumAndOverflow) {
  for (const auto field : {"measurement_ns", "minimum_observations_per_series"}) {
    Fixture fixture;
    fixture.capture.at(field) = value(0U);
    EXPECT_FALSE(fixture.parse());
  }
  Fixture fixture;
  fixture.capture.at("measurement_ns") =
      value(std::numeric_limits<std::uint64_t>::max());
  EXPECT_FALSE(fixture.parse());
  Fixture minimum;
  minimum.capture.at("minimum_observations_per_series") = value(200000U);
  EXPECT_FALSE(minimum.parse());
}
TEST(FormalRingNativeInput, RejectsStaleDeclaredLayoutAndTooSmallBudget) {
  for (const auto field : {"core_bytes", "monitor_bytes", "total_mapping_bytes"}) {
    Fixture fixture;
    fixture.resources.at(field) = value(1U);
    EXPECT_FALSE(fixture.parse());
  }
  Fixture fixture;
  auto budget = *fixture.capture.at("budget").as_object();
  budget.at("memory_bytes") = value(1U);
  fixture.capture.at("budget") = Value(std::move(budget));
  EXPECT_FALSE(fixture.parse());
  EXPECT_FALSE(runner::stage17::describe_native_formal_ring_layout(
      fixture.capture, fixture.resources, fixture.monitoring, kPrestate));
}
TEST(FormalRingNativeInput, RejectsUncoveredRawCapacity) {
  for (const auto field : {"producer_primary_rows", "consumer_primary_rows",
                           "producer_demand_rows", "consumer_demand_rows"}) {
    Fixture fixture;
    auto phases = *fixture.resources.at("phase_capacity").as_array();
    auto rows = *phases[1U].as_object();
    rows.at(field) = value(1U);
    phases[1U] = Value(std::move(rows));
    fixture.resources.at("phase_capacity") = Value(std::move(phases));
    EXPECT_FALSE(fixture.parse());
  }
}
TEST(FormalRingNativeInput, RejectsPhaseIdentityReuseAndUnexpectedArenaSeed) {
  for (const auto field : {"run_id", "seed_id", "namespace_id", "seed_hex"}) {
    Fixture fixture;
    auto warmup = *fixture.capture.at("warmup").as_object();
    warmup.at(field) = fixture.capture.at("measurement").as_object()->at(field);
    fixture.capture.at("warmup") = Value(std::move(warmup));
    EXPECT_FALSE(fixture.parse());
  }
  Fixture fixture;
  fixture.capture.at("arena_seed") = fixture.capture.at("warmup");
  EXPECT_FALSE(fixture.parse());
}
TEST(FormalRingNativeInput, RejectsOwnerCollisionAndOrdinalDisagreement) {
  Fixture fixture;
  fixture.resources.at("ordinal") = value(1U);
  EXPECT_FALSE(fixture.parse());
  Fixture owner;
  auto stack = *owner.resources.at("controller_stack").as_object();
  stack.at("owner_cpu") = value(0U);
  owner.resources.at("controller_stack") = Value(std::move(stack));
  EXPECT_FALSE(owner.parse());
}
TEST(FormalRingNativeInput, RejectsNoncanonicalSeedsAndOpaqueIdentities) {
  for (const auto phase : {"warmup", "measurement"}) {
    for (const auto field : {"run_id", "seed_id", "namespace_id"}) {
      for (const auto& invalid :
           {std::string("bad id"), std::string(257U, 'x'), std::string("-bad")}) {
        Fixture fixture;
        auto identity = *fixture.capture.at(phase).as_object();
        identity.at(field) = Value(invalid);
        fixture.capture.at(phase) = Value(identity);
        if (std::string_view(phase) == "measurement")
          fixture.capture.at("arena_seed") = Value(identity);
        EXPECT_FALSE(fixture.parse());
      }
    }
    Fixture fixture;
    auto identity = *fixture.capture.at(phase).as_object();
    identity.at("seed_hex") = Value(std::string(64U, 'A'));
    fixture.capture.at(phase) = Value(identity);
    if (std::string_view(phase) == "measurement")
      fixture.capture.at("arena_seed") = Value(identity);
    EXPECT_FALSE(fixture.parse());
  }
}
TEST(FormalRingNativeInput, AllowsZeroOffsetButRejectsObservationAtPhaseEnd) {
  Fixture fixture;
  fixture.monitoring.at("during_offset_ticks") =
      Value(Value::Array{value(0U), value(0U)});
  EXPECT_TRUE(fixture.parse());
  fixture.monitoring.at("during_offset_ticks") =
      Value(Value::Array{value(0U), value(100'000'000'000U)});
  EXPECT_FALSE(fixture.parse());
}
} // namespace
