#include "cpu_prefetch/runner/stage17_discovery_action.hpp"

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
      R"({"ordinal":0,"context_ordinal":0,"hardware_state":"H0","placement":"NEAR",
    "working_set_class":"L2_RESIDENT","warmup_ns":5000000000,"measurement_ns":100000000,
    "seed_use":"ONE_PERSISTENT_ARENA_MEASUREMENT_SEED_WARMUP_RESERVED_NO_DRAWS",
    "geometry":{"capacity":512,"cache_line_bytes":64,"base_page_bytes":4096,
      "producer_cpu":0,"consumer_cpu":1,"producer_node":0,"consumer_node":0,"shared_node":0},
    "budget":{"warmup_attempt_capacity":200000,"measurement_attempt_capacity":200000,
      "drain_ns":1000000000,"drain_attempt_capacity":513,"barrier_poll_limit":1000000,"memory_bytes":1073741824}})")};
  Object resources{object(R"({"ordinal":0,"workers":{
    "producer_stack":{"bytes":2097152,"verified_base_page_bytes":4096,"owner_cpu":0,"requested_node":0},
    "consumer_stack":{"bytes":2097152,"verified_base_page_bytes":4096,"owner_cpu":1,"requested_node":0}},
    "controller_stack":{"bytes":2097152,"verified_base_page_bytes":4096,"owner_cpu":2,"requested_node":0},
    "core_bytes":1,"monitor_bytes":1,"total_mapping_bytes":1,"region_bytes":[],
    "tls_module_capacity":32,"thread_stat_bytes":4096,"thread_status_bytes":16384,
    "thread_affinity_words":128,"initial_consumer_state":17})")};
  Object monitoring{object(R"({"ordinal":0,"during_first_page":[0,0,0,0,0,0,0],
    "during_page_count":[1,1,1,1,1,1,1],"during_offset_ticks":[1000000,1000000],
    "observer_wait_poll_limit":1000000,"control_region_index":0,
    "counter_limits":[[],[]],"hardware_identity":{"family":6,"model":62},"environment_sources":[]})")};
  Fixture() {
    const Object warmup{{"run_id", Value(std::string("native-warmup"))},
                        {"namespace_id", Value(std::string("warmup-namespace"))},
                        {"seed_hex", Value(std::string(64U, '0'))}};
    const Object measured{{"run_id", Value(std::string("native-measurement"))},
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
    calibration::NativeDiscoveryCapturePlan native{
        {{5'000'000'000'000U, 100'000'000'000U, 200000U, 200000U, 1'000'000'000'000U,
          513U, 1000000U},
         {512U, 64U, 4096U, workload::MasterSeed::from_hex(std::string(64U, '1')),
          "measurement-namespace"},
         {protocol::RunId::parse("native-warmup", "$test").value(),
          protocol::RunId::parse("native-measurement", "$test").value()},
         {17U}},
        {{2097152U, 4096U, 0U, 0U}, {2097152U, 4096U, 1U, 0U}},
        {2097152U, 4096U, 2U, 0U},
        32U,
        4096U,
        16384U,
        128U,
        {},
        {1U, 1U, 1U, 1U, 1U, 1U, 1U},
        {1000000U, 1000000U},
        1000000U,
        0U,
        {},
        {6U, 62U},
        protocol::RequestedHardwareState::h0,
        kPrestate};
    const auto layout = calibration::native_discovery_layout(native);
    resources.at("core_bytes") = value(layout.core_bytes);
    resources.at("monitor_bytes") = value(layout.monitor_bytes);
    resources.at("total_mapping_bytes") = value(layout.total_mapping_bytes);
    Value::Array sizes;
    for (const auto bytes : layout.region_bytes) {
      sizes.push_back(value(bytes));
    }
    resources.at("region_bytes") = Value(std::move(sizes));
  }
  auto parse() const {
    return runner::stage17::parse_native_discovery_capture(capture, resources,
                                                           monitoring, kPrestate);
  }
};

TEST(DiscoveryNativeInput, ConvertsExactDurationsAndExplicitSeedWithoutHardwareAccess) {
  Fixture fixture;
  const auto parsed = fixture.parse();
  ASSERT_TRUE(parsed);
  if (parsed) {
    EXPECT_EQ(parsed.value().discovery.session.warmup_duration_ticks,
              5'000'000'000'000U);
    EXPECT_EQ(parsed.value().discovery.session.measurement_duration_ticks,
              100'000'000'000U);
    EXPECT_EQ(parsed.value().discovery.arena.seed_namespace, "measurement-namespace");
    EXPECT_EQ(parsed.value().hardware_prestate.data(), kPrestate.data());
    EXPECT_FALSE(parsed.value().counter_limits[0U][0U].minor_faults.has_value());
    EXPECT_EQ(parsed.value().counter_limits[0U][0U].major_faults, 0U);
  }
}

TEST(DiscoveryNativeInput, RejectsUnqualifiedLayoutSizesBeforeAnyMapping) {
  for (const auto field : {"core_bytes", "monitor_bytes", "total_mapping_bytes"}) {
    Fixture fixture;
    fixture.resources.at(field) = value(1U);
    EXPECT_FALSE(fixture.parse());
  }
  Fixture fixture;
  fixture.resources.at("region_bytes") = Value(Value::Array(7U, value(4096U)));
  EXPECT_FALSE(fixture.parse());
}

TEST(DiscoveryNativeInput, RejectsScientificContextDriftAndNonIntegerInputs) {
  for (const auto field :
       {"warmup_ns", "measurement_ns", "ordinal", "context_ordinal"}) {
    Fixture fixture;
    fixture.capture.at(field) = value(1U);
    EXPECT_FALSE(fixture.parse());
    fixture.capture.at(field) = Value(true);
    EXPECT_FALSE(fixture.parse());
  }
  Fixture fixture;
  fixture.capture.at("hardware_state") = Value(std::string("H1"));
  EXPECT_FALSE(fixture.parse());
}

TEST(DiscoveryNativeInput, RejectsImplicitArenaSeedAndUnknownControlFields) {
  Fixture fixture;
  fixture.capture.at("arena_seed") = fixture.capture.at("warmup");
  EXPECT_FALSE(fixture.parse());
  Fixture unknown;
  unknown.monitoring.emplace("skip_controls", Value(true));
  EXPECT_FALSE(unknown.parse());
}

TEST(DiscoveryNativeInput, RejectsCpuOverflowAndAbsentLimits) {
  Fixture fixture;
  auto geometry = *fixture.capture.at("geometry").as_object();
  geometry.at("producer_cpu") = value(std::numeric_limits<std::uint64_t>::max());
  fixture.capture.at("geometry") = Value(std::move(geometry));
  EXPECT_FALSE(fixture.parse());
  Fixture bounds;
  bounds.monitoring.at("counter_limits") = Value(Value::Array{});
  EXPECT_FALSE(bounds.parse());
}

TEST(DiscoveryNativeInput, RejectsAbsentMalformedAndDuplicateEnvironmentSources) {
  Fixture absent;
  absent.monitoring.erase("environment_sources");
  EXPECT_FALSE(absent.parse());
  const auto source = object(R"({"path":"/proc/self/smaps","byte_capacity":4096,
    "chunk_bytes":1024,"max_data_reads":8,"requested":[true,true,true,true,true,true]})");
  for (const auto field :
       {"path", "byte_capacity", "chunk_bytes", "max_data_reads", "requested"}) {
    Fixture malformed;
    auto changed = source;
    changed.erase(field);
    malformed.monitoring.at("environment_sources") =
        Value(Value::Array{Value(changed)});
    EXPECT_FALSE(malformed.parse());
  }
  Fixture duplicate;
  duplicate.monitoring.at("environment_sources") =
      Value(Value::Array{Value(source), Value(source)});
  EXPECT_FALSE(duplicate.parse());
  Fixture wrong_type;
  auto changed = source;
  changed.at("requested") = Value(Value::Array(6U, value(1U)));
  wrong_type.monitoring.at("environment_sources") = Value(Value::Array{Value(changed)});
  EXPECT_FALSE(wrong_type.parse());
}

TEST(DiscoveryNativeInput,
     SizingBindsEnvironmentalStorageWithoutAdmittingPlaceholders) {
  Fixture fixture;
  const auto source = object(R"({"path":"/proc/self/smaps","byte_capacity":4096,
    "chunk_bytes":1024,"max_data_reads":8,"requested":[true,true,true,true,true,true]})");
  fixture.monitoring.at("environment_sources") = Value(Value::Array{Value(source)});
  const auto described = runner::stage17::describe_native_discovery_layout(
      fixture.capture, fixture.resources, fixture.monitoring, kPrestate);
  ASSERT_TRUE(described);
  EXPECT_FALSE(fixture.parse());
  if (described) {
    fixture.resources.at("core_bytes") = value(described.value().core_bytes);
    fixture.resources.at("monitor_bytes") = value(described.value().monitor_bytes);
    fixture.resources.at("total_mapping_bytes") =
        value(described.value().total_mapping_bytes);
    const auto parsed = fixture.parse();
    ASSERT_TRUE(parsed);
    if (parsed) {
      ASSERT_EQ(parsed.value().environment_sources.size(), 1U);
      EXPECT_EQ(parsed.value().environment_sources[0U].path, "/proc/self/smaps");
      EXPECT_EQ(parsed.value().environment_sources[0U].byte_capacity, 4096U);
      EXPECT_TRUE(parsed.value().environment_sources[0U].requested[5U]);
    }
  }
}
} // namespace
