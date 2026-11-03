#include "cpu_prefetch/platform/prepared_file_snapshot.hpp"

#include <algorithm>
#include <cerrno>
#include <fcntl.h>
#include <unistd.h>

namespace cpu_prefetch::platform {
namespace {

auto observed_call(std::int64_t value) noexcept -> LinuxCallResult {
  return {value, value < 0 ? errno : 0};
}

struct Range final {
  std::uintptr_t begin;
  std::size_t bytes;
};

auto valid_storage(const PreparedFileSnapshot* owner, FileSnapshotPlan plan,
                   std::span<char> path, std::span<FileSnapshotSample> samples) noexcept
    -> bool {
  if (path.size() != plan.path.size() + 1U) {
    return false;
  }
  std::array<Range, 4U + 2U * kFileSnapshotGroups> ranges{};
  ranges[0U] = {reinterpret_cast<std::uintptr_t>(owner), sizeof(*owner)};
  ranges[1U] = {reinterpret_cast<std::uintptr_t>(plan.path.data()), plan.path.size()};
  ranges[2U] = {reinterpret_cast<std::uintptr_t>(path.data()), path.size()};
  ranges[3U] = {reinterpret_cast<std::uintptr_t>(samples.data()), samples.size_bytes()};
  for (std::size_t index = 0U; index < samples.size(); ++index) {
    const auto& sample = samples[index];
    if (sample.bytes.size() != plan.byte_capacity ||
        sample.reads.size() != plan.max_data_reads || sample.attempted ||
        sample.stop != FileSnapshotStop::not_started) {
      return false;
    }
    ranges[4U + 2U * index] = {reinterpret_cast<std::uintptr_t>(sample.bytes.data()),
                               sample.bytes.size()};
    ranges[5U + 2U * index] = {reinterpret_cast<std::uintptr_t>(sample.reads.data()),
                               sample.reads.size_bytes()};
  }
  for (std::size_t index = 0U; index < ranges.size(); ++index) {
    const auto current = ranges[index];
    if (current.begin == 0U || current.bytes == 0U ||
        current.bytes > std::numeric_limits<std::uintptr_t>::max() - current.begin) {
      return false;
    }
    for (std::size_t prior = 0U; prior < index; ++prior) {
      const auto other = ranges[prior];
      if (current.begin < other.begin + other.bytes &&
          other.begin < current.begin + current.bytes) {
        return false;
      }
    }
  }
  return true;
}

} // namespace

auto LinuxFileSnapshotOperations::open_file(const char* path, int flags) noexcept
    -> LinuxCallResult {
  return observed_call(::open(path, flags));
}

auto LinuxFileSnapshotOperations::read_at(int descriptor, std::span<std::byte> bytes,
                                          std::size_t offset) noexcept
    -> LinuxCallResult {
  return observed_call(
      ::pread(descriptor, bytes.data(), bytes.size(), static_cast<off_t>(offset)));
}

auto LinuxFileSnapshotOperations::close_file(int descriptor) noexcept
    -> LinuxCallResult {
  return observed_call(::close(descriptor));
}

auto valid_file_snapshot_plan(FileSnapshotPlan plan) noexcept -> bool {
  if (plan.path.empty() || plan.path.front() != '/' ||
      plan.path.find('\0') != std::string_view::npos ||
      plan.path.size() == std::numeric_limits<std::size_t>::max() ||
      plan.byte_capacity == 0U || plan.chunk_bytes == 0U ||
      plan.chunk_bytes > plan.byte_capacity || plan.max_data_reads == 0U ||
      plan.byte_capacity >=
          static_cast<std::size_t>(std::numeric_limits<off_t>::max()) ||
      plan.byte_capacity >
          static_cast<std::size_t>(std::numeric_limits<ssize_t>::max()) ||
      plan.max_data_reads >
          static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max()) /
              sizeof(FileSnapshotRead) ||
      std::none_of(plan.requested.begin(), plan.requested.end(),
                   [](bool value) { return value; })) {
    return false;
  }
  return true;
}

PreparedFileSnapshot::~PreparedFileSnapshot() { static_cast<void>(release()); }

auto PreparedFileSnapshot::prepare(
    FileSnapshotPlan plan, std::span<char> frozen_path,
    std::span<FileSnapshotSample, kFileSnapshotGroups> samples) noexcept -> bool {
  if (preparation_.attempted) {
    return false;
  }
  preparation_.attempted = true;
  preparation_.stop = FileSnapshotPreparationStop::invalid_plan;
  if (!valid_file_snapshot_plan(plan)) {
    return false;
  }
  if (!valid_storage(this, plan, frozen_path, samples)) {
    preparation_.stop = FileSnapshotPreparationStop::invalid_storage;
    return false;
  }
  std::copy(plan.path.begin(), plan.path.end(), frozen_path.begin());
  frozen_path.back() = '\0';
  preparation_.plan = plan;
  preparation_.plan.path = {frozen_path.data(), plan.path.size()};
  samples_ = samples;
  for (std::size_t index = 0U; index < samples_.size(); ++index) {
    auto& sample = samples_[index];
    const auto bytes = sample.bytes;
    const auto reads = sample.reads;
    sample = {bytes, reads};
    storage_[index] = {bytes, reads};
    std::fill(bytes.begin(), bytes.end(), std::byte{});
    std::fill(reads.begin(), reads.end(), FileSnapshotRead{});
  }
  preparation_.open = operations_.open_file(frozen_path.data(), O_RDONLY | O_CLOEXEC);
  if (!preparation_.open->nonnegative_return()) {
    preparation_.stop = FileSnapshotPreparationStop::open_failed;
    return false;
  }
  descriptor_ = static_cast<int>(preparation_.open->return_value);
  preparation_.stop = FileSnapshotPreparationStop::ready;
  return true;
}

auto PreparedFileSnapshot::sample(std::size_t slot) noexcept -> FileSnapshotStop {
  if (slot >= kFileSnapshotGroups) {
    return FileSnapshotStop::invalid_slot;
  }
  if (preparation_.released ||
      preparation_.stop != FileSnapshotPreparationStop::ready) {
    return FileSnapshotStop::not_prepared;
  }
  auto& sample = samples_[slot];
  if (attempted_[slot] || sample.attempted) {
    return FileSnapshotStop::output_reused;
  }
  attempted_[slot] = true;
  sample.attempted = true;
  if (sample.bytes.data() != storage_[slot].bytes.data() ||
      sample.bytes.size() != storage_[slot].bytes.size() ||
      sample.reads.data() != storage_[slot].reads.data() ||
      sample.reads.size() != storage_[slot].reads.size() ||
      sample.captured_bytes != 0U || sample.data_reads != 0U ||
      sample.stop != FileSnapshotStop::not_started) {
    sample.stop = FileSnapshotStop::invalid_storage;
    return sample.stop;
  }
  if (!preparation_.plan.requested[slot]) {
    sample.stop = FileSnapshotStop::not_requested;
    return sample.stop;
  }
  for (auto& read : sample.reads) {
    const auto remaining = sample.bytes.size() - sample.captured_bytes;
    const auto count = std::min(remaining, preparation_.plan.chunk_bytes);
    read.offset = sample.captured_bytes;
    read.requested_bytes = count;
    read.observed = operations_.read_at(
        descriptor_, sample.bytes.subspan(sample.captured_bytes, count), read.offset);
    ++sample.data_reads;
    const auto observed = *read.observed;
    if (!observed.nonnegative_return()) {
      sample.stop = FileSnapshotStop::read_failed;
      return sample.stop;
    }
    if (static_cast<std::uint64_t>(observed.return_value) > count) {
      sample.stop = FileSnapshotStop::invalid_read_count;
      return sample.stop;
    }
    if (observed.return_value == 0) {
      sample.stop = FileSnapshotStop::complete;
      return sample.stop;
    }
    sample.captured_bytes += static_cast<std::size_t>(observed.return_value);
    if (sample.captured_bytes == sample.bytes.size()) {
      break;
    }
  }
  auto& probe = sample.eof_probe;
  probe.offset = sample.captured_bytes;
  probe.requested_bytes = 1U;
  probe.observed =
      operations_.read_at(descriptor_, {&sample.probe_byte, 1U}, probe.offset);
  const auto observed = *probe.observed;
  if (!observed.nonnegative_return()) {
    sample.stop = FileSnapshotStop::probe_failed;
  } else if (observed.return_value > 1) {
    sample.stop = FileSnapshotStop::invalid_read_count;
  } else if (observed.return_value == 0) {
    sample.stop = FileSnapshotStop::complete;
  } else {
    sample.stop = sample.captured_bytes == sample.bytes.size()
                      ? FileSnapshotStop::byte_capacity_exhausted
                      : FileSnapshotStop::read_budget_exhausted;
  }
  return sample.stop;
}

auto PreparedFileSnapshot::release() noexcept -> bool {
  preparation_.attempted = true;
  preparation_.released = true;
  if (descriptor_ >= 0) {
    preparation_.close = operations_.close_file(descriptor_);
    descriptor_ = -1;
  }
  return !preparation_.close.has_value() || preparation_.close->zero_return();
}

} // namespace cpu_prefetch::platform
