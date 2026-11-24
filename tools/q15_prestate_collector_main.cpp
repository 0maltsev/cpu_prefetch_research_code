#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/qualification/q15_prestate.hpp"

#include <exception>
#include <iostream>
#include <string>
#include <string_view>

namespace {

void usage(std::ostream& output) {
  output << "Usage:\n"
         << "  cpu_prefetch_q15_prestate_collector --self-test\n"
         << "  cpu_prefetch_q15_prestate_collector --describe-contract\n"
         << "  cpu_prefetch_q15_prestate_collector --collect "
            "AUTHORIZATION_SHA256 COLLECTOR_BINARY_SHA256 "
            "COLLECTOR_CONTRACT_SHA256 CAPTURE_ID\n\n"
         << "The collection entry has fixed argv and no arbitrary command, path, "
            "environment, shell, network, key, setup, access-probe, PMU/MSR, "
            "affinity/NUMA, calibration, pilot, measurement, or confirmatory "
            "selector. Presence of this binary grants no authority; execution "
            "requires a separately approved exact Q15-R-P4-R record.\n";
}

auto run(int argc, char** argv) -> int {
  using namespace cpu_prefetch::qualification;
  if (argc == 2 && std::string_view(argv[1]) == "--self-test") {
    const auto repository = cpu_prefetch::foundation::repository_info();
    const auto commands = q15_stand_prestate_command_contract();
    if (repository.protocol_version != cpu_prefetch::protocol::kProtocolVersion ||
        kQ15StandPrestateCollectorContractId !=
            "Q15-R-STAND-PRESTATE-COLLECTOR-CONTRACT-v1" ||
        commands.size() != kQ15StandPrestateLimits.maximum_command_count ||
        commands.front().id != "P4R-001" || commands.back().id != "P4R-025") {
      std::cerr << "q15-prestate-self-test: FAIL contract mismatch\n";
      return 1;
    }
    std::cout << "q15-prestate-self-test: PASS commands=25 shell=NONE "
                 "stand=NOT_ACCESSED execution=NOT_STARTED authority=NONE\n";
    return 0;
  }
  if (argc == 2 && std::string_view(argv[1]) == "--describe-contract") {
    std::cout << "contract=" << kQ15StandPrestateCollectorContractId
              << " contract_sha256=" << kQ15StandPrestateCollectorContractSha256
              << " commands=25 retries=0 timeout_seconds="
              << kQ15StandPrestateLimits.per_command_timeout.count()
              << " total_watchdog_seconds="
              << kQ15StandPrestateLimits.external_total_watchdog.count()
              << " shell=false inherited_environment=false mutation=false "
                 "stand_access=false execution=false authority=NONE\n";
    return 0;
  }
  if (argc == 6 && std::string_view(argv[1]) == "--collect") {
    const auto repository = cpu_prefetch::foundation::repository_info();
    Q15StandPrestateContext context{
        argv[5],
        argv[2],
        argv[3],
        argv[4],
        std::string(repository.source_revision),
        std::string(kQ15SelectedReleaseArchiveSha256),
        "XEON-CPU-FETCH",
    };
    SystemQ15StandPrestateExecutor executor;
    SystemQ15StandPrestateClock clock;
    const auto artifact = collect_q15_stand_prestate(context, executor, clock);
    if (!artifact) {
      for (const auto& error : artifact.errors()) {
        std::cerr << "q15-prestate: FAIL category="
                  << cpu_prefetch::protocol::to_string(error.category)
                  << " rule=" << error.rule_id << " path=" << error.path << ' '
                  << error.message << '\n';
      }
      return 1;
    }
    std::cout << artifact.value().canonical_json;
    return artifact.value().completion == Q15StandPrestateCompletion::complete ? 0 : 1;
  }
  if (argc == 2 &&
      (std::string_view(argv[1]) == "--help" || std::string_view(argv[1]) == "-h")) {
    usage(std::cout);
    return 0;
  }
  usage(std::cerr);
  return 2;
}

} // namespace

int main(int argc, char** argv) {
  try {
    return run(argc, argv);
  } catch (const std::exception& exception) {
    std::cerr << "q15-prestate: FAIL unexpected exception: " << exception.what()
              << '\n';
  } catch (...) {
    std::cerr << "q15-prestate: FAIL unexpected non-standard exception\n";
  }
  return 1;
}
