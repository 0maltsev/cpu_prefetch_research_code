#include "cpu_prefetch/queue/adapters.hpp"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <iostream>
#include <span>
#include <thread>
#include <vector>

namespace {

using cpu_prefetch::queue::ArenaAlignmentBytes;
using cpu_prefetch::queue::CacheLineBytes;
using cpu_prefetch::queue::DequeueStatus;
using cpu_prefetch::queue::EnqueueResult;
using cpu_prefetch::queue::EventPointer;
using cpu_prefetch::queue::LinkedQueueAdapter;
using cpu_prefetch::queue::LinkedSpscQueue;
using cpu_prefetch::queue::QueueCapacity;
using cpu_prefetch::queue::RingQueueAdapter;
using cpu_prefetch::queue::RingSpscQueue;

constexpr CacheLineBytes kSyntheticCacheLine{64U};
constexpr ArenaAlignmentBytes kSyntheticPage{4096U};
constexpr std::size_t kCapacity = 257U;
constexpr std::size_t kTransfers = 200'000U;

void scheduling_perturbation(std::uint64_t& state, std::uint64_t mask) {
  state = (state * 6364136223846793005ULL) + 1442695040888963407ULL;
  if ((state & mask) == 0U) {
    std::this_thread::yield();
  }
}

EventPointer event_pointer(const void* value) {
  const auto event = EventPointer::from(value);
  if (!event.has_value()) {
    std::terminate();
  }
  return *event;
}

template <typename Adapter>
bool run_complete_transfer(Adapter& adapter, std::uint64_t producer_mask,
                           std::uint64_t consumer_mask) {
  std::vector<std::uint64_t> records(kTransfers);
  for (std::size_t index = 0; index < records.size(); ++index) {
    records[index] = static_cast<std::uint64_t>(index) ^ 0xa5a5a5a5a5a5a5a5ULL;
  }

  std::atomic<bool> start{false};
  std::atomic<bool> failed{false};
  std::thread producer([&] {
    std::uint64_t state = 0x0123456789abcdefULL;
    while (!start.load(std::memory_order_acquire)) {
    }
    for (std::size_t index = 0; index < records.size(); ++index) {
      while (adapter.try_enqueue(event_pointer(&records[index])) ==
             EnqueueResult::full) {
        scheduling_perturbation(state, producer_mask);
      }
      scheduling_perturbation(state, producer_mask);
    }
  });

  std::thread consumer([&] {
    std::uint64_t state = 0xfedcba9876543210ULL;
    while (!start.load(std::memory_order_acquire)) {
    }
    std::size_t expected = 0;
    while (expected < records.size()) {
      const auto result = adapter.try_dequeue();
      if (result.status == DequeueStatus::empty) {
        scheduling_perturbation(state, consumer_mask);
        continue;
      }
      if (result.status != DequeueStatus::item || result.event != &records[expected] ||
          *static_cast<const std::uint64_t*>(result.event) !=
              (static_cast<std::uint64_t>(expected) ^ 0xa5a5a5a5a5a5a5a5ULL)) {
        failed.store(true, std::memory_order_relaxed);
        return;
      }
      ++expected;
      scheduling_perturbation(state, consumer_mask);
    }
  });

  start.store(true, std::memory_order_release);
  producer.join();
  consumer.join();
  return !failed.load(std::memory_order_relaxed);
}

template <typename Adapter> bool run_one_attempt_history(Adapter& adapter) {
  constexpr std::size_t arrivals = 50'000U;
  std::vector<std::uint64_t> records(arrivals);
  std::vector<const void*> accepted;
  std::vector<const void*> consumed;
  accepted.reserve(arrivals);
  consumed.reserve(arrivals);
  std::atomic<bool> producer_finished{false};
  std::atomic<bool> failed{false};

  std::thread producer([&] {
    std::uint64_t state = 0x13579bdf2468ace0ULL;
    for (std::size_t index = 0; index < records.size(); ++index) {
      records[index] = static_cast<std::uint64_t>(index);
      if (adapter.try_enqueue(event_pointer(&records[index])) ==
          EnqueueResult::accepted) {
        accepted.push_back(&records[index]);
      }
      scheduling_perturbation(state, 0x3fU);
    }
    producer_finished.store(true, std::memory_order_release);
  });

  std::thread consumer([&] {
    std::uint64_t state = 0x02468ace13579bdfULL;
    for (;;) {
      const auto result = adapter.try_dequeue();
      if (result.status == DequeueStatus::item) {
        consumed.push_back(result.event);
        scheduling_perturbation(state, 0x1fU);
        continue;
      }
      if (result.status == DequeueStatus::recycler_invariant_failure) {
        failed.store(true, std::memory_order_relaxed);
        return;
      }
      if (producer_finished.load(std::memory_order_acquire)) {
        const auto final = adapter.try_dequeue();
        if (final.status == DequeueStatus::item) {
          consumed.push_back(final.event);
          continue;
        }
        if (final.status == DequeueStatus::recycler_invariant_failure) {
          failed.store(true, std::memory_order_relaxed);
        }
        return;
      }
      scheduling_perturbation(state, 0x0fU);
    }
  });

  producer.join();
  consumer.join();
  return !failed.load(std::memory_order_relaxed) && accepted == consumed;
}

std::vector<std::size_t> fixed_node_order() {
  std::vector<std::size_t> order(kCapacity + 1U);
  std::uint64_t state = 0x6a09e667f3bcc909ULL;
  for (std::size_t index = 0; index < order.size(); ++index) {
    order[index] = index;
  }
  for (std::size_t remaining = order.size(); remaining > 1U; --remaining) {
    state = (state * 2862933555777941757ULL) + 3037000493ULL;
    const auto selected = static_cast<std::size_t>(state % remaining);
    const auto last = remaining - 1U;
    const auto temporary = order[last];
    order[last] = order[selected];
    order[selected] = temporary;
  }
  return order;
}

bool stress_ring() {
  RingSpscQueue queue(QueueCapacity{kCapacity}, kSyntheticCacheLine);
  RingQueueAdapter adapter(queue);
  const bool transfers = run_complete_transfer(adapter, 0x3ffU, 0x1fU) &&
                         run_complete_transfer(adapter, 0x1fU, 0x3ffU);
  const bool one_attempt = run_one_attempt_history(adapter);
  const auto audit = queue.audit_quiescent();
  return transfers && one_attempt && audit.occupied_slots == 0U &&
         audit.positions_in_range;
}

bool stress_linked() {
  const auto order = fixed_node_order();
  LinkedSpscQueue queue(QueueCapacity{kCapacity}, kSyntheticCacheLine, kSyntheticPage,
                        std::span<const std::size_t>(order));
  LinkedQueueAdapter adapter(queue);
  const bool transfers = run_complete_transfer(adapter, 0x3ffU, 0x1fU) &&
                         run_complete_transfer(adapter, 0x1fU, 0x3ffU);
  const bool one_attempt = run_one_attempt_history(adapter);
  const auto audit = queue.audit_quiescent();
  return transfers && one_attempt && audit.queued_events == 0U && audit.chain_acyclic &&
         audit.tail_reachable && audit.every_node_owned_once &&
         audit.recycler_fifo_shape && audit.positions_in_range;
}

} // namespace

int main() {
  if (!stress_ring()) {
    std::cerr << "ring correctness stress failed\n";
    return 1;
  }
  if (!stress_linked()) {
    std::cerr << "linked/recycler correctness stress failed\n";
    return 2;
  }
  std::cout << "queue-correctness-stress: PASS\n";
  return 0;
}
