#include "cpu_prefetch/timing/cross_core_exchange.hpp"

namespace cpu_prefetch::timing {

auto CrossCoreExchangeSlot::atomic_lock_free_evidence() const noexcept
    -> queue::AtomicLockFreeEvidence {
  return {sizeof(const void*), sizeof(std::atomic<std::uint64_t>),
          alignof(std::atomic<std::uint64_t>),
          std::atomic<std::uint64_t>::is_always_lock_free,
          sequence_.is_lock_free() && first_.is_lock_free() && second_.is_lock_free()};
}

} // namespace cpu_prefetch::timing
