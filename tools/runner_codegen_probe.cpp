#include "cpu_prefetch/runner/runner.hpp"

extern "C" [[gnu::noinline]] void cpu_prefetch_runner_relax_once() noexcept {
  cpu_prefetch::runner::X86PauseRelax{}.relax();
}

int main() {
  cpu_prefetch_runner_relax_once();
  return 0;
}
