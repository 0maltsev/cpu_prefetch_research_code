#ifndef CPU_PREFETCH_CALIBRATION_MAPPED_FORMAL_RING_PREPARATION_HPP
#define CPU_PREFETCH_CALIBRATION_MAPPED_FORMAL_RING_PREPARATION_HPP

#include "cpu_prefetch/calibration/formal_ring_session.hpp"
#include "cpu_prefetch/calibration/native_capture_plan.hpp"

namespace cpu_prefetch::calibration {
namespace formal_ring_detail {
struct PhaseBuffers final {
  std::span<std::byte> demand;
  std::span<std::byte> primary;
};
struct ProducerObjects final {
  storage::ProducerObservationStream primary;
  RingDemandStream demand;
  FormalRingProducerPhase phase;
  ProducerObjects(const protocol::RunId& id, FormalRingPhaseCapacity capacity,
                  PhaseBuffers buffers)
      : primary(id, capacity.producer_primary_rows, buffers.primary),
        demand(id, RingWorker::producer, capacity.producer_demand_rows, buffers.demand),
        phase{demand, primary, storage::make_row_layout(id.value()), {}} {}
};
struct ConsumerObjects final {
  storage::ConsumerObservationStream primary;
  RingDemandStream demand;
  FormalRingConsumerPhase phase;
  ConsumerObjects(const protocol::RunId& id, FormalRingPhaseCapacity capacity,
                  workload::ConsumerState initial, PhaseBuffers buffers)
      : primary(id, capacity.consumer_primary_rows, buffers.primary),
        demand(id, RingWorker::consumer, capacity.consumer_demand_rows, buffers.demand),
        phase{demand,  primary, storage::make_row_layout(id.value()),
              initial, initial, {}} {}
};
} // namespace formal_ring_detail

struct MappedFormalRingPhaseLayout final {
  storage::RawStreamStorageRequirements primary;
  std::size_t producer_object;
  std::size_t producer_demand;
  std::size_t producer_demand_bytes;
  std::size_t producer_raw;
  std::size_t consumer_object;
  std::size_t consumer_demand;
  std::size_t consumer_demand_bytes;
  std::size_t consumer_raw;
};
struct MappedFormalRingLayout final {
  std::size_t records_bytes;
  std::size_t producer_bytes;
  std::size_t consumer_bytes;
  std::size_t record_order;
  std::size_t arena_object;
  std::size_t ring_object;
  std::size_t slots;
  std::size_t cursors;
  queue::RingStorageRequirements ring_storage;
  std::array<MappedFormalRingPhaseLayout, 2U> phases;
};

[[nodiscard]] inline auto mapped_formal_ring_layout(const MappedFormalRingPlan& plan)
    -> MappedFormalRingLayout {
  using namespace mapped_discovery_detail;
  const auto page = plan.arena.base_page_bytes;
  const auto line = plan.arena.cache_line_bytes;
  if (!valid_service_plan(plan.session) || page == 0U || (page & (page - 1U)) != 0U ||
      line == 0U || (line & (line - 1U)) != 0U || line > page ||
      line < storage::kRawBufferAlignment || plan.arena.capacity == 0U ||
      plan.arena.capacity > std::numeric_limits<std::size_t>::max() / line ||
      plan.run_ids[0U] == plan.run_ids[1U]) {
    throw std::invalid_argument("invalid mapped formal ring geometry");
  }
  MappedFormalRingLayout result{};
  LayoutBuilder records;
  static_cast<void>(records.reserve({plan.arena.capacity * line, page}));
  result.record_order = records.array<std::size_t>(plan.arena.capacity, line);
  result.records_bytes = records.reserve({0U, page});
  LayoutBuilder producer;
  LayoutBuilder consumer;
  result.arena_object = producer.array<workload::EventArena>(1U, line);
  result.ring_object = producer.array<queue::RingSpscQueue>(1U, line);
  result.ring_storage =
      queue::RingSpscQueue::storage_requirements({plan.arena.capacity}, {line});
  result.slots = producer.reserve({result.ring_storage.slot_bytes, line});
  result.cursors = producer.reserve({result.ring_storage.cursor_bytes, line});
  for (std::size_t index = 0U; index < 2U; ++index) {
    const auto capacity = plan.capacity[index];
    const auto limits = plan.session.phases[index];
    if (capacity.producer_primary_rows < limits.producer_attempt_limit ||
        capacity.consumer_primary_rows < limits.producer_attempt_limit ||
        capacity.producer_demand_rows < limits.producer_attempt_limit ||
        capacity.consumer_demand_rows < limits.consumer_poll_limit) {
      throw std::invalid_argument(
          "formal buffers do not cover prospective phase bounds");
    }
    auto& phase = result.phases[index];
    phase.primary = storage::raw_stream_storage_requirements(
        plan.run_ids[index], capacity.producer_primary_rows,
        capacity.consumer_primary_rows);
    phase.producer_object =
        producer.array<formal_ring_detail::ProducerObjects>(1U, line);
    phase.producer_demand_bytes = ring_demand_storage_requirements(
        plan.run_ids[index], capacity.producer_demand_rows);
    phase.producer_demand = producer.reserve({phase.producer_demand_bytes, line});
    phase.producer_raw = producer.reserve({phase.primary.producer_bytes, line});
    phase.consumer_object =
        consumer.array<formal_ring_detail::ConsumerObjects>(1U, line);
    phase.consumer_demand_bytes = ring_demand_storage_requirements(
        plan.run_ids[index], capacity.consumer_demand_rows);
    phase.consumer_demand = consumer.reserve({phase.consumer_demand_bytes, line});
    phase.consumer_raw = consumer.reserve({phase.primary.consumer_bytes, line});
  }
  result.producer_bytes = producer.reserve({0U, page});
  result.consumer_bytes = consumer.reserve({0U, page});
  return result;
}

// Typed R0 storage policy. Owns typed object lifetimes, not mappings. All objects
// and raw buffers are constructed on their actual owner before warmup. The
// immutable record map is read-only before the readiness handshake completes.
// No reconstruction, allocation, permutation or checksum reinitialization at reset.
template <typename Operations, typename Relax> class MappedFormalRingPreparation final {
public:
  MappedFormalRingPreparation(const MappedFormalRingPlan& plan,
                              MappedDiscoveryRegions<Operations> regions, Relax& relax)
      : plan_(plan), layout_(mapped_formal_ring_layout(plan)), regions_(regions),
        relax_(relax) {
    const auto& record = regions_.records.evidence().requested;
    const auto& producer = regions_.producer.evidence().requested;
    const auto& consumer = regions_.consumer.evidence().requested;
    if (&regions_.records == &regions_.producer ||
        &regions_.records == &regions_.consumer ||
        &regions_.producer == &regions_.consumer ||
        record.bytes != layout_.records_bytes ||
        producer.bytes != layout_.producer_bytes ||
        consumer.bytes != layout_.consumer_bytes ||
        record.verified_base_page_bytes != plan_.arena.base_page_bytes ||
        producer.verified_base_page_bytes != plan_.arena.base_page_bytes ||
        consumer.verified_base_page_bytes != plan_.arena.base_page_bytes ||
        record.owner_cpu != producer.owner_cpu ||
        record.requested_node != producer.requested_node) {
      throw std::invalid_argument("formal maps disagree with declared owners/layout");
    }
  }
  ~MappedFormalRingPreparation() {
    for (auto* object : producer_) {
      if (object != nullptr) {
        std::destroy_at(object);
      }
    }
    for (auto* object : consumer_) {
      if (object != nullptr) {
        std::destroy_at(object);
      }
    }
    if (ring_ != nullptr) {
      std::destroy_at(ring_);
    }
    if (arena_ != nullptr) {
      std::destroy_at(arena_);
    }
  }
  MappedFormalRingPreparation(const MappedFormalRingPreparation&) = delete;
  auto operator=(const MappedFormalRingPreparation&)
      -> MappedFormalRingPreparation& = delete;
  auto prepare_producer() noexcept -> bool { return prepare(0U); }
  auto prepare_consumer() noexcept -> bool { return prepare(1U); }
  auto producer_phase(bool warmup) noexcept -> FormalRingProducerPhase& {
    return producer_[warmup ? 0U : 1U]->phase;
  }
  auto consumer_phase(bool warmup) noexcept -> FormalRingConsumerPhase& {
    return consumer_[warmup ? 0U : 1U]->phase;
  }
  auto arena() const noexcept -> const workload::EventArena& { return *arena_; }
  auto ring() noexcept -> queue::RingSpscQueue& { return *ring_; }
  auto status(std::size_t worker) const -> MappedDiscoveryPreparationStop {
    return stop_.at(worker).load(std::memory_order_acquire);
  }

private:
  auto fail(std::size_t role, MappedDiscoveryPreparationStop reason) noexcept -> bool {
    stop_[role].store(reason, std::memory_order_release);
    cancelled_.store(true, std::memory_order_release);
    return false;
  }
  auto wait_for_peer(std::size_t role) noexcept -> bool {
    for (std::uint64_t poll = 0U; poll < plan_.session.barrier_poll_limit; ++poll) {
      if (cancelled_.load(std::memory_order_acquire)) {
        return fail(role, MappedDiscoveryPreparationStop::peer_failure);
      }
      if (constructed_[1U - role].load(std::memory_order_acquire)) {
        return true;
      }
      relax_.relax();
    }
    return fail(role, MappedDiscoveryPreparationStop::wait_exhausted);
  }
  void construct_producer() {
    using namespace mapped_discovery_detail;
    const auto records = regions_.records.mapped_bytes();
    const auto bytes = regions_.producer.mapped_bytes();
    auto order = initialize_array<std::size_t>(records, layout_.record_order,
                                               plan_.arena.capacity);
    arena_ = std::construct_at(
        pointer<workload::EventArena>(bytes, layout_.arena_object), plan_.arena,
        records.first(plan_.arena.capacity * plan_.arena.cache_line_bytes), order);
    ring_ = std::construct_at(
        pointer<queue::RingSpscQueue>(bytes, layout_.ring_object),
        queue::QueueCapacity{plan_.arena.capacity},
        queue::CacheLineBytes{plan_.arena.cache_line_bytes},
        queue::RingStorageView{
            bytes.subspan(layout_.slots, layout_.ring_storage.slot_bytes),
            bytes.subspan(layout_.cursors, layout_.ring_storage.cursor_bytes)});
    for (std::size_t index = 0U; index < 2U; ++index) {
      const auto& phase = layout_.phases[index];
      producer_[index] = std::construct_at(
          pointer<formal_ring_detail::ProducerObjects>(bytes, phase.producer_object),
          plan_.run_ids[index], plan_.capacity[index],
          formal_ring_detail::PhaseBuffers{
              bytes.subspan(phase.producer_demand, phase.producer_demand_bytes),
              bytes.subspan(phase.producer_raw, phase.primary.producer_bytes)});
    }
  }
  void construct_consumer() {
    using namespace mapped_discovery_detail;
    const auto bytes = regions_.consumer.mapped_bytes();
    for (std::size_t index = 0U; index < 2U; ++index) {
      const auto& phase = layout_.phases[index];
      consumer_[index] = std::construct_at(
          pointer<formal_ring_detail::ConsumerObjects>(bytes, phase.consumer_object),
          plan_.run_ids[index], plan_.capacity[index], plan_.initial_consumer,
          formal_ring_detail::PhaseBuffers{
              bytes.subspan(phase.consumer_demand, phase.consumer_demand_bytes),
              bytes.subspan(phase.consumer_raw, phase.primary.consumer_bytes)});
    }
  }
  auto prepare(std::size_t role) noexcept -> bool {
    auto expected = MappedDiscoveryPreparationStop::not_started;
    if (!stop_[role].compare_exchange_strong(
            expected, MappedDiscoveryPreparationStop::preparing)) {
      cancelled_.store(true, std::memory_order_release);
      return false;
    }
    if (cancelled_.load(std::memory_order_acquire)) {
      return fail(role, MappedDiscoveryPreparationStop::peer_failure);
    }
    try {
      if (role == 0U) {
        if (!regions_.records.prepare() || !regions_.producer.prepare()) {
          return fail(role, MappedDiscoveryPreparationStop::mapping_failure);
        }
        construct_producer();
        if (!regions_.records.protect_read_only()) {
          return fail(role, MappedDiscoveryPreparationStop::protection_failure);
        }
      } else {
        if (!regions_.consumer.prepare()) {
          return fail(role, MappedDiscoveryPreparationStop::mapping_failure);
        }
        construct_consumer();
      }
      constructed_[role].store(true, std::memory_order_release);
      if (!wait_for_peer(role)) {
        return false;
      }
      stop_[role].store(MappedDiscoveryPreparationStop::ready,
                        std::memory_order_release);
      return true;
    } catch (...) {
      return fail(role, MappedDiscoveryPreparationStop::construction_failure);
    }
  }
  const MappedFormalRingPlan& plan_;
  MappedFormalRingLayout layout_;
  MappedDiscoveryRegions<Operations> regions_;
  Relax& relax_;
  std::array<std::atomic<MappedDiscoveryPreparationStop>, 2U> stop_{};
  std::array<std::atomic<bool>, 2U> constructed_{};
  std::atomic<bool> cancelled_{false};
  workload::EventArena* arena_{nullptr};
  queue::RingSpscQueue* ring_{nullptr};
  std::array<formal_ring_detail::ProducerObjects*, 2U> producer_{};
  std::array<formal_ring_detail::ConsumerObjects*, 2U> consumer_{};
};
} // namespace cpu_prefetch::calibration
#endif
