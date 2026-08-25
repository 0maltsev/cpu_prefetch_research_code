#include "cpu_prefetch/qualification/q15_trust_anchor_adapter.hpp"

#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <array>
#include <span>
#include <utility>

namespace cpu_prefetch::qualification {
namespace {

using protocol::ErrorCategory;
using protocol::ValidationError;
using protocol::json::Value;

[[nodiscard]] auto error(ErrorCategory category, std::string path, std::string rule,
                         std::string message) -> ValidationError {
  return {category, std::move(path), std::move(rule), std::move(message)};
}

[[nodiscard]] auto sha256(const std::vector<std::byte>& bytes) -> std::string {
  return workload::sha256(std::span<const std::byte>(bytes)).hex();
}

struct SnapshotExpectation final {
  int descriptor;
  std::size_t maximum_bytes;
  std::string_view path;
};

[[nodiscard]] auto validate_snapshot(const Q15RDescriptorSnapshot& snapshot,
                                     const SnapshotExpectation& expected)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  if (snapshot.descriptor != expected.descriptor) {
    errors.push_back(error(ErrorCategory::reference_mismatch,
                           std::string(expected.path), "Q15R-ADAPTER-FD",
                           "descriptor differs from the fixed inherited-FD contract"));
  }
  if (snapshot.bytes.empty() || snapshot.bytes.size() > expected.maximum_bytes) {
    errors.push_back(error(
        ErrorCategory::out_of_range, std::string(expected.path), "Q15R-ADAPTER-BOUND",
        "descriptor snapshot must be nonempty and within its bound"));
  }
  if (!snapshot.regular_file || !snapshot.read_only || !snapshot.offset_at_start ||
      !snapshot.reached_eof) {
    errors.push_back(
        error(ErrorCategory::missing_evidence, std::string(expected.path),
              "Q15R-ADAPTER-SNAPSHOT",
              "snapshot must be a complete read-only regular file from offset zero"));
  }
  return errors;
}

void append(std::vector<ValidationError>& destination,
            std::vector<ValidationError> source) {
  destination.insert(destination.end(), std::make_move_iterator(source.begin()),
                     std::make_move_iterator(source.end()));
}

} // namespace

auto canonical_q15_r_verification_receipt(
    const Q15RSignatureVerificationReceipt& receipt) -> protocol::Result<std::string> {
  Value::Object root{
      {"allowed_signers_artifact_id", Value(receipt.allowed_signers_artifact_id)},
      {"allowed_signers_path", Value(receipt.allowed_signers_path)},
      {"allowed_signers_sha256", Value(receipt.allowed_signers_sha256)},
      {"artifact_id", Value(receipt.artifact_id)},
      {"authorization_core_sha256", Value(receipt.authorization_core_sha256)},
      {"authorization_principal", Value(receipt.authorization_principal)},
      {"detached_signature_artifact_id", Value(receipt.detached_signature_artifact_id)},
      {"detached_signature_sha256", Value(receipt.detached_signature_sha256)},
      {"private_key_present_on_stand", Value(receipt.private_key_present_on_stand)},
      {"schema_version", Value(receipt.schema_version)},
      {"signature_namespace", Value(receipt.signature_namespace)},
      {"signature_scheme", Value(receipt.signature_scheme)},
      {"signer_key_fingerprint", Value(receipt.signer_key_fingerprint)},
      {"verification_executable", Value(receipt.verification_executable)},
      {"verification_exit_code",
       Value(protocol::json::Number{protocol::json::Number::Kind::signed_integer,
                                    std::to_string(receipt.verification_exit_code),
                                    receipt.verification_exit_code})},
      {"verification_succeeded", Value(receipt.verification_succeeded)},
      {"verifier_principal_id", Value(receipt.verifier_principal_id)},
  };
  return protocol::json::canonicalize(Value(std::move(root)));
}

auto load_q15_r_trust_anchor(const Q15RControllerAdmission& admission,
                             const Q15RTrustAnchorAdapterBindings& bindings,
                             const Q15RSignatureVerificationReceipt& receipt,
                             Q15RInheritedDescriptorReader& reader)
    -> protocol::Result<Q15RControllerTrustAnchor> {
  std::vector<ValidationError> errors;
  const auto read =
      [&](int descriptor, std::size_t maximum_bytes,
          std::string_view path) -> protocol::Result<Q15RDescriptorSnapshot> {
    auto result = reader.read_bounded(descriptor, maximum_bytes);
    if (!result) {
      return result;
    }
    auto snapshot = std::move(result).value();
    auto snapshot_errors =
        validate_snapshot(snapshot, {descriptor, maximum_bytes, path});
    if (!snapshot_errors.empty()) {
      return protocol::Result<Q15RDescriptorSnapshot>::failure(
          std::move(snapshot_errors));
    }
    return protocol::Result<Q15RDescriptorSnapshot>::success(snapshot);
  };

  auto authorization =
      read(kQ15RInheritedDescriptorContract.authorization_core_fd,
           kQ15RInheritedDescriptorContract.authorization_core_maximum_bytes,
           "$/authorization_core_fd");
  if (!authorization) {
    return protocol::Result<Q15RControllerTrustAnchor>::failure(authorization.errors());
  }
  auto signature =
      read(kQ15RInheritedDescriptorContract.detached_signature_fd,
           kQ15RInheritedDescriptorContract.detached_signature_maximum_bytes,
           "$/detached_signature_fd");
  if (!signature) {
    return protocol::Result<Q15RControllerTrustAnchor>::failure(signature.errors());
  }
  auto verification =
      read(kQ15RInheritedDescriptorContract.verification_receipt_fd,
           kQ15RInheritedDescriptorContract.verification_receipt_maximum_bytes,
           "$/verification_receipt_fd");
  if (!verification) {
    return protocol::Result<Q15RControllerTrustAnchor>::failure(verification.errors());
  }

  const auto exact = [&](std::string_view actual, std::string_view expected,
                         std::string path, std::string rule) {
    if (actual != expected) {
      errors.push_back(error(ErrorCategory::reference_mismatch, std::move(path),
                             std::move(rule), "value differs from the fixed binding"));
    }
  };
  exact(sha256(authorization.value().bytes), admission.authorization_core_sha256,
        "$/authorization_core_sha256", "Q15R-ADAPTER-AUTHORIZATION-HASH");
  exact(sha256(signature.value().bytes), admission.detached_signature_sha256,
        "$/detached_signature_sha256", "Q15R-ADAPTER-SIGNATURE-HASH");
  exact(receipt.schema_version, kQ15RVerificationReceiptSchemaVersion,
        "$/receipt/schema_version", "Q15R-ADAPTER-RECEIPT-SCHEMA");
  exact(receipt.artifact_id, admission.signature_verification_artifact_id,
        "$/receipt/artifact_id", "Q15R-ADAPTER-RECEIPT-ID");
  exact(receipt.authorization_core_sha256, admission.authorization_core_sha256,
        "$/receipt/authorization_core_sha256", "Q15R-ADAPTER-RECEIPT-AUTHORIZATION");
  exact(
      receipt.detached_signature_artifact_id, admission.detached_signature_artifact_id,
      "$/receipt/detached_signature_artifact_id", "Q15R-ADAPTER-RECEIPT-SIGNATURE-ID");
  exact(receipt.detached_signature_sha256, admission.detached_signature_sha256,
        "$/receipt/detached_signature_sha256", "Q15R-ADAPTER-RECEIPT-SIGNATURE");
  exact(receipt.allowed_signers_artifact_id, bindings.allowed_signers_artifact_id,
        "$/receipt/allowed_signers_artifact_id", "Q15R-ADAPTER-TRUST-ANCHOR-ID");
  exact(receipt.allowed_signers_sha256, bindings.allowed_signers_sha256,
        "$/receipt/allowed_signers_sha256", "Q15R-ADAPTER-TRUST-ANCHOR-HASH");
  exact(receipt.allowed_signers_path, kQ15RAllowedSignersPath,
        "$/receipt/allowed_signers_path", "Q15R-ADAPTER-TRUST-ANCHOR-PATH");
  exact(receipt.authorization_principal, kQ15RAuthorizationPrincipal,
        "$/receipt/authorization_principal", "Q15R-ADAPTER-PRINCIPAL");
  exact(receipt.signer_key_fingerprint, bindings.signer_key_fingerprint,
        "$/receipt/signer_key_fingerprint", "Q15R-ADAPTER-SIGNER");
  exact(receipt.signature_scheme, kQ15RAuthorizationSignatureScheme,
        "$/receipt/signature_scheme", "Q15R-ADAPTER-SCHEME");
  exact(receipt.signature_namespace, kQ15RAuthorizationSignatureNamespace,
        "$/receipt/signature_namespace", "Q15R-ADAPTER-NAMESPACE");
  exact(receipt.verifier_principal_id, kQ15RAuditorPrincipal,
        "$/receipt/verifier_principal_id", "Q15R-ADAPTER-AUDITOR");
  exact(receipt.verification_executable, "/usr/bin/ssh-keygen",
        "$/receipt/verification_executable", "Q15R-ADAPTER-VERIFIER");
  exact(bindings.source_revision, admission.source_revision, "$/source_revision",
        "Q15R-ADAPTER-SOURCE");
  exact(bindings.controller_binary_sha256, admission.controller_binary_sha256,
        "$/controller_binary_sha256", "Q15R-ADAPTER-BINARY");
  exact(bindings.stand_id, admission.stand_id, "$/stand_id", "Q15R-ADAPTER-STAND");
  exact(bindings.binding_id, admission.binding_id, "$/binding_id",
        "Q15R-ADAPTER-BINDING");

  auto canonical_receipt = canonical_q15_r_verification_receipt(receipt);
  if (!canonical_receipt) {
    append(errors, canonical_receipt.errors());
  } else {
    const auto& bytes = verification.value().bytes;
    const std::string_view observed(reinterpret_cast<const char*>(bytes.data()),
                                    bytes.size());
    exact(observed, canonical_receipt.value(), "$/verification_receipt_fd",
          "Q15R-ADAPTER-RECEIPT-CANONICAL");
    exact(sha256(bytes), admission.signature_verification_sha256,
          "$/signature_verification_sha256", "Q15R-ADAPTER-RECEIPT-HASH");
  }

  for (const auto* hash :
       {&bindings.controller_binary_sha256, &bindings.allowed_signers_sha256,
        &admission.authorization_core_sha256, &admission.detached_signature_sha256,
        &admission.signature_verification_sha256}) {
    if (!protocol::Sha256::parse(*hash, "$/sha256")) {
      errors.push_back(error(ErrorCategory::invalid_hash, "$/sha256",
                             "Q15R-ADAPTER-SHA256",
                             "every adapter binding must be a SHA-256 value"));
    }
  }
  if (bindings.source_dirty || !receipt.verification_succeeded ||
      receipt.verification_exit_code != 0 || receipt.private_key_present_on_stand ||
      bindings.allowed_signers_artifact_id.empty() ||
      bindings.signer_key_fingerprint.empty() ||
      bindings.allowed_signers_artifact_id ==
          admission.detached_signature_artifact_id ||
      bindings.allowed_signers_artifact_id ==
          admission.signature_verification_artifact_id) {
    errors.push_back(
        error(ErrorCategory::missing_evidence, "$/trust_anchor",
              "Q15R-ADAPTER-TRUST-EVIDENCE",
              "clean source, successful independent verification, an "
              "identified trust anchor, "
              "distinct artifacts, and absence of a stand private key are mandatory"));
  }
  if (!errors.empty()) {
    return protocol::Result<Q15RControllerTrustAnchor>::failure(std::move(errors));
  }

  return protocol::Result<Q15RControllerTrustAnchor>::success(
      {bindings.source_revision, bindings.controller_binary_sha256, bindings.stand_id,
       bindings.binding_id, admission.authorization_core_sha256,
       admission.detached_signature_artifact_id, admission.detached_signature_sha256,
       admission.signature_verification_artifact_id,
       admission.signature_verification_sha256, admission.signature_scheme,
       admission.signature_namespace, false, true});
}

} // namespace cpu_prefetch::qualification
