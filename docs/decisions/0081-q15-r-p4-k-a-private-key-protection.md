# ADR-0081: Freeze P4-K-A private-key protection and custody evidence

- Status: `ACCEPTED_POLICY_LITERAL_KDF_AND_EXTERNAL_CUSTODY_EVIDENCE_REQUIRED`
- Date: 2026-08-25
- Decision ID: D-081
- Accepted by: Q15-R-P4-K-A-D, `P4KA-Q2=ACCEPT_D081_RECOMMENDATION`
- Decision owners: security, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; specializes ADR-0066 and ADR-0077
- Lifecycle gate: before controller contract freeze or P4-K-A issuance

## Context and options

The logical custody domain and custodian are accepted identities, not proof of
operational custody. Options were an encrypted OpenSSH Ed25519 private key with
an uncaptured interactive secret and non-secret custody receipt, a compatible
nonexporting alternative with SSHSIG evidence, an unencrypted or recorded
secret, or remaining blocked.

## Decision

Require an encrypted OpenSSH Ed25519 private key, an owner-selected exact KDF
work value at a later evidence gate, and interactive passphrase entry excluded
from argv, environment, captured standard input, logs, and artifacts. Require a
hash-bound non-secret custody receipt describing access controls, backup,
recovery, retention, and destruction policy without recording the private-key
path, private bytes, seed, or passphrase.

No KDF value, secret, key, private path, or custody evidence is selected or
collected by this ADR.

## Evidence and effects

- D-081 proposal SHA-256: `8acfebfb22ba7449233b5c4c5b2a7ecf9c9a48323b1d79b45b42d26867199777`.
- Acceptance SHA-256: `c68e1b9427df9306a53cac590dfe268862fa528ef5bf665bf0002972cf77ffaf`.
- The P4-K-A custody input remains null.

Scientific effect is none. Key encoding, KDF and exact work value, secret-input
boundary, custody controls, recovery/retention policy, and receipt hash become
custody identity.

## Verification and supersession

Checks must reject secret or private-path serialization, invented custody
evidence, unencrypted exportable-key policy, or action authority. Any change to
encoding, KDF/work value, secret boundary, custodian, access, backup, recovery,
retention, or destruction requires prospective acceptance and new evidence.

No protocol amendment is required.
