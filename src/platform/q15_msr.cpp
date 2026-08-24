#include "cpu_prefetch/platform/q15_msr.hpp"

#include <algorithm>
#include <array>
#include <cerrno>
#include <cpuid.h>
#include <fcntl.h>
#include <string>
#include <sys/types.h>
#include <unistd.h>

namespace cpu_prefetch::platform {
namespace {

[[nodiscard]] auto error(ErrorCategory category, std::string rule, std::string message)
    -> Error {
  return {category, "$q15_fixed_msr", std::move(rule), std::move(message)};
}

[[nodiscard]] auto allowed_cpu(std::uint32_t cpu) noexcept -> bool {
  return std::find(kHardwarePrefetchControlCpus.begin(),
                   kHardwarePrefetchControlCpus.end(),
                   cpu) != kHardwarePrefetchControlCpus.end();
}

[[nodiscard]] auto device_path(std::uint32_t cpu) -> std::string {
  return "/dev/cpu/" + std::to_string(cpu) + "/msr";
}

[[nodiscard]] auto msr_io_error(std::string rule, std::string operation) -> Error {
  const auto saved_errno = errno;
  return error(ErrorCategory::io_error, std::move(rule),
               std::move(operation) + " failed with errno " +
                   std::to_string(saved_errno));
}

[[nodiscard]] auto plan_value(std::span<const HardwarePrefetchMsrValue> values,
                              std::uint32_t cpu) -> const HardwarePrefetchMsrValue* {
  const auto position =
      std::find_if(values.begin(), values.end(),
                   [cpu](const auto& value) { return value.cpu == cpu; });
  return position == values.end() ? nullptr : &*position;
}

} // namespace

auto SystemPosixFileOperations::open_file(const char* path, int flags) -> int {
  return ::open(path, flags);
}

auto SystemPosixFileOperations::read_at(int descriptor, void* buffer, std::size_t size,
                                        FileOffset offset) -> std::ptrdiff_t {
  return ::pread(descriptor, buffer, size, static_cast<off_t>(offset.value));
}

auto SystemPosixFileOperations::write_at(int descriptor, const void* buffer,
                                         std::size_t size, FileOffset offset)
    -> std::ptrdiff_t {
  return ::pwrite(descriptor, buffer, size, static_cast<off_t>(offset.value));
}

auto SystemPosixFileOperations::close_file(int descriptor) -> int {
  return ::close(descriptor);
}

LinuxHardwarePrefetchMsrBackend::LinuxHardwarePrefetchMsrBackend(
    PosixFileOperations& files, FixedMsrAccess access) noexcept
    : files_(files), access_(access) {}

auto LinuxHardwarePrefetchMsrBackend::backend_id() const -> std::string_view {
  return access_ == FixedMsrAccess::read_only ? kQ15ReadBackendId : kQ15WriteBackendId;
}

auto LinuxHardwarePrefetchMsrBackend::read(std::uint32_t cpu) -> Result<std::uint64_t> {
  if (!allowed_cpu(cpu)) {
    return Result<std::uint64_t>::failure(
        error(ErrorCategory::invalid_request, "Q15-MSR-CPU-WHITELIST",
              "fixed MSR reads accept only CPUs 0, 1, and 26"));
  }
  const auto path = device_path(cpu);
  const auto descriptor = files_.open_file(path.c_str(), O_RDONLY | O_CLOEXEC);
  if (descriptor < 0) {
    return Result<std::uint64_t>::failure(
        msr_io_error("Q15-MSR-OPEN-READ", "fixed MSR read open"));
  }
  std::uint64_t value = 0U;
  const auto count = files_.read_at(descriptor, &value, sizeof(value),
                                    FileOffset{kHardwarePrefetchMsr});
  const auto read_errno = errno;
  const auto close_result = files_.close_file(descriptor);
  if (count != static_cast<std::ptrdiff_t>(sizeof(value))) {
    errno = read_errno;
    return Result<std::uint64_t>::failure(
        msr_io_error("Q15-MSR-READ-EXACT", "complete 64-bit fixed MSR read"));
  }
  if (close_result != 0) {
    return Result<std::uint64_t>::failure(
        msr_io_error("Q15-MSR-CLOSE-READ", "fixed MSR read close"));
  }
  return Result<std::uint64_t>::success(value);
}

// The existing HardwarePrefetchMsrBackend virtual contract fixes this order.
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
auto LinuxHardwarePrefetchMsrBackend::write(std::uint32_t cpu, std::uint64_t value)
    -> BackendResult {
  if (access_ != FixedMsrAccess::read_write) {
    return {false,
            {},
            "read-only fixed MSR backend rejected a write",
            ErrorCategory::privilege_denied};
  }
  if (!allowed_cpu(cpu)) {
    return {false,
            {},
            "fixed MSR writes accept only CPUs 0, 1, and 26",
            ErrorCategory::invalid_request};
  }
  const auto path = device_path(cpu);
  const auto descriptor = files_.open_file(path.c_str(), O_WRONLY | O_CLOEXEC);
  if (descriptor < 0) {
    return {false, {}, "fixed MSR write open failed", ErrorCategory::io_error};
  }
  const auto count = files_.write_at(descriptor, &value, sizeof(value),
                                     FileOffset{kHardwarePrefetchMsr});
  const auto close_result = files_.close_file(descriptor);
  if (count != static_cast<std::ptrdiff_t>(sizeof(value)) || close_result != 0) {
    return {
        false, {}, "complete 64-bit fixed MSR write failed", ErrorCategory::io_error};
  }
  return {true, "Q15-FIXED-MSR-WRITE", "complete fixed value written", std::nullopt};
}

auto decode_x86_family_model(std::uint32_t leaf1_eax) noexcept -> CpuFamilyModel {
  const auto base_family = (leaf1_eax >> 8U) & 0x0fU;
  const auto extended_family = (leaf1_eax >> 20U) & 0xffU;
  const auto base_model = (leaf1_eax >> 4U) & 0x0fU;
  const auto extended_model = (leaf1_eax >> 16U) & 0x0fU;
  const auto family =
      base_family == 0x0fU ? base_family + extended_family : base_family;
  const auto model = base_family == 0x06U || base_family == 0x0fU
                         ? (extended_model << 4U) | base_model
                         : base_model;
  return {family, model};
}

auto read_x86_family_model() -> Result<CpuFamilyModel> {
  std::uint32_t eax = 0U;
  std::uint32_t ebx = 0U;
  std::uint32_t ecx = 0U;
  std::uint32_t edx = 0U;
  if (__get_cpuid(1U, &eax, &ebx, &ecx, &edx) == 0) {
    return Result<CpuFamilyModel>::failure(error(ErrorCategory::missing_evidence,
                                                 "Q15-CPUID-LEAF1",
                                                 "CPUID leaf 1 is unavailable"));
  }
  return Result<CpuFamilyModel>::success(decode_x86_family_model(eax));
}

auto perform_hardware_prefetch_transition(const HardwarePrefetchPlan& plan,
                                          std::uint32_t cpu,
                                          HardwarePrefetchTransition transition,
                                          HardwarePrefetchMsrBackend& writer)
    -> Result<HardwarePrefetchMsrValue> {
  if (!allowed_cpu(cpu) || writer.backend_id().empty()) {
    return Result<HardwarePrefetchMsrValue>::failure(
        error(ErrorCategory::invalid_request, "Q15-TRANSITION-IDENTITY",
              "transition requires a selected CPU and named writer backend"));
  }
  const auto validated = make_hardware_prefetch_plan(
      {kIntelFamily6, kIntelModel55}, plan.requested_state, plan.prestate);
  if (!validated || !plan.mutating ||
      plan.requested_state != protocol::RequestedHardwareState::h1 ||
      plan.requested != validated.value().requested) {
    return Result<HardwarePrefetchMsrValue>::failure(
        error(ErrorCategory::invalid_request, "Q15-TRANSITION-PLAN",
              "transition requires the exact accepted H1 plan"));
  }
  const auto* prior = plan_value(plan.prestate, cpu);
  const auto* requested = plan_value(plan.requested, cpu);
  if (prior == nullptr || requested == nullptr) {
    return Result<HardwarePrefetchMsrValue>::failure(
        error(ErrorCategory::missing_evidence, "Q15-TRANSITION-CPU",
              "transition plan has no complete value for the selected CPU"));
  }
  const auto expected_current = transition == HardwarePrefetchTransition::apply_h1
                                    ? prior->value
                                    : requested->value;
  const auto target = transition == HardwarePrefetchTransition::apply_h1
                          ? requested->value
                          : prior->value;
  const auto observed = writer.read(cpu);
  if (!observed || observed.value() != expected_current) {
    return Result<HardwarePrefetchMsrValue>::failure(
        error(ErrorCategory::stale_state, "Q15-TRANSITION-PRECONDITION",
              "current complete value differs from the authorization-bound value"));
  }
  const auto written = writer.write(cpu, target);
  if (!written.succeeded) {
    return Result<HardwarePrefetchMsrValue>::failure(
        error(written.failure_category.value_or(ErrorCategory::apply_failure),
              "Q15-TRANSITION-WRITE", "exact complete-value transition failed"));
  }
  return Result<HardwarePrefetchMsrValue>::success({cpu, target});
}

} // namespace cpu_prefetch::platform
