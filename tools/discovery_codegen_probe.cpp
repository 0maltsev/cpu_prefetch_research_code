#include "cpu_prefetch/calibration/native_discovery_capture.hpp"

// Link anchor only: the qualified worker code comes from the production native
// capture translation unit. This file neither instantiates a replacement worker
// nor runs a capture. The checker also accepts the actual release worker binary.
extern "C" [[gnu::noinline]] auto cpu_prefetch_native_discovery_link_anchor(
    const cpu_prefetch::calibration::NativeDiscoveryCapturePlan& plan,
    cpu_prefetch::calibration::NativeDiscoveryPublication publication)
    -> cpu_prefetch::calibration::NativeDiscoveryCaptureResult {
  return cpu_prefetch::calibration::run_native_discovery_capture(plan, publication);
}

int main() { return 0; }
