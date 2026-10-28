// S17-EXT-004 QUALIFICATION_EVIDENCE envelope-authoring tool.
//
// Reads one of Q15-R's already-published, already-schema-valid raw
// artifacts (Q15_R_ATOMIC_LAYOUT_RAW / Q15_R_ADDRESS_RESIDENCY_RAW /
// Q15_R_SOFTWARE_PREFETCH_RAW / Q15_R_CPU_MIGRATION_RAW), or
// cpu_prefetch_q15_clock_qualification_tool's raw output (stage17-q15-
// clock-pair-raw-v1), plus real, already-known session facts supplied on
// the command line, and calls the existing, unit-tested typed builder in
// cpu_prefetch::runner (ADR-0147/0148/0149/0150/0152) to produce the
// schema-compliant QUALIFICATION_EVIDENCE envelope -- the same "eligible"
// logic the unit tests already verify, never re-implemented here.
//
// SELECTED_PAIR_CLOCK's own envelope previously also required
// traced_call_count/traced_syscall_count/before_block_repeat as explicit
// CLI flags, precisely because no VDSO call/syscall tracer or post-
// measurement block-repeat timestamp capture exists anywhere in this
// codebase to produce them for real. That safeguard worked exactly as
// designed -- it refused to let this tool invent them -- but real S17-
// EXT-004 admissions were made anyway by hand-typing plausible values
// past it (ADR-0154). Those three fields are removed entirely rather
// than left as an easy-to-defeat gate: eligibility no longer depends on
// evidence nothing in this codebase can measure.

#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/runner/qualification.hpp"
#include "cpu_prefetch/runner/runner.hpp"
#include "cpu_prefetch/runner/software_prefetch.hpp"
#include "cpu_prefetch/workload/deterministic.hpp"

#include <array>
#include <cstdint>
#include <exception>
#include <fstream>
#include <iostream>
#include <map>
#include <optional>
#include <span>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

namespace {

namespace runner = cpu_prefetch::runner;
namespace json = cpu_prefetch::protocol::json;

void usage(std::ostream& output) {
  output << "Usage:\n"
         << "  cpu_prefetch_q15_qualification_evidence_tool --self-test\n"
         << "  cpu_prefetch_q15_qualification_evidence_tool \\\n"
         << "      --kind RUNTIME_ATOMIC_LAYOUT|ACTUAL_CPU_MIGRATION|ADDRESS_RESIDENCY|"
            "SOFTWARE_PREFETCH_MAPPING|SELECTED_PAIR_CLOCK \\\n"
         << "      --raw RAW_ARTIFACT_PATH --output ENVELOPE_OUTPUT_PATH \\\n"
         << "      --artifact-id ID --stand-id ID --binding-id ID "
            "--source-revision REV \\\n"
         << "      --binary-sha256 HEX64 --captured-at-utc TIMESTAMP "
            "--worker-pair near|far \\\n"
         << "      [--cpu-pair-selection-id ID] \\\n"
         << "      --source-artifact-id ID \\\n"
         << "      [--gcc-codegen-passed true|false --clang-codegen-passed true|false "
            "\\\n"
         << "       --gnu-objdump-passed true|false --llvm-objdump-passed true|false]  "
            "(SOFTWARE_PREFETCH_MAPPING only)\n\n"
         << "Every identity field must be a real, already-known fact about the real "
            "session that produced --raw (its own admitted binding_id/"
            "source_revision/binary_sha256/captured_at_utc), not a freshly derived "
            "value -- this tool performs no live hardware or clock access. "
            "--source-artifact-id must be the raw artifact's own real artifact_id "
            "from that session's journal/manifest; its sha256 is computed here from "
            "the real bytes at --raw. --cpu-pair-selection-id names which registered "
            "pair identity --worker-pair far resolves to (ADR-0043's "
         << runner::kCpuPairSelectionId << " by default, or ADR-0173's "
         << runner::kCpuPairSelectionIdV5
         << "); --worker-pair near is the same real CPUs under either identity. "
            "The four codegen flags must be the real, "
            "already-passing outcome of the software-prefetch-mapping-codegen-check "
            "build target. For SELECTED_PAIR_CLOCK, --worker-pair must match --raw's "
            "own \"pair\" field exactly.\n";
}

[[noreturn]] void fail(std::string_view message) {
  throw std::runtime_error(std::string(message));
}

[[nodiscard]] auto read_file(const std::string& path) -> std::string {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    fail("cannot open file: " + path);
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    fail("cannot read file completely: " + path);
  }
  return buffer.str();
}

void write_file(const std::string& path, std::string_view content) {
  std::ofstream output(path, std::ios::binary | std::ios::trunc);
  output.write(content.data(), static_cast<std::streamsize>(content.size()));
  if (!output) {
    fail("cannot write file: " + path);
  }
}

[[nodiscard]] auto require_object(const json::Value& value, std::string_view what)
    -> const json::Value::Object& {
  const auto* object = value.as_object();
  if (object == nullptr) {
    fail(std::string(what) + " must be a JSON object");
  }
  return *object;
}

[[nodiscard]] auto field(const json::Value::Object& object, std::string_view name)
    -> const json::Value& {
  const auto iterator = object.find(name);
  if (iterator == object.end()) {
    fail("missing required field: " + std::string(name));
  }
  return iterator->second;
}

[[nodiscard]] auto require_string(const json::Value::Object& object,
                                  std::string_view name) -> const std::string& {
  const auto* value = field(object, name).as_string();
  if (value == nullptr) {
    fail("field must be a string: " + std::string(name));
  }
  return *value;
}

[[nodiscard]] auto require_uint(const json::Value::Object& object,
                                std::string_view name) -> std::uint64_t {
  const auto* number = field(object, name).as_number();
  if (number == nullptr || number->kind != json::Number::Kind::unsigned_integer) {
    fail("field must be an exact unsigned integer: " + std::string(name));
  }
  return std::get<std::uint64_t>(number->value);
}

[[nodiscard]] auto require_bool(const json::Value::Object& object,
                                std::string_view name) -> bool {
  const auto* value = field(object, name).as_bool();
  if (value == nullptr) {
    fail("field must be a boolean: " + std::string(name));
  }
  return *value;
}

[[nodiscard]] auto require_array(const json::Value::Object& object,
                                 std::string_view name) -> const json::Value::Array& {
  const auto* value = field(object, name).as_array();
  if (value == nullptr) {
    fail("field must be an array: " + std::string(name));
  }
  return *value;
}

void require_const_string(const json::Value::Object& object, std::string_view name,
                          std::string_view expected) {
  const auto& actual = require_string(object, name);
  if (actual != expected) {
    fail("unexpected " + std::string(name) + ": " + actual + " (expected " +
         std::string(expected) + ")");
  }
}

[[nodiscard]] auto build_atomic_layout_input(const json::Value::Object& raw)
    -> runner::RuntimeAtomicLayoutInput {
  require_const_string(raw, "schema_version",
                       "cpu-prefetch-stage17-q15-r-atomic-layout-raw/1");
  return {
      require_uint(raw, "pointer_atomic_width_bytes"),
      require_uint(raw, "pointer_atomic_alignment_bytes"),
      require_uint(raw, "termination_atomic_width_bytes"),
      require_uint(raw, "termination_atomic_alignment_bytes"),
      require_uint(raw, "cache_line_bytes"),
      require_bool(raw, "pointer_atomic_runtime_lock_free"),
      require_bool(raw, "termination_atomic_runtime_lock_free"),
      require_bool(raw, "queue_layout_passed"),
      require_bool(raw, "ownership_lines_separated"),
      require_bool(raw, "termination_dedicated_line"),
  };
}

// ADR-0148: Q15-R has no real producer/consumer thread pair, so its one
// real four-sample series (regular-entry, regular-exit, pointer-entry,
// pointer-exit) honestly stands for both producer_*/consumer_* fields;
// migration count is derived from adjacent-sample CPU changes within that
// one series, duplicated into both roles the same way.
[[nodiscard]] auto build_cpu_migration_input(const json::Value::Object& raw)
    -> runner::ActualCpuMigrationInput {
  require_const_string(raw, "schema_version",
                       "cpu-prefetch-stage17-q15-r-cpu-migration-raw/1");
  const auto& samples = require_array(raw, "samples");
  if (samples.size() != 4U) {
    fail("cpu-migration raw must carry exactly 4 samples");
  }
  std::array<std::uint64_t, 4U> cpus{};
  for (std::size_t index = 0U; index < 4U; ++index) {
    cpus[index] = require_uint(require_object(samples[index], "samples[]"), "cpu");
  }
  std::uint64_t migrations = 0U;
  for (std::size_t index = 0U; index + 1U < cpus.size(); ++index) {
    if (cpus[index] != cpus[index + 1U]) {
      ++migrations;
    }
  }
  const auto& singleton =
      require_object(field(raw, "singleton_affinity"), "singleton_affinity");
  const bool singleton_ok = require_bool(singleton, "regular_stream") &&
                            require_bool(singleton, "pointer_dependent");
  return {
      4U,
      4U,
      static_cast<std::uint32_t>(cpus.front()),
      static_cast<std::uint32_t>(cpus.back()),
      static_cast<std::uint32_t>(cpus.front()),
      static_cast<std::uint32_t>(cpus.back()),
      migrations,
      migrations,
      singleton_ok,
      singleton_ok,
  };
}

[[nodiscard]] auto build_address_residency_input(const json::Value::Object& raw)
    -> runner::AddressResidencyInput {
  require_const_string(raw, "schema_version",
                       "cpu-prefetch-stage17-q15-r-address-residency-raw/1");
  runner::AddressResidencyInput input;
  input.mechanism_id = require_string(raw, "mechanism_id");
  const auto& regions = require_array(raw, "regions");
  input.regions.reserve(regions.size());
  for (const auto& region_value : regions) {
    const auto& region = require_object(region_value, "regions[]");
    input.regions.push_back({
        require_string(region, "region"),
        static_cast<std::uint32_t>(require_uint(region, "expected_node")),
        require_uint(region, "before_page_count"),
        require_uint(region, "during_page_count"),
        require_uint(region, "after_page_count"),
        require_uint(region, "unavailable_page_count"),
        require_uint(region, "wrong_node_page_count"),
        require_uint(region, "migrated_page_count"),
    });
  }
  return input;
}

[[nodiscard]] auto build_software_prefetch_mapping_input(const json::Value::Object& raw,
                                                         bool gcc_codegen_passed,
                                                         bool clang_codegen_passed,
                                                         bool gnu_objdump_passed,
                                                         bool llvm_objdump_passed)
    -> runner::SoftwarePrefetchMappingInput {
  // ADR-0175: a report naming either registered software-prefetch mapping
  // (schema /1, the original PRFCHW-based mapping, or /2, also accepting
  // the PRFCHW-free T0-only mapping) is a valid raw capture.
  const auto& schema_version = require_string(raw, "schema_version");
  if (schema_version != "cpu-prefetch-stage17-q15-r-software-prefetch-raw/1"
      && schema_version != "cpu-prefetch-stage17-q15-r-software-prefetch-raw/2") {
    fail("unexpected schema_version: " + schema_version +
         " (expected .../1 or .../2)");
  }
  const runner::SoftwarePrefetchCapabilityObservation producer{
      static_cast<std::uint32_t>(require_uint(raw, "producer_maximum_extended_leaf")),
      static_cast<std::uint32_t>(require_uint(raw, "producer_extended_leaf_ecx")),
      require_bool(raw, "producer_prfchw_supported"),
  };
  const runner::SoftwarePrefetchCapabilityObservation consumer{
      static_cast<std::uint32_t>(require_uint(raw, "consumer_maximum_extended_leaf")),
      static_cast<std::uint32_t>(require_uint(raw, "consumer_extended_leaf_ecx")),
      require_bool(raw, "consumer_prfchw_supported"),
  };
  return {require_string(raw, "mapping_id"),
          producer,
          consumer,
          gcc_codegen_passed,
          clang_codegen_passed,
          gnu_objdump_passed,
          llvm_objdump_passed};
}

// per_core_evaluator_passed combines both sides' real, separately-reported
// pass/fail -- the envelope has one shared field, unlike the raw
// artifact's two.
[[nodiscard]] auto build_selected_pair_clock_input(const json::Value::Object& raw,
                                                   std::string_view worker_pair_flag)
    -> runner::SelectedPairClockInput {
  require_const_string(raw, "schema_version",
                       "cpu-prefetch-stage17-q15-clock-pair-raw/1");
  const auto& raw_pair = require_string(raw, "pair");
  if (raw_pair != worker_pair_flag) {
    fail("raw artifact pair (" + raw_pair + ") does not match --worker-pair (" +
         std::string(worker_pair_flag) + ")");
  }
  return {
      {require_uint(raw, "producer_prime_read_count"),
       require_uint(raw, "consumer_prime_read_count")},
      {require_uint(raw, "producer_delta_count"),
       require_uint(raw, "consumer_delta_count")},
      require_uint(raw, "producer_to_consumer_window_count"),
      require_uint(raw, "consumer_to_producer_window_count"),
      require_uint(raw, "exchanges_per_window"),
      require_bool(raw, "producer_per_core_passed") &&
          require_bool(raw, "consumer_per_core_passed"),
      require_bool(raw, "cross_core_passed"),
  };
}

struct Args final {
  std::optional<std::string> kind;
  std::optional<std::string> raw;
  std::optional<std::string> output;
  std::optional<std::string> artifact_id;
  std::optional<std::string> stand_id;
  std::optional<std::string> binding_id;
  std::optional<std::string> source_revision;
  std::optional<std::string> binary_sha256;
  std::optional<std::string> captured_at_utc;
  std::optional<std::string> worker_pair;
  std::optional<std::string> cpu_pair_selection_id;
  std::optional<std::string> source_artifact_id;
  std::optional<std::string> gcc_codegen_passed;
  std::optional<std::string> clang_codegen_passed;
  std::optional<std::string> gnu_objdump_passed;
  std::optional<std::string> llvm_objdump_passed;
};

[[nodiscard]] auto parse_bool_flag(std::string_view name, std::string_view text)
    -> bool {
  if (text == "true") {
    return true;
  }
  if (text == "false") {
    return false;
  }
  fail("flag " + std::string(name) + " requires true|false, got: " + std::string(text));
}

[[nodiscard]] auto parse_args(int argc, char** argv) -> Args {
  Args args;
  const auto take = [&](int& index) -> std::string {
    if (index + 1 >= argc) {
      fail(std::string("flag requires a value: ") + argv[index]);
    }
    return argv[++index];
  };
  for (int index = 1; index < argc; ++index) {
    const std::string_view flag = argv[index];
    if (flag == "--kind") {
      args.kind = take(index);
    } else if (flag == "--raw") {
      args.raw = take(index);
    } else if (flag == "--output") {
      args.output = take(index);
    } else if (flag == "--artifact-id") {
      args.artifact_id = take(index);
    } else if (flag == "--stand-id") {
      args.stand_id = take(index);
    } else if (flag == "--binding-id") {
      args.binding_id = take(index);
    } else if (flag == "--source-revision") {
      args.source_revision = take(index);
    } else if (flag == "--binary-sha256") {
      args.binary_sha256 = take(index);
    } else if (flag == "--captured-at-utc") {
      args.captured_at_utc = take(index);
    } else if (flag == "--worker-pair") {
      args.worker_pair = take(index);
    } else if (flag == "--cpu-pair-selection-id") {
      args.cpu_pair_selection_id = take(index);
    } else if (flag == "--source-artifact-id") {
      args.source_artifact_id = take(index);
    } else if (flag == "--gcc-codegen-passed") {
      args.gcc_codegen_passed = take(index);
    } else if (flag == "--clang-codegen-passed") {
      args.clang_codegen_passed = take(index);
    } else if (flag == "--gnu-objdump-passed") {
      args.gnu_objdump_passed = take(index);
    } else if (flag == "--llvm-objdump-passed") {
      args.llvm_objdump_passed = take(index);
    } else {
      fail("unrecognized flag: " + std::string(flag));
    }
  }
  return args;
}

[[nodiscard]] auto require_flag(const std::optional<std::string>& value,
                                std::string_view name) -> const std::string& {
  if (!value.has_value()) {
    fail("missing required flag: " + std::string(name));
  }
  return *value;
}

// Call sites pass --worker-pair and --cpu-pair-selection-id by name, not
// position, so a swap here would already have failed a flag lookup upstream.
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
[[nodiscard]] auto parse_worker_pair(std::string_view text,
                                     std::string_view cpu_pair_selection_id)
    -> runner::WorkerPair {
  if (!runner::is_accepted_cpu_pair_selection_id(cpu_pair_selection_id)) {
    fail("--cpu-pair-selection-id does not name a registered pair identity: " +
         std::string(cpu_pair_selection_id));
  }
  const bool is_v5 = cpu_pair_selection_id == runner::kCpuPairSelectionIdV5;
  if (text == "near") {
    return runner::kNearWorkerPair;
  }
  if (text == "far") {
    return is_v5 ? runner::kFarWorkerPairV5 : runner::kFarWorkerPair;
  }
  fail("--worker-pair must be near|far, got: " + std::string(text));
}

[[nodiscard]] auto build_artifact(std::string_view kind_text,
                                  const runner::QualificationIdentity& identity,
                                  const json::Value::Object& raw, const Args& args)
    -> cpu_prefetch::protocol::Result<runner::QualificationArtifact> {
  if (kind_text == "RUNTIME_ATOMIC_LAYOUT") {
    return runner::make_runtime_atomic_layout_evidence(identity,
                                                       build_atomic_layout_input(raw));
  }
  if (kind_text == "ACTUAL_CPU_MIGRATION") {
    return runner::make_actual_cpu_migration_evidence(identity,
                                                      build_cpu_migration_input(raw));
  }
  if (kind_text == "ADDRESS_RESIDENCY") {
    return runner::make_address_residency_evidence(identity,
                                                   build_address_residency_input(raw));
  }
  if (kind_text == "SOFTWARE_PREFETCH_MAPPING") {
    return runner::make_software_prefetch_mapping_evidence(
        identity, build_software_prefetch_mapping_input(
                      raw,
                      parse_bool_flag("--gcc-codegen-passed",
                                      require_flag(args.gcc_codegen_passed,
                                                   "--gcc-codegen-passed")),
                      parse_bool_flag("--clang-codegen-passed",
                                      require_flag(args.clang_codegen_passed,
                                                   "--clang-codegen-passed")),
                      parse_bool_flag("--gnu-objdump-passed",
                                      require_flag(args.gnu_objdump_passed,
                                                   "--gnu-objdump-passed")),
                      parse_bool_flag("--llvm-objdump-passed",
                                      require_flag(args.llvm_objdump_passed,
                                                   "--llvm-objdump-passed"))));
  }
  if (kind_text == "SELECTED_PAIR_CLOCK") {
    return runner::make_selected_pair_clock_evidence(
        identity, build_selected_pair_clock_input(
                      raw, require_flag(args.worker_pair, "--worker-pair")));
  }
  fail("--kind must be one of RUNTIME_ATOMIC_LAYOUT, ACTUAL_CPU_MIGRATION, "
       "ADDRESS_RESIDENCY, SOFTWARE_PREFETCH_MAPPING, SELECTED_PAIR_CLOCK");
}

auto author(const Args& args) -> int {
  const auto& kind_text = require_flag(args.kind, "--kind");
  const auto& raw_path = require_flag(args.raw, "--raw");
  const auto& output_path = require_flag(args.output, "--output");

  const auto raw_bytes = read_file(raw_path);
  const auto raw_sha256 =
      cpu_prefetch::workload::sha256(std::as_bytes(std::span<const char>(raw_bytes)))
          .hex();
  const auto parsed = json::parse(raw_bytes);
  if (!parsed) {
    fail("raw artifact is not valid JSON: " + raw_path);
  }
  const auto& raw = require_object(parsed.value(), "raw artifact");

  const runner::QualificationIdentity identity{
      require_flag(args.artifact_id, "--artifact-id"),
      require_flag(args.stand_id, "--stand-id"),
      require_flag(args.binding_id, "--binding-id"),
      require_flag(args.source_revision, "--source-revision"),
      require_flag(args.binary_sha256, "--binary-sha256"),
      require_flag(args.captured_at_utc, "--captured-at-utc"),
      parse_worker_pair(require_flag(args.worker_pair, "--worker-pair"),
                        args.cpu_pair_selection_id.value_or(
                            std::string(runner::kCpuPairSelectionId))),
      {{require_flag(args.source_artifact_id, "--source-artifact-id"), raw_sha256}},
  };

  const auto artifact = build_artifact(kind_text, identity, raw, args);
  if (!artifact.has_value()) {
    for (const auto& error : artifact.errors()) {
      std::cerr << cpu_prefetch::protocol::to_string(error.category) << ' '
                << error.rule_id << ' ' << error.path << ": " << error.message << '\n';
    }
    std::cerr << "q15-qualification-evidence-tool: FAIL kind=" << kind_text
              << " identity/schema validation failed\n";
    return 1;
  }

  write_file(output_path, artifact.value().canonical_json);
  std::cout << "q15-qualification-evidence-tool: "
            << (artifact.value().eligible ? "PASS" : "FAIL") << " kind=" << kind_text
            << " eligible=" << (artifact.value().eligible ? "true" : "false")
            << " output=" << output_path << '\n';
  return artifact.value().eligible ? 0 : 1;
}

auto self_test() -> int {
  const auto repository = cpu_prefetch::foundation::repository_info();
  if (repository.protocol_version != cpu_prefetch::protocol::kProtocolVersion ||
      runner::kQualificationEvidenceSchemaVersion !=
          "cpu-prefetch-qualification-evidence/2") {
    std::cerr << "q15-qualification-evidence-tool-self-test: FAIL build/profile "
                 "mismatch\n";
    return 1;
  }
  static constexpr std::string_view kSyntheticRaw =
      R"({"schema_version":"cpu-prefetch-stage17-q15-r-atomic-layout-raw/1",)"
      R"("session_id":"synthetic-session","qualification_id":"synthetic-qual",)"
      R"("pointer_atomic_width_bytes":8,"pointer_atomic_alignment_bytes":8,)"
      R"("termination_atomic_width_bytes":4,"termination_atomic_alignment_bytes":4,)"
      R"("cache_line_bytes":64,"pointer_atomic_runtime_lock_free":true,)"
      R"("termination_atomic_runtime_lock_free":true,"queue_layout_passed":true,)"
      R"("ownership_lines_separated":true,"termination_dedicated_line":true})";
  const auto parsed = json::parse(kSyntheticRaw);
  if (!parsed) {
    std::cerr << "q15-qualification-evidence-tool-self-test: FAIL synthetic raw did "
                 "not parse\n";
    return 1;
  }
  const auto* raw = parsed.value().as_object();
  if (raw == nullptr) {
    std::cerr << "q15-qualification-evidence-tool-self-test: FAIL synthetic raw is "
                 "not an object\n";
    return 1;
  }
  const runner::QualificationIdentity identity{
      "synthetic-qualification-evidence-tool-self-test",
      "SYNTHETIC-NOT-A-STAND",
      "synthetic-binding",
      "synthetic-revision",
      std::string(64U, '0'),
      "2026-09-03T00:00:00Z",
      runner::kNearWorkerPair,
      {{"synthetic-raw-source", std::string(64U, '0')}},
  };
  const auto artifact = runner::make_runtime_atomic_layout_evidence(
      identity, build_atomic_layout_input(*raw));
  if (!artifact.has_value() || !artifact.value().eligible) {
    std::cerr << "q15-qualification-evidence-tool-self-test: FAIL builder round-trip "
                 "failed\n";
    return 1;
  }
  const auto reparsed = json::parse(artifact.value().canonical_json);
  if (!reparsed.has_value()) {
    std::cerr << "q15-qualification-evidence-tool-self-test: FAIL canonical JSON did "
                 "not reparse\n";
    return 1;
  }
  const auto recanonicalized = json::canonicalize(reparsed.value());
  if (!recanonicalized.has_value() ||
      recanonicalized.value() != artifact.value().canonical_json) {
    std::cerr << "q15-qualification-evidence-tool-self-test: FAIL canonical JSON is "
                 "not idempotent\n";
    return 1;
  }
  std::cout << "q15-qualification-evidence-tool-self-test: PASS device=NOT_OPENED "
               "stand=NOT_ACCESSED clock=NOT_READ\n";
  return 0;
}

auto run(int argc, char** argv) -> int {
  if (argc == 2 && std::string_view(argv[1]) == "--self-test") {
    return self_test();
  }
  if (argc == 2 &&
      (std::string_view(argv[1]) == "--help" || std::string_view(argv[1]) == "-h")) {
    usage(std::cout);
    return 0;
  }
  if (argc < 2) {
    usage(std::cerr);
    return 2;
  }
  return author(parse_args(argc, argv));
}

} // namespace

int main(int argc, char** argv) {
  try {
    return run(argc, argv);
  } catch (const std::exception& exception) {
    std::cerr << "q15-qualification-evidence-tool: FAIL " << exception.what() << '\n';
  } catch (...) {
    std::cerr << "q15-qualification-evidence-tool: FAIL unexpected non-standard "
                 "exception\n";
  }
  return 1;
}
