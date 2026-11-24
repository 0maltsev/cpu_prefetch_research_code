#include "cpu_prefetch/calibration/native_discovery_capture.hpp"
#include "discovery_backend_test_support.hpp"

#include <gtest/gtest.h>

#include <array>
#include <cerrno>
#include <limits>
#include <numeric>

namespace {
using namespace cpu_prefetch;

constexpr std::array<platform::HardwarePrefetchMsrValue, 3U> kPrestate{
    {{0U, 0x1230U}, {1U, 0x4562U}, {8U, 0x7894U}}};

auto plan() -> calibration::NativeDiscoveryCapturePlan {
  // Explicit software-only geometry. None of these values is a stand claim.
  calibration::NativeDiscoveryCapturePlan result{
      {{5000000U, 3000000U, 256U, 256U, 1000000U, 9U, 1000000U},
       {8U, 64U, 4096U, workload::MasterSeed::from_hex(std::string(64U, '0')),
        "native-composition-layout-test"},
       {test_support::discovery_test_run_id("native-warmup"),
        test_support::discovery_test_run_id("native-measurement")},
       {17U}},
      {{std::size_t{2U} * 1024U * 1024U, 4096U, 0U, 0U},
       {std::size_t{2U} * 1024U * 1024U, 4096U, 1U, 0U}},
      {std::size_t{2U} * 1024U * 1024U, 4096U, 2U, 0U},
      32U,
      4096U,
      16384U,
      128U,
      {},
      {},
      {100000U, 100000U},
      1000000U,
      0U,
      {},
      {platform::kIntelFamily6, platform::kIntelModel3E},
      protocol::RequestedHardwareState::h0,
      kPrestate};
  result.during_page_count.fill(1U);
  return result;
}

TEST(NativeDiscovery, LayoutAccountsForEveryMappingAndAllThreeGuards) {
  const auto input = plan();
  const auto layout = calibration::native_discovery_layout(input);
  const auto worker = calibration::mapped_discovery_layout(input.discovery);
  EXPECT_EQ(layout.region_bytes[0U], worker.records_bytes);
  EXPECT_EQ(layout.region_bytes[1U], worker.producer_bytes);
  EXPECT_EQ(layout.region_bytes[2U], worker.consumer_bytes);
  EXPECT_EQ(layout.region_bytes[3U], input.workers.producer_stack.bytes);
  EXPECT_EQ(layout.region_bytes[4U], input.workers.consumer_stack.bytes);
  EXPECT_EQ(layout.region_bytes[5U], layout.core_bytes);
  EXPECT_EQ(layout.region_bytes[6U], input.controller_stack.bytes);
  const auto page = input.discovery.arena.base_page_bytes;
  for (const auto bytes : layout.region_bytes) {
    EXPECT_GT(bytes, 0U);
    EXPECT_EQ(bytes % page, 0U);
  }
  EXPECT_GT(layout.monitor_bytes, 0U);
  EXPECT_EQ(layout.monitor_bytes % page, 0U);
  EXPECT_EQ(layout.total_mapping_bytes,
            std::accumulate(layout.region_bytes.begin(), layout.region_bytes.end(),
                            std::size_t{0U}) +
                layout.monitor_bytes + 3U * page);
  EXPECT_EQ(calibration::native_discovery_layout(input).total_mapping_bytes,
            layout.total_mapping_bytes);
}

TEST(NativeDiscovery, AdditionalCallerBudgetsIncreaseDeclaredStorage) {
  auto input = plan();
  const auto original = calibration::native_discovery_layout(input);
  input.tls_module_capacity *= 8U;
  const auto tls = calibration::native_discovery_layout(input);
  EXPECT_GT(tls.core_bytes, original.core_bytes);
  input.thread_status_bytes *= 2U;
  const auto scratch = calibration::native_discovery_layout(input);
  EXPECT_GT(scratch.monitor_bytes, tls.monitor_bytes);
  input.during_page_count[3U] = 512U;
  EXPECT_GT(calibration::native_discovery_layout(input).monitor_bytes,
            scratch.monitor_bytes);
}

TEST(NativeDiscovery, RejectsInvalidFinitePlansBeforeMapping) {
  for (unsigned failure = 0U; failure < 13U; ++failure) {
    auto input = plan();
    switch (failure) {
    case 0U:
      input.tls_module_capacity = 0U;
      break;
    case 1U:
      input.thread_stat_bytes = 0U;
      break;
    case 2U:
      input.thread_status_bytes = 0U;
      break;
    case 3U:
      input.thread_affinity_words = 0U;
      break;
    case 4U:
      input.observer_wait_poll_limit = 0U;
      break;
    case 5U:
      input.controller_stack.owner_cpu = input.workers.producer_stack.owner_cpu;
      break;
    case 6U:
      input.workers.consumer_stack.owner_cpu = input.workers.producer_stack.owner_cpu;
      break;
    case 7U:
      input.controller_stack.verified_base_page_bytes = 8192U;
      break;
    case 8U:
      input.controller_stack.bytes += 1U;
      break;
    case 9U:
      input.discovery.session.drain_duration_ticks = 0U;
      break;
    case 10U:
      input.hardware_state = protocol::RequestedHardwareState::not_applicable;
      break;
    case 11U:
      input.control_region_index = calibration::kNativeDiscoveryRegions;
      break;
    case 12U:
      input.workers.consumer_stack.owner_cpu = 26U;
      break;
    default:
      FAIL();
      return;
    }
    EXPECT_THROW(static_cast<void>(calibration::native_discovery_layout(input)),
                 std::invalid_argument);
  }
}

TEST(NativeDiscovery, RejectsDuringOffsetsAndRangesOutsideTheirExactRegions) {
  auto input = plan();
  input.during_offset_ticks[0U] = input.discovery.session.warmup_duration_ticks;
  EXPECT_THROW(static_cast<void>(calibration::native_discovery_layout(input)),
               std::invalid_argument);
  input = plan();
  input.during_first_page[0U] = std::numeric_limits<std::size_t>::max();
  EXPECT_THROW(static_cast<void>(calibration::native_discovery_layout(input)),
               std::invalid_argument);
  input = plan();
  input.during_page_count[0U] = 0U;
  EXPECT_THROW(static_cast<void>(calibration::native_discovery_layout(input)),
               std::invalid_argument);
  input = plan();
  input.during_page_count[6U] = input.controller_stack.bytes / 4096U + 1U;
  EXPECT_THROW(static_cast<void>(calibration::native_discovery_layout(input)),
               std::invalid_argument);
}

TEST(NativeDiscovery, RejectsOverflowAndUnacceptedHardwareWithoutNativeAccess) {
  for (unsigned failure = 0U; failure < 5U; ++failure) {
    auto input = plan();
    switch (failure) {
    case 0U:
      input.tls_module_capacity = std::numeric_limits<std::size_t>::max();
      break;
    case 1U:
      input.thread_status_bytes = std::numeric_limits<std::size_t>::max();
      break;
    case 2U:
      input.thread_affinity_words = std::numeric_limits<std::size_t>::max();
      break;
    case 3U:
      input.hardware_identity.model = 0xffU;
      break;
    case 4U:
      input.hardware_prestate = {};
      break;
    default:
      FAIL();
      return;
    }
    EXPECT_THROW(static_cast<void>(calibration::native_discovery_layout(input)),
                 std::invalid_argument);
  }
}

TEST(NativeDiscovery, NativeEntrypointRejectsBeforeLaunchingOrPublishing) {
  bool published = false;
  const calibration::NativeDiscoveryPublication callback{
      &published,
      [](void* context, const calibration::NativeDiscoveryPublicationView&) noexcept {
        *static_cast<bool*>(context) = true;
        return true;
      }};
  auto input = plan();
  input.discovery.session.warmup_attempt_capacity = 0U;
  EXPECT_THROW(
      static_cast<void>(calibration::run_native_discovery_capture(input, callback)),
      std::invalid_argument);
  EXPECT_FALSE(published);
  EXPECT_THROW(static_cast<void>(calibration::run_native_discovery_capture(
                   plan(), {nullptr, nullptr})),
               std::invalid_argument);
}

TEST(NativeDiscovery, TlsCoverageRejectsUnallocatedOutsideAndOverflowingPayloads) {
  std::array<std::byte, 4096U> stack{};
  const auto base = reinterpret_cast<std::uintptr_t>(stack.data());
  std::array<platform::ThreadTlsModule, 1U> modules{{{0U, 1U, base + 32U, 64U}}};
  platform::ThreadTlsSnapshot observed;
  observed.stop = platform::ThreadTlsStop::complete;
  observed.iteration_return = 0;
  observed.fs_base = base + 128U;
  observed.used = 1U;
  EXPECT_TRUE(calibration::native_discovery_tls_covered(observed, modules, stack));
  modules[0U].address = 0U;
  EXPECT_FALSE(calibration::native_discovery_tls_covered(observed, modules, stack));
  modules[0U].address = base + stack.size();
  EXPECT_FALSE(calibration::native_discovery_tls_covered(observed, modules, stack));
  modules[0U].address = base + 32U;
  modules[0U].bytes = std::numeric_limits<std::size_t>::max();
  EXPECT_FALSE(calibration::native_discovery_tls_covered(observed, modules, stack));
  modules[0U].bytes = 64U;
  observed.fs_base = base - 1U;
  EXPECT_FALSE(calibration::native_discovery_tls_covered(observed, modules, stack));
  observed.fs_base = base + 128U;
  observed.used = 2U;
  EXPECT_FALSE(calibration::native_discovery_tls_covered(observed, modules, stack));
  observed.used = 1U;
  observed.stop = platform::ThreadTlsStop::capacity_exhausted;
  EXPECT_FALSE(calibration::native_discovery_tls_covered(observed, modules, stack));
}

TEST(NativeDiscovery, EnvironmentLayoutChargesAllSixGroupsIncludingUnrequested) {
  auto input = plan();
  const auto original = calibration::native_discovery_layout(input);
  input.environment_sources.push_back(
      {"/explicit/source", 4096U, 1024U, 32U, {true, false, true, true, false, true}});
  const auto first = calibration::native_discovery_layout(input);
  EXPECT_EQ(first.region_bytes, original.region_bytes);
  EXPECT_GE(first.monitor_bytes - original.monitor_bytes, std::size_t{6U} * 4096U);
  input.environment_sources[0U].byte_capacity += 4096U;
  const auto larger = calibration::native_discovery_layout(input);
  EXPECT_EQ(larger.monitor_bytes - first.monitor_bytes, std::size_t{6U} * 4096U);
  input.environment_sources[0U].max_data_reads += 1024U;
  const auto records = calibration::native_discovery_layout(input);
  EXPECT_GE(records.monitor_bytes - larger.monitor_bytes,
            std::size_t{6U} * 1024U * sizeof(platform::FileSnapshotRead));
  input.environment_sources.push_back(
      {"/another/source", 4096U, 1024U, 32U, {true, true, true, true, true, true}});
  EXPECT_GT(calibration::native_discovery_layout(input).monitor_bytes,
            records.monitor_bytes);
}

TEST(NativeDiscovery, InvalidEnvironmentAndSummedOverflowRejectBeforeNativeAccess) {
  for (unsigned variant = 0U; variant < 6U; ++variant) {
    auto input = plan();
    input.environment_sources.push_back(
        {"/explicit/source", 4096U, 1024U, 32U, {true, true, true, true, true, true}});
    auto& source = input.environment_sources[0U];
    switch (variant) {
    case 0U:
      source.path = "relative";
      break;
    case 1U:
      source.chunk_bytes = 0U;
      break;
    case 2U:
      source.requested.fill(false);
      break;
    case 3U:
      input.environment_sources.push_back(source);
      break;
    case 4U:
      source.byte_capacity =
          static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max()) / 2U;
      break;
    default:
      source.max_data_reads =
          static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max()) /
          sizeof(platform::FileSnapshotRead);
      break;
    }
    EXPECT_THROW(static_cast<void>(calibration::native_discovery_layout(input)),
                 std::invalid_argument);
  }
}

struct EnvironmentControls final {
  calibration::DiscoveryObservationStatus status{
      calibration::DiscoveryObservationStatus::accepted};
  std::size_t calls{};
  std::size_t page_calls{};
  auto observe_controls(calibration::DiscoveryResidencyRequest) noexcept
      -> calibration::DiscoveryObservationStatus {
    ++calls;
    return status;
  }
  auto control_group_complete(calibration::DiscoverySessionPhase,
                              calibration::DiscoveryResidencyMoment) const noexcept
      -> bool {
    return status == calibration::DiscoveryObservationStatus::accepted;
  }
  auto query_pages(std::span<void* const>, std::span<int>) noexcept
      -> platform::PageResidencyQueryResult {
    ++page_calls;
    return {0, 0};
  }
};

struct EnvironmentFiles final : platform::FileSnapshotOperations {
  EnvironmentControls& controls;
  explicit EnvironmentFiles(EnvironmentControls& observed) : controls(observed) {}
  std::size_t calls{};
  bool ordering_error{false};
  bool error{false};
  bool truncated{false};
  auto open_file(const char*, int) noexcept -> platform::LinuxCallResult override {
    return {42, 0};
  }
  auto read_at(int, std::span<std::byte> bytes, std::size_t offset) noexcept
      -> platform::LinuxCallResult override {
    ++calls;
    ordering_error =
        ordering_error || controls.calls == 0U || controls.page_calls != 0U;
    if (error) {
      return {-1, EIO};
    }
    if (offset == 0U || truncated) {
      bytes[0U] = std::byte{0xff};
      return {1, 0};
    }
    return {0, 0};
  }
  auto close_file(int) noexcept -> platform::LinuxCallResult override { return {0, 0}; }
};

struct EnvironmentStorage final {
  std::array<char, 3U> path{};
  std::array<std::array<std::byte, 4U>, 6U> bytes{};
  std::array<std::array<platform::FileSnapshotRead, 2U>, 6U> reads{};
  std::array<platform::FileSnapshotSample, 6U> samples{};
  EnvironmentStorage() {
    for (std::size_t index = 0U; index < samples.size(); ++index) {
      samples[index] = {bytes[index], reads[index]};
    }
  }
};

TEST(NativeDiscovery, EnvironmentSharesControlsBeforePageQueryAndRetainsSixGroups) {
  EnvironmentControls controls;
  EnvironmentFiles files(controls);
  EnvironmentStorage storage;
  platform::PreparedFileSnapshot reader(files);
  ASSERT_TRUE(reader.prepare({"/x", 4U, 4U, 2U, {true, true, true, true, true, true}},
                             storage.path, storage.samples));
  calibration::native_discovery_detail::EnvironmentQuery query(
      controls, std::span<platform::PreparedFileSnapshot>(&reader, 1U));
  for (std::size_t group = 0U; group < 6U; ++group) {
    const auto phase = static_cast<calibration::DiscoverySessionPhase>(group / 3U);
    const auto moment = static_cast<calibration::DiscoveryResidencyMoment>(group % 3U);
    EXPECT_FALSE(query.control_group_complete(phase, moment));
    EXPECT_EQ(query.observe_controls({phase, moment, 0U, 0U}),
              calibration::DiscoveryObservationStatus::accepted);
    EXPECT_TRUE(query.control_group_complete(phase, moment));
    EXPECT_TRUE(storage.samples[group].io_complete());
    EXPECT_EQ(storage.samples[group].captured_bytes, 1U);
    EXPECT_EQ(storage.samples[group].bytes[0U], std::byte{0xff});
  }
  EXPECT_FALSE(files.ordering_error);
  EXPECT_TRUE(query.query_pages({}, {}).succeeded());
  EXPECT_EQ(controls.page_calls, 1U);
  const auto reads = files.calls;
  EXPECT_EQ(
      query.observe_controls({calibration::DiscoverySessionPhase::warmup,
                              calibration::DiscoveryResidencyMoment::before, 0U, 0U}),
      calibration::DiscoveryObservationStatus::rejected);
  EXPECT_EQ(files.calls, reads);
}

TEST(NativeDiscovery, EnvironmentStillReadsAllSourcesWhenControlsAndEarlierFileFail) {
  EnvironmentControls controls;
  controls.status = calibration::DiscoveryObservationStatus::rejected;
  EnvironmentFiles first(controls);
  EnvironmentFiles second(controls);
  first.error = true;
  second.truncated = true;
  std::array<EnvironmentStorage, 2U> storage;
  std::array<platform::PreparedFileSnapshot, 2U> readers{
      platform::PreparedFileSnapshot(first), platform::PreparedFileSnapshot(second)};
  for (std::size_t index = 0U; index < readers.size(); ++index) {
    ASSERT_TRUE(
        readers[index].prepare({"/x", 4U, 4U, 2U, {true, true, true, true, true, true}},
                               storage[index].path, storage[index].samples));
  }
  calibration::native_discovery_detail::EnvironmentQuery query(
      controls, std::span<platform::PreparedFileSnapshot>(readers));
  EXPECT_EQ(
      query.observe_controls({calibration::DiscoverySessionPhase::warmup,
                              calibration::DiscoveryResidencyMoment::before, 0U, 0U}),
      calibration::DiscoveryObservationStatus::rejected);
  EXPECT_EQ(first.calls, 1U);
  EXPECT_EQ(second.calls, 3U);
  EXPECT_EQ(storage[0U].samples[0U].stop, platform::FileSnapshotStop::read_failed);
  EXPECT_EQ(storage[1U].samples[0U].stop,
            platform::FileSnapshotStop::read_budget_exhausted);
  EXPECT_EQ(storage[1U].samples[0U].captured_bytes, 2U);
  EXPECT_EQ(storage[1U].samples[0U].probe_byte, std::byte{0xff});
  EXPECT_FALSE(
      query.control_group_complete(calibration::DiscoverySessionPhase::warmup,
                                   calibration::DiscoveryResidencyMoment::before));
}

TEST(NativeDiscovery,
     EnvironmentRejectsIncompleteRequiredFileWithoutSamplingOtherRows) {
  EnvironmentControls controls;
  EnvironmentFiles files(controls);
  EnvironmentStorage storage;
  files.error = true;
  platform::PreparedFileSnapshot reader(files);
  ASSERT_TRUE(reader.prepare({"/x", 4U, 4U, 2U, {true, false, true, true, false, true}},
                             storage.path, storage.samples));
  calibration::native_discovery_detail::EnvironmentQuery query(
      controls, std::span<platform::PreparedFileSnapshot>(&reader, 1U));
  controls.status = calibration::DiscoveryObservationStatus::not_configured;
  EXPECT_EQ(
      query.observe_controls({calibration::DiscoverySessionPhase::warmup,
                              calibration::DiscoveryResidencyMoment::before, 1U, 0U}),
      calibration::DiscoveryObservationStatus::not_configured);
  EXPECT_EQ(files.calls, 0U);
  controls.status = calibration::DiscoveryObservationStatus::accepted;
  EXPECT_EQ(
      query.observe_controls({calibration::DiscoverySessionPhase::warmup,
                              calibration::DiscoveryResidencyMoment::before, 0U, 0U}),
      calibration::DiscoveryObservationStatus::rejected);
  EXPECT_FALSE(
      query.control_group_complete(calibration::DiscoverySessionPhase::warmup,
                                   calibration::DiscoveryResidencyMoment::before));
  EXPECT_EQ(
      query.observe_controls({calibration::DiscoverySessionPhase::warmup,
                              calibration::DiscoveryResidencyMoment::during, 0U, 1U}),
      calibration::DiscoveryObservationStatus::accepted);
  EXPECT_EQ(storage.samples[1U].stop, platform::FileSnapshotStop::not_requested);
  EXPECT_EQ(files.calls, 1U);
}

auto retained_capacity_session() -> calibration::DiscoverySessionResult {
  calibration::DiscoverySessionResult result;
  result.stop = calibration::DiscoverySessionStop::trace_capacity;
  result.preparation.fill(calibration::DiscoveryPreparationStatus::ready);
  result.private_reset_verified.fill(true);
  result.warmup_verified = true;
  result.measurement_verified = true;
  for (auto& worker : result.warmup) {
    worker.stop = calibration::DiscoveryWorkerStop::fixed_deadline;
  }
  result.measurement[0U].stop = calibration::DiscoveryWorkerStop::trace_capacity;
  result.measurement[1U].stop = calibration::DiscoveryWorkerStop::peer_stopped;
  result.warmup_drain.stop = calibration::DiscoveryDrainStop::complete;
  result.warmup_drain.reset_verified = true;
  result.measurement_drain.stop = calibration::DiscoveryDrainStop::complete;
  result.origins = {17U, 99U};
  result.observed_origins = result.origins;
  result.origin_status.fill(timing::ClockReadStatus::ok);
  result.observations.fill({calibration::DiscoveryObservationStatus::accepted,
                            calibration::DiscoveryObservationStatus::accepted,
                            calibration::DiscoveryObservationStatus::accepted});
  return result;
}

TEST(NativeDiscovery, MeasurementTraceCapacityIsDistinctRetainedInsufficientData) {
  for (const auto peer : {calibration::DiscoveryWorkerStop::peer_stopped,
                          calibration::DiscoveryWorkerStop::trace_capacity,
                          calibration::DiscoveryWorkerStop::fixed_deadline}) {
    for (std::size_t owner = 0U; owner < 2U; ++owner) {
      auto result = retained_capacity_session();
      result.measurement[owner].stop = calibration::DiscoveryWorkerStop::trace_capacity;
      result.measurement[1U - owner].stop = peer;
      EXPECT_EQ(calibration::native_discovery_detail::session_stop(result),
                calibration::NativeDiscoveryCaptureStop::trace_capacity);
    }
  }
}

TEST(NativeDiscovery, TraceCapacityRequiresCompletedMandatorySessionEvidence) {
  for (unsigned variant = 0U; variant < 23U; ++variant) {
    auto result = retained_capacity_session();
    switch (variant) {
    case 0U:
      result.stop = calibration::DiscoverySessionStop::warmup_failure;
      break;
    case 1U:
      result.warmup[0U].stop = calibration::DiscoveryWorkerStop::trace_capacity;
      break;
    case 2U:
      result.warmup_verified = false;
      break;
    case 3U:
      result.measurement_verified = false;
      break;
    case 4U:
      result.private_reset_verified[0U] = false;
      break;
    case 5U:
      result.warmup_drain.reset_verified = false;
      break;
    case 6U:
      result.warmup_drain.stop = calibration::DiscoveryDrainStop::reset_failure;
      break;
    case 7U:
      result.measurement_drain.stop = calibration::DiscoveryDrainStop::count_mismatch;
      break;
    case 8U:
      result.worker_exception[1U] = true;
      break;
    case 9U:
      result.preparation[1U] = calibration::DiscoveryPreparationStatus::rejected;
      break;
    case 10U:
      result.origins[1U].reset();
      break;
    case 11U:
      result.observed_origins[1U] = 98U;
      break;
    case 12U:
      result.origin_status[1U].reset();
      break;
    case 13U:
      result.observations[0U].before =
          calibration::DiscoveryObservationStatus::not_configured;
      break;
    case 14U:
      result.observations[1U].during =
          calibration::DiscoveryObservationStatus::rejected;
      break;
    case 15U:
      result.observations[1U].after =
          calibration::DiscoveryObservationStatus::not_started;
      break;
    case 16U:
      result.measurement[1U].stop = calibration::DiscoveryWorkerStop::invalid_plan;
      break;
    case 17U:
      result.stop = calibration::DiscoverySessionStop::observation_failure;
      break;
    case 18U:
      result.measurement[0U].failed_clock_status = timing::ClockReadStatus::call_failed;
      break;
    case 19U:
      result.warmup[1U].failed_clock_status = timing::ClockReadStatus::overflow;
      break;
    case 20U:
      result.measurement_drain.failed_clock_status =
          timing::ClockReadStatus::call_failed;
      break;
    case 21U:
      result.warmup_drain.failed_clock_status = timing::ClockReadStatus::call_failed;
      break;
    default:
      result.measurement[0U].stop = calibration::DiscoveryWorkerStop::peer_stopped;
      break;
    }
    EXPECT_EQ(calibration::native_discovery_detail::session_stop(result),
              calibration::NativeDiscoveryCaptureStop::capture_failed)
        << variant;
  }
}

TEST(NativeDiscovery, MandatoryCleanupFailureOverridesRetainedCapacityClassification) {
  using Stop = calibration::NativeDiscoveryCaptureStop;
  for (const auto original : {Stop::complete, Stop::trace_capacity}) {
    for (const auto failure :
         {Stop::environment_monitor_failure, Stop::hardware_monitor_failure,
          Stop::thread_monitor_failure, Stop::cleanup_failed}) {
      EXPECT_EQ(
          calibration::native_discovery_detail::after_cleanup(original, true, failure),
          original);
      EXPECT_EQ(
          calibration::native_discovery_detail::after_cleanup(original, false, failure),
          failure);
    }
  }
  EXPECT_EQ(calibration::native_discovery_detail::after_cleanup(
                Stop::capture_failed, true, Stop::cleanup_failed),
            Stop::capture_failed);
  EXPECT_EQ(calibration::native_discovery_detail::after_cleanup(
                Stop::publication_failed, false, Stop::cleanup_failed),
            Stop::publication_failed);
}

} // namespace
