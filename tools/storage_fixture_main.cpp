#include "cpu_prefetch/storage/artifacts.hpp"
#include "cpu_prefetch/storage/raw_observations.hpp"

#include <array>
#include <cstddef>
#include <filesystem>
#include <fstream>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

namespace protocol = cpu_prefetch::protocol;
namespace storage = cpu_prefetch::storage;
namespace timing = cpu_prefetch::timing;
namespace workload = cpu_prefetch::workload;

auto run_id() -> protocol::RunId {
  auto parsed = protocol::RunId::parse("r", "$fixture/run_id");
  if (!parsed) {
    throw std::runtime_error("fixture run ID is invalid");
  }
  return std::move(parsed).value();
}

void write_bytes(const std::filesystem::path& path, std::span<const std::byte> bytes) {
  std::ofstream output(path, std::ios::binary | std::ios::trunc);
  output.write(reinterpret_cast<const char*>(bytes.data()),
               static_cast<std::streamsize>(bytes.size()));
  if (!output) {
    throw std::runtime_error("fixture byte write failed");
  }
}

void write_text(const std::filesystem::path& path, std::string_view text) {
  std::ofstream output(path, std::ios::binary | std::ios::trunc);
  output.write(text.data(), static_cast<std::streamsize>(text.size()));
  if (!output) {
    throw std::runtime_error("fixture text write failed");
  }
}

auto envelope(protocol::StreamKind kind, std::string artifact_id, std::string uri,
              std::span<const std::byte> bytes, std::uint64_t row_count,
              std::vector<storage::ArtifactRefText> sources = {})
    -> storage::RawEnvelopeDocument {
  auto result =
      storage::make_external_raw_envelope({std::move(artifact_id),
                                           "r",
                                           kind,
                                           std::move(uri),
                                           row_count,
                                           static_cast<std::uint64_t>(bytes.size()),
                                           workload::sha256(bytes).hex(),
                                           {"fixture-integrity", std::string(64U, '1')},
                                           std::move(sources)});
  if (!result) {
    throw std::runtime_error(result.errors().front().message);
  }
  return std::move(result).value();
}

auto joined_record(const protocol::RunId& id) -> protocol::JoinedRecord {
  return {id,    0U,    0U,    7U,    0U,    0U,    500U,  1000U, 2000U,
          3000U, 4000U, 5000U, 5000U, 6000U, 7000U, 8000U, 500U,  1000U,
          2000U, 3500U, 2000U, 2000U, 2000U, 1000U, 7500U};
}

} // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    return 2;
  }
  try {
    const std::filesystem::path output_directory(argv[1]);
    std::filesystem::create_directories(output_directory);
    const auto id = run_id();
    storage::ProducerObservationStream producer(id, 2U);
    if (!producer.prepare_for_owner()) {
      return 3;
    }
    const timing::ProducerObservation accepted{workload::LogicalSequence{0U},
                                               workload::RecordIndex{7U},
                                               500U,
                                               {101U, 1000U},
                                               {102U, 2000U},
                                               {103U, 3000U},
                                               timing::ClockSample{104U, 4000U},
                                               {105U, 5000U},
                                               protocol::ProducerOutcome::accepted,
                                               workload::AcceptedOrdinal{0U}};
    const timing::ProducerObservation full{workload::LogicalSequence{1U},
                                           workload::RecordIndex{8U},
                                           1500U,
                                           {102U, 2000U},
                                           {103U, 3000U},
                                           {104U, 4000U},
                                           std::nullopt,
                                           {105U, 5000U},
                                           protocol::ProducerOutcome::full,
                                           std::nullopt};
    if (producer.append(accepted) != storage::AppendStatus::appended ||
        producer.append(full) != storage::AppendStatus::appended ||
        !producer.seal_complete()) {
      return 3;
    }

    storage::ConsumerObservationStream consumer(id, 1U);
    if (!consumer.prepare_for_owner()) {
      return 4;
    }
    const timing::ConsumerObservation consumed{workload::AcceptedOrdinal{0U},
                                               workload::RecordIndex{7U},
                                               {105U, 5000U},
                                               {106U, 6000U},
                                               {107U, 7000U},
                                               {108U, 8000U}};
    if (consumer.append(consumed) != storage::AppendStatus::appended ||
        !consumer.seal_complete()) {
      return 4;
    }
    const std::array joined{joined_record(id)};
    const auto joined_bytes = storage::encode_joined_rows_for_format_test(id, joined);
    const auto producer_snapshot = producer.snapshot();
    const auto consumer_snapshot = consumer.snapshot();
    write_bytes(output_directory / "producer.raw", producer_snapshot.bytes);
    write_bytes(output_directory / "consumer.raw", consumer_snapshot.bytes);
    write_bytes(output_directory / "joined.raw", joined_bytes);
    write_bytes(output_directory / "empty.raw", {});
    const auto producer_envelope =
        envelope(protocol::StreamKind::producer, "producer-artifact", "producer.raw",
                 producer_snapshot.bytes, 2U);
    const auto consumer_envelope =
        envelope(protocol::StreamKind::consumer, "consumer-artifact", "consumer.raw",
                 consumer_snapshot.bytes, 1U);
    const auto joined_envelope = envelope(
        protocol::StreamKind::joined_derived, "joined-artifact", "joined.raw",
        joined_bytes, 1U,
        {{"producer-artifact", workload::sha256(producer_snapshot.bytes).hex()},
         {"consumer-artifact", workload::sha256(consumer_snapshot.bytes).hex()}});
    write_text(output_directory / "producer.json", producer_envelope.document.bytes);
    write_text(output_directory / "consumer.json", consumer_envelope.document.bytes);
    write_text(output_directory / "joined.json", joined_envelope.document.bytes);
    const auto checksum = workload::sha256(producer_snapshot.bytes);
    auto integrity = storage::make_phase_integrity_document(
        {"fixture-integrity", "r", workload::ConsumerState{0x12U}, checksum, checksum,
         checksum, checksum});
    if (!integrity) {
      return 5;
    }
    write_text(output_directory / "integrity.json", integrity.value().bytes);

    auto ledger = storage::make_copy_ledger_document(
        {"fixture-ledger",
         "r",
         "producer-object",
         "PRODUCER_RAW",
         "producer-artifact",
         static_cast<std::uint64_t>(producer_snapshot.bytes.size()),
         workload::sha256(producer_snapshot.bytes).hex(),
         storage::StreamCompleteness::sealed_complete,
         storage::CopyFinalizationState::sealed_complete,
         {{"domain-a", "producer-a.raw",
           static_cast<std::uint64_t>(producer_snapshot.bytes.size()),
           workload::sha256(producer_snapshot.bytes).hex(), "2026-08-21T00:00:00Z",
           true, true},
          {"domain-b", "producer-b.raw",
           static_cast<std::uint64_t>(producer_snapshot.bytes.size()),
           workload::sha256(producer_snapshot.bytes).hex(), "2026-08-21T00:00:01Z",
           true, true}},
         {}});
    if (!ledger) {
      return 5;
    }
    write_text(output_directory / "copy-ledger.json", ledger.value().bytes);
  } catch (const std::exception&) {
    return 5;
  }
  return 0;
}
