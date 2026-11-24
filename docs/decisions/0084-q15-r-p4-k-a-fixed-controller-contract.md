# ADR-0084: Freeze the no-authority P4-K-A fixed-controller contract

- Status: `ACCEPTED_POLICY_IMPLEMENTATION_REQUIRES_SEPARATE_EXPLICIT_AUTHORITY`
- Date: 2026-08-25
- Decision ID: D-084
- Accepted by: Q15-R-P4-K-A-D, `P4KA-Q5=ACCEPT_D084_D085_RECOMMENDATIONS`
- Decision owners: security, repository, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; specializes ADR-0078
- Lifecycle gate: separate implementation authorization before source changes; clean release before issuance

## Context and options

The accepted P4-K-A template is data, not an executable controller. Options
were a hash-bound no-shell fixed controller, an equivalent independently
reviewed fixed-argv path, an ad hoc shell/retry/unbounded environment, or
remaining blocked.

## Decision

Freeze a repository-owned controller contract with no key-action mode unless a
later exact signed authorization passes. It must execute only an accepted
absolute tool path with fixed argv and environment; accept the passphrase only
through an uncaptured controlling TTY or dedicated non-recorded descriptor;
use create-exclusive public outputs; capture bounded non-secret
stdout/stderr/exit evidence; attempt the action once; retry, repair, overwrite,
and cleanup zero times; and stop before P4-K-R.

The current owner response accepts this policy but does not include the
broader repository-local implementation authorization proposed in the bundle.
Controller, schema, template, and test implementation therefore remain a
separate explicit gate.

## Evidence and effects

- D-084 proposal SHA-256: `8acfebfb22ba7449233b5c4c5b2a7ecf9c9a48323b1d79b45b42d26867199777`.
- Acceptance SHA-256: `c68e1b9427df9306a53cac590dfe268862fa528ef5bf665bf0002972cf77ffaf`.
- No controller implementation or action authority is created.

Scientific effect is none. Future controller bytes, tool path, argv,
environment, descriptor/TTY contract, output bounds, action order, attempt
count, and receipt become transaction identity.

## Verification and supersession

Acceptance checks must reject implementation authority, shell execution,
retry/repair/overwrite/cleanup, key activity, or automatic continuation. Any
future controller byte, tool path, argv, environment, descriptor, secret-input
boundary, output, order, bound, or failure-policy change requires a clean
release and prospective decision.

No protocol amendment is required.
