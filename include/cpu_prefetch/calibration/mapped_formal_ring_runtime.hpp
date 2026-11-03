#ifndef CPU_PREFETCH_CALIBRATION_MAPPED_FORMAL_RING_RUNTIME_HPP
#define CPU_PREFETCH_CALIBRATION_MAPPED_FORMAL_RING_RUNTIME_HPP

#include "cpu_prefetch/calibration/discovery_residency_observer.hpp"
#include "cpu_prefetch/calibration/mapped_formal_ring_preparation.hpp"
#include "cpu_prefetch/platform/thread_tls.hpp"

namespace cpu_prefetch::calibration {

// Typed D210 runtime policy. Other service packages can supply their own
// preparation/backend policy while reusing this exact owner/stack/TLS lifetime.
struct FormalRingRuntimePolicy final {
  using Plan = MappedFormalRingPlan;
  using Layout = MappedFormalRingLayout;
  using SessionStorage = ServiceSessionStorage;
  using SessionResult = ServiceSessionResult;
  static auto base_plan(const Plan& plan) noexcept -> const Plan& { return plan; }
  static auto base_plan(const Plan&&) -> const Plan& = delete;
  template <typename Operations, typename Relax>
  using Provider = MappedFormalRingPreparation<Operations, Relax>;
  template <typename Clock, typename Preparation>
  using Backend = FormalRingSessionBackend<Clock, Preparation>;
  static auto layout(const Plan& plan) -> Layout {
    return mapped_formal_ring_layout(plan);
  }
  template <typename Clock, typename Preparation>
  static auto make_backend(const Plan& plan, Clock& clock, Preparation& preparation)
      -> Backend<Clock, Preparation> {
    return {plan.session, clock, preparation};
  }
  template <typename Clock, typename Preparation, typename Relax, typename Observer,
            typename Threads>
  static auto run(const Plan&, Backend<Clock, Preparation>& backend, Preparation&,
                  Relax& relax, Observer& observer, Threads& threads,
                  ServiceSessionStorage& storage) -> ServiceSessionResult {
    return run_formal_ring_session(backend, relax, observer, threads, storage);
  }
};

// Persistent service runtime, statically bound to its capture/storage policy. Construct
// this object, Clock, Relax and TLS output in declared prepared control storage; invoke
// run on the declared mapped controller stack. The observer adds that shared/control
// footprint to worker_regions() and establishes actual placement/control evidence. This
// class is not an admission ticket, does not publish artifacts, and never
// converts successful preparation into observed residency.
template <typename Clock, typename Relax, typename Policy = FormalRingRuntimePolicy,
          typename MemoryOperations = platform::LinuxOwnerMemoryOperations,
          typename StackOperations = platform::LinuxOwnerMemoryOperations>
class MappedServiceRuntime final {
public:
  MappedServiceRuntime(typename Policy::Plan plan, DiscoveryRuntimePlacement placement,
                       DiscoveryRuntimeTlsStorage tls,
                       std::array<std::span<std::byte>, 2U> termination, Clock& clock,
                       Relax& relax)
      : plan_(std::move(plan)), placement_(placement), tls_(tls),
        layout_(Policy::layout(plan_)),
        records_(memory_plan(layout_.records_bytes, placement_.producer_stack),
                 memory_operations_[0U]),
        producer_(memory_plan(layout_.producer_bytes, placement_.producer_stack),
                  memory_operations_[1U]),
        consumer_(memory_plan(layout_.consumer_bytes, placement_.consumer_stack),
                  memory_operations_[2U]),
        producer_stack_(placement_.producer_stack, stack_operations_[0U]),
        consumer_stack_(placement_.consumer_stack, stack_operations_[1U]),
        mapped_(
            std::in_place, plan_,
            MappedDiscoveryRegions<MemoryOperations>{records_, producer_, consumer_},
            relax),
        preparation_(*this), backend_(Policy::make_backend(plan_, clock, preparation_)),
        threads_(
            DiscoveryWorkerStacks<StackOperations>{producer_stack_, consumer_stack_}),
        warmup_({Policy::base_plan(plan_).arena.cache_line_bytes},
                checked_termination(termination, 0U)),
        measurement_({Policy::base_plan(plan_).arena.cache_line_bytes},
                     termination[1U]),
        session_({warmup_, measurement_}), relax_(relax) {
    if (placement_.producer_stack.verified_base_page_bytes !=
            Policy::base_plan(plan_).arena.base_page_bytes ||
        placement_.consumer_stack.verified_base_page_bytes !=
            Policy::base_plan(plan_).arena.base_page_bytes) {
      throw std::invalid_argument("runtime owners disagree on verified page size");
    }
    validate_tls_storage();
    if (!mapped_.has_value()) {
      throw std::logic_error("runtime provider was not constructed");
    }
    mapped_live_ = &*mapped_;
  }
  ~MappedServiceRuntime() { static_cast<void>(close()); }
  MappedServiceRuntime(const MappedServiceRuntime&) = delete;
  auto operator=(const MappedServiceRuntime&) -> MappedServiceRuntime& = delete;

  template <typename Observer>
  [[nodiscard]] auto run(Observer& observer) -> typename Policy::SessionResult {
    if (mapped_live_ == nullptr) {
      return {};
    }
    return Policy::run(plan_, backend_, preparation_, relax_, observer, threads_,
                       session_);
  }
  // Controller-only after publication. Join first, then destroy typed objects
  // before releasing their storage. Every release is attempted even if another
  // fails; underlying one-shot release records preserve the first outcome.
  [[nodiscard]] auto close() noexcept -> bool {
    threads_.join();
    mapped_live_ = nullptr;
    mapped_.reset();
    const bool records = records_.release();
    const bool producer = producer_.release();
    const bool consumer = consumer_.release();
    const bool producer_stack = producer_stack_.release();
    const bool consumer_stack = consumer_stack_.release();
    return records && producer && consumer && producer_stack && consumer_stack;
  }
  [[nodiscard]] auto worker_regions() const noexcept
      -> std::array<DiscoveryResidencyRegion, 5U> {
    return {{{records_.mapped_bytes(), placement_.producer_stack.requested_node},
             {producer_.mapped_bytes(), placement_.producer_stack.requested_node},
             {consumer_.mapped_bytes(), placement_.consumer_stack.requested_node},
             {producer_stack_.body(), placement_.producer_stack.requested_node},
             {consumer_stack_.body(), placement_.consumer_stack.requested_node}}};
  }
  auto preparation() -> typename Policy::template Provider<MemoryOperations, Relax>& {
    if (mapped_live_ == nullptr) {
      throw std::logic_error("runtime provider is closed");
    }
    return *mapped_live_;
  }
  auto session() const noexcept -> const typename Policy::SessionStorage& {
    return session_;
  }
  auto mapping_operations(std::size_t index) -> MemoryOperations& {
    return memory_operations_.at(index);
  }
  auto records() const noexcept -> const platform::OwnerMapping<MemoryOperations>& {
    return records_;
  }
  auto producer_memory() const noexcept
      -> const platform::OwnerMapping<MemoryOperations>& {
    return producer_;
  }
  auto consumer_memory() const noexcept
      -> const platform::OwnerMapping<MemoryOperations>& {
    return consumer_;
  }
  auto producer_stack() const noexcept
      -> const platform::MappedWorkerThread<StackOperations>& {
    return producer_stack_;
  }
  auto consumer_stack() const noexcept
      -> const platform::MappedWorkerThread<StackOperations>& {
    return consumer_stack_;
  }
  auto tls_before_warmup() const noexcept
      -> const std::array<platform::ThreadTlsSnapshot, 2U>& {
    return tls_warmup_;
  }
  auto tls_before_measurement() const noexcept
      -> const std::array<platform::ThreadTlsSnapshot, 2U>& {
    return tls_measurement_;
  }

private:
  auto checked_termination(std::array<std::span<std::byte>, 2U> spans,
                           std::size_t selected) -> std::span<std::byte> {
    const auto size = lifecycle::TerminationControl::storage_requirements(
        {Policy::base_plan(plan_).arena.cache_line_bytes});
    const auto object = reinterpret_cast<std::uintptr_t>(this);
    for (const auto bytes : spans) {
      const auto begin = reinterpret_cast<std::uintptr_t>(bytes.data());
      if (bytes.size() != size || begin == 0U ||
          !queue::detail::is_aligned(bytes.data(), size) ||
          bytes.size() > std::numeric_limits<std::uintptr_t>::max() - begin ||
          (begin < object + sizeof(*this) && object < begin + bytes.size())) {
        throw std::invalid_argument("invalid runtime termination storage");
      }
    }
    const auto first = reinterpret_cast<std::uintptr_t>(spans[0U].data());
    const auto second = reinterpret_cast<std::uintptr_t>(spans[1U].data());
    if (first < second + size && second < first + size) {
      throw std::invalid_argument("runtime termination lines overlap");
    }
    return spans[selected];
  }
  static auto memory_plan(std::size_t bytes, platform::OwnerMappingPlan owner) noexcept
      -> platform::OwnerMappingPlan {
    owner.bytes = bytes;
    return owner;
  }
  void validate_tls_storage() const {
    const std::array spans{tls_.before_warmup[0U], tls_.before_warmup[1U],
                           tls_.before_measurement[0U], tls_.before_measurement[1U]};
    for (std::size_t index = 0U; index < spans.size(); ++index) {
      const auto span = spans[index];
      const auto begin = reinterpret_cast<std::uintptr_t>(span.data());
      if (span.empty() || begin == 0U ||
          span.size() > std::numeric_limits<std::size_t>::max() /
                            sizeof(platform::ThreadTlsModule) ||
          span.size_bytes() > std::numeric_limits<std::uintptr_t>::max() - begin) {
        throw std::invalid_argument("runtime TLS storage is empty or overflows");
      }
      for (std::size_t prior = 0U; prior < index; ++prior) {
        const auto other = reinterpret_cast<std::uintptr_t>(spans[prior].data());
        if (begin < other + spans[prior].size_bytes() &&
            other < begin + span.size_bytes()) {
          throw std::invalid_argument("runtime TLS snapshots alias");
        }
      }
    }
  }
  auto observe_tls(std::size_t role, bool measurement) noexcept -> bool {
    auto& snapshot = measurement ? tls_measurement_[role] : tls_warmup_[role];
    const auto output =
        measurement ? tls_.before_measurement[role] : tls_.before_warmup[role];
    snapshot = platform::observe_thread_tls(output);
    if (snapshot.stop != platform::ThreadTlsStop::complete) {
      return false;
    }
    return !measurement ||
           platform::same_thread_tls(tls_warmup_[role], tls_.before_warmup[role],
                                     snapshot, output);
  }
  class Preparation final {
  public:
    explicit Preparation(MappedServiceRuntime& runtime) noexcept : runtime_(runtime) {}
    auto prepare_producer() noexcept -> bool {
      return runtime_.mapped_live_->prepare_producer() &&
             runtime_.observe_tls(0U, false);
    }
    auto prepare_consumer() noexcept -> bool {
      return runtime_.mapped_live_->prepare_consumer() &&
             runtime_.observe_tls(1U, false);
    }
    auto before_measurement_producer() noexcept -> bool {
      return runtime_.observe_tls(0U, true);
    }
    auto before_measurement_consumer() noexcept -> bool {
      return runtime_.observe_tls(1U, true);
    }
    auto producer_phase(bool warmup) noexcept -> decltype(auto) {
      return runtime_.mapped_live_->producer_phase(warmup);
    }
    auto consumer_phase(bool warmup) noexcept -> decltype(auto) {
      return runtime_.mapped_live_->consumer_phase(warmup);
    }
    auto run_id(bool warmup) const noexcept -> const protocol::RunId& {
      return Policy::base_plan(runtime_.plan_).run_ids[warmup ? 0U : 1U];
    }
    auto queue() noexcept -> decltype(auto) { return runtime_.mapped_live_->queue(); }
    auto package() noexcept -> decltype(auto) {
      return runtime_.mapped_live_->package();
    }
    auto schedule(ServicePhase phase) const noexcept
        -> lifecycle::PreparedScheduleView {
      return runtime_.mapped_live_->schedule(phase);
    }
    auto ring() noexcept -> queue::RingSpscQueue& {
      return runtime_.mapped_live_->ring();
    }
    auto arena() const noexcept -> const workload::EventArena& {
      return runtime_.mapped_live_->arena();
    }

  private:
    MappedServiceRuntime& runtime_;
  };

  const typename Policy::Plan plan_;
  const DiscoveryRuntimePlacement placement_;
  const DiscoveryRuntimeTlsStorage tls_;
  const typename Policy::Layout layout_;
  std::array<MemoryOperations, 3U> memory_operations_;
  std::array<StackOperations, 2U> stack_operations_;
  platform::OwnerMapping<MemoryOperations> records_;
  platform::OwnerMapping<MemoryOperations> producer_;
  platform::OwnerMapping<MemoryOperations> consumer_;
  platform::MappedWorkerThread<StackOperations> producer_stack_;
  platform::MappedWorkerThread<StackOperations> consumer_stack_;
  std::optional<typename Policy::template Provider<MemoryOperations, Relax>> mapped_;
  typename Policy::template Provider<MemoryOperations, Relax>* mapped_live_{nullptr};
  Preparation preparation_;
  typename Policy::template Backend<Clock, Preparation> backend_;
  MappedDiscoveryThreads<StackOperations> threads_;
  lifecycle::TerminationControl warmup_;
  lifecycle::TerminationControl measurement_;
  typename Policy::SessionStorage session_;
  std::array<platform::ThreadTlsSnapshot, 2U> tls_warmup_{};
  std::array<platform::ThreadTlsSnapshot, 2U> tls_measurement_{};
  Relax& relax_;
};

template <typename Clock, typename Relax,
          typename MemoryOperations = platform::LinuxOwnerMemoryOperations,
          typename StackOperations = platform::LinuxOwnerMemoryOperations>
using MappedFormalRingRuntime =
    MappedServiceRuntime<Clock, Relax, FormalRingRuntimePolicy, MemoryOperations,
                         StackOperations>;

} // namespace cpu_prefetch::calibration

#endif
