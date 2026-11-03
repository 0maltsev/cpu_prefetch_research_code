#include "cpu_prefetch/runner/stage17_discovery_publication.hpp"
#include "discovery_backend_test_support.hpp"

#include <gtest/gtest.h>

#include <cerrno>
#include <limits>

namespace {
using namespace cpu_prefetch;
namespace stage17 = runner::stage17;
using Value = protocol::json::Value;

class MemorySink final : public stage17::ArtifactSink {
public:
  std::vector<stage17::ArtifactPayload> artifacts;
  std::optional<std::size_t> fail_at;
  std::size_t calls{0U};
  auto publish(stage17::ArtifactPayload artifact)
      -> protocol::Result<stage17::ArtifactBinding> override {
    const auto index = calls++;
    if (fail_at == index)
      return protocol::Result<stage17::ArtifactBinding>::failure(
          {protocol::ErrorCategory::cross_field, "$test/sink", "TEST-SINK-FAILURE",
           "injected sink failure"});
    stage17::ArtifactBinding result{
        artifact.role,         artifact.schema_identity,
        artifact.media_type,   artifact.file_name,
        artifact.bytes.size(), workload::sha256(artifact.bytes).hex()};
    artifacts.push_back(std::move(artifact));
    return protocol::Result<stage17::ArtifactBinding>::success(result);
  }
};

auto member(const Value& value, std::string_view key) -> const Value& {
  if (value.as_object() == nullptr)
    throw std::logic_error("expected JSON object");
  return value.as_object()->at(std::string(key));
}
auto element(const Value& value, std::size_t index) -> const Value& {
  if (value.as_array() == nullptr)
    throw std::logic_error("expected JSON array");
  return value.as_array()->at(index);
}
auto integer(const Value& value) -> std::uint64_t {
  const auto* number = value.as_number();
  if (number == nullptr)
    throw std::logic_error("expected exact JSON integer");
  if (const auto* u = std::get_if<std::uint64_t>(&number->value))
    return *u;
  if (const auto* s = std::get_if<std::int64_t>(&number->value);
      s != nullptr && *s >= 0)
    return static_cast<std::uint64_t>(*s);
  throw std::logic_error("JSON integer lost precision/type");
}
auto document(const MemorySink& sink) -> Value {
  const auto& bytes = sink.artifacts.back().bytes;
  auto parsed = protocol::json::parse(
      std::string_view(reinterpret_cast<const char*>(bytes.data()), bytes.size()));
  if (!parsed)
    throw std::logic_error("publisher emitted invalid JSON");
  return std::move(parsed).value();
}
// Independent little-endian reader, deliberately not the production raw codec.
auto read_u64(const std::vector<std::byte>& bytes, std::size_t offset)
    -> std::uint64_t {
  if (offset > bytes.size() || bytes.size() - offset < 8U)
    throw std::out_of_range("short u64");
  std::uint64_t value = 0U;
  for (std::size_t index = 8U; index != 0U; --index)
    value = value * 256U + std::to_integer<unsigned int>(bytes[offset + index - 1U]);
  return value;
}

struct Fixture final {
  test_support::DiscoveryTestPhase<8U> warmup{"publisher-warmup"};
  test_support::DiscoveryTestPhase<8U> measurement{"publisher-measurement"};
  MemorySink sink;
  platform::PrefetchReadbackPreparation hardware{};
  calibration::NativeDiscoveryCaptureLayout layout{};
  calibration::NativeDiscoveryCaptureResult result{};
  calibration::NativeDiscoveryPublicationView view{
      result,
      layout,
      {},
      {},
      {},
      {},
      {},
      hardware,
      {},
      {&warmup.producer, &measurement.producer},
      {&warmup.consumer, &measurement.consumer},
      {},
      {}};
  Fixture() {
    for (auto* phase : {&warmup, &measurement}) {
      if (!phase->producer_stream.prepare_for_owner() ||
          !phase->consumer_stream.prepare_for_owner() ||
          !phase->trace.prepare_worker(calibration::RingWorker::producer) ||
          !phase->trace.prepare_worker(calibration::RingWorker::consumer))
        throw std::logic_error("test phase preparation failed");
    }
  }
  auto publish(std::size_t ordinal = 0U) {
    return stage17::publish_discovery_capture(sink, ordinal, view);
  }
};

TEST(Stage17DiscoveryPublication, PreservesRawCodecRunIdsAndFourVectorOffsets) {
  Fixture f;
  constexpr std::uint64_t large = 9007199254740993ULL;
  const timing::ProducerObservation row{{7U},
                                        {3U},
                                        large,
                                        {11U, 1000U},
                                        {12U, 2000U},
                                        {13U, 3000U},
                                        timing::ClockSample{14U, 4000U},
                                        {15U, 5000U},
                                        protocol::ProducerOutcome::accepted,
                                        workload::AcceptedOrdinal{0U}};
  ASSERT_EQ(f.warmup.producer_stream.append(row), storage::AppendStatus::appended);
  ASSERT_EQ(f.measurement.producer_stream.append(row), storage::AppendStatus::appended);
  const timing::ConsumerObservation consumed{{0U},         {3U},         {16U, 6000U},
                                             {17U, 7000U}, {18U, 8000U}, {19U, 9000U}};
  ASSERT_EQ(f.warmup.consumer_stream.append(consumed), storage::AppendStatus::appended);
  ASSERT_TRUE(f.warmup.trace.record(calibration::RingWorker::producer, 0U, large,
                                    calibration::RingAttemptOutcome::advanced));
  ASSERT_TRUE(f.warmup.trace.record(calibration::RingWorker::producer, large + 2U,
                                    large + 5U,
                                    calibration::RingAttemptOutcome::advanced));
  ASSERT_TRUE(f.warmup.trace.record(calibration::RingWorker::consumer, 10U, 15U,
                                    calibration::RingAttemptOutcome::advanced));
  ASSERT_TRUE(f.warmup.trace.record(calibration::RingWorker::consumer, 20U, 27U,
                                    calibration::RingAttemptOutcome::advanced));
  auto result = f.publish();
  ASSERT_TRUE(result);
  ASSERT_EQ(result.value().size(), 7U);
  const auto& producer = f.sink.artifacts[0U].bytes;
  EXPECT_EQ(std::to_integer<unsigned int>(producer[0U]), 16U);
  for (std::size_t i = 1U; i < 4U; ++i)
    EXPECT_EQ(producer[i], std::byte{0U});
  EXPECT_EQ(std::string(reinterpret_cast<const char*>(producer.data() + 4U), 16U),
            "publisher-warmup");
  for (std::size_t i = 20U; i < 24U; ++i)
    EXPECT_EQ(producer[i], std::byte{0U});
  EXPECT_EQ(read_u64(producer, 24U), 7U);
  EXPECT_EQ(read_u64(producer, 32U), 3U);
  EXPECT_EQ(read_u64(producer, 40U), large);
  EXPECT_EQ(std::to_integer<unsigned int>(f.sink.artifacts[3U].bytes[0U]), 21U);
  EXPECT_EQ(
      std::string(reinterpret_cast<const char*>(f.sink.artifacts[3U].bytes.data() + 4U),
                  21U),
      "publisher-measurement");
  const auto& demand = f.sink.artifacts[2U].bytes;
  ASSERT_EQ(demand.size(), 48U);
  const std::array expected{large,
                            std::uint64_t{3U},
                            large + 2U,
                            std::uint64_t{5U},
                            std::uint64_t{7U},
                            std::uint64_t{10U}};
  for (std::size_t index = 0U; index < expected.size(); ++index)
    EXPECT_EQ(read_u64(demand, index * 8U), expected[index]);
  const auto json = document(f.sink);
  const auto& vectors = member(element(member(json, "phases"), 0U), "demand_vectors");
  const std::array offsets{0U, 16U, 24U, 40U};
  const std::array counts{2U, 1U, 2U, 1U};
  for (std::size_t index = 0U; index < 4U; ++index) {
    EXPECT_EQ(integer(member(element(vectors, index), "offset_bytes")), offsets[index]);
    EXPECT_EQ(integer(member(element(vectors, index), "count")), counts[index]);
  }
  EXPECT_EQ(*member(element(member(json, "phases"), 0U), "run_id").as_string(),
            "publisher-warmup");
  EXPECT_EQ(f.sink.artifacts[0U].file_name, "discovery-c00-warmup-producer.bin");
  EXPECT_EQ(f.sink.artifacts[1U].role, "DISCOVERY_CONSUMER_RAW");
  EXPECT_EQ(f.sink.artifacts[2U].schema_identity, "DISCOVERY-FOUR-U64LE-VECTORS-v1");
  EXPECT_EQ(f.sink.artifacts[6U].file_name, "discovery-c00-control.json");
  EXPECT_FALSE(*member(json, "execution_authority").as_bool());
}

TEST(Stage17DiscoveryPublication, MissingOwnersRetainSevenFilesAndNullFacts) {
  Fixture f;
  f.view.producer = {nullptr, nullptr};
  f.view.consumer = {nullptr, nullptr};
  f.result.stop = calibration::NativeDiscoveryCaptureStop::mapping_failure;
  ASSERT_TRUE(f.publish(35U));
  ASSERT_EQ(f.sink.artifacts.size(), 7U);
  for (std::size_t i = 0U; i < 6U; ++i)
    EXPECT_TRUE(f.sink.artifacts[i].bytes.empty());
  const auto json = document(f.sink);
  EXPECT_TRUE(member(json, "session").is_null());
  EXPECT_TRUE(member(json, "clock_origin").is_null());
  const auto& phase = element(member(json, "phases"), 0U);
  EXPECT_FALSE(*member(phase, "producer_available").as_bool());
  EXPECT_TRUE(member(phase, "producer_snapshot").is_null());
  EXPECT_TRUE(member(element(member(phase, "demand_vectors"), 0U), "count").is_null());
  EXPECT_EQ(f.sink.artifacts.back().file_name, "discovery-c35-control.json");
}

TEST(Stage17DiscoveryPublication, ConsumerIdentityIsRetainedWhenProducerMissing) {
  Fixture f;
  f.view.producer[0U] = nullptr;
  ASSERT_TRUE(f.warmup.trace.record(calibration::RingWorker::consumer, 2U, 9U,
                                    calibration::RingAttemptOutcome::empty));
  ASSERT_TRUE(f.publish());
  const auto json = document(f.sink);
  const auto& phase = element(member(json, "phases"), 0U);
  EXPECT_EQ(*member(phase, "consumer_run_id").as_string(), "publisher-warmup");
  ASSERT_EQ(f.sink.artifacts[2U].bytes.size(), 8U);
  EXPECT_EQ(read_u64(f.sink.artifacts[2U].bytes, 0U), 7U);
  EXPECT_TRUE(member(element(member(phase, "demand_vectors"), 0U), "count").is_null());
  EXPECT_EQ(integer(member(element(member(phase, "demand_vectors"), 2U), "count")), 1U);
}

TEST(Stage17DiscoveryPublication,
     RetainsFailedCurrentEventDrainAndSessionWithoutCompletenessClaim) {
  Fixture f;
  f.result.session.emplace();
  f.result.session->stop = calibration::DiscoverySessionStop::drain_failure;
  f.result.session->warmup_drain = {calibration::DiscoveryDrainStop::clock_failure};
  f.result.session->warmup_drain.failed_clock_status =
      timing::ClockReadStatus::call_failed;
  f.warmup.producer.primary_prefix_complete = false;
  f.warmup.producer.current.requested_attempt =
      calibration::DiscoveryProducerAttemptIdentity{
          {UINT64_MAX}, UINT64_MAX, {UINT64_MAX}};
  f.warmup.producer.current.failed_boundary =
      calibration::DiscoveryCaptureBoundary::enqueue_publication;
  f.warmup.producer.current.enqueue_publication =
      timing::ClockReadResult{timing::ClockReadStatus::call_failed, {0U, 0U}};
  f.warmup.consumer.drain_requests = 1U;
  f.warmup.consumer.drain_rows[0U].candidate_consumed_ordinal =
      workload::AcceptedOrdinal{UINT64_MAX};
  f.warmup.consumer.drain_rows[0U].operation =
      queue::DequeueResult{queue::DequeueStatus::item, &f};
  f.warmup.consumer.drain_rows[0U].capture.operation_performed = true;
  f.warmup.consumer.drain_rows[0U].access = workload::RecordAccessResult{
      workload::RecordAccessStatus::record_index_corrupt, {UINT64_MAX}, UINT64_MAX};
  f.warmup.consumer.last_join = {calibration::DiscoveryJoinStatus::checksum_mismatch,
                                 7U, 9U};
  f.warmup.producer_stream.seal_incomplete();
  ASSERT_TRUE(f.publish());
  const auto json = document(f.sink);
  const auto& phase = element(member(json, "phases"), 0U);
  EXPECT_EQ(*member(member(phase, "producer_snapshot"), "completeness").as_string(),
            "SEALED_INCOMPLETE");
  EXPECT_EQ(
      integer(member(member(member(phase, "producer_current"), "requested_attempt"),
                     "logical_sequence")),
      UINT64_MAX);
  EXPECT_TRUE(member(member(member(phase, "producer_current"), "enqueue_publication"),
                     "absolute_nanoseconds")
                  .is_null());
  EXPECT_EQ(integer(member(element(member(phase, "drain_rows"), 0U),
                           "candidate_consumed_ordinal")),
            UINT64_MAX);
  EXPECT_EQ(integer(member(member(element(member(phase, "drain_rows"), 0U), "access"),
                           "record_index")),
            UINT64_MAX);
  EXPECT_EQ(integer(member(member(element(member(phase, "drain_rows"), 0U), "access"),
                           "payload")),
            UINT64_MAX);
  EXPECT_EQ(integer(member(member(phase, "consumer_last_join"), "failed_producer_row")),
            9U);
  EXPECT_EQ(integer(member(member(member(json, "session"), "warmup_drain"),
                           "failed_clock_status")),
            static_cast<unsigned int>(timing::ClockReadStatus::call_failed));
}

TEST(Stage17DiscoveryPublication, SinkFailureStopsImmediatelyWithoutRetryOrSuccess) {
  for (std::size_t failure = 0U; failure < 7U; ++failure) {
    Fixture f;
    f.sink.fail_at = failure;
    auto result = f.publish();
    EXPECT_FALSE(result);
    EXPECT_EQ(f.sink.calls, failure + 1U);
    EXPECT_EQ(f.sink.artifacts.size(), failure);
  }
}

TEST(Stage17DiscoveryPublication, InvalidOrdinalPublishesNothing) {
  Fixture f;
  EXPECT_FALSE(f.publish(36U));
  EXPECT_EQ(f.sink.calls, 0U);
}

TEST(Stage17DiscoveryPublication,
     FinalResultRetainsCleanupFailuresAndMissingObservations) {
  calibration::NativeDiscoveryCaptureResult result{};
  const auto absent = stage17::discovery_capture_result_json(result);
  EXPECT_TRUE(member(absent, "worker_mappings").is_null());
  EXPECT_TRUE(member(absent, "worker_stacks").is_null());
  EXPECT_TRUE(member(absent, "clock_origin").is_null());
  result.stop = calibration::NativeDiscoveryCaptureStop::cleanup_failed;
  result.publication_attempted = true;
  result.publication_succeeded = true;
  result.core_mapping.cleanup_attempted = true;
  result.core_mapping.unlock = platform::LinuxCallResult{-1, EIO};
  result.core_mapping.unmap = platform::LinuxCallResult{0, 0};
  result.monitor_mapping.cleanup_attempted = true;
  result.monitor_mapping.unmap = platform::LinuxCallResult{-1, EINVAL};
  result.worker_mappings.emplace();
  result.worker_stacks.emplace();
  result.worker_mappings->at(2U).cleanup_attempted = true;
  result.worker_mappings->at(2U).unmap = platform::LinuxCallResult{-1, ENOMEM};
  result.worker_stacks->at(1U).cleanup_attempted = true;
  result.worker_stacks->at(1U).thread.join = 0;
  result.worker_stacks->at(1U).unmap = platform::LinuxCallResult{-1, EBUSY};
  result.controller_stack.cleanup_attempted = true;
  result.controller_stack.thread.join = 0;
  result.controller_stack.unmap = platform::LinuxCallResult{0, 0};
  result.session.emplace();
  result.session->warmup_drain.attempts = UINT64_MAX;
  const auto value = stage17::discovery_capture_result_json(result);
  EXPECT_EQ(
      integer(member(member(member(value, "core_mapping"), "unlock"), "error_number")),
      EIO);
  EXPECT_EQ(integer(member(member(member(value, "monitor_mapping"), "unmap"),
                           "error_number")),
            EINVAL);
  EXPECT_EQ(
      integer(member(member(element(member(value, "worker_mappings"), 2U), "unmap"),
                     "error_number")),
      ENOMEM);
  EXPECT_EQ(integer(member(member(element(member(value, "worker_stacks"), 1U), "unmap"),
                           "error_number")),
            EBUSY);
  EXPECT_EQ(
      integer(member(member(member(value, "controller_stack"), "thread"), "join")), 0U);
  EXPECT_TRUE(*member(value, "publication_succeeded").as_bool());
  EXPECT_EQ(
      integer(member(member(member(value, "session"), "warmup_drain"), "attempts")),
      UINT64_MAX);
}

TEST(Stage17DiscoveryPublication,
     RetainsPartialSyscallsMonitorPreparationTlsAndMappingFacts) {
  Fixture f;
  std::array<char, 4U> raw{char(0xFF), 'x', 'y', 'z'};
  std::array<unsigned long, 1U> affinity{1UL << 3U};
  platform::ThreadMonitorScratch scratch{raw, raw, raw, affinity};
  platform::ThreadMonitorPreparation prep{};
  prep.attempted = true;
  prep.requested_task_id = 73;
  prep.directory_open = platform::LinuxCallResult{9, 0};
  prep.stat_open = platform::LinuxCallResult{10, 0};
  prep.status_open = platform::LinuxCallResult{-1, ENOENT};
  prep.closes[0U] = platform::LinuxCallResult{-1, EINTR};
  prep.initial.stat_before_read.read = platform::LinuxCallResult{2, 0};
  prep.initial.affinity_call = platform::LinuxCallResult{8, 0};
  prep.initial.affinity_mask = affinity;
  prep.initial.stat_before =
      platform::ThreadStatObservation{73, 'R', UINT64_MAX, UINT64_MAX, 7U, 3};
  f.view.thread_preparations[0U] = &prep;
  f.view.thread_preparation_scratch[0U] = scratch;
  f.hardware.attempted = true;
  f.hardware.released = true;
  f.hardware.requested_identity = {6U, 63U};
  f.hardware.observed_identity =
      platform::Result<platform::CpuFamilyModel>::success({6U, 63U});
  f.hardware.cpu_count = 1U;
  f.hardware.cpus[0U] = {3U, UINT64_MAX, UINT64_MAX - 15U,
                         platform::LinuxCallResult{11, 0},
                         platform::LinuxCallResult{-1, EIO}};
  std::array<calibration::DiscoveryControlSample, 1U> control{};
  control[0U].attempted = true;
  control[0U].scratch[0U] = scratch;
  control[0U].workers[0U] = prep.initial;
  auto& h = control[0U].hardware;
  h.attempted = true;
  h.cpu_count = 1U;
  h.prepared_controller_identity = platform::CpuFamilyModel{6U, 63U};
  h.cpus[0U].read = platform::LinuxCallResult{2, 0};
  h.cpus[0U].raw_bytes[0U] = std::byte{0xFE};
  h.cpus[0U].raw_bytes[1U] = std::byte{0xDC};
  f.view.controls = control;
  std::array<platform::ThreadTlsModule, 1U> modules{{{123U, 17U, 456U, 789U}}};
  f.view.tls_modules[0U] = modules;
  f.view.tls_snapshots[0U].used = 1U;
  f.view.tls_snapshots[0U].loader_adds = UINT64_MAX;
  f.result.core_mapping.binding = platform::LinuxCallResult{-1, EPERM};
  f.result.core_mapping.cleanup_attempted = true;
  f.result.core_mapping.unmap = platform::LinuxCallResult{-1, EIO};
  f.result.controller_stack.thread.join = 0;
  f.result.controller_stack.cleanup_attempted = false;
  ASSERT_TRUE(f.publish());
  const auto json = document(f.sink);
  const auto& initial =
      member(element(member(json, "thread_preparations"), 0U), "initial");
  EXPECT_EQ(integer(member(member(initial, "stat_before"), "start_time_ticks")),
            UINT64_MAX);
  const auto& observed_raw = member(member(initial, "stat_before_read"), "raw_bytes");
  ASSERT_EQ(observed_raw.as_array()->size(), 2U);
  EXPECT_EQ(integer(element(observed_raw, 0U)), 255U);
  EXPECT_TRUE(member(member(initial, "status_read"), "raw_bytes").is_null());
  const auto& cpu = element(
      member(member(element(member(json, "controls"), 0U), "hardware"), "cpus"), 0U);
  ASSERT_EQ(member(cpu, "raw_bytes").as_array()->size(), 2U);
  EXPECT_EQ(integer(element(member(cpu, "raw_bytes"), 1U)), 220U);
  EXPECT_TRUE(member(cpu, "observed_value").is_null());
  EXPECT_EQ(
      integer(member(element(member(member(json, "hardware_preparation"), "cpus"), 0U),
                     "expected_h0")),
      UINT64_MAX);
  EXPECT_EQ(integer(member(element(member(json, "tls_snapshots"), 0U), "loader_adds")),
            UINT64_MAX);
  EXPECT_EQ(
      integer(member(
          element(member(element(member(json, "tls_snapshots"), 0U), "modules"), 0U),
          "bytes")),
      789U);
  EXPECT_EQ(
      integer(member(member(member(json, "core_mapping"), "unmap"), "error_number")),
      EIO);
  EXPECT_FALSE(
      *member(member(json, "controller_stack"), "cleanup_attempted").as_bool());
  EXPECT_TRUE(member(json, "result_worker_stacks").is_null());
}

TEST(Stage17DiscoveryPublication, RetainsPageErrorsAndArenaIntegrityAtPublication) {
  Fixture f;
  alignas(64) std::array<std::byte, 128U> pages_memory{};
  std::array<void*, 2U> addresses{};
  std::array<int, 2U> statuses{};
  platform::PreparedPageResidencyQuery pages(pages_memory, 64U, addresses, statuses);
  statuses = {2, -EACCES};
  std::array<calibration::DiscoveryResidencySample, 1U> samples{
      calibration::DiscoveryResidencySample{
          {calibration::DiscoverySessionPhase::measurement,
           calibration::DiscoveryResidencyMoment::during, 3U, UINT64_MAX},
          pages}};
  samples[0U].query = platform::PageResidencyQueryResult{1, 0};
  samples[0U].stop = calibration::DiscoveryResidencyStop::wrong_node;
  f.view.residency = samples;
  workload::EventArena arena({8U, 64U, 4096U,
                              workload::MasterSeed::from_hex(std::string(64U, '0')),
                              "publication-test"});
  f.view.arena = &arena;
  auto& record = const_cast<workload::EventRecord&>(arena.physical_record(0U));
  record.payload ^= 1U;
  ASSERT_TRUE(f.publish());
  const auto json = document(f.sink);
  EXPECT_FALSE(*member(member(json, "arena"), "content_unchanged").as_bool());
  const auto& sampled = element(member(json, "residency"), 0U);
  EXPECT_EQ(integer(member(member(sampled, "request"), "offset_ticks")), UINT64_MAX);
  EXPECT_EQ(integer(element(member(sampled, "page_status"), 0U)), 2U);
  EXPECT_EQ(std::get<std::int64_t>(
                element(member(sampled, "page_status"), 1U).as_number()->value),
            -EACCES);
  EXPECT_EQ(integer(element(member(sampled, "page_addresses"), 1U)),
            reinterpret_cast<std::uintptr_t>(pages_memory.data() + 64U));
}

TEST(Stage17DiscoveryPublication, CorruptArenaOrderRetainsControlAndRawArtifacts) {
  Fixture f;
  workload::EventArena arena({8U, 64U, 4096U,
                              workload::MasterSeed::from_hex(std::string(64U, '0')),
                              "publication-corruption"});
  auto* order = const_cast<std::size_t*>(arena.record_order().data());
  order[0U] = order[1U];
  f.view.arena = &arena;
  ASSERT_TRUE(f.publish());
  EXPECT_EQ(f.sink.artifacts.size(), 7U);
  const auto json = document(f.sink);
  const auto& observed = member(json, "arena");
  EXPECT_TRUE(member(observed, "ordered_index_sha256").is_null());
  EXPECT_TRUE(member(observed, "address_delta_sha256").is_null());
  ASSERT_NE(member(observed, "ordered_index_error").as_string(), nullptr);
  EXPECT_FALSE(member(observed, "ordered_index_error").as_string()->empty());
  EXPECT_TRUE(*member(observed, "content_unchanged").as_bool());
}

TEST(Stage17DiscoveryPublication,
     EnvironmentalSnapshotsRetainBytesPartialReadsAndGroupIdentity) {
  Fixture f;
  const std::string path = std::string("/proc/") + char(0xFF) + "x";
  std::array<platform::FileSnapshotPreparation, 2U> preparations{};
  preparations[0U].attempted = true;
  preparations[0U].released = true;
  preparations[0U].plan = {path, 4U, 2U, 2U, {true, true, false, true, false, true}};
  preparations[0U].open = platform::LinuxCallResult{12, 0};
  preparations[0U].close = platform::LinuxCallResult{-1, EIO};
  preparations[0U].stop = platform::FileSnapshotPreparationStop::ready;
  preparations[1U].plan = {
      "/proc/second", 4U, 2U, 2U, {true, false, false, false, false, false}};
  std::array<std::array<std::byte, 4U>, 12U> bytes{};
  std::array<std::array<platform::FileSnapshotRead, 2U>, 12U> reads{};
  std::array<platform::FileSnapshotSample, 12U> samples{};
  for (std::size_t index = 0U; index < samples.size(); ++index) {
    samples[index].bytes = bytes[index];
    samples[index].reads = reads[index];
  }
  bytes[0U] = {std::byte{0xFF}, std::byte{0U}, std::byte{0x42}, std::byte{0xDD}};
  reads[0U] = {platform::FileSnapshotRead{0U, 2U, platform::LinuxCallResult{2, 0}},
               platform::FileSnapshotRead{2U, 2U, platform::LinuxCallResult{1, 0}}};
  samples[0U].attempted = true;
  samples[0U].captured_bytes = 3U;
  samples[0U].data_reads = 2U;
  samples[0U].eof_probe = {3U, 1U, platform::LinuxCallResult{1, 0}};
  samples[0U].probe_byte = std::byte{0xFE};
  samples[0U].stop = platform::FileSnapshotStop::read_budget_exhausted;
  bytes[1U][0U] = std::byte{0xAA};
  reads[1U] = {
      platform::FileSnapshotRead{0U, 2U, platform::LinuxCallResult{1, 0}},
      platform::FileSnapshotRead{1U, 2U, platform::LinuxCallResult{-1, EINTR}}};
  samples[1U].attempted = true;
  samples[1U].captured_bytes = 1U;
  samples[1U].data_reads = 2U;
  samples[1U].stop = platform::FileSnapshotStop::read_failed;
  reads[6U][0U] = {0U, 2U, platform::LinuxCallResult{0, 0}};
  samples[6U].attempted = true;
  samples[6U].data_reads = 1U;
  samples[6U].stop = platform::FileSnapshotStop::complete;
  f.view.environment_preparations = preparations;
  f.view.environment_samples = samples;
  ASSERT_TRUE(f.publish());
  const auto json = document(f.sink);
  const auto& prep = element(member(json, "environment_preparations"), 0U);
  EXPECT_EQ(integer(element(member(member(prep, "plan"), "path_bytes"), 6U)), 255U);
  EXPECT_EQ(integer(member(member(prep, "close"), "error_number")), EIO);
  EXPECT_FALSE(*element(member(member(prep, "plan"), "requested"), 2U).as_bool());
  const auto& retained = member(json, "environment_samples");
  const auto& first = element(retained, 0U);
  ASSERT_EQ(member(first, "raw_bytes").as_array()->size(), 3U);
  EXPECT_EQ(integer(element(member(first, "raw_bytes"), 0U)), 255U);
  EXPECT_EQ(integer(element(member(first, "raw_bytes"), 1U)), 0U);
  EXPECT_EQ(integer(member(first, "probe_byte")), 254U);
  EXPECT_EQ(integer(member(element(member(first, "reads"), 1U), "offset")), 2U);
  EXPECT_EQ(integer(member(member(first, "eof_probe"), "offset")), 3U);
  const auto& failed = element(retained, 1U);
  EXPECT_EQ(integer(member(member(element(member(failed, "reads"), 1U), "observed"),
                           "error_number")),
            EINTR);
  EXPECT_EQ(member(failed, "raw_bytes").as_array()->size(), 1U);
  EXPECT_TRUE(member(failed, "probe_byte").is_null());
  EXPECT_TRUE(member(element(retained, 2U), "raw_bytes").is_null());
  const auto& empty = element(retained, 6U);
  EXPECT_EQ(integer(member(empty, "source_index")), 1U);
  EXPECT_EQ(integer(member(empty, "group_index")), 0U);
  EXPECT_TRUE(member(empty, "raw_bytes").as_array()->empty());
  EXPECT_TRUE(member(empty, "probe_byte").is_null());
}

TEST(Stage17DiscoveryPublication, EnvironmentalStorageExtentCannotBeInvented) {
  for (const bool invalid_bytes : {true, false}) {
    Fixture f;
    std::array<std::byte, 1U> bytes{};
    std::array<platform::FileSnapshotRead, 1U> reads{};
    platform::FileSnapshotSample sample{};
    sample.attempted = true;
    sample.bytes = bytes;
    sample.reads = reads;
    sample.captured_bytes = invalid_bytes ? 2U : 0U;
    sample.data_reads = invalid_bytes ? 0U : 2U;
    f.view.environment_samples = std::span(&sample, 1U);
    EXPECT_FALSE(f.publish());
    EXPECT_EQ(f.sink.artifacts.size(), 6U);
  }
}
} // namespace
