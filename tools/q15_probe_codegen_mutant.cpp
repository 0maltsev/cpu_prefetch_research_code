#include <immintrin.h>

#include <cstddef>
#include <cstdint>

extern "C" [[gnu::noinline]] auto cpu_prefetch_q15_regular_counted_traversal_mutant(
    const std::byte* buffer, std::size_t line_count) noexcept -> std::uint64_t {
  std::uint64_t observed = 0U;
#if defined(__clang__)
#pragma clang loop unroll(disable)
#elif defined(__GNUC__)
#pragma GCC unroll 1
#endif
  for (std::size_t line = 0U; line < line_count; ++line) {
    const auto* first =
        reinterpret_cast<const volatile std::uint64_t*>(buffer + (line * 64U));
    const auto* second =
        reinterpret_cast<const volatile std::uint64_t*>(buffer + (line * 64U) + 8U);
    observed ^= *first;
    observed ^= *second;
  }
  return observed;
}

extern "C" [[gnu::noinline]] auto cpu_prefetch_q15_pointer_counted_traversal_mutant(
    std::size_t line_count, const std::byte* buffer, std::uint32_t start_index) noexcept
    -> std::uint32_t {
  auto current = start_index;
#if defined(__clang__)
#pragma clang loop unroll(disable)
#elif defined(__GNUC__)
#pragma GCC unroll 1
#endif
  for (std::size_t load = 0U; load < line_count; ++load) {
    const auto* address = buffer + (static_cast<std::size_t>(current) * 64U);
    _mm_prefetch(reinterpret_cast<const char*>(address), _MM_HINT_T0);
    current = *reinterpret_cast<const volatile std::uint32_t*>(address);
  }
  return current;
}

int main() { return 0; }
