#ifndef CPU_PREFETCH_RUNNER_STAGE17_FORMAL_SERVICE_ACTION_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_FORMAL_SERVICE_ACTION_HPP

#include "cpu_prefetch/calibration/calibration.hpp"
#include "cpu_prefetch/calibration/native_formal_service_capture.hpp"
#include "cpu_prefetch/protocol/json.hpp"

namespace cpu_prefetch::runner::stage17 {

// Cold D035/D211 five-package boundary. Paths and hardware prestate borrow the supplied
// objects; keep those alive through the synchronous capture. Declared layout sizes are
// assertions against this binary's pure layout calculation, not allocations.
// This validates one capture, not family coverage, admission or run authority.
[[nodiscard]] auto parse_native_formal_service_capture(
    const protocol::json::Value::Object& capture,
    const protocol::json::Value::Object& resources,
    const protocol::json::Value::Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeFormalServiceCapturePlan>;

// Software-only prospective sizing. No mappings, hardware access or execution
// authority; declared sizes may be placeholders but the memory ceiling applies.
[[nodiscard]] auto describe_native_formal_service_layout(
    const protocol::json::Value::Object& capture,
    const protocol::json::Value::Object& resources,
    const protocol::json::Value::Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeFormalServiceCaptureLayout>;

} // namespace cpu_prefetch::runner::stage17
#endif
