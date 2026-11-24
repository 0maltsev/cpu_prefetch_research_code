#ifndef CPU_PREFETCH_PLATFORM_Q15_RUNTIME_HPP
#define CPU_PREFETCH_PLATFORM_Q15_RUNTIME_HPP

#include "cpu_prefetch/platform/platform.hpp"
#include "cpu_prefetch/platform/q15_probe.hpp"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::platform {

inline constexpr std::string_view kQ15DynamicImplementationProfileId =
    "Q15-DYNAMIC-IMPLEMENTATION-PROFILE-v1";
inline constexpr std::string_view kQ15SessionProtocolId =
    "Q15-PHASE-SPANNING-SESSION-v1";
inline constexpr std::string_view kQ15EvidenceFrameId =
    "Q15-CANONICAL-U32BE-LENGTH-PREFIXED-FRAME-v1";
inline constexpr std::string_view kQ15AbstractSocketPrefix = "cpu-prefetch-q15-";
inline constexpr std::uint64_t kQ15AllPrefetchPerfConfig = 0xf824U;

struct Q15PerfEventRequest final {
  std::uint32_t type;
  std::uint64_t config;
  std::int32_t pid;
  std::int32_t cpu;
  std::int32_t group_fd;
  std::uint64_t flags;
  bool disabled;
  bool inherit;
  bool pinned;
  bool exclude_user;
  bool exclude_kernel;
  bool exclude_hypervisor;
  bool exclude_guest;
  bool read_total_time_enabled;
  bool read_total_time_running;

  auto operator==(const Q15PerfEventRequest&) const -> bool = default;
};

[[nodiscard]] auto q15_perf_event_request() noexcept -> Q15PerfEventRequest;
[[nodiscard]] auto
is_exact_q15_perf_event_request(const Q15PerfEventRequest& request) noexcept -> bool;

class Q15PerfOperations {
public:
  virtual ~Q15PerfOperations() = default;
  [[nodiscard]] virtual auto open_event(const Q15PerfEventRequest& request)
      -> Result<int> = 0;
  [[nodiscard]] virtual auto reset(int descriptor) noexcept -> bool = 0;
  [[nodiscard]] virtual auto enable(int descriptor) noexcept -> bool = 0;
  [[nodiscard]] virtual auto disable(int descriptor) noexcept -> bool = 0;
  [[nodiscard]] virtual auto read(int descriptor) -> Result<Q15CounterReading> = 0;
  [[nodiscard]] virtual auto close(int descriptor) noexcept -> bool = 0;
};

class LinuxQ15PerfOperations final : public Q15PerfOperations {
public:
  [[nodiscard]] auto open_event(const Q15PerfEventRequest& request)
      -> Result<int> override;
  [[nodiscard]] auto reset(int descriptor) noexcept -> bool override;
  [[nodiscard]] auto enable(int descriptor) noexcept -> bool override;
  [[nodiscard]] auto disable(int descriptor) noexcept -> bool override;
  [[nodiscard]] auto read(int descriptor) -> Result<Q15CounterReading> override;
  [[nodiscard]] auto close(int descriptor) noexcept -> bool override;
};

// The only production counter-enabled regions. Counter control returns plain
// booleans so construction of diagnostic Error/string state cannot occur while
// the PMU is enabled. The caller handles every failure after the disable/close
// boundary. The generated-code gate requires exactly one accepted traversal
// call between the enable and disable virtual calls.
struct Q15CountedRegionResult final {
  std::uint64_t retention_value;
  bool enabled;
  bool disabled;
};

extern "C" [[gnu::noinline]] auto cpu_prefetch_q15_regular_counted_region(
    Q15PerfOperations* operations, int descriptor, const std::byte* buffer,
    std::size_t line_count) noexcept -> Q15CountedRegionResult;
extern "C" [[gnu::noinline]] auto
cpu_prefetch_q15_pointer_counted_region(Q15PerfOperations* operations, int descriptor,
                                        const std::byte* buffer, std::size_t line_count,
                                        std::uint32_t start_index) noexcept
    -> Q15CountedRegionResult;

struct Q15ThreadFaults final {
  std::uint64_t minor_faults;
  std::uint64_t major_faults;
};

struct Q15ResidencySnapshot final {
  std::vector<std::int32_t> page_nodes;

  [[nodiscard]] auto passes(std::uint32_t expected_node,
                            std::size_t expected_pages) const noexcept -> bool;
};

struct Q15MemoryBindingRequest final {
  std::byte* address;
  std::size_t byte_count;
  std::uint32_t numa_node;
};

class Q15PlatformOperations {
public:
  virtual ~Q15PlatformOperations() = default;
  [[nodiscard]] virtual auto bind_current_thread(std::uint32_t cpu)
      -> BackendResult = 0;
  [[nodiscard]] virtual auto singleton_affinity_matches(std::uint32_t cpu)
      -> Result<bool> = 0;
  [[nodiscard]] virtual auto current_cpu() -> Result<std::uint32_t> = 0;
  [[nodiscard]] virtual auto map_private_anonymous(std::size_t byte_count)
      -> Result<std::byte*> = 0;
  [[nodiscard]] virtual auto bind_memory(const Q15MemoryBindingRequest& request)
      -> BackendResult = 0;
  [[nodiscard]] virtual auto disable_transparent_huge_pages(std::byte* address,
                                                            std::size_t byte_count)
      -> BackendResult = 0;
  [[nodiscard]] virtual auto query_residency(std::byte* address, std::size_t byte_count,
                                             std::size_t page_bytes)
      -> Result<Q15ResidencySnapshot> = 0;
  [[nodiscard]] virtual auto thread_faults() -> Result<Q15ThreadFaults> = 0;
  [[nodiscard]] virtual auto monotonic_raw_nanoseconds() -> Result<std::uint64_t> = 0;
  [[nodiscard]] virtual auto unmap(std::byte* address, std::size_t byte_count)
      -> BackendResult = 0;
};

class LinuxQ15PlatformOperations final : public Q15PlatformOperations {
public:
  [[nodiscard]] auto bind_current_thread(std::uint32_t cpu) -> BackendResult override;
  [[nodiscard]] auto singleton_affinity_matches(std::uint32_t cpu)
      -> Result<bool> override;
  [[nodiscard]] auto current_cpu() -> Result<std::uint32_t> override;
  [[nodiscard]] auto map_private_anonymous(std::size_t byte_count)
      -> Result<std::byte*> override;
  [[nodiscard]] auto bind_memory(const Q15MemoryBindingRequest& request)
      -> BackendResult override;
  [[nodiscard]] auto disable_transparent_huge_pages(std::byte* address,
                                                    std::size_t byte_count)
      -> BackendResult override;
  [[nodiscard]] auto query_residency(std::byte* address, std::size_t byte_count,
                                     std::size_t page_bytes)
      -> Result<Q15ResidencySnapshot> override;
  [[nodiscard]] auto thread_faults() -> Result<Q15ThreadFaults> override;
  [[nodiscard]] auto monotonic_raw_nanoseconds() -> Result<std::uint64_t> override;
  [[nodiscard]] auto unmap(std::byte* address, std::size_t byte_count)
      -> BackendResult override;
};

struct Q15ProbePlatformBinding final {
  std::uint32_t cpu;
  std::uint32_t numa_node;
  std::uint64_t verified_local_llc_bytes;
  std::uint64_t verified_base_page_bytes;
};

[[nodiscard]] auto q15_expected_numa_node(std::uint32_t cpu) -> Result<std::uint32_t>;
[[nodiscard]] auto q15_working_set_bytes(const Q15ProbePlatformBinding& binding)
    -> Result<std::size_t>;

class Q15PreparedProbeMemory final {
public:
  [[nodiscard]] static auto create(const Q15ProbePlatformBinding& binding,
                                   Q15PlatformOperations& operations)
      -> Result<std::unique_ptr<Q15PreparedProbeMemory>>;
  ~Q15PreparedProbeMemory();

  Q15PreparedProbeMemory(const Q15PreparedProbeMemory&) = delete;
  auto operator=(const Q15PreparedProbeMemory&) -> Q15PreparedProbeMemory& = delete;
  Q15PreparedProbeMemory(Q15PreparedProbeMemory&&) = delete;
  auto operator=(Q15PreparedProbeMemory&&) -> Q15PreparedProbeMemory& = delete;

  [[nodiscard]] auto address() const noexcept -> std::byte* { return address_; }
  [[nodiscard]] auto bytes() const noexcept -> std::span<const std::byte> {
    return {address_, byte_count_};
  }
  [[nodiscard]] auto mutable_bytes() noexcept -> std::span<std::byte> {
    return {address_, byte_count_};
  }
  [[nodiscard]] auto byte_count() const noexcept -> std::size_t { return byte_count_; }
  [[nodiscard]] auto page_count() const noexcept -> std::size_t {
    return byte_count_ / page_bytes_;
  }
  [[nodiscard]] auto page_bytes() const noexcept -> std::size_t { return page_bytes_; }
  [[nodiscard]] auto line_count() const noexcept -> std::size_t {
    return byte_count_ / kQ15ProbeCacheLineBytes;
  }
  [[nodiscard]] auto start_index() const noexcept -> std::uint32_t {
    return preparation_.start_index;
  }
  [[nodiscard]] auto prepared_sha256() const noexcept -> const workload::Sha256Digest& {
    return preparation_.prepared_sha256;
  }
  [[nodiscard]] auto cpu() const noexcept -> std::uint32_t { return cpu_; }
  [[nodiscard]] auto numa_node() const noexcept -> std::uint32_t { return numa_node_; }

private:
  Q15PreparedProbeMemory(Q15PlatformOperations& operations, std::byte* address,
                         std::size_t byte_count, Q15ProbePlatformBinding binding,
                         Q15PointerProbePreparation preparation) noexcept;

  Q15PlatformOperations* operations_;
  std::byte* address_;
  std::size_t byte_count_;
  std::size_t page_bytes_;
  std::uint32_t cpu_;
  std::uint32_t numa_node_;
  Q15PointerProbePreparation preparation_;
};

struct Q15ProbePassObservation final {
  Q15ProbeKind kind;
  Q15CountedPassEvidence counted;
  Q15ProbeIntegrityEvidence integrity;
  Q15ResidencySnapshot before_residency;
  Q15ResidencySnapshot during_residency;
  Q15ResidencySnapshot after_residency;
  std::uint32_t entry_cpu;
  std::uint32_t exit_cpu;
  bool singleton_affinity;
  std::uint64_t diagnostic_begin_nanoseconds;
  std::uint64_t diagnostic_end_nanoseconds;
  std::uint64_t retention_value;

  [[nodiscard]] auto residency_passes(std::uint32_t expected_node,
                                      std::size_t expected_pages) const noexcept
      -> bool;
  [[nodiscard]] auto cpu_passes(std::uint32_t expected_cpu) const noexcept -> bool;
};

[[nodiscard]] auto run_q15_probe_pass(Q15ProbeKind kind, Q15PreparedProbeMemory& memory,
                                      Q15PerfOperations& perf,
                                      Q15PlatformOperations& platform)
    -> Result<Q15ProbePassObservation>;

[[nodiscard]] auto encode_q15_evidence_frame(std::string_view canonical_json,
                                             std::size_t maximum_payload_bytes)
    -> Result<std::vector<std::byte>>;
[[nodiscard]] auto decode_q15_evidence_frame(std::span<const std::byte> frame,
                                             std::size_t maximum_payload_bytes)
    -> Result<std::string>;

struct Q15PeerCredentials final {
  std::int32_t process_id;
  std::uint32_t user_id;
  std::uint32_t group_id;

  auto operator==(const Q15PeerCredentials&) const -> bool = default;
};

struct Q15AcceptedPeer final {
  int descriptor;
  Q15PeerCredentials credentials;
};

struct Q15FrameLimit final {
  std::size_t maximum_payload_bytes;
};

// Fixed AF_UNIX/SOCK_SEQPACKET production seam. Abstract names must use the
// accepted prefix, and SO_PEERCRED is captured before any frame is accepted.
// These methods perform no retry, authorization decision, or network listen.
class LinuxQ15LocalSocketOperations final {
public:
  [[nodiscard]] auto create_listener(std::string_view abstract_name) -> Result<int>;
  [[nodiscard]] auto accept_peer(int listener_descriptor) -> Result<Q15AcceptedPeer>;
  [[nodiscard]] auto receive_frame(int peer_descriptor, Q15FrameLimit limit)
      -> Result<std::string>;
  [[nodiscard]] auto send_frame(int peer_descriptor, std::string_view canonical_json,
                                std::size_t maximum_payload_bytes) -> BackendResult;
  [[nodiscard]] auto close_socket(int descriptor) -> BackendResult;
};

enum class Q15SessionState : std::uint8_t {
  created,
  h0_regular_complete,
  h0_pointer_complete,
  h0_sealed_waiting_for_q15_w,
  h1_readback_verified,
  h1_regular_complete,
  h1_pointer_complete,
  restoration_readback_verified,
  completed,
  failed,
};

enum class Q15SessionAction : std::uint8_t {
  record_h0_regular,
  record_h0_pointer,
  seal_h0,
  verify_h1_readback,
  record_h1_regular,
  record_h1_pointer,
  verify_restoration_readback,
  finalize,
};

[[nodiscard]] auto to_string(Q15SessionState state) noexcept -> std::string_view;

struct Q15SessionBinding final {
  std::string session_id;
  std::string stand_id;
  std::string binding_id;
  std::string q15_r_authorization_sha256;
  std::string binary_sha256;
  std::string probe_contract_sha256;
  std::string probe_implementation_profile_sha256;
  std::string dynamic_implementation_profile_sha256;
  std::uint32_t cpu;
  std::uint32_t numa_node;
  std::uint64_t verified_local_llc_bytes;
  std::uint64_t verified_base_page_bytes;
  Q15PeerCredentials q15_r_controller;
  Q15PeerCredentials q15_w_controller;
  std::uint64_t h0_complete_value;
  std::uint64_t h1_complete_value;
  std::uint64_t expires_at_monotonic_nanoseconds;
};

struct Q15SessionActionInput final {
  Q15SessionAction action;
  Q15PeerCredentials peer;
  std::uint64_t now_monotonic_nanoseconds;
  std::string authorization_sha256;
  std::string evidence_artifact_id;
  std::string evidence_sha256;
  std::string q15_r_evidence_set_sha256;
  std::uint64_t observed_complete_value;
  const std::byte* buffer_address;
  workload::Sha256Digest buffer_sha256;
};

struct Q15SessionTransition final {
  Q15SessionState from;
  Q15SessionState to;
  Q15SessionAction action;
  std::uint64_t at_monotonic_nanoseconds;
  Q15PeerCredentials peer;
  std::string evidence_artifact_id;
  std::string evidence_sha256;
};

struct Q15SessionFailure final {
  Q15SessionState from;
  std::uint64_t at_monotonic_nanoseconds;
  Q15PeerCredentials peer;
  Error error;
};

class Q15ProbeSessionStateMachine final {
public:
  [[nodiscard]] static auto create(const Q15SessionBinding& binding,
                                   const Q15PreparedProbeMemory& memory)
      -> Result<std::unique_ptr<Q15ProbeSessionStateMachine>>;

  [[nodiscard]] auto advance(const Q15SessionActionInput& input)
      -> Result<Q15SessionTransition>;
  [[nodiscard]] auto record_control_disconnect(Q15PeerCredentials peer,
                                               std::uint64_t at_monotonic_nanoseconds)
      -> Result<Q15SessionTransition>;
  [[nodiscard]] auto state() const noexcept -> Q15SessionState { return state_; }
  [[nodiscard]] auto transitions() const noexcept
      -> std::span<const Q15SessionTransition> {
    return transitions_;
  }
  [[nodiscard]] auto failure() const noexcept -> const Q15SessionFailure* {
    return failure_ ? &*failure_ : nullptr;
  }
  [[nodiscard]] auto
  buffer_identity_unchanged(const Q15PreparedProbeMemory& memory) const -> bool;

private:
  Q15ProbeSessionStateMachine(Q15SessionBinding binding,
                              const Q15PreparedProbeMemory& memory);
  [[nodiscard]] auto fail(Error error, Q15PeerCredentials peer,
                          std::uint64_t at_monotonic_nanoseconds)
      -> Result<Q15SessionTransition>;

  Q15SessionBinding binding_;
  Q15SessionState state_{Q15SessionState::created};
  const Q15PreparedProbeMemory* memory_{nullptr};
  const std::byte* buffer_address_{nullptr};
  std::size_t buffer_byte_count_{0U};
  workload::Sha256Digest prepared_sha256_{{}};
  std::string q15_w_authorization_sha256_;
  std::string q15_r_evidence_set_sha256_;
  std::vector<Q15SessionTransition> transitions_;
  std::optional<Q15SessionFailure> failure_;
};

} // namespace cpu_prefetch::platform

#endif // CPU_PREFETCH_PLATFORM_Q15_RUNTIME_HPP
