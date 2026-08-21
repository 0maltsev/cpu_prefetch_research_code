#ifndef CPU_PREFETCH_RECONCILIATION_RECONCILIATION_HPP
#define CPU_PREFETCH_RECONCILIATION_RECONCILIATION_HPP

#include "cpu_prefetch/protocol/model.hpp"

#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::reconciliation {

enum class FailureClass : std::uint8_t {
  producer_count,
  producer_run_identity,
  producer_logical_sequence,
  producer_record_mapping,
  producer_outcome_shape,
  accepted_ordinal,
  consumer_count,
  consumer_run_identity,
  consumer_ordinal,
  consumer_record_index,
  timestamp_order,
};

[[nodiscard]] auto to_string(FailureClass failure) noexcept -> std::string_view;

struct Issue final {
  FailureClass failure;
  protocol::ValidationError error;
  auto operator==(const Issue&) const -> bool = default;
};

struct ReconciliationResult final {
  protocol::JoinStatus status{protocol::JoinStatus::not_attempted};
  std::uint64_t producer_rows{0U};
  std::uint64_t accepted_rows{0U};
  std::uint64_t full_rows{0U};
  std::uint64_t consumer_rows{0U};
  std::vector<protocol::JoinedRecord> joined_rows;
  std::vector<Issue> issues;
};

// expected_record_indices is the immutable Stage 6 logical-sequence mapping.
// It is the post-run address-relation witness; no pointer value is serialized.
[[nodiscard]] auto reconcile(const protocol::RunId& run_id,
                             std::span<const protocol::ProducerRecord> producer_rows,
                             std::span<const protocol::ConsumerRecord> consumer_rows,
                             std::span<const std::uint64_t> expected_record_indices)
    -> ReconciliationResult;

enum class LifecycleCompletion : std::uint8_t {
  not_evaluated,
  incomplete,
  complete,
};

struct AuthoritativeGate final {
  protocol::GateStatus status{protocol::GateStatus::not_evaluated};
  bool authoritative{false};
};

struct AuthoritativeBlockCompleteness final {
  protocol::BlockCompleteness status{protocol::BlockCompleteness::not_evaluated};
  bool authoritative{false};
};

struct RunStatusInput final {
  protocol::Stage stage{protocol::Stage::stage_a};
  protocol::LifecycleState lifecycle_state{protocol::LifecycleState::planned};
  protocol::JoinStatus join_status{protocol::JoinStatus::not_attempted};
  std::optional<protocol::RunCounts> counts;
  bool invalidating_failure_record_present{false};
  AuthoritativeBlockCompleteness block_completeness;
  AuthoritativeGate access_integrity;
};

struct RunStatus final {
  LifecycleCompletion lifecycle_completion{LifecycleCompletion::not_evaluated};
  protocol::RunValidity validity{protocol::RunValidity::not_evaluated};
  protocol::JoinStatus join_status{protocol::JoinStatus::not_attempted};
  protocol::GateStatus count_reconciliation{protocol::GateStatus::not_evaluated};
  protocol::GateStatus zero_loss{protocol::GateStatus::not_evaluated};
  protocol::GateStatus effective_tail{protocol::GateStatus::not_evaluated};
  protocol::ConfirmatoryEstimability confirmatory_estimability{
      protocol::ConfirmatoryEstimability::not_evaluated};
  protocol::BlockCompleteness block_completeness{
      protocol::BlockCompleteness::not_evaluated};
  std::vector<protocol::ConfirmatoryBlocker> confirmatory_blockers;
};

// A failed Result means the requested status would assert INVALID without an
// invalidating failure record, or contains incomplete/non-exact count evidence.
[[nodiscard]] auto evaluate_run_status(const RunStatusInput& input)
    -> protocol::Result<RunStatus>;

struct JoinAuditInput final {
  protocol::ArtifactReference producer_source;
  protocol::ArtifactReference consumer_source;
  std::optional<protocol::ArtifactReference> joined_artifact;
};

// Produces JCS-I64-v1 bytes with a zero-self SHA-256 profile. A failed join
// cannot name a joined artifact; a passed join must name it.
[[nodiscard]] auto make_join_audit(const protocol::RunId& run_id,
                                   const ReconciliationResult& result,
                                   const JoinAuditInput& artifacts)
    -> protocol::Result<std::string>;

struct ArtifactBytes final {
  protocol::ArtifactId artifact_id;
  std::span<const std::byte> bytes;
};

struct RunEvidence final {
  protocol::RunId run_id;
  std::span<const std::uint64_t> expected_record_indices;
  AuthoritativeBlockCompleteness block_completeness;
  AuthoritativeGate access_integrity;
};

// Stage 12 implements run-level relationships. Exact Stage A block factorial
// completeness and access/freeze chronology remain Stage 14 responsibilities;
// their independently computed results are injected as authoritative gates.
class Stage12CrossRecordSemanticValidator final
    : public protocol::CrossRecordSemanticValidator {
public:
  Stage12CrossRecordSemanticValidator(std::span<const ArtifactBytes> artifacts,
                                      std::span<const RunEvidence> evidence)
      : artifacts_(artifacts), evidence_(evidence) {}

  [[nodiscard]] auto validate(const protocol::SemanticRecordSet& records) const
      -> std::vector<protocol::ValidationError> override;

private:
  std::span<const ArtifactBytes> artifacts_;
  std::span<const RunEvidence> evidence_;
};

} // namespace cpu_prefetch::reconciliation

#endif // CPU_PREFETCH_RECONCILIATION_RECONCILIATION_HPP
