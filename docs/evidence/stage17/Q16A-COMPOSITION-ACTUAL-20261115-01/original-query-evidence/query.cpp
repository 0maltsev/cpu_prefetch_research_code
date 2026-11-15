// Software-only arithmetic call into the source-bound dd981b4 queue implementation.
// No queue construction, operations, allocation, clock, affinity or hardware probe.
#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/queue/ring_spsc.hpp"
#include <charconv>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <sys/resource.h>
namespace {
auto number(const char* s) -> std::size_t {
  const std::string_view text(s);std::size_t result{};
  const auto parsed=std::from_chars(text.data(),text.data()+text.size(),result);
  if(parsed.ec!=std::errc{} || parsed.ptr!=text.data()+text.size() || result==0)
    throw std::invalid_argument("explicit positive integer required");
  return result;
}
}
int main(int argc,char** argv) {
 try {
  const rlimit memory{1024U*1024U*1024U,1024U*1024U*1024U};
  const rlimit cpu{10U,10U};
  if(setrlimit(RLIMIT_AS,&memory)!=0 || setrlimit(RLIMIT_CPU,&cpu)!=0)
    throw std::runtime_error("software bounds failed");
  if(argc!=8)throw std::invalid_argument("usage: native_geometry CACHE_LINE C0 C1 C2 C3 C4 C5");
  const auto line=number(argv[1]);
  const auto info=cpu_prefetch::foundation::repository_info();
  std::cout<<"{\"schema_version\":\"software-native-ring-slot-geometry/1\",\"source_revision\":\""
           <<info.source_revision<<"\",\"source_dirty\":"<<(info.source_dirty?"true":"false")
           <<",\"api\":\"RingSpscQueue::storage_requirements\",\"hardware_observation\":false,\"execution_authority\":false,\"records\":[";
  for(int i=0;i<6;++i){
   const auto capacity=number(argv[i+2]);
   const auto storage=cpu_prefetch::queue::RingSpscQueue::storage_requirements({capacity},{line});
   if(i!=0)std::cout<<',';
   std::cout<<"{\"context_ordinal\":"<<i<<",\"capacity\":"<<capacity
            <<",\"cache_line_bytes\":"<<line<<",\"slot_storage_bytes\":"<<storage.slot_bytes
            <<",\"cursor_storage_bytes\":"<<storage.cursor_bytes<<'}';
  }
  std::cout<<"]}\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
