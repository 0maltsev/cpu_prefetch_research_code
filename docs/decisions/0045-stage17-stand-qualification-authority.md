# ADR-0045: Stage 17 stand-qualification authority

- Status: `ACCEPTED`
- Date: 2026-08-22
- Decision owners: platform, timing, queue-correctness, security, custody, and
  audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: none
- Lifecycle gate: Q15 before any dynamic stand qualification

## Context and scientific constraints

Read-only inventory and topology identify a candidate stand and CPU pairs but
do not qualify them. Root SSH access, a successful control command, and a
self-authored record are not authority or independent verification. Requested
and verified state must stay separate, and restoration must be demonstrated
before a control can be eligible.

## Options considered

1. Reuse inventory as qualification.
2. Permit an omnibus root session or broad conditional authorization.
3. Require an immutable hash-bound authorization for one exact release, stand,
   pair set, command whitelist, limits, authority set, and evidence plan;
   separate nonprivileged dynamic checks from one-control-at-a-time privileged
   rehearsal.

## Decision

Select option 3. Q14 accepts the policy and repository-local schema/validator
work only. A future Q15 must name and hash the exact release and every command,
target, value, inverse, readback, probe, output, byte/time limit, stop
condition, authority, and custody path. It may collect qualification evidence
but cannot use a scientific schedule or Stage 17 namespace.

No stand command is authorized by this ADR. Wildcards, `latest`, unresolved
inputs, unbounded root commands, unhashed scripts, expired records, and
partially applied records fail closed.

## Evidence

- Q14 acceptance and D-045 bundle row.
- ADR-0018 through ADR-0020 and the Stage 9 request/apply/readback/restoration
  interfaces.
- Stage 16 inventory-only, topology, and single-durable-domain evidence.
- Q13 pair selection without dynamic qualification.

## Consequences and compatibility

Qualification identity includes the stand, release, pair, control, authority,
whitelist, pre-state, readback, probe, restoration, clock, atomic/layout,
residency, storage, and record hashes. Any material dependency change requires
a new qualification record. Q15 cannot be prepared until the exact clean v2
candidate release and all authorization fields exist.

## Verification and acceptance tests

- Schema and semantic rejection of missing hashes, wildcard/latest targets,
  absent limits, overlapping authority, privilege scope drift, missing inverse,
  and pilot/confirmatory permission.
- Fake-backend evidence producers for selected-pair clock, atomic/layout,
  actual-CPU/migration, and address-residency records.
- Negative tests proving validation cannot apply a control or mint a runner
  phase ticket.

## Rollback or supersession

Stop after the first mismatch, restore applied controls in reverse order, and
quarantine the stand on restoration uncertainty. Retain every partial record.
Policy changes require a superseding ADR; operational changes require a new
prospective Q15.

## Protocol-amendment assessment

This strengthens the authority/evidence boundary and changes no scientific
state or treatment. No protocol amendment is required.
