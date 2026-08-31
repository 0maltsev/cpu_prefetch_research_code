# ADR-0121: Stage 17 preflight marker runtime-cardinality correction

- **Status:** `ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- **Decision ID:** D-121
- **Classification:** implementation correctness, evidence compatibility, and
  pre-marker recovery
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any new `S17-EXT-001` transport attempt

## Context

The first real policy-v11 preflight transaction reached complete pre-marker
preparation and failed schema validation. Policy v11 correctly bound nineteen
runtime implementation identities, while attempt schema v7 still required
exactly seventeen. No attempt marker, SSH transport, remote observation, or
scientific action was created. The authorization is finite and cannot be
extended or silently retried.

## Decision

Preserve policy v11, executor v9, the original external journal, and its empty
preflight output directory unchanged. Add a versioned successor consisting of:

- preflight policy v12 and semantic verifier v12;
- attempt schema v8, which admits exactly the twenty named policy-v12 runtime
  identities rather than an unexplained numeric predecessor count;
- authorization/supporting-contract v10 and envelope v12, binding executor
  v10 and an exact pre-marker-blocker receipt;
- executor v10, which preserves v9 action, clock, snapshot, one-shot, and
  process-quiescence behavior and emits attempt v8; and
- operational policy v16/journal/controller/CLI successors for the same graph.

A new operational transaction is allowed only when a typed blocker receipt
re-reads the predecessor journal and authorization bytes, proves the v7
expected/actual cardinalities, and observes that the predecessor output root
contains no attempt, receipt, failure, completion, stdout, or stderr record.
The prior transaction remains append-only and is never rewritten. The new
authorization has a new ID, bounded UTC window, transaction ID, and exact
successor runtime bindings. It is not a retry of a consumed action because no
one-shot marker or transport existed.

## Effects

There is no scientific effect and no new authority. The six fixed read-only
observations, target, limits, command graph, zero-retry rule, and Stage 18
denial remain unchanged. The compatibility effect is fail-closed: policy-v11
records cannot be executed by executor v10, and policy-v12 admission requires
the retained predecessor-blocker lineage.

## Verification and supersession

Acceptance requires characterization of the 19-versus-17 failure, positive
attempt-v8 validation with the exact policy-v12 key set, rejection of missing
or forged blocker lineage, a persisted fresh-journal preparation test, the
full Stage 17 regression suite, and a clean verified bundle. Any later runtime,
authority, action, or schema change requires another prospective ADR.
