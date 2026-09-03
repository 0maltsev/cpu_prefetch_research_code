# 0150. Stage 17 S17-EXT-004 selected-pair-clock real invocation

Status: PROPOSED (design)

## Context

S17-EXT-004's `SELECTED_PAIR_CLOCK` qualification-evidence kind requires
(`config/schemas/qualification-evidence-v1.schema.json`'s `clock_
details`) real per-core and cross-core clock-pairing measurements:
`producer_prime_read_count`, `consumer_prime_read_count`, `producer_
delta_count`, `consumer_delta_count`, `traced_call_count`, `traced_
syscall_count`, `producer_to_consumer_window_count`, `consumer_to_
producer_window_count`, `exchanges_per_window`, `per_core_evaluator_
passed`, `cross_core_evaluator_passed`, `before_block_repeat`.

This is the deepest gap of the five kinds, and unlike ADR-0147/0148/0152
it is not merely unwired -- it is a real, previously-untouched
measurement-engineering project. It is a *named, tracked* project-level
blocker, not something incidental to S17-EXT-004: `docs/Q15_
QUALIFICATION_CONTRACT.md`'s collector matrix lists `Q15-CLOCK-COLLECTOR-
v1` under Q15-R with boundary "Accepted clock qualification evaluators
and frozen repetition counts; raw evidence retained; no correction," and
`docs/STAGE17_PILOT_AUTHORIZATION_DECISION_BUNDLE.md`'s readiness table
carries "Pair/clock qualification plan ... Timing/platform owners ...
`BLOCKED`: software evaluator only" as its own row, independent of this
ADR's existence.

Three layers of evaluator-only code exist, confirmed by direct reading,
none of which measures anything:

- `make_selected_pair_clock_evidence` (`src/runner/qualification.cpp`)
  only validates a supplied `SelectedPairClockInput` against frozen
  constants.
- `timing::evaluate_per_core_qualification`/`evaluate_cross_core_pair`
  (`src/timing/qualification.cpp`) evaluate already-collected timestamp
  arrays; they read no clock and touch no thread.
- `qualification::collect_q15_clock` (`src/qualification/q15_collectors.
  cpp`, a real static library `cpu_prefetch_q15_qualification`, actually
  linked into a real binary `cpu_prefetch_q15_tool` -- a layer this ADR
  had not previously found) still only wraps the two evaluators above
  around a caller-supplied `Q15ClockRawObservation`; `cpu_prefetch_q15_
  tool`'s own real command dispatch never calls it, only `--self-test`'s
  registry-size check does.

The frozen constants (`include/cpu_prefetch/timing/qualification.hpp`):
`kQualificationPrimeReadCount = 100,000`, `kQualificationDeltaCount =
10,000,000` (both per core), `kCrossCoreExchangeCountPerWindow =
100,000`, `kCrossCoreWindowCount = 3`, `kMinimumCrossCoreWindowStartSpan
Nanoseconds = 60,000,000,000` (60s). `CrossCoreExchangeSample{request_
send, request_receive, response_send, response_receive}` is a Cristian's-
algorithm-shaped round-trip: two threads on two different CPUs exchange
timestamped messages to bound their clocks' relative offset.

Two already-accepted, already-implemented real primitives exist to build
on, avoiding new low-level plumbing:

- `timing::read_monotonic_raw_absolute()` (`include/cpu_prefetch/timing/
  clock.hpp`) is the ADR-0030-accepted real `clock_gettime(CLOCK_
  MONOTONIC_RAW)` reader (`kClockSuiteId = "LINUX-CLOCK-MONOTONIC-RAW-
  VDSO-PS-v1"`), already used throughout the real capture path
  (`timing/capture.cpp`). This directly supplies per-core prime/delta
  sampling: pin via the same `bind_current_thread`/`singleton_affinity_
  matches` primitives Q15-R already uses, then call this in a tight loop.
- `queue::RingSpscQueue` was considered for the cross-core exchange and
  rejected: it operates on `workload::EventArena`/`EventPointer`
  workload-record abstractions built for the SPSC benchmark path, not a
  minimal timestamp exchange, and pulling it in would mean constructing
  unrelated workload machinery (`MasterSeed`, record sequences) purely as
  scaffolding for a 16-byte round trip.

Note also found during this ADR's own investigation, worth recording for
whoever eventually revisits ADR-0149: `Q15_QUALIFICATION_CONTRACT.md`'s
own `Q15-ADDRESS-RESIDENCY-COLLECTOR-v1` boundary is a single-region
whole-buffer check ("`move_pages` covers every page ... equal nonzero
page counts, zero unavailable/wrong-node/migrated pages"), matching
Q15-R's real code -- while `STAGE17_PILOT_AUTHORIZATION_DECISION_BUNDLE.
md`'s residency row uses producer/consumer-shaped language. The two
authoritative docs disagree with each other, not just with ADR-0149's
retracted claim; this reinforces that ADR-0149's open question is real,
not something this session should resolve unilaterally in either
direction.

## Decision (design, not yet implemented)

**(a) Once per selected pair, not per Q15-R session.** The clock
relationship between two specific CPUs is a hardware/platform fact of
that CPU pair on that stand, not something that changes with a
particular Q15-R session's own H0/H1 measurement -- the same reasoning
`docs/PLATFORM_CONTROL.md` uses ("full Stage 8 clock qualification on
both selected pairs"). The resulting evidence artifact should be
produced once per pair (`XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1`'s NEAR
and FAR pairs, each separately) and referenced by session lineage the
same way `PLATFORM_MANIFEST` (ADR-0151) is, rather than re-measured for
every Q15-R session.

**(b) Real backend, proposed design:**

1. A new, minimal, purpose-built cross-core exchange primitive: two
   cache-line-separated `std::atomic<uint64_t>` sequence/timestamp slot
   pairs per direction (one pair for producer-to-consumer, one for
   consumer-to-producer), following the same atomic-width/alignment/
   separation discipline already codified by `queue::common.hpp`'s
   `AtomicLockFreeEvidence`/`LayoutEvidence`. This is new code, and (like
   the D-047 mapping) needs its own dual-disassembler codegen-audit
   discipline before being trusted for real, timed measurement -- it
   should get a `RUNTIME_ATOMIC_LAYOUT`-style layout/lock-free evidence
   check of its own before first real use, not just before qualification
   evidence is built from its output.
2. A new dedicated CLI tool (mirroring `cpu_prefetch_q15_tool`'s
   pattern, not integrated into Q15-R's own worker) that:
   - Accepts a pair selector (`NEAR`/`FAR`) and CPU pin arguments.
   - Spawns two threads, pins each via the existing `bind_current_
     thread`/`singleton_affinity_matches` primitives.
   - Per-core phase: each thread independently runs `kQualification
     PrimeReadCount` prime reads then `kQualificationDeltaCount` delta
     reads of `timing::read_monotonic_raw_absolute()`, filling one
     `PerCoreQualificationInput` each.
   - Cross-core phase: `kCrossCoreWindowCount` windows, each starting no
     sooner than `kMinimumCrossCoreWindowStartSpanNanoseconds` after the
     previous window's start; within each window, `kCrossCoreExchangeCo
     untPerWindow` round trips per direction using the atomic ping-pong
     pairs from (1), each round trip recording all four `CrossCoreExcha
     ngeSample` timestamps via the same accepted clock reader.
   - Feeds the collected data into the already-accepted `timing::
     evaluate_per_core_qualification`/`evaluate_cross_core_pair`/
     `evaluate_static_clock_evidence` and `runner::make_selected_pair_
     clock_evidence` (or `qualification::collect_q15_clock`), unchanged.
   - Publishes raw results as a sibling artifact, the same pattern as
     ADR-0147/0148/0152, for later authoring into the final envelope.

Real cost: at minimum `kCrossCoreWindowCount *
kMinimumCrossCoreWindowStartSpanNanoseconds` = 180 real, uninterruptible
seconds per pair for the cross-core windows alone, plus per-core sampling
(low hundreds of milliseconds to a few seconds at accepted `clock_
gettime` call latencies for 10.1M calls per core) -- three real minutes
per pair, twice if both NEAR and FAR pairs are qualified.

This ADR still does not implement the above. It records a concrete,
investigated design so a future implementation session (or a follow-up
in this one) does not need to re-derive it, consistent with how ADR-0147
first recorded its own finding before a later pass implemented it.

## Consequences

- This remains real, separate scientific/engineering work, now with a
  concrete design rather than an open question -- still not a quick
  follow-up to ADR-0147/0148/0152.
- Introduces one genuinely new low-level primitive (the atomic ping-pong
  exchange pair) that needs its own codegen/atomic-safety verification
  before being trusted, mirroring the discipline already applied to the
  D-047 mapping and the SPSC queue's own atomics.
- Requires new real-stand time distinct from and larger than a normal
  Q15-R session (minutes, not the seconds a Q15-R H0 baseline takes) --
  should be scheduled and confirmed explicitly, not run opportunistically
  alongside another action.
- Blocks S17-EXT-004 admission independent of whether ADR-0147/0148/0149
  are completed -- all five `QUALIFICATION_EVIDENCE` kinds are required,
  so S17-EXT-004 cannot be built until this is resolved too.
- Surfaced, incidentally, a genuine internal disagreement between two of
  the project's own authoritative documents about `ADDRESS_RESIDENCY`'s
  intended shape (recorded above for whoever revisits ADR-0149).
