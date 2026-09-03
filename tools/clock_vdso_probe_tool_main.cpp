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
// This tool is that external qualification's two halves:
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

#include "cpu_prefetch/timing/clock.hpp"
#include "cpu_prefetch/timing/qualification.hpp"

#include <charconv>
#include <cstdint>
#include <exception>
#include <iostream>
#include <string_view>
#include <system_error>

namespace {

void usage(std::ostream& output) {
  output << "Usage:\n"
         << "  cpu_prefetch_clock_vdso_probe_tool --self-test\n"
         << "  cpu_prefetch_clock_vdso_probe_tool --check-vdso-symbol\n"
         << "  cpu_prefetch_clock_vdso_probe_tool --check-resolution\n"
         << "  cpu_prefetch_clock_vdso_probe_tool --probe [--call-count N]\n\n"
         << "D-009/ADR-0030. --check-vdso-symbol and --check-resolution are real, "
            "in-process, non-perturbing checks. --probe is the isolated tracee "
            "for the real zero-syscall proof: it primes the reader once, then "
            "performs exactly --call-count (default "
         << cpu_prefetch::timing::kQualificationDeltaCount
         << ") real clock_gettime(CLOCK_MONOTONIC_RAW) calls and nothing else. "
            "Run it under an external syscall tracer on the accepted stand -- "
            "this tool never claims a syscall count for itself, since docs/"
            "TIMING.md requires that proof come from outside the traced "
            "process.\n";
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
