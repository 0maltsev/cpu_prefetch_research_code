# D313: mapped S180 data and monitored native capture

Accepted engineering implementation under the exact D310 S180 approval and
D311 blueprint. The immutable protocol and completed EXT007 records remain
unchanged. This decision adds no experiment, repetition, deadline reset or
qualification invocation. No stand preparation has started.

## Persistent data and private capture storage

`MappedPilotData` owns two explicit producer-owned, node-bound mappings through
the entire family: immutable event records/order and mutable typed arena/queue
objects, ring storage, linked nodes/recycler/ownership/order scratch. It uses the
existing `OwnerMapping`, `EventArena`, queues and original `NodeOrderPlan`.
Payload/order generation happens once during cold preparation; event storage
is made read-only. Preparation is one-shot, and failure cannot expose a ready
view. Release destroys typed objects before releasing mappings and retains
actual cleanup results. The caller serializes captures and releases shared data
only after the family is quiescent. No logical reset regenerates data or order.

Each capture borrows one of the six placement/working-set contexts. It checks
exact mapped extents, owner/node/page requests, live preparation/read-only
results, object addresses, arena identity/seed and linked order identity before
constructing private storage. It does not infer verified residency from a
requested node or from a successful bind. Releasing shared data invalidates its
borrowed view; the family must keep the owner alive through every capture and
synchronous publication.

`MappedPilotPreparation` copies the two original source arrays into a separate
producer-owned read-only mapping and constructs independent warmup/measurement
producer and consumer streams on their owners before release. Package/emitter
selection is static. The unchanged `MappedServiceRuntime`, scheduled session,
worker stacks, TLS observations, capture primitives and reconciliation execute
both phases on the same two workers. Initial drained-queue reset uses the D312
bridge, and an undrained prior queue remains a blocking outcome. Closing a
capture releases only its private storage/stacks; it never releases family data.
Both phases' raw objects survive join through synchronous publication, including
warmup when measurement fails. Reusing a session cannot launch another capture.

## Complete native monitoring

`NativePilotCapturePlan` is a distinct typed plan, not a Q16c request relabeling.
It uses nine observed regions: the existing three private worker maps, two
worker stacks, core and controller stack, plus the two persistent maps. Each
phase has full before/after and explicitly bounded during residency queries for
all nine regions (54 independent query/status records across both phases).
The shared native envelope and prepared monitor size this list from a compile-
time trait. Existing discovery/service/scheduled traits retain seven regions
and 42 queries; their input/output contracts and default behavior stay intact.

The pilot layout rejects missing shared coverage, requested owner drift,
unregistered model/software-prefetch combinations and an unmet original node
address-pattern gate. Native execution uses the registered static emitter and
the existing actual Linux clock, owners, stack/TLS/readback/environment and
residency observer. The publication callback receives the actual nine-region
observations, both phases' raw pointers and source views, and live shared-data
mapping evidence before private cleanup. A returned capture result records
private cleanup only. Final family cleanup must be separately published; it
cannot be claimed from a per-capture result.

Sizing exposes every live shared byte, including both ring and linked storage,
even when one package is selected. Future exact EXT008/009 plans must account
for six retained contexts without double-allocating one per capture and must
revalidate full-footprint working-set classification against actual geometry.
Neither this layout nor a historical class label establishes that gate.

## Verification and activation boundary

Software tests use synthetic clocks and explicitly simulated memory placement/
locking observations with real mmap/mprotect, worker stacks/TLS, queues, raw
streams and reconciliation. They check all five packages across ten captures
on one unchanged context, both phase streams, failure retention, shared/private
cleanup separation, original node-order generation, seed/geometry/lifetime
rejection and native cold layout/coverage. These are correctness tests only;
they make no timing, NUMA, qualification or empirical performance claim.

The fixed-action production pilot entry, sealed-source authenticated routing,
complete versioned artifact publication/archive and scoped EXT008/009/010
admission are still required. No legacy readiness flag is promoted. Strict
release codegen, a clean qualified release and compatibility proof, exact total
resource/time budget presented to the owner, and the single approved operational
window remain mandatory before the stand can collect S180. Completed calibration
is not repeated. Stage17 is incomplete and Stage18 remains deferred.
