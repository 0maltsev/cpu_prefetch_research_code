# ADR-0180: Discovery worker deadline and prepared trace component

- Status: `ACCEPTED`
- Date: 2026-10-30
- Decision ID: D-180
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: engineering implementation under the owner-approved ADR-0178 design
- Lifecycle gate: local component verification only; no diagnostic execution or formal Q16a admission

## Decision

Implement a worker component using an explicit common origin, fixed duration,
worker role, and attempt/trace capacity. Time uses the selected clock's
relative-picosecond unit. Check overflow and invalid budgets before clock
or queue work. Check the clock and deadline before admitting each attempt;
minimum observation counts are deliberately absent from this worker API,
so they cannot extend the window or cause early success.

An attempt admitted before the deadline can finish afterward. The next gate
retains the actually observed stop tick without clamping or extrapolation;
this component makes no hard real-time preemption guarantee. The enclosing
diagnostic process must still enforce its independent finite watchdog.

Record independent producer/consumer attempt, advance, FULL/empty, and
clock-status evidence. Stop on an observed clock failure, clock reversal,
wrong-role outcome, failed slot-demand capture, or peer cancellation.
An attempt reported as successful with failed clock status is still invalid;
retain the reported advance and failure evidence rather than silently
accepting it. Trace exhaustion stops before an overflowing attempt and
signals the peer. If a read observes the deadline exactly when capacity is
full, no further attempt is needed and the deadline takes precedence.

Add explicit owner-thread trace preparation: instantiate and reserve storage
before capture, then resize, touch every owned demand/issue element through
volatile stores, and clear only logical lengths before measurement. This
prevents the compiler from eliminating the prefault stores. Each worker
touches only its own two buffers. Preparation refuses already prepared or
nonempty traces and cannot erase earlier observations. It selects no CPU
or NUMA value; the caller must first establish actual binding and page policy.

The prepared worker adapter requires preparation, empty logical buffers,
and an exact trace/budget match. A separate quiescent validator cross-checks
recorded demand/issue/nonadvance counts against the worker's independent
counts only after both workers have stopped and joined. Scanning arrays
while a peer finishes its last in-flight attempt would perturb capture.
The validator also rejects nonpositive demand or advancing-issue observations,
retaining those observations rather than deleting them
or declaring a clock call failed when its actual status was successful.
No allocation, logging, configuration parsing, I/O, quantile calculation,
or adaptive threshold selection occurs in the capture loop. Queue
release/acquire and slot-demand bracketing are unchanged.

## Verification and limits

Fifteen targeted tests exercise deadlines (including an already expired
window and exact full-buffer boundary), capacity, integer overflow, clock
failure/reversal, cancellation, inconsistent successful-capture status,
prepared-buffer requirements, count/trace mismatch, retained FULL attempts,
and concurrent real SPSC queue workers with synthetic time. The concurrent
test reconciles produced and consumed advances after an unmeasured drain
and verifies quiescent reset. Existing calibration tests remain applicable.

The API does not authenticate run identity, pin threads, bind/verify shared
NUMA pages, coordinate a warm-up/start barrier, drain on a wall-clock
budget, control MSRs, persist artifacts, prove quarantine, or issue an
authorization. The producer and consumer must receive the same prepared
origin from the future diagnostic coordinator. Prefaulting is not a claim
that pages cannot later fault or migrate; actual runtime checks remain
mandatory.

The old sample-count-only Q16a worker is not relabeled or silently replaced.
The new component has no executable diagnostic action surface and is not
enabled by the existing six-action production contract. A future qualified
diagnostic release must bind the new header and changed calibration sources,
complete the missing coordination/preparation/evidence path, and pass its
exact operational admission before live collection. No formal data or
duration selection is produced by these tests.
