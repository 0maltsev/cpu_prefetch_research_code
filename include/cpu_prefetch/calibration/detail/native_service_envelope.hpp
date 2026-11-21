#ifndef CPU_PREFETCH_CALIBRATION_DETAIL_NATIVE_SERVICE_ENVELOPE_HPP
#define CPU_PREFETCH_CALIBRATION_DETAIL_NATIVE_SERVICE_ENVELOPE_HPP

#include "cpu_prefetch/calibration/detail/native_capture_monitor.hpp"
#include "cpu_prefetch/calibration/native_formal_ring_capture.hpp"

namespace cpu_prefetch::calibration::native_capture_detail {

// One native cold envelope shared by statically typed formal runtimes. Traits
// bind storage/lifecycle/publication; no package choice enters worker loops.
// Existing diagnostic dispatch remains independent. No helper grants admission.
template <typename Traits> struct ServiceEnvelope final {
  static constexpr std::size_t extra_regions = [] {
    if constexpr (requires { Traits::extra_region_count; })
      return Traits::extra_region_count;
    else
      return std::size_t{0U};
  }();
  static constexpr std::size_t region_count = kNativeCaptureRegions + extra_regions;
  static constexpr std::size_t observation_count = 6U * region_count;

  using Plan = typename Traits::Plan;
  using PublicLayout = typename Traits::Layout;
  using Result = typename Traits::Result;
  using Publication = typename Traits::Publication;
  using Runtime = typename Traits::template Runtime<Clock, Relax>;
  using Mapping = platform::OwnerMapping<>;
  using Stack = platform::MappedWorkerThread<>;
  static auto after_cleanup(NativeCaptureStop stop, bool succeeded,
                            NativeCaptureStop failure) noexcept -> NativeCaptureStop {
    return !succeeded && stop == NativeCaptureStop::complete ? failure : stop;
  }
  struct Core final {
    Plan plan;
    Clock clock;
    Relax relax;
    std::array<std::span<platform::ThreadTlsModule>, 6U> tls;
    Runtime runtime;
    std::array<platform::ThreadTlsSnapshot, 2U> controller_tls{};
    Result result;

    Core(const Plan& input, timing::ClockOrigin origin,
         std::array<std::span<platform::ThreadTlsModule>, 6U> modules,
         std::array<std::span<std::byte>, 2U> termination)
        : plan(input), clock(origin), tls(modules),
          runtime(Traits::runtime_plan(plan), plan.controls.workers,
                  {{{tls[0U], tls[1U]}}, {{tls[2U], tls[3U]}}}, termination, clock,
                  relax) {}
  };

  struct Layout final {
    PublicLayout public_layout;
    std::array<std::size_t, 6U> tls;
    std::array<std::size_t, 2U> termination;
    std::size_t regions;
    std::size_t controls;
    std::size_t queries;
    std::size_t residency;
    std::array<std::size_t, observation_count> pointers;
    std::array<std::size_t, observation_count> statuses;
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

  static auto make_layout(const Plan& plan) -> Layout {
    const auto workers = Traits::worker_layout(plan);
    std::array<std::size_t, extra_regions> sizes{};
    if constexpr (extra_regions != 0U) {
      const auto shared = Traits::extra_regions(plan);
      for (std::size_t i = 0U; i < extra_regions; ++i)
        sizes[i] = shared[i].mapping.size();
    }
    return size_layout(plan, workers, sizes);
  }
  // The same arithmetic is used for cold prospective sizing. Execution always
  // enters through make_layout and its strict live worker/shared-view guards.
  static auto size_layout(const Plan& plan,
                          const decltype(PublicLayout::workers)& workers,
                          const std::array<std::size_t, extra_regions>& extra_sizes)
      -> Layout {
    Layout result{};
    const auto page = Traits::capture_plan(plan).arena.base_page_bytes;
    result.public_layout.workers = workers;
    const auto& session = Traits::capture_plan(plan).session;
    if (session.phases[0U].duration_ticks == 0U ||
        session.phases[1U].duration_ticks == 0U || !valid_service_plan(session) ||
        plan.controls.tls_module_capacity == 0U ||
        plan.controls.thread_stat_bytes == 0U ||
        plan.controls.thread_status_bytes == 0U ||
        plan.controls.thread_affinity_words == 0U ||
        plan.controls.thread_affinity_words >
            std::numeric_limits<unsigned int>::max() / sizeof(unsigned long) ||
        plan.controls.observer_wait_poll_limit == 0U ||
        plan.controls.control_region_index >= region_count ||
        plan.controls.during_offset_ticks[0U] >= session.phases[0U].duration_ticks ||
        plan.controls.during_offset_ticks[1U] >= session.phases[1U].duration_ticks ||
        plan.controls.workers.producer_stack.owner_cpu ==
            plan.controls.workers.consumer_stack.owner_cpu ||
        plan.controls.controller_stack.owner_cpu ==
            plan.controls.workers.producer_stack.owner_cpu ||
        plan.controls.controller_stack.owner_cpu ==
            plan.controls.workers.consumer_stack.owner_cpu) {
      throw std::invalid_argument("native formal capture requires explicit finite "
                                  "geometry and three distinct CPUs");
    }
    for (const auto stack :
         {plan.controls.workers.producer_stack, plan.controls.workers.consumer_stack,
          plan.controls.controller_stack}) {
      if (stack.verified_base_page_bytes != page || stack.bytes == 0U ||
          stack.bytes % page != 0U ||
          stack.bytes >
              static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max()) -
                  page ||
          stack.requested_node >= std::numeric_limits<unsigned long>::digits) {
        throw std::invalid_argument("native formal capture stack geometry is invalid");
      }
    }
    if (plan.controls.hardware_state != protocol::RequestedHardwareState::h0 &&
        plan.controls.hardware_state != protocol::RequestedHardwareState::h1) {
      throw std::invalid_argument("native formal capture requires H0 or H1");
    }
    for (const auto state :
         {protocol::RequestedHardwareState::h0, protocol::RequestedHardwareState::h1}) {
      const auto resolved = platform::make_hardware_prefetch_plan(
          plan.controls.hardware_identity, state, plan.controls.hardware_prestate);
      const auto* accepted = resolved.value_if();
      if (accepted == nullptr) {
        throw std::invalid_argument(
            "native formal capture prestate has no accepted H0/H1 plan");
      }
      for (const auto cpu : {plan.controls.workers.producer_stack.owner_cpu,
                             plan.controls.workers.consumer_stack.owner_cpu}) {
        if (std::none_of(accepted->requested.begin(), accepted->requested.end(),
                         [cpu](const auto& value) { return value.cpu == cpu; })) {
          throw std::invalid_argument(
              "native formal capture worker is outside the accepted MSR CPU set");
        }
      }
    }
    Builder core;
    static_cast<void>(core.array<Core>(1U, page));
    for (auto& offset : result.tls) {
      offset = core.array<platform::ThreadTlsModule>(
          plan.controls.tls_module_capacity, alignof(platform::ThreadTlsModule));
    }
    for (auto& offset : result.termination) {
      const auto line = Traits::capture_plan(plan).arena.cache_line_bytes;
      offset = core.reserve(
          {lifecycle::TerminationControl::storage_requirements({line}), line});
    }
    result.public_layout.core_bytes = core.reserve({0U, page});
    const auto& worker = result.public_layout.workers;
    result.public_layout.region_bytes = {worker.records_bytes,
                                         worker.producer_bytes,
                                         worker.consumer_bytes,
                                         plan.controls.workers.producer_stack.bytes,
                                         plan.controls.workers.consumer_stack.bytes,
                                         result.public_layout.core_bytes,
                                         plan.controls.controller_stack.bytes};
    if constexpr (extra_regions != 0U) {
      for (std::size_t i = 0U; i < extra_regions; ++i)
        result.public_layout.region_bytes[kNativeCaptureRegions + i] = extra_sizes[i];
    }
    for (std::size_t index = 0U; index < region_count; ++index) {
      const auto pages = result.public_layout.region_bytes[index] / page;
      if (plan.controls.during_page_count[index] == 0U ||
          plan.controls.during_first_page[index] >= pages ||
          plan.controls.during_page_count[index] >
              pages - plan.controls.during_first_page[index]) {
        throw std::invalid_argument(
            "native formal capture during query exceeds declared region");
      }
    }
    allocate_monitor_layout<region_count>(result, plan.controls, page);
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

  struct Bridge final {
    Core& core;
    Monitor& monitor;
    const Layout& layout;
    std::span<std::byte> core_bytes;
    std::span<std::byte> monitor_bytes;
    std::span<std::byte> controller_stack;

    auto tls(ServicePhase phase) noexcept -> bool {
      const auto measurement = phase == ServicePhase::measurement;
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
      const auto node = core.plan.controls.controller_stack.requested_node;
      monitor.regions[5U] = {core_bytes, node};
      monitor.regions[6U] = {controller_stack, node};
      if constexpr (extra_regions != 0U) {
        const auto shared = Traits::extra_regions(core.plan);
        std::copy(shared.begin(), shared.end(),
                  monitor.regions.begin() + kNativeCaptureRegions);
      }
      std::array<int, 2U> ids{};
      const auto& owner_snapshots = core.runtime.tls_before_warmup();
      const std::array owners{&monitor.producer, &monitor.consumer};
      for (std::size_t role = 0U; role < owners.size(); ++role) {
        const auto id = owner_snapshots[role].thread_before;
        if (!id.has_value() || !id->nonnegative_return() || id->return_value <= 0 ||
            id->return_value > std::numeric_limits<int>::max()) {
          core.result.stop = NativeCaptureStop::thread_monitor_failure;
          return false;
        }
        ids[role] = static_cast<int>(id->return_value);
        if (!owners[role]->prepare(ids[role], monitor.initial_scratch[role])) {
          core.result.stop = NativeCaptureStop::thread_monitor_failure;
          return false;
        }
      }
      const auto page = Traits::capture_plan(core.plan).arena.base_page_bytes;
      for (std::size_t index = 0U; index < observation_count; ++index) {
        const auto region = index % region_count;
        const auto group = index / region_count;
        const auto phase = static_cast<DiscoverySessionPhase>(group / 3U);
        const auto moment = static_cast<DiscoveryResidencyMoment>(group % 3U);
        const bool during = moment == DiscoveryResidencyMoment::during;
        const auto offset =
            during ? core.plan.controls.during_offset_ticks[group / 3U] : 0U;
        auto range = monitor.regions[region].mapping;
        if (during) {
          range = range.subspan(core.plan.controls.during_first_page[region] * page,
                                core.plan.controls.during_page_count[region] * page);
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
      const DiscoveryControlPlan controls{
          {core.plan.controls.workers.producer_stack.owner_cpu,
           core.plan.controls.workers.consumer_stack.owner_cpu},
          ids,
          core.plan.controls.counter_limits,
          core.plan.controls.hardware_state};
      monitor.control_query.emplace(
          controls, owners, monitor.hardware, monitor.pages,
          std::span<DiscoveryControlSample, 6U>(monitor.controls.data(), 6U));
      monitor.query.emplace(*monitor.control_query, monitor.files);
      monitor.observer.emplace(
          Traits::observer_plan(Traits::capture_plan(core.plan)),
          DiscoveryResidencyControls{page, core.plan.controls.observer_wait_poll_limit},
          monitor.regions, monitor.residency, core.clock, *monitor.query, core.relax);
      return true;
    }

    auto before_phase(ServicePhase phase) -> bool {
      if (!tls(phase)) {
        core.result.stop = NativeCaptureStop::tls_footprint_failure;
        return false;
      }
      if (!monitor.observer.has_value() && !initialize()) {
        return false;
      }
      return monitor.observer.has_value() &&
             monitor.observer->before_phase(static_cast<DiscoverySessionPhase>(phase));
    }
    auto during_phase(ServicePhase phase, ServiceWindow window,
                      const std::atomic<std::uint32_t>& finished) noexcept -> bool {
      return monitor.observer.has_value() &&
             monitor.observer->during_phase(
                 static_cast<DiscoverySessionPhase>(phase),
                 {window.origin_ticks, window.duration_ticks}, finished);
    }
    auto after_phase(ServicePhase phase) noexcept -> bool {
      return monitor.observer.has_value() &&
             monitor.observer->after_phase(static_cast<DiscoverySessionPhase>(phase));
    }
  };

  struct Entry final {
    const Plan& plan;
    const Layout& layout;
    Publication publication;
    Stack& stack;
    Mapping& core_mapping;
    Mapping& monitor_mapping;
    Result& result;
    std::atomic<bool> creator_done{false};
    bool creator_started{false};

    static void run(void* context) noexcept {
      auto& self = *static_cast<Entry*>(context);
      // start_mapped_worker records attribute destruction on the creator after
      // pthread_create. Publish none of that evidence until this release/acquire
      // handoff; timeout retains failure and never enters capture.
      Relax relax;
      for (std::uint64_t poll = 0U;
           poll < Traits::capture_plan(self.plan).session.barrier_poll_limit; ++poll) {
        if (self.creator_done.load(std::memory_order_acquire)) {
          if (self.creator_started) {
            self.execute();
          } else {
            self.result.stop = NativeCaptureStop::controller_start_failure;
          }
          return;
        }
        relax.relax();
      }
      self.result.stop = NativeCaptureStop::controller_start_failure;
    }
    void execute() noexcept {
      Core* core = nullptr;
      Monitor* monitor = nullptr;
      try {
        if (!stack.prepared()) {
          result.stop = NativeCaptureStop::controller_preparation_failure;
        } else if (!core_mapping.prepare() || !monitor_mapping.prepare()) {
          result.stop = NativeCaptureStop::mapping_failure;
        } else {
          const auto origin = Clock::capture_origin();
          result.clock_origin = origin;
          if (origin.status != timing::ClockReadStatus::ok) {
            result.stop = NativeCaptureStop::clock_failure;
          } else {
            const auto core_bytes = core_mapping.mapped_bytes();
            const auto monitor_bytes = monitor_mapping.mapped_bytes();
            std::array<std::span<platform::ThreadTlsModule>, 6U> tls;
            for (std::size_t index = 0U; index < tls.size(); ++index) {
              tls[index] =
                  mapped_discovery_detail::initialize_array<platform::ThreadTlsModule>(
                      core_bytes, layout.tls[index], plan.controls.tls_module_capacity);
            }
            std::array<std::span<std::byte>, 2U> termination;
            for (std::size_t index = 0U; index < 2U; ++index) {
              termination[index] = mapped_discovery_detail::initialize_array<std::byte>(
                  core_bytes, layout.termination[index],
                  Traits::capture_plan(plan).arena.cache_line_bytes);
            }
            core = std::construct_at(reinterpret_cast<Core*>(core_bytes.data()), plan,
                                     timing::ClockOrigin{origin.absolute_nanoseconds},
                                     tls, termination);
            core->result.clock_origin = origin;
            monitor =
                std::construct_at(reinterpret_cast<Monitor*>(monitor_bytes.data()));
            monitor->regions =
                mapped_discovery_detail::initialize_array<DiscoveryResidencyRegion>(
                    monitor_bytes, layout.regions, region_count);
            monitor->controls =
                mapped_discovery_detail::initialize_array<DiscoveryControlSample>(
                    monitor_bytes, layout.controls, 6U);
            monitor->prepared_pages = storage<platform::PreparedPageResidencyQuery>(
                monitor_bytes, layout.queries, observation_count);
            monitor->residency = storage<DiscoveryResidencySample>(
                monitor_bytes, layout.residency, observation_count);
            for (std::size_t role = 0U; role < 2U; ++role) {
              monitor->initial_scratch[role] = scratch(
                  monitor_bytes, layout.thread_scratch[role], core->plan.controls);
            }
            for (std::size_t group = 0U; group < 6U; ++group) {
              auto& row = monitor->controls[group];
              row.request = {static_cast<DiscoverySessionPhase>(group / 3U),
                             static_cast<DiscoveryResidencyMoment>(group % 3U),
                             plan.controls.control_region_index,
                             group % 3U == 1U
                                 ? plan.controls.during_offset_ticks[group / 3U]
                                 : 0U};
              for (std::size_t role = 0U; role < 2U; ++role) {
                row.scratch[role] = scratch(
                    monitor_bytes, layout.thread_scratch[2U + group * 2U + role],
                    core->plan.controls);
              }
            }
            const bool environment_ready = prepare_environment(
                *monitor, layout, core->plan.controls, monitor_bytes);
            if (!environment_ready) {
              core->result.stop = NativeCaptureStop::environment_monitor_failure;
            } else if (!monitor->hardware.prepare(plan.controls.hardware_identity,
                                                  plan.controls.hardware_prestate)) {
              core->result.stop = NativeCaptureStop::hardware_monitor_failure;
            } else {
              Bridge bridge{*core,      *monitor,      layout,
                            core_bytes, monitor_bytes, stack.body()};
              core->result.session = core->runtime.run(bridge);
              if (core->result.stop == NativeCaptureStop::not_started) {
                core->result.stop = Traits::session_stop(*core->result.session);
              }
            }
          }
        }
      } catch (...) {
        if (core != nullptr) {
          core->result.stop = NativeCaptureStop::exception;
        } else {
          result.stop = NativeCaptureStop::exception;
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
          core->result.stop =
              after_cleanup(core->result.stop, closed,
                            NativeCaptureStop::environment_monitor_failure);
        }
        const bool hardware_closed = monitor->hardware.release();
        core->result.stop = after_cleanup(core->result.stop, hardware_closed,
                                          NativeCaptureStop::hardware_monitor_failure);
        for (const auto* owner : {&monitor->producer, &monitor->consumer}) {
          for (const auto& closed : owner->preparation().closes) {
            if (closed.has_value()) {
              core->result.stop =
                  after_cleanup(core->result.stop, closed->zero_return(),
                                NativeCaptureStop::thread_monitor_failure);
            }
          }
        }
        try {
          publish(*core, *monitor);
        } catch (...) {
          core->result.stop = NativeCaptureStop::publication_failed;
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
          core->result.stop = NativeCaptureStop::cleanup_failed;
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
      result.stop = after_cleanup(result.stop, monitor_released && core_released,
                                  NativeCaptureStop::cleanup_failed);
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
                             plan.controls.controller_stack.requested_node};
      monitor.regions[6U] = {stack.body(),
                             plan.controls.controller_stack.requested_node};
      if constexpr (extra_regions != 0U) {
        const auto shared = Traits::extra_regions(core.plan);
        std::copy(shared.begin(), shared.end(),
                  monitor.regions.begin() + kNativeCaptureRegions);
      }
      NativeCaptureObservationView view{
          monitor.regions,
          monitor.residency.first(monitor.constructed_samples),
          monitor.controls,
          {},
          {},
          monitor.hardware.preparation(),
          {&monitor.producer.preparation(), &monitor.consumer.preparation()},
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
      core.result.publication_attempted = true;
      core.result.publication_succeeded = Traits::publish(
          publication, core.result, layout.public_layout, view, core.runtime);
      if (!core.result.publication_succeeded) {
        core.result.stop = NativeCaptureStop::publication_failed;
      }
    }
  };
  static auto run(const Plan& plan, Publication publication) -> Result {
    if (publication.publish == nullptr) {
      throw std::invalid_argument(
          "native formal capture requires synchronous raw publication");
    }
    const auto layout = make_layout(plan);
    // Stateless syscall adapter: no requested or observed hardware state is
    // shared. Evidence addresses are independent of an adapter stack lifetime.
    static platform::LinuxOwnerMemoryOperations operations;
    auto owner = plan.controls.controller_stack;
    owner.bytes = layout.public_layout.core_bytes;
    Mapping core(owner, operations);
    owner.bytes = layout.public_layout.monitor_bytes;
    Mapping monitor(owner, operations);
    Stack stack(plan.controls.controller_stack, operations);
    Result result;
    Entry entry{plan, layout, publication, stack, core, monitor, result};
    const bool started = stack.start(&Entry::run, &entry);
    entry.creator_started = started;
    entry.creator_done.store(true, std::memory_order_release);
    stack.join();
    if (!started && entry.result.stop == NativeCaptureStop::not_started) {
      entry.result.stop = NativeCaptureStop::controller_start_failure;
    }
    entry.result.stop = after_cleanup(entry.result.stop, stack.release(),
                                      NativeCaptureStop::cleanup_failed);
    entry.result.controller_stack = stack.evidence();
    entry.result.core_mapping = core.evidence();
    entry.result.monitor_mapping = monitor.evidence();
    return result;
  }
};
} // namespace cpu_prefetch::calibration::native_capture_detail
#endif
