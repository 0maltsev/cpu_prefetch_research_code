#include "cpu_prefetch/workload/packages.hpp"
#include "cpu_prefetch/workload/records.hpp"

namespace {

struct CapturingEmitter final {
  const void** target;

  void ring_producer_write(const void* value) const noexcept { *target = value; }
  void ring_consumer_read(const void* value) const noexcept { *target = value; }
  void successor_header(const void* value) const noexcept { *target = value; }
};

} // namespace

extern "C" [[gnu::noinline]] std::uint64_t cpu_prefetch_consumer_record_action(
    std::uint64_t state, const cpu_prefetch::workload::EventRecord* record) noexcept {
  const auto record_index = record->record_index;
  const auto payload = record->payload;
  return cpu_prefetch::workload::mix_consumer_state(
             cpu_prefetch::workload::ConsumerState{state},
             cpu_prefetch::workload::RecordIndex{record_index}, payload)
      .value;
}

extern "C" [[gnu::noinline]] cpu_prefetch::queue::EnqueueResult
cpu_prefetch_r1_try_enqueue(cpu_prefetch::queue::RingSpscQueue* queue,
                            cpu_prefetch::queue::EventPointer event,
                            const cpu_prefetch::workload::RingDistance* distance,
                            const void** target) noexcept {
  CapturingEmitter emitter{target};
  cpu_prefetch::workload::R1Package package(*queue, emitter, *distance);
  return package.try_enqueue(event);
}

extern "C" [[gnu::noinline]] cpu_prefetch::queue::DequeueResult
cpu_prefetch_r1_try_dequeue(cpu_prefetch::queue::RingSpscQueue* queue,
                            const cpu_prefetch::workload::RingDistance* distance,
                            const void** target) noexcept {
  CapturingEmitter emitter{target};
  cpu_prefetch::workload::R1Package package(*queue, emitter, *distance);
  return package.try_dequeue();
}

extern "C" [[gnu::noinline]] cpu_prefetch::queue::EnqueueResult
cpu_prefetch_r2_try_enqueue(
    cpu_prefetch::queue::RingSpscQueue* queue, cpu_prefetch::queue::EventPointer event,
    const cpu_prefetch::workload::CalibratedRingDistance* distance,
    const void** target) noexcept {
  CapturingEmitter emitter{target};
  cpu_prefetch::workload::R2Package package(*queue, emitter, *distance);
  return package.try_enqueue(event);
}

extern "C" [[gnu::noinline]] cpu_prefetch::queue::DequeueResult
cpu_prefetch_r2_try_dequeue(
    cpu_prefetch::queue::RingSpscQueue* queue,
    const cpu_prefetch::workload::CalibratedRingDistance* distance,
    const void** target) noexcept {
  CapturingEmitter emitter{target};
  cpu_prefetch::workload::R2Package package(*queue, emitter, *distance);
  return package.try_dequeue();
}

extern "C" [[gnu::noinline]] cpu_prefetch::queue::DequeueResult
cpu_prefetch_l1_try_dequeue(cpu_prefetch::queue::LinkedSpscQueue* queue,
                            const void** target) noexcept {
  CapturingEmitter emitter{target};
  cpu_prefetch::workload::L1Package package(*queue, emitter);
  return package.try_dequeue();
}

int main() { return 0; }
