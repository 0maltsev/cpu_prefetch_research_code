#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/runner/runner.hpp"

#include <exception>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <string_view>

namespace {

void usage(std::ostream& output) {
  output << "Usage:\n"
         << "  cpu_prefetch_runner --self-test\n"
         << "  cpu_prefetch_runner --validate-admission FILE --stand-id ID "
            "--binding-id ID\n\n"
         << "Q14 authorizes repository-local implementation and validation only. "
            "This executable "
            "does not expose a measurement, calibration, pilot, or confirmatory "
            "execution command.\n";
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
  const auto binary_sha256 = cpu_prefetch::runner::sha256_file("/proc/self/exe");
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
