#ifndef CPU_PREFETCH_CALIBRATION_MAPPED_PILOT_DATA_HPP
#define CPU_PREFETCH_CALIBRATION_MAPPED_PILOT_DATA_HPP

#include "cpu_prefetch/calibration/discovery_residency_observer.hpp"
#include "cpu_prefetch/calibration/formal_service_plan.hpp"
#include "cpu_prefetch/calibration/mapped_discovery_preparation.hpp"
#include "cpu_prefetch/calibration/pilot_shared_data.hpp"
#include "cpu_prefetch/workload/working_set.hpp"

namespace cpu_prefetch::calibration {
struct MappedPilotDataPlan final {
  PilotContextKey key;
  workload::EventArenaConfig arena;
  FormalLinkedOrderPlan node_order;
  std::uint32_t producer_cpu;
  std::uint32_t shared_node;
};
struct MappedPilotDataLayout final {
  std::size_t records_bytes, queues_bytes;
  std::size_t record_order, arena_object, ring_object, linked_object, data_object;
  std::size_t ring_slots, ring_cursors, nodes, recycler, ownership;
  std::size_t node_input, node_initial, node_validation;
  queue::RingStorageRequirements ring;
  queue::LinkedStorageRequirements linked;
};
inline auto mapped_pilot_data_layout(const MappedPilotDataPlan& plan)
    -> MappedPilotDataLayout {
  const auto& a = plan.arena;
  const auto page = a.base_page_bytes, line = a.cache_line_bytes;
  if (!pilot_context_index(plan.key) || a.capacity < 8U || page == 0U ||
      (page & (page - 1U)) != 0U || line < storage::kRawBufferAlignment ||
      (line & (line - 1U)) != 0U || line > page ||
      a.capacity > std::numeric_limits<std::size_t>::max() / line ||
      a.seed_namespace.empty() || plan.node_order.seed_namespace.empty() ||
      a.seed_namespace == plan.node_order.seed_namespace ||
      plan.node_order.arena_alignment_bytes != page ||
      plan.shared_node >= std::numeric_limits<unsigned long>::digits)
    throw std::invalid_argument("mapped pilot shared geometry/seed is invalid");
  MappedPilotDataLayout out{};
  out.ring = queue::RingSpscQueue::storage_requirements({a.capacity}, {line});
  out.linked =
      queue::LinkedSpscQueue::storage_requirements({a.capacity}, {line}, {page});
  mapped_discovery_detail::LayoutBuilder records, queues;
  static_cast<void>(records.reserve({a.capacity * line, page}));
  out.record_order = records.array<std::size_t>(a.capacity, line);
  out.records_bytes = records.reserve({0U, page});
  out.arena_object = queues.array<workload::EventArena>(1U, line);
  out.ring_object = queues.array<queue::RingSpscQueue>(1U, line);
  out.linked_object = queues.array<queue::LinkedSpscQueue>(1U, line);
  out.data_object = queues.array<PilotSharedData>(1U, line);
  out.ring_slots = queues.reserve({out.ring.slot_bytes, line});
  out.ring_cursors = queues.reserve({out.ring.cursor_bytes, line});
  out.nodes = queues.reserve({out.linked.node_bytes, page});
  out.recycler = queues.reserve({out.linked.recycler_bytes, line});
  out.ownership = queues.reserve({out.linked.ownership_bytes, line});
  out.node_input = queues.array<std::size_t>(out.linked.order_count, line);
  out.node_initial = queues.array<std::size_t>(out.linked.order_count, line);
  out.node_validation = queues.reserve({out.linked.validation_bytes, line});
  out.queues_bytes = queues.reserve({0U, page});
  return out;
}

struct PreparedPilotDataView final {
  PilotSharedData* data;
  const MappedPilotDataPlan* plan;
  std::array<DiscoveryResidencyRegion, 2U> regions;
  std::array<const platform::OwnerMappingEvidence*, 2U> mappings;
  std::span<const std::size_t> node_order;
  workload::AddressPatternSummary node_pattern;
};

// Entire-family ownership. Prepare on the explicit producer owner before any
// capture, retain both mappings across all paired runs, release only after the
// family is quiescent. Preparation does not imply address-pattern admission.
template <typename Operations = platform::LinuxOwnerMemoryOperations>
class MappedPilotData final {
public:
  explicit MappedPilotData(MappedPilotDataPlan plan)
      : plan_(std::move(plan)), layout_(mapped_pilot_data_layout(plan_)),
        records_({layout_.records_bytes, plan_.arena.base_page_bytes,
                  plan_.producer_cpu, plan_.shared_node},
                 operations_[0U]),
        queues_({layout_.queues_bytes, plan_.arena.base_page_bytes, plan_.producer_cpu,
                 plan_.shared_node},
                operations_[1U]) {}
  MappedPilotData(const MappedPilotData&) = delete;
  auto operator=(const MappedPilotData&) -> MappedPilotData& = delete;
  ~MappedPilotData() { static_cast<void>(release()); }
  auto prepare() noexcept -> bool {
    if (claimed_ || released_)
      return false;
    claimed_ = true;
    try {
      if (!records_.prepare() || !queues_.prepare())
        return false;
      using namespace mapped_discovery_detail;
      const auto r = records_.mapped_bytes(), q = queues_.mapped_bytes();
      const auto& a = plan_.arena;
      auto record_order =
          initialize_array<std::size_t>(r, layout_.record_order, a.capacity);
      arena_ =
          std::construct_at(pointer<workload::EventArena>(q, layout_.arena_object), a,
                            r.first(a.capacity * a.cache_line_bytes), record_order);
      ring_ = std::construct_at(
          pointer<queue::RingSpscQueue>(q, layout_.ring_object),
          queue::QueueCapacity{a.capacity}, queue::CacheLineBytes{a.cache_line_bytes},
          queue::RingStorageView{
              q.subspan(layout_.ring_slots, layout_.ring.slot_bytes),
              q.subspan(layout_.ring_cursors, layout_.ring.cursor_bytes)});
      auto input = initialize_array<std::size_t>(q, layout_.node_input,
                                                 layout_.linked.order_count);
      {
        const workload::NodeOrderPlan generated(
            {a.capacity, a.cache_line_bytes, a.cache_line_bytes, a.base_page_bytes},
            plan_.node_order.master_seed, plan_.node_order.seed_namespace);
        std::copy(generated.order().begin(), generated.order().end(), input.begin());
        pattern_ = generated.summary();
      }
      auto initial = initialize_array<std::size_t>(q, layout_.node_initial,
                                                   layout_.linked.order_count);
      linked_ = std::construct_at(
          pointer<queue::LinkedSpscQueue>(q, layout_.linked_object),
          queue::QueueCapacity{a.capacity}, queue::CacheLineBytes{a.cache_line_bytes},
          queue::ArenaAlignmentBytes{a.base_page_bytes},
          std::span<const std::size_t>(input),
          queue::LinkedStorageView{
              q.subspan(layout_.nodes, layout_.linked.node_bytes),
              q.subspan(layout_.recycler, layout_.linked.recycler_bytes),
              q.subspan(layout_.ownership, layout_.linked.ownership_bytes), initial,
              q.subspan(layout_.node_validation, layout_.linked.validation_bytes)});
      data_ = std::construct_at(pointer<PilotSharedData>(q, layout_.data_object),
                                plan_.key, *arena_, *ring_, *linked_);
      node_order_ = initial;
      ready_ = records_.protect_read_only();
      return ready_;
    } catch (...) {
      return false;
    }
  }
  auto view() const -> PreparedPilotDataView {
    if (!ready_ || released_ || !data_->stable())
      throw std::logic_error("mapped pilot data is not prepared/live");
    return {data_,
            &plan_,
            {{{records_.mapped_bytes(), plan_.shared_node},
              {queues_.mapped_bytes(), plan_.shared_node}}},
            {&records_.evidence(), &queues_.evidence()},
            node_order_,
            pattern_};
  }
  auto release() noexcept -> bool {
    if (!released_) {
      released_ = true;
      ready_ = false;
      if (data_) {
        std::destroy_at(data_);
        data_ = nullptr;
      }
      if (linked_) {
        std::destroy_at(linked_);
        linked_ = nullptr;
      }
      if (ring_) {
        std::destroy_at(ring_);
        ring_ = nullptr;
      }
      if (arena_) {
        std::destroy_at(arena_);
        arena_ = nullptr;
      }
    }
    const bool q = queues_.release(), r = records_.release();
    return q && r;
  }
  auto records_evidence() const noexcept -> const platform::OwnerMappingEvidence& {
    return records_.evidence();
  }
  auto queues_evidence() const noexcept -> const platform::OwnerMappingEvidence& {
    return queues_.evidence();
  }
  auto operations(std::size_t i) -> Operations& { return operations_.at(i); }
  auto layout() const noexcept -> const MappedPilotDataLayout& { return layout_; }

private:
  const MappedPilotDataPlan plan_;
  const MappedPilotDataLayout layout_;
  std::array<Operations, 2U> operations_;
  platform::OwnerMapping<Operations> records_, queues_;
  workload::EventArena* arena_{nullptr};
  queue::RingSpscQueue* ring_{nullptr};
  queue::LinkedSpscQueue* linked_{nullptr};
  PilotSharedData* data_{nullptr};
  std::span<const std::size_t> node_order_;
  workload::AddressPatternSummary pattern_{};
  bool claimed_{false}, ready_{false}, released_{false};
};
} // namespace cpu_prefetch::calibration
#endif
