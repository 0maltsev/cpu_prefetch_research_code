#include "cpu_prefetch/runner/stage17_formal_scheduled_action.hpp"
#include "cpu_prefetch/runner/stage17_schedule_source.hpp"

#include "stage17_formal_input_detail.hpp"

#include <chrono>
#include <fcntl.h>
#include <sys/stat.h>

namespace cpu_prefetch::runner::stage17 {
namespace {
using namespace formal_input_detail;
auto parse_capture(const Object& capture, const Object& resources,
                   const Object& monitoring,
                   std::span<const platform::HardwarePrefetchMsrValue> prestate,
                   bool verify_declared_layout,
                   const FormalScheduleSourceContext* sources = nullptr)
    -> protocol::Result<ParsedNativeFormalScheduledCapture> {
  try {
    fields(capture, {"schema_version",    "ordinal",
                     "cell_ordinal",      "repetition_ordinal",
                     "method_id",         "package",
                     "hardware_state",    "placement",
                     "working_set_class", "warmup_ns",
                     "measurement_ns",    "software_prefetch_mapping_id",
                     "linked_order",      "ring_distance",
                     "geometry",          "warmup",
                     "measurement",       "arena_seed",
                     "seed_use",          "budget",
                     "load_level",        "scale_ordinal",
                     "schedules"});
    fields(resources,
           {"ordinal", "workers", "controller_stack", "core_bytes", "monitor_bytes",
            "total_mapping_bytes", "region_bytes", "tls_module_capacity",
            "thread_stat_bytes", "thread_status_bytes", "thread_affinity_words",
            "initial_consumer_state", "phase_capacity"});
    fields(monitoring,
           {"ordinal", "during_first_page", "during_page_count", "during_offset_ticks",
            "observer_wait_poll_limit", "control_region_index", "counter_limits",
            "hardware_identity", "environment_sources"});
    const auto ordinal = number(capture, "ordinal");
    const auto full_cell = number(capture, "cell_ordinal");
    const auto cell = full_cell / 3U;
    const auto context = cell % 12U;
    constexpr std::array packages{
        protocol::QueuePackage::r0, protocol::QueuePackage::r1,
        protocol::QueuePackage::r2, protocol::QueuePackage::l0,
        protocol::QueuePackage::l1};
    constexpr std::array<std::string_view, 5U> names{"R0", "R1", "R2", "L0", "L1"};
    static_cast<void>(number(capture, "repetition_ordinal"));
    constexpr std::array<std::string_view, 3U> classes{"L2_RESIDENT", "LLC_RESIDENT",
                                                       "BEYOND_LLC"};
    const bool sealed = sources != nullptr;
    if (text(capture, "schema_version") !=
            (sealed ? "cpu-prefetch-stage17-formal-scheduled-capture/2"
                    : "cpu-prefetch-stage17-formal-scheduled-capture/1") ||
        text(capture, "method_id") != calibration::kMatrixFeasibilityMethodId ||
        full_cell >= 180U || number(capture, "scale_ordinal") >= 5U ||
        text(capture, "load_level") !=
            std::array<std::string_view, 3U>{"L025", "L050", "L075"}[full_cell % 3U] ||
        text(capture, "package") != names[cell / 12U] ||
        number(resources, "ordinal") != ordinal ||
        number(monitoring, "ordinal") != ordinal ||
        number(capture, "warmup_ns") != 5'000'000'000U ||
        text(capture, "hardware_state") != (context < 6U ? "H0" : "H1") ||
        text(capture, "placement") != ((context / 3U) % 2U == 0U ? "NEAR" : "FAR") ||
        text(capture, "working_set_class") != classes[context % 3U]) {
      throw std::invalid_argument("native formal service identity/context differs");
    }
    const auto& geometry = object(capture, "geometry");
    fields(geometry, {"capacity", "cache_line_bytes", "base_page_bytes", "producer_cpu",
                      "consumer_cpu", "producer_node", "consumer_node", "shared_node"});
    const auto& budget = object(capture, "budget");
    fields(budget, {"phases", "barrier_poll_limit", "memory_bytes"});
    const auto& phases = array(budget, "phases", 2U);
    const auto& capacities = array(resources, "phase_capacity", 2U);
    calibration::ServiceSessionPlan session{{}, number(budget, "barrier_poll_limit")};
    std::array<calibration::FormalServicePhaseCapacity, 2U> capacity{};
    for (std::size_t i = 0U; i < 2U; ++i) {
      const auto* phase = phases[i].as_object();
      const auto* rows = capacities[i].as_object();
      if (phase == nullptr || rows == nullptr) {
        throw std::invalid_argument("formal phase bounds must be objects");
      }
      fields(*phase, {"producer_attempt_limit", "consumer_poll_limit", "drain_ns"});
      fields(*rows, {"producer_primary_rows", "consumer_primary_rows"});
      session.phases[i] = {
          ticks(number(capture, i == 0U ? "warmup_ns" : "measurement_ns")),
          number(*phase, "producer_attempt_limit"),
          number(*phase, "consumer_poll_limit"), ticks(number(*phase, "drain_ns"))};
      capacity[i] = {number(*rows, "producer_primary_rows"),
                     number(*rows, "consumer_primary_rows")};
    }
    if (!calibration::valid_service_plan(session)) {
      throw std::invalid_argument("invalid formal service phase bounds");
    }
    const auto& warmup = object(capture, "warmup");
    const auto& measurement = object(capture, "measurement");
    phase_identity(warmup);
    phase_identity(measurement);
    static_cast<void>(workload::MasterSeed::from_hex(text(warmup, "seed_hex")));
    if (object(capture, "arena_seed") != measurement ||
        text(capture, "seed_use") !=
            "ONE_PERSISTENT_ARENA_MEASUREMENT_SEED_WARMUP_RESERVED_NO_DRAWS" ||
        text(warmup, "run_id") == text(measurement, "run_id") ||
        text(warmup, "seed_id") == text(measurement, "seed_id") ||
        text(warmup, "namespace_id") == text(measurement, "namespace_id") ||
        text(warmup, "seed_hex") == text(measurement, "seed_hex")) {
      throw std::invalid_argument(
          "native persistent-arena seed or phase identity differs");
    }
    std::optional<calibration::FormalLinkedOrderPlan> linked;
    if (!member(capture, "linked_order").is_null()) {
      const auto& item = object(capture, "linked_order");
      fields(item, {"seed_id", "seed_hex", "namespace_id", "arena_alignment_bytes"});
      static_cast<void>(opaque_text(item, "seed_id"));
      linked.emplace(workload::MasterSeed::from_hex(seed_text(item)),
                     opaque_text(item, "namespace_id"),
                     size(item, "arena_alignment_bytes"));
    }
    std::optional<calibration::FormalRingDistancePlan> distance;
    if (!member(capture, "ring_distance").is_null()) {
      const auto& item = object(capture, "ring_distance");
      fields(item, {"cache_lines", "calibration_evidence_id"});
      const auto* evidence = member(item, "calibration_evidence_id").as_string();
      if (evidence == nullptr)
        throw std::invalid_argument("ring distance evidence must be a string");
      if (!evidence->empty())
        static_cast<void>(opaque_text(item, "calibration_evidence_id"));
      distance.emplace(size(item, "cache_lines"), *evidence);
    }
    calibration::NativeFormalServiceCapturePlan result{
        {packages[cell / 12U],
         session,
         {size(geometry, "capacity"), size(geometry, "cache_line_bytes"),
          size(geometry, "base_page_bytes"),
          workload::MasterSeed::from_hex(text(measurement, "seed_hex")),
          text(measurement, "namespace_id")},
         {run_id(warmup), run_id(measurement)},
         {number(resources, "initial_consumer_state")},
         capacity,
         std::move(linked),
         std::move(distance)},
        parse_controls(capture, resources, monitoring, prestate),
        opaque_text(capture, "software_prefetch_mapping_id")};
    const auto& schedule_records = array(capture, "schedules", 2U);
    ParsedNativeFormalScheduledCapture::Deadlines deadlines;
    std::uint64_t total_source_bytes = 0U;
    const auto parse_schedule = [&](std::size_t index) {
      const auto* source = schedule_records[index].as_object();
      if (source == nullptr)
        throw std::invalid_argument("schedule must be object");
      if (sealed)
        fields(*source, {"schedule_id", "seed_id", "seed_hex", "namespace_id",
                         "source_origin_ticks", "source_horizon_ticks", "offered_count",
                         "storage_format", "source_artifact"});
      else
        fields(*source, {"schedule_id", "seed_id", "seed_hex", "namespace_id",
                         "source_origin_ticks", "source_horizon_ticks", "offered_count",
                         "deadline_ticks", "source_artifact"});
      const auto id =
          protocol::ScheduleId::parse(opaque_text(*source, "schedule_id"), "$schedule");
      const auto ns = protocol::NamespaceId::parse(opaque_text(*source, "namespace_id"),
                                                   "$schedule");
      if (!id || !ns)
        throw std::invalid_argument("invalid schedule identity");
      static_cast<void>(opaque_text(*source, "seed_id"));
      static_cast<void>(workload::MasterSeed::from_hex(seed_text(*source)));
      const auto& provenance = object(*source, "source_artifact");
      fields(provenance, {"artifact_id", "sha256"});
      static_cast<void>(opaque_text(provenance, "artifact_id"));
      const auto& hash = text(provenance, "sha256");
      if (hash.size() != 64U || !std::all_of(hash.begin(), hash.end(), [](char c) {
            return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
          }))
        throw std::invalid_argument("invalid source artifact SHA256");
      const auto count = number(*source, "offered_count");
      const auto remaining = number(budget, "memory_bytes") - total_source_bytes;
      if (count > session.phases[index].producer_attempt_limit ||
          count > remaining / sizeof(std::uint64_t) ||
          count > deadlines[index].max_size())
        throw std::invalid_argument("schedule count exceeds source or finite bounds");
      if (sealed) {
        if (text(*source, "storage_format") != "SEALED_U64BE_ORIGINAL-v1" ||
            total_source_bytes > sources->maximum_vector_bytes ||
            count > (sources->maximum_vector_bytes - total_source_bytes) / 16U)
          throw std::invalid_argument(
              "sealed schedule transient allocation is unbudgeted");
        const auto& artifact = text(provenance, "artifact_id");
        const FormalScheduleSourceBinding* bound = nullptr;
        for (const auto& binding : sources->bindings) {
          if (binding.artifact_id != artifact)
            continue;
          if (bound != nullptr)
            throw std::invalid_argument("duplicate sealed source binding");
          bound = &binding;
        }
        if (bound == nullptr || bound->canonical_sha256 != hash ||
            bound->size_bytes != count * 8U)
          throw std::invalid_argument(
              "sealed source binding differs from original artifact");
        auto loaded = load_sealed_schedule_source(
            bound->descriptor,
            {artifact, hash, count, number(*source, "source_origin_ticks"),
             number(*source, "source_horizon_ticks"),
             sources->maximum_vector_bytes - total_source_bytes,
             sources->deadline_monotonic_ns});
        if (!loaded)
          throw std::invalid_argument(loaded.errors().front().message);
        deadlines[index] = std::move(loaded.value());
      } else {
        const auto* values = member(*source, "deadline_ticks").as_array();
        if (values == nullptr || values->size() != count)
          throw std::invalid_argument("inline schedule count differs from source");
        deadlines[index].reserve(static_cast<std::size_t>(count));
        for (const auto& deadline : *values)
          deadlines[index].push_back(number(deadline));
      }
      total_source_bytes += count * sizeof(std::uint64_t);
      return calibration::ScheduledPhasePlan{number(*source, "source_origin_ticks"),
                                             number(*source, "source_horizon_ticks"),
                                             count, id.value(), ns.value()};
    };
    std::array<calibration::ScheduledPhasePlan, 2U> schedules{parse_schedule(0U),
                                                              parse_schedule(1U)};
    const auto& first = *schedule_records[0U].as_object();
    const auto& second = *schedule_records[1U].as_object();
    if (text(first, "seed_id") == text(second, "seed_id"))
      throw std::invalid_argument("phase schedule seed identities must be distinct");
    for (const auto* source : {&first, &second}) {
      for (const auto* identity : {&warmup, &measurement}) {
        if (text(*source, "namespace_id") == text(*identity, "namespace_id") ||
            text(*source, "seed_id") == text(*identity, "seed_id"))
          throw std::invalid_argument("schedule and arena identities must be separate");
      }
    }
    ParsedNativeFormalScheduledCapture owned(
        {{std::move(result.service), std::move(schedules), {}},
         std::move(result.controls),
         std::move(result.software_prefetch_mapping_id)},
        std::move(deadlines));
    const auto layout = calibration::native_formal_scheduled_layout(owned.plan());
    check_layout(layout, resources, budget, verify_declared_layout);
    return protocol::Result<ParsedNativeFormalScheduledCapture>::success(owned);
  } catch (const std::exception& error) {
    return protocol::Result<ParsedNativeFormalScheduledCapture>::failure(
        {protocol::ErrorCategory::cross_field, "$/formal/scheduled_capture",
         "S17-FORMAL-SCHEDULED-PLAN", error.what()});
  }
}
} // namespace

auto parse_formal_schedule_source_context(const Object& plan, const Object& context,
                                          std::span<const int> reserved)
    -> protocol::Result<PreparedFormalScheduleSources> {
  try {
    fields(context, {"schema_version", "bindings", "deadline_monotonic_ns"});
    const bool continuation =
        text(plan, "schema_version") == "cpu-prefetch-stage17-formal-scheduled-plan/4";
    if ((!continuation && text(plan, "schema_version") !=
                              "cpu-prefetch-stage17-formal-scheduled-plan/3") ||
        text(context, "schema_version") !=
            "cpu-prefetch-stage17-schedule-source-context/1")
      throw std::invalid_argument(
          "sealed source context requires the explicit descriptive family");
    const auto deadline = number(context, "deadline_monotonic_ns");
    const auto now = std::chrono::duration_cast<std::chrono::nanoseconds>(
                         std::chrono::steady_clock::now().time_since_epoch())
                         .count();
    const auto setup = number(object(plan, "budget"), "setup_ns");
    if (now < 0 || deadline <= static_cast<std::uint64_t>(now) ||
        deadline - static_cast<std::uint64_t>(now) > setup)
      throw std::invalid_argument("source loading deadline exceeds prospective setup");
    const auto& transport = object(plan, "source_transport");
    const auto context_bytes =
        protocol::json::canonicalize(protocol::json::Value(context));
    if (!context_bytes ||
        context_bytes.value().size() > number(transport, "metadata_bytes"))
      throw std::invalid_argument("source context exceeds metadata reservation");
    const auto source_count = continuation ? 188U : 360U;
    const auto& entries = array(context, "bindings", source_count);
    const auto& captures = array(plan, "captures", source_count / 2U);
    PreparedFormalScheduleSources result{
        {}, number(transport, "owned_vector_bytes"), deadline};
    const auto transient = number(transport, "loader_transient_bytes");
    if (transient >
        std::numeric_limits<std::uint64_t>::max() - result.maximum_vector_bytes)
      throw std::invalid_argument("source vector bound overflows");
    result.maximum_vector_bytes += transient;
    std::set<int> descriptors(reserved.begin(), reserved.end());
    std::set<std::pair<dev_t, ino_t>> identities;
    for (const auto fd : reserved) {
      struct stat info{};
      if (::fstat(fd, &info) == 0 && S_ISREG(info.st_mode))
        identities.insert({info.st_dev, info.st_ino});
    }
    std::set<std::string> artifacts;
    result.bindings.reserve(source_count);
    for (std::size_t i = 0U; i < entries.size(); ++i) {
      const auto* bound = entries[i].as_object();
      const auto* item = captures[i / 2U].as_object();
      if (bound == nullptr || item == nullptr)
        throw std::invalid_argument("sealed source binding/capture must be an object");
      fields(*bound, {"artifact_id", "sha256", "size_bytes", "descriptor"});
      const auto& source = array(object(*item, "capture"), "schedules", 2U)[i % 2U];
      if (source.as_object() == nullptr)
        throw std::invalid_argument("sealed source must be an object");
      const auto& artifact = object(*source.as_object(), "source_artifact");
      const auto count = number(*source.as_object(), "offered_count");
      const auto fd = number(*bound, "descriptor");
      if (count > std::numeric_limits<std::uint64_t>::max() / 8U || fd <= 2U ||
          fd > static_cast<std::uint64_t>(std::numeric_limits<int>::max()) ||
          text(*bound, "artifact_id") != text(artifact, "artifact_id") ||
          text(*bound, "sha256") != text(artifact, "sha256") ||
          number(*bound, "size_bytes") != count * 8U ||
          !artifacts.insert(text(*bound, "artifact_id")).second ||
          !descriptors.insert(static_cast<int>(fd)).second)
        throw std::invalid_argument(
            "sealed source membership/hash/size/descriptor differs");
      struct stat info{};
      const auto descriptor = static_cast<int>(fd);
      const auto flags = ::fcntl(descriptor, F_GETFL);
      const auto seals = ::fcntl(descriptor, F_GET_SEALS);
      constexpr int all_seals =
          F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL;
      if (::fstat(descriptor, &info) != 0 || !S_ISREG(info.st_mode) ||
          info.st_size < 0 || static_cast<std::uint64_t>(info.st_size) != count * 8U ||
          flags < 0 || (flags & O_ACCMODE) != O_RDONLY || seals < 0 ||
          (seals & all_seals) != all_seals ||
          !identities.insert({info.st_dev, info.st_ino}).second)
        throw std::invalid_argument(
            "sealed source physical identity is invalid or aliased");
      result.bindings.push_back({text(*bound, "artifact_id"), text(*bound, "sha256"),
                                 count * 8U, descriptor});
    }
    return protocol::Result<PreparedFormalScheduleSources>::success(result);
  } catch (const std::exception& error) {
    return protocol::Result<PreparedFormalScheduleSources>::failure(
        {protocol::ErrorCategory::cross_field, "$/formal/source_context",
         "S17-FORMAL-SOURCE-CONTEXT", error.what()});
  }
}

ParsedNativeFormalScheduledCapture::ParsedNativeFormalScheduledCapture(
    calibration::NativeFormalScheduledCapturePlan plan, Deadlines deadlines)
    : plan_(std::move(plan)),
      deadlines_(std::make_shared<const Deadlines>(std::move(deadlines))),
      hardware_prestate_(plan_.controls.hardware_prestate.begin(),
                         plan_.controls.hardware_prestate.end()) {
  plan_.scheduled.deadlines = {};
  plan_.controls.hardware_prestate = {};
}
auto ParsedNativeFormalScheduledCapture::plan() const
    -> calibration::NativeFormalScheduledCapturePlan {
  if (!deadlines_)
    throw std::logic_error("moved-from scheduled capture");
  auto result = plan_;
  result.scheduled.deadlines = {(*deadlines_)[0U], (*deadlines_)[1U]};
  result.controls.hardware_prestate = hardware_prestate_;
  return result;
}

auto parse_native_formal_scheduled_capture(
    const Object& capture, const Object& resources, const Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<ParsedNativeFormalScheduledCapture> {
  return parse_capture(capture, resources, monitoring, prestate, true);
}

auto parse_native_formal_scheduled_capture_from_sources(
    const Object& capture, const Object& resources, const Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate,
    const FormalScheduleSourceContext& sources)
    -> protocol::Result<ParsedNativeFormalScheduledCapture> {
  return parse_capture(capture, resources, monitoring, prestate, true, &sources);
}

auto describe_native_formal_scheduled_layout(
    const Object& capture, const Object& resources, const Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeFormalScheduledCaptureLayout> {
  const auto parsed = parse_capture(capture, resources, monitoring, prestate, false);
  if (!parsed) {
    return protocol::Result<calibration::NativeFormalScheduledCaptureLayout>::failure(
        parsed.errors());
  }
  return protocol::Result<calibration::NativeFormalScheduledCaptureLayout>::success(
      calibration::native_formal_scheduled_layout(parsed.value().plan()));
}

auto describe_native_formal_scheduled_layout_from_sources(
    const Object& capture, const Object& resources, const Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate,
    const FormalScheduleSourceContext& sources)
    -> protocol::Result<calibration::NativeFormalScheduledCaptureLayout> {
  const auto parsed =
      parse_capture(capture, resources, monitoring, prestate, false, &sources);
  if (!parsed)
    return protocol::Result<calibration::NativeFormalScheduledCaptureLayout>::failure(
        parsed.errors());
  return protocol::Result<calibration::NativeFormalScheduledCaptureLayout>::success(
      calibration::native_formal_scheduled_layout(parsed.value().plan()));
}
} // namespace cpu_prefetch::runner::stage17
