# ADR-0181: Preserve queue outcomes when demand capture fails

- Status: `ACCEPTED`
- Date: 2026-10-30
- Decision ID: D-181
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: correctness prerequisite for the authorized EXT007 continuation
- Lifecycle gate: local verification; no experiment or release authority

## Problem and decision

The existing ring-demand observer discovers clock or trace failure after the
queue operation. Returning only `clock_failure` or `trace_failure` loses
whether that operation already accepted, consumed, returned FULL, or returned
empty. The bounded discovery worker consequently undercounted actual queue
advances on this failure path. A stop cannot undo an accepted enqueue or a
completed dequeue, and drain reconciliation must retain that fact.

Append an optional, independently reported `operation_outcome` to
`RingCaptureResult`. Both real ring capture helpers populate it immediately
from the queue result, including every failed observation path. Existing
`outcome`, before/after clock statuses, slot-demand boundaries, and queue
algorithm/memory orders retain their meanings. The discovery worker records
the last actual operation separately and increments the actual advance,
FULL, or empty counter even when capture failed. It still stops and cancels
its peer; a correct operation cannot turn a failed measurement into valid
data or create a fabricated timing sample.

Older synthetic callback aggregates can omit the appended field; their
previous successful outcome semantics remain usable for component tests.
Missing actual-operation evidence is not a new empirical observation.
The formal Q16a action remains the legacy sample-count implementation and
does not gain fixed-duration or diagnostic authority from this change.

## Verification and remaining work

Three regression tests failed before the fix, with six failed assertions:
both actual advances and FULL/empty results disappeared after capture
failure. They use the real SPSC ring with exhausted clocks or reversed
demand timestamps, not a mocked queue outcome. The corrected tests retain
actual occupancy and operation counts while retaining the mandatory capture
failure and peer cancellation. Existing successful capture and trace tests
remain applicable. Relevant compiler and sanitizer results are recorded in
the EXT007 readiness record after execution.

This is independent of the unimplemented discovery coordinator, integrity
join/consumer action, NUMA verification, watchdog, persistence, and signed
diagnostic admission. A future qualified diagnostic policy must explicitly
bind these changed calibration headers and sources; prospective v54 remains
unpromoted and grants no such action authority.
