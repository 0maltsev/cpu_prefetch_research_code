#ifndef CPU_PREFETCH_QUALIFICATION_P4_K_A_CONTROLLER_HPP
#define CPU_PREFETCH_QUALIFICATION_P4_K_A_CONTROLLER_HPP

#include "cpu_prefetch/protocol/model.hpp"

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::qualification {

inline constexpr std::string_view kP4KAControllerProfileId =
    "Q15-R-P4-K-A-FIXED-CEREMONY-CONTROLLER-v1";
inline constexpr std::string_view kP4KAControllerAdmissionSchemaVersion =
    "cpu-prefetch-q15-r-p4-k-a-controller-admission/1";
inline constexpr std::string_view kP4KAGateId = "Q15-R-P4-K-A";
inline constexpr std::string_view kP4KASignatureScheme =
    "OPENSSH-SSHSIG-ED25519-SHA512-v1";
inline constexpr std::string_view kP4KASignatureNamespace =
    "cpu-prefetch-q15-authorization";
inline constexpr std::string_view kP4KAAuthorizationPrincipal =
    "cpu-prefetch-q15-authorization";
inline constexpr std::uint64_t kP4KAAuthorizationValiditySeconds = 1'800U;

enum class P4KAControllerStep : std::uint8_t {
  verify_signed_authorization_and_bootstrap_trust,
  verify_offline_environment_toolchain_and_network_state,
  verify_custody_and_create_exclusive_public_outputs,
  generate_encrypted_ed25519_private_key_once,
  extract_ed25519_public_key_once,
  derive_ed25519_fingerprint_once,
  construct_canonical_allowed_signers_once,
  capture_nonsecret_custody_receipt,
  seal_complete_or_partial_public_evidence,
  stop_for_separate_p4_k_r,
};

inline constexpr std::array kP4KAControllerGraph{
    P4KAControllerStep::verify_signed_authorization_and_bootstrap_trust,
    P4KAControllerStep::verify_offline_environment_toolchain_and_network_state,
    P4KAControllerStep::verify_custody_and_create_exclusive_public_outputs,
    P4KAControllerStep::generate_encrypted_ed25519_private_key_once,
    P4KAControllerStep::extract_ed25519_public_key_once,
    P4KAControllerStep::derive_ed25519_fingerprint_once,
    P4KAControllerStep::construct_canonical_allowed_signers_once,
    P4KAControllerStep::capture_nonsecret_custody_receipt,
    P4KAControllerStep::seal_complete_or_partial_public_evidence,
    P4KAControllerStep::stop_for_separate_p4_k_r,
};

[[nodiscard]] auto to_string(P4KAControllerStep step) noexcept -> std::string_view;

enum class P4KASecretInputKind : std::uint8_t {
  controlling_tty,
  dedicated_descriptor,
};

struct P4KAEnvironmentEntry final {
  std::string name;
  std::string value;

  auto operator==(const P4KAEnvironmentEntry&) const -> bool = default;
};

struct P4KAControllerLimits final {
  std::uint64_t maximum_wall_seconds;
  std::uint64_t maximum_stdout_bytes;
  std::uint64_t maximum_stderr_bytes;
  std::uint64_t maximum_public_artifact_count;

  auto operator==(const P4KAControllerLimits&) const -> bool = default;
};

struct P4KAControllerAdmission final {
  std::string schema_version;
  std::string protocol_version;
  std::string controller_profile_id;
  std::string gate_id;
  std::string status;
  std::string source_revision;
  std::string controller_binary_sha256;
  std::string binding_id;
  std::string authorization_id;
  std::string authorization_core_sha256;
  std::string issued_at_utc;
  std::string expires_at_utc;
  std::string detached_signature_artifact_id;
  std::string detached_signature_sha256;
  std::string signature_verification_artifact_id;
  std::string signature_verification_sha256;
  std::string signature_scheme;
  std::string signature_namespace;
  std::string authorization_principal;
  std::string bootstrap_signer_fingerprint;
  std::string bootstrap_trust_artifact_id;
  std::string bootstrap_trust_sha256;
  std::string auditor_review_artifact_id;
  std::string auditor_review_sha256;
  std::string offline_environment_artifact_id;
  std::string offline_environment_sha256;
  std::string toolchain_artifact_id;
  std::string toolchain_sha256;
  std::string custody_artifact_id;
  std::string custody_sha256;
  std::string public_export_transaction_id;
  std::string public_export_root;
  std::string key_generation_tool_path;
  std::vector<std::string> key_generation_argv;
  std::string public_extraction_tool_path;
  std::vector<std::string> public_extraction_argv;
  std::vector<P4KAEnvironmentEntry> fixed_environment;
  P4KASecretInputKind secret_input_kind;
  std::optional<int> secret_input_descriptor;
  P4KAControllerLimits limits;
  std::vector<P4KAControllerStep> command_graph;
  std::uint64_t action_attempt_count;
  std::uint64_t retry_count;
  bool network_unavailable_verified;
  bool public_export_outside_repository_and_stand_verified;
  bool create_exclusive_public_outputs;
  bool overwrite_repair_cleanup_allowed;
  bool stop_before_p4_k_r;
  bool automatic_continuation_allowed;
};

struct P4KAControllerTrustAnchor final {
  std::string source_revision;
  std::string controller_binary_sha256;
  std::string binding_id;
  std::string authorization_core_sha256;
  std::string detached_signature_artifact_id;
  std::string detached_signature_sha256;
  std::string signature_verification_artifact_id;
  std::string signature_verification_sha256;
  std::string bootstrap_signer_fingerprint;
  std::string bootstrap_trust_artifact_id;
  std::string bootstrap_trust_sha256;
  std::string auditor_review_artifact_id;
  std::string auditor_review_sha256;
  std::string offline_environment_sha256;
  std::string toolchain_sha256;
  std::string custody_sha256;
  std::string public_export_transaction_id;
  std::string public_export_root;
  std::string issued_at_utc;
  std::string expires_at_utc;
  bool source_dirty;
  bool bootstrap_signature_verified;
  bool distinct_auditor_review_verified;
  bool offline_environment_verified;
  bool custody_verified;
  bool public_export_verified_create_exclusive;
};

class P4KAControllerTicket final {
public:
  [[nodiscard]] auto binding_id() const noexcept -> std::string_view {
    return binding_id_;
  }
  [[nodiscard]] auto authorization_core_sha256() const noexcept -> std::string_view {
    return authorization_core_sha256_;
  }
  [[nodiscard]] auto limits() const noexcept -> const P4KAControllerLimits& {
    return limits_;
  }
  [[nodiscard]] auto expires_at_epoch_seconds() const noexcept -> std::uint64_t {
    return expires_at_epoch_seconds_;
  }

private:
  friend auto admit_p4_k_a_controller(const P4KAControllerAdmission&,
                                      const P4KAControllerTrustAnchor&, std::uint64_t)
      -> protocol::Result<P4KAControllerTicket>;

  P4KAControllerTicket(std::string binding_id, std::string authorization_core_sha256,
                       P4KAControllerLimits limits,
                       std::uint64_t expires_at_epoch_seconds)
      : binding_id_(std::move(binding_id)),
        authorization_core_sha256_(std::move(authorization_core_sha256)),
        limits_(limits), expires_at_epoch_seconds_(expires_at_epoch_seconds) {}

  std::string binding_id_;
  std::string authorization_core_sha256_;
  P4KAControllerLimits limits_{};
  std::uint64_t expires_at_epoch_seconds_{};
};

[[nodiscard]] auto
validate_p4_k_a_controller_admission(const P4KAControllerAdmission& admission,
                                     const P4KAControllerTrustAnchor& trust_anchor,
                                     std::uint64_t now_epoch_seconds)
    -> std::vector<protocol::ValidationError>;

[[nodiscard]] auto
admit_p4_k_a_controller(const P4KAControllerAdmission& admission,
                        const P4KAControllerTrustAnchor& trust_anchor,
                        std::uint64_t now_epoch_seconds)
    -> protocol::Result<P4KAControllerTicket>;

struct P4KAStepEvidence final {
  P4KAControllerStep step;
  std::string artifact_id;
  std::string sha256;
  std::uint64_t stdout_bytes;
  std::uint64_t stderr_bytes;
  std::uint64_t public_artifact_count;
  std::uint64_t wall_seconds;
  std::uint64_t observed_at_epoch_seconds;
  bool complete;
  bool private_material_disclosed;
  bool overwrite_retry_repair_or_cleanup_performed;
};

class P4KAControllerOperations {
public:
  virtual ~P4KAControllerOperations() = default;
  [[nodiscard]] virtual auto run_step(P4KAControllerStep step,
                                      const P4KAControllerTicket& ticket)
      -> protocol::Result<P4KAStepEvidence> = 0;
};

enum class P4KAControllerState : std::uint8_t {
  not_started,
  public_evidence_sealed_waiting_for_p4_k_r,
  failed_partial_retained,
};

struct P4KAControllerReport final {
  P4KAControllerState state;
  std::vector<P4KAStepEvidence> evidence;
  std::optional<P4KAControllerStep> failed_step;
  std::vector<protocol::ValidationError> errors;
  std::uint64_t total_stdout_bytes;
  std::uint64_t total_stderr_bytes;
  std::uint64_t total_public_artifact_count;
};

[[nodiscard]] auto execute_p4_k_a_controller(const P4KAControllerTicket& ticket,
                                             P4KAControllerOperations& operations)
    -> P4KAControllerReport;

} // namespace cpu_prefetch::qualification

#endif // CPU_PREFETCH_QUALIFICATION_P4_K_A_CONTROLLER_HPP
