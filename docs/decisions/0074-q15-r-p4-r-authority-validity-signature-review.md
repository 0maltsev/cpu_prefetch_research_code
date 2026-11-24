# ADR-0074: Freeze Q15-R-P4-R authority, validity, signature, and review policy

- Status: `ACCEPTED_REPOSITORY_LOCAL_TEMPLATE_FREEZE_NO_STAND_AUTHORITY`
- Date: 2026-08-25
- Decision ID: D-074
- Accepted by: Q15-R-P4-F
- Decision owners: protocol, platform, security, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; specializes ADR-0058 and ADR-0060 for the split P4-R transaction
- Lifecycle gate: before issuing or signing either P4-R-I or P4-R-C

## Context and scientific constraints

SSH reachability and the bootstrap `root` account are transport, not
authority. The accepted four-role policy forbids issuer/reviewer/custodian
collapse, and P4-K still lacks actual key, fingerprint, allowed-signers, and
custody evidence. A policy may be frozen without fabricating those external
facts or issuing an authorization.

## Options considered

1. named operator authority, exact nonrenewable 1,800-second UTC validity,
   accepted OpenSSH SSHSIG Ed25519/SHA-512 profile, and distinct auditor review;
2. treat root/SSH reachability as authority;
3. use unsigned, indefinite, renewable, or self-reviewed approval; or
4. remain blocked.

## Decision

Freeze `cpu-prefetch-q15-operator` as named authority,
`cpu-prefetch-q15-authorization` as SSHSIG principal and namespace,
`cpu-prefetch-q15-custodian` as custodian, and
`cpu-prefetch-q15-auditor` as independent reviewer. Freeze `JCS-I64-v1`,
`OPENSSH-SSHSIG-ED25519-SHA512-v1`, private-key custody off stand, exact
issue-to-expiry duration `1800` seconds, no renewal or reuse, and the `900`-
second external collector watchdog inside the authorization window.

Literal issue/expiry instants, authorization hash, signer fingerprint,
detached-signature hash, review hash, allowed-signers bytes, and custody
evidence remain null. No key, signature, or authorization is created or used.

## Evidence

- ADR-0058 freezes distinct logical roles; ADR-0060 freezes the canonical
  SSHSIG issuance boundary; P4-K remains byte-identical with eight null inputs.
- P4-K SHA-256:
  `c56ae3dc74142d244e448b9a6f638960f0cce1eb1a9e7a106fea90a4bcf55e0f`.
- Decision bundle SHA-256:
  `18c29f6f3710b061bcf593ad6615589a6b50c4bf28ebceb4bee3714702389604`.
- Q15-R-P4-F acceptance SHA-256:
  `ae879bd113939ee06fd3673c0f14d054d92d6c30c0162ffa6727d2a42973cb8c`.

## Consequences and compatibility

Scientific effect is none. Compatibility effect is exact: principals,
canonicalization, signature scheme and namespace, duration, single-use rule,
fingerprint, authorization/signature hashes, and review receipt become
authorization identity when later populated from evidence.

## Verification and acceptance tests

Checks reject role collapse, root-as-authority, changed policy values,
fabricated non-null evidence, renewed/reused authorization, or widened
authority. Actual key/custody evidence, timestamps, signatures, and reviewer
receipt require separate approvals.

## Rollback or supersession

Any principal, canonicalization, scheme, namespace, duration, signer key,
custody, or review-profile change requires a new ADR, new canonical unsigned
authorization bytes, and prospective acceptance. An issued record is never
edited.

## Protocol-amendment assessment

No protocol amendment is required. This constrains governance and evidence
compatibility without changing scientific semantics.
