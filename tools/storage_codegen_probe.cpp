#include "cpu_prefetch/storage/raw_observations.hpp"

extern "C" [[gnu::noinline]] cpu_prefetch::storage::AppendStatus
cpu_prefetch_storage_producer_append(
    cpu_prefetch::storage::ProducerObservationStream* stream,
    const cpu_prefetch::timing::ProducerObservation* observation) noexcept {
  return stream->append(*observation);
}

extern "C" [[gnu::noinline]] cpu_prefetch::storage::AppendStatus
cpu_prefetch_storage_consumer_append(
    cpu_prefetch::storage::ConsumerObservationStream* stream,
    const cpu_prefetch::timing::ConsumerObservation* observation) noexcept {
  return stream->append(*observation);
}

int main() { return 0; }
