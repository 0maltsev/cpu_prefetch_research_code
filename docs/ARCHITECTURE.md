# Architecture

## Scope and authority

This is the accepted Stage 2 architecture for Stage A of protocol `2.0.0-pre.1`. It freezes boundaries, not the recommended C++/Linux/toolchain choices. The imported snapshot remains authoritative; contradictions require a versioned protocol amendment. Stage B and Stage C are excluded.

The architecture has three planes:

1. **Benchmark data plane**: only protocol-declared producer/consumer work and thread-private observation appends.
2. **Experiment controller**: preparation, validation, lifecycle transitions, launch/drain, platform evidence, failure recording, and immutable handoff.
3. **Offline validation and analysis**: reconciliation, gates, summaries, inference, sealing, and authorized access after immutable raw publication.

ADR-0001 through ADR-0006 accept these boundaries. Executable topology, language, toolchain, concrete codecs, platform adapters, and dependency implementations remain open in the decision register.

## Component map

| Plane | Component | Responsibility | Timed-horizon status | Replaceable boundary / state |
|---|---|---|---|---|
| Data | Specialized producer | Pre-generated arrivals, one enqueue attempt, producer timestamps/outcome, private append, release termination | Required | Queue, clock, prepared schedule, private sink; implementation blocked |
| Data | Specialized consumer | Poll/dequeue, consumer timestamps, immutable record read, fixed checksum update, private append, acquire termination/drain | Required | Queue, clock, record arena, private sink; implementation blocked |
| Data | Queue adapter binding | Narrow operation/boundary seam while preserving ring or linked/recycler semantics | Required | Binding mechanism, provenance, and atomic mapping blocked |
| Controller | Run-image builder | Parse and semantically validate config, allocate/touch/initialize arenas and buffers, derive schedules, bind identities and capacity proof | Forbidden | Prepared-run image interface; deterministic primitives blocked |
| Controller | Lifecycle orchestrator | Barrier/start/drain/reset, state transitions, failure capture, evidence/artifact publication | Outside horizon | Process topology blocked |
| Controller | Platform-control adapter | Request affinity/NUMA/pages/frequency/HW-PF state, read back and probe, rollback | Forbidden | Linux candidate only; target/authority blocked |
| Controller | Clock qualification | Qualify source, conversion, skew/drift/read cost and code boundaries | Reads only are timed | Clock interface; source blocked |
| Controller | Logical record model | Typed representation of imported schema/data-dictionary meanings | Private row construction only | Accepted stable boundary |
| Controller | Physical codec | Encode/decode exact logical rows/envelopes | Private fixed-row write may be timed after format freeze; general codec outside | Replaceable; format blocked until pre-pilot |
| Controller | Artifact store | Immutable content-addressed publication, lineage, access/failure records | Forbidden | Replaceable durable store; custody blocked |
| Offline | Structural validator | Draft 2020-12 validation against imported schemas | Forbidden | Validator product open |
| Offline | Semantic validator | Cross-record identity, arithmetic, lifecycle, schedule, namespace, timestamp, coverage, replacement, access checks | Forbidden | Versioned rules; implementation open |
| Offline | Reconciler | Join producer/consumer by `(run_id, accepted_ordinal)`, validate record index, emit audit and optional derived join | Forbidden | Consumes immutable sources only |
| Offline | Statistical analysis | Fixed quantiles, diagnostics, H1/H2 families, sealed H3 chronology | Forbidden | Deferred; cannot influence implementation choices |

## Stable interfaces

These are semantic interfaces; they do not prescribe source-language syntax.

### `PreparedRun`

An immutable, fully validated run image containing run identity, specialized package identity, pre-generated integer deadlines, record/node arenas, thread-private buffer extents, exact capacity proof, clock/conversion identity, requested and verified platform evidence references, seeds/algorithm-suite IDs, and all worker addresses. Workers neither parse nor select configuration.

### `QueueAdapter`

A package-bound seam providing one-attempt enqueue/dequeue outcomes and explicit protocol boundary hooks. It must expose, not hide, package-specific linearization, full, recycler, memory-order, prefetch, and progress semantics. API substitutability alone is not scientific equivalence. Static templates, direct binding, and separate binaries remain candidates; Q2 recommends a binding with no measured-path dispatch or treatment-selection branch, but that recommendation is not accepted by this interface.

### `ClockSource`

A qualified integer-tick read plus immutable clock identity/conversion evidence. Qualification covers monotonicity, cross-core skew, drift, resolution, serialization, migration handling, read cost, overflow, and generated instructions. The run cannot switch source or conversion after preparation.

### `PlatformControl`

Separate request, readback, behavioral-probe, and rollback operations for affinity, NUMA placement/residency, page mode, frequency, and documented HW-PF controls. Unsupported or unauthorized capability fails closed. Requested values are never copied into verified fields.

### `LogicalModel` and `PhysicalCodec`

The logical model preserves every imported field, exact integer, relationship, row ordering, and stream kind. A versioned codec declares format, endianness, row/envelope size, alignment, time unit, compression, decoder identity, and corruption behavior. A codec selection cannot change logical meaning.

### `ArtifactStore`

Publishes immutable byte objects and append-only metadata with stable IDs, SHA-256, byte/row counts, origin, lifecycle state, lineage, access state, and compatibility identifiers. Corrections/conversions are new derived objects. A failed step publishes only evidence actually produced.

### `QueueProvenance`

For each queue package, binds paper section/figure, official artifact search record, immutable artifact IDs/hashes if any, license, selected reuse/adaptation/independent mode, adaptation list, and refinement proof. Absence blocks queue source work.

## Timed-path contract

Allowed operations are limited to:

- read a pre-generated deadline and qualified clock; relax-only polling;
- process overdue logical arrivals in original order;
- deterministic precomputed record-pointer lookup;
- exactly one package-bound enqueue attempt with fixed timestamps;
- package-bound dequeue polling and drain with fixed timestamps;
- protocol-declared ring or linked/recycler operations and prefetch hints;
- immutable record index/payload loads and one fixed private checksum update;
- fixed-capacity append to the calling worker's private raw buffer;
- isolated release/acquire termination.

Forbidden operations include allocation/deallocation, buffer growth, locks, blocking I/O, file access, console logging, formatting, dynamic parsing, RNG/permutation, manifest construction, whole-artifact hashing, compression, reconciliation, quantiles/histograms, analysis, adaptive backoff, sleep/yield, scheduler calls, mutable record preparation, and platform-state changes. The binding mechanism is still a Q2 decision; whichever mechanism is accepted must be frozen and included in generated-code and treatment-equivalence review.

Generated-code and call-graph acceptance must prove this contract for every package specialization. Overflow never triggers aggregation, allocation, or emergency I/O; it records a measurement failure after safely leaving the horizon.

## Ownership and proposed deployment

The accepted architecture requires exactly one producer and one consumer and exclusive mutable cache-line ownership. D-006 recommends one unprivileged measurement process with a quiescent controller main thread and two workers, while privileged platform control and validation custody remain out of process. This topology is not accepted until the owner chooses it. Whichever topology is accepted must prove:

- worker-local raw buffers and mutable controls occupy separately evidenced cache lines/pages;
- no observer touches hot ownership lines during the horizon;
- affinity and page placement are commanded and independently verified;
- crash/lifecycle states yield the exact append-only artifact set;
- privileges are absent from the measurement process;
- validation custody is technically separated from implementation/platform operation.

## Failure and compatibility model

Lifecycle transitions and partial failures are append-only. Early failure cannot fabricate raw artifacts. Producer and consumer sources remain independently immutable; failed reconciliation produces an audit and no joined-derived stream. A correction or format conversion creates a derived artifact. Replacement follows the complete-block protocol and never reuses run identity.

Readers fail closed on unknown protocol/schema, artifact-kind, physical-format, clock, RNG, permutation, mixing, checksum, or canonicalization identifiers. Additive compatibility must be declared and tested; changed bytes always receive new content identity.

## Deferred decisions

The concrete language/toolchain/build/tests, target stand, queue implementation mode, atomics, clock, raw format, RNG/schedule/mixing/checksum suite, Linux API bindings, privilege/custody design, generated-code tools, sanitizer thresholds, compression/copies, and project license remain in `docs/DECISIONS_REQUIRED.md`. Production code must not start while their Stage 3 blockers remain open.
