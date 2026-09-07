#include <gtest/gtest.h>

#include "cpu_prefetch/queue/ring_spsc.hpp"
#include "cpu_prefetch/storage/artifact_store.hpp"
#include "cpu_prefetch/storage/artifacts.hpp"
#include "cpu_prefetch/storage/budget.hpp"
#include "cpu_prefetch/storage/capture_backend.hpp"
#include "cpu_prefetch/storage/finalization.hpp"
#include "cpu_prefetch/storage/raw_observations.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"
#include "cpu_prefetch/workload/packages.hpp"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <limits>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unistd.h>
#include <utility>
#include <variant>
#include <vector>

namespace {

namespace protocol = cpu_prefetch::protocol;
namespace storage = cpu_prefetch::storage;
namespace timing = cpu_prefetch::timing;
namespace workload = cpu_prefetch::workload;

auto run_id(std::string text = "r") -> protocol::RunId {
  auto parsed = protocol::RunId::parse(std::move(text), "$test/run_id");
  if (!parsed) {
    throw std::logic_error("invalid test run ID");
  }
  return std::move(parsed).value();
}

auto digest(std::span<const std::byte> bytes) -> std::string {
  return workload::sha256(bytes).hex();
}

auto accepted_observation(std::uint64_t logical_sequence = 0U,
                          std::uint64_t accepted_ordinal = 0U)
    -> timing::ProducerObservation {
  return {workload::LogicalSequence{logical_sequence},
          workload::RecordIndex{7U},
          500U,
          timing::ClockSample{101U, 1000U},
          timing::ClockSample{102U, 2000U},
          timing::ClockSample{103U, 3000U},
          timing::ClockSample{104U, 4000U},
          timing::ClockSample{105U, 5000U},
          protocol::ProducerOutcome::accepted,
          workload::AcceptedOrdinal{accepted_ordinal}};
}

auto full_observation(std::uint64_t logical_sequence = 1U)
    -> timing::ProducerObservation {
  return {workload::LogicalSequence{logical_sequence},
          workload::RecordIndex{8U},
          1500U,
          timing::ClockSample{102U, 2000U},
          timing::ClockSample{103U, 3000U},
          timing::ClockSample{104U, 4000U},
          std::nullopt,
          timing::ClockSample{105U, 5000U},
          protocol::ProducerOutcome::full,
          std::nullopt};
}

auto consumer_observation(std::uint64_t ordinal = 0U) -> timing::ConsumerObservation {
  return {workload::AcceptedOrdinal{ordinal}, workload::RecordIndex{7U},
          timing::ClockSample{105U, 5000U},   timing::ClockSample{106U, 6000U},
          timing::ClockSample{107U, 7000U},   timing::ClockSample{108U, 8000U}};
}

class CaptureSequenceClock final {
public:
  explicit CaptureSequenceClock(std::vector<timing::ClockReadResult> reads)
      : reads_(std::move(reads)) {}

  [[nodiscard]] auto read() noexcept -> timing::ClockReadResult {
    if (position_ >= reads_.size()) {
      return {timing::ClockReadStatus::call_failed, {0U, 0U}};
    }
    return reads_[position_++];
  }

private:
  std::vector<timing::ClockReadResult> reads_;
  std::size_t position_{0U};
};

auto test_seed() -> workload::MasterSeed {
  return workload::MasterSeed::from_hex("000102030405060708090a0b0c0d0e0f"
                                        "101112131415161718191a1b1c1d1e1f");
}

auto joined_record(const protocol::RunId& id) -> protocol::JoinedRecord {
  return {id,    0U,    0U,    7U,    0U,    0U,    500U,  1000U, 2000U,
          3000U, 4000U, 5000U, 5000U, 6000U, 7000U, 8000U, 500U,  1000U,
          2000U, 3500U, 2000U, 2000U, 2000U, 1000U, 7500U};
}

auto external_envelope(protocol::StreamKind kind, std::string_view id,
                       std::span<const std::byte> bytes, std::uint64_t rows,
                       std::vector<storage::ArtifactRefText> sources = {})
    -> storage::RawEnvelopeDocument {
  auto result = storage::make_external_raw_envelope(
      {"raw-artifact-" + std::string(id),
       std::string(id),
       kind,
       "/immutable/raw",
       rows,
       static_cast<std::uint64_t>(bytes.size()),
       digest(bytes),
       {"integrity-artifact", std::string(64U, '1')},
       std::move(sources)});
  if (!result) {
    throw std::logic_error("test raw envelope failed");
  }
  return std::move(result).value();
}

class TempDomains final {
public:
  TempDomains() {
    static std::atomic<std::uint64_t> next{0U};
    root_ = std::filesystem::temp_directory_path() /
            ("cpu-prefetch-stage11-test-" + std::to_string(::getpid()) + "-" +
             std::to_string(next.fetch_add(1U, std::memory_order_relaxed)));
    std::filesystem::create_directories(root_ / "domain-a");
    std::filesystem::create_directories(root_ / "domain-b");
  }

  ~TempDomains() {
    std::error_code error;
    std::filesystem::remove_all(root_, error);
  }

  [[nodiscard]] auto domains() const -> std::vector<storage::LocalStorageDomain> {
    return {{"domain-a", root_ / "domain-a"}, {"domain-b", root_ / "domain-b"}};
  }

private:
  std::filesystem::path root_;
};

auto store_config(const TempDomains& temporary,
                  storage::PublicationFaultPlan fault = {})
    -> storage::LocalRunStoreConfig {
  return {"storage-run", "2026-08-21T00:00:00Z", temporary.domains(), fault};
}

TEST(StorageFormat, AcceptedGoldenProducerConsumerAndJoinedVectorsMatch) {
  const auto id = run_id();
  storage::ProducerObservationStream producer(id, 2U);
  ASSERT_TRUE(producer.prepare_for_owner());
  EXPECT_EQ(producer.append(accepted_observation()), storage::AppendStatus::appended);
  EXPECT_EQ(producer.append(full_observation()), storage::AppendStatus::appended);
  ASSERT_TRUE(producer.seal_complete());
  const auto producer_snapshot = producer.snapshot();
  EXPECT_EQ(producer_snapshot.row_count, 2U);
  EXPECT_EQ(producer_snapshot.bytes.size(), 256U);
  EXPECT_EQ(digest(producer_snapshot.bytes),
            "c6b47e3a4e73fa26e913ccd9101bd68e72bc3de4a488c3e3332fc65c7c61787c");
  EXPECT_EQ(reinterpret_cast<std::uintptr_t>(producer.buffer_address()) % 64U, 0U);

  storage::ConsumerObservationStream consumer(id, 1U);
  ASSERT_TRUE(consumer.prepare_for_owner());
  EXPECT_EQ(consumer.append(consumer_observation()), storage::AppendStatus::appended);
  ASSERT_TRUE(consumer.seal_complete());
  const auto consumer_snapshot = consumer.snapshot();
  EXPECT_EQ(consumer_snapshot.bytes.size(), 88U);
  EXPECT_EQ(digest(consumer_snapshot.bytes),
            "0ed5a56f76a293b344eca47c684558d7fe6e46cebffd06981a446fd2c667a888");
  EXPECT_EQ(reinterpret_cast<std::uintptr_t>(consumer.buffer_address()) % 64U, 0U);

  const std::array joined{joined_record(id)};
  const auto joined_bytes = storage::encode_joined_rows_for_format_test(id, joined);
  EXPECT_EQ(joined_bytes.size(), 200U);
  EXPECT_EQ(digest(joined_bytes),
            "f02f4b2bc4a035dba7b9d5e91bb38a20aa2d309c19d81f49b9054aad9bc28f2a");

  auto producer_envelope = external_envelope(protocol::StreamKind::producer, "r",
                                             producer_snapshot.bytes, 2U);
  auto decoded_producer =
      storage::decode_external_raw(producer_envelope.envelope, producer_snapshot.bytes);
  ASSERT_TRUE(decoded_producer) << decoded_producer.errors().front().message;
  const auto& producer_rows =
      std::get<std::vector<storage::DecodedProducerRow>>(decoded_producer.value().rows);
  ASSERT_EQ(producer_rows.size(), 2U);
  const auto& linearization = producer_rows[0].observation.enqueue_linearization;
  if (!linearization.has_value()) {
    FAIL() << "accepted producer row lost enqueue linearization";
    return;
  }
  EXPECT_EQ(linearization->absolute_nanoseconds, 104U);
  EXPECT_EQ(producer_rows[1].observation.outcome, protocol::ProducerOutcome::full);
  EXPECT_FALSE(producer_rows[1].observation.accepted_ordinal.has_value());

  auto consumer_envelope = external_envelope(protocol::StreamKind::consumer, "r",
                                             consumer_snapshot.bytes, 1U);
  auto decoded_consumer =
      storage::decode_external_raw(consumer_envelope.envelope, consumer_snapshot.bytes);
  ASSERT_TRUE(decoded_consumer) << decoded_consumer.errors().front().message;
  EXPECT_EQ(std::get<std::vector<storage::DecodedConsumerRow>>(
                decoded_consumer.value().rows)[0]
                .observation.consumer_action_completion.absolute_nanoseconds,
            108U);

  auto joined_envelope = external_envelope(
      protocol::StreamKind::joined_derived, "r", joined_bytes, 1U,
      {{"producer", std::string(64U, '2')}, {"consumer", std::string(64U, '3')}});
  auto decoded_joined =
      storage::decode_external_raw(joined_envelope.envelope, joined_bytes);
  ASSERT_TRUE(decoded_joined) << decoded_joined.errors().front().message;
  EXPECT_EQ(
      std::get<std::vector<protocol::JoinedRecord>>(decoded_joined.value().rows)[0]
          .end_to_end_latency,
      7500U);
}

TEST(StorageFormat, ExactCapacityZeroRowsAndOverflowFailClosed) {
  const auto id = run_id("capacity-run");
  storage::ProducerObservationStream producer(id, 1U);
  ASSERT_TRUE(producer.prepare_for_owner());
  EXPECT_EQ(producer.append(accepted_observation()), storage::AppendStatus::appended);
  const auto before_overflow = std::vector<std::byte>(producer.snapshot().bytes.begin(),
                                                      producer.snapshot().bytes.end());
  EXPECT_EQ(producer.append(full_observation()),
            storage::AppendStatus::buffer_overflow);
  const auto snapshot = producer.snapshot();
  EXPECT_EQ(snapshot.row_count, 1U);
  EXPECT_TRUE(snapshot.overflowed);
  EXPECT_EQ(snapshot.completeness, storage::StreamCompleteness::sealed_incomplete);
  EXPECT_EQ(std::vector<std::byte>(snapshot.bytes.begin(), snapshot.bytes.end()),
            before_overflow);
  EXPECT_FALSE(producer.seal_complete());

  storage::ConsumerObservationStream empty(id, 0U);
  ASSERT_TRUE(empty.prepare_for_owner());
  ASSERT_TRUE(empty.seal_complete());
  EXPECT_TRUE(empty.snapshot().bytes.empty());
  EXPECT_EQ(digest(empty.snapshot().bytes),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  auto envelope = external_envelope(protocol::StreamKind::consumer, "capacity-run",
                                    empty.snapshot().bytes, 0U);
  EXPECT_TRUE(storage::decode_external_raw(envelope.envelope, empty.snapshot().bytes));
}

TEST(StorageFormat, CorruptionCountsVersionsAndOrderingAreRejected) {
  const auto id = run_id();
  storage::ProducerObservationStream producer(id, 2U);
  ASSERT_TRUE(producer.prepare_for_owner());
  ASSERT_EQ(producer.append(accepted_observation()), storage::AppendStatus::appended);
  ASSERT_EQ(producer.append(full_observation()), storage::AppendStatus::appended);
  ASSERT_TRUE(producer.seal_complete());
  const auto original = producer.snapshot();

  auto envelope =
      external_envelope(protocol::StreamKind::producer, "r", original.bytes, 2U);
  auto bad_format = envelope.envelope;
  bad_format.encoding = "UNKNOWN";
  EXPECT_FALSE(storage::decode_external_raw(bad_format, original.bytes));
  auto unknown_id = protocol::RecordId::parse("UNKNOWN-FORMAT", "$test/format");
  ASSERT_TRUE(unknown_id);
  bad_format = envelope.envelope;
  bad_format.physical_format_record_id = std::move(unknown_id).value();
  EXPECT_FALSE(storage::decode_external_raw(bad_format, original.bytes));
  auto bad_endianness = envelope.envelope;
  bad_endianness.endianness = protocol::Endianness::big_endian;
  EXPECT_FALSE(storage::decode_external_raw(bad_endianness, original.bytes));
  auto bad_count = envelope.envelope;
  bad_count.row_count = 1U;
  EXPECT_FALSE(storage::decode_external_raw(bad_count, original.bytes));
  auto bad_bytes = envelope.envelope;
  ++bad_bytes.byte_count;
  EXPECT_FALSE(storage::decode_external_raw(bad_bytes, original.bytes));
  EXPECT_FALSE(storage::decode_external_raw(
      envelope.envelope, original.bytes.first(original.bytes.size() - 1U)));

  auto padding = std::vector<std::byte>(original.bytes.begin(), original.bytes.end());
  padding[5U] = std::byte{1U};
  auto padding_envelope =
      external_envelope(protocol::StreamKind::producer, "r", padding, 2U);
  EXPECT_FALSE(storage::decode_external_raw(padding_envelope.envelope, padding));

  auto flags = std::vector<std::byte>(original.bytes.begin(), original.bytes.end());
  constexpr std::size_t flags_offset = 8U + 14U * sizeof(std::uint64_t);
  flags[flags_offset] = std::byte{3U};
  auto flags_envelope =
      external_envelope(protocol::StreamKind::producer, "r", flags, 2U);
  EXPECT_FALSE(storage::decode_external_raw(flags_envelope.envelope, flags));

  auto reordered = std::vector<std::byte>(original.bytes.begin(), original.bytes.end());
  constexpr std::size_t second_logical_sequence = 128U + 8U;
  reordered[second_logical_sequence] = std::byte{7U};
  auto reordered_envelope =
      external_envelope(protocol::StreamKind::producer, "r", reordered, 2U);
  EXPECT_FALSE(storage::decode_external_raw(reordered_envelope.envelope, reordered));
}

TEST(StorageFormat, InvalidObservationAndLogicalTimestampOrderAreRejected) {
  const auto id = run_id();
  storage::ProducerObservationStream producer(id, 1U);
  EXPECT_EQ(producer.append(accepted_observation()),
            storage::AppendStatus::stream_unprepared);
  ASSERT_TRUE(producer.prepare_for_owner());
  auto invalid = accepted_observation();
  invalid.accepted_ordinal = std::nullopt;
  EXPECT_EQ(producer.append(invalid), storage::AppendStatus::invalid_observation);
  auto bad_order = accepted_observation();
  bad_order.producer_handle_begin.relative_picoseconds = 0U;
  ASSERT_EQ(producer.append(bad_order), storage::AppendStatus::appended);
  ASSERT_TRUE(producer.seal_complete());
  auto envelope = external_envelope(protocol::StreamKind::producer, "r",
                                    producer.snapshot().bytes, 1U);
  EXPECT_FALSE(
      storage::decode_external_raw(envelope.envelope, producer.snapshot().bytes));
}

TEST(StorageCaptureBackend, CompleteCaptureCommitsIndependentRowsBeforeReporting) {
  const auto id = run_id("capture-run");
  workload::EventArena arena({2U, 64U, 4096U, test_seed(), "storage-capture"});
  cpu_prefetch::queue::RingSpscQueue queue({1U}, {64U});
  workload::R0Package package(queue);
  workload::ConsumerState state{1U};
  storage::ProducerObservationStream producer(id, 2U);
  storage::ConsumerObservationStream consumer(id, 1U);
  ASSERT_TRUE(producer.prepare_for_owner());
  ASSERT_TRUE(consumer.prepare_for_owner());
  CaptureSequenceClock clock({
      {timing::ClockReadStatus::ok, {1U, 1000U}},
      {timing::ClockReadStatus::ok, {2U, 2000U}},
      {timing::ClockReadStatus::ok, {3U, 3000U}},
      {timing::ClockReadStatus::ok, {4U, 4000U}},
      {timing::ClockReadStatus::ok, {5U, 5000U}},
      {timing::ClockReadStatus::ok, {6U, 6000U}},
      {timing::ClockReadStatus::ok, {7U, 7000U}},
      {timing::ClockReadStatus::ok, {8U, 8000U}},
      {timing::ClockReadStatus::ok, {9U, 9000U}},
      {timing::ClockReadStatus::ok, {10U, 10'000U}},
      {timing::ClockReadStatus::ok, {11U, 11'000U}},
      {timing::ClockReadStatus::ok, {12U, 12'000U}},
      {timing::ClockReadStatus::ok, {13U, 13'000U}},
  });
  storage::CapturingObservationBackend backend(clock, arena, package, state, producer,
                                               consumer);
  const auto accepted = backend.try_producer_attempt({0U, 0U, 0U});
  const auto full = backend.try_producer_attempt({1U, 1U, 1U});
  const auto consumed = backend.try_consumer_poll(0U);
  EXPECT_EQ(accepted.status, cpu_prefetch::lifecycle::AttemptStatus::complete);
  EXPECT_EQ(accepted.outcome, cpu_prefetch::queue::EnqueueResult::accepted);
  EXPECT_EQ(full.status, cpu_prefetch::lifecycle::AttemptStatus::complete);
  EXPECT_EQ(full.outcome, cpu_prefetch::queue::EnqueueResult::full);
  EXPECT_EQ(consumed.status, cpu_prefetch::lifecycle::ConsumerPollStatus::item);
  EXPECT_EQ(producer.snapshot().row_count, 2U);
  EXPECT_EQ(consumer.snapshot().row_count, 1U);
}

TEST(StorageCaptureBackend, OverflowBecomesMeasurementFailureAfterExactCapture) {
  const auto id = run_id("capture-overflow");
  workload::EventArena arena({2U, 64U, 4096U, test_seed(), "storage-overflow"});
  cpu_prefetch::queue::RingSpscQueue queue({1U}, {64U});
  workload::R0Package package(queue);
  workload::ConsumerState state{1U};
  storage::ProducerObservationStream producer(id, 0U);
  storage::ConsumerObservationStream consumer(id, 1U);
  ASSERT_TRUE(producer.prepare_for_owner());
  ASSERT_TRUE(consumer.prepare_for_owner());
  CaptureSequenceClock clock({
      {timing::ClockReadStatus::ok, {1U, 1000U}},
      {timing::ClockReadStatus::ok, {2U, 2000U}},
      {timing::ClockReadStatus::ok, {3U, 3000U}},
      {timing::ClockReadStatus::ok, {4U, 4000U}},
      {timing::ClockReadStatus::ok, {5U, 5000U}},
  });
  storage::CapturingObservationBackend backend(clock, arena, package, state, producer,
                                               consumer);
  const auto result = backend.try_producer_attempt({0U, 0U, 0U});
  EXPECT_EQ(result.status, cpu_prefetch::lifecycle::AttemptStatus::failure);
  EXPECT_TRUE(producer.snapshot().overflowed);
  EXPECT_EQ(producer.snapshot().row_count, 0U);
}

TEST(StorageArtifacts, IntegrityAndImportedRawEnvelopeAreCanonicalAndBound) {
  const std::array<std::byte, 1> value{std::byte{7U}};
  const auto checksum = workload::sha256(value);
  auto report = storage::make_phase_integrity_document(
      {"integrity", "run", workload::ConsumerState{0x12U}, checksum, checksum, checksum,
       checksum});
  ASSERT_TRUE(report);
  EXPECT_FALSE(report.value().bytes.empty());
  EXPECT_NE(report.value().bytes.back(), '\n');
  EXPECT_EQ(report.value().sha256,
            digest(std::span<const std::byte>(
                reinterpret_cast<const std::byte*>(report.value().bytes.data()),
                report.value().bytes.size())));
  EXPECT_NE(report.value().bytes.find("0012"), std::string::npos);
  EXPECT_NE(report.value().bytes.find("content_checksum_match\":true"),
            std::string::npos);

  const auto empty_sha = digest(std::span<const std::byte>{});
  auto envelope =
      storage::make_external_raw_envelope({"raw",
                                           "run",
                                           protocol::StreamKind::consumer,
                                           "/raw",
                                           0U,
                                           0U,
                                           empty_sha,
                                           {"integrity", report.value().sha256},
                                           {}});
  ASSERT_TRUE(envelope);
  EXPECT_EQ(envelope.value().envelope.byte_count, 0U);
  EXPECT_EQ(envelope.value().envelope.physical_format_record_id.value(),
            storage::kRawFormatId);
  EXPECT_NE(envelope.value().document.bytes.find("EXTERNAL_IMMUTABLE_ARTIFACT"),
            std::string::npos);

  auto inconsistent_ledger = storage::make_copy_ledger_document(
      {"ledger",
       "run",
       "object",
       "RAW",
       "raw",
       0U,
       empty_sha,
       storage::StreamCompleteness::sealed_complete,
       storage::CopyFinalizationState::sealed_complete,
       {{"domain-a", "/a", 1U, empty_sha, "2026-08-21T00:00:00Z", true, true},
        {"domain-b", "/b", 0U, empty_sha, "2026-08-21T00:00:01Z", true, true}},
       {}});
  ASSERT_FALSE(inconsistent_ledger);
  EXPECT_EQ(inconsistent_ledger.errors().front().rule_id,
            "STO-LEDGER-VERIFIED-IDENTITY");
}

TEST(StorageBudget, CheckedExactFormulasTailBoundsAndStageACounts) {
  auto run = storage::checked_run_storage_budget({"r", 10U, 7U, 200'000U}, 4096U);
  ASSERT_FALSE(run);
  EXPECT_EQ(run.errors().front().rule_id, "STO-NEFF-BOUND");

  run = storage::checked_run_storage_budget({"r", 10U, 7U, 7U}, 4096U);
  ASSERT_TRUE(run);
  EXPECT_EQ(run.value().producer_row_bytes, 128U);
  EXPECT_EQ(run.value().consumer_row_bytes, 88U);
  EXPECT_EQ(run.value().joined_row_bytes, 200U);
  EXPECT_EQ(run.value().actual_hot_payload_bytes, 10U * 128U + 7U * 88U);
  EXPECT_EQ(run.value().conservative_hot_payload_bytes, 10U * (128U + 88U));
  EXPECT_EQ(run.value().raw_storage_bytes,
            3U * (10U * 128U + 7U * 88U) + 2U * 7U * 200U);
  EXPECT_EQ(run.value().producer_mapped_bytes, 4096U);
  EXPECT_EQ(run.value().consumer_mapped_bytes, 4096U);
  EXPECT_FALSE(run.value().primary_tail_count_possible);

  storage::StageAStorageBudgetRequest request;
  request.r_total = 1U;
  request.block_count = 1U;
  request.verified_base_page_bytes = 4096U;
  request.auxiliary = {1U, 2U, 3U, 4U, 5U, 6U, 7U};
  request.available_bytes = std::numeric_limits<std::uint64_t>::max();
  for (std::uint64_t index = 0U; index < 180U; ++index) {
    request.runs.push_back({"run-" + std::to_string(index), 1U, 1U, std::nullopt});
  }
  auto plan = storage::checked_stage_a_storage_budget(request);
  ASSERT_TRUE(plan);
  EXPECT_EQ(plan.value().run_count, 180U);
  EXPECT_EQ(plan.value().temporary_raw_copies, 1U);
  EXPECT_EQ(plan.value().durable_raw_copies, 2U);
  EXPECT_TRUE(plan.value().capacity_pass);
  request.available_bytes = 1U;
  plan = storage::checked_stage_a_storage_budget(request);
  ASSERT_TRUE(plan);
  EXPECT_FALSE(plan.value().capacity_pass);
  request.runs.pop_back();
  EXPECT_FALSE(storage::checked_stage_a_storage_budget(request));
}

TEST(StorageBudget, OverflowAndImpossibleCountsFail) {
  EXPECT_FALSE(storage::checked_run_storage_budget({"r", 1U, 2U, std::nullopt}, 4096U));
  EXPECT_FALSE(storage::checked_run_storage_budget(
      {"r", std::numeric_limits<std::uint64_t>::max(), 0U, std::nullopt}, 4096U));
  EXPECT_FALSE(storage::checked_run_storage_budget({"r", 1U, 1U, std::nullopt}, 0U));
}

TEST(StorageStore, TwoCopiesAreReadBackAndDuplicateObjectCannotOverwrite) {
  TempDomains temporary;
  storage::LocalAppendOnlyRunStore store(store_config(temporary));
  const std::array<std::byte, 4> bytes{std::byte{1U}, std::byte{2U}, std::byte{3U},
                                       std::byte{4U}};
  const auto sha = digest(bytes);
  auto result = store.publish({"object", "PRODUCER_RAW", "artifact", "ledger-1", bytes,
                               sha, storage::StreamCompleteness::sealed_complete});
  ASSERT_TRUE(result);
  EXPECT_EQ(result.value().finalization_state,
            storage::CopyFinalizationState::sealed_complete);
  ASSERT_EQ(result.value().copies.size(), 2U);
  EXPECT_NE(result.value().copies[0].storage_domain_id,
            result.value().copies[1].storage_domain_id);
  EXPECT_TRUE(result.value().copies[0].verified);
  EXPECT_TRUE(result.value().copies[1].verified);
  EXPECT_TRUE(result.value().ledger_persisted);

  auto duplicate =
      store.publish({"object", "PRODUCER_RAW", "artifact", "ledger-2", bytes, sha,
                     storage::StreamCompleteness::sealed_complete});
  ASSERT_FALSE(duplicate);
  EXPECT_EQ(duplicate.errors().front().rule_id, "STO-DUPLICATE-OBJECT-ID");
  auto duplicate_artifact =
      store.publish({"another-object", "PRODUCER_RAW", "artifact", "ledger-3", bytes,
                     sha, storage::StreamCompleteness::sealed_complete});
  ASSERT_FALSE(duplicate_artifact);
  EXPECT_EQ(duplicate_artifact.errors().front().rule_id, "STO-DUPLICATE-ARTIFACT-ID");

  auto wrong_checksum = store.publish(
      {"wrong-checksum", "PRODUCER_RAW", "wrong-artifact", "ledger-4", bytes,
       std::string(64U, '0'), storage::StreamCompleteness::sealed_complete});
  ASSERT_TRUE(wrong_checksum);
  EXPECT_TRUE(wrong_checksum.value().copies.empty());
  EXPECT_EQ(wrong_checksum.value().finalization_state,
            storage::CopyFinalizationState::incomplete);
}

TEST(StorageStore, PartialWriteAndReadbackMismatchRemainIncomplete) {
  const std::array<std::byte, 16> bytes{};
  const auto sha = digest(bytes);
  {
    TempDomains temporary;
    storage::LocalAppendOnlyRunStore store(store_config(
        temporary, {storage::PublicationFaultPoint::storage_exhausted, 0U, 0U}));
    auto result = store.publish({"full-device", "RAW", "artifact", "ledger", bytes, sha,
                                 storage::StreamCompleteness::sealed_complete});
    ASSERT_TRUE(result);
    EXPECT_EQ(result.value().finalization_state,
              storage::CopyFinalizationState::incomplete);
    EXPECT_TRUE(result.value().copies.empty());
    ASSERT_FALSE(result.value().failures.empty());
    EXPECT_NE(result.value().failures.front().find("ENOSPC"), std::string::npos);
  }
  {
    TempDomains temporary;
    storage::LocalAppendOnlyRunStore store(store_config(
        temporary, {storage::PublicationFaultPoint::partial_staging_write, 0U, 5U}));
    auto result = store.publish({"partial", "RAW", "artifact", "ledger", bytes, sha,
                                 storage::StreamCompleteness::sealed_complete});
    ASSERT_TRUE(result);
    EXPECT_EQ(result.value().finalization_state,
              storage::CopyFinalizationState::incomplete);
    EXPECT_TRUE(result.value().copies.empty());
    const auto recovery = store.recover_staging(0U, "partial", bytes.size(), sha);
    EXPECT_FALSE(recovery.promoted);
    EXPECT_FALSE(recovery.failure.empty());
  }
  {
    TempDomains temporary;
    storage::LocalAppendOnlyRunStore store(store_config(
        temporary, {storage::PublicationFaultPoint::readback_mismatch, 1U, 0U}));
    auto result = store.publish({"mismatch", "RAW", "artifact", "ledger", bytes, sha,
                                 storage::StreamCompleteness::sealed_complete});
    ASSERT_TRUE(result);
    EXPECT_EQ(result.value().finalization_state,
              storage::CopyFinalizationState::incomplete);
    ASSERT_EQ(result.value().copies.size(), 2U);
    EXPECT_FALSE(result.value().copies[1].verified);
  }
}

TEST(StorageStore, SyncedStagingCanBePromotedOnlyWithExactIdentity) {
  TempDomains temporary;
  const std::array<std::byte, 8> bytes{std::byte{9U}};
  const auto sha = digest(bytes);
  {
    storage::LocalAppendOnlyRunStore interrupted(store_config(
        temporary, {storage::PublicationFaultPoint::after_staging_sync, 0U, 0U}));
    auto result =
        interrupted.publish({"recover", "RAW", "artifact", "ledger", bytes, sha,
                             storage::StreamCompleteness::sealed_complete});
    ASSERT_TRUE(result);
    EXPECT_EQ(result.value().finalization_state,
              storage::CopyFinalizationState::incomplete);
  }

  auto recovery_config = store_config(temporary);
  recovery_config.open_mode = storage::RunStoreOpenMode::recover_existing;
  storage::LocalAppendOnlyRunStore recovered_store(std::move(recovery_config));
  EXPECT_FALSE(recovered_store
                   .recover_staging(0U, "recover", bytes.size(), std::string(64U, '0'))
                   .promoted);
  const auto recovered =
      recovered_store.recover_staging(0U, "recover", bytes.size(), sha);
  EXPECT_TRUE(recovered.promoted);
  if (!recovered.copy.has_value()) {
    FAIL() << "recovered staging object has no copy evidence";
    return;
  }
  EXPECT_TRUE(recovered.copy->verified);
  const auto again = recovered_store.recover_staging(0U, "recover", bytes.size(), sha);
  EXPECT_TRUE(again.already_published);
  EXPECT_FALSE(again.promoted);
  auto forbidden_publish =
      recovered_store.publish({"new-object", "RAW", "new-artifact", "new-ledger", bytes,
                               sha, storage::StreamCompleteness::sealed_complete});
  ASSERT_FALSE(forbidden_publish);
  EXPECT_EQ(forbidden_publish.errors().front().rule_id, "STO-RECOVERY-ONLY");
}

TEST(StorageStore, CrashAfterPrimaryAndLedgerFailurePreserveVerifiedObjects) {
  const std::array<std::byte, 8> bytes{std::byte{5U}};
  const auto sha = digest(bytes);
  {
    TempDomains temporary;
    storage::LocalAppendOnlyRunStore store(store_config(
        temporary, {storage::PublicationFaultPoint::after_primary_publish, 0U, 0U}));
    auto result = store.publish({"primary", "RAW", "artifact", "ledger", bytes, sha,
                                 storage::StreamCompleteness::sealed_complete});
    ASSERT_TRUE(result);
    ASSERT_EQ(result.value().copies.size(), 1U);
    EXPECT_TRUE(result.value().copies[0].verified);
    EXPECT_EQ(result.value().finalization_state,
              storage::CopyFinalizationState::incomplete);
  }
  {
    TempDomains temporary;
    storage::LocalAppendOnlyRunStore store(store_config(
        temporary, {storage::PublicationFaultPoint::before_ledger_write, 0U, 0U}));
    auto result = store.publish({"ledger-fail", "RAW", "artifact", "ledger", bytes, sha,
                                 storage::StreamCompleteness::sealed_complete});
    ASSERT_TRUE(result);
    EXPECT_EQ(result.value().copies.size(), 2U);
    EXPECT_FALSE(result.value().ledger_persisted);
    EXPECT_EQ(result.value().finalization_state,
              storage::CopyFinalizationState::incomplete);
    EXPECT_NE(result.value().ledger.bytes.find("copy ledger persistence failed"),
              std::string::npos);
  }
  {
    TempDomains temporary;
    storage::LocalAppendOnlyRunStore store(store_config(
        temporary, {storage::PublicationFaultPoint::partial_ledger_write, 0U, 9U}));
    auto result = store.publish({"partial-ledger", "RAW", "artifact", "ledger", bytes,
                                 sha, storage::StreamCompleteness::sealed_complete});
    ASSERT_TRUE(result);
    EXPECT_EQ(result.value().copies.size(), 2U);
    EXPECT_FALSE(result.value().ledger_persisted);
    EXPECT_EQ(result.value().finalization_state,
              storage::CopyFinalizationState::incomplete);
    EXPECT_TRUE(std::filesystem::is_empty(store.run_directories().front() / "ledger"));
    EXPECT_FALSE(
        std::filesystem::is_empty(store.run_directories().front() / "ledger-staging"));
  }
}

TEST(StorageFinalization, CompleteIndependentStreamsSealWithoutReconciliation) {
  const auto id = run_id("storage-run");
  storage::ProducerObservationStream producer(id, 1U);
  storage::ConsumerObservationStream consumer(id, 1U);
  ASSERT_TRUE(producer.prepare_for_owner());
  ASSERT_TRUE(consumer.prepare_for_owner());
  ASSERT_EQ(producer.append(accepted_observation()), storage::AppendStatus::appended);
  ASSERT_EQ(consumer.append(consumer_observation()), storage::AppendStatus::appended);
  ASSERT_TRUE(producer.seal_complete());
  ASSERT_TRUE(consumer.seal_complete());
  const auto value = workload::sha256(std::span<const std::byte>{});
  TempDomains temporary;
  storage::LocalAppendOnlyRunStore store(store_config(temporary));
  auto result = storage::finalize_run_observations(
      store,
      {"storage-run",
       true,
       {"integrity-artifact", "storage-run", workload::ConsumerState{1U}, value, value,
        value, value},
       {"integrity-object", "integrity-artifact", "ledger-integrity"},
       storage::RawStreamPublicationPlan{
           producer.snapshot(),
           {"producer-object", "producer-artifact", "ledger-producer"},
           {"producer-envelope-object", "producer-envelope", "ledger-producer-env"}},
       storage::RawStreamPublicationPlan{
           consumer.snapshot(),
           {"consumer-object", "consumer-artifact", "ledger-consumer"},
           {"consumer-envelope-object", "consumer-envelope", "ledger-consumer-env"}}});
  ASSERT_TRUE(result);
  EXPECT_EQ(result.value().finalization_state,
            storage::CopyFinalizationState::sealed_complete);
  EXPECT_TRUE(result.value().failures.empty());
  const auto& published_producer = result.value().producer;
  const auto& published_consumer = result.value().consumer;
  if (!published_producer.has_value() || !published_consumer.has_value()) {
    FAIL() << "complete finalization lost a raw stream";
    return;
  }
  const auto& producer_envelope = published_producer->envelope_document;
  const auto& consumer_envelope = published_consumer->envelope_document;
  if (!producer_envelope.has_value() || !consumer_envelope.has_value()) {
    FAIL() << "complete finalization lost a raw envelope";
    return;
  }
  EXPECT_TRUE(storage::decode_external_raw(producer_envelope->envelope,
                                           producer.snapshot().bytes));
  EXPECT_TRUE(storage::decode_external_raw(consumer_envelope->envelope,
                                           consumer.snapshot().bytes));
}

TEST(StorageFinalization, PartialFailurePreservesExistingStreamAndFabricatesNone) {
  const auto id = run_id("storage-run");
  storage::ProducerObservationStream producer(id, 2U);
  ASSERT_TRUE(producer.prepare_for_owner());
  ASSERT_EQ(producer.append(accepted_observation()), storage::AppendStatus::appended);
  producer.seal_incomplete();
  const auto value = workload::sha256(std::span<const std::byte>{});
  TempDomains temporary;
  storage::LocalAppendOnlyRunStore store(store_config(temporary));
  auto result = storage::finalize_run_observations(
      store,
      {"storage-run",
       false,
       {"integrity-artifact", "storage-run", workload::ConsumerState{1U}, value, value,
        value, value},
       {"integrity-object", "integrity-artifact", "ledger-integrity"},
       storage::RawStreamPublicationPlan{
           producer.snapshot(),
           {"producer-object", "producer-artifact", "ledger-producer"},
           {"producer-envelope-object", "producer-envelope", "ledger-producer-env"}},
       std::nullopt});
  ASSERT_TRUE(result);
  EXPECT_EQ(result.value().finalization_state,
            storage::CopyFinalizationState::incomplete);
  EXPECT_TRUE(result.value().producer.has_value());
  EXPECT_FALSE(result.value().consumer.has_value());
  EXPECT_FALSE(result.value().failures.empty());
}

TEST(StorageStore, DuplicateRunDirectoryAndSameDomainAreRejected) {
  TempDomains temporary;
  storage::LocalAppendOnlyRunStore store(store_config(temporary));
  EXPECT_THROW(storage::LocalAppendOnlyRunStore duplicate(store_config(temporary)),
               storage::StorageSetupError);
  auto invalid = store_config(temporary);
  invalid.run_id = "another-run";
  invalid.domains[1].root = invalid.domains[0].root;
  EXPECT_THROW(storage::LocalAppendOnlyRunStore duplicate(std::move(invalid)),
               storage::StorageSetupError);
}

} // namespace
