#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/runner/qualification.hpp"
#include "cpu_prefetch/runner/runner.hpp"

#include <gtest/gtest.h>

#include <array>
#include <atomic>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
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
  output << R"({"schema_version":"cpu-prefetch-runner-admission/2",)"
         << R"("protocol_version":"2.0.0-pre.2",)"
         << R"("runner_profile_id":"STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v2",)"
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

class FakeBindingBackend final
    : public cpu_prefetch::runner::CurrentThreadBindingBackend {
public:
  std::uint32_t failed_cpu{std::numeric_limits<std::uint32_t>::max()};

  [[nodiscard]] auto bind_and_verify(std::uint32_t requested_cpu) noexcept
      -> cpu_prefetch::runner::ThreadBindingObservation override {
    const bool passes = requested_cpu != failed_cpu;
    return {requested_cpu, passes ? requested_cpu : requested_cpu + 1U, passes, passes,
            passes};
  }
};

class FakeSoftwarePrefetchCapabilityBackend final
    : public cpu_prefetch::runner::CurrentCpuSoftwarePrefetchCapabilityBackend {
public:
  bool supported{true};

  [[nodiscard]] auto observe() noexcept
      -> cpu_prefetch::runner::SoftwarePrefetchCapabilityObservation override {
    return {cpu_prefetch::runner::kPrfchwExtendedLeaf,
            supported ? cpu_prefetch::runner::kPrfchwEcxMask : 0U, supported};
  }
};

class RunnerStepClock final {
public:
  [[nodiscard]] auto read_ticks() noexcept -> cpu_prefetch::lifecycle::TickRead {
    return {true, ticks_.fetch_add(1U, std::memory_order_relaxed)};
  }

private:
  std::atomic<std::uint64_t> ticks_{1U};
};

class EmptyR0Backend final {
public:
  static constexpr auto package_kind = QueuePackage::r0;

  [[nodiscard]] auto
  try_producer_attempt(cpu_prefetch::lifecycle::ProducerAttempt) noexcept
      -> cpu_prefetch::lifecycle::ProducerAttemptResult {
    return {cpu_prefetch::lifecycle::AttemptStatus::failure,
            cpu_prefetch::queue::EnqueueResult::full};
  }

  [[nodiscard]] auto try_consumer_poll(std::uint64_t) noexcept
      -> cpu_prefetch::lifecycle::ConsumerPollResult {
    return {cpu_prefetch::lifecycle::ConsumerPollStatus::empty};
  }
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
  EXPECT_EQ(cpu_prefetch::runner::kSoftwarePrefetchMappingId,
            "X86-64-PREFETCHW-PREFETCHT0-v1");
  cpu_prefetch::runner::X86PauseRelax{}.relax();
  alignas(64) std::array<char, 64U> target{};
  const cpu_prefetch::runner::X86RetainingPrefetchEmitter emitter;
  emitter.ring_producer_write(target.data());
  emitter.ring_consumer_read(target.data());
  emitter.successor_header(target.data());
}

TEST(RunnerAdmission, CompleteSyntheticFixturePassesFieldValidation) {
  const auto admission = complete_admission();
  EXPECT_TRUE(cpu_prefetch::runner::validate_admission_fields(admission, trust_anchor())
                  .empty());
}

TEST(RunnerPreparation, AffinityReadbackPrecedesOwnerPrivateFirstTouch) {
  const auto run_id =
      cpu_prefetch::protocol::RunId::parse("runner-preparation", "$/run_id");
  ASSERT_TRUE(run_id.has_value());
  cpu_prefetch::storage::ProducerObservationStream producer(run_id.value(), 2U);
  cpu_prefetch::storage::ConsumerObservationStream consumer(run_id.value(), 2U);
  FakeBindingBackend binding;
  FakeSoftwarePrefetchCapabilityBackend capability;
  cpu_prefetch::runner::AffinedObservationPreparation preparation(
      binding, capability, cpu_prefetch::runner::kNearWorkerPair, producer, consumer);

  bool producer_ready = false;
  bool consumer_ready = false;
  std::thread producer_thread([&] { producer_ready = preparation.prepare_producer(); });
  std::thread consumer_thread([&] { consumer_ready = preparation.prepare_consumer(); });
  producer_thread.join();
  consumer_thread.join();

  EXPECT_TRUE(producer_ready);
  EXPECT_TRUE(consumer_ready);
  EXPECT_TRUE(preparation.evidence().passes());
  EXPECT_EQ(producer.snapshot().completeness,
            cpu_prefetch::storage::StreamCompleteness::writing);
  EXPECT_EQ(consumer.snapshot().completeness,
            cpu_prefetch::storage::StreamCompleteness::writing);
}

TEST(RunnerPreparation, AffinityMismatchFailsBeforePrivateFirstTouch) {
  const auto run_id =
      cpu_prefetch::protocol::RunId::parse("runner-affinity-fail", "$/run_id");
  ASSERT_TRUE(run_id.has_value());
  cpu_prefetch::storage::ProducerObservationStream producer(run_id.value(), 1U);
  cpu_prefetch::storage::ConsumerObservationStream consumer(run_id.value(), 1U);
  FakeBindingBackend binding;
  FakeSoftwarePrefetchCapabilityBackend capability;
  binding.failed_cpu = cpu_prefetch::runner::kNearWorkerPair.producer_cpu;
  cpu_prefetch::runner::AffinedObservationPreparation preparation(
      binding, capability, cpu_prefetch::runner::kNearWorkerPair, producer, consumer);

  EXPECT_FALSE(preparation.prepare_producer());
  EXPECT_EQ(producer.append({}),
            cpu_prefetch::storage::AppendStatus::stream_unprepared);
  EXPECT_FALSE(preparation.evidence().passes());
}

TEST(RunnerPreparation, MissingPrfchwFailsBeforePrivateFirstTouch) {
  const auto run_id =
      cpu_prefetch::protocol::RunId::parse("runner-prfchw-fail", "$/run_id");
  ASSERT_TRUE(run_id.has_value());
  cpu_prefetch::storage::ProducerObservationStream producer(run_id.value(), 1U);
  cpu_prefetch::storage::ConsumerObservationStream consumer(run_id.value(), 1U);
  FakeBindingBackend binding;
  FakeSoftwarePrefetchCapabilityBackend capability;
  capability.supported = false;
  cpu_prefetch::runner::AffinedObservationPreparation preparation(
      binding, capability, cpu_prefetch::runner::kNearWorkerPair, producer, consumer);

  EXPECT_FALSE(preparation.prepare_producer());
  EXPECT_EQ(producer.append({}),
            cpu_prefetch::storage::AppendStatus::stream_unprepared);
  const auto evidence = preparation.evidence();
  EXPECT_TRUE(evidence.producer_binding.passes());
  EXPECT_FALSE(evidence.producer_software_prefetch_capability.passes());
  EXPECT_FALSE(evidence.passes());
}

TEST(RunnerPreparation, AdmittedStaticPathUsesAffinedPreparationBeforeEmptyRun) {
  const auto directory = test_directory("prepared-static-test");
  const auto artifact = directory / "artifact.bin";
  {
    std::ofstream output(artifact, std::ios::binary | std::ios::trunc);
    output << "synthetic-prepared-static-evidence";
  }
  const auto digest = cpu_prefetch::runner::sha256_file(artifact);
  ASSERT_TRUE(digest.has_value());
  auto admission = complete_admission();
  admission.execution_limits = {1'000'000U, 1'000'000U, 1U, 1'000'000U, 1'000'000U};
  for (auto& reference : admission.evidence) {
    reference.path = artifact.filename();
    reference.sha256 = digest.value();
  }
  const auto ticket =
      cpu_prefetch::runner::admit_runner(admission, trust_anchor(), directory);
  ASSERT_TRUE(ticket.has_value());

  const auto run_id =
      cpu_prefetch::protocol::RunId::parse("runner-prepared-static", "$/run_id");
  ASSERT_TRUE(run_id.has_value());
  cpu_prefetch::storage::ProducerObservationStream producer(run_id.value(), 0U);
  cpu_prefetch::storage::ConsumerObservationStream consumer(run_id.value(), 0U);
  FakeBindingBackend binding;
  FakeSoftwarePrefetchCapabilityBackend capability;
  cpu_prefetch::runner::AffinedObservationPreparation preparation(
      binding, capability, cpu_prefetch::runner::kNearWorkerPair, producer, consumer);
  RunnerStepClock clock;
  EmptyR0Backend backend;
  cpu_prefetch::lifecycle::TerminationControl termination(
      cpu_prefetch::queue::CacheLineBytes{64U});
  constexpr std::array<std::uint64_t, 0U> deadlines{};

  const auto report =
      cpu_prefetch::runner::execute_static_prepared_measurement<QueuePackage::r0>(
          ticket.value(), {deadlines, 0U, 1U}, clock, backend, termination,
          preparation);
  EXPECT_EQ(report.failure_phase, cpu_prefetch::lifecycle::ExecutionFailurePhase::none);
  EXPECT_EQ(report.attempted, 0U);
  EXPECT_TRUE(report.producer_completed);
  EXPECT_TRUE(report.consumer_drained);
  EXPECT_TRUE(preparation.evidence().passes());
  std::filesystem::remove_all(directory);
}

[[nodiscard]] auto qualification_identity()
    -> cpu_prefetch::runner::QualificationIdentity {
  return {"synthetic-qualification",
          "SYNTHETIC-NOT-A-STAND",
          "synthetic-binding",
          "synthetic-revision",
          std::string(kZeroHash),
          "2026-08-22T00:00:00Z",
          cpu_prefetch::runner::kNearWorkerPair,
          {{"synthetic-source", std::string(kZeroHash)}}};
}

TEST(RunnerQualification, TypedArtifactProducersDeriveEligibilityAndCanonicalBytes) {
  using namespace cpu_prefetch::runner;
  const auto identity = qualification_identity();
  const auto clock =
      make_selected_pair_clock_evidence(identity, {{100'000U, 100'000U},
                                                   {10'000'000U, 10'000'000U},
                                                   10'000'000U,
                                                   0U,
                                                   3U,
                                                   3U,
                                                   100'000U,
                                                   true,
                                                   true,
                                                   true});
  ASSERT_TRUE(clock.has_value());
  EXPECT_TRUE(clock.value().eligible);

  const auto atomics = make_runtime_atomic_layout_evidence(
      identity, {sizeof(void*), alignof(void*), sizeof(std::uint32_t),
                 alignof(std::uint32_t), 64U, true, true, true, true, true});
  ASSERT_TRUE(atomics.has_value());
  EXPECT_TRUE(atomics.value().eligible);

  const auto migration = make_actual_cpu_migration_evidence(
      identity, {2U, 2U, 0U, 0U, 1U, 1U, 0U, 0U, true, true});
  ASSERT_TRUE(migration.has_value());
  EXPECT_TRUE(migration.value().eligible);

  const RegionResidencyInput shared{
      "SHARED_EVENT_AND_QUEUE", 0U, 4U, 4U, 4U, 0U, 0U, 0U};
  const RegionResidencyInput producer{"PRODUCER_PRIVATE", 0U, 2U, 2U, 2U, 0U, 0U, 0U};
  const RegionResidencyInput consumer{"CONSUMER_PRIVATE", 0U, 2U, 2U, 2U, 0U, 0U, 0U};
  const auto residency = make_address_residency_evidence(
      identity, {"SYNTHETIC-RESIDENCY-MECHANISM", shared, producer, consumer});
  ASSERT_TRUE(residency.has_value());
  EXPECT_TRUE(residency.value().eligible);

  const SoftwarePrefetchCapabilityObservation prefetch_capability{0x80000008U, 0x121U,
                                                                  true};
  const auto software_prefetch = make_software_prefetch_mapping_evidence(
      identity, {std::string(kSoftwarePrefetchMappingId), prefetch_capability,
                 prefetch_capability, true, true, true, true});
  ASSERT_TRUE(software_prefetch.has_value());
  EXPECT_TRUE(software_prefetch.value().eligible);

  for (const auto* document :
       {&clock.value().canonical_json, &atomics.value().canonical_json,
        &migration.value().canonical_json, &residency.value().canonical_json,
        &software_prefetch.value().canonical_json}) {
    const auto parsed = cpu_prefetch::protocol::json::parse(*document);
    ASSERT_TRUE(parsed.has_value());
    const auto canonical = cpu_prefetch::protocol::json::canonicalize(parsed.value());
    ASSERT_TRUE(canonical.has_value());
    EXPECT_EQ(canonical.value(), *document);
  }
}

TEST(RunnerQualification, MissingCountsMigrationsAndUnavailablePagesStayIneligible) {
  using namespace cpu_prefetch::runner;
  const auto identity = qualification_identity();
  auto clock_input = SelectedPairClockInput{{100'000U, 100'000U},
                                            {10'000'000U, 9'999'999U},
                                            10'000'000U,
                                            1U,
                                            3U,
                                            3U,
                                            100'000U,
                                            true,
                                            true,
                                            true};
  const auto clock = make_selected_pair_clock_evidence(identity, clock_input);
  ASSERT_TRUE(clock.has_value());
  EXPECT_FALSE(clock.value().eligible);

  const auto migration = make_actual_cpu_migration_evidence(
      identity, {2U, 2U, 0U, 0U, 1U, 26U, 0U, 1U, true, true});
  ASSERT_TRUE(migration.has_value());
  EXPECT_FALSE(migration.value().eligible);

  const RegionResidencyInput unavailable{
      "SHARED_EVENT_AND_QUEUE", 0U, 4U, 4U, 4U, 1U, 0U, 0U};
  const auto residency = make_address_residency_evidence(
      identity,
      {"SYNTHETIC-RESIDENCY-MECHANISM", unavailable, unavailable, unavailable});
  ASSERT_TRUE(residency.has_value());
  EXPECT_FALSE(residency.value().eligible);

  const SoftwarePrefetchCapabilityObservation supported{0x80000008U, 0x121U, true};
  const SoftwarePrefetchCapabilityObservation unsupported{0x80000008U, 0x21U, false};
  const auto software_prefetch = make_software_prefetch_mapping_evidence(
      identity, {std::string(kSoftwarePrefetchMappingId), supported, unsupported, true,
                 true, true, true});
  ASSERT_TRUE(software_prefetch.has_value());
  EXPECT_FALSE(software_prefetch.value().eligible);
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
