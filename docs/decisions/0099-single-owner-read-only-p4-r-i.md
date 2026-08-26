# ADR-0099: Authorize one single-owner read-only P4-R-I transaction

- Status: `ACCEPTED_ONE_READ_ONLY_P4_R_I_TRANSACTION_AND_PUBLIC_REVIEW`
- Date: 2026-08-26
- Decision ID: D-099
- Accepted by: exact `Q15-R-P4-R-I-D099` authorization
- Decision owners: protocol, platform, security, custody, and audit owner
  acting as one owner under this explicit waiver
- Protocol version: `2.0.0-pre.2`
- Lifecycle gate: one P4-R-I identity capture and review, followed by a
  mandatory stop before P4-R-C

## Context

D-097 completed review of the P4-K target public trust identity and stopped
before P5. ADR-0072 through ADR-0075 freeze a separate P4-R-I read-only identity
gate before P4-R-C may stage or execute the collector. The candidate stand has
an existing locally pinned Ed25519 SSH host identity and a local transport key,
but the earlier distinct-role policy cannot be realized by the single owner.

The options were to remain blocked, establish distinct people and custody, or
accept a single-owner downgrade for P4-R-I only. The owner explicitly selected
the downgrade and accepted the loss of independent misuse detection,
host/account impersonation exposure, misuse, and unrecoverable-key risks.

## Decision

Authorize exactly one D-099 transaction with these boundaries:

- the logical operator, custodian, and auditor principals remain named as
  frozen by ADR-0074, while owner `omaltsev` performs all three roles under an
  explicit waiver;
- use the D-097-reviewed P4-K v2 Ed25519 identity for exactly one SSHSIG over
  the canonical D-099 authorization, without recording private bytes;
- pin only the existing `ssh-ed25519` host key for `185.184.131.153`, fingerprint
  `SHA256:HZMyUcQIuSQIodYGxXGQ3RCoqR8UcOWPPzuTDhXKtS4`;
- use the local transport public identity fingerprint
  `SHA256:mtIlJWQzNackGLwexvC6bTnmLb8yJtdUQdC/k+FxKRo` with fixed OpenSSH options,
  no agent, no password, no keyboard interaction, one connection attempt per
  observation, and zero retries;
- execute exactly the four read-only argv vectors frozen by ADR-0075, each at
  most once, with bounded stdout, stderr, and timeout;
- create the frozen repository-local identity artifact and sidecar
  exclusively, preserve partial failure evidence, and perform one public
  single-owner review; and
- stop after review with no automatic continuation to P4-R-C.

The detached signature hash is retained in execution and completion evidence
instead of inside the signed payload, avoiding a circular self-hash while
preserving exact signature identity. This supersedes ADR-0074's distinct-review
requirement and signature-field placement only for D-099/P4-R-I. It does not
change either rule for P4-R-C.

## Scientific and compatibility effects

Scientific effect is none: the action observes platform identity and does not
run the collector, control hardware, calibrate, or measure. Compatibility
effect is exact: predecessor commit, tool and policy bytes, target signer,
pinned host key, transport public identity, four argv vectors, UTC window,
authorization/signature hashes, output paths, and review bytes identify the
transaction.

## Failure and authority boundary

Any missing, expired, mismatched, existing-path, host-key, authentication,
command, output-bound, signature, hash, or review condition stops. A partial
local evidence tree is retained; retry, overwrite, delete, repair, cleanup, or
reuse is forbidden.

This ADR authorizes repository-local verification, one target-key
authorization signature, four fixed read-only stand observations, one
create-exclusive local capture, and one public single-owner review. It
authorizes no stand filesystem mutation, transfer, extraction, collector
self-test or execution, P4-R-C, P5, Q15-R/Q15-W, platform control, calibration,
pilot, measurement, confirmatory execution, or automatic continuation.

## Verification and supersession

The preflight checker must bind every immutable input, validate canonical
authorization and SSHSIG, reject widened authority and command drift, scan the
executor for shell/retry/dynamic-command paths, and run a no-network self-test.
The completion checker must verify the artifact, sidecar, review, exact four
observations, zero retry, read-only status, and P4-R-C stop. Any change requires
a new prospective ADR and unused capture identity; existing evidence remains
append-only.

No protocol amendment is required because this changes qualification
governance/security only and leaves every scientific treatment, measurement,
calibration, and inference rule unchanged.
