// D-009/ADR-0030's Stage 8 clock suite requires proving the accepted
// LINUX-CLOCK-MONOTONIC-RAW-VDSO-PS-v1 reader (1) resolves through a real,
// versioned x86-64 vDSO symbol, (2) reports a resolution no worse than
// 1000 picoseconds, and (3) makes zero real clock_gettime syscalls across
// a real 10,000,000-call sequence. docs/TIMING.md is explicit that (3) is
// "deliberately an external qualification input" -- the code can prove the
// symbol exists, but proving the call sequence never falls back to a
// syscall is something only an external tracer watching the process can
// show, not something this process can honestly claim about itself.
//
// This tool is that external qualification's building blocks:
//   --check-vdso-symbol / --check-resolution: real, in-process checks
//     (cpu_prefetch::timing::probe_vdso_clock_gettime() /
//     monotonic_raw_resolution(), both already real and unit-tested,
//     just not wired into any production tool before this).
//   --probe: the isolated tracee. It does nothing but prime the reader
//     once (matching q15_clock_pair_qualification.cpp's own real priming
//     pattern) and then perform exactly --call-count (default: the real
//     accepted 10,000,000, cpu_prefetch::timing::kQualificationDeltaCount)
//     real clock_gettime(CLOCK_MONOTONIC_RAW) calls through the accepted
//     reader, reporting call failures for real -- nothing else, so an
//     external trace attributes every observed syscall to this exact
//     loop. Run it under a real syscall tracer (e.g.
//     `strace -c -e trace=clock_gettime -- cpu_prefetch_clock_vdso_probe_tool --probe`)
//     on the accepted stand to get the real probe_syscall_count/
//     probe_call_count/probe_failure_count StaticClockEvidenceInput needs;
//     this tool never fabricates those numbers itself.
//   --collect: assembles a complete, real StaticClockEvidenceInput and
//     calls the existing, unit-tested evaluate_static_clock_evidence()
//     directly -- never reimplementing its pass/fail logic. Every field
//     that can be locally, honestly observed is (CPUID hypervisor bit,
//     current clocksource, /proc/cpuinfo TSC flags, CPUID invariant-TSC
//     bit, /proc/cmdline clocksource override, dmesg unstable-clock
//     report, the vDSO symbol and resolution checks above). The three
//     fields that cannot be honestly observed from inside this process
//     -- the real --probe run's own numbers, and generated_code_passes
//     (the real, separately-run timing-codegen-check build target's
//     outcome) -- are required, never-defaulted CLI flags instead.

#include "cpu_prefetch/timing/clock.hpp"
#include "cpu_prefetch/timing/qualification.hpp"

#include <algorithm>
#include <cctype>
#include <charconv>
#include <cpuid.h>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <sys/wait.h>
#include <system_error>
#include <unistd.h>

namespace {

void usage(std::ostream& output) {
  output << "Usage:\n"
         << "  cpu_prefetch_clock_vdso_probe_tool --self-test\n"
         << "  cpu_prefetch_clock_vdso_probe_tool --check-vdso-symbol\n"
         << "  cpu_prefetch_clock_vdso_probe_tool --check-resolution\n"
         << "  cpu_prefetch_clock_vdso_probe_tool --probe [--call-count N]\n"
         << "  cpu_prefetch_clock_vdso_probe_tool --collect \\\n"
         << "      --probe-call-count N --probe-syscall-count N "
            "--probe-failure-count N \\\n"
         << "      --glibc-call-path-verified true|false "
            "--generated-code-passes true|false\n\n"
         << "D-009/ADR-0030. --check-vdso-symbol and --check-resolution are real, "
            "in-process, non-perturbing checks. --probe is the isolated tracee "
            "for the real zero-syscall proof: it primes the reader once, then "
            "performs exactly --call-count (default "
         << cpu_prefetch::timing::kQualificationDeltaCount
         << ") real clock_gettime(CLOCK_MONOTONIC_RAW) calls and nothing else. "
            "Run it under an external syscall tracer on the accepted stand -- "
            "this tool never claims a syscall count for itself, since docs/"
            "TIMING.md requires that proof come from outside the traced "
            "process. --collect assembles the complete real StaticClockEvidence"
            "Input (locally-observable facts plus the --probe-*/"
            "--generated-code-passes flags, which must be the real outcome of "
            "an actual --probe run under a tracer and the real timing-codegen-"
            "check build target -- never guessed) and prints the real "
            "evaluate_static_clock_evidence() verdict.\n";
}

[[nodiscard]] auto read_file_trimmed(const std::string& path)
    -> std::optional<std::string> {
  std::ifstream file(path);
  if (!file) {
    return std::nullopt;
  }
  std::string content((std::istreambuf_iterator<char>(file)),
                      std::istreambuf_iterator<char>());
  const auto begin = content.find_first_not_of(" \t\r\n");
  if (begin == std::string::npos) {
    return std::string();
  }
  const auto end = content.find_last_not_of(" \t\r\n");
  return content.substr(begin, end - begin + 1U);
}

// /proc/cpuinfo's "flags" line is the same real source the accepted Stage 8
// archive was manually read from (docs/STAGE8_CLOCK_DECISION_BUNDLE.md:
// "kernel clocksource tsc, rdtscp, constant_tsc, nonstop_tsc").
[[nodiscard]] auto cpuinfo_flags() -> std::optional<std::set<std::string>> {
  std::ifstream file("/proc/cpuinfo");
  if (!file) {
    return std::nullopt;
  }
  std::string line;
  while (std::getline(file, line)) {
    if (line.rfind("flags", 0) != 0U) {
      continue;
    }
    const auto colon = line.find(':');
    if (colon == std::string::npos) {
      continue;
    }
    std::set<std::string> flags;
    std::istringstream stream(line.substr(colon + 1U));
    std::string token;
    while (stream >> token) {
      flags.insert(token);
    }
    return flags;
  }
  return std::nullopt;
}

[[nodiscard]] auto contains_case_insensitive(std::string_view haystack,
                                             std::string_view needle) -> bool {
  const auto lower = [](unsigned char value) {
    return static_cast<char>(std::tolower(value));
  };
  const auto it = std::search(haystack.begin(), haystack.end(), needle.begin(),
                              needle.end(), [&](char a, char b) {
                                return lower(static_cast<unsigned char>(a)) ==
                                       lower(static_cast<unsigned char>(b));
                              });
  return it != haystack.end();
}

// CPUID leaf 1 ECX bit 31: the hypervisor-present bit real hypervisors set
// for guests. Absent is the real, portable bare-metal signal; it does not
// by itself prove Linux/x86-64 (a build-time given for this codebase), only
// that no hypervisor announced itself to this CPU.
[[nodiscard]] auto hypervisor_bit_absent() -> bool {
  std::uint32_t eax = 0U;
  std::uint32_t ebx = 0U;
  std::uint32_t ecx = 0U;
  std::uint32_t edx = 0U;
  if (__get_cpuid(1U, &eax, &ebx, &ecx, &edx) == 0U) {
    return false;
  }
  return (ecx & (1U << 31U)) == 0U;
}

// CPUID leaf 0x80000007 EDX bit 8: the raw invariant-TSC bit, independent
// of and lower-level than /proc/cpuinfo's kernel-derived constant_tsc/
// nonstop_tsc flags -- the same real leaf docs/STAGE8_CLOCK_DECISION_
// BUNDLE.md's "invariant TSC CPUID bit" refers to.
[[nodiscard]] auto invariant_tsc_cpuid_bit() -> bool {
  std::uint32_t eax = 0U;
  std::uint32_t ebx = 0U;
  std::uint32_t ecx = 0U;
  std::uint32_t edx = 0U;
  if (__get_cpuid(0x80000007U, &eax, &ebx, &ecx, &edx) == 0U) {
    return false;
  }
  return (edx & (1U << 8U)) != 0U;
}

[[nodiscard]] auto current_clocksource_is_tsc() -> bool {
  const auto value = read_file_trimmed(
      "/sys/devices/system/clocksource/clocksource0/current_clocksource");
  return value.has_value() && *value == "tsc";
}

[[nodiscard]] auto no_clocksource_override() -> bool {
  const auto cmdline = read_file_trimmed("/proc/cmdline");
  return cmdline.has_value() && cmdline->find("clocksource=") == std::string::npos;
}

// Real kernel unstable-clocksource warnings ("clocksource: timekeeping
// watchdog on CPU...: Marking clocksource 'tsc' as unstable") land in the
// kernel ring buffer read by dmesg(1); reading it via dmesg itself (rather
// than reimplementing klogctl(2) parsing) reuses the same tool an operator
// would otherwise run by hand. Runs it directly via fork/exec (no shell:
// popen's command-processor indirection is unnecessary here and its own
// real fragility). Any failure to read it (missing dmesg, insufficient
// privilege) means this cannot honestly assert "no report", so it returns
// false rather than assuming the absence of evidence is evidence of
// absence. Output is accumulated whole before searching so "unstable"
// can never be missed by falling across a read() chunk boundary.
[[nodiscard]] auto no_unstable_clock_report() -> bool {
  int pipe_fds[2] = {-1, -1};
  if (::pipe(pipe_fds) != 0) {
    return false;
  }
  const auto pid = ::fork();
  if (pid < 0) {
    ::close(pipe_fds[0]);
    ::close(pipe_fds[1]);
    return false;
  }
  if (pid == 0) {
    ::close(pipe_fds[0]);
    static_cast<void>(::dup2(pipe_fds[1], STDOUT_FILENO));
    ::close(pipe_fds[1]);
    const int null_fd = ::open("/dev/null", O_WRONLY);
    if (null_fd >= 0) {
      static_cast<void>(::dup2(null_fd, STDERR_FILENO));
      ::close(null_fd);
    }
    ::execlp("dmesg", "dmesg", static_cast<char*>(nullptr));
    ::_exit(127);
  }
  ::close(pipe_fds[1]);
  std::string output;
  char buffer[4096];
  ssize_t bytes_read = 0;
  while ((bytes_read = ::read(pipe_fds[0], buffer, sizeof(buffer))) > 0) {
    output.append(buffer, static_cast<std::size_t>(bytes_read));
  }
  ::close(pipe_fds[0]);
  int status = 0;
  ::waitpid(pid, &status, 0);
  if (!WIFEXITED(status) || WEXITSTATUS(status) != 0 || output.empty()) {
    return false;
  }
  return !contains_case_insensitive(output, "unstable");
}

[[nodiscard]] auto parse_bool_flag(std::string_view name, std::string_view text)
    -> bool {
  if (text == "true") {
    return true;
  }
  if (text == "false") {
    return false;
  }
  throw std::runtime_error("flag " + std::string(name) +
                           " requires true|false, got: " + std::string(text));
}

[[nodiscard]] auto parse_uint_flag(std::string_view name, std::string_view text)
    -> std::uint64_t {
  std::uint64_t value = 0U;
  const auto [position, error] =
      std::from_chars(text.data(), text.data() + text.size(), value);
  if (error != std::errc{} || position != text.data() + text.size()) {
    throw std::runtime_error(
        "flag " + std::string(name) +
        " requires a base-10 unsigned integer, got: " + std::string(text));
  }
  return value;
}

auto collect(std::uint64_t probe_call_count, std::uint64_t probe_syscall_count,
             std::uint64_t probe_failure_count, bool glibc_call_path_verified,
             bool generated_code_passes) -> int {
  const auto resolution = cpu_prefetch::timing::monotonic_raw_resolution();
  const bool clock_monotonic_raw_supported =
      resolution.status == cpu_prefetch::timing::ClockReadStatus::ok;
  const auto vdso = cpu_prefetch::timing::probe_vdso_clock_gettime();
  const auto flags = cpuinfo_flags();
  const cpu_prefetch::timing::StaticClockEvidenceInput input{
      hypervisor_bit_absent(),
      clock_monotonic_raw_supported,
      current_clocksource_is_tsc(),
      no_unstable_clock_report(),
      flags.has_value() && flags->count("constant_tsc") != 0U,
      flags.has_value() && flags->count("nonstop_tsc") != 0U,
      invariant_tsc_cpuid_bit(),
      vdso.versioned_symbol_present,
      glibc_call_path_verified,
      probe_call_count,
      probe_syscall_count,
      probe_failure_count,
      no_clocksource_override(),
      generated_code_passes,
      clock_monotonic_raw_supported ? resolution.resolution_picoseconds : 0U,
  };
  const auto evidence = cpu_prefetch::timing::evaluate_static_clock_evidence(input);
  std::cout << "clock-vdso-probe: " << (evidence.passes ? "PASS" : "FAIL")
            << " static clock evidence\n"
            << "  bare_metal_linux_x86_64=" << input.bare_metal_linux_x86_64 << '\n'
            << "  clock_monotonic_raw_supported=" << input.clock_monotonic_raw_supported
            << '\n'
            << "  current_clocksource_tsc=" << input.current_clocksource_tsc << '\n'
            << "  no_unstable_clock_report=" << input.no_unstable_clock_report << '\n'
            << "  constant_tsc=" << input.constant_tsc << '\n'
            << "  nonstop_tsc=" << input.nonstop_tsc << '\n'
            << "  invariant_tsc=" << input.invariant_tsc << '\n'
            << "  vdso_versioned_symbol=" << input.vdso_versioned_symbol << '\n'
            << "  glibc_call_path_verified_vdso=" << input.glibc_call_path_verified_vdso
            << '\n'
            << "  probe_call_count=" << input.probe_call_count << '\n'
            << "  probe_syscall_count=" << input.probe_syscall_count << '\n'
            << "  probe_failure_count=" << input.probe_failure_count << '\n'
            << "  no_clocksource_override=" << input.no_clocksource_override << '\n'
            << "  generated_code_passes=" << input.generated_code_passes << '\n'
            << "  resolution_picoseconds=" << input.resolution_picoseconds << '\n'
            << "  -- evaluate_static_clock_evidence() --\n"
            << "  platform_passes=" << evidence.platform_passes << '\n'
            << "  source_passes=" << evidence.source_passes << '\n'
            << "  frequency_invariance_passes=" << evidence.frequency_invariance_passes
            << '\n'
            << "  vdso_symbol_passes=" << evidence.vdso_symbol_passes << '\n'
            << "  vdso_execution_passes=" << evidence.vdso_execution_passes << '\n'
            << "  generated_code_passes_evidence=" << evidence.generated_code_passes
            << '\n'
            << "  resolution_passes=" << evidence.resolution_passes << '\n';
  return evidence.passes ? 0 : 1;
}

auto check_vdso_symbol() -> int {
  const auto evidence = cpu_prefetch::timing::probe_vdso_clock_gettime();
  std::cout << "clock-vdso-probe: "
            << (evidence.versioned_symbol_present ? "PASS" : "FAIL")
            << " library_opened=" << evidence.library_opened
            << " clock_gettime_symbol_present=" << evidence.clock_gettime_symbol_present
            << " versioned_symbol_present=" << evidence.versioned_symbol_present
            << '\n';
  return evidence.versioned_symbol_present ? 0 : 1;
}

auto check_resolution() -> int {
  const auto result = cpu_prefetch::timing::monotonic_raw_resolution();
  if (result.status != cpu_prefetch::timing::ClockReadStatus::ok) {
    std::cerr << "clock-vdso-probe: FAIL clock_getres call failed\n";
    return 1;
  }
  const bool passes = result.resolution_picoseconds <= 1000U;
  std::cout << "clock-vdso-probe: " << (passes ? "PASS" : "FAIL")
            << " resolution_picoseconds=" << result.resolution_picoseconds << '\n';
  return passes ? 0 : 1;
}

auto probe(std::uint64_t call_count) -> int {
  const auto origin = cpu_prefetch::timing::MonotonicRawClock::capture_origin();
  if (origin.status != cpu_prefetch::timing::ClockReadStatus::ok) {
    std::cerr << "clock-vdso-probe: FAIL priming read failed\n";
    return 1;
  }
  const cpu_prefetch::timing::MonotonicRawClock clock({origin.absolute_nanoseconds});
  std::uint64_t call_failures = 0U;
  for (std::uint64_t index = 0U; index < call_count; ++index) {
    if (clock.read().status != cpu_prefetch::timing::ClockReadStatus::ok) {
      ++call_failures;
    }
  }
  std::cout << "clock-vdso-probe: PROBE_COMPLETE call_count=" << call_count
            << " call_failures=" << call_failures
            << " probe_syscall_count=EXTERNAL_TRACE_REQUIRED\n";
  return call_failures == 0U ? 0 : 1;
}

auto self_test() -> int {
  if (cpu_prefetch::timing::kClockSuiteId != "LINUX-CLOCK-MONOTONIC-RAW-VDSO-PS-v1") {
    std::cerr << "clock-vdso-probe-self-test: FAIL build/profile mismatch\n";
    return 1;
  }
  std::cout << "clock-vdso-probe-self-test: PASS device=NOT_OPENED clock=NOT_READ "
               "tracer=NOT_INVOKED\n";
  return 0;
}

auto collect_from_args(int argc, char** argv) -> int {
  std::optional<std::string> probe_call_count;
  std::optional<std::string> probe_syscall_count;
  std::optional<std::string> probe_failure_count;
  std::optional<std::string> glibc_call_path_verified;
  std::optional<std::string> generated_code_passes;
  const auto take = [&](int& index) -> std::string {
    if (index + 1 >= argc) {
      throw std::runtime_error(std::string("flag requires a value: ") + argv[index]);
    }
    return argv[++index];
  };
  for (int index = 2; index < argc; ++index) {
    const std::string_view flag = argv[index];
    if (flag == "--probe-call-count") {
      probe_call_count = take(index);
    } else if (flag == "--probe-syscall-count") {
      probe_syscall_count = take(index);
    } else if (flag == "--probe-failure-count") {
      probe_failure_count = take(index);
    } else if (flag == "--glibc-call-path-verified") {
      glibc_call_path_verified = take(index);
    } else if (flag == "--generated-code-passes") {
      generated_code_passes = take(index);
    } else {
      throw std::runtime_error("unrecognized flag: " + std::string(flag));
    }
  }
  const auto require = [](const std::optional<std::string>& value,
                          std::string_view name) -> const std::string& {
    if (!value.has_value()) {
      throw std::runtime_error("missing required flag: " + std::string(name));
    }
    return *value;
  };
  return collect(
      parse_uint_flag("--probe-call-count",
                      require(probe_call_count, "--probe-call-count")),
      parse_uint_flag("--probe-syscall-count",
                      require(probe_syscall_count, "--probe-syscall-count")),
      parse_uint_flag("--probe-failure-count",
                      require(probe_failure_count, "--probe-failure-count")),
      parse_bool_flag("--glibc-call-path-verified",
                      require(glibc_call_path_verified, "--glibc-call-path-verified")),
      parse_bool_flag("--generated-code-passes",
                      require(generated_code_passes, "--generated-code-passes")));
}

auto run(int argc, char** argv) -> int {
  if (argc == 2 && std::string_view(argv[1]) == "--self-test") {
    return self_test();
  }
  if (argc == 2 && std::string_view(argv[1]) == "--check-vdso-symbol") {
    return check_vdso_symbol();
  }
  if (argc == 2 && std::string_view(argv[1]) == "--check-resolution") {
    return check_resolution();
  }
  if (argc == 2 && std::string_view(argv[1]) == "--probe") {
    return probe(cpu_prefetch::timing::kQualificationDeltaCount);
  }
  if (argc == 4 && std::string_view(argv[1]) == "--probe" &&
      std::string_view(argv[2]) == "--call-count") {
    std::uint64_t call_count = 0U;
    const std::string_view text(argv[3]);
    const auto [position, error] =
        std::from_chars(text.data(), text.data() + text.size(), call_count);
    if (error != std::errc{} || position != text.data() + text.size()) {
      std::cerr << "clock-vdso-probe: FAIL --call-count requires a base-10 unsigned "
                   "integer\n";
      return 2;
    }
    return probe(call_count);
  }
  if (argc >= 2 && std::string_view(argv[1]) == "--collect") {
    return collect_from_args(argc, argv);
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
    std::cerr << "clock-vdso-probe: FAIL unexpected exception: " << exception.what()
              << '\n';
  } catch (...) {
    std::cerr << "clock-vdso-probe: FAIL unexpected non-standard exception\n";
  }
  return 1;
}
