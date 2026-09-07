#include "cpu_prefetch/orchestration/block_planning.hpp"

#include <algorithm>
#include <array>
#include <limits>
#include <map>
#include <set>
#include <tuple>
#include <utility>

namespace cpu_prefetch::orchestration {
namespace {

using CellKey =
    std::tuple<protocol::QueuePackage, protocol::RequestedHardwareState,
               protocol::Placement, protocol::WorkingSetClass, protocol::LoadLevel>;
using WithinPlotKey = std::tuple<protocol::QueuePackage, protocol::Placement,
                                 protocol::WorkingSetClass, protocol::LoadLevel>;

void add(std::vector<protocol::ValidationError>& errors,
         protocol::ErrorCategory category, std::string path, std::string rule,
         std::string message) {
  errors.push_back({category, std::move(path), std::move(rule), std::move(message)});
}

template <typename T>
[[nodiscard]] auto fail(protocol::ErrorCategory category, std::string path,
                        std::string rule, std::string message) -> protocol::Result<T> {
  return protocol::Result<T>::failure(
      {category, std::move(path), std::move(rule), std::move(message)});
}

[[nodiscard]] auto opaque(std::string_view value) noexcept -> bool {
  return !value.empty() && value.find('/') == std::string_view::npos &&
         value.find('\\') == std::string_view::npos;
}

[[nodiscard]] auto role_name(protocol::BlockRole role) -> std::string_view {
  switch (role) {
  case protocol::BlockRole::h3_train:
    return "H3_TRAIN";
  case protocol::BlockRole::h3_validation:
    return "H3_VALIDATION";
  case protocol::BlockRole::h1h2_supplemental:
    return "H1H2_SUPPLEMENTAL";
  case protocol::BlockRole::not_applicable:
    break;
  }
  return {};
}

[[nodiscard]] auto package_name(protocol::QueuePackage package) -> std::string_view {
  switch (package) {
  case protocol::QueuePackage::r0:
    return "R0";
  case protocol::QueuePackage::r1:
    return "R1";
  case protocol::QueuePackage::r2:
    return "R2";
  case protocol::QueuePackage::l0:
    return "L0";
  case protocol::QueuePackage::l1:
    return "L1";
  case protocol::QueuePackage::nblfq_mpsc:
  case protocol::QueuePackage::not_applicable:
    break;
  }
  return {};
}

[[nodiscard]] auto hardware_name(protocol::RequestedHardwareState state)
    -> std::string_view {
  switch (state) {
  case protocol::RequestedHardwareState::h0:
    return "H0";
  case protocol::RequestedHardwareState::h1:
    return "H1";
  case protocol::RequestedHardwareState::not_applicable:
    break;
  }
  return {};
}

[[nodiscard]] auto placement_name(protocol::Placement placement) -> std::string_view {
  switch (placement) {
  case protocol::Placement::near:
    return "NEAR";
  case protocol::Placement::far:
    return "FAR";
  case protocol::Placement::stage_c_other:
  case protocol::Placement::not_applicable:
    break;
  }
  return {};
}

[[nodiscard]] auto working_set_name(protocol::WorkingSetClass working_set)
    -> std::string_view {
  switch (working_set) {
  case protocol::WorkingSetClass::l2_resident:
    return "L2_RESIDENT";
  case protocol::WorkingSetClass::llc_resident:
    return "LLC_RESIDENT";
  case protocol::WorkingSetClass::beyond_llc:
    return "BEYOND_LLC";
  case protocol::WorkingSetClass::not_applicable:
    break;
  }
  return {};
}

[[nodiscard]] auto load_name(protocol::LoadLevel load) -> std::string_view {
  switch (load) {
  case protocol::LoadLevel::l025:
    return "L025";
  case protocol::LoadLevel::l050:
    return "L050";
  case protocol::LoadLevel::l075:
    return "L075";
  case protocol::LoadLevel::calibration_ready:
  case protocol::LoadLevel::stage_c_other:
  case protocol::LoadLevel::not_applicable:
    break;
  }
  return {};
}

[[nodiscard]] auto string_value(std::string_view value) -> protocol::json::Value {
  return protocol::json::Value(std::string(value));
}

[[nodiscard]] auto uint_value(std::uint64_t value) -> protocol::json::Value {
  return protocol::json::Value(protocol::json::Number{
      protocol::json::Number::Kind::unsigned_integer, std::to_string(value), value});
}

[[nodiscard]] auto linked(protocol::QueuePackage package) noexcept -> bool {
  return package == protocol::QueuePackage::l0 || package == protocol::QueuePackage::l1;
}

[[nodiscard]] auto placement_index(protocol::Placement placement)
    -> std::optional<std::size_t> {
  if (placement == protocol::Placement::near) {
    return 0U;
  }
  if (placement == protocol::Placement::far) {
    return 1U;
  }
  return std::nullopt;
}

[[nodiscard]] auto working_set_index(protocol::WorkingSetClass working_set)
    -> std::optional<std::size_t> {
  if (working_set == protocol::WorkingSetClass::l2_resident) {
    return 0U;
  }
  if (working_set == protocol::WorkingSetClass::llc_resident) {
    return 1U;
  }
  if (working_set == protocol::WorkingSetClass::beyond_llc) {
    return 2U;
  }
  return std::nullopt;
}

[[nodiscard]] auto load_index(protocol::LoadLevel load) -> std::optional<std::size_t> {
  if (load == protocol::LoadLevel::l025) {
    return 0U;
  }
  if (load == protocol::LoadLevel::l050) {
    return 1U;
  }
  if (load == protocol::LoadLevel::l075) {
    return 2U;
  }
  return std::nullopt;
}

[[nodiscard]] auto arena_index(protocol::Placement placement,
                               protocol::WorkingSetClass working_set)
    -> std::optional<std::size_t> {
  const auto placement_value = placement_index(placement);
  const auto working_set_value = working_set_index(working_set);
  if (!placement_value || !working_set_value) {
    return std::nullopt;
  }
  return (*placement_value * 3U) + *working_set_value;
}

[[nodiscard]] auto arrival_index(protocol::Placement placement,
                                 protocol::WorkingSetClass working_set,
                                 protocol::LoadLevel load)
    -> std::optional<std::size_t> {
  const auto arena = arena_index(placement, working_set);
  const auto load_value = load_index(load);
  if (!arena || !load_value) {
    return std::nullopt;
  }
  return (*arena * 3U) + *load_value;
}

[[nodiscard]] auto sha_from_text(std::string_view text)
    -> protocol::Result<protocol::Sha256> {
  const auto* bytes = reinterpret_cast<const std::byte*>(text.data());
  const auto digest = workload::sha256(std::span(bytes, text.size()));
  return protocol::Sha256::parse(digest.hex(), "$/sha256");
}

[[nodiscard]] auto identity_document(const protocol::PlatformId& platform_id,
                                     const protocol::BuildId& build_id,
                                     protocol::BlockRole role, std::uint64_t ordinal)
    -> protocol::json::Value {
  protocol::json::Value::Object object;
  object.emplace("block_ordinal", uint_value(ordinal));
  object.emplace("block_role", string_value(role_name(role)));
  object.emplace("build_id", string_value(build_id.value()));
  object.emplace("platform_id", string_value(platform_id.value()));
  object.emplace("protocol_version", string_value(protocol::kProtocolVersion));
  object.emplace("stage", string_value("STAGE_A"));
  return protocol::json::Value(std::move(object));
}

[[nodiscard]] auto cell_document(const protocol::StageACell& cell)
    -> protocol::json::Value {
  protocol::json::Value::Object object;
  object.emplace("arrival_seed_ref", string_value(cell.arrival_seed_ref.value()));
  object.emplace("cell_ordinal", uint_value(cell.cell_ordinal));
  object.emplace("event_seed_ref", string_value(cell.event_seed_ref.value()));
  object.emplace("load_level", string_value(load_name(cell.load_level)));
  if (cell.node_seed_ref) {
    object.emplace("node_seed_ref", string_value(cell.node_seed_ref->value()));
  } else {
    object.emplace("node_seed_ref", protocol::json::Value(nullptr));
  }
  object.emplace("package", string_value(package_name(cell.package)));
  object.emplace("placement", string_value(placement_name(cell.placement)));
  object.emplace("requested_hardware_state",
                 string_value(hardware_name(cell.requested_hardware_state)));
  object.emplace("working_set_class",
                 string_value(working_set_name(cell.working_set_class)));
  return protocol::json::Value(std::move(object));
}

[[nodiscard]] auto
block_document(const BlockGenerationInput& input, const protocol::BlockId& block_id,
               const std::array<protocol::RequestedHardwareState, 2>& whole_plot_order,
               const std::vector<protocol::StageACell>& cells,
               std::string_view plan_hash) -> protocol::json::Value {
  protocol::json::Value::Object object;
  object.emplace("access_state", string_value("PLANNED"));
  object.emplace("block_id", string_value(block_id.value()));
  object.emplace("block_ordinal", uint_value(input.block_ordinal));
  object.emplace("block_role", string_value(role_name(input.role)));
  object.emplace("build_id", string_value(input.build_id.value()));
  protocol::json::Value::Array cell_values;
  cell_values.reserve(cells.size());
  for (const auto& cell : cells) {
    cell_values.push_back(cell_document(cell));
  }
  object.emplace("cells", protocol::json::Value(std::move(cell_values)));
  object.emplace("plan_sha256", string_value(plan_hash));
  object.emplace("platform_id", string_value(input.platform_id.value()));
  object.emplace("protocol_version", string_value(protocol::kProtocolVersion));
  if (input.replacement) {
    protocol::json::Value::Object lineage;
    lineage.emplace("replaced_block_ordinal",
                    uint_value(input.replacement->replaced_block_ordinal));
    lineage.emplace("replaced_block_role",
                    string_value(role_name(input.replacement->replaced_block_role)));
    lineage.emplace("replaced_seed_subspace_id",
                    string_value(input.replacement->replaced_seed_subspace_id.value()));
    object.emplace(
        "replacement_authorization_id",
        string_value(input.replacement->replacement_authorization_id.value()));
    object.emplace("replacement_lineage", protocol::json::Value(std::move(lineage)));
    object.emplace("replaces_block_id",
                   string_value(input.replacement->replaced_block_id.value()));
  } else {
    object.emplace("replacement_authorization_id", protocol::json::Value(nullptr));
    object.emplace("replacement_lineage", protocol::json::Value(nullptr));
    object.emplace("replaces_block_id", protocol::json::Value(nullptr));
  }
  object.emplace("schema_version", string_value(protocol::kProtocolVersion));
  object.emplace("seed_subspace_id",
                 string_value(input.seeds.block_subspace_id.value()));
  object.emplace("stage", string_value("STAGE_A"));
  protocol::json::Value::Array order;
  order.push_back(string_value(hardware_name(whole_plot_order[0])));
  order.push_back(string_value(hardware_name(whole_plot_order[1])));
  object.emplace("whole_plot_order", protocol::json::Value(std::move(order)));
  return protocol::json::Value(std::move(object));
}

[[nodiscard]] auto find_binding(const RoleNamespaceRegistry& registry,
                                protocol::BlockRole role)
    -> const RoleNamespaceBinding* {
  const auto iterator = std::find_if(
      registry.role_bindings.begin(), registry.role_bindings.end(),
      [role](const RoleNamespaceBinding& binding) { return binding.role == role; });
  return iterator == registry.role_bindings.end() ? nullptr : &*iterator;
}

[[nodiscard]] auto verify_plan_hash(const protocol::BlockPlan& block) -> bool {
  const auto* source = block.source_document.as_object();
  if (source == nullptr || !source->contains("plan_sha256")) {
    return false;
  }
  auto zeroed = *source;
  zeroed["plan_sha256"] = string_value(std::string(64U, '0'));
  const auto canonical =
      protocol::json::canonicalize(protocol::json::Value(std::move(zeroed)));
  if (!canonical) {
    return false;
  }
  const auto digest = sha_from_text(canonical.value());
  return digest && digest.value() == block.plan_sha256;
}

} // namespace

auto expected_stage_a_cells() -> std::vector<CellKey> {
  constexpr std::array packages{protocol::QueuePackage::r0, protocol::QueuePackage::r1,
                                protocol::QueuePackage::r2, protocol::QueuePackage::l0,
                                protocol::QueuePackage::l1};
  constexpr std::array states{protocol::RequestedHardwareState::h0,
                              protocol::RequestedHardwareState::h1};
  constexpr std::array placements{protocol::Placement::near, protocol::Placement::far};
  constexpr std::array working_sets{protocol::WorkingSetClass::l2_resident,
                                    protocol::WorkingSetClass::llc_resident,
                                    protocol::WorkingSetClass::beyond_llc};
  constexpr std::array loads{protocol::LoadLevel::l025, protocol::LoadLevel::l050,
                             protocol::LoadLevel::l075};
  std::vector<CellKey> result;
  result.reserve(kStageACellsPerBlock);
  for (const auto package : packages) {
    for (const auto state : states) {
      for (const auto placement : placements) {
        for (const auto working_set : working_sets) {
          for (const auto load : loads) {
            result.emplace_back(package, state, placement, working_set, load);
          }
        }
      }
    }
  }
  return result;
}

auto make_block_id(const protocol::PlatformId& platform_id,
                   const protocol::BuildId& build_id, protocol::BlockRole role,
                   std::uint64_t block_ordinal) -> protocol::Result<protocol::BlockId> {
  if (!opaque(platform_id.value()) || !opaque(build_id.value()) ||
      role_name(role).empty()) {
    return fail<protocol::BlockId>(
        protocol::ErrorCategory::invalid_id, "$/block_id", "BLK-ID-FIELDS",
        "block identity fields must be opaque and Stage A compatible");
  }
  const auto canonical = protocol::json::canonicalize(
      identity_document(platform_id, build_id, role, block_ordinal));
  if (!canonical) {
    return protocol::Result<protocol::BlockId>::failure(canonical.errors());
  }
  const auto digest = sha_from_text(canonical.value());
  if (!digest) {
    return protocol::Result<protocol::BlockId>::failure(digest.errors());
  }
  return protocol::BlockId::parse("stage-a-block-" + digest.value().hex(),
                                  "$/block_id");
}

auto validate_role_namespaces(const RoleNamespaceRegistry& registry)
    -> std::vector<protocol::ValidationError> {
  std::vector<protocol::ValidationError> errors;
  if (!opaque(registry.common_stage_a_namespace_id.value())) {
    add(errors, protocol::ErrorCategory::invalid_id,
        "$/role_namespaces/common_stage_a_namespace_id", "BLK-NAMESPACE-OPAQUE",
        "common Stage A namespace must be an opaque stored identity");
  }
  constexpr std::array required{protocol::BlockRole::h3_train,
                                protocol::BlockRole::h3_validation,
                                protocol::BlockRole::h1h2_supplemental};
  std::set<protocol::BlockRole> roles;
  std::set<std::string> identifiers;
  identifiers.insert(std::string(registry.common_stage_a_namespace_id.value()));
  for (std::size_t index = 0U; index < registry.role_bindings.size(); ++index) {
    const auto& binding = registry.role_bindings[index];
    if (role_name(binding.role).empty() || !opaque(binding.namespace_id.value()) ||
        !opaque(binding.parent_namespace_id.value()) ||
        binding.parent_namespace_id != registry.common_stage_a_namespace_id) {
      add(errors, protocol::ErrorCategory::cross_field,
          "$/role_namespaces/role_bindings/" + std::to_string(index),
          "BLK-ROLE-NAMESPACE-PARENT",
          "every registered role needs an explicit distinct child of the common "
          "namespace");
    }
    if (!roles.insert(binding.role).second ||
        !identifiers.insert(std::string(binding.namespace_id.value())).second) {
      add(errors, protocol::ErrorCategory::duplicate_value,
          "$/role_namespaces/role_bindings", "BLK-ROLE-NAMESPACE-UNIQUE",
          "role and namespace bindings must be unique and nonoverlapping");
    }
  }
  for (const auto role : required) {
    if (!roles.contains(role)) {
      add(errors, protocol::ErrorCategory::missing_evidence,
          "$/role_namespaces/role_bindings", "BLK-ROLE-NAMESPACE-COMPLETE",
          "training, validation, and supplemental namespaces are all required");
    }
  }
  if (registry.role_bindings.size() != required.size()) {
    add(errors, protocol::ErrorCategory::out_of_range,
        "$/role_namespaces/role_bindings", "BLK-ROLE-NAMESPACE-EXACT",
        "the common Stage A pool has exactly three role namespaces");
  }
  return errors;
}

auto validate_seed_catalog(const BlockSeedCatalog& catalog,
                           const RoleNamespaceRegistry& registry)
    -> std::vector<protocol::ValidationError> {
  auto errors = validate_role_namespaces(registry);
  const auto* binding = find_binding(registry, catalog.role);
  if (binding == nullptr || binding->namespace_id != catalog.role_namespace_id ||
      !opaque(catalog.block_subspace_id.value()) ||
      catalog.block_subspace_id == catalog.role_namespace_id ||
      catalog.block_subspace_id == registry.common_stage_a_namespace_id) {
    add(errors, protocol::ErrorCategory::reference_mismatch, "$/seed_catalog",
        "BLK-SEED-SUBSPACE-ROLE",
        "block seed subspace must explicitly belong to its immutable role namespace");
  }
  if (!opaque(catalog.derivation_artifact.artifact_id.value())) {
    add(errors, protocol::ErrorCategory::invalid_id,
        "$/seed_catalog/derivation_artifact", "BLK-SEED-DERIVATION",
        "randomization derivation evidence must have an opaque artifact identity");
  }
  if (catalog.arrival_seed_ids.size() != kArrivalSeedCountPerBlock ||
      catalog.node_seed_ids.size() != kArenaSeedCountPerBlock ||
      catalog.event_seed_ids.size() != kArenaSeedCountPerBlock) {
    add(errors, protocol::ErrorCategory::out_of_range, "$/seed_catalog",
        "BLK-SEED-CARDINALITY",
        "a block needs 18 arrival and six node/event arena seed identities");
  }
  std::set<std::string> identifiers;
  const auto inspect = [&](const auto& values, std::string_view path) {
    for (std::size_t index = 0U; index < values.size(); ++index) {
      const auto value = values[index].value();
      if (!opaque(value)) {
        add(errors, protocol::ErrorCategory::invalid_id,
            std::string(path) + "/" + std::to_string(index), "BLK-SEED-OPAQUE",
            "seed identity must be stored and must not be interpreted as a path");
      }
      if (!identifiers.insert(std::string(value)).second) {
        add(errors, protocol::ErrorCategory::duplicate_value, std::string(path),
            "BLK-SEED-DOMAIN-SEPARATION",
            "arrival, node, and event seed identities must be domain-separated");
      }
    }
  };
  inspect(catalog.arrival_seed_ids, "$/seed_catalog/arrival_seed_ids");
  inspect(catalog.node_seed_ids, "$/seed_catalog/node_seed_ids");
  inspect(catalog.event_seed_ids, "$/seed_catalog/event_seed_ids");
  return errors;
}

auto generate_block_plan(const BlockGenerationInput& input,
                         const RoleNamespaceRegistry& registry)
    -> protocol::Result<GeneratedBlockPlan> {
  const auto seed_errors = validate_seed_catalog(input.seeds, registry);
  if (!seed_errors.empty()) {
    return protocol::Result<GeneratedBlockPlan>::failure(seed_errors);
  }
  if (input.role != input.seeds.role || !opaque(input.build_id.value())) {
    return fail<GeneratedBlockPlan>(
        protocol::ErrorCategory::reference_mismatch, "$/block_generation",
        "BLK-GENERATION-IDENTITY",
        "block role and build identity must match explicit prospective inputs");
  }
  if (input.replacement && input.replacement->replaced_block_role != input.role) {
    return fail<GeneratedBlockPlan>(
        protocol::ErrorCategory::cross_field, "$/replacement", "BLK-ROLE-IMMUTABLE",
        "replacement must preserve the original block role");
  }
  const auto block_id =
      make_block_id(input.platform_id, input.build_id, input.role, input.block_ordinal);
  if (!block_id) {
    return protocol::Result<GeneratedBlockPlan>::failure(block_id.errors());
  }
  if (input.replacement && input.replacement->replaced_block_id == block_id.value()) {
    return fail<GeneratedBlockPlan>(
        protocol::ErrorCategory::cross_field, "$/replacement/replaced_block_id",
        "BLK-REPLACEMENT-NEW-ID", "replacement block identity must be new");
  }

  const workload::DeterministicStream whole_plot_stream(input.seeds.whole_plot_key);
  const workload::DeterministicStream h0_stream(input.seeds.h0_cell_order_key);
  const workload::DeterministicStream h1_stream(input.seeds.h1_cell_order_key);
  const auto whole_plot_permutation = workload::make_permutation(2U, whole_plot_stream);
  std::array<protocol::RequestedHardwareState, 2> whole_plot_order{};
  constexpr std::array states{protocol::RequestedHardwareState::h0,
                              protocol::RequestedHardwareState::h1};
  for (std::size_t index = 0U; index < whole_plot_order.size(); ++index) {
    whole_plot_order[index] = states[whole_plot_permutation[index]];
  }

  constexpr std::array packages{protocol::QueuePackage::r0, protocol::QueuePackage::r1,
                                protocol::QueuePackage::r2, protocol::QueuePackage::l0,
                                protocol::QueuePackage::l1};
  constexpr std::array placements{protocol::Placement::near, protocol::Placement::far};
  constexpr std::array working_sets{protocol::WorkingSetClass::l2_resident,
                                    protocol::WorkingSetClass::llc_resident,
                                    protocol::WorkingSetClass::beyond_llc};
  constexpr std::array loads{protocol::LoadLevel::l025, protocol::LoadLevel::l050,
                             protocol::LoadLevel::l075};
  std::vector<WithinPlotKey> base;
  base.reserve(kStageACellsPerWholePlot);
  for (const auto package : packages) {
    for (const auto placement : placements) {
      for (const auto working_set : working_sets) {
        for (const auto load : loads) {
          base.emplace_back(package, placement, working_set, load);
        }
      }
    }
  }
  const auto h0_order = workload::make_permutation(base.size(), h0_stream);
  const auto h1_order = workload::make_permutation(base.size(), h1_stream);
  std::vector<protocol::StageACell> cells;
  cells.reserve(kStageACellsPerBlock);
  for (const auto state : whole_plot_order) {
    const auto& order =
        state == protocol::RequestedHardwareState::h0 ? h0_order : h1_order;
    for (const auto selected : order) {
      const auto& [package, placement, working_set, load] = base[selected];
      const auto arrival = arrival_index(placement, working_set, load);
      const auto arena = arena_index(placement, working_set);
      if (!arrival || !arena) {
        return fail<GeneratedBlockPlan>(
            protocol::ErrorCategory::cross_field, "$/cells", "BLK-FACTOR-INDEX",
            "registered factor could not map to its seed domain");
      }
      std::optional<protocol::SeedId> node;
      if (linked(package)) {
        node = input.seeds.node_seed_ids[*arena];
      }
      cells.push_back({static_cast<std::uint64_t>(cells.size()), package, state,
                       placement, working_set, load,
                       input.seeds.arrival_seed_ids[*arrival], std::move(node),
                       input.seeds.event_seed_ids[*arena]});
    }
  }

  const auto zero_document = block_document(input, block_id.value(), whole_plot_order,
                                            cells, std::string(64U, '0'));
  const auto zero_canonical = protocol::json::canonicalize(zero_document);
  if (!zero_canonical) {
    return protocol::Result<GeneratedBlockPlan>::failure(zero_canonical.errors());
  }
  const auto plan_hash = sha_from_text(zero_canonical.value());
  if (!plan_hash) {
    return protocol::Result<GeneratedBlockPlan>::failure(plan_hash.errors());
  }
  const auto final_document = block_document(input, block_id.value(), whole_plot_order,
                                             cells, plan_hash.value().hex());
  const auto canonical = protocol::json::canonicalize(final_document);
  if (!canonical) {
    return protocol::Result<GeneratedBlockPlan>::failure(canonical.errors());
  }
  const auto loaded =
      protocol::load_document(protocol::DocumentKind::block_plan, final_document);
  if (!loaded) {
    return protocol::Result<GeneratedBlockPlan>::failure(loaded.errors());
  }
  const auto* plan = std::get_if<protocol::BlockPlan>(&loaded.value());
  if (plan == nullptr) {
    return fail<GeneratedBlockPlan>(
        protocol::ErrorCategory::invalid_type, "$/block_plan", "BLK-GENERATION-TYPE",
        "generated document did not decode as a block plan");
  }
  const auto validation = validate_block_plan(*plan, input.seeds, registry);
  if (!validation.empty()) {
    return protocol::Result<GeneratedBlockPlan>::failure(validation);
  }
  return protocol::Result<GeneratedBlockPlan>::success({*plan, canonical.value()});
}

auto validate_block_plan(const protocol::BlockPlan& block,
                         const BlockSeedCatalog& seeds,
                         const RoleNamespaceRegistry& registry)
    -> std::vector<protocol::ValidationError> {
  auto errors = validate_seed_catalog(seeds, registry);
  const protocol::Stage4SemanticValidator local;
  const auto local_errors = local.validate(protocol::ProtocolRecord{block});
  errors.insert(errors.end(), local_errors.begin(), local_errors.end());
  if (block.protocol_version != protocol::ProtocolVersion::v2_0_0_pre_2 ||
      block.schema_version != protocol::ProtocolVersion::v2_0_0_pre_2 ||
      block.stage != protocol::Stage::stage_a) {
    add(errors, protocol::ErrorCategory::unsupported_version, "$/block_plan",
        "BLK-CURRENT-STAGE-A",
        "new Stage 14 plans must use protocol 2.0.0-pre.2 and STAGE_A");
  }
  const auto expected_id = make_block_id(block.platform_id, block.build_id,
                                         block.block_role, block.block_ordinal);
  if (!expected_id || expected_id.value() != block.block_id ||
      !opaque(block.block_id.value()) || !opaque(block.build_id.value())) {
    add(errors, protocol::ErrorCategory::invalid_id, "$/block_id", "BLK-CANONICAL-ID",
        "block ID must be derived from explicit fields and never from a path");
  }
  if (block.block_role != seeds.role ||
      block.seed_subspace_id != seeds.block_subspace_id) {
    add(errors, protocol::ErrorCategory::reference_mismatch, "$/seed_subspace_id",
        "BLK-SEED-CATALOG-BINDING",
        "block role and seed subspace must match the immutable seed catalog");
  }
  if (!verify_plan_hash(block)) {
    add(errors, protocol::ErrorCategory::invalid_hash, "$/plan_sha256",
        "BLK-PLAN-ZEROSELF-HASH",
        "plan hash must match the accepted zero-self canonical record profile");
  }

  std::set<CellKey> actual;
  std::array<const protocol::StageACell*, kStageACellsPerBlock> by_ordinal{};
  for (std::size_t index = 0U; index < block.cells.size(); ++index) {
    const auto& cell = block.cells[index];
    const auto key = CellKey{cell.package, cell.requested_hardware_state,
                             cell.placement, cell.working_set_class, cell.load_level};
    if (!actual.insert(key).second) {
      add(errors, protocol::ErrorCategory::duplicate_value,
          "$/cells/" + std::to_string(index), "BLK-FACTOR-DUPLICATE",
          "each registered Stage A factor tuple must occur exactly once");
    }
    if (cell.cell_ordinal >= by_ordinal.size() ||
        (cell.cell_ordinal < by_ordinal.size() &&
         by_ordinal[static_cast<std::size_t>(cell.cell_ordinal)] != nullptr)) {
      add(errors, protocol::ErrorCategory::duplicate_value,
          "$/cells/" + std::to_string(index) + "/cell_ordinal",
          "BLK-CELL-ORDINAL-EXACT",
          "cell ordinals must be unique and exactly cover 0 through 179");
      continue;
    }
    by_ordinal[static_cast<std::size_t>(cell.cell_ordinal)] = &cell;
    const auto arrival =
        arrival_index(cell.placement, cell.working_set_class, cell.load_level);
    const auto arena = arena_index(cell.placement, cell.working_set_class);
    if (!arrival || !arena || *arrival >= seeds.arrival_seed_ids.size() ||
        *arena >= seeds.event_seed_ids.size() || *arena >= seeds.node_seed_ids.size()) {
      add(errors, protocol::ErrorCategory::unknown_enum,
          "$/cells/" + std::to_string(index), "BLK-REGISTERED-FACTORS",
          "cell contains a factor outside the registered Stage A product");
      continue;
    }
    if (cell.arrival_seed_ref != seeds.arrival_seed_ids[*arrival] ||
        cell.event_seed_ref != seeds.event_seed_ids[*arena] ||
        (linked(cell.package) &&
         (!cell.node_seed_ref || *cell.node_seed_ref != seeds.node_seed_ids[*arena])) ||
        (!linked(cell.package) && cell.node_seed_ref.has_value())) {
      add(errors, protocol::ErrorCategory::reference_mismatch,
          "$/cells/" + std::to_string(index), "BLK-SEED-SHARING",
          "arrival and persistent arena seed references must follow their "
          "role-compatible matched domains");
    }
  }
  const auto expected = expected_stage_a_cells();
  if (block.cells.size() != kStageACellsPerBlock || actual.size() != expected.size() ||
      !std::all_of(expected.begin(), expected.end(),
                   [&](const CellKey& key) { return actual.contains(key); })) {
    add(errors, protocol::ErrorCategory::cross_field, "$/cells",
        "BLK-EXACT-FACTORIAL-PROOF",
        "block must equal the complete registered 5x2x2x3x3 Cartesian product");
  }
  for (std::size_t ordinal = 0U; ordinal < by_ordinal.size(); ++ordinal) {
    if (by_ordinal[ordinal] == nullptr) {
      add(errors, protocol::ErrorCategory::missing_evidence, "$/cells",
          "BLK-CELL-ORDINAL-EXACT",
          "cell ordinals must be unique and exactly cover 0 through 179");
      break;
    }
    const auto expected_state = ordinal < kStageACellsPerWholePlot
                                    ? block.whole_plot_order[0]
                                    : block.whole_plot_order[1];
    if (by_ordinal[ordinal]->requested_hardware_state != expected_state) {
      add(errors, protocol::ErrorCategory::cross_field,
          "$/cells/" + std::to_string(ordinal), "BLK-WHOLE-PLOT-ORDER",
          "the first and second 90 logical ordinals must follow the frozen whole-plot "
          "order");
      break;
    }
  }
  for (std::size_t plot = 0U; plot < 2U; ++plot) {
    std::set<WithinPlotKey> within;
    const auto begin = plot * kStageACellsPerWholePlot;
    const auto end = begin + kStageACellsPerWholePlot;
    for (std::size_t ordinal = begin; ordinal < end; ++ordinal) {
      if (by_ordinal[ordinal] != nullptr) {
        const auto& cell = *by_ordinal[ordinal];
        within.emplace(cell.package, cell.placement, cell.working_set_class,
                       cell.load_level);
      }
    }
    if (within.size() != kStageACellsPerWholePlot) {
      add(errors, protocol::ErrorCategory::cross_field, "$/cells",
          "BLK-WHOLE-PLOT-COMPOSITION",
          "each hardware whole plot must contain all 90 package/context/load cells "
          "once");
    }
  }
  return errors;
}

auto validate_block_pool(std::span<const protocol::BlockPlan> blocks,
                         std::span<const BlockSeedCatalog> seed_catalogs,
                         const RoleNamespaceRegistry& registry,
                         std::uint64_t expected_train_blocks,
                         std::uint64_t expected_validation_blocks,
                         std::uint64_t expected_supplemental_blocks)
    -> std::vector<protocol::ValidationError> {
  std::vector<protocol::ValidationError> errors;
  std::uint64_t expected_total = expected_train_blocks;
  if (expected_total >
      std::numeric_limits<std::uint64_t>::max() - expected_validation_blocks) {
    add(errors, protocol::ErrorCategory::out_of_range, "$/block_pool",
        "BLK-POOL-COUNT-OVERFLOW", "role-count sum overflows u64");
    return errors;
  }
  expected_total += expected_validation_blocks;
  if (expected_total >
      std::numeric_limits<std::uint64_t>::max() - expected_supplemental_blocks) {
    add(errors, protocol::ErrorCategory::out_of_range, "$/block_pool",
        "BLK-POOL-COUNT-OVERFLOW", "role-count sum overflows u64");
    return errors;
  }
  expected_total += expected_supplemental_blocks;
  if (blocks.size() != expected_total || seed_catalogs.size() != blocks.size()) {
    add(errors, protocol::ErrorCategory::out_of_range, "$/block_pool",
        "BLK-POOL-EXACT-COUNT",
        "block and seed-catalog counts must equal the frozen role-count sum");
  }
  std::set<std::string> block_ids;
  std::set<std::uint64_t> ordinals;
  std::set<std::string> subspaces;
  std::set<std::string> seed_ids;
  std::map<protocol::BlockRole, std::uint64_t> roles;
  std::uint64_t h0_first = 0U;
  std::uint64_t h1_first = 0U;
  const auto count = std::min(blocks.size(), seed_catalogs.size());
  for (std::size_t index = 0U; index < count; ++index) {
    const auto block_errors =
        validate_block_plan(blocks[index], seed_catalogs[index], registry);
    errors.insert(errors.end(), block_errors.begin(), block_errors.end());
    if (!block_ids.insert(std::string(blocks[index].block_id.value())).second ||
        !ordinals.insert(blocks[index].block_ordinal).second ||
        !subspaces.insert(std::string(seed_catalogs[index].block_subspace_id.value()))
             .second) {
      add(errors, protocol::ErrorCategory::duplicate_value,
          "$/block_pool/" + std::to_string(index), "BLK-POOL-IDENTITY-UNIQUE",
          "block IDs, ordinals, and block seed subspaces must be globally unique");
    }
    ++roles[blocks[index].block_role];
    h0_first +=
        blocks[index].whole_plot_order[0] == protocol::RequestedHardwareState::h0 ? 1U
                                                                                  : 0U;
    h1_first +=
        blocks[index].whole_plot_order[0] == protocol::RequestedHardwareState::h1 ? 1U
                                                                                  : 0U;
    for (const auto* collection :
         {&seed_catalogs[index].arrival_seed_ids, &seed_catalogs[index].node_seed_ids,
          &seed_catalogs[index].event_seed_ids}) {
      for (const auto& seed : *collection) {
        if (!seed_ids.insert(std::string(seed.value())).second) {
          add(errors, protocol::ErrorCategory::duplicate_value,
              "$/block_pool/seed_catalogs", "BLK-POOL-SEED-NO-REUSE",
              "role-specific block seed identities cannot overlap across blocks");
        }
      }
    }
  }
  if (roles[protocol::BlockRole::h3_train] != expected_train_blocks ||
      roles[protocol::BlockRole::h3_validation] != expected_validation_blocks ||
      roles[protocol::BlockRole::h1h2_supplemental] != expected_supplemental_blocks) {
    add(errors, protocol::ErrorCategory::cross_field, "$/block_pool/roles",
        "BLK-POOL-ROLE-COUNTS",
        "immutable block roles must exactly equal the prospective precision counts");
  }
  const auto difference =
      h0_first > h1_first ? h0_first - h1_first : h1_first - h0_first;
  if (difference > 1U) {
    add(errors, protocol::ErrorCategory::cross_field, "$/block_pool/whole_plot_order",
        "BLK-WHOLE-PLOT-COUNTERBALANCE",
        "H0-first and H1-first whole-plot counts must differ by at most one");
  }
  return errors;
}

} // namespace cpu_prefetch::orchestration
