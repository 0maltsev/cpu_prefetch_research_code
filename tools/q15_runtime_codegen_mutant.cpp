#include "cpu_prefetch/platform/q15_runtime.hpp"

#include <cstddef>

extern "C" [[gnu::noinline]] auto cpu_prefetch_q15_regular_counted_region_mutant(
    cpu_prefetch::platform::Q15PerfOperations* operations, int descriptor,
    const std::byte* buffer, std::size_t line_count) noexcept
    -> cpu_prefetch::platform::Q15CountedRegionResult {
  if (operations == nullptr || !operations->enable(descriptor)) {
    return {0U, false, false};
  }
  const auto first = cpu_prefetch::platform::cpu_prefetch_q15_regular_counted_traversal(
      buffer, line_count);
  const auto forbidden_retry =
      cpu_prefetch::platform::cpu_prefetch_q15_regular_counted_traversal(buffer,
                                                                         line_count);
  return {first ^ forbidden_retry, true, operations->disable(descriptor)};
}

extern "C" [[gnu::noinline]] auto cpu_prefetch_q15_pointer_counted_region_mutant(
    cpu_prefetch::platform::Q15PerfOperations* operations, int descriptor,
    const std::byte* buffer, std::size_t line_count, std::uint32_t start_index) noexcept
    -> cpu_prefetch::platform::Q15CountedRegionResult {
  if (operations == nullptr || !operations->enable(descriptor)) {
    return {0U, false, false};
  }
  __builtin_prefetch(buffer, 0, 3);
  const auto retention =
      cpu_prefetch::platform::cpu_prefetch_q15_pointer_counted_traversal(
          line_count, buffer, start_index);
  return {retention, true, operations->disable(descriptor)};
}

int main() { return 0; }
