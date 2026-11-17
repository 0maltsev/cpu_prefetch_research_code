#include "cpu_prefetch/runner/stage17_formal_family.hpp"

#include "stage17_formal_input_detail.hpp"

#include <array>
#include <map>
#include <set>

namespace cpu_prefetch::runner::stage17 {
namespace {
namespace input = formal_input_detail;
using Object = protocol::json::Value::Object;
using Value = protocol::json::Value;

void require(bool condition, std::string_view message) {
  if (!condition)
    throw std::invalid_argument(std::string(message));
}
auto add(std::uint64_t a, std::uint64_t b) -> std::uint64_t {
  require(b <= std::numeric_limits<std::uint64_t>::max() - a,
          "formal family sum overflow");
  return a + b;
}
auto multiply(std::uint64_t a, std::uint64_t b) -> std::uint64_t {
  require(a == 0U || b <= std::numeric_limits<std::uint64_t>::max() / a,
          "formal family product overflow");
  return a * b;
}
auto positive(const Object& object, std::string_view field) -> std::uint64_t {
  const auto n = input::number(object, field);
  require(n > 0U, "formal budget must be positive");
  return n;
}
auto encode(const Value& value) -> std::string {
  const auto canonical = protocol::json::canonicalize(value);
  require(canonical.has_value(), "formal value is not canonicalizable");
  return canonical.value();
}
void same(const Value& a, const Value& b) {
  require(encode(a) == encode(b), "formal family repeated declaration differs");
}
auto bounded_watchdog(const Object& object) -> std::uint64_t {
  const auto ns = positive(object, "watchdog_ns");
  require(ns <= static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()),
          "formal watchdog exceeds signed native duration");
  return ns;
}
struct RawExtentInput final {
  const Object& capture;
  const Object& resources;
};
auto raw_extent(RawExtentInput inputs, bool demand)
    -> std::pair<std::uint64_t, std::uint64_t> {
  const auto& capture = inputs.capture;
  const auto& resources = inputs.resources;
  std::uint64_t total = 0U;
  std::uint64_t largest = 0U;
  constexpr std::array phase_names{"warmup", "measurement"};
  constexpr std::array names{"producer_primary_rows", "consumer_primary_rows",
                             "producer_demand_rows", "consumer_demand_rows"};
  constexpr std::array<std::uint64_t, 4U> bodies{120U, 80U, 72U, 72U};
  const auto& capacities = input::array(resources, "phase_capacity", 2U);
  const auto& limits = input::array(input::object(capture, "budget"), "phases", 2U);
  for (std::size_t phase = 0U; phase < 2U; ++phase) {
    const auto& id = input::text(input::object(capture, phase_names[phase]), "run_id");
    const auto prefix = multiply(add(4U, add(id.size(), 7U)) / 8U, 8U);
    const auto* rows = capacities[phase].as_object();
    const auto* bounds = limits[phase].as_object();
    require(rows != nullptr && bounds != nullptr, "formal row bounds absent");
    for (std::size_t index = 0U; index < (demand ? 4U : 2U); ++index) {
      const auto count = positive(*rows, names[index]);
      const auto minimum = positive(*bounds, index == 3U ? "consumer_poll_limit"
                                                         : "producer_attempt_limit");
      require(count >= minimum, "formal raw capacity omits prospective attempts");
      const auto bytes = multiply(count, add(prefix, bodies[index]));
      total = add(total, bytes);
      largest = std::max(largest, bytes);
    }
  }
  return {total, largest};
}

void continuation_contract(const Object& value) {
  input::fields(value, {"policy_id", "parent_plan", "failed_family_receipt",
                        "accepted_prefix_manifest", "compatibility_manifest",
                        "reused_contexts", "remaining_contexts",
                        "original_first_ordinal", "failed_original_ordinal",
                        "seed_policy", "monitor_path_replacements", "future_retries"});
  require(input::text(value, "policy_id") == "Q16A-COMPLETE-CONTEXT-CONTINUATION-v1" &&
              input::text(value, "seed_policy") ==
                  "PRESERVE_ORIGINAL_NUMERIC_SEEDS_FRESH_IDENTITIES" &&
              input::number(value, "original_first_ordinal") == 177U &&
              input::number(value, "failed_original_ordinal") == 177U &&
              input::number(value, "future_retries") == 0U,
          "continuation is outside the accepted one-attempt incident");
  const auto& reused = input::array(value, "reused_contexts", 3U);
  const auto& remaining = input::array(value, "remaining_contexts", 9U);
  for (std::size_t i = 0U; i < reused.size(); ++i)
    require(input::number(reused[i]) == i, "continuation reused context differs");
  for (std::size_t i = 0U; i < remaining.size(); ++i)
    require(input::number(remaining[i]) == i + 3U,
            "continuation remaining context differs");
  for (const auto field : {"parent_plan", "failed_family_receipt",
                           "accepted_prefix_manifest", "compatibility_manifest"}) {
    const auto& binding = input::object(value, field);
    input::fields(binding, {"path", "size_bytes", "sha256"});
    const auto& path = input::text(binding, "path");
    const auto& hash = input::text(binding, "sha256");
    require(
        !path.empty() && path.front() == '/' && path.find('\0') == std::string::npos &&
            path.find("/../") == std::string::npos && !path.ends_with("/..") &&
            positive(binding, "size_bytes") <= std::uint64_t{128U} * 1024U * 1024U &&
            hash.size() == 64U &&
            std::all_of(hash.begin(), hash.end(),
                        [](char c) {
                          return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
                        }),
        "continuation proof binding differs");
  }
  const auto& parent = input::object(value, "parent_plan");
  const auto& failed = input::object(value, "failed_family_receipt");
  require(input::text(parent, "sha256") ==
                  "a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7" &&
              input::number(parent, "size_bytes") == 12128860U &&
              input::text(failed, "sha256") ==
                  "a6704159e3dd2adab1598e2959202cfa5a6a0b5c9164a01fab967deeb251c7e4" &&
              input::number(failed, "size_bytes") == 1082U,
          "continuation original incident differs");
  const auto* paths = input::member(value, "monitor_path_replacements").as_array();
  require(paths != nullptr && (paths->empty() || paths->size() == 5U),
          "continuation monitoring replacement count differs");
  for (const auto& item : *paths) {
    const auto* replacement = item.as_object();
    require(replacement != nullptr,
            "continuation monitoring replacement is not an object");
    input::fields(*replacement, {"original_path", "continuation_path"});
    for (const auto field : {"original_path", "continuation_path"}) {
      const auto& path = input::text(*replacement, field);
      require(!path.empty() && path.front() == '/' &&
                  path.find('\0') == std::string::npos,
              "continuation monitoring path is not absolute");
    }
  }
  // File authenticity, original-plan equality, prefix validity and cross-release
  // compatibility are separately checked by signed controller admission.
}

void service_continuation_contract(const Object& value) {
  input::fields(value, {"policy_id", "parent_plan", "failed_family_receipt",
                        "accepted_prefix_manifest", "compatibility_manifest",
                        "reused_capture_ordinals", "original_first_ordinal",
                        "original_total_captures", "remaining_capture_count",
                        "seed_policy", "monitor_path_replacements", "future_retries"});
  require(input::text(value, "policy_id") == "Q16B-RETAINED-PREFIX-CONTINUATION-v1" &&
              input::text(value, "seed_policy") ==
                  "PRESERVE_ORIGINAL_NUMERIC_SEEDS_FRESH_IDENTITIES" &&
              input::number(value, "original_first_ordinal") == 17U &&
              input::number(value, "original_total_captures") == 120U &&
              input::number(value, "remaining_capture_count") == 103U &&
              input::number(value, "future_retries") == 0U,
          "service continuation differs from the accepted incident");
  const auto& reused = input::array(value, "reused_capture_ordinals", 17U);
  for (std::size_t i = 0U; i < reused.size(); ++i)
    require(input::number(reused[i]) == i, "service continuation prefix differs");
  for (const auto field : {"parent_plan", "failed_family_receipt",
                           "accepted_prefix_manifest", "compatibility_manifest"}) {
    const auto& binding = input::object(value, field);
    input::fields(binding, {"path", "size_bytes", "sha256"});
    const auto& path = input::text(binding, "path");
    const auto& hash = input::text(binding, "sha256");
    require(
        !path.empty() && path.front() == '/' && path.find('\0') == std::string::npos &&
            path.find("/../") == std::string::npos && !path.ends_with("/..") &&
            positive(binding, "size_bytes") <= std::uint64_t{128U} * 1024U * 1024U &&
            hash.size() == 64U &&
            std::all_of(hash.begin(), hash.end(),
                        [](char c) {
                          return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
                        }),
        "service continuation proof binding differs");
  }
  const auto& parent = input::object(value, "parent_plan");
  const auto& failed = input::object(value, "failed_family_receipt");
  require(input::text(parent, "sha256") ==
                  "53ef4baad885eeece98697d6c57b0dd0a375107504b277ffef7482185081e486" &&
              input::number(parent, "size_bytes") == 2072840U &&
              input::text(failed, "sha256") ==
                  "332662f64d2f802578c0152aec69781f3b913afca43efe2714483da7e80b3269" &&
              input::number(failed, "size_bytes") == 1084U,
          "service continuation original incident differs");
  const auto* paths = input::member(value, "monitor_path_replacements").as_array();
  require(paths != nullptr && (paths->empty() || paths->size() == 5U),
          "service continuation monitoring replacement count differs");
  for (const auto& item : *paths) {
    const auto* replacement = item.as_object();
    require(replacement != nullptr,
            "service continuation replacement is not an object");
    input::fields(*replacement, {"original_path", "continuation_path"});
    for (const auto field : {"original_path", "continuation_path"}) {
      const auto& path = input::text(*replacement, field);
      require(!path.empty() && path.front() == '/' &&
                  path.find('\0') == std::string::npos,
              "service continuation monitoring path is not absolute");
    }
  }
  // Signed controller admission authenticates the actual prefix, parent,
  // post-exit custody and cross-release compatibility, separately from parsing.
}

auto validate(FixedAction action, const Object& plan, std::string_view revision)
    -> FormalFamilyBudget {
  const bool ring = action == FixedAction::q16a;
  const bool scheduled = action == FixedAction::q16c;
  require(ring || scheduled || action == FixedAction::q16b,
          "formal family action is unsupported");
  auto common = plan;
  const auto& schema_version = input::text(plan, "schema_version");
  const bool continuation =
      ring && schema_version == "cpu-prefetch-stage17-formal-ring-plan/3";
  const bool service_continuation =
      action == FixedAction::q16b &&
      schema_version == "cpu-prefetch-stage17-formal-service-plan/4";
  const bool service_daycap =
      action == FixedAction::q16b &&
      (schema_version == "cpu-prefetch-stage17-formal-service-plan/3" ||
       service_continuation);
  const bool scheduled_descriptive =
      scheduled && schema_version == "cpu-prefetch-stage17-formal-scheduled-plan/3";
  const bool archived = schema_version.ends_with("/2") || continuation ||
                        service_daycap || scheduled_descriptive;
  if (scheduled_descriptive)
    common.erase("source_transport");
  if (continuation) {
    continuation_contract(input::object(plan, "continuation"));
    common.erase("continuation");
  }
  if (service_continuation) {
    service_continuation_contract(input::object(plan, "continuation"));
    common.erase("continuation");
    require(revision != "aa3285f15acbd3314cae64a628c113488a8438b8",
            "service continuation requires a new qualified source");
  }
  if (archived)
    common.erase("storage");
  common.erase(ring ? "repetitions_per_context" : "repetitions_per_cell");
  if (ring)
    common.erase("minimum_observations_per_series");
  if (scheduled)
    common.erase("scale_ordinal");
  input::fields(common, {"schema_version", "plan_id", "protocol_version", "action_id",
                         "method_id", "source_revision", "clean_source", "stand_id",
                         "measurement_ns", "warmup_namespace", "measurement_namespace",
                         "custody_policy_id", "captures", "budget"});
  const auto expected_schema =
      std::string(ring        ? "cpu-prefetch-stage17-formal-ring-plan/"
                  : scheduled ? "cpu-prefetch-stage17-formal-scheduled-plan/"
                              : "cpu-prefetch-stage17-formal-service-plan/") +
      (service_continuation                                      ? "4"
       : continuation || service_daycap || scheduled_descriptive ? "3"
       : archived                                                ? "2"
                                                                 : "1");
  const auto expected_capture_method =
      ring        ? "RING-D2-RUNTAIL-LTL95C95-WINDOW-v2"
      : scheduled ? "MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1"
                  : "SERVICE-RATE-NP-LTL95C95-MIN-v1";
  // D254 keeps the legacy collector format, whose inferential validity remains
  // unestablished. Its method name does not grant the descriptive family a
  // 95/95 claim; the new family method explicitly replaces that guarantee.
  const auto expected_family_method =
      scheduled_descriptive ? "MATRIX-FULL-DESCRIPTIVE-SCREEN-v1"
      : service_daycap      ? "SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1"
                            : expected_capture_method;
  require(input::text(plan, "schema_version") == expected_schema &&
              input::text(plan, "method_id") == expected_family_method &&
              input::text(plan, "protocol_version") == "2.0.0-pre.3" &&
              input::text(plan, "action_id") == to_string(action) &&
              input::text(plan, "source_revision") == revision &&
              revision.size() == 40U &&
              input::text(plan, "custody_policy_id") ==
                  (archived ? "EXT007-FORMAL-LOSSLESS-STAND-PRIMARY-v1"
                            : "EXT007-RAW-NONE-STAND-PRIMARY-v1"),
          "formal family identity/source/method differs");
  const auto* clean = input::member(plan, "clean_source").as_bool();
  require(std::all_of(
              revision.begin(), revision.end(),
              [](char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }),
          "formal source revision is not lowercase hexadecimal");
  require(clean != nullptr && *clean, "formal family source is not clean");
  for (const auto field :
       {"plan_id", "stand_id", "warmup_namespace", "measurement_namespace"})
    static_cast<void>(input::opaque_text(plan, field));
  require(input::text(plan, "warmup_namespace") !=
              input::text(plan, "measurement_namespace"),
          "formal phase namespaces coincide");
  const auto repetitions =
      positive(plan, ring ? "repetitions_per_context" : "repetitions_per_cell");
  if (scheduled_descriptive)
    require(repetitions == 1U,
            "descriptive screen requires exactly one repetition per cell");
  else if (service_daycap)
    require(repetitions == 2U,
            "service daycap requires exactly two repetitions per cell");
  else
    require(repetitions >= (scheduled ? 1U : 59U),
            "formal family has too few planned runs");
  require(!continuation || repetitions == 59U,
          "continuation must preserve exactly 59 repetitions per context");
  const auto duration = positive(plan, "measurement_ns");
  require(!(service_daycap || scheduled_descriptive) || duration == 1'000'000'000U,
          "service daycap requires exactly one second measurement");
  static_cast<void>(input::ticks(duration));
  const auto minimum = ring ? positive(plan, "minimum_observations_per_series") : 0U;
  const auto scale = scheduled ? input::number(plan, "scale_ordinal") : 0U;
  require(scale < 5U, "formal scale is outside the accepted ladder");
  require(!scheduled_descriptive || scale == 0U,
          "descriptive screen permits only the initial global scale");
  const auto cells = ring ? 12U : scheduled ? 180U : 60U;
  const auto count =
      service_continuation ? 103U : multiply(continuation ? 9U : cells, repetitions);
  require(count <= std::numeric_limits<std::size_t>::max(),
          "formal family size overflow");
  const auto& captures =
      input::array(plan, "captures", static_cast<std::size_t>(count));
  constexpr std::array packages{"R0", "R1", "R2", "L0", "L1"};
  constexpr std::array classes{"L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC"};
  constexpr std::array loads{"L025", "L050", "L075"};
  std::array<std::set<std::string>, 3U> seen;
  std::map<std::size_t, std::string> geometries;
  std::map<std::size_t, std::string> repeated_bounds;
  FormalFamilyBudget result{};
  result.captures.reserve(captures.size());
  const auto& family = input::object(plan, "budget");
  input::fields(family,
                {"setup_ns", "cleanup_ns", "watchdog_ns", "controller_memory_bytes",
                 "memory_bytes", "metadata_output_bytes", "max_output_bytes",
                 "analysis_scratch_bytes", "disk_reserve_bytes",
                 "required_free_disk_bytes"});
  auto time = add(positive(family, "setup_ns"), positive(family, "cleanup_ns"));
  auto output = positive(family, "metadata_output_bytes");
  std::uint64_t peak = 0U;
  std::uint64_t source_bytes = 0U;
  std::uint64_t largest_source = 0U;
  std::set<std::string> source_ids;
  for (std::size_t ordinal = 0U; ordinal < captures.size(); ++ordinal) {
    const auto* item = captures[ordinal].as_object();
    require(item != nullptr, "formal capture entry is not an object");
    input::fields(*item, {"capture", "resources", "monitoring", "execution_budget"});
    const auto& capture = input::object(*item, "capture");
    const auto& resources = input::object(*item, "resources");
    const auto& monitoring = input::object(*item, "monitoring");
    const auto original_ordinal = ordinal + (service_continuation ? 17U : 0U);
    const auto repetition = original_ordinal % repetitions;
    const auto position = original_ordinal / repetitions + (continuation ? 3U : 0U);
    const auto state = position / (cells / 2U);
    const auto in_state = position % (cells / 2U);
    const auto load = scheduled ? in_state % 3U : 0U;
    const auto service_position = scheduled ? in_state / 3U : in_state;
    const auto package = ring ? 0U : service_position / 6U;
    const auto context_in_state = service_position % 6U;
    const auto context = state * 6U + context_in_state;
    const auto cell = ring        ? context
                      : scheduled ? (package * 12U + context) * 3U + load
                                  : package * 12U + context;
    require(input::number(capture, "ordinal") == ordinal &&
                input::number(resources, "ordinal") == ordinal &&
                input::number(monitoring, "ordinal") == ordinal &&
                input::number(capture, ring ? "context_ordinal" : "cell_ordinal") ==
                    cell &&
                input::number(capture, "repetition_ordinal") == repetition &&
                input::text(capture, "package") == packages[package] &&
                input::text(capture, "hardware_state") == (state == 0U ? "H0" : "H1") &&
                input::text(capture, "placement") ==
                    (context_in_state < 3U ? "NEAR" : "FAR") &&
                input::text(capture, "working_set_class") ==
                    classes[context_in_state % 3U] &&
                input::number(capture, "measurement_ns") == duration &&
                input::number(capture, "warmup_ns") == 5'000'000'000U &&
                input::text(capture, "method_id") == expected_capture_method,
            "formal family order/context/duration differs");
    if (ring)
      require(input::number(capture, "minimum_observations_per_series") == minimum,
              "formal demand minimum differs");
    if (scheduled)
      require(input::number(capture, "scale_ordinal") == scale &&
                  input::text(capture, "load_level") == loads[load],
              "formal scheduled cell/scale differs");
    for (const auto phase : {"warmup", "measurement"}) {
      const auto& identity = input::object(capture, phase);
      input::phase_identity(identity);
      require(input::text(identity, "namespace_id") ==
                  input::text(plan, std::string(phase) + "_namespace"),
              "formal run namespace differs");
      std::size_t index = 0U;
      for (const auto field : {"run_id", "seed_id", "seed_hex"})
        require(seen[index++].insert(input::text(identity, field)).second,
                "formal family reuses a run or seed");
    }
    same(input::member(capture, "arena_seed"), input::member(capture, "measurement"));
    const auto geometry = encode(input::member(capture, "geometry"));
    const auto [g, inserted] =
        geometries.emplace(package * 6U + context_in_state, geometry);
    require(inserted || g->second == geometry, "formal paired geometry differs");
    auto resource_bounds = resources;
    auto monitor_bounds = monitoring;
    resource_bounds.erase("ordinal");
    monitor_bounds.erase("ordinal");
    const auto invariant =
        encode(Value(Object{{"budget", input::member(capture, "budget")},
                            {"resources", Value(std::move(resource_bounds))},
                            {"monitoring", Value(std::move(monitor_bounds))}}));
    const auto [b, first] = repeated_bounds.emplace(cell, invariant);
    require(first || b->second == invariant, "formal repeated cell bounds differ");
    const auto& budget = input::object(*item, "execution_budget");
    input::fields(budget,
                  {"setup_ns", "publication_ns", "cleanup_ns", "watchdog_ns",
                   "publication_memory_bytes", "other_memory_bytes", "memory_bytes",
                   "metadata_output_bytes", "max_output_bytes"});
    auto capture_time =
        add(add(positive(budget, "setup_ns"), 5'000'000'000U), duration);
    for (const auto& phase :
         input::array(input::object(capture, "budget"), "phases", 2U)) {
      require(phase.as_object() != nullptr, "formal phase limits are absent");
      capture_time = add(capture_time, positive(*phase.as_object(), "drain_ns"));
    }
    capture_time = add(capture_time, add(positive(budget, "publication_ns"),
                                         positive(budget, "cleanup_ns")));
    const auto [raw, largest] =
        raw_extent({.capture = capture, .resources = resources}, ring);
    auto extra_raw = std::uint64_t{0U};
    if (!ring && package >= 3U)
      extra_raw = multiply(
          add(positive(input::object(capture, "geometry"), "capacity"), 1U), 8U);
    if (scheduled) {
      for (const auto& phase : input::array(capture, "schedules", 2U)) {
        require(phase.as_object() != nullptr, "formal schedule is absent");
        if (scheduled_descriptive) {
          require(input::text(capture, "schema_version") ==
                          "cpu-prefetch-stage17-formal-scheduled-capture/2" &&
                      input::text(*phase.as_object(), "storage_format") ==
                          "SEALED_U64BE_ORIGINAL-v1",
                  "descriptive screen requires original sealed sources");
          const auto& artifact = input::object(*phase.as_object(), "source_artifact");
          require(source_ids.insert(input::opaque_text(artifact, "artifact_id")).second,
                  "original-source identity is reused");
          const auto bytes =
              multiply(input::number(*phase.as_object(), "offered_count"), 8U);
          source_bytes = add(source_bytes, bytes);
          largest_source = std::max(largest_source, bytes);
        }
        extra_raw =
            add(extra_raw,
                multiply(input::number(*phase.as_object(), "offered_count"), 8U));
      }
    }
    const auto publication = positive(budget, "publication_memory_bytes");
    require(publication >= std::max(largest, extra_raw),
            "formal publication allocation is unbudgeted");
    FormalCaptureBudget declared{bounded_watchdog(budget),
                                 positive(budget, "memory_bytes"),
                                 positive(budget, "metadata_output_bytes"),
                                 positive(budget, "max_output_bytes")};
    require(declared.watchdog_ns >= capture_time &&
                declared.memory_bytes >=
                    add(positive(resources, "total_mapping_bytes"),
                        add(publication, positive(budget, "other_memory_bytes"))) &&
                declared.max_output_bytes >=
                    add(add(raw, extra_raw), declared.metadata_output_bytes),
            "formal capture budget omits time/memory/output");
    time = add(time, declared.watchdog_ns);
    output = add(output, declared.max_output_bytes);
    peak = std::max(peak, declared.memory_bytes);
    result.captures.push_back(declared);
  }
  const auto controller_memory = positive(family, "controller_memory_bytes");
  require(controller_memory >= encode(Value(plan)).size(),
          "formal controller cannot hold plan bytes");
  result.watchdog_ns = bounded_watchdog(family);
  require(!(service_daycap || scheduled_descriptive) ||
              result.watchdog_ns <= 86'400'000'000'000U,
          "service daycap family watchdog exceeds 24 hours");
  result.memory_bytes = positive(family, "memory_bytes");
  result.metadata_output_bytes = positive(family, "metadata_output_bytes");
  result.max_output_bytes = positive(family, "max_output_bytes");
  result.required_free_disk_bytes = positive(family, "required_free_disk_bytes");
  auto memory = add(controller_memory, peak);
  if (scheduled_descriptive) {
    const auto& transport = input::object(plan, "source_transport");
    input::fields(transport,
                  {"schema_version", "format", "source_bytes", "owned_vector_bytes",
                   "loader_transient_bytes", "descriptor_count", "metadata_bytes",
                   "maximum_source_memory_bytes"});
    require(input::text(transport, "schema_version") ==
                    "cpu-prefetch-stage17-schedule-transport-budget/1" &&
                input::text(transport, "format") == "SEALED_U64BE_ORIGINAL-v1" &&
                positive(transport, "descriptor_count") == 360U &&
                source_ids.size() == 360U &&
                input::number(transport, "source_bytes") == source_bytes &&
                input::number(transport, "owned_vector_bytes") == source_bytes &&
                positive(transport, "loader_transient_bytes") >=
                    add(largest_source, 8192U) &&
                positive(transport, "metadata_bytes") >= 1024U * 1024U &&
                positive(transport, "maximum_source_memory_bytes") >=
                    add(multiply(source_bytes, 2U),
                        add(positive(transport, "loader_transient_bytes"),
                            positive(transport, "metadata_bytes"))),
            "original source transport extent is incomplete");
    memory = add(memory, positive(transport, "maximum_source_memory_bytes"));
  }
  auto disk =
      add(result.max_output_bytes, add(positive(family, "analysis_scratch_bytes"),
                                       positive(family, "disk_reserve_bytes")));
  if (archived) {
    constexpr std::uint64_t quota = 6'000'000'000'000U;
    constexpr std::uint64_t gib = std::uint64_t{1024U} * 1024U * 1024U;
    constexpr auto workspace = 512U * gib;
    constexpr auto scratch = 256U * gib;
    constexpr auto reserve = 16U * gib;
    constexpr auto codec_memory = 2U * gib;
    const auto& storage = input::object(plan, "storage");
    input::fields(storage,
                  {"schema_version", "program_id", "policy_id",
                   "implementation_profile_sha256", "program_scope_sha256",
                   "archive_quota_bytes", "workspace_bytes", "analysis_scratch_bytes",
                   "disk_reserve_bytes", "codec_address_space_bytes", "codec_processes",
                   "broker_address_space_bytes", "per_capture_archive_ns",
                   "archive_staging_bytes", "capture_workspace_overhead_bytes",
                   "checkpoint_bytes", "analysis_capture_workspace_bytes"});
    require(input::text(storage, "schema_version") ==
                    "cpu-prefetch-stage17-formal-storage-plan/1" &&
                input::text(storage, "policy_id") ==
                    "EXT007-FORMAL-LOSSLESS-STAND-PRIMARY-v1" &&
                positive(storage, "archive_quota_bytes") == quota &&
                positive(storage, "workspace_bytes") == workspace &&
                positive(storage, "analysis_scratch_bytes") == scratch &&
                positive(storage, "disk_reserve_bytes") == reserve &&
                positive(storage, "codec_address_space_bytes") == codec_memory &&
                positive(storage, "codec_processes") == 1U &&
                positive(family, "analysis_scratch_bytes") == scratch &&
                positive(family, "disk_reserve_bytes") == reserve,
            "formal storage differs from the accepted D233 constants");
    FormalStorageBudget declared{input::opaque_text(storage, "program_id"),
                                 input::text(storage, "implementation_profile_sha256"),
                                 input::text(storage, "program_scope_sha256"),
                                 positive(storage, "broker_address_space_bytes"),
                                 positive(storage, "per_capture_archive_ns"),
                                 positive(storage, "archive_staging_bytes"),
                                 positive(storage, "capture_workspace_overhead_bytes"),
                                 positive(storage, "checkpoint_bytes"),
                                 positive(storage, "analysis_capture_workspace_bytes")};
    require(declared.broker_address_space_bytes <= codec_memory &&
                declared.program_scope_sha256.size() == 64U &&
                std::all_of(declared.program_scope_sha256.begin(),
                            declared.program_scope_sha256.end(),
                            [](char c) {
                              return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
                            }) &&
                declared.implementation_profile_sha256.size() == 64U &&
                std::all_of(declared.implementation_profile_sha256.begin(),
                            declared.implementation_profile_sha256.end(),
                            [](char c) {
                              return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
                            }),
            "formal archive implementation profile hash is malformed");
    std::uint64_t largest = 0U;
    for (const auto& capture : result.captures) {
      largest = std::max(largest, capture.max_output_bytes);
      require(capture.metadata_output_bytes >= declared.checkpoint_bytes,
              "formal capture metadata omits its final checkpoint");
    }
    require(declared.archive_staging_bytes <= quota &&
                add(largest, add(declared.archive_staging_bytes,
                                 declared.capture_workspace_overhead_bytes)) <=
                    workspace &&
                largest <= declared.analysis_capture_workspace_bytes &&
                declared.analysis_capture_workspace_bytes <= scratch,
            "formal capture/staging/analysis exceeds its physical workspace");
    time = add(time, multiply(count, declared.per_capture_archive_ns));
    memory = add(memory, add(codec_memory, declared.broker_address_space_bytes));
    disk = add(quota, add(workspace, add(scratch, reserve)));
    result.storage = std::move(declared);
  }
  require(result.watchdog_ns >= time && result.memory_bytes >= memory &&
              result.max_output_bytes >= output &&
              result.required_free_disk_bytes >= disk,
          "formal family budget omits declared components");
  return result;
}
} // namespace

auto validate_formal_family(FixedAction action, const Object& plan,
                            std::string_view expected_source_revision)
    -> protocol::Result<FormalFamilyBudget> {
  try {
    return protocol::Result<FormalFamilyBudget>::success(
        validate(action, plan, expected_source_revision));
  } catch (const std::exception& error) {
    return protocol::Result<FormalFamilyBudget>::failure(
        {protocol::ErrorCategory::cross_field, "$/formal/plan", "S17-FORMAL-FAMILY",
         error.what()});
  }
}
} // namespace cpu_prefetch::runner::stage17
