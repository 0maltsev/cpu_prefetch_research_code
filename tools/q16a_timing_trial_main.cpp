// Standalone, informal diagnostic ONLY -- not part of the Stage 17 formal
// admission/measurement ceremony, not wired into any CMake target, and not
// a scientific result. Its only purpose is to observe real enqueue/dequeue
// timing on cpu-prefetch-v5's own real near pair {0,1}, using the same
// RingSpscQueue/R0Package the real Q16a captures will use, so the owner can
// pick warmup/measurement durations for the real 708-capture campaign from
// real observed numbers on this hardware instead of an invented value.

#include "cpu_prefetch/queue/common.hpp"
#include "cpu_prefetch/queue/ring_spsc.hpp"
#include "cpu_prefetch/timing/clock.hpp"
#include "cpu_prefetch/workload/packages.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <pthread.h>
#include <sched.h>
#include <string>
#include <thread>
#include <vector>

namespace {

using cpu_prefetch::queue::CacheLineBytes;
using cpu_prefetch::queue::EnqueueResult;
using cpu_prefetch::queue::EventPointer;
using cpu_prefetch::queue::QueueCapacity;
using cpu_prefetch::queue::RingSpscQueue;
using cpu_prefetch::timing::ClockOrigin;
using cpu_prefetch::timing::MonotonicRawClock;
using cpu_prefetch::workload::R0Package;

void pin_to_cpu(unsigned cpu) {
  cpu_set_t set;
  CPU_ZERO(&set);
  CPU_SET(cpu, &set);
  pthread_setaffinity_np(pthread_self(), sizeof(set), &set);
}

alignas(64) std::array<char, 64> dummy_event{};

} // namespace

int main(int argument_count, char** arguments) {
  const unsigned producer_cpu = 0U;
  const unsigned consumer_cpu =
      argument_count > 2 ? static_cast<unsigned>(std::stoul(arguments[2])) : 1U;
  const std::size_t capacity = 256U;
  const std::size_t sample_count =
      argument_count > 1 ? static_cast<std::size_t>(std::stoul(arguments[1])) : 100000U;

  RingSpscQueue queue(QueueCapacity{capacity}, CacheLineBytes{64U});
  R0Package package(queue);

  const auto origin = MonotonicRawClock::capture_origin();
  if (origin.status != cpu_prefetch::timing::ClockReadStatus::ok) {
    std::fprintf(stderr, "clock origin capture failed\n");
    return 1;
  }
  MonotonicRawClock clock(ClockOrigin{origin.absolute_nanoseconds});

  const auto event = EventPointer::from(dummy_event.data());
  if (!event.has_value()) {
    std::fprintf(stderr, "event pointer construction failed\n");
    return 1;
  }

  std::atomic<bool> start{false};
  std::atomic<bool> producer_ready{false};
  std::atomic<bool> consumer_ready{false};
  std::vector<std::uint64_t> receive_ticks(sample_count, 0U);

  std::thread producer([&] {
    pin_to_cpu(producer_cpu);
    producer_ready.store(true, std::memory_order_release);
    while (!start.load(std::memory_order_acquire)) {
    }
    for (std::size_t index = 0U; index < sample_count; ++index) {
      while (package.try_enqueue(*event) != EnqueueResult::accepted) {
      }
    }
  });

  std::thread consumer([&] {
    pin_to_cpu(consumer_cpu);
    consumer_ready.store(true, std::memory_order_release);
    while (!start.load(std::memory_order_acquire)) {
    }
    for (std::size_t index = 0U; index < sample_count; ++index) {
      cpu_prefetch::queue::DequeueResult result;
      do {
        result = package.try_dequeue();
      } while (result.status != cpu_prefetch::queue::DequeueStatus::item);
      const auto sample = clock.read();
      receive_ticks[index] = sample.status == cpu_prefetch::timing::ClockReadStatus::ok
                                 ? sample.sample.relative_picoseconds
                                 : 0U;
    }
  });

  while (!producer_ready.load(std::memory_order_acquire) ||
         !consumer_ready.load(std::memory_order_acquire)) {
  }
  const auto begin = clock.read();
  start.store(true, std::memory_order_release);
  producer.join();
  consumer.join();
  const auto last_valid = std::find_if(receive_ticks.rbegin(), receive_ticks.rend(),
                                       [](std::uint64_t value) { return value != 0U; });

  if (begin.status != cpu_prefetch::timing::ClockReadStatus::ok ||
      last_valid == receive_ticks.rend()) {
    std::fprintf(stderr, "timing capture incomplete\n");
    return 1;
  }
  const auto total_ps = *last_valid - begin.sample.relative_picoseconds;
  const auto total_ns = total_ps / 1000U;
  std::vector<std::uint64_t> deltas;
  deltas.reserve(sample_count - 1U);
  for (std::size_t index = 1U; index < sample_count; ++index) {
    if (receive_ticks[index] != 0U && receive_ticks[index - 1U] != 0U) {
      deltas.push_back(receive_ticks[index] - receive_ticks[index - 1U]);
    }
  }
  std::sort(deltas.begin(), deltas.end());
  const auto p50 = deltas[deltas.size() / 2U] / 1000U;
  const auto p99 = deltas[(deltas.size() * 99U) / 100U] / 1000U;
  const auto minimum = deltas.front() / 1000U;
  const auto maximum = deltas.back() / 1000U;

  std::printf("producer_cpu=%u consumer_cpu=%u capacity=%zu samples=%zu "
              "total_ns=%lu mean_ns_per_sample=%.1f p50_ns=%lu p99_ns=%lu min_ns=%lu "
              "max_ns=%lu\n",
              producer_cpu, consumer_cpu, capacity, sample_count,
              static_cast<unsigned long>(total_ns),
              static_cast<double>(total_ns) / static_cast<double>(sample_count),
              static_cast<unsigned long>(p50), static_cast<unsigned long>(p99),
              static_cast<unsigned long>(minimum), static_cast<unsigned long>(maximum));
  return 0;
}
