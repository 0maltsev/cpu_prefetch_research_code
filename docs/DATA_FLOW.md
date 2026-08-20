# Data Flow and Artifact Lifecycle

Protocol version: **`2.0.0-pre.1`**. This document preserves the imported logical model; it does not select a physical raw encoding.

## End-to-end flow

| Phase | Inputs | Work | Append-only outputs | Timed? |
|---|---|---|---|---|
| Import/readiness | Immutable protocol snapshot and manifest | Hash, inventory, JSON parse, Draft 2020-12 meta-schema, positive/negative fixture, and canonical-byte checks | Readiness evidence in repository status | No |
| Experiment preparation | Protocol, accepted ADRs, platform inventory, block/run plan, algorithm suite, seeds | Imported-schema validation, immutable typed loading, deterministic stream derivation, complete offline schedule generation/validation, arena first touch, record/node permutation, footprint proof, and package binding | Validated logical records, schedule artifact/envelope/derivation record, and prepared workload inputs; later run-image identity and platform evidence references | No |
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

Stage 5 supplies the queue-operation seam beneath a future prepared image.
The producer can issue one direct nonblocking enqueue call and retain
`accepted` or `full`; the consumer can issue one direct nonblocking dequeue
poll and retain `item` or `empty`. Ring and linked/recycler adapters remain
distinct, so linked recycler exhaustion/ownership and ring slot reuse are not
normalized away. Stage 5 tests execute these operations with synthetic records
but create no run identity, clock, observation row, manifest, or measurement.

Stage 6 supplies the preparation-side workload image. HMAC-derived,
purpose-separated Philox streams initialize every payload and two independent
permutations before worker release. The event arena is base-page aligned,
fully first-touched, immutable through `const` access, and cyclically selected by
logical sequence. The linked arena consumes the complete `C+1` node order.
Content, ordered-index, and signed closure-delta SHA-256 inputs are derived from
logical bytes and within-arena offsets, never absolute pointers. The five
package policies bind exact hint targets without selecting a platform
instruction or calibrated `d2`.

Stage 7 implements ADR-0029 at the preparation boundary. The standalone Python
tool writes complete absolute-u64be deadline bytes plus imported-schema and
derivation envelopes before worker release. The C++ decoder verifies the
suite/runtime/reference bindings, exact byte/count/order/horizon rules, and all
four hashes before exposing an immutable deadline span. Generation has no
queue, completion, outcome, clock, or worker input. Explicit namespace roles
and common-family records are validated without parsing identifier text or
paths.

Q7/ADR-0030 fixes the Stage 8 clock seam as vDSO
`clock_gettime(CLOCK_MONOTONIC_RAW)` with exact nanosecond-to-picosecond
conversion, compiler-only read fences, bracketed publication/observation
boundaries, and uncorrected raw timestamps. Stage 8 now implements that seam:
each in-memory observation retains absolute nanoseconds and exact relative
picoseconds, and imported logical rows receive the relative fields without
selecting D-010's durable encoding. Static/per-core/bidirectional qualification
evaluators reject incomplete sample counts. Static stand inventory still
supplies neither an eligible worker pair nor dynamic clock evidence, and no
measurement path exists yet.

The producer and consumer receive disjoint mutable observation buffers. They record their own facts independently and in program order. `LogicalSequence` selects a cyclic record pointer before enqueue; `AcceptedOrdinal` is assigned only to accepted arrivals. The repeating `RecordIndex` validates the demanded record and is never an event ID. Accepted observations are reconciled later by run identity and accepted ordinal. A process-local pointer is never durable identity.

## Logical streams

| Stream | Principal producer | Identity/order | Required handling |
|---|---|---|---|
| Schedule | Offline generator, validated by controller | Schedule ID, seed/parent/child namespace, suite, exact rate/origin/horizon, immutable deadline order | Publish artifact/envelope/derivation together without overwrite; reject partial, mismatched, or outcome-derived schedules |
| Producer raw | Producer worker, published by controller | `run_id`, attempt order, accepted ordinal where applicable | Preserve every attempt/outcome, exact integer ticks, and original order |
| Consumer raw | Consumer worker, published by controller | `run_id`, dequeue/completion order and accepted ordinal | Preserve independent observations, record index/payload validation, exact ticks |
| Join audit | Offline reconciler | Source artifact IDs/hashes and `run_id` | Record all reconciliation/count/timestamp checks whether pass or fail |
| Joined derived | Offline reconciler | `(run_id, accepted_ordinal)` | Create only after successful audit; raw sources stay authoritative |
| Failure | Controller/validator/store | Failure-record ID, lifecycle state, related run/artifacts | Append actual evidence; never synthesize missing artifacts |
| Platform | Platform adapter/operator | requested-state ID and verified-evidence ID | Keep request and observation separate; unavailable stays unavailable |
| Access/sealing | Custody system | artifact/state/actor/time/authorization identity | Append chronology; never overwrite or backdate state |

Every physical artifact envelope declares artifact kind, protocol/schema version, physical-format version, algorithm-suite IDs, row and byte count, immutable ordering, integer time unit, endianness, compression/copy identity, producer identity, source lineage, URI/store identity, and SHA-256. Exact required fields remain governed by the imported schemas and semantic rules.

Stage 8's post-run derivation computes only from complete logical producer and
consumer rows. It validates the partial timestamp order and identity first,
then proves `end_to_end = admission + residence + delivery`. Lateness, lookup,
enqueue service, dequeue service, and consumer action are nested diagnostics;
they are not added again. Artifact lookup, stream reconciliation, join-audit
publication, and durable output remain Phase 12 responsibilities.

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
