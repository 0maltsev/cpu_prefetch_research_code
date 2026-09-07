#ifndef CPU_PREFETCH_ORCHESTRATION_ACCESS_HPP
#define CPU_PREFETCH_ORCHESTRATION_ACCESS_HPP

#include "cpu_prefetch/orchestration/block_planning.hpp"
#include "cpu_prefetch/orchestration/precision.hpp"
#include "cpu_prefetch/protocol/model.hpp"

#include <cstdint>
#include <optional>
#include <span>
#include <vector>

namespace cpu_prefetch::orchestration {

enum class AccessPrincipalRole : std::uint8_t {
  freeze_authority,
  custodian,
  training_analyst,
  validation_authority,
  confirmatory_analyst,
  replacement_authority,
};

enum class OutcomeDomain : std::uint8_t {
  h3_training,
  h3_validation,
  h1h2,
};

struct PrincipalAssignment final {
  AccessPrincipalRole role;
  protocol::AuthorityId authority_id;
};

struct RoleOverlapAuthorization final {
  AccessPrincipalRole first;
  AccessPrincipalRole second;
  protocol::AuthorityId authority_id;
  protocol::ArtifactReference authorization_artifact;
};

struct AuthorityPolicy final {
  std::vector<PrincipalAssignment> assignments;
  std::vector<RoleOverlapAuthorization> permitted_overlaps;
};

struct ArtifactAccessRecord final {
  protocol::ArtifactReference artifact;
  protocol::AccessClass access_class;
  std::optional<protocol::BlockId> block_id;
  std::optional<protocol::NamespaceId> namespace_id;
  std::optional<protocol::BlockRole> block_role;
  std::optional<AccessPrincipalRole> issuing_role;
  std::optional<protocol::AuthorityId> issuer_id;
};

struct ReplacementBudget final {
  protocol::PlatformId platform_id;
  std::uint64_t maximum_replacement_blocks;
  protocol::ArtifactReference budget_artifact;
};

enum class ReplacementDecisionState : std::uint8_t {
  authorized,
  study_unresolved,
};

struct ReplacementDecision final {
  ReplacementDecisionState state;
  std::optional<GeneratedBlockPlan> replacement_plan;
  std::vector<std::string> blockers;
};

struct ReplacementRequest final {
  const protocol::BlockPlan& replaced_block;
  const protocol::RunManifest& invalid_run;
  const protocol::FailureRecord& failure;
  const protocol::FreezeRecord& authorization;
  BlockGenerationInput replacement_input;
};

struct AccessRequest final {
  protocol::AuthorityId actor_id;
  AccessPrincipalRole actor_role;
  OutcomeDomain domain;
  protocol::BlockId block_id;
};

struct AccessLedgerResult final {
  protocol::AccessState final_state;
  std::vector<protocol::ValidationError> errors;
};

[[nodiscard]] auto
validate_authority_policy(const AuthorityPolicy& policy,
                          std::span<const ArtifactAccessRecord> artifacts)
    -> std::vector<protocol::ValidationError>;

[[nodiscard]] auto
validate_access_ledger(std::span<const protocol::BlockPlan> blocks,
                       std::span<const protocol::FreezeRecord> records,
                       std::span<const ArtifactAccessRecord> artifacts,
                       const RoleNamespaceRegistry& namespaces,
                       const AuthorityPolicy& authorities) -> AccessLedgerResult;

[[nodiscard]] auto authorize_outcome_access(const AccessLedgerResult& ledger,
                                            std::span<const protocol::BlockPlan> blocks,
                                            const AuthorityPolicy& authorities,
                                            const AccessRequest& request)
    -> protocol::Result<bool>;

[[nodiscard]] auto
decide_complete_block_replacement(const ReplacementRequest& request,
                                  std::span<const protocol::BlockPlan> existing_blocks,
                                  const ReplacementBudget& budget,
                                  const RoleNamespaceRegistry& namespaces)
    -> protocol::Result<ReplacementDecision>;

class Stage14CrossRecordSemanticValidator final
    : public protocol::CrossRecordSemanticValidator {
public:
  Stage14CrossRecordSemanticValidator(
      const RoleNamespaceRegistry& namespaces,
      std::span<const BlockSeedCatalog> seed_catalogs,
      std::span<const ArtifactAccessRecord> artifacts,
      const AuthorityPolicy& authorities,
      const std::optional<PrecisionResult>& precision,
      const std::optional<ReplacementBudget>& replacement_budget)
      : namespaces_(namespaces), seed_catalogs_(seed_catalogs), artifacts_(artifacts),
        authorities_(authorities), precision_(precision),
        replacement_budget_(replacement_budget) {}

  [[nodiscard]] auto validate(const protocol::SemanticRecordSet& records) const
      -> std::vector<protocol::ValidationError> override;

private:
  const RoleNamespaceRegistry& namespaces_;
  std::span<const BlockSeedCatalog> seed_catalogs_;
  std::span<const ArtifactAccessRecord> artifacts_;
  const AuthorityPolicy& authorities_;
  const std::optional<PrecisionResult>& precision_;
  const std::optional<ReplacementBudget>& replacement_budget_;
};

} // namespace cpu_prefetch::orchestration

#endif // CPU_PREFETCH_ORCHESTRATION_ACCESS_HPP
