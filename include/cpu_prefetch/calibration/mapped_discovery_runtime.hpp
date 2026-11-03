#ifndef CPU_PREFETCH_CALIBRATION_MAPPED_DISCOVERY_RUNTIME_HPP
#define CPU_PREFETCH_CALIBRATION_MAPPED_DISCOVERY_RUNTIME_HPP

#include "cpu_prefetch/calibration/discovery_residency_observer.hpp"
#include "cpu_prefetch/calibration/mapped_discovery_preparation.hpp"
#include "cpu_prefetch/platform/thread_tls.hpp"

namespace cpu_prefetch::calibration {

struct DiscoveryRuntimePlacement final {
  platform::OwnerMappingPlan producer_stack;
  platform::OwnerMappingPlan consumer_stack;
};

struct DiscoveryRuntimeTlsStorage final {
  // Distinct caller-owned arrays for the two owners and two cold observations.
  std::array<std::span<platform::ThreadTlsModule>, 2U> before_warmup;
  std::array<std::span<platform::ThreadTlsModule>, 2U> before_measurement;
};

// One complete R0 runtime composition. Construct this object, Clock, Relax and
// TLS output in declared prepared control storage; invoke run on the declared
// mapped controller stack. The observer adds that shared/control footprint to
// worker_regions() and establishes actual placement/control evidence. This
// class is not an admission ticket, does not publish artifacts, and never
// converts successful preparation into observed residency.
template <typename Clock, typename Relax,
          typename MemoryOperations = platform::LinuxOwnerMemoryOperations,
          typename StackOperations = platform::LinuxOwnerMemoryOperations>
class MappedDiscoveryRuntime final {
public:
  MappedDiscoveryRuntime(MappedDiscoveryPlan plan, DiscoveryRuntimePlacement placement,
                         DiscoveryRuntimeTlsStorage tls, Clock& clock, Relax& relax)
      : plan_(std::move(plan)), placement_(placement), tls_(tls),
        layout_(mapped_discovery_layout(plan_)),
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
        preparation_(*this), backend_(plan_.session, clock, preparation_),
        threads_(
            DiscoveryWorkerStacks<StackOperations>{producer_stack_, consumer_stack_}),
        clock_(clock), relax_(relax) {
    if (placement_.producer_stack.verified_base_page_bytes !=
            plan_.arena.base_page_bytes ||
        placement_.consumer_stack.verified_base_page_bytes !=
            plan_.arena.base_page_bytes) {
      throw std::invalid_argument("runtime owners disagree on verified page size");
    }
    validate_tls_storage();
    if (!mapped_.has_value()) {
      throw std::logic_error("runtime provider was not constructed");
    }
    mapped_live_ = &*mapped_;
  }
  ~MappedDiscoveryRuntime() { static_cast<void>(close()); }
  MappedDiscoveryRuntime(const MappedDiscoveryRuntime&) = delete;
  auto operator=(const MappedDiscoveryRuntime&) -> MappedDiscoveryRuntime& = delete;

  template <typename Observer>
  [[nodiscard]] auto run(Observer& observer) -> DiscoverySessionResult {
    if (mapped_live_ == nullptr) {
      return {};
    }
    return run_discovery_session(plan_.session, clock_, backend_, relax_, observer,
                                 threads_, session_);
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
  auto preparation() -> MappedDiscoveryPreparation<MemoryOperations, Relax>& {
    if (mapped_live_ == nullptr) {
      throw std::logic_error("runtime provider is closed");
    }
    return *mapped_live_;
  }
  auto session() const noexcept -> const DiscoverySessionStorage& { return session_; }
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
    explicit Preparation(MappedDiscoveryRuntime& runtime) noexcept
        : runtime_(runtime) {}
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
    auto producer_phase(bool warmup) noexcept -> MappedProducerPhase& {
      return runtime_.mapped_live_->producer_phase(warmup);
    }
    auto consumer_phase(bool warmup) noexcept -> MappedConsumerPhase& {
      return runtime_.mapped_live_->consumer_phase(warmup);
    }
    auto ring() noexcept -> queue::RingSpscQueue& {
      return runtime_.mapped_live_->ring();
    }
    auto arena() const noexcept -> const workload::EventArena& {
      return runtime_.mapped_live_->arena();
    }

  private:
    MappedDiscoveryRuntime& runtime_;
  };

  const MappedDiscoveryPlan plan_;
  const DiscoveryRuntimePlacement placement_;
  const DiscoveryRuntimeTlsStorage tls_;
  const MappedDiscoveryLayout layout_;
  std::array<MemoryOperations, 3U> memory_operations_;
  std::array<StackOperations, 2U> stack_operations_;
  platform::OwnerMapping<MemoryOperations> records_;
  platform::OwnerMapping<MemoryOperations> producer_;
  platform::OwnerMapping<MemoryOperations> consumer_;
  platform::MappedWorkerThread<StackOperations> producer_stack_;
  platform::MappedWorkerThread<StackOperations> consumer_stack_;
  std::optional<MappedDiscoveryPreparation<MemoryOperations, Relax>> mapped_;
  MappedDiscoveryPreparation<MemoryOperations, Relax>* mapped_live_{nullptr};
  Preparation preparation_;
  DiscoveryRingPhaseBackend<Clock, Preparation> backend_;
  MappedDiscoveryThreads<StackOperations> threads_;
  DiscoverySessionStorage session_;
  std::array<platform::ThreadTlsSnapshot, 2U> tls_warmup_{};
  std::array<platform::ThreadTlsSnapshot, 2U> tls_measurement_{};
  Clock& clock_;
  Relax& relax_;
};

} // namespace cpu_prefetch::calibration

#endif
