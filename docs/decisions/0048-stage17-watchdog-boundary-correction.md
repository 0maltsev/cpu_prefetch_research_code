# ADR-0048: Stage 17 watchdog boundary correction

- Status: `ACCEPTED_AND_IMPLEMENTED_SOFTWARE`
- Date: 2026-08-24
- Decision ID: D-048
- Classification: scientific-semantics-preserving lifecycle correction
- Decision owners: protocol, controller, lifecycle, platform, and validation owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: the in-measurement poll-count interpretation in ADR-0031 and the
  five-limit admission form in ADR-0043/ADR-0044; their start-barrier,
  one-attempt, termination, failure-retention, and no-retry rules remain
- Lifecycle gate: Q15-P0 before a new pilot-candidate release

## Context

The protocol requires the producer to tight-poll until every frozen deadline
and the consumer to poll until it acquire-observes producer completion and the
queue is empty. The v2 runner instead allowed finite producer-wait,
pre-completion-empty, and drain poll counts. Poll count is not elapsed time: a
valid open-loop gap or valid accepted backlog could exhaust the count and be
misclassified as a measurement/drain failure. That changes which observations
are valid and is therefore an implementation defect, not a platform value to
calibrate.

## Options considered

1. Select larger fixed poll counts.
2. Derive poll counts from observed processor speed or pilot outcomes.
3. Remove in-measurement poll-count expiry and place hang containment in the
   external controller/process boundary with an exact prospective wall-clock
   bound.
4. Leave the v2 candidate eligible.

## Decision

Select option 3. The producer waits until due or an actual clock/backend/peer
failure; the consumer polls until the exact termination-plus-empty condition
or an actual backend/peer failure. Drain has no count-dependent early exit.
Only the two pre-measurement start-barrier poll limits remain inside
`ExecutionLimits`. Their values and the external process watchdog's exact
wall-clock bound remain mandatory prospective Q15 inputs; no default is added.

The incompatible current identities are
`cpu-prefetch-runner-admission/3` and
`STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v3`. Admission v1/v2 schemas remain
unchanged and readable but cannot arm v3.

## Evidence and effects

- Imported implementation specification Sections 5.1, 5.2, and 5.5.
- Owner acceptance of Q15-P0 on 2026-08-24.
- Targeted tests cross a 50,000-tick idle gap and a drain backlog beyond the
  former cap without failure; clock, queue, cancellation, and start failures
  remain explicit.

Scientific effect: restores the registered waiting/drain semantics and removes
an outcome-dependent invalidation path. Compatibility effect: admission,
runner profile, generated code, sanitizer evidence, and candidate hashes must
be regenerated. Owner: controller/lifecycle. Deadline: before Q15. A future
change to worker waiting, termination, or failure eligibility requires a
superseding ADR and protocol review; a new external timeout value requires a
new authorization/evidence record without changing this loop.

## Authority boundary

Q15-P0 authorizes repository-local correction and testing only. It does not
authorize a process timeout value, stand access, qualification, calibration,
pilot, or confirmation.
