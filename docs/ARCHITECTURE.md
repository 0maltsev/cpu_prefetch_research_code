# Architecture

## Scope and authority

This is the accepted architecture for Stage A of protocol `2.0.0-pre.2`, with
immutable predecessor `2.0.0-pre.1`. ADR-0007 through ADR-0040 freeze the
owner-approved software foundation through Stage 14 synthetic orchestration
software. Exact eligible-stand mappings/evidence, concrete Stage A freeze
inputs, and later pilot outputs remain open. Imported
snapshots remain authoritative under their versions; contradictions require a
versioned protocol amendment. Stage B and Stage C are excluded.

The architecture has three planes:

1. **Benchmark data plane**: only protocol-declared producer/consumer work and thread-private observation appends.
2. **Experiment controller**: preparation, validation, lifecycle transitions, launch/drain, platform evidence, failure recording, and immutable handoff.
3. **Offline validation and analysis**: reconciliation, gates, summaries, inference, sealing, and authorized access after immutable raw publication.

ADR-0001 through ADR-0006 accept the core boundaries. ADR-0007 through ADR-0021 select the implementation architecture and no-license posture. ADR-0022 fixes the Stage 3 build/CI baseline, ADR-0023 implements the imported logical contracts, and ADR-0032/0033 now supply the replaceable v1 physical codec and local durability implementation. Platform facts, measured-release pins, real storage domains, and scientific/pilot algorithms remain later evidence in the decision register.

## Component map

| Plane | Component | Responsibility | Timed-horizon status | Replaceable boundary / state |
|---|---|---|---|---|
| Data | Specialized producer | Pre-generated arrivals, one enqueue attempt, producer timestamps/outcome, private append, release termination | Required | Stage 10 implements the generic executor; Stage 11 statically binds exact capture to a preallocated producer-private sink; final package/platform specialization remains Phase 16 |
| Data | Specialized consumer | Poll/dequeue, consumer timestamps, immutable record read, fixed checksum update, private append, acquire termination/drain | Required | Stage 10 implements polling/drain; Stage 11 statically binds exact capture to a preallocated consumer-private sink; final package/platform specialization remains Phase 16 |
| Data | Queue/package binding | Five concrete static policies preserve ring/linked semantics and exact treatment-specific hint targets | Required | Stage 5 queue cores plus Stage 6 target seams/codegen pass; platform hint instruction and `d2` evidence remain open |
| Controller | Run-image builder | Parse and semantically validate config, allocate/touch/initialize arenas and buffers, derive schedules, bind identities and capacity proof | Forbidden | Stage 6 arena/order/footprint and Stage 7 schedule primitives implemented; integration and real stand facts blocked |
| Controller | Schedule preparation | Derive the purpose-separated stream, generate the complete open-loop schedule, publish artifact/envelopes, decode and validate immutable deadlines | Forbidden | Stage 7 implemented; all lifecycle values remain explicit and no outcome/clock input exists |
| Controller | Workload construction | Derive domain-separated streams, build event/node order, initialize records, retain integrity inputs, bind one package type | Forbidden | Stage 6 implemented; all values explicit and no worker mutation surface |
| Controller | Lifecycle orchestrator | Barrier/start/drain/reset, state transitions, failure capture, evidence/artifact consequences | Outside horizon | Stage 10 lifecycle is implemented; Stage 11 adds partial-stream finalization and immutable publication without reconciliation |
| Controller | Block planner | Prove/generate the exact Stage A product from explicit frozen roles, namespaces, keys, seed catalogs, counts, and identities | Forbidden | Stage 14 deterministic generator/pool validator implemented; concrete pilot-derived inputs remain external |
| Controller | Platform-control adapter | Inventory/capabilities, explicit affinity/NUMA/pages/environment/HW-PF request, separate apply/readback/probe, reverse rollback, manifests | Forbidden | Stage 9 read-only Linux inventory, dry-run, strict validation, injected actuator/verifier, restoration, and manifests implemented; exact stand actuator/authority and dynamic address evidence remain external gates |
| Controller | Clock qualification | Evaluate the accepted source, conversion, skew/drift/read cost and code boundaries from explicit platform evidence | Reads only are timed | D-009 software/codegen implemented; dynamic explicit-pair and before-block evidence pending Phase 9/16 |
| Controller | Logical record model | Typed representation of all seven imported schema families, exact values, lifecycle/gate states, and immutable configuration | Private row construction only | Stage 4 implemented; [model contract](PROTOCOL_MODEL.md) |
| Controller | Physical codec | Encode/decode exact logical rows/envelopes | Private fixed-row write is timed; decoding/envelopes are outside | `RAW-OBS-U64LE-LP-RUNID-v1` implemented; new formats remain replaceable under a new ID |
| Controller | Artifact store | Immutable content-addressed publication, copy evidence, partial finalization | Forbidden | Stage 11 local no-replace/two-copy backend implemented; real failure domains and separated custody remain Phase 16 evidence |
| Offline | Structural validator | Draft 2020-12 validation against unmodified imported schemas | Forbidden | Stage 4 implemented with pinned jsonschema and positive/negative fixtures |
| Offline | Semantic validator | Record-local arithmetic/lifecycle, run-level immutable relationships, and block/replacement/access graph validation | Forbidden | Stage 4 local, Stage 12 run-level, and Stage 14 block/access layers implemented; final acceptance still requires concrete frozen evidence |
| Offline | Reconciler | Build accepted producer order; exact k-th join by `(run_id, accepted_ordinal)`; validate Stage 6 mapping/index; emit audit and conditional derived join | Forbidden | Stage 12 implemented; consumes immutable sources only and derives nothing on failed audit |
| Offline | Calibration evaluator | Validate prospective service/ring/probe plans and immutable raw evidence; compute exact minima/tails/exposure bounds; emit append-only freeze candidates | Forbidden | Stage 13 implemented with synthetic/fake inputs; stand values and final exposure remain external gates |
| Offline | Access/replacement orchestrator | Enforce sealing chronology, authority segregation, immutable amendment lineage, and complete-block-only replacement | Forbidden | Stage 14 implemented with synthetic records; real principals/custody/budget remain Phase 16/18 evidence |
| Offline | Statistical analysis | Fixed quantiles, diagnostics, H1/H2 families, sealed H3 chronology | Forbidden | Deferred; cannot influence implementation choices |

## Stable interfaces

These are semantic interfaces; they do not prescribe source-language syntax.

### `PreparedRun`

An immutable, fully validated run image containing run identity, specialized package identity, pre-generated integer deadlines, record/node arenas, thread-private buffer extents, exact capacity proof, clock/conversion identity, requested and verified platform evidence references, seeds/algorithm-suite IDs, and all worker addresses. Workers neither parse nor select configuration.

### `QueueAdapter`

A package-bound seam providing one-attempt enqueue/dequeue outcomes while retaining package-specific linearization, full, recycler, memory-order, and progress semantics. Stage 5 implements separate final `RingQueueAdapter` and `LinkedQueueAdapter` types with no common virtual base or runtime family selector. Stage 6 adds concrete `R0`, `R1`, `R2`, `L0`, and `L1` policy types: their target sites are fixed and a statically bound emitter preserves the still-unselected platform encoding. Their `noexcept` operations are constant-step and contain no allocation, retry, wait, logging, exception control flow, or runtime package dispatch. API substitutability alone is not scientific equivalence.

### `WorkloadConstruction`

Consumes only explicit line/page/cache/capacity, seed, namespace, and accepted
algorithm identifiers. It produces a base-page-aligned, fully touched immutable
event arena, cyclic event order, `C+1` linked-node order, exact footprint
results, content/order/delta integrity inputs, and one statically selected
package. `RecordIndex`, `LogicalSequence`, and `AcceptedOrdinal` are distinct;
no pointer is serialized. Platform residency and prefetch encoding remain
outside this interface and cannot be inferred from allocation success.

### `SchedulePreparation`

The standalone Python 3.14 producer consumes only explicit schedule identity,
kind, master seed and seed identity, parent/child namespaces, origin, positive
horizon, reduced rational rate, and output identities. It emits immutable
absolute-u64be bytes, the imported logical envelope, and a self-hashed
derivation record. The C++ decoder validates the accepted suite, exact
derivation/runtime binding, artifact shape, half-open/nondecreasing/count rules,
and all integrity identities before returning a `PreparedSchedule`. A separate
validator receives explicit lifecycle roles and common-family membership; it
never infers either from a path or name. Generation and validation cannot see
queue completion, clock readings, or measured outcomes.

### `CalibrationEvaluation`

Consumes a complete prospective plan plus immutable raw calibration references.
The C++ service evaluator requires the exact 60-cell Stage A context product
and permits only the continuous-ready workload difference. Plans require
owner, authority, and stand-budget evidence. The ring evaluator requires six
contexts, separate H0/H1 R0 evidence, preallocated acquire-demand series, and
advancement-only issue intervals. Both retain per-run status/source decisions
and emit exact typed results or explicit unresolved/ineligible blockers;
neither retries, tops up, reads confirmatory outcomes, or selects from treatment
effects. The offline matrix interface requires an exact 180-cell result for
each evaluated member of the predeclared five-candidate family, accepted
confidence, threshold, descending-prefix stopping rule, and Decimal profile.
Canonical plan/result/freeze records publish no-replace and bind a material
invalidation fingerprint. This interface has no default duration, count,
capacity, rate, distance, exposure, stand, or authority.

### `BlockOrchestration`

Consumes explicit prospective precision evidence, platform/build identity,
role namespaces, block seed catalogs, pre-derived Philox keys, authority
assignments, immutable artifacts, and replacement budget. It proves the exact
180-cell product and pool role counts, emits a deterministic imported block
document, evaluates sealing/access chronology, and authorizes only complete
role-preserving replacements. Missing inputs remain unresolved. The interface
has no filesystem identity inference, outcome input to generation/resizing,
artifact-reader capability, cell-repair method, or execution method. See
[`ORCHESTRATION.md`](ORCHESTRATION.md).

### `ClockSource`

A qualified integer-picosecond read plus immutable clock identity/conversion
evidence. D-009/ADR-0030 selects vDSO
`clock_gettime(CLOCK_MONOTONIC_RAW)`, exact nanosecond-to-picosecond conversion,
compiler-only read fences, bracketed queue boundaries, and uncorrected raw
values. `cpu_prefetch_timing` implements the reader, raw absolute-nanosecond plus
relative-picosecond sample, static producer/consumer boundary observers,
offline interval equations, and fail-closed qualification evaluators.
Qualification covers monotonicity, cross-core skew, drift, resolution,
serialization, migration handling, read cost, overflow, syscall exclusion, and
generated instructions. The run cannot switch source or conversion after
preparation, and static inventory cannot substitute for explicit worker-pair
and dynamic qualification evidence.

### `PlatformControl`

`cpu_prefetch_platform` separates inventory, capability detection, requested-state validation, apply, independent verification, restoration, and manifest emission. The real Linux provider is read-only and records CPU/core/package/NUMA/cache/PCI topology, page and environment observations, and software/hardware provenance without choosing a stand or pair. Stage A validation requires explicit non-SMT near/far CPUs, producer-home shared memory, worker-local private buffers, and the inventoried base-page policy; Stage C alternatives reject.

Every control names an exact target/value, authority, actuation mechanism, verification mechanism, snapshot, and state epoch. Dry-run never calls an actuator. Successful apply is only an apply fact; fresh exact readback through the verifier is required separately. Partial apply restores recorded pre-state in reverse order and retains any restoration failure. Rich canonical evidence preserves partial failure, while a separate emitter produces only the immutable imported platform-schema shape. Unsupported/unauthorized/missing/stale capability fails closed. The repository does not ship a mutating stand backend: exact stand mappings, vendor HW-prefetch fields, behavioral probes, privileges, and rollback remain required evidence under [the Stage 9 contract](PLATFORM_CONTROL.md).

### `RunLifecycle`

`cpu_prefetch_lifecycle` owns an explicit controller phase graph whose values
project onto, but never extend, the imported stable lifecycle enum. Each
transition records time, actor, reason, and append/retain/absence consequences.
Preparation and warm-up evidence require distinct schedule namespaces,
deterministic preallocation, stopped/drained warm arrivals, and no ambiguous
continuation. A replaceable reset interface verifies exact ring or linked
origin while preserving allocation/mapping/data-home/permutation/payload
identity.

The start barrier release-publishes one explicit measurement origin. A generic
compile-time executor consumes only an immutable deadline span, issues exactly
one producer backend call per due arrival, polls the consumer, and uses a
dedicated lock-free u32 release/acquire termination word before drain-to-empty.
It supplies no clock, relax instruction, watchdog value, queue family, or
platform default. Stage 11 supplies a statically bound physical capture backend
without selecting those remaining facts. Full semantics and later gates are recorded in
[`LIFECYCLE.md`](LIFECYCLE.md).

### `LogicalModel` and `PhysicalCodec`

The Stage 4 logical model preserves every imported field, exact integer,
relationship, row ordering, and stream kind. Opaque IDs are never parsed from
paths. Unknown versions/enums/fields fail; configuration has no mutation
surface after load. Structural validation and record-local semantic validation
are separate, and `JCS-I64-v1` supplies deterministic canonical bytes. A
versioned codec declares format, endianness, row/envelope size, alignment, time
unit, compression, decoder identity, and corruption behavior. A codec selection
cannot change logical meaning. Q9/ADR-0032 now freezes
`RAW-OBS-U64LE-LP-RUNID-v1`; Stage 11 implements it behind this seam without
replacing the logical model with its byte layout. Its decoder maps into Stage
4 logical rows and applies the record-local semantic validator.

### `ArtifactStore`

Publishes immutable byte objects and append-only metadata with stable IDs,
SHA-256, byte/row counts, origin, lifecycle state, lineage, access state, and
compatibility identifiers. Stage 11 implements unique run directories,
exclusive staging, checked sync/readback, atomic no-replace publication, two
explicit domain copies, copy ledgers, and recovery-only reopening of an exact
staging object. Corrections/conversions are new derived objects. A failed step
publishes only evidence actually produced.

### `QueueProvenance`

For each queue package, binds paper section/figure, official artifact search record, source hashes, license, independent mode, every adaptation, memory-order/atomic/layout map, claim boundary, refinement proof, tests, sanitizers, and generated-code status. Stage 5 records live under `config/queue-provenance/` and are fail-closed checked. Exact historical FastFlow artifact status remains unresolved but no source is reused. Missing dual-disassembler evidence blocks Stage 5 closure without changing the implementation mode.

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

Readers fail closed on unknown protocol/schema, artifact-kind, physical-format,
clock, RNG, permutation, mixing, checksum, or canonicalization identifiers.
The loader reads pre.1 and pre.2 under distinct contracts; new output is pre.2
and Stage 12 rejects mixed graphs. There is no implicit migration, repair, or
future-enum pass-through. Frozen ADR-0025/0029 pre.1 derivation-domain labels
remain suite identity. Additive compatibility must be declared and tested;
changed bytes always receive new content identity.

## Accepted baselines and deferred evidence

The owner selected no repository license grant in ADR-0021. ADR-0022 through
ADR-0028 fix the development toolchain, typed model, queues, and Stage 6
construction; ADR-0029 fixes the schedule; ADR-0030 fixes the implemented clock
contract; and ADR-0031 fixes the Stage 10 lifecycle/termination mapping. Stage
9 implements the accepted ADR-0018/0019 software boundary without selecting
target facts.

Q9/ADR-0032/0033 additionally freeze the raw format and no-compression/
one-temporary/two-durable-domain policy. Stage 11 implements the codec,
preallocated private writers, integrity/envelope/ledger records, checked
capacity model, and local crash-aware store; cross-decoder, corruption,
sanitizer, and dual-disassembler software evidence passes. Phase 16 real
domain/custody/capacity/page-residency/recovery proof remains open. Concrete seeds/capacities, node
page-frame qualification, vendor prefetch encoding/probes, calibrated `d2`,
eligible-stand facts, and other later inputs remain unresolved and cannot be
filled by a build or configuration default.
