#ifndef CPU_PREFETCH_LIFECYCLE_RUNTIME_HPP
#define CPU_PREFETCH_LIFECYCLE_RUNTIME_HPP

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include "cpu_prefetch/protocol/model.hpp"
#include "cpu_prefetch/queue/common.hpp"

namespace cpu_prefetch::lifecycle {

inline constexpr std::string_view kTerminationPublicationPolicy =
    "ARRIVALS-FINISHED-U32-RELEASE-ACQUIRE-v1";
inline constexpr std::string_view kLogicalResetPolicy = "WARM-START-LOGICAL-RESET-v1";

struct TerminationEvidence final {
  std::size_t value_width_bytes;
  std::size_t atomic_width_bytes;
  std::size_t atomic_alignment_bytes;
  std::size_t requested_cache_line_bytes;
  bool always_lock_free;
  bool runtime_lock_free;
  bool dedicated_cache_line;
};

class TerminationControl final {
public:
  explicit TerminationControl(queue::CacheLineBytes cache_line_bytes);
  ~TerminationControl();

  TerminationControl(const TerminationControl&) = delete;
  auto operator=(const TerminationControl&) -> TerminationControl& = delete;
  TerminationControl(TerminationControl&&) = delete;
  auto operator=(TerminationControl&&) -> TerminationControl& = delete;

  // reset_quiescent is preparation-only. Passing false prevents a reset while
  // either worker might still access the publication word.
  [[nodiscard]] auto reset_quiescent(bool workers_quiescent) noexcept -> bool;
  inline void publish_arrivals_finished() noexcept {
    value_->store(1U, std::memory_order_release);
  }
  [[nodiscard]] inline auto arrivals_finished() const noexcept -> bool {
    return value_->load(std::memory_order_acquire) == 1U;
  }
  [[nodiscard]] auto evidence() const noexcept -> TerminationEvidence;

private:
  queue::detail::AlignedBlock storage_;
  std::atomic<std::uint32_t>* value_{nullptr};
  std::size_t cache_line_bytes_{0U};
};

enum class StartBarrierStatus : std::uint8_t {
  ready,
  released,
  cancelled,
  watchdog_expired,
  duplicate_worker,
};

enum class WorkerRole : std::uint8_t { producer = 0U, consumer = 1U };

class WorkerStartBarrier final {
public:
  WorkerStartBarrier() noexcept = default;

  [[nodiscard]] auto arrive(WorkerRole role) noexcept -> StartBarrierStatus;
  [[nodiscard]] auto all_workers_ready() const noexcept -> bool;
  [[nodiscard]] auto
  release_with_measurement_origin(std::uint64_t measurement_origin_ticks) noexcept
      -> StartBarrierStatus;
  void cancel() noexcept;
  [[nodiscard]] auto measurement_origin() const noexcept -> std::uint64_t;

  template <typename Relax>
  [[nodiscard]] auto controller_wait(std::uint64_t poll_limit,
                                     Relax&& relax) const noexcept
      -> StartBarrierStatus {
    for (std::uint64_t poll = 0U; poll < poll_limit; ++poll) {
      if (cancelled_.load(std::memory_order_acquire)) {
        return StartBarrierStatus::cancelled;
      }
      if (all_workers_ready()) {
        return StartBarrierStatus::ready;
      }
      relax();
    }
    return StartBarrierStatus::watchdog_expired;
  }

  template <typename Relax>
  [[nodiscard]] auto worker_wait(std::uint64_t poll_limit, Relax&& relax) const noexcept
      -> StartBarrierStatus {
    for (std::uint64_t poll = 0U; poll < poll_limit; ++poll) {
      if (cancelled_.load(std::memory_order_acquire)) {
        return StartBarrierStatus::cancelled;
      }
      if (released_.load(std::memory_order_acquire)) {
        return StartBarrierStatus::released;
      }
      relax();
    }
    return StartBarrierStatus::watchdog_expired;
  }

private:
  std::atomic<std::uint32_t> arrived_mask_{0U};
  std::atomic<bool> released_{false};
  std::atomic<bool> cancelled_{false};
  std::atomic<std::uint64_t> measurement_origin_ticks_{0U};
};

struct PreparedScheduleView final {
  std::span<const std::uint64_t> deadline_ticks;
  std::uint64_t origin_ticks;
  std::uint64_t horizon_ticks;
};

[[nodiscard]] auto validate_prepared_schedule(PreparedScheduleView schedule)
    -> std::vector<protocol::ValidationError>;

struct PreparationEvidence final {
  protocol::ScheduleId warmup_schedule_id;
  protocol::ScheduleId measurement_schedule_id;
  protocol::NamespaceId warmup_namespace_id;
  protocol::NamespaceId measurement_namespace_id;
  std::string deterministic_initialization_id;
  bool scientific_configuration_frozen;
  bool platform_state_independently_verified;
  bool queue_initialized;
  bool record_storage_initialized;
  bool schedules_fully_decoded;
  bool observation_storage_preallocated;
  bool termination_reset_while_quiescent;
  bool measurement_origin_unset;
  std::uint64_t allocation_count_at_preparation_end;
};

struct WarmupCompletionEvidence final {
  protocol::ScheduleId schedule_id;
  protocol::NamespaceId namespace_id;
  std::uint64_t offered_count;
  std::uint64_t attempted_count;
  bool producer_complete;
  bool warm_arrivals_stopped;
  bool queue_drained;
  bool both_workers_at_reset_barrier;
  bool measurement_observations_emitted;
  bool resumed_prior_measurement;
  bool regenerated_schedule;
  std::uint64_t allocation_count_delta;
};

[[nodiscard]] auto
validate_preparation(const protocol::ScheduleId& expected_warmup_schedule_id,
                     const protocol::ScheduleId& expected_measurement_schedule_id,
                     const protocol::NamespaceId& expected_warmup_namespace_id,
                     const protocol::NamespaceId& expected_measurement_namespace_id,
                     const PreparationEvidence& evidence)
    -> std::vector<protocol::ValidationError>;

[[nodiscard]] auto
validate_warmup_completion(const protocol::ScheduleId& expected_schedule_id,
                           const protocol::NamespaceId& expected_namespace_id,
                           const WarmupCompletionEvidence& evidence)
    -> std::vector<protocol::ValidationError>;

enum class QueueResetKind : std::uint8_t { ring, linked };

struct WarmStartIdentity final {
  std::string allocation_id;
  std::string virtual_mapping_id;
  std::string data_home_id;
  std::string record_permutation_id;
  std::string payload_content_id;

  auto operator==(const WarmStartIdentity&) const -> bool = default;
};

struct LogicalResetRequest final {
  QueueResetKind queue_kind;
  std::uint64_t capacity_events;
  std::uint64_t initial_consumer_checksum;
  WarmStartIdentity warm_identity;
};

struct LogicalResetEvidence final {
  QueueResetKind queue_kind;
  std::uint64_t capacity_events;
  bool warm_arrivals_stopped;
  bool queue_drained;
  bool workers_at_reset_barrier;
  std::uint64_t occupancy_after_reset;

  bool ring_slots_empty;
  bool ring_producer_position_zero;
  bool ring_consumer_position_zero;

  bool linked_sentinel_is_pi0;
  bool linked_recycler_order_is_pi1_to_pi_c;
  std::uint64_t linked_recycler_node_count;

  std::uint64_t logical_sequence;
  std::uint64_t accepted_ordinal;
  std::uint64_t producer_attempted;
  std::uint64_t producer_accepted;
  std::uint64_t producer_full;
  std::uint64_t consumer_consumed;
  std::uint64_t producer_sample_position;
  std::uint64_t consumer_sample_position;
  std::uint64_t consumer_checksum;
  bool measurement_origin_cleared;

  WarmStartIdentity identity_after_reset;
  std::uint64_t allocation_count_delta;
  bool regenerated_schedule;
  bool remapped_memory;
  bool retouched_payload;
};

class LogicalResetBackend {
public:
  virtual ~LogicalResetBackend() = default;
  [[nodiscard]] virtual auto perform(const LogicalResetRequest& request)
      -> protocol::Result<LogicalResetEvidence> = 0;
};

[[nodiscard]] auto validate_logical_reset(const LogicalResetRequest& request,
                                          const LogicalResetEvidence& evidence)
    -> std::vector<protocol::ValidationError>;

[[nodiscard]] auto perform_and_verify_logical_reset(LogicalResetBackend& backend,
                                                    const LogicalResetRequest& request)
    -> protocol::Result<LogicalResetEvidence>;

static_assert(sizeof(std::uint32_t) == 4U);
static_assert(std::atomic<std::uint32_t>::is_always_lock_free);
static_assert(std::atomic<std::uint64_t>::is_always_lock_free);

} // namespace cpu_prefetch::lifecycle

#endif // CPU_PREFETCH_LIFECYCLE_RUNTIME_HPP
