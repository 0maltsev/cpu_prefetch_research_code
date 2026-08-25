# ADR-0066: Require an owner-selected offline Ed25519 signer

- Status: `ACCEPTED_METHOD_LITERAL_VALUE_UNRESOLVED`
- Decision ID: D-066
- Accepted by: Q15-R-P4-D on 2026-08-25
- Classification: security and custody engineering
- Owners: security and custody owners
- Lifecycle gate: before allowed-signers construction or stand setup
- Supersedes: the unresolved acquisition method after ADR-0062; no key or artifact

## Decision

Use an owner-selected offline Ed25519 public key. The private key must never be
created, imported, copied, or stored on the stand. An existing owner-controlled
offline key or a new separately authorized offline ceremony may supply the key;
that choice, custody domain, public bytes, and evidence remain unresolved.

Options considered were an existing offline key, a separately authorized new
offline key, stand-local generation/private-key storage, and remaining blocked.
Stand-local custody is rejected. Evidence is ADR-0062, the accepted OpenSSH
SSHSIG Ed25519/SHA-512 policy, and the still-null allowed-signers source.

Scientific effect is none. Compatibility effect is exact: public-key bytes,
fingerprint, custody identity, principal, namespace, allowed-signers bytes, and
artifact hashes become authorization identity.

## Authority and supersession

Q15-R-P4-D authorizes preparation only. It does not authorize any key action.
Q15-R-P4-K requires separate exact approval. Key rotation or custody change
requires a new ADR, artifacts, independent review, signatures, and prospective
acceptance; prior evidence remains immutable.
