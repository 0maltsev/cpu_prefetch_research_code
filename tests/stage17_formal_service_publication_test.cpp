#include "cpu_prefetch/runner/stage17_formal_service_publication.hpp"
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
  calibration::FormalServiceProducerPhase producer;
  calibration::FormalServiceConsumerPhase consumer;
  explicit Phase(std::string name)
      : id(test_support::discovery_test_run_id(std::move(name))),
        producer_stream(id, 8U), consumer_stream(id, 8U),
        producer{producer_stream, storage::make_row_layout(id.value())},
        consumer{consumer_stream, storage::make_row_layout(id.value()), {17U}, {17U}} {
    if (!producer_stream.prepare_for_owner() || !consumer_stream.prepare_for_owner())
      throw std::logic_error("software fixture primary preparation failed");
  }
};
struct Fixture final {
  Phase warmup{"service-publisher-warmup"};
  Phase measurement{"service-publisher-measurement"};
  MemorySink sink;
  platform::PrefetchReadbackPreparation hardware{};
  calibration::NativeFormalServiceCaptureLayout layout{};
  calibration::NativeFormalServiceCaptureResult result{};
  calibration::NativeFormalServicePublicationView view{
      result,
      layout,
      {{}, {}, {}, {}, {}, hardware, {}, {}, {}},
      {&warmup.producer, &measurement.producer},
      {&warmup.consumer, &measurement.consumer},
      nullptr,
      {}};
  auto publish() { return stage17::publish_formal_service_capture(sink, 3U, view); }
};
TEST(FormalServicePublication, RetainsFourIndependentPrimaryStreams) {
  Fixture f;
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
  for (auto* phase : {&f.warmup, &f.measurement}) {
    ASSERT_EQ(phase->producer_stream.append(produced), storage::AppendStatus::appended);
    ASSERT_EQ(phase->consumer_stream.append(consumed), storage::AppendStatus::appended);
  }
  ASSERT_TRUE(f.publish());
  ASSERT_EQ(f.sink.artifacts.size(), 6U);
  for (std::size_t i = 0U; i < 2U; ++i) {
    const auto* phase = i == 0U ? &f.warmup : &f.measurement;
    const auto producer = phase->producer_stream.snapshot();
    const auto consumer = phase->consumer_stream.snapshot();
    EXPECT_EQ(f.sink.artifacts[i * 2U].bytes,
              std::vector<std::byte>(producer.bytes.begin(), producer.bytes.end()));
    EXPECT_EQ(f.sink.artifacts[i * 2U + 1U].bytes,
              std::vector<std::byte>(consumer.bytes.begin(), consumer.bytes.end()));
  }
  EXPECT_TRUE(f.sink.artifacts[4U].bytes.empty());
}
TEST(FormalServicePublication, KeepsIntervalNumeratorSeparateFromDrainCount) {
  Fixture f;
  f.measurement.consumer.retained_consumed = 3U;
  f.measurement.consumer.interval = calibration::ServiceIntervalResult{
      calibration::ServiceIntervalStatus::complete,
      calibration::ServiceIntervalCounts{{timing::kClockSuiteId,
                                          "PICOSECONDS",
                                          1'000'000'000'000U,
                                          100U,
                                          {210U, 110000U},
                                          100000U},
                                         210000U,
                                         3U,
                                         2U,
                                         1U},
      std::nullopt};
  ASSERT_TRUE(f.publish());
  const auto doc = document(f.sink);
  const auto& phase = element(member(doc, "phases"), 1U);
  EXPECT_EQ(integer(member(phase, "retained_consumed_including_drain")), 3U);
  const auto& counts = member(member(phase, "completion_interval"), "counts");
  EXPECT_EQ(integer(member(counts, "interval_consumed_count")), 2U);
  EXPECT_EQ(integer(member(counts, "outside_interval_consumed_count")), 1U);
  EXPECT_TRUE(
      member(element(member(doc, "phases"), 0U), "completion_interval").is_null());
  EXPECT_FALSE(*member(doc, "inferential_validity_established").as_bool());
}
TEST(FormalServicePublication, RetainsUnknownFailureWithoutInventingObservation) {
  Fixture f;
  f.measurement.consumer.current =
      timing::ConsumerCaptureResult{timing::CaptureStatus::clock_failure,
                                    timing::TimestampBoundary::dequeue_completion,
                                    timing::ClockReadStatus::call_failed,
                                    workload::RecordAccessStatus::valid, std::nullopt};
  f.measurement.consumer.stopped = true;
  f.measurement.consumer_stream.seal_incomplete();
  ASSERT_TRUE(f.publish());
  const auto doc = document(f.sink);
  const auto& phase = element(member(doc, "phases"), 1U);
  EXPECT_TRUE(*member(phase, "consumer_stopped").as_bool());
  const auto& current = member(phase, "consumer_current");
  EXPECT_TRUE(member(current, "observation").is_null());
  EXPECT_EQ(integer(member(current, "failed_boundary")),
            static_cast<std::uint64_t>(timing::TimestampBoundary::dequeue_completion));
  EXPECT_TRUE(member(phase, "completion_interval").is_null());
}
TEST(FormalServicePublication, RetainsNodeOrderAsExactUnsignedLittleEndian) {
  Fixture f;
  const std::array<std::size_t, 3U> order{2U, 0U, 1U};
  f.view.node_order = order;
  ASSERT_TRUE(f.publish());
  const auto& bytes = f.sink.artifacts[4U].bytes;
  ASSERT_EQ(bytes.size(), 24U);
  EXPECT_EQ(read_u64(bytes, 0U), 2U);
  EXPECT_EQ(read_u64(bytes, 8U), 0U);
  EXPECT_EQ(read_u64(bytes, 16U), 1U);
  EXPECT_EQ(integer(member(document(f.sink), "node_order_count")), 3U);
}
TEST(FormalServicePublication, PreservesMissingOwnersAndStopsAtSinkFailure) {
  Fixture f;
  f.view.producer = {nullptr, nullptr};
  f.view.consumer = {nullptr, nullptr};
  ASSERT_TRUE(f.publish());
  EXPECT_EQ(f.sink.artifacts.size(), 6U);
  EXPECT_TRUE(
      member(element(member(document(f.sink), "phases"), 0U), "producer_snapshot")
          .is_null());
  Fixture failed;
  failed.sink.fail_at = 2U;
  EXPECT_FALSE(failed.publish());
  EXPECT_EQ(failed.sink.calls, 3U);
  EXPECT_EQ(failed.sink.artifacts.size(), 2U);
}
TEST(FormalServicePublication, FinalCleanupRemainsSeparateEvidence) {
  Fixture f;
  ASSERT_TRUE(f.publish());
  f.result.stop = calibration::NativeCaptureStop::cleanup_failed;
  f.result.publication_succeeded = true;
  const auto result = stage17::formal_service_capture_result_json(f.result);
  EXPECT_EQ(integer(member(result, "stop")),
            static_cast<std::uint64_t>(calibration::NativeCaptureStop::cleanup_failed));
  EXPECT_FALSE(
      *member(member(document(f.sink), "native_result_before_publication_returns"),
              "publication_succeeded")
           .as_bool());
}
} // namespace
