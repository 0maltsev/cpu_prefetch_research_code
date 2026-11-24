#ifndef CPU_PREFETCH_CALIBRATION_PILOT_SCHEDULED_CAPTURE_HPP
#define CPU_PREFETCH_CALIBRATION_PILOT_SCHEDULED_CAPTURE_HPP

#include "cpu_prefetch/calibration/formal_service_session.hpp"
#include "cpu_prefetch/calibration/pilot_shared_data.hpp"
#include "cpu_prefetch/calibration/scheduled_session.hpp"

#include <array>
#include <atomic>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>

namespace cpu_prefetch::calibration {
struct PilotPhaseBuffers final {
  std::array<FormalServiceProducerPhase*, 2U> producer;
  std::array<FormalServiceConsumerPhase*, 2U> consumer;
};
struct PilotPhaseRawView final {
  std::string_view run_id;
  storage::RawStreamSnapshot producer;
  storage::RawStreamSnapshot consumer;
};
struct PilotScheduledCaptureResult final {
  ScheduledSessionResult session;
  // Borrowed complete OR incomplete bytes from both original phases. Caller's
  // streams, IDs and raw storage remain alive until synchronous publication.
  std::array<PilotPhaseRawView, 2U> raw;
  bool initial_queue_reset;
};

namespace pilot_detail {
// Shared cold controller bridge, also used by mapped pilot runtimes. Reset is
// reached only after one-shot claim, both owner preparations and source checks.
template <typename Reset, typename Observer> struct WarmupResetObserver final {
  Reset reset;
  Observer& observer;
  bool initial_queue_reset{false};
  auto before_phase(ServicePhase phase) -> bool {
    if (phase == ServicePhase::warmup) {
      initial_queue_reset = reset();
      if (!initial_queue_reset)
        return false;
    }
    return observer.before_phase(phase);
  }
  auto during_phase(ServicePhase phase, ServiceWindow window,
                    const std::atomic<std::uint32_t>& finished) -> bool {
    return observer.during_phase(phase, window, finished);
  }
  auto after_phase(ServicePhase phase) -> bool { return observer.after_phase(phase); }
};
template <protocol::QueuePackage Kind, typename Emitter> struct PackageType final {
  static_assert(Kind == protocol::QueuePackage::r0 ||
                Kind == protocol::QueuePackage::r1 ||
                Kind == protocol::QueuePackage::r2 ||
                Kind == protocol::QueuePackage::l0 ||
                Kind == protocol::QueuePackage::l1);
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
} // namespace pilot_detail

// Caller constructs all phase streams/objects in declared owner storage before
// warmup. Owners implements actual mapping/affinity/TLS observation callbacks;
// this adapter never treats a callback or requested placement as qualification.
// All owner callbacks must obey the existing no-allocation reset contract.
template <protocol::QueuePackage Kind, typename Emitter, typename Owners>
class PilotScheduledPreparation final {
  using Types = pilot_detail::PackageType<Kind, Emitter>;

public:
  PilotScheduledPreparation(PilotSharedData& data, const ScheduledSessionPlan& plan,
                            const std::array<protocol::RunId, 2U>& ids,
                            PilotPhaseBuffers buffers,
                            std::array<lifecycle::PreparedScheduleView, 2U> sources,
                            Owners& owners, Emitter& emitter,
                            const workload::CalibratedRingDistance* distance = nullptr)
      : data_(data), plan_(plan), ids_(ids), buffers_(buffers), sources_(sources),
        owners_(owners), package_(make_package(data, emitter, distance)) {
    if (!valid_scheduled_plan(plan) || ids[0U] == ids[1U] || !data.stable())
      throw std::invalid_argument("pilot phase plan/identity is invalid");
    std::array<pilot_detail::MemoryRange, 8U> ranges{};
    ranges[0U] = data.arena_range();
    ranges[1U] = data.node_range();
    for (std::size_t phase = 0U; phase < 2U; ++phase) {
      if (buffers.producer[phase] == nullptr || buffers.consumer[phase] == nullptr)
        throw std::invalid_argument("pilot phase storage is missing");
      const auto p = buffers.producer[phase]->primary.snapshot();
      const auto c = buffers.consumer[phase]->primary.snapshot();
      if (p.run_id != ids[phase].value() || c.run_id != ids[phase].value() ||
          p.row_capacity < plan.bounds.phases[phase].producer_attempt_limit ||
          c.row_capacity < plan.bounds.phases[phase].producer_attempt_limit ||
          p.row_bytes != buffers.producer[phase]->layout.producer_row_bytes ||
          c.row_bytes != buffers.consumer[phase]->layout.consumer_row_bytes)
        throw std::invalid_argument("pilot raw capacity/identity differs from plan");
      const auto ps = extent(p.row_capacity, p.row_bytes);
      const auto cs = extent(c.row_capacity, c.row_bytes);
      buffer_addresses_[2U * phase] = buffers.producer[phase]->primary.buffer_address();
      buffer_addresses_[2U * phase + 1U] =
          buffers.consumer[phase]->primary.buffer_address();
      ranges[2U + 2U * phase] =
          pilot_detail::memory_range(buffer_addresses_[2U * phase], ps);
      ranges[3U + 2U * phase] =
          pilot_detail::memory_range(buffer_addresses_[2U * phase + 1U], cs);
      const auto& source = sources[phase];
      const auto& declared = plan.phases[phase];
      if (source.deadline_ticks.size() != declared.offered_count ||
          source.origin_ticks != declared.source_origin_ticks ||
          source.horizon_ticks != declared.source_horizon_ticks ||
          (!source.deadline_ticks.empty() &&
           reinterpret_cast<std::uintptr_t>(source.deadline_ticks.data()) %
                   alignof(std::uint64_t) !=
               0U))
        throw std::invalid_argument("pilot source shape differs from plan");
      ranges[6U + phase] = pilot_detail::memory_range(
          source.deadline_ticks.data(),
          extent(source.deadline_ticks.size(), sizeof(std::uint64_t)));
    }
    for (std::size_t a = 0U; a < ranges.size(); ++a)
      for (std::size_t b = a + 1U; b < ranges.size(); ++b)
        if (pilot_detail::overlaps(ranges[a], ranges[b]))
          throw std::invalid_argument("pilot phase sources/raw/shared data alias");
    // Do not read/prefault sources here. Existing scheduled-session validation
    // reads actual source values only after both owners prepare successfully.
  }
  PilotScheduledPreparation(const PilotScheduledPreparation&) = delete;
  auto operator=(const PilotScheduledPreparation&)
      -> PilotScheduledPreparation& = delete;
  auto plan() const noexcept -> const ScheduledSessionPlan& { return plan_; }
  auto prepare_producer() noexcept -> bool {
    const bool ready = stable() && owners_.prepare_producer();
    prepared_[0U].store(ready, std::memory_order_release);
    return ready;
  }
  auto prepare_consumer() noexcept -> bool {
    const bool ready = stable() && owners_.prepare_consumer();
    prepared_[1U].store(ready, std::memory_order_release);
    return ready;
  }
  auto before_measurement_producer() noexcept -> bool {
    return stable() && owners_.before_measurement_producer();
  }
  auto before_measurement_consumer() noexcept -> bool {
    return stable() && owners_.before_measurement_consumer();
  }
  auto producer_phase(bool warmup) noexcept -> FormalServiceProducerPhase& {
    return *buffers_.producer[warmup ? 0U : 1U];
  }
  auto consumer_phase(bool warmup) noexcept -> FormalServiceConsumerPhase& {
    return *buffers_.consumer[warmup ? 0U : 1U];
  }
  auto run_id(bool warmup) const noexcept -> const protocol::RunId& {
    return ids_[warmup ? 0U : 1U];
  }
  auto arena() const noexcept -> const workload::EventArena& { return data_.arena(); }
  auto queue() noexcept -> typename Types::Queue& {
    if constexpr (Types::linked)
      return data_.linked();
    else
      return data_.ring();
  }
  auto package() noexcept -> typename Types::Package& { return package_; }
  // Controller-only, after both owners park and before any warmup release.
  // An undrained queue fails; its observations are never silently discarded.
  auto reset_before_warmup() noexcept -> bool {
    return stable() && queue().reset_quiescent();
  }
  auto schedule(ServicePhase phase) const -> lifecycle::PreparedScheduleView {
    if (!prepared_[0U].load(std::memory_order_acquire) ||
        !prepared_[1U].load(std::memory_order_acquire))
      throw std::logic_error("pilot schedule requested before owners prepared");
    return sources_[phase == ServicePhase::warmup ? 0U : 1U];
  }
  // Controller-only after the session has joined both workers, even on failure.
  auto raw_after_join() const noexcept -> std::array<PilotPhaseRawView, 2U> {
    return {{{ids_[0U].value(), buffers_.producer[0U]->primary.snapshot(),
              buffers_.consumer[0U]->primary.snapshot()},
             {ids_[1U].value(), buffers_.producer[1U]->primary.snapshot(),
              buffers_.consumer[1U]->primary.snapshot()}}};
  }

private:
  static auto extent(std::uint64_t count, std::uint64_t row_bytes) -> std::size_t {
    if (row_bytes == 0U || count > std::numeric_limits<std::size_t>::max() / row_bytes)
      throw std::invalid_argument("pilot storage extent overflows");
    return static_cast<std::size_t>(count * row_bytes);
  }
  static auto make_package(PilotSharedData& data, Emitter& emitter,
                           const workload::CalibratedRingDistance* distance) ->
      typename Types::Package {
    if constexpr (Kind == protocol::QueuePackage::r0)
      return workload::R0Package(data.ring());
    else if constexpr (Kind == protocol::QueuePackage::l0)
      return workload::L0Package(data.linked());
    else if constexpr (Kind == protocol::QueuePackage::l1)
      return workload::L1Package<Emitter>(data.linked(), emitter);
    else if constexpr (Kind == protocol::QueuePackage::r1)
      return workload::R1Package<Emitter>(
          data.ring(), emitter,
          workload::ring_one_line_distance({data.arena().capacity(),
                                            data.arena().cache_line_bytes(),
                                            sizeof(void*)}));
    else {
      if (distance == nullptr)
        throw std::invalid_argument("pilot R2 needs explicit accepted distance");
      const auto checked = workload::resolve_calibrated_ring_distance(
          {data.arena().capacity(), data.arena().cache_line_bytes(), sizeof(void*)},
          distance->distance().cache_lines(),
          std::string(distance->calibration_evidence_id()));
      if (checked.distance().slots() != distance->distance().slots())
        throw std::invalid_argument("pilot R2 distance differs from shared geometry");
      return workload::R2Package<Emitter>(data.ring(), emitter, *distance);
    }
  }
  auto stable() const noexcept -> bool {
    if (!data_.stable())
      return false;
    for (std::size_t phase = 0U; phase < 2U; ++phase)
      if (buffers_.producer[phase]->primary.buffer_address() !=
              buffer_addresses_[2U * phase] ||
          buffers_.consumer[phase]->primary.buffer_address() !=
              buffer_addresses_[2U * phase + 1U])
        return false;
    return true;
  }
  PilotSharedData& data_;
  const ScheduledSessionPlan& plan_;
  const std::array<protocol::RunId, 2U>& ids_;
  const PilotPhaseBuffers buffers_;
  const std::array<lifecycle::PreparedScheduleView, 2U> sources_;
  Owners& owners_;
  typename Types::Package package_;
  std::array<const std::byte*, 4U> buffer_addresses_{};
  std::array<std::atomic<bool>, 2U> prepared_{};
};

template <typename Clock, typename Preparation, typename Relax, typename Observer,
          typename Threads>
[[nodiscard]] auto
run_pilot_scheduled_capture(const ScheduledSessionPlan& plan, Clock& clock,
                            Preparation& preparation, Relax& relax, Observer& observer,
                            Threads& threads, ScheduledSessionStorage& storage)
    -> PilotScheduledCaptureResult {
  if (&plan != &preparation.plan())
    throw std::invalid_argument("pilot session changed its bound plan");
  FormalServiceSessionBackend<Clock, Preparation, FormalCapturePurpose::scheduled>
      backend(plan.bounds, clock, preparation);
  pilot_detail::WarmupResetObserver checked_observer{
      [&]() noexcept { return preparation.reset_before_warmup(); }, observer};
  const auto result = run_scheduled_session(plan, clock, backend, preparation, relax,
                                            checked_observer, threads, storage);
  return {result, preparation.raw_after_join(), checked_observer.initial_queue_reset};
}
} // namespace cpu_prefetch::calibration
#endif
