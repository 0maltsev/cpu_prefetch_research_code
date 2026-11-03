#ifndef CPU_PREFETCH_RUNNER_STAGE17_DISCOVERY_ACTION_HPP
#define CPU_PREFETCH_RUNNER_STAGE17_DISCOVERY_ACTION_HPP

#include "cpu_prefetch/calibration/native_discovery_capture.hpp"
#include "cpu_prefetch/protocol/json.hpp"

namespace cpu_prefetch::runner::stage17 {

// Cold native boundary. The returned prestate span borrows the supplied admitted
// values and monitoring path strings, which must outlive the capture.
// Recomputes the actual binary's layout;
// serialized sizes are checked assertions, never allocation instructions.
[[nodiscard]] auto parse_native_discovery_capture(
    const protocol::json::Value::Object& capture,
    const protocol::json::Value::Object& resources,
    const protocol::json::Value::Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeDiscoveryCapturePlan>;

// Read-only prospective sizing. Computes sizes instead of accepting declarations;
// returns no runnable plan, performs no hardware access and grants no authority.
[[nodiscard]] auto describe_native_discovery_layout(
    const protocol::json::Value::Object& capture,
    const protocol::json::Value::Object& resources,
    const protocol::json::Value::Object& monitoring,
    std::span<const platform::HardwarePrefetchMsrValue> prestate)
    -> protocol::Result<calibration::NativeDiscoveryCaptureLayout>;

} // namespace cpu_prefetch::runner::stage17

#endif
