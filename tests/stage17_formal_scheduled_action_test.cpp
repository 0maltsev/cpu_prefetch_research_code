#include "cpu_prefetch/runner/stage17_formal_scheduled_action.hpp"

#include "cpu_prefetch/runner/software_prefetch.hpp"
#include <gtest/gtest.h>

#include <chrono>
#include <fcntl.h>
#include <functional>
#include <limits>
#include <sys/mman.h>
#include <unistd.h>

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
      R"({"schema_version":"cpu-prefetch-stage17-formal-scheduled-capture/1",
    "method_id":"MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1","package":"R0",
    "ordinal":0,"cell_ordinal":0,"load_level":"L025","scale_ordinal":0,"repetition_ordinal":0,"linked_order":null,"ring_distance":null,"hardware_state":"H0","placement":"NEAR",
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
    Value::Array schedules;
    for (std::size_t i = 0U; i < 2U; ++i) {
      schedules.emplace_back(Object{
          {"schedule_id",
           Value(std::string(i == 0U ? "warmup-schedule" : "measurement-schedule"))},
          {"seed_id", Value(std::string(i == 0U ? "warmup-schedule-seed"
                                                : "measurement-schedule-seed"))},
          {"seed_hex", Value(std::string(64U, i == 0U ? '3' : '4'))},
          {"namespace_id",
           Value(std::string(i == 0U ? "warmup-schedule-namespace"
                                     : "measurement-schedule-namespace"))},
          {"source_origin_ticks", value(1000U)},
          {"source_horizon_ticks",
           value(i == 0U ? 5'000'000'001'000U : 100'000'001'000U)},
          {"offered_count", value(2U)},
          {"deadline_ticks", Value(Value::Array{value(1000U), value(2000U)})},
          {"source_artifact",
           Value(Object{
               {"artifact_id",
                Value(std::string(i == 0U ? "warmup-source" : "measurement-source"))},
               {"sha256", Value(std::string(64U, i == 0U ? 'a' : 'b'))}})}});
    }
    capture.emplace("schedules", Value(std::move(schedules)));
    refresh_layout();
  }
  void mutate_schedule(std::size_t i, const std::function<void(Object&)>& change) {
    auto schedules = *capture.at("schedules").as_array();
    auto source = *schedules[i].as_object();
    change(source);
    schedules[i] = Value(std::move(source));
    capture.at("schedules") = Value(std::move(schedules));
  }
  auto parse() const {
    return runner::stage17::parse_native_formal_scheduled_capture(
        capture, resources, monitoring, kPrestate);
  }
  void refresh_layout() {
    const auto described = runner::stage17::describe_native_formal_scheduled_layout(
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
  void configure_cell(std::uint64_t cell, std::uint64_t load = 0U) {
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
    capture.at("cell_ordinal") = value(cell * 3U + load);
    capture.at("load_level") = Value(
        std::string(std::array<std::string_view, 3U>{"L025", "L050", "L075"}[load]));
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

TEST(FormalScheduledNativeInput, CoversAllCellsAndBothPhaseBounds) {
  for (std::uint64_t cell = 0U; cell < 180U; ++cell) {
    Fixture f;
    f.configure_cell(cell / 3U, cell % 3U);
    const auto parsed = f.parse();
    ASSERT_TRUE(parsed);
    EXPECT_EQ(parsed.value().plan().scheduled.service.session.phases[0U].duration_ticks,
              5'000'000'000'000U);
    EXPECT_EQ(parsed.value().plan().scheduled.service.session.phases[1U].duration_ticks,
              100'000'000'000U);
    EXPECT_EQ(parsed.value().plan().controls.workers.consumer_stack.owner_cpu,
              ((cell / 3U) % 12U) / 3U % 2U == 0U ? 1U : 8U);
  }
}

TEST(FormalScheduledNativeInput, SealedOriginalSourcesRequireExplicitBoundContext) {
  Fixture f;
  constexpr std::array<unsigned char, 16U> bytes{0, 0, 0, 0, 0, 0, 3, 232,
                                                 0, 0, 0, 0, 0, 0, 7, 208};
  constexpr auto hash =
      "9ad73ef44071e053f7c97cecc2d125c201b883a22482eba73b98482585cb239c";
  const auto writer =
      ::memfd_create("formal-source-test", MFD_CLOEXEC | MFD_ALLOW_SEALING);
  ASSERT_GE(writer, 0);
  ASSERT_EQ(::write(writer, bytes.data(), bytes.size()), 16);
  ASSERT_EQ(::fcntl(writer, F_ADD_SEALS,
                    F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL),
            0);
  const auto reader =
      ::open(("/proc/self/fd/" + std::to_string(writer)).c_str(), O_RDONLY | O_CLOEXEC);
  ASSERT_GE(reader, 0);
  f.capture.at("schema_version") =
      Value(std::string("cpu-prefetch-stage17-formal-scheduled-capture/2"));
  for (std::size_t phase = 0U; phase < 2U; ++phase)
    f.mutate_schedule(phase, [&](Object& source) {
      source.erase("deadline_ticks");
      source.emplace("storage_format", Value(std::string("SEALED_U64BE_ORIGINAL-v1")));
      auto artifact = *source.at("source_artifact").as_object();
      artifact.at("sha256") = Value(std::string(hash));
      source.at("source_artifact") = Value(std::move(artifact));
    });
  std::array<runner::stage17::FormalScheduleSourceBinding, 2U> bindings{
      {{"warmup-source", hash, 16U, reader},
       {"measurement-source", hash, 16U, reader}}};
  const runner::stage17::FormalScheduleSourceContext context{
      bindings, 64U, std::numeric_limits<std::uint64_t>::max()};
  const auto parse = [&] {
    return runner::stage17::parse_native_formal_scheduled_capture_from_sources(
        f.capture, f.resources, f.monitoring, kPrestate, context);
  };
  EXPECT_FALSE(f.parse());
  auto parsed = parse();
  ASSERT_TRUE(parsed) << (parsed ? "" : parsed.errors().front().message);
  EXPECT_EQ(parsed.value().plan().scheduled.deadlines[0U][1U], 2000U);
  EXPECT_EQ(parsed.value().plan().scheduled.deadlines[1U][0U], 1000U);
  auto provisional = f.resources;
  provisional.at("total_mapping_bytes") = value(1U);
  const auto described =
      runner::stage17::describe_native_formal_scheduled_layout_from_sources(
          f.capture, provisional, f.monitoring, kPrestate, context);
  ASSERT_TRUE(described);
  EXPECT_EQ(described.value().total_mapping_bytes,
            std::get<std::uint64_t>(
                f.resources.at("total_mapping_bytes").as_number()->value));
  EXPECT_FALSE(runner::stage17::parse_native_formal_scheduled_capture_from_sources(
      f.capture, provisional, f.monitoring, kPrestate, context));
  bindings[1U].canonical_sha256 = std::string(64U, '0');
  EXPECT_FALSE(parse());
  bindings[1U].canonical_sha256 = hash;
  bindings[1U].size_bytes = 15U;
  EXPECT_FALSE(parse());
  bindings[1U].size_bytes = 16U;
  bindings[1U].descriptor = writer;
  EXPECT_FALSE(parse());
  ASSERT_EQ(::close(reader), 0);
  ASSERT_EQ(::close(writer), 0);
  // Native arrays own the checked values after the borrowed descriptors close.
  EXPECT_EQ(parsed.value().plan().scheduled.deadlines[1U][1U], 2000U);
}

class FamilySources final {
public:
  Object plan;
  Object context;
  std::vector<int> readers;
  FamilySources() {
    Value::Array captures;
    Value::Array bindings;
    for (std::size_t ordinal = 0U; ordinal < 180U; ++ordinal) {
      Value::Array sources;
      for (std::size_t phase = 0U; phase < 2U; ++phase) {
        const auto writer =
            ::memfd_create("source-context-test", MFD_CLOEXEC | MFD_ALLOW_SEALING);
        if (writer < 0 || ::ftruncate(writer, 16) != 0 ||
            ::fcntl(writer, F_ADD_SEALS,
                    F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL) != 0)
          throw std::runtime_error("source fixture creation failed");
        const auto reader = ::open(("/proc/self/fd/" + std::to_string(writer)).c_str(),
                                   O_RDONLY | O_CLOEXEC);
        static_cast<void>(::close(writer));
        if (reader < 0)
          throw std::runtime_error("source fixture reopen failed");
        readers.push_back(reader);
        const auto id = "original-" + std::to_string(2U * ordinal + phase);
        const Object artifact{{"artifact_id", Value(id)},
                              {"sha256", Value(std::string(64U, 'a'))}};
        sources.emplace_back(
            Object{{"source_artifact", Value(artifact)}, {"offered_count", value(2U)}});
        bindings.emplace_back(
            Object{{"artifact_id", Value(id)},
                   {"sha256", Value(std::string(64U, 'a'))},
                   {"size_bytes", value(16U)},
                   {"descriptor", value(static_cast<std::uint64_t>(reader))}});
      }
      captures.emplace_back(
          Object{{"capture", Value(Object{{"schedules", Value(std::move(sources))}})}});
    }
    const auto now = std::chrono::duration_cast<std::chrono::nanoseconds>(
                         std::chrono::steady_clock::now().time_since_epoch())
                         .count();
    plan = Object{
        {"schema_version",
         Value(std::string("cpu-prefetch-stage17-formal-scheduled-plan/3"))},
        {"budget", Value(Object{{"setup_ns", value(60'000'000'000U)}})},
        {"source_transport", Value(Object{{"owned_vector_bytes", value(5760U)},
                                          {"loader_transient_bytes", value(8208U)},
                                          {"metadata_bytes", value(1024U * 1024U)}})},
        {"captures", Value(std::move(captures))}};
    context =
        Object{{"schema_version",
                Value(std::string("cpu-prefetch-stage17-schedule-source-context/1"))},
               {"deadline_monotonic_ns",
                value(static_cast<std::uint64_t>(now) + 30'000'000'000U)},
               {"bindings", Value(std::move(bindings))}};
  }
  ~FamilySources() {
    for (const auto reader : readers)
      static_cast<void>(::close(reader));
  }
  FamilySources(const FamilySources&) = delete;
  auto operator=(const FamilySources&) -> FamilySources& = delete;
};

TEST(FormalScheduledNativeInput,
     WholeFamilySourceContextRejectsMissingExtraChangedAndAliasedDescriptors) {
  FamilySources f;
  using runner::stage17::parse_formal_schedule_source_context;
  auto accepted = parse_formal_schedule_source_context(f.plan, f.context, {});
  ASSERT_TRUE(accepted) << (accepted ? "" : accepted.errors().front().message);
  EXPECT_EQ(accepted.value().bindings.size(), 360U);
  const std::array reserved{f.readers[0U]};
  EXPECT_FALSE(parse_formal_schedule_source_context(f.plan, f.context, reserved));
  auto bindings = *f.context.at("bindings").as_array();
  bindings.pop_back();
  auto context = f.context;
  context.at("bindings") = Value(bindings);
  EXPECT_FALSE(parse_formal_schedule_source_context(f.plan, context, {}));
  bindings.push_back(*f.context.at("bindings").as_array()->rbegin());
  bindings.push_back(bindings.back());
  context.at("bindings") = Value(bindings);
  EXPECT_FALSE(parse_formal_schedule_source_context(f.plan, context, {}));
  for (const auto field : {"sha256", "size_bytes", "descriptor", "artifact_id"}) {
    bindings = *f.context.at("bindings").as_array();
    auto second = *bindings[1U].as_object();
    second.at(field) = bindings[0U].as_object()->at(field);
    if (std::string_view(field) == "sha256")
      second.at(field) = Value(std::string(64U, '0'));
    if (std::string_view(field) == "size_bytes")
      second.at(field) = value(15U);
    bindings[1U] = Value(std::move(second));
    context.at("bindings") = Value(std::move(bindings));
    EXPECT_FALSE(parse_formal_schedule_source_context(f.plan, context, {})) << field;
  }
  // Different FD numbers still cannot alias the same original memfd.
  const auto alias = ::dup(f.readers[0U]);
  ASSERT_GE(alias, 0);
  bindings = *f.context.at("bindings").as_array();
  auto second = *bindings[1U].as_object();
  second.at("descriptor") = value(static_cast<std::uint64_t>(alias));
  bindings[1U] = Value(std::move(second));
  context.at("bindings") = Value(std::move(bindings));
  EXPECT_FALSE(parse_formal_schedule_source_context(f.plan, context, {}));
  ASSERT_EQ(::close(alias), 0);
  for (const auto deadline :
       std::array<std::uint64_t, 2U>{1U, std::numeric_limits<std::uint64_t>::max()}) {
    context = f.context;
    context.at("deadline_monotonic_ns") = value(deadline);
    EXPECT_FALSE(parse_formal_schedule_source_context(f.plan, context, {}));
  }
}
TEST(FormalScheduledNativeInput, RequiresExactPackageCellAndMethod) {
  Fixture f;
  f.capture.at("package") = Value(std::string("L1"));
  EXPECT_FALSE(f.parse());
  Fixture method;
  method.capture.at("method_id") = Value(std::string("wrong"));
  EXPECT_FALSE(method.parse());
  Fixture ordinal;
  ordinal.capture.at("cell_ordinal") = value(180U);
  EXPECT_FALSE(ordinal.parse());
}
TEST(FormalScheduledNativeInput, RequiresAcceptedSoftwareMappingForDeclaredModel) {
  Fixture f;
  f.capture.at("software_prefetch_mapping_id") = Value(std::string("unknown-mapping"));
  EXPECT_FALSE(f.parse());
  f.capture.at("software_prefetch_mapping_id") =
      Value(std::string(runner::kSoftwarePrefetchMappingId));
  EXPECT_FALSE(f.parse());
}
TEST(FormalScheduledNativeInput, RequiresLinkedSeedAndRejectsItForRing) {
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
TEST(FormalScheduledNativeInput, RequiresR1OneLineAndR2ExplicitEvidence) {
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
TEST(FormalScheduledNativeInput, RejectsStaleLayoutAndUncoveredCapacity) {
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
TEST(FormalScheduledNativeInput, RejectsWindowOverflowAndMissingWarmup) {
  Fixture f;
  f.capture.at("warmup_ns") = value(0U);
  EXPECT_FALSE(f.parse());
  Fixture overflow;
  overflow.capture.at("measurement_ns") =
      value(std::numeric_limits<std::uint64_t>::max());
  EXPECT_FALSE(overflow.parse());
}
TEST(FormalScheduledNativeInput, RejectsNoncanonicalSeedAndReusedPhaseIdentity) {
  Fixture f;
  auto identity = *f.capture.at("warmup").as_object();
  identity.at("seed_hex") = Value(std::string(64U, 'A'));
  f.capture.at("warmup") = Value(std::move(identity));
  EXPECT_FALSE(f.parse());
  Fixture reuse;
  reuse.capture.at("warmup") = reuse.capture.at("measurement");
  EXPECT_FALSE(reuse.parse());
}

TEST(FormalScheduledNativeInput, RejectsScheduleBoundariesCountsSeedsAndProvenance) {
  for (unsigned mutant = 0U; mutant < 10U; ++mutant) {
    Fixture f;
    f.mutate_schedule(1U, [&](Object& source) {
      switch (mutant) {
      case 0:
        source.at("deadline_ticks") = Value(Value::Array{value(999U), value(2000U)});
        break;
      case 1:
        source.at("deadline_ticks") =
            Value(Value::Array{value(1000U), value(100'000'001'000U)});
        break;
      case 2:
        source.at("deadline_ticks") = Value(Value::Array{value(2000U), value(1000U)});
        break;
      case 3:
        source.at("offered_count") = value(3U);
        break;
      case 4:
        source.at("source_horizon_ticks") = value(2000U);
        break;
      case 5:
        source.at("schedule_id") = Value(std::string("warmup-schedule"));
        break;
      case 6:
        source.at("namespace_id") = Value(std::string("warmup-schedule-namespace"));
        break;
      case 7:
        source.at("seed_id") = Value(std::string("warmup-schedule-seed"));
        break;
      case 8:
        source.erase("source_artifact");
        break;
      default:
        source.at("source_artifact") =
            Value(Object{{"artifact_id", Value(std::string("source"))},
                         {"sha256", Value(std::string("bad"))}});
        break;
      }
    });
    EXPECT_FALSE(f.parse()) << mutant;
  }
}
TEST(FormalScheduledNativeInput,
     SharedMasterSeedWithDisjointScheduleNamespacesIsValid) {
  Fixture f;
  f.mutate_schedule(
      1U, [](Object& source) { source.at("seed_hex") = Value(std::string(64U, '3')); });
  EXPECT_TRUE(f.parse());
}
TEST(FormalScheduledNativeInput, RejectsEmptyMeasurementButNotInventedWarmupMinimum) {
  Fixture measured;
  measured.mutate_schedule(1U, [](Object& s) {
    s.at("offered_count") = value(0U);
    s.at("deadline_ticks") = Value(Value::Array{});
  });
  EXPECT_FALSE(measured.parse());
  Fixture warmup;
  warmup.mutate_schedule(0U, [](Object& s) {
    s.at("offered_count") = value(0U);
    s.at("deadline_ticks") = Value(Value::Array{});
  });
  warmup.refresh_layout();
  EXPECT_TRUE(warmup.parse());
}
TEST(FormalScheduledNativeInput,
     OwnedDeadlinesSurviveParsedCopyMoveAndJsonDestruction) {
  auto owned = [] {
    Fixture f;
    auto parsed = f.parse();
    if (!parsed)
      throw std::logic_error("parse failed");
    return parsed.value();
  }();
  auto copied = owned;
  auto moved = std::move(copied);
  auto native = moved.plan();
  ASSERT_EQ(native.scheduled.deadlines[1U].size(), 2U);
  EXPECT_EQ(native.scheduled.deadlines[1U][1U], 2000U);
  EXPECT_EQ(native.scheduled.deadlines[0U].data(),
            owned.plan().scheduled.deadlines[0U].data());
  // No borrowed environmental paths in this fixture.
}
TEST(FormalScheduledNativeInput, HardwarePrestateSurvivesParserScopeCopyAndMove) {
  auto owned = [] {
    Fixture f;
    auto prestate = kPrestate;
    auto parsed = runner::stage17::parse_native_formal_scheduled_capture(
        f.capture, f.resources, f.monitoring, prestate);
    if (!parsed)
      throw std::logic_error("parse failed");
    // The accepted state is a snapshot, even when the caller reuses its buffer.
    prestate[0U] = {99U, 0xffffU};
    EXPECT_EQ(parsed.value().plan().controls.hardware_prestate[0U].cpu, 0U);
    return parsed.value();
  }();
  auto copied = owned;
  auto moved = std::move(copied);
  const auto native = moved.plan();
  ASSERT_EQ(native.controls.hardware_prestate.size(), kPrestate.size());
  for (std::size_t i = 0U; i < kPrestate.size(); ++i) {
    EXPECT_EQ(native.controls.hardware_prestate[i].cpu, kPrestate[i].cpu);
    EXPECT_EQ(native.controls.hardware_prestate[i].value, kPrestate[i].value);
  }
  EXPECT_NO_THROW((void)calibration::native_formal_scheduled_layout(native));
}
TEST(FormalScheduledNativeInput, LoadScaleUnknownFieldsAndMemoryBudgetFailClosed) {
  Fixture load;
  load.capture.at("load_level") = Value(std::string("L075"));
  EXPECT_FALSE(load.parse());
  Fixture scale;
  scale.capture.at("scale_ordinal") = value(5U);
  EXPECT_FALSE(scale.parse());
  Fixture unknown;
  unknown.capture.emplace("extra", value(1U));
  EXPECT_FALSE(unknown.parse());
  Fixture bound;
  auto budget = *bound.capture.at("budget").as_object();
  budget.at("memory_bytes") = value(8U);
  bound.capture.at("budget") = Value(std::move(budget));
  EXPECT_FALSE(bound.parse());
}
} // namespace
