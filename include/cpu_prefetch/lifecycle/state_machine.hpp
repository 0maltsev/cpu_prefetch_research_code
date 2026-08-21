#ifndef CPU_PREFETCH_LIFECYCLE_STATE_MACHINE_HPP
#define CPU_PREFETCH_LIFECYCLE_STATE_MACHINE_HPP

#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include "cpu_prefetch/protocol/model.hpp"

namespace cpu_prefetch::lifecycle {

enum class RunPhase : std::uint8_t {
  planned,
  preflight,
  pre_run_failure,
  preparation,
  warmup,
  warmup_failure,
  logical_reset,
  reset_failure,
  measurement_started,
  measurement_failure,
  producer_complete,
  drain,
  drain_failure,
  completed,
  finalized_invalid,
  finalized_valid,
};

struct PhaseTransition final {
  RunPhase from;
  RunPhase to;
};

[[nodiscard]] auto to_string(RunPhase phase) -> std::string_view;
[[nodiscard]] auto is_legal_transition(PhaseTransition transition) noexcept -> bool;

enum class LifecycleArtifactKind : std::uint8_t {
  plan,
  warmup_schedule,
  measurement_schedule,
  reset_evidence,
  producer_observations,
  consumer_observations,
  counts,
  phase_integrity,
  failure_evidence,
  transition_journal,
  recovery_evidence,
};

enum class ArtifactAction : std::uint8_t {
  retain,
  append_partial,
  append_complete,
  declare_absent,
};

[[nodiscard]] auto to_string(LifecycleArtifactKind kind) -> std::string_view;
[[nodiscard]] auto to_string(ArtifactAction action) -> std::string_view;

struct ArtifactConsequence final {
  LifecycleArtifactKind kind;
  ArtifactAction action;
  std::string artifact_id;
  std::uint64_t row_count;

  auto operator==(const ArtifactConsequence&) const -> bool = default;
};

struct LifecycleContext final {
  protocol::RunId run_id;
  protocol::BlockId block_id;
  protocol::ScheduleId warmup_schedule_id;
  protocol::ScheduleId measurement_schedule_id;
  protocol::NamespaceId warmup_namespace_id;
  protocol::NamespaceId measurement_namespace_id;
  std::string transition_clock_id;
  std::string transition_time_unit;
};

struct TransitionRequest final {
  RunPhase next;
  std::uint64_t timestamp;
  std::string actor;
  std::string reason;
  std::vector<ArtifactConsequence> artifact_consequences;
};

struct TransitionRecord final {
  std::uint64_t sequence;
  std::optional<RunPhase> from;
  RunPhase to;
  protocol::LifecycleState protocol_lifecycle_state;
  std::uint64_t timestamp;
  std::string actor;
  std::string reason;
  std::vector<ArtifactConsequence> artifact_consequences;
};

enum class NonFailureOutcome : std::uint8_t {
  reconciled_full,
  genuine_low_effective_tail,
};

[[nodiscard]] auto to_string(NonFailureOutcome outcome) -> std::string_view;

struct OutcomeAnnotation final {
  NonFailureOutcome outcome;
  std::uint64_t timestamp;
  std::string actor;
  std::string reason;
  bool lifecycle_failure;
  bool replacement_trigger;
};

struct RecoveryRequest final {
  std::string policy_id;
  std::uint64_t duration_ticks;
  std::uint64_t started_at;
  std::uint64_t completed_at;
  std::string actor;
  std::string reason;
  std::string evidence_artifact_id;
};

struct RecoveryRecord final {
  std::string policy_id;
  std::uint64_t duration_ticks;
  std::uint64_t started_at;
  std::uint64_t completed_at;
  std::string actor;
  std::string reason;
  std::string evidence_artifact_id;
};

class RunStateMachine final {
public:
  [[nodiscard]] static auto create(LifecycleContext context, TransitionRequest genesis)
      -> protocol::Result<RunStateMachine>;

  [[nodiscard]] auto transition(TransitionRequest request)
      -> std::vector<protocol::ValidationError>;
  [[nodiscard]] auto record_non_failure_outcome(OutcomeAnnotation annotation)
      -> std::vector<protocol::ValidationError>;
  [[nodiscard]] auto record_recovery(RecoveryRequest request)
      -> std::vector<protocol::ValidationError>;

  [[nodiscard]] auto context() const noexcept -> const LifecycleContext& {
    return context_;
  }
  [[nodiscard]] auto phase() const noexcept -> RunPhase { return phase_; }
  [[nodiscard]] auto protocol_lifecycle_state() const noexcept
      -> protocol::LifecycleState {
    return protocol_state_;
  }
  [[nodiscard]] auto transitions() const noexcept -> std::span<const TransitionRecord> {
    return transitions_;
  }
  [[nodiscard]] auto outcomes() const noexcept -> std::span<const OutcomeAnnotation> {
    return outcomes_;
  }
  [[nodiscard]] auto recoveries() const noexcept -> std::span<const RecoveryRecord> {
    return recoveries_;
  }

private:
  RunStateMachine(LifecycleContext context, TransitionRecord genesis);

  LifecycleContext context_;
  RunPhase phase_{RunPhase::planned};
  protocol::LifecycleState protocol_state_{protocol::LifecycleState::planned};
  std::uint64_t last_timestamp_{0U};
  std::vector<TransitionRecord> transitions_;
  std::vector<OutcomeAnnotation> outcomes_;
  std::vector<RecoveryRecord> recoveries_;
};

} // namespace cpu_prefetch::lifecycle

#endif // CPU_PREFETCH_LIFECYCLE_STATE_MACHINE_HPP
