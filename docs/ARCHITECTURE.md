# Architecture

## Purpose and authority

This document designs component boundaries for Stage A protocol `2.0.0-pre.1`; it does not choose a language, toolchain, raw-data encoding, queue source, platform API, or executable layout. The imported protocol controls scientific behavior. Engineering choices may realize that behavior but may not reinterpret it.

The design separates three concerns:

1. the benchmark data plane performs only predeclared measurement work;
2. the controller and validation plane prepares, verifies, and records a run;
3. the offline plane reconciles immutable streams, applies gates, and performs analysis under access control.

Any interface that cannot preserve a normative requirement is blocked pending an ADR or, for a scientific change, a protocol amendment.

## Planned components

| Component | Responsibility | Principal inputs and outputs | Timed-path role | Current state |
|---|---|---|---|---|
| Benchmark data plane | Specialized producer/consumer execution, one-attempt arrivals, polling, termination, and private observation writes | Frozen run image; producer and consumer logical observations | Yes; smallest possible owner | Blocked on language, process/thread model, clock, and storage layout |
| Experiment controller | Lifecycle state machine, preparation, barriers, run launch, drain, evidence collection, failure/sealing coordination | Validated run plan to append-only manifest/failure/artifact records | Control only; absent during measurement except prebuilt synchronization | Architecture planned |
| Protocol/configuration validation | Draft 2020-12 structural validation plus cross-record semantic validation | Immutable config/records to typed validation reports | Forbidden | Validator architecture unresolved |
| Schedule generation | Seed namespace derivation, pre-generated deadlines, exact rational rates, half-open horizons, encoding envelope, checksums | Frozen seed/config to immutable schedule artifact | Reads next prepared deadline only | Algorithms/encoding unresolved |
| Queue adapters | One stable `try_enqueue`/`try_dequeue` seam while preserving package-specific linearization, memory order, progress, prefetch, and recycler semantics | Pointer plus package configuration; operation outcome/boundaries | Yes | Blocked on provenance/license/mode and atomic mapping |
| Record and working-set generation | One-line immutable record arena, payload/index initialization, event permutation, linked-node permutation, footprint and address-pattern evidence | Frozen seeds/platform cache facts to persistent arenas and reports | Deterministic pointer lookup and immutable record loads only | Algorithms and platform facts unresolved |
| Timing | Monotonic cross-core tick reads, boundaries, conversion record, overhead/skew/drift evidence | Platform clock record to integer timestamps | Yes, only frozen boundary reads | Platform mapping unresolved |
| Affinity, NUMA, and hardware-state control | Core selection, first touch, page residency, requested HW-PF actuation, independent readback/probe, environmental checks | Platform/control authorization to requested and verified state records | Verification must not touch hot lines; no dynamic control in timed path | Platform and authority unresolved |
| Raw-stream storage | Preallocated producer-private and consumer-private buffers; post-run immutable artifact sealing | Logical rows to external immutable streams/envelopes | Private fixed-capacity append only | Physical encoding deliberately unresolved |
| Producer/consumer reconciliation | Accepted-sequence construction, ordinal join, record-index validation, timestamp/equation checks, joined stream and join audit | Two immutable raw streams to pass/fail audit and optional joined-derived artifact | Forbidden | Planned |
| Manifest, integrity, failure, and sealing records | Append-only identity, lifecycle, count, checksum, provenance, access, and failure relationships | Component evidence to schemas and content hashes | Forbidden except final private checksum value accumulation defined by protocol | Sealing architecture unresolved |
| Calibration | Treatment-blind service-rate, zero-loss feasibility, ring-distance, clock, horizon, and environment procedures | Valid calibration/pilot artifacts to frozen decision records | Separate run mode, never substituted for Stage A | Deferred and unauthorized |
| Block planning and Stage A orchestration | Exact 180-cell factorials, whole plots, immutable roles, role-compatible namespaces, randomized order, complete-block replacement | Frozen decisions/seeds to block and run plans | Forbidden | Counts, algorithms, budget, and authorities unresolved |
| Offline statistical analysis | Inverse-ECDF summaries, effective-tail diagnostics, model/contrasts, separate H1/H2 max-T, sealed H3 sequence, derived outputs | Passed immutable artifacts and authorized access state to source-linked results | Forbidden | Deferred; no result pipeline implemented |

## Boundary rules

### Data-plane input

Before worker release, the controller must provide a closed, validated run image containing all addresses, queue/package specialization, schedule, seeds, preallocated capacities, timestamp conversion identity, requested and verified hardware state evidence, and immutable run identity. Workers do not parse manifests or choose behavior dynamically.

### Queue seam

The future queue seam is behavioral rather than a license to normalize algorithms. It must expose a one-attempt outcome and the protocol-defined invocation, queue-specific linearization, and response boundaries. Package-specific code remains statically specialized so the common driver does not introduce virtual dispatch or a treatment-dependent branch. The linked adapter includes the regular recycler path. A common facade must not erase different full semantics, memory orders, prefetch sites, or refinement obligations.

### Storage interface

No concrete binary or columnar encoding is selected. The future storage interface must:

- accept fixed-capacity thread-private appends without allocation or blocking;
- represent every normative logical field and exact integer tick;
- distinguish producer, consumer, and joined-derived stream kinds;
- bind every row and envelope to `run_id`;
- expose row count, byte count, encoding, time unit, endianness, compression, immutable ordering, physical-format record ID, URI, integrity reference, and SHA-256;
- decode exactly the declared count and validate decoded logical rows;
- seal raw source streams immutably and create corrections only as new derived artifacts;
- compress only after measurement with a frozen lossless method.

Before pilot, an ADR and freeze record must select the physical format, row layouts/sizes/alignment, endianness, lossless compression, copy policy, canonical serialization, and capacity proof. Selecting those items now would invent evidence not present in the protocol.

### Validation interface

Schema validation checks document shape. A separate semantic validator must check arithmetic, decoded schedules, namespaces, cross-record hashes, lifecycle chronology, count identities, timestamp equations, exact factorial coverage, replacement lineage/budget, access chronology, role membership, and authority segregation. Neither layer may silently repair an instance.

### Failure and append-only behavior

The controller records the lifecycle reached and only artifacts that actually exist. Early failure never fabricates raw data. Failed reconciliation seals a failed join audit and forbids joined-derived data. Raw producer/consumer artifacts are never overwritten. A correctness or measurement failure leaves its original block incomplete; only an authorized new complete role-compatible block can replace it.

## Timed-path allowlist and denylist

Only these planned operations may occur in the Stage A measurement path:

- poll a pre-generated deadline with the frozen clock read and processor-relax mapping;
- handle overdue logical arrivals in original order;
- deterministic record-index/pointer lookup;
- one specialized queue `try_enqueue` attempt and its timestamps;
- specialized repeated `try_dequeue`, empty polling, and timestamps;
- the protocol-fixed ring or linked queue/recycler operations and prefetch hints;
- immutable record index/payload loads and one fixed consumer-private checksum update;
- fixed-capacity writes to the calling worker's private raw buffer;
- release/acquire termination using an isolated control line.

The measurement path forbids unplanned allocation/deallocation, buffer growth, locks, blocking I/O, file access, console logging, formatted output, dynamic configuration parsing, RNG use, permutation/sorting, manifest construction, checksum of whole artifacts, compression, reconciliation, quantile/histogram computation, statistical analysis, adaptive backoff, sleep/yield/scheduler calls, virtual dispatch, treatment-dependent driver branches, mutable event preparation, and platform-state changes.

## Deployment and process boundary

The process/thread model is deliberately open. Any candidate must provide exactly one producer and one consumer for Stage A, isolate mutable ownership lines, support worker-local raw buffers and page placement, allow independent control/custody processes where sealing requires them, and leave no observer touching hot ownership lines. The selected model, crash behavior, privilege separation, and artifact handoff require an ADR before production architecture is finalized.

## Deferred scope

Stage B tagged-pointer MPSC and all Stage C ablations are outside this architecture. They may reuse stable infrastructure only after separate authorization; they cannot weaken or substitute any Stage A component or gate.
