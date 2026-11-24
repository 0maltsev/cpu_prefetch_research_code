#include "cpu_prefetch/platform/worker_stack.hpp"

#include <cerrno>
#include <sched.h>

namespace cpu_prefetch::platform {

auto start_mapped_worker(pthread_t& thread, std::span<std::byte> stack,
                         std::uint32_t cpu, void* (*entry)(void*), void* context,
                         WorkerThreadCalls& calls) noexcept -> bool {
  if (cpu >= CPU_SETSIZE || stack.empty() || entry == nullptr) {
    return false;
  }
  pthread_attr_t attributes;
  calls.attribute_init = ::pthread_attr_init(&attributes);
  if (*calls.attribute_init != 0) {
    return false;
  }
  calls.attribute_stack =
      ::pthread_attr_setstack(&attributes, stack.data(), stack.size());
  if (*calls.attribute_stack == 0) {
    calls.attribute_guard = ::pthread_attr_setguardsize(&attributes, 0U);
    if (*calls.attribute_guard == 0) {
      cpu_set_t affinity;
      CPU_ZERO(&affinity);
      CPU_SET(cpu, &affinity);
      calls.attribute_affinity =
          ::pthread_attr_setaffinity_np(&attributes, sizeof(affinity), &affinity);
      if (*calls.attribute_affinity == 0) {
        calls.create = ::pthread_create(&thread, &attributes, entry, context);
      }
    }
  }
  calls.attribute_destroy = ::pthread_attr_destroy(&attributes);
  // A successful create must always be joined even if attribute cleanup failed.
  return calls.create.has_value() && *calls.create == 0;
}

} // namespace cpu_prefetch::platform
