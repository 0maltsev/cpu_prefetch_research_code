# ADR-0017: Sanitizer and correctness acceptance

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Correctness gate
- Decision owners: Repository owner; test owner; queue correctness owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2 policy; applicable gates pass before dependent phase/pilot

## Context and scientific constraints

Repository policy requires correctness before measurement, targeted tests for behavior changes, relevant sanitizers, deterministic concurrency evidence, and no empirical claims from instrumented/development runs.

## Options considered

1. ASan/UBSan only.
2. TSan only.
3. ASan+UBSan and TSan where the selected matrix is supported, plus deterministic refinement and recorded-seed stress.
4. Stress testing without sanitizers.

## Decision

Adopt option 3 for both supported toolchain matrices where compatible. Acceptance is zero unresolved findings. No unreviewed suppression is permitted; each suppression or unavailable combination needs a named owner, exact scoped rationale, compensating evidence, and expiry/review gate. Sanitizer results are correctness evidence only.

## Evidence

The repository owner accepted Q2 on 2026-08-17. This implements the root repository rule and the protocol's correctness-before-measurement gate.

## Consequences and compatibility

Scientific effect: none; instrumented builds never produce empirical performance evidence. Compatibility effect: separate instrumented configurations and toolchain-specific availability records are required.

## Verification and acceptance tests

Stage 3 proves minimal sanitizer execution. Later phases run targeted unit/property/refinement/stress suites under all applicable sanitizers and retain reports, seeds, incompatibilities, and suppression records.

## Rollback or supersession

A weaker matrix requires a superseding ADR with risk review and equal-or-stronger compensating correctness evidence; failed findings cannot be waived to collect data.

## Protocol-amendment assessment

No amendment is required.
