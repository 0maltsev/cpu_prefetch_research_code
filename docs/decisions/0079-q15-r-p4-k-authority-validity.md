# ADR-0079: Freeze P4-K authority, validity, signature, and review policy

- Status: `ACCEPTED_REPOSITORY_LOCAL_POLICY_AND_TEMPLATE_PREPARATION_ONLY`
- Date: 2026-08-25
- Decision ID: D-079
- Accepted by: Q15-R-P4-K-D owner-delegated recommended choice
- Decision owners: protocol, security, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; extends ADR-0074's governance profile to P4-K gates
- Lifecycle gate: before signing or issuing P4-K-A or P4-K-R

## Context and scientific constraints

Root access, SSH reachability, and a logical custody declaration are not
authorization. P4-K also has a bootstrap-signing problem: the new target key
does not yet exist and therefore cannot silently authenticate its own creation.
The actual authorization signer and trust evidence remain external inputs.

## Options considered

1. `cpu-prefetch-q15-operator`, exact nonrenewable 1,800-second UTC validity,
   `JCS-I64-v1`, accepted SSHSIG Ed25519/SHA-512, and distinct auditor review;
2. a different exact owner-supplied authority/validity profile;
3. root or SSH reachability as authority;
4. unsigned, renewable, indefinite, or self-reviewed action; or
5. remain blocked.

## Decision

Freeze `cpu-prefetch-q15-operator` as named authority,
`cpu-prefetch-q15-custodian` as custodian, and
`cpu-prefetch-q15-auditor` as distinct reviewer. Freeze `JCS-I64-v1`,
`OPENSSH-SSHSIG-ED25519-SHA512-v1`, principal and namespace
`cpu-prefetch-q15-authorization`, exactly `1800` seconds, and no renewal or
reuse.

Literal issue/expiry instants, bootstrap signer fingerprint and trust evidence,
authorization hash, detached-signature hash, and pre-execution review hash
remain null. The target P4-K public key and its fingerprint also remain null.
No authorization is signed or issued.

## Evidence

- ADR-0058 and ADR-0060 freeze the distinct roles and canonical SSHSIG boundary.
- ADR-0074 accepts the same policy profile for P4-R but did not silently extend
  it to P4-K.
- D-076 through D-079 proposal SHA-256:
  `cf05bbfdfeb92e9f4de438beac7a05f9f77bfc316c8dc3793e76cf2a47f52ff5`.
- Q15-R-P4-K-D acceptance SHA-256:
  `11b9c357468515145bc5e7b2b477515c814d31ec97603245eff378d0259e6be7`.

## Consequences and compatibility

Scientific effect is none. Principals, canonicalization, signature scheme,
duration, bootstrap signer/trust identity, literal instants, authorization and
signature hashes, and review receipts become transaction identity.

## Verification and acceptance tests

Checks reject root-as-authority, role collapse, changed duration/scheme,
renewal/reuse, self-review, a fabricated bootstrap signer, target-key
self-authorization, non-null issue/signature fields, or issuance authority.

## Rollback or supersession

Any principal, scheme, duration, signer/trust, canonicalization, or review
change requires new canonical unsigned bytes, a prospective ADR, and new
acceptance. Issued records are never edited or retargeted.

## Protocol-amendment assessment

No protocol amendment is required. This constrains authorization mechanics
without changing scientific semantics.
