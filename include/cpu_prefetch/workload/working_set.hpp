#ifndef CPU_PREFETCH_WORKLOAD_WORKING_SET_HPP
#define CPU_PREFETCH_WORKLOAD_WORKING_SET_HPP

#include "cpu_prefetch/protocol/model.hpp"
#include "cpu_prefetch/workload/records.hpp"

#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <vector>

namespace cpu_prefetch::workload {

struct SharedFootprintCandidate final {
  std::size_t capacity;
  std::uint64_t ring_bytes;
  std::uint64_t linked_bytes;
};

struct CacheCapacityEvidence final {
  std::uint64_t cache_line_bytes;
  std::uint64_t smaller_usable_l2_bytes;
  std::uint64_t producer_home_usable_llc_bytes;
};

struct CapacitySelection final {
  protocol::WorkingSetClass working_set_class;
  SharedFootprintCandidate selected;
};

[[nodiscard]] SharedFootprintCandidate
make_shared_footprint_candidate(std::size_t capacity, std::uint64_t event_arena_bytes,
                                std::uint64_t ring_queue_bytes,
                                std::uint64_t linked_queue_bytes);

[[nodiscard]] CapacitySelection
select_common_capacity(protocol::WorkingSetClass working_set_class,
                       const CacheCapacityEvidence& cache_evidence,
                       std::span<const SharedFootprintCandidate> candidates);

struct AddressPatternSummary final {
  std::size_t transition_count;
  std::size_t distinct_line_count;
  std::size_t distinct_page_count;
  std::size_t shortest_period;
  std::size_t adjacent_line_transition_count;
  std::size_t modal_nonzero_delta_count;
  std::optional<std::int64_t> modal_nonzero_delta;
  bool adjacent_fraction_at_most_one_percent;
  bool modal_fraction_at_most_one_percent;
};

struct NodeOrderConfig final {
  std::size_t logical_capacity;
  std::size_t node_stride_bytes;
  std::size_t cache_line_bytes;
  std::size_t base_page_bytes;
};

class NodeOrderPlan final {
public:
  NodeOrderPlan(const NodeOrderConfig& config, const MasterSeed& master_seed,
                const std::string& seed_namespace);

  [[nodiscard]] std::size_t logical_capacity() const noexcept {
    return order_.size() - 1U;
  }
  [[nodiscard]] std::size_t node_stride_bytes() const noexcept {
    return node_stride_bytes_;
  }
  [[nodiscard]] std::size_t base_page_bytes() const noexcept {
    return base_page_bytes_;
  }
  [[nodiscard]] std::size_t cache_line_bytes() const noexcept {
    return cache_line_bytes_;
  }
  [[nodiscard]] std::span<const std::size_t> order() const noexcept { return order_; }
  [[nodiscard]] std::span<const std::int64_t> deltas() const noexcept {
    return deltas_;
  }
  [[nodiscard]] const Sha256Digest& ordered_index_checksum() const noexcept {
    return ordered_index_checksum_;
  }
  [[nodiscard]] const Sha256Digest& address_delta_checksum() const noexcept {
    return address_delta_checksum_;
  }
  [[nodiscard]] const AddressPatternSummary& summary() const noexcept {
    return summary_;
  }

private:
  std::size_t node_stride_bytes_{0};
  std::size_t cache_line_bytes_{0};
  std::size_t base_page_bytes_{0};
  std::vector<std::size_t> order_;
  std::vector<std::int64_t> deltas_;
  Sha256Digest ordered_index_checksum_{{}};
  Sha256Digest address_delta_checksum_{{}};
  AddressPatternSummary summary_{};
};

} // namespace cpu_prefetch::workload

#endif // CPU_PREFETCH_WORKLOAD_WORKING_SET_HPP
