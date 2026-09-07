#include "cpu_prefetch/timing/clock.hpp"
#include "cpu_prefetch/workload/packages.hpp"

#include <cstdint>

namespace {

class BoundaryClock final {
public:
  BoundaryClock(cpu_prefetch::timing::ClockOrigin origin,
                std::uint64_t* captured) noexcept
      : clock_(origin), captured_(captured) {}

  [[nodiscard]] bool before_enqueue_publication() noexcept { return capture(); }
  [[nodiscard]] bool after_dequeue_observation() noexcept { return capture(); }

private:
  [[nodiscard]] bool capture() noexcept {
    const auto reading = clock_.read();
    if (reading.status != cpu_prefetch::timing::ClockReadStatus::ok) {
      return false;
    }
    *captured_ = reading.sample.relative_picoseconds;
    return true;
  }

  cpu_prefetch::timing::MonotonicRawClock clock_;
  std::uint64_t* captured_;
};

struct PrefetchEmitter final {
  const void** target;
  void ring_producer_write(const void* value) const noexcept { *target = value; }
  void ring_consumer_read(const void* value) const noexcept { *target = value; }
  void successor_header(const void* value) const noexcept { *target = value; }
};

} // namespace

extern "C" [[gnu::noinline]] std::uint64_t
cpu_prefetch_timing_read(cpu_prefetch::timing::ClockOrigin origin) noexcept {
  const auto result = cpu_prefetch::timing::MonotonicRawClock(origin).read();
  return result.status == cpu_prefetch::timing::ClockReadStatus::ok
             ? result.sample.relative_picoseconds
             : UINT64_MAX;
}

extern "C" [[gnu::noinline]] std::uint32_t cpu_prefetch_timing_r0_enqueue(
    cpu_prefetch::queue::RingSpscQueue* queue, cpu_prefetch::queue::EventPointer event,
    cpu_prefetch::timing::ClockOrigin origin, std::uint64_t* captured) noexcept {
  cpu_prefetch::workload::R0Package package(*queue);
  BoundaryClock clock(origin, captured);
  const auto result = package.try_enqueue_with_boundary_observer(event, clock);
  return static_cast<std::uint32_t>(result.status) |
         (static_cast<std::uint32_t>(result.result) + 1U) << 8U;
}

extern "C" [[gnu::noinline]] std::uint32_t
cpu_prefetch_timing_r0_dequeue(cpu_prefetch::queue::RingSpscQueue* queue,
                               cpu_prefetch::timing::ClockOrigin origin,
                               std::uint64_t* captured) noexcept {
  cpu_prefetch::workload::R0Package package(*queue);
  BoundaryClock clock(origin, captured);
  const auto result = package.try_dequeue_with_boundary_observer(clock);
  return static_cast<std::uint32_t>(result.status) |
         (static_cast<std::uint32_t>(result.result.status) + 1U) << 8U;
}

extern "C" [[gnu::noinline]] std::uint32_t
cpu_prefetch_timing_r1_enqueue(cpu_prefetch::queue::RingSpscQueue* queue,
                               cpu_prefetch::queue::EventPointer event,
                               const cpu_prefetch::workload::RingDistance* distance,
                               cpu_prefetch::timing::ClockOrigin origin,
                               std::uint64_t* captured, const void** target) noexcept {
  PrefetchEmitter emitter{target};
  cpu_prefetch::workload::R1Package package(*queue, emitter, *distance);
  BoundaryClock clock(origin, captured);
  const auto result = package.try_enqueue_with_boundary_observer(event, clock);
  return static_cast<std::uint32_t>(result.status) |
         (static_cast<std::uint32_t>(result.result) + 1U) << 8U;
}

extern "C" [[gnu::noinline]] std::uint32_t
cpu_prefetch_timing_r1_dequeue(cpu_prefetch::queue::RingSpscQueue* queue,
                               const cpu_prefetch::workload::RingDistance* distance,
                               cpu_prefetch::timing::ClockOrigin origin,
                               std::uint64_t* captured, const void** target) noexcept {
  PrefetchEmitter emitter{target};
  cpu_prefetch::workload::R1Package package(*queue, emitter, *distance);
  BoundaryClock clock(origin, captured);
  const auto result = package.try_dequeue_with_boundary_observer(clock);
  return static_cast<std::uint32_t>(result.status) |
         (static_cast<std::uint32_t>(result.result.status) + 1U) << 8U;
}

extern "C" [[gnu::noinline]] std::uint32_t cpu_prefetch_timing_r2_enqueue(
    cpu_prefetch::queue::RingSpscQueue* queue, cpu_prefetch::queue::EventPointer event,
    const cpu_prefetch::workload::CalibratedRingDistance* distance,
    cpu_prefetch::timing::ClockOrigin origin, std::uint64_t* captured,
    const void** target) noexcept {
  PrefetchEmitter emitter{target};
  cpu_prefetch::workload::R2Package package(*queue, emitter, *distance);
  BoundaryClock clock(origin, captured);
  const auto result = package.try_enqueue_with_boundary_observer(event, clock);
  return static_cast<std::uint32_t>(result.status) |
         (static_cast<std::uint32_t>(result.result) + 1U) << 8U;
}

extern "C" [[gnu::noinline]] std::uint32_t cpu_prefetch_timing_r2_dequeue(
    cpu_prefetch::queue::RingSpscQueue* queue,
    const cpu_prefetch::workload::CalibratedRingDistance* distance,
    cpu_prefetch::timing::ClockOrigin origin, std::uint64_t* captured,
    const void** target) noexcept {
  PrefetchEmitter emitter{target};
  cpu_prefetch::workload::R2Package package(*queue, emitter, *distance);
  BoundaryClock clock(origin, captured);
  const auto result = package.try_dequeue_with_boundary_observer(clock);
  return static_cast<std::uint32_t>(result.status) |
         (static_cast<std::uint32_t>(result.result.status) + 1U) << 8U;
}

extern "C" [[gnu::noinline]] std::uint32_t
cpu_prefetch_timing_l0_enqueue(cpu_prefetch::queue::LinkedSpscQueue* queue,
                               cpu_prefetch::queue::EventPointer event,
                               cpu_prefetch::timing::ClockOrigin origin,
                               std::uint64_t* captured) noexcept {
  cpu_prefetch::workload::L0Package package(*queue);
  BoundaryClock clock(origin, captured);
  const auto result = package.try_enqueue_with_boundary_observer(event, clock);
  return static_cast<std::uint32_t>(result.status) |
         (static_cast<std::uint32_t>(result.result) + 1U) << 8U;
}

extern "C" [[gnu::noinline]] std::uint32_t
cpu_prefetch_timing_l0_dequeue(cpu_prefetch::queue::LinkedSpscQueue* queue,
                               cpu_prefetch::timing::ClockOrigin origin,
                               std::uint64_t* captured) noexcept {
  cpu_prefetch::workload::L0Package package(*queue);
  BoundaryClock clock(origin, captured);
  const auto result = package.try_dequeue_with_boundary_observer(clock);
  return static_cast<std::uint32_t>(result.status) |
         (static_cast<std::uint32_t>(result.result.status) + 1U) << 8U;
}

extern "C" [[gnu::noinline]] std::uint32_t
cpu_prefetch_timing_l1_enqueue(cpu_prefetch::queue::LinkedSpscQueue* queue,
                               cpu_prefetch::queue::EventPointer event,
                               cpu_prefetch::timing::ClockOrigin origin,
                               std::uint64_t* captured, const void** target) noexcept {
  PrefetchEmitter emitter{target};
  cpu_prefetch::workload::L1Package package(*queue, emitter);
  BoundaryClock clock(origin, captured);
  const auto result = package.try_enqueue_with_boundary_observer(event, clock);
  return static_cast<std::uint32_t>(result.status) |
         (static_cast<std::uint32_t>(result.result) + 1U) << 8U;
}

extern "C" [[gnu::noinline]] std::uint32_t
cpu_prefetch_timing_l1_dequeue(cpu_prefetch::queue::LinkedSpscQueue* queue,
                               cpu_prefetch::timing::ClockOrigin origin,
                               std::uint64_t* captured, const void** target) noexcept {
  PrefetchEmitter emitter{target};
  cpu_prefetch::workload::L1Package package(*queue, emitter);
  BoundaryClock clock(origin, captured);
  const auto result = package.try_dequeue_with_boundary_observer(clock);
  return static_cast<std::uint32_t>(result.status) |
         (static_cast<std::uint32_t>(result.result.status) + 1U) << 8U;
}

int main() { return 0; }
