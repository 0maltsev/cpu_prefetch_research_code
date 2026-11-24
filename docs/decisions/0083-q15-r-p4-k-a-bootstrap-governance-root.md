# ADR-0083: Require a separate bootstrap governance root and block P4-K-A

- Status: `ACCEPTED_POLICY_BLOCKED_NO_QUALIFYING_BOOTSTRAP_SIGNER`
- Date: 2026-08-25
- Decision ID: D-083
- Accepted by: Q15-R-P4-K-A-D, `P4KA-Q4=NO_QUALIFYING_BOOTSTRAP_SIGNER_REMAIN_BLOCKED`
- Decision owners: security, protocol, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; closes ADR-0079's bootstrap-evidence branch
- Lifecycle gate: blocking before any P4-K-A signing or issuance

## Context and options

The target P4-K key does not exist and cannot authenticate its own creation.
Options were an existing distinct reviewed governance signer, separately
establishing a bootstrap governance root, treating the target/root/SSH/chat as
authorization, or remaining blocked.

## Decision

The owner states that no qualifying bootstrap signer evidence exists.
Therefore select the separate-bootstrap-root branch and keep P4-K-A blocked.
A future, separately governed process must establish an owner-controlled
offline Ed25519 governance signer distinct from the target key, custodian, and
auditor. Before returning to P4-K-A it must provide non-secret public
fingerprint, canonical allowed-signers/trust bytes and SHA-256, custody lineage,
principal/namespace compatibility, and independent review evidence.

This ADR does not authorize establishment of that root, access to a signer or
trust artifact, key activity, signing, issuance, or use of chat, SSH, or root
access as a substitute.

## Evidence and effects

- D-083 proposal SHA-256: `8acfebfb22ba7449233b5c4c5b2a7ecf9c9a48323b1d79b45b42d26867199777`.
- Acceptance SHA-256: `c68e1b9427df9306a53cac590dfe268862fa528ef5bf665bf0002972cf77ffaf`.
- Bootstrap signer/trust fields remain null and `P4-K-A` is blocked.

Scientific effect is none. A future bootstrap public key/fingerprint, trust
bytes/hash, custody lineage, principal/namespace, algorithm, and reviewer
receipt become authorization identity.

## Verification and supersession

Checks must reject any claim that bootstrap evidence exists, target-key
self-authorization, root/SSH/chat authority, or P4-K-A issuance. Any future
signer, trust, custody, signature profile, or reviewer value requires a
separate prospective governance bundle and exact acceptance; this ADR remains
the provenance of the prior blocked state.

No protocol amendment is required.
