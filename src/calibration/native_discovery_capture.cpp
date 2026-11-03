#include "cpu_prefetch/calibration/native_discovery_capture.hpp"
#include "cpu_prefetch/runner/runner.hpp"

#include <memory>

namespace cpu_prefetch::calibration {
namespace {

using Clock = timing::MonotonicRawClock;
using Relax = runner::X86PauseRelax;
using Runtime = MappedDiscoveryRuntime<Clock, Relax>;
using Controls = DiscoveryControlQuery<>;
using Query = native_discovery_detail::EnvironmentQuery<Controls>;
using Observer = PreparedDiscoveryResidencyObserver<Clock, Query, Relax>;
using Mapping = platform::OwnerMapping<>;
using Stack = platform::MappedWorkerThread<>;
using Builder = mapped_discovery_detail::LayoutBuilder;

struct Core final {
  NativeDiscoveryCapturePlan plan;
  Clock clock;
  Relax relax;
  std::array<std::span<platform::ThreadTlsModule>, 6U> tls;
  Runtime runtime;
  std::array<platform::ThreadTlsSnapshot, 2U> controller_tls{};
  NativeDiscoveryCaptureResult result;

  Core(const NativeDiscoveryCapturePlan& input, timing::ClockOrigin origin,
       std::array<std::span<platform::ThreadTlsModule>, 6U> modules)
      : plan(input), clock(origin), tls(modules),
        runtime(plan.discovery, plan.workers,
                {{{tls[0U], tls[1U]}}, {{tls[2U], tls[3U]}}}, clock, relax) {}
};

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

struct Layout final {
  NativeDiscoveryCaptureLayout public_layout;
  std::array<std::size_t, 6U> tls;
  std::size_t regions;
  std::size_t controls;
  std::size_t queries;
  std::size_t residency;
  std::array<std::size_t, kNativeDiscoveryObservations> pointers;
  std::array<std::size_t, kNativeDiscoveryObservations> statuses;
  std::array<ScratchOffsets, 14U> thread_scratch;
  struct FileOffsets final {
    std::size_t path;
    std::array<std::size_t, platform::kFileSnapshotGroups> bytes;
    std::array<std::size_t, platform::kFileSnapshotGroups> reads;
  };
  std::size_t files;
  std::size_t file_preparations;
  std::size_t file_samples;
  std::vector<FileOffsets> environment;
};

auto make_layout(const NativeDiscoveryCapturePlan& plan) -> Layout {
  Layout result{};
  const auto page = plan.discovery.arena.base_page_bytes;
  result.public_layout.workers = mapped_discovery_layout(plan.discovery);
  const auto& session = plan.discovery.session;
  if (session.warmup_duration_ticks == 0U || session.measurement_duration_ticks == 0U ||
      session.drain_duration_ticks == 0U || plan.tls_module_capacity == 0U ||
      plan.thread_stat_bytes == 0U || plan.thread_status_bytes == 0U ||
      plan.thread_affinity_words == 0U ||
      plan.thread_affinity_words >
          std::numeric_limits<unsigned int>::max() / sizeof(unsigned long) ||
      plan.observer_wait_poll_limit == 0U ||
      plan.control_region_index >= kNativeDiscoveryRegions ||
      plan.during_offset_ticks[0U] >= session.warmup_duration_ticks ||
      plan.during_offset_ticks[1U] >= session.measurement_duration_ticks ||
      plan.workers.producer_stack.owner_cpu == plan.workers.consumer_stack.owner_cpu ||
      plan.controller_stack.owner_cpu == plan.workers.producer_stack.owner_cpu ||
      plan.controller_stack.owner_cpu == plan.workers.consumer_stack.owner_cpu) {
    throw std::invalid_argument(
        "native discovery requires explicit finite geometry and three distinct CPUs");
  }
  for (const auto stack : {plan.workers.producer_stack, plan.workers.consumer_stack,
                           plan.controller_stack}) {
    if (stack.verified_base_page_bytes != page || stack.bytes == 0U ||
        stack.bytes % page != 0U ||
        stack.bytes >
            static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max()) -
                page ||
        stack.requested_node >= std::numeric_limits<unsigned long>::digits) {
      throw std::invalid_argument("native discovery stack geometry is invalid");
    }
  }
  if (plan.hardware_state != protocol::RequestedHardwareState::h0 &&
      plan.hardware_state != protocol::RequestedHardwareState::h1) {
    throw std::invalid_argument("native discovery requires H0 or H1");
  }
  for (const auto state :
       {protocol::RequestedHardwareState::h0, protocol::RequestedHardwareState::h1}) {
    const auto resolved = platform::make_hardware_prefetch_plan(
        plan.hardware_identity, state, plan.hardware_prestate);
    const auto* accepted = resolved.value_if();
    if (accepted == nullptr) {
      throw std::invalid_argument(
          "native discovery prestate has no accepted H0/H1 plan");
    }
    for (const auto cpu : {plan.workers.producer_stack.owner_cpu,
                           plan.workers.consumer_stack.owner_cpu}) {
      if (std::none_of(accepted->requested.begin(), accepted->requested.end(),
                       [cpu](const auto& value) { return value.cpu == cpu; })) {
        throw std::invalid_argument(
            "native discovery worker is outside the accepted MSR CPU set");
      }
    }
  }
  Builder core;
  static_cast<void>(core.array<Core>(1U, page));
  for (auto& offset : result.tls) {
    offset = core.array<platform::ThreadTlsModule>(plan.tls_module_capacity,
                                                   alignof(platform::ThreadTlsModule));
  }
  result.public_layout.core_bytes = core.reserve({0U, page});
  const auto& worker = result.public_layout.workers;
  result.public_layout.region_bytes = {worker.records_bytes,
                                       worker.producer_bytes,
                                       worker.consumer_bytes,
                                       plan.workers.producer_stack.bytes,
                                       plan.workers.consumer_stack.bytes,
                                       result.public_layout.core_bytes,
                                       plan.controller_stack.bytes};
  for (std::size_t index = 0U; index < kNativeDiscoveryRegions; ++index) {
    const auto pages = result.public_layout.region_bytes[index] / page;
    if (plan.during_page_count[index] == 0U || plan.during_first_page[index] >= pages ||
        plan.during_page_count[index] > pages - plan.during_first_page[index]) {
      throw std::invalid_argument(
          "native discovery during query exceeds declared region");
    }
  }
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
    Layout::FileOffsets offsets{};
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
  Builder total;
  for (const auto bytes : result.public_layout.region_bytes) {
    static_cast<void>(total.reserve({bytes, page}));
  }
  static_cast<void>(total.reserve({result.public_layout.monitor_bytes, page}));
  for (std::size_t guard = 0U; guard < 3U; ++guard) {
    static_cast<void>(total.reserve({page, page}));
  }
  result.public_layout.total_mapping_bytes = total.bytes;
  return result;
}

template <typename T>
auto storage(std::span<std::byte> mapping, std::size_t offset, std::size_t count)
    -> std::span<T> {
  return {reinterpret_cast<T*>(mapping.data() + offset), count};
}

auto scratch(std::span<std::byte> mapping, ScratchOffsets offsets,
             const NativeDiscoveryCapturePlan& plan) -> platform::ThreadMonitorScratch {
  return {mapped_discovery_detail::initialize_array<char>(mapping, offsets.first,
                                                          plan.thread_stat_bytes),
          mapped_discovery_detail::initialize_array<char>(mapping, offsets.status,
                                                          plan.thread_status_bytes),
          mapped_discovery_detail::initialize_array<char>(mapping, offsets.last,
                                                          plan.thread_stat_bytes),
          mapped_discovery_detail::initialize_array<unsigned long>(
              mapping, offsets.affinity, plan.thread_affinity_words)};
}

auto prepare_environment(Monitor& monitor, const Layout& layout,
                         const NativeDiscoveryCapturePlan& plan,
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

struct Bridge final {
  Core& core;
  Monitor& monitor;
  const Layout& layout;
  std::span<std::byte> core_bytes;
  std::span<std::byte> monitor_bytes;
  std::span<std::byte> controller_stack;

  auto tls(DiscoverySessionPhase phase) noexcept -> bool {
    const auto measurement = phase == DiscoverySessionPhase::measurement;
    const auto index = measurement ? 1U : 0U;
    const auto base = measurement ? 2U : 0U;
    const auto& snapshots = measurement ? core.runtime.tls_before_measurement()
                                        : core.runtime.tls_before_warmup();
    const auto workers = core.runtime.worker_regions();
    for (std::size_t role = 0U; role < 2U; ++role) {
      if (!native_discovery_tls_covered(snapshots[role], core.tls[base + role],
                                        workers[3U + role].mapping)) {
        return false;
      }
    }
    auto& observed = core.controller_tls[index];
    observed = platform::observe_thread_tls(core.tls[4U + index]);
    return native_discovery_tls_covered(observed, core.tls[4U + index],
                                        controller_stack) &&
           (!measurement ||
            platform::same_thread_tls(core.controller_tls[0U], core.tls[4U], observed,
                                      core.tls[5U]));
  }

  auto initialize() -> bool {
    const auto workers = core.runtime.worker_regions();
    std::copy(workers.begin(), workers.end(), monitor.regions.begin());
    const auto node = core.plan.controller_stack.requested_node;
    monitor.regions[5U] = {core_bytes, node};
    monitor.regions[6U] = {controller_stack, node};
    std::array<int, 2U> ids{};
    const auto& owner_snapshots = core.runtime.tls_before_warmup();
    const std::array owners{&monitor.producer, &monitor.consumer};
    for (std::size_t role = 0U; role < owners.size(); ++role) {
      const auto id = owner_snapshots[role].thread_before;
      if (!id.has_value() || !id->nonnegative_return() || id->return_value <= 0 ||
          id->return_value > std::numeric_limits<int>::max()) {
        core.result.stop = NativeDiscoveryCaptureStop::thread_monitor_failure;
        return false;
      }
      ids[role] = static_cast<int>(id->return_value);
      if (!owners[role]->prepare(ids[role], monitor.initial_scratch[role])) {
        core.result.stop = NativeDiscoveryCaptureStop::thread_monitor_failure;
        return false;
      }
    }
    const auto page = core.plan.discovery.arena.base_page_bytes;
    for (std::size_t index = 0U; index < kNativeDiscoveryObservations; ++index) {
      const auto region = index % kNativeDiscoveryRegions;
      const auto group = index / kNativeDiscoveryRegions;
      const auto phase = static_cast<DiscoverySessionPhase>(group / 3U);
      const auto moment = static_cast<DiscoveryResidencyMoment>(group % 3U);
      const bool during = moment == DiscoveryResidencyMoment::during;
      const auto offset = during ? core.plan.during_offset_ticks[group / 3U] : 0U;
      auto range = monitor.regions[region].mapping;
      if (during) {
        range = range.subspan(core.plan.during_first_page[region] * page,
                              core.plan.during_page_count[region] * page);
      }
      auto pointers = mapped_discovery_detail::initialize_array<void*>(
          monitor_bytes, layout.pointers[index], range.size() / page);
      auto statuses = mapped_discovery_detail::initialize_array<int>(
          monitor_bytes, layout.statuses[index], range.size() / page);
      std::construct_at(&monitor.prepared_pages[index], range, page, pointers,
                        statuses);
      ++monitor.constructed_queries;
      std::construct_at(&monitor.residency[index],
                        DiscoveryResidencyRequest{phase, moment, region, offset},
                        monitor.prepared_pages[index]);
      ++monitor.constructed_samples;
    }
    const DiscoveryControlPlan controls{{core.plan.workers.producer_stack.owner_cpu,
                                         core.plan.workers.consumer_stack.owner_cpu},
                                        ids,
                                        core.plan.counter_limits,
                                        core.plan.hardware_state};
    monitor.control_query.emplace(
        controls, owners, monitor.hardware, monitor.pages,
        std::span<DiscoveryControlSample, 6U>(monitor.controls.data(), 6U));
    monitor.query.emplace(*monitor.control_query, monitor.files);
    monitor.observer.emplace(
        core.plan.discovery.session,
        DiscoveryResidencyControls{page, core.plan.observer_wait_poll_limit},
        monitor.regions, monitor.residency, core.clock, *monitor.query, core.relax);
    return true;
  }

  auto before_phase(DiscoverySessionPhase phase) -> bool {
    if (!tls(phase)) {
      core.result.stop = NativeDiscoveryCaptureStop::tls_footprint_failure;
      return false;
    }
    if (!monitor.observer.has_value() && !initialize()) {
      return false;
    }
    return monitor.observer.has_value() && monitor.observer->before_phase(phase);
  }
  auto during_phase(DiscoverySessionPhase phase, DiscoveryObservationWindow window,
                    const std::atomic<std::uint32_t>& finished) noexcept -> bool {
    return monitor.observer.has_value() &&
           monitor.observer->during_phase(phase, window, finished);
  }
  auto after_phase(DiscoverySessionPhase phase) noexcept -> bool {
    return monitor.observer.has_value() && monitor.observer->after_phase(phase);
  }
};

struct Entry final {
  const NativeDiscoveryCapturePlan& plan;
  const Layout& layout;
  NativeDiscoveryPublication publication;
  Stack& stack;
  Mapping& core_mapping;
  Mapping& monitor_mapping;
  NativeDiscoveryCaptureResult& result;
  std::atomic<bool> creator_done{false};
  bool creator_started{false};

  static void run(void* context) noexcept {
    auto& self = *static_cast<Entry*>(context);
    // start_mapped_worker records attribute destruction on the creator after
    // pthread_create. Publish none of that evidence until this release/acquire
    // handoff; timeout retains failure and never enters capture.
    Relax relax;
    for (std::uint64_t poll = 0U; poll < self.plan.discovery.session.barrier_poll_limit;
         ++poll) {
      if (self.creator_done.load(std::memory_order_acquire)) {
        if (self.creator_started) {
          self.execute();
        } else {
          self.result.stop = NativeDiscoveryCaptureStop::controller_start_failure;
        }
        return;
      }
      relax.relax();
    }
    self.result.stop = NativeDiscoveryCaptureStop::controller_start_failure;
  }
  void execute() noexcept {
    Core* core = nullptr;
    Monitor* monitor = nullptr;
    try {
      if (!stack.prepared()) {
        result.stop = NativeDiscoveryCaptureStop::controller_preparation_failure;
      } else if (!core_mapping.prepare() || !monitor_mapping.prepare()) {
        result.stop = NativeDiscoveryCaptureStop::mapping_failure;
      } else {
        const auto origin = Clock::capture_origin();
        result.clock_origin = origin;
        if (origin.status != timing::ClockReadStatus::ok) {
          result.stop = NativeDiscoveryCaptureStop::clock_failure;
        } else {
          const auto core_bytes = core_mapping.mapped_bytes();
          const auto monitor_bytes = monitor_mapping.mapped_bytes();
          std::array<std::span<platform::ThreadTlsModule>, 6U> tls;
          for (std::size_t index = 0U; index < tls.size(); ++index) {
            tls[index] =
                mapped_discovery_detail::initialize_array<platform::ThreadTlsModule>(
                    core_bytes, layout.tls[index], plan.tls_module_capacity);
          }
          core =
              std::construct_at(reinterpret_cast<Core*>(core_bytes.data()), plan,
                                timing::ClockOrigin{origin.absolute_nanoseconds}, tls);
          core->result.clock_origin = origin;
          monitor = std::construct_at(reinterpret_cast<Monitor*>(monitor_bytes.data()));
          monitor->regions =
              mapped_discovery_detail::initialize_array<DiscoveryResidencyRegion>(
                  monitor_bytes, layout.regions, kNativeDiscoveryRegions);
          monitor->controls =
              mapped_discovery_detail::initialize_array<DiscoveryControlSample>(
                  monitor_bytes, layout.controls, 6U);
          monitor->prepared_pages = storage<platform::PreparedPageResidencyQuery>(
              monitor_bytes, layout.queries, kNativeDiscoveryObservations);
          monitor->residency = storage<DiscoveryResidencySample>(
              monitor_bytes, layout.residency, kNativeDiscoveryObservations);
          for (std::size_t role = 0U; role < 2U; ++role) {
            monitor->initial_scratch[role] =
                scratch(monitor_bytes, layout.thread_scratch[role], core->plan);
          }
          for (std::size_t group = 0U; group < 6U; ++group) {
            auto& row = monitor->controls[group];
            row.request = {static_cast<DiscoverySessionPhase>(group / 3U),
                           static_cast<DiscoveryResidencyMoment>(group % 3U),
                           plan.control_region_index,
                           group % 3U == 1U ? plan.during_offset_ticks[group / 3U]
                                            : 0U};
            for (std::size_t role = 0U; role < 2U; ++role) {
              row.scratch[role] =
                  scratch(monitor_bytes, layout.thread_scratch[2U + group * 2U + role],
                          core->plan);
            }
          }
          const bool environment_ready =
              prepare_environment(*monitor, layout, core->plan, monitor_bytes);
          if (!environment_ready) {
            core->result.stop = NativeDiscoveryCaptureStop::environment_monitor_failure;
          } else if (!monitor->hardware.prepare(plan.hardware_identity,
                                                plan.hardware_prestate)) {
            core->result.stop = NativeDiscoveryCaptureStop::hardware_monitor_failure;
          } else {
            Bridge bridge{*core,      *monitor,      layout,
                          core_bytes, monitor_bytes, stack.body()};
            core->result.session = core->runtime.run(bridge);
            if (core->result.stop == NativeDiscoveryCaptureStop::not_started) {
              core->result.stop =
                  native_discovery_detail::session_stop(*core->result.session);
            }
          }
        }
      }
    } catch (...) {
      if (core != nullptr) {
        core->result.stop = NativeDiscoveryCaptureStop::exception;
      } else {
        result.stop = NativeDiscoveryCaptureStop::exception;
      }
    }
    if (core != nullptr && monitor != nullptr) {
      // Runtime.run joins even rejected capture paths. Close observers before
      // publication so all close facts accompany the raw streams.
      monitor->producer.release();
      monitor->consumer.release();
      for (std::size_t index = 0U; index < monitor->constructed_files; ++index) {
        const bool closed = monitor->files[index].release();
        monitor->file_preparations[index] = monitor->files[index].preparation();
        core->result.stop = native_discovery_detail::after_cleanup(
            core->result.stop, closed,
            NativeDiscoveryCaptureStop::environment_monitor_failure);
      }
      const bool hardware_closed = monitor->hardware.release();
      core->result.stop = native_discovery_detail::after_cleanup(
          core->result.stop, hardware_closed,
          NativeDiscoveryCaptureStop::hardware_monitor_failure);
      for (const auto* owner : {&monitor->producer, &monitor->consumer}) {
        for (const auto& closed : owner->preparation().closes) {
          if (closed.has_value()) {
            core->result.stop = native_discovery_detail::after_cleanup(
                core->result.stop, closed->zero_return(),
                NativeDiscoveryCaptureStop::thread_monitor_failure);
          }
        }
      }
      try {
        publish(*core, *monitor);
      } catch (...) {
        core->result.stop = NativeDiscoveryCaptureStop::publication_failed;
      }
    }
    if (core != nullptr) {
      const bool workers_closed = core->runtime.close();
      core->result.worker_mappings =
          std::array{core->runtime.records().evidence(),
                     core->runtime.producer_memory().evidence(),
                     core->runtime.consumer_memory().evidence()};
      core->result.worker_stacks =
          std::array{core->runtime.producer_stack().evidence(),
                     core->runtime.consumer_stack().evidence()};
      if (!workers_closed) {
        core->result.stop = NativeDiscoveryCaptureStop::cleanup_failed;
      }
      result = core->result;
    }
    if (monitor != nullptr) {
      std::destroy_at(monitor);
    }
    if (core != nullptr) {
      std::destroy_at(core);
    }
    const bool monitor_released = monitor_mapping.release();
    const bool core_released = core_mapping.release();
    result.stop = native_discovery_detail::after_cleanup(
        result.stop, monitor_released && core_released,
        NativeDiscoveryCaptureStop::cleanup_failed);
    result.monitor_mapping = monitor_mapping.evidence();
    result.core_mapping = core_mapping.evidence();
  }

  void publish(Core& core, Monitor& monitor) {
    core.result.core_mapping = core_mapping.evidence();
    core.result.monitor_mapping = monitor_mapping.evidence();
    core.result.controller_stack = stack.evidence();
    const auto actual_regions = core.runtime.worker_regions();
    std::copy(actual_regions.begin(), actual_regions.end(), monitor.regions.begin());
    monitor.regions[5U] = {core_mapping.mapped_bytes(),
                           plan.controller_stack.requested_node};
    monitor.regions[6U] = {stack.body(), plan.controller_stack.requested_node};
    NativeDiscoveryPublicationView view{
        core.result,
        layout.public_layout,
        monitor.regions,
        monitor.residency.first(monitor.constructed_samples),
        monitor.controls,
        {},
        {},
        monitor.hardware.preparation(),
        {&monitor.producer.preparation(), &monitor.consumer.preparation()},
        {},
        {},
        core_mapping.mapped_bytes(),
        monitor_mapping.mapped_bytes()};
    for (std::size_t index = 0U; index < core.tls.size(); ++index) {
      view.tls_modules[index] = core.tls[index];
    }
    for (std::size_t role = 0U; role < 2U; ++role) {
      view.tls_snapshots[role] = core.runtime.tls_before_warmup()[role];
      view.tls_snapshots[2U + role] = core.runtime.tls_before_measurement()[role];
    }
    view.tls_snapshots[4U] = core.controller_tls[0U];
    view.tls_snapshots[5U] = core.controller_tls[1U];
    view.thread_preparation_scratch = monitor.initial_scratch;
    view.environment_preparations =
        monitor.file_preparations.first(monitor.constructed_files);
    view.environment_samples = monitor.file_samples.first(
        monitor.constructed_files * platform::kFileSnapshotGroups);
    view.worker_mappings = {&core.runtime.records().evidence(),
                            &core.runtime.producer_memory().evidence(),
                            &core.runtime.consumer_memory().evidence()};
    view.worker_stacks = {&core.runtime.producer_stack().evidence(),
                          &core.runtime.consumer_stack().evidence()};
    view.worker_preparation = {core.runtime.preparation().status(0U),
                               core.runtime.preparation().status(1U)};
    if (view.worker_preparation[0U] == MappedDiscoveryPreparationStop::ready) {
      view.arena = &core.runtime.preparation().arena();
    }
    for (std::size_t phase = 0U; phase < 2U; ++phase) {
      auto& prepared = core.runtime.preparation();
      if (prepared.status(0U) == MappedDiscoveryPreparationStop::ready) {
        view.producer[phase] = &prepared.producer_phase(phase == 0U);
      }
      if (prepared.status(1U) == MappedDiscoveryPreparationStop::ready) {
        view.consumer[phase] = &prepared.consumer_phase(phase == 0U);
      }
    }
    core.result.publication_attempted = true;
    core.result.publication_succeeded = publication.publish(publication.context, view);
    if (!core.result.publication_succeeded) {
      core.result.stop = NativeDiscoveryCaptureStop::publication_failed;
    }
  }
};

} // namespace

auto native_discovery_detail::session_stop(
    const DiscoverySessionResult& session) noexcept -> NativeDiscoveryCaptureStop {
  if (session.stop == DiscoverySessionStop::complete) {
    return NativeDiscoveryCaptureStop::complete;
  }
  if (session.stop != DiscoverySessionStop::trace_capacity ||
      !session.warmup_verified || !session.measurement_verified ||
      session.warmup_drain.stop != DiscoveryDrainStop::complete ||
      !session.warmup_drain.reset_verified ||
      session.measurement_drain.stop != DiscoveryDrainStop::complete ||
      session.warmup_drain.failed_clock_status.has_value() ||
      session.measurement_drain.failed_clock_status.has_value()) {
    return NativeDiscoveryCaptureStop::capture_failed;
  }
  for (std::size_t index = 0U; index < 2U; ++index) {
    const auto& observed = session.observations[index];
    if (session.preparation[index] != DiscoveryPreparationStatus::ready ||
        session.worker_exception[index] || !session.private_reset_verified[index] ||
        session.warmup[index].stop != DiscoveryWorkerStop::fixed_deadline ||
        session.warmup[index].failed_clock_status.has_value() ||
        session.measurement[index].failed_clock_status.has_value() ||
        !session.origins[index].has_value() ||
        session.observed_origins[index] != session.origins[index] ||
        session.origin_status[index] != timing::ClockReadStatus::ok ||
        observed.before != DiscoveryObservationStatus::accepted ||
        observed.during != DiscoveryObservationStatus::accepted ||
        observed.after != DiscoveryObservationStatus::accepted) {
      return NativeDiscoveryCaptureStop::capture_failed;
    }
  }
  const auto permissible_peer = [](DiscoveryWorkerStop stop) noexcept {
    return stop == DiscoveryWorkerStop::trace_capacity ||
           stop == DiscoveryWorkerStop::peer_stopped ||
           stop == DiscoveryWorkerStop::fixed_deadline;
  };
  const auto first = session.measurement[0U].stop;
  const auto second = session.measurement[1U].stop;
  if ((first == DiscoveryWorkerStop::trace_capacity && permissible_peer(second)) ||
      (second == DiscoveryWorkerStop::trace_capacity && permissible_peer(first))) {
    return NativeDiscoveryCaptureStop::trace_capacity;
  }
  return NativeDiscoveryCaptureStop::capture_failed;
}

auto native_discovery_detail::after_cleanup(NativeDiscoveryCaptureStop stop,
                                            bool succeeded,
                                            NativeDiscoveryCaptureStop failure) noexcept
    -> NativeDiscoveryCaptureStop {
  return !succeeded && (stop == NativeDiscoveryCaptureStop::complete ||
                        stop == NativeDiscoveryCaptureStop::trace_capacity)
             ? failure
             : stop;
}

auto native_discovery_layout(const NativeDiscoveryCapturePlan& plan)
    -> NativeDiscoveryCaptureLayout {
  return make_layout(plan).public_layout;
}

auto native_discovery_tls_covered(const platform::ThreadTlsSnapshot& snapshot,
                                  std::span<const platform::ThreadTlsModule> modules,
                                  std::span<const std::byte> owner_stack) noexcept
    -> bool {
  const auto begin = reinterpret_cast<std::uintptr_t>(owner_stack.data());
  if (snapshot.stop != platform::ThreadTlsStop::complete ||
      snapshot.iteration_return != 0 || !snapshot.fs_base.has_value() ||
      snapshot.used > modules.size() || owner_stack.empty() || begin == 0U ||
      owner_stack.size() > std::numeric_limits<std::uintptr_t>::max() - begin) {
    return false;
  }
  const auto end = begin + owner_stack.size();
  if (*snapshot.fs_base < begin || *snapshot.fs_base >= end) {
    return false;
  }
  for (const auto& module : modules.first(snapshot.used)) {
    if (module.bytes != 0U && (module.address < begin || module.address >= end ||
                               module.bytes > end - module.address)) {
      return false;
    }
  }
  return true;
}

auto run_native_discovery_capture(const NativeDiscoveryCapturePlan& plan,
                                  NativeDiscoveryPublication publication)
    -> NativeDiscoveryCaptureResult {
  if (publication.publish == nullptr) {
    throw std::invalid_argument(
        "native discovery requires synchronous raw publication");
  }
  const auto layout = make_layout(plan);
  // Stateless syscall adapter: no requested or observed hardware state is
  // shared. Evidence addresses are independent of an adapter stack lifetime.
  static platform::LinuxOwnerMemoryOperations operations;
  auto owner = plan.controller_stack;
  owner.bytes = layout.public_layout.core_bytes;
  Mapping core(owner, operations);
  owner.bytes = layout.public_layout.monitor_bytes;
  Mapping monitor(owner, operations);
  Stack stack(plan.controller_stack, operations);
  NativeDiscoveryCaptureResult result;
  Entry entry{plan, layout, publication, stack, core, monitor, result};
  const bool started = stack.start(&Entry::run, &entry);
  entry.creator_started = started;
  entry.creator_done.store(true, std::memory_order_release);
  stack.join();
  if (!started && entry.result.stop == NativeDiscoveryCaptureStop::not_started) {
    entry.result.stop = NativeDiscoveryCaptureStop::controller_start_failure;
  }
  entry.result.stop = native_discovery_detail::after_cleanup(
      entry.result.stop, stack.release(), NativeDiscoveryCaptureStop::cleanup_failed);
  entry.result.controller_stack = stack.evidence();
  entry.result.core_mapping = core.evidence();
  entry.result.monitor_mapping = monitor.evidence();
  return result;
}

} // namespace cpu_prefetch::calibration
