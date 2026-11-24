# ADR-0080: Freeze the P4-K-A offline environment and toolchain contract

- Status: `ACCEPTED_POLICY_EXTERNAL_EVIDENCE_REQUIRED_NO_ENVIRONMENT_ACCESS_AUTHORITY`
- Date: 2026-08-25
- Decision ID: D-080
- Accepted by: Q15-R-P4-K-A-D, `P4KA-Q1=ACCEPT_D080_RECOMMENDATION`
- Decision owners: security, custody, release, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no artifact; specializes ADR-0076
- Lifecycle gate: before controller specialization or any P4-K-A issuance

## Context and options

The accepted source mode requires a new offline Ed25519 ceremony, but no
ceremony environment or executable has been identified. Options were a
dedicated owner-controlled offline Linux/OpenSSH toolchain with exact evidence,
an owner-supplied compatible alternative with independent evidence, an
uninventoried online or stand toolchain, or remaining blocked.

## Decision

Use a dedicated owner-controlled offline Linux environment with a
pre-provisioned OpenSSH-compatible Ed25519 toolchain. A later gate must bind the
non-secret environment identity, OS and tool versions, executable and relevant
library SHA-256 values, exact fixed argv, output compatibility, and evidence
that network interfaces are unavailable during the one authorized action.

This ADR does not select an environment or tool, access or inventory one, or
authorize controller implementation or a ceremony.

## Evidence and effects

- D-080 proposal SHA-256: `8acfebfb22ba7449233b5c4c5b2a7ecf9c9a48323b1d79b45b42d26867199777`.
- Q15-R-P4-K-A-D acceptance SHA-256: `c68e1b9427df9306a53cac590dfe268862fa528ef5bf665bf0002972cf77ffaf`.
- The P4-K-A tool input remains null; no offline inventory exists.

Scientific effect is none. Environment identity, OS/tool/dependency bytes and
versions, network state, fixed argv, and output format become ceremony
identity and compatibility evidence.

## Verification and supersession

Acceptance checks must reject inferred environments, current-host or stand
substitution, non-null external evidence, or widened authority. Any change to
the environment, executable, library, version, network state, argv, or output
format requires a new clean inventory, independent review, and prospective
decision.

No protocol amendment is required because this constrains authorization-key
custody mechanics without changing scientific semantics.
