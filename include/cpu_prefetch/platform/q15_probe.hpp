#ifndef CPU_PREFETCH_PLATFORM_Q15_PROBE_HPP
#define CPU_PREFETCH_PLATFORM_Q15_PROBE_HPP

#include "cpu_prefetch/workload/deterministic.hpp"

#include <cstddef>
#include <cstdint>
#include <span>
#include <string_view>
#include <vector>

namespace cpu_prefetch::platform {

inline constexpr std::string_view kQ15ProbeImplementationProfileId =
    "Q15-PROBE-IMPLEMENTATION-PROFILE-v1";
inline constexpr std::string_view kQ15PointerProbeNamespace =
    "Q15-POINTER-PROBE-PERMUTATION-v1";
inline constexpr std::string_view kQ15PointerProbePurpose = "node-order";
inline constexpr std::string_view kQ15PointerProbeSeedHex =
    "b7ad8c3db8469f8b60ec679eb68b10b040a4b509438882732854257d582aff9b";
inline constexpr std::size_t kQ15ProbeCacheLineBytes = 64U;
inline constexpr std::size_t kQ15ProbeBasePageBytes = 4096U;

enum class Q15ProbeKind : std::uint8_t { regular_stream, pointer_dependent };

enum class Q15PointerClassification : std::uint8_t {
  distinguished,
  not_distinguishable_where_not_possible,
};

struct Q15CounterReading final {
  std::uint64_t all_pf_count;
  std::uint64_t time_enabled;
  std::uint64_t time_running;
};

struct Q15CountedPassEvidence final {
  Q15CounterReading counter;
  std::uint64_t minor_faults;
  std::uint64_t major_faults;
};

struct Q15ProbeIntegrityEvidence final {
  workload::Sha256Digest pre_sha256;
  workload::Sha256Digest post_sha256;
  std::uint64_t counted_load_count;
  std::uint32_t start_index;
  std::uint32_t final_index;
  bool exact_cycle_before_counted_pass;

  [[nodiscard]] auto content_unchanged() const noexcept -> bool;
  [[nodiscard]] auto passes_pointer_cycle(std::size_t line_count) const noexcept
      -> bool;
};

struct Q15ProbePairAssessment final {
  Q15ProbeKind kind;
  Q15PointerClassification pointer_classification;
  bool counter_not_multiplexed;
  bool counted_pass_fault_free;
  bool integrity_passed;
  bool h0_positive;
  bool h1_zero;
  bool accepted;
  bool distinguished;
};

struct Q15PointerProbePreparation final {
  std::uint32_t start_index;
  std::vector<std::size_t> order;
  workload::Sha256Digest prepared_sha256;
};

// Initialize an already allocated, page-policy-qualified buffer. This is the
// production-session seam used by ADR-0054/0055 so the private anonymous
// mapping can outlive both Q15 phases. It performs all generation and hashing
// before a counted traversal.
[[nodiscard]] auto prepare_q15_pointer_probe_buffer(std::span<std::byte> buffer,
                                                    std::size_t line_count)
    -> Q15PointerProbePreparation;

// Setup-only storage for the D-053 deterministic single-cycle probe. Allocation,
// initialization, permutation generation, and SHA-256 all happen outside the
// counted traversal.
class Q15PointerProbeBuffer final {
public:
  explicit Q15PointerProbeBuffer(std::size_t line_count);
  ~Q15PointerProbeBuffer();

  Q15PointerProbeBuffer(const Q15PointerProbeBuffer&) = delete;
  Q15PointerProbeBuffer& operator=(const Q15PointerProbeBuffer&) = delete;
  Q15PointerProbeBuffer(Q15PointerProbeBuffer&&) = delete;
  Q15PointerProbeBuffer& operator=(Q15PointerProbeBuffer&&) = delete;

  [[nodiscard]] auto line_count() const noexcept -> std::size_t { return line_count_; }
  [[nodiscard]] auto byte_count() const noexcept -> std::size_t { return byte_count_; }
  [[nodiscard]] auto start_index() const noexcept -> std::uint32_t {
    return start_index_;
  }
  [[nodiscard]] auto data() const noexcept -> const std::byte* { return storage_; }
  [[nodiscard]] auto bytes() const noexcept -> std::span<const std::byte> {
    return {storage_, byte_count_};
  }
  [[nodiscard]] auto order() const noexcept -> std::span<const std::size_t> {
    return order_;
  }
  [[nodiscard]] auto prepared_sha256() const noexcept -> const workload::Sha256Digest& {
    return prepared_sha256_;
  }

private:
  std::size_t line_count_{0U};
  std::size_t byte_count_{0U};
  std::byte* storage_{nullptr};
  std::uint32_t start_index_{0U};
  std::vector<std::size_t> order_;
  workload::Sha256Digest prepared_sha256_{{}};
};

[[nodiscard]] auto q15_pointer_probe_key() -> workload::PhiloxKey;
[[nodiscard]] auto validate_q15_pointer_cycle(std::span<const std::byte> buffer,
                                              std::size_t line_count,
                                              std::uint32_t start_index) -> bool;
[[nodiscard]] auto evaluate_q15_probe_pair(Q15ProbeKind kind,
                                           const Q15CountedPassEvidence& h0,
                                           const Q15CountedPassEvidence& h1,
                                           const Q15ProbeIntegrityEvidence& integrity,
                                           std::size_t line_count) noexcept
    -> Q15ProbePairAssessment;

// These are the only counted traversal bodies. They contain no allocation,
// checksum, filesystem, counter, timing, or logging work. The return values keep
// demanded loads observable to the caller; they are diagnostic integrity inputs,
// not performance results.
extern "C" [[gnu::noinline]] auto cpu_prefetch_q15_regular_counted_traversal(
    const std::byte* buffer, std::size_t line_count) noexcept -> std::uint64_t;
extern "C" [[gnu::noinline]] auto cpu_prefetch_q15_pointer_counted_traversal(
    std::size_t line_count, const std::byte* buffer, std::uint32_t start_index) noexcept
    -> std::uint32_t;

} // namespace cpu_prefetch::platform

#endif // CPU_PREFETCH_PLATFORM_Q15_PROBE_HPP
