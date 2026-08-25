#include "cpu_prefetch/qualification/p4_k_a_controller.hpp"

#include <algorithm>
#include <array>
#include <chrono>
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

[[nodiscard]] auto decimal(std::string_view text, std::size_t offset, std::size_t count)
    -> std::optional<unsigned> {
  unsigned value = 0U;
  if (offset > text.size() || count > text.size() - offset) {
    return std::nullopt;
  }
  for (std::size_t index = offset; index < offset + count; ++index) {
    if (text[index] < '0' || text[index] > '9') {
      return std::nullopt;
    }
    value = value * 10U + static_cast<unsigned>(text[index] - '0');
  }
  return value;
}

[[nodiscard]] auto parse_utc_seconds(std::string_view text)
    -> std::optional<std::uint64_t> {
  if (text.size() != 20U || text[4] != '-' || text[7] != '-' || text[10] != 'T' ||
      text[13] != ':' || text[16] != ':' || text[19] != 'Z') {
    return std::nullopt;
  }
  const auto year = decimal(text, 0U, 4U);
  const auto month = decimal(text, 5U, 2U);
  const auto day = decimal(text, 8U, 2U);
  const auto hour = decimal(text, 11U, 2U);
  const auto minute = decimal(text, 14U, 2U);
  const auto second = decimal(text, 17U, 2U);
  if (!year || !month || !day || !hour || !minute || !second || *hour >= 24U ||
      *minute >= 60U || *second >= 60U) {
    return std::nullopt;
  }
  const std::chrono::year_month_day date{std::chrono::year(static_cast<int>(*year)),
                                         std::chrono::month(*month),
                                         std::chrono::day(*day)};
  if (!date.ok()) {
    return std::nullopt;
  }
  const auto days = std::chrono::sys_days(date).time_since_epoch().count();
  if (days < 0) {
    return std::nullopt;
  }
  constexpr std::uint64_t kSecondsPerDay = 86'400U;
  const auto day_count = static_cast<std::uint64_t>(days);
  if (day_count > std::numeric_limits<std::uint64_t>::max() / kSecondsPerDay) {
    return std::nullopt;
  }
  return day_count * kSecondsPerDay + static_cast<std::uint64_t>(*hour) * 3'600U +
         static_cast<std::uint64_t>(*minute) * 60U +
         static_cast<std::uint64_t>(*second);
}

[[nodiscard]] auto is_direct_absolute_tool(std::string_view path) -> bool {
  constexpr std::array<std::string_view, 5U> kForbidden{
      "/bin/sh", "/usr/bin/sh", "/bin/bash", "/usr/bin/bash", "/usr/bin/env"};
  return !path.empty() && path.front() == '/' &&
         std::ranges::find(kForbidden, path) == kForbidden.end();
}

[[nodiscard]] auto environment_is_bounded_and_nonsecret(
    const std::vector<P4KAEnvironmentEntry>& environment) -> bool {
  constexpr std::array<std::string_view, 4U> kAllowed{"LANG", "LC_ALL", "PATH", "TZ"};
  std::set<std::string> names;
  for (const auto& entry : environment) {
    if (std::ranges::find(kAllowed, entry.name) == kAllowed.end() ||
        !names.insert(entry.name).second || entry.value.empty() ||
        entry.value.find('\0') != std::string::npos) {
      return false;
    }
  }
  return !environment.empty();
}

[[nodiscard]] auto add_checked(std::uint64_t& total, std::uint64_t increment) -> bool {
  if (increment > std::numeric_limits<std::uint64_t>::max() - total) {
    return false;
  }
  total += increment;
  return true;
}

} // namespace

auto to_string(P4KAControllerStep step) noexcept -> std::string_view {
  switch (step) {
  case P4KAControllerStep::verify_signed_authorization_and_bootstrap_trust:
    return "VERIFY_SIGNED_AUTHORIZATION_AND_BOOTSTRAP_TRUST";
  case P4KAControllerStep::verify_offline_environment_toolchain_and_network_state:
    return "VERIFY_OFFLINE_ENVIRONMENT_TOOLCHAIN_AND_NETWORK_STATE";
  case P4KAControllerStep::verify_custody_and_create_exclusive_public_outputs:
    return "VERIFY_CUSTODY_AND_CREATE_EXCLUSIVE_PUBLIC_OUTPUTS";
  case P4KAControllerStep::generate_encrypted_ed25519_private_key_once:
    return "GENERATE_ENCRYPTED_ED25519_PRIVATE_KEY_ONCE";
  case P4KAControllerStep::extract_ed25519_public_key_once:
    return "EXTRACT_ED25519_PUBLIC_KEY_ONCE";
  case P4KAControllerStep::derive_ed25519_fingerprint_once:
    return "DERIVE_ED25519_FINGERPRINT_ONCE";
  case P4KAControllerStep::construct_canonical_allowed_signers_once:
    return "CONSTRUCT_CANONICAL_ALLOWED_SIGNERS_ONCE";
  case P4KAControllerStep::capture_nonsecret_custody_receipt:
    return "CAPTURE_NONSECRET_CUSTODY_RECEIPT";
  case P4KAControllerStep::seal_complete_or_partial_public_evidence:
    return "SEAL_COMPLETE_OR_PARTIAL_PUBLIC_EVIDENCE";
  case P4KAControllerStep::stop_for_separate_p4_k_r:
    return "STOP_FOR_SEPARATE_P4_K_R";
  }
  return "UNKNOWN";
}

auto validate_p4_k_a_controller_admission(const P4KAControllerAdmission& admission,
                                          const P4KAControllerTrustAnchor& trust_anchor,
                                          std::uint64_t now_epoch_seconds)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  const auto exact = [&](std::string_view actual, std::string_view expected,
                         std::string path, std::string rule) {
    if (actual != expected) {
      errors.push_back(error(ErrorCategory::reference_mismatch, std::move(path),
                             std::move(rule), "value differs from the fixed binding"));
    }
  };
  exact(admission.schema_version, kP4KAControllerAdmissionSchemaVersion,
        "$/schema_version", "P4KA-SCHEMA");
  exact(admission.protocol_version, protocol::kProtocolVersion, "$/protocol_version",
        "P4KA-PROTOCOL");
  exact(admission.controller_profile_id, kP4KAControllerProfileId,
        "$/controller_profile_id", "P4KA-CONTROLLER-PROFILE");
  exact(admission.gate_id, kP4KAGateId, "$/gate_id", "P4KA-GATE");
  exact(admission.status, "AUTHORIZED", "$/status", "P4KA-STATUS");
  exact(admission.signature_scheme, kP4KASignatureScheme, "$/signature_scheme",
        "P4KA-SIGNATURE-SCHEME");
  exact(admission.signature_namespace, kP4KASignatureNamespace, "$/signature_namespace",
        "P4KA-SIGNATURE-NAMESPACE");
  exact(admission.authorization_principal, kP4KAAuthorizationPrincipal,
        "$/authorization_principal", "P4KA-AUTHORIZATION-PRINCIPAL");

  exact(admission.source_revision, trust_anchor.source_revision, "$/source_revision",
        "P4KA-SOURCE");
  exact(admission.controller_binary_sha256, trust_anchor.controller_binary_sha256,
        "$/controller_binary_sha256", "P4KA-BINARY");
  exact(admission.binding_id, trust_anchor.binding_id, "$/binding_id", "P4KA-BINDING");
  exact(admission.authorization_core_sha256, trust_anchor.authorization_core_sha256,
        "$/authorization_core_sha256", "P4KA-AUTHORIZATION-CORE");
  exact(admission.detached_signature_artifact_id,
        trust_anchor.detached_signature_artifact_id, "$/detached_signature_artifact_id",
        "P4KA-SIGNATURE-ID");
  exact(admission.detached_signature_sha256, trust_anchor.detached_signature_sha256,
        "$/detached_signature_sha256", "P4KA-SIGNATURE-HASH");
  exact(admission.signature_verification_artifact_id,
        trust_anchor.signature_verification_artifact_id,
        "$/signature_verification_artifact_id", "P4KA-VERIFICATION-ID");
  exact(admission.signature_verification_sha256,
        trust_anchor.signature_verification_sha256, "$/signature_verification_sha256",
        "P4KA-VERIFICATION-HASH");
  exact(admission.bootstrap_signer_fingerprint,
        trust_anchor.bootstrap_signer_fingerprint, "$/bootstrap_signer_fingerprint",
        "P4KA-BOOTSTRAP-SIGNER");
  exact(admission.bootstrap_trust_artifact_id, trust_anchor.bootstrap_trust_artifact_id,
        "$/bootstrap_trust_artifact_id", "P4KA-BOOTSTRAP-TRUST-ID");
  exact(admission.bootstrap_trust_sha256, trust_anchor.bootstrap_trust_sha256,
        "$/bootstrap_trust_sha256", "P4KA-BOOTSTRAP-TRUST-HASH");
  exact(admission.auditor_review_artifact_id, trust_anchor.auditor_review_artifact_id,
        "$/auditor_review_artifact_id", "P4KA-AUDITOR-REVIEW-ID");
  exact(admission.auditor_review_sha256, trust_anchor.auditor_review_sha256,
        "$/auditor_review_sha256", "P4KA-AUDITOR-REVIEW-HASH");
  exact(admission.offline_environment_sha256, trust_anchor.offline_environment_sha256,
        "$/offline_environment_sha256", "P4KA-ENVIRONMENT-HASH");
  exact(admission.toolchain_sha256, trust_anchor.toolchain_sha256, "$/toolchain_sha256",
        "P4KA-TOOLCHAIN-HASH");
  exact(admission.custody_sha256, trust_anchor.custody_sha256, "$/custody_sha256",
        "P4KA-CUSTODY-HASH");
  exact(admission.public_export_transaction_id,
        trust_anchor.public_export_transaction_id, "$/public_export_transaction_id",
        "P4KA-PUBLIC-EXPORT-ID");
  exact(admission.public_export_root, trust_anchor.public_export_root,
        "$/public_export_root", "P4KA-PUBLIC-EXPORT-ROOT");
  exact(admission.issued_at_utc, trust_anchor.issued_at_utc, "$/issued_at_utc",
        "P4KA-ISSUED-AT");
  exact(admission.expires_at_utc, trust_anchor.expires_at_utc, "$/expires_at_utc",
        "P4KA-EXPIRES-AT");

  for (const auto* value :
       {&admission.controller_binary_sha256, &admission.authorization_core_sha256,
        &admission.detached_signature_sha256, &admission.signature_verification_sha256,
        &admission.bootstrap_trust_sha256, &admission.auditor_review_sha256,
        &admission.offline_environment_sha256, &admission.toolchain_sha256,
        &admission.custody_sha256}) {
    if (!protocol::Sha256::parse(*value, "$/sha256")) {
      errors.push_back(error(ErrorCategory::invalid_hash, "$/sha256", "P4KA-SHA256",
                             "every bound hash must be valid"));
    }
  }

  const auto issued = parse_utc_seconds(admission.issued_at_utc);
  const auto expires = parse_utc_seconds(admission.expires_at_utc);
  if (!issued || !expires || *expires < *issued ||
      *expires - *issued != kP4KAAuthorizationValiditySeconds ||
      now_epoch_seconds < issued.value_or(0U) ||
      now_epoch_seconds >= expires.value_or(0U)) {
    errors.push_back(
        error(ErrorCategory::out_of_range, "$/validity", "P4KA-VALIDITY",
              "RFC3339 UTC authorization must be active and exactly 1800 seconds"));
  }

  if (trust_anchor.source_dirty || !trust_anchor.bootstrap_signature_verified ||
      !trust_anchor.distinct_auditor_review_verified ||
      !trust_anchor.offline_environment_verified || !trust_anchor.custody_verified ||
      !trust_anchor.public_export_verified_create_exclusive) {
    errors.push_back(
        error(ErrorCategory::missing_evidence, "$/trust_anchor", "P4KA-TRUST-EVIDENCE",
              "clean source and independent bootstrap, auditor, environment, custody, "
              "and create-exclusive export verification are mandatory"));
  }

  const std::array<std::string_view, 9U> artifact_ids{
      admission.detached_signature_artifact_id,
      admission.signature_verification_artifact_id,
      admission.bootstrap_trust_artifact_id,
      admission.auditor_review_artifact_id,
      admission.offline_environment_artifact_id,
      admission.toolchain_artifact_id,
      admission.custody_artifact_id,
      admission.public_export_transaction_id,
      admission.authorization_id,
  };
  std::set<std::string_view> distinct_artifacts;
  if (admission.binding_id.empty() || admission.source_revision.empty() ||
      admission.bootstrap_signer_fingerprint.empty() ||
      admission.public_export_root.empty() ||
      admission.public_export_root.front() != '/' ||
      std::ranges::any_of(artifact_ids,
                          [](std::string_view value) { return value.empty(); }) ||
      !std::ranges::all_of(artifact_ids, [&](std::string_view value) {
        return distinct_artifacts.insert(value).second;
      })) {
    errors.push_back(error(ErrorCategory::reference_mismatch, "$/identity",
                           "P4KA-IDENTITY-SEPARATION",
                           "binding, signer, absolute export root, and distinct "
                           "nonempty artifact identities are mandatory"));
  }

  if (!is_direct_absolute_tool(admission.key_generation_tool_path) ||
      !is_direct_absolute_tool(admission.public_extraction_tool_path) ||
      admission.key_generation_argv.empty() ||
      admission.public_extraction_argv.empty() ||
      admission.key_generation_argv.front() != admission.key_generation_tool_path ||
      admission.public_extraction_argv.front() !=
          admission.public_extraction_tool_path ||
      !environment_is_bounded_and_nonsecret(admission.fixed_environment)) {
    errors.push_back(error(
        ErrorCategory::reference_mismatch, "$/process_contract", "P4KA-DIRECT-ARGV-ENV",
        "absolute non-shell tools, matching argv[0], and a bounded non-secret "
        "environment are mandatory"));
  }

  const bool descriptor_contract =
      (admission.secret_input_kind == P4KASecretInputKind::controlling_tty &&
       !admission.secret_input_descriptor.has_value()) ||
      (admission.secret_input_kind == P4KASecretInputKind::dedicated_descriptor &&
       admission.secret_input_descriptor.has_value() &&
       *admission.secret_input_descriptor >= 3);
  if (!descriptor_contract) {
    errors.push_back(error(ErrorCategory::cross_field, "$/secret_input",
                           "P4KA-SECRET-INPUT-BOUNDARY",
                           "secret input must use only an uncaptured controlling TTY "
                           "or one dedicated descriptor"));
  }

  if (admission.limits.maximum_wall_seconds == 0U ||
      admission.limits.maximum_stdout_bytes == 0U ||
      admission.limits.maximum_stderr_bytes == 0U ||
      admission.limits.maximum_public_artifact_count == 0U) {
    errors.push_back(
        error(ErrorCategory::out_of_range, "$/limits", "P4KA-LIMITS",
              "every authorization-bound resource limit must be positive"));
  }
  if (!std::ranges::equal(admission.command_graph, kP4KAControllerGraph) ||
      admission.action_attempt_count != 1U || admission.retry_count != 0U ||
      !admission.network_unavailable_verified ||
      !admission.public_export_outside_repository_and_stand_verified ||
      !admission.create_exclusive_public_outputs ||
      admission.overwrite_repair_cleanup_allowed || !admission.stop_before_p4_k_r ||
      admission.automatic_continuation_allowed) {
    errors.push_back(
        error(ErrorCategory::reference_mismatch, "$/fixed_action_contract",
              "P4KA-FIXED-ACTION-CONTRACT",
              "the fixed graph, offline/export proof, one attempt, zero retry, no "
              "overwrite/repair/cleanup, and mandatory P4-K-R stop must be exact"));
  }
  return errors;
}

auto admit_p4_k_a_controller(const P4KAControllerAdmission& admission,
                             const P4KAControllerTrustAnchor& trust_anchor,
                             std::uint64_t now_epoch_seconds)
    -> protocol::Result<P4KAControllerTicket> {
  auto errors =
      validate_p4_k_a_controller_admission(admission, trust_anchor, now_epoch_seconds);
  if (!errors.empty()) {
    return protocol::Result<P4KAControllerTicket>::failure(std::move(errors));
  }
  const auto expires = parse_utc_seconds(admission.expires_at_utc);
  if (!expires) {
    return protocol::Result<P4KAControllerTicket>::failure(
        {error(ErrorCategory::out_of_range, "$/expires_at_utc", "P4KA-VALIDITY",
               "validated expiry must remain parseable")});
  }
  return protocol::Result<P4KAControllerTicket>::success(
      P4KAControllerTicket(admission.binding_id, admission.authorization_core_sha256,
                           admission.limits, *expires));
}

auto execute_p4_k_a_controller(const P4KAControllerTicket& ticket,
                               P4KAControllerOperations& operations)
    -> P4KAControllerReport {
  P4KAControllerReport report{
      P4KAControllerState::not_started, {}, std::nullopt, {}, 0U, 0U, 0U};
  report.evidence.reserve(kP4KAControllerGraph.size());
  std::set<std::string> artifact_ids;
  for (const auto step : kP4KAControllerGraph) {
    auto result = operations.run_step(step, ticket);
    if (!result) {
      report.state = P4KAControllerState::failed_partial_retained;
      report.failed_step = step;
      report.errors = result.errors();
      return report;
    }
    auto evidence = std::move(result).value();
    if (evidence.step != step || evidence.artifact_id.empty() || !evidence.complete ||
        !artifact_ids.insert(evidence.artifact_id).second ||
        !protocol::Sha256::parse(evidence.sha256, "$/evidence/sha256") ||
        evidence.private_material_disclosed ||
        evidence.overwrite_retry_repair_or_cleanup_performed) {
      report.state = P4KAControllerState::failed_partial_retained;
      report.failed_step = step;
      report.errors.push_back(error(
          ErrorCategory::reference_mismatch, "$/evidence", "P4KA-STEP-EVIDENCE",
          "evidence must be complete, unique, hash-bound, step-matched, public-only, "
          "and produced without overwrite, retry, repair, or cleanup"));
      return report;
    }
    if (evidence.wall_seconds > ticket.limits().maximum_wall_seconds ||
        evidence.observed_at_epoch_seconds >= ticket.expires_at_epoch_seconds()) {
      report.state = P4KAControllerState::failed_partial_retained;
      report.failed_step = step;
      report.errors.push_back(error(ErrorCategory::out_of_range, "$/limits",
                                    "P4KA-TIME-LIMIT",
                                    "step wall time or authorization expiry exceeded"));
      return report;
    }
    if (!add_checked(report.total_stdout_bytes, evidence.stdout_bytes) ||
        !add_checked(report.total_stderr_bytes, evidence.stderr_bytes) ||
        !add_checked(report.total_public_artifact_count,
                     evidence.public_artifact_count)) {
      report.state = P4KAControllerState::failed_partial_retained;
      report.failed_step = step;
      report.errors.push_back(error(ErrorCategory::out_of_range, "$/limits",
                                    "P4KA-RESOURCE-OVERFLOW",
                                    "resource accumulation overflowed"));
      return report;
    }
    report.evidence.push_back(std::move(evidence));
    if (report.total_stdout_bytes > ticket.limits().maximum_stdout_bytes ||
        report.total_stderr_bytes > ticket.limits().maximum_stderr_bytes ||
        report.total_public_artifact_count >
            ticket.limits().maximum_public_artifact_count) {
      report.state = P4KAControllerState::failed_partial_retained;
      report.failed_step = step;
      report.errors.push_back(
          error(ErrorCategory::out_of_range, "$/limits", "P4KA-RESOURCE-LIMIT",
                "authorization-bound public evidence limit exceeded"));
      return report;
    }
  }
  report.state = P4KAControllerState::public_evidence_sealed_waiting_for_p4_k_r;
  return report;
}

} // namespace cpu_prefetch::qualification
