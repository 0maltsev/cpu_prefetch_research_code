#include "cpu_prefetch/runner/runner.hpp"

#include "cpu_prefetch/protocol/json.hpp"

#include <openssl/evp.h>

#include <algorithm>
#include <array>
#include <cpuid.h>
#include <fstream>
#include <limits>
#include <memory>
#include <sched.h>
#include <set>
#include <system_error>

namespace cpu_prefetch::runner {
namespace {

using namespace std::string_view_literals;

using protocol::ErrorCategory;
using protocol::ValidationError;
using protocol::json::Value;

[[nodiscard]] auto error(ErrorCategory category, std::string path, std::string rule,
                         std::string message) -> ValidationError {
  return {category, std::move(path), std::move(rule), std::move(message)};
}

[[nodiscard]] auto object_of(const Value& value, std::string_view path,
                             std::vector<ValidationError>& errors)
    -> const Value::Object* {
  const auto* object = value.as_object();
  if (object == nullptr) {
    errors.push_back(error(ErrorCategory::invalid_type, std::string(path), "RUN-TYPE",
                           "value must be an object"));
  }
  return object;
}

[[nodiscard]] auto field(const Value::Object& object, std::string_view name,
                         std::string_view path, std::vector<ValidationError>& errors)
    -> const Value* {
  const auto iterator = object.find(name);
  if (iterator == object.end()) {
    errors.push_back(error(ErrorCategory::missing_field,
                           std::string(path) + "/" + std::string(name), "RUN-REQUIRED",
                           "required field is missing"));
    return nullptr;
  }
  return &iterator->second;
}

void reject_unknown(const Value::Object& object,
                    std::span<const std::string_view> accepted, std::string_view path,
                    std::vector<ValidationError>& errors) {
  for (const auto& [name, unused] : object) {
    static_cast<void>(unused);
    if (std::find(accepted.begin(), accepted.end(), name) == accepted.end()) {
      errors.push_back(error(ErrorCategory::unknown_field,
                             std::string(path) + "/" + name, "RUN-UNKNOWN",
                             "unknown field is forbidden"));
    }
  }
}

[[nodiscard]] auto string_field(const Value::Object& object, std::string_view name,
                                std::string_view path,
                                std::vector<ValidationError>& errors) -> std::string {
  const auto* value = field(object, name, path, errors);
  if (value == nullptr) {
    return {};
  }
  const auto* text = value->as_string();
  if (text == nullptr) {
    errors.push_back(error(ErrorCategory::invalid_type,
                           std::string(path) + "/" + std::string(name), "RUN-STRING",
                           "field must be a string"));
    return {};
  }
  return *text;
}

[[nodiscard]] auto bool_field(const Value::Object& object, std::string_view name,
                              std::string_view path,
                              std::vector<ValidationError>& errors) -> bool {
  const auto* value = field(object, name, path, errors);
  if (value == nullptr) {
    return false;
  }
  const auto* boolean = value->as_bool();
  if (boolean == nullptr) {
    errors.push_back(error(ErrorCategory::invalid_type,
                           std::string(path) + "/" + std::string(name), "RUN-BOOLEAN",
                           "field must be a boolean"));
    return false;
  }
  return *boolean;
}

[[nodiscard]] auto uint_field(const Value::Object& object, std::string_view name,
                              std::string_view path,
                              std::vector<ValidationError>& errors) -> std::uint64_t {
  const auto* value = field(object, name, path, errors);
  if (value == nullptr) {
    return 0U;
  }
  const auto* number = value->as_number();
  if (number == nullptr ||
      number->kind != protocol::json::Number::Kind::unsigned_integer) {
    errors.push_back(error(ErrorCategory::invalid_type,
                           std::string(path) + "/" + std::string(name), "RUN-U64",
                           "field must be an exact unsigned integer"));
    return 0U;
  }
  return std::get<std::uint64_t>(number->value);
}

[[nodiscard]] auto supported_package(protocol::QueuePackage package) noexcept -> bool {
  return package == protocol::QueuePackage::r0 ||
         package == protocol::QueuePackage::r1 ||
         package == protocol::QueuePackage::r2 ||
         package == protocol::QueuePackage::l0 || package == protocol::QueuePackage::l1;
}

void add_mismatch(std::vector<ValidationError>& errors, std::string path,
                  std::string rule, std::string message) {
  errors.push_back(error(ErrorCategory::reference_mismatch, std::move(path),
                         std::move(rule), std::move(message)));
}

} // namespace

auto selected_worker_pair(protocol::Placement placement) noexcept -> WorkerPair {
  if (placement == protocol::Placement::near) {
    return kNearWorkerPair;
  }
  if (placement == protocol::Placement::far) {
    return kFarWorkerPair;
  }
  return {std::numeric_limits<std::uint32_t>::max(),
          std::numeric_limits<std::uint32_t>::max()};
}

auto LinuxCurrentThreadBindingBackend::bind_and_verify(
    std::uint32_t requested_cpu) noexcept -> ThreadBindingObservation {
  ThreadBindingObservation observation{
      requested_cpu, std::numeric_limits<std::uint32_t>::max(), false, false, false};
  if (requested_cpu >= CPU_SETSIZE) {
    return observation;
  }
  cpu_set_t requested_set;
  CPU_ZERO(&requested_set);
  CPU_SET(requested_cpu, &requested_set);
  observation.affinity_applied =
      ::sched_setaffinity(0, sizeof(requested_set), &requested_set) == 0;
  if (!observation.affinity_applied) {
    return observation;
  }

  cpu_set_t observed_set;
  CPU_ZERO(&observed_set);
  if (::sched_getaffinity(0, sizeof(observed_set), &observed_set) == 0) {
    observation.singleton_readback =
        CPU_COUNT(&observed_set) == 1 && CPU_ISSET(requested_cpu, &observed_set);
  }
  const auto actual = ::sched_getcpu();
  if (actual >= 0) {
    observation.actual_cpu = static_cast<std::uint32_t>(actual);
    observation.actual_cpu_matches = observation.actual_cpu == requested_cpu;
  }
  return observation;
}

auto X86CurrentCpuSoftwarePrefetchCapabilityBackend::observe() noexcept
    -> SoftwarePrefetchCapabilityObservation {
  unsigned int vendor_signature = 0U;
  const auto maximum_extended_leaf = __get_cpuid_max(0x80000000U, &vendor_signature);
  if (maximum_extended_leaf < kPrfchwExtendedLeaf) {
    return {maximum_extended_leaf, 0U, false};
  }
  unsigned int eax = 0U;
  unsigned int ebx = 0U;
  unsigned int ecx = 0U;
  unsigned int edx = 0U;
  if (__get_cpuid(kPrfchwExtendedLeaf, &eax, &ebx, &ecx, &edx) == 0) {
    return {maximum_extended_leaf, 0U, false};
  }
  return {maximum_extended_leaf, ecx, (ecx & kPrfchwEcxMask) != 0U};
}

auto AffinedObservationPreparation::prepare_producer() noexcept -> bool {
  producer_result_.binding = binding_backend_.bind_and_verify(workers_.producer_cpu);
  if (!producer_result_.binding.passes()) {
    return false;
  }
  producer_result_.software_prefetch_capability = capability_backend_.observe();
  if (!producer_result_.software_prefetch_capability.passes()) {
    return false;
  }
  producer_result_.private_stream_prepared = producer_stream_.prepare_for_owner();
  return producer_result_.private_stream_prepared;
}

auto AffinedObservationPreparation::prepare_consumer() noexcept -> bool {
  consumer_result_.binding = binding_backend_.bind_and_verify(workers_.consumer_cpu);
  if (!consumer_result_.binding.passes()) {
    return false;
  }
  consumer_result_.software_prefetch_capability = capability_backend_.observe();
  if (!consumer_result_.software_prefetch_capability.passes()) {
    return false;
  }
  consumer_result_.private_stream_prepared = consumer_stream_.prepare_for_owner();
  return consumer_result_.private_stream_prepared;
}

auto AffinedObservationPreparation::evidence() const noexcept
    -> AffinedPreparationEvidence {
  return {producer_result_.binding,
          consumer_result_.binding,
          producer_result_.software_prefetch_capability,
          consumer_result_.software_prefetch_capability,
          producer_result_.private_stream_prepared,
          consumer_result_.private_stream_prepared};
}

auto to_string(EvidenceKind kind) noexcept -> std::string_view {
  switch (kind) {
  case EvidenceKind::protocol_snapshot:
    return "PROTOCOL_SNAPSHOT";
  case EvidenceKind::source_release:
    return "SOURCE_RELEASE";
  case EvidenceKind::run_plan:
    return "RUN_PLAN";
  case EvidenceKind::warmup_schedule:
    return "WARMUP_SCHEDULE";
  case EvidenceKind::measurement_schedule:
    return "MEASUREMENT_SCHEDULE";
  case EvidenceKind::seed_derivation:
    return "SEED_DERIVATION";
  case EvidenceKind::platform_inventory:
    return "PLATFORM_INVENTORY";
  case EvidenceKind::platform_request:
    return "PLATFORM_REQUEST";
  case EvidenceKind::platform_verification:
    return "PLATFORM_VERIFICATION";
  case EvidenceKind::hardware_prefetch_mapping:
    return "HARDWARE_PREFETCH_MAPPING";
  case EvidenceKind::software_prefetch_mapping:
    return "SOFTWARE_PREFETCH_MAPPING";
  case EvidenceKind::clock_qualification:
    return "CLOCK_QUALIFICATION";
  case EvidenceKind::queue_provenance:
    return "QUEUE_PROVENANCE";
  case EvidenceKind::runtime_atomic_layout:
    return "RUNTIME_ATOMIC_LAYOUT";
  case EvidenceKind::address_residency:
    return "ADDRESS_RESIDENCY";
  case EvidenceKind::storage_budget:
    return "STORAGE_BUDGET";
  case EvidenceKind::durability_domains:
    return "DURABILITY_DOMAINS";
  case EvidenceKind::calibration_freeze:
    return "CALIBRATION_FREEZE";
  case EvidenceKind::execution_limits:
    return "EXECUTION_LIMITS";
  case EvidenceKind::authority_custody:
    return "AUTHORITY_CUSTODY";
  case EvidenceKind::phase_execution_authorization:
    return "PHASE_EXECUTION_AUTHORIZATION";
  }
  return "UNKNOWN";
}

auto parse_evidence_kind(std::string_view value, std::string path)
    -> protocol::Result<EvidenceKind> {
  for (const auto kind : kRequiredEvidenceKinds) {
    if (to_string(kind) == value) {
      return protocol::Result<EvidenceKind>::success(kind);
    }
  }
  return protocol::Result<EvidenceKind>::failure(
      error(ErrorCategory::unknown_enum, std::move(path), "RUN-EVIDENCE-KIND",
            "unknown runner evidence kind"));
}

auto load_admission(std::string_view document) -> protocol::Result<RunnerAdmission> {
  const auto parsed = protocol::json::parse(document);
  if (!parsed) {
    return protocol::Result<RunnerAdmission>::failure(parsed.errors());
  }
  std::vector<ValidationError> errors;
  const auto* root = object_of(parsed.value(), "$", errors);
  if (root == nullptr) {
    return protocol::Result<RunnerAdmission>::failure(std::move(errors));
  }
  constexpr std::array root_fields{
      "schema_version"sv,    "protocol_version"sv,
      "runner_profile_id"sv, "cpu_pair_selection_id"sv,
      "relax_mapping_id"sv,  "source_revision"sv,
      "binary_sha256"sv,     "stand_id"sv,
      "binding_id"sv,        "package"sv,
      "placement"sv,         "producer_cpu"sv,
      "consumer_cpu"sv,      "execution_limits"sv,
      "evidence"sv,
  };
  reject_unknown(*root, root_fields, "$", errors);

  RunnerAdmission admission{
      string_field(*root, "schema_version", "$", errors),
      string_field(*root, "protocol_version", "$", errors),
      string_field(*root, "runner_profile_id", "$", errors),
      string_field(*root, "cpu_pair_selection_id", "$", errors),
      string_field(*root, "relax_mapping_id", "$", errors),
      string_field(*root, "source_revision", "$", errors),
      string_field(*root, "binary_sha256", "$", errors),
      string_field(*root, "stand_id", "$", errors),
      string_field(*root, "binding_id", "$", errors),
      protocol::QueuePackage::not_applicable,
      protocol::Placement::not_applicable,
      {0U, 0U},
      {},
      {},
  };

  const auto package_text = string_field(*root, "package", "$", errors);
  if (!package_text.empty()) {
    auto package = protocol::parse_queue_package(package_text, "$/package");
    if (package) {
      admission.package = package.value();
    } else {
      errors.insert(errors.end(), package.errors().begin(), package.errors().end());
    }
  }
  const auto placement_text = string_field(*root, "placement", "$", errors);
  if (!placement_text.empty()) {
    auto placement = protocol::parse_placement(placement_text, "$/placement");
    if (placement) {
      admission.placement = placement.value();
    } else {
      errors.insert(errors.end(), placement.errors().begin(), placement.errors().end());
    }
  }
  const auto producer_cpu = uint_field(*root, "producer_cpu", "$", errors);
  const auto consumer_cpu = uint_field(*root, "consumer_cpu", "$", errors);
  if (producer_cpu > std::numeric_limits<std::uint32_t>::max() ||
      consumer_cpu > std::numeric_limits<std::uint32_t>::max()) {
    errors.push_back(error(ErrorCategory::out_of_range, "$/producer_cpu", "RUN-CPU-U32",
                           "worker CPU must fit uint32"));
  } else {
    admission.workers = {static_cast<std::uint32_t>(producer_cpu),
                         static_cast<std::uint32_t>(consumer_cpu)};
  }

  if (const auto* limits_value = field(*root, "execution_limits", "$", errors)) {
    const auto* limits = object_of(*limits_value, "$/execution_limits", errors);
    if (limits != nullptr) {
      constexpr std::array limit_fields{
          "controller_start_poll_limit"sv,
          "worker_start_poll_limit"sv,
      };
      reject_unknown(*limits, limit_fields, "$/execution_limits", errors);
      admission.execution_limits = {
          uint_field(*limits, "controller_start_poll_limit", "$/execution_limits",
                     errors),
          uint_field(*limits, "worker_start_poll_limit", "$/execution_limits", errors),
      };
    }
  }

  if (const auto* evidence_value = field(*root, "evidence", "$", errors)) {
    const auto* evidence = evidence_value->as_array();
    if (evidence == nullptr) {
      errors.push_back(error(ErrorCategory::invalid_type, "$/evidence", "RUN-ARRAY",
                             "evidence must be an array"));
    } else {
      admission.evidence.reserve(evidence->size());
      for (std::size_t index = 0U; index < evidence->size(); ++index) {
        const auto path = "$/evidence/" + std::to_string(index);
        const auto* item = object_of((*evidence)[index], path, errors);
        if (item == nullptr) {
          continue;
        }
        constexpr std::array evidence_fields{
            "kind"sv,       "artifact_id"sv, "path"sv,     "sha256"sv,
            "binding_id"sv, "immutable"sv,   "eligible"sv,
        };
        reject_unknown(*item, evidence_fields, path, errors);
        const auto kind_text = string_field(*item, "kind", path, errors);
        const auto kind = parse_evidence_kind(kind_text, path + "/kind");
        if (!kind) {
          errors.insert(errors.end(), kind.errors().begin(), kind.errors().end());
          continue;
        }
        admission.evidence.push_back({kind.value(),
                                      string_field(*item, "artifact_id", path, errors),
                                      string_field(*item, "path", path, errors),
                                      string_field(*item, "sha256", path, errors),
                                      string_field(*item, "binding_id", path, errors),
                                      bool_field(*item, "immutable", path, errors),
                                      bool_field(*item, "eligible", path, errors)});
      }
    }
  }

  if (!errors.empty()) {
    return protocol::Result<RunnerAdmission>::failure(std::move(errors));
  }
  return protocol::Result<RunnerAdmission>::success(admission);
}

auto validate_admission_fields(const RunnerAdmission& admission,
                               const AdmissionTrustAnchor& trust_anchor)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  const auto require_nonempty = [&](std::string_view value, std::string path,
                                    std::string rule) {
    if (value.empty()) {
      errors.push_back(error(ErrorCategory::missing_field, std::move(path),
                             std::move(rule),
                             "current admission identity must be nonempty"));
    }
  };
  const auto exact = [&](std::string_view observed, std::string_view expected,
                         std::string path, std::string rule) {
    if (observed != expected) {
      add_mismatch(errors, std::move(path), std::move(rule),
                   "value does not match the accepted/current binding");
    }
  };

  exact(admission.schema_version, kAdmissionSchemaVersion, "$/schema_version",
        "RUN-SCHEMA");
  exact(admission.protocol_version, protocol::kProtocolVersion, "$/protocol_version",
        "RUN-PROTOCOL");
  exact(admission.runner_profile_id, kRunnerProfileId, "$/runner_profile_id",
        "RUN-PROFILE");
  exact(admission.cpu_pair_selection_id, kCpuPairSelectionId, "$/cpu_pair_selection_id",
        "RUN-CPU-PROFILE");
  exact(admission.relax_mapping_id, kRelaxMappingId, "$/relax_mapping_id", "RUN-RELAX");
  require_nonempty(admission.source_revision, "$/source_revision", "RUN-SOURCE-EMPTY");
  require_nonempty(admission.stand_id, "$/stand_id", "RUN-STAND-EMPTY");
  require_nonempty(admission.binding_id, "$/binding_id", "RUN-BINDING-EMPTY");
  if (!protocol::Sha256::parse(admission.binary_sha256, "$/binary_sha256")) {
    errors.push_back(error(ErrorCategory::invalid_hash, "$/binary_sha256",
                           "RUN-BINARY-SHA256",
                           "binary SHA-256 must be lowercase hexadecimal"));
  }
  exact(admission.source_revision, trust_anchor.source_revision, "$/source_revision",
        "RUN-SOURCE");
  exact(admission.binary_sha256, trust_anchor.binary_sha256, "$/binary_sha256",
        "RUN-BINARY");
  exact(admission.stand_id, trust_anchor.stand_id, "$/stand_id", "RUN-STAND");
  exact(admission.binding_id, trust_anchor.binding_id, "$/binding_id", "RUN-BINDING");
  if (trust_anchor.source_dirty) {
    errors.push_back(error(ErrorCategory::missing_evidence, "$/source_revision",
                           "RUN-DIRTY-SOURCE",
                           "a dirty-source build cannot receive an admission ticket"));
  }
  if (!supported_package(admission.package)) {
    errors.push_back(error(ErrorCategory::unknown_enum, "$/package", "RUN-PACKAGE",
                           "only the five Stage A packages are supported"));
  }
  if (admission.placement != protocol::Placement::near &&
      admission.placement != protocol::Placement::far) {
    errors.push_back(error(ErrorCategory::unknown_enum, "$/placement", "RUN-PLACEMENT",
                           "only the accepted NEAR and FAR placements are supported"));
  } else if (admission.workers != selected_worker_pair(admission.placement)) {
    add_mismatch(errors, "$/producer_cpu", "RUN-CPU-PAIR",
                 "worker CPUs do not match the Q13 placement pair");
  }

  const auto& limits = admission.execution_limits;
  if (limits.controller_start_poll_limit == 0U ||
      limits.worker_start_poll_limit == 0U) {
    errors.push_back(error(ErrorCategory::missing_evidence, "$/execution_limits",
                           "RUN-LIMITS",
                           "both prospectively accepted start-barrier limits must be "
                           "nonzero"));
  }

  std::set<EvidenceKind> observed_kinds;
  std::set<std::string> artifact_ids;
  for (std::size_t index = 0U; index < admission.evidence.size(); ++index) {
    const auto& reference = admission.evidence[index];
    const auto path = "$/evidence/" + std::to_string(index);
    if (!observed_kinds.insert(reference.kind).second) {
      errors.push_back(error(ErrorCategory::duplicate_value, path + "/kind",
                             "RUN-EVIDENCE-UNIQUE",
                             "each required evidence kind must appear exactly once"));
    }
    if (reference.artifact_id.empty() ||
        !artifact_ids.insert(reference.artifact_id).second) {
      errors.push_back(error(ErrorCategory::duplicate_value, path + "/artifact_id",
                             "RUN-ARTIFACT-UNIQUE",
                             "artifact IDs must be nonempty and unique"));
    }
    if (reference.path.empty()) {
      errors.push_back(error(ErrorCategory::missing_field, path + "/path",
                             "RUN-EVIDENCE-PATH", "evidence path must be explicit"));
    }
    if (!protocol::Sha256::parse(reference.sha256, path + "/sha256")) {
      errors.push_back(error(ErrorCategory::invalid_hash, path + "/sha256",
                             "RUN-EVIDENCE-SHA256",
                             "evidence SHA-256 must be lowercase hexadecimal"));
    }
    if (reference.binding_id != admission.binding_id) {
      add_mismatch(errors, path + "/binding_id", "RUN-EVIDENCE-STALE",
                   "evidence is not bound to the current admission epoch");
    }
    if (!reference.immutable) {
      errors.push_back(error(ErrorCategory::immutable_configuration,
                             path + "/immutable", "RUN-EVIDENCE-IMMUTABLE",
                             "mutable evidence cannot arm the runner"));
    }
    if (!reference.eligible) {
      errors.push_back(error(
          ErrorCategory::missing_evidence, path + "/eligible", "RUN-EVIDENCE-ELIGIBLE",
          "unresolved or ineligible evidence cannot arm the runner"));
    }
  }
  for (const auto required : kRequiredEvidenceKinds) {
    if (!observed_kinds.contains(required)) {
      errors.push_back(
          error(ErrorCategory::missing_evidence, "$/evidence", "RUN-EVIDENCE-COMPLETE",
                "missing required evidence kind " + std::string(to_string(required))));
    }
  }

  return errors;
}

auto sha256_file(const std::filesystem::path& path) -> protocol::Result<std::string> {
  std::error_code filesystem_error;
  const auto status = std::filesystem::symlink_status(path, filesystem_error);
  if (filesystem_error || !std::filesystem::is_regular_file(status) ||
      std::filesystem::is_symlink(status)) {
    return protocol::Result<std::string>::failure(
        error(ErrorCategory::missing_evidence, "$file", "RUN-FILE-REGULAR",
              "evidence must be an existing non-symlink regular file"));
  }
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return protocol::Result<std::string>::failure(
        error(ErrorCategory::missing_evidence, "$file", "RUN-FILE-OPEN",
              "evidence file cannot be opened"));
  }
  using Context = std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)>;
  Context context(EVP_MD_CTX_new(), &EVP_MD_CTX_free);
  if (context == nullptr ||
      EVP_DigestInit_ex(context.get(), EVP_sha256(), nullptr) != 1) {
    return protocol::Result<std::string>::failure(
        error(ErrorCategory::missing_evidence, "$file", "RUN-SHA256-INIT",
              "SHA-256 initialization failed"));
  }
  std::array<char, std::size_t{64U} * 1024U> buffer{};
  while (input) {
    input.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
    const auto count = input.gcount();
    if (count > 0 && EVP_DigestUpdate(context.get(), buffer.data(),
                                      static_cast<std::size_t>(count)) != 1) {
      return protocol::Result<std::string>::failure(
          error(ErrorCategory::missing_evidence, "$file", "RUN-SHA256-UPDATE",
                "SHA-256 update failed"));
    }
  }
  if (!input.eof()) {
    return protocol::Result<std::string>::failure(
        error(ErrorCategory::missing_evidence, "$file", "RUN-FILE-READ",
              "evidence file could not be read completely"));
  }
  std::array<unsigned char, 32> digest{};
  unsigned int digest_size = 0U;
  if (EVP_DigestFinal_ex(context.get(), digest.data(), &digest_size) != 1 ||
      digest_size != digest.size()) {
    return protocol::Result<std::string>::failure(error(ErrorCategory::missing_evidence,
                                                        "$file", "RUN-SHA256-FINAL",
                                                        "SHA-256 finalization failed"));
  }
  constexpr std::array digits{'0', '1', '2', '3', '4', '5', '6', '7',
                              '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'};
  std::string output;
  output.reserve(64U);
  for (const auto byte : digest) {
    output.push_back(digits[(byte >> 4U) & 0x0fU]);
    output.push_back(digits[byte & 0x0fU]);
  }
  return protocol::Result<std::string>::success(output);
}

auto verify_evidence_files(const RunnerAdmission& admission,
                           const std::filesystem::path& manifest_parent)
    -> std::vector<ValidationError> {
  std::vector<ValidationError> errors;
  for (std::size_t index = 0U; index < admission.evidence.size(); ++index) {
    const auto& reference = admission.evidence[index];
    const auto resolved = reference.path.is_absolute()
                              ? reference.path
                              : manifest_parent / reference.path;
    const auto digest = sha256_file(resolved);
    const auto path = "$/evidence/" + std::to_string(index) + "/path";
    if (!digest) {
      errors.push_back(error(ErrorCategory::missing_evidence, path, "RUN-EVIDENCE-FILE",
                             "evidence artifact is absent or unreadable"));
    } else if (digest.value() != reference.sha256) {
      errors.push_back(error(ErrorCategory::reference_mismatch, path,
                             "RUN-EVIDENCE-HASH",
                             "evidence bytes do not match the declared SHA-256"));
    }
  }
  return errors;
}

auto admit_runner(const RunnerAdmission& admission,
                  const AdmissionTrustAnchor& trust_anchor,
                  const std::filesystem::path& manifest_parent)
    -> protocol::Result<AdmissionTicket> {
  auto errors = validate_admission_fields(admission, trust_anchor);
  auto file_errors = verify_evidence_files(admission, manifest_parent);
  errors.insert(errors.end(), std::make_move_iterator(file_errors.begin()),
                std::make_move_iterator(file_errors.end()));
  if (!errors.empty()) {
    return protocol::Result<AdmissionTicket>::failure(std::move(errors));
  }
  return protocol::Result<AdmissionTicket>::success(
      AdmissionTicket(admission.package, admission.placement, admission.workers,
                      admission.execution_limits, admission.binding_id));
}

auto admit_runner_from_sealed_controller(const RunnerAdmission& admission,
                                         const AdmissionTrustAnchor& trust_anchor,
                                         const SealedControllerProof& proof)
    -> protocol::Result<AdmissionTicket> {
  auto errors = validate_admission_fields(admission, trust_anchor);
  if (!protocol::Sha256::parse(proof.canonical_admission_sha256,
                               "$/runner_admission_sha256")) {
    errors.push_back(error(ErrorCategory::invalid_hash, "$/runner_admission_sha256",
                           "RUN-SEALED-ADMISSION-SHA256",
                           "sealed admission digest must be lowercase SHA-256"));
  }
  if (!protocol::Sha256::parse(proof.evidence_set_sha256,
                               "$/runner_evidence_set_sha256")) {
    errors.push_back(error(ErrorCategory::invalid_hash, "$/runner_evidence_set_sha256",
                           "RUN-SEALED-EVIDENCE-SHA256",
                           "sealed evidence-set digest must be lowercase SHA-256"));
  }
  if (!errors.empty()) {
    return protocol::Result<AdmissionTicket>::failure(std::move(errors));
  }
  return protocol::Result<AdmissionTicket>::success(
      AdmissionTicket(admission.package, admission.placement, admission.workers,
                      admission.execution_limits, admission.binding_id));
}

} // namespace cpu_prefetch::runner
