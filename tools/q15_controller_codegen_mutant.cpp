#include "cpu_prefetch/qualification/q15_controller.hpp"

#include <cstddef>

extern "C" [[gnu::noinline]] auto cpu_prefetch_q15_controller_retry_mutant(
    cpu_prefetch::qualification::Q15RControllerOperations* operations,
    const cpu_prefetch::qualification::Q15RControllerTicket* ticket) -> std::size_t {
  if (operations == nullptr || ticket == nullptr) {
    return 0U;
  }
  std::size_t completed = 0U;
  for (const auto step : cpu_prefetch::qualification::kQ15RControllerGraph) {
    auto result = operations->run_step(step, *ticket);
    if (!result) {
      result = operations->run_step(step, *ticket); // forbidden hidden retry
    }
    if (!result) {
      return completed;
    }
    ++completed;
  }
  return completed;
}

int main() { return 0; }
