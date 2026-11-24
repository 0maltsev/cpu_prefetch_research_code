#ifndef CPU_PREFETCH_PROTOCOL_MODEL_HPP
#define CPU_PREFETCH_PROTOCOL_MODEL_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/protocol/validation.hpp"

namespace cpu_prefetch::protocol {

inline constexpr std::string_view kProtocolVersion = "2.0.0-pre.3";
inline constexpr std::string_view kPreviousProtocolVersion = "2.0.0-pre.2";
inline constexpr std::string_view kOldestReadableProtocolVersion = "2.0.0-pre.1";
inline constexpr std::string_view kLogicalRowSchemaVersion = "2.0.0-pre.3";
inline constexpr std::string_view kCanonicalizationSuite = "JCS-I64-v1";

enum class ProtocolVersion : std::uint8_t {
  v2_0_0_pre_1,
  v2_0_0_pre_2,
  v2_0_0_pre_3,
};

template <typename Tag> class Identifier {
public:
  // Value and diagnostic path are deliberately adjacent parts of the parsing API.
  // NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
  [[nodiscard]] static auto parse(std::string value, std::string path)
      -> Result<Identifier> {
    if (value.empty()) {
      return Result<Identifier>::failure({ErrorCategory::invalid_id, std::move(path),
                                          "DAT-ID-NONEMPTY",
                                          "identifier must not be empty"});
    }
    return Result<Identifier>::success(Identifier(std::move(value)));
  }

  [[nodiscard]] auto value() const noexcept -> std::string_view { return value_; }
  auto operator==(const Identifier&) const -> bool = default;

private:
  explicit Identifier(std::string value) : value_(std::move(value)) {}
  std::string value_;
};

struct RunIdTag;
struct BlockIdTag;
struct ArtifactIdTag;
struct PlatformIdTag;
struct BuildIdTag;
struct RecordIdTag;
struct ScheduleIdTag;
struct NamespaceIdTag;
struct SeedIdTag;
struct AuthorityIdTag;

using RunId = Identifier<RunIdTag>;
using BlockId = Identifier<BlockIdTag>;
using ArtifactId = Identifier<ArtifactIdTag>;
using PlatformId = Identifier<PlatformIdTag>;
using BuildId = Identifier<BuildIdTag>;
using RecordId = Identifier<RecordIdTag>;
using ScheduleId = Identifier<ScheduleIdTag>;
using NamespaceId = Identifier<NamespaceIdTag>;
using SeedId = Identifier<SeedIdTag>;
using AuthorityId = Identifier<AuthorityIdTag>;

class Sha256 {
public:
  [[nodiscard]] static auto parse(std::string_view text, std::string path)
      -> Result<Sha256>;
  [[nodiscard]] auto hex() const -> std::string;
  auto operator==(const Sha256&) const -> bool = default;

private:
  explicit Sha256(std::array<std::byte, 32> bytes) : bytes_(bytes) {}
  std::array<std::byte, 32> bytes_{};
};

enum class Stage : std::uint8_t {
  calibration,
  pilot,
  stage_a,
  stage_b,
  stage_c,
  diagnostic
};
enum class RunMode : std::uint8_t {
  latency,
  service_rate_calibration,
  d2_calibration,
  counter_diagnostic,
  exploratory,
};
enum class LifecycleState : std::uint8_t {
  planned,
  pre_run_failure,
  warmup_failure,
  reset_failure,
  measurement_started,
  measurement_failure,
  drain_failure,
  completed,
};
enum class JoinStatus : std::uint8_t { not_attempted, failed, passed };
enum class BlockRole : std::uint8_t {
  h3_train,
  h3_validation,
  h1h2_supplemental,
  not_applicable
};
enum class QueuePackage : std::uint8_t {
  r0,
  r1,
  r2,
  l0,
  l1,
  nblfq_mpsc,
  not_applicable
};
enum class RequestedHardwareState : std::uint8_t { h0, h1, not_applicable };
enum class VerifiedHardwareState : std::uint8_t {
  verified_default,
  verified_changed,
  verification_failed,
  unknown,
  not_applicable,
};
enum class Placement : std::uint8_t { near, far, stage_c_other, not_applicable };
enum class WorkingSetClass : std::uint8_t {
  l2_resident,
  llc_resident,
  beyond_llc,
  not_applicable,
};
enum class LoadLevel : std::uint8_t {
  l025,
  l050,
  l075,
  calibration_ready,
  stage_c_other,
  not_applicable,
};
enum class RunValidity : std::uint8_t { not_evaluated, valid, invalid };
enum class GateStatus : std::uint8_t { not_evaluated, pass, fail, not_applicable };
enum class ConfirmatoryEstimability : std::uint8_t {
  not_evaluated,
  estimable,
  blocked_zero_loss,
  blocked_effective_tail,
  blocked_invalid_run,
  blocked_incomplete_block,
  blocked_access_leakage,
  blocked_multiple,
  not_applicable,
};
// Declaration order is the required ascending UTF-8 token-byte order.
enum class ConfirmatoryBlocker : std::uint8_t {
  blocked_access_leakage,
  blocked_effective_tail,
  blocked_incomplete_block,
  blocked_invalid_run,
  blocked_zero_loss,
};
enum class BlockCompleteness : std::uint8_t {
  not_evaluated,
  complete,
  incomplete,
  not_applicable
};
enum class AccessState : std::uint8_t {
  planned,
  collected_sealed,
  training_open,
  selection_frozen,
  validation_unsealed,
  h3_evaluated,
  h1h2_released,
  archived,
};
enum class ProducerOutcome : std::uint8_t { accepted, full };
enum class StreamKind : std::uint8_t { producer, consumer, joined_derived };
enum class Endianness : std::uint8_t { little_endian, big_endian, not_applicable };
enum class StorageMode : std::uint8_t { external_immutable_artifact, inline_test_only };
enum class ScheduleKind : std::uint8_t {
  warmup,
  calibration,
  pilot,
  confirmatory,
  diagnostic,
  stage_b,
  stage_c,
};
enum class ArrivalFamily : std::uint8_t {
  poisson_exponential,
  continuous_ready,
  predeclared_burst,
  predeclared_other,
};
enum class DeadlineEncoding : std::uint8_t {
  absolute_integer_ticks,
  delta_integer_ticks
};
enum class FailureScope : std::uint8_t {
  run,
  block,
  platform,
  build,
  protocol,
  access
};
enum class FailureCategory : std::uint8_t {
  correctness,
  count_reconciliation,
  clock,
  affinity,
  numa,
  hardware_state,
  process_interruption,
  sample_loss,
  buffer_overflow,
  corrupt_output,
  manifest,
  address_pattern,
  phase_reset,
  environment,
  access_leakage,
  other_measurement,
};
enum class DetectedPhase : std::uint8_t {
  pre_run,
  warmup,
  reset,
  measurement,
  drain,
  post_run,
  analysis,
  access_audit,
};
enum class BlockConsequence : std::uint8_t {
  none,
  original_block_incomplete,
  study_unresolved,
  not_applicable,
};
enum class ResolutionStatus : std::uint8_t {
  open,
  retained_diagnostic_only,
  replacement_authorized,
  replacement_denied,
  resolved_before_measurement,
  study_stopped,
};
enum class ArtifactRelationship : std::uint8_t {
  producer_raw,
  consumer_raw,
  join_audit,
  joined_derived,
  phase_integrity_report,
  schedule,
  counter,
  derived,
  provenance,
  failure_evidence,
};
enum class RecordKind : std::uint8_t {
  protocol_freeze,
  selection_freeze,
  validation_unseal,
  h3_evaluated,
  h1h2_released,
  replacement_authorization,
  amendment,
};
enum class ReadinessBoundary : std::uint8_t {
  ready_for_implementation,
  blocked_before_implementation,
  blocked_before_pilot,
  blocked_before_confirmatory_execution,
  submission_only,
};
enum class FreezeStatus : std::uint8_t {
  open,
  frozen,
  authorized,
  rejected,
  superseded
};
enum class AuthorizationStatus : std::uint8_t {
  not_applicable,
  pending,
  authorized,
  rejected
};
enum class AuthorityRole : std::uint8_t {
  protocol_owner,
  freeze_authority,
  validation_custodian,
  confirmatory_analyst,
  replacement_authority,
  platform_operator,
  author,
};
enum class AccessClass : std::uint8_t {
  treatment_blind,
  training_only,
  validation_sealed,
  validation_unsealed,
  public_protocol,
  platform_evidence,
};
enum class H3Context : std::uint8_t {
  near_l2_l050,
  near_llc_l050,
  near_beyond_llc_l050,
  far_l2_l050,
  far_llc_l050,
  far_beyond_llc_l050,
};

[[nodiscard]] auto parse_protocol_version(std::string_view text, std::string path)
    -> Result<ProtocolVersion>;

#define CPU_PREFETCH_DECLARE_ENUM_PARSER(function_name, type_name)                     \
  [[nodiscard]] auto parse_##function_name(std::string_view text, std::string path)    \
      -> Result<type_name>

CPU_PREFETCH_DECLARE_ENUM_PARSER(stage, Stage);
CPU_PREFETCH_DECLARE_ENUM_PARSER(run_mode, RunMode);
CPU_PREFETCH_DECLARE_ENUM_PARSER(lifecycle_state, LifecycleState);
CPU_PREFETCH_DECLARE_ENUM_PARSER(join_status, JoinStatus);
CPU_PREFETCH_DECLARE_ENUM_PARSER(block_role, BlockRole);
CPU_PREFETCH_DECLARE_ENUM_PARSER(queue_package, QueuePackage);
CPU_PREFETCH_DECLARE_ENUM_PARSER(requested_hardware_state, RequestedHardwareState);
CPU_PREFETCH_DECLARE_ENUM_PARSER(verified_hardware_state, VerifiedHardwareState);
CPU_PREFETCH_DECLARE_ENUM_PARSER(placement, Placement);
CPU_PREFETCH_DECLARE_ENUM_PARSER(working_set_class, WorkingSetClass);
CPU_PREFETCH_DECLARE_ENUM_PARSER(load_level, LoadLevel);
CPU_PREFETCH_DECLARE_ENUM_PARSER(run_validity, RunValidity);
CPU_PREFETCH_DECLARE_ENUM_PARSER(gate_status, GateStatus);
CPU_PREFETCH_DECLARE_ENUM_PARSER(confirmatory_estimability, ConfirmatoryEstimability);
CPU_PREFETCH_DECLARE_ENUM_PARSER(confirmatory_blocker, ConfirmatoryBlocker);
CPU_PREFETCH_DECLARE_ENUM_PARSER(block_completeness, BlockCompleteness);
CPU_PREFETCH_DECLARE_ENUM_PARSER(access_state, AccessState);

#undef CPU_PREFETCH_DECLARE_ENUM_PARSER

struct ArtifactReference {
  ArtifactId artifact_id;
  Sha256 sha256;
  auto operator==(const ArtifactReference&) const -> bool = default;
};

struct TypedArtifactReference {
  ArtifactReference artifact;
  ArtifactRelationship relationship;
};

struct ExactRate {
  std::uint64_t numerator_events;
  std::uint64_t denominator_ticks;
};

struct RequestedAndVerifiedHardwareState {
  RequestedHardwareState requested;
  VerifiedHardwareState verified;
  ArtifactId readback_artifact_id;
  ArtifactId behavioral_probe_artifact_id;
  AuthorityId privileged_authority_id;
};

struct RngMetadata {
  std::string algorithm;
  std::string version;
  SeedId seed_id;
  RecordId derivation_record_id;
  NamespaceId parent_namespace_id;
};

struct ExternalStorage {
  std::string artifact_uri;
};

struct InlineDeadlineStorage {
  std::vector<std::uint64_t> deadline_ticks;
};

struct ExternalScheduleStorage {
  ArtifactId artifact_id;
  std::string artifact_uri;
  std::uint64_t row_count;
  std::uint64_t byte_count;
  Sha256 artifact_sha256;
};

struct ScheduleRecord {
  ProtocolVersion schema_version;
  ProtocolVersion protocol_version;
  ScheduleId schedule_id;
  ScheduleKind schedule_kind;
  ArrivalFamily arrival_family;
  NamespaceId namespace_id;
  RngMetadata rng;
  std::string time_unit;
  DeadlineEncoding deadline_encoding;
  std::uint64_t origin_ticks;
  std::uint64_t horizon_ticks;
  std::uint64_t offered_count;
  ExactRate nominal_offered_rate;
  RecordId overflow_rule_record_id;
  std::variant<ExternalScheduleStorage, InlineDeadlineStorage> deadline_storage;
  Sha256 decoded_deadlines_sha256;
  Sha256 schedule_sha256;
  json::Value source_document;
};

struct ProducerRecord {
  RunId run_id;
  std::uint64_t logical_sequence;
  std::uint64_t record_index;
  std::uint64_t scheduled_arrival;
  std::uint64_t producer_handle_begin;
  std::uint64_t record_lookup_completion;
  std::uint64_t enqueue_invocation;
  std::optional<std::uint64_t> enqueue_linearization;
  std::uint64_t enqueue_attempt_completion;
  ProducerOutcome outcome;
  std::optional<std::uint64_t> accepted_ordinal;
};

struct ConsumerRecord {
  RunId run_id;
  std::uint64_t consumed_ordinal;
  std::uint64_t observed_record_index;
  std::uint64_t dequeue_invocation;
  std::uint64_t dequeue_linearization;
  std::uint64_t dequeue_completion;
  std::uint64_t consumer_action_completion;
};

struct JoinedRecord {
  RunId run_id;
  std::uint64_t accepted_ordinal;
  std::uint64_t logical_sequence;
  std::uint64_t record_index;
  std::uint64_t producer_row_ordinal;
  std::uint64_t consumer_row_ordinal;
  std::uint64_t scheduled_arrival;
  std::uint64_t producer_handle_begin;
  std::uint64_t record_lookup_completion;
  std::uint64_t enqueue_invocation;
  std::uint64_t enqueue_linearization;
  std::uint64_t enqueue_attempt_completion;
  std::uint64_t dequeue_invocation;
  std::uint64_t dequeue_linearization;
  std::uint64_t dequeue_completion;
  std::uint64_t consumer_action_completion;
  std::uint64_t producer_lateness;
  std::uint64_t pointer_lookup_interval;
  std::uint64_t enqueue_service_time;
  std::uint64_t admission_delay;
  std::uint64_t queue_residence;
  std::uint64_t dequeue_service_time;
  std::uint64_t post_dequeue_delivery_interval;
  std::uint64_t consumer_action_interval;
  std::uint64_t end_to_end_latency;
};

using InlineObservationRows =
    std::variant<std::vector<ProducerRecord>, std::vector<ConsumerRecord>,
                 std::vector<JoinedRecord>>;

struct RawObservationEnvelope {
  ProtocolVersion schema_version;
  ProtocolVersion protocol_version;
  ArtifactId artifact_id;
  RunId run_id;
  StreamKind stream_kind;
  ProtocolVersion logical_row_schema_version;
  RecordId physical_format_record_id;
  std::string encoding;
  std::string time_unit;
  Endianness endianness;
  std::string compression;
  std::uint64_t row_count;
  std::uint64_t byte_count;
  std::variant<ExternalStorage, InlineObservationRows> storage;
  std::vector<ArtifactReference> source_artifacts;
  ArtifactReference integrity_artifact_ref;
  Sha256 artifact_sha256;
  json::Value source_document;
};

struct ChecksumEvidence {
  RecordId algorithm_record_id;
  std::string algorithm_version;
  std::string value_hex;
};

struct PhaseIntegrityRecord {
  ArtifactReference report_artifact;
  ChecksumEvidence final_consumer_rolling_checksum;
  ChecksumEvidence event_records_pre_checksum;
  ChecksumEvidence event_records_post_checksum;
  ChecksumEvidence ordered_index_checksum;
  ChecksumEvidence address_delta_checksum;
};

struct RunCounts {
  std::optional<std::uint64_t> offered;
  std::optional<std::uint64_t> attempted;
  std::optional<std::uint64_t> accepted;
  std::optional<std::uint64_t> full;
  std::optional<std::uint64_t> consumed;
  std::optional<std::uint64_t> final_occupancy;
  std::optional<std::uint64_t> raw_sample_count;
  std::optional<json::Number> n_eff_p999;
};

struct RunProvenance {
  std::string paper_repository_revision;
  std::string implementation_repository_revision;
  Sha256 build_artifact_sha256;
  std::string compiler_identity;
  std::vector<std::string> compiler_flags;
  std::string standard_library;
  RecordId dependency_record_id;
};

struct RunScheduleReferences {
  ArtifactReference measurement;
  ArtifactReference warmup;
};

struct RunSeedReferences {
  SeedId arrival;
  std::optional<SeedId> node_order;
  SeedId event_order;
  SeedId warmup;
  RecordId derivation_record_id;
};

struct RunManifest {
  ProtocolVersion schema_version;
  ProtocolVersion protocol_version;
  RunId run_id;
  PlatformId platform_id;
  BuildId build_id;
  std::uint64_t within_cell_ordinal;
  RecordId queue_provenance_id;
  RunProvenance provenance;
  Stage stage;
  RunMode run_mode;
  LifecycleState lifecycle_state;
  BlockId block_id;
  BlockRole block_role;
  QueuePackage package;
  RequestedHardwareState requested_hardware_state;
  VerifiedHardwareState verified_hardware_state;
  Placement placement;
  WorkingSetClass working_set_class;
  LoadLevel load_level;
  std::uint64_t capacity_events;
  std::string time_unit;
  RunScheduleReferences schedule_refs;
  RunSeedReferences seed_refs;
  RunValidity validity;
  GateStatus count_reconciliation;
  GateStatus zero_loss_status;
  GateStatus effective_tail_status;
  ConfirmatoryEstimability confirmatory_estimability;
  std::vector<ConfirmatoryBlocker> confirmatory_blockers;
  BlockCompleteness block_completeness;
  JoinStatus join_status;
  std::optional<RunCounts> counts;
  std::optional<PhaseIntegrityRecord> integrity_evidence;
  std::vector<RecordId> failure_record_ids;
  std::vector<TypedArtifactReference> artifact_refs;
  Sha256 manifest_sha256;
  json::Value source_document;
};

struct StageACell {
  std::uint64_t cell_ordinal;
  QueuePackage package;
  RequestedHardwareState requested_hardware_state;
  Placement placement;
  WorkingSetClass working_set_class;
  LoadLevel load_level;
  SeedId arrival_seed_ref;
  std::optional<SeedId> node_seed_ref;
  SeedId event_seed_ref;
};

struct ReplacementLineage {
  std::uint64_t replaced_block_ordinal;
  BlockRole replaced_block_role;
  NamespaceId replaced_seed_subspace_id;
};

struct BlockPlan {
  ProtocolVersion schema_version;
  ProtocolVersion protocol_version;
  BlockId block_id;
  PlatformId platform_id;
  BuildId build_id;
  Stage stage;
  BlockRole block_role;
  std::uint64_t block_ordinal;
  NamespaceId seed_subspace_id;
  std::optional<BlockId> replaces_block_id;
  std::optional<RecordId> replacement_authorization_id;
  std::optional<ReplacementLineage> replacement_lineage;
  std::array<RequestedHardwareState, 2> whole_plot_order;
  std::vector<StageACell> cells;
  AccessState access_state;
  Sha256 plan_sha256;
  json::Value source_document;
};

struct FailureRecord {
  ProtocolVersion schema_version;
  ProtocolVersion protocol_version;
  RecordId failure_record_id;
  PlatformId platform_id;
  Stage stage;
  FailureScope scope;
  std::optional<RunId> run_id;
  std::optional<BlockId> block_id;
  std::optional<BuildId> build_id;
  FailureCategory category;
  DetectedPhase detected_phase;
  std::string observed_at_utc;
  std::string description;
  bool invalidates_run;
  BlockConsequence block_consequence;
  ResolutionStatus resolution_status;
  std::optional<RecordId> replacement_authorization_id;
  std::optional<BlockId> replacement_block_id;
  std::optional<RecordId> supersedes_id;
  std::vector<ArtifactReference> evidence_refs;
  Sha256 record_sha256;
  json::Value source_document;
};

struct H3Candidate {
  QueuePackage package;
  RequestedHardwareState requested_hardware_state;
};

struct Authority {
  AuthorityId authority_id;
  AuthorityRole role;
  std::string attestation;
  std::optional<ArtifactId> signature_artifact_id;
};

struct AccessInputArtifact {
  ArtifactReference artifact;
  AccessClass access_class;
};

struct ReplacementAuthorization {
  BlockId original_block_id;
  BlockId replacement_block_id;
  std::uint64_t replacement_block_ordinal;
  BlockRole block_role;
  NamespaceId replacement_seed_subspace_id;
  RecordId failure_record_id;
  RecordId replacement_budget_record_id;
};

struct FreezeRecord {
  ProtocolVersion schema_version;
  ProtocolVersion protocol_version;
  RecordId record_id;
  RecordKind record_kind;
  std::string decision_id;
  ReadinessBoundary readiness_boundary;
  FreezeStatus status;
  AuthorizationStatus authorization_status;
  std::string created_at_utc;
  Authority authority;
  std::optional<json::Value> decision_value;
  std::optional<std::string> rationale;
  AccessState access_state_before;
  AccessState access_state_after;
  bool outcome_access_prohibited;
  std::vector<BlockId> affected_block_ids;
  std::map<H3Context, H3Candidate> h3_selections;
  std::vector<ArtifactReference> training_input_artifacts;
  std::optional<std::string> selection_rule_version;
  std::optional<Sha256> selection_record_checksum_sha256;
  std::optional<ArtifactReference> selection_record_ref;
  std::optional<NamespaceId> validation_namespace_id;
  std::optional<ArtifactReference> validation_artifact_ref;
  std::optional<ArtifactReference> validation_unseal_record_ref;
  std::optional<ArtifactReference> h3_evaluation_artifact_ref;
  std::optional<ArtifactReference> h3_access_record_ref;
  std::optional<ReplacementAuthorization> replacement;
  std::optional<RecordId> supersedes_id;
  std::optional<std::string> prior_protocol_version;
  std::optional<std::string> new_protocol_version;
  std::vector<std::string> affected_documents;
  std::vector<std::string> affected_schema_ids;
  std::vector<std::string> affected_estimands;
  std::vector<std::string> affected_contrast_ids;
  std::optional<std::string> pilot_record_disposition;
  std::vector<ArtifactReference> prior_authoritative_hashes;
  std::vector<AccessInputArtifact> input_artifacts;
  Sha256 record_sha256;
  json::Value source_document;
};

struct AmendmentRecord {
  RecordId record_id;
  RecordId supersedes_id;
  std::string prior_protocol_version;
  std::string new_protocol_version;
  std::vector<std::string> affected_documents;
  std::vector<std::string> affected_schema_ids;
  std::vector<std::string> affected_estimands;
  std::vector<std::string> affected_contrast_ids;
  std::vector<ArtifactReference> prior_authoritative_hashes;
  Sha256 record_sha256;
};

struct PlatformCpu {
  std::string vendor;
  std::string model;
  std::string stepping;
  std::string microcode;
  std::uint64_t cache_line_bytes;
  std::uint64_t atomic_width_bits;
  std::uint64_t atomic_alignment_bytes;
};

struct PlatformTopology {
  std::uint64_t sockets;
  std::uint64_t numa_nodes;
  std::uint64_t physical_cores;
  bool smt_enabled;
  std::vector<std::string> cache_domains;
  std::array<std::uint64_t, 2> near_core_pair;
  std::array<std::uint64_t, 2> far_core_pair;
};

struct PlatformMemory {
  std::string population;
  std::uint64_t base_page_bytes;
  std::string residency_verification_method;
};

struct PlatformSoftware {
  std::string operating_system;
  std::string kernel;
  std::string compiler;
  std::string standard_library;
  std::string language_standard;
  std::vector<std::string> flags;
  std::string link_mode;
};

struct PlatformClock {
  std::string source;
  std::string time_unit;
  RecordId conversion_record_id;
  RecordId serialization_record_id;
  RecordId acceptance_record_id;
};

struct PlatformRecord {
  ProtocolVersion schema_version;
  ProtocolVersion protocol_version;
  PlatformId platform_id;
  PlatformCpu cpu;
  PlatformTopology topology;
  PlatformMemory memory;
  PlatformSoftware software;
  PlatformClock clock;
  std::vector<RequestedAndVerifiedHardwareState> hardware_prefetch_states;
  Sha256 record_sha256;
  json::Value source_document;
};

using ProtocolRecord =
    std::variant<PlatformRecord, ScheduleRecord, RawObservationEnvelope, RunManifest,
                 BlockPlan, FailureRecord, FreezeRecord>;

enum class DocumentKind : std::uint8_t {
  platform,
  schedule,
  raw_observation,
  run_manifest,
  block_plan,
  failure_record,
  freeze_record,
};

[[nodiscard]] auto load_document(DocumentKind kind, std::string_view json_text)
    -> Result<ProtocolRecord>;
[[nodiscard]] auto load_document(DocumentKind kind, const json::Value& document)
    -> Result<ProtocolRecord>;
[[nodiscard]] auto amendment_view(const FreezeRecord& record)
    -> Result<AmendmentRecord>;

// The returned value is the immutable parsed source document. Serializers use
// it so unknown lossless representation details are retained without inventing
// defaults. Compatibility remains fail-closed at the loader boundary.
[[nodiscard]] auto source_document(const ProtocolRecord& record) -> const json::Value&;

class SemanticValidator {
public:
  virtual ~SemanticValidator() = default;
  [[nodiscard]] virtual auto validate(const ProtocolRecord& record) const
      -> std::vector<ValidationError> = 0;
};

class Stage4SemanticValidator final : public SemanticValidator {
public:
  [[nodiscard]] auto validate(const ProtocolRecord& record) const
      -> std::vector<ValidationError> override;
};

struct SemanticRecordSet {
  std::span<const ProtocolRecord> records;
};

// Later stages implement this interface once immutable artifact lookup and
// append-only lineage stores exist. Stage 4 intentionally does not pretend that
// record-local evidence can prove cross-record hashes, chronology, or custody.
class CrossRecordSemanticValidator {
public:
  virtual ~CrossRecordSemanticValidator() = default;
  [[nodiscard]] virtual auto validate(const SemanticRecordSet& records) const
      -> std::vector<ValidationError> = 0;
};

class ScientificConfiguration {
public:
  [[nodiscard]] static auto load(DocumentKind kind, std::string_view text)
      -> Result<ScientificConfiguration>;

  ScientificConfiguration(const ScientificConfiguration&) = default;
  ScientificConfiguration(ScientificConfiguration&&) noexcept = default;
  auto operator=(const ScientificConfiguration&) -> ScientificConfiguration& = delete;
  auto operator=(ScientificConfiguration&&) -> ScientificConfiguration& = delete;

  [[nodiscard]] auto record() const noexcept -> const ProtocolRecord& {
    return record_;
  }

private:
  explicit ScientificConfiguration(ProtocolRecord record)
      : record_(std::move(record)) {}
  ProtocolRecord record_;
};

} // namespace cpu_prefetch::protocol

#endif
