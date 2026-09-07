# ADR-0018: Unprivileged measurement and platform-control boundary

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Privilege / platform control
- Decision owners: Repository owner; platform owner; security owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2 boundary; operational authority due before Phase 9

## Context and scientific constraints

Platform actuation may require privilege, while measurement must avoid control work/interference and the protocol requires requested/verified separation, readback, behavioral probes, audit, least privilege, and rollback.

## Options considered

1. Privileged benchmark process.
2. Unprivileged measurement with a narrow external service.
3. Unprivileged measurement with an authorized operator/runbook.

## Decision

The measurement process is always unprivileged. Platform actuation occurs only before/after the timed horizon through a narrow audited service or authorized operator with whitelisted operations, independent readback/probes, and failure-safe rollback. Unsupported or unauthorized capability fails closed.

## Evidence

The repository owner accepted Q3 on 2026-08-17. The protocol separates requested and verified state and requires authority/readback rather than inferred control.

## Consequences and compatibility

Scientific effect: avoids privileged control activity in measurement and prevents requested state from becoming evidence. Compatibility effect: deployment needs an external authority interface; missing authority makes the stand ineligible.

## Verification and acceptance tests

Prove the measurement process lacks control capabilities, reject unauthorized/partial operations, test readback/probe mismatch, audit every request/result, and exercise rollback and rollback-failure paths.

## Rollback or supersession

An authority mechanism change requires a superseding ADR and repeated least-privilege, audit, readback, negative-access, and rollback tests.

## Protocol-amendment assessment

No amendment is required.
