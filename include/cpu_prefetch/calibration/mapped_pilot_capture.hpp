#ifndef CPU_PREFETCH_CALIBRATION_MAPPED_PILOT_CAPTURE_HPP
#define CPU_PREFETCH_CALIBRATION_MAPPED_PILOT_CAPTURE_HPP

#include "cpu_prefetch/calibration/mapped_formal_scheduled_runtime.hpp"
#include "cpu_prefetch/calibration/mapped_pilot_data.hpp"
#include "cpu_prefetch/calibration/pilot_scheduled_capture.hpp"

namespace cpu_prefetch::calibration {
struct MappedPilotCapturePlan final {
  MappedFormalScheduledPlan scheduled;
  PreparedPilotDataView shared;
};
struct PilotPrivateLayout final {
  std::size_t records_bytes, producer_bytes, consumer_bytes;
  std::array<std::size_t, 2U> schedule_offsets;
  std::array<MappedFormalServicePhaseLayout, 2U> phases;
  std::size_t emitter_object, package_object;
};
struct PilotLifecycleResult final {
  ScheduledSessionResult session;
  bool initial_queue_reset;
};
inline void validate_pilot_shared_view(const MappedPilotCapturePlan& plan) {
  const auto& v = plan.shared;
  const auto& service = plan.scheduled.service;
  if (!v.data || !v.plan || !v.mappings[0U] || !v.mappings[1U])
    throw std::invalid_argument("pilot shared view is incomplete");
  for (std::size_t i = 0U; i < 2U; ++i) {
    const auto& e = *v.mappings[i];
    if (e.stop != platform::OwnerMappingStop::ready || e.cleanup_attempted ||
        !e.mapping || e.mapping->address != v.regions[i].mapping.data() ||
        e.requested.bytes != v.regions[i].mapping.size() ||
        e.requested.owner_cpu != v.plan->producer_cpu ||
        e.requested.requested_node != v.plan->shared_node ||
        v.regions[i].expected_node != v.plan->shared_node ||
        e.requested.verified_base_page_bytes != service.arena.base_page_bytes)
      throw std::invalid_argument("pilot persistent mapping is not prepared/live");
  }
  const auto expected = mapped_pilot_data_layout(*v.plan);
  const auto records = v.regions[0U].mapping, queues = v.regions[1U].mapping;
  if (records.size() != expected.records_bytes ||
      queues.size() != expected.queues_bytes ||
      pilot_detail::overlaps(
          pilot_detail::memory_range(records.data(), records.size()),
          pilot_detail::memory_range(queues.data(), queues.size())) ||
      static_cast<const void*>(v.data) != queues.data() + expected.data_object ||
      v.node_order.data() !=
          reinterpret_cast<const std::size_t*>(queues.data() + expected.node_initial) ||
      v.node_order.size() != expected.linked.order_count)
    throw std::invalid_argument("pilot persistent view differs from mapped layout");
  const auto identity = v.data->identity();
  if (identity.arena_bytes != records.data() ||
      identity.arena_object != queues.data() + expected.arena_object ||
      identity.ring_object != queues.data() + expected.ring_object ||
      identity.linked_object != queues.data() + expected.linked_object ||
      identity.node_bytes != queues.data() + expected.nodes)
    throw std::invalid_argument("pilot shared objects escape their observed mappings");
  const auto& protection = v.mappings[0U]->read_only;
  if (!protection.has_value() || !protection->zero_return() || !v.data->stable() ||
      v.data->key() != v.plan->key ||
      v.data->arena().capacity() != service.arena.capacity ||
      v.plan->arena.capacity != service.arena.capacity ||
      v.plan->arena.cache_line_bytes != service.arena.cache_line_bytes ||
      v.plan->arena.base_page_bytes != service.arena.base_page_bytes ||
      v.plan->arena.master_seed != service.arena.master_seed ||
      v.plan->arena.seed_namespace != service.arena.seed_namespace)
    throw std::invalid_argument("pilot capture changed its persistent arena");
  const bool linked = service.package == protocol::QueuePackage::l0 ||
                      service.package == protocol::QueuePackage::l1;
  if (linked &&
      (!service.linked_order ||
       service.linked_order->master_seed != v.plan->node_order.master_seed ||
       service.linked_order->seed_namespace != v.plan->node_order.seed_namespace ||
       service.linked_order->arena_alignment_bytes !=
           v.plan->node_order.arena_alignment_bytes))
    throw std::invalid_argument("pilot capture changed its persistent node order");
}
template <protocol::QueuePackage Kind, typename Emitter>
auto prospective_pilot_private_layout(const MappedFormalScheduledPlan& plan)
    -> PilotPrivateLayout {
  if (!valid_scheduled_plan({plan.service.session, plan.phases}))
    throw std::invalid_argument("prospective pilot source windows/counts are invalid");
  // Validate the same package/arena/raw-buffer rules without inventing spans or
  // allocating the represented schedules. This helper establishes size only.
  static_cast<void>(mapped_formal_service_layout<Kind, Emitter>(plan.service));
  const auto& service = plan.service;
  using Types = pilot_detail::PackageType<Kind, Emitter>;
  mapped_discovery_detail::LayoutBuilder records, producer, consumer;
  PilotPrivateLayout out{};
  const auto line = service.arena.cache_line_bytes,
             page = service.arena.base_page_bytes;
  for (std::size_t i = 0U; i < 2U; ++i) {
    if (plan.phases[i].offered_count > std::numeric_limits<std::size_t>::max() ||
        plan.phases[i].offered_count > service.session.phases[i].producer_attempt_limit)
      throw std::invalid_argument(
          "prospective pilot source count exceeds finite bounds");
    out.schedule_offsets[i] = records.array<std::uint64_t>(
        static_cast<std::size_t>(plan.phases[i].offered_count), line);
  }
  // OwnerMapping requires a nonempty page even for two empty source arrays.
  if (records.bytes == 0U)
    static_cast<void>(records.reserve({1U, page}));
  out.records_bytes = records.reserve({0U, page});
  out.emitter_object = producer.array<Emitter>(1U, line);
  out.package_object = producer.array<typename Types::Package>(1U, line);
  for (std::size_t i = 0U; i < 2U; ++i) {
    auto& p = out.phases[i];
    p.raw = storage::raw_stream_storage_requirements(
        service.run_ids[i], service.capacity[i].producer_primary_rows,
        service.capacity[i].consumer_primary_rows);
    p.producer_object =
        producer.array<formal_service_detail::ProducerObjects>(1U, line);
    p.producer_raw = producer.reserve({p.raw.producer_bytes, line});
    p.consumer_object =
        consumer.array<formal_service_detail::ConsumerObjects>(1U, line);
    p.consumer_raw = consumer.reserve({p.raw.consumer_bytes, line});
  }
  out.producer_bytes = producer.reserve({0U, page});
  out.consumer_bytes = consumer.reserve({0U, page});
  return out;
}
template <protocol::QueuePackage Kind, typename Emitter>
auto mapped_pilot_capture_layout(const MappedPilotCapturePlan& plan)
    -> PilotPrivateLayout {
  validate_pilot_shared_view(plan);
  validate_mapped_scheduled_plan(plan.scheduled);
  return prospective_pilot_private_layout<Kind, Emitter>(plan.scheduled);
}

template <protocol::QueuePackage Kind, typename Emitter, typename Operations,
          typename Relax>
class MappedPilotPreparation final {
  using Types = pilot_detail::PackageType<Kind, Emitter>;

public:
  MappedPilotPreparation(const MappedPilotCapturePlan& plan,
                         MappedDiscoveryRegions<Operations> regions, Relax&)
      : plan_(plan), layout_(mapped_pilot_capture_layout<Kind, Emitter>(plan)),
        regions_(regions) {
    const auto r = regions.records.evidence().requested,
               p = regions.producer.evidence().requested,
               c = regions.consumer.evidence().requested;
    if (r.bytes != layout_.records_bytes || p.bytes != layout_.producer_bytes ||
        c.bytes != layout_.consumer_bytes ||
        r.owner_cpu != plan.shared.plan->producer_cpu || p.owner_cpu != r.owner_cpu ||
        r.requested_node != plan.shared.plan->shared_node ||
        p.requested_node != r.requested_node ||
        r.verified_base_page_bytes != plan.scheduled.service.arena.base_page_bytes ||
        p.verified_base_page_bytes != r.verified_base_page_bytes ||
        c.verified_base_page_bytes != r.verified_base_page_bytes)
      throw std::invalid_argument("pilot private mappings differ from owners/layout");
  }
  ~MappedPilotPreparation() {
    for (auto* p : producer_)
      if (p)
        std::destroy_at(p);
    for (auto* p : consumer_)
      if (p)
        std::destroy_at(p);
    if (package_)
      std::destroy_at(package_);
    if (emitter_)
      std::destroy_at(emitter_);
  }
  auto prepare_producer() noexcept -> bool { return prepare(0U); }
  auto prepare_consumer() noexcept -> bool { return prepare(1U); }
  auto producer_phase(bool warmup) noexcept -> FormalServiceProducerPhase& {
    return producer_[warmup ? 0U : 1U]->phase;
  }
  auto consumer_phase(bool warmup) noexcept -> FormalServiceConsumerPhase& {
    return consumer_[warmup ? 0U : 1U]->phase;
  }
  auto arena() const noexcept -> const workload::EventArena& {
    return plan_.shared.data->arena();
  }
  auto queue() noexcept -> typename Types::Queue& {
    if constexpr (Types::linked)
      return plan_.shared.data->linked();
    else
      return plan_.shared.data->ring();
  }
  auto package() noexcept -> typename Types::Package& { return *package_; }
  auto shared_view() const noexcept -> PreparedPilotDataView { return plan_.shared; }
  auto status(std::size_t role) const -> MappedDiscoveryPreparationStop {
    return stop_.at(role).load(std::memory_order_acquire);
  }
  auto node_order() const noexcept -> std::span<const std::size_t> {
    return plan_.shared.node_order;
  }
  auto schedule(ServicePhase phase) const noexcept -> lifecycle::PreparedScheduleView {
    const auto i = phase == ServicePhase::warmup ? 0U : 1U;
    const auto& p = plan_.scheduled.phases[i];
    return {schedules_[i], p.source_origin_ticks, p.source_horizon_ticks};
  }

private:
  auto prepare(std::size_t role) noexcept -> bool {
    auto expected = MappedDiscoveryPreparationStop::not_started;
    if (!stop_[role].compare_exchange_strong(expected,
                                             MappedDiscoveryPreparationStop::preparing))
      return false;
    auto fail = [&](MappedDiscoveryPreparationStop why) {
      stop_[role].store(why, std::memory_order_release);
      return false;
    };
    try {
      using namespace mapped_discovery_detail;
      const auto& service = plan_.scheduled.service;
      if (role == 0U) {
        if (!regions_.records.prepare() || !regions_.producer.prepare())
          return fail(MappedDiscoveryPreparationStop::mapping_failure);
        const auto r = regions_.records.mapped_bytes(),
                   p = regions_.producer.mapped_bytes();
        for (std::size_t i = 0U; i < 2U; ++i) {
          auto dst = initialize_array<std::uint64_t>(
              r, layout_.schedule_offsets[i], plan_.scheduled.deadlines[i].size());
          std::copy(plan_.scheduled.deadlines[i].begin(),
                    plan_.scheduled.deadlines[i].end(), dst.begin());
          schedules_[i] = dst;
        }
        emitter_ = std::construct_at(pointer<Emitter>(p, layout_.emitter_object));
        auto* target = pointer<typename Types::Package>(p, layout_.package_object);
        if constexpr (Kind == protocol::QueuePackage::r0 ||
                      Kind == protocol::QueuePackage::l0)
          package_ = std::construct_at(target, queue());
        else if constexpr (Kind == protocol::QueuePackage::l1)
          package_ = std::construct_at(target, queue(), *emitter_);
        else if constexpr (Kind == protocol::QueuePackage::r1)
          package_ =
              std::construct_at(target, queue(), *emitter_,
                                workload::ring_one_line_distance(
                                    {service.arena.capacity,
                                     service.arena.cache_line_bytes, sizeof(void*)}));
        else {
          if (!service.ring_distance.has_value())
            throw std::invalid_argument("pilot R2 distance is missing");
          const auto& d = *service.ring_distance;
          const auto resolved = workload::resolve_calibrated_ring_distance(
              {service.arena.capacity, service.arena.cache_line_bytes, sizeof(void*)},
              d.cache_lines, d.calibration_evidence_id);
          package_ = std::construct_at(target, queue(), *emitter_, resolved);
        }
        for (std::size_t i = 0U; i < 2U; ++i)
          producer_[i] = std::construct_at(
              pointer<formal_service_detail::ProducerObjects>(
                  p, layout_.phases[i].producer_object),
              service.run_ids[i], service.capacity[i].producer_primary_rows,
              p.subspan(layout_.phases[i].producer_raw,
                        layout_.phases[i].raw.producer_bytes));
        if (!regions_.records.protect_read_only())
          return fail(MappedDiscoveryPreparationStop::protection_failure);
      } else {
        if (!regions_.consumer.prepare())
          return fail(MappedDiscoveryPreparationStop::mapping_failure);
        const auto p = regions_.consumer.mapped_bytes();
        for (std::size_t i = 0U; i < 2U; ++i)
          consumer_[i] = std::construct_at(
              pointer<formal_service_detail::ConsumerObjects>(
                  p, layout_.phases[i].consumer_object),
              service.run_ids[i], service.capacity[i].consumer_primary_rows,
              service.initial_consumer,
              p.subspan(layout_.phases[i].consumer_raw,
                        layout_.phases[i].raw.consumer_bytes));
      }
      stop_[role].store(MappedDiscoveryPreparationStop::ready,
                        std::memory_order_release);
      return true;
    } catch (...) {
      return fail(MappedDiscoveryPreparationStop::construction_failure);
    }
  }
  const MappedPilotCapturePlan& plan_;
  const PilotPrivateLayout layout_;
  MappedDiscoveryRegions<Operations> regions_;
  Emitter* emitter_{nullptr};
  typename Types::Package* package_{nullptr};
  std::array<formal_service_detail::ProducerObjects*, 2U> producer_{};
  std::array<formal_service_detail::ConsumerObjects*, 2U> consumer_{};
  std::array<std::span<const std::uint64_t>, 2U> schedules_{};
  std::array<std::atomic<MappedDiscoveryPreparationStop>, 2U> stop_{};
};

template <protocol::QueuePackage Kind, typename Emitter>
struct PilotRuntimePolicy final {
  using Plan = MappedPilotCapturePlan;
  using Layout = PilotPrivateLayout;
  using SessionStorage = ScheduledSessionStorage;
  using SessionResult = PilotLifecycleResult;
  template <typename Ops, typename Relax>
  using Provider = MappedPilotPreparation<Kind, Emitter, Ops, Relax>;
  template <typename Clock, typename Prep>
  using Backend =
      FormalServiceSessionBackend<Clock, Prep, FormalCapturePurpose::scheduled>;
  static auto base_plan(const Plan& p) noexcept -> const MappedFormalServicePlan& {
    return p.scheduled.service;
  }
  static auto layout(const Plan& p) -> Layout {
    return mapped_pilot_capture_layout<Kind, Emitter>(p);
  }
  template <typename Clock, typename Prep>
  static auto make_backend(const Plan& p, Clock& clock, Prep& prep)
      -> Backend<Clock, Prep> {
    return {p.scheduled.service.session, clock, prep};
  }
  template <typename Clock, typename Prep, typename Relax, typename Observer,
            typename Threads>
  static auto run(const Plan& p, Backend<Clock, Prep>& backend, Prep& prep,
                  Relax& relax, Observer& observer, Threads& threads,
                  SessionStorage& storage) -> SessionResult {
    pilot_detail::WarmupResetObserver bridge{[&]() noexcept {
                                               return p.shared.data->stable() &&
                                                      prep.queue().reset_quiescent();
                                             },
                                             observer};
    const auto session = run_scheduled_session(
        {p.scheduled.service.session, p.scheduled.phases}, backend.clock(), backend,
        prep, relax, bridge, threads, storage);
    return {session, bridge.initial_queue_reset};
  }
};
} // namespace cpu_prefetch::calibration
#endif
