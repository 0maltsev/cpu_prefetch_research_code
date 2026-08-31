# ADR-0123: Stage 17 action-time schema-binding compatibility

- **Status:** `ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- **Decision ID:** D-123
- **Classification:** implementation correctness, action admission, provenance,
  and one-shot replacement lineage
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any replacement `S17-EXT-001` transaction after D-122

## Context

The first policy-v17 action was admitted with receipt schema v6, but the
immutable v13 verifier delegated action-time revalidation to the v8 helper.
That helper rebuilt `record_schema_bindings` by indexing the current policy
with its historical v5 receipt path.  Policy v13 intentionally contains only
the current v6 receipt binding, so revalidation raised `KeyError` before the
attempt marker and before `Popen`.  The output root remained empty and no
stand observation was started.

## Decision

Preserve the D-122 authorization, resolution, T1 journal and empty output root
through a typed action-revalidation blocker.  They are terminal inputs and
must not be retried.

Policy v14 and executor v12 bind action-time revalidation to the current
policy's record-schema map.  A compatibility copy containing predecessor
schema keys may be used only to execute the immutable predecessor's non-record
checks; its returned record bindings and filenames are discarded.  The
successor then installs and re-verifies only the policy-v14 attempt v10,
receipt v7, failure v8, failure-retention v3 and completion v7 bindings.
All terminal schemas accept the same exact twenty-three named runtime
identities, including the immutable v13 verifier helper actually loaded.

Every attempt marker version v1 through v10 and every registered terminal
filename blocks reuse.  A replacement authorization must bind the D-120,
D-121 and D-123 receipts, use a new attempt ID and empty output root, and pass
the same fixed six read-only actions.  No command, target, scientific value,
retry, privileged control, calibration, pilot or Phase 18 authority is added.

## Effects

The scientific design and fixed remote programs are unchanged.  Compatibility
is fail-closed: unknown current schema bindings, predecessor drift, a missing
D-123 receipt, or any prior marker/output rejects before transport.

## Verification and supersession

Acceptance requires a regression reproducing v13's v5/v6 `KeyError`, positive
action readiness using only current record bindings, negative missing/drifted
binding cases, exact terminal-schema runtime sets, cross-version replay tests,
all prior Stage 17 suites, sanitizers and a clean verified candidate bundle.
Any later change to authority, action semantics, schema selection, process
ownership or record shape requires another prospective successor.
