#include "cpu_prefetch/qualification/q15_controller.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace {

using cpu_prefetch::protocol::ErrorCategory;
using cpu_prefetch::protocol::Result;
using cpu_prefetch::qualification::Q15RControllerAdmission;
using cpu_prefetch::qualification::Q15RControllerOperations;
using cpu_prefetch::qualification::Q15RControllerState;
using cpu_prefetch::qualification::Q15RControllerStep;
using cpu_prefetch::qualification::Q15RControllerTicket;
using cpu_prefetch::qualification::Q15RControllerTrustAnchor;
using cpu_prefetch::qualification::Q15RStepEvidence;

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

[[nodiscard]] auto admission() -> Q15RControllerAdmission {
  using namespace cpu_prefetch::qualification;
  return {
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
}

[[nodiscard]] auto trust() -> Q15RControllerTrustAnchor {
  return {
      "source",
      std::string(kHash0),
      "XEON-CPU-FETCH",
      "binding",
      std::string(kHash1),
      "signature",
      std::string(kHash0),
      "signature-verification",
      std::string(kHash1),
      std::string(cpu_prefetch::qualification::kQ15RAuthorizationSignatureScheme),
      std::string(cpu_prefetch::qualification::kQ15RAuthorizationSignatureNamespace),
      false,
      true};
}

class FakeOperations final : public Q15RControllerOperations {
public:
  [[nodiscard]] auto run_step(Q15RControllerStep step,
                              const Q15RControllerTicket& ticket)
      -> Result<Q15RStepEvidence> override {
    observed.push_back(step);
    observed_binding = std::string(ticket.binding_id());
    if (fail_at && step == *fail_at) {
      return Result<Q15RStepEvidence>::failure(
          {ErrorCategory::missing_evidence, "$/fake", "Q15R-FAKE-FAIL",
           "injected controller operation failure"});
    }
    auto artifact_id =
        "artifact-" + std::string(cpu_prefetch::qualification::to_string(step));
    if (duplicate_artifact && !observed.empty()) {
      artifact_id = "duplicate";
    }
    return Result<Q15RStepEvidence>::success(
        {wrong_step ? Q15RControllerStep::collect_clock : step, std::move(artifact_id),
         malformed_hash ? "bad" : std::string(kHash0), bytes_per_step,
         maximum_frame_payload_bytes, active_collection_wall_seconds,
         same_buffer_session_wall_seconds, cpu_seconds, complete});
  }

  std::vector<Q15RControllerStep> observed;
  std::string observed_binding;
  std::optional<Q15RControllerStep> fail_at;
  std::uint64_t bytes_per_step{1U};
  std::uint64_t maximum_frame_payload_bytes{1U};
  std::uint64_t active_collection_wall_seconds{1U};
  std::uint64_t same_buffer_session_wall_seconds{1U};
  std::uint64_t cpu_seconds{1U};
  bool duplicate_artifact{false};
  bool malformed_hash{false};
  bool complete{true};
  bool wrong_step{false};
};

[[nodiscard]] auto ticket() -> Q15RControllerTicket {
  auto admitted =
      cpu_prefetch::qualification::admit_q15_r_controller(admission(), trust());
  EXPECT_TRUE(admitted.has_value());
  return std::move(admitted).value();
}

TEST(Q15RController, AdmissionBindsEveryAcceptedPolicyAndIndependentSignature) {
  const auto accepted =
      cpu_prefetch::qualification::admit_q15_r_controller(admission(), trust());
  ASSERT_TRUE(accepted.has_value());
  EXPECT_EQ(accepted.value().binding_id(), "binding");
  EXPECT_EQ(accepted.value().authorization_core_sha256(), kHash1);

  auto rejected_trust = trust();
  rejected_trust.independent_signature_verified = false;
  auto rejected =
      cpu_prefetch::qualification::admit_q15_r_controller(admission(), rejected_trust);
  ASSERT_FALSE(rejected.has_value());
  EXPECT_TRUE(std::ranges::any_of(rejected.errors(), [](const auto& error) {
    return error.rule_id == "Q15R-SIGNATURE-NOT-VERIFIED";
  }));

  for (auto mutate : {
           +[](Q15RControllerTrustAnchor& anchor) {
             anchor.authorization_core_sha256 = std::string(kHash0);
           },
           +[](Q15RControllerTrustAnchor& anchor) {
             anchor.detached_signature_artifact_id = "other-signature";
           },
           +[](Q15RControllerTrustAnchor& anchor) {
             anchor.detached_signature_sha256 = std::string(kHash1);
           },
           +[](Q15RControllerTrustAnchor& anchor) {
             anchor.signature_namespace = "other-namespace";
           },
       }) {
    auto mismatched = trust();
    mutate(mismatched);
    EXPECT_FALSE(
        cpu_prefetch::qualification::admit_q15_r_controller(admission(), mismatched)
            .has_value());
  }
}

TEST(Q15RController, AdmissionRejectsGraphRoleLimitCustodyScopeAndDirtyDrift) {
  const auto expect_rejected = [](const Q15RControllerAdmission& candidate,
                                  const Q15RControllerTrustAnchor& anchor = trust()) {
    EXPECT_FALSE(cpu_prefetch::qualification::admit_q15_r_controller(candidate, anchor)
                     .has_value());
  };

  auto graph = admission();
  std::swap(graph.command_graph[0], graph.command_graph[1]);
  expect_rejected(graph);
  auto role = admission();
  role.authorities.auditor_id = role.authorities.controller_id;
  expect_rejected(role);
  auto limit = admission();
  limit.limits.external_start_watchdog_seconds = 0U;
  expect_rejected(limit);
  auto custody = admission();
  custody.custody.secondary_domain_id = custody.custody.primary_domain_id;
  expect_rejected(custody);
  auto scope = admission();
  scope.all_prohibitions_disabled = false;
  expect_rejected(scope);
  auto anchor = trust();
  anchor.source_dirty = true;
  expect_rejected(admission(), anchor);
}

TEST(Q15RController, ExactGraphExecutesOnceInOrderAndEndsWaitingForQ15W) {
  FakeOperations operations;
  const auto report =
      cpu_prefetch::qualification::execute_q15_r_controller(ticket(), operations);
  EXPECT_EQ(report.state, Q15RControllerState::q15_r_sealed_waiting_for_q15_w);
  EXPECT_TRUE(std::ranges::equal(operations.observed,
                                 cpu_prefetch::qualification::kQ15RControllerGraph));
  EXPECT_EQ(operations.observed_binding, "binding");
  EXPECT_EQ(report.evidence.size(),
            cpu_prefetch::qualification::kQ15RControllerGraph.size());
  EXPECT_EQ(report.total_output_bytes,
            cpu_prefetch::qualification::kQ15RControllerGraph.size());
  EXPECT_FALSE(report.failed_step.has_value());
  EXPECT_TRUE(report.errors.empty());
}

TEST(Q15RController, EveryStepFailureStopsWithoutRetryAndRetainsPriorEvidence) {
  for (std::size_t index = 0U;
       index < cpu_prefetch::qualification::kQ15RControllerGraph.size(); ++index) {
    FakeOperations operations;
    operations.fail_at = cpu_prefetch::qualification::kQ15RControllerGraph[index];
    const auto report =
        cpu_prefetch::qualification::execute_q15_r_controller(ticket(), operations);
    EXPECT_EQ(report.state, Q15RControllerState::failed_partial_retained);
    const auto expected_step = cpu_prefetch::qualification::kQ15RControllerGraph[index];
    EXPECT_EQ(report.failed_step, std::optional{expected_step});
    EXPECT_EQ(operations.observed.size(), index + 1U);
    EXPECT_EQ(report.evidence.size(), index);
    EXPECT_EQ(std::ranges::count(operations.observed, expected_step), 1);
  }
}

TEST(Q15RController, MalformedDuplicateIncompleteAndWrongStepEvidenceFailClosed) {
  using Configure = void (*)(FakeOperations&);
  constexpr std::array<Configure, 3U> configurations{
      [](FakeOperations& operations) { operations.malformed_hash = true; },
      [](FakeOperations& operations) { operations.complete = false; },
      [](FakeOperations& operations) { operations.wrong_step = true; },
  };
  for (const auto configure : configurations) {
    FakeOperations operations;
    configure(operations);
    const auto report =
        cpu_prefetch::qualification::execute_q15_r_controller(ticket(), operations);
    EXPECT_EQ(report.state, Q15RControllerState::failed_partial_retained);
    EXPECT_EQ(operations.observed.size(), 1U);
  }

  FakeOperations duplicate;
  duplicate.duplicate_artifact = true;
  const auto report =
      cpu_prefetch::qualification::execute_q15_r_controller(ticket(), duplicate);
  EXPECT_EQ(report.state, Q15RControllerState::failed_partial_retained);
  EXPECT_EQ(duplicate.observed.size(), 2U);
  EXPECT_EQ(report.evidence.size(), 1U);
}

TEST(Q15RController, OutputLimitFailsAfterRetainingExactBoundedPrefix) {
  FakeOperations operations;
  operations.bytes_per_step = 200'000'000U;
  const auto report =
      cpu_prefetch::qualification::execute_q15_r_controller(ticket(), operations);
  EXPECT_EQ(report.state, Q15RControllerState::failed_partial_retained);
  ASSERT_TRUE(report.failed_step.has_value());
  EXPECT_EQ(report.evidence.size(), 11U);
  EXPECT_EQ(operations.observed.size(), 11U);
  EXPECT_GT(report.total_output_bytes,
            cpu_prefetch::qualification::kQ15RControllerLimits.max_output_bytes);
}

TEST(Q15RController, EveryDirectResourceLimitFailsClosedBeforePromotion) {
  using Configure = void (*)(FakeOperations&);
  constexpr std::array<Configure, 4U> configurations{
      [](FakeOperations& operations) {
        operations.maximum_frame_payload_bytes =
            cpu_prefetch::qualification::kQ15RControllerLimits
                .frame_maximum_payload_bytes +
            1U;
      },
      [](FakeOperations& operations) {
        operations.active_collection_wall_seconds =
            cpu_prefetch::qualification::kQ15RControllerLimits
                .max_active_collection_wall_seconds +
            1U;
      },
      [](FakeOperations& operations) {
        operations.same_buffer_session_wall_seconds =
            cpu_prefetch::qualification::kQ15RControllerLimits
                .max_same_buffer_session_wall_seconds +
            1U;
      },
      [](FakeOperations& operations) {
        operations.cpu_seconds =
            cpu_prefetch::qualification::kQ15RControllerLimits.max_cpu_seconds + 1U;
      },
  };
  for (const auto configure : configurations) {
    FakeOperations operations;
    configure(operations);
    const auto report =
        cpu_prefetch::qualification::execute_q15_r_controller(ticket(), operations);
    EXPECT_EQ(report.state, Q15RControllerState::failed_partial_retained);
    EXPECT_EQ(operations.observed.size(), 1U);
    EXPECT_TRUE(report.evidence.empty());
    ASSERT_EQ(report.errors.size(), 1U);
    EXPECT_EQ(report.errors.front().rule_id, "Q15R-RESOURCE-LIMIT");
  }
}

} // namespace
