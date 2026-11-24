# D312: S180 persistent capture core and complete phase retention

Accepted engineering implementation under the owner's D310 S180 approval and
D311 prospective blueprint. No protocol snapshot, existing qualified worker,
calibration record, estimator or experimental count/duration changes here.

The legacy pilot uses a load-dependent persistent-context key and retains only
the warmup summary while constructing a separate measured capture. Introduce
new native capture primitives that use the existing scheduled-session state
machine and unchanged capture/workload/queue operations, without activating the
legacy pilot entry point or changing its historical output contracts.

## Data and lifetime contract

`PilotSharedData` binds caller-owned immutable event records and the same ring
and linked objects. `PilotContextRegistry` has exactly six placement/working-set
slots; package, hardware state and load are not keys. Rebinding cannot replace
an admitted object, and overlapping event/node arenas are rejected. This is a
data-lifetime constraint, not evidence of NUMA placement, address-pattern/seed
acceptance, current qualification or archive custody. Actual native integration
must supply and independently observe every mapped region and retain these
objects through all paired runs in the temporal block.

`PilotScheduledPreparation` statically selects one of the five existing packages.
The caller supplies both phases' original independent producer/consumer streams,
IDs and immutable source-array views. Phase objects/raw buffers must be placed
and prepared on their owners before warmup. Exact capacities/identities, address
representability/alignment and disjoint source/raw/data ranges are checked cold.
Schedule values are checked only after owner preparation, through the existing
scheduled driver. An R2 distance must be explicit and fit this context's geometry;
the later operational admission must additionally bind its accepted provenance.

The same two worker instances perform warmup, drain, parked logical reset and
measurement. The controller resets the selected drained queue before releasing
warmup, after the existing source/owner/start-barrier gates. Undrained prior data
block release without being discarded. The actual initial-reset result remains
separate from the later warmup-to-measurement reset. Reusing session storage is
rejected before either reset/release can run again.

Reset does not allocate, remap, regenerate a schedule/permutation or retouch event
payloads. Owner callbacks retain the existing actual affinity/memory/TLS duties;
callbacks returning true alone establish no platform proof. All source arrays,
shared data, callbacks, phase objects and raw buffers outlive the session and
synchronous publication. The caller serializes access to each shared context.

The result exposes both original phases' primary raw byte views after join,
including completed warmup when later measurement fails and incomplete evidence
on failure. No phase is concatenated, copied over the other, silently dropped,
counted as an independent repetition, or relabeled as calibration. FULL remains
valid reconciled data and cannot satisfy the separate zero-loss gate. The new
core performs no archive I/O or post-run statistical inference.

## Verification and activation boundary

Tests use real queue/package/primary-stream/reconciliation code with a synthetic
clock and explicit software-only owner/observer callbacks. They cover all five
packages, both retained phases, six-context reuse, FULL, observation/reset/source
failure, alias/alignment/geometry rejection, replay rejection and allocation/free
hooks. These results support software correctness only. Clang TSan excludes the
global allocator hook under the existing repository convention; other matrices
must establish that separate gate. No runtime observation is fabricated by a test.

This core is not yet a launched S180 native worker. Monitored mapped owner/control
storage, actual sealed-source transport wiring, full artifact publication/archive,
typed scoped EXT008/009/010 integration, exact resource/time envelopes, codegen
and actual qualified-release compatibility remain required before execution.
The operational24h window has not started. No experiment, calibration rerun,
automatic retry, new qualification invocation or Stage18 authority follows.
