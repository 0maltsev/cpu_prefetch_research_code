# ADR-0119: Stage 17 preflight canonical-serializer runtime successor

- **Status:** `ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- **Decision ID:** D-119 / STAGE17-PREFLIGHT-CANONICAL-SERIALIZER-RUNTIME-v1
- **Classification:** engineering correctness and runtime-identity compatibility
- **Owner:** repository implementation owner
- **Gate:** before another `S17-EXT-001` authorization or read-only preflight
- **Supersedes:** only the executable eligibility of ADR-0118 policy v13 /
  preflight policy v10 / executor v8; all predecessor bytes and failed or
  partial transactions remain immutable

## Context

The first real external-journal handoff reached transition T1 and then stopped
before its one-shot marker and before transport. Executor v8 called
`stage17_state_journal_v3.canonical_json_bytes()` while that module name was
not imported. Prospective admission did not execute the complete preparation
path, so its narrower regression passed even though `_prepare_action()` raised
`NameError`. Retrying that transaction is prohibited.

This is an implementation defect. It does not change the fixed six read-only
observations, target, authority window, OpenSSH snapshot mechanism, process
supervision, scientific design, or Stage 18 boundary.

## Options considered

1. Edit executor v8 or policy v10 in place.
2. Inject the missing module dynamically without changing the policy-bound
   identity.
3. Preserve every predecessor and create a versioned policy, verifier,
   journal, CLI, and executor successor whose complete preparation path is
   tested from persisted external-journal records.

Option 3 is selected. Options 1 and 2 would make recorded hashes or the actual
runtime differ from the admitted identity.

## Decision

Preflight policy v11 and operational policy v14 bind executor v9, semantic
verifiers v11/v14, journal runtime v12, CLI v6, the new schemas, this ADR, and
their complete discovered Python closure. Executor v9 uses the already-bound
`stage17_state_journal.canonical_json_bytes()` helper for both pinned-input
metadata and typed failure records. Authorization and supporting-contract v9,
the six fixed observations, action plans v6/v7, attempt/receipt/failure/
completion schemas, and graph/catalog/genesis remain unchanged.

The regression must reload a persisted external journal, prove action
readiness under the successor, run the complete pre-marker preparation with
synthetic credentials and no transport, and show that executor v8 still
reproduces the missing-import defect in an isolated process. Candidate-bundle
creation and clean-extraction verification must materialize and verify the
entire nested policy-v11 closure.

## Effects and compatibility

- **Scientific effect:** none.
- **Compatibility effect:** policy-v13/v10-envelope records are immutable
  predecessors and cannot authorize executor v9. Fresh operational work must
  use policy v14, preflight policy v11, envelope v11, CLI v6, journal v12, and
  executor v9 as one exact release closure.
- **Authority:** none is issued by this ADR or its tests. No retry, automatic
  transition, stand mutation, Q15/Q16, calibration, pilot, measurement, or
  Stage 18 authority is added.
- **Partial evidence:** every prior transaction is retained and never reused.

## Supersession rule

Any change to serializer bytes, executor/verifier/journal/CLI identity,
external-root lineage, fixed action input, authority rule, marker semantics,
OpenSSH consumption, or process cleanup requires another prospective
versioned ADR and fresh release. A scientific change requires a versioned
protocol amendment.
