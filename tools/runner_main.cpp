#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/runner/runner.hpp"
#include "cpu_prefetch/runner/stage17_discovery_action.hpp"
#include "cpu_prefetch/runner/stage17_fixed_action.hpp"
#include "cpu_prefetch/runner/stage17_s180_worker.hpp"

#include <array>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <string_view>

namespace {

void usage(std::ostream& output) {
  output << "Usage:\n"
         << "  cpu_prefetch_runner --self-test\n"
         << "  cpu_prefetch_runner --stage17-s180-runtime-identity-v1\n"
         << "  cpu_prefetch_runner --describe-stage17-s180-layouts-v1 FILE\n"
         << "  cpu_prefetch_runner --describe-stage17-discovery-layout-v1 FILE\n"
         << "  cpu_prefetch_runner --describe-stage17-discovery-layout-v2 FILE\n"
         << "  cpu_prefetch_runner --execute-fixed-stage17-action-v4 ACTION "
            "--request-fd FD --context-fd FD --output-dir-fd FD "
            "--fixed-dispatch-end\n"
         << "  cpu_prefetch_runner --execute-fixed-stage17-action-v5 "
            "Q16A-DURATION-DISCOVERY "
            "--request-fd FD --context-fd FD --output-dir-fd FD --fixed-dispatch-end\n"
         << "  cpu_prefetch_runner --execute-stage17-q15-session-v1 "
            "--q15-r-request-fd FD --q15-r-context-fd FD "
            "--q15-w-control-fd FD --output-dir-fd FD --fixed-dispatch-end\n"
         << "  cpu_prefetch_runner --execute-stage17-pilot-session-v1 "
            "--request-fd FD --context-fd FD --output-dir-fd FD "
            "--fixed-dispatch-end\n"
         << "  cpu_prefetch_runner --execute-stage17-s180-session-v1 "
            "--request-fd FD --context-fd FD --output-dir-fd FD "
            "--fixed-dispatch-end\n"
         << "  cpu_prefetch_runner --validate-admission FILE --stand-id ID "
            "--binding-id ID\n\n"
         << "The Stage 17 action entry is an internal fd-only dispatcher. It accepts "
            "only seven compiled actions and no command, plugin, path-based request, "
            "stdin, output name, fake backend, or Phase 18 authority.\n";
}

[[nodiscard]] auto read_file(const std::filesystem::path& path) -> std::string {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    throw std::runtime_error("cannot open admission document");
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    throw std::runtime_error("cannot read admission document completely");
  }
  return buffer.str();
}

void print_errors(std::span<const cpu_prefetch::protocol::ValidationError> errors) {
  for (const auto& error : errors) {
    std::cerr << cpu_prefetch::protocol::to_string(error.category) << ' '
              << error.rule_id << ' ' << error.path << ": " << error.message << '\n';
  }
}

int run(int argc, char** argv) {
  if (argc == 3 && std::string_view(argv[1]) == "--describe-stage17-s180-layouts-v1") {
    std::ifstream stream(argv[2], std::ios::binary);
    if (!stream)
      throw std::runtime_error("cannot open S180 sizing input");
    constexpr auto maximum = std::size_t{16U} * 1024U * 1024U;
    std::string raw;
    std::array<char, 8192U> buffer{};
    while (stream) {
      stream.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
      const auto count = static_cast<std::size_t>(stream.gcount());
      if (count > maximum - raw.size())
        throw std::runtime_error("S180 sizing input exceeds fixed bound");
      raw.append(buffer.data(), count);
    }
    if (!stream.eof())
      throw std::runtime_error("S180 sizing input read failed");
    const auto parsed = cpu_prefetch::protocol::json::parse(raw);
    if (!parsed || !parsed.value().as_object())
      throw std::runtime_error("S180 sizing input must be an object");
    auto result = cpu_prefetch::runner::stage17::describe_s180_session_layouts(
        *parsed.value().as_object());
    if (!result) {
      print_errors(result.errors());
      return 1;
    }
    const auto identity = cpu_prefetch::runner::stage17::inspect_s180_executable();
    if (!identity) {
      print_errors(identity.errors());
      return 1;
    }
    const auto source = cpu_prefetch::foundation::repository_info();
    auto& output = result.value();
    output["binary_sha256"] =
        cpu_prefetch::protocol::json::Value(identity.value().sha256);
    output["source_revision"] =
        cpu_prefetch::protocol::json::Value(std::string(source.source_revision));
    output["source_dirty"] = cpu_prefetch::protocol::json::Value(source.source_dirty);
    const auto canonical = cpu_prefetch::protocol::json::canonicalize(parsed.value());
    if (!canonical)
      throw std::runtime_error("S180 sizing canonicalization failed");
    output["sizing_plan_sha256"] = cpu_prefetch::protocol::json::Value(
        cpu_prefetch::workload::sha256(
            std::as_bytes(
                std::span(canonical.value().data(), canonical.value().size())))
            .hex());
    const auto encoded = cpu_prefetch::protocol::json::canonicalize(
        cpu_prefetch::protocol::json::Value(output));
    if (!encoded)
      throw std::runtime_error("S180 sizing result canonicalization failed");
    std::cout << encoded.value() << '\n';
    return 0;
  }
  if (argc == 2 && std::string_view(argv[1]) == "--stage17-s180-runtime-identity-v1") {
    const auto repository = cpu_prefetch::foundation::repository_info();
    const auto identity = cpu_prefetch::runner::stage17::inspect_s180_executable();
    if (!identity) {
      print_errors(identity.errors());
      return 1;
    }
    std::cout << "{\"schema_version\":\"cpu-prefetch-stage17-s180-runtime-identity/1\","
                 "\"role\":\""
              << cpu_prefetch::runner::stage17::kS180WorkerRole << "\",\"profile\":\""
              << cpu_prefetch::runner::stage17::kS180WorkerProfile << "\",\"sha256\":\""
              << identity.value().sha256
              << "\",\"size_bytes\":" << identity.value().size_bytes
              << ",\"source_revision\":\"" << repository.source_revision
              << "\",\"source_dirty\":" << (repository.source_dirty ? "true" : "false")
              << ",\"synthetic_test_only\":false,\"execution_authority\":false,"
                 "\"phase18_authority\":false}\n";
    return 0;
  }
  if (argc == 3 &&
      (std::string_view(argv[1]) == "--describe-stage17-discovery-layout-v1" ||
       std::string_view(argv[1]) == "--describe-stage17-discovery-layout-v2")) {
    const auto design =
        std::string_view(argv[1]) == "--describe-stage17-discovery-layout-v2"
            ? cpu_prefetch::runner::stage17::DiscoveryNativeDesign::d207_v2
            : cpu_prefetch::runner::stage17::DiscoveryNativeDesign::d178_v1;
    const auto input = cpu_prefetch::protocol::json::parse(read_file(argv[2]));
    if (!input || input.value().as_object() == nullptr) {
      throw std::runtime_error("discovery layout input is not a JSON object");
    }
    const auto& document = *input.value().as_object();
    if (document.size() != 4U || !document.contains("capture") ||
        !document.contains("resources") || !document.contains("monitoring") ||
        !document.contains("hardware_prestate")) {
      throw std::runtime_error("discovery layout input field set differs");
    }
    const auto* capture = document.at("capture").as_object();
    const auto* resources = document.at("resources").as_object();
    const auto* monitoring = document.at("monitoring").as_object();
    if (capture == nullptr || resources == nullptr || monitoring == nullptr) {
      throw std::runtime_error("discovery layout input components are not objects");
    }
    const auto* values = document.at("hardware_prestate").as_array();
    if (values == nullptr) {
      throw std::runtime_error("discovery layout prestate is not an array");
    }
    std::vector<cpu_prefetch::platform::HardwarePrefetchMsrValue> prestate;
    for (const auto& value : *values) {
      const auto* item = value.as_object();
      if (item == nullptr || item->size() != 2U || !item->contains("cpu") ||
          !item->contains("value")) {
        throw std::runtime_error("discovery layout prestate field set differs");
      }
      const auto* cpu = item->at("cpu").as_number();
      const auto* observed = item->at("value").as_number();
      using Kind = cpu_prefetch::protocol::json::Number::Kind;
      if (cpu == nullptr || observed == nullptr ||
          cpu->kind != Kind::unsigned_integer ||
          observed->kind != Kind::unsigned_integer ||
          std::get<std::uint64_t>(cpu->value) >
              std::numeric_limits<std::uint32_t>::max()) {
        throw std::runtime_error(
            "discovery layout prestate requires unsigned integers");
      }
      prestate.push_back(
          {static_cast<std::uint32_t>(std::get<std::uint64_t>(cpu->value)),
           std::get<std::uint64_t>(observed->value)});
    }
    const auto layout = cpu_prefetch::runner::stage17::describe_native_discovery_layout(
        *capture, *resources, *monitoring, prestate, design);
    const auto identity = cpu_prefetch::runner::stage17::self_executable_sha256();
    if (!layout || !identity) {
      print_errors(!layout ? layout.errors() : identity.errors());
      return 1;
    }
    const auto repository = cpu_prefetch::foundation::repository_info();
    std::cout << "{\"schema_version\":\"cpu-prefetch-discovery-layout/1\","
                 "\"execution_authority\":false,\"binary_sha256\":\""
              << identity.value() << "\",\"source_revision\":\""
              << repository.source_revision
              << "\",\"source_dirty\":" << (repository.source_dirty ? "true" : "false")
              << ",\"core_bytes\":" << layout.value().core_bytes
              << ",\"monitor_bytes\":" << layout.value().monitor_bytes
              << ",\"total_mapping_bytes\":" << layout.value().total_mapping_bytes
              << ",\"region_bytes\":[";
    for (std::size_t index = 0U; index < layout.value().region_bytes.size(); ++index) {
      if (index != 0U) {
        std::cout << ',';
      }
      std::cout << layout.value().region_bytes[index];
    }
    std::cout << "]}\n";
    return 0;
  }
  if (argc == 2 && std::string_view(argv[1]) == "--stage17-runtime-identity-v4") {
    const auto repository = cpu_prefetch::foundation::repository_info();
    const auto binary_sha256 = cpu_prefetch::runner::stage17::self_executable_sha256();
    if (!binary_sha256) {
      print_errors(binary_sha256.errors());
      return 1;
    }
    std::cout
        << "{\"binary_sha256\":\"" << binary_sha256.value()
        << "\",\"protocol_version\":\"" << repository.protocol_version
        << "\",\"role\":\"" << cpu_prefetch::runner::stage17::kFixedActionWorkerRole
        << "\",\"runtime_profile\":\""
        << cpu_prefetch::runner::stage17::kFixedActionRuntimeProfile
        << "\",\"source_dirty\":" << (repository.source_dirty ? "true" : "false")
        << ",\"source_revision\":\"" << repository.source_revision
        << "\",\"supported_actions\":[\"Q15-R\",\"Q15-W\",\"Q16a\","
           "\"Q16b\",\"Q16c\",\"STAGE17-BLINDED-PILOT\",\"Q16A-DURATION-DISCOVERY\"],"
           "\"synthetic_test_only\":false}\n";
    return 0;
  }
  if (argc >= 2 && (std::string_view(argv[1]) == "--execute-fixed-stage17-action-v4" ||
                    std::string_view(argv[1]) == "--execute-fixed-stage17-action-v5" ||
                    std::string_view(argv[1]) == "--execute-fixed-stage17-action-v6")) {
    cpu_prefetch::runner::stage17::LinuxFixedActionOperations operations;
    return cpu_prefetch::runner::stage17::run_fixed_action_worker(argc, argv,
                                                                  operations);
  }
  if (argc >= 2 && std::string_view(argv[1]) == "--execute-stage17-q15-session-v1") {
    return cpu_prefetch::runner::stage17::run_q15_phase_session_worker(argc, argv);
  }
  if (argc >= 2 && std::string_view(argv[1]) == "--execute-stage17-pilot-session-v1") {
    cpu_prefetch::runner::stage17::LinuxFixedActionOperations operations;
    return cpu_prefetch::runner::stage17::run_pilot_session_worker(argc, argv,
                                                                   operations);
  }
  if (argc >= 2 && std::string_view(argv[1]) == "--execute-stage17-s180-session-v1") {
    cpu_prefetch::runner::stage17::LinuxS180WorkerOperations operations;
    return cpu_prefetch::runner::stage17::run_s180_session_worker(argc, argv,
                                                                  operations);
  }
  if (argc == 2 && std::string_view(argv[1]) == "--self-test") {
    const auto repository = cpu_prefetch::foundation::repository_info();
    if (repository.protocol_version != cpu_prefetch::protocol::kProtocolVersion ||
        repository.source_revision.empty() ||
        cpu_prefetch::runner::selected_worker_pair(
            cpu_prefetch::protocol::Placement::near) !=
            cpu_prefetch::runner::kNearWorkerPair ||
        cpu_prefetch::runner::selected_worker_pair(
            cpu_prefetch::protocol::Placement::far) !=
            cpu_prefetch::runner::kFarWorkerPair ||
        cpu_prefetch::runner::kSoftwarePrefetchMappingId !=
            "X86-64-PREFETCHW-PREFETCHT0-v1") {
      std::cerr << "runner-self-test: FAIL: build or accepted policy mismatch\n";
      return 1;
    }
    cpu_prefetch::runner::X86PauseRelax{}.relax();
    std::cout << "runner-self-test: PASS profile="
              << cpu_prefetch::runner::kRunnerProfileId << " software_prefetch_mapping="
              << cpu_prefetch::runner::kSoftwarePrefetchMappingId
              << " execution=NOT_AUTHORIZED\n";
    return 0;
  }
  if (argc == 2 &&
      (std::string_view(argv[1]) == "--help" || std::string_view(argv[1]) == "-h")) {
    usage(std::cout);
    return 0;
  }
  if (argc != 7 || std::string_view(argv[1]) != "--validate-admission" ||
      std::string_view(argv[3]) != "--stand-id" ||
      std::string_view(argv[5]) != "--binding-id") {
    usage(std::cerr);
    return 2;
  }

  const std::filesystem::path manifest_path(argv[2]);
  const auto admission = cpu_prefetch::runner::load_admission(read_file(manifest_path));
  if (!admission) {
    print_errors(admission.errors());
    return 1;
  }
  const auto binary_sha256 = cpu_prefetch::runner::sha256_running_binary();
  if (!binary_sha256) {
    print_errors(binary_sha256.errors());
    return 1;
  }
  const auto repository = cpu_prefetch::foundation::repository_info();
  const cpu_prefetch::runner::AdmissionTrustAnchor trust_anchor{
      std::string(repository.source_revision), binary_sha256.value(), argv[4], argv[6],
      repository.source_dirty};
  const auto ticket = cpu_prefetch::runner::admit_runner(
      admission.value(), trust_anchor, manifest_path.parent_path());
  if (!ticket) {
    print_errors(ticket.errors());
    return 1;
  }
  std::cout << "runner-admission: PASS binding=" << ticket.value().binding_id()
            << " state=VALIDATED_FOR_PREPARATION_ONLY execution=NOT_STARTED\n";
  return 0;
}

} // namespace

int main(int argc, char** argv) {
  try {
    return run(argc, argv);
  } catch (const std::exception& exception) {
    std::cerr << "runner: FAIL: " << exception.what() << '\n';
  } catch (...) {
    std::cerr << "runner: FAIL: unhandled non-standard exception\n";
  }
  return 1;
}
