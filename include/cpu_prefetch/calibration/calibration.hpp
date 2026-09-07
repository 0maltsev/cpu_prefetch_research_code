#ifndef CPU_PREFETCH_CALIBRATION_CALIBRATION_HPP
#define CPU_PREFETCH_CALIBRATION_CALIBRATION_HPP

#include "cpu_prefetch/protocol/model.hpp"
#include "cpu_prefetch/protocol/validation.hpp"
#include "cpu_prefetch/queue/common.hpp"
#include "cpu_prefetch/queue/ring_spsc.hpp"
#include "cpu_prefetch/timing/clock.hpp"
#include "cpu_prefetch/workload/packages.hpp"

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::calibration {

inline constexpr std::string_view kServiceRateMethodId =
    "SERVICE-RATE-NP-LTL95C95-MIN-v1";
inline constexpr std::string_view kMatrixFeasibilityMethodId =
    "MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1";
inline constexpr std::string_view kRingDistanceMethodId = "RING-D2-RUNTAIL-LTL95C95-v1";
inline constexpr std::string_view kCalibrationRecordFamily =
    "cpu-prefetch-calibration/1";
inline constexpr std::size_t kMinimumValidIndependentRuns = 59U;
inline constexpr std::size_t kRequiredServiceCellCount = 60U;
inline constexpr std::size_t kRequiredRingContextCount = 6U;

enum class EvaluationState : std::uint8_t {
  not_evaluated,
  resolved,
  ineligible,
};

enum class CalibrationRunValidity : std::uint8_t { valid, invalid };

struct ExactRational final {
  std::uint64_t numerator;
  std::uint64_t denominator;
  auto operator==(const ExactRational&) const -> bool = default;
};

[[nodiscard]] auto make_rational(std::uint64_t numerator, std::uint64_t denominator,
                                 std::string path = "$/rate")
    -> protocol::Result<ExactRational>;
struct ThroughputObservation final {
  std::uint64_t consumed_events;
  std::uint64_t ticks_per_second;
  std::uint64_t interval_ticks;
};
[[nodiscard]] auto exact_throughput(ThroughputObservation observation)
    -> protocol::Result<ExactRational>;
[[nodiscard]] auto compare(const ExactRational& left, const ExactRational& right)
    -> protocol::Result<int>;
[[nodiscard]] auto multiply(const ExactRational& left, const ExactRational& right,
                            std::string path = "$/rate")
    -> protocol::Result<ExactRational>;

struct EvidenceReference final {
  std::string artifact_id;
  std::string sha256;
  auto operator==(const EvidenceReference&) const -> bool = default;
};

struct CalibrationGovernance final {
  std::vector<std::string> owner_ids;
  EvidenceReference authority_artifact;
  EvidenceReference stand_budget_artifact;
};

struct ServiceCellKey final {
  protocol::QueuePackage package;
  protocol::RequestedHardwareState hardware_state;
  protocol::Placement placement;
  protocol::WorkingSetClass working_set;
  auto operator==(const ServiceCellKey&) const -> bool = default;
};

struct StageAContext final {
  std::string platform_id;
  std::string build_id;
  std::string queue_implementation_id;
  std::string consumer_action_id;
  std::string placement_evidence_id;
  std::string capacity_evidence_id;
  std::string working_set_evidence_id;
  std::string hardware_state_evidence_id;
  std::string software_policy_id;
  std::string clock_policy_id;
  std::uint64_t logical_capacity;
  auto operator==(const StageAContext&) const -> bool = default;
};

struct ServiceCellPlan final {
  ServiceCellKey key;
  StageAContext context;
  std::uint64_t duration_ticks;
  std::uint64_t ticks_per_second;
  std::vector<protocol::RunId> planned_run_ids;
};

struct ServiceRatePlan final {
  std::string record_id;
  std::string estimator_id;
  std::string seed_namespace_id;
  std::vector<std::string> assumptions;
  CalibrationGovernance governance;
  std::vector<ServiceCellPlan> cells;
};

struct ServiceRunEvidence final {
  protocol::RunId run_id;
  ServiceCellKey key;
  StageAContext context;
  protocol::Stage stage;
  protocol::RunMode run_mode;
  protocol::ArrivalFamily arrival_family;
  CalibrationRunValidity validity;
  std::uint64_t consumed_events;
  std::uint64_t interval_ticks;
  std::uint64_t ticks_per_second;
  std::vector<EvidenceReference> raw_run_artifacts;
  std::optional<EvidenceReference> integrity_artifact;
  std::optional<EvidenceReference> failure_artifact;
};

struct ServiceRunDecision final {
  protocol::RunId run_id;
  CalibrationRunValidity validity;
  std::uint64_t consumed_events;
  std::uint64_t interval_ticks;
  std::uint64_t ticks_per_second;
  std::optional<ExactRational> throughput;
  std::vector<EvidenceReference> raw_run_artifacts;
  std::optional<EvidenceReference> integrity_artifact;
  std::optional<EvidenceReference> failure_artifact;
};

struct ServiceCellResult final {
  ServiceCellKey key;
  EvaluationState state;
  std::size_t planned_runs;
  std::size_t present_runs;
  std::size_t valid_runs;
  std::optional<ExactRational> mu_cell;
  std::vector<ServiceRunDecision> run_decisions;
  std::vector<std::string> blockers;
};

struct ServiceRateResult final {
  EvaluationState state;
  std::vector<ServiceCellResult> cells;
  std::optional<ExactRational> mu_ref;
  std::vector<ExactRational> candidate_loads;
  std::vector<std::string> blockers;
};

[[nodiscard]] auto required_service_cells() -> std::vector<ServiceCellKey>;
[[nodiscard]] auto evaluate_service_rate(const ServiceRatePlan& plan,
                                         const std::vector<ServiceRunEvidence>& runs)
    -> protocol::Result<ServiceRateResult>;

enum class RingWorker : std::uint8_t { producer, consumer };
enum class RingAttemptOutcome : std::uint8_t {
  advanced,
  full,
  empty,
  clock_failure,
  trace_failure,
};

struct RingDemandSeries final {
  std::vector<std::uint64_t> producer_demand_ticks;
  std::vector<std::uint64_t> consumer_demand_ticks;
  std::vector<std::uint64_t> producer_issue_ticks;
  std::vector<std::uint64_t> consumer_issue_ticks;
  std::uint64_t producer_full_count{0U};
  std::uint64_t consumer_empty_count{0U};
};

class RingDemandTrace final {
public:
  explicit RingDemandTrace(std::size_t max_attempts_per_worker);
  [[nodiscard]] auto record(RingWorker worker, std::uint64_t demand_start,
                            std::uint64_t demand_end,
                            RingAttemptOutcome outcome) noexcept -> bool;
  [[nodiscard]] auto series() const noexcept -> const RingDemandSeries& {
    return series_;
  }

private:
  RingDemandSeries series_;
  std::optional<std::uint64_t> previous_producer_advance_start_;
  std::optional<std::uint64_t> previous_consumer_advance_start_;
  std::size_t max_attempts_per_worker_;
};

struct RingCaptureResult final {
  RingAttemptOutcome outcome;
  timing::ClockReadStatus before_status;
  timing::ClockReadStatus after_status;
};

template <typename Clock>
[[nodiscard]] auto
capture_producer_ring_demand(Clock& clock, queue::RingSpscQueue& queue,
                             queue::EventPointer event, RingDemandTrace& trace) noexcept
    -> RingCaptureResult {
  struct Observer final {
    Clock& clock;
    timing::ClockReadResult before{timing::ClockReadStatus::call_failed, {0U, 0U}};
    timing::ClockReadResult after{timing::ClockReadStatus::call_failed, {0U, 0U}};
    void before_slot_acquire() noexcept { before = clock.read(); }
    void after_slot_acquire() noexcept { after = clock.read(); }
  } observer{clock};
  const auto result = queue.try_enqueue_with_slot_demand_observer(event, observer);
  if (observer.before.status != timing::ClockReadStatus::ok ||
      observer.after.status != timing::ClockReadStatus::ok) {
    return {RingAttemptOutcome::clock_failure, observer.before.status,
            observer.after.status};
  }
  const auto outcome = result == queue::EnqueueResult::accepted
                           ? RingAttemptOutcome::advanced
                           : RingAttemptOutcome::full;
  if (!trace.record(RingWorker::producer, observer.before.sample.relative_picoseconds,
                    observer.after.sample.relative_picoseconds, outcome)) {
    return {RingAttemptOutcome::trace_failure, observer.before.status,
            observer.after.status};
  }
  return {outcome, observer.before.status, observer.after.status};
}

template <typename Clock>
[[nodiscard]] auto capture_consumer_ring_demand(Clock& clock,
                                                queue::RingSpscQueue& queue,
                                                RingDemandTrace& trace) noexcept
    -> RingCaptureResult {
  struct Observer final {
    Clock& clock;
    timing::ClockReadResult before{timing::ClockReadStatus::call_failed, {0U, 0U}};
    timing::ClockReadResult after{timing::ClockReadStatus::call_failed, {0U, 0U}};
    void before_slot_acquire() noexcept { before = clock.read(); }
    void after_slot_acquire() noexcept { after = clock.read(); }
  } observer{clock};
  const auto result = queue.try_dequeue_with_slot_demand_observer(observer);
  if (observer.before.status != timing::ClockReadStatus::ok ||
      observer.after.status != timing::ClockReadStatus::ok) {
    return {RingAttemptOutcome::clock_failure, observer.before.status,
            observer.after.status};
  }
  const auto outcome = result.status == queue::DequeueStatus::item
                           ? RingAttemptOutcome::advanced
                           : RingAttemptOutcome::empty;
  if (!trace.record(RingWorker::consumer, observer.before.sample.relative_picoseconds,
                    observer.after.sample.relative_picoseconds, outcome)) {
    return {RingAttemptOutcome::trace_failure, observer.before.status,
            observer.after.status};
  }
  return {outcome, observer.before.status, observer.after.status};
}

struct RingContextKey final {
  protocol::Placement placement;
  protocol::WorkingSetClass working_set;
  auto operator==(const RingContextKey&) const -> bool = default;
};

struct RingStatePlan final {
  protocol::RequestedHardwareState hardware_state;
  StageAContext ring_off_context;
  std::vector<protocol::RunId> planned_run_ids;
};

struct RingContextPlan final {
  RingContextKey key;
  workload::RingGeometry geometry;
  std::uint64_t duration_ticks;
  std::uint64_t minimum_observations_per_series;
  std::vector<RingStatePlan> states;
};

struct RingDistancePlan final {
  std::string record_id;
  std::string estimator_id;
  std::string seed_namespace_id;
  std::vector<std::string> assumptions;
  CalibrationGovernance governance;
  std::vector<RingContextPlan> contexts;
};

struct RingRunEvidence final {
  protocol::RunId run_id;
  RingContextKey key;
  StageAContext ring_off_context;
  protocol::RequestedHardwareState hardware_state;
  protocol::Stage stage;
  protocol::RunMode run_mode;
  protocol::QueuePackage package;
  CalibrationRunValidity validity;
  std::uint64_t interval_ticks;
  RingDemandSeries series;
  std::vector<EvidenceReference> raw_run_artifacts;
  std::optional<EvidenceReference> integrity_artifact;
  std::optional<EvidenceReference> failure_artifact;
};

struct RingRunDecision final {
  protocol::RunId run_id;
  protocol::RequestedHardwareState hardware_state;
  CalibrationRunValidity validity;
  std::optional<std::uint64_t> producer_demand_p999_ticks;
  std::optional<std::uint64_t> consumer_demand_p999_ticks;
  std::optional<std::uint64_t> producer_issue_p001_ticks;
  std::optional<std::uint64_t> consumer_issue_p001_ticks;
  std::vector<EvidenceReference> raw_run_artifacts;
  std::optional<EvidenceReference> integrity_artifact;
  std::optional<EvidenceReference> failure_artifact;
};

struct RingContextResult final {
  RingContextKey key;
  EvaluationState state;
  std::optional<std::uint64_t> producer_demand_upper_ticks;
  std::optional<std::uint64_t> consumer_demand_upper_ticks;
  std::optional<std::uint64_t> producer_issue_lower_ticks;
  std::optional<std::uint64_t> consumer_issue_lower_ticks;
  std::optional<std::uint64_t> conservative_demand_ticks;
  std::optional<std::uint64_t> conservative_issue_ticks;
  std::optional<std::uint64_t> d1_slots;
  std::optional<std::uint64_t> d2_cache_lines;
  std::optional<std::uint64_t> producer_distance_slots;
  std::optional<std::uint64_t> consumer_distance_slots;
  std::vector<RingRunDecision> run_decisions;
  std::vector<std::string> blockers;
};

struct RingDistanceResult final {
  EvaluationState state;
  std::vector<RingContextResult> contexts;
  std::vector<std::string> blockers;
};

[[nodiscard]] auto required_ring_contexts() -> std::vector<RingContextKey>;
[[nodiscard]] auto inverse_ecdf(std::vector<std::uint64_t> values,
                                std::uint64_t probability_numerator,
                                std::uint64_t probability_denominator)
    -> protocol::Result<std::uint64_t>;
[[nodiscard]] auto evaluate_ring_distance(const RingDistancePlan& plan,
                                          const std::vector<RingRunEvidence>& runs)
    -> protocol::Result<RingDistanceResult>;

} // namespace cpu_prefetch::calibration

#endif // CPU_PREFETCH_CALIBRATION_CALIBRATION_HPP
