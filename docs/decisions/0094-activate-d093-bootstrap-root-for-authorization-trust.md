# ADR-0094: Activate the exact D-093 root for future authorization trust

- Status: `ACCEPTED_ROOT_ACTIVE_NO_SIGNING_OR_DOWNSTREAM_ACTION_AUTHORITY`
- Date: 2026-08-25
- Decision ID: D-094
- Accepted by: the owner's instruction to perform the exact next gate without
  further interaction
- Decision owners: protocol, security, custody, and audit owner acting under
  the D-093 single-owner waiver
- Protocol version: `2.0.0-pre.2`
- Supersedes: no evidence; transitions only the exact D-093 fingerprint from
  `CREATED` to `ACTIVE`
- Lifecycle gate: bootstrap trust activation before P4-K-A authorization
  preparation

## Context and options

D-093 created one bootstrap root and verified its public evidence, but its
append-only lifecycle policy intentionally stopped in `CREATED`. Options were
to leave it inactive, revoke or mark it compromised/lost, or activate exactly
that public fingerprint as the eligible signer for a later separately
authorized P4-K-A action. The owner instructed the repository to perform the
exact next gate and granted the authority needed to do so without another
round trip.

## Decision

Activate only fingerprint
`SHA256:JuRM4SuWL9C1xvOes9z+CAKZV1rvel27VZ/+qiuVNs0` under the existing
principal and namespace `cpu-prefetch-q15-authorization`. Activation binds the
D-093 evidence record SHA-256
`e7066cf41fe2af2d38ee0c0a8947ce326f78882ed07294faa42143f1ef020361`,
the create-exclusive `allowed_signers` SHA-256
`6c21b0d631a3842e182bd92e0856aa5073c949f5c5a6b4a8e85b48dd2016f33d`,
and the immutable D-093 lifecycle-policy SHA-256
`863ad34c5ea144b0cfd2ad71a99e205cd082683cc4e1941fa06ec3fc289641d5`.

This is a repository trust-state transition. It does not read, hash, copy,
decrypt, invoke, or sign with the private key. It authorizes no P4-K-A action
and no generic or stand operation. A versioned P4-K-A successor may record the
now-eligible fingerprint and trust evidence while retaining every other
unresolved input and the unissued state.

## Effects and authority boundary

Scientific effect is none. Compatibility effect is material: the exact
fingerprint, principal, namespace, public trust bytes/hash, D-093 evidence, and
activation lineage become the only eligible bootstrap identity for a future
P4-K-A authorization. D-093's critical impersonation and unrecoverable-loss
risks remain open.

This decision authorizes the D-094 acceptance/activation records, schemas,
checkers, documentation, and a repository-local versioned P4-K-A preparation
with only its bootstrap-trust input resolved. It does not authorize private-key
use, signature creation, P4-K-A/P4-K-R execution, target-key creation, stand
access, Q15-R/Q15-W, controls, qualification, calibration, pilot, measurement,
or confirmatory execution.

## Verification and supersession

Checks must bind the exact D-093 evidence and lifecycle hashes, fingerprint,
principal/namespace, transition order, public trust hash, and lack of signing
or downstream authority. They must reject a different root, a transition from
any state other than `CREATED`, active-root signing claims, fabricated P4-K-A
inputs, or mutation of predecessor records.

Any fingerprint, public bytes, principal, namespace, prior state, activation
scope, signing scope, compromise/loss disposition, or downstream authority
change requires a new prospective ADR and append-only lifecycle record. The
D-093 and D-094 records are never edited.

No protocol amendment is required because this changes authorization trust
governance without changing experimental semantics.
