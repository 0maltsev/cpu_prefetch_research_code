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
auto fixture(Action action = Action::q16a) -> Object {
  const bool ring = action == Action::q16a;
  const bool scheduled = action == Action::q16c;
  const std::size_t cells = ring ? 12U : scheduled ? 180U : 60U;
  const std::size_t repetitions = scheduled ? 1U : 59U;
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

auto archived_fixture(Action action) -> Object {
  auto plan = fixture(action);
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
} // namespace
