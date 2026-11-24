# ADR-0199: Owner-prepared discovery runtime objects

- Status: `ACCEPTED`
- Date: 2026-11-03
- Decision ID: D-199
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: integrate the R0 discovery backend with actual owner mappings

Compose D-188/D-190/D-191/D-194 caller-owned storage, D-195's phase backend,
D-196's owner-mapping lifecycle and D-198's persistent worker stacks. Calculate
exact logical extents and page-rounded mapping requirements before launch,
using the actual compiled object types, queue storage requirements, raw codec,
run IDs and explicit prospective capacities. Reject bad geometry, arithmetic
overflow, reused phase IDs, mismatched mapping sizes and a records home that
differs from the producer home. Copy the input plan before preparation so
later caller mutations cannot change mapped extents or polling controls.
No numeric resource capacity is selected or qualified by this calculation.

Use three separately declared mappings. The actual affined producer prepares
the records/order mapping and producer-state mapping; the actual affined
consumer prepares the consumer-state mapping. Each preparation retains
D-196's requested controls and independent syscall/owner observations. The
producer constructs the arena, active permutation, ring object, slots and
cursors, plus both producer traces, streams and phase state. The consumer
constructs its own traces, streams, phase state and bounded drain retention.
Objects, arrays and raw buffers start at checked cache-line-aligned offsets;
round whole mappings to the verified base-page size. Protect records/order
read-only after producer construction and before readiness publication.

Each worker publishes construction with a release operation. Its peer observes
that publication with acquire semantics before constructing its own trace
facades over the two immutable buffer descriptors. Each facade and phase
object remains in its owner's mapping. Peer construction failure cancels the
handshake; a missing peer exhausts the explicit finite poll budget. Retain
mapping, protection, construction, peer and wait failures distinctly. No
failure permits warmup release, a silent fallback or another preparation.
Destruction after both workers join handles partially constructed objects;
typed destruction precedes release of caller-owned mappings.

Warmup and measurement have distinct primary IDs, buffers, trace state and
ordinals. The same immutable arena, ring and worker threads persist through
the accepted drain/reset transition. Exact raw reconciliation, ordinary
consumer checksums, partial-prefix preservation and no-allocation reset remain
D-195 behavior. This provider supplies no alternative capture algorithm,
estimator, retry, top-up or extension rule.

This does not yet declare the complete process footprint. The provider object,
clock, backend, session/controller coordination, TLS and runtime pages require
explicit placement/coverage in the final action. Independent page residency,
smaps, affinity/fault/control monitoring, finite resource admission, durable
publication, watchdog, source-bound release and exact-boundary qualification
remain required. Successful syscall preparation cannot replace those checks.

Exercise the actual native mappings and persistent mapped pthread stacks with
the real queue, raw streams, immutable arena, bounded drain and exact joins.
Verify owner thread identity, object/buffer containment, read-only requests,
both phases, preparation failure propagation, finite missing-peer waits,
one-shot behavior and frozen-plan independence. Test binding is injected and
timing is synthetic; no empirical observation or stand NUMA claim follows.
Run both compiler suites, relevant sanitizers and strict analysis/format checks.
