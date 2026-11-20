#ifndef CPU_PREFETCH_RUNNER_STAGE17_S180_SOURCES_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_S180_SOURCES_HPP
#include "cpu_prefetch/calibration/native_pilot_capture.hpp"
#include "cpu_prefetch/runner/stage17_formal_scheduled_action.hpp"
namespace cpu_prefetch::runner::stage17 {
struct S180SourceArtifact final {
  std::string artifact_id;
  std::string sha256;
};
// Owns both original decoded vectors and the MSR prestate through native join
// and publication. Shared family data and environment paths remain borrowed.
// This is a cold prepared value, never an authority/admission ticket.
class PreparedS180Capture final {
public:
  using Deadlines = std::array<std::vector<std::uint64_t>, 2U>;
  PreparedS180Capture(calibration::NativePilotCapturePlan, Deadlines);
  [[nodiscard]] auto plan() const -> calibration::NativePilotCapturePlan;

private:
  calibration::NativePilotCapturePlan plan_;
  std::shared_ptr<const Deadlines> deadlines_;
  std::vector<platform::HardwarePrefetchMsrValue> prestate_;
};
// Parent authenticates full family source provenance/membership and reserves
// namespaces before invoking this cold loader. This checks exact selected
// artifact/hash/count, immutable read-only physical FDs, all reserved aliases,
// both fixed windows and aggregate retained/transient vector memory. It never
// regenerates schedules, changes FD offsets, touches hardware or starts workers.
[[nodiscard]] auto prepare_s180_capture_from_sources(
    calibration::NativePilotCapturePlan, const std::array<S180SourceArtifact, 2U>&,
    const FormalScheduleSourceContext&, std::span<const int> reserved_descriptors)
    -> protocol::Result<PreparedS180Capture>;
} // namespace cpu_prefetch::runner::stage17
#endif
