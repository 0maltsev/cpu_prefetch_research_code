#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/platform/q15_msr.hpp"
#include "cpu_prefetch/runner/stage17_archive_channel.hpp"
#include "cpu_prefetch/runner/stage17_formal_checkpoint.hpp"
#include "cpu_prefetch/runner/stage17_s180_session.hpp"

#include <chrono>
#include <thread>

namespace cpu_prefetch::runner::stage17 {
namespace {
using V = protocol::json::Value;
using O = V::Object;
using A = V::Array;
auto text(std::string_view s) -> V { return V(std::string(s)); }
auto integer(std::uint64_t n) -> V {
  return V(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                  std::to_string(n), n});
}
auto ref(const ArtifactBinding& b) -> V {
  return V(O{{"role", text(b.role)},
             {"schema_identity", text(b.schema_identity)},
             {"media_type", text(b.media_type)},
             {"file_name", text(b.file_name)},
             {"size_bytes", integer(b.size_bytes)},
             {"sha256", text(b.sha256)}});
}
auto references(std::span<const ArtifactBinding> b) -> V {
  A out;
  for (const auto& item : b)
    out.push_back(ref(item));
  return V(std::move(out));
}
auto now() noexcept -> std::optional<std::uint64_t> {
  // The kernel timer and source loaders use CLOCK_MONOTONIC, not RAW.
  timespec t{};
  if (::clock_gettime(CLOCK_MONOTONIC, &t) != 0 || t.tv_sec < 0 ||
      static_cast<std::uint64_t>(t.tv_sec) >
          std::numeric_limits<std::uint64_t>::max() / 1'000'000'000U)
    return std::nullopt;
  return static_cast<std::uint64_t>(t.tv_sec) * 1'000'000'000U +
         static_cast<std::uint64_t>(t.tv_nsec);
}
class Output final : public ArtifactSink {
public:
  Output(ArtifactSink& sink, std::uint64_t limit,
         std::vector<ArtifactBinding>& retained)
      : sink_(sink), remaining_(limit), retained_(retained) {}
  struct Limits final {
    std::uint64_t total, metadata;
  };
  void capture_budget(Limits limits) noexcept {
    capture_ = limits.total;
    metadata_ = limits.metadata;
  }
  void family_budget() noexcept {
    capture_.reset();
    metadata_.reset();
  }
  auto account(const ArtifactBinding& b) -> bool {
    if (b.size_bytes > remaining_ || (capture_ && b.size_bytes > *capture_) ||
        (b.media_type == "application/json" && metadata_ && b.size_bytes > *metadata_))
      return false;
    remaining_ -= b.size_bytes;
    if (capture_)
      *capture_ -= b.size_bytes;
    if (b.media_type == "application/json" && metadata_)
      *metadata_ -= b.size_bytes;
    retained_.push_back(b);
    return true;
  }
  auto publish(ArtifactPayload a) -> protocol::Result<ArtifactBinding> override {
    const auto size = a.bytes.size();
    if (size > remaining_ || (capture_ && size > *capture_) ||
        (a.media_type == "application/json" && metadata_ && size > *metadata_))
      return protocol::Result<ArtifactBinding>::failure(
          {protocol::ErrorCategory::cross_field, "$s180/output",
           "S17-S180-OUTPUT-BUDGET", "prospective output bound exceeded"});
    auto result = sink_.publish(std::move(a));
    if (result && !account(result.value()))
      throw std::logic_error("S180 output accounting changed after publication");
    return result;
  }
  auto json(std::string name, std::string role, std::string schema, O document)
      -> protocol::Result<ArtifactBinding> {
    auto canonical = protocol::json::canonicalize(V(std::move(document)));
    if (!canonical)
      return protocol::Result<ArtifactBinding>::failure(canonical.errors());
    const auto bytes =
        std::as_bytes(std::span(canonical.value().data(), canonical.value().size()));
    return publish({std::move(role),
                    std::move(schema),
                    "application/json",
                    std::move(name),
                    {bytes.begin(), bytes.end()}});
  }

private:
  ArtifactSink& sink_;
  std::uint64_t remaining_;
  std::vector<ArtifactBinding>& retained_;
  std::optional<std::uint64_t> capture_, metadata_;
};
auto same_layout(const calibration::NativePilotCaptureLayout& a,
                 const calibration::NativePilotCaptureLayout& b) -> bool {
  if (a.region_bytes != b.region_bytes || a.core_bytes != b.core_bytes ||
      a.monitor_bytes != b.monitor_bytes ||
      a.total_mapping_bytes != b.total_mapping_bytes)
    return false;
  const auto& x = a.workers;
  const auto& y = b.workers;
  if (x.records_bytes != y.records_bytes || x.producer_bytes != y.producer_bytes ||
      x.consumer_bytes != y.consumer_bytes ||
      x.schedule_offsets != y.schedule_offsets ||
      x.emitter_object != y.emitter_object || x.package_object != y.package_object)
    return false;
  for (std::size_t i = 0U; i < 2U; ++i) {
    const auto& p = x.phases[i];
    const auto& q = y.phases[i];
    if (p.producer_object != q.producer_object ||
        p.consumer_object != q.consumer_object || p.producer_raw != q.producer_raw ||
        p.consumer_raw != q.consumer_raw ||
        p.raw.producer_bytes != q.raw.producer_bytes ||
        p.raw.consumer_bytes != q.raw.consumer_bytes)
      return false;
  }
  return true;
}
class Native final : public S180SessionOperations {
public:
  Native(const S180SessionInput& input, const S180SessionAuthority& authority,
         S180ArchiveSink& sink)
      : input_(input), authority_(authority), sink_(sink),
        output_(sink, input.max_output_bytes, bindings),
        writer_(writer_files_, platform::FixedMsrAccess::read_write, cpus(input)),
        verifier_(verifier_files_, platform::FixedMsrAccess::read_only, cpus(input)),
        hardware_(input.captures.front().native.controls.hardware_identity,
                  input.captures.front().native.controls.hardware_prestate,
                  {writer_, verifier_}) {}
  auto now_monotonic_ns() const noexcept -> std::optional<std::uint64_t> override {
    return now();
  }
  auto prepare(const S180SessionShape& shape) -> bool override {
    shape_ = shape;
    FormalArchiveDeadline deadline({bounded_deadline(input_.setup_ns)});
    for (std::size_t i = 0U; i < 6U; ++i) {
      data_[i] = std::make_unique<calibration::MappedPilotData<>>(input_.contexts[i]);
      if (!data_[i]->prepare())
        return false;
    }
    std::uint64_t retained = 0U;
    prepared_.reserve(180U);
    metadata_.reserve(180U);
    const auto& rows = *input_.blueprint.at("captures").as_array();
    for (std::size_t i = 0U; i < 180U; ++i) {
      auto p = input_.captures[i].native;
      p.capture.shared = data_[shape.contexts[i]]->view();
      const auto group = shape.source_groups[i];
      auto& group_sources = sources_[group];
      if (!group_sources.has_value()) {
        auto context = input_.sources;
        if (retained > context.maximum_vector_bytes)
          return false;
        context.maximum_vector_bytes -= retained;
        auto owned = prepare_s180_capture_from_sources(
            p, input_.source_artifacts[group], context, input_.reserved_descriptors);
        if (!owned)
          return false;
        group_sources.emplace(std::move(owned.value()));
        for (const auto& phase : p.capture.scheduled.phases)
          retained += phase.offered_count * 8U;
      }
      if (!group_sources.has_value())
        throw std::logic_error("S180 common source owner was not retained");
      p.capture.scheduled.deadlines = group_sources->plan().capture.scheduled.deadlines;
      if (!same_layout(calibration::native_pilot_layout(p),
                       input_.captures[i].expected_layout))
        return false;
      O metadata = *rows[shape.cells[i]].as_object();
      A phase_sources;
      for (std::size_t phase = 0U; phase < 2U; ++phase) {
        const auto& source = input_.source_artifacts[group][phase];
        phase_sources.emplace_back(
            O{{"schedule_id",
               text(p.capture.scheduled.phases[phase].schedule_id.value())},
              {"namespace_id",
               text(p.capture.scheduled.phases[phase].namespace_id.value())},
              {"source_artifact", V(O{{"artifact_id", text(source.artifact_id)},
                                      {"sha256", text(source.sha256)}})}});
      }
      metadata.emplace("schedules", V(std::move(phase_sources)));
      metadata_.push_back(std::move(metadata));
      prepared_.push_back(std::move(p));
    }
    return retained == shape.retained_vector_bytes;
  }
  auto mark_attempt(std::size_t i) -> bool override {
    current_ = i;
    capture_artifacts_.clear();
    native_result_ = {};
    output_.capture_budget(
        {input_.captures[i].max_output_bytes, input_.captures[i].metadata_bytes});
    capture_deadline_ = bounded_deadline(input_.captures[i].watchdog_ns);
    deadline_ = std::make_unique<FormalArchiveDeadline>(
        FormalArchiveAbsoluteDeadline{capture_deadline_});
    const auto r = output_.json(
        prefix(i) + "-attempt.json", "S180_RUN_ATTEMPT",
        "cpu-prefetch-stage17-s180-run-attempt/1",
        {{"schema_version", text("cpu-prefetch-stage17-s180-run-attempt/1")},
         {"session_id", text(authority_.session_id)},
         {"plan_sha256", text(authority_.plan_sha256)},
         {"execution_ordinal", integer(i)},
         {"cell_ordinal", integer(shape_.cells[i])},
         {"run_id", text(prepared_[i].capture.scheduled.service.run_ids[1U].value())},
         {"deadline_monotonic_ns", integer(capture_deadline_)},
         {"retry_allowed", V(false)}});
    return r.has_value();
  }
  auto enter(protocol::RequestedHardwareState state) -> bool override {
    const auto observed = platform::read_x86_family_model();
    return observed && hardware_.enter(observed.value(), state);
  }
  auto capture(std::size_t i) -> bool override {
    current_ = i;
    native_result_ =
        calibration::run_native_pilot_capture(prepared_[i], {this, &publish});
    return native_result_.stop == calibration::NativeCaptureStop::complete &&
           native_result_.publication_succeeded && capture_artifacts_.size() == 8U;
  }
  auto archive(std::size_t i, bool complete) -> bool override {
    deadline_.reset();
    const auto limit =
        std::min(capture_deadline_, bounded_deadline(input_.captures[i].archive_ns));
    FormalArchiveDeadline guard({limit});
    const auto checkpoint = output_.json(
        prefix(i) + "-checkpoint.json", "S180_CAPTURE_CHECKPOINT",
        "cpu-prefetch-stage17-s180-capture-checkpoint/1",
        {{"schema_version", text("cpu-prefetch-stage17-s180-capture-checkpoint/1")},
         {"session_id", text(authority_.session_id)},
         {"plan_sha256", text(authority_.plan_sha256)},
         {"program_scope_sha256", text(authority_.program_scope_sha256)},
         {"execution_ordinal", integer(i)},
         {"native_complete", V(complete)},
         {"native_result_after_private_cleanup",
          s180_capture_result_json(native_result_)},
         {"artifacts", references(capture_artifacts_)},
         {"shared_data_still_family_owned", V(true)},
         {"scientific_validity", text("NOT_ASSESSED")},
         {"execution_authority", V(false)},
         {"phase18_authority", V(false)}});
    if (!checkpoint)
      return false;
    const auto custody = sink_.archive_checkpoint(checkpoint.value(), limit);
    if (!custody || custody.value().role != "S180_ARCHIVE_CUSTODY" ||
        custody.value().schema_identity !=
            "cpu-prefetch-stage17-s180-archive-custody/1" ||
        !protocol::Sha256::parse(custody.value().sha256, "$s180/custody"))
      return false;
    const bool accounted = output_.account(custody.value());
    boundary_pending_ = i == 89U && complete && accounted;
    output_.family_budget();
    return accounted;
  }
  auto restore() noexcept -> bool override {
    try {
      deadline_.reset();
      std::uint64_t end = 0U;
      if (boundary_pending_) {
        transition_deadline_ = bounded_deadline(input_.whole_plot_transition_ns +
                                                input_.whole_plot_recovery_ns);
        end = bounded_deadline(input_.whole_plot_transition_ns);
      } else
        end = final_deadline();
      boundary_pending_ = false;
      FormalArchiveDeadline guard({end});
      bool result = hardware_.leave();
      A independently_observed;
      for (const auto& expected :
           input_.captures.front().native.controls.hardware_prestate) {
        const auto actual = verifier_.read(expected.cpu);
        independently_observed.emplace_back(
            O{{"cpu", integer(expected.cpu)},
              {"requested_prestate", integer(expected.value)},
              {"observed_value", actual ? integer(actual.value()) : V()},
              {"read_succeeded", V(actual.has_value())}});
        result = result && actual && actual.value() == expected.value;
      }
      const auto encode =
          [](std::span<const platform::HardwarePrefetchMsrValue> values) {
            A a;
            for (const auto& v : values)
              a.emplace_back(
                  O{{"cpu", integer(v.cpu)}, {"complete_value", integer(v.value)}});
            return V(std::move(a));
          };
      whole_plots_.emplace_back(
          O{{"requested_state",
             text(input_.captures[current_].native.controls.hardware_state ==
                          protocol::RequestedHardwareState::h1
                      ? "H1"
                      : "H0")},
            {"cumulative_apply_readback", encode(hardware_.apply_readback())},
            {"cumulative_restore_readback", encode(hardware_.restore_readback())},
            {"independent_restore_observations", V(std::move(independently_observed))},
            {"restoration_verified", V(result)}});
      return result;
    } catch (...) {
      return false;
    }
  }
  auto recover(std::uint64_t ns) -> bool override {
    if (ns > static_cast<std::uint64_t>(std::chrono::nanoseconds::max().count()))
      return false;
    if (!transition_deadline_)
      return false;
    FormalArchiveDeadline guard({*transition_deadline_});
    std::this_thread::sleep_for(std::chrono::nanoseconds(ns));
    transition_deadline_.reset();
    return true;
  }
  auto release_contexts() noexcept -> bool override {
    bool result = true;
    deadline_.reset();
    std::unique_ptr<FormalArchiveDeadline> guard;
    try {
      guard = std::make_unique<FormalArchiveDeadline>(
          FormalArchiveAbsoluteDeadline{final_deadline()});
    } catch (...) {
      result = false;
    }
    // All captures have joined before this family-level release. Every context
    // is attempted even when an earlier context's cleanup failed.
    for (auto& context : data_)
      if (context && !context->release())
        result = false;
    return result;
  }
  auto finish(const S180SessionResult& result) -> bool override {
    deadline_.reset();
    output_.capture_budget({input_.final_metadata_bytes, input_.final_metadata_bytes});
    FormalArchiveDeadline guard({final_deadline()});
    std::array<std::array<const platform::OwnerMappingEvidence*, 2U>, 6U> cleanup{};
    for (std::size_t i = 0U; i < 6U; ++i)
      if (data_[i])
        cleanup[i] = {&data_[i]->records_evidence(), &data_[i]->queues_evidence()};
    const auto report = output_.json(
        "s180-session-result.json", "S180_SESSION_RESULT",
        "cpu-prefetch-stage17-s180-session-result/1",
        {{"schema_version", text("cpu-prefetch-stage17-s180-session-result/1")},
         {"session_id", text(authority_.session_id)},
         {"plan_sha256", text(authority_.plan_sha256)},
         {"blueprint_sha256", text(kS180BlueprintSha256)},
         {"method_id", text(kS180MethodId)},
         {"stop", integer(static_cast<std::uint64_t>(result.stop))},
         {"attempted", integer(result.attempted)},
         {"completed", integer(result.completed)},
         {"restoration_attempted", V(result.restoration_attempted)},
         {"restoration_verified", V(result.restoration_verified)},
         {"cleanup_verified", V(result.cleanup_verified)},
         {"contexts_after_family_release", s180_context_cleanup_json(cleanup)},
         {"whole_plots", V(std::move(whole_plots_))},
         {"artifacts", references(bindings)},
         {"publication_scope", text("BEFORE_FINAL_PUBLICATION_RETURNS")},
         {"execution_authority", V(false)},
         {"phase18_authority", V(false)}});
    return report.has_value();
  }
  std::vector<ArtifactBinding> bindings;

private:
  static auto cpus(const S180SessionInput& input) -> std::span<const std::uint32_t> {
    const auto m = platform::find_hardware_prefetch_mapping(
        input.captures.front().native.controls.hardware_identity);
    if (!m || !m->control_cpus)
      throw std::invalid_argument("unregistered S180 hardware CPU set");
    return *m->control_cpus;
  }
  auto bounded_deadline(std::uint64_t duration) const -> std::uint64_t {
    const auto t = now();
    if (!t || duration > std::numeric_limits<std::uint64_t>::max() - *t)
      throw std::invalid_argument("S180 deadline cannot be represented");
    return std::min(*t + duration, authority_.window_end_monotonic_ns);
  }
  auto final_deadline() -> std::uint64_t {
    if (final_deadline_.has_value())
      return *final_deadline_;
    const auto end = bounded_deadline(input_.finalization_ns);
    final_deadline_ = end;
    return end;
  }
  static auto prefix(std::size_t i) -> std::string {
    return "s180-e" + std::to_string(i);
  }
  static auto publish(void* pointer,
                      const calibration::NativePilotPublicationView& view) noexcept
      -> bool {
    auto& self = *static_cast<Native*>(pointer);
    try {
      FormalPublicationTrackingSink tracked(self.output_, self.capture_artifacts_);
      return publish_s180_capture(tracked, self.current_, self.metadata_[self.current_],
                                  view)
          .has_value();
    } catch (...) {
      return false;
    }
  }
  const S180SessionInput& input_;
  const S180SessionAuthority& authority_;
  S180ArchiveSink& sink_;
  Output output_;
  S180SessionShape shape_{};
  platform::SystemPosixFileOperations writer_files_, verifier_files_;
  platform::LinuxHardwarePrefetchMsrBackend writer_, verifier_;
  platform::HardwarePrefetchWholePlotControl hardware_;
  std::array<std::unique_ptr<calibration::MappedPilotData<>>, 6U> data_;
  std::array<std::optional<PreparedS180Capture>, 18U> sources_;
  std::vector<calibration::NativePilotCapturePlan> prepared_;
  std::vector<O> metadata_;
  std::vector<ArtifactBinding> capture_artifacts_;
  calibration::NativePilotCaptureResult native_result_{};
  A whole_plots_;
  std::size_t current_{0U};
  std::uint64_t capture_deadline_{0U};
  std::unique_ptr<FormalArchiveDeadline> deadline_;
  std::optional<std::uint64_t> transition_deadline_, final_deadline_;
  bool boundary_pending_{false};
};
} // namespace
auto run_native_s180_session(const S180SessionInput& input,
                             const S180SessionAuthority& authority,
                             S180ArchiveSink& sink) -> protocol::Result<ActionOutcome> {
  try {
    const auto shape = validate_s180_session(input);
    if (!shape)
      return protocol::Result<ActionOutcome>::failure(shape.errors());
    const auto source = foundation::repository_info();
    if (source.source_dirty || input.source_revision != source.source_revision ||
        !sink.has_archive_checkpoint() ||
        authority.program_scope_sha256 != sink.s180_program_scope_sha256() ||
        !protocol::Sha256::parse(authority.program_scope_sha256, "$s180"))
      throw std::invalid_argument("S180 requires clean exact source and a scope-bound "
                                  "qualified S180 archive sink");
    Native native(input, authority, sink);
    const auto result = run_s180_session(input, authority, native);
    if (!result)
      return protocol::Result<ActionOutcome>::failure(result.errors());
    const auto& r = result.value();
    return protocol::Result<ActionOutcome>::success(
        {std::move(native.bindings), r.restoration_verified,
         !r.cleanup_verified || !r.restoration_verified,
         r.stop == S180SessionStop::complete ? "S180_PILOT_FAMILY_COMPLETED"
                                             : "S180_PILOT_FAMILY_INCOMPLETE"});
  } catch (const std::exception& e) {
    return protocol::Result<ActionOutcome>::failure(
        {protocol::ErrorCategory::cross_field, "$/s180/native-session",
         "S17-S180-NATIVE-SESSION", e.what()});
  }
}
} // namespace cpu_prefetch::runner::stage17
