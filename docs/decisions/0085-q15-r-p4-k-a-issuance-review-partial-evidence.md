# ADR-0085: Freeze P4-K-A issuance, review, and partial-evidence governance

- Status: `ACCEPTED_POLICY_LITERAL_ISSUANCE_AND_REVIEW_EVIDENCE_REQUIRED`
- Date: 2026-08-25
- Decision ID: D-085
- Accepted by: Q15-R-P4-K-A-D, `P4KA-Q5=ACCEPT_D084_D085_RECOMMENDATIONS`
- Decision owners: protocol, security, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; specializes ADR-0078 and ADR-0079
- Lifecycle gate: before P4-K-A issuance and execution

## Context and options

Policy must distinguish accepted mechanics from literal authority. Options
were distinct pre-execution review and an exact nonrenewable 1,800-second
SSHSIG action with append-only partial evidence, a stronger compatible policy,
unsigned/renewable/self-reviewed/delete-on-failure continuation, or remaining
blocked.

## Decision

Require canonical unsigned authorization bytes bound to every accepted
environment, tool, controller, path, custody, and bootstrap input; a distinct
auditor pre-execution review; literal issue and expiry instants exactly 1,800
seconds apart; OpenSSH SSHSIG signature and hash verification; first-failure
stop; append-only complete or partial public receipts; no deletion, cleanup,
repair, or retry; and a mandatory stop for separately authorized P4-K-R.

No literal time, signer, authorization bytes, signature, review, or receipt is
selected, created, or issued. The missing bootstrap root independently blocks
issuance.

## Evidence and effects

- D-085 proposal SHA-256: `8acfebfb22ba7449233b5c4c5b2a7ecf9c9a48323b1d79b45b42d26867199777`.
- Acceptance SHA-256: `c68e1b9427df9306a53cac590dfe268862fa528ef5bf665bf0002972cf77ffaf`.
- Every UTC, authorization, signature, and auditor-review input remains null.

Scientific effect is none. Canonical authorization bytes/hash, exact UTC
instants, signer fingerprint, detached-signature hash, review hash, partial or
complete receipt, and stop disposition become action identity.

## Verification and supersession

Checks must reject renewable or reused windows, self-review, unsigned or
self-authorized action, missing input bindings, cleanup/retry, automatic
continuation, or issuance authority. Any authority, duration,
canonicalization, signer, review, failure, retention, retry, cleanup, or
continuation change requires new canonical bytes and prospective acceptance.

No protocol amendment is required.
