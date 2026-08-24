#ifndef CPU_PREFETCH_PLATFORM_Q15_MSR_HPP
#define CPU_PREFETCH_PLATFORM_Q15_MSR_HPP

#include "cpu_prefetch/platform/platform.hpp"

#include <cstddef>
#include <cstdint>
#include <string_view>

namespace cpu_prefetch::platform {

inline constexpr std::string_view kQ15QualificationToolProfileId =
    "Q15-FIXED-QUALIFICATION-TOOL-v1";
inline constexpr std::string_view kQ15ReadBackendId =
    "Q15-LINUX-MSR-READONLY-06_55H-1A4-v1";
inline constexpr std::string_view kQ15WriteBackendId =
    "Q15-LINUX-MSR-WRITER-06_55H-1A4-v1";

enum class FixedMsrAccess : std::uint8_t { read_only, read_write };
enum class HardwarePrefetchTransition : std::uint8_t { apply_h1, restore_h0 };

struct FileOffset final {
  std::uint64_t value;
};

// System-call seam used only to test the fixed Linux adapter without opening an
// MSR device. LinuxHardwarePrefetchMsrBackend supplies every path, flag, size,
// and offset; callers cannot pass an MSR address, path, or mask to that backend.
class PosixFileOperations {
public:
  virtual ~PosixFileOperations() = default;
  [[nodiscard]] virtual auto open_file(const char* path, int flags) -> int = 0;
  [[nodiscard]] virtual auto read_at(int descriptor, void* buffer, std::size_t size,
                                     FileOffset offset) -> std::ptrdiff_t = 0;
  [[nodiscard]] virtual auto write_at(int descriptor, const void* buffer,
                                      std::size_t size, FileOffset offset)
      -> std::ptrdiff_t = 0;
  [[nodiscard]] virtual auto close_file(int descriptor) -> int = 0;
};

class SystemPosixFileOperations final : public PosixFileOperations {
public:
  [[nodiscard]] auto open_file(const char* path, int flags) -> int override;
  [[nodiscard]] auto read_at(int descriptor, void* buffer, std::size_t size,
                             FileOffset offset) -> std::ptrdiff_t override;
  [[nodiscard]] auto write_at(int descriptor, const void* buffer, std::size_t size,
                              FileOffset offset) -> std::ptrdiff_t override;
  [[nodiscard]] auto close_file(int descriptor) -> int override;
};

class LinuxHardwarePrefetchMsrBackend final : public HardwarePrefetchMsrBackend {
public:
  LinuxHardwarePrefetchMsrBackend(PosixFileOperations& files,
                                  FixedMsrAccess access) noexcept;

  [[nodiscard]] auto backend_id() const -> std::string_view override;
  [[nodiscard]] auto read(std::uint32_t cpu) -> Result<std::uint64_t> override;
  [[nodiscard]] auto write(std::uint32_t cpu, std::uint64_t value)
      -> BackendResult override;

private:
  PosixFileOperations& files_;
  FixedMsrAccess access_;
};

// Decode CPUID.01H:EAX using Intel's architectural family/model encoding. The
// production tool checks the result before any fixed MSR operation.
[[nodiscard]] auto decode_x86_family_model(std::uint32_t leaf1_eax) noexcept
    -> CpuFamilyModel;
[[nodiscard]] auto read_x86_family_model() -> Result<CpuFamilyModel>;

// Perform exactly one already-planned CPU transition. This helper checks the
// current complete value before writing but intentionally does not self-verify;
// ADR-0051 requires the separately authorized auditor/readback command to do
// that. It exposes no retry and no arbitrary MSR/mask/path.
[[nodiscard]] auto perform_hardware_prefetch_transition(
    const HardwarePrefetchPlan& plan, std::uint32_t cpu,
    HardwarePrefetchTransition transition, HardwarePrefetchMsrBackend& writer)
    -> Result<HardwarePrefetchMsrValue>;

} // namespace cpu_prefetch::platform

#endif // CPU_PREFETCH_PLATFORM_Q15_MSR_HPP
