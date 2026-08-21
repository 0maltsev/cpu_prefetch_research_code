#ifndef CPU_PREFETCH_ORCHESTRATION_BLOCK_PLANNING_HPP
#define CPU_PREFETCH_ORCHESTRATION_BLOCK_PLANNING_HPP

#include "cpu_prefetch/protocol/model.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <tuple>
#include <vector>

namespace cpu_prefetch::orchestration {

inline constexpr std::size_t kStageACellsPerBlock = 180U;
inline constexpr std::size_t kStageACellsPerWholePlot = 90U;
inline constexpr std::size_t kArrivalSeedCountPerBlock = 18U;
inline constexpr std::size_t kArenaSeedCountPerBlock = 6U;
inline constexpr std::string_view kBlockPermutationSuite =
    "STAGE-A-BLOCK-PHILOX-FISHER-YATES-v1";
inline constexpr std::string_view kBlockPlanHashSuite =
    "BLOCK-PLAN-JCS-I64-ZEROSELF-SHA256-v1";

struct RoleNamespaceBinding final {
  protocol::BlockRole role;
  protocol::NamespaceId namespace_id;
  protocol::NamespaceId parent_namespace_id;
};

struct RoleNamespaceRegistry final {
  protocol::NamespaceId common_stage_a_namespace_id;
  std::vector<RoleNamespaceBinding> role_bindings;
};

// All values are prospective inputs. The planner never creates seed values or
// infers membership from an identifier's spelling.
struct BlockSeedCatalog final {
  protocol::BlockRole role;
  protocol::NamespaceId role_namespace_id;
  protocol::NamespaceId block_subspace_id;
  protocol::ArtifactReference derivation_artifact;
  workload::PhiloxKey whole_plot_key;
  workload::PhiloxKey h0_cell_order_key;
  workload::PhiloxKey h1_cell_order_key;
  std::vector<protocol::SeedId> arrival_seed_ids;
  std::vector<protocol::SeedId> node_seed_ids;
  std::vector<protocol::SeedId> event_seed_ids;
};

struct ReplacementPlanInput final {
  protocol::BlockId replaced_block_id;
  protocol::RecordId replacement_authorization_id;
  std::uint64_t replaced_block_ordinal;
  protocol::BlockRole replaced_block_role;
  protocol::NamespaceId replaced_seed_subspace_id;
};

struct BlockGenerationInput final {
  protocol::PlatformId platform_id;
  protocol::BuildId build_id;
  protocol::BlockRole role;
  std::uint64_t block_ordinal;
  BlockSeedCatalog seeds;
  std::optional<ReplacementPlanInput> replacement;
};

struct GeneratedBlockPlan final {
  protocol::BlockPlan plan;
  std::string canonical_json;
};

[[nodiscard]] auto expected_stage_a_cells() -> std::vector<
    std::tuple<protocol::QueuePackage, protocol::RequestedHardwareState,
               protocol::Placement, protocol::WorkingSetClass, protocol::LoadLevel>>;

[[nodiscard]] auto make_block_id(const protocol::PlatformId& platform_id,
                                 const protocol::BuildId& build_id,
                                 protocol::BlockRole role, std::uint64_t block_ordinal)
    -> protocol::Result<protocol::BlockId>;

[[nodiscard]] auto validate_role_namespaces(const RoleNamespaceRegistry& registry)
    -> std::vector<protocol::ValidationError>;

[[nodiscard]] auto validate_seed_catalog(const BlockSeedCatalog& catalog,
                                         const RoleNamespaceRegistry& registry)
    -> std::vector<protocol::ValidationError>;

[[nodiscard]] auto generate_block_plan(const BlockGenerationInput& input,
                                       const RoleNamespaceRegistry& registry)
    -> protocol::Result<GeneratedBlockPlan>;

[[nodiscard]] auto validate_block_plan(const protocol::BlockPlan& block,
                                       const BlockSeedCatalog& seeds,
                                       const RoleNamespaceRegistry& registry)
    -> std::vector<protocol::ValidationError>;

[[nodiscard]] auto validate_block_pool(std::span<const protocol::BlockPlan> blocks,
                                       std::span<const BlockSeedCatalog> seed_catalogs,
                                       const RoleNamespaceRegistry& registry,
                                       std::uint64_t expected_train_blocks,
                                       std::uint64_t expected_validation_blocks,
                                       std::uint64_t expected_supplemental_blocks)
    -> std::vector<protocol::ValidationError>;

} // namespace cpu_prefetch::orchestration

#endif // CPU_PREFETCH_ORCHESTRATION_BLOCK_PLANNING_HPP
