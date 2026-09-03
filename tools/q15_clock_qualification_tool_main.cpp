#include "cpu_prefetch/platform/platform.hpp"
#include "cpu_prefetch/platform/q15_msr.hpp"
#include "cpu_prefetch/qualification/q15_clock_pair_qualification.hpp"
#include "cpu_prefetch/runner/runner.hpp"
#include "cpu_prefetch/timing/cross_core_exchange.hpp"

#include <atomic>
#include <iostream>
#include <string_view>

namespace {

using cpu_prefetch::qualification::kAcceptedClockPairQualificationCounts;
using cpu_prefetch::qualification::run_clock_pair_qualification;
using cpu_prefetch::runner::kFarWorkerPair;
using cpu_prefetch::runner::kNearWorkerPair;

void usage(std::ostream& output) {
  output << "Usage:\n"
         << "  cpu_prefetch_q15_clock_qualification_tool --self-test\n"
         << "  cpu_prefetch_q15_clock_qualification_tool --qualify-pair near\n"
         << "  cpu_prefetch_q15_clock_qualification_tool --qualify-pair far\n\n"
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
            "requires this to run on the accepted stand.\n";
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

auto qualify_pair(std::string_view pair_name) -> int {
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
  const auto result =
      run_clock_pair_qualification(pair, kAcceptedClockPairQualificationCounts);
  if (!result.producer_pinned || !result.consumer_pinned || !result.complete) {
    std::cerr << "q15-clock-tool: FAIL pair=" << pair_name
              << " producer_pinned=" << result.producer_pinned
              << " consumer_pinned=" << result.consumer_pinned
              << " complete=" << result.complete << '\n';
    return 1;
  }
  std::cout << "q15-clock-pair-qualification: " << (result.passes ? "PASS" : "FAIL")
            << " pair=" << pair_name << " producer_cpu=" << pair.producer_cpu
            << " consumer_cpu=" << pair.consumer_cpu
            << " producer_per_core_passes=" << result.producer_per_core->passes
            << " consumer_per_core_passes=" << result.consumer_per_core->passes
            << " cross_core_passes=" << result.cross_core->passes
            << " independent_role=EXTERNALLY_ENFORCED\n";
  return result.passes ? 0 : 1;
}

auto run(int argc, char** argv) -> int {
  if (argc == 2 && std::string_view(argv[1]) == "--self-test") {
    return self_test();
  }
  if (argc == 3 && std::string_view(argv[1]) == "--qualify-pair") {
    return qualify_pair(argv[2]);
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
