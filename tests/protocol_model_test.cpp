#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/protocol/model.hpp"

#include <gtest/gtest.h>

#include <array>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
#include <variant>
#include <vector>

namespace {

using cpu_prefetch::protocol::DocumentKind;
using cpu_prefetch::protocol::ErrorCategory;
using cpu_prefetch::protocol::ProtocolRecord;
using cpu_prefetch::protocol::ScientificConfiguration;
using cpu_prefetch::protocol::Stage4SemanticValidator;

constexpr std::string_view kHash =
    "0000000000000000000000000000000000000000000000000000000000000000";

auto has_rule(const std::vector<cpu_prefetch::protocol::ValidationError>& errors,
              std::string_view rule) -> bool {
  for (const auto& error : errors) {
    if (error.rule_id == rule) {
      return true;
    }
  }
  return false;
}

auto validate_semantics(const ProtocolRecord& record)
    -> std::vector<cpu_prefetch::protocol::ValidationError> {
  return Stage4SemanticValidator{}.validate(record);
}

auto schedule_json(std::string_view version = "2.0.0-pre.1",
                   std::string_view unit = "candidate_ticks",
                   std::string_view family = "POISSON_EXPONENTIAL",
                   std::string_view deadlines = "[110,120]", std::uint64_t count = 2)
    -> std::string {
  std::ostringstream output;
  output
      << R"({"schema_version":"2.0.0-pre.1","protocol_version":")" << version
      << R"(","schedule_id":"schedule","schedule_kind":"CONFIRMATORY","arrival_family":")"
      << family
      << R"(","namespace_id":"namespace","rng":{"algorithm":"fixture","version":"test-only","seed_id":"seed","derivation_record_id":"derivation","parent_namespace_id":"parent"},"time_unit":")"
      << unit
      << R"(","deadline_encoding":"ABSOLUTE_INTEGER_TICKS","origin_ticks":100,"horizon_ticks":100,"inclusion_boundary":{"start_inclusive":true,"end_exclusive":true},"offered_count":)"
      << count
      << R"(,"nominal_offered_rate":{"numerator_events":1,"denominator_ticks":10},"overflow_rule_record_id":"overflow","immutable_ordering":true,"deadline_storage":{"mode":"INLINE_TEST_ONLY","deadline_ticks":)"
      << deadlines << R"(},"decoded_deadlines_sha256":")" << kHash
      << R"(","schedule_sha256":")" << kHash << R"("})";
  return output.str();
}

auto producer_envelope(std::string_view row) -> std::string {
  std::ostringstream output;
  output
      << R"({"schema_version":"2.0.0-pre.1","protocol_version":"2.0.0-pre.1","artifact_id":"producer","run_id":"run","stream_kind":"PRODUCER","logical_row_schema_version":"2.0.0-pre.1","physical_format_record_id":"inline-test","encoding":"INLINE_TEST_JSON","time_unit":"candidate_ticks","endianness":"NOT_APPLICABLE","compression":"NONE","row_count":1,"byte_count":0,"immutable_ordering":true,"storage":{"mode":"INLINE_TEST_ONLY","inline_rows":[)"
      << row << R"(]},"integrity_artifact_ref":{"artifact_id":"integrity","sha256":")"
      << kHash << R"("},"artifact_sha256":")" << kHash << R"("})";
  return output.str();
}

auto joined_envelope(bool wrong_equation = false) -> std::string {
  std::ostringstream output;
  output
      << R"({"schema_version":"2.0.0-pre.1","protocol_version":"2.0.0-pre.1","artifact_id":"joined","run_id":"run","stream_kind":"JOINED_DERIVED","logical_row_schema_version":"2.0.0-pre.1","physical_format_record_id":"inline-test","encoding":"INLINE_TEST_JSON","time_unit":"candidate_ticks","endianness":"NOT_APPLICABLE","compression":"NONE","row_count":1,"byte_count":0,"immutable_ordering":true,"storage":{"mode":"INLINE_TEST_ONLY","inline_rows":[{"run_id":"run","accepted_ordinal":0,"logical_sequence":0,"record_index":0,"producer_row_ordinal":0,"consumer_row_ordinal":0,"scheduled_arrival":10,"producer_handle_begin":11,"record_lookup_completion":12,"enqueue_invocation":13,"enqueue_linearization":14,"enqueue_attempt_completion":15,"dequeue_invocation":15,"dequeue_linearization":16,"dequeue_completion":17,"consumer_action_completion":20,"producer_lateness":1,"pointer_lookup_interval":1,"enqueue_service_time":2,"admission_delay":4,"queue_residence":2,"dequeue_service_time":2,"post_dequeue_delivery_interval":4,"consumer_action_interval":3,"end_to_end_latency":)"
      << (wrong_equation ? 9 : 10)
      << R"(}]},"source_artifacts":[{"artifact_id":"producer","sha256":")" << kHash
      << R"("},{"artifact_id":"consumer","sha256":")" << kHash
      << R"("}],"integrity_artifact_ref":{"artifact_id":"integrity","sha256":")"
      << kHash << R"("},"artifact_sha256":")" << kHash << R"("})";
  return output.str();
}

auto manifest_json(bool early_failure, std::uint64_t full, std::uint64_t n_eff,
                   bool omit_joined = false, bool fabricate_early = false,
                   std::string_view package = "R0") -> std::string {
  const bool tail_pass = n_eff >= 200000;
  const std::string estimability = early_failure ? "BLOCKED_INVALID_RUN"
                                   : full != 0   ? "BLOCKED_ZERO_LOSS"
                                   : tail_pass   ? "ESTIMABLE"
                                                 : "BLOCKED_EFFECTIVE_TAIL";
  std::ostringstream output;
  output
      << R"({"schema_version":"2.0.0-pre.1","protocol_version":"2.0.0-pre.1","run_id":"run","platform_id":"platform","build_id":"build","within_cell_ordinal":0,"queue_provenance_id":"queue-provenance","provenance":{"paper_repository_revision":"paper","implementation_repository_revision":"implementation","build_artifact_sha256":")"
      << kHash
      << R"(","compiler_identity":"compiler","compiler_flags":[],"standard_library":"stdlib","dependency_record_id":"dependencies"},"stage":"STAGE_A","run_mode":"LATENCY","lifecycle_state":")"
      << (early_failure ? "PRE_RUN_FAILURE" : "COMPLETED")
      << R"(","block_id":"block","block_role":"H3_TRAIN","package":")" << package
      << R"(","requested_hardware_state":"H0","verified_hardware_state":"VERIFIED_DEFAULT","placement":"NEAR","working_set_class":"L2_RESIDENT","load_level":"L025","capacity_events":64,"time_unit":"candidate_ticks","schedule_refs":{"measurement":{"artifact_id":"measurement-schedule","sha256":")"
      << kHash << R"("},"warmup":{"artifact_id":"warmup-schedule","sha256":")" << kHash
      << R"("}},"seed_refs":{"arrival":"arrival","node_order":null,"event_order":"event","warmup":"warmup","derivation_record_id":"derivation"},"validity":")"
      << (early_failure ? "INVALID" : "VALID") << R"(","count_reconciliation":")"
      << (early_failure ? "NOT_EVALUATED" : "PASS") << R"(","zero_loss_status":")"
      << (early_failure ? "NOT_EVALUATED" : (full == 0 ? "PASS" : "FAIL"))
      << R"(","effective_tail_status":")"
      << (early_failure ? "NOT_EVALUATED" : (tail_pass ? "PASS" : "FAIL"))
      << R"(","confirmatory_estimability":")" << estimability
      << R"(","block_completeness":")" << (early_failure ? "INCOMPLETE" : "COMPLETE")
      << R"(","join_status":")" << (early_failure ? "NOT_ATTEMPTED" : "PASSED") << '"';
  if (!early_failure || fabricate_early) {
    const auto accepted = 10 - full;
    output << R"(,"counts":{"offered":10,"attempted":10,"accepted":)" << accepted
           << R"(,"full":)" << full << R"(,"consumed":)" << accepted
           << R"(,"final_occupancy":0,"raw_sample_count":)" << accepted
           << R"(,"n_eff_p999":)" << n_eff << '}';
  }
  if (!early_failure) {
    output
        << R"(,"integrity_evidence":{"report_artifact":{"artifact_id":"integrity","sha256":")"
        << kHash << R"("})";
    for (std::string_view name :
         {"final_consumer_rolling_checksum", "event_records_pre_checksum",
          "event_records_post_checksum", "ordered_index_checksum",
          "address_delta_checksum"}) {
      output
          << R"(,")" << name
          << R"(":{"algorithm_record_id":"algorithm","algorithm_version":"test-only","value_hex":"00"})";
    }
    output << '}';
  }
  output << R"(,"failure_record_ids":)" << (early_failure ? R"(["failure"])" : "[]")
         << R"(,"artifact_refs":[)";
  if (!early_failure || fabricate_early) {
    bool first = true;
    for (std::string_view relationship :
         {"PRODUCER_RAW", "CONSUMER_RAW", "JOIN_AUDIT", "JOINED_DERIVED",
          "PHASE_INTEGRITY_REPORT", "PROVENANCE"}) {
      if (omit_joined && relationship == "JOINED_DERIVED") {
        continue;
      }
      if (!first) {
        output << ',';
      }
      first = false;
      output << R"({"artifact_id":"artifact-)" << relationship
             << R"(","relationship":")" << relationship << R"(","sha256":")" << kHash
             << R"("})";
    }
  }
  output << R"(],"manifest_sha256":")" << kHash << R"("})";
  return output.str();
}

auto block_json(bool replacement, bool duplicate_cell = false, bool bad_lineage = false)
    -> std::string {
  std::ostringstream output;
  output
      << R"({"schema_version":"2.0.0-pre.1","protocol_version":"2.0.0-pre.1","block_id":")"
      << (replacement && !bad_lineage ? "replacement" : "original")
      << R"(","platform_id":"platform","build_id":"build","stage":"STAGE_A","block_role":"H3_TRAIN","block_ordinal":)"
      << (replacement ? 2 : 1) << R"(,"seed_subspace_id":")"
      << (replacement && !bad_lineage ? "replacement-subspace" : "original-subspace")
      << R"(","replaces_block_id":)" << (replacement ? R"("original")" : "null")
      << R"(,"replacement_authorization_id":)"
      << (replacement ? R"("authorization")" : "null") << R"(,"replacement_lineage":)";
  if (replacement) {
    output
        << R"({"replaced_block_ordinal":1,"replaced_block_role":"H3_TRAIN","replaced_seed_subspace_id":"original-subspace"})";
  } else {
    output << "null";
  }
  output << R"(,"whole_plot_order":["H0","H1"],"cells":[)";
  const std::array packages{"R0", "R1", "R2", "L0", "L1"};
  const std::array hardware{"H0", "H1"};
  const std::array placements{"NEAR", "FAR"};
  const std::array working_sets{"L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC"};
  const std::array loads{"L025", "L050", "L075"};
  std::uint64_t ordinal = 0;
  for (auto package : packages) {
    for (auto state : hardware) {
      for (auto placement : placements) {
        for (auto working_set : working_sets) {
          for (auto load : loads) {
            if (ordinal != 0) {
              output << ',';
            }
            const bool replace_last = duplicate_cell && ordinal == 179;
            output << R"({"cell_ordinal":)" << ordinal << R"(,"package":")"
                   << (replace_last ? "R0" : package)
                   << R"(","requested_hardware_state":")"
                   << (replace_last ? "H0" : state) << R"(","placement":")"
                   << (replace_last ? "NEAR" : placement)
                   << R"(","working_set_class":")"
                   << (replace_last ? "L2_RESIDENT" : working_set)
                   << R"(","load_level":")" << (replace_last ? "L025" : load)
                   << R"(","arrival_seed_ref":"arrival-)" << ordinal
                   << R"(","node_seed_ref":)";
            const bool linked = !replace_last && package[0] == 'L';
            output << (linked ? R"("node-)" + std::to_string(ordinal) + '"' : "null")
                   << R"(,"event_seed_ref":"event-)" << ordinal << R"("})";
            ++ordinal;
          }
        }
      }
    }
  }
  output << R"(],"access_state":"PLANNED","plan_sha256":")" << kHash << R"("})";
  return output.str();
}

auto unseal_json(bool empty_blocks = false, bool missing_hash = false) -> std::string {
  std::ostringstream output;
  output
      << R"({"schema_version":"2.0.0-pre.1","protocol_version":"2.0.0-pre.1","record_id":"unseal","record_kind":"VALIDATION_UNSEAL","decision_id":"decision","readiness_boundary":"BLOCKED_BEFORE_CONFIRMATORY_EXECUTION","status":"AUTHORIZED","authorization_status":"AUTHORIZED","created_at_utc":"2026-08-17T00:00:00Z","authority":{"authority_id":"custodian","role":"VALIDATION_CUSTODIAN","attestation":"fixture","signature_artifact_id":null},"access_state_before":"SELECTION_FROZEN","access_state_after":"VALIDATION_UNSEALED","affected_block_ids":)"
      << (empty_blocks ? "[]" : R"(["validation-block"])")
      << R"(,"selection_record_ref":{"artifact_id":"selection")";
  if (!missing_hash) {
    output << R"(,"sha256":")" << kHash << '"';
  }
  output
      << R"(},"validation_namespace_id":"validation-namespace","validation_artifact_ref":{"artifact_id":"validation","sha256":")"
      << kHash
      << R"("},"outcome_access_prohibited":false,"input_artifacts":[{"artifact_id":"input","sha256":")"
      << kHash << R"(","access_class":"VALIDATION_SEALED"}],"record_sha256":")" << kHash
      << R"("})";
  return output.str();
}

auto platform_json() -> std::string {
  std::ostringstream output;
  output
      << R"({"schema_version":"2.0.0-pre.1","protocol_version":"2.0.0-pre.1","platform_id":"platform","cpu":{"vendor":"fixture","model":"fixture","stepping":"fixture","microcode":"fixture","cache_line_bytes":64,"atomic_width_bits":64,"atomic_alignment_bytes":8},"topology":{"sockets":1,"numa_nodes":2,"physical_cores":4,"smt_enabled":false,"cache_domains":["domain"],"near_core_pair":[0,1],"far_core_pair":[0,2]},"memory":{"population":"fixture","base_page_bytes":4096,"residency_verification_method":"fixture"},"software":{"operating_system":"Linux","kernel":"fixture","compiler":"fixture","standard_library":"fixture","language_standard":"C++20","flags":[],"link_mode":"fixture"},"clock":{"source":"candidate-only","time_unit":"candidate_ticks","conversion_record_id":"conversion","serialization_record_id":"serialization","acceptance_record_id":"acceptance"},"hardware_prefetch_states":[{"requested":"H0","verified":"VERIFIED_DEFAULT","readback_artifact_id":"readback-h0","behavioral_probe_artifact_id":"probe-h0","privileged_authority_id":"operator"},{"requested":"H1","verified":"VERIFIED_CHANGED","readback_artifact_id":"readback-h1","behavioral_probe_artifact_id":"probe-h1","privileged_authority_id":"operator"}],"record_sha256":")"
      << kHash << R"("})";
  return output.str();
}

auto failure_json() -> std::string {
  std::ostringstream output;
  output
      << R"({"schema_version":"2.0.0-pre.1","protocol_version":"2.0.0-pre.1","failure_record_id":"failure","platform_id":"platform","stage":"STAGE_A","scope":"RUN","run_id":"run","block_id":"block","build_id":"build","category":"CORRECTNESS","detected_phase":"PRE_RUN","observed_at_utc":"2026-08-17T00:00:00Z","description":"synthetic fixture","invalidates_run":true,"block_consequence":"ORIGINAL_BLOCK_INCOMPLETE","resolution_status":"OPEN","replacement_authorization_id":null,"replacement_block_id":null,"supersedes_id":null,"evidence_refs":[{"artifact_id":"evidence","sha256":")"
      << kHash << R"("}],"record_sha256":")" << kHash << R"("})";
  return output.str();
}

TEST(JsonModel, CanonicalSerializationPreservesExactIntegersAndIsDeterministic) {
  const auto parsed = cpu_prefetch::protocol::json::parse(
      R"({"small":1e-7,"big":9007199254740993,"fixed":0.000001,"minus":-0.0})");
  ASSERT_TRUE(parsed) << parsed.errors().front().message;
  const auto canonical = cpu_prefetch::protocol::json::canonicalize(parsed.value());
  ASSERT_TRUE(canonical);
  EXPECT_EQ(canonical.value(),
            R"({"big":9007199254740993,"fixed":0.000001,"minus":0,"small":1e-7})");
  const auto reparsed = cpu_prefetch::protocol::json::parse(canonical.value());
  ASSERT_TRUE(reparsed);
  const auto second = cpu_prefetch::protocol::json::canonicalize(reparsed.value());
  ASSERT_TRUE(second);
  EXPECT_EQ(second.value(), canonical.value());
}

TEST(JsonModel, CanonicalPropertyOrderUsesUtf16CodeUnits) {
  const auto parsed =
      cpu_prefetch::protocol::json::parse("{\"\\ue000\":1,\"\\ud83d\\ude00\":2}");
  ASSERT_TRUE(parsed);
  const auto canonical = cpu_prefetch::protocol::json::canonicalize(parsed.value());
  ASSERT_TRUE(canonical) << canonical.errors().front().message;
  EXPECT_EQ(canonical.value(), "{\"😀\":2,\"\":1}");
}

TEST(JsonModel, CanonicalBinary64FormattingMatchesRfc8785Examples) {
  const auto parsed = cpu_prefetch::protocol::json::parse(
      R"({"numbers":[333333333.33333329,1E30,4.50,2e-3,0.000000000000000000000000001]})");
  ASSERT_TRUE(parsed);
  const auto canonical = cpu_prefetch::protocol::json::canonicalize(parsed.value());
  ASSERT_TRUE(canonical) << canonical.errors().front().message;
  EXPECT_EQ(canonical.value(),
            R"({"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27]})");
}

TEST(JsonModel, SharedJcsI64BoundaryFixturesPassInCpp) {
  const std::string fixture_path =
      std::string(CPU_PREFETCH_SOURCE_DIR) + "/tests/fixtures/jcs_i64_v1.json";
  std::ifstream stream(fixture_path);
  ASSERT_TRUE(stream.good());
  std::ostringstream fixture_text;
  fixture_text << stream.rdbuf();
  const auto fixture = cpu_prefetch::protocol::json::parse(fixture_text.str());
  ASSERT_TRUE(fixture);
  const auto* root = fixture.value().as_object();
  ASSERT_NE(root, nullptr);
  const auto* cases = root->at("cases").as_array();
  ASSERT_NE(cases, nullptr);
  ASSERT_FALSE(cases->empty());
  for (const auto& entry : *cases) {
    const auto* object = entry.as_object();
    ASSERT_NE(object, nullptr);
    const auto* input = object->at("input").as_string();
    const auto* expected = object->at("canonical").as_string();
    ASSERT_NE(input, nullptr);
    ASSERT_NE(expected, nullptr);
    const auto parsed = cpu_prefetch::protocol::json::parse(*input);
    ASSERT_TRUE(parsed);
    const auto canonical = cpu_prefetch::protocol::json::canonicalize(parsed.value());
    ASSERT_TRUE(canonical) << *object->at("name").as_string();
    EXPECT_EQ(canonical.value(), *expected);
  }
}

TEST(JsonModel, DuplicateObjectMembersFailClosed) {
  const auto parsed = cpu_prefetch::protocol::json::parse(R"({"x":1,"x":2})");
  ASSERT_FALSE(parsed);
  EXPECT_EQ(parsed.errors().front().category, ErrorCategory::duplicate_value);
  EXPECT_EQ(parsed.errors().front().path, "$/x");
}

TEST(Configuration, VersionEnumHashIdAndUnitErrorsAreStable) {
  auto version = cpu_prefetch::protocol::load_document(DocumentKind::schedule,
                                                       schedule_json("1.0.0-pre.1"));
  ASSERT_FALSE(version);
  EXPECT_EQ(version.errors().front().category, ErrorCategory::unsupported_version);
  EXPECT_EQ(version.errors().front().path, "$out/protocol_version");

  std::string schema_version = schedule_json();
  const auto schema_value = schema_version.find("2.0.0-pre.1");
  ASSERT_NE(schema_value, std::string::npos);
  schema_version.replace(schema_value, std::string_view("2.0.0-pre.1").size(), "3.0.0");
  version =
      cpu_prefetch::protocol::load_document(DocumentKind::schedule, schema_version);
  ASSERT_FALSE(version);
  EXPECT_EQ(version.errors().front().path, "$out/schema_version");

  std::string mixed_row_version = producer_envelope(
      R"({"run_id":"run","logical_sequence":0,"record_index":0,"scheduled_arrival":10,"producer_handle_begin":11,"record_lookup_completion":12,"enqueue_invocation":13,"enqueue_attempt_completion":15,"attempted":true,"outcome":"FULL"})");
  const std::string row_token = R"("logical_row_schema_version":"2.0.0-pre.1")";
  const auto row_version = mixed_row_version.find(row_token);
  ASSERT_NE(row_version, std::string::npos);
  mixed_row_version.replace(row_version, row_token.size(),
                            R"("logical_row_schema_version":"1.0.0")");
  auto mixed = cpu_prefetch::protocol::load_document(DocumentKind::raw_observation,
                                                     mixed_row_version);
  ASSERT_FALSE(mixed);
  EXPECT_EQ(mixed.errors().front().path, "$out/logical_row_schema_version");

  auto unknown_enum = cpu_prefetch::protocol::load_document(
      DocumentKind::run_manifest, manifest_json(true, 0, 0, false, false, "FUTURE"));
  ASSERT_FALSE(unknown_enum);
  EXPECT_EQ(unknown_enum.errors().front().category, ErrorCategory::unknown_enum);

  std::string bad_hash = schedule_json();
  bad_hash.replace(bad_hash.rfind(std::string(kHash)), kHash.size(), "abc");
  auto hash = cpu_prefetch::protocol::load_document(DocumentKind::schedule, bad_hash);
  ASSERT_FALSE(hash);
  EXPECT_EQ(hash.errors().front().category, ErrorCategory::invalid_hash);

  auto identifier = cpu_prefetch::protocol::RunId::parse("", "$out/run_id");
  ASSERT_FALSE(identifier);
  EXPECT_EQ(identifier.errors().front().category, ErrorCategory::invalid_id);

  auto unit = cpu_prefetch::protocol::load_document(DocumentKind::schedule,
                                                    schedule_json("2.0.0-pre.1", ""));
  ASSERT_FALSE(unit);
  EXPECT_EQ(unit.errors().front().category, ErrorCategory::invalid_unit);
}

TEST(Configuration, LoadedScientificConfigurationIsImmutable) {
  static_assert(!std::is_copy_assignable_v<ScientificConfiguration>);
  static_assert(!std::is_move_assignable_v<ScientificConfiguration>);
  const auto loaded =
      ScientificConfiguration::load(DocumentKind::schedule, schedule_json());
  EXPECT_TRUE(loaded) << loaded.errors().front().message;
}

TEST(Configuration, PlatformAndFailureRecordsLoadAsTypedVariants) {
  auto platform =
      cpu_prefetch::protocol::load_document(DocumentKind::platform, platform_json());
  ASSERT_TRUE(platform) << platform.errors().front().message;
  EXPECT_TRUE(
      std::holds_alternative<cpu_prefetch::protocol::PlatformRecord>(platform.value()));
  EXPECT_TRUE(validate_semantics(platform.value()).empty());

  auto failure = cpu_prefetch::protocol::load_document(DocumentKind::failure_record,
                                                       failure_json());
  ASSERT_TRUE(failure) << failure.errors().front().message;
  EXPECT_TRUE(
      std::holds_alternative<cpu_prefetch::protocol::FailureRecord>(failure.value()));
  EXPECT_TRUE(validate_semantics(failure.value()).empty());
}

TEST(ScheduleSemantics, ExactRateAndHalfOpenDecodedSchedulePass) {
  auto loaded =
      cpu_prefetch::protocol::load_document(DocumentKind::schedule, schedule_json());
  ASSERT_TRUE(loaded);
  const auto errors = validate_semantics(loaded.value());
  EXPECT_TRUE(errors.empty());
  const auto& schedule =
      std::get<cpu_prefetch::protocol::ScheduleRecord>(loaded.value());
  EXPECT_EQ(schedule.nominal_offered_rate.numerator_events, 1U);
  EXPECT_EQ(schedule.nominal_offered_rate.denominator_ticks, 10U);
}

TEST(ScheduleSemantics, CountOrderingBoundaryAndFamilyCombinationsReject) {
  auto bad_count = cpu_prefetch::protocol::load_document(
      DocumentKind::schedule, schedule_json("2.0.0-pre.1", "candidate_ticks",
                                            "POISSON_EXPONENTIAL", "[120,110]", 3));
  ASSERT_TRUE(bad_count);
  const auto errors = validate_semantics(bad_count.value());
  EXPECT_TRUE(has_rule(errors, "SCH-DECODED-COUNT"));
  EXPECT_TRUE(has_rule(errors, "SCH-NONDECREASING"));

  auto boundary = cpu_prefetch::protocol::load_document(
      DocumentKind::schedule, schedule_json("2.0.0-pre.1", "candidate_ticks",
                                            "POISSON_EXPONENTIAL", "[110,200]"));
  ASSERT_TRUE(boundary);
  EXPECT_TRUE(has_rule(validate_semantics(boundary.value()), "SCH-HALF-OPEN"));

  auto family = cpu_prefetch::protocol::load_document(
      DocumentKind::schedule,
      schedule_json("2.0.0-pre.1", "candidate_ticks", "CONTINUOUS_READY"));
  ASSERT_TRUE(family);
  EXPECT_TRUE(has_rule(validate_semantics(family.value()), "SCH-CONFIRMATORY-FAMILY"));
}

TEST(RawRecords, AcceptedAndFullProducerShapesAreIndependent) {
  const auto accepted = producer_envelope(
      R"({"run_id":"run","logical_sequence":0,"record_index":0,"scheduled_arrival":10,"producer_handle_begin":11,"record_lookup_completion":12,"enqueue_invocation":13,"enqueue_linearization":14,"enqueue_attempt_completion":15,"attempted":true,"outcome":"ACCEPTED","accepted_ordinal":0})");
  auto loaded =
      cpu_prefetch::protocol::load_document(DocumentKind::raw_observation, accepted);
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(validate_semantics(loaded.value()).empty());

  const auto full = producer_envelope(
      R"({"run_id":"run","logical_sequence":0,"record_index":0,"scheduled_arrival":10,"producer_handle_begin":11,"record_lookup_completion":12,"enqueue_invocation":13,"enqueue_attempt_completion":15,"attempted":true,"outcome":"FULL"})");
  loaded = cpu_prefetch::protocol::load_document(DocumentKind::raw_observation, full);
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(validate_semantics(loaded.value()).empty());

  const auto fabricated = producer_envelope(
      R"({"run_id":"run","logical_sequence":0,"record_index":0,"scheduled_arrival":10,"producer_handle_begin":11,"record_lookup_completion":12,"enqueue_invocation":13,"enqueue_linearization":14,"enqueue_attempt_completion":15,"attempted":true,"outcome":"FULL","accepted_ordinal":0})");
  loaded =
      cpu_prefetch::protocol::load_document(DocumentKind::raw_observation, fabricated);
  ASSERT_FALSE(loaded);
  EXPECT_EQ(loaded.errors().front().rule_id, "RAW-FULL-FIELDS");
}

TEST(RawRecords, JoinedTimestampsAndEveryDerivedEquationAreChecked) {
  auto loaded = cpu_prefetch::protocol::load_document(DocumentKind::raw_observation,
                                                      joined_envelope());
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(validate_semantics(loaded.value()).empty());
  loaded = cpu_prefetch::protocol::load_document(DocumentKind::raw_observation,
                                                 joined_envelope(true));
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(has_rule(validate_semantics(loaded.value()), "TIM-EQ-END-TO-END"));
}

TEST(ManifestSemantics, PartialInvalidManifestDoesNotFabricateArtifacts) {
  auto loaded = cpu_prefetch::protocol::load_document(DocumentKind::run_manifest,
                                                      manifest_json(true, 0, 0));
  ASSERT_TRUE(loaded) << loaded.errors().front().message;
  EXPECT_TRUE(validate_semantics(loaded.value()).empty());

  loaded = cpu_prefetch::protocol::load_document(
      DocumentKind::run_manifest, manifest_json(true, 0, 0, false, true));
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(has_rule(validate_semantics(loaded.value()), "LIF-NO-FABRICATION"));
}

TEST(ManifestSemantics, ValidFullFailsZeroLossWithoutBecomingInvalid) {
  const auto fixture = manifest_json(false, 1, 200000);
  auto loaded =
      cpu_prefetch::protocol::load_document(DocumentKind::run_manifest, fixture);
  ASSERT_TRUE(loaded) << loaded.errors().front().message << '\n' << fixture;
  EXPECT_TRUE(validate_semantics(loaded.value()).empty());
  const auto& manifest = std::get<cpu_prefetch::protocol::RunManifest>(loaded.value());
  EXPECT_EQ(manifest.validity, cpu_prefetch::protocol::RunValidity::valid);
  EXPECT_EQ(manifest.zero_loss_status, cpu_prefetch::protocol::GateStatus::fail);
}

TEST(ManifestSemantics, ValidLowEffectiveCountFailsTailEstimabilityWithoutInvalidity) {
  auto loaded = cpu_prefetch::protocol::load_document(DocumentKind::run_manifest,
                                                      manifest_json(false, 0, 199999));
  ASSERT_TRUE(loaded) << loaded.errors().front().message;
  EXPECT_TRUE(validate_semantics(loaded.value()).empty());
  const auto& manifest = std::get<cpu_prefetch::protocol::RunManifest>(loaded.value());
  EXPECT_EQ(manifest.validity, cpu_prefetch::protocol::RunValidity::valid);
  EXPECT_EQ(manifest.effective_tail_status, cpu_prefetch::protocol::GateStatus::fail);
}

TEST(ManifestSemantics, SimultaneousGateFailuresDoNotInventReasonPrecedence) {
  auto blocked_zero = manifest_json(false, 1, 199999);
  auto loaded =
      cpu_prefetch::protocol::load_document(DocumentKind::run_manifest, blocked_zero);
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(validate_semantics(loaded.value()).empty());

  const auto reason = blocked_zero.find("BLOCKED_ZERO_LOSS");
  ASSERT_NE(reason, std::string::npos);
  blocked_zero.replace(reason, std::string_view("BLOCKED_ZERO_LOSS").size(),
                       "BLOCKED_EFFECTIVE_TAIL");
  loaded =
      cpu_prefetch::protocol::load_document(DocumentKind::run_manifest, blocked_zero);
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(validate_semantics(loaded.value()).empty());

  const auto tail_reason = blocked_zero.find("BLOCKED_EFFECTIVE_TAIL");
  ASSERT_NE(tail_reason, std::string::npos);
  blocked_zero.replace(tail_reason, std::string_view("BLOCKED_EFFECTIVE_TAIL").size(),
                       "ESTIMABLE");
  loaded =
      cpu_prefetch::protocol::load_document(DocumentKind::run_manifest, blocked_zero);
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(
      has_rule(validate_semantics(loaded.value()), "LIF-ESTIMABILITY-APPLICABILITY"));
}

TEST(ManifestSemantics, CompletedValidRunMissingEvidenceRejects) {
  auto loaded = cpu_prefetch::protocol::load_document(
      DocumentKind::run_manifest, manifest_json(false, 0, 200000, true));
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(has_rule(validate_semantics(loaded.value()), "LIF-COMPLETED-ARTIFACTS"));
}

TEST(BlockSemantics, OriginalAndReplacementBlocksPassExactProduct) {
  for (const bool replacement : {false, true}) {
    auto loaded = cpu_prefetch::protocol::load_document(DocumentKind::block_plan,
                                                        block_json(replacement));
    ASSERT_TRUE(loaded) << loaded.errors().front().message;
    EXPECT_TRUE(validate_semantics(loaded.value()).empty());
  }
}

TEST(BlockSemantics, DuplicateFactorCellAndInvalidReplacementLineageReject) {
  auto loaded = cpu_prefetch::protocol::load_document(DocumentKind::block_plan,
                                                      block_json(false, true));
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(has_rule(validate_semantics(loaded.value()), "BLK-FACTORIAL-PRODUCT"));

  loaded = cpu_prefetch::protocol::load_document(DocumentKind::block_plan,
                                                 block_json(true, false, true));
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(has_rule(validate_semantics(loaded.value()), "BLK-REPLACEMENT-LINEAGE"));
}

TEST(FreezeSemantics, ValidationUnsealRequiresHashesAndAffectedBlocks) {
  auto loaded =
      cpu_prefetch::protocol::load_document(DocumentKind::freeze_record, unseal_json());
  ASSERT_TRUE(loaded) << loaded.errors().front().message;
  EXPECT_TRUE(validate_semantics(loaded.value()).empty());

  loaded = cpu_prefetch::protocol::load_document(DocumentKind::freeze_record,
                                                 unseal_json(true));
  ASSERT_TRUE(loaded);
  EXPECT_TRUE(has_rule(validate_semantics(loaded.value()), "ACC-AFFECTED-BLOCKS"));

  loaded = cpu_prefetch::protocol::load_document(DocumentKind::freeze_record,
                                                 unseal_json(false, true));
  ASSERT_FALSE(loaded);
  EXPECT_EQ(loaded.errors().front().path, "$out/selection_record_ref/sha256");
}

TEST(FreezeSemantics, DuplicateH3ContextKeyFailsAtParsingBoundary) {
  const std::string duplicate =
      R"({"schema_version":"2.0.0-pre.1","protocol_version":"2.0.0-pre.1","record_id":"selection","record_kind":"SELECTION_FREEZE","decision_id":"decision","readiness_boundary":"BLOCKED_BEFORE_CONFIRMATORY_EXECUTION","status":"FROZEN","authorization_status":"AUTHORIZED","created_at_utc":"2026-08-17T00:00:00Z","authority":{"authority_id":"owner","role":"FREEZE_AUTHORITY","attestation":"fixture"},"access_state_before":"TRAINING_OPEN","access_state_after":"SELECTION_FROZEN","outcome_access_prohibited":true,"input_artifacts":[{"artifact_id":"input","sha256":"0000000000000000000000000000000000000000000000000000000000000000","access_class":"TRAINING_ONLY"}],"affected_block_ids":["block"],"h3_selections":{"NEAR_L2_L050":{"package":"R0","requested_hardware_state":"H0"},"NEAR_L2_L050":{"package":"R1","requested_hardware_state":"H1"}},"training_input_artifacts":[{"artifact_id":"training","sha256":"0000000000000000000000000000000000000000000000000000000000000000"}],"selection_rule_version":"2.0.0-pre.1","selection_record_checksum_sha256":"0000000000000000000000000000000000000000000000000000000000000000","record_sha256":"0000000000000000000000000000000000000000000000000000000000000000"})";
  const auto loaded =
      cpu_prefetch::protocol::load_document(DocumentKind::freeze_record, duplicate);
  ASSERT_FALSE(loaded);
  EXPECT_EQ(loaded.errors().front().category, ErrorCategory::duplicate_value);
}

TEST(RoundTrip, TypedSourceDocumentCanonicalRoundTripLosesNoInformation) {
  const auto loaded =
      cpu_prefetch::protocol::load_document(DocumentKind::schedule, schedule_json());
  ASSERT_TRUE(loaded);
  const auto first = cpu_prefetch::protocol::json::canonicalize(
      cpu_prefetch::protocol::source_document(loaded.value()));
  ASSERT_TRUE(first);
  const auto reloaded =
      cpu_prefetch::protocol::load_document(DocumentKind::schedule, first.value());
  ASSERT_TRUE(reloaded);
  const auto second = cpu_prefetch::protocol::json::canonicalize(
      cpu_prefetch::protocol::source_document(reloaded.value()));
  ASSERT_TRUE(second);
  EXPECT_EQ(first.value(), second.value());
}

} // namespace
