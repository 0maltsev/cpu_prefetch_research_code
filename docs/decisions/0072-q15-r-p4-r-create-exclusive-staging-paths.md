# ADR-0072: Freeze create-exclusive Q15-R-P4-R staging paths

- Status: `ACCEPTED_REPOSITORY_LOCAL_TEMPLATE_FREEZE_NO_STAND_AUTHORITY`
- Date: 2026-08-25
- Decision ID: D-072
- Accepted by: Q15-R-P4-F
- Decision owners: platform, release, security, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; resolves the literal staging-path method left open by ADR-0067 for P4-R only
- Lifecycle gate: before any v3 archive transfer, stand-directory creation,
  extraction, or collector self-test

## Context and scientific constraints

The clean collector-bearing v3 release is immutable, but its later P4-R
staging location was unresolved. A reusable directory, mutable activation
alias, or premature use of the future operational root would weaken transaction
identity and rollback. The choice is engineering-only and cannot provide
platform qualification or scientific evidence.

## Options considered

1. the exact unique root-owned transaction tree selected below, with
   create-exclusive components and no activation path;
2. a mutable `latest`/`current` alias or reusable directory;
3. the future `/var/lib/cpu-prefetch/q15-r` operational root before fresh
   prestate; or
4. remain blocked.

## Decision

Freeze the stand transaction root
`/root/cpu-prefetch-q15-r-p4-r/Q15-R-P4-R-XEON-CPU-FETCH-20260825-01`
and the exact incoming, archive, sidecar, extraction, release-root, and
collector-executable descendants recorded by the accepted decision bundle.
Every component is future create-exclusive state, mode `0700` where the
transaction directories are created, and must be absent and nonsymlinked.
Reuse, overwrite, activation links, mutable aliases, or promotion into an
operational root are forbidden.

This selects immutable template literals only. It does not create a path or
authorize stand access, transfer, extraction, self-test, collection, cleanup,
or activation.

## Evidence

- Governance commit: `f30036e31acc8ae036f2f31086d493eeb30db9d7`.
- Immutable v3 archive SHA-256:
  `f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a`.
- Decision bundle SHA-256:
  `18c29f6f3710b061bcf593ad6615589a6b50c4bf28ebceb4bee3714702389604`.
- Q15-R-P4-F acceptance SHA-256:
  `ae879bd113939ee06fd3673c0f14d054d92d6c30c0162ffa6727d2a42973cb8c`.

## Consequences and compatibility

Scientific effect is none. Compatibility effect is exact: endpoint, archive
and extraction layout, collector path, mode, collision policy, and absence of
an activation path are transaction identity. A later authorization cannot
retarget them.

## Verification and acceptance tests

Repository checks must reject path, archive, mode, collision, symlink,
activation, authority, or lineage drift. Operational absence, permissions, and
host identity remain future read-only evidence and are not asserted here.

## Rollback or supersession

Any path, layout, archive byte, owner/mode, collision policy, or activation
change requires a prospective decision and a new unused transaction identity.
An existing or partial path is retained and stops the transaction; it is never
silently removed or reused.

## Protocol-amendment assessment

No protocol amendment is required. This ADR freezes an implementation/custody
literal without changing treatment, measurement, calibration, or inference
semantics.
