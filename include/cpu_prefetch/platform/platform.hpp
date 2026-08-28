#ifndef CPU_PREFETCH_PLATFORM_PLATFORM_HPP
#define CPU_PREFETCH_PLATFORM_PLATFORM_HPP

#include <array>
#include <cstdint>
#include <map>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <variant>
#include <vector>

#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/protocol/model.hpp"

namespace cpu_prefetch::platform {

inline constexpr std::string_view kPlatformEvidenceVersion =
    "LINUX-PLATFORM-EVIDENCE-v1";

// Q15-P0 fixes only this candidate-stand mapping. The interface deliberately
// has no arbitrary MSR address or mask parameter.
inline constexpr std::string_view kHardwarePrefetchMappingId =
    "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1";
inline constexpr std::uint32_t kIntelFamily6 = 0x06U;
inline constexpr std::uint32_t kIntelModel55 = 0x55U;
inline constexpr std::uint32_t kHardwarePrefetchMsr = 0x1A4U;
inline constexpr std::uint64_t kHardwarePrefetchDisableMask = 0x0fU;
inline constexpr std::array<std::uint32_t, 3U> kHardwarePrefetchControlCpus{0U, 1U,
                                                                            26U};

enum class ErrorCategory : std::uint8_t {
  parse_error,
  missing_evidence,
  invalid_request,
  impossible_placement,
  sibling_conflict,
  numa_mismatch,
  unsupported_control,
  privilege_denied,
  apply_failure,
  verification_mismatch,
  restoration_failure,
  stale_state,
  manifest_incomplete,
  io_error,
};

[[nodiscard]] auto to_string(ErrorCategory category) -> std::string_view;

struct Error final {
  ErrorCategory category;
  std::string path;
  std::string rule_id;
  std::string message;

  auto operator==(const Error&) const -> bool = default;
};

template <typename T> class Result final {
public:
  [[nodiscard]] static auto success(T value) -> Result {
    return Result(std::in_place_index<0>, std::move(value));
  }
  [[nodiscard]] static auto failure(Error error) -> Result {
    return Result(std::in_place_index<1>, std::vector<Error>{std::move(error)});
  }
  [[nodiscard]] static auto failure(std::vector<Error> errors) -> Result {
    return Result(std::in_place_index<1>, std::move(errors));
  }

  [[nodiscard]] auto has_value() const noexcept -> bool {
    return storage_.index() == 0U;
  }
  explicit operator bool() const noexcept { return has_value(); }
  [[nodiscard]] auto value() & -> T& { return std::get<0>(storage_); }
  [[nodiscard]] auto value() const& -> const T& { return std::get<0>(storage_); }
  [[nodiscard]] auto value() && -> T&& { return std::get<0>(std::move(storage_)); }
  [[nodiscard]] auto value_if() noexcept -> T* { return std::get_if<0>(&storage_); }
  [[nodiscard]] auto value_if() const noexcept -> const T* {
    return std::get_if<0>(&storage_);
  }
  [[nodiscard]] auto errors() const -> const std::vector<Error>& {
    static const std::vector<Error> no_errors;
    return has_value() ? no_errors : std::get<1>(storage_);
  }

private:
  explicit Result(std::in_place_index_t<0>, T value)
      : storage_(std::in_place_index<0>, std::move(value)) {}
  explicit Result(std::in_place_index_t<1>, std::vector<Error> errors)
      : storage_(std::in_place_index<1>, std::move(errors)) {}

  std::variant<T, std::vector<Error>> storage_;
};

struct EvidenceValue final {
  std::string name;
  std::string source;
  std::optional<std::string> value;

  auto operator==(const EvidenceValue&) const -> bool = default;
};

struct LogicalCpu final {
  std::uint32_t logical_id;
  std::uint32_t core_id;
  std::uint32_t package_id;
  std::uint32_t numa_node;
  std::vector<std::uint32_t> thread_siblings;
  std::vector<std::string> cache_domains;
  bool online;

  auto operator==(const LogicalCpu&) const -> bool = default;
};

struct CacheDomain final {
  std::string domain_id;
  std::uint32_t level;
  std::string kind;
  std::uint64_t size_bytes;
  std::vector<std::uint32_t> shared_cpus;
  bool last_level;

  auto operator==(const CacheDomain&) const -> bool = default;
};

struct NumaNode final {
  std::uint32_t node_id;
  std::vector<std::uint32_t> logical_cpus;

  auto operator==(const NumaNode&) const -> bool = default;
};

struct PciDevice final {
  std::string address;
  std::string vendor;
  std::string device;
  std::string device_class;
  std::optional<std::int32_t> numa_node;
  std::vector<std::uint32_t> local_cpus;

  auto operator==(const PciDevice&) const -> bool = default;
};

struct CpuIdentity final {
  std::string vendor;
  std::string model;
  std::string stepping;
  std::string microcode;
  std::uint64_t cache_line_bytes;
  std::uint64_t atomic_width_bits;
  std::uint64_t atomic_alignment_bytes;
  bool pointer_atomic_lock_free;

  auto operator==(const CpuIdentity&) const -> bool = default;
};

struct SoftwareIdentity final {
  std::string operating_system;
  std::string kernel;
  std::string compiler;
  std::string standard_library;
  std::string language_standard;

  auto operator==(const SoftwareIdentity&) const -> bool = default;
};

struct PlatformInventory final {
  std::string snapshot_id;
  std::string captured_at_utc;
  CpuIdentity cpu;
  SoftwareIdentity software;
  std::uint64_t base_page_bytes;
  std::vector<LogicalCpu> logical_cpus;
  std::vector<CacheDomain> cache_domains;
  std::vector<NumaNode> numa_nodes;
  std::vector<PciDevice> pci_devices;
  std::vector<EvidenceValue> observations;

  auto operator==(const PlatformInventory&) const -> bool = default;
};

enum class ControlKind : std::uint8_t {
  producer_affinity,
  consumer_affinity,
  producer_actual_cpu,
  consumer_actual_cpu,
  shared_memory_policy,
  producer_private_memory_policy,
  consumer_private_memory_policy,
  shared_page_residency,
  private_page_residency,
  base_page_state,
  huge_page_state,
  governor,
  fixed_frequency,
  turbo,
  c_state,
  smt,
  interrupt_routing,
  cpu_isolation,
  hardware_prefetch,
  clock_source,
  microcode,
  firmware,
  compiler,
  binary,
  library,
};

[[nodiscard]] auto to_string(ControlKind kind) -> std::string_view;

enum class CapabilityStatus : std::uint8_t {
  read_only,
  external_authority_required,
  unavailable,
  mapping_unresolved,
};

[[nodiscard]] auto to_string(CapabilityStatus status) -> std::string_view;

struct Capability final {
  ControlKind kind;
  CapabilityStatus status;
  std::string detection_mechanism;
  std::string evidence;
  bool kernel_privilege_required;

  auto operator==(const Capability&) const -> bool = default;
};

enum class MemoryPolicy : std::uint8_t {
  bind_producer_node,
  bind_worker_local,
  interleave,
  consumer_local,
  replicated,
  migrated,
};

[[nodiscard]] auto to_string(MemoryPolicy policy) -> std::string_view;

enum class PagePolicy : std::uint8_t {
  verified_base_pages,
  explicit_huge_pages,
  transparent_huge_pages,
};

[[nodiscard]] auto to_string(PagePolicy policy) -> std::string_view;

struct PlacementRequest final {
  protocol::Placement placement;
  std::uint32_t producer_cpu;
  std::uint32_t consumer_cpu;
  MemoryPolicy shared_memory_policy;
  std::vector<std::uint32_t> shared_memory_nodes;
  MemoryPolicy producer_private_memory_policy;
  std::vector<std::uint32_t> producer_private_nodes;
  MemoryPolicy consumer_private_memory_policy;
  std::vector<std::uint32_t> consumer_private_nodes;
  PagePolicy page_policy;
  std::uint64_t requested_page_bytes;

  auto operator==(const PlacementRequest&) const -> bool = default;
};

struct ControlRequest final {
  std::string control_id;
  ControlKind kind;
  std::string target;
  std::string requested_value;
  bool mandatory;
  bool mutating;
  std::string authority_id;
  std::string actuation_mechanism;
  std::string verification_mechanism;

  auto operator==(const ControlRequest&) const -> bool = default;
};

struct RequestedState final {
  std::string request_id;
  std::string inventory_snapshot_id;
  std::uint64_t state_epoch;
  PlacementRequest placement;
  protocol::RequestedHardwareState hardware_prefetch_state;
  std::vector<ControlRequest> controls;

  auto operator==(const RequestedState&) const -> bool = default;
};

struct CpuFamilyModel final {
  std::uint32_t family;
  std::uint32_t model;

  auto operator==(const CpuFamilyModel&) const -> bool = default;
};

struct HardwarePrefetchMsrValue final {
  std::uint32_t cpu;
  std::uint64_t value;

  auto operator==(const HardwarePrefetchMsrValue&) const -> bool = default;
};

struct HardwarePrefetchPlan final {
  protocol::RequestedHardwareState requested_state;
  std::vector<HardwarePrefetchMsrValue> prestate;
  std::vector<HardwarePrefetchMsrValue> requested;
  bool mutating;
};

struct BackendResult;

// Plan construction accepts only the selected model, selected CPUs and H0/H1.
// H0 preserves the observed default exactly. H1 preserves bits 63:4 and sets
// documented disable bits 3:0. A prestate with every disable bit already set
// is rejected because H0/H1 would collapse on that owner CPU.
[[nodiscard]] auto make_hardware_prefetch_plan(
    CpuFamilyModel identity, protocol::RequestedHardwareState requested_state,
    std::span<const HardwarePrefetchMsrValue> prestate) -> Result<HardwarePrefetchPlan>;

class HardwarePrefetchMsrBackend {
public:
  virtual ~HardwarePrefetchMsrBackend() = default;
  [[nodiscard]] virtual auto backend_id() const -> std::string_view = 0;
  [[nodiscard]] virtual auto read(std::uint32_t cpu) -> Result<std::uint64_t> = 0;
  [[nodiscard]] virtual auto write(std::uint32_t cpu, std::uint64_t value)
      -> BackendResult = 0;
};

struct HardwarePrefetchProbeInput final {
  bool regular_stream_passed;
  bool pointer_stream_passed;
};

struct HardwarePrefetchTransactionReport final {
  bool applied;
  bool verified;
  bool probes_passed;
  bool restored;
  bool quarantined;
  std::vector<HardwarePrefetchMsrValue> apply_readback;
  std::vector<HardwarePrefetchMsrValue> restore_readback;
  std::vector<Error> errors;
};

// The writer and verifier must be independent backends. Every H1 transaction
// restores the complete 64-bit prestate and verifies restoration, including
// after an apply/readback/probe failure. No caller can supply an MSR number or
// mask. This function is exercised with fake backends until an exact Q15
// authorizes a hash-bound privileged adapter on the candidate stand.
[[nodiscard]] auto qualify_hardware_prefetch_plan(
    const HardwarePrefetchPlan& plan, HardwarePrefetchMsrBackend& writer,
    HardwarePrefetchMsrBackend& independent_verifier, HardwarePrefetchProbeInput probes)
    -> HardwarePrefetchTransactionReport;

[[nodiscard]] auto detect_capabilities(const PlatformInventory& inventory)
    -> std::vector<Capability>;
[[nodiscard]] auto validate_requested_state(const PlatformInventory& inventory,
                                            std::span<const Capability> capabilities,
                                            const RequestedState& request)
    -> std::vector<Error>;

enum class ApplyMode : std::uint8_t { dry_run, authorized_apply };
enum class StepStatus : std::uint8_t {
  planned,
  applied,
  apply_failed,
  verified,
  verification_failed,
  stale,
  restored,
  restoration_failed,
};

[[nodiscard]] auto to_string(ApplyMode mode) -> std::string_view;
[[nodiscard]] auto to_string(StepStatus status) -> std::string_view;

struct StateObservation final {
  std::string control_id;
  std::string inventory_snapshot_id;
  std::uint64_t state_epoch;
  std::optional<std::string> observed_value;
  std::string evidence_id;
  std::string mechanism_id;

  auto operator==(const StateObservation&) const -> bool = default;
};

struct BackendResult final {
  bool succeeded;
  std::string evidence_id;
  std::string detail;
  std::optional<ErrorCategory> failure_category;
};

class ControlActuator {
public:
  virtual ~ControlActuator() = default;
  [[nodiscard]] virtual auto backend_id() const -> std::string_view = 0;
  [[nodiscard]] virtual auto apply(const ControlRequest& request) -> BackendResult = 0;
  [[nodiscard]] virtual auto restore(const ControlRequest& request,
                                     const StateObservation& prior_state)
      -> BackendResult = 0;
};

class StateVerifier {
public:
  virtual ~StateVerifier() = default;
  [[nodiscard]] virtual auto backend_id() const -> std::string_view = 0;
  [[nodiscard]] virtual auto readback(const ControlRequest& request)
      -> Result<StateObservation> = 0;
};

struct ApplyStep final {
  std::string control_id;
  StepStatus status;
  std::string evidence_id;
  std::string detail;

  auto operator==(const ApplyStep&) const -> bool = default;
};

struct RestorationReport final {
  bool attempted;
  bool complete;
  std::vector<ApplyStep> steps;
  std::vector<Error> errors;
};

struct ApplyReport final {
  ApplyMode mode;
  bool complete;
  std::vector<ApplyStep> steps;
  RestorationReport restoration;
  std::vector<Error> errors;
};

struct VerificationReport final {
  bool complete;
  bool all_mandatory_match;
  std::vector<StateObservation> observations;
  std::vector<ApplyStep> steps;
  std::vector<Error> errors;
};

[[nodiscard]] auto
restore_platform_state(std::span<const ControlRequest> applied_controls,
                       std::span<const StateObservation> prior_state,
                       ControlActuator& actuator) -> RestorationReport;

[[nodiscard]] auto apply_requested_state(const RequestedState& request,
                                         std::span<const StateObservation> prior_state,
                                         ApplyMode mode, ControlActuator* actuator)
    -> ApplyReport;

[[nodiscard]] auto verify_requested_state(const RequestedState& request,
                                          StateVerifier& verifier)
    -> VerificationReport;

struct LibraryProvenance final {
  std::string name;
  std::string version;
  std::string artifact_sha256;

  auto operator==(const LibraryProvenance&) const -> bool = default;
};

struct ManifestContext final {
  std::string platform_id;
  std::string manifest_id;
  std::string build_id;
  std::string binary_sha256;
  std::vector<std::string> compiler_flags;
  std::string link_mode;
  std::vector<LibraryProvenance> libraries;

  auto operator==(const ManifestContext&) const -> bool = default;
};

struct ManifestArtifact final {
  std::string canonical_json;
  std::string sha256;
  bool eligible;
};

[[nodiscard]] auto
emit_manifest(const ManifestContext& context, const PlatformInventory& inventory,
              std::span<const Capability> capabilities, const RequestedState& request,
              const ApplyReport& apply_report,
              const VerificationReport& verification_report)
    -> Result<ManifestArtifact>;

struct ClockEvidenceReferences final {
  std::string source;
  std::string time_unit;
  std::string conversion_record_id;
  std::string serialization_record_id;
  std::string acceptance_record_id;
};

struct HardwarePrefetchEvidence final {
  protocol::RequestedHardwareState requested;
  protocol::VerifiedHardwareState verified;
  std::string readback_artifact_id;
  std::string behavioral_probe_artifact_id;
  std::string privileged_authority_id;
};

struct ProtocolPlatformContext final {
  std::string platform_id;
  std::array<std::uint32_t, 2> near_core_pair;
  std::array<std::uint32_t, 2> far_core_pair;
  std::string memory_population;
  std::string residency_verification_method;
  std::vector<std::string> compiler_flags;
  std::string link_mode;
  ClockEvidenceReferences clock;
  std::array<HardwarePrefetchEvidence, 2> hardware_prefetch_states;
};

struct ProtocolPlatformArtifact final {
  std::string canonical_json;
  std::string record_sha256;
  bool hardware_states_verified;
};

// Emits the exact imported platform.schema.json logical shape. Rich apply,
// restoration, firmware, binary, library, and per-control facts remain in the
// evidence manifest and are referenced by the IDs supplied here.
[[nodiscard]] auto emit_protocol_platform_record(const ProtocolPlatformContext& context,
                                                 const PlatformInventory& inventory)
    -> Result<ProtocolPlatformArtifact>;

} // namespace cpu_prefetch::platform

#endif // CPU_PREFETCH_PLATFORM_PLATFORM_HPP
