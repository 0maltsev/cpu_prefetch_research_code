#include "cpu_prefetch/workload/packages.hpp"

#include <limits>

namespace cpu_prefetch::workload {
namespace {

[[nodiscard]] bool is_power_of_two(std::size_t value) noexcept {
  return value != 0U && (value & (value - 1U)) == 0U;
}

[[nodiscard]] std::size_t checked_multiply(std::size_t left, std::size_t right) {
  if (left != 0U && right > std::numeric_limits<std::size_t>::max() / left) {
    throw WorkloadSetupError("ring distance overflows size_t");
  }
  return left * right;
}

} // namespace

RingDistance ring_one_line_distance(const RingGeometry& geometry) {
  if (!is_power_of_two(geometry.capacity) || geometry.cache_line_bytes == 0U ||
      geometry.slot_bytes == 0U) {
    throw WorkloadSetupError(
        "ring distance requires power-of-two capacity and explicit nonzero units");
  }
  const auto slots = (geometry.cache_line_bytes / geometry.slot_bytes) +
                     (geometry.cache_line_bytes % geometry.slot_bytes == 0U ? 0U : 1U);
  if (slots == 0U || slots >= geometry.capacity) {
    throw WorkloadSetupError(
        "one-line ring lookahead must name a distinct future slot line");
  }
  return RingDistance({slots, 1U});
}

CalibratedRingDistance
resolve_calibrated_ring_distance(const RingGeometry& geometry,
                                 std::size_t calibrated_cache_lines,
                                 std::string calibration_evidence_id) {
  const auto one_line = ring_one_line_distance(geometry);
  if (calibration_evidence_id.empty()) {
    throw WorkloadSetupError("R2 distance requires calibration evidence identity");
  }
  if (calibrated_cache_lines < 2U) {
    throw WorkloadSetupError("R2 distance must be at least two cache lines");
  }
  const auto slots = checked_multiply(one_line.slots(), calibrated_cache_lines);
  if (slots > geometry.capacity / 4U) {
    throw WorkloadSetupError("R2 distance exceeds the one-quarter capacity cap");
  }
  if (slots == one_line.slots()) {
    throw WorkloadSetupError("R2 cap collapses to R1; the cell is ineligible");
  }
  return CalibratedRingDistance(RingDistance({slots, calibrated_cache_lines}),
                                std::move(calibration_evidence_id));
}

} // namespace cpu_prefetch::workload
