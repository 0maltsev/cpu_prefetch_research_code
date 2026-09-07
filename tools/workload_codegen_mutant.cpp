#include "cpu_prefetch/workload/records.hpp"

#include <atomic>

namespace {
std::atomic<std::uint64_t> forbidden_observations{0U};
}

extern "C" [[gnu::noinline]] void
cpu_prefetch_forbidden_workload_observer(std::uint64_t value) noexcept {
  forbidden_observations.fetch_add(value, std::memory_order_seq_cst);
}

extern "C" [[gnu::noinline]] std::uint64_t cpu_prefetch_consumer_record_action_mutant(
    std::uint64_t state, const cpu_prefetch::workload::EventRecord* record) noexcept {
  const auto result =
      cpu_prefetch::workload::mix_consumer_state(
          cpu_prefetch::workload::ConsumerState{state},
          cpu_prefetch::workload::RecordIndex{record->record_index}, record->payload)
          .value;
  cpu_prefetch_forbidden_workload_observer(result);
  return result;
}

int main() { return 0; }
