#include "cpu_prefetch/qualification/p4_k_a_controller.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <optional>
#include <ranges>
#include <string>
#include <utility>
#include <vector>

namespace {

using cpu_prefetch::protocol::ErrorCategory;
using cpu_prefetch::protocol::Result;
using cpu_prefetch::qualification::P4KAControllerAdmission;
using cpu_prefetch::qualification::P4KAControllerOperations;
using cpu_prefetch::qualification::P4KAControllerState;
using cpu_prefetch::qualification::P4KAControllerStep;
using cpu_prefetch::qualification::P4KAControllerTicket;
using cpu_prefetch::qualification::P4KAControllerTrustAnchor;
using cpu_prefetch::qualification::P4KAStepEvidence;

constexpr std::string_view kHash0 =
    "0000000000000000000000000000000000000000000000000000000000000000";
constexpr std::string_view kHash1 =
    "1111111111111111111111111111111111111111111111111111111111111111";
constexpr std::string_view kHash2 =
    "2222222222222222222222222222222222222222222222222222222222222222";

[[nodiscard]] auto epoch(std::chrono::year_month_day date) -> std::uint64_t {
  const auto value = std::chrono::sys_days(date).time_since_epoch();
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::seconds>(value).count());
}

[[nodiscard]] auto now() -> std::uint64_t {
  using namespace std::chrono;
  return epoch(year{2026} / August / day{25}) + 60U;
}

[[nodiscard]] auto admission() -> P4KAControllerAdmission {
  using namespace cpu_prefetch::qualification;
  return {
      std::string(kP4KAControllerAdmissionSchemaVersion),
      std::string(cpu_prefetch::protocol::kProtocolVersion),
      std::string(kP4KAControllerProfileId),
      std::string(kP4KAGateId),
      "AUTHORIZED",
      "clean-source",
      std::string(kHash0),
      "p4-k-a-binding",
      "p4-k-a-authorization",
      std::string(kHash1),
      "2026-08-25T00:00:00Z",
      "2026-08-25T00:30:00Z",
      "detached-signature",
      std::string(kHash2),
      "signature-verification",
      std::string(kHash0),
      std::string(kP4KASignatureScheme),
      std::string(kP4KASignatureNamespace),
      std::string(kP4KAAuthorizationPrincipal),
      "SHA256:BOOTSTRAP",
      "bootstrap-trust",
      std::string(kHash1),
      "auditor-review",
      std::string(kHash2),
      "offline-environment",
      std::string(kHash0),
      "toolchain",
      std::string(kHash1),
      "custody",
      std::string(kHash2),
      "p4-k-a-public-export-transaction",
      "/owner-offline/public/p4-k-a-transaction",
      "/usr/bin/ssh-keygen",
      {"/usr/bin/ssh-keygen", "-t", "ed25519"},
      "/usr/bin/ssh-keygen",
      {"/usr/bin/ssh-keygen", "-y"},
      {{"LANG", "C"}, {"LC_ALL", "C"}, {"PATH", "/usr/bin"}, {"TZ", "UTC"}},
      P4KASecretInputKind::controlling_tty,
      std::nullopt,
      {600U, 4'096U, 4'096U, 32U},
      {kP4KAControllerGraph.begin(), kP4KAControllerGraph.end()},
      1U,
      0U,
      true,
      true,
      true,
      false,
      true,
      false,
  };
}

[[nodiscard]] auto trust() -> P4KAControllerTrustAnchor {
  const auto input = admission();
  return {
      input.source_revision,
      input.controller_binary_sha256,
      input.binding_id,
      input.authorization_core_sha256,
      input.detached_signature_artifact_id,
      input.detached_signature_sha256,
      input.signature_verification_artifact_id,
      input.signature_verification_sha256,
      input.bootstrap_signer_fingerprint,
      input.bootstrap_trust_artifact_id,
      input.bootstrap_trust_sha256,
      input.auditor_review_artifact_id,
      input.auditor_review_sha256,
      input.offline_environment_sha256,
      input.toolchain_sha256,
      input.custody_sha256,
      input.public_export_transaction_id,
      input.public_export_root,
      input.issued_at_utc,
      input.expires_at_utc,
      false,
      true,
      true,
      true,
      true,
      true,
  };
}

class FakeOperations final : public P4KAControllerOperations {
public:
  [[nodiscard]] auto run_step(P4KAControllerStep step,
                              const P4KAControllerTicket& ticket)
      -> Result<P4KAStepEvidence> override {
    observed.push_back(step);
    observed_binding = std::string(ticket.binding_id());
    if (fail_at && *fail_at == step) {
      return Result<P4KAStepEvidence>::failure({ErrorCategory::missing_evidence,
                                                "$/fake", "P4KA-FAKE-FAIL",
                                                "injected failure"});
    }
    std::string artifact_id =
        duplicate_artifact ? "duplicate" : "artifact-" + std::string(to_string(step));
    return Result<P4KAStepEvidence>::success(
        {wrong_step ? P4KAControllerStep::stop_for_separate_p4_k_r : step,
         std::move(artifact_id), malformed_hash ? "bad" : std::string(kHash0),
         stdout_bytes, stderr_bytes, public_artifact_count, wall_seconds,
         observed_at_epoch_seconds, complete, private_material_disclosed,
         forbidden_mutation_performed});
  }

  std::vector<P4KAControllerStep> observed;
  std::string observed_binding;
  std::optional<P4KAControllerStep> fail_at;
  std::uint64_t stdout_bytes{1U};
  std::uint64_t stderr_bytes{1U};
  std::uint64_t public_artifact_count{1U};
  std::uint64_t wall_seconds{1U};
  std::uint64_t observed_at_epoch_seconds{now()};
  bool duplicate_artifact{false};
  bool malformed_hash{false};
  bool complete{true};
  bool private_material_disclosed{false};
  bool forbidden_mutation_performed{false};
  bool wrong_step{false};
};

[[nodiscard]] auto ticket() -> P4KAControllerTicket {
  auto result =
      cpu_prefetch::qualification::admit_p4_k_a_controller(admission(), trust(), now());
  EXPECT_TRUE(result.has_value());
  return std::move(result).value();
}

TEST(P4KAController, CompleteExplicitAdmissionIsRequiredAndHashBound) {
  using cpu_prefetch::qualification::admit_p4_k_a_controller;
  auto result = admit_p4_k_a_controller(admission(), trust(), now());
  ASSERT_TRUE(result.has_value());
  EXPECT_EQ(result.value().binding_id(), "p4-k-a-binding");
  EXPECT_EQ(result.value().authorization_core_sha256(), kHash1);

  auto missing_root = trust();
  missing_root.bootstrap_signature_verified = false;
  EXPECT_FALSE(admit_p4_k_a_controller(admission(), missing_root, now()).has_value());
  auto dirty = trust();
  dirty.source_dirty = true;
  EXPECT_FALSE(admit_p4_k_a_controller(admission(), dirty, now()).has_value());
  auto mismatch = trust();
  mismatch.toolchain_sha256 = std::string(kHash0);
  EXPECT_FALSE(admit_p4_k_a_controller(admission(), mismatch, now()).has_value());
}

TEST(P4KAController, UnsafeProcessSecretAndActionContractsFailClosed) {
  using cpu_prefetch::qualification::admit_p4_k_a_controller;
  const auto rejected = [&](const P4KAControllerAdmission& candidate) {
    EXPECT_FALSE(admit_p4_k_a_controller(candidate, trust(), now()).has_value());
  };

  auto shell = admission();
  shell.key_generation_tool_path = "/bin/sh";
  shell.key_generation_argv.front() = "/bin/sh";
  rejected(shell);
  auto secret_environment = admission();
  secret_environment.fixed_environment.push_back({"PASSPHRASE", "secret"});
  rejected(secret_environment);
  auto descriptor = admission();
  descriptor.secret_input_kind =
      cpu_prefetch::qualification::P4KASecretInputKind::dedicated_descriptor;
  descriptor.secret_input_descriptor = 2;
  rejected(descriptor);
  auto retry = admission();
  retry.retry_count = 1U;
  rejected(retry);
  auto cleanup = admission();
  cleanup.overwrite_repair_cleanup_allowed = true;
  rejected(cleanup);
  auto continuation = admission();
  continuation.automatic_continuation_allowed = true;
  rejected(continuation);
  auto reordered = admission();
  std::swap(reordered.command_graph[0], reordered.command_graph[1]);
  rejected(reordered);
}

TEST(P4KAController, ExactGraphRunsOnceAndStopsForSeparateReview) {
  FakeOperations operations;
  const auto report =
      cpu_prefetch::qualification::execute_p4_k_a_controller(ticket(), operations);
  EXPECT_EQ(report.state,
            P4KAControllerState::public_evidence_sealed_waiting_for_p4_k_r);
  EXPECT_TRUE(std::ranges::equal(operations.observed,
                                 cpu_prefetch::qualification::kP4KAControllerGraph));
  EXPECT_EQ(operations.observed_binding, "p4-k-a-binding");
  EXPECT_EQ(report.evidence.size(),
            cpu_prefetch::qualification::kP4KAControllerGraph.size());
  EXPECT_FALSE(report.failed_step.has_value());
  EXPECT_TRUE(report.errors.empty());
}

TEST(P4KAController, EveryStepFailureStopsWithoutRetryAndRetainsPrefix) {
  for (std::size_t index = 0U;
       index < cpu_prefetch::qualification::kP4KAControllerGraph.size(); ++index) {
    FakeOperations operations;
    operations.fail_at = cpu_prefetch::qualification::kP4KAControllerGraph[index];
    const auto report =
        cpu_prefetch::qualification::execute_p4_k_a_controller(ticket(), operations);
    EXPECT_EQ(report.state, P4KAControllerState::failed_partial_retained);
    EXPECT_EQ(report.failed_step, operations.fail_at);
    EXPECT_EQ(operations.observed.size(), index + 1U);
    EXPECT_EQ(report.evidence.size(), index);
    EXPECT_EQ(std::ranges::count(operations.observed, *operations.fail_at), 1);
  }
}

TEST(P4KAController, UnsafeEvidenceLimitsAndExpiryStopBeforeContinuation) {
  using Configure = void (*)(FakeOperations&);
  constexpr std::array<Configure, 7U> configurations{
      [](FakeOperations& value) { value.malformed_hash = true; },
      [](FakeOperations& value) { value.complete = false; },
      [](FakeOperations& value) { value.private_material_disclosed = true; },
      [](FakeOperations& value) { value.forbidden_mutation_performed = true; },
      [](FakeOperations& value) { value.wrong_step = true; },
      [](FakeOperations& value) { value.stdout_bytes = 4'097U; },
      [](FakeOperations& value) { value.observed_at_epoch_seconds = now() + 1'800U; },
  };
  for (const auto configure : configurations) {
    FakeOperations operations;
    configure(operations);
    const auto report =
        cpu_prefetch::qualification::execute_p4_k_a_controller(ticket(), operations);
    EXPECT_EQ(report.state, P4KAControllerState::failed_partial_retained);
    EXPECT_EQ(operations.observed.size(), 1U);
  }

  auto invalid_window = admission();
  invalid_window.expires_at_utc = "2026-08-25T00:30:01Z";
  EXPECT_FALSE(cpu_prefetch::qualification::admit_p4_k_a_controller(invalid_window,
                                                                    trust(), now())
                   .has_value());
  EXPECT_FALSE(cpu_prefetch::qualification::admit_p4_k_a_controller(
                   admission(), trust(), now() + 1'800U)
                   .has_value());
}

} // namespace
