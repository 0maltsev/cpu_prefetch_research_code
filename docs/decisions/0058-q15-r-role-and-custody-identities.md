# ADR-0058: Freeze Q15 role and custody identifiers

- Status: `ACCEPTED_POLICY_NO_STAND_SETUP_AUTHORITY`
- Date: 2026-08-24
- Decision ID: D-058
- Classification: least-privilege identity and two-domain custody engineering
- Decision owners: security, platform, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no decision; completes the identifiers left open by ADR-0050
- Lifecycle gate: before role/custody setup and Q15-R issuance

## Decision

Q15-R-P1 freezes principal IDs `cpu-prefetch-q15-operator`,
`cpu-prefetch-q15-controller`, `cpu-prefetch-q15-custodian`, and
`cpu-prefetch-q15-auditor`. The proposed primary domain is
`XEON-CPU-FETCH-MD3-Q15-CUSTODY`, the secondary is
`DEVELOPMENT-REPOSITORY-Q15-CUSTODY`, and the scoped primary root is
`/var/lib/cpu-prefetch/q15-r`. Append-only, transfer, partial-artifact, and
recovery policy IDs are exactly those in the accepted decision record.

Shared credentials and same-domain custody are forbidden. Actual accounts,
keys, groups, capabilities, permissions, paths, quotas, negative access tests,
and transfer receipts remain missing evidence; Q15-R-P1 does not authorize
creating or changing them.

Scientific effect: none. Every effective identity, credential, permission,
domain, path, quota, and policy becomes authorization identity. Any change
requires fresh prospective authority and negative evidence.
