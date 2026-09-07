#include "cpu_prefetch/storage/budget.hpp"

#include "cpu_prefetch/storage/raw_observations.hpp"

#include <limits>
#include <string_view>
#include <utility>

namespace cpu_prefetch::storage {
namespace {

[[nodiscard]] auto checked_add(std::uint64_t left, std::uint64_t right,
                               std::uint64_t& output) noexcept -> bool {
  if (right > std::numeric_limits<std::uint64_t>::max() - left) {
    return false;
  }
  output = left + right;
  return true;
}

[[nodiscard]] auto checked_multiply(std::uint64_t left, std::uint64_t right,
                                    std::uint64_t& output) noexcept -> bool {
  if (left != 0U && right > std::numeric_limits<std::uint64_t>::max() / left) {
    return false;
  }
  output = left * right;
  return true;
}

[[nodiscard]] auto checked_round_up(std::uint64_t value, std::uint64_t alignment,
                                    std::uint64_t& output) noexcept -> bool {
  if (alignment == 0U) {
    return false;
  }
  const auto remainder = value % alignment;
  if (remainder == 0U) {
    output = value;
    return true;
  }
  return checked_add(value, alignment - remainder, output);
}

template <typename T>
[[nodiscard]] auto fail(std::string path, std::string rule, std::string message)
    -> protocol::Result<T> {
  return protocol::Result<T>::failure({protocol::ErrorCategory::out_of_range,
                                       std::move(path), std::move(rule),
                                       std::move(message)});
}

[[nodiscard]] auto sum_auxiliary(const AuxiliaryStorageBytes& auxiliary,
                                 std::uint64_t& output) noexcept -> bool {
  output = 0U;
  for (const auto value :
       {auxiliary.envelopes, auxiliary.integrity_records, auxiliary.copy_ledgers,
        auxiliary.schedules, auxiliary.manifests, auxiliary.filesystem_overhead,
        auxiliary.operator_reserve}) {
    if (!checked_add(output, value, output)) {
      return false;
    }
  }
  return true;
}

} // namespace

auto checked_run_storage_budget(const RunStorageInput& input,
                                std::uint64_t base_page_bytes)
    -> protocol::Result<RunStorageBudget> {
  if (base_page_bytes == 0U) {
    return fail<RunStorageBudget>(
        "$input/verified_base_page_bytes", "STO-PAGE-NONZERO",
        "verified base-page bytes must be explicit and nonzero");
  }
  if (input.accepted_rows > input.scheduled_rows) {
    return fail<RunStorageBudget>("$input/accepted_rows", "STO-ACCEPTED-BOUND",
                                  "accepted rows cannot exceed scheduled rows");
  }
  if (input.effective_rows.has_value() && *input.effective_rows > input.accepted_rows) {
    return fail<RunStorageBudget>("$input/effective_rows", "STO-NEFF-BOUND",
                                  "effective rows cannot exceed accepted rows");
  }

  RowLayout layout{};
  try {
    layout = make_row_layout(input.run_id);
  } catch (const StorageSetupError& error) {
    return fail<RunStorageBudget>("$input/run_id", "STO-RUN-ID", error.what());
  }

  std::uint64_t producer = 0U;
  std::uint64_t consumer = 0U;
  std::uint64_t joined = 0U;
  std::uint64_t actual_hot = 0U;
  std::uint64_t conservative_row_pair = 0U;
  std::uint64_t conservative_hot = 0U;
  std::uint64_t producer_mapped = 0U;
  std::uint64_t consumer_conservative = 0U;
  std::uint64_t consumer_mapped = 0U;
  std::uint64_t mapped_hot = 0U;
  std::uint64_t raw_pair = 0U;
  std::uint64_t raw_three = 0U;
  std::uint64_t joined_two = 0U;
  std::uint64_t raw_total = 0U;
  const bool ok =
      checked_multiply(input.scheduled_rows, layout.producer_row_bytes, producer) &&
      checked_multiply(input.accepted_rows, layout.consumer_row_bytes, consumer) &&
      checked_multiply(input.accepted_rows, layout.joined_row_bytes, joined) &&
      checked_add(producer, consumer, actual_hot) &&
      checked_add(layout.producer_row_bytes, layout.consumer_row_bytes,
                  conservative_row_pair) &&
      checked_multiply(input.scheduled_rows, conservative_row_pair, conservative_hot) &&
      checked_round_up(producer, base_page_bytes, producer_mapped) &&
      checked_multiply(input.scheduled_rows, layout.consumer_row_bytes,
                       consumer_conservative) &&
      checked_round_up(consumer_conservative, base_page_bytes, consumer_mapped) &&
      checked_add(producer_mapped, consumer_mapped, mapped_hot) &&
      checked_add(producer, consumer, raw_pair) &&
      checked_multiply(kTemporaryRawCopies + kDurableRawCopies, raw_pair, raw_three) &&
      checked_multiply(kDurableRawCopies, joined, joined_two) &&
      checked_add(raw_three, joined_two, raw_total);
  if (!ok) {
    return fail<RunStorageBudget>("$input", "STO-RUN-BUDGET-OVERFLOW",
                                  "run storage budget arithmetic overflows uint64");
  }
  const auto effective = input.effective_rows.value_or(0U);
  return protocol::Result<RunStorageBudget>::success(
      {input.run_id, layout.producer_row_bytes, layout.consumer_row_bytes,
       layout.joined_row_bytes, producer, consumer, joined, actual_hot,
       conservative_hot, producer_mapped, consumer_mapped, mapped_hot, raw_total,
       input.effective_rows.has_value() && effective >= 200'000U,
       input.effective_rows.has_value() && effective >= 2'000'000U});
}

auto checked_stage_a_storage_budget(const StageAStorageBudgetRequest& request)
    -> protocol::Result<StageAStorageBudget> {
  if (request.r_total == 0U || request.block_count == 0U) {
    return fail<StageAStorageBudget>(
        "$input/r_total", "STO-RUN-PLAN-NONZERO",
        "Rtotal and block count must be explicit and nonzero");
  }
  if (request.r_total != request.block_count) {
    return fail<StageAStorageBudget>(
        "$input/block_count", "STO-BLOCK-RUN-PLAN",
        "the Stage A plan must explicitly bind one 180-cell block per Rtotal unit");
  }
  std::uint64_t expected_runs = 0U;
  if (!checked_multiply(kStageACellsPerBlock, request.r_total, expected_runs) ||
      expected_runs != request.runs.size()) {
    return fail<StageAStorageBudget>(
        "$input/runs", "STO-STAGE-A-RUN-COUNT",
        "Stage A storage proof requires exactly 180*Rtotal concrete run terms");
  }
  if (request.available_bytes == 0U) {
    return fail<StageAStorageBudget>(
        "$input/available_bytes", "STO-AVAILABLE-EXPLICIT",
        "available storage must be independently observed and explicitly nonzero");
  }

  std::vector<RunStorageBudget> run_budgets;
  run_budgets.reserve(request.runs.size());
  std::uint64_t raw_total = 0U;
  for (std::size_t index = 0U; index < request.runs.size(); ++index) {
    auto run = checked_run_storage_budget(request.runs[index],
                                          request.verified_base_page_bytes);
    if (!run) {
      auto errors = run.errors();
      for (auto& error : errors) {
        error.path = "$input/runs/" + std::to_string(index) + error.path.substr(6U);
      }
      return protocol::Result<StageAStorageBudget>::failure(std::move(errors));
    }
    if (!checked_add(raw_total, run.value().raw_storage_bytes, raw_total)) {
      return fail<StageAStorageBudget>("$input/runs", "STO-PLAN-RAW-OVERFLOW",
                                       "aggregate raw-storage bytes overflow uint64");
    }
    run_budgets.push_back(std::move(run).value());
  }
  std::uint64_t auxiliary = 0U;
  std::uint64_t required = 0U;
  if (!sum_auxiliary(request.auxiliary, auxiliary) ||
      !checked_add(raw_total, auxiliary, required)) {
    return fail<StageAStorageBudget>(
        "$input/auxiliary", "STO-PLAN-AUX-OVERFLOW",
        "aggregate auxiliary/reserve bytes overflow uint64");
  }
  return protocol::Result<StageAStorageBudget>::success(
      {expected_runs, request.block_count, request.r_total, kTemporaryRawCopies,
       kDurableRawCopies, raw_total, auxiliary, required, request.available_bytes,
       request.available_bytes >= required, std::move(run_budgets)});
}

} // namespace cpu_prefetch::storage
