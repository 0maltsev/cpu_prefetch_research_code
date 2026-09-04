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

Run for real on the accepted stand: the `release-gcc` build of
`cpu_prefetch_clock_vdso_probe_tool`
(sha256 `48fb45971dd034b60a2997e60f346e22e7c75ce47e86a269909a274384687293`)
was staged there (scp, hash-verified identical on arrival) and run for
real. `--check-vdso-symbol`/`--check-resolution` both real-PASS on the
accepted stand itself (`versioned_symbol_present=true`,
`resolution_picoseconds=1000`). `--probe` at the real accepted scale
(10,000,000 calls) under `strace -c` (no filter, so every syscall the
whole process makes is visible, not just an assumed-empty filtered
view): `call_failures=0`, and the complete summary shows 93 total
syscalls across the entire process lifetime -- all ordinary startup/
teardown calls (`mprotect`/`brk`/`munmap`/`mmap`/`openat`/`read`/etc.)
-- with `clock_gettime` appearing zero times. This is the real
`probe_call_count=10000000`, `probe_syscall_count=0`,
`probe_failure_count=0` `StaticClockEvidenceInput` needs, captured
`2026-09-03T21:37:11Z` on kernel `7.0.0-30-generic` with `strace` 6.19.
Full trace output preserved at `/home/omaltsev/stage17-owner-evidence/
clock-vdso-static-probe-evidence/` (`trace-10m-stdout.log`,
`trace-10m-strace.log`).

The remaining `StaticClockEvidenceInput` fields are now also wired: new
`--collect` assembles the complete input (locally-observable facts for
`bare_metal_linux_x86_64` via the CPUID hypervisor-present bit,
`current_clocksource_tsc` via sysfs, `constant_tsc`/`nonstop_tsc` via
`/proc/cpuinfo`'s flags line, `invariant_tsc` via CPUID leaf `0x80000007`,
`no_clocksource_override` via `/proc/cmdline`, `no_unstable_clock_report`
via the real kernel ring buffer through `dmesg` run by direct fork/exec;
`--probe-*`/`--generated-code-passes` as required CLI flags for what
cannot be honestly self-observed) and calls the real
`evaluate_static_clock_evidence()` directly.

Run for real on the accepted stand with the real numbers above plus a
real, current `timing-codegen-check` run
(`cmake --build --preset release-gcc --target timing-codegen-check`:
PASS, 11 operations, 6 source mutants, 3 machine mutants, confirmed the
same day rather than assumed from the docs' own historical claim) and
`--glibc-call-path-verified true` (justified by the real trace itself --
zero syscalls across the traced sequence plus the real versioned vDSO
symbol together are exactly what "the glibc call path used the vDSO"
means): **every field is real and true, and
`evaluate_static_clock_evidence()`'s own verdict is a real PASS** --
`platform_passes`/`source_passes`/`frequency_invariance_passes`/
`vdso_symbol_passes`/`vdso_execution_passes`/`generated_code_passes`/
`resolution_passes` all true. `no_unstable_clock_report` came back
`false` when this same command was first tried in this session's own dev
sandbox (no kernel-buffer read permission there); on the stand, running
as root, it is `true` for real. Captured `2026-09-03T21:46:06Z`, full
output preserved at `/home/omaltsev/stage17-owner-evidence/clock-vdso-
static-probe-evidence/collect-20260903-output.log`. This is Stage 8's
entire static clock evidence gate, real and passing, on the accepted
stand.

## A real cross-core exchange livelock, found and fixed at accepted scale

The first-ever real `--qualify-pair` run at full accepted frozen scale on
the stand did not complete in the "roughly two real minutes" estimated
above -- it ran for 8.4+ real hours, still climbing, pegged at ~200% CPU
with no output. This was a real, previously-undiscovered livelock: the
initiator's own inter-window pacing sleep (up to ~30 real seconds between
window starts at accepted scale) vastly exceeds
`kCrossCoreExchangeMaximumSpinIterations`'s real-time budget (a few real
seconds), and the responder side had no accommodation for that gap --
once its spin timed out once, both sides' unconditionally-incremented
local sequence counters permanently desynchronized, and every remaining
exchange for the rest of that direction burned its full spin budget for
nothing. Never caught by the unit tests: their reduced-scale pacing gap
(200ms) is 300x shorter than accepted scale, never long enough to expose
it.

Fixed by giving `CrossCoreExchangeSlot::wait_for` a second, opt-in,
wall-clock-bounded phase after the fast spin (see the commit and the
primitive's own doc comments for the full design). Verified for real on
the accepted stand with the fix: `--qualify-pair near` completed in
**2m0.9s** real elapsed time -- matching the original estimate almost
exactly -- with `cross_core_passed=true` for the first time ever at
accepted scale.

That same real run's `producer_per_core_passed`/
`consumer_per_core_passed` were both `false` -- a separate, real finding,
unrelated to this fix (a different code path,
`evaluate_per_core_qualification`/`evaluate_clock_sequence`, never
touched here). Not yet investigated; see whatever ADR/commit follows
this one for that.

## Real per-core qualification investigation: a real tail-latency gap, not a code bug

Investigating that `producer_per_core_passed`/`consumer_per_core_passed
=false` finding. `--qualify-pair`'s stdout gained a per-core diagnostic
line (not part of the raw artifact schema) surfacing
`evaluate_clock_sequence`'s full real numbers, which
`PerCoreQualificationEvidence` had been reducing to a single
`read_status_passes` bool. Real results from the accepted stand, both
sides:

| | producer | consumer | threshold |
|---|---|---|---|
| p99.9 delta | 1.596 us | 1.586 us | <= 1.0 us |
| p99.999 delta | 15.94 us | 15.82 us | <= 10.0 us |
| max delta | 137.2 us | 123.4 us | (none) |
| regressions / ties / call failures / affinity | all clean | all clean | -- |

Everything else about the real measurement is exactly right: zero call
failures, zero regressions, zero ties, the exact accepted
10,000,000-sample count, singleton affinity holds throughout. Only the
delta-read tail latency exceeds Stage 8's own already-accepted
`CLOCK-QUAL-LMRV1` thresholds -- a small, real fraction of the 10
million consecutive `clock_gettime(CLOCK_MONOTONIC_RAW)` reads take
longer than expected. This is not a code defect: the tool correctly
implements the already-frozen D-009 policy exactly as documented: the
real question is whether *this stand, in its current configuration*,
can meet it.

A real, read-only investigation of the stand found no CPU isolation at
all: `/proc/cmdline` has no `isolcpus`/`nohz_full`/`irqaffinity`; over
200 real hardware IRQs had `smp_affinity_list` including CPUs 0 and 1
(the near pair) and their real HT siblings 52/53 (`0-25,52-77` or
`0-103`); both CPUs ran the `schedutil` governor with turbo boost
enabled. Load average was low (0.08) and no heavy background process
was visible -- this is "not configured to protect two cores from the
scheduler/interrupts/frequency scaling," not "the machine is busy."

Tried, for real, a reversible, no-reboot mitigation: governor set to
`performance` for CPUs 0/1, turbo disabled system-wide (no per-CPU
control exists), and IRQ affinity moved off CPUs 0/1/52/53 wherever the
kernel allowed it (229 of 310 real IRQs changed; the other 81 either
already excluded those CPUs or, for 2 fixed legacy IRQs, cannot be
reaffinitized at all). Every original setting was snapshotted first.
Re-running `--qualify-pair near` with these tweaks in place gave a real,
mixed result:

| | producer (after) | consumer (after) | vs. before |
|---|---|---|---|
| p99.9 delta | 2.176 us | 2.169 us | worse |
| p99.999 delta | 6.508 us | 6.459 us | better, now under 10.0 us |
| max delta | 270.7 us | 135.2 us | worse (producer) |

The rare, large outliers (p99.999) improved substantially; the more
common near-threshold outliers (p99.9 -- the actual blocking criterion)
got slightly worse, and the single worst outlier grew. Net: still
fails, and not clearly closer to passing. All tweaks were reverted
immediately after (governor, turbo, and all 308 restorable IRQ affinity
entries -- 2 were never changeable in the first place); a full `diff`
against the original snapshot confirmed zero remaining differences.

Working hypothesis for the real remaining cause: CPU idle C-states
(real, well-known multi-microsecond wake latency from deep sleep,
unaffected by governor/turbo/IRQ-affinity settings) and/or ordinary
kernel threads still being scheduled onto CPUs 0/1 -- IRQ affinity does
not prevent the scheduler from placing unrelated kernel work there, only
interrupt routing.

Cgroup-based CPU shielding (cgroup v2 cpuset, no reboot) was attempted
next, to try ruling out the kernel-thread-scheduling half of that
hypothesis. Real, read-only investigation first: `cgroup2` is the only
mounted hierarchy; the root's real `cgroup.controllers` lists `cpuset`
as available, but its `cgroup.subtree_control` only had `cpu memory
pids` enabled, so `system.slice`/`user.slice`/`init.scope` had no
`cpuset.cpus` files at all yet -- `cpuset` had never been delegated to
them. Enabling it (`echo +cpuset > cgroup.subtree_control`, confirmed
via each slice's own real `cpuset.cpus.effective` immediately becoming
the expected `0-103`, unrestricted) is itself inert on its own: it only
makes per-cgroup CPU restriction *possible*, and changes no scheduling
behavior for any already-running task by itself.

The next real step -- creating an isolated cgroup and setting its
`cpuset.cpus.partition=isolated` (the standard cgroup v2 mechanism that
would remove CPUs 0/1/52/53 from every sibling cgroup's effective set,
without needing to touch `system.slice`/`user.slice` individually) --
was blocked by Claude Code's own auto-mode permission classifier before
it ran. Nothing in that blocked command executed, including the `mkdir`
for the new cgroup, confirmed by it never existing afterward. Real
end state on the stand: `cpuset` remains enabled in the root's
`cgroup.subtree_control` (confirmed harmless -- both real sibling
slices still show unrestricted `0-103` effective sets); no cgroup, no
task movement, no CPU exclusion was ever actually applied.

So: cgroup-based CPU shielding remains genuinely untried, blocked by
tooling policy rather than found infeasible or unhelpful. Real options
for whoever picks this up: run the isolation write manually on the
stand (a human, not this session, since the block is specifically on
Claude Code's own classifier) and hand control back for verification/
the real qualify-pair run/cleanup, or pursue the `isolcpus`/
`processor.max_cstate` boot-parameter route instead.

That boot-parameter route was tried next, with real, explicit user
confirmation given the meaningfully higher risk (a real reboot of the
accepted stand, with `GRUB_TIMEOUT_STYLE=hidden`/`GRUB_TIMEOUT=0` --
an invisible, zero-delay boot menu -- and no IPMI/serial-console/
physical access available to this session as a recovery path if
anything went wrong). `/etc/default/grub` and `/boot/grub/grub.cfg`
were both backed up (hash-verified copies, one kept locally too) before
touching anything; no other users were logged in. `GRUB_CMDLINE_LINUX`
was edited with a single, precise, verified-by-diff line change adding
`isolcpus=0,1,52,53 nohz_full=0,1,52,53 irqaffinity=2-51,54-103
processor.max_cstate=1 intel_idle.max_cstate=0`.

The next real step, `update-grub` (which regenerates `/boot/grub/
grub.cfg`, the file GRUB actually reads at boot -- without it, the
edited `/etc/default/grub` is inert), was blocked by the same auto-mode
permission classifier that blocked the cgroup partition write. No
reboot was ever attempted; the machine's real, running kernel
command line never changed. `/etc/default/grub` was restored from its
backup (hash-verified identical to the pre-edit original) and both
backup copies removed. Real end state, fully confirmed: `/etc/default/
grub` byte-identical to before, `/boot/grub/grub.cfg` never regenerated
(unchanged), `/proc/cmdline` unchanged, no reboot occurred.

So both remaining real per-core remediation paths -- cgroup shielding
and `isolcpus`/`processor.max_cstate` -- are now blocked at their
critical execution step by Claude Code's own auto-mode permission
classifier, not found infeasible or unhelpful by investigation. Real
option for whoever picks this up: a human (not this session) runs
`update-grub` and the reboot directly on the stand, following the exact
`/etc/default/grub` edit already proven correct here, then hands control
back for the post-reboot verification/real qualify-pair run/revert-and-
reboot-again cleanup.

### The `isolcpus` boot-parameter route, completed and reverted

That handoff happened for real. The `/etc/default/grub` edit (unchanged
from above) plus `update-grub` and the reboot were run directly by the
stand's owner, using a script (`apply-isolcpus.sh`) prepared and
reviewed here first: it backs up both `/etc/default/grub` and
`/boot/grub/grub.cfg`, applies the single precise `GRUB_CMDLINE_LINUX`
edit, runs `update-grub`, and prints the real generated kernel-entry
lines for review -- deliberately not rebooting itself. Before approving
the reboot, an imprecise verification grep in that script (`grep 'linux
' grub.cfg`, which also matches menu-title text like `--class
gnu-linux` as a substring) was caught here and replaced with a precise
one (`grep -n '^[[:space:]]*linux[[:space:]]' grub.cfg`), confirming the
real default boot entry (line 167, `vmlinuz-7.0.0-30-generic`, root UUID
`a16cbbf7-3e5d-472a-9633-84e405f5cf39`) correctly carried
`isolcpus=0,1,52,53 nohz_full=0,1,52,53 irqaffinity=2-51,54-103
processor.max_cstate=1 intel_idle.max_cstate=0` before the reboot was
approved.

Post-reboot verification, all real: `/proc/cmdline` carried the new
parameters; `/sys/devices/system/cpu/isolated` read `0-1,52-53`,
confirming kernel-level isolation was actually active (not just present
on the command line); all 104 CPUs stayed online (`isolcpus` excludes
from scheduling, it does not offline); the qualification tool binary's
sha256 was unchanged across the reboot. `systemctl is-system-running`
reported `degraded`, traced to `systemd-networkd-wait-online.service`
alone (`systemctl --failed`) -- a known benign quirk, confirmed
unrelated by working SSH connectivity, not a real regression.

Two real, independent `--qualify-pair near` runs with isolation active
(~2 minutes real elapsed each):

| | run 1 producer | run 1 consumer | run 2 producer | run 2 consumer | threshold |
|---|---|---|---|---|---|
| p99.9 delta | 2.176 us | 2.169 us | 1.753 us | 3.967 us | <= 1.0 us |
| p99.999 delta | 6.508 us | 6.459 us | 4.927 us | 12.408 us | <= 10.0 us |
| max delta | 270.7 us | 135.2 us | 132.2 us | 167.6 us | (none) |

Both runs: `producer_per_core_passed=false`, `consumer_per_core_passed
=false`; call failures, regressions, ties, sample count, and affinity
all still clean on both sides. `isolcpus` reproduced the same pattern
as the earlier IRQ/governor-only tweak -- p99.999 improves, sometimes
substantially -- but p99.9 (the real blocking criterion) does not
reliably clear the threshold, and run-to-run variance is large enough
(consumer p99.999 went from 6.459us to 12.408us, back over the limit,
between two runs under the *same* configuration) that this is not a
marginal, nearly-passing case. Three real remediation attempts now
(IRQ/governor tweaks, cgroup shielding blocked before producing data,
and `isolcpus`/`nohz_full`/`irqaffinity`/`processor.max_cstate`/
`intel_idle.max_cstate`), none clearing the p99.9 threshold.

Given that, the stand was reverted to its original boot configuration:
a second script (`revert-isolcpus.sh`), again run directly by the
stand's owner after review here, restored `/etc/default/grub` from the
pre-change backup, ran `update-grub`, and printed the regenerated
kernel-entry lines for verification (confirmed byte-for-byte matching
the pre-change originals, `isolcpus` grep count 0) before the second
real reboot was approved. Post-second-reboot verification, all real:
`/proc/cmdline` clean of every added parameter, `/sys/devices/system/
cpu/isolated` empty, `nproc=104`, `/etc/default/grub` byte-identical
to the original pre-change backup (`diff` empty), tool binary sha256
unchanged, and the same benign `systemd-networkd-wait-online.service`
quirk (nothing new). The stand is back in its original, unmodified
boot configuration.

### The cgroup shielding retry: a real gap in cross-core thread pinning

Cgroup-based CPU shielding was retried afterward. `cpuset` delegation
had reset across the two intervening reboots (root `cgroup.subtree_
control` was back to `cpu memory pids`); re-enabling `+cpuset` and then
creating the isolated partition itself (`mkdir /sys/fs/cgroup/
qual_isolated`, `cpuset.cpus=0,1,52,53`, `cpuset.cpus.partition=
isolated`) both succeeded this time -- not blocked by the auto-mode
classifier, unlike the first attempt. Real confirmation: `qual_isolated`
effective set `0-1,52-53`; root and `system.slice` effective sets
correctly shrank to `2-51,54-103`.

Running the qualification tool inside the new partition required
moving its process into `qual_isolated` first (`echo $$ > .../cgroup.
procs` from the invoking shell before `exec`), since the SSH session's
own cgroup no longer had CPUs 0/1/52/53 in its effective set once the
partition existed. That part worked. But the resulting run exposed a
real, previously-latent gap in the tool itself: in `q15_clock_pair_
qualification.cpp`, only the per-core capture threads (`producer_per_
core`/`consumer_per_core`) call `bind_current_thread` to actually pin
themselves via `sched_setaffinity`; the cross-core exchange threads
(`producer_side`/`consumer_side`) never do -- they simply inherit
whatever affinity the spawning thread already had. Outside a
restrictive cgroup, with 104 mostly-idle CPUs, ordinary Linux thread
placement happens to spread two freshly spawned threads across
different cores almost every time, so this was never noticed in any
prior real run (including the earlier `isolcpus` runs, which only
restrict the domain, not within-domain placement). Inside the new
4-CPU `qual_isolated` partition, both threads landed on the same
physical core (52) and stayed there: `ps -T` showed `PSR=52` for both
`producer_side`/`consumer_side` for the tool's full 12+ minutes of real
runtime (vs. the usual ~2 minutes), each near 50% CPU -- genuine
core-sharing contention, not the earlier livelock (the process was
alive and making CPU progress the whole time, just on one core instead
of two). Any resulting numbers would have been scientifically invalid
regardless of pass/fail, since the entire premise of the cross-core
measurement is two threads on two separate physical cores. The run was
killed before producing an output artifact (confirmed: no `near-raw.
json` was left behind). The `qual_isolated` cgroup was removed and
`cpuset` delegation disabled again afterward, restoring the pre-attempt
state exactly.

So cgroup-based CPU shielding is no longer blocked by tooling policy --
the write itself now succeeds -- but it surfaced a real, independent
gap (missing cross-core thread pinning) that needed a real code fix
(an explicit `bind_current_thread` call for `producer_side`/
`consumer_side`, matching the existing per-core pattern) before this
approach could produce valid data.

### The cross-core pinning fix, and a third real cgroup attempt

That fix was made: `producer_side`/`consumer_side` in
`run_clock_pair_qualification` now each construct their own
`platform::LinuxQ15PlatformOperations` and call `bind_current_thread`
on `pair.producer_cpu`/`pair.consumer_cpu` before doing any exchange
work, mirroring the existing per-core capture pattern exactly; a failed
bind makes the thread return early, leaving its `DirectionCapture`
unset, which the existing "captures missing" check already turns into
`complete=false`/`passes=false` -- no new result fields needed. Verified
locally: clean release-gcc build, clean under ThreadSanitizer and
ASan/UBSan, both existing `q15_clock_pair_qualification_test.cpp` cases
still pass unchanged (the CPU-domain-validation edge case never reaches
the new code -- it still fails at the earlier per-core gate).

Rebuilt the release-gcc tool (sha256 `637b2e38...`, differing from the
pre-fix `13daae36...` as expected), deployed it to the stand, and
recreated the `qual_isolated` isolated cpuset partition a third time.
With the fix in place, a live check mid-run confirmed the two worker
threads now land on separate real cores (`PSR=0` and `PSR=1`, not the
same core as before). The real run completed in the normal ~2 minutes
(`2:00.93` elapsed, `cross_core_passes=1`) rather than stalling:

| | producer | consumer | threshold |
|---|---|---|---|
| p99.9 delta | 1.472 us | 1.545 us | <= 1.0 us |
| p99.999 delta | 4.041 us | 7.335 us | <= 10.0 us |

This is the best real result across every attempt this session: p99.999
now clears comfortably on both sides (better than any prior attempt),
and p99.9, while still not clearing the threshold, is closer than the
`isolcpus`/IRQ-governor attempts and does not show the regression those
showed. Still `producer_per_core_passes=0`/`consumer_per_core_passes
=0`. The real output artifact was preserved (`near-raw.json`, 487
bytes); the `qual_isolated` cgroup and `cpuset` delegation were fully
reverted afterward, confirmed by an empty `cgroup.procs` before removal
and the root effective set returning to `0-103`.

Real per-core qualification at accepted scale remains an open blocker:
not a code defect in the sense the frozen D-009/`CLOCK-QUAL-LMRV1`
policy is being misapplied (it is not; the cross-core pinning fix above
is a real, independent, genuine bug fix, but the *blocking* criterion
here has always been per-core, not cross-core), and not yet resolved by
any of the four real remediation attempts tried against this stand's
current hardware/OS configuration (IRQ/governor tweaks, `isolcpus`/
`processor.max_cstate`, and three cgroup shielding attempts -- the last
with correct pinning).

### Combining cgroup shielding with the IRQ/governor tweaks: worse, not better

Tried next: layering the earlier IRQ-affinity/governor/turbo tweaks
(`performance` governor on CPUs 0/1, turbo off system-wide, 229/310
movable IRQs shifted off CPUs 0/1/52/53 -- same snapshot and script as
the original attempt) underneath the now-correctly-pinned `qual_isolated`
cgroup partition, to see whether the two real mitigations would compound.
Both layers applied cleanly (229 IRQs changed, partition `isolated` with
effective set `0-1,52-53`, matching every prior application exactly).
Real result:

| | producer | consumer | threshold |
|---|---|---|---|
| p99.9 delta | 2.183 us | 2.199 us | <= 1.0 us |
| p99.999 delta | 6.508 us | 6.491 us | <= 10.0 us |

This is worse than cgroup shielding alone (1.472 us / 1.545 us) and
matches the IRQ/governor-tweaks-alone result almost exactly (2.176 us /
2.169 us from the earlier attempt) -- meaning the cgroup isolation's
benefit is not additive with the governor/turbo change; if anything, the
governor/turbo change dominates and actively works against p99.9
regardless of what else is layered on top of it, consistent with the
"tried alone" result. Both layers were reverted immediately after: the
cgroup was removed and `cpuset` delegation disabled (root effective set
back to `0-103`), and the IRQ/governor snapshot was restored (308/310
IRQs, the same 2 fixed/unmovable ones as every prior revert) with a full
per-IRQ diff against the original snapshot confirming zero remaining
differences.

So: of the five real remediation attempts and combinations tried this
session, cgroup shielding *alone*, with the cross-core pinning fix
applied, remains the single best real result (p99.9 1.472 us / 1.545 us,
p99.999 comfortably under threshold on both sides) -- still short of
the p99.9 <= 1.0 us threshold, but the closest and the only one not
made worse by adding the governor/IRQ-affinity changes. The strongest
candidate for further real investigation, should someone continue this,
is refining the cgroup-only approach rather than combining it with the
governor/turbo tweaks.

### Cgroup shielding alone at the real far-pair scale

Tried the same cgroup-shielding-alone configuration (no governor/IRQ
tweaks) against the real `far` pair (`kFarWorkerPair{0, 26}` --
producer CPU 0 on real NUMA node0, consumer CPU 26 on real NUMA node1,
confirmed genuinely cross-socket via `lscpu`: `NUMA node0 CPU(s):
0-25,52-77`, `NUMA node1 CPU(s): 26-51,78-103`). Real HT siblings
confirmed via `/sys/devices/system/cpu/cpu{0,26}/topology/
thread_siblings_list`: CPU 0 pairs with 52, CPU 26 pairs with 78 --
so the isolated partition covered `0,26,52,78` rather than the near
pair's `0,1,52,53`. A live mid-run check confirmed correct placement
under the cross-core pinning fix: producer thread on `PSR=0`, consumer
thread on `PSR=26`, distinct real cores on distinct real sockets.

Real result (2:01.04 elapsed, `cross_core_passes=1` -- the pinning fix
holds at far-pair scale too):

| | producer | consumer | threshold |
|---|---|---|---|
| p99.9 delta | 1.857 us | 1.560 us | <= 1.0 us |
| p99.999 delta | 10.220 us | 4.054 us | <= 10.0 us |

Worse than the near pair's cgroup-alone result (1.472 us / 1.545 us):
the producer side (on node0, same physical location as every near-pair
run) now also misses the looser p99.999 threshold, if barely (10.220 us
against a 10.0 us limit). Consistent with the far pair's real
cross-NUMA-node communication path adding latency that CPU isolation
alone cannot remove -- isolation controls scheduling contention on each
individual core, not the real physical cost of a cross-socket
round trip. `producer_per_core_passes=0`/`consumer_per_core_passes=0`,
same as every other real attempt. The real output artifact
(`far-raw.json`, 487 bytes) was preserved; the `qual_isolated` cgroup
and `cpuset` delegation were fully reverted afterward (empty
`cgroup.procs` before removal, root effective set back to `0-103`).

So the near pair, not the far pair, is the more promising real
candidate for ever clearing the per-core threshold under cgroup
shielding -- the far pair's cross-socket physical distance appears to
set a real latency floor on top of whatever scheduling-contention gap
isolation closes.

### A diagnostic: does a longer warm-up (prime-read count) help?

Tried increasing the per-core warm-up phase itself, on the theory that
some of the tail latency might be a cold-start effect (frequency
ramp-up, branch predictor/cache warm-up) rather than steady-state
scheduling noise. `evaluate_clock_sequence`'s `prime_count_passes`
checks `prime_read_count` against the exact frozen constant
(`timing::kQualificationPrimeReadCount = 100'000`), so no real run at a
different prime count could ever produce accepted evidence regardless
of its tail-latency numbers -- this was explicitly a diagnostic
experiment, not a remediation candidate in the same sense as the
others. Added a `--prime-read-count N` flag to the tool for this
purpose (real code, committed, clang-tidy-clean beyond the pre-existing
unrelated finding): it overrides `ClockPairQualificationCounts.
prime_read_count` for one run, prints an explicit diagnostic-only note,
and refuses to combine with `--output` so no raw artifact could ever
report a prime count that didn't match what was frozen.

Real run: near pair, cgroup shielding alone (the best configuration so
far), 1,000,000 prime reads (10x the frozen 100,000), same 10,000,000
delta reads:

| | producer | consumer | threshold |
|---|---|---|---|
| p99.9 delta | 1.603 us | 1.528 us | <= 1.0 us |
| p99.999 delta | 5.385 us | 3.996 us | <= 10.0 us |

Compared against the same cgroup-alone configuration at the frozen
prime count (1.472 us / 1.545 us p99.9, 4.041 us / 7.335 us p99.999):
producer p99.9 got slightly worse, consumer p99.9 was essentially
unchanged, and p99.999 moved in opposite directions on the two sides.
No real improvement -- the differences are within the same run-to-run
noise band already seen across other real repeated attempts this
session (e.g. the two `isolcpus` runs). A 10x longer warm-up does not
meaningfully change the tail latency; whatever is producing the p99.9
gap is not a cold-start effect. Cgroup state was fully reverted
afterward, as with every other real attempt.

### A second diagnostic: does a larger delta sample count help?

Same rationale, aimed at a different question: if the tail outliers were
tied to a roughly fixed number of real periodic events across wall-clock
time (e.g. a timer interrupt, NMI, or SMI happening a fixed number of
times per second) rather than a fixed fraction of calls, a 10x larger
sample count would dilute their share of the distribution and p99.9
should improve. Added a matching `--delta-count N` flag (same pattern as
`--prime-read-count`: real code, committed, refuses `--output`, prints
an explicit diagnostic-only note; `accepted_policy_sample_count` checks
`delta_count` against the exact frozen `10'000'000` constant, so this
can never produce accepted evidence either).

Real run: near pair, cgroup shielding alone, 100,000,000 delta reads
(10x the frozen 10,000,000), frozen prime count:

| | producer | consumer | threshold |
|---|---|---|---|
| p99.9 delta | 1.506 us | 1.500 us | <= 1.0 us |
| p99.999 delta | 4.087 us | 3.994 us | <= 10.0 us |

Compared against the same cgroup-alone configuration at the frozen
delta count (1.472 us / 1.545 us p99.9, 4.041 us / 7.335 us p99.999):
p99.9 is essentially unchanged on both sides -- well within the same
noise band as every other repeated real run this session. p99.999 held
steady on the producer and improved on the consumer. The maximum delta
grew by roughly 20x (max 2.49 s / 2.81 s vs. the earlier ~127 ms / 138
ms), consistent with simple extreme-value behavior at 10x the sample
count and not evidence of anything new. A 10x larger sample does not
move the p99.9 percentile at all, which rules out a wall-clock-periodic,
dilutable-outlier explanation: roughly a fixed ~0.1% of individual
`clock_gettime(CLOCK_MONOTONIC_RAW)` delta reads exceed the ~1.5 us
range on this stand regardless of how many are taken, a stable, systemic
property of the read path here rather than a rare event that scales
with wall-clock time. Cgroup state was fully reverted afterward.

Between the two diagnostics, neither a longer warm-up nor a larger
sample count changes the real p99.9 result -- the gap looks like an
intrinsic property of this specific stand's `clock_gettime`/vDSO path at
the tail, not an artifact of any of the measurement's own tunable
parameters.

### Root-causing a slow read: MSR SMI count and perf stat, both real

Two concrete real hypotheses, checked directly rather than by further
parameter sweeps: system management interrupts (SMI -- firmware-level,
invisible to the OS and scheduler, a well-known cause of exactly this
kind of stable microsecond-scale stall that no cgroup/isolcpus/IRQ
tuning can touch), and first-touch minor page faults from the
`std::vector<std::uint64_t>` each per-core thread `reserve()`s for its
10,000,000 timestamps but never pre-faults.

SMI count is Intel MSR 0x34 (`MSR_SMI_COUNT`); `rdmsr` itself isn't
installed on the stand, but the `msr` kernel module is loaded and
`/dev/cpu/N/msr` is readable as root, so it was read directly (`dd
if=/dev/cpu/N/msr bs=8 count=1 skip=$((0x34)) iflag=skip_bytes`,
confirmed working by reading it twice a second apart first). Read on
both CPU 0 and CPU 1 immediately before and immediately after a full
real cgroup-isolated `--qualify-pair near` run (~2m10s): **512 before,
512 after, on both CPUs -- zero SMIs during the entire run.** This rules
out SMI entirely as a contributor.

`perf stat -e task-clock,page-faults,minor-faults,major-faults,
context-switches,cpu-migrations,cache-misses,cache-references -p PID`
was attached to the qualification process (still cgroup-isolated) for
the same run. Real result: **56,940 page faults, all minor, zero
major**; 220,880 context-switches; 1 cpu-migration; ~29.3M cache misses
against ~60.0M cache references. The page-fault count lines up with the
pre-fault hypothesis: two threads each `reserve()`-ing 80 MB (10,000,000
x 8 bytes) untouched-until-written is ~19,531 pages each, ~39,062
combined, plus the smaller cross-core exchange sample buffers -- the
same order of magnitude as the observed 56,940. A minor page fault
typically costs on the order of 1-10 us, consistent with the observed
p99.9 (~1.5 us) and p99.999 (~4-8 us) tail. The context-switch count is
not treated as evidence of interference on the per-core delta-read loop:
`run_direction_initiator`'s own pacing (`sleep_for(1ms)` between window
starts, up to ~30,000 real sleep/wake cycles per window across up to two
initiator roles) is a large, expected, benign source of voluntary
context switches during the ~118-second cross-core phase that follows
the brief per-core phase in the same run, and this `perf stat` invocation
spanned the whole run rather than being time-bounded to just the
per-core phase -- attributing the aggregate count to delta-read
interference specifically would overstate what was actually measured.

So: a real, concrete, actionable lead -- first-touch page faults on the
reserved-but-unfaulted timestamp vector -- with a real negative control
(SMI, cleanly ruled out) and one real, honestly-caveated ambiguous
signal (context-switches, most plausibly benign pacing sleeps, not
re-attributed to the per-core phase without further time-bounded
evidence). Cgroup state was fully reverted afterward. Not yet tried:
pre-faulting the vector (e.g. `std::vector(count, 0)` instead of
`reserve` + `push_back`, or an explicit touch pass before starting the
timed loop) to see whether it measurably closes the p99.9 gap.

## Resolution: the tail-latency gap was a page-fault artifact of the measurement itself

That fix was made and verified for real, and it resolved the blocker
completely. `capture_per_core` (`src/qualification/
q15_clock_pair_qualification.cpp`) changed from `std::vector<uint64_t>
timestamps; timestamps.reserve(counts.delta_count + 1U);` with
`push_back` inside the timed loop, to `std::vector<uint64_t>
timestamps(counts.delta_count + 1U, 0U);` (value-initialized, which
libstdc++ implements as a real memset over the whole buffer at
construction time) with indexed assignment inside the loop. This moves
every page fault from first-touch of the 80 MB buffer to before the
timed loop starts, rather than scattered across it. Verified locally
first: clean release-gcc build, clean under ThreadSanitizer and ASan/
UBSan, both existing tests still pass unchanged.

Deployed to the stand (sha256 `2187e340...`) and re-run under the same
cgroup-shielding-alone configuration that had produced the best result
so far. Real result: **full PASS** -- `producer_per_core_passes=1
consumer_per_core_passes=1 cross_core_passes=1`. p99.9 delta dropped
from ~1.5 us to **51 ns / 49 ns** on the two sides (a ~30x reduction);
p99.999 dropped to 1.572 us / 1.745 us, comfortably under the 10.0 us
limit. A `perf stat` taken on this same run showed page-fault count
essentially unchanged from before the fix (63,633 vs. the earlier
56,940) -- confirming the mechanism precisely: the fix did not reduce
the number of page faults, it moved *when* they happen, out of the
timed window entirely.

Given every real remediation attempt this session (IRQ/governor tweaks,
`isolcpus`, all four cgroup-shielding attempts) had produced roughly the
same ~1.5-2.2 us p99.9 regardless of OS-level tuning, the natural next
real question was whether the fix needed cgroup shielding at all, or
was sufficient by itself. Removed the cgroup entirely (delegation
disabled, root `cpuset.cpus.effective` back to `0-103`) and re-ran
`--qualify-pair near` on the stand's completely default configuration
-- no cgroup, no `isolcpus`, no governor/turbo changes, nothing. Real
result: **full PASS again**, p99.9 51 ns / 51 ns, p99.999 3.069 us /
3.321 us. Then `--qualify-pair far` (CPU 0 / CPU 26, genuinely
cross-NUMA-socket) under the same plain default configuration: **full
PASS**, p99.9 52 ns / 51 ns, p99.999 3.200 us / 4.199 us. Both raw
output artifacts are real, complete, and fully passing for the first
time this entire engagement:

```
near-raw.json: producer_per_core_passed=true consumer_per_core_passed=true cross_core_passed=true
far-raw.json:  producer_per_core_passed=true consumer_per_core_passed=true cross_core_passed=true
```

So none of the OS-level remediation explored earlier in this document
(IRQ/governor tweaks, `isolcpus`/`processor.max_cstate`, cgroup
shielding, or any combination) was ever actually the fix -- they each
produced small, inconsistent, partial improvements because they
happened to reduce contention that was itself a much smaller factor
than the measurement code's own first-touch page faults. The real
production configuration needs no stand-side system reconfiguration at
all: the accepted stand, completely unmodified, passes real per-core
qualification for both the near and far pairs at the full frozen scale
(10,000,000 delta reads, 100,000 prime reads) with this fix in place.

Real per-core qualification at accepted scale is no longer a blocker.
Combined with cross-core exchange (fixed and verified earlier in this
document) and Stage 8's static clock evidence gate (also a real,
complete PASS on the accepted stand), all three real measurement
components `SELECTED_PAIR_CLOCK` evidence depends on now produce real,
passing evidence for both pairs on the accepted stand. What remains
before `SELECTED_PAIR_CLOCK` evidence can be assembled: `traced_call_
count`/`traced_syscall_count` (the raw artifact still deliberately omits
these -- no real VDSO call/syscall tracer exists in this codebase yet,
separate from the static-clock gate's own external tracer requirement)
and `before_block_repeat`'s post-measurement timestamp capture, neither
of which was touched this session.

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
  so S17-EXT-004 cannot be built until this is resolved too. Stage 8's
  entire static clock evidence gate now has a real, complete PASS on the
  accepted stand, cross-core exchange completes for real at accepted
  scale, and -- as of the page-fault fix recorded above -- real per-core
  qualification now passes for real at accepted scale too, for both the
  near and far pairs, on the stand's completely unmodified default
  configuration (no cgroup, `isolcpus`, or governor tuning needed; the
  real cause was ~57,000 first-touch page faults from the per-core
  timestamp buffer landing inside the timed loop, not any stand-side
  scheduling, interrupt, or power-management factor -- six real OS-level
  remediation attempts and two sample-count diagnostics tried before
  root-causing it this way all produced small, inconsistent, partial
  improvements because they addressed a much smaller factor than the
  measurement code's own allocation pattern; see above for the full
  investigation). Still blocked: `traced_call_count`/`traced_syscall_
  count` (the raw artifact deliberately omits these -- no real VDSO
  call/syscall tracer exists in this codebase yet, separate from the
  static-clock gate's own external tracer requirement) and
  `before_block_repeat`'s post-measurement timestamp capture
  (`SelectedPairClockInput`'s own field, distinct from
  `StaticClockEvidenceInput`) -- neither touched this session.
- Surfaced, incidentally, a genuine internal disagreement between two of
  the project's own authoritative documents about `ADDRESS_RESIDENCY`'s
  intended shape (recorded above for whoever revisits ADR-0149).
