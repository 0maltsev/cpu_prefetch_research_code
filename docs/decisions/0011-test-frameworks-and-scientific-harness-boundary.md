# ADR-0011: Test frameworks and scientific-harness boundary

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Correctness tooling
- Decision owners: Repository owner; test owner; build owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2; compatibility probes due in Stage 3

## Context and scientific constraints

The repository needs unit, property, deterministic concurrency/refinement, and long stress evidence. Test frameworks must not enter the timed data plane or define scientific iteration behavior.

## Options considered

1. GoogleTest plus RapidCheck, CTest, and repository-owned concurrency/stress executables.
2. Catch2 or a custom unit/property stack.
3. Google Benchmark as the scientific harness.

## Decision

Use GoogleTest for unit tests, RapidCheck for property tests after a current-toolchain compatibility probe, CTest for orchestration, and repository-owned deterministic/refinement/stress executables. GoogleTest and RapidCheck are test-only dependencies. No Google Benchmark control loop is used for the scientific harness.

## Evidence

The repository owner accepted Q1 on 2026-08-17. GoogleTest documents CMake integration; RapidCheck supplies property generation/shrinking but still requires the accepted compatibility and license/provenance probes.

## Consequences and compatibility

Scientific effect: none; all randomized tests use test-only recorded seeds. Compatibility effect: Stage 3 must pin dependency versions/hashes/licenses and prove both toolchain matrices or record a supported subset with explicit evidence.

## Verification and acceptance tests

Run minimal tests, a deliberately failing test, property generation/shrinking, recorded-seed replay, sanitizer integration, and offline dependency recreation in Stage 3.

## Rollback or supersession

A framework change requires a superseding engineering ADR with equivalent behavioral coverage, replay, sanitizer, provenance, and clean-room evidence.

## Protocol-amendment assessment

No amendment is required.
