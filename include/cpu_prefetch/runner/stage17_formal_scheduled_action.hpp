#ifndef CPU_PREFETCH_RUNNER_STAGE17_FORMAL_SCHEDULED_ACTION_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_FORMAL_SCHEDULED_ACTION_HPP
#include "cpu_prefetch/calibration/calibration.hpp"
#include "cpu_prefetch/calibration/native_formal_scheduled_capture.hpp"
#include "cpu_prefetch/protocol/json.hpp"
#include <memory>
namespace cpu_prefetch::runner::stage17 {
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
// Pure sizing only: no mappings/hardware/authority; memory ceiling still enforced.
[[nodiscard]] auto describe_native_formal_scheduled_layout(
    const protocol::json::Value::Object& capture,
    const protocol::json::Value::Object& resources,
    const protocol::json::Value::Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeFormalScheduledCaptureLayout>;
} // namespace cpu_prefetch::runner::stage17
#endif
