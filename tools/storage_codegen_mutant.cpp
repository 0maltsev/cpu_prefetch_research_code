#include "cpu_prefetch/storage/raw_observations.hpp"

#include <atomic>

namespace {
std::atomic<unsigned int> forbidden_observation{0U};
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_forbidden_storage_observer(unsigned int status) noexcept {
  forbidden_observation.fetch_add(status, std::memory_order_seq_cst);
}

extern "C" [[gnu::noinline]] cpu_prefetch::storage::AppendStatus
cpu_prefetch_storage_append_mutant(
    cpu_prefetch::storage::ProducerObservationStream* stream,
    const cpu_prefetch::timing::ProducerObservation* observation) noexcept {
  const auto status = stream->append(*observation);
  cpu_prefetch_forbidden_storage_observer(static_cast<unsigned int>(status));
  return status;
}

int main() { return 0; }
