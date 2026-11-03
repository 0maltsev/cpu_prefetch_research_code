#ifndef CPU_PREFETCH_CALIBRATION_RING_DEMAND_WINDOW_HPP
#define CPU_PREFETCH_CALIBRATION_RING_DEMAND_WINDOW_HPP

#include "cpu_prefetch/calibration/calibration.hpp"
#include "cpu_prefetch/calibration/service_interval_count.hpp"

#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string_view>

namespace cpu_prefetch::calibration {

inline constexpr std::string_view kRingDemandFormatId = "Q16A-DEMAND-U64LE-LP-RUNID-v1";
inline constexpr std::uint64_t kRingDemandBodyBytes = 9U * sizeof(std::uint64_t);

// Wire order: attempt, outcome (advanced=0/full=1/empty=2), advancement,
// before status/absolute ns/relative ps, after status/absolute ns/relative ps.
// Attempts and advancements are independently zero-based. Nonadvancement uses
// advancement=0. Failed clock statuses are retained, never valid window data.
struct RingDemandRecord final {
  std::uint64_t attempt_ordinal;
  RingAttemptOutcome outcome;
  std::uint64_t advancing_ordinal;
  timing::ClockReadResult before;
  timing::ClockReadResult after;
};

struct RingDemandLayout final {
  std::uint64_t run_id_bytes;
  std::uint64_t prefix_bytes;
  std::uint64_t row_bytes;
};

enum class RingDemandPhase : std::uint8_t { warmup, measurement };

[[nodiscard]] auto ring_demand_layout(const protocol::RunId& run_id)
    -> RingDemandLayout;
[[nodiscard]] auto ring_demand_storage_requirements(const protocol::RunId& run_id,
                                                    std::uint64_t row_capacity)
    -> std::size_t;

// Role, phase and expected run identity remain independently bound external
// metadata. The explicit phase selects raw-only warmup validation or D212
// measurement classification after the required warmup drain/reset barrier.
struct RingDemandSnapshot final {
  std::string_view format_id;
  RingWorker worker;
  std::string_view run_id;
  std::span<const std::byte> bytes;
  std::uint64_t row_count;
  std::uint64_t row_capacity;
  std::uint64_t row_bytes;
  storage::StreamCompleteness completeness;
  bool overflowed;
};

// Single owner. Construct and prepare on its affined worker before capture.
// Caller retains this object, run_id and exact-size 64-byte-aligned byte region;
// all must remain live and disjoint. No owned allocation, I/O or statistics.
class RingDemandStream final {
public:
  RingDemandStream(const protocol::RunId& run_id, RingWorker worker,
                   std::uint64_t row_capacity, std::span<std::byte> external_storage);
  RingDemandStream(const RingDemandStream&) = delete;
  auto operator=(const RingDemandStream&) -> RingDemandStream& = delete;

  [[nodiscard]] auto prepare_for_owner() noexcept -> bool;
  // Call only for an actually performed acquire with known outcome and both
  // demand samples present. Retains supplied failure statuses verbatim. Earlier
  // capture failure belongs in control evidence, not a fabricated demand row.
  // Scientific/identity/time checks occur only in the cold classifier.
  [[nodiscard]] auto append(const RingDemandRecord& record) noexcept
      -> storage::AppendStatus;
  [[nodiscard]] auto seal_complete() noexcept -> bool;
  void seal_incomplete() noexcept;
  [[nodiscard]] auto snapshot() const noexcept -> RingDemandSnapshot;

private:
  std::string_view run_id_;
  RingWorker worker_;
  RingDemandLayout layout_;
  std::span<std::byte> storage_;
  std::uint64_t capacity_;
  std::uint64_t count_{0U};
  storage::StreamCompleteness completeness_{storage::StreamCompleteness::writing};
  bool overflowed_{false};
  bool prepared_{false};
};

// Quiescent codec reader checks shape, literal LP identity/padding and enum
// ranges, including failed-status rows. It does not establish completeness or
// temporal validity, which the classifier checks independently.
[[nodiscard]] auto read_ring_demand_row(const RingDemandSnapshot& stream,
                                        std::uint64_t index) noexcept
    -> std::optional<RingDemandRecord>;

enum class RingDemandWindowStatus : std::uint8_t {
  complete,
  identity_mismatch,
  clock_domain_mismatch,
  invalid_duration,
  invalid_phase_contract,
  clock_binding_mismatch,
  arithmetic_overflow,
  stream_incomplete,
  malformed_stream,
  malformed_row,
  clock_failure,
  invalid_outcome,
  ordinal_mismatch,
  before_measurement_origin,
  timestamp_order,
  nonpositive_demand,
  nonpositive_issue,
  insufficient_observations,
  output_capacity,
  overlapping_output,
};

struct RingDemandWindowSeries final {
  RingDemandPhase phase;
  // Reuses the clock geometry type; measurement_origin is this phase's origin.
  ServiceIntervalClock phase_window;
  std::uint64_t interval_end_ticks;
  std::uint64_t total_attempts;
  std::uint64_t total_advancements;
  std::uint64_t outside_window_attempts;
  std::uint64_t eligible_advancements;
  RingWorkerDemandView eligible;
  bool inferential_eligible;
};

struct RingDemandWindowResult final {
  RingDemandWindowStatus status;
  std::optional<RingDemandWindowSeries> series{};
  std::optional<std::uint64_t> failed_row{};
};

struct RingDemandWindowBuffers final {
  std::span<std::uint64_t> demand;
  std::span<std::uint64_t> issue;
};

// Cold, two-pass, constant-memory validation then materialization into caller
// buffers. Checks ALL retained rows, even excluded drain, before writing any
// output. Failed classification returns no series and leaves buffers unchanged.
// Eligible starts lie in [actual origin, origin+duration); crossing brackets
// enter whole, advancing pairs number max(k-1,0). Positivity applies only to
// eligible measurement series. Warmup emits no inferential series and requires
// null minimum; measurement requires an explicit positive minimum per series.
// Quantile and family decisions remain the caller's.
// No cross-primary reconciliation, execution authority or zero-loss inference.
// Result spans and metadata string_views borrow caller-owned storage.
[[nodiscard]] auto classify_ring_demand_window(
    const RingDemandSnapshot& stream, const protocol::RunId& expected_run_id,
    RingWorker expected_worker, RingDemandPhase phase, ServiceIntervalClock clock,
    std::optional<std::uint64_t> minimum_observations_per_series,
    RingDemandWindowBuffers buffers) noexcept -> RingDemandWindowResult;

} // namespace cpu_prefetch::calibration

#endif // CPU_PREFETCH_CALIBRATION_RING_DEMAND_WINDOW_HPP
