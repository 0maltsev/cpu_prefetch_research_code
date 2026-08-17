# Data Flow and Artifact Lifecycle

Protocol version: **`2.0.0-pre.1`**. This document preserves the imported logical model; it does not select a physical raw encoding.

## End-to-end flow

| Phase | Inputs | Work | Append-only outputs | Timed? |
|---|---|---|---|---|
| Import/readiness | Immutable protocol snapshot and manifest | Hash, inventory, JSON parse, Draft 2020-12 meta-schema, positive/negative fixture, and canonical-byte checks | Readiness evidence in repository status | No |
| Experiment preparation | Protocol, accepted ADRs, platform inventory, block/run plan, algorithm suite, seeds | Imported-schema validation, immutable typed loading, record-local semantic validation, then later derivation/allocation/capacity proof | Validated logical records; later prepared-run identity, schedule, provenance, and platform evidence references | No |
| Platform preparation | Requested state and authorized adapter/operator | Affinity/NUMA/page/frequency/HW-PF actuation, independent readback/probes, rollback readiness | Requested-state and verified-state records, capability/failure evidence | No |
| Run launch | Closed `PreparedRun` | Barrier/reset/warm-up/start transition | Lifecycle transition(s) | No; boundary reads only as fixed |
| Measurement horizon | Pre-generated deadlines, fixed arenas, specialized queue, qualified clock | Producer and consumer execute fixed data-plane work | Thread-private producer and consumer observations in preallocated buffers | Yes |
| Drain/finalize | Worker state and private buffers | Protocol drain/termination, count capture, checksum finalization | Final worker counts/status; no artifact I/O yet | Fixed drain semantics; publication no |
| Raw publication | Completed or partial buffers plus lifecycle state | Encode, hash, durably append, link failures | Immutable producer and/or consumer raw artifacts, manifests, failure records | No |
| Reconciliation | Two immutable raw sources | Build accepted sequences, join by `(run_id, accepted_ordinal)`, validate record index/timestamps/counts | Immutable join audit; joined-derived artifact only on success | No |
| Validation/gates | Immutable artifacts and platform evidence | Structural then semantic validation; correctness, measurement, zero-loss, tail gates | Versioned validation reports and eligibility states | No |
| Analysis/sealing | Eligible immutable artifacts and authorized access state | Fixed summaries/inference; H3 training, seal, validation access | Derived results, source links, signatures/access records | No and custody-controlled |

## Preparation-to-worker boundary

The controller resolves every dynamic choice before release. The prepared image contains exact addresses and extents, pre-generated deadlines, package specialization, run and algorithm-suite IDs, clock identity, platform evidence references, and fixed buffer capacity. Allocation, schema/config parsing, seed derivation, RNG, permutation, compression, and analysis are absent from the worker call graph.

Stage 4 supplies the pre-worker typed boundary but does not build a prepared
image. Each input first passes its unmodified imported Draft 2020-12 schema,
then immutable typed loading, then record-local semantic rules. Stable errors
carry category/path/rule identity and never repair input. Cross-record
resolution is accepted only after the Phase 12/14 validators described in
[`PROTOCOL_MODEL.md`](PROTOCOL_MODEL.md) exist.

Stage 5 supplies only the queue-operation seam beneath a future prepared image.
The producer can issue one direct nonblocking enqueue call and retain
`accepted` or `full`; the consumer can issue one direct nonblocking dequeue
poll and retain `item` or `empty`. Ring and linked/recycler adapters remain
distinct, so linked recycler exhaustion/ownership and ring slot reuse are not
normalized away. Stage 5 tests execute these operations with synthetic records
but create no run identity, clock, observation row, manifest, or measurement.

The producer and consumer receive disjoint mutable observation buffers. They record their own facts independently and in program order. The repeating record index is a validation field only; it is never an event ID. Accepted observations are reconciled later by run identity and accepted ordinal.

## Logical streams

| Stream | Principal producer | Identity/order | Required handling |
|---|---|---|---|
| Producer raw | Producer worker, published by controller | `run_id`, attempt order, accepted ordinal where applicable | Preserve every attempt/outcome, exact integer ticks, and original order |
| Consumer raw | Consumer worker, published by controller | `run_id`, dequeue/completion order and accepted ordinal | Preserve independent observations, record index/payload validation, exact ticks |
| Join audit | Offline reconciler | Source artifact IDs/hashes and `run_id` | Record all reconciliation/count/timestamp checks whether pass or fail |
| Joined derived | Offline reconciler | `(run_id, accepted_ordinal)` | Create only after successful audit; raw sources stay authoritative |
| Failure | Controller/validator/store | Failure-record ID, lifecycle state, related run/artifacts | Append actual evidence; never synthesize missing artifacts |
| Platform | Platform adapter/operator | requested-state ID and verified-evidence ID | Keep request and observation separate; unavailable stays unavailable |
| Access/sealing | Custody system | artifact/state/actor/time/authorization identity | Append chronology; never overwrite or backdate state |

Every physical artifact envelope declares artifact kind, protocol/schema version, physical-format version, algorithm-suite IDs, row and byte count, immutable ordering, integer time unit, endianness, compression/copy identity, producer identity, source lineage, URI/store identity, and SHA-256. Exact required fields remain governed by the imported schemas and semantic rules.

## Partial-failure publication matrix

| Highest completed point | Producer raw | Consumer raw | Join audit | Joined derived | Failure/lifecycle record |
|---|---:|---:|---:|---:|---:|
| Before worker release | No | No | No | No | Yes |
| Worker started but no valid raw buffer can be published | Only if actually recoverable | Only if actually recoverable | No | No | Yes |
| One private stream publishes | If available | If available | No | No | Yes |
| Both raw streams publish; reconciliation fails | Yes | Yes | Yes, failed | No | Yes |
| Reconciliation succeeds; later gate fails | Yes | Yes | Yes, passed | Yes | Yes, with separate correctness/measurement/gate status |
| Full success | Yes | Yes | Yes, passed | Yes | Lifecycle success record |

`FULL` is a valid reconciled outcome and remains in data; it separately fails the zero-loss gate. Genuine low `N_eff` remains retained. Neither condition authorizes repetition. An invalid original block remains in the lineage; only a new complete role-compatible block may replace it under the frozen budget/authority.

## Codec and storage boundary

The timed writer eventually needs a frozen-size representation, but Stage 2 accepts only the interface. A physical-format ADR before pilot must establish exact row/envelope bytes, endianness, alignment, time unit, codec version, lossless round trip, truncation/trailing-byte behavior, corruption detection, compression timing, durable/temporary copy count, buffer and filesystem capacity, and two independent decoders or equivalent cross-tool evidence.

Raw source objects are immutable once published. Canonical metadata uses the
tested `JCS-I64-v1` exact-integer profile and never depends on filesystem order,
locale, or implementation-defined serialization. Unknown versions or algorithm
identifiers fail closed.

## Access and analysis boundary

Offline analysis reads only immutable, passed artifacts through the access/sealing state machine. It cannot reach worker memory or control a running experiment. H3 validation data remain technically inaccessible until the imported state sequence authorizes access. Analysis output records every source artifact ID/hash and algorithm/version so results can be regenerated without modifying inputs.
