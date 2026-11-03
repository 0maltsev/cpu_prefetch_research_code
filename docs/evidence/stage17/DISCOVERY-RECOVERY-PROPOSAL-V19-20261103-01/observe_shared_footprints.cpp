// Cold metadata observation only: constructs storage, never runs queue operations.
// Cache capacities are explicit caller inputs, never detected or invented here.
#include "cpu_prefetch/queue/linked_spsc.hpp"
#include "cpu_prefetch/queue/ring_spsc.hpp"
#include "cpu_prefetch/workload/working_set.hpp"
#include <cstdint>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

int main(int argc, char** argv) {
  if (argc != 5) return 2;
  const auto line = std::stoull(argv[1]);
  const auto page = std::stoull(argv[2]);
  const auto l2 = std::stoull(argv[3]);
  const auto llc = std::stoull(argv[4]);
  using namespace cpu_prefetch;
  std::vector<workload::SharedFootprintCandidate> candidates;
  const auto seed = workload::MasterSeed::from_hex(std::string(64, '0'));
  std::cout << "{\"scope\":\"COLD_ALLOCATED_STORAGE_METADATA_NO_QUEUE_OPERATIONS\","
               "\"execution_authority\":false,\"cache_inputs_are_caller_supplied\":true,"
               "\"cache_line_bytes\":" << line << ",\"page_bytes\":" << page
            << ",\"l2_input_bytes\":" << l2 << ",\"llc_input_bytes\":" << llc
            << ",\"candidates\":[";
  bool comma = false;
  for (std::size_t capacity = 1; capacity <= 2'097'152; capacity *= 2) {
    workload::EventArena arena({capacity, line, page, seed,
                               "FOOTPRINT-METADATA-NOT-EXPERIMENT"});
    queue::RingSpscQueue ring({capacity}, {line});
    std::vector<std::size_t> order(capacity + 1);
    std::iota(order.begin(), order.end(), std::size_t{0});
    queue::LinkedSpscQueue linked({capacity}, {line}, {page}, order);
    const auto r = ring.layout_evidence();
    const auto l = linked.layout_evidence();
    const auto a = arena.layout();
    if (!(r.bases_aligned && l.bases_aligned && r.ownership_lines_separated &&
          l.ownership_lines_separated && a.base_page_aligned &&
          a.every_record_line_aligned)) return 3;
    const auto candidate = workload::make_shared_footprint_candidate(
        capacity, a.allocated_bytes, r.storage_bytes, l.storage_bytes);
    candidates.push_back(candidate);
    if (comma) std::cout << ',';
    comma = true;
    std::cout << "{\"capacity\":" << capacity << ",\"event_arena_bytes\":"
              << a.allocated_bytes << ",\"ring_queue_bytes\":" << r.storage_bytes
              << ",\"linked_queue_bytes\":" << l.storage_bytes
              << ",\"ring_full_bytes\":" << candidate.ring_bytes
              << ",\"linked_full_bytes\":" << candidate.linked_bytes << '}';
  }
  std::cout << "],\"conditional_selected\":[";
  comma = false;
  for (auto kind : {protocol::WorkingSetClass::l2_resident,
                    protocol::WorkingSetClass::llc_resident,
                    protocol::WorkingSetClass::beyond_llc}) {
    auto chosen = workload::select_common_capacity(kind, {line, l2, llc}, candidates);
    if (comma) std::cout << ',';
    comma = true;
    std::cout << chosen.selected.capacity;
  }
  std::cout << "]}\n";
}
