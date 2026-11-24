# ADR-0064: Fail setup closed with complete access evidence and quarantine

- Status: `ACCEPTED_POLICY_NO_PROBE_OR_Q15_AUTHORITY`
- Date: 2026-08-25
- Decision ID: D-064
- Classification: negative access, rollback, and phase-authority boundary
- Decision owners: security, platform, custody, audit, and protocol owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no decision; specializes ADR-0059 and ADR-0060
- Lifecycle gate: before setup execution and again before Q15-R issuance

## Decision

Require all 24 role/target probes, including exactly 18 denials. Stop on the
first mismatch, preserve the completed prefix and all evidence, perform only
the applicable reverse-prefix lock/quarantine operations, and delete nothing.
Quarantine is not a claim of complete prestate restoration. Any failure requires
a new authorization; successful setup still does not authorize Q15-R.

Q15-R-P2 authorizes neither the probes nor setup execution. Any matrix,
expected result, rollback, deletion, retry, evidence, or authority change needs
a new prospective decision. The policy has no scientific effect and requires no
protocol amendment.
