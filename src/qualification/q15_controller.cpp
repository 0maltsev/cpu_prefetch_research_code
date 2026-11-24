#include "cpu_prefetch/qualification/q15_controller.hpp"

#include <algorithm>
#include <limits>
#include <set>
#include <utility>

namespace cpu_prefetch::qualification {
namespace {

using protocol::ErrorCategory;
using protocol::ValidationError;

[[nodiscard]] auto error(ErrorCategory category, std::string path, std::string rule,
                         std::string message) -> ValidationError {
  return {category, std::move(path), std::move(rule), std::move(message)};
}

[[nodiscard]] auto authorities_are_exact(const Q15RControllerAuthorities& authorities)
    -> bool {
  return authorities.operator_id == "cpu-prefetch-q15-operator" &&
         authorities.controller_id == "cpu-prefetch-q15-controller" &&
         authorities.custodian_id == "cpu-prefetch-q15-custodian" &&
         authorities.auditor_id == "cpu-prefetch-q15-auditor";
}

[[nodiscard]] auto custody_is_exact(const Q15RControllerCustody& custody) -> bool {
  return custody.primary_domain_id == "XEON-CPU-FETCH-MD3-Q15-CUSTODY" &&
         custody.secondary_domain_id == "DEVELOPMENT-REPOSITORY-Q15-CUSTODY" &&
         custody.primary_domain_id != custody.secondary_domain_id &&
         custody.output_root == "/var/lib/cpu-prefetch/q15-r" &&
         custody.append_only_policy_id ==
             "Q15-PRIMARY-APPEND-ONLY-SEAL-THEN-TRANSFER-v1" &&
         custody.transfer_policy_id == "Q15-HASHED-SEALED-TRANSFER-WITH-RECEIPT-v1" &&
         custody.partial_artifact_policy_id == "Q15-RETAIN-PARTIAL-NEVER-PROMOTE-v1" &&
         custody.recovery_policy_id == "Q15-NO-OVERWRITE-NEW-ARTIFACT-ID-v1";
}

inline constexpr std::array<std::string_view, 7U> kQ15RStopConditions{
    "FIRST_AUTHORIZATION_OR_RELEASE_BINDING_MISMATCH",
    "FIRST_ROLE_OR_NEGATIVE_ACCESS_MISMATCH",
    "FIRST_PEER_CREDENTIAL_OR_TRANSPORT_MISMATCH",
    "FIRST_CLOCK_AFFINITY_NUMA_RESIDENCY_FAULT_PMU_OR_MSR_FAILURE",
    "FIRST_INTEGRITY_COUNT_CANONICALIZATION_HASH_OR_CUSTODY_FAILURE",
    "FIRST_LIMIT_EXPIRY_OR_DISCONNECT",
    "PRESERVE_PARTIAL_EVIDENCE_AND_NEVER_RETRY",
};

} // namespace

auto to_string(Q15RControllerStep step) noexcept -> std::string_view {
  switch (step) {
  case Q15RControllerStep::verify_authorization_and_release_bindings:
    return "VERIFY_AUTHORIZATION_AND_RELEASE_BINDINGS";
  case Q15RControllerStep::verify_role_and_negative_access_evidence:
    return "VERIFY_ROLE_AND_NEGATIVE_ACCESS_EVIDENCE";
  case Q15RControllerStep::create_private_same_buffer_session:
    return "CREATE_PRIVATE_SAME_BUFFER_SESSION";
  case Q15RControllerStep::collect_fixed_msr_prestate_as_auditor:
    return "COLLECT_FIXED_MSR_PRESTATE_AS_AUDITOR";
  case Q15RControllerStep::collect_clock:
    return "COLLECT_CLOCK";
  case Q15RControllerStep::collect_atomic_layout:
    return "COLLECT_ATOMIC_LAYOUT";
  case Q15RControllerStep::collect_actual_cpu_migration:
    return "COLLECT_ACTUAL_CPU_MIGRATION";
  case Q15RControllerStep::collect_address_residency:
    return "COLLECT_ADDRESS_RESIDENCY";
  case Q15RControllerStep::collect_software_prefetch_capability:
    return "COLLECT_SOFTWARE_PREFETCH_CAPABILITY";
  case Q15RControllerStep::collect_storage_custody:
    return "COLLECT_STORAGE_CUSTODY";
  case Q15RControllerStep::negative_access_check:
    return "NEGATIVE_ACCESS_CHECK";
  case Q15RControllerStep::run_h0_regular_stream_probe:
    return "RUN_H0_REGULAR_STREAM_PROBE";
  case Q15RControllerStep::run_h0_pointer_stream_probe:
    return "RUN_H0_POINTER_STREAM_PROBE";
  case Q15RControllerStep::seal_q15_r_evidence:
    return "SEAL_Q15_R_EVIDENCE";
  case Q15RControllerStep::wait_for_separate_q15_w_or_expire_fail_closed:
    return "WAIT_FOR_SEPARATE_Q15_W_OR_EXPIRE_FAIL_CLOSED";
  }
  return "UNKNOWN";
}

auto validate_q15_r_controller_admission(const Q15RControllerAdmission& admission,
                                         const Q15RControllerTrustAnchor& trust_anchor)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  const auto exact = [&](std::string_view actual, std::string_view expected,
                         std::string path, std::string rule) {
    if (actual != expected) {
      errors.push_back(error(ErrorCategory::reference_mismatch, std::move(path),
                             std::move(rule), "value differs from the fixed binding"));
    }
  };
  exact(admission.schema_version, kQ15RAuthorizationSchemaVersion, "$/schema_version",
        "Q15R-SCHEMA");
  exact(admission.protocol_version, protocol::kProtocolVersion, "$/protocol_version",
        "Q15R-PROTOCOL");
  exact(admission.controller_profile_id, kQ15RControllerProfileId,
        "$/controller_profile_id", "Q15R-CONTROLLER-PROFILE");
  exact(admission.phase, "Q15_R_READ_ONLY", "$/phase", "Q15R-PHASE");
  exact(admission.status, "AUTHORIZED", "$/status", "Q15R-STATUS");
  exact(admission.signature_scheme, kQ15RAuthorizationSignatureScheme,
        "$/signature_scheme", "Q15R-SIGNATURE-SCHEME");
  exact(admission.signature_namespace, kQ15RAuthorizationSignatureNamespace,
        "$/signature_namespace", "Q15R-SIGNATURE-NAMESPACE");
  exact(admission.source_revision, trust_anchor.source_revision, "$/source_revision",
        "Q15R-SOURCE");
  exact(admission.controller_binary_sha256, trust_anchor.controller_binary_sha256,
        "$/controller_binary_sha256", "Q15R-BINARY");
  exact(admission.stand_id, trust_anchor.stand_id, "$/stand_id", "Q15R-STAND");
  exact(admission.binding_id, trust_anchor.binding_id, "$/binding_id", "Q15R-BINDING");
  exact(admission.authorization_core_sha256, trust_anchor.authorization_core_sha256,
        "$/authorization_core_sha256", "Q15R-AUTHORIZATION-CORE");
  exact(admission.detached_signature_artifact_id,
        trust_anchor.detached_signature_artifact_id, "$/detached_signature_artifact_id",
        "Q15R-DETACHED-SIGNATURE-ARTIFACT");
  exact(admission.detached_signature_sha256, trust_anchor.detached_signature_sha256,
        "$/detached_signature_sha256", "Q15R-DETACHED-SIGNATURE");
  exact(admission.signature_verification_artifact_id,
        trust_anchor.signature_verification_artifact_id,
        "$/signature_verification_artifact_id", "Q15R-SIGNATURE-ARTIFACT");
  exact(admission.signature_verification_sha256,
        trust_anchor.signature_verification_sha256, "$/signature_verification_sha256",
        "Q15R-SIGNATURE-EVIDENCE");
  exact(admission.signature_scheme, trust_anchor.signature_scheme, "$/signature_scheme",
        "Q15R-VERIFIED-SIGNATURE-SCHEME");
  exact(admission.signature_namespace, trust_anchor.signature_namespace,
        "$/signature_namespace", "Q15R-VERIFIED-SIGNATURE-NAMESPACE");

  if (trust_anchor.source_dirty) {
    errors.push_back(error(ErrorCategory::missing_evidence, "$/source_revision",
                           "Q15R-DIRTY-SOURCE",
                           "a dirty controller cannot receive an execution ticket"));
  }
  if (!trust_anchor.independent_signature_verified) {
    errors.push_back(error(ErrorCategory::missing_evidence,
                           "$/independent_signature_verification",
                           "Q15R-SIGNATURE-NOT-VERIFIED",
                           "independent SSHSIG verification must pass first"));
  }
  for (const auto* value :
       {&admission.controller_binary_sha256, &admission.authorization_core_sha256,
        &admission.detached_signature_sha256,
        &admission.signature_verification_sha256}) {
    if (!protocol::Sha256::parse(*value, "$/sha256")) {
      errors.push_back(error(ErrorCategory::invalid_hash, "$/sha256", "Q15R-SHA256",
                             "all bound hashes must be valid"));
    }
  }
  if (admission.detached_signature_artifact_id.empty() ||
      admission.signature_verification_artifact_id.empty() ||
      admission.detached_signature_artifact_id ==
          admission.signature_verification_artifact_id) {
    errors.push_back(error(ErrorCategory::reference_mismatch, "$/signature",
                           "Q15R-SIGNATURE-SEPARATION",
                           "signature and verification artifacts must be distinct"));
  }
  if (admission.limits != kQ15RControllerLimits) {
    errors.push_back(error(ErrorCategory::reference_mismatch, "$/limits", "Q15R-LIMITS",
                           "limits differ from ADR-0059"));
  }
  if (!authorities_are_exact(admission.authorities)) {
    errors.push_back(error(ErrorCategory::reference_mismatch, "$/authorities",
                           "Q15R-AUTHORITIES", "role IDs differ from ADR-0058"));
  }
  if (!custody_is_exact(admission.custody)) {
    errors.push_back(error(ErrorCategory::reference_mismatch, "$/storage_custody",
                           "Q15R-CUSTODY", "custody policy differs from ADR-0058"));
  }
  if (!std::ranges::equal(admission.command_graph, kQ15RControllerGraph)) {
    errors.push_back(error(ErrorCategory::reference_mismatch, "$/command_graph",
                           "Q15R-GRAPH", "controller graph differs from ADR-0057"));
  }
  if (admission.stop_conditions.size() != kQ15RStopConditions.size() ||
      !std::equal(admission.stop_conditions.begin(), admission.stop_conditions.end(),
                  kQ15RStopConditions.begin())) {
    errors.push_back(error(ErrorCategory::reference_mismatch, "$/stop_conditions",
                           "Q15R-STOPS", "stop conditions differ from ADR-0059"));
  }
  if (!admission.all_prohibitions_disabled) {
    errors.push_back(error(ErrorCategory::missing_evidence, "$/prohibitions",
                           "Q15R-PROHIBITIONS",
                           "every prohibited action must remain disabled"));
  }
  return errors;
}

auto admit_q15_r_controller(const Q15RControllerAdmission& admission,
                            const Q15RControllerTrustAnchor& trust_anchor)
    -> protocol::Result<Q15RControllerTicket> {
  auto errors = validate_q15_r_controller_admission(admission, trust_anchor);
  if (!errors.empty()) {
    return protocol::Result<Q15RControllerTicket>::failure(std::move(errors));
  }
  return protocol::Result<Q15RControllerTicket>::success(Q15RControllerTicket(
      admission.binding_id, admission.authorization_core_sha256, admission.limits));
}

auto execute_q15_r_controller(const Q15RControllerTicket& ticket,
                              Q15RControllerOperations& operations)
    -> Q15RControllerReport {
  Q15RControllerReport report{
      Q15RControllerState::not_started, {}, std::nullopt, {}, 0U};
  report.evidence.reserve(kQ15RControllerGraph.size());
  std::set<std::string> artifact_ids;
  for (const auto step : kQ15RControllerGraph) {
    auto result = operations.run_step(step, ticket);
    if (!result) {
      report.state = Q15RControllerState::failed_partial_retained;
      report.failed_step = step;
      report.errors = result.errors();
      return report;
    }
    auto evidence = std::move(result).value();
    if (evidence.step != step || evidence.artifact_id.empty() || !evidence.complete ||
        !artifact_ids.insert(evidence.artifact_id).second ||
        !protocol::Sha256::parse(evidence.sha256, "$/evidence/sha256")) {
      report.state = Q15RControllerState::failed_partial_retained;
      report.failed_step = step;
      report.errors.push_back(error(
          ErrorCategory::reference_mismatch, "$/evidence", "Q15R-STEP-EVIDENCE",
          "step evidence must be complete, unique, hash-bound, and step-matched"));
      return report;
    }
    if (evidence.maximum_frame_payload_bytes >
            ticket.limits().frame_maximum_payload_bytes ||
        evidence.active_collection_wall_seconds >
            ticket.limits().max_active_collection_wall_seconds ||
        evidence.same_buffer_session_wall_seconds >
            ticket.limits().max_same_buffer_session_wall_seconds ||
        evidence.cpu_seconds > ticket.limits().max_cpu_seconds) {
      report.state = Q15RControllerState::failed_partial_retained;
      report.failed_step = step;
      report.errors.push_back(
          error(ErrorCategory::out_of_range, "$/limits", "Q15R-RESOURCE-LIMIT",
                "frame, wall-time, same-buffer-session, or CPU limit exceeded"));
      return report;
    }
    if (evidence.byte_count >
        std::numeric_limits<std::uint64_t>::max() - report.total_output_bytes) {
      report.state = Q15RControllerState::failed_partial_retained;
      report.failed_step = step;
      report.errors.push_back(error(ErrorCategory::out_of_range, "$/output_bytes",
                                    "Q15R-OUTPUT-OVERFLOW",
                                    "output byte accumulation overflowed"));
      return report;
    }
    report.total_output_bytes += evidence.byte_count;
    report.evidence.push_back(std::move(evidence));
    if (report.evidence.size() > ticket.limits().max_artifact_count ||
        report.total_output_bytes > ticket.limits().max_output_bytes) {
      report.state = Q15RControllerState::failed_partial_retained;
      report.failed_step = step;
      report.errors.push_back(error(ErrorCategory::out_of_range, "$/limits",
                                    "Q15R-OUTPUT-LIMIT",
                                    "artifact or output-byte limit exceeded"));
      return report;
    }
  }
  report.state = Q15RControllerState::q15_r_sealed_waiting_for_q15_w;
  return report;
}

} // namespace cpu_prefetch::qualification
