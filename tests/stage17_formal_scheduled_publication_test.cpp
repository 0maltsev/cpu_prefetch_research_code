#include "cpu_prefetch/runner/stage17_formal_scheduled_publication.hpp"
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
  Phase warmup{"scheduled-publisher-warmup"};
  Phase measurement{"scheduled-publisher-measurement"};
  MemorySink sink;
  Value::Object prospective{
      {"schedules",
       Value(Value::Array{
           Value(Value::Object{{"schedule_id", Value(std::string("warmup-source"))},
                               {"deadline_ticks", Value(Value::Array{})}}),
           Value(
               Value::Object{{"schedule_id", Value(std::string("measurement-source"))},
                             {"deadline_ticks", Value(Value::Array{})}})})}};
  platform::PrefetchReadbackPreparation hardware{};
  calibration::NativeFormalScheduledCaptureLayout layout{};
  calibration::NativeFormalScheduledCaptureResult result{};
  calibration::NativeFormalScheduledPublicationView view{
      result,
      layout,
      {{}, {}, {}, {}, {}, hardware, {}, {}, {}},
      {&warmup.producer, &measurement.producer},
      {&warmup.consumer, &measurement.consumer},
      nullptr,
      {}};
  auto publish() {
    return stage17::publish_formal_scheduled_capture(sink, 3U, prospective, view);
  }
};
TEST(FormalScheduledPublication, RetainsFourIndependentPrimaryStreams) {
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
  ASSERT_EQ(f.sink.artifacts.size(), 8U);
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
TEST(FormalScheduledPublication, PreparedSchedulesAreNotFabricatedExecution) {
  Fixture f;
  const std::array<std::uint64_t, 3U> deadlines{1000U, 1000U, 0x0102030405060708U};
  f.view.schedules[0U] =
      lifecycle::PreparedScheduleView{deadlines, 1000U, 0x0102030405060709U};
  f.result.session.emplace();
  ASSERT_TRUE(f.publish());
  ASSERT_EQ(f.sink.artifacts.size(), 8U);
  const auto& words = f.sink.artifacts[5U].bytes;
  ASSERT_EQ(words.size(), 24U);
  for (std::size_t i = 0U; i < 3U; ++i)
    EXPECT_EQ(read_u64(words, i * 8U), deadlines[i]);
  auto doc = document(f.sink);
  const auto& source = element(member(doc, "schedules"), 0U);
  EXPECT_TRUE(*member(source, "prepared_available").as_bool());
  EXPECT_FALSE(*member(source, "phase_released").as_bool());
  EXPECT_FALSE(*member(source, "all_arrivals_attempted").as_bool());
  EXPECT_EQ(integer(member(source, "prepared_count")), 3U);
  EXPECT_FALSE(member(source, "prospective").as_object()->contains("deadline_ticks"));
  const auto& absent = element(member(doc, "schedules"), 1U);
  EXPECT_FALSE(*member(absent, "prepared_available").as_bool());
  EXPECT_TRUE(member(absent, "prepared_count").is_null());
  EXPECT_TRUE(f.sink.artifacts[6U].bytes.empty());
  EXPECT_FALSE(*member(doc, "inferential_validity_established").as_bool());
}
TEST(FormalScheduledPublication, RetainsActualReleaseCompletionAndDrainWithoutD211) {
  Fixture f;
  f.result.session.emplace();
  auto& session = *f.result.session;
  session.lifecycle.phases[1U].released = true;
  session.lifecycle.phases[1U].producer.attempted = 3U;
  session.lifecycle.phases[1U].producer.arrivals_finished_published = true;
  session.lifecycle.phases[1U].consumer.consumed = 3U;
  session.schedules[1U].offered = 3U;
  session.schedules[1U].all_arrivals_attempted = true;
  session.schedules[1U].producer_completion =
      timing::ClockReadResult{timing::ClockReadStatus::ok, {200U, 100000U}};
  f.measurement.consumer.retained_consumed = 3U;
  ASSERT_TRUE(f.publish());
  auto doc = document(f.sink);
  EXPECT_TRUE(
      *member(element(member(doc, "schedules"), 1U), "phase_released").as_bool());
  const auto& phase = element(member(doc, "phases"), 1U);
  EXPECT_FALSE(phase.as_object()->contains("completion_interval"));
  EXPECT_EQ(integer(member(phase, "retained_consumed_including_drain")), 3U);
  const auto& result =
      member(member(doc, "native_result_before_publication_returns"), "session");
  EXPECT_EQ(integer(member(
                member(element(member(result, "schedules"), 1U), "producer_completion"),
                "relative_picoseconds")),
            100000U);
}
TEST(FormalScheduledPublication, RetainsUnknownFailureWithoutInventingObservation) {
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
  EXPECT_FALSE(phase.as_object()->contains("completion_interval"));
}
TEST(FormalScheduledPublication, RetainsNodeOrderAsExactUnsignedLittleEndian) {
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
TEST(FormalScheduledPublication, PreservesMissingOwnersAndStopsAtSinkFailure) {
  Fixture f;
  f.view.producer = {nullptr, nullptr};
  f.view.consumer = {nullptr, nullptr};
  ASSERT_TRUE(f.publish());
  EXPECT_EQ(f.sink.artifacts.size(), 8U);
  EXPECT_TRUE(
      member(element(member(document(f.sink), "phases"), 0U), "producer_snapshot")
          .is_null());
  Fixture failed;
  failed.sink.fail_at = 2U;
  EXPECT_FALSE(failed.publish());
  EXPECT_EQ(failed.sink.calls, 3U);
  EXPECT_EQ(failed.sink.artifacts.size(), 2U);
}
TEST(FormalScheduledPublication, FinalCleanupRemainsSeparateEvidence) {
  Fixture f;
  ASSERT_TRUE(f.publish());
  f.result.stop = calibration::NativeCaptureStop::cleanup_failed;
  f.result.publication_succeeded = true;
  const auto result = stage17::formal_scheduled_capture_result_json(f.result);
  EXPECT_EQ(integer(member(result, "stop")),
            static_cast<std::uint64_t>(calibration::NativeCaptureStop::cleanup_failed));
  EXPECT_FALSE(
      *member(member(document(f.sink), "native_result_before_publication_returns"),
              "publication_succeeded")
           .as_bool());
}
} // namespace
