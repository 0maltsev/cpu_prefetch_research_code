#ifndef CPU_PREFETCH_RUNNER_SOFTWARE_PREFETCH_HPP
#define CPU_PREFETCH_RUNNER_SOFTWARE_PREFETCH_HPP

#include <cstdint>
#include <string_view>

#if !defined(__linux__) || !defined(__x86_64__)
#error "D-047 software prefetch mapping requires the accepted Linux x86-64 target"
#endif

namespace cpu_prefetch::runner {

inline constexpr std::string_view kSoftwarePrefetchMappingId =
    "X86-64-PREFETCHW-PREFETCHT0-v1";
inline constexpr std::uint32_t kPrfchwExtendedLeaf = 0x80000001U;
inline constexpr std::uint32_t kPrfchwEcxBit = 8U;
inline constexpr std::uint32_t kPrfchwEcxMask = 1U << kPrfchwEcxBit;

struct SoftwarePrefetchCapabilityObservation final {
  std::uint32_t maximum_extended_leaf;
  std::uint32_t extended_leaf_ecx;
  bool prfchw_supported;

  [[nodiscard]] auto passes() const noexcept -> bool {
    return maximum_extended_leaf >= kPrfchwExtendedLeaf &&
           (extended_leaf_ecx & kPrfchwEcxMask) != 0U && prfchw_supported;
  }
};

class CurrentCpuSoftwarePrefetchCapabilityBackend {
public:
  virtual ~CurrentCpuSoftwarePrefetchCapabilityBackend() = default;
  [[nodiscard]] virtual auto observe() noexcept
      -> SoftwarePrefetchCapabilityObservation = 0;
};

class X86CurrentCpuSoftwarePrefetchCapabilityBackend final
    : public CurrentCpuSoftwarePrefetchCapabilityBackend {
public:
  [[nodiscard]] auto observe() noexcept
      -> SoftwarePrefetchCapabilityObservation override;
};

// D-047 fixes the physical Stage A mapping. The explicit GNU-style asm keeps
// GCC 16 and Clang 22 from lowering a write-intent builtin to PREFETCHT0 when
// the translation unit has no global PRFCHW target flag. No memory clobber is
// used: the hint is not a compiler fence. The complete release call graph is
// nevertheless required to preserve each registered site and exact count.
class X86RetainingPrefetchEmitter final {
public:
  inline void ring_producer_write(const void* address) const noexcept {
    asm volatile("prefetchw %0" : : "m"(*static_cast<const char*>(address)));
  }

  inline void ring_consumer_read(const void* address) const noexcept {
    asm volatile("prefetcht0 %0" : : "m"(*static_cast<const char*>(address)));
  }

  inline void successor_header(const void* address) const noexcept {
    asm volatile("prefetcht0 %0" : : "m"(*static_cast<const char*>(address)));
  }
};

} // namespace cpu_prefetch::runner

#endif // CPU_PREFETCH_RUNNER_SOFTWARE_PREFETCH_HPP
