# 0150. Stage 17 S17-EXT-004 selected-pair-clock real invocation

Status: ACCEPTED

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

Real cost, refined by the implementation below: each direction's own
window set spans `kMinimumCrossCoreWindowStartSpanNanoseconds` (60s)
start-to-start, and the two directions run sequentially on the same pair
of threads (producer-to-consumer, then consumer-to-producer) -- roughly
two real minutes per pair for the cross-core phase, plus per-core
sampling (low hundreds of milliseconds to a few seconds at accepted
`clock_gettime` call latencies for 10.1M calls per core), twice if both
NEAR and FAR pairs are qualified.

## Implementation

Built and verified locally (no real stand execution -- this machine is
not the accepted Xeon 06_55H stand, and its 12 logical CPUs don't even
include CPU 26, the FAR pair's second CPU):

- `timing::CrossCoreExchangeSlot`/`CrossCoreExchangeChannel`
  (`include/cpu_prefetch/timing/cross_core_exchange.hpp`, `src/timing/
  cross_core_exchange.cpp`): the atomic ping-pong primitive from (b.1)
  above, three cache-line-separated `std::atomic<uint64_t>` per slot
  (sequence, and a two-word payload so a responder can transmit both of
  its own timestamps back in one publish), bounded busy-spin with an
  injectable `max_spins` (production default 2 billion; tests pass a
  small bound to exercise the timeout path without waiting). Its own
  `atomic_lock_free_evidence()` mirrors `queue::RingSpscQueue`'s own
  pattern exactly, verified via a dedicated unit test rather than a
  dual-disassembler codegen probe/mutant pair: unlike the D-047 mapping,
  this primitive uses only standard `std::atomic` load/store/fetch_add,
  which the C++ standard already guarantees correct codegen for -- there
  is no "compiler silently substitutes the wrong instruction" risk a
  hand-written-asm mapping has, so a codegen-probe/mutant pair would
  duplicate a guarantee the language already provides. Verified clean
  under ThreadSanitizer and ASan/UBSan, plus 20 repeated runs with no
  flakiness.
- `qualification::run_clock_pair_qualification` (`include/cpu_prefetch/
  qualification/q15_clock_pair_qualification.hpp`, `src/qualification/
  q15_clock_pair_qualification.cpp`): the (b.2) orchestration -- spawns
  two real OS threads, each independently runs its own per-core prime/
  delta phase via `timing::read_monotonic_raw_absolute()` while pinned
  through the existing `bind_current_thread`/`singleton_affinity_
  matches` primitives, then the two threads run the cross-core phase
  (paced window starts, sequential producer-to-consumer then consumer-
  to-producer directions) and feed the results into the unmodified
  `timing::evaluate_per_core_qualification`/`evaluate_cross_core_pair`.
  Repeat scale is a parameter (`ClockPairQualificationCounts`), not
  hard-coded, specifically so the mechanism is testable at reduced scale
  without touching the real, frozen production constants (`kAccepted
  ClockPairQualificationCounts`). This function performs no CPU-family/
  model check itself, the same separation `platform::run_q15_probe_pass`
  already uses; a caller that wants the result trusted as real evidence
  must gate that itself.
- `tools/q15_clock_qualification_tool_main.cpp` (`cpu_prefetch_q15_
  clock_qualification_tool`): the gated real command surface --
  `--self-test` exercises only the exchange primitive with a synthetic
  clock (touches no hardware, matching every other q15 tool's
  `device=NOT_OPENED` self-test convention); `--qualify-pair near|far`
  requires family 06 model 55H before calling `run_clock_pair_
  qualification` with the real frozen constants. Verified: `--self-test`
  passes; `--qualify-pair` on this (non-accepted, non-06_55H) machine
  correctly fails closed at the family/model gate before touching any
  thread or clock, exactly as intended.
- `tests/q15_clock_pair_qualification_test.cpp`: a real (not
  synthetic-clock), reduced-scale (1,000 prime / 5,000 delta / 3 windows
  of 200 exchanges / 200ms window span, vs. the frozen 100,000/
  10,000,000/3/100,000/60s) end-to-end run of `run_clock_pair_
  qualification` on real CPUs 0 and 1, completing in ~400ms. Verifies
  the substantive, scale-independent correctness properties (zero call/
  timespec failures, zero causal regressions, affinity held throughout,
  a genuinely nonempty and tightly bracketed clock-offset interval per
  window) while correctly expecting the frozen-threshold booleans
  (`prime_count_passes`, `accepted_policy_sample_count`, `window_span_
  passes`, the aggregate `passes`) to read false at reduced scale, since
  those specific checks compare against the frozen global constants
  directly, not against the test's own smaller counts. Stable across ten
  repeated runs and clean under ThreadSanitizer.

Also fixed during implementation, caught by review before building: the
first draft of `run_direction_initiator` returned `CrossCoreWindowInput`
values whose `exchanges` spans pointed into a vector-of-vectors local to
that same function -- a dangling-span bug once the function returned.
Fixed by having it return an owning `DirectionCapture` struct instead,
with the caller building the transient `CrossCoreWindowInput` spans only
after the owning captures are safely held in its own, longer-lived
scope.

Verified: `cmake --build --preset dev-gcc` (full default target set)
succeeds, including the new `cpu_prefetch_q15_clock_qualification_tool`
and `cpu_prefetch_q15_clock_pair_qualification_tests` targets; all 6 new
tests (4 `TimingCrossCoreExchange`, 2 `Q15ClockPairQualification`) pass,
individually confirmed via `ctest --test-dir build/dev-gcc -R
"^TimingCrossCoreExchange|^Q15ClockPairQualification"`; clean under the
`tsan-gcc` and `asan-ubsan-gcc` presets for both new test binaries; no
regressions in the rest of the existing suite (`ctest --test-dir
build/dev-gcc`, 100% pass apart from two pre-existing, environment-
dependent failures confirmed unrelated to this work by reproducing them
identically with this session's changes stashed out: one needs
`/proc/1/ns/pid` read access this shell does not have, the other needs a
"classified dry-run bundle" state this build tree does not currently
have materialized).

Not yet done, and out of scope without a separate, explicit decision:
running `--qualify-pair` at the real frozen scale on the accepted stand
(the only environment that can produce real `SELECTED_PAIR_CLOCK`
evidence).

## Raw artifact, envelope wiring, and the static-clock VDSO tracer

Since the above: `--qualify-pair --output PATH` now writes a real,
partial raw artifact (schema `stage17-q15-clock-pair-raw-v1`) covering
everything the pair-qualification measurement itself produces --
deliberately excluding `traced_call_count`/`traced_syscall_count`/
`before_block_repeat`, which have no real source in that measurement.
`cpu_prefetch_q15_qualification_evidence_tool --kind SELECTED_PAIR_CLOCK`
wraps that raw artifact into the real `qualification-evidence-v1`
envelope, taking those three missing fields as required, never-defaulted
CLI flags instead (in C++, following the same "don't reimplement
eligibility logic in a second language" decision as the other four
kinds, not the Python pattern originally sketched here).

Those three fields are a *different* real gap from `SELECTED_PAIR_CLOCK`
itself: they belong to `StaticClockEvidenceInput`/
`evaluate_static_clock_evidence` (Stage 8's own static clock
qualification, `timing/qualification.hpp`), not to the per-core/cross-
core pair measurement this ADR implements. New
`cpu_prefetch_clock_vdso_probe_tool` wires the two of that static
input's checks that are real, in-process, and already implemented but
never production-wired (`probe_vdso_clock_gettime()`,
`monotonic_raw_resolution()`), and adds `--probe`: an isolated tracee
performing exactly the real accepted 10,000,000-call
`clock_gettime(CLOCK_MONOTONIC_RAW)` sequence and nothing else, matching
`docs/TIMING.md`'s own requirement that the zero-syscall proof be "an
external qualification input" -- proven by tracing this exact process
from outside (`strace -c -e trace=clock_gettime`), not by anything the
process claims about itself. Confirmed `strace`/`perf` are both present
on the accepted stand.

Not yet done: running that trace for real on the stand (needs this tool
in a release bundle staged there), and the other `StaticClockEvidenceInput`
fields this tool does not cover (`bare_metal_linux_x86_64`,
`current_clocksource_tsc`, `no_unstable_clock_report`, `constant_tsc`/
`nonstop_tsc`/`invariant_tsc`, `no_clocksource_override`,
`generated_code_passes`) -- all real, locally-observable facts, but a
separate piece of work from "the VDSO tracer" specifically.

## Consequences

- The mechanism is now real, implemented, and verified at reduced scale
  on real (non-accepted) hardware -- what remains is exclusively real
  stand time at full frozen scale, not further design or engineering
  risk.
- Introduces one genuinely new low-level primitive (the atomic ping-pong
  exchange pair), verified via unit tests plus ThreadSanitizer/ASan/
  UBSan rather than a dual-disassembler codegen pair, for the reasons
  recorded above.
- Requires new real-stand time distinct from and larger than a normal
  Q15-R session (roughly two real minutes per pair, not the seconds a
  Q15-R H0 baseline takes) -- should be scheduled and confirmed
  explicitly, not run opportunistically alongside another action.
- Blocks S17-EXT-004 admission independent of whether ADR-0147/0148/0149
  are completed -- all five `QUALIFICATION_EVIDENCE` kinds are required,
  so S17-EXT-004 cannot be built until this is resolved too. Still
  blocked: real `--qualify-pair` execution on the accepted stand, and
  the real static-clock VDSO trace (tool now exists; not yet run there).
- Surfaced, incidentally, a genuine internal disagreement between two of
  the project's own authoritative documents about `ADDRESS_RESIDENCY`'s
  intended shape (recorded above for whoever revisits ADR-0149).
