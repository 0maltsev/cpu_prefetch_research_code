#ifndef CPU_PREFETCH_STORAGE_ARTIFACTS_HPP
#define CPU_PREFETCH_STORAGE_ARTIFACTS_HPP

#include "cpu_prefetch/protocol/model.hpp"
#include "cpu_prefetch/storage/raw_observations.hpp"
#include "cpu_prefetch/workload/records.hpp"

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::storage {

inline constexpr std::string_view kPhaseIntegritySchema =
    "cpu-prefetch-phase-integrity-report/1";
inline constexpr std::string_view kCopyLedgerSchema =
    "cpu-prefetch-copy-ledger-record/1";
inline constexpr std::string_view kConsumerMixerRecordId =
    "cpu-prefetch/consumer-mix64-adr0027/v1";
inline constexpr std::string_view kContentChecksumRecordId =
    "cpu-prefetch/event-record-content-sha256/v1";
inline constexpr std::string_view kOrderedIndexChecksumRecordId =
    "cpu-prefetch/ordered-index-sha256/v1";
inline constexpr std::string_view kAddressDeltaChecksumRecordId =
    "cpu-prefetch/address-delta-sha256/v1";
inline constexpr std::string_view kChecksumAlgorithmVersion = "1";

struct CanonicalDocument final {
  std::string bytes;
  std::string sha256;
};

struct ArtifactRefText final {
  std::string artifact_id;
  std::string sha256;
};

struct PhaseIntegrityInput final {
  std::string artifact_id;
  std::string run_id;
  workload::ConsumerState final_consumer_state;
  workload::Sha256Digest event_records_pre;
  workload::Sha256Digest event_records_post;
  workload::Sha256Digest ordered_index;
  workload::Sha256Digest address_delta;
};

[[nodiscard]] auto make_phase_integrity_document(const PhaseIntegrityInput& input)
    -> protocol::Result<CanonicalDocument>;

struct RawEnvelopeInput final {
  std::string artifact_id;
  std::string run_id;
  protocol::StreamKind stream_kind;
  std::string artifact_uri;
  std::uint64_t row_count;
  std::uint64_t byte_count;
  std::string artifact_sha256;
  ArtifactRefText integrity_artifact;
  std::vector<ArtifactRefText> source_artifacts;
};

struct RawEnvelopeDocument final {
  CanonicalDocument document;
  protocol::RawObservationEnvelope envelope;
};

[[nodiscard]] auto make_external_raw_envelope(const RawEnvelopeInput& input)
    -> protocol::Result<RawEnvelopeDocument>;

enum class CopyFinalizationState : std::uint8_t {
  incomplete,
  sealed_complete,
};

[[nodiscard]] auto to_string(CopyFinalizationState state) noexcept -> std::string_view;

struct CopyEvidence final {
  std::string storage_domain_id;
  std::string artifact_uri;
  std::uint64_t observed_byte_count;
  std::string observed_sha256;
  std::string verified_at;
  bool independently_read_back;
  bool verified;
};

struct CopyLedgerInput final {
  std::string ledger_record_id;
  std::string run_id;
  std::string object_id;
  std::string object_role;
  std::string artifact_id;
  std::uint64_t byte_count;
  std::string sha256;
  StreamCompleteness stream_completeness;
  CopyFinalizationState finalization_state;
  std::vector<CopyEvidence> copies;
  std::vector<std::string> failures;
};

[[nodiscard]] auto make_copy_ledger_document(const CopyLedgerInput& input)
    -> protocol::Result<CanonicalDocument>;

} // namespace cpu_prefetch::storage

#endif // CPU_PREFETCH_STORAGE_ARTIFACTS_HPP
