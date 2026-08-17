# ADR-0005: Append-only partial-failure lifecycle

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Failure handling / data integrity
- Decision owners: Repository owner; controller and storage owners
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2; concrete durable store remains open

## Context and scientific constraints

Runs can fail after different lifecycle transitions. Raw producer and consumer streams are independently observed and must not be fabricated, repaired in place, or overwritten. Replacement occurs only at complete-block scope.

## Options considered

1. Transactionally publish only fully successful runs and discard partial artifacts.
2. Rewrite a run record as later phases complete.
3. Append lifecycle transitions, artifacts, audits, failures, and corrections as distinct immutable records.

## Decision

Adopt option 3. Partial outcomes are first-class. The controller records the highest reached state and only artifacts actually created. Failed reconciliation retains raw sources and a failed audit but creates no joined-derived stream. Corrections and replacements are new records with lineage; they never mutate the source.

## Evidence

- Imported schemas, access/sealing protocol, data dictionary, and implementation-spec sections 16, 19, and 20.
- Explicit Stage 2 partial-failure and append-only requirements.

## Consequences and compatibility

Scientific effect: prevents silent exclusion or reconstruction and preserves the replacement rule. Compatibility effect: storage must support durable append, stable IDs, lineage, and crash recovery; consumers must tolerate incomplete lifecycles without inventing defaults.

## Verification and acceptance tests

Inject failure at every lifecycle boundary; verify exact artifact presence/absence, immutable hashes, idempotent recovery, failed-join behavior, and complete-block replacement lineage.

## Rollback or supersession

Only a stronger immutable lifecycle may supersede this ADR. Destructive update or discard of required evidence needs a protocol amendment.

## Protocol-amendment assessment

No amendment is required.
