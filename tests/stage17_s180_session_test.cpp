#include "s180_session_test_support.hpp"
namespace {
using namespace cpu_prefetch::test::s180;
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
