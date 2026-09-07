# ADR-0031: Stage 10 lifecycle projection and termination mapping

- Status: `ACCEPTED`
- Date: 2026-08-21
- Classification: Controller lifecycle / concurrency / failure evidence
- Decision owners: Repository owner; controller owner; queue-correctness owner; data owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None; completes the controller portion left open by ADR-0012 and ADR-0014
- Lifecycle gate: Stage 10 software; repeat integrated and stand evidence before pilot

## Context and scientific constraints

The imported protocol fixes eight stable run-manifest lifecycle values, a
controlled warm start, exact logical reset, one producer attempt per due
arrival, continuous consumer polling, release/acquire termination, drain to
empty, partial-failure retention, and no hidden rerun. It does not encode every
controller subphase or fix the C++ width/layout of the termination publication.
Adding manifest enum values would be an incompatible protocol change.

Warm-up duration, recovery duration, watchdog bounds, platform relax
instruction, physical observation storage, and selected stand facts remain
open at later gates and cannot become Stage 10 defaults.

## Options considered

1. Extend the imported lifecycle enum with every controller subphase.
2. Use only the eight imported values and leave controller progress implicit.
3. Keep an explicit internal phase graph and project each phase onto the exact
   imported enum.

For producer termination: a byte/bool atomic, an ABI pointer-width atomic, a
32-bit `0/1` atomic, mutex/condition-variable signaling, and a stronger
sequentially consistent atomic were considered.

## Decision

Select option 3. The internal graph is `PLANNED -> PREFLIGHT -> PREPARATION ->
WARMUP -> LOGICAL_RESET -> MEASUREMENT_STARTED -> PRODUCER_COMPLETE -> DRAIN ->
COMPLETED -> FINALIZED_VALID/INVALID`, with the exact phase-specific failure
edges recorded in [`docs/LIFECYCLE.md`](../LIFECYCLE.md). Every transition is
append-only and carries timestamp, actor, reason, and actual/absent artifact
consequences. Its projection never adds or renames an imported enum.

Use suite `ARRIVALS-FINISHED-U32-RELEASE-ACQUIRE-v1`: an explicitly aligned
dedicated cache-line allocation containing a C++ `atomic<uint32_t>` whose only
values are zero and one. Preparation resets zero with relaxed order only after
both workers are quiescent. Producer completion stores one with release order;
consumer termination/drain checks load with acquire order. Compile-time and
runtime lock-free checks are mandatory. The claim covers this word only.

The controller is a compile-time generic seam over clock, capture/storage
backend, and relax operation. Schedules and storage are complete before worker
release. Every poll/watchdog bound is explicit; expiration records failure and
partial evidence, never a retry. `FULL` and low `N_eff` are non-failure facts.

## Evidence

- Imported implementation specification Sections 2, 5.1--5.5, 8, 10.8,
  11.1--11.2, the data dictionary, run-manifest/failure schemas, and lifecycle
  rules.
- ADR-0001, ADR-0005, ADR-0012, ADR-0014, ADR-0017, ADR-0024, ADR-0027,
  ADR-0029, and ADR-0030.
- The user's Stage 10 instruction explicitly requires the detailed phases,
  release/acquire termination, exact one-attempt behavior, drain/watchdog,
  partial artifacts, no retry, and fake-backed tests.
- Stage 10 state-graph, reset, publication, race, failure, and deterministic
  concurrency tests plus applicable sanitizer evidence recorded in `STATUS.md`.

## Consequences and compatibility

Scientific effect: none beyond implementing fixed prospective behavior. The
controller cannot convert `FULL` or low `N_eff` into failure/retry and cannot
resume a failed run identity. Warm-up and measurement identities remain
separate and outcomes cannot change their schedules.

Compatibility effect: the internal transition record, projection rule, reset
evidence contract, and termination suite ID are versioned implementation
contracts. A different width/value encoding, memory order, cache-line sharing,
transition projection, retry policy, or failure attribution is incompatible.
Queue memory orders and claim boundaries are unchanged.

## Verification and acceptance tests

Enumerate all legal/illegal state pairs; inject failure at each phase; require
explicit early absence and partial-runtime evidence; test monotonic transition
metadata; verify warm-up/measurement separation and deterministic reset for
both queue shapes; exercise start races, release/acquire publication, empty and
backlogged drain, exactly-one-attempt `FULL`, cancellation/watchdogs, producer
and drain failures, and varied deterministic schedules under ASan/UBSan and
TSan where supported.

Final package/storage specializations must later pass ADR-0016 generated-code
rules. Fake backends, development-host scheduling, and static atomic evidence
do not qualify the stand or measured release.

## Rollback or supersession

Any incompatible transition, publication, reset, or failure-policy change
requires a superseding ADR, new suite/rule identity, full lifecycle,
sanitizer/concurrency/generated-code requalification, and prospective use only.
Existing transition/artifact evidence remains immutable. A failed runtime
records partial evidence and ends that run identity; rollback never means
continuation or deletion.

## Protocol-amendment assessment

No amendment is expected because the mapping preserves the exact imported
lifecycle values and implements explicitly required release/acquire behavior.
Any proposal to add/rename stable states, retry `FULL`, repeat low `N_eff`,
change warm-start semantics, or weaken complete-block replacement requires a
versioned protocol amendment, not this ADR.
