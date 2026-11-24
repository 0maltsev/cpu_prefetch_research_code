#include "cpu_prefetch/platform/thread_monitor.hpp"

#include <algorithm>
#include <bit>
#include <cerrno>
#include <charconv>
#include <fcntl.h>
#include <limits>
#include <sys/syscall.h>
#include <unistd.h>

namespace cpu_prefetch::platform {
namespace {

auto call_result(std::int64_t value) noexcept -> LinuxCallResult {
  return {value, value < 0 ? errno : 0};
}

auto trim(std::string_view text) noexcept -> std::string_view {
  const auto begin = text.find_first_not_of(" \t\r\n");
  if (begin == std::string_view::npos) {
    return {};
  }
  const auto end = text.find_last_not_of(" \t\r\n");
  return text.substr(begin, end - begin + 1U);
}

template <typename Integer>
auto number(std::string_view text, Integer& value) noexcept -> bool {
  if (text.empty()) {
    return false;
  }
  const auto parsed = std::from_chars(text.data(), text.data() + text.size(), value);
  return parsed.ec == std::errc{} && parsed.ptr == text.data() + text.size();
}

auto token(std::string_view& text) noexcept -> std::string_view {
  text = trim(text);
  const auto end = text.find_first_of(" \t\r\n");
  const auto result = text.substr(0U, end);
  text = end == std::string_view::npos ? std::string_view{} : text.substr(end);
  return result;
}

auto complete_text(std::string_view text) noexcept -> bool {
  return !text.empty() && text.back() == '\n' &&
         text.find('\0') == std::string_view::npos;
}

auto valid_scratch(ThreadMonitorScratch scratch) noexcept -> bool {
  struct Range final {
    std::uintptr_t begin;
    std::size_t bytes;
  };
  if (scratch.affinity.size() >
      std::numeric_limits<unsigned int>::max() / sizeof(unsigned long)) {
    return false;
  }
  const std::array ranges{
      Range{reinterpret_cast<std::uintptr_t>(scratch.stat_before.data()),
            scratch.stat_before.size()},
      Range{reinterpret_cast<std::uintptr_t>(scratch.status.data()),
            scratch.status.size()},
      Range{reinterpret_cast<std::uintptr_t>(scratch.stat_after.data()),
            scratch.stat_after.size()},
      Range{reinterpret_cast<std::uintptr_t>(scratch.affinity.data()),
            scratch.affinity.size_bytes()}};
  for (std::size_t index = 0U; index < ranges.size(); ++index) {
    const auto range = ranges[index];
    if (range.begin == 0U || range.bytes == 0U ||
        range.bytes > static_cast<std::size_t>(std::numeric_limits<ssize_t>::max()) ||
        range.bytes > std::numeric_limits<std::uintptr_t>::max() - range.begin) {
      return false;
    }
    for (std::size_t other = 0U; other < index; ++other) {
      const auto prior = ranges[other];
      if (range.begin < prior.begin + prior.bytes &&
          prior.begin < range.begin + range.bytes) {
        return false;
      }
    }
  }
  return true;
}

auto read_file(ThreadMonitorOperations& operations, int descriptor,
               std::span<char> bytes) noexcept -> ThreadFileRead {
  ThreadFileRead result;
  std::fill(bytes.begin(), bytes.end(), '\0');
  result.read = operations.read_at_start(descriptor, bytes);
  const auto read = *result.read;
  if (!read.nonnegative_return() || read.return_value == 0 ||
      static_cast<std::uint64_t>(read.return_value) >= bytes.size()) {
    return result;
  }
  const auto count = static_cast<std::size_t>(read.return_value);
  result.end_probe = operations.read_at_end(descriptor, count, result.end_probe_byte);
  result.complete = result.end_probe->zero_return() && bytes[count - 1U] == '\n';
  return result;
}

auto read_text(const ThreadFileRead& read, std::span<char> bytes) noexcept
    -> std::string_view {
  if (!read.read.has_value() || !read.complete || read.read->return_value <= 0 ||
      static_cast<std::uint64_t>(read.read->return_value) > bytes.size()) {
    return {};
  }
  return {bytes.data(), static_cast<std::size_t>(read.read->return_value)};
}

auto dead(const ThreadStatObservation& stat) noexcept -> bool {
  return stat.state == 'Z' || stat.state == 'X' || stat.state == 'x';
}

auto same_identity(const ThreadStatObservation& left,
                   const ThreadStatObservation& right) noexcept -> bool {
  return left.task_id == right.task_id &&
         left.start_time_ticks == right.start_time_ticks;
}

} // namespace

auto parse_thread_stat(std::string_view text) noexcept
    -> std::optional<ThreadStatObservation> {
  if (!complete_text(text)) {
    return std::nullopt;
  }
  // comm may itself contain spaces, parentheses and newlines. Fields after
  // its final ") " contain only state and numbers, so never split on comm.
  const auto open = text.find(" (");
  const auto close = text.rfind(") ");
  ThreadStatObservation result{};
  if (open == std::string_view::npos || close == std::string_view::npos ||
      close < open + 2U || !number(text.substr(0U, open), result.task_id) ||
      result.task_id <= 0) {
    return std::nullopt;
  }
  text.remove_prefix(close + 2U);
  const auto state = token(text);
  if (state.size() != 1U ||
      std::string_view("RSDZTtXxKWPI").find(state.front()) == std::string_view::npos) {
    return std::nullopt;
  }
  result.state = state.front();
  std::size_t field = 4U;
  while (!trim(text).empty()) {
    const auto value = token(text);
    std::uint64_t unsigned_value{};
    std::int64_t signed_value{};
    if (value.front() == '-') {
      if (!number(value, signed_value)) {
        return std::nullopt;
      }
    } else if (!number(value, unsigned_value)) {
      return std::nullopt;
    }
    if (field == 10U || field == 12U || field == 22U || field == 39U) {
      if (value.front() == '-') {
        return std::nullopt;
      }
      switch (field) {
      case 10U:
        result.minor_faults = unsigned_value;
        break;
      case 12U:
        result.major_faults = unsigned_value;
        break;
      case 22U:
        result.start_time_ticks = unsigned_value;
        break;
      case 39U:
        if (unsigned_value >
            static_cast<std::uint64_t>(std::numeric_limits<int>::max())) {
          return std::nullopt;
        }
        result.last_cpu = static_cast<int>(unsigned_value);
        break;
      default:
        break;
      }
    }
    ++field;
  }
  // All 52 documented Linux fields must be present. Future appended numeric
  // fields are accepted; a prefix ending at the last interesting field is not.
  return field >= 53U ? std::optional{result} : std::nullopt;
}

auto parse_thread_status(std::string_view text) noexcept
    -> std::optional<ThreadStatusObservation> {
  if (!complete_text(text)) {
    return std::nullopt;
  }
  constexpr std::array keys{std::string_view{"Pid"}, std::string_view{"Tgid"},
                            std::string_view{"voluntary_ctxt_switches"},
                            std::string_view{"nonvoluntary_ctxt_switches"}};
  std::array<std::uint64_t, 4U> values{};
  std::array<bool, 4U> seen{};
  while (!text.empty()) {
    const auto end = text.find('\n');
    if (end == std::string_view::npos) {
      return std::nullopt;
    }
    const auto line = text.substr(0U, end);
    text.remove_prefix(end + 1U);
    const auto colon = line.find(':');
    if (colon == std::string_view::npos) {
      return std::nullopt;
    }
    for (std::size_t index = 0U; index < keys.size(); ++index) {
      if (line.substr(0U, colon) == keys[index]) {
        if (seen[index] || !number(trim(line.substr(colon + 1U)), values[index])) {
          return std::nullopt;
        }
        seen[index] = true;
      }
    }
  }
  if (!std::all_of(seen.begin(), seen.end(), [](bool value) { return value; }) ||
      values[0] == 0U || values[1] == 0U ||
      values[0] > static_cast<std::uint64_t>(std::numeric_limits<int>::max()) ||
      values[1] > static_cast<std::uint64_t>(std::numeric_limits<int>::max())) {
    return std::nullopt;
  }
  return ThreadStatusObservation{static_cast<int>(values[0]),
                                 static_cast<int>(values[1]), values[2], values[3]};
}

auto LinuxThreadMonitorOperations::open_task(int task_id) noexcept -> LinuxCallResult {
  if (task_id <= 0) {
    return {-1, EINVAL};
  }
  std::array<char, 64U> path{};
  constexpr std::string_view prefix{"/proc/self/task/"};
  std::copy(prefix.begin(), prefix.end(), path.begin());
  const auto end = std::to_chars(path.data() + prefix.size(),
                                 path.data() + path.size() - 1U, task_id);
  if (end.ec != std::errc{}) {
    return {-1, EOVERFLOW};
  }
  return call_result(
      ::open(path.data(), O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW));
}

auto LinuxThreadMonitorOperations::open_file(int directory, bool status) noexcept
    -> LinuxCallResult {
  return call_result(::openat(directory, status ? "status" : "stat",
                              O_RDONLY | O_CLOEXEC | O_NOFOLLOW));
}

auto LinuxThreadMonitorOperations::read_at_start(int descriptor,
                                                 std::span<char> bytes) noexcept
    -> LinuxCallResult {
  return call_result(::pread(descriptor, bytes.data(), bytes.size(), 0));
}

auto LinuxThreadMonitorOperations::read_at_end(int descriptor, std::size_t offset,
                                               char& byte) noexcept -> LinuxCallResult {
  return call_result(::pread(descriptor, &byte, 1U, static_cast<off_t>(offset)));
}

auto LinuxThreadMonitorOperations::affinity(int task_id,
                                            std::span<unsigned long> mask) noexcept
    -> LinuxCallResult {
  return call_result(
      ::syscall(SYS_sched_getaffinity, task_id, mask.size_bytes(), mask.data()));
}

auto LinuxThreadMonitorOperations::close_file(int descriptor) noexcept
    -> LinuxCallResult {
  return call_result(::close(descriptor));
}

PreparedThreadMonitor::~PreparedThreadMonitor() { release(); }

auto PreparedThreadMonitor::prepare(int task_id, ThreadMonitorScratch scratch) noexcept
    -> bool {
  if (preparation_.attempted) {
    return false;
  }
  preparation_.attempted = true;
  preparation_.requested_task_id = task_id;
  if (task_id <= 0 || !valid_scratch(scratch)) {
    return false;
  }
  preparation_.directory_open = operations_.open_task(task_id);
  if (!preparation_.directory_open->nonnegative_return()) {
    return false;
  }
  descriptors_[2] = static_cast<int>(preparation_.directory_open->return_value);
  preparation_.stat_open = operations_.open_file(descriptors_[2], false);
  if (!preparation_.stat_open->nonnegative_return()) {
    return false;
  }
  descriptors_[0] = static_cast<int>(preparation_.stat_open->return_value);
  preparation_.status_open = operations_.open_file(descriptors_[2], true);
  if (!preparation_.status_open->nonnegative_return()) {
    return false;
  }
  descriptors_[1] = static_cast<int>(preparation_.status_open->return_value);
  preparation_.initial = observe(scratch);
  preparation_.ready = preparation_.initial.succeeded();
  return preparation_.ready;
}

auto PreparedThreadMonitor::sample(ThreadMonitorScratch scratch) noexcept
    -> ThreadControlSample {
  if (!preparation_.ready) {
    return {};
  }
  return observe(scratch);
}

auto PreparedThreadMonitor::observe(ThreadMonitorScratch scratch) noexcept
    -> ThreadControlSample {
  ThreadControlSample result;
  if (!valid_scratch(scratch)) {
    result.stop = ThreadMonitorStop::invalid_scratch;
    return result;
  }
  result.stat_before_read =
      read_file(operations_, descriptors_[0], scratch.stat_before);
  if (!result.stat_before_read.complete) {
    result.stop = ThreadMonitorStop::file_read_failure;
    return result;
  }
  result.stat_before =
      parse_thread_stat(read_text(result.stat_before_read, scratch.stat_before));
  if (!result.stat_before.has_value()) {
    result.stop = ThreadMonitorStop::parse_failure;
    return result;
  }
  const auto& baseline = preparation_.initial.stat_before;
  if (result.stat_before->task_id != preparation_.requested_task_id ||
      (baseline.has_value() && !same_identity(*baseline, *result.stat_before))) {
    result.stop = ThreadMonitorStop::identity_changed;
    return result;
  }
  if (dead(*result.stat_before)) {
    result.stop = ThreadMonitorStop::task_exited;
    return result;
  }
  result.status_read = read_file(operations_, descriptors_[1], scratch.status);
  if (result.status_read.complete) {
    result.status = parse_thread_status(read_text(result.status_read, scratch.status));
  }
  std::fill(scratch.affinity.begin(), scratch.affinity.end(), 0UL);
  result.affinity_mask = scratch.affinity;
  result.affinity_call =
      operations_.affinity(preparation_.requested_task_id, scratch.affinity);
  const auto affinity = *result.affinity_call;
  const bool affinity_ok =
      affinity.nonnegative_return() && affinity.return_value > 0 &&
      static_cast<std::uint64_t>(affinity.return_value) <=
          scratch.affinity.size_bytes() &&
      static_cast<std::uint64_t>(affinity.return_value) % sizeof(unsigned long) == 0U;
  if (affinity_ok) {
    std::size_t count = 0U;
    std::size_t last_cpu = 0U;
    const auto words =
        static_cast<std::size_t>(affinity.return_value) / sizeof(unsigned long);
    for (std::size_t index = 0U; index < words; ++index) {
      const auto word = scratch.affinity[index];
      count += static_cast<std::size_t>(std::popcount(word));
      if (word != 0UL) {
        last_cpu = index * std::numeric_limits<unsigned long>::digits +
                   static_cast<std::size_t>(std::countr_zero(word));
      }
    }
    result.affinity_cpu_count = count;
    if (count == 1U) {
      result.singleton_affinity_cpu = last_cpu;
    }
  }
  result.stat_after_read = read_file(operations_, descriptors_[0], scratch.stat_after);
  if (result.stat_after_read.complete) {
    result.stat_after =
        parse_thread_stat(read_text(result.stat_after_read, scratch.stat_after));
  }
  if (!result.status_read.complete || !result.stat_after_read.complete) {
    result.stop = ThreadMonitorStop::file_read_failure;
  } else if (!result.status.has_value() || !result.stat_after.has_value()) {
    result.stop = ThreadMonitorStop::parse_failure;
  } else if (!same_identity(*result.stat_before, *result.stat_after) ||
             result.status->task_id != preparation_.requested_task_id ||
             (preparation_.initial.status.has_value() &&
              result.status->thread_group_id !=
                  preparation_.initial.status->thread_group_id)) {
    result.stop = ThreadMonitorStop::identity_changed;
  } else if (dead(*result.stat_after)) {
    result.stop = ThreadMonitorStop::task_exited;
  } else if (!affinity_ok || result.affinity_cpu_count == 0U) {
    result.stop = ThreadMonitorStop::affinity_failure;
  } else {
    result.stop = ThreadMonitorStop::sampled;
  }
  return result;
}

void PreparedThreadMonitor::release() noexcept {
  preparation_.attempted = true;
  preparation_.ready = false;
  for (std::size_t index = 0U; index < descriptors_.size(); ++index) {
    if (descriptors_[index] >= 0) {
      preparation_.closes[index] = operations_.close_file(descriptors_[index]);
      descriptors_[index] = -1;
    }
  }
}

} // namespace cpu_prefetch::platform
