# ADR-0063: Require the exact four-role and two-domain setup transaction

- Status: `ACCEPTED_POLICY_NO_STAND_SETUP_AUTHORITY`
- Date: 2026-08-25
- Decision ID: D-063
- Classification: four-role and two-domain stand setup transaction
- Decision owners: security, platform, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no decision; specializes ADR-0058
- Lifecycle gate: before any stand account, key, path, permission, or install change

## Decision

Retain four distinct system principals—operator, controller, custodian, and
auditor—and two distinct custody domains. Use the accepted literal-argv setup
graph and complete access matrix. Root or shared credentials cannot substitute
for the roles. Unresolved release, signer, secondary-domain, and current-prestate
facts must become hash-bound literals in a later exact setup authorization.

Q15-R-P2 authorizes only repository-local preparation. It creates no account,
group, key, path, permission, trust anchor, or custody evidence. Any role, group,
path, mode, device, quota, domain, credential, or access-matrix change requires
a new prospective setup record and fresh evidence. No protocol amendment is
required because the transaction is qualification governance only.
