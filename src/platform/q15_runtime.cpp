#include "cpu_prefetch/platform/q15_runtime.hpp"

#include <algorithm>
#include <arpa/inet.h>
#include <array>
#include <cerrno>
#include <cstring>
#include <limits>
#include <linux/mempolicy.h>
#include <linux/perf_event.h>
#include <sched.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>
#include <utility>

namespace cpu_prefetch::platform {
namespace {

[[nodiscard]] auto error(ErrorCategory category, std::string rule, std::string message)
    -> Error {
  return {category, "$q15_dynamic", std::move(rule), std::move(message)};
}

[[nodiscard]] auto system_error(std::string rule, std::string operation) -> Error {
  const auto saved_errno = errno;
  return error(ErrorCategory::io_error, std::move(rule),
               std::move(operation) + " failed with errno " +
                   std::to_string(saved_errno));
}

[[nodiscard]] auto backend_success(std::string evidence) -> BackendResult {
  return {true, std::move(evidence), "complete", std::nullopt};
}

[[nodiscard]] auto backend_failure(ErrorCategory category, std::string detail)
    -> BackendResult {
  return {false, {}, std::move(detail), category};
}

[[nodiscard]] auto selected_cpu(std::uint32_t cpu) noexcept -> bool {
  return std::find(kHardwarePrefetchControlCpus.begin(),
                   kHardwarePrefetchControlCpus.end(),
                   cpu) != kHardwarePrefetchControlCpus.end();
}

[[nodiscard]] auto valid_sha256(std::string_view text) noexcept -> bool {
  return text.size() == 64U &&
         std::all_of(text.begin(), text.end(), [](char character) {
           return (character >= '0' && character <= '9') ||
                  (character >= 'a' && character <= 'f');
         });
}

[[nodiscard]] auto valid_peer(const Q15PeerCredentials& peer) noexcept -> bool {
  return peer.process_id > 0;
}

[[nodiscard]] auto backend_error(const BackendResult& result, std::string rule,
                                 std::string message) -> Error {
  return error(result.failure_category.value_or(ErrorCategory::io_error),
               std::move(rule), std::move(message) + ": " + result.detail);
}

[[nodiscard]] auto checked_fault_delta(std::uint64_t after, std::uint64_t before,
                                       std::uint64_t& output) noexcept -> bool {
  if (after < before) {
    return false;
  }
  output = after - before;
  return true;
}

[[nodiscard]] auto exact_request() noexcept -> Q15PerfEventRequest {
  return {PERF_TYPE_RAW,
          kQ15AllPrefetchPerfConfig,
          0,
          -1,
          -1,
          0U,
          true,
          false,
          true,
          false,
          true,
          true,
          true,
          true,
          true};
}

[[nodiscard]] auto run_traversal(Q15ProbeKind kind,
                                 Q15PreparedProbeMemory& memory) noexcept
    -> std::uint64_t {
  if (kind == Q15ProbeKind::regular_stream) {
    return cpu_prefetch_q15_regular_counted_traversal(memory.address(),
                                                      memory.line_count());
  }
  return cpu_prefetch_q15_pointer_counted_traversal(
      memory.line_count(), memory.address(), memory.start_index());
}

} // namespace

auto q15_perf_event_request() noexcept -> Q15PerfEventRequest {
  return exact_request();
}

auto is_exact_q15_perf_event_request(const Q15PerfEventRequest& request) noexcept
    -> bool {
  return request == exact_request();
}

auto LinuxQ15PerfOperations::open_event(const Q15PerfEventRequest& request)
    -> Result<int> {
  if (!is_exact_q15_perf_event_request(request)) {
    return Result<int>::failure(error(ErrorCategory::invalid_request,
                                      "Q15-PERF-REQUEST-EXACT",
                                      "only the frozen raw event request is allowed"));
  }
  perf_event_attr attributes{};
  attributes.type = request.type;
  attributes.size = sizeof(attributes);
  attributes.config = request.config;
  attributes.disabled = request.disabled ? 1U : 0U;
  attributes.inherit = request.inherit ? 1U : 0U;
  attributes.pinned = request.pinned ? 1U : 0U;
  attributes.exclude_user = request.exclude_user ? 1U : 0U;
  attributes.exclude_kernel = request.exclude_kernel ? 1U : 0U;
  attributes.exclude_hv = request.exclude_hypervisor ? 1U : 0U;
  attributes.exclude_guest = request.exclude_guest ? 1U : 0U;
  attributes.read_format =
      PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING;
  const auto descriptor =
      static_cast<int>(::syscall(SYS_perf_event_open, &attributes, request.pid,
                                 request.cpu, request.group_fd, request.flags));
  if (descriptor < 0) {
    return Result<int>::failure(system_error("Q15-PERF-OPEN", "fixed perf_event_open"));
  }
  return Result<int>::success(descriptor);
}

auto LinuxQ15PerfOperations::reset(int descriptor) noexcept -> bool {
  return ::ioctl(descriptor, PERF_EVENT_IOC_RESET, 0) == 0;
}

auto LinuxQ15PerfOperations::enable(int descriptor) noexcept -> bool {
  return ::ioctl(descriptor, PERF_EVENT_IOC_ENABLE, 0) == 0;
}

auto LinuxQ15PerfOperations::disable(int descriptor) noexcept -> bool {
  return ::ioctl(descriptor, PERF_EVENT_IOC_DISABLE, 0) == 0;
}

auto LinuxQ15PerfOperations::read(int descriptor) -> Result<Q15CounterReading> {
  std::array<std::uint64_t, 3U> values{};
  const auto count = ::read(descriptor, values.data(), sizeof(values));
  if (count != static_cast<std::ptrdiff_t>(sizeof(values))) {
    return Result<Q15CounterReading>::failure(
        system_error("Q15-PERF-READ", "complete fixed perf read"));
  }
  return Result<Q15CounterReading>::success({values[0], values[1], values[2]});
}

auto LinuxQ15PerfOperations::close(int descriptor) noexcept -> bool {
  return ::close(descriptor) == 0;
}

auto Q15ResidencySnapshot::passes(std::uint32_t expected_node,
                                  std::size_t expected_pages) const noexcept -> bool {
  return expected_pages != 0U && page_nodes.size() == expected_pages &&
         std::all_of(
             page_nodes.begin(), page_nodes.end(), [expected_node](std::int32_t node) {
               return node >= 0 && static_cast<std::uint32_t>(node) == expected_node;
             });
}

auto LinuxQ15PlatformOperations::bind_current_thread(std::uint32_t cpu)
    -> BackendResult {
  if (!selected_cpu(cpu) || cpu >= CPU_SETSIZE) {
    return backend_failure(ErrorCategory::invalid_request,
                           "CPU is outside the fixed Q15 domain");
  }
  cpu_set_t set;
  CPU_ZERO(&set);
  CPU_SET(cpu, &set);
  if (::sched_setaffinity(0, sizeof(set), &set) != 0) {
    return backend_failure(ErrorCategory::apply_failure,
                           "singleton sched_setaffinity failed");
  }
  return backend_success("Q15-SINGLETON-AFFINITY-APPLY");
}

auto LinuxQ15PlatformOperations::singleton_affinity_matches(std::uint32_t cpu)
    -> Result<bool> {
  if (!selected_cpu(cpu) || cpu >= CPU_SETSIZE) {
    return Result<bool>::failure(error(ErrorCategory::invalid_request,
                                       "Q15-AFFINITY-CPU",
                                       "CPU is outside the fixed Q15 domain"));
  }
  cpu_set_t set;
  CPU_ZERO(&set);
  if (::sched_getaffinity(0, sizeof(set), &set) != 0) {
    return Result<bool>::failure(
        system_error("Q15-AFFINITY-READBACK", "sched_getaffinity"));
  }
  return Result<bool>::success(CPU_COUNT(&set) == 1 && CPU_ISSET(cpu, &set));
}

auto LinuxQ15PlatformOperations::current_cpu() -> Result<std::uint32_t> {
  const auto cpu = ::sched_getcpu();
  if (cpu < 0) {
    return Result<std::uint32_t>::failure(
        system_error("Q15-ACTUAL-CPU", "sched_getcpu"));
  }
  return Result<std::uint32_t>::success(static_cast<std::uint32_t>(cpu));
}

auto LinuxQ15PlatformOperations::map_private_anonymous(std::size_t byte_count)
    -> Result<std::byte*> {
  if (byte_count == 0U) {
    return Result<std::byte*>::failure(error(ErrorCategory::invalid_request,
                                             "Q15-MMAP-SIZE",
                                             "mapping size must be positive"));
  }
  void* mapped = ::mmap(nullptr, byte_count, PROT_READ | PROT_WRITE,
                        MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  if (mapped == MAP_FAILED) {
    return Result<std::byte*>::failure(
        system_error("Q15-MMAP", "private anonymous mmap"));
  }
  return Result<std::byte*>::success(static_cast<std::byte*>(mapped));
}

auto LinuxQ15PlatformOperations::bind_memory(const Q15MemoryBindingRequest& request)
    -> BackendResult {
  if (request.address == nullptr || request.byte_count == 0U ||
      request.numa_node >= 64U) {
    return backend_failure(ErrorCategory::invalid_request,
                           "invalid fixed Q15 mbind request");
  }
  const unsigned long mask = 1UL << request.numa_node;
  if (::syscall(SYS_mbind, request.address, request.byte_count, MPOL_BIND, &mask, 64UL,
                0UL) != 0) {
    return backend_failure(ErrorCategory::apply_failure, "fixed MPOL_BIND failed");
  }
  return backend_success("Q15-MPOL-BIND");
}

auto LinuxQ15PlatformOperations::disable_transparent_huge_pages(std::byte* address,
                                                                std::size_t byte_count)
    -> BackendResult {
  if (address == nullptr || byte_count == 0U ||
      ::madvise(address, byte_count, MADV_NOHUGEPAGE) != 0) {
    return backend_failure(ErrorCategory::apply_failure, "MADV_NOHUGEPAGE failed");
  }
  return backend_success("Q15-MADV-NOHUGEPAGE");
}

auto LinuxQ15PlatformOperations::query_residency(std::byte* address,
                                                 std::size_t byte_count,
                                                 std::size_t page_bytes)
    -> Result<Q15ResidencySnapshot> {
  if (address == nullptr || byte_count == 0U || page_bytes == 0U ||
      byte_count % page_bytes != 0U) {
    return Result<Q15ResidencySnapshot>::failure(
        error(ErrorCategory::invalid_request, "Q15-MOVE-PAGES-RANGE",
              "residency range must contain whole nonzero pages"));
  }
  const auto count = byte_count / page_bytes;
  std::vector<void*> pages(count);
  std::vector<std::int32_t> status(count, -1);
  for (std::size_t index = 0U; index < count; ++index) {
    pages[index] = address + (index * page_bytes);
  }
  if (::syscall(SYS_move_pages, 0, count, pages.data(), nullptr, status.data(), 0) !=
      0) {
    return Result<Q15ResidencySnapshot>::failure(
        system_error("Q15-MOVE-PAGES", "exhaustive move_pages query"));
  }
  return Result<Q15ResidencySnapshot>::success({std::move(status)});
}

auto LinuxQ15PlatformOperations::thread_faults() -> Result<Q15ThreadFaults> {
  rusage usage{};
  if (::getrusage(RUSAGE_THREAD, &usage) != 0 || usage.ru_minflt < 0 ||
      usage.ru_majflt < 0) {
    return Result<Q15ThreadFaults>::failure(
        system_error("Q15-RUSAGE", "getrusage RUSAGE_THREAD"));
  }
  return Result<Q15ThreadFaults>::success(
      {static_cast<std::uint64_t>(usage.ru_minflt),
       static_cast<std::uint64_t>(usage.ru_majflt)});
}

auto LinuxQ15PlatformOperations::monotonic_raw_nanoseconds() -> Result<std::uint64_t> {
  timespec value{};
  if (::clock_gettime(CLOCK_MONOTONIC_RAW, &value) != 0 || value.tv_sec < 0 ||
      value.tv_nsec < 0 || value.tv_nsec >= 1'000'000'000L) {
    return Result<std::uint64_t>::failure(
        system_error("Q15-CLOCK", "CLOCK_MONOTONIC_RAW"));
  }
  const auto seconds = static_cast<std::uint64_t>(value.tv_sec);
  if (seconds > (std::numeric_limits<std::uint64_t>::max() -
                 static_cast<std::uint64_t>(value.tv_nsec)) /
                    1'000'000'000U) {
    return Result<std::uint64_t>::failure(
        error(ErrorCategory::invalid_request, "Q15-CLOCK-OVERFLOW",
              "CLOCK_MONOTONIC_RAW nanosecond conversion overflowed"));
  }
  return Result<std::uint64_t>::success(seconds * 1'000'000'000U +
                                        static_cast<std::uint64_t>(value.tv_nsec));
}

auto LinuxQ15PlatformOperations::unmap(std::byte* address, std::size_t byte_count)
    -> BackendResult {
  if (address == nullptr || byte_count == 0U || ::munmap(address, byte_count) != 0) {
    return backend_failure(ErrorCategory::io_error, "fixed probe munmap failed");
  }
  return backend_success("Q15-MUNMAP");
}

auto q15_expected_numa_node(std::uint32_t cpu) -> Result<std::uint32_t> {
  if (cpu == 0U || cpu == 1U) {
    return Result<std::uint32_t>::success(0U);
  }
  if (cpu == 26U) {
    return Result<std::uint32_t>::success(1U);
  }
  return Result<std::uint32_t>::failure(
      error(ErrorCategory::invalid_request, "Q15-CPU-NODE-DOMAIN",
            "Q15 accepts only CPU 0/1 on node 0 and CPU 26 on node 1"));
}

auto q15_working_set_bytes(const Q15ProbePlatformBinding& binding)
    -> Result<std::size_t> {
  const auto expected_node = q15_expected_numa_node(binding.cpu);
  if (!expected_node || expected_node.value() != binding.numa_node) {
    return Result<std::size_t>::failure(
        error(ErrorCategory::numa_mismatch, "Q15-WORKING-SET-NODE",
              "CPU and NUMA node do not match the accepted candidate topology"));
  }
  if (binding.verified_local_llc_bytes == 0U ||
      binding.verified_base_page_bytes != kQ15ProbeBasePageBytes ||
      binding.verified_local_llc_bytes >
          std::numeric_limits<std::uint64_t>::max() / 2U) {
    return Result<std::size_t>::failure(
        error(ErrorCategory::invalid_request, "Q15-WORKING-SET-INPUT",
              "positive LLC and exact verified 4096-byte base pages are required"));
  }
  const auto doubled = binding.verified_local_llc_bytes * 2U;
  const auto page = binding.verified_base_page_bytes;
  const auto remainder = doubled % page;
  const auto addition = remainder == 0U ? 0U : page - remainder;
  if (doubled > std::numeric_limits<std::uint64_t>::max() - addition) {
    return Result<std::size_t>::failure(
        error(ErrorCategory::invalid_request, "Q15-WORKING-SET-OVERFLOW",
              "rounded working-set byte count overflowed"));
  }
  const auto rounded = doubled + addition;
  if (rounded > std::numeric_limits<std::size_t>::max() ||
      rounded % kQ15ProbeCacheLineBytes != 0U) {
    return Result<std::size_t>::failure(
        error(ErrorCategory::invalid_request, "Q15-WORKING-SET-SIZE-T",
              "working-set byte count is not representable by this release"));
  }
  return Result<std::size_t>::success(static_cast<std::size_t>(rounded));
}

Q15PreparedProbeMemory::Q15PreparedProbeMemory(
    Q15PlatformOperations& operations, std::byte* address, std::size_t byte_count,
    Q15ProbePlatformBinding binding, Q15PointerProbePreparation preparation) noexcept
    : operations_(&operations), address_(address), byte_count_(byte_count),
      page_bytes_(static_cast<std::size_t>(binding.verified_base_page_bytes)),
      cpu_(binding.cpu), numa_node_(binding.numa_node),
      preparation_(std::move(preparation)) {}

auto Q15PreparedProbeMemory::create(const Q15ProbePlatformBinding& binding,
                                    Q15PlatformOperations& operations)
    -> Result<std::unique_ptr<Q15PreparedProbeMemory>> {
  const auto byte_count = q15_working_set_bytes(binding);
  if (!byte_count) {
    return Result<std::unique_ptr<Q15PreparedProbeMemory>>::failure(
        byte_count.errors());
  }
  const auto mapped = operations.map_private_anonymous(byte_count.value());
  if (!mapped) {
    return Result<std::unique_ptr<Q15PreparedProbeMemory>>::failure(mapped.errors());
  }
  auto* address = mapped.value();
  const auto cleanup = [&operations, address, &byte_count]() {
    static_cast<void>(operations.unmap(address, byte_count.value()));
  };
  const auto bound =
      operations.bind_memory({address, byte_count.value(), binding.numa_node});
  if (!bound.succeeded) {
    cleanup();
    return Result<std::unique_ptr<Q15PreparedProbeMemory>>::failure(
        backend_error(bound, "Q15-MEMORY-BIND", "target-node binding failed"));
  }
  const auto no_huge =
      operations.disable_transparent_huge_pages(address, byte_count.value());
  if (!no_huge.succeeded) {
    cleanup();
    return Result<std::unique_ptr<Q15PreparedProbeMemory>>::failure(backend_error(
        no_huge, "Q15-MEMORY-BASE-PAGES", "base-page mapping request failed"));
  }
  const auto affinity = operations.bind_current_thread(binding.cpu);
  if (!affinity.succeeded) {
    cleanup();
    return Result<std::unique_ptr<Q15PreparedProbeMemory>>::failure(
        backend_error(affinity, "Q15-PREP-AFFINITY",
                      "target-CPU affinity failed before first touch"));
  }
  const auto affinity_readback = operations.singleton_affinity_matches(binding.cpu);
  const auto actual_cpu = operations.current_cpu();
  if (!affinity_readback || !affinity_readback.value() || !actual_cpu ||
      actual_cpu.value() != binding.cpu) {
    cleanup();
    return Result<std::unique_ptr<Q15PreparedProbeMemory>>::failure(
        error(ErrorCategory::verification_mismatch, "Q15-PREP-AFFINITY-READBACK",
              "singleton affinity and actual CPU must pass before first touch"));
  }
  try {
    auto preparation = prepare_q15_pointer_probe_buffer(
        {address, byte_count.value()}, byte_count.value() / kQ15ProbeCacheLineBytes);
    return Result<std::unique_ptr<Q15PreparedProbeMemory>>::success(
        std::unique_ptr<Q15PreparedProbeMemory>(new Q15PreparedProbeMemory(
            operations, address, byte_count.value(), binding, std::move(preparation))));
  } catch (const std::exception& exception) {
    cleanup();
    return Result<std::unique_ptr<Q15PreparedProbeMemory>>::failure(
        error(ErrorCategory::apply_failure, "Q15-PREP-BUFFER",
              std::string("deterministic first-touch initialization failed: ") +
                  exception.what()));
  }
}

Q15PreparedProbeMemory::~Q15PreparedProbeMemory() {
  if (operations_ != nullptr && address_ != nullptr) {
    static_cast<void>(operations_->unmap(address_, byte_count_));
  }
}

auto Q15ProbePassObservation::residency_passes(
    std::uint32_t expected_node, std::size_t expected_pages) const noexcept -> bool {
  return before_residency.passes(expected_node, expected_pages) &&
         during_residency.passes(expected_node, expected_pages) &&
         after_residency.passes(expected_node, expected_pages);
}

auto Q15ProbePassObservation::cpu_passes(std::uint32_t expected_cpu) const noexcept
    -> bool {
  return singleton_affinity && entry_cpu == expected_cpu && exit_cpu == expected_cpu;
}

auto run_q15_probe_pass(Q15ProbeKind kind, Q15PreparedProbeMemory& memory,
                        Q15PerfOperations& perf, Q15PlatformOperations& platform)
    -> Result<Q15ProbePassObservation> {
  const auto affinity = platform.singleton_affinity_matches(memory.cpu());
  if (!affinity || !affinity.value()) {
    return Result<Q15ProbePassObservation>::failure(
        error(ErrorCategory::verification_mismatch, "Q15-PASS-AFFINITY",
              "counted pass requires singleton affinity readback"));
  }
  const auto before = platform.query_residency(memory.address(), memory.byte_count(),
                                               kQ15ProbeBasePageBytes);
  if (!before) {
    return Result<Q15ProbePassObservation>::failure(before.errors());
  }
  const auto prime_retention = run_traversal(kind, memory);
  const auto during = platform.query_residency(memory.address(), memory.byte_count(),
                                               kQ15ProbeBasePageBytes);
  if (!during) {
    return Result<Q15ProbePassObservation>::failure(during.errors());
  }
  const auto pre_hash = workload::sha256(memory.bytes());
  const bool cycle_before = validate_q15_pointer_cycle(
      memory.bytes(), memory.line_count(), memory.start_index());
  const auto faults_before = platform.thread_faults();
  const auto begin = platform.monotonic_raw_nanoseconds();
  const auto entry_cpu = platform.current_cpu();
  if (!faults_before || !begin || !entry_cpu) {
    return Result<Q15ProbePassObservation>::failure(
        !faults_before ? faults_before.errors()
                       : (!begin ? begin.errors() : entry_cpu.errors()));
  }
  const auto opened = perf.open_event(q15_perf_event_request());
  if (!opened) {
    return Result<Q15ProbePassObservation>::failure(opened.errors());
  }
  const auto descriptor = opened.value();
  const auto reset = perf.reset(descriptor);
  if (!reset) {
    static_cast<void>(perf.close(descriptor));
    return Result<Q15ProbePassObservation>::failure(
        error(ErrorCategory::io_error, "Q15-PASS-RESET", "counter reset failed"));
  }
  const auto counted =
      kind == Q15ProbeKind::regular_stream
          ? cpu_prefetch_q15_regular_counted_region(&perf, descriptor, memory.address(),
                                                    memory.line_count())
          : cpu_prefetch_q15_pointer_counted_region(&perf, descriptor, memory.address(),
                                                    memory.line_count(),
                                                    memory.start_index());
  if (!counted.enabled) {
    static_cast<void>(perf.close(descriptor));
    return Result<Q15ProbePassObservation>::failure(
        error(ErrorCategory::io_error, "Q15-PASS-ENABLE", "counter enable failed"));
  }
  if (!counted.disabled) {
    static_cast<void>(perf.close(descriptor));
    return Result<Q15ProbePassObservation>::failure(
        error(ErrorCategory::io_error, "Q15-PASS-DISABLE", "counter disable failed"));
  }
  const auto exit_cpu = platform.current_cpu();
  const auto end = platform.monotonic_raw_nanoseconds();
  const auto faults_after = platform.thread_faults();
  const auto counter = perf.read(descriptor);
  const auto closed = perf.close(descriptor);
  if (!exit_cpu || !end || !faults_after || !counter || !closed) {
    if (!exit_cpu) {
      return Result<Q15ProbePassObservation>::failure(exit_cpu.errors());
    }
    if (!end) {
      return Result<Q15ProbePassObservation>::failure(end.errors());
    }
    if (!faults_after) {
      return Result<Q15ProbePassObservation>::failure(faults_after.errors());
    }
    if (!counter) {
      return Result<Q15ProbePassObservation>::failure(counter.errors());
    }
    return Result<Q15ProbePassObservation>::failure(
        error(ErrorCategory::io_error, "Q15-PASS-CLOSE", "counter close failed"));
  }
  if (end.value() < begin.value()) {
    return Result<Q15ProbePassObservation>::failure(
        error(ErrorCategory::verification_mismatch, "Q15-PASS-CLOCK-ORDER",
              "diagnostic clock regressed"));
  }
  std::uint64_t minor_delta = 0U;
  std::uint64_t major_delta = 0U;
  if (!checked_fault_delta(faults_after.value().minor_faults,
                           faults_before.value().minor_faults, minor_delta) ||
      !checked_fault_delta(faults_after.value().major_faults,
                           faults_before.value().major_faults, major_delta)) {
    return Result<Q15ProbePassObservation>::failure(
        error(ErrorCategory::verification_mismatch, "Q15-PASS-FAULT-ORDER",
              "thread fault counters regressed"));
  }
  const auto after = platform.query_residency(memory.address(), memory.byte_count(),
                                              kQ15ProbeBasePageBytes);
  if (!after) {
    return Result<Q15ProbePassObservation>::failure(after.errors());
  }
  const auto post_hash = workload::sha256(memory.bytes());
  const auto final_index = kind == Q15ProbeKind::pointer_dependent
                               ? static_cast<std::uint32_t>(counted.retention_value)
                               : memory.start_index();
  Q15ProbePassObservation observation{kind,
                                      {counter.value(), minor_delta, major_delta},
                                      {pre_hash, post_hash,
                                       static_cast<std::uint64_t>(memory.line_count()),
                                       memory.start_index(), final_index, cycle_before},
                                      before.value(),
                                      during.value(),
                                      after.value(),
                                      entry_cpu.value(),
                                      exit_cpu.value(),
                                      affinity.value(),
                                      begin.value(),
                                      end.value(),
                                      prime_retention ^ counted.retention_value};
  return Result<Q15ProbePassObservation>::success(std::move(observation));
}

auto encode_q15_evidence_frame(std::string_view canonical_json,
                               std::size_t maximum_payload_bytes)
    -> Result<std::vector<std::byte>> {
  if (canonical_json.empty() || maximum_payload_bytes == 0U ||
      canonical_json.size() > maximum_payload_bytes ||
      canonical_json.size() > std::numeric_limits<std::uint32_t>::max() ||
      canonical_json.size() > std::numeric_limits<std::size_t>::max() - 4U) {
    return Result<std::vector<std::byte>>::failure(
        error(ErrorCategory::invalid_request, "Q15-FRAME-LENGTH",
              "canonical payload must fit the explicit nonzero frame limit and u32"));
  }
  const auto parsed = protocol::json::parse(canonical_json);
  if (!parsed) {
    return Result<std::vector<std::byte>>::failure(
        error(ErrorCategory::parse_error, "Q15-FRAME-JSON",
              "frame payload must be valid JSON"));
  }
  const auto canonical = protocol::json::canonicalize(parsed.value());
  if (!canonical || canonical.value() != canonical_json) {
    return Result<std::vector<std::byte>>::failure(
        error(ErrorCategory::invalid_request, "Q15-FRAME-CANONICAL",
              "frame payload must already be exact JCS-I64-v1 bytes"));
  }
  std::vector<std::byte> frame(4U + canonical_json.size());
  const auto network_size = ::htonl(static_cast<std::uint32_t>(canonical_json.size()));
  std::memcpy(frame.data(), &network_size, sizeof(network_size));
  std::memcpy(frame.data() + 4U, canonical_json.data(), canonical_json.size());
  return Result<std::vector<std::byte>>::success(std::move(frame));
}

auto decode_q15_evidence_frame(std::span<const std::byte> frame,
                               std::size_t maximum_payload_bytes)
    -> Result<std::string> {
  if (frame.size() < 4U || maximum_payload_bytes == 0U) {
    return Result<std::string>::failure(
        error(ErrorCategory::parse_error, "Q15-FRAME-HEADER",
              "frame requires a u32be header and explicit nonzero limit"));
  }
  std::uint32_t network_size = 0U;
  std::memcpy(&network_size, frame.data(), sizeof(network_size));
  const auto payload_size = static_cast<std::size_t>(::ntohl(network_size));
  if (payload_size == 0U || payload_size > maximum_payload_bytes ||
      payload_size != frame.size() - 4U) {
    return Result<std::string>::failure(
        error(ErrorCategory::parse_error, "Q15-FRAME-EXACT-LENGTH",
              "frame header must equal the exact bounded payload byte count"));
  }
  std::string payload(payload_size, '\0');
  std::memcpy(payload.data(), frame.data() + 4U, payload_size);
  const auto encoded = encode_q15_evidence_frame(payload, maximum_payload_bytes);
  if (!encoded ||
      encoded.value() != std::vector<std::byte>(frame.begin(), frame.end())) {
    return Result<std::string>::failure(
        error(ErrorCategory::parse_error, "Q15-FRAME-CANONICAL",
              "decoded frame payload is not exact canonical JSON"));
  }
  return Result<std::string>::success(std::move(payload));
}

auto LinuxQ15LocalSocketOperations::create_listener(std::string_view abstract_name)
    -> Result<int> {
  if (!abstract_name.starts_with(kQ15AbstractSocketPrefix) ||
      abstract_name.size() + 1U > sizeof(sockaddr_un::sun_path)) {
    return Result<int>::failure(
        error(ErrorCategory::invalid_request, "Q15-SOCKET-NAME",
              "local abstract endpoint requires the fixed prefix and bounded name"));
  }
  const auto descriptor = ::socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0);
  if (descriptor < 0) {
    return Result<int>::failure(
        system_error("Q15-SOCKET-CREATE", "AF_UNIX SOCK_SEQPACKET socket"));
  }
  sockaddr_un address{};
  address.sun_family = AF_UNIX;
  address.sun_path[0] = '\0';
  std::memcpy(address.sun_path + 1, abstract_name.data(), abstract_name.size());
  const auto length = static_cast<socklen_t>(offsetof(sockaddr_un, sun_path) + 1U +
                                             abstract_name.size());
  if (::bind(descriptor, reinterpret_cast<const sockaddr*>(&address), length) != 0 ||
      ::listen(descriptor, 1) != 0) {
    const auto failure =
        system_error("Q15-SOCKET-LISTEN", "fixed abstract AF_UNIX bind/listen");
    static_cast<void>(::close(descriptor));
    return Result<int>::failure(failure);
  }
  return Result<int>::success(descriptor);
}

auto LinuxQ15LocalSocketOperations::accept_peer(int listener_descriptor)
    -> Result<Q15AcceptedPeer> {
  const auto peer = ::accept4(listener_descriptor, nullptr, nullptr, SOCK_CLOEXEC);
  if (peer < 0) {
    return Result<Q15AcceptedPeer>::failure(
        system_error("Q15-SOCKET-ACCEPT", "fixed local peer accept"));
  }
  ucred credentials{};
  socklen_t size = sizeof(credentials);
  if (::getsockopt(peer, SOL_SOCKET, SO_PEERCRED, &credentials, &size) != 0 ||
      size != sizeof(credentials) || credentials.pid <= 0) {
    const auto failure = system_error("Q15-SOCKET-PEERCRED", "SO_PEERCRED");
    static_cast<void>(::close(peer));
    return Result<Q15AcceptedPeer>::failure(failure);
  }
  return Result<Q15AcceptedPeer>::success(
      {peer,
       {credentials.pid, static_cast<std::uint32_t>(credentials.uid),
        static_cast<std::uint32_t>(credentials.gid)}});
}

auto LinuxQ15LocalSocketOperations::receive_frame(int peer_descriptor,
                                                  Q15FrameLimit limit)
    -> Result<std::string> {
  const auto maximum_payload_bytes = limit.maximum_payload_bytes;
  if (maximum_payload_bytes == 0U ||
      maximum_payload_bytes > std::numeric_limits<std::uint32_t>::max() ||
      maximum_payload_bytes > std::numeric_limits<std::size_t>::max() - 4U) {
    return Result<std::string>::failure(
        error(ErrorCategory::invalid_request, "Q15-SOCKET-RECEIVE-LIMIT",
              "receive requires an explicit positive u32 payload bound"));
  }
  std::vector<std::byte> buffer(maximum_payload_bytes + 4U);
  const auto count = ::recv(peer_descriptor, buffer.data(), buffer.size(), MSG_TRUNC);
  if (count <= 0 || static_cast<std::size_t>(count) > buffer.size()) {
    return Result<std::string>::failure(
        system_error("Q15-SOCKET-RECEIVE", "one complete local frame receive"));
  }
  buffer.resize(static_cast<std::size_t>(count));
  return decode_q15_evidence_frame(buffer, maximum_payload_bytes);
}

auto LinuxQ15LocalSocketOperations::send_frame(int peer_descriptor,
                                               std::string_view canonical_json,
                                               std::size_t maximum_payload_bytes)
    -> BackendResult {
  const auto frame = encode_q15_evidence_frame(canonical_json, maximum_payload_bytes);
  if (!frame) {
    return backend_failure(ErrorCategory::invalid_request,
                           "canonical frame construction failed");
  }
  const auto count =
      ::send(peer_descriptor, frame.value().data(), frame.value().size(), MSG_NOSIGNAL);
  if (count != static_cast<std::ptrdiff_t>(frame.value().size())) {
    return backend_failure(ErrorCategory::io_error,
                           "one complete local frame send failed");
  }
  return backend_success("Q15-LOCAL-FRAME-SEND");
}

auto LinuxQ15LocalSocketOperations::close_socket(int descriptor) -> BackendResult {
  if (::close(descriptor) != 0) {
    return backend_failure(ErrorCategory::io_error, "local socket close failed");
  }
  return backend_success("Q15-LOCAL-SOCKET-CLOSE");
}

auto to_string(Q15SessionState state) noexcept -> std::string_view {
  switch (state) {
  case Q15SessionState::created:
    return "CREATED";
  case Q15SessionState::h0_regular_complete:
    return "H0_REGULAR_COMPLETE";
  case Q15SessionState::h0_pointer_complete:
    return "H0_POINTER_COMPLETE";
  case Q15SessionState::h0_sealed_waiting_for_q15_w:
    return "H0_SEALED_WAITING_FOR_Q15_W";
  case Q15SessionState::h1_readback_verified:
    return "H1_READBACK_VERIFIED";
  case Q15SessionState::h1_regular_complete:
    return "H1_REGULAR_COMPLETE";
  case Q15SessionState::h1_pointer_complete:
    return "H1_POINTER_COMPLETE";
  case Q15SessionState::restoration_readback_verified:
    return "RESTORATION_READBACK_VERIFIED";
  case Q15SessionState::completed:
    return "COMPLETED";
  case Q15SessionState::failed:
    return "FAILED";
  }
  return "UNKNOWN";
}

Q15ProbeSessionStateMachine::Q15ProbeSessionStateMachine(
    Q15SessionBinding binding, const Q15PreparedProbeMemory& memory)
    : binding_(std::move(binding)), memory_(&memory), buffer_address_(memory.address()),
      buffer_byte_count_(memory.byte_count()),
      prepared_sha256_(memory.prepared_sha256()) {}

auto Q15ProbeSessionStateMachine::create(const Q15SessionBinding& binding,
                                         const Q15PreparedProbeMemory& memory)
    -> Result<std::unique_ptr<Q15ProbeSessionStateMachine>> {
  const auto expected_node = q15_expected_numa_node(binding.cpu);
  const auto expected_bytes = q15_working_set_bytes({binding.cpu, binding.numa_node,
                                                     binding.verified_local_llc_bytes,
                                                     binding.verified_base_page_bytes});
  if (binding.session_id.empty() || binding.stand_id.empty() ||
      binding.binding_id.empty() || !valid_sha256(binding.q15_r_authorization_sha256) ||
      !valid_sha256(binding.binary_sha256) ||
      !valid_sha256(binding.probe_contract_sha256) ||
      !valid_sha256(binding.probe_implementation_profile_sha256) ||
      !valid_sha256(binding.dynamic_implementation_profile_sha256) || !expected_node ||
      !expected_bytes || expected_node.value() != binding.numa_node ||
      memory.cpu() != binding.cpu || memory.numa_node() != binding.numa_node ||
      memory.byte_count() != expected_bytes.value() ||
      memory.page_bytes() != binding.verified_base_page_bytes ||
      !valid_peer(binding.q15_r_controller) || !valid_peer(binding.q15_w_controller) ||
      binding.q15_r_controller.user_id == binding.q15_w_controller.user_id ||
      binding.h1_complete_value !=
          (binding.h0_complete_value | kHardwarePrefetchDisableMask) ||
      binding.h1_complete_value == binding.h0_complete_value ||
      binding.expires_at_monotonic_nanoseconds == 0U || memory.address() == nullptr ||
      memory.byte_count() == 0U ||
      workload::sha256(memory.bytes()) != memory.prepared_sha256()) {
    return Result<std::unique_ptr<Q15ProbeSessionStateMachine>>::failure(
        error(ErrorCategory::invalid_request, "Q15-SESSION-BINDING",
              "complete exact session, profiles, CPU/node, LLC/page, H0/H1, expiry, "
              "hash, and buffer binding is required"));
  }
  return Result<std::unique_ptr<Q15ProbeSessionStateMachine>>::success(
      std::unique_ptr<Q15ProbeSessionStateMachine>(
          new Q15ProbeSessionStateMachine(binding, memory)));
}

auto Q15ProbeSessionStateMachine::fail(Error failure, Q15PeerCredentials peer,
                                       std::uint64_t at_monotonic_nanoseconds)
    -> Result<Q15SessionTransition> {
  if (state_ != Q15SessionState::failed) {
    failure_ = Q15SessionFailure{state_, at_monotonic_nanoseconds, peer, failure};
    state_ = Q15SessionState::failed;
  }
  return Result<Q15SessionTransition>::failure(std::move(failure));
}

auto Q15ProbeSessionStateMachine::record_control_disconnect(
    Q15PeerCredentials peer, std::uint64_t at_monotonic_nanoseconds)
    -> Result<Q15SessionTransition> {
  if (state_ == Q15SessionState::completed) {
    return Result<Q15SessionTransition>::failure(
        error(ErrorCategory::stale_state, "Q15-SESSION-TERMINAL",
              "completed session ignores later control disconnects"));
  }
  return fail(error(ErrorCategory::io_error, "Q15-SESSION-DISCONNECT",
                    "control peer disconnected before session completion"),
              peer, at_monotonic_nanoseconds);
}

auto Q15ProbeSessionStateMachine::buffer_identity_unchanged(
    const Q15PreparedProbeMemory& memory) const -> bool {
  return memory.address() == buffer_address_ &&
         memory.byte_count() == buffer_byte_count_ &&
         memory.prepared_sha256() == prepared_sha256_ &&
         workload::sha256(memory.bytes()) == prepared_sha256_;
}

auto Q15ProbeSessionStateMachine::advance(const Q15SessionActionInput& input)
    -> Result<Q15SessionTransition> {
  if (state_ == Q15SessionState::completed) {
    return Result<Q15SessionTransition>::failure(
        error(ErrorCategory::stale_state, "Q15-SESSION-TERMINAL",
              "completed session cannot accept another action"));
  }
  const auto reject = [&](Error failure) {
    return fail(std::move(failure), input.peer, input.now_monotonic_nanoseconds);
  };
  if (state_ == Q15SessionState::failed) {
    return reject(error(ErrorCategory::stale_state, "Q15-SESSION-TERMINAL",
                        "failed session cannot accept another action"));
  }
  if (input.now_monotonic_nanoseconds >= binding_.expires_at_monotonic_nanoseconds) {
    return reject(error(ErrorCategory::stale_state, "Q15-SESSION-EXPIRED",
                        "session authorization lifetime expired"));
  }
  if (input.buffer_address != buffer_address_ ||
      input.buffer_sha256 != prepared_sha256_ || memory_ == nullptr ||
      workload::sha256(memory_->bytes()) != prepared_sha256_ ||
      input.evidence_artifact_id.empty() || !valid_sha256(input.evidence_sha256)) {
    return reject(error(ErrorCategory::verification_mismatch,
                        "Q15-SESSION-EVIDENCE-BINDING",
                        "same buffer and complete evidence identity are required"));
  }

  std::optional<Q15SessionState> next;
  switch (input.action) {
  case Q15SessionAction::record_h0_regular:
    if (state_ != Q15SessionState::created || input.peer != binding_.q15_r_controller ||
        input.authorization_sha256 != binding_.q15_r_authorization_sha256) {
      return reject(error(ErrorCategory::stale_state, "Q15-SESSION-H0-REGULAR",
                          "H0 regular requires the exact Q15-R controller and state"));
    }
    next = Q15SessionState::h0_regular_complete;
    break;
  case Q15SessionAction::record_h0_pointer:
    if (state_ != Q15SessionState::h0_regular_complete ||
        input.peer != binding_.q15_r_controller ||
        input.authorization_sha256 != binding_.q15_r_authorization_sha256) {
      return reject(error(ErrorCategory::stale_state, "Q15-SESSION-H0-POINTER",
                          "H0 pointer must follow exact H0 regular evidence"));
    }
    next = Q15SessionState::h0_pointer_complete;
    break;
  case Q15SessionAction::seal_h0:
    if (state_ != Q15SessionState::h0_pointer_complete ||
        input.peer != binding_.q15_r_controller ||
        input.authorization_sha256 != binding_.q15_r_authorization_sha256 ||
        !valid_sha256(input.q15_r_evidence_set_sha256)) {
      return reject(error(ErrorCategory::stale_state, "Q15-SESSION-H0-SEAL",
                          "H0 seal requires the exact complete Q15-R evidence hash"));
    }
    q15_r_evidence_set_sha256_ = input.q15_r_evidence_set_sha256;
    next = Q15SessionState::h0_sealed_waiting_for_q15_w;
    break;
  case Q15SessionAction::verify_h1_readback:
    if (state_ != Q15SessionState::h0_sealed_waiting_for_q15_w ||
        input.peer != binding_.q15_w_controller ||
        !valid_sha256(input.authorization_sha256) ||
        input.authorization_sha256 == binding_.q15_r_authorization_sha256 ||
        input.q15_r_evidence_set_sha256 != q15_r_evidence_set_sha256_ ||
        input.observed_complete_value != binding_.h1_complete_value) {
      return reject(error(
          ErrorCategory::verification_mismatch, "Q15-SESSION-H1-READBACK",
          "H1 requires later Q15-W, sealed Q15-R, and exact independent readback"));
    }
    q15_w_authorization_sha256_ = input.authorization_sha256;
    next = Q15SessionState::h1_readback_verified;
    break;
  case Q15SessionAction::record_h1_regular:
    if (state_ != Q15SessionState::h1_readback_verified ||
        input.peer != binding_.q15_w_controller ||
        input.authorization_sha256 != q15_w_authorization_sha256_) {
      return reject(error(ErrorCategory::stale_state, "Q15-SESSION-H1-REGULAR",
                          "H1 regular requires exact verified Q15-W state"));
    }
    next = Q15SessionState::h1_regular_complete;
    break;
  case Q15SessionAction::record_h1_pointer:
    if (state_ != Q15SessionState::h1_regular_complete ||
        input.peer != binding_.q15_w_controller ||
        input.authorization_sha256 != q15_w_authorization_sha256_) {
      return reject(error(ErrorCategory::stale_state, "Q15-SESSION-H1-POINTER",
                          "H1 pointer must follow exact H1 regular evidence"));
    }
    next = Q15SessionState::h1_pointer_complete;
    break;
  case Q15SessionAction::verify_restoration_readback:
    if (state_ != Q15SessionState::h1_pointer_complete ||
        input.peer != binding_.q15_w_controller ||
        input.authorization_sha256 != q15_w_authorization_sha256_ ||
        input.observed_complete_value != binding_.h0_complete_value) {
      return reject(
          error(ErrorCategory::verification_mismatch, "Q15-SESSION-RESTORE-READBACK",
                "completion requires exact independent complete H0 readback"));
    }
    next = Q15SessionState::restoration_readback_verified;
    break;
  case Q15SessionAction::finalize:
    if (state_ != Q15SessionState::restoration_readback_verified ||
        input.peer != binding_.q15_w_controller ||
        input.authorization_sha256 != q15_w_authorization_sha256_) {
      return reject(error(ErrorCategory::stale_state, "Q15-SESSION-FINALIZE",
                          "only restored exact Q15-W session can finalize"));
    }
    next = Q15SessionState::completed;
    break;
  }

  if (!next) {
    return reject(error(ErrorCategory::invalid_request, "Q15-SESSION-ACTION",
                        "session action enum is unregistered"));
  }

  Q15SessionTransition transition{state_,
                                  *next,
                                  input.action,
                                  input.now_monotonic_nanoseconds,
                                  input.peer,
                                  input.evidence_artifact_id,
                                  input.evidence_sha256};
  state_ = *next;
  transitions_.push_back(transition);
  return Result<Q15SessionTransition>::success(std::move(transition));
}

} // namespace cpu_prefetch::platform
