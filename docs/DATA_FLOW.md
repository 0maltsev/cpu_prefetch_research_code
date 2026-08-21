# Data Flow and Artifact Lifecycle

Protocol version: **`2.0.0-pre.1`**. This document preserves the imported
logical model. Q9/ADR-0032/0033 select the physical raw encoding and copy policy
without making them logical fields. Stage 11 implements those contracts while
leaving reconciliation and joined-row construction to Stage 12.

## End-to-end flow

| Phase | Inputs | Work | Append-only outputs | Timed? |
|---|---|---|---|---|
| Import/readiness | Immutable protocol snapshot and manifest | Hash, inventory, JSON parse, Draft 2020-12 meta-schema, positive/negative fixture, and canonical-byte checks | Readiness evidence in repository status | No |
| Experiment preparation | Protocol, accepted ADRs, platform inventory, block/run plan, algorithm suite, seeds | Imported-schema validation, immutable typed loading, deterministic stream derivation, complete offline schedule generation/validation, arena first touch, record/node permutation, footprint proof, and package binding | Validated logical records, schedule artifact/envelope/derivation record, and prepared workload inputs; later run-image identity and platform evidence references | No |
| Platform preparation | Requested state and authorized adapter/operator | Affinity/NUMA/page/frequency/HW-PF actuation, independent readback/probes, rollback readiness | Requested-state and verified-state records, capability/failure evidence | No |
| Run launch | Closed `PreparedRun` | Preparation evidence, warm-up, drain/barrier, logical reset, two-worker start, one clock-derived origin | Append-only lifecycle transition candidates and reset evidence | No; the fixed origin read is the boundary |
| Measurement horizon | Pre-generated deadlines, fixed arenas, specialized queue, qualified clock | Producer and consumer execute fixed data-plane work | Thread-private producer and consumer observations in preallocated buffers | Yes |
| Drain/finalize | Worker state and private buffers | Producer release publication, consumer acquire observation and drain-to-empty, count capture, checksum finalization | Final/partial worker counts, lifecycle and failure consequences; no artifact I/O yet | Drain queue polls are fixed data-plane work; artifact publication no |
| Raw publication | Sealed complete or partial private buffers plus lifecycle state | Hash, no-replace publish, sync, independent readback, second-domain replication, envelope/ledger emission | Immutable producer and/or consumer raw artifacts, raw envelopes, phase/integrity report, copy ledgers, partial-failure evidence | No |
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
having selected D-010 during Stage 8. Q9 has since accepted D-010/ADR-0032's
durable representation, which Stage 11 now implements. Static/per-core/
bidirectional qualification evaluators reject incomplete sample counts. Stage
11 now preserves both representations in every physical boundary pair. Static stand inventory still
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
| Platform | Read-only inventory, external platform operator, independent verifier | inventory snapshot, requested-state ID/epoch, apply audit, verified-evidence ID, restoration audit | Dry-run cannot actuate; apply is never verification; stale/missing mandatory readback fails closed; partial failure remains append-only |
| Access/sealing | Custody system | artifact/state/actor/time/authorization identity | Append chronology; never overwrite or backdate state |

Every raw artifact envelope declares artifact kind, protocol/schema version,
physical-format version, row and byte count, immutable ordering, integer time
unit, endianness, compression, run identity, source lineage where applicable,
external URI, integrity reference, and SHA-256. ADR-0033 copy policy, domain
IDs, readback results, timestamps, completeness, and locations are held in the
separate append-only copy ledger rather than extending the imported schema.

Stage 8's post-run derivation computes only from complete logical producer and
consumer rows. It validates the partial timestamp order and identity first,
then proves `end_to_end = admission + residence + delivery`. Lateness, lookup,
enqueue service, dequeue service, and consumer action are nested diagnostics;
they are not added again. Artifact lookup, cross-stream reconciliation,
join-audit publication, and conditional joined output remain Phase 12
responsibilities.

Stage 9 adds no data-plane edge. Before worker release, the controller consumes
one explicit inventory snapshot, detects capability without upgrading unknown
state, validates a typed Stage A placement/request, obtains independently read
pre-state, and either emits a dry-run plan or delegates whitelisted actions to
an approved external actuator. The verifier then reads every exact value
through a separately identified mechanism. A mismatch, stale epoch, partial
apply, or restoration failure flows to a platform failure and ineligible
manifest; requested values never flow into verified fields. The rich evidence
manifest retains provenance and partial failures, and an explicit projection
emits the unmodified imported platform logical record.

Stage 10 closes the controller concurrency edge without choosing storage or a
stand. Preparation proves all allocation and schedule decoding complete.
Warm-up and measurement use distinct typed schedule/namespace identities;
warm-up stops, drains, and reaches a two-worker reset barrier. Verified logical
reset preserves warm mappings/content while zeroing counters, ordinals, sample
positions, queue origin, checksum state, and the unset measurement origin.

After both workers arrive, the controller captures one origin and
release-publishes it. The producer maps every immutable deadline to that origin
with checked arithmetic, performs one backend attempt, and records `FULL`
without retry. It then release-publishes a dedicated u32 finished word. The
consumer acquire-observes it and continues polling through backlog to empty.
Failures append actual/absent consequences; no path resumes the run identity.
Stage 11 supplies a compile-time `CapturingObservationBackend` that joins the
Stage 8 capture seam to separate fixed producer/consumer streams and reports a
backend call complete only after a complete physical row commits. Buffer
allocation is controller-side, while the already-affined owner explicitly
initializes and first-touches every reserved byte before the barrier. Overflow
becomes a measurement failure. Platform page binding/residency and the final
package-specialized worker audit remain Phase 16 evidence.

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

Q9/ADR-0032 freezes `RAW-OBS-U64LE-LP-RUNID-v1` with exact literal-ID
prefixes, row bodies/sizes, little-endian words, raw/relative clock pairs, and
the JCS external envelope. ADR-0033 freezes `compression=NONE`, `m_tmp=1`, and
`m_dur=2` in distinct verified domains. Stage 11 implements the exact fixed
writers/decoder, C++/Python goldens, corruption rejection, first-touch API,
checked budget model, JCS phase/envelope/ledger documents, unique local
no-replace publication, streaming readback SHA-256, two-copy sequencing, and
exact-candidate recovery. See [`STORAGE.md`](STORAGE.md). Phase 16 must still
supply the concrete run plan, real failure domains, available capacity,
permissions/custody, page residency, and operational recovery evidence.

Raw source objects are immutable once published. Canonical metadata uses the
tested `JCS-I64-v1` exact-integer profile and never depends on filesystem order,
locale, or implementation-defined serialization. Unknown versions or algorithm
identifiers fail closed.

## Access and analysis boundary

Offline analysis reads only immutable, passed artifacts through the access/sealing state machine. It cannot reach worker memory or control a running experiment. H3 validation data remain technically inaccessible until the imported state sequence authorizes access. Analysis output records every source artifact ID/hash and algorithm/version so results can be regenerated without modifying inputs.
