#include "cpu_prefetch/qualification/q15_controller.hpp"

#include <string>
#include <vector>

namespace {

using cpu_prefetch::protocol::Result;
using namespace cpu_prefetch::qualification;

constexpr std::string_view kHash0 =
    "0000000000000000000000000000000000000000000000000000000000000000";
constexpr std::string_view kHash1 =
    "1111111111111111111111111111111111111111111111111111111111111111";

[[nodiscard]] auto stop_conditions() -> std::vector<std::string> {
  return {
      "FIRST_AUTHORIZATION_OR_RELEASE_BINDING_MISMATCH",
      "FIRST_ROLE_OR_NEGATIVE_ACCESS_MISMATCH",
      "FIRST_PEER_CREDENTIAL_OR_TRANSPORT_MISMATCH",
      "FIRST_CLOCK_AFFINITY_NUMA_RESIDENCY_FAULT_PMU_OR_MSR_FAILURE",
      "FIRST_INTEGRITY_COUNT_CANONICALIZATION_HASH_OR_CUSTODY_FAILURE",
      "FIRST_LIMIT_EXPIRY_OR_DISCONNECT",
      "PRESERVE_PARTIAL_EVIDENCE_AND_NEVER_RETRY",
  };
}

class CodegenOperations final : public Q15RControllerOperations {
public:
  [[nodiscard]] auto run_step(Q15RControllerStep step, const Q15RControllerTicket&)
      -> Result<Q15RStepEvidence> override {
    ++calls;
    return Result<Q15RStepEvidence>::success({step, "artifact-" + std::to_string(calls),
                                              std::string(kHash0), 1U, 1U, 1U, 1U, 1U,
                                              true});
  }

  std::size_t calls{0U};
};

[[nodiscard]] auto make_ticket()
    -> cpu_prefetch::protocol::Result<Q15RControllerTicket> {
  const Q15RControllerAdmission admission{
      std::string(kQ15RAuthorizationSchemaVersion),
      std::string(cpu_prefetch::protocol::kProtocolVersion),
      std::string(kQ15RControllerProfileId),
      "Q15_R_READ_ONLY",
      "AUTHORIZED",
      "source",
      std::string(kHash0),
      "XEON-CPU-FETCH",
      "binding",
      std::string(kHash1),
      "signature",
      std::string(kHash0),
      "signature-verification",
      std::string(kHash1),
      std::string(kQ15RAuthorizationSignatureScheme),
      std::string(kQ15RAuthorizationSignatureNamespace),
      kQ15RControllerLimits,
      {"cpu-prefetch-q15-operator", "cpu-prefetch-q15-controller",
       "cpu-prefetch-q15-custodian", "cpu-prefetch-q15-auditor"},
      {"XEON-CPU-FETCH-MD3-Q15-CUSTODY", "DEVELOPMENT-REPOSITORY-Q15-CUSTODY",
       "/var/lib/cpu-prefetch/q15-r", "Q15-PRIMARY-APPEND-ONLY-SEAL-THEN-TRANSFER-v1",
       "Q15-HASHED-SEALED-TRANSFER-WITH-RECEIPT-v1",
       "Q15-RETAIN-PARTIAL-NEVER-PROMOTE-v1", "Q15-NO-OVERWRITE-NEW-ARTIFACT-ID-v1"},
      {kQ15RControllerGraph.begin(), kQ15RControllerGraph.end()},
      stop_conditions(),
      true,
  };
  const Q15RControllerTrustAnchor trust{
      "source",
      std::string(kHash0),
      "XEON-CPU-FETCH",
      "binding",
      std::string(kHash1),
      "signature",
      std::string(kHash0),
      "signature-verification",
      std::string(kHash1),
      std::string(kQ15RAuthorizationSignatureScheme),
      std::string(kQ15RAuthorizationSignatureNamespace),
      false,
      true};
  return admit_q15_r_controller(admission, trust);
}

} // namespace

int main() {
  auto ticket = make_ticket();
  if (!ticket) {
    return 2;
  }
  CodegenOperations operations;
  const auto report = execute_q15_r_controller(ticket.value(), operations);
  return report.state == Q15RControllerState::q15_r_sealed_waiting_for_q15_w &&
                 operations.calls == kQ15RControllerGraph.size()
             ? 0
             : 1;
}
