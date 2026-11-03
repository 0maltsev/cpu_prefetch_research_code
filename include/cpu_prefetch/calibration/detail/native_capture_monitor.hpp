#ifndef CPU_PREFETCH_CALIBRATION_DETAIL_NATIVE_CAPTURE_MONITOR_HPP
#define CPU_PREFETCH_CALIBRATION_DETAIL_NATIVE_CAPTURE_MONITOR_HPP

#include "cpu_prefetch/calibration/native_discovery_capture.hpp"
#include "cpu_prefetch/runner/runner.hpp"

#include <memory>

namespace cpu_prefetch::calibration::native_capture_detail {
using Clock = timing::MonotonicRawClock;
using Relax = runner::X86PauseRelax;
using Controls = DiscoveryControlQuery<>;
using Query = native_discovery_detail::EnvironmentQuery<Controls>;
using Observer = PreparedDiscoveryResidencyObserver<Clock, Query, Relax>;
using Builder = mapped_discovery_detail::LayoutBuilder;

// Identical cold observation storage and destruction order shared by diagnostic
// and formal native compositions. This owns no mappings and defines no lifecycle.
struct Monitor final {
  platform::LinuxThreadMonitorOperations thread_operations;
  platform::PreparedThreadMonitor producer{thread_operations};
  platform::PreparedThreadMonitor consumer{thread_operations};
  platform::LinuxPrefetchReadbackOperations hardware_operations;
  platform::PreparedPrefetchReadback hardware{hardware_operations};
  platform::LinuxPageResidencyQuery pages;
  platform::LinuxFileSnapshotOperations file_operations;
  std::span<platform::PreparedFileSnapshot> files;
  std::span<platform::FileSnapshotPreparation> file_preparations;
  std::span<platform::FileSnapshotSample> file_samples;
  std::optional<Controls> control_query;
  std::optional<Query> query;
  std::optional<Observer> observer;
  std::span<DiscoveryResidencyRegion> regions;
  std::span<DiscoveryControlSample> controls;
  std::span<platform::PreparedPageResidencyQuery> prepared_pages;
  std::span<DiscoveryResidencySample> residency;
  std::array<platform::ThreadMonitorScratch, 2U> initial_scratch;
  std::size_t constructed_queries{0U};
  std::size_t constructed_samples{0U};
  std::size_t constructed_files{0U};
  ~Monitor() {
    observer.reset();
    query.reset();
    control_query.reset();
    for (std::size_t index = 0U; index < constructed_files; ++index) {
      std::destroy_at(&files[index]);
    }
    for (std::size_t index = 0U; index < constructed_samples; ++index) {
      std::destroy_at(&residency[index]);
    }
    for (std::size_t index = 0U; index < constructed_queries; ++index) {
      std::destroy_at(&prepared_pages[index]);
    }
  }
};

struct ScratchOffsets final {
  std::size_t first;
  std::size_t status;
  std::size_t last;
  std::size_t affinity;
};

template <typename Layout, typename Plan>
void allocate_monitor_layout(Layout& result, const Plan& plan, std::size_t page) {
  Builder monitor;
  static_cast<void>(monitor.array<Monitor>(1U, page));
  result.regions = monitor.array<DiscoveryResidencyRegion>(
      kNativeDiscoveryRegions, alignof(DiscoveryResidencyRegion));
  result.controls =
      monitor.array<DiscoveryControlSample>(6U, alignof(DiscoveryControlSample));
  result.queries = monitor.array<platform::PreparedPageResidencyQuery>(
      kNativeDiscoveryObservations, alignof(platform::PreparedPageResidencyQuery));
  result.residency = monitor.array<DiscoveryResidencySample>(
      kNativeDiscoveryObservations, alignof(DiscoveryResidencySample));
  for (std::size_t index = 0U; index < kNativeDiscoveryObservations; ++index) {
    const auto region = index % kNativeDiscoveryRegions;
    const auto during = (index / kNativeDiscoveryRegions) % 3U == 1U;
    const auto count = during ? plan.during_page_count[region]
                              : result.public_layout.region_bytes[region] / page;
    result.pointers[index] = monitor.array<void*>(count, alignof(void*));
    result.statuses[index] = monitor.array<int>(count, alignof(int));
  }
  for (auto& scratch : result.thread_scratch) {
    scratch.first = monitor.array<char>(plan.thread_stat_bytes, alignof(char));
    scratch.status = monitor.array<char>(plan.thread_status_bytes, alignof(char));
    scratch.last = monitor.array<char>(plan.thread_stat_bytes, alignof(char));
    scratch.affinity = monitor.array<unsigned long>(plan.thread_affinity_words,
                                                    alignof(unsigned long));
  }
  const auto source_count = plan.environment_sources.size();
  if (source_count >
      std::numeric_limits<std::size_t>::max() / platform::kFileSnapshotGroups) {
    throw std::invalid_argument("native environment source count overflows");
  }
  result.files = monitor.array<platform::PreparedFileSnapshot>(
      source_count, alignof(platform::PreparedFileSnapshot));
  result.file_preparations = monitor.array<platform::FileSnapshotPreparation>(
      source_count, alignof(platform::FileSnapshotPreparation));
  result.file_samples = monitor.array<platform::FileSnapshotSample>(
      source_count * platform::kFileSnapshotGroups,
      alignof(platform::FileSnapshotSample));
  for (std::size_t index = 0U; index < source_count; ++index) {
    const auto& source = plan.environment_sources[index];
    if (!platform::valid_file_snapshot_plan(source)) {
      throw std::invalid_argument("native environment source plan is invalid");
    }
    for (std::size_t prior = 0U; prior < index; ++prior) {
      if (source.path == plan.environment_sources[prior].path) {
        throw std::invalid_argument("native environment source path is duplicated");
      }
    }
    typename Layout::FileOffsets offsets{};
    offsets.path = monitor.array<char>(source.path.size() + 1U, alignof(char));
    for (std::size_t group = 0U; group < platform::kFileSnapshotGroups; ++group) {
      offsets.bytes[group] =
          monitor.array<std::byte>(source.byte_capacity, alignof(std::byte));
      offsets.reads[group] = monitor.array<platform::FileSnapshotRead>(
          source.max_data_reads, alignof(platform::FileSnapshotRead));
    }
    result.environment.push_back(offsets);
  }
  result.public_layout.monitor_bytes = monitor.reserve({0U, page});
}

template <typename T>
auto storage(std::span<std::byte> mapping, std::size_t offset, std::size_t count)
    -> std::span<T> {
  return {reinterpret_cast<T*>(mapping.data() + offset), count};
}

template <typename Plan>
auto scratch(std::span<std::byte> mapping, ScratchOffsets offsets, const Plan& plan)
    -> platform::ThreadMonitorScratch {
  return {mapped_discovery_detail::initialize_array<char>(mapping, offsets.first,
                                                          plan.thread_stat_bytes),
          mapped_discovery_detail::initialize_array<char>(mapping, offsets.status,
                                                          plan.thread_status_bytes),
          mapped_discovery_detail::initialize_array<char>(mapping, offsets.last,
                                                          plan.thread_stat_bytes),
          mapped_discovery_detail::initialize_array<unsigned long>(
              mapping, offsets.affinity, plan.thread_affinity_words)};
}

template <typename Layout, typename Plan>
auto prepare_environment(Monitor& monitor, const Layout& layout, const Plan& plan,
                         std::span<std::byte> bytes) -> bool {
  const auto count = plan.environment_sources.size();
  monitor.files = storage<platform::PreparedFileSnapshot>(bytes, layout.files, count);
  monitor.file_preparations =
      mapped_discovery_detail::initialize_array<platform::FileSnapshotPreparation>(
          bytes, layout.file_preparations, count);
  monitor.file_samples =
      mapped_discovery_detail::initialize_array<platform::FileSnapshotSample>(
          bytes, layout.file_samples, count * platform::kFileSnapshotGroups);
  bool complete = true;
  for (std::size_t index = 0U; index < count; ++index) {
    const auto source = plan.environment_sources[index];
    const auto& offsets = layout.environment[index];
    auto path = mapped_discovery_detail::initialize_array<char>(
        bytes, offsets.path, source.path.size() + 1U);
    const auto first = index * platform::kFileSnapshotGroups;
    for (std::size_t group = 0U; group < platform::kFileSnapshotGroups; ++group) {
      monitor.file_samples[first + group] = {
          mapped_discovery_detail::initialize_array<std::byte>(
              bytes, offsets.bytes[group], source.byte_capacity),
          mapped_discovery_detail::initialize_array<platform::FileSnapshotRead>(
              bytes, offsets.reads[group], source.max_data_reads)};
    }
    auto* reader = std::construct_at(&monitor.files[index], monitor.file_operations);
    ++monitor.constructed_files;
    const auto prepared = reader->prepare(
        source, path,
        std::span<platform::FileSnapshotSample, platform::kFileSnapshotGroups>(
            monitor.file_samples.data() + first, platform::kFileSnapshotGroups));
    if (!prepared) {
      complete = false;
    }
  }
  return complete;
}

} // namespace cpu_prefetch::calibration::native_capture_detail
#endif
