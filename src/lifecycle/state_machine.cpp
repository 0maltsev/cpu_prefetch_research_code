#include "cpu_prefetch/lifecycle/state_machine.hpp"

#include <algorithm>
#include <array>
#include <set>
#include <utility>

namespace cpu_prefetch::lifecycle {
namespace {

using protocol::ErrorCategory;
using protocol::ValidationError;

void add_error(std::vector<ValidationError>& errors, ErrorCategory category,
               std::string path, std::string rule_id, std::string message) {
  errors.push_back({category, std::move(path), std::move(rule_id), std::move(message)});
}

[[nodiscard]] auto is_failure_phase(RunPhase phase) noexcept -> bool {
  return phase == RunPhase::pre_run_failure || phase == RunPhase::warmup_failure ||
         phase == RunPhase::reset_failure || phase == RunPhase::measurement_failure ||
         phase == RunPhase::drain_failure;
}

[[nodiscard]] auto is_early_failure(RunPhase phase) noexcept -> bool {
  return phase == RunPhase::pre_run_failure || phase == RunPhase::warmup_failure ||
         phase == RunPhase::reset_failure;
}

[[nodiscard]] auto protocol_projection(RunPhase phase,
                                       protocol::LifecycleState retained) noexcept
    -> protocol::LifecycleState {
  switch (phase) {
  case RunPhase::planned:
  case RunPhase::preflight:
  case RunPhase::preparation:
  case RunPhase::warmup:
  case RunPhase::logical_reset:
    return protocol::LifecycleState::planned;
  case RunPhase::pre_run_failure:
    return protocol::LifecycleState::pre_run_failure;
  case RunPhase::warmup_failure:
    return protocol::LifecycleState::warmup_failure;
  case RunPhase::reset_failure:
    return protocol::LifecycleState::reset_failure;
  case RunPhase::measurement_started:
  case RunPhase::producer_complete:
  case RunPhase::drain:
    return protocol::LifecycleState::measurement_started;
  case RunPhase::measurement_failure:
    return protocol::LifecycleState::measurement_failure;
  case RunPhase::drain_failure:
    return protocol::LifecycleState::drain_failure;
  case RunPhase::completed:
  case RunPhase::finalized_valid:
    return protocol::LifecycleState::completed;
  case RunPhase::finalized_invalid:
    return retained;
  }
  return retained;
}

[[nodiscard]] auto has_artifact_kind(std::span<const ArtifactConsequence> consequences,
                                     LifecycleArtifactKind kind) -> bool {
  return std::any_of(consequences.begin(), consequences.end(),
                     [kind](const ArtifactConsequence& consequence) {
                       return consequence.kind == kind;
                     });
}

[[nodiscard]] auto
has_present_artifact_kind(std::span<const ArtifactConsequence> consequences,
                          LifecycleArtifactKind kind) -> bool {
  return std::any_of(consequences.begin(), consequences.end(),
                     [kind](const ArtifactConsequence& consequence) {
                       return consequence.kind == kind &&
                              consequence.action != ArtifactAction::declare_absent;
                     });
}

[[nodiscard]] auto
validate_consequences(RunPhase target,
                      std::span<const ArtifactConsequence> consequences)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  if (consequences.empty()) {
    add_error(errors, ErrorCategory::missing_evidence,
              "$transition/artifact_consequences", "LIF-TRANSITION-CONSEQUENCE",
              "every lifecycle transition requires explicit artifact consequences");
    return errors;
  }
  std::set<LifecycleArtifactKind> seen;
  for (std::size_t index = 0U; index < consequences.size(); ++index) {
    const auto& consequence = consequences[index];
    const auto path = "$transition/artifact_consequences/" + std::to_string(index);
    if (!seen.insert(consequence.kind).second) {
      add_error(errors, ErrorCategory::duplicate_value, path,
                "LIF-TRANSITION-ARTIFACT-UNIQUE",
                "one transition cannot state two consequences for one artifact kind");
    }
    if (consequence.action == ArtifactAction::declare_absent) {
      if (!consequence.artifact_id.empty() || consequence.row_count != 0U) {
        add_error(errors, ErrorCategory::cross_field, path, "LIF-ABSENT-ARTIFACT",
                  "an explicitly absent artifact has no ID and zero rows");
      }
    } else if (consequence.artifact_id.empty()) {
      add_error(errors, ErrorCategory::missing_field, path + "/artifact_id",
                "LIF-ARTIFACT-ID",
                "retained or appended artifact evidence requires an ID");
    }
  }

  if (is_failure_phase(target) &&
      !has_present_artifact_kind(consequences,
                                 LifecycleArtifactKind::failure_evidence)) {
    add_error(errors, ErrorCategory::missing_evidence,
              "$transition/artifact_consequences", "LIF-FAILURE-EVIDENCE",
              "a failure transition must append or retain failure evidence");
  }
  if (is_early_failure(target)) {
    constexpr std::array forbidden{LifecycleArtifactKind::producer_observations,
                                   LifecycleArtifactKind::consumer_observations,
                                   LifecycleArtifactKind::counts,
                                   LifecycleArtifactKind::phase_integrity};
    for (const auto kind : forbidden) {
      if (has_present_artifact_kind(consequences, kind)) {
        add_error(errors, ErrorCategory::cross_field,
                  "$transition/artifact_consequences", "LIF-NO-FABRICATION",
                  "pre-measurement failure cannot claim measurement artifacts");
      }
      if (!has_artifact_kind(consequences, kind)) {
        add_error(errors, ErrorCategory::missing_evidence,
                  "$transition/artifact_consequences", "LIF-ABSENCE-EXPLICIT",
                  "pre-measurement failure must explicitly declare measurement "
                  "artifacts absent");
      }
    }
  }
  if (target == RunPhase::completed) {
    constexpr std::array required{LifecycleArtifactKind::producer_observations,
                                  LifecycleArtifactKind::consumer_observations,
                                  LifecycleArtifactKind::counts,
                                  LifecycleArtifactKind::phase_integrity};
    for (const auto kind : required) {
      if (!has_present_artifact_kind(consequences, kind)) {
        add_error(errors, ErrorCategory::missing_evidence,
                  "$transition/artifact_consequences", "LIF-COMPLETED-CANDIDATES",
                  "completed execution requires every Stage 10 artifact candidate");
      }
    }
  }
  if (target == RunPhase::finalized_invalid &&
      !has_present_artifact_kind(consequences,
                                 LifecycleArtifactKind::failure_evidence)) {
    add_error(errors, ErrorCategory::missing_evidence,
              "$transition/artifact_consequences", "LIF-INVALID-EVIDENCE",
              "finalized invalid execution must retain failure evidence");
  }
  return errors;
}

[[nodiscard]] auto terminal(RunPhase phase) noexcept -> bool {
  return phase == RunPhase::finalized_invalid || phase == RunPhase::finalized_valid;
}

} // namespace

auto to_string(RunPhase phase) -> std::string_view {
  switch (phase) {
  case RunPhase::planned:
    return "PLANNED";
  case RunPhase::preflight:
    return "PREFLIGHT";
  case RunPhase::pre_run_failure:
    return "PRE_RUN_FAILURE";
  case RunPhase::preparation:
    return "PREPARATION";
  case RunPhase::warmup:
    return "WARMUP";
  case RunPhase::warmup_failure:
    return "WARMUP_FAILURE";
  case RunPhase::logical_reset:
    return "LOGICAL_RESET";
  case RunPhase::reset_failure:
    return "RESET_FAILURE";
  case RunPhase::measurement_started:
    return "MEASUREMENT_STARTED";
  case RunPhase::measurement_failure:
    return "MEASUREMENT_FAILURE";
  case RunPhase::producer_complete:
    return "PRODUCER_COMPLETE";
  case RunPhase::drain:
    return "DRAIN";
  case RunPhase::drain_failure:
    return "DRAIN_FAILURE";
  case RunPhase::completed:
    return "COMPLETED";
  case RunPhase::finalized_invalid:
    return "FINALIZED_INVALID";
  case RunPhase::finalized_valid:
    return "FINALIZED_VALID";
  }
  return "UNKNOWN";
}

auto is_legal_transition(PhaseTransition transition) noexcept -> bool {
  switch (transition.from) {
  case RunPhase::planned:
    return transition.to == RunPhase::preflight;
  case RunPhase::preflight:
    return transition.to == RunPhase::preparation ||
           transition.to == RunPhase::pre_run_failure;
  case RunPhase::preparation:
    return transition.to == RunPhase::warmup ||
           transition.to == RunPhase::pre_run_failure;
  case RunPhase::warmup:
    return transition.to == RunPhase::logical_reset ||
           transition.to == RunPhase::warmup_failure;
  case RunPhase::logical_reset:
    return transition.to == RunPhase::measurement_started ||
           transition.to == RunPhase::reset_failure;
  case RunPhase::measurement_started:
    return transition.to == RunPhase::producer_complete ||
           transition.to == RunPhase::measurement_failure;
  case RunPhase::producer_complete:
    return transition.to == RunPhase::drain ||
           transition.to == RunPhase::measurement_failure;
  case RunPhase::drain:
    return transition.to == RunPhase::completed ||
           transition.to == RunPhase::drain_failure;
  case RunPhase::completed:
    return transition.to == RunPhase::finalized_valid ||
           transition.to == RunPhase::finalized_invalid;
  case RunPhase::pre_run_failure:
  case RunPhase::warmup_failure:
  case RunPhase::reset_failure:
  case RunPhase::measurement_failure:
  case RunPhase::drain_failure:
    return transition.to == RunPhase::finalized_invalid;
  case RunPhase::finalized_invalid:
  case RunPhase::finalized_valid:
    return false;
  }
  return false;
}

auto to_string(LifecycleArtifactKind kind) -> std::string_view {
  switch (kind) {
  case LifecycleArtifactKind::plan:
    return "PLAN";
  case LifecycleArtifactKind::warmup_schedule:
    return "WARMUP_SCHEDULE";
  case LifecycleArtifactKind::measurement_schedule:
    return "MEASUREMENT_SCHEDULE";
  case LifecycleArtifactKind::reset_evidence:
    return "RESET_EVIDENCE";
  case LifecycleArtifactKind::producer_observations:
    return "PRODUCER_OBSERVATIONS";
  case LifecycleArtifactKind::consumer_observations:
    return "CONSUMER_OBSERVATIONS";
  case LifecycleArtifactKind::counts:
    return "COUNTS";
  case LifecycleArtifactKind::phase_integrity:
    return "PHASE_INTEGRITY";
  case LifecycleArtifactKind::failure_evidence:
    return "FAILURE_EVIDENCE";
  case LifecycleArtifactKind::transition_journal:
    return "TRANSITION_JOURNAL";
  case LifecycleArtifactKind::recovery_evidence:
    return "RECOVERY_EVIDENCE";
  }
  return "UNKNOWN";
}

auto to_string(ArtifactAction action) -> std::string_view {
  switch (action) {
  case ArtifactAction::retain:
    return "RETAIN";
  case ArtifactAction::append_partial:
    return "APPEND_PARTIAL";
  case ArtifactAction::append_complete:
    return "APPEND_COMPLETE";
  case ArtifactAction::declare_absent:
    return "DECLARE_ABSENT";
  }
  return "UNKNOWN";
}

auto to_string(NonFailureOutcome outcome) -> std::string_view {
  switch (outcome) {
  case NonFailureOutcome::reconciled_full:
    return "RECONCILED_FULL";
  case NonFailureOutcome::genuine_low_effective_tail:
    return "GENUINE_LOW_EFFECTIVE_TAIL";
  }
  return "UNKNOWN";
}

RunStateMachine::RunStateMachine(LifecycleContext context, TransitionRecord genesis)
    : context_(std::move(context)), last_timestamp_(genesis.timestamp) {
  transitions_.push_back(std::move(genesis));
}

auto RunStateMachine::create(LifecycleContext context, TransitionRequest genesis)
    -> protocol::Result<RunStateMachine> {
  std::vector<ValidationError> errors;
  if (context.warmup_namespace_id == context.measurement_namespace_id) {
    add_error(errors, ErrorCategory::cross_field, "$lifecycle/namespaces",
              "LIF-NAMESPACE-SEPARATION",
              "warm-up and measurement namespaces must be distinct");
  }
  if (context.warmup_schedule_id == context.measurement_schedule_id) {
    add_error(errors, ErrorCategory::cross_field, "$lifecycle/schedules",
              "LIF-SCHEDULE-SEPARATION",
              "warm-up and measurement schedules must have distinct identities");
  }
  if (context.transition_clock_id.empty() || context.transition_time_unit.empty()) {
    add_error(errors, ErrorCategory::missing_field, "$lifecycle/transition_clock",
              "LIF-TRANSITION-CLOCK",
              "transition clock identity and unit are explicit required values");
  }
  if (genesis.next != RunPhase::planned) {
    add_error(errors, ErrorCategory::cross_field, "$transition/next",
              "LIF-GENESIS-PLANNED",
              "the initial lifecycle record must create PLANNED");
  }
  if (genesis.actor.empty() || genesis.reason.empty()) {
    add_error(errors, ErrorCategory::missing_field, "$transition",
              "LIF-TRANSITION-WHO-WHY",
              "every transition requires a nonempty actor and reason");
  }
  auto consequence_errors =
      validate_consequences(genesis.next, genesis.artifact_consequences);
  errors.insert(errors.end(), consequence_errors.begin(), consequence_errors.end());
  if (!errors.empty()) {
    return protocol::Result<RunStateMachine>::failure(std::move(errors));
  }
  TransitionRecord record{0U,
                          std::nullopt,
                          RunPhase::planned,
                          protocol::LifecycleState::planned,
                          genesis.timestamp,
                          std::move(genesis.actor),
                          std::move(genesis.reason),
                          std::move(genesis.artifact_consequences)};
  const RunStateMachine machine(std::move(context), std::move(record));
  return protocol::Result<RunStateMachine>::success(machine);
}

auto RunStateMachine::transition(TransitionRequest request)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  if (!is_legal_transition({phase_, request.next})) {
    add_error(errors, ErrorCategory::cross_field, "$transition/next",
              "LIF-ILLEGAL-TRANSITION",
              "transition is not in the accepted Stage 10 state graph");
  }
  if (request.actor.empty() || request.reason.empty()) {
    add_error(errors, ErrorCategory::missing_field, "$transition",
              "LIF-TRANSITION-WHO-WHY",
              "every transition requires a nonempty actor and reason");
  }
  if (request.timestamp < last_timestamp_) {
    add_error(errors, ErrorCategory::cross_field, "$transition/timestamp",
              "LIF-TRANSITION-TIME", "transition timestamps must be nondecreasing");
  }
  auto consequence_errors =
      validate_consequences(request.next, request.artifact_consequences);
  errors.insert(errors.end(), consequence_errors.begin(), consequence_errors.end());
  if (!errors.empty()) {
    return errors;
  }

  const auto previous = phase_;
  protocol_state_ = protocol_projection(request.next, protocol_state_);
  phase_ = request.next;
  last_timestamp_ = request.timestamp;
  transitions_.push_back({transitions_.size(), previous, phase_, protocol_state_,
                          request.timestamp, std::move(request.actor),
                          std::move(request.reason),
                          std::move(request.artifact_consequences)});
  return {};
}

auto RunStateMachine::record_non_failure_outcome(OutcomeAnnotation annotation)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  if (phase_ != RunPhase::completed && phase_ != RunPhase::finalized_valid) {
    add_error(errors, ErrorCategory::cross_field, "$outcome", "LIF-OUTCOME-PHASE",
              "FULL and effective-tail outcomes are recorded only after completion");
  }
  if (annotation.actor.empty() || annotation.reason.empty()) {
    add_error(errors, ErrorCategory::missing_field, "$outcome", "LIF-OUTCOME-WHO-WHY",
              "outcome annotation requires actor and reason");
  }
  if (annotation.timestamp < last_timestamp_) {
    add_error(errors, ErrorCategory::cross_field, "$outcome/timestamp",
              "LIF-OUTCOME-TIME", "outcome timestamp precedes lifecycle evidence");
  }
  if (annotation.lifecycle_failure || annotation.replacement_trigger) {
    add_error(errors, ErrorCategory::cross_field, "$outcome", "LIF-OUTCOME-NOT-FAILURE",
              "reconciled FULL and genuine low N_eff are not lifecycle or replacement "
              "triggers");
  }
  if (!errors.empty()) {
    return errors;
  }
  last_timestamp_ = annotation.timestamp;
  outcomes_.push_back(std::move(annotation));
  return {};
}

auto RunStateMachine::record_recovery(RecoveryRequest request)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  if (!terminal(phase_)) {
    add_error(errors, ErrorCategory::cross_field, "$recovery",
              "LIF-RECOVERY-OUTSIDE-RUN",
              "recovery may begin only after lifecycle finalization");
  }
  if (request.policy_id.empty() || request.actor.empty() || request.reason.empty() ||
      request.evidence_artifact_id.empty() || request.duration_ticks == 0U) {
    add_error(errors, ErrorCategory::missing_field, "$recovery",
              "LIF-RECOVERY-EXPLICIT",
              "recovery policy, positive duration, actor, reason, and evidence are "
              "required");
  }
  if (request.started_at < last_timestamp_ ||
      request.completed_at < request.started_at ||
      request.completed_at - request.started_at < request.duration_ticks) {
    add_error(errors, ErrorCategory::cross_field, "$recovery/timestamps",
              "LIF-RECOVERY-DURATION",
              "recovery must occur after finalization and cover its explicit duration");
  }
  if (!errors.empty()) {
    return errors;
  }
  last_timestamp_ = request.completed_at;
  recoveries_.push_back({std::move(request.policy_id), request.duration_ticks,
                         request.started_at, request.completed_at,
                         std::move(request.actor), std::move(request.reason),
                         std::move(request.evidence_artifact_id)});
  return {};
}

} // namespace cpu_prefetch::lifecycle
