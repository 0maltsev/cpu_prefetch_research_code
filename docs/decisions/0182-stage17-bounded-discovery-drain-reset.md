# ADR-0182: Bounded quiescent discovery drain and reset

- Status: `ACCEPTED`
- Date: 2026-10-30
- Decision ID: D-182
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: engineering component for EXT007 diagnostic coordination
- Lifecycle gate: local verification only; no diagnostic executable or authority

## Decision

Provide a consumer-owned drain primitive for the point at which both
capture workers are quiescent. Take explicit clock-origin, fixed-duration,
maximum-attempt, expected-pending-count, and logical-reset-request inputs.
Reject invalid/overflowing budgets before clock or queue access. Check the
actual clock before every dequeue, with no new attempt at or after the
deadline and no attempt beyond the fixed capacity. No count-driven extension
or dynamic buffer growth is permitted.

Pass each actual dequeued pointer through the caller's ordinary consumer
validation/checksum action. Retain the dequeue count even if that action
fails. Stop on callback failure, unexpected extra events, clock failure or
reversal, expired horizon, or exhausted capacity. Return partial counts and
observed clock evidence. These are failure outcomes, not permission to reset
or proceed to measurement.

Completion requires observing empty, an actual quiescent ring audit with
zero occupancy and valid cursor ranges, and exact reconciliation against
the independently supplied pending count. Matching the number of events
alone does not establish observed empty. An exhausted budget cannot be
overridden by inferring emptiness from counts.

Only after successful drain may an explicitly requested warm-up reset call
the existing `RingSpscQueue::reset_quiescent`. Verify occupancy and both zero
cursors afterward. Final measurement drains can omit logical reset. The
primitive never reallocates/remaps arenas, regenerates records/permutations,
retouches payloads, changes hardware state, or admits a run. A failed or
insufficient original capture remains so even if subsequent recovery drains
successfully. The future coordinator must check both original worker results
and the drain result before any next phase.

## Verification and limits

Two initial real-ring tests failed against an inert implementation and pass
with the drain implementation. Seven drain tests now cover ordered callback
delivery, consumer failure after a real dequeue, both count-mismatch
directions, partial clock/deadline/capacity failures, reversed time, invalid
and overflowing budgets, an unobserved-empty boundary, and final drain
without reset. The existing concurrent real-ring capture test now uses this
primitive to reconcile accepted advances against consumed plus drained
events and to reset the same ring after both worker threads join.

The caller still must establish worker affinity, actual quiescence and
ownership, the approved consumer action, independent counts, and finite
outer watchdog authority. This component cannot interrupt a stuck clock or
callback and is not a process watchdog. It does not select a scientific
warm-up duration, authenticate a run, retain raw files, or provide a live
diagnostic action. The implementation does not change the immutable pre.3
five-second pre-freeze formal calibration/pilot warm-up rule.
