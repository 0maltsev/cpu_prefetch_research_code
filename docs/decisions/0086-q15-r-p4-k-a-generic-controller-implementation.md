# ADR-0086: Implement the generic no-authority P4-K-A controller

- Status: `ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_EXTERNAL_OR_EXECUTION_AUTHORITY`
- Date: 2026-08-25
- Decision ID: D-086
- Accepted by: owner delegation to do all work needed to reach the next gate
- Decision owners: repository, security, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; implements ADR-0084 without environment specialization
- Lifecycle gate: before a clean controller release and before any P4-K-A admission

## Context and options

ADR-0084 freezes a no-shell, one-attempt, zero-retry controller policy. Exact
offline tools, environment, custody, public paths, bootstrap trust, issuance,
and review evidence do not exist. Options were a generic hash-bound policy
engine that cannot admit an action without every external input, premature
specialization to invented environment values, an ad hoc executable, or no
implementation.

## Decision

Implement the generic policy engine. It has no OS process backend and cannot
read a path, environment, descriptor, key, trust artifact, or authorization.
Its admission boundary requires:

- clean source and controller hashes;
- a currently active, exact 1,800-second authorization;
- independently verified bootstrap signature and distinct auditor review;
- exact environment, toolchain, custody, and create-exclusive public-export
  evidence;
- direct absolute tools and structured argv, never a shell or `/usr/bin/env`;
- only `LANG`, `LC_ALL`, `PATH`, and `TZ` in the non-secret environment;
- an uncaptured controlling TTY or dedicated descriptor at least 3 for secret
  input;
- explicit positive resource limits supplied by the future authorization; and
- the fixed ten-step graph, one action attempt, zero retry, no overwrite,
  repair, cleanup, or automatic continuation.

Every successful fake step returns public-only, unique, hash-bound evidence.
The controller stops with retained partial evidence on the first mismatch,
failure, expiry, limit, secret disclosure, or forbidden mutation. Success ends
only in `public_evidence_sealed_waiting_for_p4_k_r`.

## Evidence and effects

- Q15-R-P4-K-A-D acceptance SHA-256:
  `c68e1b9427df9306a53cac590dfe268862fa528ef5bf665bf0002972cf77ffaf`.
- Implementation profile SHA-256:
  `0ceafd80200ba62584532e035a4c2a21015c2b56f75d0ebbfdffbd7f3b945875`.
- Typed header/source/fake-test hashes are bound in that profile.

Scientific effect is none. Controller profile, graph, admission fields,
process/secret boundary, resource-limit values, source/binary bytes, and every
external evidence hash become transaction compatibility identity.

## Verification and authority boundary

Unit tests cover complete admission, absent bootstrap trust, dirty/hash drift,
shell and secret-environment rejection, descriptor mismatch, graph/retry/
cleanup/continuation rejection, exact execution order, failure at every step,
unsafe evidence, resource bounds, and expiry. Schema/profile checks bind source
hashes and reject widened authority.

This ADR authorizes repository-local source, schema, tests, and documentation
only. It does not select or access an offline environment, establish a
bootstrap root, read/generate/import/copy/fingerprint/use a key, collect a
private path/passphrase/seed, create public paths/artifacts, sign or issue an
authorization, access the stand, or authorize P4-K-A, P4-K-R, Q15, calibration,
pilot, measurement, or confirmatory work.

## Supersession

Any graph, admission, direct-process, environment allowlist, secret-input,
limit semantics, evidence, failure, retry, cleanup, or stop change requires a
new prospective ADR, clean source/release identity, and independent review.
Issued records are never edited or retargeted.

No protocol amendment is required because the controller cannot alter the
experiment or produce scientific evidence.
