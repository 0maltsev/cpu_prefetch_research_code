#include "cpu_prefetch/runner/runner.hpp"

#include <gtest/gtest.h>

#include <array>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using cpu_prefetch::protocol::Placement;
using cpu_prefetch::protocol::QueuePackage;
using cpu_prefetch::runner::AdmissionTrustAnchor;
using cpu_prefetch::runner::EvidenceReference;
using cpu_prefetch::runner::RunnerAdmission;

constexpr std::string_view kZeroHash =
    "0000000000000000000000000000000000000000000000000000000000000000";

[[nodiscard]] auto complete_admission() -> RunnerAdmission {
  std::vector<EvidenceReference> evidence;
  evidence.reserve(cpu_prefetch::runner::kRequiredEvidenceKinds.size());
  for (const auto kind : cpu_prefetch::runner::kRequiredEvidenceKinds) {
    const auto name = std::string(cpu_prefetch::runner::to_string(kind));
    evidence.push_back({kind, "synthetic-" + name, "synthetic.bin",
                        std::string(kZeroHash), "synthetic-binding", true, true});
  }
  return {
      std::string(cpu_prefetch::runner::kAdmissionSchemaVersion),
      std::string(cpu_prefetch::protocol::kProtocolVersion),
      std::string(cpu_prefetch::runner::kRunnerProfileId),
      std::string(cpu_prefetch::runner::kCpuPairSelectionId),
      std::string(cpu_prefetch::runner::kRelaxMappingId),
      "synthetic-revision",
      std::string(kZeroHash),
      "SYNTHETIC-NOT-A-STAND",
      "synthetic-binding",
      QueuePackage::r0,
      Placement::near,
      cpu_prefetch::runner::kNearWorkerPair,
      {1U, 2U, 3U, 4U, 5U},
      std::move(evidence),
  };
}

[[nodiscard]] auto trust_anchor() -> AdmissionTrustAnchor {
  return {"synthetic-revision", std::string(kZeroHash), "SYNTHETIC-NOT-A-STAND",
          "synthetic-binding", false};
}

[[nodiscard]] auto complete_admission_json() -> std::string {
  std::ostringstream output;
  output << R"({"schema_version":"cpu-prefetch-runner-admission/1",)"
         << R"("protocol_version":"2.0.0-pre.2",)"
         << R"("runner_profile_id":"STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v1",)"
         << R"("cpu_pair_selection_id":"XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1",)"
         << R"("relax_mapping_id":"X86-PAUSE-ONE-PER-RELAX-SITE-v1",)"
         << R"("source_revision":"synthetic-revision",)"
         << R"("binary_sha256":")" << kZeroHash
         << R"(","stand_id":"SYNTHETIC-NOT-A-STAND",)"
         << R"("binding_id":"synthetic-binding","package":"R0",)"
         << R"("placement":"NEAR","producer_cpu":0,"consumer_cpu":1,)"
         << R"("execution_limits":{"controller_start_poll_limit":1,)"
         << R"("worker_start_poll_limit":2,)"
         << R"("producer_due_poll_limit_per_arrival":3,)"
         << R"("consumer_empty_poll_limit_before_finish":4,)"
         << R"("drain_poll_limit":5},"evidence":[)";
  for (std::size_t index = 0U;
       index < cpu_prefetch::runner::kRequiredEvidenceKinds.size(); ++index) {
    if (index != 0U) {
      output << ',';
    }
    const auto kind = cpu_prefetch::runner::to_string(
        cpu_prefetch::runner::kRequiredEvidenceKinds[index]);
    output << R"({"kind":")" << kind << R"(","artifact_id":"artifact-)" << index
           << R"(","path":"synthetic.bin","sha256":")" << kZeroHash
           << R"(","binding_id":"synthetic-binding",)"
           << R"("immutable":true,"eligible":true})";
  }
  output << "]}";
  return output.str();
}

[[nodiscard]] auto
has_rule(const std::vector<cpu_prefetch::protocol::ValidationError>& errors,
         std::string_view rule) -> bool {
  for (const auto& error : errors) {
    if (error.rule_id == rule) {
      return true;
    }
  }
  return false;
}

[[nodiscard]] auto test_directory(std::string_view name) -> std::filesystem::path {
  const auto pattern = (std::filesystem::temp_directory_path() /
                        ("cpu-prefetch-runner-" + std::string(name) + "-XXXXXX"))
                           .string();
  std::vector<char> writable_pattern(pattern.begin(), pattern.end());
  writable_pattern.push_back('\0');
  const auto* created = ::mkdtemp(writable_pattern.data());
  if (created == nullptr) {
    throw std::runtime_error("cannot create isolated runner test directory");
  }
  return created;
}

struct DispatchRecorder final {
  std::vector<QueuePackage>* observed;

  template <QueuePackage Package> void operator()() { observed->push_back(Package); }
};

TEST(RunnerQ13Policy, ExactNearFarPairsAndOneStatelessPauseMappingAreFrozen) {
  EXPECT_EQ(cpu_prefetch::runner::selected_worker_pair(Placement::near),
            cpu_prefetch::runner::kNearWorkerPair);
  EXPECT_EQ(cpu_prefetch::runner::selected_worker_pair(Placement::far),
            cpu_prefetch::runner::kFarWorkerPair);
  EXPECT_EQ(cpu_prefetch::runner::kNearWorkerPair,
            (cpu_prefetch::runner::WorkerPair{0U, 1U}));
  EXPECT_EQ(cpu_prefetch::runner::kFarWorkerPair,
            (cpu_prefetch::runner::WorkerPair{0U, 26U}));
  EXPECT_EQ(cpu_prefetch::runner::kRelaxMappingId, "X86-PAUSE-ONE-PER-RELAX-SITE-v1");
  cpu_prefetch::runner::X86PauseRelax{}.relax();
}

TEST(RunnerAdmission, CompleteSyntheticFixturePassesFieldValidation) {
  const auto admission = complete_admission();
  EXPECT_TRUE(cpu_prefetch::runner::validate_admission_fields(admission, trust_anchor())
                  .empty());
}

TEST(RunnerAdmission, EveryEvidenceKindIsMandatoryAndUnique) {
  for (std::size_t index = 0U;
       index < cpu_prefetch::runner::kRequiredEvidenceKinds.size(); ++index) {
    auto admission = complete_admission();
    admission.evidence.erase(admission.evidence.begin() +
                             static_cast<std::ptrdiff_t>(index));
    const auto errors =
        cpu_prefetch::runner::validate_admission_fields(admission, trust_anchor());
    EXPECT_TRUE(has_rule(errors, "RUN-EVIDENCE-COMPLETE")) << index;
  }

  auto duplicate = complete_admission();
  duplicate.evidence.back().kind = duplicate.evidence.front().kind;
  const auto errors =
      cpu_prefetch::runner::validate_admission_fields(duplicate, trust_anchor());
  EXPECT_TRUE(has_rule(errors, "RUN-EVIDENCE-UNIQUE"));
}

TEST(RunnerAdmission, MissingStaleMutableOrIneligibleInputsFailClosed) {
  auto admission = complete_admission();
  admission.execution_limits.drain_poll_limit = 0U;
  admission.evidence[0].binding_id = "stale-binding";
  admission.evidence[1].immutable = false;
  admission.evidence[2].eligible = false;
  auto anchor = trust_anchor();
  anchor.source_dirty = true;
  const auto errors =
      cpu_prefetch::runner::validate_admission_fields(admission, anchor);
  EXPECT_TRUE(has_rule(errors, "RUN-LIMITS"));
  EXPECT_TRUE(has_rule(errors, "RUN-EVIDENCE-STALE"));
  EXPECT_TRUE(has_rule(errors, "RUN-EVIDENCE-IMMUTABLE"));
  EXPECT_TRUE(has_rule(errors, "RUN-EVIDENCE-ELIGIBLE"));
  EXPECT_TRUE(has_rule(errors, "RUN-DIRTY-SOURCE"));
}

TEST(RunnerAdmission, EmptyIdentityAndMalformedBinaryHashFailClosed) {
  auto admission = complete_admission();
  auto anchor = trust_anchor();
  admission.source_revision.clear();
  admission.stand_id.clear();
  admission.binding_id.clear();
  admission.binary_sha256 = "not-a-sha256";
  anchor.source_revision.clear();
  anchor.stand_id.clear();
  anchor.binding_id.clear();
  anchor.binary_sha256 = admission.binary_sha256;
  for (auto& reference : admission.evidence) {
    reference.binding_id.clear();
  }
  const auto errors =
      cpu_prefetch::runner::validate_admission_fields(admission, anchor);
  EXPECT_TRUE(has_rule(errors, "RUN-SOURCE-EMPTY"));
  EXPECT_TRUE(has_rule(errors, "RUN-STAND-EMPTY"));
  EXPECT_TRUE(has_rule(errors, "RUN-BINDING-EMPTY"));
  EXPECT_TRUE(has_rule(errors, "RUN-BINARY-SHA256"));
}

TEST(RunnerAdmission, PairProfilePackageAndBuildDriftFailClosed) {
  auto admission = complete_admission();
  admission.workers = {1U, 0U};
  admission.relax_mapping_id = "UNACCEPTED";
  admission.package = QueuePackage::nblfq_mpsc;
  auto anchor = trust_anchor();
  anchor.binary_sha256 = std::string(64U, '1');
  const auto errors =
      cpu_prefetch::runner::validate_admission_fields(admission, anchor);
  EXPECT_TRUE(has_rule(errors, "RUN-CPU-PAIR"));
  EXPECT_TRUE(has_rule(errors, "RUN-RELAX"));
  EXPECT_TRUE(has_rule(errors, "RUN-PACKAGE"));
  EXPECT_TRUE(has_rule(errors, "RUN-BINARY"));
}

TEST(RunnerAdmission, StaticDispatcherInstantiatesExactlyTheSelectedPackage) {
  const auto directory = test_directory("dispatch-test");
  const auto artifact = directory / "artifact.bin";
  {
    std::ofstream output(artifact, std::ios::binary | std::ios::trunc);
    output << "synthetic-dispatch-evidence";
  }
  const auto digest = cpu_prefetch::runner::sha256_file(artifact);
  ASSERT_TRUE(digest.has_value());
  constexpr std::array packages{QueuePackage::r0, QueuePackage::r1, QueuePackage::r2,
                                QueuePackage::l0, QueuePackage::l1};
  for (const auto package : packages) {
    auto admission = complete_admission();
    admission.package = package;
    for (auto& reference : admission.evidence) {
      reference.path = artifact.filename();
      reference.sha256 = digest.value();
    }
    const auto ticket =
        cpu_prefetch::runner::admit_runner(admission, trust_anchor(), directory);
    ASSERT_TRUE(ticket.has_value());
    std::vector<QueuePackage> observed;
    DispatchRecorder recorder{&observed};
    EXPECT_EQ(cpu_prefetch::runner::dispatch_static_package(ticket.value(), recorder),
              cpu_prefetch::runner::DispatchStatus::dispatched);
    ASSERT_EQ(observed.size(), 1U);
    EXPECT_EQ(observed.front(), package);
  }
  std::filesystem::remove_all(directory);
}

TEST(RunnerAdmission, FileHashVerificationRejectsMismatchAndSymlink) {
  const auto directory = test_directory("model-test");
  const auto artifact = directory / "artifact.bin";
  {
    std::ofstream output(artifact, std::ios::binary | std::ios::trunc);
    output << "synthetic-runner-evidence";
  }
  const auto digest = cpu_prefetch::runner::sha256_file(artifact);
  ASSERT_TRUE(digest.has_value());

  auto admission = complete_admission();
  for (auto& reference : admission.evidence) {
    reference.path = artifact.filename();
    reference.sha256 = digest.value();
  }
  EXPECT_TRUE(
      cpu_prefetch::runner::verify_evidence_files(admission, directory).empty());

  admission.evidence[0].sha256 = std::string(kZeroHash);
  EXPECT_TRUE(
      has_rule(cpu_prefetch::runner::verify_evidence_files(admission, directory),
               "RUN-EVIDENCE-HASH"));

  admission.evidence[0].sha256 = digest.value();
  const auto symlink = directory / "artifact-link.bin";
  std::filesystem::create_symlink(artifact.filename(), symlink);
  admission.evidence[0].path = symlink.filename();
  EXPECT_TRUE(
      has_rule(cpu_prefetch::runner::verify_evidence_files(admission, directory),
               "RUN-EVIDENCE-FILE"));
  std::filesystem::remove_all(directory);
}

TEST(RunnerAdmission, StrictJsonRejectsUnknownFieldsAndUnknownEvidence) {
  const auto complete = cpu_prefetch::runner::load_admission(complete_admission_json());
  ASSERT_TRUE(complete.has_value());
  EXPECT_TRUE(
      cpu_prefetch::runner::validate_admission_fields(complete.value(), trust_anchor())
          .empty());

  const auto unknown_root = cpu_prefetch::runner::load_admission(R"({"extra":1})");
  ASSERT_FALSE(unknown_root.has_value());
  EXPECT_TRUE(has_rule(unknown_root.errors(), "RUN-UNKNOWN"));

  const auto unknown_kind =
      cpu_prefetch::runner::parse_evidence_kind("UNREGISTERED", "$/evidence/0/kind");
  ASSERT_FALSE(unknown_kind.has_value());
  EXPECT_TRUE(has_rule(unknown_kind.errors(), "RUN-EVIDENCE-KIND"));
}

} // namespace
