# ADR-0060: Require SSHSIG and separate Q15-R issuance approval

- Status: `ACCEPTED_POLICY_NO_ISSUANCE_AUTHORITY`
- Date: 2026-08-24
- Decision ID: D-060
- Classification: approval, signature, issuance, and phase governance
- Decision owners: protocol, platform, security, controller, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no decision; specializes ADR-0045 and ADR-0051
- Lifecycle gate: before Q15-R issuance and again before execution

## Decision

The final authorization uses `JCS-I64-v1` and
`OPENSSH-SSHSIG-ED25519-SHA512-v1` with namespace
`cpu-prefetch-q15-authorization`. It must bind the actual signer/key,
canonical authorization and signature hashes, UTC validity, release/stand,
literal argv, roles, limits, outputs, custody, and prerequisites. Independent
signature verification must precede controller execution.

Q15-R-P1 authorizes repository-local implementation and no-authority setup
artifacts only. It does not authorize stand access, account/key changes,
transfer/install, Q15-R issuance/signature/execution, Q15-W, real platform or
device operations, dynamic qualification, calibration, pilot, measurement, or
confirmatory work. A later exact signed Q15-R record needs separate explicit
approval; Q15-W remains a different later authorization.

Any canonicalization, signature, trust-anchor, signer, validity, phase, or
authority-boundary change requires a new governance decision and immutable
authorization.
