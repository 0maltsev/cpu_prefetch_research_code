#ifndef CPU_PREFETCH_QUALIFICATION_Q15_TRUST_ANCHOR_ADAPTER_HPP
#define CPU_PREFETCH_QUALIFICATION_Q15_TRUST_ANCHOR_ADAPTER_HPP

#include "cpu_prefetch/qualification/q15_controller.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace cpu_prefetch::qualification {

inline constexpr std::string_view kQ15RTrustAnchorAdapterProfileId =
    "Q15-R-TRUST-ANCHOR-ADAPTER-v1";
inline constexpr std::string_view kQ15RVerificationReceiptSchemaVersion =
    "cpu-prefetch-q15-r-signature-verification-receipt/1";
inline constexpr std::string_view kQ15RAuthorizationPrincipal =
    "cpu-prefetch-q15-authorization";
inline constexpr std::string_view kQ15RAuditorPrincipal = "cpu-prefetch-q15-auditor";
inline constexpr std::string_view kQ15RAllowedSignersPath =
    "/etc/cpu-prefetch/q15/allowed_signers";

struct Q15RInheritedDescriptorContract final {
  int authorization_core_fd;
  int detached_signature_fd;
  int verification_receipt_fd;
  std::size_t authorization_core_maximum_bytes;
  std::size_t detached_signature_maximum_bytes;
  std::size_t verification_receipt_maximum_bytes;

  auto operator==(const Q15RInheritedDescriptorContract&) const -> bool = default;
};

inline constexpr Q15RInheritedDescriptorContract kQ15RInheritedDescriptorContract{
    3, 4, 5, 1'048'576U, 131'072U, 131'072U};

struct Q15RDescriptorSnapshot final {
  int descriptor;
  std::vector<std::byte> bytes;
  bool regular_file;
  bool read_only;
  bool offset_at_start;
  bool reached_eof;
};

class Q15RInheritedDescriptorReader {
public:
  virtual ~Q15RInheritedDescriptorReader() = default;

  // One logical, bounded snapshot request is made for each fixed descriptor.
  // The adapter has no path lookup, selector, fallback, or retry interface.
  [[nodiscard]] virtual auto read_bounded(int descriptor, std::size_t maximum_bytes)
      -> protocol::Result<Q15RDescriptorSnapshot> = 0;
};

struct Q15RSignatureVerificationReceipt final {
  std::string schema_version;
  std::string artifact_id;
  std::string authorization_core_sha256;
  std::string detached_signature_artifact_id;
  std::string detached_signature_sha256;
  std::string allowed_signers_artifact_id;
  std::string allowed_signers_sha256;
  std::string allowed_signers_path;
  std::string authorization_principal;
  std::string signer_key_fingerprint;
  std::string signature_scheme;
  std::string signature_namespace;
  std::string verifier_principal_id;
  std::string verification_executable;
  std::int64_t verification_exit_code;
  bool verification_succeeded;
  bool private_key_present_on_stand;
};

struct Q15RTrustAnchorAdapterBindings final {
  std::string source_revision;
  std::string controller_binary_sha256;
  std::string stand_id;
  std::string binding_id;
  std::string allowed_signers_artifact_id;
  std::string allowed_signers_sha256;
  std::string signer_key_fingerprint;
  bool source_dirty;
};

[[nodiscard]] auto
canonical_q15_r_verification_receipt(const Q15RSignatureVerificationReceipt& receipt)
    -> protocol::Result<std::string>;

// Validates three fixed inherited snapshots and constructs the already-existing
// controller trust anchor. It performs no OS open, shell, SSH, privilege, PMU,
// MSR, affinity, NUMA, qualification, or scientific operation.
[[nodiscard]] auto
load_q15_r_trust_anchor(const Q15RControllerAdmission& admission,
                        const Q15RTrustAnchorAdapterBindings& bindings,
                        const Q15RSignatureVerificationReceipt& receipt,
                        Q15RInheritedDescriptorReader& reader)
    -> protocol::Result<Q15RControllerTrustAnchor>;

} // namespace cpu_prefetch::qualification

#endif // CPU_PREFETCH_QUALIFICATION_Q15_TRUST_ANCHOR_ADAPTER_HPP
