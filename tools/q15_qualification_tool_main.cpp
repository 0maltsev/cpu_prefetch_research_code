#include "cpu_prefetch/foundation/repository_info.hpp"
#include "cpu_prefetch/platform/q15_msr.hpp"

#include <algorithm>
#include <array>
#include <charconv>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <string_view>

namespace {

using cpu_prefetch::platform::HardwarePrefetchMsrValue;

void usage(std::ostream& output) {
  output << "Usage:\n"
         << "  cpu_prefetch_q15_tool --self-test\n"
         << "  cpu_prefetch_q15_tool --describe-fixed-scope\n"
         << "  cpu_prefetch_q15_tool --read-fixed-values AUTHORIZATION_SHA256\n"
         << "  cpu_prefetch_q15_tool --read-fixed-cpu AUTHORIZATION_SHA256 CPU\n"
         << "  cpu_prefetch_q15_tool --apply-h1-cpu AUTHORIZATION_SHA256 CPU "
            "CPU0_PRESTATE_HEX CPU1_PRESTATE_HEX CPU26_PRESTATE_HEX\n"
         << "  cpu_prefetch_q15_tool --restore-h0-cpu AUTHORIZATION_SHA256 CPU "
            "CPU0_PRESTATE_HEX CPU1_PRESTATE_HEX CPU26_PRESTATE_HEX\n\n"
         << "The dynamic commands are fixed to family 06/model 55H, MSR 0x1A4, "
            "CPUs 0/1/26, and the accepted 0x0f mapping. They do not validate or "
            "grant authority. Running them requires a separately signed exact "
            "Q15-R or Q15-W record, OS role enforcement, and external limits.\n";
}

[[nodiscard]] auto valid_sha256(std::string_view text) -> bool {
  return text.size() == 64U &&
         std::all_of(text.begin(), text.end(), [](char character) {
           return (character >= '0' && character <= '9') ||
                  (character >= 'a' && character <= 'f');
         });
}

[[nodiscard]] auto parse_u32(std::string_view text, std::uint32_t& value) -> bool {
  if (text.empty()) {
    return false;
  }
  const auto [position, code] =
      std::from_chars(text.data(), text.data() + text.size(), value, 10);
  return code == std::errc{} && position == text.data() + text.size();
}

[[nodiscard]] auto parse_hex_u64(std::string_view text, std::uint64_t& value) -> bool {
  if (text.size() != 16U || !std::all_of(text.begin(), text.end(), [](char character) {
        return (character >= '0' && character <= '9') ||
               (character >= 'a' && character <= 'f');
      })) {
    return false;
  }
  const auto [position, code] =
      std::from_chars(text.data(), text.data() + text.size(), value, 16);
  return code == std::errc{} && position == text.data() + text.size();
}

[[nodiscard]] auto selected_cpu(std::uint32_t cpu) -> bool {
  const auto& cpus = cpu_prefetch::platform::kHardwarePrefetchControlCpus;
  return std::find(cpus.begin(), cpus.end(), cpu) != cpus.end();
}

[[nodiscard]] auto require_selected_model() -> bool {
  const auto identity = cpu_prefetch::platform::read_x86_family_model();
  if (!identity || identity.value().family != cpu_prefetch::platform::kIntelFamily6 ||
      identity.value().model != cpu_prefetch::platform::kIntelModel55) {
    std::cerr << "q15-tool: FAIL rule=Q15-CPUID-06_55H before_msr=true\n";
    return false;
  }
  return true;
}

[[nodiscard]] auto parse_plan(int argc, char** argv, std::uint32_t& cpu)
    -> cpu_prefetch::platform::Result<cpu_prefetch::platform::HardwarePrefetchPlan> {
  using namespace cpu_prefetch::platform;
  if (argc != 7 || !valid_sha256(argv[2]) || !parse_u32(argv[3], cpu) ||
      !selected_cpu(cpu)) {
    return Result<HardwarePrefetchPlan>::failure(Error{
        ErrorCategory::invalid_request, "$q15_tool/argv", "Q15-ARGV",
        "exact authorization hash, selected CPU, and three prestates are required"});
  }
  std::array<HardwarePrefetchMsrValue, 3U> prestate{};
  for (std::size_t index = 0U; index < prestate.size(); ++index) {
    std::uint64_t value = 0U;
    if (!parse_hex_u64(argv[index + 4U], value)) {
      return Result<HardwarePrefetchPlan>::failure(
          Error{ErrorCategory::parse_error, "$q15_tool/argv", "Q15-PRESTATE-HEX",
                "each complete prestate must be exactly 16 lowercase hex digits"});
    }
    prestate[index] = {kHardwarePrefetchControlCpus[index], value};
  }
  return make_hardware_prefetch_plan({kIntelFamily6, kIntelModel55},
                                     cpu_prefetch::protocol::RequestedHardwareState::h1,
                                     prestate);
}

auto read_fixed_values(int argc, char** argv) -> int {
  using namespace cpu_prefetch::platform;
  if (argc != 3 || !valid_sha256(argv[2])) {
    std::cerr << "q15-tool: FAIL rule=Q15-AUTHORIZATION-HASH\n";
    return 2;
  }
  if (!require_selected_model()) {
    return 1;
  }
  SystemPosixFileOperations files;
  LinuxHardwarePrefetchMsrBackend reader(files, FixedMsrAccess::read_only);
  std::array<HardwarePrefetchMsrValue, 3U> values{};
  for (std::size_t index = 0U; index < values.size(); ++index) {
    const auto value = reader.read(kHardwarePrefetchControlCpus[index]);
    if (!value) {
      std::cerr << "q15-tool: FAIL rule=" << value.errors().front().rule_id << '\n';
      return 1;
    }
    values[index] = {kHardwarePrefetchControlCpus[index], value.value()};
  }
  std::cout << "q15-fixed-values: COMPLETE mapping=" << kHardwarePrefetchMappingId
            << " authorization_sha256=" << argv[2]
            << " independent_role=EXTERNALLY_ENFORCED\n";
  for (const auto& value : values) {
    std::cout << "cpu=" << value.cpu << " value=" << std::hex << std::setw(16)
              << std::setfill('0') << value.value << std::dec << '\n';
  }
  return 0;
}

auto read_fixed_cpu(int argc, char** argv) -> int {
  using namespace cpu_prefetch::platform;
  std::uint32_t cpu = 0U;
  if (argc != 4 || !valid_sha256(argv[2]) || !parse_u32(argv[3], cpu) ||
      !selected_cpu(cpu)) {
    std::cerr << "q15-tool: FAIL rule=Q15-READ-CPU-ARGV\n";
    return 2;
  }
  if (!require_selected_model()) {
    return 1;
  }
  SystemPosixFileOperations files;
  LinuxHardwarePrefetchMsrBackend reader(files, FixedMsrAccess::read_only);
  const auto value = reader.read(cpu);
  if (!value) {
    std::cerr << "q15-tool: FAIL rule=" << value.errors().front().rule_id << '\n';
    return 1;
  }
  std::cout << "q15-fixed-value: COMPLETE mapping=" << kHardwarePrefetchMappingId
            << " authorization_sha256=" << argv[2] << " cpu=" << cpu
            << " value=" << std::hex << std::setw(16) << std::setfill('0')
            << value.value() << std::dec << " independent_role=EXTERNALLY_ENFORCED\n";
  return 0;
}

auto transition(int argc, char** argv,
                cpu_prefetch::platform::HardwarePrefetchTransition direction) -> int {
  using namespace cpu_prefetch::platform;
  std::uint32_t cpu = 0U;
  const auto plan = parse_plan(argc, argv, cpu);
  if (!plan) {
    std::cerr << "q15-tool: FAIL rule=" << plan.errors().front().rule_id << '\n';
    return 2;
  }
  if (!require_selected_model()) {
    return 1;
  }
  SystemPosixFileOperations files;
  LinuxHardwarePrefetchMsrBackend writer(files, FixedMsrAccess::read_write);
  const auto result =
      perform_hardware_prefetch_transition(plan.value(), cpu, direction, writer);
  if (!result) {
    std::cerr << "q15-tool: FAIL rule=" << result.errors().front().rule_id << '\n';
    return 1;
  }
  std::cout << "q15-fixed-transition: COMPLETE mapping=" << kHardwarePrefetchMappingId
            << " authorization_sha256=" << argv[2] << " cpu=" << result.value().cpu
            << " value=" << std::hex << std::setw(16) << std::setfill('0')
            << result.value().value << std::dec << " independent_readback=REQUIRED\n";
  return 0;
}

auto run(int argc, char** argv) -> int {
  using namespace cpu_prefetch::platform;
  if (argc == 2 && std::string_view(argv[1]) == "--self-test") {
    const auto repository = cpu_prefetch::foundation::repository_info();
    if (repository.protocol_version != cpu_prefetch::protocol::kProtocolVersion ||
        kQ15QualificationToolProfileId != "Q15-FIXED-QUALIFICATION-TOOL-v1" ||
        kHardwarePrefetchMappingId != "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1") {
      std::cerr << "q15-tool-self-test: FAIL profile mismatch\n";
      return 1;
    }
    std::cout << "q15-tool-self-test: PASS device=NOT_OPENED msr=NOT_ACCESSED "
                 "stand=NOT_ACCESSED authority=NONE\n";
    return 0;
  }
  if (argc == 2 && std::string_view(argv[1]) == "--describe-fixed-scope") {
    std::cout << "profile=" << kQ15QualificationToolProfileId
              << " mapping=" << kHardwarePrefetchMappingId
              << " family=06 model=55 msr=000001a4 mask=000000000000000f "
                 "cpus=0,1,26 measurement=false calibration=false pilot=false "
                 "confirmatory=false authority=NONE\n";
    return 0;
  }
  if (argc >= 2 && std::string_view(argv[1]) == "--read-fixed-values") {
    return read_fixed_values(argc, argv);
  }
  if (argc >= 2 && std::string_view(argv[1]) == "--read-fixed-cpu") {
    return read_fixed_cpu(argc, argv);
  }
  if (argc >= 2 && std::string_view(argv[1]) == "--apply-h1-cpu") {
    return transition(argc, argv, HardwarePrefetchTransition::apply_h1);
  }
  if (argc >= 2 && std::string_view(argv[1]) == "--restore-h0-cpu") {
    return transition(argc, argv, HardwarePrefetchTransition::restore_h0);
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
    std::cerr << "q15-tool: FAIL unexpected exception: " << exception.what() << '\n';
  } catch (...) {
    std::cerr << "q15-tool: FAIL unexpected non-standard exception\n";
  }
  return 1;
}
