#include "cpu_prefetch/runner/stage17_s180_input.hpp"
#include "stage17_formal_input_detail.hpp"
#include <set>

namespace cpu_prefetch::runner::stage17 {
namespace {
using namespace formal_input_detail;
namespace c = calibration;
void require(bool b, const char* message) {
  if (!b)
    throw std::invalid_argument(message);
}
auto hash(const Object& o, std::string_view key) -> const std::string& {
  const auto& s = text(o, key);
  require(protocol::Sha256::parse(s, "$s180").has_value(), "S180 hash is invalid");
  return s;
}
template <class T> auto identity(const std::string& value) -> T {
  auto parsed = T::parse(value, "$s180");
  require(parsed.has_value(), "S180 typed identity is invalid");
  return parsed.value();
}
auto item(const Value& v) -> const Object& {
  require(v.as_object() != nullptr, "S180 array entry is not an object");
  return *v.as_object();
}
auto slot(const Object& row) -> std::size_t {
  const auto placement = protocol::parse_placement(text(row, "placement"), "$s180");
  const auto ws =
      protocol::parse_working_set_class(text(row, "working_set_class"), "$s180");
  require(placement.has_value() && ws.has_value(), "S180 context is invalid");
  const auto index = c::pilot_context_index({placement.value(), ws.value()});
  if (!index)
    throw std::invalid_argument("S180 context slot is invalid");
  return *index;
}
auto group(const Object& row) -> std::size_t {
  const auto& load = text(row, "load_level");
  require(load == "L025" || load == "L050" || load == "L075", "S180 load is invalid");
  return slot(row) * 3U + (load == "L025" ? 0U : load == "L050" ? 1U : 2U);
}
auto data_plan(const Object& row, workload::MasterSeed master)
    -> c::MappedPilotDataPlan {
  const auto& geo = object(row, "requested_geometry");
  return {{protocol::parse_placement(text(row, "placement"), "$s180").value(),
           protocol::parse_working_set_class(text(row, "working_set_class"), "$s180")
               .value()},
          {size(geo, "capacity"), size(geo, "cache_line_bytes"),
           size(geo, "base_page_bytes"), master, text(row, "arena_namespace")},
          {master, text(row, "node_order_namespace"), size(geo, "base_page_bytes")},
          word(geo, "producer_cpu"),
          word(geo, "shared_node")};
}
struct ControlDocuments final {
  const Object& resources;
  const Object& monitoring;
  const Object& hardware;
};
auto controls(ControlDocuments documents, protocol::RequestedHardwareState state)
    -> c::NativePilotCaptureControlPlan {
  const auto& resources = documents.resources;
  const auto& monitoring = documents.monitoring;
  const auto& hardware = documents.hardware;
  fields(resources,
         {"workers", "controller_stack", "tls_module_capacity", "thread_stat_bytes",
          "thread_status_bytes", "thread_affinity_words", "initial_consumer_state",
          "phase_capacity"});
  fields(monitoring, {"during_first_page", "during_page_count", "during_offset_ticks",
                      "observer_wait_poll_limit", "control_region_index",
                      "counter_limits", "environment_sources"});
  const auto& workers = object(resources, "workers");
  fields(workers, {"producer_stack", "consumer_stack"});
  const auto& hw = object(hardware, "identity");
  c::NativePilotCaptureControlPlan out{{stack(object(workers, "producer_stack")),
                                        stack(object(workers, "consumer_stack"))},
                                       stack(object(resources, "controller_stack")),
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
                                       {word(hw, "family"), word(hw, "model")},
                                       state,
                                       {},
                                       {}};
  const auto& first = array(monitoring, "during_first_page", 9U);
  const auto& count = array(monitoring, "during_page_count", 9U);
  for (std::size_t i = 0U; i < 9U; ++i) {
    out.during_first_page[i] = size(first[i]);
    out.during_page_count[i] = size(count[i]);
  }
  const auto& offsets = array(monitoring, "during_offset_ticks", 2U);
  const auto& bounds = array(monitoring, "counter_limits", 2U);
  for (std::size_t i = 0U; i < 2U; ++i) {
    out.during_offset_ticks[i] = number(offsets[i]);
    const auto* pair = bounds[i].as_array();
    require(pair && pair->size() == 2U, "S180 disturbance limits require two workers");
    for (std::size_t j = 0U; j < 2U; ++j)
      out.counter_limits[i][j] = limits((*pair)[j]);
  }
  const auto* sources = member(monitoring, "environment_sources").as_array();
  require(sources != nullptr, "S180 environmental observations are missing");
  std::set<std::string_view> paths;
  for (const auto& value : *sources) {
    const auto& source = item(value);
    fields(source,
           {"path", "byte_capacity", "chunk_bytes", "max_data_reads", "requested"});
    platform::FileSnapshotPlan p{text(source, "path"),
                                 size(source, "byte_capacity"),
                                 size(source, "chunk_bytes"),
                                 size(source, "max_data_reads"),
                                 {}};
    const auto& requested = array(source, "requested", platform::kFileSnapshotGroups);
    for (std::size_t i = 0U; i < requested.size(); ++i) {
      require(requested[i].as_bool() != nullptr,
              "S180 observation request is not boolean");
      p.requested[i] = *requested[i].as_bool();
    }
    require(platform::valid_file_snapshot_plan(p) && paths.insert(p.path).second,
            "S180 environmental observation is invalid or duplicated");
    out.environment_sources.push_back(p);
  }
  return out;
}
auto layout(const Object& o) -> c::NativePilotCaptureLayout {
  fields(o, {"workers", "core_bytes", "monitor_bytes", "total_mapping_bytes",
             "region_bytes"});
  c::NativePilotCaptureLayout out{};
  out.core_bytes = size(o, "core_bytes");
  out.monitor_bytes = size(o, "monitor_bytes");
  out.total_mapping_bytes = size(o, "total_mapping_bytes");
  const auto& regions = array(o, "region_bytes", 9U);
  for (std::size_t i = 0U; i < 9U; ++i)
    out.region_bytes[i] = size(regions[i]);
  const auto& w = object(o, "workers");
  fields(w, {"records_bytes", "producer_bytes", "consumer_bytes", "schedule_offsets",
             "emitter_object", "package_object", "phases"});
  auto& dst = out.workers;
  dst.records_bytes = size(w, "records_bytes");
  dst.producer_bytes = size(w, "producer_bytes");
  dst.consumer_bytes = size(w, "consumer_bytes");
  dst.emitter_object = size(w, "emitter_object");
  dst.package_object = size(w, "package_object");
  const auto& offsets = array(w, "schedule_offsets", 2U);
  const auto& phases = array(w, "phases", 2U);
  for (std::size_t i = 0U; i < 2U; ++i) {
    dst.schedule_offsets[i] = size(offsets[i]);
    const auto& p = item(phases[i]);
    fields(p, {"producer_object", "producer_raw", "consumer_object", "consumer_raw",
               "raw"});
    const auto& raw = object(p, "raw");
    fields(raw, {"producer_bytes", "consumer_bytes"});
    dst.phases[i] = {{size(raw, "producer_bytes"), size(raw, "consumer_bytes")},
                     size(p, "producer_object"),
                     size(p, "producer_raw"),
                     size(p, "consumer_object"),
                     size(p, "consumer_raw")};
  }
  return out;
}
} // namespace
auto ParsedS180Input::input() const -> S180SessionInput {
  auto out = input_;
  out.sources.bindings = bindings_;
  out.reserved_descriptors = reserved_;
  for (auto& capture : out.captures)
    capture.native.controls.hardware_prestate = prestate_;
  return out;
}
auto ParsedS180Input::document() const noexcept -> const Object& { return *document_; }

auto parse_s180_session_input(Object plan, const Object& source_context,
                              std::span<const int> reserved)
    -> protocol::Result<ParsedS180Input> {
  try {
    fields(plan, {"schema_version", "source_revision", "blueprint", "hardware",
                  "captures", "budget", "storage"});
    require(text(plan, "schema_version") == "cpu-prefetch-stage17-s180-session-plan/1",
            "S180 plan version differs");
    ParsedS180Input out;
    out.document_ = std::make_shared<const Object>(std::move(plan));
    const auto& doc = *out.document_;
    auto& input = out.input_;
    input.blueprint = object(doc, "blueprint");
    const auto canonical = protocol::json::canonicalize(Value(input.blueprint));
    require(canonical &&
                workload::sha256(std::as_bytes(std::span(canonical.value().data(),
                                                         canonical.value().size())))
                        .hex() == kS180BlueprintSha256,
            "S180 exact approved blueprint differs");
    input.source_revision = text(doc, "source_revision");
    require(input.source_revision.size() == 40U &&
                std::all_of(input.source_revision.begin(), input.source_revision.end(),
                            [](char ch) {
                              return (ch >= '0' && ch <= '9') ||
                                     (ch >= 'a' && ch <= 'f');
                            }),
            "S180 clean source revision is malformed");
    const auto& hardware = object(doc, "hardware");
    fields(hardware, {"identity", "prestate", "software_prefetch_mapping_id"});
    fields(object(hardware, "identity"), {"family", "model"});
    const auto* prestate = member(hardware, "prestate").as_array();
    require(prestate && !prestate->empty(), "S180 hardware prestate missing");
    for (const auto& value : *prestate) {
      const auto& p = item(value);
      fields(p, {"cpu", "value"});
      out.prestate_.push_back({word(p, "cpu"), number(p, "value")});
    }
    fields(source_context, {"schema_version", "maximum_vector_bytes",
                            "deadline_monotonic_ns", "bindings"});
    require(text(source_context, "schema_version") ==
                "cpu-prefetch-stage17-s180-schedule-source-context/1",
            "S180 source context version differs");
    for (const auto& value : array(source_context, "bindings", 36U)) {
      const auto& b = item(value);
      fields(b, {"artifact_id", "canonical_sha256", "size_bytes", "descriptor"});
      const auto fd = number(b, "descriptor");
      require(fd > 2U &&
                  fd <= static_cast<std::uint64_t>(std::numeric_limits<int>::max()),
              "S180 source descriptor invalid");
      out.bindings_.push_back({opaque_text(b, "artifact_id"),
                               hash(b, "canonical_sha256"), number(b, "size_bytes"),
                               static_cast<int>(fd)});
    }
    out.reserved_.assign(reserved.begin(), reserved.end());
    input.sources = {out.bindings_, number(source_context, "maximum_vector_bytes"),
                     number(source_context, "deadline_monotonic_ns")};
    input.reserved_descriptors = out.reserved_;
    const auto& budget = object(doc, "budget");
    fields(budget, {"setup_ns", "whole_plot_transition_ns", "whole_plot_recovery_ns",
                    "finalization_ns", "final_metadata_bytes", "memory_bytes",
                    "max_output_bytes", "entry_metadata_bytes"});
    input.setup_ns = number(budget, "setup_ns");
    input.whole_plot_transition_ns = number(budget, "whole_plot_transition_ns");
    input.whole_plot_recovery_ns = number(budget, "whole_plot_recovery_ns");
    input.finalization_ns = number(budget, "finalization_ns");
    input.final_metadata_bytes = number(budget, "final_metadata_bytes");
    input.memory_bytes = number(budget, "memory_bytes");
    const auto entry_bytes = number(budget, "entry_metadata_bytes"),
               total_bytes = number(budget, "max_output_bytes");
    require(entry_bytes > 0U && entry_bytes < total_bytes,
            "S180 entry metadata is unbudgeted");
    input.max_output_bytes = total_bytes - entry_bytes;
    const auto& storage = object(doc, "storage");
    fields(storage, {"pilot_policy_id", "approval_sha256", "program_id",
                     "program_scope_sha256", "implementation_profile_sha256",
                     "archive_staging_bytes", "maximum_custody_receipt_bytes"});
    require(text(storage, "pilot_policy_id") == "D310-S180-LOSSLESS-STAND-PRIMARY-v1" &&
                hash(storage, "approval_sha256") ==
                    text(object(input.blueprint, "approval"), "sha256") &&
                number(storage, "archive_staging_bytes") > 0U &&
                number(storage, "maximum_custody_receipt_bytes") > 0U,
            "S180 storage extension or bounds differ");
    static_cast<void>(opaque_text(storage, "program_id"));
    static_cast<void>(hash(storage, "program_scope_sha256"));
    static_cast<void>(hash(storage, "implementation_profile_sha256"));
    const auto& frozen = array(input.blueprint, "captures", 180U);
    std::array<const Object*, 180U> order{};
    std::array<const Object*, 6U> contexts{};
    for (const auto& value : frozen) {
      const auto& row = item(value);
      const auto ordinal = size(row, "execution_ordinal");
      require(ordinal < 180U && !order[ordinal], "S180 order not a permutation");
      order[ordinal] = &row;
      contexts[slot(row)] = &row;
    }
    const auto master =
        workload::MasterSeed::from_hex(text(input.blueprint, "master_seed_hex"));
    for (const auto* row : contexts) {
      require(row != nullptr, "S180 retained context missing");
      input.contexts.push_back(data_plan(*row, master));
    }
    const auto& captures = array(doc, "captures", 180U);
    for (std::size_t i = 0U; i < 180U; ++i) {
      const auto& entry = item(captures[i]);
      fields(entry, {"execution_ordinal", "cell_ordinal", "resources", "monitoring",
                     "phases", "expected_layout", "execution_budget"});
      const auto& row = *order[i];
      require(number(entry, "execution_ordinal") == i &&
                  number(entry, "cell_ordinal") == number(row, "cell_ordinal"),
              "S180 capture order differs");
      const auto& resources = object(entry, "resources");
      const auto& eb = object(entry, "execution_budget");
      fields(eb, {"watchdog_ns", "archive_ns", "max_output_bytes", "metadata_bytes",
                  "barrier_poll_limit"});
      c::ServiceSessionPlan session{{}, number(eb, "barrier_poll_limit")};
      std::array<c::FormalServicePhaseCapacity, 2U> capacity{};
      const auto& phases = array(entry, "phases", 2U);
      const auto& capacities = array(resources, "phase_capacity", 2U);
      for (std::size_t phase = 0U; phase < 2U; ++phase) {
        const auto& p = item(phases[phase]);
        fields(p, {"producer_attempt_limit", "consumer_poll_limit",
                   "drain_duration_ticks", "schedule_id", "source_origin_ticks",
                   "source_horizon_ticks", "offered_count", "source_artifact"});
        session.phases[phase] = {
            ticks(number(row, phase == 0U ? "warmup_ns" : "measurement_ns")),
            number(p, "producer_attempt_limit"), number(p, "consumer_poll_limit"),
            number(p, "drain_duration_ticks")};
        const auto& cap = item(capacities[phase]);
        fields(cap, {"producer_primary_rows", "consumer_primary_rows"});
        capacity[phase] = {number(cap, "producer_primary_rows"),
                           number(cap, "consumer_primary_rows")};
      }
      const auto pkg =
          protocol::parse_queue_package(text(row, "package"), "$s180").value();
      const auto& data = input.contexts[slot(row)];
      c::MappedFormalServicePlan service{
          pkg,
          session,
          data.arena,
          {identity<protocol::RunId>(text(row, "warmup_run_id")),
           identity<protocol::RunId>(text(row, "run_id"))},
          {number(resources, "initial_consumer_state")},
          capacity,
          std::nullopt,
          std::nullopt};
      if (pkg == protocol::QueuePackage::l0 || pkg == protocol::QueuePackage::l1)
        service.linked_order = data.node_order;
      if (pkg == protocol::QueuePackage::r1 || pkg == protocol::QueuePackage::r2)
        service.ring_distance = c::FormalRingDistancePlan{
            pkg == protocol::QueuePackage::r1
                ? 1U
                : size(object(row, "distance"), "d2_cache_lines"),
            hash(object(input.blueprint, "calibration_freeze"), "sha256")};
      auto schedule = [&](std::size_t phase) -> c::ScheduledPhasePlan {
        const auto& p = item(phases[phase]);
        const auto& b = object(p, "source_artifact");
        fields(b, {"artifact_id", "sha256"});
        S180SourceArtifact source{opaque_text(b, "artifact_id"), hash(b, "sha256")};
        auto& expected = input.source_artifacts[group(row)][phase];
        require(expected.artifact_id.empty() ||
                    (expected.artifact_id == source.artifact_id &&
                     expected.sha256 == source.sha256),
                "S180 paired original source differs");
        expected = std::move(source);
        return {number(p, "source_origin_ticks"), number(p, "source_horizon_ticks"),
                number(p, "offered_count"),
                identity<protocol::ScheduleId>(text(p, "schedule_id")),
                identity<protocol::NamespaceId>(
                    text(row, phase == 0U ? "warmup_schedule_namespace"
                                          : "measurement_schedule_namespace"))};
      };
      c::MappedFormalScheduledPlan scheduled{
          std::move(service), {schedule(0U), schedule(1U)}, {}};
      const auto state = protocol::parse_requested_hardware_state(
                             text(row, "requested_hardware_state"), "$s180")
                             .value();
      auto ctl = controls({resources, object(entry, "monitoring"), hardware}, state);
      ctl.hardware_prestate = out.prestate_;
      input.captures.push_back({{{std::move(scheduled), {}},
                                 std::move(ctl),
                                 text(hardware, "software_prefetch_mapping_id")},
                                layout(object(entry, "expected_layout")),
                                number(eb, "watchdog_ns"),
                                number(eb, "archive_ns"),
                                number(eb, "max_output_bytes"),
                                number(eb, "metadata_bytes")});
    }
    const auto valid = validate_s180_session(input);
    if (!valid)
      return protocol::Result<ParsedS180Input>::failure(valid.errors());
    return protocol::Result<ParsedS180Input>::success(out);
  } catch (const std::exception& e) {
    return protocol::Result<ParsedS180Input>::failure(
        {protocol::ErrorCategory::cross_field, "$s180/input", "S17-S180-INPUT",
         e.what()});
  }
}
} // namespace cpu_prefetch::runner::stage17
