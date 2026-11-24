# ADR-0101: Permit only the verified D-099 custody root for P4-R-C

- Status: `ACCEPTED_REPOSITORY_LOCAL_IMPLEMENTATION_ONLY_NO_ACTION_AUTHORITY`
- Date: 2026-08-26
- Decision ID: D-101
- Accepted by: owner response bound to decision-input SHA-256 `faa4c377...`
- Owners: custody, repository, security, and audit owner
- Protocol version: `2.0.0-pre.2`
- Lifecycle gate: executor implementation before P4-R-C output creation

## Context and options

D-099 correctly created the frozen custody root and predecessor files. The old
template's broad absence wording would otherwise make its required successor
impossible. Options were a new capture identity, exact predecessor-root
compatibility, or remaining blocked.

## Decision and effects

Permit only the exact D-099 root with the verified predecessor files. Require
every P4-R-C stdout, stderr, sidecar, receipt, review, and failure destination
to be absent and create-exclusive. Any unexpected entry, symlink, overwrite,
rename, reuse, cleanup, or deletion stops. Partial output consumes the identity.

Scientific effect is none. Exact root, predecessor inventory and hashes, new
output names, and collision policy become compatibility identity. No file may
be created until a later exact signed action is approved.

## Verification and supersession

Fake-backend and semantic tests must reject missing or changed predecessors,
extra entries, existing outputs, symlinks, retries, and cleanup. Any path,
inventory, or collision change requires a new capture identity and ADR.
