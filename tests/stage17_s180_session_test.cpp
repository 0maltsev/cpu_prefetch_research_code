#include "cpu_prefetch/runner/software_prefetch.hpp"
#include "cpu_prefetch/runner/stage17_s180_session.hpp"
#include <fcntl.h>
#include <fstream>
#include <gtest/gtest.h>
#include <linux/memfd.h>
#include <numeric>
#include <sys/syscall.h>
#include <unistd.h>
namespace {
using namespace cpu_prefetch;
namespace r = runner::stage17;
namespace c = calibration;
using V = protocol::json::Value;
using O = V::Object;
auto at(const O& o, std::string_view key) -> const V& { return o.at(std::string(key)); }
auto text(const O& o, std::string_view key) -> std::string {
  return *at(o, key).as_string();
}
auto number(const O& o, std::string_view key) -> std::uint64_t {
  const auto* n = at(o, key).as_number();
  if (!n)
    throw std::logic_error("not number");
  return std::get<std::uint64_t>(n->value);
}
template <typename T> auto id(std::string s) -> T {
  auto parsed = T::parse(std::move(s), "$test");
  if (!parsed)
    throw std::logic_error("test id");
  return parsed.value();
}
class Memfd final {
public:
  std::vector<std::byte> bytes;
  int writer{-1}, reader{-1};
  explicit Memfd(std::span<const std::uint64_t> words, bool seal = true) {
    for (const auto word : words)
      for (unsigned shift = 64U; shift != 0U; shift -= 8U)
        bytes.push_back(static_cast<std::byte>((word >> (shift - 8U)) & 255U));
    writer = static_cast<int>(::syscall(SYS_memfd_create, "s180-source-test",
                                        MFD_CLOEXEC | MFD_ALLOW_SEALING));
    if (writer < 0 || ::write(writer, bytes.data(), bytes.size()) !=
                          static_cast<ssize_t>(bytes.size()))
      throw std::runtime_error("test memfd write failed");
    if (seal && ::fcntl(writer, F_ADD_SEALS,
                        F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL) != 0)
      throw std::runtime_error("test memfd seal failed");
    reader = ::open(("/proc/self/fd/" + std::to_string(writer)).c_str(),
                    O_RDONLY | O_CLOEXEC);
    if (reader < 0)
      throw std::runtime_error("test memfd read-only reopen failed");
  }
  ~Memfd() {
    static_cast<void>(::close(reader));
    static_cast<void>(::close(writer));
  }
  Memfd(const Memfd&) = delete;
  auto operator=(const Memfd&) -> Memfd& = delete;
};

struct Fixture final {
  std::array<platform::HardwarePrefetchMsrValue, 3U> prestate{
      {{0U, 0U}, {1U, 0U}, {8U, 0U}}};
  std::vector<std::unique_ptr<Memfd>> files;
  std::vector<r::FormalScheduleSourceBinding> bindings;
  r::S180SessionInput input{};
  r::S180SessionAuthority authority{"synthetic-s180-session", std::string(64U, 'a'),
                                    std::string(64U, 'b'), 100U,
                                    100U + r::kS180OperationalCapNs};
  Fixture() {
    std::ifstream f(std::string(CPU_PREFETCH_SOURCE_DIR) +
                    "/config/stage17/d310-s180-blueprint-v1.json");
    const std::string raw((std::istreambuf_iterator<char>(f)), {});
    auto parsed = protocol::json::parse(raw);
    if (!parsed || !parsed.value().as_object())
      throw std::logic_error("frozen blueprint unavailable");
    input.blueprint = *parsed.value().as_object();
    input.source_revision = std::string(40U, 'a');
    const auto master =
        workload::MasterSeed::from_hex(text(input.blueprint, "master_seed_hex"));
    const auto& rows = *at(input.blueprint, "captures").as_array();
    std::array<const O*, 180U> order{};
    for (const auto& v : rows)
      order[number(*v.as_object(), "execution_ordinal")] = v.as_object();
    const std::array<std::uint64_t, 4U> words{1U, 2U, 2U, 3U};
    for (std::size_t group = 0U; group < 18U; ++group)
      for (std::size_t phase = 0U; phase < 2U; ++phase) {
        auto file = std::make_unique<Memfd>(words);
        const auto name =
            "source-" + std::to_string(group) + "-" + std::to_string(phase);
        const auto sha = workload::sha256(file->bytes).hex();
        input.source_artifacts[group][phase] = {name, sha};
        bindings.push_back({name, sha, 32U, file->reader});
        files.push_back(std::move(file));
      }
    for (std::size_t ctx = 0U; ctx < 6U; ++ctx) {
      const auto& row = *rows[ctx < 3U ? ctx * 3U : 9U + (ctx - 3U) * 3U].as_object();
      const auto& g = *at(row, "requested_geometry").as_object();
      input.contexts.push_back(
          {{ctx < 3U ? protocol::Placement::near : protocol::Placement::far,
            static_cast<protocol::WorkingSetClass>(ctx % 3U)},
           {static_cast<std::size_t>(number(g, "capacity")),
            static_cast<std::size_t>(number(g, "cache_line_bytes")),
            static_cast<std::size_t>(number(g, "base_page_bytes")), master,
            text(row, "arena_namespace")},
           {master, text(row, "node_order_namespace"),
            static_cast<std::size_t>(number(g, "base_page_bytes"))},
           static_cast<std::uint32_t>(number(g, "producer_cpu")),
           static_cast<std::uint32_t>(number(g, "shared_node"))});
    }
    for (std::size_t i = 0U; i < 180U; ++i) {
      const auto& row = *order[i];
      const auto ctx = (text(row, "placement") == "NEAR" ? 0U : 3U) +
                       (text(row, "working_set_class") == "L2_RESIDENT"    ? 0U
                        : text(row, "working_set_class") == "LLC_RESIDENT" ? 1U
                                                                           : 2U);
      const auto load = text(row, "load_level") == "L025"   ? 0U
                        : text(row, "load_level") == "L050" ? 1U
                                                            : 2U;
      const auto& data = input.contexts[ctx];
      const auto page = data.arena.base_page_bytes;
      const auto pkg =
          protocol::parse_queue_package(text(row, "package"), "$test").value();
      c::MappedFormalServicePlan service{
          pkg,
          {{{{5'000'000'000'000U, 4U, 2048U, 20'000'000U},
             {1'000'000'000'000U, 4U, 2048U, 20'000'000U}}},
           5'000'000U},
          data.arena,
          {id<protocol::RunId>(text(row, "warmup_run_id")),
           id<protocol::RunId>(text(row, "run_id"))},
          {17U},
          {{{4U, 4U}, {4U, 4U}}},
          std::nullopt,
          std::nullopt};
      if (pkg == protocol::QueuePackage::l0 || pkg == protocol::QueuePackage::l1)
        service.linked_order = data.node_order;
      if (pkg == protocol::QueuePackage::r1 || pkg == protocol::QueuePackage::r2)
        service.ring_distance = c::FormalRingDistancePlan{
            pkg == protocol::QueuePackage::r1
                ? 1U
                : static_cast<std::size_t>(
                      number(*at(row, "distance").as_object(), "d2_cache_lines")),
            "accepted-descriptive-calibration"};
      const auto group = ctx * 3U + load;
      c::MappedFormalScheduledPlan scheduled{
          std::move(service),
          {{{0U, 5'000'000'000'000U, 4U,
             id<protocol::ScheduleId>("schedule-" + std::to_string(group) + "-0"),
             id<protocol::NamespaceId>(text(row, "warmup_schedule_namespace"))},
            {0U, 1'000'000'000'000U, 4U,
             id<protocol::ScheduleId>("schedule-" + std::to_string(group) + "-1"),
             id<protocol::NamespaceId>(text(row, "measurement_schedule_namespace"))}}},
          {}};
      const auto& g = *at(row, "requested_geometry").as_object();
      c::NativePilotCaptureControlPlan controls{
          {{8192U, page, static_cast<std::uint32_t>(number(g, "producer_cpu")),
            static_cast<std::uint32_t>(number(g, "producer_node"))},
           {8192U, page, static_cast<std::uint32_t>(number(g, "consumer_cpu")),
            static_cast<std::uint32_t>(number(g, "consumer_node"))}},
          {8192U, page, 2U, 0U},
          32U,
          4096U,
          16384U,
          128U,
          {},
          {},
          {1U, 1U},
          1'000'000U,
          0U,
          {},
          {platform::kIntelFamily6, platform::kIntelModel3E},
          text(row, "requested_hardware_state") == "H0"
              ? protocol::RequestedHardwareState::h0
              : protocol::RequestedHardwareState::h1,
          prestate,
          {}};
      controls.during_page_count.fill(1U);
      const auto shared = c::mapped_pilot_data_layout(data);
      c::NativePilotCaptureLayout layout{};
      layout.workers.records_bytes = page;
      layout.workers.producer_bytes = page;
      layout.workers.consumer_bytes = page;
      layout.core_bytes = page;
      layout.monitor_bytes = page;
      layout.region_bytes = {page,
                             page,
                             page,
                             8192U,
                             8192U,
                             page,
                             8192U,
                             shared.records_bytes,
                             shared.queues_bytes};
      layout.total_mapping_bytes =
          std::accumulate(layout.region_bytes.begin(), layout.region_bytes.end(),
                          std::size_t{0U}) +
          4U * page;
      input.captures.push_back({{{std::move(scheduled), {}},
                                 std::move(controls),
                                 std::string(runner::kSoftwarePrefetchMappingIdT0Only)},
                                layout,
                                7'000'000'000U,
                                100'000'000U,
                                std::uint64_t{1024U} * 1024U,
                                65536U});
    }
    input.sources = {bindings, 1184U, 1'000'001'000U};
    input.setup_ns = 1'000'000'000U;
    input.whole_plot_transition_ns = 1'000'000'000U;
    input.whole_plot_recovery_ns = 1'000'000'000U;
    input.final_metadata_bytes = 1'048'576U;
    input.finalization_ns = 1'000'000'000U;
    input.memory_bytes = std::uint64_t{2U} * 1024U * 1024U * 1024U;
    input.max_output_bytes = std::uint64_t{1U} * 1024U * 1024U * 1024U;
  }
};
struct Operations final : r::S180SessionOperations {
  std::uint64_t now{1000U};
  std::vector<std::string> events;
  std::string failure;
  std::size_t fail_at{3U}, restores{0U};
  auto now_monotonic_ns() const noexcept -> std::optional<std::uint64_t> override {
    return now;
  }
  auto prepare(const r::S180SessionShape& shape) -> bool override {
    events.push_back("prepare");
    EXPECT_EQ(shape.cells[0U], 137U);
    return failure != "prepare";
  }
  auto mark_attempt(std::size_t i) -> bool override {
    events.push_back("marker-" + std::to_string(i));
    if (failure == "expire-marker")
      now = r::kS180OperationalCapNs + 100U;
    if (failure == "regress-marker")
      now = 999U;
    return failure != "marker" || i != fail_at;
  }
  auto enter(protocol::RequestedHardwareState s) -> bool override {
    events.push_back(s == protocol::RequestedHardwareState::h1 ? "enter-H1"
                                                               : "enter-H0");
    return failure != "enter";
  }
  auto capture(std::size_t i) -> bool override {
    events.push_back("capture-" + std::to_string(i));
    if (failure == "throw-capture" && i == fail_at)
      throw std::runtime_error("injected capture exception");
    return failure != "capture" || i != fail_at;
  }
  auto archive(std::size_t i, bool native) -> bool override {
    events.push_back("archive-" + std::to_string(i) +
                     (native ? "-complete" : "-failed"));
    return failure != "archive" || i != fail_at;
  }
  auto restore() noexcept -> bool override {
    ++restores;
    events.push_back("restore");
    return failure != "restore";
  }
  auto recover(std::uint64_t ns) -> bool override {
    EXPECT_EQ(ns, 1'000'000'000U);
    events.push_back("recovery");
    return failure != "recovery";
  }
  auto release_contexts() noexcept -> bool override {
    events.push_back("cleanup");
    return failure != "cleanup";
  }
  auto finish(const r::S180SessionResult&) -> bool override {
    events.push_back("finish");
    return failure != "finish";
  }
};
TEST(S180Session, FrozenFullMatrixCommonSourcesAndResourceEnvelopeValidate) {
  Fixture f;
  const auto v = r::validate_s180_session(f.input);
  ASSERT_TRUE(v) << (v ? "" : v.errors().front().message);
  EXPECT_EQ(v.value().cells.front(), 137U);
  EXPECT_EQ(v.value().retained_vector_bytes, 1152U);
  EXPECT_GT(v.value().shared_mapping_bytes, 0U);
}
TEST(S180Session, ScientificOrderIdentitySharingAndFiniteResourceDriftRejectCold) {
  Fixture f;
  for (unsigned bad = 0U; bad < 13U; ++bad) {
    auto input = f.input;
    switch (bad) {
    case 0U:
      std::swap(input.captures[0U], input.captures[1U]);
      break;
    case 1U:
      input.captures.pop_back();
      break;
    case 2U:
      input.contexts[0U].arena.seed_namespace += "drift";
      break;
    case 3U:
      input.captures[1U].native.capture.scheduled.phases[0U].offered_count = 3U;
      break;
    case 4U:
      input.captures[0U].native.capture.scheduled.service.run_ids[1U] =
          id<protocol::RunId>("foreign-run");
      break;
    case 5U:
      input.source_artifacts[0U][0U] = input.source_artifacts[0U][1U];
      break;
    case 6U:
      input.sources.maximum_vector_bytes = 1183U;
      break;
    case 7U:
      input.memory_bytes = 1U;
      break;
    case 8U:
      input.max_output_bytes = 1U;
      break;
    case 9U:
      input.final_metadata_bytes = 1'048'576U;
      input.finalization_ns = r::kS180OperationalCapNs;
      break;
    case 10U:
      input.captures[0U].watchdog_ns = 1U;
      break;
    case 11U:
      input.captures[0U].expected_layout.region_bytes[8U] = 4096U;
      break;
    default:
      input.blueprint.erase("blockers");
      break;
    }
    Operations ops;
    const auto result = r::run_s180_session(input, f.authority, ops);
    EXPECT_FALSE(result) << bad;
    EXPECT_TRUE(ops.events.empty()) << bad;
  }
}
TEST(S180Session, RunsExactlyOnceInFrozenWholePlotsAndReleasesOnlyAtFamilyEnd) {
  Fixture f;
  Operations ops;
  const auto result = r::run_s180_session(f.input, f.authority, ops);
  ASSERT_TRUE(result);
  EXPECT_EQ(result.value().stop, r::S180SessionStop::complete);
  EXPECT_EQ(result.value().attempted, 180U);
  EXPECT_EQ(result.value().completed, 180U);
  EXPECT_EQ(ops.restores, 2U);
  EXPECT_TRUE(result.value().restoration_verified);
  EXPECT_TRUE(result.value().cleanup_verified);
  EXPECT_TRUE(result.value().final_publication_succeeded);
  EXPECT_EQ(ops.events.front(), "prepare");
  EXPECT_EQ(ops.events.back(), "finish");
  EXPECT_EQ(std::count(ops.events.begin(), ops.events.end(), "enter-H1"), 1);
  EXPECT_EQ(std::count(ops.events.begin(), ops.events.end(), "enter-H0"), 1);
  const auto restore = std::find(ops.events.begin(), ops.events.end(), "restore");
  ASSERT_NE(restore, ops.events.end());
  EXPECT_EQ(*(restore - 1), "archive-89-complete");
  EXPECT_EQ(*(restore + 1), "recovery");
  EXPECT_EQ(*(restore + 2), "marker-90");
}
TEST(S180Session, FirstCaptureOrArchiveFailureStopsAndPreservesFailedEvidence) {
  Fixture f;
  for (const auto* reason : {"capture", "throw-capture", "archive"}) {
    Operations ops;
    ops.failure = reason;
    auto result = r::run_s180_session(f.input, f.authority, ops);
    ASSERT_TRUE(result);
    EXPECT_EQ(result.value().attempted, 4U);
    EXPECT_EQ(result.value().completed, 3U);
    EXPECT_EQ(result.value().stop,
              ops.failure == "archive"         ? r::S180SessionStop::archive_failed
              : ops.failure == "throw-capture" ? r::S180SessionStop::exception
                                               : r::S180SessionStop::capture_failed);
    EXPECT_EQ(ops.restores, 1U);
    EXPECT_TRUE(result.value().cleanup_verified);
    EXPECT_EQ(std::count(ops.events.begin(), ops.events.end(), "capture-3"), 1);
    EXPECT_EQ(std::count(ops.events.begin(), ops.events.end(), "capture-4"), 0);
    EXPECT_NE(
        std::find(ops.events.begin(), ops.events.end(),
                  ops.failure == "archive" ? "archive-3-complete" : "archive-3-failed"),
        ops.events.end());
  }
}
TEST(S180Session, PreparationMarkerEnterAndRecoveryFailuresCannotAdvance) {
  Fixture f;
  for (const auto* reason : {"prepare", "marker", "enter", "recovery", "restore"}) {
    Operations ops;
    ops.failure = reason;
    const auto result = r::run_s180_session(f.input, f.authority, ops);
    ASSERT_TRUE(result);
    EXPECT_NE(result.value().stop, r::S180SessionStop::complete);
    EXPECT_TRUE(result.value().cleanup_attempted);
    EXPECT_EQ(std::count(ops.events.begin(), ops.events.end(), "cleanup"), 1);
    if (ops.failure == "restore" || ops.failure == "recovery") {
      EXPECT_EQ(result.value().completed, 90U);
      EXPECT_EQ(ops.restores, 1U);
      EXPECT_EQ(std::count(ops.events.begin(), ops.events.end(), "enter-H0"), 0);
    }
  }
}
TEST(S180Session, ExpiredOrResetWindowAndExpiryDuringMarkerBlockCapture) {
  Fixture f;
  for (unsigned bad = 0U; bad < 3U; ++bad) {
    Operations ops;
    auto auth = f.authority;
    if (bad == 0U)
      ops.now = auth.window_end_monotonic_ns;
    if (bad == 1U)
      ++auth.window_end_monotonic_ns;
    if (bad == 2U)
      ops.now = auth.window_end_monotonic_ns - 1U;
    auto result = r::run_s180_session(f.input, auth, ops);
    ASSERT_TRUE(result);
    EXPECT_EQ(result.value().stop, r::S180SessionStop::authority_failed);
    EXPECT_TRUE(ops.events.empty());
  }
  Operations expired;
  expired.failure = "expire-marker";
  const auto result = r::run_s180_session(f.input, f.authority, expired);
  ASSERT_TRUE(result);
  EXPECT_EQ(result.value().stop, r::S180SessionStop::authority_failed);
  EXPECT_EQ(result.value().attempted, 1U);
  EXPECT_EQ(result.value().completed, 0U);
  EXPECT_EQ(expired.restores, 0U);
}
TEST(S180Session, CleanupAndFinalPublicationFailureNeverBecomeComplete) {
  Fixture f;
  for (const auto* reason : {"cleanup", "finish"}) {
    Operations ops;
    ops.failure = reason;
    const auto result = r::run_s180_session(f.input, f.authority, ops);
    ASSERT_TRUE(result);
    EXPECT_EQ(result.value().stop, ops.failure == "cleanup"
                                       ? r::S180SessionStop::cleanup_failed
                                       : r::S180SessionStop::final_publication_failed);
    EXPECT_EQ(result.value().completed, 180U);
  }
}
TEST(S180Session, RegressedClockAndSourceDeadlineCannotReachHardware) {
  Fixture f;
  Operations ops;
  ops.failure = "regress-marker";
  const auto result = r::run_s180_session(f.input, f.authority, ops);
  ASSERT_TRUE(result);
  EXPECT_EQ(result.value().stop, r::S180SessionStop::authority_failed);
  EXPECT_EQ(ops.restores, 0U);
  EXPECT_EQ(result.value().completed, 0U);
  for (const auto deadline :
       {std::uint64_t{1U}, f.input.sources.deadline_monotonic_ns + 1U}) {
    auto input = f.input;
    input.sources.deadline_monotonic_ns = deadline;
    Operations clean;
    const auto rejected = r::run_s180_session(input, f.authority, clean);
    ASSERT_TRUE(rejected);
    EXPECT_EQ(rejected.value().stop, r::S180SessionStop::authority_failed);
    EXPECT_TRUE(clean.events.empty());
  }
}
TEST(S180Session, PhysicalSourceAliasesAndReservedIdentityRejectWholeFamilyCold) {
  Fixture f;
  Operations ops;
  const std::array reserved{f.files.front()->writer};
  f.input.reserved_descriptors = reserved;
  EXPECT_FALSE(r::run_s180_session(f.input, f.authority, ops));
  EXPECT_TRUE(ops.events.empty());
  f.input.reserved_descriptors = {};
  f.bindings[2U].descriptor = f.bindings[0U].descriptor;
  EXPECT_FALSE(r::run_s180_session(f.input, f.authority, ops));
  EXPECT_TRUE(ops.events.empty());
}
class RejectedSink final : public r::S180ArchiveSink {
public:
  std::size_t calls{0U};
  auto s180_program_scope_sha256() const noexcept -> std::string_view override {
    return "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
  }
  auto publish(r::ArtifactPayload) -> protocol::Result<r::ArtifactBinding> override {
    ++calls;
    return protocol::Result<r::ArtifactBinding>::failure(
        {protocol::ErrorCategory::cross_field, "$test", "UNEXPECTED",
         "unexpected publication"});
  }
};
TEST(S180Session, NativeEntryRejectsUnqualifiedSourceAndBrokerBeforePreparingData) {
  Fixture f;
  RejectedSink sink;
  f.input.source_revision = "THIS_IS_NOT_A_RELEASE";
  EXPECT_FALSE(r::run_native_s180_session(f.input, f.authority, sink));
  EXPECT_EQ(sink.calls, 0U);
}

TEST(S180Session, CompleteBudgetIncludesTransitionAndFinalReportReservation) {
  Fixture f;
  auto valid = r::validate_s180_session(f.input);
  ASSERT_TRUE(valid);
  EXPECT_EQ(valid.value().watchdog_ns, 1'264'000'000'000U);
  auto input = f.input;
  input.final_metadata_bytes = 0U;
  EXPECT_FALSE(r::validate_s180_session(input));
  input = f.input;
  input.whole_plot_transition_ns = 0U;
  EXPECT_FALSE(r::validate_s180_session(input));
  input = f.input;
  input.max_output_bytes = std::uint64_t{180U} * 1024U * 1024U;
  EXPECT_FALSE(r::validate_s180_session(input));
  input.max_output_bytes += input.final_metadata_bytes;
  EXPECT_TRUE(r::validate_s180_session(input));
}

} // namespace
