# ADR-0062: Use a fixed inherited-descriptor Q15-R trust-anchor adapter

- Status: `ACCEPTED_AND_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- Date: 2026-08-25
- Decision ID: D-062
- Classification: operational adapter and trust-anchor boundary
- Decision owners: controller, security, platform, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no decision; implements ADR-0057 and ADR-0060
- Lifecycle gate: before a clean operational release and Q15-R issuance

## Decision

Use `Q15-R-TRUST-ANCHOR-ADAPTER-v1`: no shell, setuid, path selector,
ambient-root interface, network operation, or private key on the stand. The
private signing key remains offline. An auditor-owned `0640` allowed-signers
artifact at `/etc/cpu-prefetch/q15/allowed_signers` is verified independently
with OpenSSH SSHSIG. The fixed core receives only bounded read-only regular-file
snapshots inherited on descriptors 3 (authorization core), 4 (detached
signature), and 5 (canonical verification receipt), with respective maximums
1 MiB, 128 KiB, and 128 KiB.

The adapter validates exact hashes, canonical receipt bytes, scheme, namespace,
principal, signer fingerprint, auditor identity, clean release bindings, and
absence of a stand private key. It has one injected read call per descriptor and
no retry or fallback. The repository supplies only a fakeable library seam; the
no-authority CLI remains disabled. Any descriptor, size, trust path, signer,
receipt, privilege, executable, or admission change requires a new ADR, clean
release, and authorization. No scientific semantics change.
