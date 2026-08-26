# ADR-0104: Finite Stage 17 pilot operational-governance successor

- Status: `ACCEPTED_PROSPECTIVE_LOCAL_IMPLEMENTATION`
- Date: 2026-08-26
- Decision ID: `STAGE17-GOVERNANCE-SUCCESSOR-v1` (accepted directly; no
  decision-only D-109/D-110 bundle)
- Classification: pilot authorization, operational roles, state machine, and
  confirmatory access boundary
- Decision owners: protocol, pilot, platform, controller, custody, and audit
  owner acting as the explicitly disclosed single owner for pilot only
- Protocol version: `2.0.0-pre.2`
- Supersedes: ADR-0045, ADR-0046, and ADR-0050 only where they make pilot
  preflight/authorization depend on distinct operational identities or a new
  PKI ceremony for each read-only observation; no confirmatory rule is
  superseded
- Lifecycle gate: before any new Stage 17 stand preflight or phase
  authorization

## Context and scientific constraints

The repository accumulated a chain in which each read-only fact created a new
decision, signature, review, and successor prerequisite. That chain could not
reach a finite pilot phase authorization even though it changed no treatment,
queue, schedule, timing boundary, estimand, or access chronology. D-099 through
D-108 and their evidence must remain immutable.

Pilot operational admission is distinct from the imported confirmatory
selection/sealing chronology. Pilot observations cannot open H3 validation or
H1/H2 outcomes. Conversely, confirmatory role and access rules do not require
one new pilot PKI ceremony per read-only runtime observation.

## Options considered

1. Continue creating one decision/signature/review successor for every missing
   read-only observation.
2. Remove all authorization and sealing controls.
3. Use one finite pilot operational state machine, one machine-readable
   external-input checklist, an explicitly disclosed single-owner role
   collapse for pilot, and preserve strict Stage 18 access chronology.

## Decision

Select option 3. The only pilot operational successor states are:

`PREPARED -> AUTHORIZED_FOR_READ_ONLY_PREFLIGHT -> PREFLIGHT_ACCEPTED -> READY_FOR_STAGE17_PHASE_AUTHORIZATION`.

Each edge consumes the exact checklist inputs registered by
`STAGE17-EXTERNAL-INPUTS-v1`; missing or invalid evidence retains the current
state and any partial artifacts. There is no automatic retry, state skip, or
authority inheritance.

For Stage 17 pilot work, one named principal,
`cpu-prefetch-stage17-pilot-owner`, may act as owner, operator, controller,
custodian, and auditor. Every resulting review must state that roles are
collapsed and independent review is not claimed. One hashed owner
authorization may cover one frozen set of read-only preflight observations;
there is no separate PKI ceremony per observation. Privileged controls and
scientific phases still require exact, prospective, bounded authorization
after their inputs exist.

The pilot role collapse does not apply to Stage 18. The imported sequence
`PLANNED`, `COLLECTED_SEALED`, `TRAINING_OPEN`, `SELECTION_FROZEN`,
`VALIDATION_UNSEALED`, `H3_EVALUATED`, `H1H2_RELEASED`, `ARCHIVED` remains
strict. Validation remains inaccessible until its authorized unseal, and
H1/H2 release still requires the sealed H3 evaluation/access predecessors.

D-099 through D-104 remain accepted historical records/evidence. D-105 through
D-108 remain byte-preserved proposed, unaccepted records; this successor does
not silently accept them and does not require their decision-only chain.

## Evidence

- Direct owner instruction in this task to remove the governance/state-machine
  deadlock locally while leaving the stand untouched.
- Imported `ACCESS_AND_SEALING_PROTOCOL.md` and the exact Stage 18 chronology.
- The preservation manifest `STAGE17-D099-D108-PRESERVATION-v1`.
- Positive full-chain and negative skip/missing-input/role/access-boundary
  tests in `tools/check_stage17_operational_successor.py`.
- The hermetic D-104 self-test and separate explicit external-archive
  integration contract.

## Scientific and compatibility effects

Scientific effect: none. No treatment, workload, queue operation, timestamp,
calibration estimator, pilot value, block, outcome, or confirmatory access is
created or changed.

Compatibility effect: the successor ID, state, checklist ID/hash, transition
evidence hashes, role-collapse acknowledgement, exact preflight observation
set, phase inputs, source/binary hashes, and authority window are identity.
Older D-104 code remains recoverable at its Git revision; a current executor
must be bound by the successor rather than rewriting D-104 preparation.

## Verification and acceptance tests

- Reject every D-099 through D-108 tracked-artifact hash change and verify the
  historical D-104 executor directly from Git object `dc643df...`.
- Accept only the three adjacent transitions and reject skips, regressions,
  unresolved prerequisites, duplicate evidence IDs, fabricated hashes,
  independent-review claims, per-observation PKI requirements, widened
  authority, and any weakening/reordering of Stage 18 access states.
- Prove `execute_d104_p4_r_c.py --self-test` supplies synthetic archive bytes
  and has no external/archive filesystem acquisition dependency.
- Validate a real qualification archive only through an explicitly invoked
  integration/action check with caller-supplied paths.

## Rollback or supersession

Do not rewrite this ADR, predecessor evidence, or completed transition records.
A prospective successor may add or narrow pilot gates while retaining the
lineage. Any change to scientific semantics or the imported Stage 18 access
chronology requires protocol review and, where applicable, a versioned protocol
amendment. Pilot failure never authorizes confirmatory access or deletion.

## Protocol-amendment assessment

No protocol amendment is required. This decision changes implementation-owned
pilot operational governance only and explicitly preserves all imported
scientific and confirmatory access semantics.
