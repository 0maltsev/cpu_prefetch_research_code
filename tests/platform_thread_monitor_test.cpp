#include "cpu_prefetch/platform/thread_monitor.hpp"
#include "worker_stack_test_support.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <limits>
#include <string>
#include <sys/syscall.h>
#include <thread>
#include <unistd.h>

namespace {

using namespace cpu_prefetch::platform;

struct Scratch final {
  std::array<char, 4096U> before{};
  std::array<char, 16384U> status{};
  std::array<char, 4096U> after{};
  std::array<unsigned long, 128U> mask{};
  auto view() noexcept -> ThreadMonitorScratch { return {before, status, after, mask}; }
};

auto stat_text(std::string_view command = "worker ) (x\ny)", std::uint64_t start = 456U)
    -> std::string {
  std::string text = "123 (" + std::string(command) + ") R";
  for (unsigned field = 4U; field <= 52U; ++field) {
    text += ' ';
    switch (field) {
    case 10U:
      text += "17";
      break;
    case 12U:
      text += "3";
      break;
    case 22U:
      text += std::to_string(start);
      break;
    case 39U:
      text += "7";
      break;
    default:
      text += "0";
      break;
    }
  }
  return text + '\n';
}

auto status_text() -> std::string {
  return "Name:\tworker\\n\nTgid:\t100\nPid:\t123\n"
         "voluntary_ctxt_switches:\t11\nnonvoluntary_ctxt_switches:\t22\n";
}

struct FakeOperations final : ThreadMonitorOperations {
  std::array<std::string, 2U> stats{stat_text(), stat_text()};
  std::string status{status_text()};
  std::size_t opens{0U};
  std::size_t reads{0U};
  std::size_t probes{0U};
  std::size_t stat_reads{0U};
  std::size_t affinity_calls{0U};
  std::size_t closes{0U};
  std::size_t fail_open{0U};
  std::size_t fail_read{0U};
  std::size_t fail_probe{0U};
  std::optional<std::size_t> limit;
  bool extra_probe_byte{false};
  std::optional<LinuxCallResult> affinity_return;
  LinuxCallResult close_return{0, 0};
  unsigned long mask{1UL << 7U};

  auto opened(int fd) noexcept -> LinuxCallResult {
    ++opens;
    return opens == fail_open ? LinuxCallResult{-1, EACCES} : LinuxCallResult{fd, 0};
  }
  auto open_task(int) noexcept -> LinuxCallResult override { return opened(10); }
  auto open_file(int, bool is_status) noexcept -> LinuxCallResult override {
    return opened(is_status ? 12 : 11);
  }
  auto read_at_start(int fd, std::span<char> bytes) noexcept
      -> LinuxCallResult override {
    ++reads;
    if (reads == fail_read) {
      return {-1, EINTR};
    }
    const auto& text = fd == 12 ? status : stats[(stat_reads++) % 2U];
    auto count = std::min(text.size(), bytes.size());
    if (limit.has_value()) {
      count = std::min(count, *limit);
    }
    std::copy_n(text.data(), count, bytes.data());
    return {static_cast<std::int64_t>(count), 0};
  }
  auto read_at_end(int, std::size_t, char& byte) noexcept -> LinuxCallResult override {
    ++probes;
    if (probes == fail_probe) {
      return {-1, EIO};
    }
    if (extra_probe_byte) {
      byte = 'x';
      return {1, 0};
    }
    return {0, 0};
  }
  auto affinity(int, std::span<unsigned long> words) noexcept
      -> LinuxCallResult override {
    ++affinity_calls;
    words.front() = mask;
    return affinity_return.value_or(LinuxCallResult{sizeof(unsigned long), 0});
  }
  auto close_file(int) noexcept -> LinuxCallResult override {
    ++closes;
    return close_return;
  }
};

TEST(ThreadMonitor, ParsesActualFieldPositionsAndArbitraryCommCharacters) {
  const auto stat = parse_thread_stat(stat_text());
  if (!stat.has_value()) {
    FAIL() << "missing parsed stat";
    return;
  }
  EXPECT_EQ(stat->task_id, 123);
  EXPECT_EQ(stat->start_time_ticks, 456U);
  EXPECT_EQ(stat->minor_faults, 17U);
  EXPECT_EQ(stat->major_faults, 3U);
  EXPECT_EQ(stat->last_cpu, 7);
  EXPECT_EQ(stat->state, 'R');
  const auto status = parse_thread_status(status_text());
  if (!status.has_value()) {
    FAIL() << "missing parsed status";
    return;
  }
  EXPECT_EQ(status->task_id, 123);
  EXPECT_EQ(status->thread_group_id, 100);
  EXPECT_EQ(status->voluntary_context_switches, 11U);
  EXPECT_EQ(status->involuntary_context_switches, 22U);
}

TEST(ThreadMonitor, RejectsMalformedTruncatedOverflowingAndDuplicateFields) {
  const auto valid = stat_text();
  for (std::size_t length = 0U; length < valid.size(); ++length) {
    EXPECT_FALSE(
        parse_thread_stat(std::string_view(valid).substr(0U, length)).has_value());
  }
  auto bad = valid;
  bad.replace(bad.find(" 17 "), 4U, " -1 ");
  EXPECT_FALSE(parse_thread_stat(bad).has_value());
  bad = valid;
  bad.replace(bad.find(" 456 "), 5U, " 18446744073709551616 ");
  EXPECT_FALSE(parse_thread_stat(bad).has_value());
  bad = valid;
  bad.replace(bad.find(" 7 "), 3U, " 2147483648 ");
  EXPECT_FALSE(parse_thread_stat(bad).has_value());
  bad = valid;
  bad.back() = '\0';
  EXPECT_FALSE(parse_thread_stat(bad).has_value());
  EXPECT_FALSE(parse_thread_stat("123 (x) ? 0\n").has_value());
  EXPECT_FALSE(parse_thread_stat("-1 (x) R 0\n").has_value());
  EXPECT_FALSE(parse_thread_status(status_text() + "Pid:\t123\n").has_value());
  EXPECT_FALSE(parse_thread_status("Pid:\t123\nTgid:\t100\n").has_value());
  EXPECT_FALSE(parse_thread_status(status_text() + "Pid:\t-1\n").has_value());
  auto overflowing = status_text();
  overflowing.replace(overflowing.find("22"), 2U, "18446744073709551616");
  EXPECT_FALSE(parse_thread_status(overflowing).has_value());
  auto incomplete = status_text();
  incomplete.pop_back();
  EXPECT_FALSE(parse_thread_status(incomplete).has_value());
}

TEST(ThreadMonitor, RetainsSeparateSamplesAndClosesDescriptorsExactlyOnce) {
  FakeOperations operations;
  Scratch preparation;
  std::array<Scratch, 3U> retained;
  PreparedThreadMonitor monitor(operations);
  ASSERT_TRUE(monitor.prepare(123, preparation.view()));
  EXPECT_FALSE(monitor.prepare(123, preparation.view()));
  std::array<ThreadControlSample, 3U> samples;
  for (std::size_t index = 0U; index < samples.size(); ++index) {
    operations.mask = 1UL << (index + 1U);
    samples[index] = monitor.sample(retained[index].view());
    const auto& sample = samples[index];
    ASSERT_TRUE(sample.succeeded());
    if (!sample.stat_before.has_value() || !sample.stat_after.has_value()) {
      FAIL() << "missing retained stat observations";
      return;
    }
    EXPECT_EQ(sample.singleton_affinity_cpu, index + 1U);
    EXPECT_EQ(sample.stat_before->last_cpu, 7);
    EXPECT_EQ(sample.stat_after->start_time_ticks, 456U);
  }
  EXPECT_EQ(samples[0].affinity_mask[0], 2UL);
  EXPECT_EQ(samples[1].affinity_mask[0], 4UL);
  EXPECT_EQ(samples[2].affinity_mask[0], 8UL);
  EXPECT_EQ(monitor.preparation().initial.affinity_mask[0], 128UL);
  EXPECT_EQ(operations.opens, 3U);
  EXPECT_EQ(operations.reads, 12U);
  EXPECT_EQ(operations.probes, 12U);
  EXPECT_EQ(operations.affinity_calls, 4U);
  monitor.release();
  monitor.release();
  EXPECT_EQ(operations.closes, 3U);
  for (const auto& closed : monitor.preparation().closes) {
    if (!closed.has_value()) {
      FAIL() << "missing close observation";
      return;
    }
    EXPECT_TRUE(closed->zero_return());
  }
  EXPECT_EQ(monitor.sample(retained[0].view()).stop, ThreadMonitorStop::not_prepared);
}

TEST(ThreadMonitor, RejectsImplicitTidInvalidScratchAndOverlapsBeforeAnyIo) {
  for (const int tid : {0, -1}) {
    FakeOperations operations;
    Scratch scratch;
    PreparedThreadMonitor monitor(operations);
    EXPECT_FALSE(monitor.prepare(tid, scratch.view()));
    EXPECT_EQ(operations.opens, 0U);
  }
  FakeOperations operations;
  Scratch scratch;
  PreparedThreadMonitor monitor(operations);
  ASSERT_TRUE(monitor.prepare(123, scratch.view()));
  const auto reads = operations.reads;
  auto invalid = scratch.view();
  invalid.status = invalid.stat_before.subspan(1U);
  EXPECT_EQ(monitor.sample(invalid).stop, ThreadMonitorStop::invalid_scratch);
  invalid = scratch.view();
  invalid.affinity = {};
  EXPECT_EQ(monitor.sample(invalid).stop, ThreadMonitorStop::invalid_scratch);
  EXPECT_EQ(operations.reads, reads);
}

TEST(ThreadMonitor, RetainsOpenFailuresAndCleansOnlyOpenedHandles) {
  for (std::size_t failed = 1U; failed <= 3U; ++failed) {
    FakeOperations operations;
    operations.fail_open = failed;
    Scratch scratch;
    PreparedThreadMonitor monitor(operations);
    EXPECT_FALSE(monitor.prepare(123, scratch.view()));
    const auto& evidence = monitor.preparation();
    const auto result =
        failed == 1U ? evidence.directory_open
                     : (failed == 2U ? evidence.stat_open : evidence.status_open);
    if (!result.has_value()) {
      FAIL() << "missing open observation";
      return;
    }
    EXPECT_EQ(result->return_value, -1);
    EXPECT_EQ(result->error_number, EACCES);
    EXPECT_EQ(operations.reads, 0U);
    monitor.release();
    EXPECT_EQ(operations.closes, failed - 1U);
  }
}

TEST(ThreadMonitor, RetainsEveryReadAndProbeFailureWithoutRetry) {
  for (std::size_t failed = 1U; failed <= 3U; ++failed) {
    for (const bool fail_probe : {false, true}) {
      FakeOperations operations;
      Scratch preparation;
      Scratch scratch;
      PreparedThreadMonitor monitor(operations);
      ASSERT_TRUE(monitor.prepare(123, preparation.view()));
      if (fail_probe) {
        operations.fail_probe = failed + 3U;
      } else {
        operations.fail_read = failed + 3U;
      }
      const auto sample = monitor.sample(scratch.view());
      EXPECT_EQ(sample.stop, ThreadMonitorStop::file_read_failure);
      const auto& read =
          failed == 1U ? sample.stat_before_read
                       : (failed == 2U ? sample.status_read : sample.stat_after_read);
      const auto result = fail_probe ? read.end_probe : read.read;
      if (!result.has_value()) {
        FAIL() << "missing read/probe observation";
        return;
      }
      EXPECT_EQ(result->return_value, -1);
      EXPECT_EQ(result->error_number, fail_probe ? EIO : EINTR);
      EXPECT_EQ(operations.reads, failed == 1U ? 4U : 6U);
      EXPECT_EQ(operations.affinity_calls, failed == 1U ? 1U : 2U);
    }
  }
}

TEST(ThreadMonitor, RejectsFullEmptyPartialAndUnterminatedReads) {
  FakeOperations operations;
  Scratch preparation;
  Scratch scratch;
  PreparedThreadMonitor monitor(operations);
  ASSERT_TRUE(monitor.prepare(123, preparation.view()));
  auto short_buffer = scratch.view();
  short_buffer.stat_before = short_buffer.stat_before.first(8U);
  EXPECT_EQ(monitor.sample(short_buffer).stop, ThreadMonitorStop::file_read_failure);
  short_buffer.stat_before =
      scratch.view().stat_before.first(operations.stats[0].size());
  EXPECT_EQ(monitor.sample(short_buffer).stop, ThreadMonitorStop::file_read_failure);
  operations.limit = 0U;
  EXPECT_EQ(monitor.sample(scratch.view()).stop, ThreadMonitorStop::file_read_failure);
  operations.limit.reset();
  operations.extra_probe_byte = true;
  auto sample = monitor.sample(scratch.view());
  EXPECT_EQ(sample.stop, ThreadMonitorStop::file_read_failure);
  if (!sample.stat_before_read.end_probe.has_value()) {
    FAIL() << "missing EOF probe observation";
    return;
  }
  EXPECT_EQ(sample.stat_before_read.end_probe->return_value, 1);
  EXPECT_EQ(sample.stat_before_read.end_probe_byte, 'x');
  operations.extra_probe_byte = false;
  operations.stats[0].pop_back();
  operations.stats[1].pop_back();
  EXPECT_EQ(monitor.sample(scratch.view()).stop, ThreadMonitorStop::file_read_failure);
}

TEST(ThreadMonitor, RejectsReusedTidAndIdentityChangesAcrossTheBracket) {
  for (const bool before : {true, false}) {
    FakeOperations operations;
    Scratch preparation;
    Scratch scratch;
    PreparedThreadMonitor monitor(operations);
    ASSERT_TRUE(monitor.prepare(123, preparation.view()));
    operations.stats[before ? 0U : 1U] = stat_text("replacement", 457U);
    const auto sample = monitor.sample(scratch.view());
    EXPECT_EQ(sample.stop, ThreadMonitorStop::identity_changed);
    EXPECT_EQ(sample.affinity_call.has_value(), !before);
    EXPECT_EQ(operations.opens, 3U);
  }
  FakeOperations operations;
  Scratch preparation;
  Scratch scratch;
  PreparedThreadMonitor monitor(operations);
  ASSERT_TRUE(monitor.prepare(123, preparation.view()));
  operations.status.replace(operations.status.find("123"), 3U, "124");
  EXPECT_EQ(monitor.sample(scratch.view()).stop, ThreadMonitorStop::identity_changed);
}

TEST(ThreadMonitor, RejectsDeadAndMalformedTasksWithoutInventingDefaults) {
  FakeOperations operations;
  Scratch preparation;
  Scratch scratch;
  PreparedThreadMonitor monitor(operations);
  ASSERT_TRUE(monitor.prepare(123, preparation.view()));
  for (auto& stat : operations.stats) {
    stat.replace(stat.rfind(") R") + 2U, 1U, "Z");
  }
  auto sample = monitor.sample(scratch.view());
  EXPECT_EQ(sample.stop, ThreadMonitorStop::task_exited);
  EXPECT_FALSE(sample.affinity_call.has_value());
  operations.stats = {"not a stat file\n", "not a stat file\n"};
  sample = monitor.sample(scratch.view());
  EXPECT_EQ(sample.stop, ThreadMonitorStop::parse_failure);
  EXPECT_FALSE(sample.stat_before.has_value());
  EXPECT_FALSE(sample.affinity_cpu_count.has_value());
}

TEST(ThreadMonitor, RejectsIdentityChangeDuringPreparationAndDoesNotRetryClose) {
  FakeOperations operations;
  operations.stats[1] = stat_text("replacement", 457U);
  operations.close_return = {-1, EINTR};
  Scratch scratch;
  PreparedThreadMonitor monitor(operations);
  EXPECT_FALSE(monitor.prepare(123, scratch.view()));
  EXPECT_EQ(monitor.preparation().initial.stop, ThreadMonitorStop::identity_changed);
  EXPECT_FALSE(monitor.prepare(123, scratch.view()));
  monitor.release();
  monitor.release();
  EXPECT_EQ(operations.opens, 3U);
  EXPECT_EQ(operations.closes, 3U);
  for (const auto& closed : monitor.preparation().closes) {
    if (!closed.has_value()) {
      FAIL() << "missing close failure";
      return;
    }
    EXPECT_EQ(closed->return_value, -1);
    EXPECT_EQ(closed->error_number, EINTR);
  }
}

TEST(ThreadMonitor, RetainsOtherObservationsWhenStatusCannotBeParsed) {
  FakeOperations operations;
  Scratch preparation;
  Scratch scratch;
  PreparedThreadMonitor monitor(operations);
  ASSERT_TRUE(monitor.prepare(123, preparation.view()));
  operations.status = "Pid:\t123\nTgid:\t100\n";
  const auto sample = monitor.sample(scratch.view());
  EXPECT_EQ(sample.stop, ThreadMonitorStop::parse_failure);
  EXPECT_TRUE(sample.status_read.complete);
  EXPECT_FALSE(sample.status.has_value());
  EXPECT_TRUE(sample.stat_before.has_value());
  EXPECT_TRUE(sample.stat_after.has_value());
  EXPECT_EQ(sample.singleton_affinity_cpu, 7U);
}

TEST(ThreadMonitor, RetainsAffinityFailureAndDoesNotInventSingletonFromMultipleCpus) {
  FakeOperations operations;
  Scratch preparation;
  Scratch scratch;
  PreparedThreadMonitor monitor(operations);
  ASSERT_TRUE(monitor.prepare(123, preparation.view()));
  operations.affinity_return = LinuxCallResult{-1, EINVAL};
  auto sample = monitor.sample(scratch.view());
  EXPECT_EQ(sample.stop, ThreadMonitorStop::affinity_failure);
  if (!sample.affinity_call.has_value()) {
    FAIL() << "missing affinity observation";
    return;
  }
  EXPECT_EQ(sample.affinity_call->error_number, EINVAL);
  EXPECT_FALSE(sample.affinity_cpu_count.has_value());
  ASSERT_TRUE(sample.stat_after.has_value());
  for (const auto invalid : {std::int64_t{0}, std::int64_t{1}, std::int64_t{8192}}) {
    operations.affinity_return = LinuxCallResult{invalid, 0};
    EXPECT_EQ(monitor.sample(scratch.view()).stop, ThreadMonitorStop::affinity_failure);
  }
  operations.affinity_return.reset();
  operations.mask = 0UL;
  EXPECT_EQ(monitor.sample(scratch.view()).stop, ThreadMonitorStop::affinity_failure);
  operations.mask = 3UL;
  sample = monitor.sample(scratch.view());
  ASSERT_TRUE(sample.succeeded());
  EXPECT_EQ(sample.affinity_cpu_count, 2U);
  EXPECT_FALSE(sample.singleton_affinity_cpu.has_value());
}

TEST(ThreadMonitor, ObservesLiveStdThreadThenRejectsExitedAnchoredTask) {
  std::atomic<int> tid{0};
  std::jthread worker([&](const std::stop_token& stop) {
    tid.store(static_cast<int>(::syscall(SYS_gettid)), std::memory_order_release);
    tid.notify_one();
    while (!stop.stop_requested()) {
      std::this_thread::yield();
    }
  });
  tid.wait(0, std::memory_order_acquire);
  LinuxThreadMonitorOperations operations;
  Scratch preparation;
  std::array<Scratch, 3U> scratch;
  PreparedThreadMonitor monitor(operations);
  ASSERT_TRUE(monitor.prepare(tid.load(), preparation.view()));
  for (auto& buffer : scratch) {
    const auto sample = monitor.sample(buffer.view());
    ASSERT_TRUE(sample.succeeded());
    if (!sample.stat_before.has_value() || !sample.status.has_value() ||
        !sample.stat_after.has_value()) {
      FAIL() << "missing native thread observations";
      return;
    }
    EXPECT_EQ(sample.stat_before->task_id, tid.load());
    EXPECT_EQ(sample.status->thread_group_id, ::getpid());
    EXPECT_GE(sample.stat_after->minor_faults, sample.stat_before->minor_faults);
    EXPECT_GE(sample.stat_after->major_faults, sample.stat_before->major_faults);
    EXPECT_EQ(sample.stat_after->start_time_ticks,
              sample.stat_before->start_time_ticks);
  }
  worker.request_stop();
  worker.join();
  // pthread join observes clear_child_tid, which can precede final kernel task
  // removal. Establish that external test precondition before the single
  // post-exit monitor call. These cold directory probes do not sample/retry the
  // monitor. The finite software-test bound is not an experimental threshold.
  bool removed = false;
  for (std::size_t attempt = 0U; attempt < 100000U; ++attempt) {
    const auto directory = operations.open_task(tid.load());
    if (!directory.nonnegative_return()) {
      EXPECT_TRUE(directory.error_number == ENOENT || directory.error_number == ESRCH);
      removed = true;
      break;
    }
    EXPECT_TRUE(
        operations.close_file(static_cast<int>(directory.return_value)).zero_return());
    std::this_thread::yield();
  }
  ASSERT_TRUE(removed);
  const auto after_exit = monitor.sample(scratch[0].view());
  EXPECT_FALSE(after_exit.succeeded());
  EXPECT_EQ(after_exit.stop, ThreadMonitorStop::file_read_failure);
  EXPECT_FALSE(after_exit.affinity_call.has_value());
  EXPECT_FALSE(monitor.prepare(tid.load(), scratch[0].view()));
}

struct MappedLiveThread final {
  cpu_prefetch::test::SoftwareStackOperations operations;
  OwnerMappingPlan plan{cpu_prefetch::test::software_stack_plan()};
  MappedWorkerThread<cpu_prefetch::test::SoftwareStackOperations> thread{plan,
                                                                         operations};
  std::atomic<int> tid{0};
  std::atomic<bool> stop{false};
  ~MappedLiveThread() {
    stop.store(true, std::memory_order_release);
    stop.notify_one();
    thread.join();
  }
  static void entry(void* raw) noexcept {
    auto& self = *static_cast<MappedLiveThread*>(raw);
    self.tid.store(static_cast<int>(::syscall(SYS_gettid)), std::memory_order_release);
    self.tid.notify_one();
    self.stop.wait(false, std::memory_order_acquire);
  }
};

TEST(ThreadMonitor, ObservesNativeMappedWorkerWithVerifiedSingletonAffinity) {
  MappedLiveThread worker;
  ASSERT_TRUE(worker.thread.start(&MappedLiveThread::entry, &worker));
  worker.tid.wait(0, std::memory_order_acquire);
  ASSERT_TRUE(worker.thread.prepared());
  LinuxThreadMonitorOperations operations;
  Scratch preparation;
  Scratch scratch;
  PreparedThreadMonitor monitor(operations);
  ASSERT_TRUE(monitor.prepare(worker.tid.load(), preparation.view()));
  const auto sample = monitor.sample(scratch.view());
  ASSERT_TRUE(sample.succeeded());
  if (!sample.stat_before.has_value() || !sample.stat_after.has_value()) {
    FAIL() << "missing mapped thread observations";
    return;
  }
  EXPECT_EQ(sample.singleton_affinity_cpu, worker.plan.owner_cpu);
  EXPECT_EQ(sample.affinity_cpu_count, 1U);
  EXPECT_EQ(sample.stat_before->last_cpu, static_cast<int>(worker.plan.owner_cpu));
  EXPECT_EQ(sample.stat_after->last_cpu, static_cast<int>(worker.plan.owner_cpu));
  EXPECT_EQ(sample.stat_before->task_id, worker.tid.load());
}

} // namespace
