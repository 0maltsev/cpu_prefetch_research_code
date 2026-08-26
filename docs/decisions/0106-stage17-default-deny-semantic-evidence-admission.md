# ADR-0106: Default-deny Stage 17 semantic evidence admission

- Status: `ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- Date: 2026-08-26
- Decision ID: `STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v2`
- Classification: operational evidence semantics, authorization scope, and
  action-readiness admission
- Decision owners: repository, pilot, platform, release, custody, and audit
  owner
- Protocol version: `2.0.0-pre.2`
- Supersedes: ADR-0105 only where generic file/receipt integrity was treated as
  sufficient operational evidence; its immutable v1 graph, catalog, genesis,
  append-only lineage, and real-byte requirements remain accepted
- Lifecycle gate: before resolving any `S17-EXT` input

## Context

ADR-0105 corrected persistence but did not prove that evidence contents met
the catalog requirement. A repository file containing `{"accepted": true}`
or an arbitrary external artifact with a structurally valid receipt could
resolve most inputs. The v1 read-only authorization allowed one arbitrary
observation and did not bind the supporting action contract. Its runtime
identity fields also conflated prospectively known local action bytes with
remote identities that can only be observed during preflight.

The v1 graph, catalog, genesis, journal snapshots, schemas, ADR-0104, and
historical D-099 through D-108 evidence are immutable and cannot be repaired
in place.

## Options considered

1. Add more generic required fields to the v1 resolution schema.
2. Treat file/receipt integrity as an owner assertion of semantic validity.
3. Preserve v1 storage identities and add a versioned, predecessor-bound,
   default-deny semantic-admission policy and typed evidence envelope.

## Decision

Select option 3. The v1 resolution remains the append-only storage envelope,
but operational admission is governed by
`STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v2`. The policy binds the exact
v1 graph, catalog, genesis snapshot and genesis record, resolution schema, and
ADR-0105. It registers every `S17-EXT-001..010` verifier. Missing, unknown, or
explicitly unimplemented verifiers return
`SEMANTIC_VERIFIER_NOT_IMPLEMENTED_FAIL_CLOSED`; generic JSON and generic
receipts cannot substitute.

`S17-EXT-001` uses a v2 semantic envelope that byte/hash-binds one v2
authorization and one v2 supporting observation contract. Its verifier
requires the six observations in exact order; exact target and pinned-host-key
evidence; the fixed pilot-candidate contract and locators; prospective local
launcher and collector bytes; exact argv/stdin/remote-command bytes;
create-exclusive outputs and finite limits; one attempt, no retries,
stop-first and retain-partial policies; disclosed role collapse; and the exact
read-only permission matrix. Local action bytes are prospective inputs.
Remote executable, module, and dependency identities are expressly deferred
to the read-only `S17-EXT-002` observation and cannot be populated in the
prospective contract.

`S17-EXT-006` retains its real caller-supplied archive/sidecar and fixed
custody/integration verifier. `S17-EXT-002..005` and `S17-EXT-007..010` remain
explicitly fail-closed until their accepted requirements have complete typed
semantic contracts. In particular, no generic `S17-EXT-010` can create pilot
readiness or stand in for predecessor-resolution hashes and permitted run IDs.

State-machine mechanics tests use only a test-harness replay seam. Production
`validate_journal()` and its CLI expose no synthetic verifier or admission
bypass.

Authorization validity at resolution/transition time is historical evidence,
not continuing action authority. Any requested action separately requires an
explicit evaluation UTC and an unexpired applicable `S17-EXT-001`,
`S17-EXT-005`, or `S17-EXT-010` authorization.

## Evidence

- A disk-backed positive S17-EXT-001 fixture with complete typed contract,
  real temporary files, and recomputed byte counts and SHA-256 values.
- A separate disk-backed `10 resolutions / 3 transitions` mechanics fixture
  that cannot be used by the production CLI for evidence admission.
- Negative tests for arbitrary/missing/changed/unbound contracts,
  observation/target/contract/limit mismatch, generic JSON, arbitrary external
  receipts, unknown/unimplemented verifier, widened permissions, expired
  action authority, predecessor-free S17-EXT-010, and synthetic placeholder
  pilot-readiness attempts.

## Scientific and compatibility effects

Scientific effect: none. The protocol, treatments, schedules, observations,
timing, calibration, estimands, replacement rules, and Stage 18 chronology are
unchanged.

Compatibility effect: existing v1 definitions and snapshots remain readable
and hash-identical. A future resolution is operationally admissible only when
its input has an implemented v2 registry entry and its evidence satisfies that
registered semantic verifier. Schema-valid legacy evidence can therefore be
retained but remains unresolved.

## Rollback or supersession

Do not rewrite a v1 or v2 definition, evidence record, resolution, transition,
or journal snapshot. A successor policy or semantic contract must use a new
version, bind this policy and all preserved predecessors, default deny unknown
inputs, and preserve the Stage 18 boundary. A scientific change additionally
requires protocol-owner review and a versioned amendment.

## Protocol-amendment assessment

No protocol amendment is required. This closes an implementation-owned
evidence-admission defect without changing scientific semantics or granting
stand, pilot, measurement, or Stage 18 authority.
