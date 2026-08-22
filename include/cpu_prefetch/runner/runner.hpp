#ifndef CPU_PREFETCH_RUNNER_RUNNER_HPP
#define CPU_PREFETCH_RUNNER_RUNNER_HPP

#include "cpu_prefetch/lifecycle/executor.hpp"
#include "cpu_prefetch/protocol/model.hpp"
#include "cpu_prefetch/runner/software_prefetch.hpp"
#include "cpu_prefetch/storage/raw_observations.hpp"

#include <array>
#include <cstdint>
#include <filesystem>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#if !defined(__x86_64__)
#error "ADR-0043 production runner requires the accepted Linux x86-64 target"
#endif

#include <immintrin.h>

namespace cpu_prefetch::runner {

inline constexpr std::string_view kAdmissionSchemaVersion =
    "cpu-prefetch-runner-admission/2";
inline constexpr std::string_view kRunnerProfileId =
    "STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v2";
inline constexpr std::string_view kCpuPairSelectionId =
    "XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1";
inline constexpr std::string_view kRelaxMappingId = "X86-PAUSE-ONE-PER-RELAX-SITE-v1";

struct WorkerPair final {
  std::uint32_t producer_cpu;
  std::uint32_t consumer_cpu;

  auto operator==(const WorkerPair&) const -> bool = default;
};

inline constexpr WorkerPair kNearWorkerPair{0U, 1U};
inline constexpr WorkerPair kFarWorkerPair{0U, 26U};

[[nodiscard]] auto selected_worker_pair(protocol::Placement placement) noexcept
    -> WorkerPair;

// Q13 selects exactly one architectural PAUSE at each executor relax site. The
// type is deliberately stateless because one instance is shared by the
// controller, producer, and consumer. It performs no adaptive backoff, system
// call, scheduler operation, memory access, or compiler fence.
class X86PauseRelax final {
public:
  inline void relax() const noexcept { _mm_pause(); }
};

enum class EvidenceKind : std::uint8_t {
  protocol_snapshot,
  source_release,
  run_plan,
  warmup_schedule,
  measurement_schedule,
  seed_derivation,
  platform_inventory,
  platform_request,
  platform_verification,
  hardware_prefetch_mapping,
  software_prefetch_mapping,
  clock_qualification,
  queue_provenance,
  runtime_atomic_layout,
  address_residency,
  storage_budget,
  durability_domains,
  calibration_freeze,
  execution_limits,
  authority_custody,
  phase_execution_authorization,
};

inline constexpr std::array kRequiredEvidenceKinds{
    EvidenceKind::protocol_snapshot,
    EvidenceKind::source_release,
    EvidenceKind::run_plan,
    EvidenceKind::warmup_schedule,
    EvidenceKind::measurement_schedule,
    EvidenceKind::seed_derivation,
    EvidenceKind::platform_inventory,
    EvidenceKind::platform_request,
    EvidenceKind::platform_verification,
    EvidenceKind::hardware_prefetch_mapping,
    EvidenceKind::software_prefetch_mapping,
    EvidenceKind::clock_qualification,
    EvidenceKind::queue_provenance,
    EvidenceKind::runtime_atomic_layout,
    EvidenceKind::address_residency,
    EvidenceKind::storage_budget,
    EvidenceKind::durability_domains,
    EvidenceKind::calibration_freeze,
    EvidenceKind::execution_limits,
    EvidenceKind::authority_custody,
    EvidenceKind::phase_execution_authorization,
};

struct ThreadBindingObservation final {
  std::uint32_t requested_cpu;
  std::uint32_t actual_cpu;
  bool affinity_applied;
  bool singleton_readback;
  bool actual_cpu_matches;

  [[nodiscard]] auto passes() const noexcept -> bool {
    return affinity_applied && singleton_readback && actual_cpu_matches &&
           actual_cpu == requested_cpu;
  }
};

class CurrentThreadBindingBackend {
public:
  virtual ~CurrentThreadBindingBackend() = default;
  [[nodiscard]] virtual auto bind_and_verify(std::uint32_t requested_cpu) noexcept
      -> ThreadBindingObservation = 0;
};

class LinuxCurrentThreadBindingBackend final : public CurrentThreadBindingBackend {
public:
  [[nodiscard]] auto bind_and_verify(std::uint32_t requested_cpu) noexcept
      -> ThreadBindingObservation override;
};

namespace detail {
struct alignas(64) OwnerPreparationResult final {
  ThreadBindingObservation binding{};
  SoftwarePrefetchCapabilityObservation software_prefetch_capability{};
  bool private_stream_prepared{false};
};
} // namespace detail

struct AffinedPreparationEvidence final {
  ThreadBindingObservation producer_binding;
  ThreadBindingObservation consumer_binding;
  SoftwarePrefetchCapabilityObservation producer_software_prefetch_capability;
  SoftwarePrefetchCapabilityObservation consumer_software_prefetch_capability;
  bool producer_stream_prepared;
  bool consumer_stream_prepared;

  [[nodiscard]] auto passes() const noexcept -> bool {
    return producer_binding.passes() && consumer_binding.passes() &&
           producer_software_prefetch_capability.passes() &&
           consumer_software_prefetch_capability.passes() && producer_stream_prepared &&
           consumer_stream_prepared;
  }
};

class AffinedObservationPreparation final {
public:
  AffinedObservationPreparation(
      CurrentThreadBindingBackend& binding_backend,
      CurrentCpuSoftwarePrefetchCapabilityBackend& capability_backend,
      WorkerPair workers, storage::ProducerObservationStream& producer_stream,
      storage::ConsumerObservationStream& consumer_stream) noexcept
      : binding_backend_(binding_backend), capability_backend_(capability_backend),
        workers_(workers), producer_stream_(producer_stream),
        consumer_stream_(consumer_stream) {}

  [[nodiscard]] auto prepare_producer() noexcept -> bool;
  [[nodiscard]] auto prepare_consumer() noexcept -> bool;
  [[nodiscard]] auto evidence() const noexcept -> AffinedPreparationEvidence;

private:
  CurrentThreadBindingBackend& binding_backend_;
  CurrentCpuSoftwarePrefetchCapabilityBackend& capability_backend_;
  WorkerPair workers_;
  storage::ProducerObservationStream& producer_stream_;
  storage::ConsumerObservationStream& consumer_stream_;
  detail::OwnerPreparationResult producer_result_{};
  detail::OwnerPreparationResult consumer_result_{};
};

[[nodiscard]] auto to_string(EvidenceKind kind) noexcept -> std::string_view;
[[nodiscard]] auto parse_evidence_kind(std::string_view value, std::string path)
    -> protocol::Result<EvidenceKind>;

struct EvidenceReference final {
  EvidenceKind kind;
  std::string artifact_id;
  std::filesystem::path path;
  std::string sha256;
  std::string binding_id;
  bool immutable;
  bool eligible;
};

struct RunnerAdmission final {
  std::string schema_version;
  std::string protocol_version;
  std::string runner_profile_id;
  std::string cpu_pair_selection_id;
  std::string relax_mapping_id;
  std::string source_revision;
  std::string binary_sha256;
  std::string stand_id;
  std::string binding_id;
  protocol::QueuePackage package;
  protocol::Placement placement;
  WorkerPair workers;
  lifecycle::ExecutionLimits execution_limits;
  std::vector<EvidenceReference> evidence;
};

struct AdmissionTrustAnchor final {
  std::string source_revision;
  std::string binary_sha256;
  std::string stand_id;
  std::string binding_id;
  bool source_dirty;
};

class AdmissionTicket final {
public:
  [[nodiscard]] auto package() const noexcept -> protocol::QueuePackage {
    return package_;
  }
  [[nodiscard]] auto placement() const noexcept -> protocol::Placement {
    return placement_;
  }
  [[nodiscard]] auto workers() const noexcept -> WorkerPair { return workers_; }
  [[nodiscard]] auto execution_limits() const noexcept
      -> const lifecycle::ExecutionLimits& {
    return execution_limits_;
  }
  [[nodiscard]] auto binding_id() const noexcept -> std::string_view {
    return binding_id_;
  }

private:
  friend auto admit_runner(const RunnerAdmission&, const AdmissionTrustAnchor&,
                           const std::filesystem::path&)
      -> protocol::Result<AdmissionTicket>;

  AdmissionTicket(protocol::QueuePackage package, protocol::Placement placement,
                  WorkerPair workers, lifecycle::ExecutionLimits execution_limits,
                  std::string binding_id)
      : package_(package), placement_(placement), workers_(workers),
        execution_limits_(execution_limits), binding_id_(std::move(binding_id)) {}

  protocol::QueuePackage package_;
  protocol::Placement placement_;
  WorkerPair workers_;
  lifecycle::ExecutionLimits execution_limits_;
  std::string binding_id_;
};

[[nodiscard]] auto load_admission(std::string_view document)
    -> protocol::Result<RunnerAdmission>;
[[nodiscard]] auto validate_admission_fields(const RunnerAdmission& admission,
                                             const AdmissionTrustAnchor& trust_anchor)
    -> std::vector<protocol::ValidationError>;
[[nodiscard]] auto admit_runner(const RunnerAdmission& admission,
                                const AdmissionTrustAnchor& trust_anchor,
                                const std::filesystem::path& manifest_parent)
    -> protocol::Result<AdmissionTicket>;
[[nodiscard]] auto verify_evidence_files(const RunnerAdmission& admission,
                                         const std::filesystem::path& manifest_parent)
    -> std::vector<protocol::ValidationError>;
[[nodiscard]] auto sha256_file(const std::filesystem::path& path)
    -> protocol::Result<std::string>;

enum class DispatchStatus : std::uint8_t { dispatched, package_mismatch };

// The switch is a controller-side operation. Each branch instantiates a
// distinct callable specialization; the selected value is never inspected by
// execute_measurement or by a queue/package hot operation.
template <typename Operation>
[[nodiscard]] auto dispatch_static_package(const AdmissionTicket& ticket,
                                           Operation&& operation) -> DispatchStatus {
  switch (ticket.package()) {
  case protocol::QueuePackage::r0:
    std::forward<Operation>(operation)
        .template operator()<protocol::QueuePackage::r0>();
    return DispatchStatus::dispatched;
  case protocol::QueuePackage::r1:
    std::forward<Operation>(operation)
        .template operator()<protocol::QueuePackage::r1>();
    return DispatchStatus::dispatched;
  case protocol::QueuePackage::r2:
    std::forward<Operation>(operation)
        .template operator()<protocol::QueuePackage::r2>();
    return DispatchStatus::dispatched;
  case protocol::QueuePackage::l0:
    std::forward<Operation>(operation)
        .template operator()<protocol::QueuePackage::l0>();
    return DispatchStatus::dispatched;
  case protocol::QueuePackage::l1:
    std::forward<Operation>(operation)
        .template operator()<protocol::QueuePackage::l1>();
    return DispatchStatus::dispatched;
  case protocol::QueuePackage::nblfq_mpsc:
  case protocol::QueuePackage::not_applicable:
    return DispatchStatus::package_mismatch;
  }
  return DispatchStatus::package_mismatch;
}

template <protocol::QueuePackage Package, typename Clock, typename Backend>
[[nodiscard]] auto
execute_static_measurement(const AdmissionTicket& ticket,
                           lifecycle::PreparedScheduleView schedule, Clock& clock,
                           Backend& backend, lifecycle::TerminationControl& termination)
    -> lifecycle::MeasurementExecutionReport {
  static_assert(
      Package == protocol::QueuePackage::r0 || Package == protocol::QueuePackage::r1 ||
      Package == protocol::QueuePackage::r2 || Package == protocol::QueuePackage::l0 ||
      Package == protocol::QueuePackage::l1);
  static_assert(Backend::package_kind == Package,
                "admission package and capture backend must be identical");
  if (ticket.package() != Package) {
    return lifecycle::detail::failure_report(
        lifecycle::ExecutionFailurePhase::pre_run,
        lifecycle::ExecutionFailureReason::invalid_schedule,
        schedule.deadline_ticks.size());
  }
  X86PauseRelax relax;
  return lifecycle::execute_measurement(schedule, clock, backend, termination,
                                        ticket.execution_limits(), relax);
}

template <protocol::QueuePackage Package, typename Clock, typename Backend,
          typename Preparation>
[[nodiscard]] auto execute_static_prepared_measurement(
    const AdmissionTicket& ticket, lifecycle::PreparedScheduleView schedule,
    Clock& clock, Backend& backend, lifecycle::TerminationControl& termination,
    Preparation& preparation) -> lifecycle::MeasurementExecutionReport {
  static_assert(
      Package == protocol::QueuePackage::r0 || Package == protocol::QueuePackage::r1 ||
      Package == protocol::QueuePackage::r2 || Package == protocol::QueuePackage::l0 ||
      Package == protocol::QueuePackage::l1);
  static_assert(Backend::package_kind == Package,
                "admission package and capture backend must be identical");
  if (ticket.package() != Package ||
      ticket.workers() != selected_worker_pair(ticket.placement())) {
    return lifecycle::detail::failure_report(
        lifecycle::ExecutionFailurePhase::pre_run,
        lifecycle::ExecutionFailureReason::worker_preparation,
        schedule.deadline_ticks.size());
  }
  X86PauseRelax relax;
  return lifecycle::execute_measurement_with_preparation(
      schedule, clock, backend, termination, ticket.execution_limits(), relax,
      preparation);
}

} // namespace cpu_prefetch::runner

#endif // CPU_PREFETCH_RUNNER_RUNNER_HPP
