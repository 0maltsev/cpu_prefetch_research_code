#include "cpu_prefetch/runner/stage17_formal_family.hpp"

#include <gtest/gtest.h>

#include <array>
#include <iomanip>
#include <limits>
#include <sstream>

namespace {
using namespace cpu_prefetch;
using Value = protocol::json::Value;
using Object = Value::Object;
using Array = Value::Array;
using Action = runner::stage17::FixedAction;
auto number(std::uint64_t n) -> Value {
  return Value(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                      std::to_string(n), n});
}
auto text(std::string_view s) -> Value { return Value(std::string(s)); }
auto identity(std::size_t ordinal, std::string_view phase) -> Value {
  const auto tag = std::string(phase) + "-" + std::to_string(ordinal);
  std::ostringstream seed;
  seed << std::hex << std::setw(64) << std::setfill('0')
       << ordinal * 2U + (phase == "warmup" ? 0U : 1U);
  return Value(Object{{"run_id", text(tag)},
                      {"seed_id", text("seed-" + tag)},
                      {"namespace_id", text(phase)},
                      {"seed_hex", text(seed.str())}});
}
auto fixture(Action action = Action::q16a, std::size_t planned_repetitions = 59U)
    -> Object {
  const bool ring = action == Action::q16a;
  const bool scheduled = action == Action::q16c;
  const std::size_t cells = ring ? 12U : scheduled ? 180U : 60U;
  const std::size_t repetitions = scheduled ? 1U : planned_repetitions;
  const auto method = ring        ? "RING-D2-RUNTAIL-LTL95C95-WINDOW-v2"
                      : scheduled ? "MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1"
                                  : "SERVICE-RATE-NP-LTL95C95-MIN-v1";
  const auto schema = ring        ? "cpu-prefetch-stage17-formal-ring-plan/1"
                      : scheduled ? "cpu-prefetch-stage17-formal-scheduled-plan/1"
                                  : "cpu-prefetch-stage17-formal-service-plan/1";
  constexpr std::array packages{"R0", "R1", "R2", "L0", "L1"};
  constexpr std::array classes{"L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC"};
  constexpr std::array loads{"L025", "L050", "L075"};
  Array entries;
  for (std::size_t state = 0U; state < 2U; ++state)
    for (std::size_t package = 0U; package < (ring ? 1U : 5U); ++package)
      for (std::size_t context = 0U; context < 6U; ++context)
        for (std::size_t load = 0U; load < (scheduled ? 3U : 1U); ++load)
          for (std::size_t repetition = 0U; repetition < repetitions; ++repetition) {
            const auto ordinal = entries.size();
            const auto cell = package * 12U + state * 6U + context;
            Object limits{{"producer_attempt_limit", number(10U)},
                          {"consumer_poll_limit", number(10U)},
                          {"drain_ns", number(1'000'000U)}};
            Object capture{
                {"ordinal", number(ordinal)},
                {ring ? "context_ordinal" : "cell_ordinal",
                 number(scheduled ? cell * 3U + load : cell)},
                {"repetition_ordinal", number(repetition)},
                {"package", text(packages[package])},
                {"hardware_state", text(state == 0U ? "H0" : "H1")},
                {"placement", text(context < 3U ? "NEAR" : "FAR")},
                {"working_set_class", text(classes[context % 3U])},
                {"warmup_ns", number(5'000'000'000U)},
                {"measurement_ns", number(1'000'000'000U)},
                {"method_id", text(method)},
                {"warmup", identity(ordinal, "warmup")},
                {"measurement", identity(ordinal, "measurement")},
                {"arena_seed", identity(ordinal, "measurement")},
                {"geometry", Value(Object{{"capacity", number(8U)}})},
                {"budget", Value(Object{{"phases", Value(Array{Value(limits),
                                                               Value(limits)})}})}};
            if (ring)
              capture.emplace("minimum_observations_per_series", number(2U));
            if (scheduled) {
              capture.emplace("scale_ordinal", number(0U));
              capture.emplace("load_level", text(loads[load]));
              const Value schedule(Object{{"offered_count", number(10U)}});
              capture.emplace("schedules", Value(Array{schedule, schedule}));
            }
            Object rows{{"producer_primary_rows", number(10U)},
                        {"consumer_primary_rows", number(10U)}};
            if (ring) {
              rows.emplace("producer_demand_rows", number(10U));
              rows.emplace("consumer_demand_rows", number(10U));
            }
            Object resources{
                {"ordinal", number(ordinal)},
                {"total_mapping_bytes", number(10000U)},
                {"phase_capacity", Value(Array{Value(rows), Value(rows)})}};
            Object budget{{"setup_ns", number(1'000'000U)},
                          {"publication_ns", number(1'000'000U)},
                          {"cleanup_ns", number(1'000'000U)},
                          {"watchdog_ns", number(7'000'000'000U)},
                          {"publication_memory_bytes", number(10000U)},
                          {"other_memory_bytes", number(10000U)},
                          {"memory_bytes", number(30000U)},
                          {"metadata_output_bytes", number(1000U)},
                          {"max_output_bytes", number(30000U)}};
            entries.emplace_back(
                Object{{"capture", Value(std::move(capture))},
                       {"resources", Value(std::move(resources))},
                       {"monitoring", Value(Object{{"ordinal", number(ordinal)}})},
                       {"execution_budget", Value(std::move(budget))}});
          }
  const auto count = cells * repetitions;
  const auto output = count * 30000U + 10000U;
  Object plan{
      {"schema_version", text(schema)},
      {"plan_id", text("software-only")},
      {"protocol_version", text("2.0.0-pre.3")},
      {"action_id", text(runner::stage17::to_string(action))},
      {"method_id", text(method)},
      {"source_revision", text(std::string(40U, 'a'))},
      {"clean_source", Value(true)},
      {"stand_id", text("synthetic-stand")},
      {ring ? "repetitions_per_context" : "repetitions_per_cell", number(repetitions)},
      {"measurement_ns", number(1'000'000'000U)},
      {"warmup_namespace", text("warmup")},
      {"measurement_namespace", text("measurement")},
      {"custody_policy_id", text("EXT007-RAW-NONE-STAND-PRIMARY-v1")},
      {"captures", Value(std::move(entries))},
      {"budget",
       Value(Object{{"setup_ns", number(1'000'000U)},
                    {"cleanup_ns", number(1'000'000U)},
                    {"watchdog_ns", number(count * 7'000'000'000U + 2'000'000U)},
                    {"controller_memory_bytes", number(100'000'000U)},
                    {"memory_bytes", number(100'030'000U)},
                    {"metadata_output_bytes", number(10000U)},
                    {"max_output_bytes", number(output)},
                    {"analysis_scratch_bytes", number(1000U)},
                    {"disk_reserve_bytes", number(1000U)},
                    {"required_free_disk_bytes", number(output + 2000U)}})}};
  if (ring)
    plan.emplace("minimum_observations_per_series", number(2U));
  if (scheduled)
    plan.emplace("scale_ordinal", number(0U));
  return plan;
}
auto validate(const Object& plan, Action action = Action::q16a) {
  return runner::stage17::validate_formal_family(action, plan, std::string(40U, 'a'));
}
// Mutations copy through the public immutable JSON accessors.
template <typename Change>
void change_entry(Object& plan, std::size_t index, Change change) {
  auto entries = *plan.at("captures").as_array();
  auto entry = *entries[index].as_object();
  change(entry);
  entries[index] = Value(std::move(entry));
  plan.at("captures") = Value(std::move(entries));
}
TEST(Stage17FormalFamily, CompleteProspectiveFamiliesHaveCheckedBudgets) {
  for (const auto action : {Action::q16a, Action::q16b, Action::q16c}) {
    const auto result = validate(fixture(action), action);
    ASSERT_TRUE(result) << (result ? "" : result.errors().front().message);
    EXPECT_EQ(result.value().captures.size(), action == Action::q16a   ? 708U
                                              : action == Action::q16b ? 3540U
                                                                       : 180U);
  }
}
TEST(Stage17FormalFamily, RejectsIncompleteAndReorderedFamilies) {
  auto plan = fixture();
  auto entries = *plan.at("captures").as_array();
  std::swap(entries[0U], entries[1U]);
  plan.at("captures") = Value(entries);
  EXPECT_FALSE(validate(plan));
  entries.pop_back();
  plan.at("captures") = Value(entries);
  EXPECT_FALSE(validate(plan));
}
TEST(Stage17FormalFamily, RejectsSourceMethodAndPhaseNamespaceDrift) {
  for (const auto field : {"source_revision", "method_id", "warmup_namespace"}) {
    auto plan = fixture();
    plan.at(field) = text(field == std::string_view("warmup_namespace") ? "measurement"
                                                                        : "different");
    EXPECT_FALSE(validate(plan));
  }
}
TEST(Stage17FormalFamily, RejectsRepeatedRunOrSeedAcrossTheCompleteFamily) {
  auto plan = fixture();
  change_entry(plan, 707U, [](Object& entry) {
    auto capture = *entry.at("capture").as_object();
    capture.at("warmup") = identity(0U, "warmup");
    entry.at("capture") = Value(capture);
  });
  EXPECT_FALSE(validate(plan));
}
TEST(Stage17FormalFamily, RejectsUnbudgetedTimeMemoryAndOutput) {
  for (const auto field : {"watchdog_ns", "memory_bytes", "max_output_bytes",
                           "publication_memory_bytes"}) {
    auto plan = fixture();
    change_entry(plan, 707U, [&](Object& entry) {
      auto budget = *entry.at("execution_budget").as_object();
      budget.at(field) = number(1U);
      entry.at("execution_budget") = Value(budget);
    });
    EXPECT_FALSE(validate(plan)) << field;
  }
}
TEST(Stage17FormalFamily, RejectsOverflowAndFamilyDiskOmission) {
  for (const auto field :
       {"watchdog_ns", "required_free_disk_bytes", "controller_memory_bytes"}) {
    auto plan = fixture();
    auto budget = *plan.at("budget").as_object();
    budget.at(field) = number(1U);
    plan.at("budget") = Value(budget);
    EXPECT_FALSE(validate(plan)) << field;
  }
  auto plan = fixture();
  plan.at("repetitions_per_context") =
      number(std::numeric_limits<std::uint64_t>::max());
  EXPECT_FALSE(validate(plan));
}
TEST(Stage17FormalFamily, RejectsOutcomeAdaptiveCapacityAndPairedGeometryChanges) {
  for (const auto field : {"geometry", "budget"}) {
    auto plan = fixture();
    change_entry(plan, 707U, [&](Object& entry) {
      auto capture = *entry.at("capture").as_object();
      auto changed = *capture.at(field).as_object();
      changed.emplace("unexpected", number(1U));
      capture.at(field) = Value(changed);
      entry.at("capture") = Value(capture);
    });
    EXPECT_FALSE(validate(plan)) << field;
  }
}
TEST(Stage17FormalFamily, RejectsExtraFieldsAndNonFormalActions) {
  auto plan = fixture();
  EXPECT_FALSE(validate(plan, Action::q15_r));
  plan.emplace("retry_until_valid", Value(true));
  EXPECT_FALSE(validate(plan));
}

auto archived_fixture(Action action, std::size_t repetitions = 59U) -> Object {
  auto plan = fixture(action, repetitions);
  auto version = *plan.at("schema_version").as_string();
  version.back() = '2';
  plan.at("schema_version") = text(version);
  plan.at("custody_policy_id") = text("EXT007-FORMAL-LOSSLESS-STAND-PRIMARY-v1");
  constexpr std::uint64_t gib = std::uint64_t{1024U} * 1024U * 1024U;
  plan.emplace(
      "storage",
      Value(
          Object{{"schema_version", text("cpu-prefetch-stage17-formal-storage-plan/1")},
                 {"program_id", text("shared-future-program")},
                 {"policy_id", text("EXT007-FORMAL-LOSSLESS-STAND-PRIMARY-v1")},
                 {"implementation_profile_sha256", text(std::string(64U, 'a'))},
                 {"program_scope_sha256", text(std::string(64U, 'b'))},
                 {"broker_address_space_bytes", number(gib)},
                 {"archive_quota_bytes", number(6'000'000'000'000U)},
                 {"workspace_bytes", number(512U * gib)},
                 {"analysis_scratch_bytes", number(256U * gib)},
                 {"disk_reserve_bytes", number(16U * gib)},
                 {"codec_address_space_bytes", number(2U * gib)},
                 {"codec_processes", number(1U)},
                 {"per_capture_archive_ns", number(1'000'000'000U)},
                 {"archive_staging_bytes", number(100000U)},
                 {"capture_workspace_overhead_bytes", number(4096U)},
                 {"checkpoint_bytes", number(1000U)},
                 {"analysis_capture_workspace_bytes", number(100000U)}}));
  auto family = *plan.at("budget").as_object();
  family.at("watchdog_ns") =
      number(plan.at("captures").as_array()->size() * 8'000'000'000U + 2'000'000U);
  family.at("memory_bytes") = number(100'030'000U + 3U * gib);
  family.at("analysis_scratch_bytes") = number(256U * gib);
  family.at("disk_reserve_bytes") = number(16U * gib);
  family.at("required_free_disk_bytes") = number(6'841'813'590'016U);
  plan.at("budget") = Value(std::move(family));
  return plan;
}

auto service_daycap_fixture(std::size_t repetitions = 2U) -> Object {
  auto plan = archived_fixture(Action::q16b, repetitions);
  plan.at("schema_version") = text("cpu-prefetch-stage17-formal-service-plan/3");
  plan.at("method_id") = text("SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1");
  return plan;
}

auto descriptive_scheduled_fixture() -> Object {
  auto plan = archived_fixture(Action::q16c);
  plan.at("schema_version") = text("cpu-prefetch-stage17-formal-scheduled-plan/3");
  plan.at("method_id") = text("MATRIX-FULL-DESCRIPTIVE-SCREEN-v1");
  auto entries = *plan.at("captures").as_array();
  for (std::size_t i = 0U; i < entries.size(); ++i) {
    auto item = *entries[i].as_object();
    auto capture = *item.at("capture").as_object();
    capture.emplace("schema_version",
                    text("cpu-prefetch-stage17-formal-scheduled-capture/2"));
    auto schedules = *capture.at("schedules").as_array();
    for (std::size_t phase = 0U; phase < 2U; ++phase) {
      auto source = *schedules[phase].as_object();
      source.emplace("storage_format", text("SEALED_U64BE_ORIGINAL-v1"));
      source.emplace("source_artifact",
                     Value(Object{{"artifact_id",
                                   text("source-" + std::to_string(i * 2U + phase))},
                                  {"sha256", text(std::string(64U, 'a'))}}));
      schedules[phase] = Value(std::move(source));
    }
    capture.at("schedules") = Value(std::move(schedules));
    item.at("capture") = Value(std::move(capture));
    entries[i] = Value(std::move(item));
  }
  plan.at("captures") = Value(std::move(entries));
  constexpr auto source_bytes = 180U * 2U * 10U * 8U;
  constexpr auto transient = 80U + 8192U;
  constexpr auto metadata = 1024U * 1024U;
  constexpr auto memory = 2U * source_bytes + transient + metadata;
  plan.emplace("source_transport",
               Value(Object{{"schema_version",
                             text("cpu-prefetch-stage17-schedule-transport-budget/1")},
                            {"format", text("SEALED_U64BE_ORIGINAL-v1")},
                            {"source_bytes", number(source_bytes)},
                            {"owned_vector_bytes", number(source_bytes)},
                            {"loader_transient_bytes", number(transient)},
                            {"descriptor_count", number(360U)},
                            {"metadata_bytes", number(metadata)},
                            {"maximum_source_memory_bytes", number(memory)}}));
  auto budget = *plan.at("budget").as_object();
  budget.at("memory_bytes") =
      number(100'030'000U + 3U * 1024U * 1024U * 1024U + memory);
  plan.at("budget") = Value(std::move(budget));
  return plan;
}

auto scheduled_continuation_fixture() -> Object {
  auto plan = descriptive_scheduled_fixture();
  plan.at("schema_version") = text("cpu-prefetch-stage17-formal-scheduled-plan/4");
  plan.at("method_id") = text("MATRIX-FULL-DESCRIPTIVE-CONTINUED-PLATFORM-STRATA-v1");
  auto captures = *plan.at("captures").as_array();
  captures.erase(captures.begin(), captures.begin() + 86);
  for (std::size_t ordinal = 0U; ordinal < captures.size(); ++ordinal) {
    auto item = *captures[ordinal].as_object();
    for (const auto field : {"capture", "resources", "monitoring"}) {
      auto part = *item.at(field).as_object();
      part.at("ordinal") = number(ordinal);
      item.at(field) = Value(std::move(part));
    }
    captures[ordinal] = Value(std::move(item));
  }
  plan.at("captures") = Value(std::move(captures));
  const auto binding = [](std::string_view hash, std::uint64_t bytes) {
    return Value(Object{{"path", text("/synthetic/evidence.json")},
                        {"size_bytes", number(bytes)},
                        {"sha256", text(hash)}});
  };
  Array reused;
  for (std::size_t i = 0U; i < 86U; ++i)
    reused.push_back(number(i));
  plan.emplace(
      "continuation",
      Value(Object{
          {"policy_id", text("Q16C-RETAINED-PREFIX-CONTINUATION-v1")},
          {"parent_plan",
           binding("36c15f402c7f20240da6b36472b9d0c56bcade8c1024604d0b1bd3deaef19a44",
                   3321611)},
          {"failed_family_receipt",
           binding("17540e9e3871cd5632205f1f6bc5526acdd2d8144a987e4611f80b6cd6abe2d8",
                   1082)},
          {"accepted_prefix_manifest", binding(std::string(64U, 'c'), 1000)},
          {"compatibility_manifest", binding(std::string(64U, 'd'), 1000)},
          {"reused_capture_ordinals", Value(std::move(reused))},
          {"original_first_ordinal", number(86)},
          {"original_total_captures", number(180)},
          {"remaining_capture_count", number(94)},
          {"seed_policy", text("PRESERVE_ORIGINAL_NUMERIC_SEEDS_FRESH_IDENTITIES")},
          {"monitor_path_replacements", Value(Array{})},
          {"future_retries", number(0)}}));
  plan.emplace(
      "platform_control",
      Value(Object{
          {"schema_version", text("cpu-prefetch-q16c-platform-control/1")},
          {"control_path", text("/proc/sys/vm/compact_unevictable_allowed")},
          {"requested_value", number(0)},
          {"observation_policy", text("BEFORE_AUTHORIZATION_AFTER_CHECKPOINT-v1")},
          {"witness_transport", text("READ_ONLY_ROOT_LEASE_FD-v1")},
          {"metadata_output_bytes", number(2U * 1024U * 1024U)}}));
  auto transport = *plan.at("source_transport").as_object();
  transport.at("source_bytes") = number(94U * 2U * 10U * 8U);
  transport.at("owned_vector_bytes") = number(94U * 2U * 10U * 8U);
  transport.at("descriptor_count") = number(188U);
  plan.at("source_transport") = Value(std::move(transport));
  auto budget = *plan.at("budget").as_object();
  budget.at("watchdog_ns") = number(24'860'000'000'000U);
  budget.at("metadata_output_bytes") = number(16U * 1024U * 1024U);
  budget.at("max_output_bytes") = number(1'000'000'000U);
  plan.at("budget") = Value(std::move(budget));
  return plan;
}

TEST(Stage17FormalFamily, ScheduledContinuationPreserves94OriginalCellPositions) {
  const auto plan = scheduled_continuation_fixture();
  const auto accepted = validate(plan, Action::q16c);
  ASSERT_TRUE(accepted) << (accepted ? "" : accepted.errors().front().message);
  EXPECT_EQ(accepted.value().captures.size(), 94U);
  EXPECT_EQ(accepted.value().watchdog_ns, 24'860'000'000'000U);
  auto legacy = plan;
  legacy.at("schema_version") = text("cpu-prefetch-stage17-formal-scheduled-plan/3");
  EXPECT_FALSE(validate(legacy, Action::q16c));
  auto missing = plan;
  auto rows = *missing.at("captures").as_array();
  rows.pop_back();
  missing.at("captures") = Value(std::move(rows));
  EXPECT_FALSE(validate(missing, Action::q16c));
}

TEST(Stage17FormalFamily, ScheduledContinuationRejectsForgedIncidentControlOrOrder) {
  auto plan = scheduled_continuation_fixture();
  auto control = *plan.at("platform_control").as_object();
  control.at("requested_value") = number(1);
  plan.at("platform_control") = Value(std::move(control));
  EXPECT_FALSE(validate(plan, Action::q16c));
  plan = scheduled_continuation_fixture();
  auto proof = *plan.at("continuation").as_object();
  proof.at("original_first_ordinal") = number(85);
  plan.at("continuation") = Value(std::move(proof));
  EXPECT_FALSE(validate(plan, Action::q16c));
  plan = scheduled_continuation_fixture();
  change_entry(plan, 0U, [](auto& entry) {
    auto capture = *entry.at("capture").as_object();
    capture.at("ordinal") = number(86);
    entry.at("capture") = Value(std::move(capture));
  });
  EXPECT_FALSE(validate(plan, Action::q16c));
}

TEST(Stage17FormalFamily, DescriptiveScheduledCoverageAndCompleteTransportBudget) {
  auto plan = descriptive_scheduled_fixture();
  const auto accepted = validate(plan, Action::q16c);
  ASSERT_TRUE(accepted) << (accepted ? "" : accepted.errors().front().message);
  EXPECT_EQ(accepted.value().captures.size(), 180U);
  EXPECT_TRUE(accepted.value().storage);
  for (const auto field :
       {"source_bytes", "owned_vector_bytes", "loader_transient_bytes",
        "descriptor_count", "metadata_bytes", "maximum_source_memory_bytes"}) {
    auto changed = plan;
    auto transport = *changed.at("source_transport").as_object();
    transport.at(field) = number(0U);
    changed.at("source_transport") = Value(std::move(transport));
    EXPECT_FALSE(validate(changed, Action::q16c)) << field;
  }
  plan.at("method_id") = text("MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1");
  EXPECT_FALSE(validate(plan, Action::q16c));
  for (const auto field : {"repetitions_per_cell", "measurement_ns", "scale_ordinal"}) {
    auto changed = descriptive_scheduled_fixture();
    changed.at(field) = number(2U);
    EXPECT_FALSE(validate(changed, Action::q16c)) << field;
  }
}

auto service_continuation_fixture() -> Object {
  auto plan = service_daycap_fixture();
  plan.at("schema_version") = text("cpu-prefetch-stage17-formal-service-plan/4");
  auto captures = *plan.at("captures").as_array();
  captures.erase(captures.begin(), captures.begin() + 17);
  for (std::size_t ordinal = 0U; ordinal < captures.size(); ++ordinal) {
    auto item = *captures[ordinal].as_object();
    for (const auto field : {"capture", "resources", "monitoring"}) {
      auto part = *item.at(field).as_object();
      part.at("ordinal") = number(ordinal);
      item.at(field) = Value(std::move(part));
    }
    captures[ordinal] = Value(std::move(item));
  }
  plan.at("captures") = Value(std::move(captures));
  const auto binding = [](std::string_view hash, std::uint64_t bytes) {
    return Value(Object{{"path", text("/synthetic/evidence.json")},
                        {"size_bytes", number(bytes)},
                        {"sha256", text(hash)}});
  };
  Array reused;
  for (std::size_t i = 0U; i < 17U; ++i)
    reused.push_back(number(i));
  plan.emplace(
      "continuation",
      Value(Object{
          {"policy_id", text("Q16B-RETAINED-PREFIX-CONTINUATION-v1")},
          {"parent_plan",
           binding("53ef4baad885eeece98697d6c57b0dd0a375107504b277ffef7482185081e486",
                   2072840)},
          {"failed_family_receipt",
           binding("332662f64d2f802578c0152aec69781f3b913afca43efe2714483da7e80b3269",
                   1084)},
          {"accepted_prefix_manifest", binding(std::string(64U, 'c'), 1000)},
          {"compatibility_manifest", binding(std::string(64U, 'd'), 1000)},
          {"reused_capture_ordinals", Value(std::move(reused))},
          {"original_first_ordinal", number(17)},
          {"original_total_captures", number(120)},
          {"remaining_capture_count", number(103)},
          {"seed_policy", text("PRESERVE_ORIGINAL_NUMERIC_SEEDS_FRESH_IDENTITIES")},
          {"monitor_path_replacements", Value(Array{})},
          {"future_retries", number(0)}}));
  return plan;
}

TEST(Stage17FormalFamily, ServiceContinuationMaps103RealCapturesFromOriginal17) {
  const auto plan = service_continuation_fixture();
  const auto result = validate(plan, Action::q16b);
  ASSERT_TRUE(result) << (result ? "" : result.errors().front().message);
  EXPECT_EQ(result.value().captures.size(), 103U);
  const auto& first =
      *plan.at("captures").as_array()->front().as_object()->at("capture").as_object();
  EXPECT_EQ(std::get<std::uint64_t>(first.at("cell_ordinal").as_number()->value), 14U);
  EXPECT_EQ(std::get<std::uint64_t>(first.at("repetition_ordinal").as_number()->value),
            1U);
  EXPECT_EQ(result.value().watchdog_ns, 960'002'000'000U);
}

TEST(Stage17FormalFamily,
     ServiceContinuationRejectsMissingExtraOrWrongFirstRepetition) {
  for (const auto mutation : {0, 1, 2, 3}) {
    auto plan = service_continuation_fixture();
    auto entries = *plan.at("captures").as_array();
    if (mutation == 0)
      entries.pop_back();
    else if (mutation == 1)
      entries.push_back(entries.back());
    else {
      auto item = *entries.front().as_object();
      auto capture = *item.at("capture").as_object();
      capture.at(mutation == 2 ? "repetition_ordinal" : "cell_ordinal") = number(0);
      item.at("capture") = Value(std::move(capture));
      entries.front() = Value(std::move(item));
    }
    plan.at("captures") = Value(std::move(entries));
    EXPECT_FALSE(validate(plan, Action::q16b)) << mutation;
  }
  auto plan = service_continuation_fixture();
  plan.at("schema_version") = text("cpu-prefetch-stage17-formal-service-plan/3");
  EXPECT_FALSE(validate(plan, Action::q16b));
}

TEST(Stage17FormalFamily, ServiceContinuationRejectsDifferentIncidentOrMissingProofs) {
  for (const auto field : {"original_first_ordinal", "original_total_captures",
                           "remaining_capture_count", "future_retries"}) {
    auto plan = service_continuation_fixture();
    auto declaration = *plan.at("continuation").as_object();
    declaration.at(field) = number(1);
    plan.at("continuation") = Value(std::move(declaration));
    EXPECT_FALSE(validate(plan, Action::q16b)) << field;
  }
  for (const auto field : {"accepted_prefix_manifest", "compatibility_manifest"}) {
    auto plan = service_continuation_fixture();
    auto declaration = *plan.at("continuation").as_object();
    declaration.erase(field);
    plan.at("continuation") = Value(std::move(declaration));
    EXPECT_FALSE(validate(plan, Action::q16b)) << field;
  }
  auto plan = service_continuation_fixture();
  auto declaration = *plan.at("continuation").as_object();
  auto parent = *declaration.at("parent_plan").as_object();
  parent.at("sha256") = text(std::string(64U, '0'));
  declaration.at("parent_plan") = Value(std::move(parent));
  plan.at("continuation") = Value(std::move(declaration));
  EXPECT_FALSE(validate(plan, Action::q16b));
}

TEST(Stage17FormalFamily, ServiceDaycapHasAllSixtyCellsTwiceAndLegacyCaptureFormat) {
  const auto plan = service_daycap_fixture();
  const auto result = validate(plan, Action::q16b);
  ASSERT_TRUE(result) << (result ? "" : result.errors().front().message);
  EXPECT_EQ(result.value().captures.size(), 120U);
  const auto& storage = result.value().storage;
  ASSERT_TRUE(storage);
  if (storage) {
    EXPECT_EQ(storage->program_id, "shared-future-program");
  }
  EXPECT_EQ(result.value().watchdog_ns, 960'002'000'000U);
  EXPECT_EQ(result.value().required_free_disk_bytes, 6'841'813'590'016U);
  std::array<std::size_t, 60U> counts{};
  for (const auto& entry : *plan.at("captures").as_array()) {
    const auto& capture = *entry.as_object()->at("capture").as_object();
    const auto cell =
        std::get<std::uint64_t>(capture.at("cell_ordinal").as_number()->value);
    ASSERT_LT(cell, counts.size());
    ++counts[cell];
    EXPECT_EQ(*capture.at("method_id").as_string(), "SERVICE-RATE-NP-LTL95C95-MIN-v1");
  }
  for (const auto count : counts)
    EXPECT_EQ(count, 2U);
}

TEST(Stage17FormalFamily, ServiceDaycapRequiresExplicitFamilyAndCaptureMethods) {
  for (const auto method :
       {"SERVICE-RATE-NP-LTL95C95-MIN-v1", "SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v2",
        "RING-D2-RUNTAIL-LTL95C95-WINDOW-v2"}) {
    auto plan = service_daycap_fixture();
    plan.at("method_id") = text(method);
    EXPECT_FALSE(validate(plan, Action::q16b)) << method;
  }
  auto plan = service_daycap_fixture();
  change_entry(plan, 119U, [](Object& entry) {
    auto capture = *entry.at("capture").as_object();
    capture.at("method_id") = text("SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1");
    entry.at("capture") = Value(std::move(capture));
  });
  EXPECT_FALSE(validate(plan, Action::q16b));
  for (const auto version : {"1", "2", "4"}) {
    plan = service_daycap_fixture();
    plan.at("schema_version") =
        text(std::string("cpu-prefetch-stage17-formal-service-plan/") + version);
    EXPECT_FALSE(validate(plan, Action::q16b)) << version;
  }
  for (const auto action : {Action::q16a, Action::q16c}) {
    plan = service_daycap_fixture();
    plan.at("action_id") = text(runner::stage17::to_string(action));
    EXPECT_FALSE(validate(plan, action));
    plan = archived_fixture(action);
    auto schema = *plan.at("schema_version").as_string();
    schema.back() = '3';
    plan.at("schema_version") = text(schema);
    plan.at("method_id") = text("SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1");
    EXPECT_FALSE(validate(plan, action));
  }
}

TEST(Stage17FormalFamily, ServiceDaycapRequiresExactlyTwoRepetitionsPerCell) {
  for (const auto repetitions : {0U, 1U, 3U, 58U, 59U})
    EXPECT_FALSE(validate(service_daycap_fixture(repetitions), Action::q16b))
        << repetitions;
}

TEST(Stage17FormalFamily, ServiceDaycapRequiresExactCoverageAndProspectiveOrder) {
  auto plan = service_daycap_fixture();
  auto captures = *plan.at("captures").as_array();
  captures.pop_back();
  plan.at("captures") = Value(captures);
  EXPECT_FALSE(validate(plan, Action::q16b));
  captures.push_back(captures.back());
  captures.push_back(captures.back());
  plan.at("captures") = Value(captures);
  EXPECT_FALSE(validate(plan, Action::q16b));
  for (const auto field : {"ordinal", "cell_ordinal", "repetition_ordinal"}) {
    plan = service_daycap_fixture();
    change_entry(plan, 119U, [&](Object& entry) {
      auto capture = *entry.at("capture").as_object();
      capture.at(field) = number(0U);
      entry.at("capture") = Value(std::move(capture));
    });
    EXPECT_FALSE(validate(plan, Action::q16b)) << field;
  }
  for (const auto field :
       {"package", "hardware_state", "placement", "working_set_class"}) {
    plan = service_daycap_fixture();
    change_entry(plan, 119U, [&](Object& entry) {
      auto capture = *entry.at("capture").as_object();
      const auto& first = *plan.at("captures").as_array()->front().as_object();
      capture.at(field) = first.at("capture").as_object()->at(field);
      entry.at("capture") = Value(std::move(capture));
    });
    EXPECT_FALSE(validate(plan, Action::q16b)) << field;
  }
  plan = service_daycap_fixture();
  captures = *plan.at("captures").as_array();
  std::swap(captures[0U], captures[2U]);
  plan.at("captures") = Value(std::move(captures));
  EXPECT_FALSE(validate(plan, Action::q16b));
}

TEST(Stage17FormalFamily, ServiceDaycapRequiresOneSecondMeasurementAndFiveWarmup) {
  for (const auto duration : {500'000'000U, 2'000'000'000U}) {
    auto plan = service_daycap_fixture();
    plan.at("measurement_ns") = number(duration);
    auto family = *plan.at("budget").as_object();
    family.at("watchdog_ns") = number(86'400'000'000'000U);
    plan.at("budget") = Value(std::move(family));
    for (std::size_t i = 0U; i < 120U; ++i)
      change_entry(plan, i, [&](Object& entry) {
        auto capture = *entry.at("capture").as_object();
        capture.at("measurement_ns") = number(duration);
        entry.at("capture") = Value(std::move(capture));
        auto budget = *entry.at("execution_budget").as_object();
        budget.at("watchdog_ns") = number(9'000'000'000U);
        entry.at("execution_budget") = Value(std::move(budget));
      });
    EXPECT_FALSE(validate(plan, Action::q16b)) << duration;
  }
  for (const auto field : {"measurement_ns", "warmup_ns"}) {
    auto plan = service_daycap_fixture();
    change_entry(plan, 119U, [&](Object& entry) {
      auto capture = *entry.at("capture").as_object();
      capture.at(field) = number(500'000'000U);
      entry.at("capture") = Value(std::move(capture));
    });
    EXPECT_FALSE(validate(plan, Action::q16b)) << field;
  }
}

TEST(Stage17FormalFamily, ServiceDaycapWatchdogIncludesAllDeclaredTimeAndCapsOneDay) {
  for (const auto watchdog : {960'002'000'000U, 86'400'000'000'000U}) {
    auto plan = service_daycap_fixture();
    auto family = *plan.at("budget").as_object();
    family.at("watchdog_ns") = number(watchdog);
    plan.at("budget") = Value(std::move(family));
    const auto result = validate(plan, Action::q16b);
    ASSERT_TRUE(result) << (result ? "" : result.errors().front().message);
    EXPECT_EQ(result.value().watchdog_ns, watchdog);
  }
  for (const auto watchdog : {960'001'999'999U, 86'400'000'000'001U}) {
    auto plan = service_daycap_fixture();
    auto family = *plan.at("budget").as_object();
    family.at("watchdog_ns") = number(watchdog);
    plan.at("budget") = Value(std::move(family));
    EXPECT_FALSE(validate(plan, Action::q16b)) << watchdog;
  }
  auto plan = service_daycap_fixture();
  auto family = *plan.at("budget").as_object();
  family.at("watchdog_ns") = number(86'400'000'000'000U);
  plan.at("budget") = Value(std::move(family));
  auto storage = *plan.at("storage").as_object();
  storage.at("per_capture_archive_ns") = number(720'000'000'000U);
  plan.at("storage") = Value(std::move(storage));
  EXPECT_FALSE(validate(plan, Action::q16b));
}

TEST(Stage17FormalFamily, ServiceDaycapRetainsArchivedStorageAndBudgetChecks) {
  auto plan = service_daycap_fixture();
  plan.erase("storage");
  EXPECT_FALSE(validate(plan, Action::q16b));
  plan = service_daycap_fixture();
  plan.at("custody_policy_id") = text("EXT007-RAW-NONE-STAND-PRIMARY-v1");
  EXPECT_FALSE(validate(plan, Action::q16b));
  for (const auto field :
       {"archive_quota_bytes", "workspace_bytes", "analysis_scratch_bytes",
        "disk_reserve_bytes", "codec_address_space_bytes", "codec_processes",
        "checkpoint_bytes", "archive_staging_bytes",
        "analysis_capture_workspace_bytes"}) {
    plan = service_daycap_fixture();
    auto storage = *plan.at("storage").as_object();
    storage.at(field) = number(1'000'000'000'000U);
    plan.at("storage") = Value(std::move(storage));
    EXPECT_FALSE(validate(plan, Action::q16b)) << field;
  }
  for (const auto field : {"watchdog_ns", "controller_memory_bytes", "memory_bytes",
                           "max_output_bytes", "required_free_disk_bytes"}) {
    plan = service_daycap_fixture();
    auto family = *plan.at("budget").as_object();
    family.at(field) = number(1U);
    plan.at("budget") = Value(std::move(family));
    EXPECT_FALSE(validate(plan, Action::q16b)) << field;
  }
}

TEST(Stage17FormalFamily, ServiceDaycapRetainsGeometryIdentityAndResourceChecks) {
  for (const auto field :
       {"geometry", "budget", "warmup", "measurement", "arena_seed"}) {
    auto plan = service_daycap_fixture();
    change_entry(plan, 119U, [&](Object& entry) {
      auto capture = *entry.at("capture").as_object();
      auto value = *capture.at(field).as_object();
      if (field == std::string_view("geometry"))
        value.at("capacity") = number(9U);
      else if (field == std::string_view("budget"))
        value.emplace("unexpected", number(1U));
      else
        value = *identity(0U, field == std::string_view("warmup") ? "warmup"
                                                                  : "measurement")
                     .as_object();
      capture.at(field) = Value(std::move(value));
      entry.at("capture") = Value(std::move(capture));
    });
    EXPECT_FALSE(validate(plan, Action::q16b)) << field;
  }
  for (const auto field : {"resources", "monitoring"}) {
    auto plan = service_daycap_fixture();
    change_entry(plan, 119U, [&](Object& entry) {
      auto value = *entry.at(field).as_object();
      value.emplace("unexpected", number(1U));
      entry.at(field) = Value(std::move(value));
    });
    EXPECT_FALSE(validate(plan, Action::q16b)) << field;
  }
  for (const auto field : {"watchdog_ns", "memory_bytes", "max_output_bytes",
                           "publication_memory_bytes", "metadata_output_bytes"}) {
    auto plan = service_daycap_fixture();
    change_entry(plan, 119U, [&](Object& entry) {
      auto budget = *entry.at("execution_budget").as_object();
      budget.at(field) = number(1U);
      entry.at("execution_budget") = Value(std::move(budget));
    });
    EXPECT_FALSE(validate(plan, Action::q16b)) << field;
  }
}

TEST(Stage17FormalFamily, OriginalRingAndServiceVersionsKeepMinimumFiftyNine) {
  for (const auto action : {Action::q16a, Action::q16b}) {
    for (const auto repetitions : {2U, 58U}) {
      EXPECT_FALSE(validate(fixture(action, repetitions), action));
      EXPECT_FALSE(validate(archived_fixture(action, repetitions), action));
    }
    for (auto plan : {fixture(action, 60U), archived_fixture(action, 60U)}) {
      auto family = *plan.at("budget").as_object();
      family.at("watchdog_ns") = number(86'400'000'000'001U);
      plan.at("budget") = Value(std::move(family));
      EXPECT_TRUE(validate(plan, action));
      plan.at("method_id") = text("SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1");
      EXPECT_FALSE(validate(plan, action));
    }
  }
}

TEST(Stage17FormalFamily, ArchivedFamiliesKeepLogicalBoundsAndAddPhysicalPolicy) {
  for (const auto action : {Action::q16a, Action::q16b, Action::q16c}) {
    const auto old = validate(fixture(action), action);
    const auto current = validate(archived_fixture(action), action);
    ASSERT_TRUE(old);
    ASSERT_TRUE(current) << (current ? "" : current.errors().front().message);
    ASSERT_TRUE(current.value().storage);
    const auto& storage = current.value().storage;
    if (storage) {
      EXPECT_EQ(storage->program_id, "shared-future-program");
    }
    EXPECT_EQ(current.value().captures.size(), old.value().captures.size());
    EXPECT_EQ(current.value().max_output_bytes, old.value().max_output_bytes);
    EXPECT_EQ(current.value().required_free_disk_bytes, 6'841'813'590'016U);
  }
}

TEST(Stage17FormalFamily, ArchiveCannotLowerApprovedStorageOrOmitCheckpoint) {
  for (const auto field :
       {"archive_quota_bytes", "workspace_bytes", "analysis_scratch_bytes",
        "disk_reserve_bytes", "codec_address_space_bytes", "codec_processes"}) {
    auto plan = archived_fixture(Action::q16a);
    auto storage = *plan.at("storage").as_object();
    storage.at(field) = number(2U);
    plan.at("storage") = Value(std::move(storage));
    EXPECT_FALSE(validate(plan)) << field;
  }
  auto plan = archived_fixture(Action::q16a);
  auto storage = *plan.at("storage").as_object();
  storage.at("checkpoint_bytes") = number(1001U);
  plan.at("storage") = Value(std::move(storage));
  EXPECT_FALSE(validate(plan));
}

TEST(Stage17FormalFamily, ArchiveRejectsOversizedWorkspaceAndColdBudgetOmission) {
  for (const auto field : {"watchdog_ns", "memory_bytes", "required_free_disk_bytes"}) {
    auto plan = archived_fixture(Action::q16a);
    auto family = *plan.at("budget").as_object();
    family.at(field) = number(1U);
    plan.at("budget") = Value(std::move(family));
    EXPECT_FALSE(validate(plan)) << field;
  }
  for (const auto field :
       {"archive_staging_bytes", "analysis_capture_workspace_bytes"}) {
    auto plan = archived_fixture(Action::q16a);
    auto storage = *plan.at("storage").as_object();
    storage.at(field) = number(std::uint64_t{512U} * 1024U * 1024U * 1024U);
    plan.at("storage") = Value(std::move(storage));
    EXPECT_FALSE(validate(plan)) << field;
  }
}

TEST(Stage17FormalFamily, ArchiveRequiresExplicitVersionAndCompleteFamily) {
  auto plan = archived_fixture(Action::q16a);
  plan.at("schema_version") = text("cpu-prefetch-stage17-formal-ring-plan/1");
  EXPECT_FALSE(validate(plan));
  plan = archived_fixture(Action::q16a);
  plan.erase("storage");
  EXPECT_FALSE(validate(plan));
  plan = archived_fixture(Action::q16a);
  auto captures = *plan.at("captures").as_array();
  captures.pop_back();
  plan.at("captures") = Value(std::move(captures));
  EXPECT_FALSE(validate(plan));
}
auto continuation_fixture() -> Object {
  auto plan = archived_fixture(Action::q16a);
  plan.at("schema_version") = text("cpu-prefetch-stage17-formal-ring-plan/3");
  auto captures = *plan.at("captures").as_array();
  captures.erase(captures.begin(), captures.begin() + 177);
  for (std::size_t ordinal = 0; ordinal < captures.size(); ++ordinal) {
    auto entry = *captures[ordinal].as_object();
    for (const auto field : {"capture", "resources", "monitoring"}) {
      auto value = *entry.at(field).as_object();
      value.at("ordinal") = number(ordinal);
      entry.at(field) = Value(std::move(value));
    }
    captures[ordinal] = Value(std::move(entry));
  }
  plan.at("captures") = Value(std::move(captures));
  const auto binding = [](std::string_view hash, std::uint64_t bytes) {
    return Value(Object{{"path", text("/evidence/bound.json")},
                        {"size_bytes", number(bytes)},
                        {"sha256", text(hash)}});
  };
  plan.emplace(
      "continuation",
      Value(Object{
          {"policy_id", text("Q16A-COMPLETE-CONTEXT-CONTINUATION-v1")},
          {"parent_plan",
           binding("a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7",
                   12128860)},
          {"failed_family_receipt",
           binding("a6704159e3dd2adab1598e2959202cfa5a6a0b5c9164a01fab967deeb251c7e4",
                   1082)},
          {"accepted_prefix_manifest", binding(std::string(64U, 'c'), 1000)},
          {"compatibility_manifest", binding(std::string(64U, 'd'), 1000)},
          {"reused_contexts", Value(Array{number(0), number(1), number(2)})},
          {"remaining_contexts",
           Value(Array{number(3), number(4), number(5), number(6), number(7), number(8),
                       number(9), number(10), number(11)})},
          {"original_first_ordinal", number(177)},
          {"failed_original_ordinal", number(177)},
          {"seed_policy", text("PRESERVE_ORIGINAL_NUMERIC_SEEDS_FRESH_IDENTITIES")},
          {"monitor_path_replacements", Value(Array{})},
          {"future_retries", number(0)}}));
  return plan;
}

TEST(Stage17FormalFamily, ContinuationExecutesOnlyNineUnfinishedContexts) {
  const auto plan = continuation_fixture();
  const auto result = validate(plan);
  ASSERT_TRUE(result) << (result ? "" : result.errors().front().message);
  EXPECT_EQ(result.value().captures.size(), 531U);
  EXPECT_TRUE(result.value().storage.has_value());
}

TEST(Stage17FormalFamily, ContinuationKeepsExactFiftyNineAndOriginalDeadlineRules) {
  auto plan = continuation_fixture();
  for (const auto repetitions : {2U, 58U, 60U}) {
    plan.at("repetitions_per_context") = number(repetitions);
    EXPECT_FALSE(validate(plan)) << repetitions;
  }
  plan.at("repetitions_per_context") = number(59U);
  auto family = *plan.at("budget").as_object();
  family.at("watchdog_ns") = number(86'400'000'000'001U);
  plan.at("budget") = Value(std::move(family));
  EXPECT_TRUE(validate(plan));
  plan.at("method_id") = text("SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1");
  EXPECT_FALSE(validate(plan));
}

TEST(Stage17FormalFamily, ContinuationRejectsPrefixRerunAndArbitraryResume) {
  for (const auto field :
       {"original_first_ordinal", "failed_original_ordinal", "future_retries"}) {
    auto plan = continuation_fixture();
    auto continuation = *plan.at("continuation").as_object();
    continuation.at(field) = number(1U);
    plan.at("continuation") = Value(std::move(continuation));
    EXPECT_FALSE(validate(plan)) << field;
  }
  auto plan = continuation_fixture();
  change_entry(plan, 0U, [](Object& entry) {
    auto capture = *entry.at("capture").as_object();
    capture.at("context_ordinal") = number(0U);
    entry.at("capture") = Value(std::move(capture));
  });
  EXPECT_FALSE(validate(plan));
  plan = continuation_fixture();
  plan.at("schema_version") = text("cpu-prefetch-stage17-formal-ring-plan/2");
  EXPECT_FALSE(validate(plan));
}

TEST(Stage17FormalFamily, ContinuationRequiresExactIncidentAndBoundProofs) {
  for (const auto field : {"parent_plan", "failed_family_receipt",
                           "accepted_prefix_manifest", "compatibility_manifest"}) {
    auto plan = continuation_fixture();
    auto continuation = *plan.at("continuation").as_object();
    continuation.erase(field);
    plan.at("continuation") = Value(std::move(continuation));
    EXPECT_FALSE(validate(plan)) << field;
  }
  auto plan = continuation_fixture();
  auto continuation = *plan.at("continuation").as_object();
  auto parent = *continuation.at("parent_plan").as_object();
  parent.at("sha256") = text(std::string(64U, 'a'));
  continuation.at("parent_plan") = Value(std::move(parent));
  plan.at("continuation") = Value(std::move(continuation));
  EXPECT_FALSE(validate(plan));
}
} // namespace
