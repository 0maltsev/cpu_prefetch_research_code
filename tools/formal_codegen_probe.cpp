#include "cpu_prefetch/calibration/native_formal_ring_capture.hpp"
#include "cpu_prefetch/calibration/native_formal_scheduled_capture.hpp"
#include "cpu_prefetch/calibration/native_formal_service_capture.hpp"

// Link anchors only. All capture code is instantiated by production native
// translation units. Running this binary does not start a capture.
extern "C" [[gnu::noinline]] auto cpu_prefetch_formal_ring_link_anchor(
    const cpu_prefetch::calibration::NativeFormalRingCapturePlan& plan,
    cpu_prefetch::calibration::NativeFormalRingPublication publication)
    -> cpu_prefetch::calibration::NativeFormalRingCaptureResult {
  return cpu_prefetch::calibration::run_native_formal_ring_capture(plan, publication);
}
extern "C" [[gnu::noinline]] auto cpu_prefetch_formal_service_link_anchor(
    const cpu_prefetch::calibration::NativeFormalServiceCapturePlan& plan,
    cpu_prefetch::calibration::NativeFormalServicePublication publication)
    -> cpu_prefetch::calibration::NativeFormalServiceCaptureResult {
  return cpu_prefetch::calibration::run_native_formal_service_capture(plan,
                                                                      publication);
}
extern "C" [[gnu::noinline]] auto cpu_prefetch_formal_scheduled_link_anchor(
    const cpu_prefetch::calibration::NativeFormalScheduledCapturePlan& plan,
    cpu_prefetch::calibration::NativeFormalScheduledPublication publication)
    -> cpu_prefetch::calibration::NativeFormalScheduledCaptureResult {
  return cpu_prefetch::calibration::run_native_formal_scheduled_capture(plan,
                                                                        publication);
}

int main() { return 0; }
