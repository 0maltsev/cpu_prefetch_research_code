# ADR-0171: Stage 17 Q16b consumer-drain race fix

- Status: `ACCEPTED`
- Date: 2026-10-10
- Classification: Correctness fix, real data-loss bug in already-accepted production code
- Decision owners: Protocol owner; repository owner
- Protocol version: `2.0.0-pre.3`
- Supersedes: None

## Context

Three consecutive real Q16b execution attempts on `cpu-prefetch-v3`
(185.184.128.107) failed with `S17-Q16B-LIFECYCLE: fixed-duration
continuous-ready capture did not complete validly`, at decreasing
partial-completion points (2071/3540, 1009/3540, then a few hundred
of 3540 runs), with no code or parameter change between attempts. Real
hardware was safely restored every time (`restoration_verified: true`
held in all three).

Root-caused by direct, live instrumented reproduction, not assumed. A
standalone build of the real `src/`+`include/` code, extended to
exercise the real `run_artifacts`/publish file-writing path into one
shared, growing output directory (mirroring the real worker's own
per-run file accumulation across a single long-lived process), caught
the failure live at iteration 920 of 4000: `accepted=46318` vs.
`consumed=46312`, a real six-item discrepancy, with every other
failure sub-condition (`cancellation`, `producer_failed`,
`AffinedPreparationEvidence`'s CPU-affinity and software-prefetch-
capability checks) passing cleanly. A prior, narrower reproduction of
the same measurement/affinity logic alone (no file I/O, 10,000
iterations) never saw the race, consistent with real disk/`fsync`
latency widening the window enough to make this already-rare
condition observable at production scale.

The real bug: `capture_ticketed_service_rate`'s consumer loop
(`src/runner/stage17_fixed_action.cpp`) polled the queue, and checked
`termination.arrivals_finished()` only *after* that poll came back
empty, concluding `consumer_drained = true` immediately on seeing it
true. If the producer's very last enqueue and its subsequent
`publish_arrivals_finished()` call both happened in the narrow window
between the consumer's "empty" poll and its `arrivals_finished()`
check, the consumer never polled again -- it had no way to observe
that last item, so `report.consumed` undercounted `report.accepted`.

## Decision

Poll once more, immediately after observing
`termination.arrivals_finished() == true`, before concluding
`consumer_drained`. This is provably correct under the C++ memory
model, not merely plausible: `publish_arrivals_finished()` is a
`memory_order_release` store and `arrivals_finished()` is a
`memory_order_acquire` load (`include/cpu_prefetch/lifecycle/
runtime.hpp`), and the ring queue's own per-slot enqueue/dequeue are
likewise `memory_order_release`/`memory_order_acquire`
(`include/cpu_prefetch/queue/ring_spsc.hpp`). The producer's last
enqueue is sequenced-before its own `publish_arrivals_finished()` call
(same thread); the consumer's acquire-load observing that release
synchronizes-with it; by transitivity, any poll the consumer performs
*after* observing `arrivals_finished() == true` is guaranteed to see
that last enqueue. The fix adds exactly this follow-up poll, with the
same item/failure/empty handling as every other poll in the loop.

Verified by rerunning the identical instrumented reproduction against
the fixed code: 10,000 real iterations, zero recurrences of the race
(or of any other failure sub-condition). At the originally observed
~1-in-920 rate, 10,000 iterations would be expected to show roughly
10-11 occurrences if the bug were still present; seeing zero is a
strong, though not absolute, positive result given the sample size.

The shared lifecycle executor (`include/cpu_prefetch/lifecycle/
executor.hpp`, used by Q16c, Q15-R, and Q15-W via
`execute_measurement`/`execute_measurement_with_preparation`) already
checks `arrivals_finished()` *before* polling within the same loop
iteration -- the opposite, already-correct order, which this ADR's
own happens-before argument shows is race-free by construction. This
bug and its fix are therefore isolated to Q16b's own separate,
hand-written consumer loop in `capture_ticketed_service_rate`; no
other fixed action is affected, and none needed a change.

This edit changes `src/runner/stage17_fixed_action.cpp`'s bytes, which
are individually pinned by `config/stage17/stage17-operational-
evidence-admission-policy-v48.json`'s own `bindings` entry (the same
file ADR-0159/ADR-0166/ADR-0168/ADR-0170 already re-pinned four times
for real changes to this exact file). A new policy generation (v49)
re-pins it again, and a matching `stage17_state_journal_v43.py`
successor propagates the new semantic-verifier generation through the
admission journal's ancestor-walk mechanism, exactly mirroring the
ADR-0170/v48 pattern.

## Consequences

Scientific effect: this fixes a real measurement-integrity bug
specific to Q16b. Unlike ADR-0170 (a pure diagnostic addition, no
behavior change), this changes real runtime behavior: before this fix,
a Q16b run could silently lose the last one or more accepted events of
its measurement window roughly once every ~920 runs, undercounting
`consumed`/`accepted` for that run. Any already-executed real Q16b
result built against the pre-fix binary reflects this exposure for
whichever individual runs (if any) it happened to hit; real hardware
was always safely restored regardless (`restoration_verified: true`
held in every observed occurrence), and the bug cannot cause data
corruption beyond an undercount in the affected run's own producer/
consumer tallies.

Compatibility effect: any pilot-candidate bundle built from a commit
at or after this one needs a fresh `S17-EXT-001` through `S17-EXT-003`
admission (worker/binary identity changes), exactly as every prior
re-pin of this same file required. A fresh journal additionally needs
`S17-EXT-004` onward rebuilt in sequence, since each of those depends
on the real Q15-R/Q15-W/Q16a/Q16b/Q16c executions that only exist
against one specific admitted binary identity at a time.

## Rollback or supersession

No rollback is anticipated: this closes a real, reproduced data-loss
race with a verified fix, not a speculative or diagnostic change. A
future ADR would only supersede this one if a further, independent
issue were found in the same consumer-drain path.
