#ifndef CPU_PREFETCH_QUALIFICATION_Q15_CONTROLLER_HPP
#define CPU_PREFETCH_QUALIFICATION_Q15_CONTROLLER_HPP

#include "cpu_prefetch/protocol/model.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::qualification {

inline constexpr std::string_view kQ15RControllerProfileId =
    "Q15-R-STATIC-CONTROLLER-v1";
inline constexpr std::string_view kQ15RAuthorizationSchemaVersion =
    "cpu-prefetch-q15-qualification-authorization/2";
inline constexpr std::string_view kQ15RAuthorizationSignatureScheme =
    "OPENSSH-SSHSIG-ED25519-SHA512-v1";
inline constexpr std::string_view kQ15RAuthorizationSignatureNamespace =
    "cpu-prefetch-q15-authorization";

enum class Q15RControllerStep : std::uint8_t {
  verify_authorization_and_release_bindings,
  verify_role_and_negative_access_evidence,
  create_private_same_buffer_session,
  collect_fixed_msr_prestate_as_auditor,
  collect_clock,
  collect_atomic_layout,
  collect_actual_cpu_migration,
  collect_address_residency,
  collect_software_prefetch_capability,
  collect_storage_custody,
  negative_access_check,
  run_h0_regular_stream_probe,
  run_h0_pointer_stream_probe,
  seal_q15_r_evidence,
  wait_for_separate_q15_w_or_expire_fail_closed,
};

inline constexpr std::array kQ15RControllerGraph{
    Q15RControllerStep::verify_authorization_and_release_bindings,
    Q15RControllerStep::verify_role_and_negative_access_evidence,
    Q15RControllerStep::create_private_same_buffer_session,
    Q15RControllerStep::collect_fixed_msr_prestate_as_auditor,
    Q15RControllerStep::collect_clock,
    Q15RControllerStep::collect_atomic_layout,
    Q15RControllerStep::collect_actual_cpu_migration,
    Q15RControllerStep::collect_address_residency,
    Q15RControllerStep::collect_software_prefetch_capability,
    Q15RControllerStep::collect_storage_custody,
    Q15RControllerStep::negative_access_check,
    Q15RControllerStep::run_h0_regular_stream_probe,
    Q15RControllerStep::run_h0_pointer_stream_probe,
    Q15RControllerStep::seal_q15_r_evidence,
    Q15RControllerStep::wait_for_separate_q15_w_or_expire_fail_closed,
};

[[nodiscard]] auto to_string(Q15RControllerStep step) noexcept -> std::string_view;

struct Q15RControllerLimits final {
  std::uint64_t authorization_validity_seconds;
  std::uint64_t max_same_buffer_session_wall_seconds;
  std::uint64_t max_active_collection_wall_seconds;
  std::uint64_t external_start_watchdog_seconds;
  std::uint64_t controller_start_poll_limit;
  std::uint64_t worker_start_poll_limit;
  std::uint64_t max_cpu_seconds;
  std::uint64_t max_output_bytes;
  std::uint64_t max_artifact_count;
  std::uint64_t frame_maximum_payload_bytes;
  std::uint64_t primary_custody_quota_bytes;

  auto operator==(const Q15RControllerLimits&) const -> bool = default;
};

inline constexpr Q15RControllerLimits kQ15RControllerLimits{
    14'400U,
    14'400U,
    1'800U,
    60U,
    18'446'744'073'709'551'615ULL,
    18'446'744'073'709'551'615ULL,
    7'200U,
    2'147'483'648U,
    128U,
    16'777'216U,
    4'294'967'296U,
};

struct Q15RControllerAuthorities final {
  std::string operator_id;
  std::string controller_id;
  std::string custodian_id;
  std::string auditor_id;
};

struct Q15RControllerCustody final {
  std::string primary_domain_id;
  std::string secondary_domain_id;
  std::string output_root;
  std::string append_only_policy_id;
  std::string transfer_policy_id;
  std::string partial_artifact_policy_id;
  std::string recovery_policy_id;
};

struct Q15RControllerAdmission final {
  std::string schema_version;
  std::string protocol_version;
  std::string controller_profile_id;
  std::string phase;
  std::string status;
  std::string source_revision;
  std::string controller_binary_sha256;
  std::string stand_id;
  std::string binding_id;
  std::string authorization_core_sha256;
  std::string detached_signature_artifact_id;
  std::string detached_signature_sha256;
  std::string signature_verification_artifact_id;
  std::string signature_verification_sha256;
  std::string signature_scheme;
  std::string signature_namespace;
  Q15RControllerLimits limits;
  Q15RControllerAuthorities authorities;
  Q15RControllerCustody custody;
  std::vector<Q15RControllerStep> command_graph;
  std::vector<std::string> stop_conditions;
  bool all_prohibitions_disabled;
};

struct Q15RControllerTrustAnchor final {
  std::string source_revision;
  std::string controller_binary_sha256;
  std::string stand_id;
  std::string binding_id;
  std::string authorization_core_sha256;
  std::string detached_signature_artifact_id;
  std::string detached_signature_sha256;
  std::string signature_verification_artifact_id;
  std::string signature_verification_sha256;
  std::string signature_scheme;
  std::string signature_namespace;
  bool source_dirty;
  bool independent_signature_verified;
};

class Q15RControllerTicket final {
public:
  [[nodiscard]] auto binding_id() const noexcept -> std::string_view {
    return binding_id_;
  }
  [[nodiscard]] auto authorization_core_sha256() const noexcept -> std::string_view {
    return authorization_core_sha256_;
  }
  [[nodiscard]] auto limits() const noexcept -> const Q15RControllerLimits& {
    return limits_;
  }

private:
  friend auto admit_q15_r_controller(const Q15RControllerAdmission&,
                                     const Q15RControllerTrustAnchor&)
      -> protocol::Result<Q15RControllerTicket>;

  Q15RControllerTicket(std::string binding_id, std::string authorization_core_sha256,
                       Q15RControllerLimits limits)
      : binding_id_(std::move(binding_id)),
        authorization_core_sha256_(std::move(authorization_core_sha256)),
        limits_(limits) {}

  std::string binding_id_;
  std::string authorization_core_sha256_;
  Q15RControllerLimits limits_{};
};

[[nodiscard]] auto
validate_q15_r_controller_admission(const Q15RControllerAdmission& admission,
                                    const Q15RControllerTrustAnchor& trust_anchor)
    -> std::vector<protocol::ValidationError>;

[[nodiscard]] auto admit_q15_r_controller(const Q15RControllerAdmission& admission,
                                          const Q15RControllerTrustAnchor& trust_anchor)
    -> protocol::Result<Q15RControllerTicket>;

struct Q15RStepEvidence final {
  Q15RControllerStep step;
  std::string artifact_id;
  std::string sha256;
  std::uint64_t byte_count;
  std::uint64_t maximum_frame_payload_bytes;
  std::uint64_t active_collection_wall_seconds;
  std::uint64_t same_buffer_session_wall_seconds;
  std::uint64_t cpu_seconds;
  bool complete;
};

class Q15RControllerOperations {
public:
  virtual ~Q15RControllerOperations() = default;
  [[nodiscard]] virtual auto run_step(Q15RControllerStep step,
                                      const Q15RControllerTicket& ticket)
      -> protocol::Result<Q15RStepEvidence> = 0;
};

enum class Q15RControllerState : std::uint8_t {
  not_started,
  q15_r_sealed_waiting_for_q15_w,
  failed_partial_retained,
};

struct Q15RControllerReport final {
  Q15RControllerState state;
  std::vector<Q15RStepEvidence> evidence;
  std::optional<Q15RControllerStep> failed_step;
  std::vector<protocol::ValidationError> errors;
  std::uint64_t total_output_bytes;
};

// Executes the exact graph once. There is no retry, fallback, step selector,
// scientific input, or continuation after the first failure.
[[nodiscard]] auto execute_q15_r_controller(const Q15RControllerTicket& ticket,
                                            Q15RControllerOperations& operations)
    -> Q15RControllerReport;

} // namespace cpu_prefetch::qualification

#endif // CPU_PREFETCH_QUALIFICATION_Q15_CONTROLLER_HPP
