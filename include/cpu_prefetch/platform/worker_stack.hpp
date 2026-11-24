#ifndef CPU_PREFETCH_PLATFORM_WORKER_STACK_HPP
#define CPU_PREFETCH_PLATFORM_WORKER_STACK_HPP

#include "cpu_prefetch/platform/owner_mapping.hpp"

#include <exception>
#include <pthread.h>

namespace cpu_prefetch::platform {

using WorkerEntry = void (*)(void*) noexcept;

// pthread APIs return error numbers directly, independently of errno.
struct WorkerThreadCalls final {
  std::optional<int> attribute_init;
  std::optional<int> attribute_stack;
  std::optional<int> attribute_guard;
  std::optional<int> attribute_affinity;
  std::optional<int> create;
  std::optional<int> attribute_destroy;
  std::optional<int> join;
};

[[nodiscard]] auto start_mapped_worker(pthread_t& thread, std::span<std::byte> stack,
                                       std::uint32_t cpu, void* (*entry)(void*),
                                       void* context, WorkerThreadCalls& calls) noexcept
    -> bool;

enum class WorkerStackStop : std::uint8_t {
  not_started,
  invalid_plan,
  geometry_failure,
  map_failure,
  binding_failure,
  huge_page_control_failure,
  guard_failure,
  thread_start_failure,
  owner_readback_failure,
  populate_failure,
  lock_failure,
  ready,
};

struct WorkerStackEvidence final {
  OwnerMappingPlan requested;
  std::optional<LinuxCallResult> base_page_bytes;
  std::optional<LinuxCallResult> minimum_stack_bytes;
  std::optional<LinuxMappingResult> mapping;
  std::optional<LinuxCallResult> binding;
  std::optional<LinuxCallResult> no_huge_pages;
  std::optional<LinuxCallResult> guard;
  std::optional<OwnerThreadObservation> before_populate;
  std::optional<LinuxCallResult> populate;
  std::optional<LinuxCallResult> lock;
  std::optional<OwnerThreadObservation> after_populate;
  std::optional<LinuxCallResult> unlock;
  std::optional<LinuxCallResult> unmap;
  WorkerThreadCalls thread;
  WorkerStackStop stop{WorkerStackStop::not_started};
  bool cleanup_attempted{false};
};

// x86-64 downward-growing stack: one explicit low guard plus requested body.
// Creator binds the new untouched allocation before pthread startup writes.
// Worker prefaults without overwriting live frames. No first-touch actor claim
// is made for libc startup metadata. Separate residency/smaps checks remain
// required. Caller owns this object and callback context until join completes;
// inspect evidence only before start or after join. No reuse or detach.
template <typename Operations = LinuxOwnerMemoryOperations>
class MappedWorkerThread final {
public:
  MappedWorkerThread(OwnerMappingPlan plan, Operations& operations) noexcept
      : operations_(operations), evidence_{} {
    evidence_.requested = plan;
  }
  ~MappedWorkerThread() {
    join();
    static_cast<void>(release());
  }
  MappedWorkerThread(const MappedWorkerThread&) = delete;
  auto operator=(const MappedWorkerThread&) -> MappedWorkerThread& = delete;
  MappedWorkerThread(MappedWorkerThread&&) = delete;
  auto operator=(MappedWorkerThread&&) -> MappedWorkerThread& = delete;

  [[nodiscard]] auto start(WorkerEntry entry, void* context) noexcept -> bool {
    if (attempted_ || evidence_.cleanup_attempted) {
      return false;
    }
    attempted_ = true;
    if (entry == nullptr || !reserve()) {
      if (entry == nullptr) {
        evidence_.stop = WorkerStackStop::invalid_plan;
      }
      return false;
    }
    entry_ = entry;
    context_ = context;
    // Only the worker writes stop/owner observations from this point until join.
    started_ = start_mapped_worker(thread_, body(), evidence_.requested.owner_cpu,
                                   &invoke, this, evidence_.thread);
    if (!started_) {
      return fail(WorkerStackStop::thread_start_failure);
    }
    return evidence_.thread.attribute_destroy.has_value() &&
           *evidence_.thread.attribute_destroy == 0;
  }

  // Read on this worker, or after join. This is not residency qualification.
  [[nodiscard]] auto prepared() const noexcept -> bool {
    return evidence_.stop == WorkerStackStop::ready && address_ != nullptr &&
           !evidence_.cleanup_attempted;
  }
  void join() noexcept {
    if (started_ && !joined_) {
      evidence_.thread.join = ::pthread_join(thread_, nullptr);
      if (*evidence_.thread.join != 0) {
        // Returning would destroy a context/stack potentially still in use.
        std::terminate();
      }
      joined_ = true;
    }
  }
  [[nodiscard]] auto body() const noexcept -> std::span<std::byte> {
    return address_ == nullptr
               ? std::span<std::byte>{}
               : std::span<std::byte>{address_ +
                                          evidence_.requested.verified_base_page_bytes,
                                      evidence_.requested.bytes};
  }
  [[nodiscard]] auto evidence() const noexcept -> const WorkerStackEvidence& {
    return evidence_;
  }
  [[nodiscard]] auto release() noexcept -> bool {
    if (started_ && !joined_) {
      return false;
    }
    if (evidence_.cleanup_attempted) {
      return cleanup_succeeded();
    }
    evidence_.cleanup_attempted = true;
    if (address_ != nullptr) {
      if (evidence_.lock.has_value() && evidence_.lock->zero_return()) {
        evidence_.unlock = operations_.unlock_pages(body());
      }
      evidence_.unmap = operations_.unmap(allocation());
      if (evidence_.unmap->zero_return()) {
        address_ = nullptr;
      }
    }
    return cleanup_succeeded();
  }

private:
  [[nodiscard]] auto allocation() const noexcept -> std::span<std::byte> {
    return {address_,
            evidence_.requested.bytes + evidence_.requested.verified_base_page_bytes};
  }
  [[nodiscard]] auto fail(WorkerStackStop stop) noexcept -> bool {
    evidence_.stop = stop;
    return false;
  }
  [[nodiscard]] auto cleanup_succeeded() const noexcept -> bool {
    return address_ == nullptr &&
           (!evidence_.unlock.has_value() || evidence_.unlock->zero_return());
  }
  [[nodiscard]] auto reserve() noexcept -> bool {
    const auto plan = evidence_.requested;
    const auto page = plan.verified_base_page_bytes;
    const auto maximum =
        static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max());
    if (page == 0U || (page & (page - 1U)) != 0U || page > maximum ||
        plan.bytes == 0U || plan.bytes % page != 0U || plan.bytes > maximum - page ||
        plan.requested_node >= std::numeric_limits<unsigned long>::digits) {
      return fail(WorkerStackStop::invalid_plan);
    }
    evidence_.base_page_bytes = operations_.base_page_bytes();
    evidence_.minimum_stack_bytes = operations_.minimum_thread_stack_bytes();
    if (!evidence_.base_page_bytes->nonnegative_return() ||
        evidence_.base_page_bytes->return_value <= 0 ||
        static_cast<std::uint64_t>(evidence_.base_page_bytes->return_value) != page ||
        !evidence_.minimum_stack_bytes->nonnegative_return() ||
        evidence_.minimum_stack_bytes->return_value <= 0 ||
        static_cast<std::uint64_t>(evidence_.minimum_stack_bytes->return_value) >
            plan.bytes) {
      return fail(WorkerStackStop::geometry_failure);
    }
    evidence_.mapping = operations_.map_private(plan.bytes + page);
    if (evidence_.mapping->address == nullptr || evidence_.mapping->error_number != 0) {
      return fail(WorkerStackStop::map_failure);
    }
    address_ = evidence_.mapping->address;
    const auto begin = reinterpret_cast<std::uintptr_t>(address_);
    if (begin % page != 0U ||
        plan.bytes + page > std::numeric_limits<std::uintptr_t>::max() - begin) {
      return fail(WorkerStackStop::map_failure);
    }
    evidence_.binding = operations_.bind_pages(allocation(), plan.requested_node);
    if (!evidence_.binding->zero_return()) {
      return fail(WorkerStackStop::binding_failure);
    }
    evidence_.no_huge_pages = operations_.disable_huge_pages(allocation());
    if (!evidence_.no_huge_pages->zero_return()) {
      return fail(WorkerStackStop::huge_page_control_failure);
    }
    evidence_.guard = operations_.protect_no_access({address_, page});
    return evidence_.guard->zero_return() || fail(WorkerStackStop::guard_failure);
  }
  void prepare_on_worker() noexcept {
    const auto cpu = evidence_.requested.owner_cpu;
    evidence_.before_populate = operations_.observe_current_thread(cpu);
    if (!evidence_.before_populate->matches(cpu)) {
      static_cast<void>(fail(WorkerStackStop::owner_readback_failure));
      return;
    }
    evidence_.populate = operations_.populate_write(body());
    if (!evidence_.populate->zero_return()) {
      static_cast<void>(fail(WorkerStackStop::populate_failure));
      return;
    }
    evidence_.lock = operations_.lock_pages(body());
    if (!evidence_.lock->zero_return()) {
      static_cast<void>(fail(WorkerStackStop::lock_failure));
      return;
    }
    evidence_.after_populate = operations_.observe_current_thread(cpu);
    const auto& before = *evidence_.before_populate;
    const auto& after = *evidence_.after_populate;
    if (!after.matches(cpu) ||
        after.thread_id.return_value != before.thread_id.return_value ||
        after.minor_faults < before.minor_faults ||
        after.major_faults < before.major_faults) {
      static_cast<void>(fail(WorkerStackStop::owner_readback_failure));
      return;
    }
    evidence_.stop = WorkerStackStop::ready;
  }
  static auto invoke(void* context) noexcept -> void* {
    auto& self = *static_cast<MappedWorkerThread*>(context);
    self.prepare_on_worker();
    self.entry_(self.context_);
    return nullptr;
  }
  Operations& operations_;
  WorkerStackEvidence evidence_;
  std::byte* address_{nullptr};
  pthread_t thread_{};
  WorkerEntry entry_{nullptr};
  void* context_{nullptr};
  bool attempted_{false};
  bool started_{false};
  bool joined_{false};
};

} // namespace cpu_prefetch::platform

#endif
