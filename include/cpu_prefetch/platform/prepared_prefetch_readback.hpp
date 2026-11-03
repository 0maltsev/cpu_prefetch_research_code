#ifndef CPU_PREFETCH_PLATFORM_PREPARED_PREFETCH_READBACK_HPP
#define CPU_PREFETCH_PLATFORM_PREPARED_PREFETCH_READBACK_HPP

#include "cpu_prefetch/platform/owner_mapping.hpp"
#include "cpu_prefetch/platform/q15_msr.hpp"

namespace cpu_prefetch::platform {

// Capacity follows the accepted registry, not an invented CPU-number limit.
inline constexpr std::size_t kPreparedPrefetchMaxCpus = [] {
  std::size_t maximum = 0U;
  for (const auto& mapping : kHardwarePrefetchMappings) {
    if (mapping.control_cpus.has_value() && mapping.control_cpus->size() > maximum) {
      maximum = mapping.control_cpus->size();
    }
  }
  return maximum;
}();
static_assert(kPreparedPrefetchMaxCpus > 0U);

// Read-only syscall seam. The prepared reader supplies every path, flag, read
// size and fixed offset. Only identity() is cold/possibly allocating; all file
// methods are nonthrowing and must not allocate or retry.
class PrefetchReadbackOperations {
public:
  virtual ~PrefetchReadbackOperations() = default;
  [[nodiscard]] virtual auto identity() -> Result<CpuFamilyModel> = 0;
  [[nodiscard]] virtual auto open_file(const char* path, int flags) noexcept
      -> LinuxCallResult = 0;
  [[nodiscard]] virtual auto read_at(int descriptor, std::span<std::byte> bytes,
                                     FileOffset offset) noexcept -> LinuxCallResult = 0;
  [[nodiscard]] virtual auto close_file(int descriptor) noexcept -> LinuxCallResult = 0;
};

class LinuxPrefetchReadbackOperations final : public PrefetchReadbackOperations {
public:
  [[nodiscard]] auto identity() -> Result<CpuFamilyModel> override;
  [[nodiscard]] auto open_file(const char* path, int flags) noexcept
      -> LinuxCallResult override;
  [[nodiscard]] auto read_at(int descriptor, std::span<std::byte> bytes,
                             FileOffset offset) noexcept -> LinuxCallResult override;
  [[nodiscard]] auto close_file(int descriptor) noexcept -> LinuxCallResult override;
};

enum class PrefetchReadbackPreparationStop : std::uint8_t {
  not_started,
  mapping_rejected,
  identity_failed,
  identity_mismatch,
  prestate_rejected,
  open_failed,
  ready,
};

struct PreparedPrefetchCpu final {
  std::uint32_t cpu{};
  std::uint64_t expected_h0{};
  std::uint64_t expected_h1{};
  std::optional<LinuxCallResult> open;
  std::optional<LinuxCallResult> close;
};

struct PrefetchReadbackPreparation final {
  bool attempted{false};
  bool released{false};
  CpuFamilyModel requested_identity{};
  // CPUID is observed on the preparing controller, not independently on each
  // control CPU. Per-CPU topology/identity qualification remains external.
  std::optional<Result<CpuFamilyModel>> observed_identity;
  std::string_view mapping_id;
  std::vector<Error> resolver_errors;
  std::size_t cpu_count{};
  std::array<PreparedPrefetchCpu, kPreparedPrefetchMaxCpus> cpus{};
  PrefetchReadbackPreparationStop stop{PrefetchReadbackPreparationStop::not_started};
};

struct PrefetchCpuReadback final {
  std::uint32_t cpu{};
  std::uint64_t expected_value{};
  std::optional<LinuxCallResult> read;
  // Retain even partial bytes; only a successful exact eight-byte read yields
  // observed_value. Unwritten zero-initialized bytes are not observations.
  std::array<std::byte, sizeof(std::uint64_t)> raw_bytes{};
  std::optional<std::uint64_t> observed_value;
  bool matches{false};
};

enum class PrefetchReadbackStop : std::uint8_t {
  not_prepared,
  invalid_state,
  read_failed,
  value_mismatch,
  sampled,
};

struct PrefetchReadbackSample final {
  bool attempted{false};
  std::optional<protocol::RequestedHardwareState> requested_state;
  std::optional<CpuFamilyModel> prepared_controller_identity;
  std::string_view mapping_id;
  std::size_t cpu_count{};
  std::array<PrefetchCpuReadback, kPreparedPrefetchMaxCpus> cpus{};
  PrefetchReadbackStop stop{PrefetchReadbackStop::not_prepared};
  [[nodiscard]] auto succeeded() const noexcept -> bool {
    return stop == PrefetchReadbackStop::sampled;
  }
};

// One cold preparation: resolve the accepted mapping, verify actual CPUID,
// resolve both H0/H1 plans from supplied prestate, then open exactly that
// model's control CPUs read-only. Prestate provenance/whole-plot authority is
// admitted externally; this reader never captures a new default or writes.
// All expected values are owned copies in resolved CPU order.
//
// Controller-only, serialized sample(state, distinct_output) is suitable for
// an observe_controls(request) callback. It performs one pread per resolved
// CPU, continuing through failures to retain every planned observation. No
// allocations, opens, retries, configuration parsing or hidden scheduling.
// Output is one-use and caller-owned; attempted output is rejected unchanged.
// Samples across CPUs are non-atomic. The caller brackets time and admits
// scheduling, watchdog limits and identity/closure applicability separately.
class PreparedPrefetchReadback final {
public:
  explicit PreparedPrefetchReadback(PrefetchReadbackOperations& operations) noexcept;
  ~PreparedPrefetchReadback();
  PreparedPrefetchReadback(const PreparedPrefetchReadback&) = delete;
  auto operator=(const PreparedPrefetchReadback&) -> PreparedPrefetchReadback& = delete;
  PreparedPrefetchReadback(PreparedPrefetchReadback&&) = delete;
  auto operator=(PreparedPrefetchReadback&&) -> PreparedPrefetchReadback& = delete;

  [[nodiscard]] auto prepare(CpuFamilyModel expected_identity,
                             std::span<const HardwarePrefetchMsrValue> prestate)
      -> bool;
  [[nodiscard]] auto sample(protocol::RequestedHardwareState requested_state,
                            PrefetchReadbackSample& output) noexcept -> bool;
  [[nodiscard]] auto release() noexcept -> bool;
  [[nodiscard]] auto preparation() const noexcept
      -> const PrefetchReadbackPreparation& {
    return preparation_;
  }

private:
  PrefetchReadbackOperations& operations_;
  PrefetchReadbackPreparation preparation_{};
  std::array<int, kPreparedPrefetchMaxCpus> descriptors_{};
};

} // namespace cpu_prefetch::platform

#endif
