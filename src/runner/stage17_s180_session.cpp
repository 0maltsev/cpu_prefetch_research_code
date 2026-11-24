#include "cpu_prefetch/runner/stage17_s180_session.hpp"
#include "cpu_prefetch/runner/software_prefetch.hpp"
#include "stage17_formal_input_detail.hpp"

#include <set>
#include <sys/stat.h>

namespace cpu_prefetch::runner::stage17 {
namespace {
using namespace formal_input_detail;
void require(bool condition, const char* message) {
  if (!condition)
    throw std::invalid_argument(message);
}
void add(std::uint64_t& total, std::uint64_t amount) {
  require(amount <= std::numeric_limits<std::uint64_t>::max() - total,
          "S180 finite sum overflows");
  total += amount;
}
auto hash(const std::string& value) -> std::string {
  return workload::sha256(std::as_bytes(std::span(value.data(), value.size()))).hex();
}
auto context_index(const Object& row) -> std::size_t {
  const auto p = protocol::parse_placement(text(row, "placement"), "$s180");
  const auto w =
      protocol::parse_working_set_class(text(row, "working_set_class"), "$s180");
  require(p.has_value() && w.has_value(), "S180 context is invalid");
  const auto i = calibration::pilot_context_index({p.value(), w.value()});
  if (!i.has_value())
    throw std::invalid_argument("S180 context is outside the six slots");
  return *i;
}
auto load_index(const Object& row) -> std::size_t {
  const auto& level = text(row, "load_level");
  if (level == "L025")
    return 0U;
  if (level == "L050")
    return 1U;
  require(level == "L075", "S180 load is invalid");
  return 2U;
}
auto package(const Object& row) -> protocol::QueuePackage {
  const auto parsed = protocol::parse_queue_package(text(row, "package"), "$s180");
  require(parsed.has_value(), "S180 package is invalid");
  return parsed.value();
}
auto state(const Object& row) -> protocol::RequestedHardwareState {
  const auto parsed = protocol::parse_requested_hardware_state(
      text(row, "requested_hardware_state"), "$s180");
  require(parsed.has_value(), "S180 state is invalid");
  return parsed.value();
}
void validate_sources(
    const S180SessionInput& input,
    const std::array<const calibration::MappedFormalScheduledPlan*, 18U>& groups,
    S180SessionShape& shape) {
  require(input.sources.bindings.size() == 36U,
          "S180 requires exactly 36 common original sources");
  std::set<std::string> artifacts, schedules, namespaces;
  std::set<int> descriptors(input.reserved_descriptors.begin(),
                            input.reserved_descriptors.end());
  std::set<std::pair<dev_t, ino_t>> identities;
  for (const auto fd : input.reserved_descriptors) {
    struct stat st{};
    if (::fstat(fd, &st) == 0)
      identities.emplace(st.st_dev, st.st_ino);
  }
  std::uint64_t retained = 0U;
  std::array<bool, 18U> visited{};
  // The first occurrence of each common group is the actual loading order.
  for (const auto group : shape.source_groups) {
    if (visited[group])
      continue;
    visited[group] = true;
    require(groups[group] != nullptr, "S180 common source group is missing");
    for (std::size_t phase = 0U; phase < 2U; ++phase) {
      const auto& expected = input.source_artifacts[group][phase];
      const auto& source = groups[group]->phases[phase];
      require(artifacts.insert(expected.artifact_id).second &&
                  schedules.insert(std::string(source.schedule_id.value())).second &&
                  namespaces.insert(std::string(source.namespace_id.value())).second,
              "S180 source identity is reused across independent groups/phases");
      const auto digest = protocol::Sha256::parse(expected.sha256, "$s180");
      require(digest.has_value() && !expected.artifact_id.empty(),
              "S180 source identity/hash is malformed");
      require(source.offered_count <= std::numeric_limits<std::uint64_t>::max() / 16U,
              "S180 source count overflows");
      require(retained <= input.sources.maximum_vector_bytes &&
                  source.offered_count <=
                      (input.sources.maximum_vector_bytes - retained) / 16U,
              "S180 retained and transient common-source memory is unbudgeted");
      add(retained, source.offered_count * 8U);
      const FormalScheduleSourceBinding* bound = nullptr;
      for (const auto& b : input.sources.bindings)
        if (b.artifact_id == expected.artifact_id) {
          require(bound == nullptr, "S180 source membership is duplicated");
          bound = &b;
        }
      require(bound != nullptr, "S180 source membership is incomplete");
      require(bound->canonical_sha256 == expected.sha256 &&
                  bound->size_bytes == source.offered_count * 8U &&
                  bound->descriptor > 2 && descriptors.insert(bound->descriptor).second,
              "S180 source descriptor/hash/size differs");
      struct stat st{};
      require(::fstat(bound->descriptor, &st) == 0 && S_ISREG(st.st_mode) &&
                  identities.emplace(st.st_dev, st.st_ino).second,
              "S180 source physical identity is invalid or aliased");
    }
  }
  shape.retained_vector_bytes = retained;
}
auto planned_source_limit(
    const S180SessionInput& input,
    const std::array<const calibration::MappedFormalScheduledPlan*, 18U>& groups,
    S180SessionShape& shape) -> std::uint64_t {
  std::array<bool, 18U> visited{};
  std::set<std::string> schedules, namespaces, artifacts;
  std::uint64_t retained = 0U, peak = 0U;
  for (const auto group : shape.source_groups) {
    if (visited[group])
      continue;
    visited[group] = true;
    require(groups[group] != nullptr, "S180 declared source group is missing");
    for (std::size_t phase = 0U; phase < 2U; ++phase) {
      const auto& source = groups[group]->phases[phase];
      require(schedules.insert(std::string(source.schedule_id.value())).second &&
                  namespaces.insert(std::string(source.namespace_id.value())).second,
              "S180 independent declared schedule identity is reused");
      const auto& binding = input.source_artifacts[group][phase];
      if (!binding.artifact_id.empty() || !binding.sha256.empty())
        require(!binding.artifact_id.empty() &&
                    protocol::Sha256::parse(binding.sha256, "$s180").has_value() &&
                    artifacts.insert(binding.artifact_id).second,
                "S180 declared source binding malformed or reused");
      require(source.offered_count <= std::numeric_limits<std::uint64_t>::max() / 16U,
              "S180 declared source count overflows");
      auto transient = retained;
      add(transient, source.offered_count * 16U);
      peak = std::max(peak, transient);
      add(retained, source.offered_count * 8U);
    }
  }
  shape.retained_vector_bytes = retained;
  return peak;
}
auto validate_session(const S180SessionInput& input, bool physical_sources)
    -> protocol::Result<S180SessionShape> {
  try {
    const auto canonical = protocol::json::canonicalize(Value(input.blueprint));
    require(canonical.has_value() && hash(canonical.value()) == kS180BlueprintSha256,
            "S180 requires the exact approved frozen blueprint");
    require(!physical_sources || input.sources.deadline_monotonic_ns > 0U,
            "S180 source deadline is missing");
    require(input.contexts.size() == 6U && input.captures.size() == 180U,
            "S180 requires six retained contexts and 180 captures");
    require(
        input.setup_ns > 0U && input.whole_plot_transition_ns > 0U &&
            input.finalization_ns > 0U && input.final_metadata_bytes > 0U &&
            input.memory_bytes > 0U && input.max_output_bytes > 0U,
        "S180 requires finite explicit preparation/recovery/finalization/resources");
    S180SessionShape out{};
    out.watchdog_ns = input.setup_ns;
    add(out.watchdog_ns, input.whole_plot_transition_ns);
    add(out.watchdog_ns, input.whole_plot_recovery_ns);
    add(out.watchdog_ns, input.finalization_ns);
    const auto& rows = array(input.blueprint, "captures", 180U);
    const auto master =
        workload::MasterSeed::from_hex(text(input.blueprint, "master_seed_hex"));
    std::array<const Object*, 180U> order{};
    for (const auto& value : rows) {
      const auto* row = value.as_object();
      require(row != nullptr, "S180 frozen row is invalid");
      const auto ordinal = size(*row, "execution_ordinal");
      require(ordinal < order.size() && order[ordinal] == nullptr,
              "S180 order is not a permutation");
      order[ordinal] = row;
    }
    for (std::size_t i = 0U; i < 6U; ++i) {
      const auto& c = input.contexts[i];
      const auto slot = calibration::pilot_context_index(c.key);
      require(slot.has_value() && *slot == i && c.arena.master_seed == master &&
                  c.node_order.master_seed == master,
              "S180 context slot or original master seed differs");
      const auto layout = calibration::mapped_pilot_data_layout(c);
      add(out.shared_mapping_bytes, layout.records_bytes);
      add(out.shared_mapping_bytes, layout.queues_bytes);
    }
    std::array<const calibration::MappedFormalScheduledPlan*, 18U> groups{};
    std::uint64_t max_private = 0U, total_output = input.final_metadata_bytes,
                  max_payload = 0U;
    std::set<std::string> runs;
    const auto& baseline = input.captures.front().native.controls;
    for (std::size_t i = 0U; i < 180U; ++i) {
      require(order[i] != nullptr, "S180 execution slot is missing");
      const auto& row = *order[i];
      const auto ctx = context_index(row), group = ctx * 3U + load_index(row);
      out.cells[i] = size(row, "cell_ordinal");
      out.contexts[i] = ctx;
      out.source_groups[i] = group;
      const auto& p = input.captures[i];
      const auto& n = p.native;
      const auto& capture = n.capture.scheduled;
      const auto& service = capture.service;
      const auto& shared = input.contexts[ctx];
      const auto& geo = object(row, "requested_geometry");
      require(n.capture.shared.data == nullptr && n.capture.shared.plan == nullptr &&
                  n.capture.shared.node_order.empty() &&
                  !n.capture.shared.mappings[0U] && !n.capture.shared.mappings[1U],
              "S180 must bind family-owned data after preparation");
      for (const auto& region : n.capture.shared.regions)
        require(region.mapping.empty(),
                "S180 cannot borrow unobserved persistent regions");
      require(service.initial_consumer.value ==
                  input.captures.front()
                      .native.capture.scheduled.service.initial_consumer.value,
              "S180 initial consumer state differs across paired treatments");
      require(service.package == package(row) &&
                  n.controls.hardware_state == state(row) &&
                  service.run_ids[0U].value() == text(row, "warmup_run_id") &&
                  service.run_ids[1U].value() == text(row, "run_id") &&
                  runs.insert(std::string(service.run_ids[0U].value())).second &&
                  runs.insert(std::string(service.run_ids[1U].value())).second,
              "S180 package/state/run identity/order differs from frozen row");
      require(service.arena.master_seed == master &&
                  service.arena.seed_namespace == text(row, "arena_namespace") &&
                  shared.arena.seed_namespace == service.arena.seed_namespace &&
                  shared.node_order.seed_namespace ==
                      text(row, "node_order_namespace") &&
                  service.arena.capacity == size(geo, "capacity") &&
                  service.arena.cache_line_bytes == size(geo, "cache_line_bytes") &&
                  service.arena.base_page_bytes == size(geo, "base_page_bytes") &&
                  shared.arena.capacity == service.arena.capacity &&
                  shared.arena.cache_line_bytes == service.arena.cache_line_bytes &&
                  shared.arena.base_page_bytes == service.arena.base_page_bytes &&
                  shared.producer_cpu == word(geo, "producer_cpu") &&
                  shared.shared_node == word(geo, "shared_node"),
              "S180 persistent data geometry/seed differs from frozen context");
      const auto& controls = n.controls;
      require(controls.workers.producer_stack.owner_cpu == word(geo, "producer_cpu") &&
                  controls.workers.consumer_stack.owner_cpu ==
                      word(geo, "consumer_cpu") &&
                  controls.workers.producer_stack.requested_node ==
                      word(geo, "producer_node") &&
                  controls.workers.consumer_stack.requested_node ==
                      word(geo, "consumer_node") &&
                  controls.workers.producer_stack.verified_base_page_bytes ==
                      service.arena.base_page_bytes &&
                  controls.workers.consumer_stack.verified_base_page_bytes ==
                      service.arena.base_page_bytes &&
                  controls.controller_stack.verified_base_page_bytes ==
                      service.arena.base_page_bytes &&
                  controls.controller_stack.owner_cpu !=
                      controls.workers.producer_stack.owner_cpu &&
                  controls.controller_stack.owner_cpu !=
                      controls.workers.consumer_stack.owner_cpu,
              "S180 owner request differs from frozen geometry");
      require(controls.hardware_identity == baseline.hardware_identity &&
                  n.software_prefetch_mapping_id ==
                      input.captures.front().native.software_prefetch_mapping_id &&
                  std::equal(controls.hardware_prestate.begin(),
                             controls.hardware_prestate.end(),
                             baseline.hardware_prestate.begin(),
                             baseline.hardware_prestate.end()),
              "S180 family hardware identity/prestate differs");
      const auto hw = platform::make_hardware_prefetch_plan(controls.hardware_identity,
                                                            controls.hardware_state,
                                                            controls.hardware_prestate);
      require(hw.has_value(), "S180 registered hardware plan is incomplete");
      const auto sw = find_software_prefetch_mapping(controls.hardware_identity);
      require(sw.has_value() && sw->mapping_id == n.software_prefetch_mapping_id,
              "S180 software-prefetch model mapping differs");
      require(calibration::valid_service_plan(service.session) &&
                  service.session.phases[0U].duration_ticks == 5'000'000'000'000U &&
                  service.session.phases[1U].duration_ticks == 1'000'000'000'000U &&
                  capture.deadlines[0U].empty() && capture.deadlines[1U].empty(),
              "S180 fixed windows or inline source contract differs");
      const bool linked = service.package == protocol::QueuePackage::l0 ||
                          service.package == protocol::QueuePackage::l1;
      if (linked) {
        const auto& l = service.linked_order;
        require(l.has_value() && l->master_seed == master &&
                    l->seed_namespace == shared.node_order.seed_namespace &&
                    l->arena_alignment_bytes == service.arena.base_page_bytes,
                "S180 shared node-order identity differs");
      } else
        require(!service.linked_order.has_value(),
                "S180 ring cannot carry a linked-order plan");
      if (service.package == protocol::QueuePackage::r1 ||
          service.package == protocol::QueuePackage::r2) {
        const auto& d = service.ring_distance;
        if (!d.has_value())
          throw std::invalid_argument("S180 ring distance is missing");
        const auto expected = service.package == protocol::QueuePackage::r1
                                  ? 1U
                                  : number(object(row, "distance"), "d2_cache_lines");
        require(d->cache_lines == expected &&
                    (service.package != protocol::QueuePackage::r1 ||
                     d->calibration_evidence_id.empty()) &&
                    (service.package != protocol::QueuePackage::r2 ||
                     !d->calibration_evidence_id.empty()),
                "S180 accepted prefetch distance differs");
      } else
        require(!service.ring_distance.has_value(),
                "S180 no-distance package carries a distance plan");
      for (std::size_t phase = 0U; phase < 2U; ++phase) {
        const auto& s = capture.phases[phase];
        const auto& expected_ns =
            text(row, phase == 0U ? "warmup_schedule_namespace"
                                  : "measurement_schedule_namespace");
        require(s.namespace_id.value() == expected_ns &&
                    !s.schedule_id.value().empty() &&
                    s.source_origin_ticks < s.source_horizon_ticks &&
                    s.source_horizon_ticks - s.source_origin_ticks ==
                        service.session.phases[phase].duration_ticks &&
                    s.offered_count <=
                        service.session.phases[phase].producer_attempt_limit &&
                    service.capacity[phase].producer_primary_rows >=
                        service.session.phases[phase].producer_attempt_limit &&
                    service.capacity[phase].consumer_primary_rows >=
                        service.session.phases[phase].producer_attempt_limit,
                "S180 source identity/window or independent raw bounds differ");
        if (groups[group]) {
          const auto& prior = groups[group]->phases[phase];
          require(s.schedule_id == prior.schedule_id &&
                      s.namespace_id == prior.namespace_id &&
                      s.source_origin_ticks == prior.source_origin_ticks &&
                      s.source_horizon_ticks == prior.source_horizon_ticks &&
                      s.offered_count == prior.offered_count,
                  "S180 paired treatments do not share the same original source");
        }
      }
      groups[group] = &capture;
      require(p.watchdog_ns > 0U && p.archive_ns > 0U && p.archive_ns < p.watchdog_ns &&
                  p.metadata_bytes > 0U && p.max_output_bytes >= p.metadata_bytes,
              "S180 capture/output/archive bounds are incomplete");
      std::uint64_t minimum = 6'000'000'000U;
      add(minimum, p.archive_ns);
      for (const auto& phase : service.session.phases)
        add(minimum, phase.drain_duration_ticks / 1000U +
                         (phase.drain_duration_ticks % 1000U != 0U ? 1U : 0U));
      require(p.watchdog_ns >= minimum,
              "S180 watchdog omits native windows/drain/archive");
      add(out.watchdog_ns, p.watchdog_ns);
      add(total_output, p.max_output_bytes);
      max_payload = std::max(max_payload, p.max_output_bytes);
      const auto& layout = p.expected_layout;
      require(layout.region_bytes[7U] ==
                      calibration::mapped_pilot_data_layout(shared).records_bytes &&
                  layout.region_bytes[8U] ==
                      calibration::mapped_pilot_data_layout(shared).queues_bytes,
              "S180 declared layout omits persistent maps");
      std::uint64_t observed = 0U;
      for (const auto bytes : layout.region_bytes) {
        require(bytes > 0U && bytes % service.arena.base_page_bytes == 0U,
                "S180 native region is empty or unaligned");
        add(observed, bytes);
      }
      add(observed, layout.monitor_bytes);
      add(observed, 3U * service.arena.base_page_bytes);
      require(observed == layout.total_mapping_bytes,
              "S180 declared native footprint differs");
      const auto shared_bytes = layout.region_bytes[7U] + layout.region_bytes[8U];
      max_private = std::max(max_private, observed - shared_bytes);
    }
    const auto vectors = physical_sources ? input.sources.maximum_vector_bytes
                                          : planned_source_limit(input, groups, out);
    if (physical_sources)
      validate_sources(input, groups, out);
    std::uint64_t memory = out.shared_mapping_bytes;
    add(memory, max_private);
    add(memory, vectors);
    add(memory, max_payload);
    add(memory, input.final_metadata_bytes);
    require(memory <= input.memory_bytes && total_output <= input.max_output_bytes &&
                out.watchdog_ns <= kS180OperationalCapNs,
            "S180 aggregate time/memory/output exceeds prospective limits");
    return protocol::Result<S180SessionShape>::success(out);
  } catch (const std::exception& e) {
    return protocol::Result<S180SessionShape>::failure(
        {protocol::ErrorCategory::cross_field, "$/s180/session", "S17-S180-SESSION",
         e.what()});
  }
}
} // namespace
auto validate_s180_session(const S180SessionInput& input)
    -> protocol::Result<S180SessionShape> {
  return validate_session(input, true);
}
auto validate_s180_prospective_declaration(const S180SessionInput& input)
    -> protocol::Result<S180SessionShape> {
  return validate_session(input, false);
}
auto run_s180_session(const S180SessionInput& input,
                      const S180SessionAuthority& authority, S180SessionOperations& ops)
    -> protocol::Result<S180SessionResult> {
  const auto shape = validate_s180_session(input);
  if (!shape)
    return protocol::Result<S180SessionResult>::failure(shape.errors());
  S180SessionResult result;
  auto last_clock = ops.now_monotonic_ns();
  const auto digest = protocol::Sha256::parse(authority.plan_sha256, "$s180");
  if (authority.session_id.empty() || !digest || !last_clock ||
      authority.window_start_monotonic_ns >= authority.window_end_monotonic_ns ||
      authority.window_end_monotonic_ns - authority.window_start_monotonic_ns !=
          kS180OperationalCapNs ||
      *last_clock < authority.window_start_monotonic_ns ||
      *last_clock >= authority.window_end_monotonic_ns ||
      shape.value().watchdog_ns > authority.window_end_monotonic_ns - *last_clock ||
      input.sources.deadline_monotonic_ns <= *last_clock ||
      input.sources.deadline_monotonic_ns > authority.window_end_monotonic_ns ||
      input.sources.deadline_monotonic_ns - *last_clock > input.setup_ns) {
    result.stop = S180SessionStop::authority_failed;
    return protocol::Result<S180SessionResult>::success(result);
  }
  const auto authorized = [&] {
    const auto now = ops.now_monotonic_ns();
    if (!now || *now < *last_clock)
      return false;
    last_clock = now;
    return *now >= authority.window_start_monotonic_ns &&
           *now < authority.window_end_monotonic_ns;
  };
  bool prepared_attempted = false, touched = false;
  auto restore = [&] {
    result.restoration_attempted = true;
    const bool ok = ops.restore();
    touched = false;
    result.restoration_verified = ok;
    if (!ok && result.stop == S180SessionStop::not_started)
      result.stop = S180SessionStop::restoration_failed;
    return ok;
  };
  try {
    prepared_attempted = true;
    if (!ops.prepare(shape.value()))
      result.stop = S180SessionStop::preparation_failed;
    for (std::size_t i = 0U; result.stop == S180SessionStop::not_started && i < 180U;
         ++i) {
      if (!authorized()) {
        result.stop = S180SessionStop::authority_failed;
        break;
      }
      if (i == 90U) {
        if (!restore())
          break;
        if (!ops.recover(input.whole_plot_recovery_ns)) {
          result.stop = S180SessionStop::recovery_failed;
          break;
        }
        if (!authorized()) {
          result.stop = S180SessionStop::authority_failed;
          break;
        }
      }
      if (!ops.mark_attempt(i)) {
        result.stop = S180SessionStop::marker_failed;
        break;
      }
      ++result.attempted;
      if (!authorized()) {
        result.stop = S180SessionStop::authority_failed;
        break;
      }
      if (i == 0U || i == 90U) {
        touched = true;
        if (!ops.enter(input.captures[i].native.controls.hardware_state)) {
          result.stop = S180SessionStop::hardware_failed;
          break;
        }
      }
      if (!authorized()) {
        result.stop = S180SessionStop::authority_failed;
        break;
      }
      bool native = false, capture_exception = false, custody = false;
      try {
        native = ops.capture(i);
      } catch (...) {
        capture_exception = true;
      }
      // Failed evidence is retained once, then the family stops. No next run.
      try {
        custody = ops.archive(i, native);
      } catch (...) {
        custody = false;
      }
      if (capture_exception) {
        result.stop = S180SessionStop::exception;
        break;
      }
      if (!native) {
        result.stop = S180SessionStop::capture_failed;
        break;
      }
      if (!custody) {
        result.stop = S180SessionStop::archive_failed;
        break;
      }
      ++result.completed;
    }
  } catch (...) {
    result.stop = S180SessionStop::exception;
  }
  if (touched)
    static_cast<void>(restore());
  if (prepared_attempted) {
    result.cleanup_attempted = true;
    result.cleanup_verified = ops.release_contexts();
    if (!result.cleanup_verified && result.stop == S180SessionStop::not_started)
      result.stop = S180SessionStop::cleanup_failed;
  }
  if (result.stop == S180SessionStop::not_started)
    result.stop = S180SessionStop::complete;
  try {
    result.final_publication_succeeded = ops.finish(result);
  } catch (...) {
    result.final_publication_succeeded = false;
  }
  if (!result.final_publication_succeeded && result.stop == S180SessionStop::complete)
    result.stop = S180SessionStop::final_publication_failed;
  return protocol::Result<S180SessionResult>::success(result);
}
} // namespace cpu_prefetch::runner::stage17
