#include "cpu_prefetch/calibration/calibration.hpp"

#include <algorithm>
#include <array>
#include <limits>
#include <numeric>
#include <set>
#include <stdexcept>
#include <utility>

namespace cpu_prefetch::calibration {
namespace {

template <typename T>
[[nodiscard]] auto fail(protocol::ErrorCategory category, std::string path,
                        std::string rule, std::string message) -> protocol::Result<T> {
  return protocol::Result<T>::failure(
      {category, std::move(path), std::move(rule), std::move(message)});
}

[[nodiscard]] auto checked_multiply(std::uint64_t left, std::uint64_t right,
                                    std::uint64_t& result) noexcept -> bool {
  if (left != 0U && right > std::numeric_limits<std::uint64_t>::max() / left) {
    return false;
  }
  result = left * right;
  return true;
}

[[nodiscard]] auto checked_ceil_divide(std::uint64_t numerator,
                                       std::uint64_t denominator,
                                       std::uint64_t& result) noexcept -> bool {
  if (denominator == 0U) {
    return false;
  }
  result = numerator / denominator;
  if (numerator % denominator != 0U) {
    if (result == std::numeric_limits<std::uint64_t>::max()) {
      return false;
    }
    ++result;
  }
  return true;
}

[[nodiscard]] auto valid_sha256(std::string_view value) noexcept -> bool {
  return value.size() == 64U &&
         std::all_of(value.begin(), value.end(), [](char character) {
           return (character >= '0' && character <= '9') ||
                  (character >= 'a' && character <= 'f');
         });
}

[[nodiscard]] auto valid_opaque_id(std::string_view value) noexcept -> bool {
  return !value.empty() && value.find('/') == std::string_view::npos;
}

[[nodiscard]] auto valid_reference(const EvidenceReference& reference) noexcept
    -> bool {
  return valid_opaque_id(reference.artifact_id) && valid_sha256(reference.sha256);
}

[[nodiscard]] auto valid_governance(const CalibrationGovernance& governance) noexcept
    -> bool {
  const std::set<std::string> unique_owners(governance.owner_ids.begin(),
                                            governance.owner_ids.end());
  return !governance.owner_ids.empty() &&
         unique_owners.size() == governance.owner_ids.size() &&
         std::all_of(governance.owner_ids.begin(), governance.owner_ids.end(),
                     [](const std::string& owner) { return valid_opaque_id(owner); }) &&
         valid_reference(governance.authority_artifact) &&
         valid_reference(governance.stand_budget_artifact);
}

[[nodiscard]] auto valid_context(const StageAContext& context) noexcept -> bool {
  return valid_opaque_id(context.platform_id) && valid_opaque_id(context.build_id) &&
         valid_opaque_id(context.queue_implementation_id) &&
         valid_opaque_id(context.consumer_action_id) &&
         valid_opaque_id(context.placement_evidence_id) &&
         valid_opaque_id(context.capacity_evidence_id) &&
         valid_opaque_id(context.working_set_evidence_id) &&
         valid_opaque_id(context.hardware_state_evidence_id) &&
         valid_opaque_id(context.software_policy_id) &&
         valid_opaque_id(context.clock_policy_id) && context.logical_capacity != 0U;
}

[[nodiscard]] auto
same_ring_context_except_hardware(const StageAContext& left,
                                  const StageAContext& right) noexcept -> bool {
  return left.platform_id == right.platform_id && left.build_id == right.build_id &&
         left.queue_implementation_id == right.queue_implementation_id &&
         left.consumer_action_id == right.consumer_action_id &&
         left.placement_evidence_id == right.placement_evidence_id &&
         left.capacity_evidence_id == right.capacity_evidence_id &&
         left.working_set_evidence_id == right.working_set_evidence_id &&
         left.software_policy_id == right.software_policy_id &&
         left.clock_policy_id == right.clock_policy_id &&
         left.logical_capacity == right.logical_capacity;
}

[[nodiscard]] auto service_key_name(const ServiceCellKey& key) -> std::string {
  return std::to_string(static_cast<unsigned int>(key.package)) + ":" +
         std::to_string(static_cast<unsigned int>(key.hardware_state)) + ":" +
         std::to_string(static_cast<unsigned int>(key.placement)) + ":" +
         std::to_string(static_cast<unsigned int>(key.working_set));
}

[[nodiscard]] auto ring_key_name(const RingContextKey& key) -> std::string {
  return std::to_string(static_cast<unsigned int>(key.placement)) + ":" +
         std::to_string(static_cast<unsigned int>(key.working_set));
}

[[nodiscard]] auto expected_service_key(const ServiceCellKey& key) noexcept -> bool {
  const auto expected = required_service_cells();
  return std::find(expected.begin(), expected.end(), key) != expected.end();
}

[[nodiscard]] auto expected_ring_key(const RingContextKey& key) noexcept -> bool {
  const auto expected = required_ring_contexts();
  return std::find(expected.begin(), expected.end(), key) != expected.end();
}

[[nodiscard]] auto
references_valid(const std::vector<EvidenceReference>& references) noexcept -> bool {
  return std::all_of(references.begin(), references.end(), valid_reference);
}

[[nodiscard]] auto all_positive(const std::vector<std::uint64_t>& values) noexcept
    -> bool {
  return std::all_of(values.begin(), values.end(),
                     [](std::uint64_t value) { return value != 0U; });
}

} // namespace

auto make_rational(std::uint64_t numerator, std::uint64_t denominator, std::string path)
    -> protocol::Result<ExactRational> {
  if (denominator == 0U) {
    return fail<ExactRational>(protocol::ErrorCategory::out_of_range, std::move(path),
                               "CAL-RATIONAL-DENOMINATOR",
                               "exact rational denominator must be nonzero");
  }
  const auto divisor = std::gcd(numerator, denominator);
  return protocol::Result<ExactRational>::success(
      {numerator / divisor, denominator / divisor});
}

auto exact_throughput(ThroughputObservation observation)
    -> protocol::Result<ExactRational> {
  if (observation.ticks_per_second == 0U || observation.interval_ticks == 0U) {
    return fail<ExactRational>(protocol::ErrorCategory::out_of_range, "$/service_run",
                               "CAL-SERVICE-UNITS",
                               "tick frequency and interval must be nonzero");
  }
  auto consumed = observation.consumed_events;
  auto frequency = observation.ticks_per_second;
  auto interval = observation.interval_ticks;
  auto divisor = std::gcd(consumed, interval);
  consumed /= divisor;
  interval /= divisor;
  divisor = std::gcd(frequency, interval);
  frequency /= divisor;
  interval /= divisor;
  std::uint64_t numerator = 0U;
  if (!checked_multiply(consumed, frequency, numerator)) {
    return fail<ExactRational>(
        protocol::ErrorCategory::out_of_range, "$/service_run/consumed_events",
        "CAL-SERVICE-THROUGHPUT-OVERFLOW", "exact throughput numerator overflows u64");
  }
  return protocol::Result<ExactRational>::success({numerator, interval});
}

auto compare(const ExactRational& left, const ExactRational& right)
    -> protocol::Result<int> {
  if (left.denominator == 0U || right.denominator == 0U) {
    return fail<int>(protocol::ErrorCategory::out_of_range, "$/rate",
                     "CAL-RATIONAL-DENOMINATOR",
                     "exact rational denominator must be nonzero");
  }
  auto left_numerator = left.numerator;
  auto left_denominator = left.denominator;
  auto right_numerator = right.numerator;
  auto right_denominator = right.denominator;
  bool inverted = false;
  while (true) {
    const auto left_quotient = left_numerator / left_denominator;
    const auto right_quotient = right_numerator / right_denominator;
    if (left_quotient != right_quotient) {
      const auto result = left_quotient < right_quotient ? -1 : 1;
      return protocol::Result<int>::success(inverted ? -result : result);
    }
    const auto left_remainder = left_numerator % left_denominator;
    const auto right_remainder = right_numerator % right_denominator;
    if (left_remainder == 0U || right_remainder == 0U) {
      if (left_remainder == 0U && right_remainder == 0U) {
        return protocol::Result<int>::success(0);
      }
      const auto result = left_remainder == 0U ? -1 : 1;
      return protocol::Result<int>::success(inverted ? -result : result);
    }
    left_numerator = left_denominator;
    left_denominator = left_remainder;
    right_numerator = right_denominator;
    right_denominator = right_remainder;
    inverted = !inverted;
  }
}

auto multiply(const ExactRational& left, const ExactRational& right, std::string path)
    -> protocol::Result<ExactRational> {
  if (left.denominator == 0U || right.denominator == 0U) {
    return fail<ExactRational>(protocol::ErrorCategory::out_of_range, std::move(path),
                               "CAL-RATIONAL-DENOMINATOR",
                               "exact rational denominator must be nonzero");
  }
  auto left_numerator = left.numerator;
  auto left_denominator = left.denominator;
  auto right_numerator = right.numerator;
  auto right_denominator = right.denominator;
  auto divisor = std::gcd(left_numerator, right_denominator);
  left_numerator /= divisor;
  right_denominator /= divisor;
  divisor = std::gcd(right_numerator, left_denominator);
  right_numerator /= divisor;
  left_denominator /= divisor;
  std::uint64_t numerator = 0U;
  std::uint64_t denominator = 0U;
  if (!checked_multiply(left_numerator, right_numerator, numerator) ||
      !checked_multiply(left_denominator, right_denominator, denominator)) {
    return fail<ExactRational>(protocol::ErrorCategory::out_of_range, std::move(path),
                               "CAL-RATIONAL-OVERFLOW",
                               "exact rational multiplication overflows u64");
  }
  return make_rational(numerator, denominator, std::move(path));
}

auto required_service_cells() -> std::vector<ServiceCellKey> {
  constexpr std::array packages{protocol::QueuePackage::r0, protocol::QueuePackage::r1,
                                protocol::QueuePackage::r2, protocol::QueuePackage::l0,
                                protocol::QueuePackage::l1};
  constexpr std::array states{protocol::RequestedHardwareState::h0,
                              protocol::RequestedHardwareState::h1};
  constexpr std::array placements{protocol::Placement::near, protocol::Placement::far};
  constexpr std::array working_sets{protocol::WorkingSetClass::l2_resident,
                                    protocol::WorkingSetClass::llc_resident,
                                    protocol::WorkingSetClass::beyond_llc};
  std::vector<ServiceCellKey> cells;
  cells.reserve(kRequiredServiceCellCount);
  for (const auto package : packages) {
    for (const auto state : states) {
      for (const auto placement : placements) {
        for (const auto working_set : working_sets) {
          cells.push_back({package, state, placement, working_set});
        }
      }
    }
  }
  return cells;
}

auto evaluate_service_rate(const ServiceRatePlan& plan,
                           const std::vector<ServiceRunEvidence>& runs)
    -> protocol::Result<ServiceRateResult> {
  if (!valid_opaque_id(plan.record_id) || !valid_opaque_id(plan.seed_namespace_id) ||
      plan.assumptions.empty() ||
      std::any_of(plan.assumptions.begin(), plan.assumptions.end(),
                  [](const std::string& assumption) { return assumption.empty(); }) ||
      !valid_governance(plan.governance) || plan.estimator_id != kServiceRateMethodId) {
    return fail<ServiceRateResult>(
        protocol::ErrorCategory::missing_field, "$/service_plan",
        "CAL-SERVICE-PLAN-IDENTITY",
        "plan requires explicit identity, namespace, and accepted estimator");
  }
  std::set<std::string> cell_names;
  std::set<std::string> planned_runs;
  for (const auto& cell : plan.cells) {
    if (!expected_service_key(cell.key) || !valid_context(cell.context) ||
        cell.duration_ticks == 0U || cell.ticks_per_second == 0U ||
        !cell_names.insert(service_key_name(cell.key)).second) {
      return fail<ServiceRateResult>(protocol::ErrorCategory::cross_field,
                                     "$/service_plan/cells", "CAL-SERVICE-CELL-PLAN",
                                     "service cell is invalid or duplicated");
    }
    for (const auto& run_id : cell.planned_run_ids) {
      if (!planned_runs.insert(std::string(run_id.value())).second) {
        return fail<ServiceRateResult>(protocol::ErrorCategory::duplicate_value,
                                       "$/service_plan/cells/planned_run_ids",
                                       "CAL-PLAN-RUN-UNIQUE",
                                       "planned run identity must be globally unique");
      }
    }
  }

  std::set<std::string> present_runs;
  for (const auto& run : runs) {
    const auto run_name = std::string(run.run_id.value());
    if (!planned_runs.contains(run_name)) {
      return fail<ServiceRateResult>(protocol::ErrorCategory::reference_mismatch,
                                     "$/service_runs/run_id", "CAL-NO-TOP-UP",
                                     "run was not in the prospective plan");
    }
    if (!present_runs.insert(run_name).second) {
      return fail<ServiceRateResult>(protocol::ErrorCategory::duplicate_value,
                                     "$/service_runs/run_id", "CAL-RUN-EVIDENCE-UNIQUE",
                                     "run evidence must be unique");
    }
  }

  ServiceRateResult result{EvaluationState::resolved, {}, std::nullopt, {}, {}};
  const auto required = required_service_cells();
  result.cells.reserve(required.size());
  for (const auto& required_key : required) {
    const auto plan_cell = std::find_if(plan.cells.begin(), plan.cells.end(),
                                        [&](const ServiceCellPlan& candidate) {
                                          return candidate.key == required_key;
                                        });
    if (plan_cell == plan.cells.end()) {
      result.state = EvaluationState::not_evaluated;
      result.blockers.push_back("missing required service cell " +
                                service_key_name(required_key));
      result.cells.push_back({required_key,
                              EvaluationState::not_evaluated,
                              0U,
                              0U,
                              0U,
                              std::nullopt,
                              {},
                              {"cell absent from prospective plan"}});
      continue;
    }

    ServiceCellResult cell_result{required_key,
                                  EvaluationState::resolved,
                                  plan_cell->planned_run_ids.size(),
                                  0U,
                                  0U,
                                  std::nullopt,
                                  {},
                                  {}};
    std::optional<ExactRational> minimum;
    for (const auto& planned_run_id : plan_cell->planned_run_ids) {
      const auto evidence = std::find_if(runs.begin(), runs.end(),
                                         [&](const ServiceRunEvidence& candidate) {
                                           return candidate.run_id == planned_run_id;
                                         });
      if (evidence == runs.end()) {
        cell_result.blockers.push_back("planned run evidence is missing: " +
                                       std::string(planned_run_id.value()));
        continue;
      }
      ++cell_result.present_runs;
      if (!(evidence->key == required_key) ||
          !(evidence->context == plan_cell->context) ||
          evidence->stage != protocol::Stage::calibration ||
          evidence->run_mode != protocol::RunMode::service_rate_calibration ||
          evidence->arrival_family != protocol::ArrivalFamily::continuous_ready ||
          evidence->interval_ticks != plan_cell->duration_ticks ||
          evidence->ticks_per_second != plan_cell->ticks_per_second) {
        return fail<ServiceRateResult>(
            protocol::ErrorCategory::reference_mismatch, "$/service_runs",
            "CAL-SERVICE-STAGE-A-MATCH",
            "service evidence differs from its Stage A context or fixed plan");
      }
      if (!references_valid(evidence->raw_run_artifacts) ||
          (evidence->integrity_artifact.has_value() &&
           !valid_reference(*evidence->integrity_artifact)) ||
          (evidence->failure_artifact.has_value() &&
           !valid_reference(*evidence->failure_artifact))) {
        return fail<ServiceRateResult>(
            protocol::ErrorCategory::invalid_hash, "$/service_runs/artifacts",
            "CAL-EVIDENCE-REFERENCE", "evidence reference is malformed");
      }
      if (evidence->validity == CalibrationRunValidity::invalid) {
        if (!evidence->failure_artifact.has_value()) {
          return fail<ServiceRateResult>(
              protocol::ErrorCategory::missing_evidence,
              "$/service_runs/failure_artifact", "CAL-INVALID-REQUIRES-FAILURE",
              "invalid calibration run needs failure evidence");
        }
        cell_result.run_decisions.push_back(
            {evidence->run_id, evidence->validity, evidence->consumed_events,
             evidence->interval_ticks, evidence->ticks_per_second, std::nullopt,
             evidence->raw_run_artifacts, evidence->integrity_artifact,
             evidence->failure_artifact});
        continue;
      }
      if (evidence->raw_run_artifacts.empty() ||
          !evidence->integrity_artifact.has_value()) {
        return fail<ServiceRateResult>(
            protocol::ErrorCategory::missing_evidence, "$/service_runs",
            "CAL-VALID-REQUIRES-EVIDENCE",
            "valid calibration run needs raw and integrity evidence");
      }
      const auto throughput =
          exact_throughput({evidence->consumed_events, evidence->ticks_per_second,
                            evidence->interval_ticks});
      if (!throughput) {
        return protocol::Result<ServiceRateResult>::failure(throughput.errors());
      }
      cell_result.run_decisions.push_back(
          {evidence->run_id, evidence->validity, evidence->consumed_events,
           evidence->interval_ticks, evidence->ticks_per_second, throughput.value(),
           evidence->raw_run_artifacts, evidence->integrity_artifact,
           evidence->failure_artifact});
      ++cell_result.valid_runs;
      const auto is_new_minimum = minimum.has_value()
                                      ? compare(throughput.value(), *minimum)
                                      : protocol::Result<int>::success(-1);
      if (!is_new_minimum) {
        return protocol::Result<ServiceRateResult>::failure(is_new_minimum.errors());
      }
      if (is_new_minimum.value() < 0) {
        minimum = throughput.value();
      }
    }
    if (cell_result.present_runs != cell_result.planned_runs) {
      cell_result.blockers.push_back("prospective run plan is incomplete");
    }
    if (cell_result.valid_runs < kMinimumValidIndependentRuns) {
      cell_result.blockers.push_back("fewer than 59 valid independent runs");
    }
    if (!cell_result.blockers.empty()) {
      cell_result.state = EvaluationState::not_evaluated;
      result.state = EvaluationState::not_evaluated;
      result.blockers.push_back("unresolved service cell " +
                                service_key_name(required_key));
    } else {
      cell_result.mu_cell = minimum;
      const auto is_global_minimum = result.mu_ref.has_value()
                                         ? compare(*minimum, *result.mu_ref)
                                         : protocol::Result<int>::success(-1);
      if (!is_global_minimum) {
        return protocol::Result<ServiceRateResult>::failure(is_global_minimum.errors());
      }
      if (is_global_minimum.value() < 0) {
        result.mu_ref = minimum;
      }
    }
    result.cells.push_back(std::move(cell_result));
  }
  if (plan.cells.size() != kRequiredServiceCellCount) {
    result.state = EvaluationState::not_evaluated;
    result.blockers.push_back("service plan is not the exact 60-cell product");
  }
  if (result.state == EvaluationState::resolved && result.mu_ref.has_value()) {
    for (const auto factor : std::array<ExactRational, 3>{
             ExactRational{1U, 4U}, ExactRational{1U, 2U}, ExactRational{3U, 4U}}) {
      const auto candidate = multiply(*result.mu_ref, factor, "$/candidate_loads");
      if (!candidate) {
        return protocol::Result<ServiceRateResult>::failure(candidate.errors());
      }
      result.candidate_loads.push_back(candidate.value());
    }
  } else {
    result.mu_ref.reset();
  }
  return protocol::Result<ServiceRateResult>::success(result);
}

RingDemandTrace::RingDemandTrace(std::size_t max_attempts_per_worker)
    : max_attempts_per_worker_(max_attempts_per_worker) {
  if (max_attempts_per_worker_ == 0U) {
    throw std::invalid_argument(
        "ring demand trace requires an explicit nonzero attempt capacity");
  }
  series_.producer_demand_ticks.reserve(max_attempts_per_worker_);
  series_.consumer_demand_ticks.reserve(max_attempts_per_worker_);
  series_.producer_issue_ticks.reserve(max_attempts_per_worker_);
  series_.consumer_issue_ticks.reserve(max_attempts_per_worker_);
}

auto RingDemandTrace::record(RingWorker worker, std::uint64_t demand_start,
                             std::uint64_t demand_end,
                             RingAttemptOutcome outcome) noexcept -> bool {
  if (outcome == RingAttemptOutcome::clock_failure ||
      outcome == RingAttemptOutcome::trace_failure || demand_end < demand_start) {
    return false;
  }
  if ((outcome == RingAttemptOutcome::full && worker != RingWorker::producer) ||
      (outcome == RingAttemptOutcome::empty && worker != RingWorker::consumer)) {
    return false;
  }
  auto& demand = worker == RingWorker::producer ? series_.producer_demand_ticks
                                                : series_.consumer_demand_ticks;
  auto& previous = worker == RingWorker::producer ? previous_producer_advance_start_
                                                  : previous_consumer_advance_start_;
  auto& issue = worker == RingWorker::producer ? series_.producer_issue_ticks
                                               : series_.consumer_issue_ticks;
  if (demand.size() >= max_attempts_per_worker_ ||
      (outcome == RingAttemptOutcome::advanced && previous.has_value() &&
       issue.size() >= max_attempts_per_worker_)) {
    return false;
  }
  if (outcome == RingAttemptOutcome::advanced && previous.has_value() &&
      demand_start < *previous) {
    return false;
  }
  demand.push_back(demand_end - demand_start);
  if (outcome == RingAttemptOutcome::full) {
    ++series_.producer_full_count;
    return true;
  }
  if (outcome == RingAttemptOutcome::empty) {
    ++series_.consumer_empty_count;
    return true;
  }
  if (previous.has_value()) {
    issue.push_back(demand_start - *previous);
  }
  previous = demand_start;
  return true;
}

auto required_ring_contexts() -> std::vector<RingContextKey> {
  constexpr std::array placements{protocol::Placement::near, protocol::Placement::far};
  constexpr std::array working_sets{protocol::WorkingSetClass::l2_resident,
                                    protocol::WorkingSetClass::llc_resident,
                                    protocol::WorkingSetClass::beyond_llc};
  std::vector<RingContextKey> contexts;
  contexts.reserve(kRequiredRingContextCount);
  for (const auto placement : placements) {
    for (const auto working_set : working_sets) {
      contexts.push_back({placement, working_set});
    }
  }
  return contexts;
}

auto inverse_ecdf(std::vector<std::uint64_t> values,
                  std::uint64_t probability_numerator,
                  std::uint64_t probability_denominator)
    -> protocol::Result<std::uint64_t> {
  if (values.empty() || probability_numerator == 0U ||
      probability_numerator > probability_denominator ||
      probability_denominator == 0U) {
    return fail<std::uint64_t>(protocol::ErrorCategory::out_of_range, "$/quantile",
                               "CAL-INVERSE-ECDF-INPUT",
                               "inverse ECDF needs data and probability in (0,1]");
  }
  const auto count = static_cast<std::uint64_t>(values.size());
  std::uint64_t whole = 0U;
  if (!checked_multiply(count / probability_denominator, probability_numerator,
                        whole)) {
    return fail<std::uint64_t>(protocol::ErrorCategory::out_of_range, "$/quantile/rank",
                               "CAL-QUANTILE-OVERFLOW", "quantile rank overflows u64");
  }
  std::uint64_t remainder_product = 0U;
  if (!checked_multiply(count % probability_denominator, probability_numerator,
                        remainder_product)) {
    return fail<std::uint64_t>(protocol::ErrorCategory::out_of_range, "$/quantile/rank",
                               "CAL-QUANTILE-OVERFLOW", "quantile rank overflows u64");
  }
  std::uint64_t remainder_rank = 0U;
  if (!checked_ceil_divide(remainder_product, probability_denominator,
                           remainder_rank) ||
      whole > std::numeric_limits<std::uint64_t>::max() - remainder_rank) {
    return fail<std::uint64_t>(protocol::ErrorCategory::out_of_range, "$/quantile/rank",
                               "CAL-QUANTILE-OVERFLOW", "quantile rank overflows u64");
  }
  const auto rank = whole + remainder_rank;
  if (rank == 0U || rank > count) {
    return fail<std::uint64_t>(protocol::ErrorCategory::cross_field, "$/quantile/rank",
                               "CAL-QUANTILE-RANK",
                               "quantile rank is outside the observed sequence");
  }
  std::sort(values.begin(), values.end());
  return protocol::Result<std::uint64_t>::success(
      values[static_cast<std::size_t>(rank - 1U)]);
}

auto evaluate_ring_distance(const RingDistancePlan& plan,
                            const std::vector<RingRunEvidence>& runs)
    -> protocol::Result<RingDistanceResult> {
  if (!valid_opaque_id(plan.record_id) || !valid_opaque_id(plan.seed_namespace_id) ||
      plan.assumptions.empty() ||
      std::any_of(plan.assumptions.begin(), plan.assumptions.end(),
                  [](const std::string& assumption) { return assumption.empty(); }) ||
      !valid_governance(plan.governance) ||
      plan.estimator_id != kRingDistanceMethodId) {
    return fail<RingDistanceResult>(
        protocol::ErrorCategory::missing_field, "$/ring_plan", "CAL-RING-PLAN-IDENTITY",
        "plan requires explicit identity, namespace, and accepted estimator");
  }
  std::set<std::string> context_names;
  std::set<std::string> planned_runs;
  for (const auto& context : plan.contexts) {
    if (!expected_ring_key(context.key) || context.duration_ticks == 0U ||
        context.minimum_observations_per_series == 0U ||
        !context_names.insert(ring_key_name(context.key)).second ||
        context.states.size() != 2U) {
      return fail<RingDistanceResult>(protocol::ErrorCategory::cross_field,
                                      "$/ring_plan/contexts", "CAL-RING-CONTEXT-PLAN",
                                      "ring context is invalid or duplicated");
    }
    std::set<unsigned int> states;
    const StageAContext* common_context = nullptr;
    for (const auto& state : context.states) {
      if ((state.hardware_state != protocol::RequestedHardwareState::h0 &&
           state.hardware_state != protocol::RequestedHardwareState::h1) ||
          !valid_context(state.ring_off_context) ||
          state.ring_off_context.logical_capacity != context.geometry.capacity ||
          !states.insert(static_cast<unsigned int>(state.hardware_state)).second) {
        return fail<RingDistanceResult>(
            protocol::ErrorCategory::cross_field, "$/ring_plan/contexts/states",
            "CAL-RING-HARDWARE-STATES", "ring context requires unique H0 and H1 plans");
      }
      if (common_context != nullptr &&
          !same_ring_context_except_hardware(*common_context, state.ring_off_context)) {
        return fail<RingDistanceResult>(
            protocol::ErrorCategory::reference_mismatch,
            "$/ring_plan/contexts/states/ring_off_context", "CAL-RING-STAGE-A-CONTEXT",
            "H0 and H1 must differ only by verified hardware-state evidence");
      }
      common_context = &state.ring_off_context;
      for (const auto& run_id : state.planned_run_ids) {
        if (!planned_runs.insert(std::string(run_id.value())).second) {
          return fail<RingDistanceResult>(
              protocol::ErrorCategory::duplicate_value, "$/ring_plan/planned_run_ids",
              "CAL-PLAN-RUN-UNIQUE", "planned run identity must be globally unique");
        }
      }
    }
  }

  std::set<std::string> present_runs;
  for (const auto& run : runs) {
    const auto run_name = std::string(run.run_id.value());
    if (!planned_runs.contains(run_name)) {
      return fail<RingDistanceResult>(protocol::ErrorCategory::reference_mismatch,
                                      "$/ring_runs/run_id", "CAL-NO-TOP-UP",
                                      "run was not in the prospective plan");
    }
    if (!present_runs.insert(run_name).second) {
      return fail<RingDistanceResult>(protocol::ErrorCategory::duplicate_value,
                                      "$/ring_runs/run_id", "CAL-RUN-EVIDENCE-UNIQUE",
                                      "run evidence must be unique");
    }
  }

  RingDistanceResult result{EvaluationState::resolved, {}, {}};
  for (const auto& required_key : required_ring_contexts()) {
    const auto context = std::find_if(plan.contexts.begin(), plan.contexts.end(),
                                      [&](const RingContextPlan& candidate) {
                                        return candidate.key == required_key;
                                      });
    if (context == plan.contexts.end()) {
      result.state = EvaluationState::not_evaluated;
      result.blockers.push_back("missing required ring context " +
                                ring_key_name(required_key));
      result.contexts.push_back({required_key,
                                 EvaluationState::not_evaluated,
                                 std::nullopt,
                                 std::nullopt,
                                 std::nullopt,
                                 std::nullopt,
                                 std::nullopt,
                                 std::nullopt,
                                 std::nullopt,
                                 std::nullopt,
                                 std::nullopt,
                                 std::nullopt,
                                 {},
                                 {"context absent from prospective plan"}});
      continue;
    }

    RingContextResult context_result{required_key, EvaluationState::resolved,
                                     std::nullopt, std::nullopt,
                                     std::nullopt, std::nullopt,
                                     std::nullopt, std::nullopt,
                                     std::nullopt, std::nullopt,
                                     std::nullopt, std::nullopt,
                                     {},           {}};
    std::optional<std::uint64_t> producer_demand_limit;
    std::optional<std::uint64_t> consumer_demand_limit;
    std::optional<std::uint64_t> producer_issue_limit;
    std::optional<std::uint64_t> consumer_issue_limit;
    for (const auto& state : context->states) {
      std::size_t present = 0U;
      std::size_t valid = 0U;
      for (const auto& planned_run_id : state.planned_run_ids) {
        const auto evidence = std::find_if(runs.begin(), runs.end(),
                                           [&](const RingRunEvidence& candidate) {
                                             return candidate.run_id == planned_run_id;
                                           });
        if (evidence == runs.end()) {
          continue;
        }
        ++present;
        if (!(evidence->key == required_key) ||
            !(evidence->ring_off_context == state.ring_off_context) ||
            evidence->hardware_state != state.hardware_state ||
            evidence->stage != protocol::Stage::calibration ||
            evidence->run_mode != protocol::RunMode::d2_calibration ||
            evidence->package != protocol::QueuePackage::r0 ||
            evidence->interval_ticks != context->duration_ticks) {
          return fail<RingDistanceResult>(
              protocol::ErrorCategory::reference_mismatch, "$/ring_runs",
              "CAL-RING-R0-CONTEXT",
              "ring evidence is not matching ring-off calibration evidence");
        }
        if (!references_valid(evidence->raw_run_artifacts) ||
            (evidence->integrity_artifact.has_value() &&
             !valid_reference(*evidence->integrity_artifact)) ||
            (evidence->failure_artifact.has_value() &&
             !valid_reference(*evidence->failure_artifact))) {
          return fail<RingDistanceResult>(
              protocol::ErrorCategory::invalid_hash, "$/ring_runs/artifacts",
              "CAL-EVIDENCE-REFERENCE", "evidence reference is malformed");
        }
        if (evidence->validity == CalibrationRunValidity::invalid) {
          if (!evidence->failure_artifact.has_value()) {
            return fail<RingDistanceResult>(
                protocol::ErrorCategory::missing_evidence,
                "$/ring_runs/failure_artifact", "CAL-INVALID-REQUIRES-FAILURE",
                "invalid calibration run needs failure evidence");
          }
          context_result.run_decisions.push_back(
              {evidence->run_id, evidence->hardware_state, evidence->validity,
               std::nullopt, std::nullopt, std::nullopt, std::nullopt,
               evidence->raw_run_artifacts, evidence->integrity_artifact,
               evidence->failure_artifact});
          continue;
        }
        const auto& series = evidence->series;
        const auto minimum_count = context->minimum_observations_per_series;
        if (series.producer_demand_ticks.size() < minimum_count ||
            series.consumer_demand_ticks.size() < minimum_count ||
            series.producer_issue_ticks.size() < minimum_count ||
            series.consumer_issue_ticks.size() < minimum_count ||
            !all_positive(series.producer_demand_ticks) ||
            !all_positive(series.consumer_demand_ticks) ||
            !all_positive(series.producer_issue_ticks) ||
            !all_positive(series.consumer_issue_ticks) ||
            evidence->raw_run_artifacts.empty() ||
            !evidence->integrity_artifact.has_value()) {
          return fail<RingDistanceResult>(
              protocol::ErrorCategory::missing_evidence, "$/ring_runs/series",
              "CAL-RING-VALID-SERIES",
              "a run marked valid needs complete positive demand/issue series and "
              "raw integrity evidence");
        }
        const auto producer_demand =
            inverse_ecdf(series.producer_demand_ticks, 999U, 1000U);
        const auto consumer_demand =
            inverse_ecdf(series.consumer_demand_ticks, 999U, 1000U);
        const auto producer_issue =
            inverse_ecdf(series.producer_issue_ticks, 1U, 1000U);
        const auto consumer_issue =
            inverse_ecdf(series.consumer_issue_ticks, 1U, 1000U);
        if (!producer_demand || !consumer_demand || !producer_issue ||
            !consumer_issue) {
          return fail<RingDistanceResult>(protocol::ErrorCategory::cross_field,
                                          "$/ring_runs/series", "CAL-RING-QUANTILES",
                                          "ring calibration quantile failed");
        }
        context_result.run_decisions.push_back(
            {evidence->run_id, evidence->hardware_state, evidence->validity,
             producer_demand.value(), consumer_demand.value(), producer_issue.value(),
             consumer_issue.value(), evidence->raw_run_artifacts,
             evidence->integrity_artifact, evidence->failure_artifact});
        if (!producer_demand_limit.has_value() ||
            producer_demand.value() > *producer_demand_limit) {
          producer_demand_limit = producer_demand.value();
        }
        if (!consumer_demand_limit.has_value() ||
            consumer_demand.value() > *consumer_demand_limit) {
          consumer_demand_limit = consumer_demand.value();
        }
        if (!producer_issue_limit.has_value() ||
            producer_issue.value() < *producer_issue_limit) {
          producer_issue_limit = producer_issue.value();
        }
        if (!consumer_issue_limit.has_value() ||
            consumer_issue.value() < *consumer_issue_limit) {
          consumer_issue_limit = consumer_issue.value();
        }
        ++valid;
      }
      if (present != state.planned_run_ids.size()) {
        context_result.blockers.push_back("prospective H-state run plan is incomplete");
      }
      if (valid < kMinimumValidIndependentRuns) {
        context_result.blockers.push_back(
            "H-state has fewer than 59 valid independent runs");
      }
    }

    if (!context_result.blockers.empty() || !producer_demand_limit.has_value() ||
        !consumer_demand_limit.has_value() || !producer_issue_limit.has_value() ||
        !consumer_issue_limit.has_value()) {
      context_result.state = EvaluationState::not_evaluated;
      result.state = EvaluationState::not_evaluated;
      result.blockers.push_back("unresolved ring context " +
                                ring_key_name(required_key));
      result.contexts.push_back(std::move(context_result));
      continue;
    }
    context_result.producer_demand_upper_ticks = producer_demand_limit;
    context_result.consumer_demand_upper_ticks = consumer_demand_limit;
    context_result.producer_issue_lower_ticks = producer_issue_limit;
    context_result.consumer_issue_lower_ticks = consumer_issue_limit;
    const auto conservative_demand =
        std::max(*producer_demand_limit, *consumer_demand_limit);
    const auto conservative_issue =
        std::min(*producer_issue_limit, *consumer_issue_limit);
    context_result.conservative_demand_ticks = conservative_demand;
    context_result.conservative_issue_ticks = conservative_issue;
    const auto& geometry = context->geometry;
    if (geometry.capacity == 0U || geometry.cache_line_bytes == 0U ||
        geometry.slot_bytes == 0U) {
      context_result.state = EvaluationState::ineligible;
      context_result.blockers.push_back("ring geometry is incomplete");
    } else {
      std::uint64_t d1_slots = 0U;
      std::uint64_t raw_slots = 0U;
      std::uint64_t raw_lines = 0U;
      const auto capacity = static_cast<std::uint64_t>(geometry.capacity);
      if (!checked_ceil_divide(static_cast<std::uint64_t>(geometry.cache_line_bytes),
                               static_cast<std::uint64_t>(geometry.slot_bytes),
                               d1_slots) ||
          !checked_ceil_divide(conservative_demand, conservative_issue, raw_slots) ||
          !checked_ceil_divide(raw_slots, d1_slots, raw_lines)) {
        context_result.state = EvaluationState::ineligible;
        context_result.blockers.push_back("distance arithmetic failed");
      } else {
        context_result.d1_slots = d1_slots;
        const auto cap_lines = (capacity / 4U) / d1_slots;
        const auto d2_lines =
            std::min(std::max<std::uint64_t>(2U, raw_lines), cap_lines);
        std::uint64_t d2_slots = 0U;
        if (cap_lines < 2U || !checked_multiply(d2_lines, d1_slots, d2_slots) ||
            d2_slots <= d1_slots) {
          context_result.state = EvaluationState::ineligible;
          context_result.blockers.push_back(
              "one-quarter cap collapses d2 to d1 or below two lines");
        } else {
          context_result.d2_cache_lines = d2_lines;
          context_result.producer_distance_slots = d2_slots;
          context_result.consumer_distance_slots = d2_slots;
        }
      }
    }
    if (context_result.state == EvaluationState::ineligible) {
      result.state = EvaluationState::ineligible;
      result.blockers.push_back("ineligible ring context " +
                                ring_key_name(required_key));
    }
    result.contexts.push_back(std::move(context_result));
  }
  if (plan.contexts.size() != kRequiredRingContextCount) {
    result.state = EvaluationState::not_evaluated;
    result.blockers.push_back("ring plan is not the exact six-context product");
  }
  return protocol::Result<RingDistanceResult>::success(result);
}

} // namespace cpu_prefetch::calibration
