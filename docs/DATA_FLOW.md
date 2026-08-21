# Data Flow and Artifact Lifecycle

Protocol version: **`2.0.0-pre.2`**; immutable predecessor `2.0.0-pre.1` is
retained. This document preserves the imported logical model. Q9/ADR-0032/0033
select the physical raw encoding/copy policy, and Q10/Q11/ADR-0034 select only
the versioned blocker representation. Stage 12 implements reconciliation and
joined-row construction offline.

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
| Calibration capture | Prospective calibration plan, matching prepared context, preallocated trace | Continuous-ready service transfer; separate open-loop FULL probe; ring-off acquire-demand capture | Independent raw calibration run artifacts and explicit failure evidence | Only the frozen calibration interval; no statistics, serialization, I/O, or growth |
| Calibration evaluation/freeze | Immutable raw calibration references, exact planned exposures, method/profile IDs | Exact service minima and loads; ring-tail merge/distance; offline run-cluster matrix bound; source/fingerprint validation | Append-only plan, service, ring, feasibility, and freeze records, including `NOT_EVALUATED`/`INELIGIBLE` | No |
| Block planning/orchestration | Prospective precision evidence, explicit platform/build, role namespaces, pre-derived keys/seed catalogs, authorities, and budget | Prove the exact product/pool, generate deterministic whole/cell orders, validate sealing and replacement lineage | Imported block plans, access/freeze/amendment records, or explicit unresolved blockers | No |
| Analysis/sealing | Eligible immutable artifacts, exact Stage 12/14 proofs, explicit prospective configuration, authorized access state | Exact run summaries/diagnostics; complete blocks; H3 training/freeze/unseal/validation; separate H1/H2 max-T | Canonical synthetic or later authorized derived reports, selection records, source/config/output hashes | No and custody-controlled |

## Preparation-to-worker boundary

The controller resolves every dynamic choice before release. The prepared image contains exact addresses and extents, pre-generated deadlines, package specialization, run and algorithm-suite IDs, clock identity, platform evidence references, and fixed buffer capacity. Allocation, schema/config parsing, seed derivation, RNG, permutation, compression, and analysis are absent from the worker call graph.

Stage 4 supplies the pre-worker typed boundary but does not build a prepared
image. Each input first passes its unmodified imported Draft 2020-12 schema,
then immutable typed loading, then record-local semantic rules. Stable errors
carry category/path/rule identity and never repair input. Run-level
cross-record resolution is implemented in Phase 12. Stage 14 adds the block,
replacement, and access graph validator; final acceptance still requires
concrete pilot/freeze evidence and technically enforced custody. See
[`PROTOCOL_MODEL.md`](PROTOCOL_MODEL.md) and
[`ORCHESTRATION.md`](ORCHESTRATION.md).

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

Stage 12 invokes Stage 8's post-run derivation only after every producer/
consumer identity, ordinal, Stage 6 mapping, count, and k-th record-index check
passes. It then proves `end_to_end = admission + residence + delivery`.
Lateness, lookup, enqueue service, dequeue service, and consumer action are
nested diagnostics and are not added again. Failed audits retain classified
faults and publish no joined rows. See [`RECONCILIATION.md`](RECONCILIATION.md).

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

Stage 13 adds calibration-specific flows without connecting generation to
outcomes. A complete prospective plan names every service or ring run before
raw value access and binds owner, authority, and stand-budget evidence. Service
evidence is accepted only when all Stage A context
identities match and the workload is explicitly continuous-ready. The ring R0
path uses a preallocated observer around the existing acquire load; statistics
consume the immutable series later. A separate offline process consumes
open-loop feasibility counts, exact planned exposures, and the accepted
profile to emit a complete 180-cell candidate result. Plan, result, failure,
and freeze records are append-only, source-hashed, and material-fingerprint
bound. Result records retain each present run/probe validity decision and its
actual raw/integrity/failure sources; invalid or missing planned runs cannot be
hidden by a smaller estimator set. Missing stand inputs flow to
`NOT_EVALUATED`; cap collapse flows to
`INELIGIBLE`. Synthetic fixtures never flow into a platform freeze. See
[`CALIBRATION.md`](CALIBRATION.md).

Stage 14 adds only offline prospective orchestration. A role namespace
registry and per-block seed catalog enter the deterministic planner; outcomes
do not. The planner emits a complete imported block document whose 180 cells,
two whole plots, ordinal coverage, seed sharing, ID, and hash are independently
validated. Precision evidence enters a separate fixed-family/count evaluator;
training or validation outcomes are rejected as sizing inputs. Access records
then flow through an append-only predecessor-hash ledger. Replacement can emit
one new complete block only when an invalid required run, failure,
authorization, lineage, and budget all resolve. `FULL`, low effective tail,
or cap exhaustion emit no replacement. Concrete seed/count/authority/budget
inputs remain outside the repository until their prospective freeze gate.

Stage 15 consumes that graph in access order. It verifies immutable metadata,
versions, hashes, reconciliation/interval evidence, counts, and independent
gates before reading a run response. Exact inverse-ECDF summaries flow into
180-cell active complete blocks only; retained inactive originals remain
diagnostic lineage. Training blocks produce a source-hashed six-context
selection record before validation evaluation, and H1/H2 wait for release of
the full active pool. Complete-block Philox resampling produces separate
7/20 two-sided and 54 one-sided outputs. Machine reports retain every input,
configuration, software, stage, selection, and output identity. Synthetic RLE
fixtures and reports are permanently labeled and cannot flow into empirical
freeze or publication claims. See [`ANALYSIS.md`](ANALYSIS.md).

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

Offline analysis reads only immutable, passed artifacts through the
access/sealing state machine. Stage 14 validates record authority, chronology,
predecessor hashes, block role, and namespace, then returns a fail-closed access
decision; it has no artifact-opening capability. Storage/custody must enforce
that decision and prove negative access operationally. Analysis cannot reach
worker memory or control a running experiment. H3 validation data remain
technically inaccessible until the imported state sequence authorizes access.
Analysis output records every source artifact ID/hash and algorithm/version so
results can be regenerated without modifying inputs.
