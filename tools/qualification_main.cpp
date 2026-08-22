#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/runner/qualification.hpp"

#include <iostream>
#include <string_view>

namespace {

void usage(std::ostream& output) {
  output << "Usage:\n"
         << "  cpu_prefetch_qualification --self-test\n"
         << "  cpu_prefetch_qualification --help\n\n"
         << "This Q14 tool contains typed qualification artifact producers but "
            "no dynamic collection or control command. A future exact Q15 is "
            "required before stand qualification.\n";
}

auto run(int argc, char** argv) -> int {
  if (argc == 2 && std::string_view(argv[1]) == "--self-test") {
    const auto repository = cpu_prefetch::foundation::repository_info();
    if (repository.protocol_version != cpu_prefetch::protocol::kProtocolVersion ||
        cpu_prefetch::runner::kQualificationEvidenceSchemaVersion !=
            "cpu-prefetch-qualification-evidence/1" ||
        cpu_prefetch::runner::kRunnerProfileId !=
            "STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v2" ||
        cpu_prefetch::runner::kSoftwarePrefetchMappingId !=
            "X86-64-PREFETCHW-PREFETCHT0-v1") {
      std::cerr << "qualification-self-test: FAIL: build/profile mismatch\n";
      return 1;
    }
    std::cout << "qualification-self-test: PASS dynamic=NOT_EXECUTED "
                 "stand=NOT_ACCESSED authority=Q15_REQUIRED\n";
    return 0;
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

int main(int argc, char** argv) { return run(argc, argv); }
