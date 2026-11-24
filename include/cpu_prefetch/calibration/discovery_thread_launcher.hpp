#ifndef CPU_PREFETCH_CALIBRATION_DISCOVERY_THREAD_LAUNCHER_HPP
#define CPU_PREFETCH_CALIBRATION_DISCOVERY_THREAD_LAUNCHER_HPP

#include "cpu_prefetch/calibration/calibration.hpp"
#include "cpu_prefetch/platform/worker_stack.hpp"

#include <array>
#include <thread>

namespace cpu_prefetch::calibration {

// Compatibility launcher for software verification; supplies no placement evidence.
class StandardDiscoveryThreads final {
public:
  auto start(RingWorker role, platform::WorkerEntry entry, void* context) -> bool {
    threads_[role == RingWorker::producer ? 0U : 1U] =
        std::thread([entry, context] { entry(context); });
    return true;
  }
  auto prepared(RingWorker) const noexcept -> bool { return true; }
  void join() {
    for (auto& thread : threads_) {
      if (thread.joinable()) {
        thread.join();
      }
    }
  }

private:
  std::array<std::thread, 2U> threads_;
};

template <typename Operations> struct DiscoveryWorkerStacks final {
  platform::MappedWorkerThread<Operations>& producer;
  platform::MappedWorkerThread<Operations>& consumer;
};

template <typename Operations = platform::LinuxOwnerMemoryOperations>
class MappedDiscoveryThreads final {
public:
  explicit MappedDiscoveryThreads(DiscoveryWorkerStacks<Operations> stacks) noexcept
      : producer_(stacks.producer), consumer_(stacks.consumer) {}
  auto start(RingWorker role, platform::WorkerEntry entry, void* context) noexcept
      -> bool {
    return select(role).start(entry, context);
  }
  auto prepared(RingWorker role) noexcept -> bool { return select(role).prepared(); }
  void join() noexcept {
    producer_.join();
    consumer_.join();
  }

private:
  auto select(RingWorker role) noexcept -> platform::MappedWorkerThread<Operations>& {
    return role == RingWorker::producer ? producer_ : consumer_;
  }
  platform::MappedWorkerThread<Operations>& producer_;
  platform::MappedWorkerThread<Operations>& consumer_;
};

} // namespace cpu_prefetch::calibration

#endif
