#include "cpu_prefetch/protocol/model.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <set>
#include <string>
#include <tuple>
#include <type_traits>
#include <utility>
#include <variant>
#include <vector>

namespace cpu_prefetch::protocol {
namespace {

void add(std::vector<ValidationError>& errors, ErrorCategory category, std::string path,
         std::string rule, std::string message) {
  errors.push_back({category, std::move(path), std::move(rule), std::move(message)});
}

auto checked_add(std::uint64_t left, std::uint64_t right, std::uint64_t& output)
    -> bool {
  if (right > std::numeric_limits<std::uint64_t>::max() - left) {
    return false;
  }
  output = left + right;
  return true;
}

auto has_relationship(const RunManifest& manifest, ArtifactRelationship relationship)
    -> bool {
  return std::ranges::any_of(manifest.artifact_refs, [&](const auto& artifact) {
    return artifact.relationship == relationship;
  });
}

auto at_least_200000(const json::Number& number) -> bool {
  if (number.kind == json::Number::Kind::signed_integer) {
    return std::get<std::int64_t>(number.value) >= 200000;
  }
  if (number.kind == json::Number::Kind::unsigned_integer) {
    return std::get<std::uint64_t>(number.value) >= 200000U;
  }
  return std::get<double>(number.value) >= 200000.0;
}

auto is_failure_lifecycle(LifecycleState state) -> bool {
  return state == LifecycleState::pre_run_failure ||
         state == LifecycleState::warmup_failure ||
         state == LifecycleState::reset_failure ||
         state == LifecycleState::measurement_failure ||
         state == LifecycleState::drain_failure;
}

auto is_early_failure(LifecycleState state) -> bool {
  return state == LifecycleState::pre_run_failure ||
         state == LifecycleState::warmup_failure ||
         state == LifecycleState::reset_failure;
}

auto validate_schedule(const ScheduleRecord& schedule) -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  if (schedule.horizon_ticks == 0) {
    add(errors, ErrorCategory::out_of_range, "$out/horizon_ticks", "SCH-HORIZON",
        "schedule horizon must be positive");
  }
  if (schedule.nominal_offered_rate.denominator_ticks == 0) {
    add(errors, ErrorCategory::out_of_range,
        "$out/nominal_offered_rate/denominator_ticks", "SCH-RATE-DENOMINATOR",
        "exact rate denominator must be positive");
  }
  if (schedule.schedule_kind == ScheduleKind::confirmatory &&
      schedule.arrival_family != ArrivalFamily::poisson_exponential) {
    add(errors, ErrorCategory::cross_field, "$out/arrival_family",
        "SCH-CONFIRMATORY-FAMILY",
        "confirmatory schedules require POISSON_EXPONENTIAL arrivals");
  }
  if (const auto* external =
          std::get_if<ExternalScheduleStorage>(&schedule.deadline_storage)) {
    if (external->row_count != schedule.offered_count) {
      add(errors, ErrorCategory::cross_field, "$out/deadline_storage/row_count",
          "SCH-ROW-COUNT", "external schedule row count must equal offered_count");
    }
    return errors;
  }
  const auto& encoded =
      std::get<InlineDeadlineStorage>(schedule.deadline_storage).deadline_ticks;
  if (encoded.size() != schedule.offered_count) {
    add(errors, ErrorCategory::cross_field, "$out/deadline_storage/deadline_ticks",
        "SCH-DECODED-COUNT", "decoded deadline count must equal offered_count");
  }
  std::uint64_t horizon_end = 0;
  if (!checked_add(schedule.origin_ticks, schedule.horizon_ticks, horizon_end)) {
    add(errors, ErrorCategory::out_of_range, "$out/horizon_ticks",
        "SCH-HORIZON-OVERFLOW", "origin plus horizon overflows the 64-bit tick domain");
    return errors;
  }
  std::uint64_t previous = 0;
  bool have_previous = false;
  std::uint64_t accumulated = schedule.origin_ticks;
  for (std::size_t index = 0; index < encoded.size(); ++index) {
    std::uint64_t deadline = encoded[index];
    if (schedule.deadline_encoding == DeadlineEncoding::delta_integer_ticks) {
      if (!checked_add(accumulated, encoded[index], deadline)) {
        add(errors, ErrorCategory::out_of_range,
            "$out/deadline_storage/deadline_ticks/" + std::to_string(index),
            "SCH-DELTA-OVERFLOW", "delta decoding overflows the 64-bit tick domain");
        continue;
      }
      accumulated = deadline;
    }
    if (have_previous && deadline < previous) {
      add(errors, ErrorCategory::cross_field,
          "$out/deadline_storage/deadline_ticks/" + std::to_string(index),
          "SCH-NONDECREASING", "decoded deadlines must be nondecreasing");
    }
    if (deadline < schedule.origin_ticks || deadline >= horizon_end) {
      add(errors, ErrorCategory::cross_field,
          "$out/deadline_storage/deadline_ticks/" + std::to_string(index),
          "SCH-HALF-OPEN", "decoded deadline is outside [origin, origin+horizon)");
    }
    previous = deadline;
    have_previous = true;
  }
  return errors;
}

void validate_producer(const ProducerRecord& row, const RunId& envelope_run_id,
                       const std::string& path, std::vector<ValidationError>& errors) {
  if (row.run_id != envelope_run_id) {
    add(errors, ErrorCategory::reference_mismatch, path + "/run_id", "DAT-RUN-ID-MATCH",
        "row run_id must match its envelope");
  }
  if (!(row.scheduled_arrival <= row.producer_handle_begin &&
        row.producer_handle_begin <= row.record_lookup_completion &&
        row.record_lookup_completion <= row.enqueue_invocation &&
        row.enqueue_invocation <= row.enqueue_attempt_completion)) {
    add(errors, ErrorCategory::cross_field, path, "TIM-PRODUCER-ORDER",
        "producer timestamps violate their protocol order");
  }
  if (row.outcome == ProducerOutcome::accepted) {
    if (!row.enqueue_linearization || !row.accepted_ordinal) {
      add(errors, ErrorCategory::missing_field, path, "RAW-ACCEPTED-FIELDS",
          "accepted row requires linearization and accepted ordinal");
    } else if (*row.enqueue_linearization < row.enqueue_invocation ||
               *row.enqueue_linearization > row.enqueue_attempt_completion) {
      add(errors, ErrorCategory::cross_field, path + "/enqueue_linearization",
          "TIM-ENQUEUE-LINEARIZATION",
          "enqueue linearization must lie between invocation and completion");
    }
  } else if (row.enqueue_linearization || row.accepted_ordinal) {
    add(errors, ErrorCategory::cross_field, path, "RAW-FULL-FIELDS",
        "FULL row must not have accepted-only fields");
  }
}

void validate_consumer(const ConsumerRecord& row, const RunId& envelope_run_id,
                       const std::string& path, std::vector<ValidationError>& errors) {
  if (row.run_id != envelope_run_id) {
    add(errors, ErrorCategory::reference_mismatch, path + "/run_id", "DAT-RUN-ID-MATCH",
        "row run_id must match its envelope");
  }
  if (!(row.dequeue_invocation <= row.dequeue_linearization &&
        row.dequeue_linearization <= row.dequeue_completion &&
        row.dequeue_completion <= row.consumer_action_completion)) {
    add(errors, ErrorCategory::cross_field, path, "TIM-CONSUMER-ORDER",
        "consumer timestamps violate their protocol order");
  }
}

void validate_joined(const JoinedRecord& row, const RunId& envelope_run_id,
                     const std::string& path, std::vector<ValidationError>& errors) {
  if (row.run_id != envelope_run_id) {
    add(errors, ErrorCategory::reference_mismatch, path + "/run_id", "DAT-RUN-ID-MATCH",
        "row run_id must match its envelope");
  }
  const bool order = row.scheduled_arrival <= row.producer_handle_begin &&
                     row.producer_handle_begin <= row.record_lookup_completion &&
                     row.record_lookup_completion <= row.enqueue_invocation &&
                     row.enqueue_invocation <= row.enqueue_linearization &&
                     row.enqueue_linearization <= row.enqueue_attempt_completion &&
                     row.dequeue_invocation <= row.dequeue_linearization &&
                     row.dequeue_linearization <= row.dequeue_completion &&
                     row.dequeue_completion <= row.consumer_action_completion &&
                     row.enqueue_linearization <= row.dequeue_linearization;
  if (!order) {
    add(errors, ErrorCategory::cross_field, path, "TIM-JOINED-ORDER",
        "joined timestamps violate producer, consumer, or queue order");
    return;
  }
  const auto expect = [&](std::uint64_t actual, std::uint64_t calculated,
                          std::string_view field, std::string_view rule) {
    if (actual != calculated) {
      add(errors, ErrorCategory::cross_field, path + "/" + std::string(field),
          std::string(rule), "derived interval does not equal its timestamp equation");
    }
  };
  expect(row.producer_lateness, row.producer_handle_begin - row.scheduled_arrival,
         "producer_lateness", "TIM-EQ-PRODUCER-LATENESS");
  expect(row.pointer_lookup_interval,
         row.record_lookup_completion - row.producer_handle_begin,
         "pointer_lookup_interval", "TIM-EQ-POINTER-LOOKUP");
  expect(row.enqueue_service_time,
         row.enqueue_attempt_completion - row.enqueue_invocation,
         "enqueue_service_time", "TIM-EQ-ENQUEUE-SERVICE");
  expect(row.admission_delay, row.enqueue_linearization - row.scheduled_arrival,
         "admission_delay", "TIM-EQ-ADMISSION");
  expect(row.queue_residence, row.dequeue_linearization - row.enqueue_linearization,
         "queue_residence", "TIM-EQ-RESIDENCE");
  expect(row.dequeue_service_time, row.dequeue_completion - row.dequeue_invocation,
         "dequeue_service_time", "TIM-EQ-DEQUEUE-SERVICE");
  expect(row.post_dequeue_delivery_interval,
         row.consumer_action_completion - row.dequeue_linearization,
         "post_dequeue_delivery_interval", "TIM-EQ-DELIVERY");
  expect(row.consumer_action_interval,
         row.consumer_action_completion - row.dequeue_completion,
         "consumer_action_interval", "TIM-EQ-CONSUMER-ACTION");
  expect(row.end_to_end_latency, row.consumer_action_completion - row.scheduled_arrival,
         "end_to_end_latency", "TIM-EQ-END-TO-END");
  std::uint64_t partial = 0;
  std::uint64_t sum = 0;
  if (!checked_add(row.admission_delay, row.queue_residence, partial) ||
      !checked_add(partial, row.post_dequeue_delivery_interval, sum) ||
      sum != row.end_to_end_latency) {
    add(errors, ErrorCategory::cross_field, path + "/end_to_end_latency",
        "TIM-EQ-ADDITIVE",
        "end-to-end latency must equal admission + residence + delivery");
  }
}

auto validate_raw(const RawObservationEnvelope& envelope)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  const auto* inline_rows = std::get_if<InlineObservationRows>(&envelope.storage);
  if (inline_rows == nullptr) {
    return errors;
  }
  std::visit(
      [&](const auto& rows) {
        if (rows.size() != envelope.row_count) {
          add(errors, ErrorCategory::cross_field, "$out/row_count", "DAT-RAW-ROW-COUNT",
              "envelope row_count must equal the inline logical row count");
        }
        for (std::size_t index = 0; index < rows.size(); ++index) {
          const auto path = "$out/storage/inline_rows/" + std::to_string(index);
          using Row = typename std::decay_t<decltype(rows)>::value_type;
          if constexpr (std::is_same_v<Row, ProducerRecord>) {
            validate_producer(rows[index], envelope.run_id, path, errors);
          } else if constexpr (std::is_same_v<Row, ConsumerRecord>) {
            validate_consumer(rows[index], envelope.run_id, path, errors);
          } else {
            validate_joined(rows[index], envelope.run_id, path, errors);
          }
        }
      },
      *inline_rows);
  return errors;
}

auto validate_manifest(const RunManifest& manifest) -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  if (manifest.protocol_version != ProtocolVersion::v2_0_0_pre_1) {
    const auto& blockers = manifest.confirmatory_blockers;
    if (!std::ranges::is_sorted(blockers) ||
        std::ranges::adjacent_find(blockers) != blockers.end()) {
      add(errors, ErrorCategory::duplicate_value, "$out/confirmatory_blockers",
          "LIF-BLOCKER-CANONICAL-ORDER",
          "confirmatory blockers must be unique and in ascending UTF-8 token order");
    }

    const bool evidence_pending =
        manifest.validity == RunValidity::not_evaluated ||
        manifest.zero_loss_status == GateStatus::not_evaluated ||
        manifest.effective_tail_status == GateStatus::not_evaluated ||
        manifest.block_completeness == BlockCompleteness::not_evaluated;
    if (evidence_pending && (manifest.confirmatory_estimability !=
                                 ConfirmatoryEstimability::not_evaluated ||
                             !blockers.empty())) {
      add(errors, ErrorCategory::cross_field, "$out/confirmatory_estimability",
          "LIF-BLOCKER-EVIDENCE-COMPLETE",
          "final estimability and blocker values require authoritative evidence for "
          "every applicable gate");
    }

    const auto contains = [&](ConfirmatoryBlocker blocker) {
      return std::ranges::find(blockers, blocker) != blockers.end();
    };
    if (!evidence_pending) {
      const bool local_mismatch =
          contains(ConfirmatoryBlocker::blocked_zero_loss) !=
              (manifest.zero_loss_status == GateStatus::fail) ||
          contains(ConfirmatoryBlocker::blocked_effective_tail) !=
              (manifest.effective_tail_status == GateStatus::fail) ||
          contains(ConfirmatoryBlocker::blocked_invalid_run) !=
              (manifest.validity == RunValidity::invalid) ||
          contains(ConfirmatoryBlocker::blocked_incomplete_block) !=
              (manifest.block_completeness == BlockCompleteness::incomplete);
      if (local_mismatch) {
        add(errors, ErrorCategory::cross_field, "$out/confirmatory_blockers",
            "LIF-BLOCKER-EXHAUSTIVE-LOCAL",
            "the blocker array must exactly reflect every locally represented "
            "failed gate");
      }
    }

    ConfirmatoryEstimability expected_summary = ConfirmatoryEstimability::not_evaluated;
    if (!evidence_pending) {
      if (blockers.empty()) {
        expected_summary = ConfirmatoryEstimability::estimable;
      } else if (blockers.size() > 1U) {
        expected_summary = ConfirmatoryEstimability::blocked_multiple;
      } else {
        switch (blockers.front()) {
        case ConfirmatoryBlocker::blocked_access_leakage:
          expected_summary = ConfirmatoryEstimability::blocked_access_leakage;
          break;
        case ConfirmatoryBlocker::blocked_effective_tail:
          expected_summary = ConfirmatoryEstimability::blocked_effective_tail;
          break;
        case ConfirmatoryBlocker::blocked_incomplete_block:
          expected_summary = ConfirmatoryEstimability::blocked_incomplete_block;
          break;
        case ConfirmatoryBlocker::blocked_invalid_run:
          expected_summary = ConfirmatoryEstimability::blocked_invalid_run;
          break;
        case ConfirmatoryBlocker::blocked_zero_loss:
          expected_summary = ConfirmatoryEstimability::blocked_zero_loss;
          break;
        }
      }
    }
    if (manifest.confirmatory_estimability != expected_summary) {
      add(errors, ErrorCategory::cross_field, "$out/confirmatory_estimability",
          "LIF-BLOCKER-SUMMARY",
          "estimability summary does not match the exhaustive blocker array");
    }
  }
  if (manifest.stage == Stage::stage_a &&
      (manifest.run_mode != RunMode::latency ||
       manifest.block_role == BlockRole::not_applicable ||
       manifest.package == QueuePackage::nblfq_mpsc ||
       manifest.package == QueuePackage::not_applicable ||
       manifest.requested_hardware_state == RequestedHardwareState::not_applicable ||
       manifest.placement == Placement::not_applicable ||
       manifest.placement == Placement::stage_c_other ||
       manifest.working_set_class == WorkingSetClass::not_applicable ||
       manifest.load_level == LoadLevel::not_applicable ||
       manifest.load_level == LoadLevel::calibration_ready ||
       manifest.load_level == LoadLevel::stage_c_other)) {
    add(errors, ErrorCategory::cross_field, "$out", "LIF-STAGE-A-FACTORS",
        "Stage A manifest factors must use the exact registered Stage A levels");
  }
  if (is_failure_lifecycle(manifest.lifecycle_state) &&
      (manifest.validity != RunValidity::invalid ||
       manifest.failure_record_ids.empty())) {
    add(errors, ErrorCategory::missing_evidence, "$out/failure_record_ids",
        "LIF-FAILURE-EVIDENCE",
        "failure lifecycle requires INVALID and a failure record");
  }
  if (manifest.validity == RunValidity::invalid &&
      manifest.failure_record_ids.empty()) {
    add(errors, ErrorCategory::missing_evidence, "$out/failure_record_ids",
        "LIF-INVALID-EVIDENCE", "invalid run requires a failure record");
  }
  if (is_early_failure(manifest.lifecycle_state)) {
    const bool fabricated =
        manifest.counts || manifest.integrity_evidence ||
        has_relationship(manifest, ArtifactRelationship::producer_raw) ||
        has_relationship(manifest, ArtifactRelationship::consumer_raw) ||
        has_relationship(manifest, ArtifactRelationship::join_audit) ||
        has_relationship(manifest, ArtifactRelationship::joined_derived) ||
        has_relationship(manifest, ArtifactRelationship::phase_integrity_report);
    if (fabricated) {
      add(errors, ErrorCategory::cross_field, "$out/artifact_refs",
          "LIF-NO-FABRICATION",
          "early failure must not fabricate measurement, join, or integrity artifacts");
    }
  }
  if (manifest.join_status == JoinStatus::failed) {
    if (manifest.validity != RunValidity::invalid ||
        manifest.failure_record_ids.empty() ||
        !has_relationship(manifest, ArtifactRelationship::join_audit) ||
        has_relationship(manifest, ArtifactRelationship::joined_derived)) {
      add(errors, ErrorCategory::cross_field, "$out/join_status", "DAT-FAILED-JOIN",
          "failed join requires invalidity, failure evidence, a join audit, and no "
          "joined data");
    }
  }
  const bool completed_stage_a =
      manifest.stage == Stage::stage_a &&
      manifest.lifecycle_state == LifecycleState::completed &&
      manifest.validity == RunValidity::valid;
  if (!completed_stage_a) {
    return errors;
  }
  const std::array required_relationships{ArtifactRelationship::producer_raw,
                                          ArtifactRelationship::consumer_raw,
                                          ArtifactRelationship::join_audit,
                                          ArtifactRelationship::joined_derived,
                                          ArtifactRelationship::phase_integrity_report,
                                          ArtifactRelationship::provenance};
  if (!manifest.counts || !manifest.integrity_evidence ||
      manifest.join_status != JoinStatus::passed ||
      manifest.count_reconciliation != GateStatus::pass) {
    add(errors, ErrorCategory::missing_evidence, "$out", "LIF-COMPLETED-EVIDENCE",
        "valid completed Stage A run requires counts, integrity, passed join and "
        "reconciliation");
  }
  for (auto relationship : required_relationships) {
    if (!has_relationship(manifest, relationship)) {
      add(errors, ErrorCategory::missing_evidence, "$out/artifact_refs",
          "LIF-COMPLETED-ARTIFACTS",
          "valid completed Stage A run is missing a required artifact relationship");
    }
  }
  if (!manifest.counts) {
    return errors;
  }
  const auto& counts = *manifest.counts;
  const bool complete_counts = counts.offered && counts.attempted && counts.accepted &&
                               counts.full && counts.consumed &&
                               counts.final_occupancy && counts.raw_sample_count &&
                               counts.n_eff_p999;
  if (!complete_counts) {
    add(errors, ErrorCategory::missing_field, "$out/counts", "LIF-COMPLETE-COUNTS",
        "valid completed Stage A run requires every registered count");
    return errors;
  }
  const auto offered = counts.offered.value_or(0);
  const auto attempted = counts.attempted.value_or(0);
  const auto accepted = counts.accepted.value_or(0);
  const auto full = counts.full.value_or(0);
  const auto consumed = counts.consumed.value_or(0);
  const auto final_occupancy = counts.final_occupancy.value_or(0);
  const auto raw_sample_count = counts.raw_sample_count.value_or(0);
  const auto n_eff_p999 = counts.n_eff_p999.value_or(
      json::Number{json::Number::Kind::signed_integer, "0", std::int64_t{0}});
  std::uint64_t attempted_from_outcomes = 0;
  const bool outcome_sum_valid = checked_add(accepted, full, attempted_from_outcomes);
  if (offered != attempted || !outcome_sum_valid ||
      attempted != attempted_from_outcomes || consumed != accepted ||
      final_occupancy != 0 || raw_sample_count != accepted) {
    add(errors, ErrorCategory::cross_field, "$out/counts", "DAT-COUNT-IDENTITIES",
        "completed count identities or zero final occupancy do not reconcile");
  }
  const GateStatus expected_zero = full == 0 ? GateStatus::pass : GateStatus::fail;
  if (manifest.zero_loss_status != expected_zero) {
    add(errors, ErrorCategory::cross_field, "$out/zero_loss_status", "LIF-ZERO-LOSS",
        "zero-loss status must be independent and derived from the FULL count");
  }
  const GateStatus expected_tail =
      at_least_200000(n_eff_p999) ? GateStatus::pass : GateStatus::fail;
  if (manifest.effective_tail_status != expected_tail) {
    add(errors, ErrorCategory::cross_field, "$out/effective_tail_status",
        "LIF-EFFECTIVE-TAIL",
        "effective-tail status must use the fixed N_eff=200000 threshold");
  }
  const auto estimability = manifest.confirmatory_estimability;
  const bool incorrectly_estimable =
      estimability == ConfirmatoryEstimability::estimable &&
      (expected_zero == GateStatus::fail || expected_tail == GateStatus::fail ||
       manifest.block_completeness == BlockCompleteness::incomplete);
  const bool selected_reason_does_not_apply =
      (estimability == ConfirmatoryEstimability::blocked_zero_loss &&
       expected_zero != GateStatus::fail) ||
      (estimability == ConfirmatoryEstimability::blocked_effective_tail &&
       expected_tail != GateStatus::fail) ||
      (estimability == ConfirmatoryEstimability::blocked_invalid_run &&
       manifest.validity != RunValidity::invalid) ||
      (estimability == ConfirmatoryEstimability::blocked_incomplete_block &&
       manifest.block_completeness != BlockCompleteness::incomplete);
  if (manifest.protocol_version == ProtocolVersion::v2_0_0_pre_1 &&
      (incorrectly_estimable || selected_reason_does_not_apply)) {
    add(errors, ErrorCategory::cross_field, "$out/confirmatory_estimability",
        "LIF-ESTIMABILITY-APPLICABILITY",
        "estimability must remain blocked when a local gate fails and any selected "
        "blocking reason must apply; Stage 4 does not invent precedence among "
        "simultaneous blockers");
  }
  return errors;
}

auto validate_block(const BlockPlan& block) -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  if (block.whole_plot_order[0] == block.whole_plot_order[1] ||
      (block.whole_plot_order[0] != RequestedHardwareState::h0 &&
       block.whole_plot_order[1] != RequestedHardwareState::h0) ||
      (block.whole_plot_order[0] != RequestedHardwareState::h1 &&
       block.whole_plot_order[1] != RequestedHardwareState::h1)) {
    add(errors, ErrorCategory::duplicate_value, "$out/whole_plot_order",
        "BLK-WHOLE-PLOTS", "whole plots must contain H0 and H1 exactly once");
  }
  if (block.cells.size() != 180) {
    add(errors, ErrorCategory::out_of_range, "$out/cells", "BLK-180-CELLS",
        "Stage A block requires exactly 180 cells");
  }
  using CellKey = std::tuple<QueuePackage, RequestedHardwareState, Placement,
                             WorkingSetClass, LoadLevel>;
  std::set<CellKey> cells;
  std::set<std::uint64_t> ordinals;
  for (std::size_t index = 0; index < block.cells.size(); ++index) {
    const auto& cell = block.cells[index];
    cells.emplace(cell.package, cell.requested_hardware_state, cell.placement,
                  cell.working_set_class, cell.load_level);
    ordinals.insert(cell.cell_ordinal);
    const bool linked =
        cell.package == QueuePackage::l0 || cell.package == QueuePackage::l1;
    if (linked != cell.node_seed_ref.has_value()) {
      add(errors, ErrorCategory::cross_field,
          "$out/cells/" + std::to_string(index) + "/node_seed_ref", "BLK-NODE-SEED",
          "node seed is required only for linked packages");
    }
  }
  if (cells.size() != 180) {
    add(errors, ErrorCategory::duplicate_value, "$out/cells", "BLK-FACTORIAL-PRODUCT",
        "cells must contain every registered Stage A Cartesian-product tuple exactly "
        "once");
  }
  bool ordinals_complete = ordinals.size() == 180;
  for (std::uint64_t ordinal = 0; ordinal < 180 && ordinals_complete; ++ordinal) {
    ordinals_complete = ordinals.contains(ordinal);
  }
  if (!ordinals_complete) {
    add(errors, ErrorCategory::cross_field, "$out/cells", "BLK-CELL-ORDINALS",
        "cell ordinals must be exactly 0 through 179");
  }
  const bool replacement = block.replaces_block_id.has_value();
  if (replacement != block.replacement_authorization_id.has_value() ||
      replacement != block.replacement_lineage.has_value()) {
    add(errors, ErrorCategory::cross_field, "$out/replaces_block_id",
        "BLK-REPLACEMENT-SHAPE",
        "replacement fields must be all absent or all present");
  }
  if (block.replacement_lineage && block.replaces_block_id) {
    const auto& lineage = block.replacement_lineage.value();
    if (block.block_id == block.replaces_block_id.value() ||
        block.block_ordinal == lineage.replaced_block_ordinal ||
        block.seed_subspace_id == lineage.replaced_seed_subspace_id ||
        block.block_role != lineage.replaced_block_role) {
      add(errors, ErrorCategory::cross_field, "$out/replacement_lineage",
          "BLK-REPLACEMENT-LINEAGE",
          "replacement requires new ID/ordinal/subspace and the same immutable role");
    }
  }
  return errors;
}

auto validate_failure(const FailureRecord& failure) -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  if (failure.scope == FailureScope::run && (!failure.run_id || !failure.block_id)) {
    add(errors, ErrorCategory::missing_field, "$out/run_id", "FAIL-RUN-IDENTITY",
        "run-scoped failure requires run_id and block_id");
  }
  if (failure.invalidates_run && failure.stage == Stage::stage_a &&
      failure.block_consequence != BlockConsequence::original_block_incomplete &&
      failure.block_consequence != BlockConsequence::study_unresolved) {
    add(errors, ErrorCategory::cross_field, "$out/block_consequence",
        "FAIL-STAGE-A-CONSEQUENCE",
        "invalid Stage A run makes its original block incomplete or study unresolved");
  }
  if (failure.resolution_status == ResolutionStatus::replacement_authorized &&
      (!failure.replacement_authorization_id || !failure.replacement_block_id)) {
    add(errors, ErrorCategory::missing_evidence, "$out/replacement_authorization_id",
        "FAIL-REPLACEMENT-EVIDENCE",
        "authorized replacement requires authorization and replacement block IDs");
  }
  return errors;
}

auto validate_freeze(const FreezeRecord& record) -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  const auto require_blocks = [&] {
    if (record.affected_block_ids.empty()) {
      add(errors, ErrorCategory::missing_evidence, "$out/affected_block_ids",
          "ACC-AFFECTED-BLOCKS",
          "this record kind requires a nonempty affected block list");
    }
  };
  switch (record.record_kind) {
  case RecordKind::selection_freeze:
    require_blocks();
    if (record.status != FreezeStatus::frozen ||
        record.authorization_status != AuthorizationStatus::authorized ||
        record.authority.role != AuthorityRole::freeze_authority ||
        record.access_state_before != AccessState::training_open ||
        record.access_state_after != AccessState::selection_frozen ||
        !record.outcome_access_prohibited || record.h3_selections.size() != 6 ||
        record.training_input_artifacts.empty() || !record.selection_rule_version ||
        !record.selection_record_checksum_sha256) {
      add(errors, ErrorCategory::missing_evidence, "$out", "ACC-SELECTION-FREEZE",
          "selection freeze lacks exact contexts, evidence, authority, or state "
          "transition");
    }
    break;
  case RecordKind::validation_unseal:
    require_blocks();
    if (record.status != FreezeStatus::authorized ||
        record.authorization_status != AuthorizationStatus::authorized ||
        record.authority.role != AuthorityRole::validation_custodian ||
        record.access_state_before != AccessState::selection_frozen ||
        record.access_state_after != AccessState::validation_unsealed ||
        record.outcome_access_prohibited || !record.selection_record_ref ||
        !record.validation_namespace_id || !record.validation_artifact_ref) {
      add(errors, ErrorCategory::missing_evidence, "$out", "ACC-VALIDATION-UNSEAL",
          "validation unseal requires selection and validation IDs/hashes and exact "
          "custody transition");
    }
    break;
  case RecordKind::h3_evaluated:
    require_blocks();
    if (record.authority.role != AuthorityRole::confirmatory_analyst ||
        record.access_state_before != AccessState::validation_unsealed ||
        record.access_state_after != AccessState::h3_evaluated ||
        !record.selection_record_ref || !record.validation_namespace_id ||
        !record.validation_artifact_ref || !record.validation_unseal_record_ref ||
        !record.h3_evaluation_artifact_ref) {
      add(errors, ErrorCategory::missing_evidence, "$out", "ACC-H3-EVALUATED",
          "H3 evaluation lacks a required predecessor or evaluation artifact hash");
    }
    break;
  case RecordKind::h1h2_released:
    require_blocks();
    if (record.authority.role != AuthorityRole::validation_custodian ||
        record.access_state_before != AccessState::h3_evaluated ||
        record.access_state_after != AccessState::h1h2_released ||
        !record.h3_access_record_ref || !record.h3_evaluation_artifact_ref) {
      add(errors, ErrorCategory::missing_evidence, "$out", "ACC-H1H2-RELEASE",
          "H1/H2 release lacks sealed H3 access/evaluation evidence");
    }
    break;
  case RecordKind::replacement_authorization:
    require_blocks();
    if (record.affected_block_ids.size() != 1 || !record.replacement ||
        record.authority.role != AuthorityRole::replacement_authority ||
        record.access_state_before != AccessState::planned ||
        record.access_state_after != AccessState::planned ||
        !record.outcome_access_prohibited) {
      add(errors, ErrorCategory::missing_evidence, "$out", "BLK-REPLACEMENT-AUTHORITY",
          "replacement authorization requires one block, budget/failure lineage, and "
          "authority");
    }
    break;
  case RecordKind::amendment:
    if (record.authority.role != AuthorityRole::protocol_owner ||
        !record.supersedes_id || !record.prior_protocol_version ||
        !record.new_protocol_version || !record.rationale ||
        record.affected_documents.empty() || record.affected_schema_ids.empty() ||
        record.affected_estimands.empty() || !record.pilot_record_disposition ||
        record.prior_authoritative_hashes.empty() ||
        !record.outcome_access_prohibited) {
      add(errors, ErrorCategory::missing_evidence, "$out", "GOV-AMENDMENT-SHAPE",
          "amendment lacks owner, lineage, impact, disposition, or prior hash "
          "evidence");
    }
    break;
  case RecordKind::protocol_freeze:
    break;
  }
  return errors;
}

auto validate_platform(const PlatformRecord& platform) -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  if (platform.cpu.cache_line_bytes == 0 || platform.cpu.atomic_width_bits == 0 ||
      platform.cpu.atomic_alignment_bytes == 0 || platform.topology.sockets == 0 ||
      platform.topology.numa_nodes == 0 || platform.topology.physical_cores < 2 ||
      platform.memory.base_page_bytes == 0) {
    add(errors, ErrorCategory::out_of_range, "$out", "PLATFORM-POSITIVE-QUANTITIES",
        "platform quantities violate imported schema minima");
  }
  bool h0 = false;
  bool h1 = false;
  for (const auto& state : platform.hardware_prefetch_states) {
    h0 = h0 || state.requested == RequestedHardwareState::h0;
    h1 = h1 || state.requested == RequestedHardwareState::h1;
    if (state.requested == RequestedHardwareState::not_applicable ||
        state.verified == VerifiedHardwareState::not_applicable) {
      add(errors, ErrorCategory::unknown_enum, "$out/hardware_prefetch_states",
          "HWP-PLATFORM-STATES",
          "platform hardware state records require H0/H1 and verification");
    }
  }
  if (!h0 || !h1) {
    add(errors, ErrorCategory::cross_field, "$out/hardware_prefetch_states",
        "HWP-PLATFORM-STATES",
        "platform record must explicitly include requested H0 and H1");
  }
  return errors;
}

} // namespace

auto Stage4SemanticValidator::validate(const ProtocolRecord& record) const
    -> std::vector<ValidationError> {
  return std::visit(
      [](const auto& typed) -> std::vector<ValidationError> {
        using Record = std::decay_t<decltype(typed)>;
        if constexpr (std::is_same_v<Record, PlatformRecord>) {
          return validate_platform(typed);
        } else if constexpr (std::is_same_v<Record, ScheduleRecord>) {
          return validate_schedule(typed);
        } else if constexpr (std::is_same_v<Record, RawObservationEnvelope>) {
          return validate_raw(typed);
        } else if constexpr (std::is_same_v<Record, RunManifest>) {
          return validate_manifest(typed);
        } else if constexpr (std::is_same_v<Record, BlockPlan>) {
          return validate_block(typed);
        } else if constexpr (std::is_same_v<Record, FailureRecord>) {
          return validate_failure(typed);
        } else {
          return validate_freeze(typed);
        }
      },
      record);
}

} // namespace cpu_prefetch::protocol
