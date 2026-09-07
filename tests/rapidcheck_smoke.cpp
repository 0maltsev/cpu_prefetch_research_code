#include <rapidcheck.h>

#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/queue/adapters.hpp"
#include "cpu_prefetch/reconciliation/reconciliation.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

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
constexpr cpu_prefetch::queue::ArenaAlignmentBytes kSyntheticPage{4096U};

cpu_prefetch::queue::EventPointer required_event_pointer(const void* pointer) {
  const auto event = cpu_prefetch::queue::EventPointer::from(pointer);
  if (!event.has_value()) {
    throw std::logic_error("non-null generated event pointer was rejected");
  }
  return event.value();
}

template <typename Adapter>
// Capacity and action history are intentionally adjacent model inputs.
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
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
              cpu_prefetch::queue::QueueCapacity{capacity}, kSyntheticCacheLine,
              kSyntheticPage, order);
          cpu_prefetch::queue::LinkedQueueAdapter adapter(queue);
          check_queue_model(adapter, capacity, actions);
          RC_ASSERT(queue.audit_quiescent().every_node_owned_once);
        });
    const bool permutation_passed = rc::check(
        "Philox rejection shuffle is a deterministic bijection",
        [](std::uint8_t raw_exponent, std::uint64_t key_material) {
          const auto exponent = static_cast<unsigned int>(raw_exponent % 9U);
          const auto count = static_cast<std::size_t>(1U) << exponent;
          const cpu_prefetch::workload::PhiloxKey key{
              {static_cast<std::uint32_t>(key_material >> 32U),
               static_cast<std::uint32_t>(key_material)}};
          const cpu_prefetch::workload::DeterministicStream stream(key);
          const auto first = cpu_prefetch::workload::make_permutation(count, stream);
          const auto second = cpu_prefetch::workload::make_permutation(count, stream);
          RC_ASSERT(first == second);
          auto sorted = first;
          std::ranges::sort(sorted);
          for (std::size_t index = 0; index < sorted.size(); ++index) {
            RC_ASSERT(sorted[index] == index);
          }
        });
    const bool reconciliation_passed = rc::check(
        "exact accepted-ordinal reconciliation refines generated producer histories",
        [](const std::vector<std::uint8_t>& generated) {
          const auto parsed =
              cpu_prefetch::protocol::RunId::parse("property-run", "$property/run_id");
          RC_ASSERT(parsed.has_value());
          const auto& id = parsed.value();
          const auto count = std::min<std::size_t>(generated.size(), 128U);
          std::vector<std::uint64_t> mapping;
          std::vector<cpu_prefetch::protocol::ProducerRecord> producers;
          std::vector<cpu_prefetch::protocol::ConsumerRecord> consumers;
          mapping.reserve(count);
          producers.reserve(count);
          consumers.reserve(count);
          std::uint64_t accepted_ordinal = 0U;
          for (std::size_t index = 0U; index < count; ++index) {
            const auto logical = static_cast<std::uint64_t>(index);
            const auto record_index = static_cast<std::uint64_t>(generated[index] % 8U);
            const auto base = 1000U + logical * 100U;
            const bool accepted = (generated[index] & 1U) == 0U;
            mapping.push_back(record_index);
            producers.push_back(
                {id, logical, record_index, base, base + 1U, base + 2U, base + 3U,
                 accepted ? std::optional<std::uint64_t>(base + 4U) : std::nullopt,
                 base + 5U,
                 accepted ? cpu_prefetch::protocol::ProducerOutcome::accepted
                          : cpu_prefetch::protocol::ProducerOutcome::full,
                 accepted ? std::optional<std::uint64_t>(accepted_ordinal)
                          : std::nullopt});
            if (accepted) {
              consumers.push_back({id, accepted_ordinal, record_index, base + 6U,
                                   base + 7U, base + 8U, base + 9U});
              ++accepted_ordinal;
            }
          }
          const auto joined = cpu_prefetch::reconciliation::reconcile(
              id, producers, consumers, mapping);
          RC_ASSERT(joined.status == cpu_prefetch::protocol::JoinStatus::passed);
          RC_ASSERT(joined.joined_rows.size() == consumers.size());
          if (!consumers.empty()) {
            consumers.back().consumed_ordinal = accepted_ordinal;
            const auto corrupted = cpu_prefetch::reconciliation::reconcile(
                id, producers, consumers, mapping);
            RC_ASSERT(corrupted.status == cpu_prefetch::protocol::JoinStatus::failed);
            RC_ASSERT(corrupted.joined_rows.empty());
          }
        });
    return framework_passed && exact_integer_passed && ring_model_passed &&
                   linked_model_passed && permutation_passed && reconciliation_passed
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
