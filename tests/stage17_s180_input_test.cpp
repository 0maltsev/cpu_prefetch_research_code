#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/runner/stage17_s180_input.hpp"
#include "cpu_prefetch/runner/stage17_s180_worker.hpp"
#include "s180_session_test_support.hpp"
#include <cerrno>
#include <chrono>
#include <poll.h>
#include <sys/socket.h>
#include <sys/wait.h>
namespace {
using namespace cpu_prefetch::test::s180;
auto n(std::uint64_t x) -> V {
  return V(protocol::json::Number{protocol::json::Number::Kind::unsigned_integer,
                                  std::to_string(x), x});
}
auto t(std::string_view s) -> V { return V(std::string(s)); }
template <class Range> auto numbers(const Range& values) -> V {
  V::Array a;
  for (auto value : values)
    a.push_back(n(value));
  return V(std::move(a));
}
auto stack_json(const platform::OwnerMappingPlan& p) -> V {
  return V(O{{"bytes", n(p.bytes)},
             {"verified_base_page_bytes", n(p.verified_base_page_bytes)},
             {"owner_cpu", n(p.owner_cpu)},
             {"requested_node", n(p.requested_node)}});
}
auto layout_json(const c::NativePilotCaptureLayout& p) -> V {
  const auto& w = p.workers;
  V::Array phases;
  for (const auto& v : w.phases)
    phases.emplace_back(O{{"producer_object", n(v.producer_object)},
                          {"producer_raw", n(v.producer_raw)},
                          {"consumer_object", n(v.consumer_object)},
                          {"consumer_raw", n(v.consumer_raw)},
                          {"raw", V(O{{"producer_bytes", n(v.raw.producer_bytes)},
                                      {"consumer_bytes", n(v.raw.consumer_bytes)}})}});
  return V(O{{"core_bytes", n(p.core_bytes)},
             {"monitor_bytes", n(p.monitor_bytes)},
             {"total_mapping_bytes", n(p.total_mapping_bytes)},
             {"region_bytes", numbers(p.region_bytes)},
             {"workers", V(O{{"records_bytes", n(w.records_bytes)},
                             {"producer_bytes", n(w.producer_bytes)},
                             {"consumer_bytes", n(w.consumer_bytes)},
                             {"schedule_offsets", numbers(w.schedule_offsets)},
                             {"emitter_object", n(w.emitter_object)},
                             {"package_object", n(w.package_object)},
                             {"phases", V(std::move(phases))}})}});
}
struct Documents final {
  O plan, source;
  explicit Documents(const Fixture& f) {
    V::Array captures, bindings, prestate;
    for (const auto& p : f.prestate)
      prestate.emplace_back(O{{"cpu", n(p.cpu)}, {"value", n(p.value)}});
    const auto& baseline = f.input.captures.front().native.controls;
    for (std::size_t i = 0U; i < 180U; ++i) {
      const auto& c = f.input.captures[i];
      const auto& ctl = c.native.controls;
      const auto& scheduled = c.native.capture.scheduled;
      const auto& service = scheduled.service;
      V::Array caps, phases, limits, environment;
      for (const auto& v : service.capacity)
        caps.emplace_back(O{{"producer_primary_rows", n(v.producer_primary_rows)},
                            {"consumer_primary_rows", n(v.consumer_primary_rows)}});
      const auto ctx =
          c.native.controls.workers.consumer_stack.owner_cpu == 1U ? 0U : 3U;
      const auto ws = service.arena.capacity == 512U     ? 0U
                      : service.arena.capacity == 65536U ? 1U
                                                         : 2U;
      const auto& rows = *at(f.input.blueprint, "captures").as_array();
      const auto found = std::find_if(rows.begin(), rows.end(), [&](const auto& row) {
        return number(*row.as_object(), "execution_ordinal") == i;
      });
      const auto& row = *found->as_object();
      const auto load = text(row, "load_level") == "L025"   ? 0U
                        : text(row, "load_level") == "L050" ? 1U
                                                            : 2U;
      for (std::size_t j = 0U; j < 2U; ++j) {
        const auto& p = service.session.phases[j];
        const auto& s = scheduled.phases[j];
        const auto& b = f.input.source_artifacts[(ctx + ws) * 3U + load][j];
        phases.emplace_back(O{{"producer_attempt_limit", n(p.producer_attempt_limit)},
                              {"consumer_poll_limit", n(p.consumer_poll_limit)},
                              {"drain_duration_ticks", n(p.drain_duration_ticks)},
                              {"schedule_id", t(s.schedule_id.value())},
                              {"source_origin_ticks", n(s.source_origin_ticks)},
                              {"source_horizon_ticks", n(s.source_horizon_ticks)},
                              {"offered_count", n(s.offered_count)},
                              {"source_artifact", V(O{{"artifact_id", t(b.artifact_id)},
                                                      {"sha256", t(b.sha256)}})}});
        V::Array owners;
        for (const auto& v : ctl.counter_limits[j]) {
          auto bound = [](auto optional) {
            return optional ? n(*optional) : V(nullptr);
          };
          owners.emplace_back(
              O{{"minor_faults", bound(v.minor_faults)},
                {"major_faults", bound(v.major_faults)},
                {"voluntary_switches", bound(v.voluntary_switches)},
                {"involuntary_switches", bound(v.involuntary_switches)}});
        }
        limits.emplace_back(std::move(owners));
      }
      // A heap-backed path exercises ownership after caller documents die.
      environment.emplace_back(
          O{{"path", t("/sys/" + std::string(160U, 'a'))},
            {"byte_capacity", n(256U)},
            {"chunk_bytes", n(64U)},
            {"max_data_reads", n(5U)},
            {"requested",
             V(V::Array{V(true), V(true), V(true), V(true), V(true), V(true)})}});
      captures.emplace_back(
          O{{"execution_ordinal", n(i)},
            {"cell_ordinal", n(number(row, "cell_ordinal"))},
            {"resources",
             V(O{{"workers",
                  V(O{{"producer_stack", stack_json(ctl.workers.producer_stack)},
                      {"consumer_stack", stack_json(ctl.workers.consumer_stack)}})},
                 {"controller_stack", stack_json(ctl.controller_stack)},
                 {"tls_module_capacity", n(ctl.tls_module_capacity)},
                 {"thread_stat_bytes", n(ctl.thread_stat_bytes)},
                 {"thread_status_bytes", n(ctl.thread_status_bytes)},
                 {"thread_affinity_words", n(ctl.thread_affinity_words)},
                 {"initial_consumer_state", n(service.initial_consumer.value)},
                 {"phase_capacity", V(std::move(caps))}})},
            {"monitoring",
             V(O{{"during_first_page", numbers(ctl.during_first_page)},
                 {"during_page_count", numbers(ctl.during_page_count)},
                 {"during_offset_ticks", numbers(ctl.during_offset_ticks)},
                 {"observer_wait_poll_limit", n(ctl.observer_wait_poll_limit)},
                 {"control_region_index", n(ctl.control_region_index)},
                 {"counter_limits", V(std::move(limits))},
                 {"environment_sources", V(std::move(environment))}})},
            {"phases", V(std::move(phases))},
            {"expected_layout", layout_json(c.expected_layout)},
            {"execution_budget",
             V(O{{"watchdog_ns", n(c.watchdog_ns)},
                 {"archive_ns", n(c.archive_ns)},
                 {"max_output_bytes", n(c.max_output_bytes)},
                 {"metadata_bytes", n(c.metadata_bytes)},
                 {"barrier_poll_limit", n(service.session.barrier_poll_limit)}})}});
    }
    for (const auto& b : f.bindings)
      bindings.emplace_back(
          O{{"artifact_id", t(b.artifact_id)},
            {"canonical_sha256", t(b.canonical_sha256)},
            {"size_bytes", n(b.size_bytes)},
            {"descriptor", n(static_cast<std::uint64_t>(b.descriptor))}});
    source = {
        {"schema_version", t("cpu-prefetch-stage17-s180-schedule-source-context/1")},
        {"maximum_vector_bytes", n(f.input.sources.maximum_vector_bytes)},
        {"deadline_monotonic_ns", n(f.input.sources.deadline_monotonic_ns)},
        {"bindings", V(std::move(bindings))}};
    plan = {{"schema_version", t("cpu-prefetch-stage17-s180-session-plan/1")},
            {"source_revision", t(f.input.source_revision)},
            {"blueprint", V(f.input.blueprint)},
            {"hardware",
             V(O{{"identity", V(O{{"family", n(baseline.hardware_identity.family)},
                                  {"model", n(baseline.hardware_identity.model)}})},
                 {"prestate", V(std::move(prestate))},
                 {"software_prefetch_mapping_id",
                  t(f.input.captures.front().native.software_prefetch_mapping_id)}})},
            {"captures", V(std::move(captures))},
            {"budget",
             V(O{{"setup_ns", n(f.input.setup_ns)},
                 {"whole_plot_transition_ns", n(f.input.whole_plot_transition_ns)},
                 {"whole_plot_recovery_ns", n(f.input.whole_plot_recovery_ns)},
                 {"finalization_ns", n(f.input.finalization_ns)},
                 {"final_metadata_bytes", n(f.input.final_metadata_bytes)},
                 {"memory_bytes", n(f.input.memory_bytes)},
                 {"max_output_bytes", n(f.input.max_output_bytes + 65536U)},
                 {"entry_metadata_bytes", n(65536U)}})},
            {"storage",
             V(O{{"pilot_policy_id", t("D310-S180-LOSSLESS-STAND-PRIMARY-v1")},
                 {"approval_sha256",
                  t(text(*at(f.input.blueprint, "approval").as_object(), "sha256"))},
                 {"program_id", t("synthetic-s180")},
                 {"program_scope_sha256", t(std::string(64U, 'b'))},
                 {"implementation_profile_sha256", t(std::string(64U, 'c'))},
                 {"archive_staging_bytes", n(1048576U)},
                 {"maximum_custody_receipt_bytes", n(131072U)}})}};
  }
};
void field(O& parent, std::initializer_list<std::string> keys, V value) {
  if (keys.size() != 2U)
    throw std::logic_error("test mutation path");
  const auto& key = *keys.begin();
  const auto& child = *(keys.begin() + 1);
  auto object = *parent.at(key).as_object();
  object.insert_or_assign(child, std::move(value));
  parent[key] = V(std::move(object));
}
TEST(S180Input, ClosedDocumentBuildsAllNativeInputsAndOwnsBorrowedPathsAfterCopyMove) {
  Fixture f;
  auto parsed = [&] {
    Documents d(f);
    return r::parse_s180_session_input(std::move(d.plan), d.source, {});
  }();
  ASSERT_TRUE(parsed) << parsed.errors().front().message;
  auto moved = std::move(parsed.value());
  // Copy construction and independent prestate ownership are under test.
  // NOLINTNEXTLINE(performance-unnecessary-copy-initialization)
  auto copy = moved;
  auto input = copy.input();
  ASSERT_TRUE(r::validate_s180_session(input));
  EXPECT_EQ(input.contexts.size(), 6U);
  EXPECT_EQ(input.captures.size(), 180U);
  EXPECT_EQ(input.sources.bindings.size(), 36U);
  EXPECT_EQ(input.captures.front().native.controls.environment_sources.front().path,
            "/sys/" + std::string(160U, 'a'));
  EXPECT_EQ(input.captures.back().native.controls.hardware_prestate.size(), 3U);
  EXPECT_NE(input.captures.front().native.controls.hardware_prestate.data(),
            f.prestate.data());
  EXPECT_EQ(input.captures[0U].native.capture.scheduled.service.run_ids[1U].value(),
            f.input.captures[0U].native.capture.scheduled.service.run_ids[1U].value());
  EXPECT_TRUE(input.captures.front().native.capture.scheduled.deadlines[0U].empty());
}
TEST(S180Input, FrozenOrderGeometryCountsAndInlineOrUnknownFieldsReject) {
  Fixture f;
  for (int mode = 0; mode < 7; ++mode) {
    Documents d(f);
    auto rows = *d.plan.at("captures").as_array();
    auto entry = *rows.front().as_object();
    if (mode == 0)
      std::swap(rows[0U], rows[1U]);
    if (mode == 1)
      rows.pop_back();
    if (mode == 2)
      entry["deadline_ticks"] = V(V::Array{});
    if (mode == 3)
      entry["execution_ordinal"] = V(false);
    if (mode == 4)
      field(d.plan, {"blueprint", "measurement_ns"}, n(2U));
    if (mode == 5)
      field(entry, {"execution_budget", "watchdog_ns"}, n(1U));
    if (mode == 6)
      field(entry, {"resources", "initial_consumer_state"}, n(99U));
    if (mode >= 2 && mode != 4)
      rows.front() = V(std::move(entry));
    d.plan["captures"] = V(std::move(rows));
    EXPECT_FALSE(r::parse_s180_session_input(std::move(d.plan), d.source, {})) << mode;
  }
}
TEST(S180Input, SourceMembershipPairedHashAndReservedPhysicalAliasesReject) {
  Fixture f;
  for (int mode = 0; mode < 4; ++mode) {
    Documents d(f);
    auto bindings = *d.source.at("bindings").as_array();
    if (mode == 0)
      bindings.pop_back();
    if (mode == 1)
      bindings[1U] = bindings[0U];
    if (mode == 2) {
      auto b = *bindings[0U].as_object();
      b["canonical_sha256"] = t(std::string(64U, 'f'));
      bindings[0U] = V(std::move(b));
    }
    d.source["bindings"] = V(std::move(bindings));
    const std::array<int, 1U> reserved{f.bindings.front().descriptor};
    EXPECT_FALSE(r::parse_s180_session_input(std::move(d.plan), d.source,
                                             mode == 3 ? std::span<const int>(reserved)
                                                       : std::span<const int>{}));
  }
}
TEST(S180Input, HardwareStorageOverflowAndObservationContractRejectBeforeExecution) {
  Fixture f;
  for (int mode = 0; mode < 5; ++mode) {
    Documents d(f);
    if (mode == 0)
      field(d.plan, {"storage", "approval_sha256"}, t(std::string(64U, 'f')));
    if (mode == 1)
      field(d.plan, {"hardware", "prestate"}, V(V::Array{}));
    if (mode == 2) {
      auto hw = *d.plan.at("hardware").as_object();
      field(hw, {"identity", "family"}, n(std::uint64_t{1U} << 40U));
      d.plan["hardware"] = V(std::move(hw));
    }
    if (mode == 3) {
      auto rows = *d.plan.at("captures").as_array();
      auto entry = *rows.front().as_object();
      field(entry, {"monitoring", "during_page_count"}, V(V::Array{}));
      rows.front() = V(std::move(entry));
      d.plan["captures"] = V(std::move(rows));
    }
    if (mode == 4)
      field(d.plan, {"budget", "memory_bytes"}, n(1U));
    EXPECT_FALSE(r::parse_s180_session_input(std::move(d.plan), d.source, {})) << mode;
  }
}
auto sizing_plan(O plan) -> O {
  plan["schema_version"] = t("cpu-prefetch-stage17-s180-sizing-plan/1");
  plan["source_count_basis"] = t("EXACT_DECLARED_COUNTS");
  auto rows = *plan.at("captures").as_array();
  for (auto& value : rows) {
    auto row = *value.as_object();
    row.erase("expected_layout");
    value = V(std::move(row));
  }
  plan["captures"] = V(std::move(rows));
  return plan;
}
TEST(S180Input, PureFamilySizingRequiresNoSourcesAndCannotBecomeAnExecutionTicket) {
  Fixture f;
  Documents d(f);
  auto plan = sizing_plan(d.plan);
  const auto result = r::describe_s180_session_layouts(plan);
  ASSERT_TRUE(result) << result.errors().front().message;
  EXPECT_EQ(result.value().at("contexts").as_array()->size(), 6U);
  const auto& rows = *result.value().at("captures").as_array();
  ASSERT_EQ(rows.size(), 180U);
  for (const auto& value : rows)
    EXPECT_GT(number(*value.as_object()->at("expected_layout").as_object(),
                     "total_mapping_bytes"),
              0U);
  EXPECT_FALSE(*result.value().at("execution_authority").as_bool());
  EXPECT_FALSE(*result.value().at("session_admission_performed").as_bool());
  EXPECT_FALSE(r::parse_s180_session_input(plan, d.source, {}));
  EXPECT_FALSE(r::describe_s180_session_layouts(d.plan));
}
TEST(S180Input, RegisteredR1DistanceIsUncalibratedAndR2BindsTheAcceptedFreeze) {
  Fixture f;
  Documents d(f);
  auto parsed = r::parse_s180_session_input(d.plan, d.source, {});
  ASSERT_TRUE(parsed);
  auto input = parsed.value().input();
  bool r1 = false, r2 = false, checked_rejection = false;
  for (auto& capture : input.captures) {
    auto& service = capture.native.capture.scheduled.service;
    if (service.package == protocol::QueuePackage::r1) {
      r1 = true;
      if (!service.ring_distance.has_value())
        throw std::logic_error("expected ring distance missing");
      auto& distance = service.ring_distance.value();
      EXPECT_TRUE(distance.calibration_evidence_id.empty());
      if (!checked_rejection) {
        distance.calibration_evidence_id = "wrong-calibration-credit";
        EXPECT_FALSE(r::validate_s180_session(input));
        distance.calibration_evidence_id.clear();
        checked_rejection = true;
      }
    }
    if (service.package == protocol::QueuePackage::r2) {
      r2 = true;
      if (!service.ring_distance.has_value())
        throw std::logic_error("expected ring distance missing");
      auto& distance = service.ring_distance.value();
      EXPECT_EQ(
          distance.calibration_evidence_id,
          text(*at(f.input.blueprint, "calibration_freeze").as_object(), "sha256"));
    }
  }
  EXPECT_TRUE(r1 && r2);
  EXPECT_TRUE(r::validate_s180_session(input));
}
auto encode(const O& o) -> std::string {
  return protocol::json::canonicalize(V(o)).value();
}
auto hash_text(std::string_view s) -> std::string {
  return workload::sha256(std::as_bytes(std::span(s.data(), s.size()))).hex();
}
struct JsonFd final {
  int writer{-1}, reader{-1};
  explicit JsonFd(const O& document, bool sealed = true) {
    const auto raw = encode(document);
    writer = static_cast<int>(::syscall(SYS_memfd_create, "s180-request-test",
                                        MFD_CLOEXEC | MFD_ALLOW_SEALING));
    if (writer < 0 ||
        ::write(writer, raw.data(), raw.size()) != static_cast<ssize_t>(raw.size()))
      throw std::runtime_error("request fixture write");
    if (sealed &&
        ::fcntl(writer, F_ADD_SEALS,
                F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL) != 0)
      throw std::runtime_error("request fixture seals");
    reader = ::open(("/proc/self/fd/" + std::to_string(writer)).c_str(),
                    O_RDONLY | O_CLOEXEC);
    if (reader < 0)
      throw std::runtime_error("request fixture reopen");
  }
  ~JsonFd() {
    static_cast<void>(::close(reader));
    static_cast<void>(::close(writer));
  }
  JsonFd(const JsonFd&) = delete;
  auto operator=(const JsonFd&) -> JsonFd& = delete;
};
struct EntryBackend final : r::S180WorkerOperations {
  bool custody{false};
  auto synthetic_test_only() const noexcept -> bool override { return true; }
  auto execute(const r::S180SessionInput& input,
               const r::S180SessionAuthority& authority, r::S180ArchiveSink& sink)
      -> protocol::Result<r::ActionOutcome> override {
    if (input.captures.size() != 180U || input.contexts.size() != 6U ||
        input.sources.bindings.size() != 36U ||
        authority.window_end_monotonic_ns - authority.window_start_monotonic_ns !=
            r::kS180OperationalCapNs ||
        input.captures.front().native.controls.environment_sources.front().path !=
            "/sys/" + std::string(160U, 'a'))
      throw std::runtime_error("entry input did not survive");
    if (custody) {
      const std::string checkpoint = "{\"synthetic_test_only\":true}";
      const auto data = std::as_bytes(std::span(checkpoint.data(), checkpoint.size()));
      auto binding = sink.publish({"S180_CAPTURE_CHECKPOINT",
                                   "cpu-prefetch-stage17-s180-capture-checkpoint/1",
                                   "application/json",
                                   "s180-e0-checkpoint.json",
                                   {data.begin(), data.end()}});
      if (!binding)
        return protocol::Result<r::ActionOutcome>::failure(binding.errors());
      const auto current = static_cast<std::uint64_t>(
          std::chrono::duration_cast<std::chrono::nanoseconds>(
              std::chrono::steady_clock::now().time_since_epoch())
              .count());
      auto receipt = sink.archive_checkpoint(binding.value(), current + 2'000'000'000U);
      if (!receipt) {
        if (sink.has_archive_checkpoint())
          throw std::runtime_error("failed custody did not latch");
        return protocol::Result<r::ActionOutcome>::failure(receipt.errors());
      }
    }
    const std::string raw =
        "{\"synthetic_test_only\":true,\"execution_authority\":false}";
    const auto bytes = std::as_bytes(std::span(raw.data(), raw.size()));
    auto published = sink.publish({"SOFTWARE_ONLY",
                                   "software-only/1",
                                   "application/json",
                                   "software-entry.json",
                                   {bytes.begin(), bytes.end()}});
    if (!published)
      return protocol::Result<r::ActionOutcome>::failure(published.errors());
    return protocol::Result<r::ActionOutcome>::success(
        {{}, true, false, "S180_PILOT_FAMILY_COMPLETED"});
  }
};
struct EntryResult final {
  int status;
  std::size_t files;
  std::string error;
};
auto entry(int mode) -> EntryResult {
  Fixture f;
  f.input.setup_ns = 30'000'000'000U;
  if (mode >= 18) {
    f.input.captures.front().archive_ns = 3'000'000'000U;
    f.input.captures.front().watchdog_ns = 10'000'000'000U;
  }
  Documents docs(f);
  if (mode == 17)
    field(docs.plan, {"budget", "entry_metadata_bytes"}, n(1U));
  const auto executable = r::inspect_s180_executable();
  if (!executable)
    throw std::runtime_error(executable.errors().front().message);
  const auto source = foundation::repository_info();
  docs.plan["source_revision"] = t(source.source_revision);
  const auto mono = static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch())
          .count());
  docs.source["deadline_monotonic_ns"] = n(mono + f.input.setup_ns);
  std::array<int, 2U> sockets{};
  if (::socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0, sockets.data()) != 0)
    throw std::runtime_error("entry test socket");
  struct Sockets final {
    std::array<int, 2U> fds;
    ~Sockets() {
      for (auto v : fds)
        static_cast<void>(::close(v));
    }
  } owned{sockets};
  const std::string scope(64U, 'b');
  O prerequisites{
      {"calibration_freeze_sha256",
       at(*at(f.input.blueprint, "calibration_freeze").as_object(), "sha256")},
      {"ext007_resolution_sha256",
       at(*at(f.input.blueprint, "ext007_resolution").as_object(), "sha256")}};
  for (const auto name : {"ext008_resolution_sha256", "ext009_resolution_sha256",
                          "ext010_authorization_sha256", "qualification_sha256",
                          "compatibility_sha256", "runtime_profile_sha256"})
    prerequisites[name] = t(std::string(64U, 'e'));
  O request{{"schema_version", t("cpu-prefetch-stage17-s180-session-request/1")},
            {"request_id", t("software-request")},
            {"session_id", t("software-session")},
            {"attempt_id", t("attempt-1")},
            {"authorization_id", t("software-authorization")},
            {"stand_id", at(f.input.blueprint, "stand_id")},
            {"plan", V(docs.plan)},
            {"runtime_binding", V(O{{"role", t(r::kS180WorkerRole)},
                                    {"profile", t(r::kS180WorkerProfile)},
                                    {"sha256", t(executable.value().sha256)},
                                    {"size_bytes", n(executable.value().size_bytes)}})},
            {"release_binding", V(O{{"source_revision", t(source.source_revision)},
                                    {"worker_sha256", t(executable.value().sha256)}})},
            {"prerequisite_bindings", V(prerequisites)},
            {"synthetic_test_only", V(true)},
            {"phase18_authority", V(false)}};
  std::array<char, 64U> temporary{};
  const std::string pattern = "/tmp/s180-entry-XXXXXX";
  std::copy(pattern.begin(), pattern.end(), temporary.begin());
  if (!::mkdtemp(temporary.data()))
    throw std::runtime_error("entry test directory");
  const auto directory_fd =
      ::open(temporary.data(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
  if (directory_fd < 0)
    throw std::runtime_error("entry test directory open");
  struct Directory final {
    int fd;
    const char* path;
    ~Directory() {
      static_cast<void>(::unlinkat(fd, "s180-session-entry.json", 0));
      static_cast<void>(::unlinkat(fd, "software-entry.json", 0));
      static_cast<void>(::unlinkat(fd, "s180-e0-checkpoint.json", 0));
      static_cast<void>(::unlinkat(fd, "s180-e0-archive-custody.json", 0));
      static_cast<void>(::close(fd));
      static_cast<void>(::rmdir(path));
    }
  } directory{directory_fd, temporary.data()};
  struct stat root{};
  if (::fstat(directory_fd, &root) != 0)
    throw std::runtime_error("entry test root");
  if (mode == 16) {
    const auto marker = ::openat(directory_fd, "s180-session-entry.json",
                                 O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (marker < 0)
      throw std::runtime_error("entry replay fixture");
    static_cast<void>(::close(marker));
  }
  std::ifstream boot_file("/proc/sys/kernel/random/boot_id");
  std::string boot;
  std::getline(boot_file, boot);
  const auto epoch = static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::seconds>(
          std::chrono::system_clock::now().time_since_epoch())
          .count());
  O context{
      {"schema_version", t("cpu-prefetch-stage17-s180-session-context/1")},
      {"request_id", t("software-request")},
      {"session_id", t("software-session")},
      {"attempt_id", t("attempt-1")},
      {"authorization_id", t("software-authorization")},
      {"authorization_sha256", t(std::string(64U, 'e'))},
      {"request_sha256", t(hash_text(encode(request)))},
      {"plan_sha256", t(hash_text(encode(docs.plan)))},
      {"runtime_sha256", t(executable.value().sha256)},
      {"release_sha256", t(executable.value().sha256)},
      {"prerequisite_bindings", V(prerequisites)},
      {"readiness_scope", t("D310-S180-SCOPED-READY-v1")},
      {"issued_at_epoch_seconds", n(epoch - 1U)},
      {"expires_at_epoch_seconds", n(epoch + 86402U)},
      {"window_start_monotonic_ns", n(mono - 1U)},
      {"window_end_monotonic_ns", n(mono - 1U + r::kS180OperationalCapNs)},
      {"schedule_source_context", V(docs.source)},
      {"archive_channel",
       V(O{{"descriptor", n(static_cast<std::uint64_t>(sockets[1U]))},
           {"controller_pid", n(static_cast<std::uint64_t>(::getpid()))},
           {"program_scope_sha256", t(scope)}})},
      {"output_directory", V(O{{"device", n(static_cast<std::uint64_t>(root.st_dev))},
                               {"inode", n(static_cast<std::uint64_t>(root.st_ino))}})},
      {"boot_id", t(boot)},
      {"synthetic_test_only", V(true)},
      {"phase18_authority", V(false)}};
  if (mode == 2)
    context["request_sha256"] = t(std::string(64U, '0'));
  if (mode == 3)
    context["runtime_sha256"] = t(std::string(64U, '0'));
  if (mode == 4)
    context["expires_at_epoch_seconds"] = n(1U);
  if (mode == 5)
    context["window_end_monotonic_ns"] = n(mono + 1000000000U);
  if (mode == 6)
    context["boot_id"] = t("foreign-boot");
  if (mode == 7)
    field(context, {"output_directory", "inode"},
          n(static_cast<std::uint64_t>(root.st_ino) + 1U));
  if (mode == 8)
    field(context, {"prerequisite_bindings", "ext009_resolution_sha256"},
          t(std::string(64U, 'f')));
  if (mode == 9)
    context["readiness_scope"] = t("LEGACY_READY");
  if (mode == 10)
    context["phase18_authority"] = V(true);
  if (mode == 11)
    field(context, {"archive_channel", "controller_pid"}, n(1U));
  if (mode == 12)
    context["plan_sha256"] = t(std::string(64U, '0'));
  if (mode == 13)
    field(context, {"schedule_source_context", "deadline_monotonic_ns"}, n(1U));
  if (mode == 15)
    context["expires_at_epoch_seconds"] = n(epoch + 60U);
  JsonFd request_fd(request, mode != 1), context_fd(context);
  std::array<int, 2U> diagnostics{};
  if (::pipe2(diagnostics.data(), O_CLOEXEC) != 0)
    throw std::runtime_error("entry test diagnostic pipe");
  const auto child = ::fork();
  if (child == 0) {
    static_cast<void>(::close(diagnostics[0U]));
    static_cast<void>(::alarm(30U));
    std::array<std::string, 9U> arguments{"worker",
                                          "--execute-stage17-s180-session-v1",
                                          "--request-fd",
                                          std::to_string(request_fd.reader),
                                          "--context-fd",
                                          std::to_string(context_fd.reader),
                                          "--output-dir-fd",
                                          std::to_string(directory_fd),
                                          "--fixed-dispatch-end"};
    std::array<char*, 9U> argv{};
    for (std::size_t i = 0U; i < argv.size(); ++i)
      argv[i] = arguments[i].data();
    EntryBackend backend;
    backend.custody = mode >= 18;
    r::LinuxS180WorkerOperations native;
    try {
      const auto status = r::run_s180_session_worker(
          9, argv.data(),
          mode == 14 ? static_cast<r::S180WorkerOperations&>(native) : backend);
      ::_exit(status);
    } catch (const std::exception& error) {
      static_cast<void>(::write(
          diagnostics[1U], error.what(),
          std::min<std::size_t>(std::char_traits<char>::length(error.what()), 1024U)));
      ::_exit(1);
    }
  }
  static_cast<void>(::close(diagnostics[1U]));
  if (child < 0)
    throw std::runtime_error("entry test fork");
  if (mode >= 18) {
    pollfd ready{sockets[0U], POLLIN, 0};
    if (::poll(&ready, 1U, 30000) != 1)
      throw std::runtime_error("entry custody fixture timeout");
    std::array<char, 8192U> packet{};
    const auto length = ::recv(sockets[0U], packet.data(), packet.size(), 0);
    if (length <= 0)
      throw std::runtime_error("entry custody fixture request");
    const auto parsed = protocol::json::parse(
        std::string_view(packet.data(), static_cast<std::size_t>(length)));
    if (!parsed || !parsed.value().as_object())
      throw std::runtime_error("entry custody fixture JSON");
    const auto& checkpoint = *at(*parsed.value().as_object(), "checkpoint").as_object();
    const std::string receipt =
        "{\"synthetic_test_only\":true,\"execution_authority\":false}";
    const auto durable = ::openat(directory_fd, "s180-e0-archive-custody.json",
                                  O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    const std::string actual = mode == 19 ? "tampered" : receipt;
    if (durable < 0 ||
        ::write(durable, actual.data(), actual.size()) !=
            static_cast<ssize_t>(actual.size()) ||
        ::fsync(durable) != 0 || ::close(durable) != 0 || ::fsync(directory_fd) != 0)
      throw std::runtime_error("entry custody fixture durability");
    const O ack{
        {"schema_version", t("cpu-prefetch-stage17-s180-archive-checkpoint-ack/1")},
        {"request_sha256", t(hash_text(encode(request)))},
        {"program_scope_sha256", t(scope)},
        {"capture_ordinal", n(0U)},
        {"checkpoint_sha256", at(checkpoint, "sha256")},
        {"status", t("ARCHIVED_AND_RELEASED")},
        {"custody_receipt", V(O{{"file_name", t("s180-e0-archive-custody.json")},
                                {"size_bytes", n(receipt.size())},
                                {"sha256", t(hash_text(receipt))}})}};
    const auto raw = encode(ack);
    if (::send(sockets[0U], raw.data(), raw.size(), MSG_NOSIGNAL) !=
        static_cast<ssize_t>(raw.size()))
      throw std::runtime_error("entry custody fixture ACK");
  }
  std::array<char, 1024U> message{};
  const auto count = ::read(diagnostics[0U], message.data(), message.size());
  static_cast<void>(::close(diagnostics[0U]));
  int status = 0;
  while (::waitpid(child, &status, 0) < 0)
    if (errno != EINTR)
      throw std::runtime_error("entry test wait");
  std::size_t files = 0U;
  for (const auto name : {"s180-session-entry.json", "software-entry.json"}) {
    struct stat st{};
    if (::fstatat(directory_fd, name, &st, AT_SYMLINK_NOFOLLOW) == 0)
      ++files;
  }
  return {WIFEXITED(status) ? WEXITSTATUS(status) : 128, files,
          count > 0 ? std::string(message.data(), static_cast<std::size_t>(count))
                    : std::string{}};
}
TEST(S180Worker, ActualSealedFdEntryReachesOnlyTheSeparatelyLinkedSoftwareBackend) {
  auto result = entry(0);
  EXPECT_EQ(result.status, 0) << result.error;
  EXPECT_EQ(result.files, 2U);
}
TEST(S180Worker, WholeSecondEpochRoundingCannotShortenTheMonotonicWindow) {
  EXPECT_FALSE(r::s180_epoch_authority_covers_window({0U, 101U, 100U, 1U}));
  EXPECT_FALSE(r::s180_epoch_authority_covers_window({0U, 101U, 100U, 1'000'000'000U}));
  EXPECT_TRUE(r::s180_epoch_authority_covers_window({0U, 102U, 100U, 1'000'000'000U}));
  EXPECT_FALSE(r::s180_epoch_authority_covers_window({101U, 102U, 100U, 1U}));
  EXPECT_FALSE(r::s180_epoch_authority_covers_window({0U, 100U, 100U, 1U}));
  EXPECT_FALSE(r::s180_epoch_authority_covers_window({0U, 102U, 100U, 0U}));
  EXPECT_FALSE(r::s180_epoch_authority_covers_window(
      {0U, ~std::uint64_t{0U}, ~std::uint64_t{0U}, 1U}));
}
TEST(S180Worker, ImmutableRequestAndExactRuntimeScopeAreRequiredBeforeAnyOutput) {
  for (const auto mode : {1, 2, 3, 8, 9, 10, 12, 14}) {
    auto result = entry(mode);
    EXPECT_NE(result.status, 0) << mode;
    EXPECT_EQ(result.files, 0U) << mode << ":" << result.error;
  }
}
TEST(S180Worker, WindowExpiryBootOutputRootAndActualParentCannotBeSubstituted) {
  for (const auto mode : {4, 5, 6, 7, 11, 13, 15}) {
    auto result = entry(mode);
    EXPECT_NE(result.status, 0) << mode;
    EXPECT_EQ(result.files, 0U) << mode << ":" << result.error;
  }
}
TEST(S180Worker, EntryMarkerCannotBeReplayedOrBorrowNativeOutputReservation) {
  auto replay = entry(16);
  EXPECT_NE(replay.status, 0);
  EXPECT_EQ(replay.files, 1U) << replay.error;
  auto tiny = entry(17);
  EXPECT_NE(tiny.status, 0);
  EXPECT_EQ(tiny.files, 0U) << tiny.error;
}
TEST(S180Worker, RealWorkerSinkChecksDurableCustodyBytesBeforeReturningFromAck) {
  auto valid = entry(18);
  EXPECT_EQ(valid.status, 0) << valid.error;
  EXPECT_EQ(valid.files, 2U);
  auto changed = entry(19);
  EXPECT_NE(changed.status, 0);
  EXPECT_EQ(changed.files, 1U) << changed.error;
}
} // namespace
