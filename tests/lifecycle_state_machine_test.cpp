#include <gtest/gtest.h>

#include "cpu_prefetch/lifecycle/runtime.hpp"
#include "cpu_prefetch/lifecycle/state_machine.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

using cpu_prefetch::lifecycle::ArtifactAction;
using cpu_prefetch::lifecycle::ArtifactConsequence;
using cpu_prefetch::lifecycle::LifecycleArtifactKind;
using cpu_prefetch::lifecycle::LifecycleContext;
using cpu_prefetch::lifecycle::LogicalResetBackend;
using cpu_prefetch::lifecycle::LogicalResetEvidence;
using cpu_prefetch::lifecycle::LogicalResetRequest;
using cpu_prefetch::lifecycle::NonFailureOutcome;
using cpu_prefetch::lifecycle::OutcomeAnnotation;
using cpu_prefetch::lifecycle::PreparationEvidence;
using cpu_prefetch::lifecycle::QueueResetKind;
using cpu_prefetch::lifecycle::RecoveryRequest;
using cpu_prefetch::lifecycle::RunPhase;
using cpu_prefetch::lifecycle::RunStateMachine;
using cpu_prefetch::lifecycle::TransitionRequest;
using cpu_prefetch::lifecycle::WarmStartIdentity;
using cpu_prefetch::lifecycle::WarmupCompletionEvidence;
using cpu_prefetch::protocol::BlockId;
using cpu_prefetch::protocol::LifecycleState;
using cpu_prefetch::protocol::NamespaceId;
using cpu_prefetch::protocol::RunId;
using cpu_prefetch::protocol::ScheduleId;
using cpu_prefetch::protocol::ValidationError;

template <typename Identifier> auto identifier(std::string value) -> Identifier {
  auto parsed = Identifier::parse(std::move(value), "$test/id");
  if (!parsed) {
    throw std::logic_error("test identifier is invalid");
  }
  return std::move(parsed).value();
}

auto context() -> LifecycleContext {
  return {identifier<RunId>("run-stage10"),
          identifier<BlockId>("block-stage10"),
          identifier<ScheduleId>("warmup-schedule"),
          identifier<ScheduleId>("measurement-schedule"),
          identifier<NamespaceId>("warmup-namespace"),
          identifier<NamespaceId>("measurement-namespace"),
          "fixture-monotonic-clock",
          "PICOSECONDS"};
}

auto consequence(LifecycleArtifactKind kind, ArtifactAction action,
                 std::uint64_t rows = 0U) -> ArtifactConsequence {
  return {kind, action,
          action == ArtifactAction::declare_absent
              ? std::string{}
              : std::string(cpu_prefetch::lifecycle::to_string(kind)) + "-fixture",
          rows};
}

auto normal_consequences() -> std::vector<ArtifactConsequence> {
  return {consequence(LifecycleArtifactKind::transition_journal,
                      ArtifactAction::append_complete, 1U)};
}

auto early_failure_consequences() -> std::vector<ArtifactConsequence> {
  return {
      consequence(LifecycleArtifactKind::failure_evidence,
                  ArtifactAction::append_complete, 1U),
      consequence(LifecycleArtifactKind::producer_observations,
                  ArtifactAction::declare_absent),
      consequence(LifecycleArtifactKind::consumer_observations,
                  ArtifactAction::declare_absent),
      consequence(LifecycleArtifactKind::counts, ArtifactAction::declare_absent),
      consequence(LifecycleArtifactKind::phase_integrity,
                  ArtifactAction::declare_absent),
      consequence(LifecycleArtifactKind::transition_journal,
                  ArtifactAction::append_complete, 1U),
  };
}

auto runtime_failure_consequences() -> std::vector<ArtifactConsequence> {
  return {
      consequence(LifecycleArtifactKind::failure_evidence,
                  ArtifactAction::append_complete, 1U),
      consequence(LifecycleArtifactKind::producer_observations,
                  ArtifactAction::append_partial, 3U),
      consequence(LifecycleArtifactKind::consumer_observations,
                  ArtifactAction::append_partial, 2U),
      consequence(LifecycleArtifactKind::counts, ArtifactAction::append_partial, 1U),
      consequence(LifecycleArtifactKind::transition_journal,
                  ArtifactAction::append_complete, 1U),
  };
}

auto completed_consequences() -> std::vector<ArtifactConsequence> {
  return {
      consequence(LifecycleArtifactKind::producer_observations,
                  ArtifactAction::append_complete, 4U),
      consequence(LifecycleArtifactKind::consumer_observations,
                  ArtifactAction::append_complete, 3U),
      consequence(LifecycleArtifactKind::counts, ArtifactAction::append_complete, 1U),
      consequence(LifecycleArtifactKind::phase_integrity,
                  ArtifactAction::append_complete, 1U),
      consequence(LifecycleArtifactKind::transition_journal,
                  ArtifactAction::append_complete, 1U),
  };
}

auto invalid_consequences() -> std::vector<ArtifactConsequence> {
  return {
      consequence(LifecycleArtifactKind::failure_evidence, ArtifactAction::retain, 1U),
      consequence(LifecycleArtifactKind::transition_journal,
                  ArtifactAction::append_complete, 1U),
  };
}

auto make_machine() -> RunStateMachine {
  auto result = RunStateMachine::create(
      context(),
      {RunPhase::planned,
       10U,
       "controller",
       "registered run plan",
       {consequence(LifecycleArtifactKind::plan, ArtifactAction::retain, 1U)}});
  if (!result) {
    throw std::logic_error(result.errors().front().message);
  }
  return std::move(result).value();
}

void advance(RunStateMachine& machine, RunPhase phase, std::uint64_t timestamp,
             std::vector<ArtifactConsequence> consequences = normal_consequences()) {
  const auto errors = machine.transition(
      {phase, timestamp, "controller", "fixture transition", std::move(consequences)});
  ASSERT_TRUE(errors.empty()) << errors.front().message;
}

auto has_rule(const std::vector<ValidationError>& errors, const std::string& rule_id)
    -> bool {
  for (const auto& error : errors) {
    if (error.rule_id == rule_id) {
      return true;
    }
  }
  return false;
}

TEST(LifecycleStateMachine, ExactInternalGraphAcceptsEveryAndOnlyRegisteredEdge) {
  constexpr std::array phases{
      RunPhase::planned,
      RunPhase::preflight,
      RunPhase::pre_run_failure,
      RunPhase::preparation,
      RunPhase::warmup,
      RunPhase::warmup_failure,
      RunPhase::logical_reset,
      RunPhase::reset_failure,
      RunPhase::measurement_started,
      RunPhase::measurement_failure,
      RunPhase::producer_complete,
      RunPhase::drain,
      RunPhase::drain_failure,
      RunPhase::completed,
      RunPhase::finalized_invalid,
      RunPhase::finalized_valid,
  };
  constexpr std::array legal{
      std::pair{RunPhase::planned, RunPhase::preflight},
      std::pair{RunPhase::preflight, RunPhase::preparation},
      std::pair{RunPhase::preflight, RunPhase::pre_run_failure},
      std::pair{RunPhase::preparation, RunPhase::warmup},
      std::pair{RunPhase::preparation, RunPhase::pre_run_failure},
      std::pair{RunPhase::warmup, RunPhase::logical_reset},
      std::pair{RunPhase::warmup, RunPhase::warmup_failure},
      std::pair{RunPhase::logical_reset, RunPhase::measurement_started},
      std::pair{RunPhase::logical_reset, RunPhase::reset_failure},
      std::pair{RunPhase::measurement_started, RunPhase::producer_complete},
      std::pair{RunPhase::measurement_started, RunPhase::measurement_failure},
      std::pair{RunPhase::producer_complete, RunPhase::drain},
      std::pair{RunPhase::producer_complete, RunPhase::measurement_failure},
      std::pair{RunPhase::drain, RunPhase::completed},
      std::pair{RunPhase::drain, RunPhase::drain_failure},
      std::pair{RunPhase::completed, RunPhase::finalized_valid},
      std::pair{RunPhase::completed, RunPhase::finalized_invalid},
      std::pair{RunPhase::pre_run_failure, RunPhase::finalized_invalid},
      std::pair{RunPhase::warmup_failure, RunPhase::finalized_invalid},
      std::pair{RunPhase::reset_failure, RunPhase::finalized_invalid},
      std::pair{RunPhase::measurement_failure, RunPhase::finalized_invalid},
      std::pair{RunPhase::drain_failure, RunPhase::finalized_invalid},
  };

  for (const auto from : phases) {
    for (const auto to : phases) {
      const bool expected =
          std::find(legal.begin(), legal.end(), std::pair{from, to}) != legal.end();
      EXPECT_EQ(cpu_prefetch::lifecycle::is_legal_transition({from, to}), expected)
          << cpu_prefetch::lifecycle::to_string(from) << " -> "
          << cpu_prefetch::lifecycle::to_string(to);
    }
  }
}

TEST(LifecycleStateMachine, HappyPathProjectsOntoImportedStableLifecycleEnum) {
  auto machine = make_machine();
  const std::array steps{
      std::pair{RunPhase::preflight, LifecycleState::planned},
      std::pair{RunPhase::preparation, LifecycleState::planned},
      std::pair{RunPhase::warmup, LifecycleState::planned},
      std::pair{RunPhase::logical_reset, LifecycleState::planned},
      std::pair{RunPhase::measurement_started, LifecycleState::measurement_started},
      std::pair{RunPhase::producer_complete, LifecycleState::measurement_started},
      std::pair{RunPhase::drain, LifecycleState::measurement_started},
  };
  std::uint64_t timestamp = 11U;
  for (const auto& [phase, projected] : steps) {
    advance(machine, phase, timestamp++);
    EXPECT_EQ(machine.protocol_lifecycle_state(), projected);
  }
  advance(machine, RunPhase::completed, timestamp++, completed_consequences());
  EXPECT_EQ(machine.protocol_lifecycle_state(), LifecycleState::completed);
  advance(machine, RunPhase::finalized_valid, timestamp++);

  EXPECT_EQ(machine.phase(), RunPhase::finalized_valid);
  ASSERT_EQ(machine.transitions().size(), 10U);
  for (const auto& transition : machine.transitions()) {
    EXPECT_FALSE(transition.actor.empty());
    EXPECT_FALSE(transition.reason.empty());
    EXPECT_FALSE(transition.artifact_consequences.empty());
  }
}

TEST(LifecycleStateMachine, EveryFailurePhasePreservesExactStableFailureState) {
  struct FailureCase final {
    std::vector<RunPhase> prefix;
    RunPhase failure;
    LifecycleState expected;
    bool early;
  };
  const std::vector<FailureCase> cases{
      {{RunPhase::preflight},
       RunPhase::pre_run_failure,
       LifecycleState::pre_run_failure,
       true},
      {{RunPhase::preflight, RunPhase::preparation},
       RunPhase::pre_run_failure,
       LifecycleState::pre_run_failure,
       true},
      {{RunPhase::preflight, RunPhase::preparation, RunPhase::warmup},
       RunPhase::warmup_failure,
       LifecycleState::warmup_failure,
       true},
      {{RunPhase::preflight, RunPhase::preparation, RunPhase::warmup,
        RunPhase::logical_reset},
       RunPhase::reset_failure,
       LifecycleState::reset_failure,
       true},
      {{RunPhase::preflight, RunPhase::preparation, RunPhase::warmup,
        RunPhase::logical_reset, RunPhase::measurement_started},
       RunPhase::measurement_failure,
       LifecycleState::measurement_failure,
       false},
      {{RunPhase::preflight, RunPhase::preparation, RunPhase::warmup,
        RunPhase::logical_reset, RunPhase::measurement_started,
        RunPhase::producer_complete},
       RunPhase::measurement_failure,
       LifecycleState::measurement_failure,
       false},
      {{RunPhase::preflight, RunPhase::preparation, RunPhase::warmup,
        RunPhase::logical_reset, RunPhase::measurement_started,
        RunPhase::producer_complete, RunPhase::drain},
       RunPhase::drain_failure,
       LifecycleState::drain_failure,
       false},
  };

  for (const auto& test_case : cases) {
    auto machine = make_machine();
    std::uint64_t timestamp = 11U;
    for (const auto phase : test_case.prefix) {
      advance(machine, phase, timestamp++);
    }
    advance(machine, test_case.failure, timestamp++,
            test_case.early ? early_failure_consequences()
                            : runtime_failure_consequences());
    EXPECT_EQ(machine.protocol_lifecycle_state(), test_case.expected);
    advance(machine, RunPhase::finalized_invalid, timestamp++, invalid_consequences());
    EXPECT_EQ(machine.protocol_lifecycle_state(), test_case.expected);
  }
}

TEST(LifecycleStateMachine, IllegalOrIncompleteTransitionDoesNotMutateState) {
  auto machine = make_machine();
  auto errors = machine.transition(
      {RunPhase::warmup, 11U, "controller", "skip", normal_consequences()});
  EXPECT_TRUE(has_rule(errors, "LIF-ILLEGAL-TRANSITION"));
  EXPECT_EQ(machine.phase(), RunPhase::planned);
  EXPECT_EQ(machine.transitions().size(), 1U);

  errors = machine.transition({RunPhase::preflight, 9U, "", "", {}});
  EXPECT_TRUE(has_rule(errors, "LIF-TRANSITION-WHO-WHY"));
  EXPECT_TRUE(has_rule(errors, "LIF-TRANSITION-TIME"));
  EXPECT_TRUE(has_rule(errors, "LIF-TRANSITION-CONSEQUENCE"));
  EXPECT_EQ(machine.phase(), RunPhase::planned);
}

TEST(LifecycleStateMachine, EarlyFailureRequiresExplicitAbsenceWithoutFabrication) {
  auto machine = make_machine();
  advance(machine, RunPhase::preflight, 11U);
  auto bad = early_failure_consequences();
  bad[1] = consequence(LifecycleArtifactKind::producer_observations,
                       ArtifactAction::append_partial, 1U);
  const auto errors = machine.transition(
      {RunPhase::pre_run_failure, 12U, "controller", "fixture failure", bad});
  EXPECT_TRUE(has_rule(errors, "LIF-NO-FABRICATION"));
  EXPECT_EQ(machine.phase(), RunPhase::preflight);
}

TEST(LifecycleStateMachine, FullAndLowEffectiveTailNeverBecomeFailuresOrRetries) {
  auto machine = make_machine();
  std::uint64_t timestamp = 11U;
  for (const auto phase : {RunPhase::preflight, RunPhase::preparation, RunPhase::warmup,
                           RunPhase::logical_reset, RunPhase::measurement_started,
                           RunPhase::producer_complete, RunPhase::drain}) {
    advance(machine, phase, timestamp++);
  }
  advance(machine, RunPhase::completed, timestamp++, completed_consequences());
  EXPECT_TRUE(machine
                  .record_non_failure_outcome({NonFailureOutcome::reconciled_full,
                                               timestamp++, "reconciler",
                                               "valid FULL row retained", false, false})
                  .empty());
  EXPECT_TRUE(machine
                  .record_non_failure_outcome(
                      {NonFailureOutcome::genuine_low_effective_tail, timestamp++,
                       "reconciler", "low N_eff retained", false, false})
                  .empty());
  const auto errors =
      machine.record_non_failure_outcome({NonFailureOutcome::reconciled_full, timestamp,
                                          "reconciler", "bad request", true, true});
  EXPECT_TRUE(has_rule(errors, "LIF-OUTCOME-NOT-FAILURE"));
  EXPECT_EQ(machine.outcomes().size(), 2U);
  EXPECT_EQ(machine.phase(), RunPhase::completed);
}

TEST(LifecycleStateMachine, RecoveryIsExplicitAndOutsideMeasurement) {
  auto machine = make_machine();
  auto errors = machine.record_recovery(
      {"recovery-fixture", 5U, 11U, 16U, "controller", "too early", "evidence"});
  EXPECT_TRUE(has_rule(errors, "LIF-RECOVERY-OUTSIDE-RUN"));

  advance(machine, RunPhase::preflight, 11U);
  advance(machine, RunPhase::pre_run_failure, 12U, early_failure_consequences());
  advance(machine, RunPhase::finalized_invalid, 13U, invalid_consequences());
  EXPECT_TRUE(machine
                  .record_recovery({"recovery-fixture", 5U, 14U, 19U, "controller",
                                    "registered recovery", "recovery-evidence"})
                  .empty());
  ASSERT_EQ(machine.recoveries().size(), 1U);
  EXPECT_EQ(machine.recoveries().front().duration_ticks, 5U);
}

auto warm_identity() -> WarmStartIdentity {
  return {"allocation-fixture", "mapping-fixture", "home-fixture",
          "permutation-fixture", "payload-fixture"};
}

auto valid_reset(QueueResetKind kind) -> LogicalResetEvidence {
  return {kind,
          4U,
          true,
          true,
          true,
          0U,
          true,
          true,
          true,
          true,
          true,
          4U,
          0U,
          0U,
          0U,
          0U,
          0U,
          0U,
          0U,
          0U,
          0x1234U,
          true,
          warm_identity(),
          0U,
          false,
          false,
          false};
}

class FakeResetBackend final : public LogicalResetBackend {
public:
  explicit FakeResetBackend(LogicalResetEvidence evidence)
      : evidence_(std::move(evidence)) {}

  [[nodiscard]] auto perform(const LogicalResetRequest&)
      -> cpu_prefetch::protocol::Result<LogicalResetEvidence> override {
    ++calls_;
    return cpu_prefetch::protocol::Result<LogicalResetEvidence>::success(evidence_);
  }

  [[nodiscard]] auto calls() const noexcept -> std::uint64_t { return calls_; }

private:
  LogicalResetEvidence evidence_;
  std::uint64_t calls_{0U};
};

TEST(LifecycleReset, RingAndLinkedWarmStartEvidencePassDeterministically) {
  for (const auto kind : {QueueResetKind::ring, QueueResetKind::linked}) {
    const LogicalResetRequest request{kind, 4U, 0x1234U, warm_identity()};
    FakeResetBackend first(valid_reset(kind));
    FakeResetBackend second(valid_reset(kind));
    auto first_result =
        cpu_prefetch::lifecycle::perform_and_verify_logical_reset(first, request);
    auto second_result =
        cpu_prefetch::lifecycle::perform_and_verify_logical_reset(second, request);
    ASSERT_TRUE(first_result);
    ASSERT_TRUE(second_result);
    EXPECT_EQ(first_result.value().identity_after_reset,
              second_result.value().identity_after_reset);
    EXPECT_EQ(first_result.value().allocation_count_delta, 0U);
    EXPECT_EQ(first.calls(), 1U);
    EXPECT_EQ(second.calls(), 1U);
  }
}

TEST(LifecycleReset, EveryWarmStartLeakFailsClosed) {
  const LogicalResetRequest request{QueueResetKind::ring, 4U, 0x1234U, warm_identity()};
  auto assert_invalid = [&](const LogicalResetEvidence& evidence,
                            const std::string& rule) {
    const auto errors =
        cpu_prefetch::lifecycle::validate_logical_reset(request, evidence);
    EXPECT_TRUE(has_rule(errors, rule));
  };

  auto evidence = valid_reset(QueueResetKind::ring);
  evidence.queue_drained = false;
  assert_invalid(evidence, "LIF-WARMUP-BOUNDARY");
  evidence = valid_reset(QueueResetKind::ring);
  evidence.occupancy_after_reset = 1U;
  assert_invalid(evidence, "LIF-RESET-EMPTY");
  evidence = valid_reset(QueueResetKind::ring);
  evidence.ring_slots_empty = false;
  assert_invalid(evidence, "LIF-RING-RESET");
  evidence = valid_reset(QueueResetKind::ring);
  evidence.accepted_ordinal = 1U;
  assert_invalid(evidence, "LIF-LOGICAL-ZERO");
  evidence = valid_reset(QueueResetKind::ring);
  evidence.consumer_checksum = 0U;
  assert_invalid(evidence, "LIF-CHECKSUM-RESET");
  evidence = valid_reset(QueueResetKind::ring);
  evidence.measurement_origin_cleared = false;
  assert_invalid(evidence, "LIF-ORIGIN-RESET");
  evidence = valid_reset(QueueResetKind::ring);
  evidence.allocation_count_delta = 1U;
  assert_invalid(evidence, "LIF-WARM-START-PRESERVE");
  evidence = valid_reset(QueueResetKind::ring);
  evidence.regenerated_schedule = true;
  assert_invalid(evidence, "LIF-WARM-START-PRESERVE");
  evidence = valid_reset(QueueResetKind::ring);
  evidence.remapped_memory = true;
  assert_invalid(evidence, "LIF-WARM-START-PRESERVE");
  evidence = valid_reset(QueueResetKind::ring);
  evidence.retouched_payload = true;
  assert_invalid(evidence, "LIF-WARM-START-PRESERVE");

  const LogicalResetRequest linked_request{QueueResetKind::linked, 4U, 0x1234U,
                                           warm_identity()};
  evidence = valid_reset(QueueResetKind::linked);
  evidence.linked_recycler_order_is_pi1_to_pi_c = false;
  EXPECT_TRUE(has_rule(
      cpu_prefetch::lifecycle::validate_logical_reset(linked_request, evidence),
      "LIF-LINKED-RESET"));
  evidence = valid_reset(QueueResetKind::linked);
  evidence.linked_recycler_node_count = 3U;
  EXPECT_TRUE(has_rule(
      cpu_prefetch::lifecycle::validate_logical_reset(linked_request, evidence),
      "LIF-LINKED-RESET"));
}

TEST(LifecycleSchedule, PreparedScheduleIsHalfOpenAndNondecreasing) {
  const std::array<std::uint64_t, 3U> good{5U, 5U, 9U};
  EXPECT_TRUE(
      cpu_prefetch::lifecycle::validate_prepared_schedule({good, 5U, 10U}).empty());
  const std::array<std::uint64_t, 2U> at_horizon{5U, 10U};
  EXPECT_TRUE(has_rule(
      cpu_prefetch::lifecycle::validate_prepared_schedule({at_horizon, 5U, 10U}),
      "LIF-SCHEDULE-HALF-OPEN"));
  const std::array<std::uint64_t, 2U> decreasing{6U, 5U};
  EXPECT_TRUE(has_rule(
      cpu_prefetch::lifecycle::validate_prepared_schedule({decreasing, 5U, 10U}),
      "LIF-SCHEDULE-NONDECREASING"));
}

TEST(LifecyclePreparation, InitializationAndWarmupMustBeCompleteAndIsolated) {
  const auto lifecycle_context = context();
  PreparationEvidence preparation{lifecycle_context.warmup_schedule_id,
                                  lifecycle_context.measurement_schedule_id,
                                  lifecycle_context.warmup_namespace_id,
                                  lifecycle_context.measurement_namespace_id,
                                  "deterministic-init-fixture",
                                  true,
                                  true,
                                  true,
                                  true,
                                  true,
                                  true,
                                  true,
                                  true,
                                  17U};
  EXPECT_TRUE(cpu_prefetch::lifecycle::validate_preparation(
                  lifecycle_context.warmup_schedule_id,
                  lifecycle_context.measurement_schedule_id,
                  lifecycle_context.warmup_namespace_id,
                  lifecycle_context.measurement_namespace_id, preparation)
                  .empty());

  preparation.observation_storage_preallocated = false;
  EXPECT_TRUE(has_rule(cpu_prefetch::lifecycle::validate_preparation(
                           lifecycle_context.warmup_schedule_id,
                           lifecycle_context.measurement_schedule_id,
                           lifecycle_context.warmup_namespace_id,
                           lifecycle_context.measurement_namespace_id, preparation),
                       "LIF-PREP-READY"));

  WarmupCompletionEvidence warmup{lifecycle_context.warmup_schedule_id,
                                  lifecycle_context.warmup_namespace_id,
                                  11U,
                                  11U,
                                  true,
                                  true,
                                  true,
                                  true,
                                  false,
                                  false,
                                  false,
                                  0U};
  EXPECT_TRUE(cpu_prefetch::lifecycle::validate_warmup_completion(
                  lifecycle_context.warmup_schedule_id,
                  lifecycle_context.warmup_namespace_id, warmup)
                  .empty());
  warmup.attempted_count = 10U;
  EXPECT_TRUE(has_rule(cpu_prefetch::lifecycle::validate_warmup_completion(
                           lifecycle_context.warmup_schedule_id,
                           lifecycle_context.warmup_namespace_id, warmup),
                       "LIF-WARMUP-COMPLETE"));
  warmup.attempted_count = 11U;
  warmup.measurement_observations_emitted = true;
  EXPECT_TRUE(has_rule(cpu_prefetch::lifecycle::validate_warmup_completion(
                           lifecycle_context.warmup_schedule_id,
                           lifecycle_context.warmup_namespace_id, warmup),
                       "LIF-WARMUP-ISOLATED"));
}

TEST(LifecycleStateMachine, WarmupAndMeasurementIdentitiesMustBeDisjoint) {
  auto bad_context = context();
  bad_context.measurement_namespace_id = bad_context.warmup_namespace_id;
  bad_context.measurement_schedule_id = bad_context.warmup_schedule_id;
  const auto result = RunStateMachine::create(
      bad_context,
      {RunPhase::planned,
       10U,
       "controller",
       "plan",
       {consequence(LifecycleArtifactKind::plan, ArtifactAction::retain, 1U)}});
  ASSERT_FALSE(result);
  EXPECT_TRUE(has_rule(result.errors(), "LIF-NAMESPACE-SEPARATION"));
  EXPECT_TRUE(has_rule(result.errors(), "LIF-SCHEDULE-SEPARATION"));
}

} // namespace
