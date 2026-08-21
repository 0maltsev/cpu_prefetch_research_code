#include "cpu_prefetch/lifecycle/runtime.hpp"

#include <algorithm>
#include <limits>
#include <memory>
#include <new>
#include <utility>

namespace cpu_prefetch::lifecycle {
namespace {

using protocol::ErrorCategory;
using protocol::ValidationError;

void add_error(std::vector<ValidationError>& errors, ErrorCategory category,
               std::string path, std::string rule_id, std::string message) {
  errors.push_back({category, std::move(path), std::move(rule_id), std::move(message)});
}

[[nodiscard]] auto identity_complete(const WarmStartIdentity& identity) -> bool {
  return !identity.allocation_id.empty() && !identity.virtual_mapping_id.empty() &&
         !identity.data_home_id.empty() && !identity.record_permutation_id.empty() &&
         !identity.payload_content_id.empty();
}

} // namespace

TerminationControl::TerminationControl(queue::CacheLineBytes cache_line_bytes)
    : storage_(cache_line_bytes.value, cache_line_bytes.value),
      cache_line_bytes_(cache_line_bytes.value) {
  queue::detail::validate_cache_line_bytes(cache_line_bytes_);
  if (storage_.size() < sizeof(std::atomic<std::uint32_t>)) {
    throw queue::QueueSetupError(
        "termination cache line is smaller than its atomic value");
  }
  value_ = ::new (static_cast<void*>(storage_.data())) std::atomic<std::uint32_t>{0U};
}

TerminationControl::~TerminationControl() {
  if (value_ != nullptr) {
    std::destroy_at(value_);
  }
}

auto TerminationControl::reset_quiescent(bool workers_quiescent) noexcept -> bool {
  if (!workers_quiescent) {
    return false;
  }
  value_->store(0U, std::memory_order_relaxed);
  return true;
}

auto TerminationControl::evidence() const noexcept -> TerminationEvidence {
  return {sizeof(std::uint32_t),
          sizeof(std::atomic<std::uint32_t>),
          alignof(std::atomic<std::uint32_t>),
          cache_line_bytes_,
          std::atomic<std::uint32_t>::is_always_lock_free,
          value_->is_lock_free(),
          storage_.size() == cache_line_bytes_ &&
              queue::detail::is_aligned(storage_.data(), cache_line_bytes_)};
}

auto WorkerStartBarrier::arrive(WorkerRole role) noexcept -> StartBarrierStatus {
  const auto bit = std::uint32_t{1U} << static_cast<std::uint8_t>(role);
  const auto previous = arrived_mask_.fetch_or(bit, std::memory_order_acq_rel);
  if ((previous & bit) != 0U) {
    cancel();
    return StartBarrierStatus::duplicate_worker;
  }
  return StartBarrierStatus::ready;
}

auto WorkerStartBarrier::all_workers_ready() const noexcept -> bool {
  return arrived_mask_.load(std::memory_order_acquire) == 0x3U;
}

auto WorkerStartBarrier::release_with_measurement_origin(
    std::uint64_t measurement_origin_ticks) noexcept -> StartBarrierStatus {
  if (cancelled_.load(std::memory_order_acquire)) {
    return StartBarrierStatus::cancelled;
  }
  if (!all_workers_ready()) {
    return StartBarrierStatus::watchdog_expired;
  }
  measurement_origin_ticks_.store(measurement_origin_ticks, std::memory_order_relaxed);
  released_.store(true, std::memory_order_release);
  return StartBarrierStatus::released;
}

void WorkerStartBarrier::cancel() noexcept {
  cancelled_.store(true, std::memory_order_release);
}

auto WorkerStartBarrier::measurement_origin() const noexcept -> std::uint64_t {
  return measurement_origin_ticks_.load(std::memory_order_acquire);
}

auto validate_prepared_schedule(PreparedScheduleView schedule)
    -> std::vector<protocol::ValidationError> {
  std::vector<ValidationError> errors;
  if (schedule.origin_ticks > schedule.horizon_ticks) {
    add_error(errors, ErrorCategory::cross_field, "$schedule/horizon_ticks",
              "LIF-SCHEDULE-HORIZON",
              "schedule origin must not exceed its frozen horizon");
  }
  for (std::size_t index = 0U; index < schedule.deadline_ticks.size(); ++index) {
    const auto deadline = schedule.deadline_ticks[index];
    const auto path = "$schedule/deadline_ticks/" + std::to_string(index);
    if (deadline < schedule.origin_ticks || deadline >= schedule.horizon_ticks) {
      add_error(errors, ErrorCategory::out_of_range, path, "LIF-SCHEDULE-HALF-OPEN",
                "each deadline must be in [origin_ticks, horizon_ticks)");
    }
    if (index != 0U && deadline < schedule.deadline_ticks[index - 1U]) {
      add_error(errors, ErrorCategory::cross_field, path, "LIF-SCHEDULE-NONDECREASING",
                "prepared deadlines must be nondecreasing");
    }
  }
  return errors;
}

auto validate_preparation(
    const protocol::ScheduleId& expected_warmup_schedule_id,
    const protocol::ScheduleId& expected_measurement_schedule_id,
    const protocol::NamespaceId& expected_warmup_namespace_id,
    const protocol::NamespaceId& expected_measurement_namespace_id,
    const PreparationEvidence& evidence) -> std::vector<protocol::ValidationError> {
  std::vector<ValidationError> errors;
  if (expected_warmup_schedule_id == expected_measurement_schedule_id ||
      expected_warmup_namespace_id == expected_measurement_namespace_id ||
      evidence.warmup_schedule_id != expected_warmup_schedule_id ||
      evidence.measurement_schedule_id != expected_measurement_schedule_id ||
      evidence.warmup_namespace_id != expected_warmup_namespace_id ||
      evidence.measurement_namespace_id != expected_measurement_namespace_id) {
    add_error(errors, ErrorCategory::reference_mismatch,
              "$preparation/schedule_identity", "LIF-PREP-SCHEDULES",
              "preparation must retain distinct, explicitly planned warm-up and "
              "measurement schedule and namespace identities");
  }
  if (evidence.deterministic_initialization_id.empty()) {
    add_error(errors, ErrorCategory::missing_field,
              "$preparation/deterministic_initialization_id", "LIF-PREP-ID",
              "deterministic initialization requires an evidence identity");
  }
  if (!evidence.scientific_configuration_frozen ||
      !evidence.platform_state_independently_verified || !evidence.queue_initialized ||
      !evidence.record_storage_initialized || !evidence.schedules_fully_decoded ||
      !evidence.observation_storage_preallocated ||
      !evidence.termination_reset_while_quiescent ||
      !evidence.measurement_origin_unset) {
    add_error(errors, ErrorCategory::missing_evidence, "$preparation/readiness",
              "LIF-PREP-READY",
              "configuration, verified platform state, queue, records, schedules, "
              "observation storage, termination, and unset origin are all required");
  }
  return errors;
}

auto validate_warmup_completion(const protocol::ScheduleId& expected_schedule_id,
                                const protocol::NamespaceId& expected_namespace_id,
                                const WarmupCompletionEvidence& evidence)
    -> std::vector<protocol::ValidationError> {
  std::vector<ValidationError> errors;
  if (evidence.schedule_id != expected_schedule_id ||
      evidence.namespace_id != expected_namespace_id) {
    add_error(errors, ErrorCategory::reference_mismatch, "$warmup/schedule_identity",
              "LIF-WARMUP-SCHEDULE",
              "warm-up must consume only its planned schedule and namespace");
  }
  if (evidence.attempted_count != evidence.offered_count ||
      !evidence.producer_complete || !evidence.warm_arrivals_stopped ||
      !evidence.queue_drained || !evidence.both_workers_at_reset_barrier) {
    add_error(errors, ErrorCategory::cross_field, "$warmup/completion",
              "LIF-WARMUP-COMPLETE",
              "all warm-up arrivals must be attempted, then stopped and drained "
              "before both workers enter the reset barrier");
  }
  if (evidence.measurement_observations_emitted || evidence.resumed_prior_measurement ||
      evidence.regenerated_schedule || evidence.allocation_count_delta != 0U) {
    add_error(errors, ErrorCategory::cross_field, "$warmup/isolation",
              "LIF-WARMUP-ISOLATED",
              "warm-up cannot emit measurement rows, continue a prior measurement, "
              "regenerate a schedule, or allocate after preparation");
  }
  return errors;
}

auto validate_logical_reset(const LogicalResetRequest& request,
                            const LogicalResetEvidence& evidence)
    -> std::vector<protocol::ValidationError> {
  std::vector<ValidationError> errors;
  if (request.capacity_events == 0U) {
    add_error(errors, ErrorCategory::out_of_range, "$reset_request/capacity_events",
              "LIF-RESET-CAPACITY", "queue capacity must be positive");
  }
  if (!identity_complete(request.warm_identity) ||
      !identity_complete(evidence.identity_after_reset)) {
    add_error(errors, ErrorCategory::missing_field, "$reset/identity",
              "LIF-WARM-IDENTITY",
              "allocation, mapping, data-home, permutation, and payload identities "
              "must all be explicit");
  }
  if (evidence.queue_kind != request.queue_kind ||
      evidence.capacity_events != request.capacity_events) {
    add_error(errors, ErrorCategory::cross_field, "$reset/queue",
              "LIF-RESET-QUEUE-MATCH",
              "reset evidence must identify the requested queue kind and capacity");
  }
  if (!evidence.warm_arrivals_stopped || !evidence.queue_drained ||
      !evidence.workers_at_reset_barrier) {
    add_error(errors, ErrorCategory::missing_evidence, "$reset/warmup_boundary",
              "LIF-WARMUP-BOUNDARY",
              "warm arrivals must stop, the queue must drain, and both workers must "
              "reach the reset barrier");
  }
  if (evidence.occupancy_after_reset != 0U) {
    add_error(errors, ErrorCategory::cross_field, "$reset/occupancy_after_reset",
              "LIF-RESET-EMPTY", "logical reset must leave zero queue occupancy");
  }
  if (request.queue_kind == QueueResetKind::ring &&
      (!evidence.ring_slots_empty || !evidence.ring_producer_position_zero ||
       !evidence.ring_consumer_position_zero)) {
    add_error(errors, ErrorCategory::missing_evidence, "$reset/ring", "LIF-RING-RESET",
              "ring reset requires empty slots and zero producer/consumer positions");
  }
  if (request.queue_kind == QueueResetKind::linked &&
      (!evidence.linked_sentinel_is_pi0 ||
       !evidence.linked_recycler_order_is_pi1_to_pi_c ||
       evidence.linked_recycler_node_count != request.capacity_events)) {
    add_error(errors, ErrorCategory::missing_evidence, "$reset/linked",
              "LIF-LINKED-RESET",
              "linked reset requires sentinel pi0 and recycler pi1..piC");
  }
  if (evidence.logical_sequence != 0U || evidence.accepted_ordinal != 0U ||
      evidence.producer_attempted != 0U || evidence.producer_accepted != 0U ||
      evidence.producer_full != 0U || evidence.consumer_consumed != 0U ||
      evidence.producer_sample_position != 0U ||
      evidence.consumer_sample_position != 0U) {
    add_error(errors, ErrorCategory::cross_field, "$reset/logical_state",
              "LIF-LOGICAL-ZERO",
              "sequence, ordinal, counts, and sample positions must reset to zero");
  }
  if (evidence.consumer_checksum != request.initial_consumer_checksum) {
    add_error(errors, ErrorCategory::cross_field, "$reset/consumer_checksum",
              "LIF-CHECKSUM-RESET",
              "consumer checksum must equal the explicitly requested initial value");
  }
  if (!evidence.measurement_origin_cleared) {
    add_error(errors, ErrorCategory::cross_field, "$reset/measurement_origin_cleared",
              "LIF-ORIGIN-RESET",
              "measurement origin must be unset until the post-reset start barrier");
  }
  if (evidence.identity_after_reset != request.warm_identity ||
      evidence.allocation_count_delta != 0U || evidence.regenerated_schedule ||
      evidence.remapped_memory || evidence.retouched_payload) {
    add_error(errors, ErrorCategory::cross_field, "$reset/warm_start",
              "LIF-WARM-START-PRESERVE",
              "reset must preserve allocation, mappings, data homes, permutation, "
              "payload, and pre-generated schedules");
  }
  return errors;
}

auto perform_and_verify_logical_reset(LogicalResetBackend& backend,
                                      const LogicalResetRequest& request)
    -> protocol::Result<LogicalResetEvidence> {
  auto result = backend.perform(request);
  if (!result) {
    return result;
  }
  auto errors = validate_logical_reset(request, result.value());
  if (!errors.empty()) {
    return protocol::Result<LogicalResetEvidence>::failure(std::move(errors));
  }
  return result;
}

} // namespace cpu_prefetch::lifecycle
