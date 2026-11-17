#ifndef CPU_PREFETCH_RUNNER_STAGE17_FORMAL_SCHEDULED_ACTION_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_FORMAL_SCHEDULED_ACTION_HPP
#include "cpu_prefetch/calibration/calibration.hpp"
#include "cpu_prefetch/calibration/native_formal_scheduled_capture.hpp"
#include "cpu_prefetch/protocol/json.hpp"
#include <memory>
namespace cpu_prefetch::runner::stage17 {
// Bound by the authenticated parent context, never a descriptor chosen by the
// schedule document. The parent separately proves accepted-generator provenance.
struct FormalScheduleSourceBinding final {
  std::string artifact_id;
  std::string canonical_sha256;
  std::uint64_t size_bytes;
  int descriptor;
};
struct FormalScheduleSourceContext final {
  std::span<const FormalScheduleSourceBinding> bindings;
  std::uint64_t maximum_vector_bytes;
  std::uint64_t deadline_monotonic_ns;
};
struct PreparedFormalScheduleSources final {
  std::vector<FormalScheduleSourceBinding> bindings;
  std::uint64_t maximum_vector_bytes;
  std::uint64_t deadline_monotonic_ns;
  [[nodiscard]] auto context() const -> FormalScheduleSourceContext {
    return {bindings, maximum_vector_bytes, deadline_monotonic_ns};
  }
};
// The context is parent-authenticated and distinct from the signed request.
// Checks exact complete membership and physical descriptor identities before
// the cold loaders allocate/read/hash, without touching borrowed offsets.
[[nodiscard]] auto parse_formal_schedule_source_context(
    const protocol::json::Value::Object& plan,
    const protocol::json::Value::Object& source_context,
    std::span<const int> reserved_descriptors)
    -> protocol::Result<PreparedFormalScheduleSources>;
// Immutable owned deadline arrays survive copies/moves of this parsed value.
// plan() rebinds the native spans; retain a parsed owner until capture returns.
// Environmental path strings and hardware prestate still borrow parser inputs.
class ParsedNativeFormalScheduledCapture final {
public:
  using Deadlines = std::array<std::vector<std::uint64_t>, 2U>;
  ParsedNativeFormalScheduledCapture(calibration::NativeFormalScheduledCapturePlan plan,
                                     Deadlines deadlines);
  [[nodiscard]] auto plan() const -> calibration::NativeFormalScheduledCapturePlan;

private:
  calibration::NativeFormalScheduledCapturePlan plan_;
  std::shared_ptr<const Deadlines> deadlines_;
};
[[nodiscard]] auto parse_native_formal_scheduled_capture(
    const protocol::json::Value::Object& capture,
    const protocol::json::Value::Object& resources,
    const protocol::json::Value::Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<ParsedNativeFormalScheduledCapture>;
[[nodiscard]] auto parse_native_formal_scheduled_capture_from_sources(
    const protocol::json::Value::Object& capture,
    const protocol::json::Value::Object& resources,
    const protocol::json::Value::Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate,
    const FormalScheduleSourceContext& sources)
    -> protocol::Result<ParsedNativeFormalScheduledCapture>;
// Pure sizing only: no mappings/hardware/authority; memory ceiling still enforced.
[[nodiscard]] auto describe_native_formal_scheduled_layout(
    const protocol::json::Value::Object& capture,
    const protocol::json::Value::Object& resources,
    const protocol::json::Value::Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeFormalScheduledCaptureLayout>;
[[nodiscard]] auto describe_native_formal_scheduled_layout_from_sources(
    const protocol::json::Value::Object& capture,
    const protocol::json::Value::Object& resources,
    const protocol::json::Value::Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate,
    const FormalScheduleSourceContext& sources)
    -> protocol::Result<calibration::NativeFormalScheduledCaptureLayout>;
} // namespace cpu_prefetch::runner::stage17
#endif
