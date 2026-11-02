#ifndef CPU_PREFETCH_PLATFORM_OWNER_MAPPING_HPP
#define CPU_PREFETCH_PLATFORM_OWNER_MAPPING_HPP

#include <cstddef>
#include <cstdint>
#include <limits>
#include <new>
#include <optional>
#include <span>

namespace cpu_prefetch::platform {

struct LinuxCallResult final {
  std::int64_t return_value;
  int error_number;
  [[nodiscard]] auto zero_return() const noexcept -> bool {
    return return_value == 0 && error_number == 0;
  }
  [[nodiscard]] auto nonnegative_return() const noexcept -> bool {
    return return_value >= 0 && error_number == 0;
  }
};

struct LinuxMappingResult final {
  std::byte* address;
  int error_number;
};

struct LinuxOwnerBindingRequest final {
  std::span<std::byte> bytes;
  unsigned long node_mask;
  unsigned long max_node;
  unsigned long flags;
  int policy;
};

[[nodiscard]] auto linux_owner_binding_request(std::span<std::byte> bytes,
                                               std::uint32_t node) noexcept
    -> std::optional<LinuxOwnerBindingRequest>;

struct OwnerThreadObservation final {
  LinuxCallResult affinity;
  LinuxCallResult current_cpu;
  LinuxCallResult thread_id;
  LinuxCallResult faults;
  std::int64_t minor_faults;
  std::int64_t major_faults;
  int affinity_cpu_count;
  bool requested_cpu_in_affinity;

  [[nodiscard]] auto matches(std::uint32_t requested_cpu) const noexcept -> bool {
    return affinity.zero_return() && affinity_cpu_count == 1 &&
           requested_cpu_in_affinity && current_cpu.nonnegative_return() &&
           current_cpu.return_value == static_cast<std::int64_t>(requested_cpu) &&
           thread_id.nonnegative_return() && thread_id.return_value > 0 &&
           faults.zero_return() && minor_faults >= 0 && major_faults >= 0;
  }
};

// Cold preparation operations. No topology is inferred from a CPU number. A
// node must fit one native nodemask word; unsupported geometry is rejected.
// These operations never migrate existing pages or alter global NUMA policy.
class LinuxOwnerMemoryOperations final {
public:
  [[nodiscard]] auto base_page_bytes() const noexcept -> LinuxCallResult;
  [[nodiscard]] auto map_private(std::size_t bytes) const noexcept
      -> LinuxMappingResult;
  [[nodiscard]] auto bind_pages(std::span<std::byte> bytes,
                                std::uint32_t node) const noexcept -> LinuxCallResult;
  [[nodiscard]] auto disable_huge_pages(std::span<std::byte> bytes) const noexcept
      -> LinuxCallResult;
  [[nodiscard]] auto bind_current_thread(std::uint32_t cpu) const noexcept
      -> LinuxCallResult;
  [[nodiscard]] auto observe_current_thread(std::uint32_t requested_cpu) const noexcept
      -> OwnerThreadObservation;
  [[nodiscard]] auto lock_pages(std::span<std::byte> bytes) const noexcept
      -> LinuxCallResult;
  [[nodiscard]] auto protect_read_only(std::span<std::byte> bytes) const noexcept
      -> LinuxCallResult;
  [[nodiscard]] auto unlock_pages(std::span<std::byte> bytes) const noexcept
      -> LinuxCallResult;
  [[nodiscard]] auto unmap(std::span<std::byte> bytes) const noexcept
      -> LinuxCallResult;
};

struct OwnerMappingPlan final {
  std::size_t bytes;
  std::size_t verified_base_page_bytes;
  std::uint32_t owner_cpu;
  std::uint32_t requested_node;
};

enum class OwnerMappingStop : std::uint8_t {
  not_started,
  invalid_plan,
  page_geometry_failure,
  map_failure,
  binding_failure,
  huge_page_control_failure,
  affinity_failure,
  owner_readback_failure,
  lock_failure,
  read_only_failure,
  ready,
};

struct OwnerMappingEvidence final {
  OwnerMappingPlan requested;
  std::optional<LinuxCallResult> base_page_bytes;
  std::optional<LinuxMappingResult> mapping;
  std::optional<LinuxCallResult> binding;
  std::optional<LinuxCallResult> no_huge_pages;
  std::optional<LinuxCallResult> affinity_request;
  std::optional<OwnerThreadObservation> before_touch;
  std::optional<OwnerThreadObservation> after_touch;
  std::optional<LinuxCallResult> lock;
  std::optional<LinuxCallResult> read_only;
  std::optional<LinuxCallResult> unlock;
  std::optional<LinuxCallResult> unmap;
  std::size_t prefaulted_pages{0U};
  OwnerMappingStop stop{OwnerMappingStop::not_started};
  bool cleanup_attempted{false};
};

// Construct before worker launch; prepare once on the actual affined owner.
// Preparation first-touches only new, private anonymous memory. This must not
// wrap an active stack, existing object, or borrowed mapping. Caller serializes
// all access and releases only after workers/queries no longer refer to it.
// Syscall acceptance/owner observations are not page-residency qualification;
// use independent PreparedPageResidencyQuery snapshots and smaps validation.
template <typename Operations = LinuxOwnerMemoryOperations> class OwnerMapping final {
public:
  OwnerMapping(OwnerMappingPlan plan, Operations& operations) noexcept
      : operations_(operations), evidence_{} {
    evidence_.requested = plan;
  }
  ~OwnerMapping() { static_cast<void>(release()); }
  OwnerMapping(const OwnerMapping&) = delete;
  auto operator=(const OwnerMapping&) -> OwnerMapping& = delete;
  OwnerMapping(OwnerMapping&&) = delete;
  auto operator=(OwnerMapping&&) -> OwnerMapping& = delete;

  [[nodiscard]] auto prepare() noexcept -> bool {
    if (evidence_.stop != OwnerMappingStop::not_started ||
        evidence_.cleanup_attempted) {
      return false;
    }
    const auto plan = evidence_.requested;
    const auto page = plan.verified_base_page_bytes;
    if (page == 0U || (page & (page - 1U)) != 0U || plan.bytes == 0U ||
        plan.bytes % page != 0U ||
        plan.bytes >
            static_cast<std::size_t>(std::numeric_limits<std::ptrdiff_t>::max()) ||
        plan.requested_node >= std::numeric_limits<unsigned long>::digits) {
      return fail(OwnerMappingStop::invalid_plan);
    }
    evidence_.base_page_bytes = operations_.base_page_bytes();
    const auto observed_page = *evidence_.base_page_bytes;
    if (!observed_page.nonnegative_return() || observed_page.return_value == 0 ||
        static_cast<std::uint64_t>(observed_page.return_value) != page) {
      return fail(OwnerMappingStop::page_geometry_failure);
    }
    evidence_.mapping = operations_.map_private(plan.bytes);
    const auto mapped = *evidence_.mapping;
    if (mapped.address == nullptr || mapped.error_number != 0) {
      return fail(OwnerMappingStop::map_failure);
    }
    address_ = mapped.address;
    const auto begin = reinterpret_cast<std::uintptr_t>(address_);
    if (begin % page != 0U ||
        plan.bytes > std::numeric_limits<std::uintptr_t>::max() - begin) {
      return fail(OwnerMappingStop::map_failure);
    }
    evidence_.binding = operations_.bind_pages(mapped_bytes(), plan.requested_node);
    if (!evidence_.binding->zero_return()) {
      return fail(OwnerMappingStop::binding_failure);
    }
    evidence_.no_huge_pages = operations_.disable_huge_pages(mapped_bytes());
    if (!evidence_.no_huge_pages->zero_return()) {
      return fail(OwnerMappingStop::huge_page_control_failure);
    }
    evidence_.affinity_request = operations_.bind_current_thread(plan.owner_cpu);
    if (!evidence_.affinity_request->zero_return()) {
      return fail(OwnerMappingStop::affinity_failure);
    }
    evidence_.before_touch = operations_.observe_current_thread(plan.owner_cpu);
    if (!evidence_.before_touch->matches(plan.owner_cpu)) {
      return fail(OwnerMappingStop::owner_readback_failure);
    }
    // Begin byte-array lifetime without initialization, then force one write to
    // every page on this owner. Later typed construction must precede use.
    static_cast<void>(::new (static_cast<void*>(address_)) std::byte[plan.bytes]);
    volatile std::byte* prefault = address_;
    for (std::size_t offset = 0U; offset < plan.bytes; offset += page) {
      prefault[offset] = std::byte{0};
      ++evidence_.prefaulted_pages;
    }
    evidence_.lock = operations_.lock_pages(mapped_bytes());
    if (!evidence_.lock->zero_return()) {
      return fail(OwnerMappingStop::lock_failure);
    }
    evidence_.after_touch = operations_.observe_current_thread(plan.owner_cpu);
    if (!evidence_.after_touch->matches(plan.owner_cpu) ||
        evidence_.after_touch->thread_id.return_value !=
            evidence_.before_touch->thread_id.return_value ||
        evidence_.after_touch->minor_faults < evidence_.before_touch->minor_faults ||
        evidence_.after_touch->major_faults < evidence_.before_touch->major_faults) {
      return fail(OwnerMappingStop::owner_readback_failure);
    }
    evidence_.stop = OwnerMappingStop::ready;
    return true;
  }

  [[nodiscard]] auto protect_read_only() noexcept -> bool {
    if (!ready() || evidence_.read_only.has_value()) {
      return false;
    }
    evidence_.read_only = operations_.protect_read_only(mapped_bytes());
    return evidence_.read_only->zero_return() ||
           fail(OwnerMappingStop::read_only_failure);
  }
  [[nodiscard]] auto ready() const noexcept -> bool {
    return evidence_.stop == OwnerMappingStop::ready && address_ != nullptr &&
           !evidence_.cleanup_attempted;
  }
  [[nodiscard]] auto mapped_bytes() const noexcept -> std::span<std::byte> {
    return {address_, address_ == nullptr ? 0U : evidence_.requested.bytes};
  }
  [[nodiscard]] auto evidence() const noexcept -> const OwnerMappingEvidence& {
    return evidence_;
  }
  // Explicit cleanup retains both results even when unlock fails. A failed
  // unmap remains a failed cleanup, never an observed release or retry license.
  [[nodiscard]] auto release() noexcept -> bool {
    if (evidence_.cleanup_attempted) {
      return cleanup_succeeded();
    }
    evidence_.cleanup_attempted = true;
    if (address_ == nullptr) {
      return true;
    }
    if (evidence_.lock.has_value() && evidence_.lock->zero_return()) {
      evidence_.unlock = operations_.unlock_pages(mapped_bytes());
    }
    evidence_.unmap = operations_.unmap(mapped_bytes());
    if (evidence_.unmap->zero_return()) {
      address_ = nullptr;
    }
    return cleanup_succeeded();
  }

private:
  [[nodiscard]] auto fail(OwnerMappingStop stop) noexcept -> bool {
    evidence_.stop = stop;
    return false;
  }
  [[nodiscard]] auto cleanup_succeeded() const noexcept -> bool {
    return address_ == nullptr &&
           (!evidence_.unlock.has_value() || evidence_.unlock->zero_return());
  }
  Operations& operations_;
  OwnerMappingEvidence evidence_;
  std::byte* address_{nullptr};
};

} // namespace cpu_prefetch::platform

#endif
