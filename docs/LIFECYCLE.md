# Deterministic Run Lifecycle

Protocol version: **`2.0.0-pre.1`**. This is a non-measuring Stage 10 software
contract. Synthetic/fake execution is correctness evidence only.

## State model

The imported run-manifest enum remains exactly:
`PLANNED`, `PRE_RUN_FAILURE`, `WARMUP_FAILURE`, `RESET_FAILURE`,
`MEASUREMENT_STARTED`, `MEASUREMENT_FAILURE`, `DRAIN_FAILURE`, and `COMPLETED`.
Stage 10 does not add values to that stable protocol enum. The controller uses
the following more precise internal phases and projects them onto the imported
values:

| Internal phase | Imported lifecycle value | Allowed successor(s) |
|---|---|---|
| `PLANNED` | `PLANNED` | `PREFLIGHT` |
| `PREFLIGHT` | `PLANNED` | `PREPARATION`, `PRE_RUN_FAILURE` |
| `PREPARATION` | `PLANNED` | `WARMUP`, `PRE_RUN_FAILURE` |
| `WARMUP` | `PLANNED` | `LOGICAL_RESET`, `WARMUP_FAILURE` |
| `LOGICAL_RESET` | `PLANNED` | `MEASUREMENT_STARTED`, `RESET_FAILURE` |
| `MEASUREMENT_STARTED` | `MEASUREMENT_STARTED` | `PRODUCER_COMPLETE`, `MEASUREMENT_FAILURE` |
| `PRODUCER_COMPLETE` | `MEASUREMENT_STARTED` | `DRAIN`, `MEASUREMENT_FAILURE` |
| `DRAIN` | `MEASUREMENT_STARTED` | `COMPLETED`, `DRAIN_FAILURE` |
| `COMPLETED` | `COMPLETED` | `FINALIZED_VALID`, `FINALIZED_INVALID` |
| Each failure phase | Corresponding imported failure | `FINALIZED_INVALID` |
| `FINALIZED_VALID` / `FINALIZED_INVALID` | `COMPLETED` or retained failure | None |

`FINALIZED_INVALID` retains the exact preceding imported failure value. If a
completed execution later fails an integrity/validity gate, its imported
lifecycle remains `COMPLETED`; validity is a separate protocol field.

Every initial/transition record has a monotonic timestamp, actor, nonempty
reason, sequence, exact imported projection, and explicit artifact
consequences. Illegal, backward-time, incomplete, or duplicate-consequence
transitions fail without changing state. Early failures must declare producer,
consumer, count, and phase-integrity artifacts absent. Measurement/drain
failures may retain only rows actually produced. Completion carries candidate
producer, consumer, count, and phase-integrity evidence; Stage 11 publishes
their bytes and Stage 12 decides reconciliation/validity.

## Preparation, warm-up, and reset

Preparation evidence must prove that scientific configuration is frozen,
platform state was independently verified, queue and deterministic records are
initialized, both complete schedules are decoded, observation storage is
preallocated, termination was reset while workers were quiescent, and the
measurement origin is unset. Warm-up and measurement schedule/namespace IDs
are typed, explicit, and distinct. No path parsing or implicit identity exists.

Warm-up completion requires every planned warm arrival to have one attempt,
then warm arrivals stop, the queue drains, and both workers reach the reset
barrier. It rejects measurement rows, continuation of a prior measurement,
schedule regeneration, or allocation. Warm-up duration remains an explicit
pilot/freeze input; Stage 10 supplies no duration default.

`LogicalResetBackend` is a replaceable preparation-only interface. Its
independent verifier requires:

- stopped arrivals, a drained queue, both workers at the barrier, and zero
  occupancy;
- ring empty slots plus zero producer/consumer positions, or linked sentinel
  `pi0` plus recycler `pi1..piC`;
- zero logical sequence, accepted ordinal, all counts, and both sample
  positions;
- the explicit initial consumer checksum and an unset measurement origin;
- unchanged allocation, virtual mapping, data home, record permutation, and
  payload identities; and
- no allocation, schedule regeneration, memory remap, or payload retouch.

The interface and fake deterministic backends are covered in Stage 10. The
concrete ring/linked reset bindings must pass the same evidence contract in the
final integrated worker build; no scientific run is authorized by the fake
evidence.

## Start, producer, consumer, and drain

Both workers are created before measurement and arrive at a two-worker start
barrier. The controller waits with an explicit bound, captures exactly one
origin from the injected qualified clock, and release-publishes it. Each worker
acquire-observes release before reading the origin. A cancellation unblocks
both sides; a barrier or origin-read failure is pre-measurement evidence.

The producer consumes an already validated immutable deadline span. For each
deadline it computes `t0 + (deadline - schedule_origin)` with checked unsigned
arithmetic, polls only the injected clock/relax operation, and calls
`try_producer_attempt` exactly once. `FULL` increments `attempted` and `full`,
assigns no accepted ordinal, causes no retry, and is not a lifecycle failure.
Logical sequence advances once per completed logical arrival; accepted ordinal
advances only after `ACCEPTED`.

The consumer repeatedly calls `try_consumer_poll`. A successful poll increments
the candidate consumed ordinal only after the backend has completed and
retained the Stage 8 dequeue/action observation. Empty polls produce no row.
After the producer's final attempt it stores the 32-bit value `1` with
`memory_order_release` to a dedicated, explicitly sized cache line. The
consumer loads that word with `memory_order_acquire`; after observing it, the
consumer continues polling until empty. A failure racing publication performs
a second acquire so it is attributed to drain if publication already occurred.

The termination word is exactly `uint32_t` `0/1`, is reset with relaxed order
only while both workers are quiescent, and must be compile-time and runtime
lock-free. This is only the termination-publication claim; it does not broaden
the queue lock-free/wait-free claim boundary. Cache-line size is mandatory
input, never a platform default.

`Clock`, capture backend, relax operation, schedule, and safety bounds are
injected at compile time. The controller selects no sleep, yield, scheduler
call, adaptive backoff, queue family, treatment, platform instruction, or
watchdog value. Producer and consumer execution counters remain stack-local
during their loops and are transferred to controller-owned result slots only
when each worker exits; the hot loops do not update one shared report object.
Test fakes may yield solely to vary host scheduling. The final platform relax
instruction and watchdog/failure bounds remain explicit pre-pilot evidence.

## Failure and artifact matrix

| Failure point | Imported state | Artifacts that may exist | Forbidden behavior |
|---|---|---|---|
| Preflight/preparation | `PRE_RUN_FAILURE` | Plan, platform/preflight evidence, failure/journal | Fabricated measurement streams or hidden relaunch |
| Warm-up | `WARMUP_FAILURE` | Warm-up evidence and failure/journal | Measurement rows or continuation under same run ID |
| Logical reset | `RESET_FAILURE` | Reset/identity evidence and failure/journal | New allocation/remap/retouch or measurement start |
| Barrier/origin/producer/consumer before producer completion | `MEASUREMENT_FAILURE` after start, otherwise pre-run/reset phase as applicable | Actual partial producer/consumer rows, partial counts, failure/journal | Filling missing rows, retrying a logical arrival, resuming run |
| Post-publication drain/watchdog | `DRAIN_FAILURE` | Complete producer stream, actual partial consumer stream/counts, failure/journal | Treating backlog as consumed or fabricating an empty observation |
| Completed execution | `COMPLETED` | Candidate complete streams/counts/integrity | Declaring validity before Stage 12 reconciliation |

Watchdog/cancellation exits are failures with retained partial counts; they do
not restart a run. Recovery is recorded only after finalization with explicit
policy ID, positive duration, start/end timestamps, actor, reason, and evidence
artifact. Its value remains treatment-blind and externally frozen. The
controller has no automatic recovery default or run-retry API.

A correctly reconciled `FULL` and genuine low effective-tail count are explicit
non-failure annotations. Neither can change lifecycle, authorize replacement,
or trigger extension. Complete-block replacement remains a later separately
authorized protocol operation.

## Stage 10 evidence and remaining gates

`cpu_prefetch_lifecycle` contains the fail-closed state machine, preparation /
warm-up / reset validators, isolated termination word, start barrier, immutable
schedule check, and compile-time fake-backed producer/consumer executor. Unit
tests enumerate every state-pair, every failure phase, early/partial artifact
rules, deterministic ring/linked reset evidence, empty and `FULL` schedules,
partial producer failure, barrier and publication races, drain failures,
watchdogs, backlog drain, and 100 deterministic varied-scheduling histories.

The GCC release fake specialization was inspected after inlining the
termination accessors. Its producer/consumer bodies have direct atomic
termination operations, a concrete backend type with no backend vtable, and no
worker-body allocation, I/O, logging, or sleep call. The visible
`sched_yield` calls come only from the deliberately injected test relax type.
This limited audit proves the generic seam can specialize statically; it is not
the ADR-0016 acceptance audit for the future real package/storage/platform
specializations.

The executor performs no schema parsing, RNG, allocation, I/O, logging,
compression, reconciliation, or analysis after the measurement origin. Its
backend contract requires preallocated observation retention; the Stage 11
physical storage decision and implementation must provide and prove that
backend. Final package-specific code generation, production reset bindings,
platform relax mapping, explicit watchdog values, selected stand state, and
clock qualification remain pre-pilot/Phase 16 evidence. Development-host and
fake results are never latency or throughput evidence.
