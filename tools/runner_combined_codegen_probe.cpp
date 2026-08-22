#include "cpu_prefetch/runner/runner.hpp"
#include "cpu_prefetch/storage/capture_backend.hpp"
#include "cpu_prefetch/timing/clock.hpp"
#include "cpu_prefetch/workload/packages.hpp"

namespace {

using Clock = cpu_prefetch::timing::MonotonicRawClock;
using Emitter = cpu_prefetch::runner::X86RetainingPrefetchEmitter;
using R0 = cpu_prefetch::workload::R0Package;
using R1 = cpu_prefetch::workload::R1Package<Emitter>;
using R2 = cpu_prefetch::workload::R2Package<Emitter>;
using L0 = cpu_prefetch::workload::L0Package;
using L1 = cpu_prefetch::workload::L1Package<Emitter>;

template <typename Package>
using Backend = cpu_prefetch::storage::CapturingObservationBackend<Clock, Package>;

template <typename Package>
[[nodiscard]] auto producer(Backend<Package>* backend,
                            cpu_prefetch::lifecycle::ProducerAttempt attempt) noexcept
    -> cpu_prefetch::lifecycle::ProducerAttemptResult {
  return backend->try_producer_attempt(attempt);
}

template <typename Package>
[[nodiscard]] auto consumer(Backend<Package>* backend, std::uint64_t ordinal) noexcept
    -> cpu_prefetch::lifecycle::ConsumerPollResult {
  return backend->try_consumer_poll(ordinal);
}

} // namespace

#define CPU_PREFETCH_COMBINED_PROBES(NAME, TYPE)                                       \
  extern "C" [[gnu::noinline]] auto cpu_prefetch_combined_##NAME##_producer(           \
      Backend<TYPE>* backend,                                                          \
      cpu_prefetch::lifecycle::ProducerAttempt attempt) noexcept                       \
      -> cpu_prefetch::lifecycle::ProducerAttemptResult {                              \
    return producer(backend, attempt);                                                 \
  }                                                                                    \
  extern "C" [[gnu::noinline]] auto cpu_prefetch_combined_##NAME##_consumer(           \
      Backend<TYPE>* backend, std::uint64_t ordinal) noexcept                          \
      -> cpu_prefetch::lifecycle::ConsumerPollResult {                                 \
    return consumer(backend, ordinal);                                                 \
  }

CPU_PREFETCH_COMBINED_PROBES(r0, R0)
CPU_PREFETCH_COMBINED_PROBES(r1, R1)
CPU_PREFETCH_COMBINED_PROBES(r2, R2)
CPU_PREFETCH_COMBINED_PROBES(l0, L0)
CPU_PREFETCH_COMBINED_PROBES(l1, L1)

#undef CPU_PREFETCH_COMBINED_PROBES

int main() { return 0; }
