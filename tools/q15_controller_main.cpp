#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/qualification/q15_controller.hpp"

#include <exception>
#include <iostream>
#include <string_view>

namespace {

void usage(std::ostream& output) {
  output << "Usage:\n"
         << "  cpu_prefetch_q15_controller --self-test\n"
         << "  cpu_prefetch_q15_controller --describe-scope\n"
         << "  cpu_prefetch_q15_controller --execute-q15-r "
            "EXACT_AUTHORIZATION EXACT_DETACHED_SIGNATURE\n\n"
         << "The execution entry is fail-closed in a no-authority build until a "
            "clean controller-bearing release, actual trust anchor, independent "
            "signature-verification evidence, role/custody setup, and separately "
            "approved exact Q15-R authorization are bound.\n";
}

auto run(int argc, char** argv) -> int {
  using namespace cpu_prefetch::qualification;
  if (argc == 2 && std::string_view(argv[1]) == "--self-test") {
    const auto repository = cpu_prefetch::foundation::repository_info();
    if (repository.protocol_version != cpu_prefetch::protocol::kProtocolVersion ||
        kQ15RControllerProfileId != "Q15-R-STATIC-CONTROLLER-v1" ||
        kQ15RAuthorizationSchemaVersion !=
            "cpu-prefetch-q15-qualification-authorization/2" ||
        kQ15RControllerGraph.size() != 15U ||
        kQ15RControllerGraph.front() !=
            Q15RControllerStep::verify_authorization_and_release_bindings ||
        kQ15RControllerGraph.back() !=
            Q15RControllerStep::wait_for_separate_q15_w_or_expire_fail_closed ||
        kQ15RControllerLimits.external_start_watchdog_seconds != 60U ||
        kQ15RControllerLimits.max_same_buffer_session_wall_seconds != 14'400U) {
      std::cerr << "q15-controller-self-test: FAIL profile mismatch\n";
      return 1;
    }
    std::cout << "q15-controller-self-test: PASS profile=" << kQ15RControllerProfileId
              << " graph_steps=15 stand=NOT_ACCESSED signature=NOT_VERIFIED "
                 "authority=NONE execution=NOT_STARTED\n";
    return 0;
  }
  if (argc == 2 && std::string_view(argv[1]) == "--describe-scope") {
    std::cout
        << "profile=" << kQ15RControllerProfileId
        << " authorization=" << kQ15RAuthorizationSchemaVersion
        << " graph_steps=15 q15_r=true q15_w=false arbitrary_selectors=false "
           "stand_access=false real_pmu=false msr=false affinity=false numa=false "
           "calibration=false pilot=false measurement=false confirmatory=false "
           "authority=NONE\n";
    return 0;
  }
  if (argc == 4 && std::string_view(argv[1]) == "--execute-q15-r") {
    // Q15-R-P1 authorizes implementation, not a trust anchor, signed record,
    // clean controller release, stand setup, or execution. Do not open even the
    // supplied paths until those inputs are bound by a later authorization.
    static_cast<void>(argv[2]);
    static_cast<void>(argv[3]);
    std::cerr << "q15-controller: FAIL rule=Q15R-NO-AUTHORITY-BUILD "
                 "authorization=NOT_OPENED signature=NOT_OPENED stand=NOT_ACCESSED\n";
    return 1;
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
    std::cerr << "q15-controller: FAIL unexpected exception: " << exception.what()
              << '\n';
  } catch (...) {
    std::cerr << "q15-controller: FAIL unexpected non-standard exception\n";
  }
  return 1;
}
