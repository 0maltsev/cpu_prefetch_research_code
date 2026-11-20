#include "cpu_prefetch/runner/stage17_s180_sources.hpp"
#include "cpu_prefetch/runner/stage17_schedule_source.hpp"

#include <chrono>
#include <limits>
#include <sys/stat.h>

namespace cpu_prefetch::runner::stage17 {
PreparedS180Capture::PreparedS180Capture(calibration::NativePilotCapturePlan plan,
                                         Deadlines deadlines)
    : plan_(std::move(plan)),
      deadlines_(std::make_shared<const Deadlines>(std::move(deadlines))),
      prestate_(plan_.controls.hardware_prestate.begin(),
                plan_.controls.hardware_prestate.end()) {
  plan_.capture.scheduled.deadlines = {};
  plan_.controls.hardware_prestate = {};
}
auto PreparedS180Capture::plan() const -> calibration::NativePilotCapturePlan {
  if (!deadlines_)
    throw std::logic_error("moved-from S180 prepared capture");
  auto result = plan_;
  result.capture.scheduled.deadlines = {(*deadlines_)[0U], (*deadlines_)[1U]};
  result.controls.hardware_prestate = prestate_;
  return result;
}
namespace {
auto before_deadline(std::uint64_t deadline) -> bool {
  const auto now = std::chrono::duration_cast<std::chrono::nanoseconds>(
                       std::chrono::steady_clock::now().time_since_epoch())
                       .count();
  return now >= 0 && static_cast<std::uint64_t>(now) < deadline;
}
} // namespace
auto prepare_s180_capture_from_sources(
    calibration::NativePilotCapturePlan plan,
    const std::array<S180SourceArtifact, 2U>& artifacts,
    const FormalScheduleSourceContext& sources, std::span<const int> reserved)
    -> protocol::Result<PreparedS180Capture> {
  try {
    auto& scheduled = plan.capture.scheduled;
    calibration::validate_pilot_shared_view(plan.capture);
    if (scheduled.service.session.phases[0U].duration_ticks != 5'000'000'000'000U ||
        scheduled.service.session.phases[1U].duration_ticks != 1'000'000'000'000U ||
        !scheduled.deadlines[0U].empty() || !scheduled.deadlines[1U].empty() ||
        artifacts[0U].artifact_id == artifacts[1U].artifact_id ||
        !before_deadline(sources.deadline_monotonic_ns))
      throw std::invalid_argument(
          "S180 source window, identity, inline data or deadline differs");
    PreparedS180Capture::Deadlines deadlines;
    std::uint64_t retained = 0U;
    std::array<const FormalScheduleSourceBinding*, 2U> bound{};
    std::array<struct stat, 2U> selected{};
    // Complete both physical identity checks before allocating any vector.
    for (std::size_t i = 0U; i < 2U; ++i) {
      const auto& a = artifacts[i];
      const auto count = scheduled.phases[i].offered_count;
      for (const auto& entry : sources.bindings)
        if (entry.artifact_id == a.artifact_id) {
          if (bound[i] != nullptr)
            throw std::invalid_argument("duplicate S180 source membership");
          bound[i] = &entry;
        }
      if (bound[i] == nullptr || bound[i]->descriptor <= 2 ||
          count > std::numeric_limits<std::uint64_t>::max() / 8U ||
          count > std::numeric_limits<std::size_t>::max() / sizeof(std::uint64_t) ||
          count > scheduled.service.session.phases[i].producer_attempt_limit ||
          bound[i]->canonical_sha256 != a.sha256 ||
          bound[i]->size_bytes != count * 8U ||
          ::fstat(bound[i]->descriptor, &selected[i]) != 0 ||
          !S_ISREG(selected[i].st_mode))
        throw std::invalid_argument(
            "S180 source binding/hash/count/descriptor differs");
      for (const int fd : reserved) {
        struct stat other{};
        if (fd == bound[i]->descriptor ||
            (::fstat(fd, &other) == 0 && other.st_dev == selected[i].st_dev &&
             other.st_ino == selected[i].st_ino))
          throw std::invalid_argument("S180 source aliases a reserved descriptor");
      }
    }
    if (selected[0U].st_dev == selected[1U].st_dev &&
        selected[0U].st_ino == selected[1U].st_ino)
      throw std::invalid_argument("S180 phase sources alias the same physical file");
    for (std::size_t i = 0U; i < 2U; ++i) {
      const auto& phase = scheduled.phases[i];
      if (retained > sources.maximum_vector_bytes ||
          phase.offered_count > (sources.maximum_vector_bytes - retained) / 16U)
        throw std::invalid_argument("S180 aggregate vector/transient budget exceeded");
      auto loaded = load_sealed_schedule_source(
          bound[i]->descriptor,
          {artifacts[i].artifact_id, artifacts[i].sha256, phase.offered_count,
           phase.source_origin_ticks, phase.source_horizon_ticks,
           sources.maximum_vector_bytes - retained, sources.deadline_monotonic_ns});
      if (!loaded)
        return protocol::Result<PreparedS180Capture>::failure(loaded.errors());
      deadlines[i] = std::move(loaded.value());
      retained += phase.offered_count * 8U;
    }
    PreparedS180Capture result(std::move(plan), std::move(deadlines));
    // Exact current native sizing/seed/layout/source checks, without execution.
    static_cast<void>(calibration::native_pilot_layout(result.plan()));
    if (!before_deadline(sources.deadline_monotonic_ns))
      throw std::invalid_argument("S180 source preparation exhausted its deadline");
    return protocol::Result<PreparedS180Capture>::success(result);
  } catch (const std::exception& error) {
    return protocol::Result<PreparedS180Capture>::failure(
        {protocol::ErrorCategory::cross_field, "$/s180/sources", "S17-S180-SOURCES",
         error.what()});
  }
}
} // namespace cpu_prefetch::runner::stage17
