#ifndef CPU_PREFETCH_CALIBRATION_PILOT_SHARED_DATA_HPP
#define CPU_PREFETCH_CALIBRATION_PILOT_SHARED_DATA_HPP

#include "cpu_prefetch/workload/packages.hpp"
#include "cpu_prefetch/workload/records.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <stdexcept>

namespace cpu_prefetch::calibration {

// No package, hardware-state, or load field: all paired treatments use the
// same six placement/working-set objects for the entire temporal block.
struct PilotContextKey final {
  protocol::Placement placement;
  protocol::WorkingSetClass working_set;
  auto operator==(const PilotContextKey&) const -> bool = default;
};

inline auto pilot_context_index(PilotContextKey key) noexcept
    -> std::optional<std::size_t> {
  std::size_t placement;
  switch (key.placement) {
  case protocol::Placement::near:
    placement = 0U;
    break;
  case protocol::Placement::far:
    placement = 1U;
    break;
  default:
    return std::nullopt;
  }
  std::size_t working;
  switch (key.working_set) {
  case protocol::WorkingSetClass::l2_resident:
    working = 0U;
    break;
  case protocol::WorkingSetClass::llc_resident:
    working = 1U;
    break;
  case protocol::WorkingSetClass::beyond_llc:
    working = 2U;
    break;
  default:
    return std::nullopt;
  }
  return placement * 3U + working;
}

namespace pilot_detail {
struct MemoryRange final {
  std::uintptr_t begin;
  std::uintptr_t end;
};
inline auto memory_range(const void* address, std::size_t size) -> MemoryRange {
  const auto begin = reinterpret_cast<std::uintptr_t>(address);
  if (size == 0U)
    return {begin, begin};
  if (begin == 0U || size > std::numeric_limits<std::uintptr_t>::max() - begin)
    throw std::invalid_argument("pilot storage range is not representable");
  return {begin, begin + size};
}
inline auto overlaps(MemoryRange a, MemoryRange b) noexcept -> bool {
  return a.begin < a.end && b.begin < b.end && a.begin < b.end && b.begin < a.end;
}
} // namespace pilot_detail

struct PilotDataIdentity final {
  const void* arena_object;
  const void* arena_bytes;
  const void* ring_object;
  const void* linked_object;
  const void* node_bytes;
  std::size_t capacity;
  std::size_t cache_line_bytes;
  std::size_t base_page_bytes;
  std::size_t node_stride_bytes;
  auto operator==(const PilotDataIdentity&) const -> bool = default;
};

// Nonowning, caller-placed native data binding. Caller prepares/qualifies the
// actual arena, node permutation, queues, memory homes and mapped lifetimes.
// This class neither allocates nor creates residency/seed/qualification evidence.
// It survives every package, load and H0/H1 capture in its temporal block.
class PilotSharedData final {
public:
  PilotSharedData(PilotContextKey key, workload::EventArena& arena,
                  queue::RingSpscQueue& ring, queue::LinkedSpscQueue& linked)
      : key_(key), arena_(arena), ring_(ring), linked_(linked), identity_(identity()) {
    const auto maximum = std::numeric_limits<std::size_t>::max();
    if (!pilot_context_index(key) || arena.capacity() < 8U ||
        ring.capacity() != arena.capacity() || linked.capacity() != arena.capacity() ||
        linked.node_stride_bytes() != arena.cache_line_bytes() ||
        linked.node_arena_alignment_bytes() != arena.base_page_bytes() ||
        arena.capacity() == maximum ||
        arena.capacity() + 1U > maximum / linked.node_stride_bytes() ||
        pilot_detail::overlaps(arena_range(), node_range())) {
      throw std::invalid_argument("pilot shared data geometry/key is inconsistent");
    }
  }
  PilotSharedData(const PilotSharedData&) = delete;
  auto operator=(const PilotSharedData&) -> PilotSharedData& = delete;
  auto key() const noexcept -> PilotContextKey { return key_; }
  auto arena() const noexcept -> const workload::EventArena& { return arena_; }
  auto ring() noexcept -> queue::RingSpscQueue& { return ring_; }
  auto linked() noexcept -> queue::LinkedSpscQueue& { return linked_; }
  auto identity() const noexcept -> PilotDataIdentity {
    return {&arena_,
            arena_.storage_address(),
            &ring_,
            &linked_,
            linked_.node_arena_base(),
            arena_.capacity(),
            arena_.cache_line_bytes(),
            arena_.base_page_bytes(),
            linked_.node_stride_bytes()};
  }
  auto stable() const noexcept -> bool { return identity() == identity_; }
  auto arena_range() const -> pilot_detail::MemoryRange {
    return pilot_detail::memory_range(arena_.storage_address(),
                                      arena_.allocated_bytes());
  }
  auto node_range() const -> pilot_detail::MemoryRange {
    return pilot_detail::memory_range(linked_.node_arena_base(),
                                      (arena_.capacity() + 1U) *
                                          linked_.node_stride_bytes());
  }

private:
  const PilotContextKey key_;
  workload::EventArena& arena_;
  queue::RingSpscQueue& ring_;
  queue::LinkedSpscQueue& linked_;
  const PilotDataIdentity identity_;
};

// Controller-only registry. The caller retains all six objects and their actual
// mappings until the entire family is quiescent. Rebinding cannot replace data.
class PilotContextRegistry final {
public:
  auto bind(PilotSharedData& data) -> bool {
    const auto index = pilot_context_index(data.key());
    if (!index || !data.stable())
      return false;
    auto*& slot = contexts_[*index];
    if (slot != nullptr)
      return slot == &data;
    for (const auto* prior : contexts_) {
      if (prior != nullptr) {
        const auto a = prior->identity(), b = data.identity();
        if (a.arena_object == b.arena_object || a.arena_bytes == b.arena_bytes ||
            a.ring_object == b.ring_object || a.linked_object == b.linked_object ||
            a.node_bytes == b.node_bytes)
          return false;
        if (pilot_detail::overlaps(prior->arena_range(), data.arena_range()) ||
            pilot_detail::overlaps(prior->arena_range(), data.node_range()) ||
            pilot_detail::overlaps(prior->node_range(), data.arena_range()) ||
            pilot_detail::overlaps(prior->node_range(), data.node_range()))
          return false;
      }
    }
    slot = &data;
    return true;
  }
  auto find(PilotContextKey key) const noexcept -> PilotSharedData* {
    const auto index = pilot_context_index(key);
    return index ? contexts_[*index] : nullptr;
  }
  auto size() const noexcept -> std::size_t {
    return static_cast<std::size_t>(
        std::count_if(contexts_.begin(), contexts_.end(),
                      [](const auto* p) { return p != nullptr; }));
  }
  auto complete() const noexcept -> bool { return size() == contexts_.size(); }

private:
  std::array<PilotSharedData*, 6U> contexts_{};
};
} // namespace cpu_prefetch::calibration
#endif
