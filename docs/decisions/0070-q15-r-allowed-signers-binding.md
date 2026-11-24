# ADR-0070: Bind canonical allowed-signers bytes independently off-stand

- Status: `ACCEPTED_METHOD_LITERAL_VALUE_UNRESOLVED`
- Decision ID: D-070
- Accepted by: Q15-R-P4-D on 2026-08-25
- Classification: security and integrity engineering
- Owners: security, custody, and audit owners
- Lifecycle gate: before trust-anchor installation or signed Q15-R preparation
- Supersedes: the unresolved actual allowed-signers identity after ADR-0062

## Decision

Construct one canonical allowed-signers artifact off-stand from the accepted
offline Ed25519 public key, record its artifact ID and SHA-256, derive the key
fingerprint independently, and later require installed-byte equality. The
actual key, bytes, hash, fingerprint, source path, and review evidence remain
null.

Options considered were independent canonical construction, an unverified
user-written file/fingerprint, derivation only after stand installation, and
remaining blocked. Only independent off-stand construction is accepted.
Evidence is ADR-0061/0062 and the unresolved signer binding.

Scientific effect is none. Compatibility effect binds canonical file bytes,
artifact ID, SHA-256, Ed25519 fingerprint, SSHSIG principal/namespace, and
verification tool as authorization identity.

## Authority and supersession

Q15-R-P4-D authorizes preparation only; Q15-R-P4-K separately governs any key
or artifact action. Key rotation requires a new ADR, artifacts, hashes,
fingerprint, signatures, independent review, and prospective acceptance.
