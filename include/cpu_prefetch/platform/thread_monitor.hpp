#ifndef CPU_PREFETCH_PLATFORM_THREAD_MONITOR_HPP
#define CPU_PREFETCH_PLATFORM_THREAD_MONITOR_HPP

#include "cpu_prefetch/platform/owner_mapping.hpp"

#include <array>
#include <optional>
#include <span>
#include <string_view>

namespace cpu_prefetch::platform {

struct ThreadStatObservation final {
  int task_id;
  char state;
  std::uint64_t start_time_ticks;
  std::uint64_t minor_faults;
  std::uint64_t major_faults;
  int last_cpu; // proc stat processor field: last executed CPU, not sched_getcpu().
};

struct ThreadStatusObservation final {
  int task_id;
  int thread_group_id;
  std::uint64_t voluntary_context_switches;
  std::uint64_t involuntary_context_switches;
};

// Strict, allocation-free parsers. Input must contain the complete file,
// including its final newline. Malformed/absent/duplicate required fields fail.
[[nodiscard]] auto parse_thread_stat(std::string_view text) noexcept
    -> std::optional<ThreadStatObservation>;
[[nodiscard]] auto parse_thread_status(std::string_view text) noexcept
    -> std::optional<ThreadStatusObservation>;

// A narrow syscall seam for native execution and deterministic failure tests.
// Implementations must not allocate or retry in read_at_start/read_at_end/affinity.
class ThreadMonitorOperations {
public:
  virtual ~ThreadMonitorOperations() = default;
  [[nodiscard]] virtual auto open_task(int task_id) noexcept -> LinuxCallResult = 0;
  [[nodiscard]] virtual auto open_file(int directory, bool status) noexcept
      -> LinuxCallResult = 0;
  [[nodiscard]] virtual auto read_at_start(int descriptor,
                                           std::span<char> bytes) noexcept
      -> LinuxCallResult = 0;
  [[nodiscard]] virtual auto read_at_end(int descriptor, std::size_t offset,
                                         char& byte) noexcept -> LinuxCallResult = 0;
  // Native raw sched_getaffinity return is the number of mask bytes written.
  [[nodiscard]] virtual auto affinity(int task_id,
                                      std::span<unsigned long> mask) noexcept
      -> LinuxCallResult = 0;
  [[nodiscard]] virtual auto close_file(int descriptor) noexcept -> LinuxCallResult = 0;
};

class LinuxThreadMonitorOperations final : public ThreadMonitorOperations {
public:
  [[nodiscard]] auto open_task(int task_id) noexcept -> LinuxCallResult override;
  [[nodiscard]] auto open_file(int directory, bool status) noexcept
      -> LinuxCallResult override;
  [[nodiscard]] auto read_at_start(int descriptor, std::span<char> bytes) noexcept
      -> LinuxCallResult override;
  [[nodiscard]] auto read_at_end(int descriptor, std::size_t offset,
                                 char& byte) noexcept -> LinuxCallResult override;
  [[nodiscard]] auto affinity(int task_id, std::span<unsigned long> mask) noexcept
      -> LinuxCallResult override;
  [[nodiscard]] auto close_file(int descriptor) noexcept -> LinuxCallResult override;
};

struct ThreadMonitorScratch final {
  std::span<char> stat_before;
  std::span<char> status;
  std::span<char> stat_after;
  std::span<unsigned long> affinity;
};

struct ThreadFileRead final {
  std::optional<LinuxCallResult> read;
  std::optional<LinuxCallResult> end_probe;
  char end_probe_byte{};
  bool complete{false};
};

enum class ThreadMonitorStop : std::uint8_t {
  not_prepared,
  invalid_scratch,
  file_read_failure,
  parse_failure,
  identity_changed,
  task_exited,
  affinity_failure,
  sampled,
};

struct ThreadControlSample final {
  ThreadFileRead stat_before_read;
  ThreadFileRead status_read;
  ThreadFileRead stat_after_read;
  std::optional<ThreadStatObservation> stat_before;
  std::optional<ThreadStatusObservation> status;
  std::optional<ThreadStatObservation> stat_after;
  std::optional<LinuxCallResult> affinity_call;
  std::span<const unsigned long> affinity_mask;
  std::optional<std::size_t> affinity_cpu_count;
  std::optional<std::size_t> singleton_affinity_cpu;
  ThreadMonitorStop stop{ThreadMonitorStop::not_prepared};
  [[nodiscard]] auto succeeded() const noexcept -> bool {
    return stop == ThreadMonitorStop::sampled;
  }
};

struct ThreadMonitorPreparation final {
  int requested_task_id{};
  bool attempted{false};
  bool ready{false};
  std::optional<LinuxCallResult> directory_open;
  std::optional<LinuxCallResult> stat_open;
  std::optional<LinuxCallResult> status_open;
  ThreadControlSample initial;
  // stat, status, directory, in that order. Linux close is never retried.
  std::array<std::optional<LinuxCallResult>, 3U> closes;
};

// Cold, one-shot binding to /proc/self/task/<explicit-positive-TID>. Keeping
// procfs FDs anchors the task; they never switch to a reused numeric TID.
// Caller holds the intended worker alive through prepare(); a bare TID cannot
// identify a task that already exited/reused that number before binding.
// Each sample brackets status/affinity with reads of that anchored stat FD.
// No sample is atomic. A successful sample does NOT prove continuous CPU
// residency, absence of migrations/faults, or compliance with any threshold.
//
// Controller-only, serialized calls. Caller prepares/prefaults scratch and
// retains distinct scratch per required sample (including preparation). The
// returned mask borrows that scratch; raw file bytes remain there as evidence.
// No allocation, file opens, sleeps, retries, thresholds or scheduling occurs
// in sample(). Each file uses one pread and at most one one-byte EOF probe;
// partial/filled buffers fail rather than being extended or retried. Syscalls
// have bounded counts, not guaranteed wall time; the controller must bracket
// time and enforce its separately admitted deadline/watchdog and observation
// schedule, including before/during/after samples. Worker loops do no I/O here.
class PreparedThreadMonitor final {
public:
  explicit PreparedThreadMonitor(ThreadMonitorOperations& operations) noexcept
      : operations_(operations) {}
  ~PreparedThreadMonitor();
  PreparedThreadMonitor(const PreparedThreadMonitor&) = delete;
  auto operator=(const PreparedThreadMonitor&) -> PreparedThreadMonitor& = delete;
  PreparedThreadMonitor(PreparedThreadMonitor&&) = delete;
  auto operator=(PreparedThreadMonitor&&) -> PreparedThreadMonitor& = delete;

  [[nodiscard]] auto prepare(int task_id, ThreadMonitorScratch scratch) noexcept
      -> bool;
  [[nodiscard]] auto sample(ThreadMonitorScratch scratch) noexcept
      -> ThreadControlSample;
  void release() noexcept;
  [[nodiscard]] auto preparation() const noexcept -> const ThreadMonitorPreparation& {
    return preparation_;
  }

private:
  [[nodiscard]] auto observe(ThreadMonitorScratch scratch) noexcept
      -> ThreadControlSample;
  ThreadMonitorOperations& operations_;
  ThreadMonitorPreparation preparation_{};
  std::array<int, 3U> descriptors_{-1, -1, -1};
};

} // namespace cpu_prefetch::platform

#endif
