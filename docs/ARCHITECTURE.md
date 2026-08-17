# Architecture

## Scope and authority

This is the accepted architecture for Stage A of protocol `2.0.0-pre.1`. ADR-0007 through ADR-0023 additionally freeze the owner-approved C++20/Linux/toolchain/build/test, process/queue/atomic/integrity/correctness, platform/custody, licensing, Stage 3 tooling, and Stage 4 protocol-model boundaries. Exact later platform/pilot evidence remains open. The imported snapshot remains authoritative; contradictions require a versioned protocol amendment. Stage B and Stage C are excluded.

The architecture has three planes:

1. **Benchmark data plane**: only protocol-declared producer/consumer work and thread-private observation appends.
2. **Experiment controller**: preparation, validation, lifecycle transitions, launch/drain, platform evidence, failure recording, and immutable handoff.
3. **Offline validation and analysis**: reconciliation, gates, summaries, inference, sealing, and authorized access after immutable raw publication.

ADR-0001 through ADR-0006 accept the core boundaries. ADR-0007 through ADR-0021 select the implementation architecture and no-license posture. ADR-0022 fixes the Stage 3 build/CI baseline, and ADR-0023 implements the imported logical contracts without selecting a physical codec. Concrete codecs, platform facts, measured-release pins, and scientific/pilot algorithms remain later evidence in the decision register.

## Component map

| Plane | Component | Responsibility | Timed-horizon status | Replaceable boundary / state |
|---|---|---|---|---|
| Data | Specialized producer | Pre-generated arrivals, one enqueue attempt, producer timestamps/outcome, private append, release termination | Required | Queue, clock, prepared schedule, private sink; implementation blocked |
| Data | Specialized consumer | Poll/dequeue, consumer timestamps, immutable record read, fixed checksum update, private append, acquire termination/drain | Required | Queue, clock, record arena, private sink; implementation blocked |
| Data | Queue adapter binding | Narrow operation/boundary seam while preserving ring or linked/recycler semantics | Required | Non-dispatch binding and independent mode accepted; exact proof/representation due Phase 5 |
| Controller | Run-image builder | Parse and semantically validate config, allocate/touch/initialize arenas and buffers, derive schedules, bind identities and capacity proof | Forbidden | Prepared-run image interface; deterministic primitives blocked |
| Controller | Lifecycle orchestrator | Barrier/start/drain/reset, state transitions, failure capture, evidence/artifact publication | Outside horizon | One-process/two-worker topology accepted; implementation pending |
| Controller | Platform-control adapter | Request affinity/NUMA/pages/frequency/HW-PF state, read back and probe, rollback | Forbidden | Linux interface accepted; exact target/authority evidence due Phase 9 |
| Controller | Clock qualification | Qualify source, conversion, skew/drift/read cost and code boundaries | Reads only are timed | Clock interface; source blocked |
| Controller | Logical record model | Typed representation of all seven imported schema families, exact values, lifecycle/gate states, and immutable configuration | Private row construction only | Stage 4 implemented; [model contract](PROTOCOL_MODEL.md) |
| Controller | Physical codec | Encode/decode exact logical rows/envelopes | Private fixed-row write may be timed after format freeze; general codec outside | Replaceable; format blocked until pre-pilot |
| Controller | Artifact store | Immutable content-addressed publication, lineage, access/failure records | Forbidden | Replaceable durable store and separated custody accepted; concrete enforcement later |
| Offline | Structural validator | Draft 2020-12 validation against unmodified imported schemas | Forbidden | Stage 4 implemented with pinned jsonschema and positive/negative fixtures |
| Offline | Semantic validator | Record-local arithmetic, lifecycle, schedule, timestamp, coverage, replacement, and access checks; later cross-record seam | Forbidden | Stage 4 local rules implemented; store-dependent rules explicitly deferred to Phases 12/14 |
| Offline | Reconciler | Join producer/consumer by `(run_id, accepted_ordinal)`, validate record index, emit audit and optional derived join | Forbidden | Consumes immutable sources only |
| Offline | Statistical analysis | Fixed quantiles, diagnostics, H1/H2 families, sealed H3 chronology | Forbidden | Deferred; cannot influence implementation choices |

## Stable interfaces

These are semantic interfaces; they do not prescribe source-language syntax.

### `PreparedRun`

An immutable, fully validated run image containing run identity, specialized package identity, pre-generated integer deadlines, record/node arenas, thread-private buffer extents, exact capacity proof, clock/conversion identity, requested and verified platform evidence references, seeds/algorithm-suite IDs, and all worker addresses. Workers neither parse nor select configuration.

### `QueueAdapter`

A package-bound seam providing one-attempt enqueue/dequeue outcomes and explicit protocol boundary hooks. It must expose, not hide, package-specific linearization, full, recycler, memory-order, prefetch, and progress semantics. API substitutability alone is not scientific equivalence. ADR-0012 requires compile/link-time, direct, or separate-binary binding with no measured-path virtual dispatch or treatment-selection branch.

### `ClockSource`

A qualified integer-tick read plus immutable clock identity/conversion evidence. Qualification covers monotonicity, cross-core skew, drift, resolution, serialization, migration handling, read cost, overflow, and generated instructions. The run cannot switch source or conversion after preparation.

### `PlatformControl`

Separate request, readback, behavioral-probe, and rollback operations for affinity, NUMA placement/residency, page mode, frequency, and documented HW-PF controls. Unsupported or unauthorized capability fails closed. Requested values are never copied into verified fields.

### `LogicalModel` and `PhysicalCodec`

The Stage 4 logical model preserves every imported field, exact integer,
relationship, row ordering, and stream kind. Opaque IDs are never parsed from
paths. Unknown versions/enums/fields fail; configuration has no mutation
surface after load. Structural validation and record-local semantic validation
are separate, and `JCS-I64-v1` supplies deterministic canonical bytes. A
versioned codec declares format, endianness, row/envelope size, alignment, time
unit, compression, decoder identity, and corruption behavior. A codec selection
cannot change logical meaning.

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

Forbidden operations include allocation/deallocation, buffer growth, locks, blocking I/O, file access, console logging, formatting, dynamic parsing, RNG/permutation, manifest construction, whole-artifact hashing, compression, reconciliation, quantiles/histograms, analysis, adaptive backoff, sleep/yield, scheduler calls, runtime queue dispatch/treatment selection, mutable record preparation, and platform-state changes.

Generated-code and call-graph acceptance must prove this contract for every package specialization. Overflow never triggers aggregation, allocation, or emergency I/O; it records a measurement failure after safely leaving the horizon.

## Ownership and accepted deployment

ADR-0012 requires one unprivileged measurement process with a quiescent controller main thread, exactly one producer, exactly one consumer, and exclusive mutable cache-line ownership. ADR-0018 and ADR-0020 keep privileged platform control and validation custody out of process under separate principals. The implementation must prove:

- worker-local raw buffers and mutable controls occupy separately evidenced cache lines/pages;
- no observer touches hot ownership lines during the horizon;
- affinity and page placement are commanded and independently verified;
- crash/lifecycle states yield the exact append-only artifact set;
- privileges are absent from the measurement process;
- validation custody is technically separated from implementation/platform operation.

## Failure and compatibility model

Lifecycle transitions and partial failures are append-only. Early failure cannot fabricate raw artifacts. Producer and consumer sources remain independently immutable; failed reconciliation produces an audit and no joined-derived stream. A correction or format conversion creates a derived artifact. Replacement follows the complete-block protocol and never reuses run identity.

Readers fail closed on unknown protocol/schema, artifact-kind, physical-format, clock, RNG, permutation, mixing, checksum, or canonicalization identifiers. The current implementation accepts only internally consistent `2.0.0-pre.1` records; it provides no 1.x migration or future-enum pass-through. Additive compatibility must be declared and tested; changed bytes always receive new content identity.

## Deferred decisions

The owner selected no repository license grant in ADR-0021, Stage 3 pins the development/CI tool series in ADR-0022, and Stage 4 implements typed logical records in ADR-0023. Queue representation/proofs, exact measured-release pins, target stand/authority facts, clock, raw format, RNG/schedule/mixing/checksum details, Linux target mappings, custody enforcement, and compression/copies remain at their documented later gates. None may be filled by a build or configuration default.
