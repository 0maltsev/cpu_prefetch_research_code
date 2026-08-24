#include "cpu_prefetch/platform/q15_runtime.hpp"

namespace cpu_prefetch::platform {

extern "C" [[gnu::noinline]] auto cpu_prefetch_q15_regular_counted_region(
    Q15PerfOperations* operations, int descriptor, const std::byte* buffer,
    std::size_t line_count) noexcept -> Q15CountedRegionResult {
  if (operations == nullptr || !operations->enable(descriptor)) {
    return {0U, false, false};
  }
  const auto retention = cpu_prefetch_q15_regular_counted_traversal(buffer, line_count);
  return {retention, true, operations->disable(descriptor)};
}

extern "C" [[gnu::noinline]] auto
cpu_prefetch_q15_pointer_counted_region(Q15PerfOperations* operations, int descriptor,
                                        const std::byte* buffer, std::size_t line_count,
                                        std::uint32_t start_index) noexcept
    -> Q15CountedRegionResult {
  if (operations == nullptr || !operations->enable(descriptor)) {
    return {0U, false, false};
  }
  const auto retention =
      cpu_prefetch_q15_pointer_counted_traversal(line_count, buffer, start_index);
  return {retention, true, operations->disable(descriptor)};
}

} // namespace cpu_prefetch::platform
