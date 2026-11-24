#ifndef CPU_PREFETCH_CALIBRATION_MAPPED_FORMAL_SERVICE_PREPARATION_HPP
#define CPU_PREFETCH_CALIBRATION_MAPPED_FORMAL_SERVICE_PREPARATION_HPP

#include "cpu_prefetch/calibration/formal_service_plan.hpp"
#include "cpu_prefetch/calibration/formal_service_session.hpp"
#include "cpu_prefetch/workload/packages.hpp"

namespace cpu_prefetch::calibration {
namespace formal_service_detail {
struct ProducerObjects final {
  storage::ProducerObservationStream primary;
  FormalServiceProducerPhase phase;
  ProducerObjects(const protocol::RunId& id, std::uint64_t count,
                  std::span<std::byte> bytes)
      : primary(id, count, bytes),
        phase{primary, storage::make_row_layout(id.value())} {}
};
struct ConsumerObjects final {
  storage::ConsumerObservationStream primary;
  FormalServiceConsumerPhase phase;
  ConsumerObjects(const protocol::RunId& id, std::uint64_t count,
                  workload::ConsumerState initial, std::span<std::byte> bytes)
      : primary(id, count, bytes),
        phase{primary, storage::make_row_layout(id.value()), initial, initial} {}
};
template <protocol::QueuePackage Kind, typename Emitter> struct Types final {
  static constexpr bool linked =
      Kind == protocol::QueuePackage::l0 || Kind == protocol::QueuePackage::l1;
  using Queue =
      std::conditional_t<linked, queue::LinkedSpscQueue, queue::RingSpscQueue>;
  using Package = std::conditional_t<
      Kind == protocol::QueuePackage::r0, workload::R0Package,
      std::conditional_t<
          Kind == protocol::QueuePackage::r1, workload::R1Package<Emitter>,
          std::conditional_t<
              Kind == protocol::QueuePackage::r2, workload::R2Package<Emitter>,
              std::conditional_t<Kind == protocol::QueuePackage::l0,
                                 workload::L0Package, workload::L1Package<Emitter>>>>>;
};
} // namespace formal_service_detail
struct MappedFormalServicePhaseLayout final {
  storage::RawStreamStorageRequirements raw;
  std::size_t producer_object;
  std::size_t producer_raw;
  std::size_t consumer_object;
  std::size_t consumer_raw;
};
using FormalScheduleSources = std::array<std::span<const std::uint64_t>, 2U>;
struct MappedFormalServiceLayout final {
  std::size_t records_bytes;
  std::size_t producer_bytes;
  std::size_t consumer_bytes;
  std::size_t record_order;
  std::array<std::size_t, 2U> schedule_offsets;
  std::array<std::size_t, 2U> schedule_counts;
  std::size_t arena_object;
  std::size_t queue_object;
  std::size_t package_object;
  std::size_t emitter_object;
  std::optional<queue::RingStorageRequirements> ring;
  std::size_t slots;
  std::size_t cursors;
  std::optional<queue::LinkedStorageRequirements> linked;
  std::size_t nodes;
  std::size_t recycler;
  std::size_t ownership;
  std::size_t node_input_order;
  std::size_t node_initial_order;
  std::size_t node_validation;
  std::array<MappedFormalServicePhaseLayout, 2U> phases;
};

template <protocol::QueuePackage Kind, typename Emitter>
[[nodiscard]] auto mapped_formal_service_layout(const MappedFormalServicePlan& plan,
                                                FormalScheduleSources schedules = {})
    -> MappedFormalServiceLayout {
  using Types = formal_service_detail::Types<Kind, Emitter>;
  using namespace mapped_discovery_detail;
  const auto page = plan.arena.base_page_bytes;
  const auto line = plan.arena.cache_line_bytes;
  if (plan.package != Kind || !valid_service_plan(plan.session) || page == 0U ||
      (page & (page - 1U)) != 0U || line < storage::kRawBufferAlignment ||
      (line & (line - 1U)) != 0U || line > page || plan.arena.capacity == 0U ||
      plan.arena.capacity > std::numeric_limits<std::size_t>::max() / line ||
      plan.run_ids[0U] == plan.run_ids[1U]) {
    throw std::invalid_argument("invalid mapped service plan/geometry");
  }
  if constexpr (Types::linked) {
    if (!plan.linked_order || plan.linked_order->seed_namespace.empty() ||
        plan.linked_order->arena_alignment_bytes != page || plan.ring_distance) {
      throw std::invalid_argument(
          "linked service requires exact explicit node geometry/seed");
    }
  } else {
    if (plan.linked_order) {
      throw std::invalid_argument("ring service cannot bind linked order");
    }
    if constexpr (Kind == protocol::QueuePackage::r0) {
      if (plan.ring_distance) {
        throw std::invalid_argument("R0 cannot bind a prefetch distance");
      }
    } else {
      if (!plan.ring_distance) {
        throw std::invalid_argument("prefetched ring requires explicit distance");
      }
      const auto& distance = *plan.ring_distance;
      const workload::RingGeometry geometry{
          plan.arena.capacity, line,
          queue::RingSpscQueue::storage_requirements({plan.arena.capacity}, {line})
                  .slot_bytes /
              plan.arena.capacity};
      if constexpr (Kind == protocol::QueuePackage::r1) {
        if (distance.cache_lines != 1U || !distance.calibration_evidence_id.empty()) {
          throw std::invalid_argument(
              "R1 requires registered one-line policy, not calibrated evidence");
        }
        static_cast<void>(workload::ring_one_line_distance(geometry));
      } else {
        static_cast<void>(workload::resolve_calibrated_ring_distance(
            geometry, distance.cache_lines, distance.calibration_evidence_id));
      }
    }
  }
  MappedFormalServiceLayout result{};
  LayoutBuilder records, producer, consumer;
  static_cast<void>(records.reserve({plan.arena.capacity * line, page}));
  result.record_order = records.array<std::size_t>(plan.arena.capacity, line);
  for (std::size_t index = 0U; index < schedules.size(); ++index) {
    const auto source = schedules[index];
    const auto address = reinterpret_cast<std::uintptr_t>(source.data());
    if (source.size() > plan.session.phases[index].producer_attempt_limit ||
        source.size() >
            std::numeric_limits<std::size_t>::max() / sizeof(std::uint64_t) ||
        (!source.empty() &&
         (address == 0U || source.size_bytes() >
                               std::numeric_limits<std::uintptr_t>::max() - address))) {
      throw std::invalid_argument("scheduled storage exceeds explicit finite bounds");
    }
    result.schedule_counts[index] = source.size();
    result.schedule_offsets[index] = records.array<std::uint64_t>(source.size(), line);
  }
  result.records_bytes = records.reserve({0U, page});
  result.arena_object = producer.array<workload::EventArena>(1U, line);
  result.queue_object = producer.array<typename Types::Queue>(1U, line);
  result.package_object = producer.array<typename Types::Package>(1U, line);
  result.emitter_object = producer.array<Emitter>(1U, line);
  if constexpr (Types::linked) {
    result.linked = queue::LinkedSpscQueue::storage_requirements({plan.arena.capacity},
                                                                 {line}, {page});
    const auto required = *result.linked;
    result.nodes = producer.reserve({required.node_bytes, page});
    result.recycler = producer.reserve({required.recycler_bytes, line});
    result.ownership = producer.reserve({required.ownership_bytes, line});
    result.node_input_order = producer.array<std::size_t>(required.order_count, line);
    result.node_initial_order = producer.array<std::size_t>(required.order_count, line);
    result.node_validation = producer.reserve({required.validation_bytes, line});
  } else {
    result.ring =
        queue::RingSpscQueue::storage_requirements({plan.arena.capacity}, {line});
    result.slots = producer.reserve({result.ring->slot_bytes, line});
    result.cursors = producer.reserve({result.ring->cursor_bytes, line});
  }
  for (std::size_t index = 0U; index < 2U; ++index) {
    const auto capacity = plan.capacity[index];
    if (capacity.producer_primary_rows <
            plan.session.phases[index].producer_attempt_limit ||
        capacity.consumer_primary_rows <
            plan.session.phases[index].producer_attempt_limit) {
      throw std::invalid_argument(
          "service primary buffers cannot cover prospective producer bound");
    }
    auto& phase = result.phases[index];
    phase.raw = storage::raw_stream_storage_requirements(
        plan.run_ids[index], capacity.producer_primary_rows,
        capacity.consumer_primary_rows);
    phase.producer_object =
        producer.array<formal_service_detail::ProducerObjects>(1U, line);
    phase.producer_raw = producer.reserve({phase.raw.producer_bytes, line});
    phase.consumer_object =
        consumer.array<formal_service_detail::ConsumerObjects>(1U, line);
    phase.consumer_raw = consumer.reserve({phase.raw.consumer_bytes, line});
  }
  result.producer_bytes = producer.reserve({0U, page});
  result.consumer_bytes = consumer.reserve({0U, page});
  return result;
}

// Queue/package choice is a compile-time type. All measured data, linked node
// recycler/ownership/frozen order and phase buffers live in the declared maps.
// Temporary seed-generation vectors and distance-evidence strings die during
// cold construction; existing primary stream run-ID metadata remains cold.
template <protocol::QueuePackage Kind, typename Emitter, typename Operations,
          typename Relax>
class MappedFormalServicePreparation final {
  using Types = formal_service_detail::Types<Kind, Emitter>;

public:
  using Queue = typename Types::Queue;
  using Package = typename Types::Package;
  MappedFormalServicePreparation(const MappedFormalServicePlan& plan,
                                 MappedDiscoveryRegions<Operations> regions,
                                 Relax& relax, FormalScheduleSources schedules = {})
      : plan_(plan),
        layout_(mapped_formal_service_layout<Kind, Emitter>(plan, schedules)),
        regions_(regions), relax_(relax), schedule_sources_(schedules) {
    const auto record = regions_.records.evidence().requested;
    const auto producer = regions_.producer.evidence().requested;
    const auto consumer = regions_.consumer.evidence().requested;
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
      throw std::invalid_argument("service maps disagree with exact layout/owners");
    }
  }
  ~MappedFormalServicePreparation() {
    for (auto* object : producer_) {
      if (object != nullptr)
        std::destroy_at(object);
    }
    for (auto* object : consumer_) {
      if (object != nullptr)
        std::destroy_at(object);
    }
    if (package_ != nullptr)
      std::destroy_at(package_);
    if (emitter_ != nullptr)
      std::destroy_at(emitter_);
    if (queue_ != nullptr)
      std::destroy_at(queue_);
    if (arena_ != nullptr)
      std::destroy_at(arena_);
  }
  MappedFormalServicePreparation(const MappedFormalServicePreparation&) = delete;
  auto operator=(const MappedFormalServicePreparation&)
      -> MappedFormalServicePreparation& = delete;
  auto prepare_producer() noexcept -> bool { return prepare(0U); }
  auto prepare_consumer() noexcept -> bool { return prepare(1U); }
  auto producer_phase(bool warmup) noexcept -> FormalServiceProducerPhase& {
    return producer_[warmup ? 0U : 1U]->phase;
  }
  auto consumer_phase(bool warmup) noexcept -> FormalServiceConsumerPhase& {
    return consumer_[warmup ? 0U : 1U]->phase;
  }
  auto arena() const noexcept -> const workload::EventArena& { return *arena_; }
  auto queue() noexcept -> Queue& { return *queue_; }
  auto package() noexcept -> Package& { return *package_; }
  auto status(std::size_t worker) const -> MappedDiscoveryPreparationStop {
    return stop_.at(worker).load(std::memory_order_acquire);
  }
  auto emitter() const noexcept -> const Emitter& { return *emitter_; }
  auto node_order() const noexcept -> std::span<const std::size_t> {
    return node_order_;
  }
  auto layout() const noexcept -> const MappedFormalServiceLayout& { return layout_; }
  // Called only after preparation; the parent input is never returned.
  auto schedule_deadlines(std::size_t phase) const noexcept
      -> std::span<const std::uint64_t> {
    return mapped_schedules_[phase];
  }

private:
  template <typename T>
  static auto required_storage(const std::optional<T>& value) -> const T& {
    if (!value.has_value()) {
      throw std::logic_error("checked formal package storage is absent");
    }
    return *value;
  }
  auto fail(std::size_t role, MappedDiscoveryPreparationStop reason) noexcept -> bool {
    stop_[role].store(reason, std::memory_order_release);
    cancelled_.store(true, std::memory_order_release);
    return false;
  }
  auto wait_for_peer(std::size_t role) noexcept -> bool {
    for (std::uint64_t poll = 0U; poll < plan_.session.barrier_poll_limit; ++poll) {
      if (cancelled_.load(std::memory_order_acquire))
        return fail(role, MappedDiscoveryPreparationStop::peer_failure);
      if (constructed_[1U - role].load(std::memory_order_acquire))
        return true;
      relax_.relax();
    }
    return fail(role, MappedDiscoveryPreparationStop::wait_exhausted);
  }
  void construct_producer() {
    using namespace mapped_discovery_detail;
    const auto records = regions_.records.mapped_bytes();
    const auto bytes = regions_.producer.mapped_bytes();
    for (std::size_t index = 0U; index < schedule_sources_.size(); ++index) {
      auto output = initialize_array<std::uint64_t>(
          records, layout_.schedule_offsets[index], layout_.schedule_counts[index]);
      std::copy(schedule_sources_[index].begin(), schedule_sources_[index].end(),
                output.begin());
      mapped_schedules_[index] = output;
    }
    auto record_order = initialize_array<std::size_t>(records, layout_.record_order,
                                                      plan_.arena.capacity);
    arena_ = std::construct_at(
        pointer<workload::EventArena>(bytes, layout_.arena_object), plan_.arena,
        records.first(plan_.arena.capacity * plan_.arena.cache_line_bytes),
        record_order);
    if constexpr (Types::linked) {
      const auto required = required_storage(layout_.linked);
      auto order = initialize_array<std::size_t>(bytes, layout_.node_input_order,
                                                 required.order_count);
      const auto& bound = required_storage(plan_.linked_order);
      { // Existing deterministic generator only; release temporary heap scratch now.
        const workload::DeterministicStream stream(
            workload::derive_stream_key(bound.master_seed, bound.seed_namespace,
                                        workload::StreamPurpose::node_order));
        const auto temporary = workload::make_permutation(required.order_count, stream);
        std::copy(temporary.begin(), temporary.end(), order.begin());
      }
      auto initial = initialize_array<std::size_t>(bytes, layout_.node_initial_order,
                                                   required.order_count);
      queue_ = std::construct_at(
          pointer<Queue>(bytes, layout_.queue_object),
          queue::QueueCapacity{plan_.arena.capacity},
          queue::CacheLineBytes{plan_.arena.cache_line_bytes},
          queue::ArenaAlignmentBytes{bound.arena_alignment_bytes},
          std::span<const std::size_t>(order),
          queue::LinkedStorageView{
              bytes.subspan(layout_.nodes, required.node_bytes),
              bytes.subspan(layout_.recycler, required.recycler_bytes),
              bytes.subspan(layout_.ownership, required.ownership_bytes), initial,
              bytes.subspan(layout_.node_validation, required.validation_bytes)});
      node_order_ = initial;
    } else {
      const auto required = required_storage(layout_.ring);
      queue_ =
          std::construct_at(pointer<Queue>(bytes, layout_.queue_object),
                            queue::QueueCapacity{plan_.arena.capacity},
                            queue::CacheLineBytes{plan_.arena.cache_line_bytes},
                            queue::RingStorageView{
                                bytes.subspan(layout_.slots, required.slot_bytes),
                                bytes.subspan(layout_.cursors, required.cursor_bytes)});
    }
    emitter_ = std::construct_at(pointer<Emitter>(bytes, layout_.emitter_object));
    if constexpr (Kind == protocol::QueuePackage::r0 ||
                  Kind == protocol::QueuePackage::l0) {
      package_ =
          std::construct_at(pointer<Package>(bytes, layout_.package_object), *queue_);
    } else if constexpr (Kind == protocol::QueuePackage::l1) {
      package_ = std::construct_at(pointer<Package>(bytes, layout_.package_object),
                                   *queue_, *emitter_);
    } else {
      const workload::RingGeometry geometry{
          plan_.arena.capacity, plan_.arena.cache_line_bytes,
          required_storage(layout_.ring).slot_bytes / plan_.arena.capacity};
      if constexpr (Kind == protocol::QueuePackage::r1) {
        package_ =
            std::construct_at(pointer<Package>(bytes, layout_.package_object), *queue_,
                              *emitter_, workload::ring_one_line_distance(geometry));
      } else {
        const auto& bound = required_storage(plan_.ring_distance);
        const auto distance = workload::resolve_calibrated_ring_distance(
            geometry, bound.cache_lines, bound.calibration_evidence_id);
        package_ = std::construct_at(pointer<Package>(bytes, layout_.package_object),
                                     *queue_, *emitter_, distance);
      }
    }
    for (std::size_t index = 0U; index < 2U; ++index) {
      const auto phase = layout_.phases[index];
      producer_[index] = std::construct_at(
          pointer<formal_service_detail::ProducerObjects>(bytes, phase.producer_object),
          plan_.run_ids[index], plan_.capacity[index].producer_primary_rows,
          bytes.subspan(phase.producer_raw, phase.raw.producer_bytes));
    }
  }
  void construct_consumer() {
    using namespace mapped_discovery_detail;
    const auto bytes = regions_.consumer.mapped_bytes();
    for (std::size_t index = 0U; index < 2U; ++index) {
      const auto phase = layout_.phases[index];
      consumer_[index] = std::construct_at(
          pointer<formal_service_detail::ConsumerObjects>(bytes, phase.consumer_object),
          plan_.run_ids[index], plan_.capacity[index].consumer_primary_rows,
          plan_.initial_consumer,
          bytes.subspan(phase.consumer_raw, phase.raw.consumer_bytes));
    }
  }
  auto prepare(std::size_t role) noexcept -> bool {
    auto expected = MappedDiscoveryPreparationStop::not_started;
    if (!stop_[role].compare_exchange_strong(
            expected, MappedDiscoveryPreparationStop::preparing)) {
      cancelled_.store(true, std::memory_order_release);
      return false;
    }
    try {
      if (role == 0U) {
        if (!regions_.records.prepare() || !regions_.producer.prepare())
          return fail(role, MappedDiscoveryPreparationStop::mapping_failure);
        construct_producer();
        if (!regions_.records.protect_read_only())
          return fail(role, MappedDiscoveryPreparationStop::protection_failure);
      } else {
        if (!regions_.consumer.prepare())
          return fail(role, MappedDiscoveryPreparationStop::mapping_failure);
        construct_consumer();
      }
      constructed_[role].store(true, std::memory_order_release);
      if (!wait_for_peer(role))
        return false;
      stop_[role].store(MappedDiscoveryPreparationStop::ready,
                        std::memory_order_release);
      return true;
    } catch (...) {
      return fail(role, MappedDiscoveryPreparationStop::construction_failure);
    }
  }
  const MappedFormalServicePlan& plan_;
  MappedFormalServiceLayout layout_;
  MappedDiscoveryRegions<Operations> regions_;
  Relax& relax_;
  FormalScheduleSources schedule_sources_;
  FormalScheduleSources mapped_schedules_{};
  std::array<std::atomic<MappedDiscoveryPreparationStop>, 2U> stop_{};
  std::array<std::atomic<bool>, 2U> constructed_{};
  std::atomic<bool> cancelled_{false};
  workload::EventArena* arena_{nullptr};
  Queue* queue_{nullptr};
  Emitter* emitter_{nullptr};
  Package* package_{nullptr};
  std::span<const std::size_t> node_order_{};
  std::array<formal_service_detail::ProducerObjects*, 2U> producer_{};
  std::array<formal_service_detail::ConsumerObjects*, 2U> consumer_{};
};
} // namespace cpu_prefetch::calibration
#endif
