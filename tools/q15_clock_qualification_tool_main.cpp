#include "cpu_prefetch/platform/platform.hpp"
#include "cpu_prefetch/platform/q15_msr.hpp"
#include "cpu_prefetch/protocol/json.hpp"
#include "cpu_prefetch/qualification/q15_clock_pair_qualification.hpp"
#include "cpu_prefetch/runner/runner.hpp"
#include "cpu_prefetch/timing/cross_core_exchange.hpp"

#include <atomic>
#include <charconv>
#include <fstream>
#include <iostream>
#include <optional>
#include <string>
#include <string_view>
#include <system_error>

namespace {

using cpu_prefetch::qualification::ClockPairQualificationCounts;
using cpu_prefetch::qualification::ClockPairQualificationResult;
using cpu_prefetch::qualification::kAcceptedClockPairQualificationCounts;
using cpu_prefetch::qualification::run_clock_pair_qualification;
using cpu_prefetch::runner::kFarWorkerPair;
using cpu_prefetch::runner::kNearWorkerPair;
using cpu_prefetch::runner::WorkerPair;

void usage(std::ostream& output) {
  output << "Usage:\n"
         << "  cpu_prefetch_q15_clock_qualification_tool --self-test\n"
         << "  cpu_prefetch_q15_clock_qualification_tool --qualify-pair near|far "
            "[--output PATH]\n"
         << "  cpu_prefetch_q15_clock_qualification_tool --qualify-pair near|far "
            "--prime-read-count N\n"
         << "  cpu_prefetch_q15_clock_qualification_tool --qualify-pair near|far "
            "--delta-count N\n\n"
         << "ADR-0150. --qualify-pair runs the full frozen-constant "
            "per-core-then-cross-core measurement for real on this machine's "
            "CPUs (production repeat scale: "
         << cpu_prefetch::timing::kQualificationPrimeReadCount << " prime reads + "
         << cpu_prefetch::timing::kQualificationDeltaCount << " delta reads per core, "
         << cpu_prefetch::timing::kCrossCoreWindowCount << " windows of "
         << cpu_prefetch::timing::kCrossCoreExchangeCountPerWindow
         << " exchanges per direction, spanning at least "
         << cpu_prefetch::timing::kMinimumCrossCoreWindowStartSpanNanoseconds /
                1'000'000'000ULL
         << " real seconds). It requires family 06 model 55H and does not "
            "validate or grant authority; real qualification evidence also "
            "requires this to run on the accepted stand. --output writes a raw, "
            "partial pre-envelope artifact (schema stage17-q15-clock-pair-raw-v1) "
            "covering only what this tool actually measures: prime/delta counts, "
            "window counts, exchanges per window, and per-core/cross-core "
            "pass/fail. It deliberately omits traced_call_count/"
            "traced_syscall_count/before_block_repeat -- no real VDSO call/"
            "syscall tracer or post-measurement block-repeat timestamp capture "
            "exists in this codebase yet, so those SELECTED_PAIR_CLOCK envelope "
            "fields cannot be derived from this artifact alone. Only written "
            "when the measurement completes (producer_pinned, consumer_pinned, "
            "and complete all true); a completed-but-failing measurement is "
            "still written, since the raw artifact reports real facts, not a "
            "verdict. --prime-read-count N / --delta-count N replace the "
            "frozen prime read count / delta read count for a diagnostic "
            "run only -- the matching accepted_policy_sample_count check "
            "will correctly read false since N no longer matches the "
            "accepted constant, this can never produce real qualification "
            "evidence, and it cannot be combined with --output.\n";
}

[[nodiscard]] auto require_selected_model() -> bool {
  const auto identity = cpu_prefetch::platform::read_x86_family_model();
  if (!identity || identity.value().family != cpu_prefetch::platform::kIntelFamily6 ||
      identity.value().model != cpu_prefetch::platform::kIntelModel55) {
    std::cerr << "q15-clock-tool: FAIL rule=Q15-CPUID-06_55H before_hardware=true\n";
    return false;
  }
  return true;
}

auto self_test() -> int {
  // Touches no hardware and pins no thread: exercises the exchange
  // primitive with a synthetic clock only, the same "device=NOT_OPENED"
  // boundary every other q15 tool's --self-test observes.
  cpu_prefetch::timing::CrossCoreExchangeChannel channel;
  std::atomic<std::uint64_t> synthetic_clock{0U};
  const auto now = [&] {
    return synthetic_clock.fetch_add(1U, std::memory_order_relaxed);
  };
  channel.forward.publish(1U, 100U, 0U);
  const auto request = channel.forward.wait_for(1U, /*max_spins=*/1U);
  channel.backward.publish(1U, 200U, 300U);
  const auto reply = channel.backward.wait_for(1U, /*max_spins=*/1U);
  const auto evidence = channel.forward.atomic_lock_free_evidence();
  static_cast<void>(now());
  if (!request.has_value() || request->first != 100U || !reply.has_value() ||
      reply->first != 200U || reply->second != 300U || !evidence.always_lock_free) {
    std::cerr << "q15-clock-tool-self-test: FAIL exchange primitive mismatch\n";
    return 1;
  }
  std::cout << "q15-clock-tool-self-test: PASS device=NOT_OPENED clock=NOT_READ "
               "threads=NOT_PINNED authority=NONE\n";
  return 0;
}

namespace json = cpu_prefetch::protocol::json;

[[nodiscard]] auto uint_value(std::uint64_t value) -> json::Value {
  return json::Value(
      json::Number{json::Number::Kind::unsigned_integer, std::to_string(value), value});
}

// Writes only what run_clock_pair_qualification actually measured -- see
// usage()'s --output paragraph for exactly which SELECTED_PAIR_CLOCK
// envelope fields this deliberately omits and why. Takes the per-core/
// cross-core evidence already unwrapped, rather than the optionals
// ClockPairQualificationResult holds them in, so the caller's single
// has_value() check (immediately before calling this) is the only one
// needed.
[[nodiscard]] auto
write_raw_output(const std::string& path, std::string_view pair_name, WorkerPair pair,
                 bool producer_pinned, bool consumer_pinned,
                 const cpu_prefetch::timing::PerCoreQualificationEvidence& producer,
                 const cpu_prefetch::timing::PerCoreQualificationEvidence& consumer,
                 const cpu_prefetch::timing::CrossCorePairEvidence& cross_core)
    -> bool {
  const auto document = json::Value(json::Value::Object{
      {"schema_version",
       json::Value(std::string("cpu-prefetch-stage17-q15-clock-pair-raw/1"))},
      {"pair", json::Value(std::string(pair_name))},
      {"producer_cpu", uint_value(pair.producer_cpu)},
      {"consumer_cpu", uint_value(pair.consumer_cpu)},
      {"producer_pinned", json::Value(producer_pinned)},
      {"consumer_pinned", json::Value(consumer_pinned)},
      {"producer_prime_read_count",
       uint_value(kAcceptedClockPairQualificationCounts.prime_read_count)},
      {"consumer_prime_read_count",
       uint_value(kAcceptedClockPairQualificationCounts.prime_read_count)},
      {"producer_delta_count", uint_value(producer.sequence.delta_count)},
      {"consumer_delta_count", uint_value(consumer.sequence.delta_count)},
      {"producer_to_consumer_window_count",
       uint_value(cross_core.producer_to_consumer.windows.size())},
      {"consumer_to_producer_window_count",
       uint_value(cross_core.consumer_to_producer.windows.size())},
      {"exchanges_per_window",
       uint_value(cross_core.producer_to_consumer.exchange_count_per_window)},
      {"producer_per_core_passed", json::Value(producer.passes)},
      {"consumer_per_core_passed", json::Value(consumer.passes)},
      {"cross_core_passed", json::Value(cross_core.passes)},
  });
  const auto canonical = json::canonicalize(document);
  if (!canonical) {
    return false;
  }
  std::ofstream file(path, std::ios::binary | std::ios::trunc);
  file.write(canonical.value().data(),
             static_cast<std::streamsize>(canonical.value().size()));
  return static_cast<bool>(file);
}

auto qualify_pair(std::string_view pair_name, std::optional<std::string> output_path,
                  ClockPairQualificationCounts counts =
                      kAcceptedClockPairQualificationCounts) -> int {
  if (!require_selected_model()) {
    return 1;
  }
  const auto pair = pair_name == "near"  ? kNearWorkerPair
                    : pair_name == "far" ? kFarWorkerPair
                                         : cpu_prefetch::runner::WorkerPair{0U, 0U};
  if (pair_name != "near" && pair_name != "far") {
    std::cerr << "q15-clock-tool: FAIL rule=Q15-CLOCK-PAIR-ARGV\n";
    return 2;
  }
  if (counts.prime_read_count != kAcceptedClockPairQualificationCounts.prime_read_count ||
      counts.delta_count != kAcceptedClockPairQualificationCounts.delta_count) {
    std::cerr << "q15-clock-tool: NOTE diagnostic-only run, prime_read_count="
              << counts.prime_read_count
              << " (accepted=" << kAcceptedClockPairQualificationCounts.prime_read_count
              << ") delta_count=" << counts.delta_count
              << " (accepted=" << kAcceptedClockPairQualificationCounts.delta_count
              << ") -- cannot produce real qualification evidence\n";
  }
  const auto result = run_clock_pair_qualification(pair, counts);
  if (!result.producer_pinned || !result.consumer_pinned || !result.complete) {
    std::cerr << "q15-clock-tool: FAIL pair=" << pair_name
              << " producer_pinned=" << result.producer_pinned
              << " consumer_pinned=" << result.consumer_pinned
              << " complete=" << result.complete << '\n';
    return 1;
  }
  if (!result.producer_per_core.has_value() || !result.consumer_per_core.has_value() ||
      !result.cross_core.has_value()) {
    std::cerr << "q15-clock-tool: FAIL evidence missing despite complete=true\n";
    return 1;
  }
  const auto& producer = result.producer_per_core.value();
  const auto& consumer = result.consumer_per_core.value();
  const auto& cross_core = result.cross_core.value();
  if (output_path &&
      !write_raw_output(*output_path, pair_name, pair, result.producer_pinned,
                        result.consumer_pinned, producer, consumer, cross_core)) {
    std::cerr << "q15-clock-tool: FAIL cannot write raw output: " << *output_path
              << '\n';
    return 1;
  }
  std::cout << "q15-clock-pair-qualification: " << (result.passes ? "PASS" : "FAIL")
            << " pair=" << pair_name << " producer_cpu=" << pair.producer_cpu
            << " consumer_cpu=" << pair.consumer_cpu
            << " producer_per_core_passes=" << producer.passes
            << " consumer_per_core_passes=" << consumer.passes
            << " cross_core_passes=" << cross_core.passes
            << " independent_role=EXTERNALLY_ENFORCED"
            << (output_path ? " output=" + *output_path : std::string()) << '\n';
  // Diagnostic only (not part of the raw artifact schema): PerCoreQualificationEvidence
  // reduces call_failure_count/invalid_timespec_count into a single read_status_passes
  // bool, but the per-core delta-sequence stats (evaluate_clock_sequence's own real
  // regression/tie/percentile numbers) are printed here in full so a real failure's
  // exact cause is visible without re-deriving it from the raw timestamp stream.
  const auto print_per_core =
      [](std::string_view role,
         const cpu_prefetch::timing::PerCoreQualificationEvidence& evidence) {
        std::cout << "q15-clock-pair-qualification: per_core role=" << role
                  << " prime_count_passes=" << evidence.prime_count_passes
                  << " read_status_passes=" << evidence.read_status_passes
                  << " affinity_passes=" << evidence.affinity_passes
                  << " sequence_delta_count=" << evidence.sequence.delta_count
                  << " sequence_regression_count=" << evidence.sequence.regression_count
                  << " sequence_equal_count=" << evidence.sequence.equal_count
                  << " sequence_p999_delta_picoseconds="
                  << evidence.sequence.p999_delta_picoseconds
                  << " sequence_p99999_delta_picoseconds="
                  << evidence.sequence.p99999_delta_picoseconds
                  << " sequence_maximum_delta_picoseconds="
                  << evidence.sequence.maximum_delta_picoseconds
                  << " sequence_accepted_policy_sample_count="
                  << evidence.sequence.accepted_policy_sample_count
                  << " sequence_limits_pass=" << evidence.sequence.limits_pass
                  << " sequence_passes=" << evidence.sequence.passes << '\n';
      };
  print_per_core("producer", producer);
  print_per_core("consumer", consumer);
  return result.passes ? 0 : 1;
}

auto run(int argc, char** argv) -> int {
  if (argc == 2 && std::string_view(argv[1]) == "--self-test") {
    return self_test();
  }
  if (argc == 3 && std::string_view(argv[1]) == "--qualify-pair") {
    return qualify_pair(argv[2], std::nullopt);
  }
  if (argc == 5 && std::string_view(argv[1]) == "--qualify-pair" &&
      std::string_view(argv[3]) == "--output") {
    return qualify_pair(argv[2], std::string(argv[4]));
  }
  if (argc == 5 && std::string_view(argv[1]) == "--qualify-pair" &&
      (std::string_view(argv[3]) == "--prime-read-count" ||
       std::string_view(argv[3]) == "--delta-count")) {
    std::size_t count = 0U;
    const auto [pointer, error] =
        std::from_chars(argv[4], argv[4] + std::string_view(argv[4]).size(), count);
    if (error != std::errc{} || pointer != argv[4] + std::string_view(argv[4]).size()) {
      usage(std::cerr);
      return 2;
    }
    auto counts = kAcceptedClockPairQualificationCounts;
    if (std::string_view(argv[3]) == "--prime-read-count") {
      counts.prime_read_count = count;
    } else {
      counts.delta_count = count;
    }
    return qualify_pair(argv[2], std::nullopt, counts);
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
    std::cerr << "q15-clock-tool: FAIL unexpected exception: " << exception.what()
              << '\n';
  } catch (...) {
    std::cerr << "q15-clock-tool: FAIL unexpected non-standard exception\n";
  }
  return 1;
}
