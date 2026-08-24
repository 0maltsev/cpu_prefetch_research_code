#include "cpu_prefetch/platform/q15_runtime.hpp"

#include <array>
#include <cstddef>

namespace {

class CodegenPerf final : public cpu_prefetch::platform::Q15PerfOperations {
public:
  [[nodiscard]] auto open_event(const cpu_prefetch::platform::Q15PerfEventRequest&)
      -> cpu_prefetch::platform::Result<int> override {
    return cpu_prefetch::platform::Result<int>::success(3);
  }
  [[nodiscard]] auto reset(int) noexcept -> bool override { return true; }
  [[nodiscard]] auto enable(int) noexcept -> bool override { return true; }
  [[nodiscard]] auto disable(int) noexcept -> bool override { return true; }
  [[nodiscard]] auto read(int) -> cpu_prefetch::platform::Result<
      cpu_prefetch::platform::Q15CounterReading> override {
    return cpu_prefetch::platform::Result<
        cpu_prefetch::platform::Q15CounterReading>::success({1U, 1U, 1U});
  }
  [[nodiscard]] auto close(int) noexcept -> bool override { return true; }
};

alignas(4096) std::array<std::byte, std::size_t{8U} * 64U> buffer{};

} // namespace

int main() {
  CodegenPerf perf;
  const auto regular = cpu_prefetch::platform::cpu_prefetch_q15_regular_counted_region(
      &perf, 3, buffer.data(), 8U);
  const auto pointer = cpu_prefetch::platform::cpu_prefetch_q15_pointer_counted_region(
      &perf, 3, buffer.data(), 8U, 0U);
  return regular.enabled && regular.disabled && pointer.enabled && pointer.disabled ? 0
                                                                                    : 1;
}
