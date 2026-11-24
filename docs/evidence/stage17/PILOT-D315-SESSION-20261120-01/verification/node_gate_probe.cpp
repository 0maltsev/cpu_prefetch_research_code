#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/workload/working_set.hpp"
#include <fstream>
#include <iostream>
int main() {
 using namespace cpu_prefetch;
 std::ifstream f("config/stage17/d310-s180-blueprint-v1.json");
 std::string raw((std::istreambuf_iterator<char>(f)),{});
 auto j=protocol::json::parse(raw);
 if (!j || !j.value().as_object())return 2;
 const auto& d=*j.value().as_object();
 const auto seed=workload::MasterSeed::from_hex(*d.at("master_seed_hex").as_string());
 const auto& rows=*d.at("captures").as_array();
 std::cout<<"{\"scope\":\"DETERMINISTIC_SOFTWARE_PLANNING_ONLY\",\"contexts\":[";
 bool first=true;
 for (std::size_t ctx=0;ctx<6;++ctx) {
   const auto& row=*rows[(ctx<3 ? 0:9)+(ctx%3)*3].as_object();
   const auto& g=*row.at("requested_geometry").as_object();
   auto n=[&](const char* k){return static_cast<std::size_t>(std::get<std::uint64_t>(g.at(k).as_number()->value));};
   workload::NodeOrderPlan p({n("capacity"),n("cache_line_bytes"),n("cache_line_bytes"),n("base_page_bytes")},seed,*row.at("node_order_namespace").as_string());
   const auto& s=p.summary();
   if (!first)std::cout<<",";first=false;
   std::cout<<"{\"context\":"<<ctx<<",\"capacity\":"<<n("capacity")
      <<",\"distinct_lines\":"<<s.distinct_line_count<<",\"distinct_pages\":"<<s.distinct_page_count
      <<",\"shortest_period\":"<<s.shortest_period
      <<",\"ordered_index_sha256\":\""<<p.ordered_index_checksum().hex()<<"\",\"address_delta_sha256\":\""<<p.address_delta_checksum().hex()<<"\""
      <<",\"adjacent_count\":"<<s.adjacent_line_transition_count
      <<",\"modal_count\":"<<s.modal_nonzero_delta_count<<",\"transitions\":"<<s.transition_count
      <<",\"adjacent_gate\":"<<(s.adjacent_fraction_at_most_one_percent ? "true":"false")
      <<",\"modal_gate\":"<<(s.modal_fraction_at_most_one_percent ? "true":"false")<<"}";
 }
 std::cout<<"],\"stand_accessed\":false,\"experimental_observations\":0}\n";
}
