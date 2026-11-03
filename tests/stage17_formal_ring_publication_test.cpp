#include "cpu_prefetch/runner/stage17_formal_ring_publication.hpp"
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

struct Phase final {
  protocol::RunId id;
  storage::ProducerObservationStream producer_stream;
  storage::ConsumerObservationStream consumer_stream;
  queue::detail::AlignedBlock producer_bytes;
  queue::detail::AlignedBlock consumer_bytes;
  calibration::RingDemandStream producer_demand;
  calibration::RingDemandStream consumer_demand;
  calibration::FormalRingProducerPhase producer;
  calibration::FormalRingConsumerPhase consumer;
  explicit Phase(std::string name)
      : id(test_support::discovery_test_run_id(std::move(name))),
        producer_stream(id, 8U), consumer_stream(id, 8U),
        producer_bytes(calibration::ring_demand_storage_requirements(id, 8U), 64U),
        consumer_bytes(calibration::ring_demand_storage_requirements(id, 8U), 64U),
        producer_demand(id, calibration::RingWorker::producer, 8U,
                        {producer_bytes.data(), producer_bytes.size()}),
        consumer_demand(id, calibration::RingWorker::consumer, 8U,
                        {consumer_bytes.data(), consumer_bytes.size()}),
        producer{
            producer_demand, producer_stream, storage::make_row_layout(id.value()), {}},
        consumer{consumer_demand, consumer_stream, storage::make_row_layout(id.value()),
                 {17U},           {17U},           {}} {
    if (!producer_stream.prepare_for_owner() || !consumer_stream.prepare_for_owner() ||
        !producer_demand.prepare_for_owner() || !consumer_demand.prepare_for_owner())
      throw std::logic_error("test stream preparation failed");
  }
};
struct Fixture final {
  Phase warmup{"formal-publisher-warmup"};
  Phase measurement{"formal-publisher-measurement"};
  MemorySink sink;
  platform::PrefetchReadbackPreparation hardware{};
  calibration::NativeFormalRingCaptureLayout layout{};
  calibration::NativeFormalRingCaptureResult result{};
  calibration::NativeFormalRingPublicationView view{
      result,
      layout,
      {{}, {}, {}, {}, {}, hardware, {}, {}, {}},
      {&warmup.producer, &measurement.producer},
      {&warmup.consumer, &measurement.consumer},
      nullptr};
  auto publish() { return stage17::publish_formal_ring_capture(sink, 7U, 1U, view); }
  void set_windows() {
    result.session.emplace();
    result.session->clock_origin = timing::ClockOrigin{100U};
    for (std::size_t i = 0U; i < 2U; ++i) {
      auto& phase = result.session->phases[i];
      phase.origin_sample =
          timing::ClockSample{110U + i * 100U, 10'000U + i * 100'000U};
      phase.origin_status = timing::ClockReadStatus::ok;
      phase.window = calibration::ServiceWindow{
          phase.origin_sample->relative_picoseconds, 100'000U,
          phase.origin_sample->relative_picoseconds + 100'000U,
          phase.origin_sample->relative_picoseconds + 200'000U};
    }
  }
};

TEST(FormalRingPublication, RetainsEightRawStreamsAndAbsentOwnersExplicitly) {
  Fixture fixture;
  fixture.view.producer = {nullptr, nullptr};
  fixture.view.consumer = {nullptr, nullptr};
  ASSERT_TRUE(fixture.publish());
  ASSERT_EQ(fixture.sink.artifacts.size(), 9U);
  for (std::size_t i = 0U; i < 8U; ++i)
    EXPECT_TRUE(fixture.sink.artifacts[i].bytes.empty());
  const auto doc = document(fixture.sink);
  const auto& phase = element(member(doc, "phases"), 0U);
  ASSERT_NE(member(phase, "producer_available").as_bool(), nullptr);
  EXPECT_FALSE(*member(phase, "producer_available").as_bool());
  EXPECT_TRUE(member(phase, "producer_snapshot").is_null());
  EXPECT_TRUE(member(phase, "producer_demand_contract").is_null());
  EXPECT_TRUE(member(member(doc, "native_result_before_publication_returns"), "session")
                  .is_null());
}
TEST(FormalRingPublication, CopiesAllDemandBytesWithoutWindowFiltering) {
  Fixture fixture;
  fixture.set_windows();
  const auto append = [&](std::uint64_t ordinal, std::uint64_t start,
                          std::uint64_t end) {
    return fixture.measurement.producer_demand.append(
        {ordinal,
         calibration::RingAttemptOutcome::full,
         0U,
         {timing::ClockReadStatus::ok, {100U + start / 1000U, start}},
         {timing::ClockReadStatus::ok, {100U + end / 1000U, end}}});
  };
  ASSERT_EQ(append(0U, 209000U, 211000U), storage::AppendStatus::appended);
  ASSERT_EQ(append(1U, 210000U, 210000U), storage::AppendStatus::appended);
  ASSERT_TRUE(fixture.publish());
  ASSERT_EQ(fixture.sink.artifacts.size(), 9U);
  const auto original = fixture.measurement.producer_demand.snapshot();
  const auto& retained = fixture.sink.artifacts[5U].bytes;
  EXPECT_EQ(retained,
            std::vector<std::byte>(original.bytes.begin(), original.bytes.end()));
  EXPECT_EQ(
      read_u64(retained,
               calibration::ring_demand_layout(fixture.measurement.id).prefix_bytes),
      0U);
  const auto doc = document(fixture.sink);
  const auto& measured = element(member(doc, "phases"), 1U);
  EXPECT_EQ(integer(member(member(measured, "producer_demand_snapshot"), "row_count")),
            2U);
  const auto& contract = member(measured, "producer_demand_contract");
  EXPECT_EQ(integer(member(contract, "minimum_observations_per_series")), 1U);
  EXPECT_EQ(integer(member(member(contract, "stream"), "row_count")), 2U);
  EXPECT_EQ(integer(member(member(contract, "phase_window"), "duration_ticks")),
            100000U);
  const auto& warmup = element(member(doc, "phases"), 0U);
  EXPECT_TRUE(member(member(warmup, "producer_demand_contract"),
                     "minimum_observations_per_series")
                  .is_null());
}
TEST(FormalRingPublication, PreservesFailedClockAndIncompletePrefix) {
  Fixture fixture;
  ASSERT_EQ(fixture.warmup.consumer_demand.append(
                {0U,
                 calibration::RingAttemptOutcome::empty,
                 0U,
                 {timing::ClockReadStatus::call_failed, {12U, 34U}},
                 {timing::ClockReadStatus::ok, {15U, 15000U}}}),
            storage::AppendStatus::appended);
  fixture.warmup.consumer_demand.seal_incomplete();
  ASSERT_TRUE(fixture.publish());
  const auto& retained = fixture.sink.artifacts[3U].bytes;
  const auto offset = calibration::ring_demand_layout(fixture.warmup.id).prefix_bytes;
  EXPECT_EQ(read_u64(retained, offset + 24U),
            static_cast<std::uint64_t>(timing::ClockReadStatus::call_failed));
  EXPECT_EQ(read_u64(retained, offset + 32U), 12U);
  EXPECT_EQ(read_u64(retained, offset + 40U), 34U);
  EXPECT_TRUE(member(element(member(document(fixture.sink), "phases"), 0U),
                     "consumer_demand_contract")
                  .is_null());
}
TEST(FormalRingPublication, StopsAtSinkFailureAndRetainsPriorArtifacts) {
  Fixture fixture;
  fixture.sink.fail_at = 3U;
  EXPECT_FALSE(fixture.publish());
  EXPECT_EQ(fixture.sink.calls, 4U);
  EXPECT_EQ(fixture.sink.artifacts.size(), 3U);
}
TEST(FormalRingPublication, NeverInfersFinalCleanupFromPrePublicationState) {
  Fixture fixture;
  ASSERT_TRUE(fixture.publish());
  const auto before = document(fixture.sink);
  EXPECT_FALSE(*member(member(before, "native_result_before_publication_returns"),
                       "publication_succeeded")
                    .as_bool());
  fixture.result.publication_attempted = true;
  fixture.result.publication_succeeded = true;
  fixture.result.stop = calibration::NativeCaptureStop::cleanup_failed;
  const auto after = stage17::formal_ring_capture_result_json(fixture.result);
  EXPECT_EQ(integer(member(after, "stop")),
            static_cast<std::uint64_t>(calibration::NativeCaptureStop::cleanup_failed));
  EXPECT_TRUE(*member(after, "publication_succeeded").as_bool());
  EXPECT_FALSE(*member(before, "inferential_validity_established").as_bool());
}
TEST(FormalRingPublication, RejectsAbsentProspectiveMinimumBeforePublishing) {
  Fixture fixture;
  EXPECT_FALSE(
      stage17::publish_formal_ring_capture(fixture.sink, 7U, 0U, fixture.view));
  EXPECT_TRUE(fixture.sink.artifacts.empty());
}
TEST(FormalRingPublication, PreservesIndependentPrimaryBytesAndExactDemandBindings) {
  Fixture fixture;
  fixture.set_windows();
  const timing::ProducerObservation produced{{0U},
                                             {3U},
                                             110000U,
                                             {210U, 110000U},
                                             {211U, 111000U},
                                             {212U, 112000U},
                                             timing::ClockSample{214U, 114000U},
                                             {215U, 115000U},
                                             protocol::ProducerOutcome::accepted,
                                             workload::AcceptedOrdinal{0U}};
  const timing::ConsumerObservation consumed{
      {0U}, {3U}, {216U, 116000U}, {217U, 117000U}, {218U, 118000U}, {219U, 119000U}};
  ASSERT_EQ(fixture.measurement.producer_stream.append(produced),
            storage::AppendStatus::appended);
  ASSERT_EQ(fixture.measurement.consumer_stream.append(consumed),
            storage::AppendStatus::appended);
  ASSERT_TRUE(fixture.publish());
  const auto producer = fixture.measurement.producer_stream.snapshot();
  const auto consumer = fixture.measurement.consumer_stream.snapshot();
  EXPECT_EQ(fixture.sink.artifacts[4U].bytes,
            std::vector<std::byte>(producer.bytes.begin(), producer.bytes.end()));
  EXPECT_EQ(fixture.sink.artifacts[6U].bytes,
            std::vector<std::byte>(consumer.bytes.begin(), consumer.bytes.end()));
  const auto doc = document(fixture.sink);
  const auto& phase = element(member(doc, "phases"), 1U);
  for (std::size_t i = 0U; i < 2U; ++i) {
    const auto& contract = member(phase, i == 0U ? "producer_demand_contract"
                                                 : "consumer_demand_contract");
    const auto& artifact = fixture.sink.artifacts[5U + i * 2U];
    EXPECT_EQ(*member(contract, "role").as_string(), i == 0U ? "producer" : "consumer");
    EXPECT_EQ(*member(contract, "phase").as_string(), "measurement");
    EXPECT_EQ(*member(contract, "run_id").as_string(), fixture.measurement.id.value());
    const auto& binding = member(contract, "stream");
    EXPECT_EQ(*member(binding, "path").as_string(), artifact.file_name);
    EXPECT_EQ(integer(member(binding, "size_bytes")), artifact.bytes.size());
    EXPECT_EQ(*member(binding, "sha256").as_string(),
              workload::sha256(artifact.bytes).hex());
    const auto& window = member(contract, "phase_window");
    EXPECT_EQ(integer(member(window, "clock_origin_absolute_nanoseconds")), 100U);
    EXPECT_EQ(integer(member(member(window, "phase_origin"), "absolute_nanoseconds")),
              210U);
    EXPECT_EQ(integer(member(member(window, "phase_origin"), "relative_picoseconds")),
              110000U);
  }
}
} // namespace
