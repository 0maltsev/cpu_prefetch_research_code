#ifndef CPU_PREFETCH_STORAGE_BUDGET_HPP
#define CPU_PREFETCH_STORAGE_BUDGET_HPP

#include "cpu_prefetch/protocol/validation.hpp"

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace cpu_prefetch::storage {

inline constexpr std::uint64_t kStageACellsPerBlock = 180U;
inline constexpr std::uint64_t kTemporaryRawCopies = 1U;
inline constexpr std::uint64_t kDurableRawCopies = 2U;

struct RunStorageInput final {
  std::string run_id;
  std::uint64_t scheduled_rows;
  std::uint64_t accepted_rows;
  std::optional<std::uint64_t> effective_rows;
};

struct RunStorageBudget final {
  std::string run_id;
  std::uint64_t producer_row_bytes;
  std::uint64_t consumer_row_bytes;
  std::uint64_t joined_row_bytes;
  std::uint64_t producer_payload_bytes;
  std::uint64_t consumer_payload_bytes;
  std::uint64_t joined_payload_bytes;
  std::uint64_t actual_hot_payload_bytes;
  std::uint64_t conservative_hot_payload_bytes;
  std::uint64_t producer_mapped_bytes;
  std::uint64_t consumer_mapped_bytes;
  std::uint64_t conservative_mapped_hot_bytes;
  std::uint64_t raw_storage_bytes;
  bool primary_tail_count_possible;
  bool secondary_tail_count_possible;
};

struct AuxiliaryStorageBytes final {
  std::uint64_t envelopes;
  std::uint64_t integrity_records;
  std::uint64_t copy_ledgers;
  std::uint64_t schedules;
  std::uint64_t manifests;
  std::uint64_t filesystem_overhead;
  std::uint64_t operator_reserve;
};

struct StageAStorageBudgetRequest final {
  std::vector<RunStorageInput> runs;
  std::uint64_t r_total;
  std::uint64_t block_count;
  std::uint64_t verified_base_page_bytes;
  AuxiliaryStorageBytes auxiliary;
  std::uint64_t available_bytes;
};

struct StageAStorageBudget final {
  std::uint64_t run_count;
  std::uint64_t block_count;
  std::uint64_t r_total;
  std::uint64_t temporary_raw_copies;
  std::uint64_t durable_raw_copies;
  std::uint64_t raw_storage_bytes;
  std::uint64_t auxiliary_and_reserve_bytes;
  std::uint64_t required_bytes;
  std::uint64_t available_bytes;
  bool capacity_pass;
  std::vector<RunStorageBudget> runs;
};

[[nodiscard]] auto checked_run_storage_budget(const RunStorageInput& input,
                                              std::uint64_t base_page_bytes)
    -> protocol::Result<RunStorageBudget>;

[[nodiscard]] auto
checked_stage_a_storage_budget(const StageAStorageBudgetRequest& request)
    -> protocol::Result<StageAStorageBudget>;

} // namespace cpu_prefetch::storage

#endif // CPU_PREFETCH_STORAGE_BUDGET_HPP
