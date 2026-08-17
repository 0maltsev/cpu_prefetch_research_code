#include <rapidcheck.h>

#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/queue/adapters.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr cpu_prefetch::queue::CacheLineBytes kSyntheticCacheLine{64U};

cpu_prefetch::queue::EventPointer required_event_pointer(const void* pointer) {
  const auto event = cpu_prefetch::queue::EventPointer::from(pointer);
  if (!event.has_value()) {
    throw std::logic_error("non-null generated event pointer was rejected");
  }
  return event.value();
}

template <typename Adapter>
void check_queue_model(Adapter& adapter, std::size_t capacity,
                       const std::vector<std::uint8_t>& actions) {
  std::vector<std::uint64_t> events(actions.size() + 1U);
  std::deque<const void*> model;
  std::size_t next_event = 0;
  for (const auto action : actions) {
    if ((action & 1U) == 0U) {
      const auto* pointer = &events[next_event++];
      const auto result = adapter.try_enqueue(required_event_pointer(pointer));
      if (model.size() == capacity) {
        RC_ASSERT(result == cpu_prefetch::queue::EnqueueResult::full);
      } else {
        RC_ASSERT(result == cpu_prefetch::queue::EnqueueResult::accepted);
        model.push_back(pointer);
      }
    } else {
      const auto result = adapter.try_dequeue();
      if (model.empty()) {
        RC_ASSERT(result.status == cpu_prefetch::queue::DequeueStatus::empty);
      } else {
        RC_ASSERT(result.status == cpu_prefetch::queue::DequeueStatus::item);
        RC_ASSERT(reinterpret_cast<std::uintptr_t>(result.event) ==
                  reinterpret_cast<std::uintptr_t>(model.front()));
        model.pop_front();
      }
    }
  }
}

} // namespace

int main() {
  try {
    const bool framework_passed = rc::check("reversing a vector twice preserves it",
                                            [](const std::vector<int>& input) {
                                              auto copy = input;
                                              std::reverse(copy.begin(), copy.end());
                                              std::reverse(copy.begin(), copy.end());
                                              RC_ASSERT(copy == input);
                                            });
    const bool exact_integer_passed = rc::check(
        "JCS-I64 preserves every generated uint64 value", [](std::uint64_t input) {
          const std::string text = "{\"value\":" + std::to_string(input) + "}";
          const auto parsed = cpu_prefetch::protocol::json::parse(text);
          RC_ASSERT(parsed.has_value());
          const auto canonical =
              cpu_prefetch::protocol::json::canonicalize(parsed.value());
          RC_ASSERT(canonical.has_value());
          RC_ASSERT(canonical.value() == text);
        });
    const bool ring_model_passed = rc::check(
        "ring refines a bounded FIFO for generated sequential histories",
        [](const std::vector<std::uint8_t>& actions, std::uint8_t raw_capacity) {
          const auto capacity = static_cast<std::size_t>(raw_capacity % 8U) + 1U;
          cpu_prefetch::queue::RingSpscQueue queue(
              cpu_prefetch::queue::QueueCapacity{capacity}, kSyntheticCacheLine);
          cpu_prefetch::queue::RingQueueAdapter adapter(queue);
          check_queue_model(adapter, capacity, actions);
        });
    const bool linked_model_passed = rc::check(
        "linked/recycler refines a bounded FIFO for generated sequential histories",
        [](const std::vector<std::uint8_t>& actions, std::uint8_t raw_capacity) {
          const auto capacity = static_cast<std::size_t>(raw_capacity % 8U) + 1U;
          std::vector<std::size_t> order(capacity + 1U);
          for (std::size_t index = 0; index < order.size(); ++index) {
            order[index] = order.size() - 1U - index;
          }
          cpu_prefetch::queue::LinkedSpscQueue queue(
              cpu_prefetch::queue::QueueCapacity{capacity}, kSyntheticCacheLine, order);
          cpu_prefetch::queue::LinkedQueueAdapter adapter(queue);
          check_queue_model(adapter, capacity, actions);
          RC_ASSERT(queue.audit_quiescent().every_node_owned_once);
        });
    return framework_passed && exact_integer_passed && ring_model_passed &&
                   linked_model_passed
               ? 0
               : 1;
  } catch (const std::exception& error) {
    std::cerr << "RapidCheck smoke test failed with exception: " << error.what()
              << '\n';
  } catch (...) {
    std::cerr << "RapidCheck smoke test failed with an unknown exception\n";
  }
  return 2;
}
