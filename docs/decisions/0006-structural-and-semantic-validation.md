# ADR-0006: Structural and semantic validation

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Correctness architecture
- Decision owners: Repository owner; validation owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2; validator product remains Stage 3 selection

## Context and scientific constraints

Draft 2020-12 schemas validate document shape but cannot prove all arithmetic, decoded-schedule, namespace, chronology, cross-hash, factorial-coverage, replacement, or authority constraints.

## Options considered

1. Schema validation only.
2. One validator with indistinguishable structural and semantic repairs.
3. Separate structural and semantic passes with immutable, machine-readable failure reports and no repair.

## Decision

Adopt option 3. Structural validation uses the imported schemas. A second validator checks cross-record and protocol semantics. Both fail closed and never mutate input. A record is usable only after all required passes succeed.

## Evidence

- Imported schemas, data dictionary, readiness report, and freeze checklist.
- Explicit Stage 2 requirement for a replaceable validation boundary and Stage 1 finding that semantic validation is distinct from JSON parsing.

## Consequences and compatibility

Scientific effect: none; it enforces fixed protocol rules. Compatibility effect: the implementation needs stable validation-result codes and versioned rules; selecting a Draft 2020-12 library alone does not complete the validator.

## Verification and acceptance tests

Use valid golden records plus one negative fixture per schema constraint and semantic invariant. Include cross-hash, lifecycle, count, timestamp, schedule, namespace, factorial, access, and replacement mutations.

## Rollback or supersession

The validator implementation may change behind the interface if its conformance suite remains valid. Removing a normative check requires protocol review and normally an amendment.

## Protocol-amendment assessment

No amendment is required.
