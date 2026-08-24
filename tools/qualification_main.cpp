#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/platform/platform.hpp"
#include "cpu_prefetch/runner/qualification.hpp"

#include <array>
#include <charconv>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <string>
#include <string_view>

namespace {

void usage(std::ostream& output) {
  output << "Usage:\n"
         << "  cpu_prefetch_qualification --self-test\n"
         << "  cpu_prefetch_qualification --hardware-prefetch-plan H0|H1 "
            "CPU0_HEX CPU1_HEX CPU26_HEX\n"
         << "  cpu_prefetch_qualification --help\n\n"
         << "The plan command is a pure Q15-P0 mapping check over supplied "
            "complete 64-bit prestates. This tool has no MSR read/write, dynamic "
            "collection, or control command. A future exact Q15 is required "
            "before stand qualification.\n";
}

[[nodiscard]] auto parse_hex_u64(std::string_view text, std::uint64_t& value) -> bool {
  if (text.empty()) {
    return false;
  }
  const auto [position, error] =
      std::from_chars(text.data(), text.data() + text.size(), value, 16);
  return error == std::errc{} && position == text.data() + text.size();
}

auto hardware_prefetch_plan(int argc, char** argv) -> int {
  if (argc != 6) {
    usage(std::cerr);
    return 2;
  }
  const auto state_text = std::string_view(argv[2]);
  const auto state =
      state_text == "H0" ? cpu_prefetch::protocol::RequestedHardwareState::h0
      : state_text == "H1"
          ? cpu_prefetch::protocol::RequestedHardwareState::h1
          : cpu_prefetch::protocol::RequestedHardwareState::not_applicable;
  std::array<cpu_prefetch::platform::HardwarePrefetchMsrValue, 3U> prestate{};
  for (std::size_t index = 0U; index < prestate.size(); ++index) {
    std::uint64_t value = 0U;
    if (!parse_hex_u64(argv[index + 3U], value)) {
      std::cerr << "hardware-prefetch-plan: FAIL invalid complete hex prestate\n";
      return 1;
    }
    prestate[index] = {cpu_prefetch::platform::kHardwarePrefetchControlCpus[index],
                       value};
  }
  const auto plan = cpu_prefetch::platform::make_hardware_prefetch_plan(
      {cpu_prefetch::platform::kIntelFamily6, cpu_prefetch::platform::kIntelModel55},
      state, prestate);
  if (!plan) {
    std::cerr << "hardware-prefetch-plan: FAIL rule=" << plan.errors().front().rule_id
              << '\n';
    return 1;
  }
  std::cout << "hardware-prefetch-plan: PASS mapping="
            << cpu_prefetch::platform::kHardwarePrefetchMappingId << " msr=0x"
            << std::hex << cpu_prefetch::platform::kHardwarePrefetchMsr << std::dec
            << " state=" << state_text << " dynamic=NOT_EXECUTED\n";
  for (std::size_t index = 0U; index < prestate.size(); ++index) {
    std::cout << "cpu=" << prestate[index].cpu << " prestate=" << std::hex
              << std::setw(16) << std::setfill('0') << prestate[index].value
              << " requested=" << std::setw(16) << plan.value().requested[index].value
              << std::dec << '\n';
  }
  return 0;
}

auto run(int argc, char** argv) -> int {
  if (argc == 2 && std::string_view(argv[1]) == "--self-test") {
    const auto repository = cpu_prefetch::foundation::repository_info();
    if (repository.protocol_version != cpu_prefetch::protocol::kProtocolVersion ||
        cpu_prefetch::runner::kQualificationEvidenceSchemaVersion !=
            "cpu-prefetch-qualification-evidence/1" ||
        cpu_prefetch::runner::kRunnerProfileId !=
            "STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v3" ||
        cpu_prefetch::runner::kSoftwarePrefetchMappingId !=
            "X86-64-PREFETCHW-PREFETCHT0-v1") {
      std::cerr << "qualification-self-test: FAIL: build/profile mismatch\n";
      return 1;
    }
    std::cout << "qualification-self-test: PASS dynamic=NOT_EXECUTED "
                 "stand=NOT_ACCESSED authority=Q15_REQUIRED\n";
    return 0;
  }
  if (argc >= 2 && std::string_view(argv[1]) == "--hardware-prefetch-plan") {
    return hardware_prefetch_plan(argc, argv);
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
    std::cerr << "qualification: FAIL unexpected exception: " << exception.what()
              << '\n';
  } catch (...) {
    std::cerr << "qualification: FAIL unexpected non-standard exception\n";
  }
  return 1;
}
