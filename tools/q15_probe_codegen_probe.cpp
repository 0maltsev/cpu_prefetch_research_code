#include "cpu_prefetch/platform/q15_probe.hpp"

#include <array>
#include <cstddef>

namespace {

alignas(4096) std::array<std::byte, std::size_t{8U} * 64U> buffer{};

} // namespace

int main() {
  const auto regular =
      cpu_prefetch::platform::cpu_prefetch_q15_regular_counted_traversal(buffer.data(),
                                                                         8U);
  const auto pointer =
      cpu_prefetch::platform::cpu_prefetch_q15_pointer_counted_traversal(
          8U, buffer.data(), 0U);
  return regular == pointer ? 0 : 1;
}
