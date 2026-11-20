#include "cpu_prefetch/calibration/mapped_pilot_capture.hpp"
#include "cpu_prefetch/calibration/native_pilot_capture.hpp"
#include "cpu_prefetch/runner/software_prefetch.hpp"
#include "cpu_prefetch/runner/stage17_s180_publication.hpp"
#include "cpu_prefetch/runner/stage17_s180_sources.hpp"
#include "cpu_prefetch/workload/working_set.hpp"
#include "discovery_backend_test_support.hpp"
#include "worker_stack_test_support.hpp"

#include <chrono>
#include <fcntl.h>
#include <gtest/gtest.h>
#include <linux/memfd.h>
#include <numeric>
#include <sys/syscall.h>
#include <unistd.h>

namespace {
using namespace cpu_prefetch;
namespace c = calibration;
struct Memory final {
  platform::LinuxOwnerMemoryOperations native;
  auto base_page_bytes() noexcept { return native.base_page_bytes(); }
  auto map_private(std::size_t size) noexcept { return native.map_private(size); }
  auto bind_pages(std::span<std::byte>, std::uint32_t) noexcept
      -> platform::LinuxCallResult {
    return {0, 0};
  }
  auto disable_huge_pages(std::span<std::byte> bytes) noexcept {
    return native.disable_huge_pages(bytes);
  }
  auto bind_current_thread(std::uint32_t) noexcept -> platform::LinuxCallResult {
    return {0, 0};
  }
  auto observe_current_thread(std::uint32_t cpu) noexcept {
    return platform::OwnerThreadObservation{
        {0, 0}, {cpu, 0}, {::gettid(), 0}, {0, 0}, 0, 0, 1, true};
  }
  auto lock_pages(std::span<std::byte> bytes) noexcept {
    static_cast<void>(bytes);
    return platform::LinuxCallResult{0, 0};
  }
  auto protect_read_only(std::span<std::byte> bytes) noexcept {
    return native.protect_read_only(bytes);
  }
  auto unlock_pages(std::span<std::byte> bytes) noexcept {
    static_cast<void>(bytes);
    return platform::LinuxCallResult{0, 0};
  }
  auto unmap(std::span<std::byte> bytes) noexcept { return native.unmap(bytes); }
};
struct Clock final {
  std::atomic<std::uint64_t> next{1U};
  auto origin() const noexcept -> timing::ClockOrigin { return {0U}; }
  auto read() noexcept -> timing::ClockReadResult {
    const auto tick = next.fetch_add(1U);
    return {timing::ClockReadStatus::ok, {tick, tick * 1000U}};
  }
};
struct Emitter final {
  std::atomic<std::uint64_t> producer{0U}, consumer{0U}, successor{0U};
  void ring_producer_write(const void*) noexcept { producer.fetch_add(1U); }
  void ring_consumer_read(const void*) noexcept { consumer.fetch_add(1U); }
  void successor_header(const void*) noexcept { successor.fetch_add(1U); }
};
struct Observer final {
  bool fail_measurement{false};
  auto before_phase(c::ServicePhase phase) const noexcept -> bool {
    return !fail_measurement || phase != c::ServicePhase::measurement;
  }
  auto during_phase(c::ServicePhase, c::ServiceWindow,
                    const std::atomic<std::uint32_t>&) const noexcept -> bool {
    return true;
  }
  auto after_phase(c::ServicePhase) const noexcept -> bool { return true; }
};
auto plan(protocol::QueuePackage package) -> c::MappedFormalServicePlan {
  c::MappedFormalServicePlan result{
      package,
      {{{{1'000'000U, 2048U, 4096U, 20'000'000U},
         {1'000'000U, 2048U, 4096U, 20'000'000U}}},
       5'000'000U},
      {512U, 64U, test::software_stack_plan().verified_base_page_bytes,
       workload::MasterSeed::from_hex(std::string(64U, '0')), "service-mapped-test"},
      {test_support::discovery_test_run_id("service-warmup"),
       test_support::discovery_test_run_id("service-measured")},
      {17U},
      {{{2048U, 2048U}, {2048U, 2048U}}},
      std::nullopt,
      std::nullopt};
  if (package == protocol::QueuePackage::l0 || package == protocol::QueuePackage::l1) {
    result.linked_order =
        c::FormalLinkedOrderPlan{workload::MasterSeed::from_hex(std::string(64U, '1')),
                                 "service-node-test", result.arena.base_page_bytes};
  } else if (package == protocol::QueuePackage::r1) {
    result.ring_distance = c::FormalRingDistancePlan{1U, ""};
  } else if (package == protocol::QueuePackage::r2) {
    result.ring_distance = c::FormalRingDistancePlan{2U, "software-only-prior-d2"};
  }
  return result;
}

struct Source final {
  std::array<std::uint64_t, 4U> warmup{1000U, 2000U, 2000U, 3000U};
  std::array<std::uint64_t, 4U> measured{101000U, 102000U, 102000U, 103000U};
  auto input(protocol::QueuePackage package) const -> c::MappedFormalScheduledPlan {
    auto service = plan(package);
    service.session.phases[0U].duration_ticks = 5'000'000'000'000U;
    return {std::move(service),
            {{{1000U, 5'000'000'001'000U, warmup.size(),
               protocol::ScheduleId::parse("warmup-schedule", "$test").value(),
               protocol::NamespaceId::parse("warmup-source", "$test").value()},
              {100000U, 1100000U, measured.size(),
               protocol::ScheduleId::parse("measured-schedule", "$test").value(),
               protocol::NamespaceId::parse("measured-source", "$test").value()}}},
            {warmup, measured}};
  }
};
auto data_plan(const c::MappedFormalServicePlan& service, std::uint32_t cpu)
    -> c::MappedPilotDataPlan {
  return {{protocol::Placement::near, protocol::WorkingSetClass::l2_resident},
          service.arena,
          {workload::MasterSeed::from_hex(std::string(64U, '1')), "service-node-test",
           service.arena.base_page_bytes},
          cpu,
          0U};
}
namespace r = runner::stage17;
using Value = protocol::json::Value;
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
class Sink final : public r::ArtifactSink {
public:
  std::vector<r::ArtifactPayload> artifacts;
  std::optional<std::size_t> fail_at;
  auto publish(r::ArtifactPayload a) -> protocol::Result<r::ArtifactBinding> override {
    if (fail_at == artifacts.size())
      return protocol::Result<r::ArtifactBinding>::failure(
          {protocol::ErrorCategory::cross_field, "$test", "SINK-FAIL",
           "injected sink failure"});
    r::ArtifactBinding b{a.role,         a.schema_identity,
                         a.media_type,   a.file_name,
                         a.bytes.size(), workload::sha256(a.bytes).hex()};
    artifacts.push_back(std::move(a));
    return protocol::Result<r::ArtifactBinding>::success(b);
  }
};
auto member(const Value& v, std::string_view key) -> const Value& {
  if (!v.as_object())
    throw std::logic_error("expected object");
  return v.as_object()->at(std::string(key));
}
auto document(const Sink& sink) -> Value {
  const auto& b = sink.artifacts.back().bytes;
  auto parsed = protocol::json::parse(
      std::string_view(reinterpret_cast<const char*>(b.data()), b.size()));
  if (!parsed)
    throw std::logic_error("invalid published JSON");
  return std::move(parsed).value();
}
auto shared_plan() -> c::MappedPilotDataPlan {
  auto p = data_plan(plan(protocol::QueuePackage::r0), 0U);
  p.arena.capacity = 4096U;
  return p;
}
struct Fixture final {
  Source values;
  c::MappedPilotData<Memory> data{shared_plan()};
  Memfd warmup{values.warmup}, measurement{values.measured};
  std::array<platform::HardwarePrefetchMsrValue, 3U> prestate{
      {{0U, 0U}, {1U, 0U}, {8U, 0U}}};
  std::array<r::S180SourceArtifact, 2U> artifacts{
      {{"warmup-original", workload::sha256(warmup.bytes).hex()},
       {"measured-original", workload::sha256(measurement.bytes).hex()}}};
  std::vector<r::FormalScheduleSourceBinding> bindings{
      {artifacts[0U].artifact_id, artifacts[0U].sha256, 32U, warmup.reader},
      {artifacts[1U].artifact_id, artifacts[1U].sha256, 32U, measurement.reader}};
  Fixture() {
    if (!data.prepare())
      throw std::runtime_error("synthetic shared preparation failed");
  }
  auto input() -> c::NativePilotCapturePlan {
    auto p = values.input(protocol::QueuePackage::r0);
    p.service.arena = shared_plan().arena;
    p.service.session.phases[1U].duration_ticks = 1'000'000'000'000U;
    p.phases[1U].source_horizon_ticks =
        p.phases[1U].source_origin_ticks + 1'000'000'000'000U;
    p.deadlines = {};
    const auto page = p.service.arena.base_page_bytes;
    constexpr auto stack = std::size_t{2U} * 1024U * 1024U;
    c::NativePilotCaptureControlPlan control{
        {{stack, page, 0U, 0U}, {stack, page, 1U, 0U}},
        {stack, page, 2U, 0U},
        32U,
        4096U,
        16384U,
        128U,
        {},
        {},
        {10U, 10U},
        1'000'000U,
        0U,
        {},
        {platform::kIntelFamily6, platform::kIntelModel3E},
        protocol::RequestedHardwareState::h0,
        prestate,
        {}};
    control.during_page_count.fill(1U);
    return {{std::move(p), data.view()},
            std::move(control),
            std::string(runner::kSoftwarePrefetchMappingIdT0Only)};
  }
  auto context(std::uint64_t max_bytes = 96U) -> r::FormalScheduleSourceContext {
    const auto now = std::chrono::duration_cast<std::chrono::nanoseconds>(
                         std::chrono::steady_clock::now().time_since_epoch())
                         .count();
    return {bindings, max_bytes, static_cast<std::uint64_t>(now) + 60'000'000'000U};
  }
  auto prepare() {
    return r::prepare_s180_capture_from_sources(input(), artifacts, context(), {});
  }
  auto metadata() const -> Value::Object {
    Value::Array sources;
    for (const auto& a : artifacts)
      sources.emplace_back(Value::Object{
          {"source_artifact", Value(Value::Object{{"artifact_id", Value(a.artifact_id)},
                                                  {"sha256", Value(a.sha256)}})}});
    return {{"method_id", Value(std::string(r::kS180MethodId))},
            {"schedules", Value(std::move(sources))}};
  }
};
TEST(S180Sources, ExactOriginalVectorsSurviveCopiesMovesAndBorrowedOffset) {
  Fixture f;
  ASSERT_EQ(::lseek(f.warmup.reader, 7, SEEK_SET), 7);
  auto prepared = f.prepare();
  ASSERT_TRUE(prepared) << (prepared ? "" : prepared.errors().front().message);
  auto copy = prepared.value();
  auto moved = std::move(copy);
  // The API explicitly guards moved-from access; exercise that rejection.
  // NOLINTNEXTLINE(bugprone-use-after-move)
  EXPECT_THROW(static_cast<void>(copy.plan()), std::logic_error);
  f.prestate.fill({99U, 999U});
  const auto p = moved.plan();
  EXPECT_TRUE(std::equal(p.capture.scheduled.deadlines[0U].begin(),
                         p.capture.scheduled.deadlines[0U].end(),
                         f.values.warmup.begin()));
  EXPECT_TRUE(std::equal(p.capture.scheduled.deadlines[1U].begin(),
                         p.capture.scheduled.deadlines[1U].end(),
                         f.values.measured.begin()));
  EXPECT_EQ(p.controls.hardware_prestate[0U].cpu, 0U);
  EXPECT_EQ(p.controls.hardware_prestate[0U].value, 0U);
  EXPECT_EQ(::lseek(f.warmup.reader, 0, SEEK_CUR), 7);
  EXPECT_GE(::fcntl(f.measurement.reader, F_GETFD), 0);
}
TEST(S180Sources, AggregateRetainedAndTransientMemoryIsMandatory) {
  Fixture f;
  for (const auto bytes : {0U, 63U, 64U, 95U})
    EXPECT_FALSE(r::prepare_s180_capture_from_sources(f.input(), f.artifacts,
                                                      f.context(bytes), {}));
  EXPECT_TRUE(f.prepare());
}
TEST(S180Sources, ReservedAndDuplicatedPhysicalDescriptorsReject) {
  Fixture f;
  const std::array reserved{f.warmup.writer};
  EXPECT_FALSE(r::prepare_s180_capture_from_sources(f.input(), f.artifacts, f.context(),
                                                    reserved));
  f.bindings[1U].descriptor = f.warmup.reader;
  EXPECT_FALSE(f.prepare());
  f.bindings[1U].descriptor = f.measurement.reader;
  f.bindings.push_back(f.bindings.front());
  EXPECT_FALSE(f.prepare());
}
TEST(S180Sources, HashSealsMembershipInlineWindowAndDeadlineDriftReject) {
  Fixture f;
  Memfd unsealed(f.values.warmup, false);
  for (unsigned failure = 0U; failure < 9U; ++failure) {
    auto p = f.input();
    auto artifacts = f.artifacts;
    auto context = f.context();
    auto bindings = f.bindings;
    context.bindings = bindings;
    switch (failure) {
    case 0U:
      artifacts[0U].sha256 = std::string(64U, '0');
      bindings[0U].canonical_sha256 = artifacts[0U].sha256;
      break;
    case 1U:
      bindings[0U].descriptor = unsealed.reader;
      break;
    case 2U:
      bindings[0U].descriptor = f.warmup.writer;
      break;
    case 3U:
      artifacts[0U].artifact_id = "absent";
      break;
    case 4U:
      p.capture.scheduled.deadlines[0U] = f.values.warmup;
      break;
    case 5U:
      p.capture.scheduled.service.session.phases[1U].duration_ticks = 2U;
      break;
    case 6U:
      context.deadline_monotonic_ns = 1U;
      break;
    case 7U:
      p.capture.scheduled.phases[0U].source_origin_ticks = 1001U;
      break;
    default:
      artifacts[1U].artifact_id = artifacts[0U].artifact_id;
      break;
    }
    EXPECT_FALSE(
        r::prepare_s180_capture_from_sources(std::move(p), artifacts, context, {}))
        << failure;
  }
}
void capture_and_publish(bool failed_measurement) {
  Fixture f;
  auto prepared = f.prepare();
  ASSERT_TRUE(prepared) << (prepared ? "" : prepared.errors().front().message);
  const auto native = prepared.value().plan();
  using Modules = std::array<platform::ThreadTlsModule, 128U>;
  std::array<Modules, 4U> tls{};
  alignas(64) std::array<std::byte, 128U> termination{};
  Clock clock;
  test_support::DiscoveryTestRelax relax;
  using Runtime = c::MappedServiceRuntime<
      Clock, test_support::DiscoveryTestRelax,
      c::PilotRuntimePolicy<protocol::QueuePackage::r0, Emitter>, Memory,
      test::SoftwareStackOperations>;
  auto owner = test::software_stack_plan();
  owner.owner_cpu = 0U;
  Runtime runtime{native.capture,
                  {owner, owner},
                  {{{tls[0U], tls[1U]}}, {{tls[2U], tls[3U]}}},
                  {std::span(termination).first(64U), std::span(termination).last(64U)},
                  clock,
                  relax};
  Observer observer{failed_measurement};
  const auto session = runtime.run(observer);
  ASSERT_EQ(session.session.lifecycle.stop,
            failed_measurement ? c::ServiceSessionStop::observation_failure
                               : c::ServiceSessionStop::complete);
  // Retain the actual software lifecycle while native hardware observations
  // stay unobserved. This test never invokes the native envelope or MSRs.
  c::NativePilotCaptureResult result{};
  result.session = session;
  const auto layout = c::native_pilot_layout(native);
  platform::PrefetchReadbackPreparation hardware{};
  std::array<c::DiscoveryResidencyRegion, 9U> regions{};
  const auto workers = runtime.worker_regions();
  std::copy(workers.begin(), workers.end(), regions.begin());
  regions[7U] = f.data.view().regions[0U];
  regions[8U] = f.data.view().regions[1U];
  c::NativePilotPublicationView view{
      result, layout, {regions, {}, {}, {}, {}, hardware, {}, {}, {}}, f.data.view()};
  for (std::size_t i = 0U; i < 2U; ++i) {
    view.producer[i] = &runtime.preparation().producer_phase(i == 0U);
    view.consumer[i] = &runtime.preparation().consumer_phase(i == 0U);
    view.schedules[i] = runtime.preparation().schedule(
        i == 0U ? c::ServicePhase::warmup : c::ServicePhase::measurement);
  }
  Sink sink;
  const auto published = r::publish_s180_capture(sink, 0U, f.metadata(), view);
  ASSERT_TRUE(published);
  ASSERT_EQ(sink.artifacts.size(), 8U);
  for (std::size_t i = 0U; i < 2U; ++i) {
    const auto p = view.producer[i]->primary.snapshot(),
               craw = view.consumer[i]->primary.snapshot();
    EXPECT_EQ(sink.artifacts[i * 2U].bytes,
              (std::vector<std::byte>(p.bytes.begin(), p.bytes.end())));
    EXPECT_EQ(sink.artifacts[i * 2U + 1U].bytes,
              (std::vector<std::byte>(craw.bytes.begin(), craw.bytes.end())));
    EXPECT_EQ(p.row_count, failed_measurement && i == 1U ? 0U : 4U);
    EXPECT_EQ(sink.artifacts[i * 2U].role, "S180_PRIMARY_RAW");
  }
  // Independent BE-to-LE transformation of the original artifact, no production codec.
  for (std::size_t phase = 0U; phase < 2U; ++phase) {
    auto expected = phase == 0U ? f.warmup.bytes : f.measurement.bytes;
    for (std::size_t pos = 0U; pos < expected.size(); pos += 8U)
      std::reverse(expected.begin() + static_cast<std::ptrdiff_t>(pos),
                   expected.begin() + static_cast<std::ptrdiff_t>(pos + 8U));
    EXPECT_EQ(sink.artifacts[5U + phase].bytes, expected);
  }
  const auto doc = document(sink);
  EXPECT_EQ(*member(doc, "schema_version").as_string(), r::kS180ControlSchema);
  EXPECT_EQ(*member(doc, "method_id").as_string(), r::kS180MethodId);
  EXPECT_EQ(member(member(doc, "layout"), "region_bytes").as_array()->size(), 9U);
  EXPECT_EQ(member(doc, "regions").as_array()->size(), 9U);
  EXPECT_TRUE(member(doc, "residency").as_array()->empty());
  EXPECT_FALSE(
      *member(member(doc, "shared_data"), "final_family_cleanup_observed").as_bool());
  EXPECT_FALSE(*member(doc, "execution_authority").as_bool());
  EXPECT_FALSE(*member(doc, "inferential_validity_established").as_bool());
  EXPECT_FALSE(*member(doc, "phase18_authority").as_bool());
  for (std::size_t i = 0U; i < published.value().size(); ++i)
    EXPECT_EQ(published.value()[i].sha256,
              workload::sha256(sink.artifacts[i].bytes).hex());
  Sink failed;
  failed.fail_at = 2U;
  EXPECT_FALSE(r::publish_s180_capture(failed, 0U, f.metadata(), view));
  EXPECT_EQ(failed.artifacts.size(), 2U);
  EXPECT_FALSE(r::publish_s180_capture(failed, 180U, f.metadata(), view));
  EXPECT_TRUE(runtime.close());
  EXPECT_FALSE(f.data.records_evidence().cleanup_attempted);
}
TEST(S180Publication, OriginalSealedSourcesFlowThroughMappedCaptureAndPublication) {
  capture_and_publish(false);
}
TEST(S180Publication, CompletedWarmupSurvivesMeasurementFailureAndSinkFailureStops) {
  capture_and_publish(true);
}
TEST(S180Publication, UnobservedPreparationIsNeverInvented) {
  Fixture f;
  Sink sink;
  c::NativePilotCaptureResult result{};
  c::NativePilotCaptureLayout layout{};
  platform::PrefetchReadbackPreparation hardware{};
  c::NativePilotPublicationView view{
      result, layout, {{}, {}, {}, {}, {}, hardware, {}, {}, {}}, {}};
  ASSERT_TRUE(r::publish_s180_capture(sink, 0U, f.metadata(), view));
  const auto doc = document(sink);
  EXPECT_FALSE(*member(member(doc, "shared_data"), "available").as_bool());
  EXPECT_TRUE(member(doc, "arena").is_null());
  EXPECT_TRUE(member(member(doc, "shared_data"), "node_pattern").is_null());
  EXPECT_TRUE(member(member(doc, "native_result_before_publication_returns"), "session")
                  .is_null());
  EXPECT_TRUE(sink.artifacts[0U].bytes.empty());
  EXPECT_TRUE(sink.artifacts[5U].bytes.empty());
  EXPECT_TRUE(sink.artifacts[6U].bytes.empty());
}
} // namespace
