# ADR-0046: Stage 17 phase-scoped execution authority

- Status: `ACCEPTED`
- Date: 2026-08-22
- Decision owners: protocol, statistical, calibration, platform, controller,
  security, and custody owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: none
- Lifecycle gate: Q16a through Q16d before each dependency-ready Stage 17 phase

## Context and scientific constraints

Ring-distance calibration precedes service calibration; service output
precedes feasibility probes; those outputs and later treatment-blind pilot
evidence precede freezes. An omnibus or conditional Stage 17 approval would
allow later inputs to be chosen before immutable predecessor evidence exists.

## Options considered

1. One omnibus Stage 17 approval.
2. Treat SSH/root possession as execution authority.
3. One conditional approval naming incomplete future inputs.
4. Separate immutable dependency-ready authorizations for D2 calibration,
   service calibration, feasibility probes, and blinded pilot/freeze-input
   collection.

## Decision

Select option 4. Q14 accepts this governance rule only. Each future Q16 record
must bind the exact phase, release/stand/qualification, predecessor hashes,
run plan, configurations, schedules, namespaces, seeds, counts, durations,
capacities, budgets, authorities, storage/custody, stop conditions, expiry, and
partial-artifact disposition. The runner accepts only the exact current phase
authorization referenced by admission.

Q16a through Q16d are not approval-ready. Q14 and Q15 do not imply any of
them. Stage 18 confirmatory execution requires a separate later readiness
review and authority.

## Evidence

- Q14 acceptance and D-046 bundle row.
- Imported calibration dependency graph, access/sealing chronology, freeze
  checklist, and failure-retention rules.
- D-035 through D-039 and ADR-0035 through ADR-0040.

## Consequences and compatibility

Authorization identity includes every phase input and predecessor hash. An
expired, superseded, mismatched, partially applied, or unresolved record cannot
arm the runner. A material dependency change invalidates downstream authority
but never removes completed or failed evidence.

## Verification and acceptance tests

- Reject wrong/missing phase, predecessor, plan, schedule, namespace, seed,
  budget, authority, storage, qualification, expiry, and hash fields.
- Reject omnibus, wildcard, `latest`, confirmatory, top-up, hidden retry,
  cell-repair, and later-phase permissions.
- Prove the validation tool cannot execute a phase or access outcomes.

## Rollback or supersession

There is no execution rollback and no silent retry. Preserve partial evidence,
restore the stand, and issue a new prospective authorization only after the
dependency graph is again complete. A change to scientific chronology requires
protocol review and normally an amendment.

## Protocol-amendment assessment

This enforces the imported chronology and authority boundary without changing
an estimator, run, or treatment. No protocol amendment is required.
