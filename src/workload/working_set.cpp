#include "cpu_prefetch/workload/working_set.hpp"

#include <algorithm>
#include <limits>
#include <map>
#include <set>

namespace cpu_prefetch::workload {
namespace {

struct AddressGeometry final {
  std::size_t stride_bytes;
  std::size_t base_page_bytes;
};

[[nodiscard]] bool is_power_of_two(std::size_t value) noexcept {
  return value != 0U && (value & (value - 1U)) == 0U;
}

[[nodiscard]] std::uint64_t checked_product(std::uint64_t left, std::uint64_t right,
                                            std::string_view field) {
  if (left != 0U && right > std::numeric_limits<std::uint64_t>::max() / left) {
    throw WorkloadSetupError(std::string(field) + " overflows uint64");
  }
  return left * right;
}

[[nodiscard]] std::uint64_t checked_sum(std::uint64_t left, std::uint64_t right,
                                        std::string_view field) {
  if (right > std::numeric_limits<std::uint64_t>::max() - left) {
    throw WorkloadSetupError(std::string(field) + " overflows uint64");
  }
  return left + right;
}

[[nodiscard]] bool both_match(const SharedFootprintCandidate& candidate,
                              const CacheCapacityEvidence& cache,
                              protocol::WorkingSetClass working_set_class) {
  const auto lower_l2 =
      checked_product(4U, cache.cache_line_bytes, "four-cache-line lower bound");
  const auto twice_l2 =
      checked_product(2U, cache.smaller_usable_l2_bytes, "two-L2 lower bound");
  const auto twice_llc =
      checked_product(2U, cache.producer_home_usable_llc_bytes, "two-LLC lower bound");
  const auto matches = [&](std::uint64_t footprint) {
    switch (working_set_class) {
    case protocol::WorkingSetClass::l2_resident:
      return footprint > lower_l2 && footprint <= cache.smaller_usable_l2_bytes / 2U;
    case protocol::WorkingSetClass::llc_resident:
      return footprint > twice_l2 &&
             footprint <= cache.producer_home_usable_llc_bytes / 2U;
    case protocol::WorkingSetClass::beyond_llc:
      return footprint >= twice_llc;
    case protocol::WorkingSetClass::not_applicable:
      break;
    }
    return false;
  };
  return matches(candidate.ring_bytes) && matches(candidate.linked_bytes);
}

[[nodiscard]] bool one_percent_or_less(std::size_t count, std::size_t total) noexcept {
  return count <= total / 100U;
}

[[nodiscard]] AddressPatternSummary summarize(std::span<const std::size_t> order,
                                              std::span<const std::int64_t> deltas,
                                              AddressGeometry geometry) {
  std::size_t adjacent_count = 0U;
  std::map<std::int64_t, std::size_t> nonzero_counts;
  for (const auto delta : deltas) {
    const auto magnitude = delta < 0 ? static_cast<std::uint64_t>(-(delta + 1)) + 1U
                                     : static_cast<std::uint64_t>(delta);
    if (magnitude == geometry.stride_bytes) {
      ++adjacent_count;
    }
    if (delta != 0) {
      ++nonzero_counts[delta];
    }
  }

  std::optional<std::int64_t> modal_delta;
  std::size_t modal_count = 0U;
  for (const auto& [delta, count] : nonzero_counts) {
    if (count > modal_count) {
      modal_count = count;
      modal_delta = delta;
    }
  }
  const auto allocated_bytes =
      checked_product(order.size(), geometry.stride_bytes, "node arena byte count");
  const auto page_count = static_cast<std::size_t>(
      (allocated_bytes / geometry.base_page_bytes) +
      (allocated_bytes % geometry.base_page_bytes == 0U ? 0U : 1U));
  return {deltas.size(),
          order.size(),
          page_count,
          order.size(),
          adjacent_count,
          modal_count,
          modal_delta,
          one_percent_or_less(adjacent_count, deltas.size()),
          one_percent_or_less(modal_count, deltas.size())};
}

} // namespace

SharedFootprintCandidate
make_shared_footprint_candidate(std::size_t capacity, std::uint64_t event_arena_bytes,
                                std::uint64_t ring_queue_bytes,
                                std::uint64_t linked_queue_bytes) {
  if (!is_power_of_two(capacity) || event_arena_bytes == 0U || ring_queue_bytes == 0U ||
      linked_queue_bytes == 0U) {
    throw WorkloadSetupError("footprint accounting requires a power-of-two capacity "
                             "and actual nonzero byte counts");
  }
  return {
      capacity,
      checked_sum(event_arena_bytes, ring_queue_bytes, "ring shared footprint"),
      checked_sum(event_arena_bytes, linked_queue_bytes, "linked shared footprint")};
}

CapacitySelection
select_common_capacity(protocol::WorkingSetClass working_set_class,
                       const CacheCapacityEvidence& cache_evidence,
                       std::span<const SharedFootprintCandidate> candidates) {
  if (working_set_class == protocol::WorkingSetClass::not_applicable) {
    throw WorkloadSetupError("Stage A working-set class must be applicable");
  }
  if (cache_evidence.cache_line_bytes == 0U ||
      !is_power_of_two(cache_evidence.cache_line_bytes) ||
      cache_evidence.smaller_usable_l2_bytes == 0U ||
      cache_evidence.producer_home_usable_llc_bytes == 0U) {
    throw WorkloadSetupError(
        "capacity selection requires explicit nonzero cache facts");
  }
  if (candidates.empty()) {
    throw WorkloadSetupError("capacity selection requires footprint candidates");
  }

  std::set<std::size_t> seen;
  std::optional<SharedFootprintCandidate> selected;
  for (const auto& candidate : candidates) {
    if (!is_power_of_two(candidate.capacity) || candidate.ring_bytes == 0U ||
        candidate.linked_bytes == 0U) {
      throw WorkloadSetupError("every footprint candidate needs a unique power-of-two "
                               "capacity and nonzero bytes");
    }
    if (!seen.insert(candidate.capacity).second) {
      throw WorkloadSetupError("footprint candidate capacities must be unique");
    }
    if (!both_match(candidate, cache_evidence, working_set_class)) {
      continue;
    }
    if (!selected.has_value() ||
        (working_set_class == protocol::WorkingSetClass::beyond_llc
             ? candidate.capacity < selected->capacity
             : candidate.capacity > selected->capacity)) {
      selected = candidate;
    }
  }
  if (!selected.has_value()) {
    throw WorkloadSetupError(
        "no common logical capacity satisfies both queue footprint rules");
  }
  return {working_set_class, *selected};
}

NodeOrderPlan::NodeOrderPlan(const NodeOrderConfig& config,
                             const MasterSeed& master_seed,
                             const std::string& seed_namespace)
    : node_stride_bytes_(config.node_stride_bytes),
      cache_line_bytes_(config.cache_line_bytes),
      base_page_bytes_(config.base_page_bytes) {
  if (!is_power_of_two(config.logical_capacity)) {
    throw WorkloadSetupError("linked logical capacity must be a nonzero power of two");
  }
  if (!is_power_of_two(cache_line_bytes_) || cache_line_bytes_ < sizeof(void*) ||
      node_stride_bytes_ == 0U || node_stride_bytes_ % cache_line_bytes_ != 0U ||
      base_page_bytes_ == 0U || base_page_bytes_ % cache_line_bytes_ != 0U) {
    throw WorkloadSetupError(
        "node stride must contain integral cache lines and page bytes must be "
        "cache-line compatible");
  }
  if (seed_namespace.empty()) {
    throw WorkloadSetupError("node-order seed namespace must not be empty");
  }
  if (config.logical_capacity == std::numeric_limits<std::size_t>::max()) {
    throw WorkloadSetupError("linked node count overflows size_t");
  }
  const DeterministicStream stream(
      derive_stream_key(master_seed, seed_namespace, StreamPurpose::node_order));
  order_ = make_permutation(config.logical_capacity + 1U, stream);
  deltas_ = make_cyclic_address_deltas(order_, node_stride_bytes_);
  ordered_index_checksum_ = ordered_index_sha256(order_);
  address_delta_checksum_ = address_delta_sha256(deltas_);
  summary_ =
      summarize(order_, deltas_, AddressGeometry{node_stride_bytes_, base_page_bytes_});
}

} // namespace cpu_prefetch::workload
