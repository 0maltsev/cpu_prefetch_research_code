#ifndef CPU_PREFETCH_CALIBRATION_MAPPED_DISCOVERY_PREPARATION_HPP
#define CPU_PREFETCH_CALIBRATION_MAPPED_DISCOVERY_PREPARATION_HPP

#include "cpu_prefetch/calibration/caller_owned_trace.hpp"
#include "cpu_prefetch/calibration/discovery_ring_backend.hpp"
#include "cpu_prefetch/platform/owner_mapping.hpp"

#include <memory>

namespace cpu_prefetch::calibration {

using MappedProducerPhase = DiscoveryProducerPhase<CallerOwnedRingDemandTrace>;
using MappedConsumerPhase = DiscoveryConsumerPhase<CallerOwnedRingDemandTrace>;

struct MappedDiscoveryPlan final {
  DiscoverySessionPlan session;
  workload::EventArenaConfig arena;
  std::array<protocol::RunId, 2U> run_ids;
  workload::ConsumerState initial_consumer;
};

namespace mapped_discovery_detail {

struct ProducerObjects final {
  CallerOwnedRingDemandWorker worker;
  storage::ProducerObservationStream stream;
  std::optional<CallerOwnedRingDemandTrace> trace;
  std::optional<MappedProducerPhase> phase;
  ProducerObjects(const protocol::RunId& id, std::span<std::uint64_t> demand,
                  std::span<std::uint64_t> issue, std::span<std::byte> raw)
      : worker(RingWorker::producer, demand, issue), stream(id, demand.size(), raw) {}
};

struct ConsumerObjects final {
  CallerOwnedRingDemandWorker worker;
  storage::ConsumerObservationStream stream;
  std::optional<CallerOwnedRingDemandTrace> trace;
  std::optional<MappedConsumerPhase> phase;
  ConsumerObjects(const protocol::RunId& id, std::span<std::uint64_t> demand,
                  std::span<std::uint64_t> issue, std::span<std::byte> raw)
      : worker(RingWorker::consumer, demand, issue), stream(id, demand.size(), raw) {}
};

// Cold checked layout arithmetic only; no allocation or platform-value default.
struct LayoutBuilder final {
  struct Request final {
    std::size_t size;
    std::size_t alignment;
  };
  std::size_t bytes{0U};
  auto reserve(Request request) -> std::size_t {
    const auto [size, alignment] = request;
    constexpr auto maximum =
        static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max());
    if (alignment == 0U || (alignment & (alignment - 1U)) != 0U ||
        alignment > maximum || bytes > maximum - (alignment - 1U)) {
      throw std::invalid_argument("discovery layout alignment/size overflows");
    }
    const auto offset = (bytes + alignment - 1U) & ~(alignment - 1U);
    if (size > maximum - offset) {
      throw std::invalid_argument("discovery layout extent overflows");
    }
    bytes = offset + size;
    return offset;
  }
  template <typename T>
  auto array(std::size_t count, std::size_t alignment) -> std::size_t {
    if (count > std::numeric_limits<std::size_t>::max() / sizeof(T)) {
      throw std::invalid_argument("discovery array extent overflows");
    }
    return reserve({count * sizeof(T), std::max(alignment, alignof(T))});
  }
};

template <typename T>
auto pointer(std::span<std::byte> bytes, std::size_t offset) noexcept -> T* {
  return reinterpret_cast<T*>(bytes.data() + offset);
}

template <typename T>
auto initialize_array(std::span<std::byte> bytes, std::size_t offset, std::size_t count)
    -> std::span<T> {
  auto* result = ::new (static_cast<void*>(bytes.data() + offset)) T[count]{};
  return {result, count};
}

} // namespace mapped_discovery_detail

struct MappedDiscoveryPhaseLayout final {
  std::size_t count;
  storage::RowLayout row;
  storage::RawStreamStorageRequirements raw;
  std::size_t producer_object;
  std::size_t producer_demand;
  std::size_t producer_issue;
  std::size_t producer_raw;
  std::size_t consumer_object;
  std::size_t consumer_demand;
  std::size_t consumer_issue;
  std::size_t consumer_raw;
  std::size_t drain;
};

struct MappedDiscoveryLayout final {
  std::size_t records_bytes;
  std::size_t producer_bytes;
  std::size_t consumer_bytes;
  std::size_t record_order;
  std::size_t arena_object;
  std::size_t ring_object;
  std::size_t slots;
  std::size_t cursors;
  queue::RingStorageRequirements ring_storage;
  std::array<MappedDiscoveryPhaseLayout, 2U> phases;
};

[[nodiscard]] inline auto mapped_discovery_layout(const MappedDiscoveryPlan& plan)
    -> MappedDiscoveryLayout {
  using namespace mapped_discovery_detail;
  const auto page = plan.arena.base_page_bytes;
  const auto line = plan.arena.cache_line_bytes;
  if (page == 0U || (page & (page - 1U)) != 0U || line == 0U ||
      (line & (line - 1U)) != 0U || line > page ||
      line < storage::kRawBufferAlignment || plan.arena.capacity == 0U ||
      plan.run_ids[0U] == plan.run_ids[1U] ||
      plan.session.warmup_attempt_capacity == 0U ||
      plan.session.measurement_attempt_capacity == 0U ||
      plan.session.drain_attempt_capacity == 0U ||
      plan.session.barrier_poll_limit == 0U) {
    throw std::invalid_argument("invalid mapped discovery plan");
  }
  MappedDiscoveryLayout result{};
  LayoutBuilder records;
  if (plan.arena.capacity > std::numeric_limits<std::size_t>::max() / line) {
    throw std::invalid_argument("discovery records extent overflows");
  }
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
    auto& phase = result.phases[index];
    const auto count = index == 0U ? plan.session.warmup_attempt_capacity
                                   : plan.session.measurement_attempt_capacity;
    if (count > std::numeric_limits<std::size_t>::max() ||
        plan.session.drain_attempt_capacity > std::numeric_limits<std::size_t>::max()) {
      throw std::invalid_argument("discovery counts exceed addressable storage");
    }
    phase.count = static_cast<std::size_t>(count);
    phase.row = storage::make_row_layout(plan.run_ids[index].value());
    phase.raw =
        storage::raw_stream_storage_requirements(plan.run_ids[index], count, count);
    phase.producer_object = producer.array<ProducerObjects>(1U, line);
    phase.producer_demand = producer.array<std::uint64_t>(phase.count, line);
    phase.producer_issue = producer.array<std::uint64_t>(phase.count, line);
    phase.producer_raw = producer.reserve({phase.raw.producer_bytes, line});
    phase.consumer_object = consumer.array<ConsumerObjects>(1U, line);
    phase.consumer_demand = consumer.array<std::uint64_t>(phase.count, line);
    phase.consumer_issue = consumer.array<std::uint64_t>(phase.count, line);
    phase.consumer_raw = consumer.reserve({phase.raw.consumer_bytes, line});
    phase.drain = consumer.array<DiscoveryConsumerEventCapture>(
        static_cast<std::size_t>(plan.session.drain_attempt_capacity), line);
  }
  result.producer_bytes = producer.reserve({0U, page});
  result.consumer_bytes = consumer.reserve({0U, page});
  return result;
}

template <typename Operations> struct MappedDiscoveryRegions final {
  platform::OwnerMapping<Operations>& records;
  platform::OwnerMapping<Operations>& producer;
  platform::OwnerMapping<Operations>& consumer;
};

enum class MappedDiscoveryPreparationStop : std::uint8_t {
  not_started,
  preparing,
  mapping_failure,
  construction_failure,
  protection_failure,
  peer_failure,
  wait_exhausted,
  ready,
};

// Owns typed objects and a frozen plan copy, not mappings. Mappings outlive this
// provider; destroy it only after both workers join, then release mappings. Caller must
// separately place/declare this provider, clock, backend and session context.
// Accepted preparation is not independent residency or execution qualification.
template <typename Operations, typename Relax> class MappedDiscoveryPreparation final {
public:
  MappedDiscoveryPreparation(const MappedDiscoveryPlan& plan,
                             MappedDiscoveryRegions<Operations> regions, Relax& relax)
      : plan_(plan), layout_(mapped_discovery_layout(plan)), regions_(regions),
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
      throw std::invalid_argument(
          "mapped discovery regions do not match layout/owners");
    }
  }
  ~MappedDiscoveryPreparation() {
    for (auto* objects : producer_objects_) {
      if (objects != nullptr) {
        std::destroy_at(objects);
      }
    }
    for (auto* objects : consumer_objects_) {
      if (objects != nullptr) {
        std::destroy_at(objects);
      }
    }
    if (ring_ != nullptr) {
      std::destroy_at(ring_);
    }
    if (arena_ != nullptr) {
      std::destroy_at(arena_);
    }
  }
  MappedDiscoveryPreparation(const MappedDiscoveryPreparation&) = delete;
  auto operator=(const MappedDiscoveryPreparation&)
      -> MappedDiscoveryPreparation& = delete;
  auto prepare_producer() noexcept -> bool { return prepare(0U); }
  auto prepare_consumer() noexcept -> bool { return prepare(1U); }
  auto producer_phase(bool warmup) noexcept -> MappedProducerPhase& {
    return *producer_phases_[warmup ? 0U : 1U];
  }
  auto consumer_phase(bool warmup) noexcept -> MappedConsumerPhase& {
    return *consumer_phases_[warmup ? 0U : 1U];
  }
  auto arena() const noexcept -> const workload::EventArena& { return *arena_; }
  auto ring() noexcept -> queue::RingSpscQueue& { return *ring_; }
  auto layout() const noexcept -> const MappedDiscoveryLayout& { return layout_; }
  auto status(std::size_t worker) const noexcept -> MappedDiscoveryPreparationStop {
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
    const auto data = regions_.records.mapped_bytes();
    const auto memory = regions_.producer.mapped_bytes();
    auto order =
        initialize_array<std::size_t>(data, layout_.record_order, plan_.arena.capacity);
    arena_ = std::construct_at(
        pointer<workload::EventArena>(memory, layout_.arena_object), plan_.arena,
        data.first(plan_.arena.capacity * plan_.arena.cache_line_bytes), order);
    ring_ = std::construct_at(
        pointer<queue::RingSpscQueue>(memory, layout_.ring_object),
        queue::QueueCapacity{plan_.arena.capacity},
        queue::CacheLineBytes{plan_.arena.cache_line_bytes},
        queue::RingStorageView{
            memory.subspan(layout_.slots, layout_.ring_storage.slot_bytes),
            memory.subspan(layout_.cursors, layout_.ring_storage.cursor_bytes)});
    for (std::size_t index = 0U; index < 2U; ++index) {
      const auto& phase = layout_.phases[index];
      producer_objects_[index] = std::construct_at(
          pointer<ProducerObjects>(memory, phase.producer_object), plan_.run_ids[index],
          initialize_array<std::uint64_t>(memory, phase.producer_demand, phase.count),
          initialize_array<std::uint64_t>(memory, phase.producer_issue, phase.count),
          memory.subspan(phase.producer_raw, phase.raw.producer_bytes));
    }
  }
  void construct_consumer() {
    using namespace mapped_discovery_detail;
    const auto memory = regions_.consumer.mapped_bytes();
    for (std::size_t index = 0U; index < 2U; ++index) {
      const auto& phase = layout_.phases[index];
      consumer_objects_[index] = std::construct_at(
          pointer<ConsumerObjects>(memory, phase.consumer_object), plan_.run_ids[index],
          initialize_array<std::uint64_t>(memory, phase.consumer_demand, phase.count),
          initialize_array<std::uint64_t>(memory, phase.consumer_issue, phase.count),
          memory.subspan(phase.consumer_raw, phase.raw.consumer_bytes));
      drain_[index] = initialize_array<DiscoveryConsumerEventCapture>(
          memory, phase.drain,
          static_cast<std::size_t>(plan_.session.drain_attempt_capacity));
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
      for (std::size_t index = 0U; index < 2U; ++index) {
        auto& producer = *producer_objects_[index];
        auto& consumer = *consumer_objects_[index];
        if (role == 0U) {
          auto& trace = producer.trace.emplace(producer.worker, consumer.worker);
          producer_phases_[index] = &producer.phase.emplace(trace, producer.stream,
                                                            layout_.phases[index].row);
        } else {
          auto& trace = consumer.trace.emplace(producer.worker, consumer.worker);
          consumer_phases_[index] =
              &consumer.phase.emplace(trace, consumer.stream, layout_.phases[index].row,
                                      plan_.initial_consumer, drain_[index]);
        }
      }
      if (cancelled_.load(std::memory_order_acquire)) {
        return fail(role, MappedDiscoveryPreparationStop::peer_failure);
      }
      stop_[role].store(MappedDiscoveryPreparationStop::ready,
                        std::memory_order_release);
      return true;
    } catch (...) {
      return fail(role, MappedDiscoveryPreparationStop::construction_failure);
    }
  }
  const MappedDiscoveryPlan plan_;
  MappedDiscoveryLayout layout_;
  MappedDiscoveryRegions<Operations> regions_;
  Relax& relax_;
  std::array<std::atomic<MappedDiscoveryPreparationStop>, 2U> stop_{};
  std::array<std::atomic<bool>, 2U> constructed_{};
  std::atomic<bool> cancelled_{false};
  workload::EventArena* arena_{nullptr};
  queue::RingSpscQueue* ring_{nullptr};
  std::array<mapped_discovery_detail::ProducerObjects*, 2U> producer_objects_{};
  std::array<mapped_discovery_detail::ConsumerObjects*, 2U> consumer_objects_{};
  std::array<MappedProducerPhase*, 2U> producer_phases_{};
  std::array<MappedConsumerPhase*, 2U> consumer_phases_{};
  std::array<std::span<DiscoveryConsumerEventCapture>, 2U> drain_{};
};

} // namespace cpu_prefetch::calibration

#endif
