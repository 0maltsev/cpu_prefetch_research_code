# ADR-0010: CMake, Ninja, and offline dependency policy

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Build / dependency provenance
- Decision owners: Repository owner; build owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2; implementation commands due in Stage 3

## Context and scientific constraints

The build must be reproducible from recorded inputs, preserve dependency provenance/licenses, and make every measured binary traceable. The scientific harness control loop cannot be delegated to a convenience benchmarking framework.

## Options considered

1. CMake with Ninja and locked offline inputs.
2. Meson or direct Make.
3. Configure-time network fetching.
4. Google Benchmark or equivalent owning the scientific measurement loop.

## Decision

Use CMake plus Ninja, checked-in presets/toolchain descriptions, network-disabled configure/build/test, and immutable hashes/licenses for every dependency. Google Benchmark or another generic benchmark-framework control loop may be used only for labeled developer microtests and must not own the scientific harness.

## Evidence

The repository owner accepted Q1 on 2026-08-17. CMake officially supports the Ninja generator; the protocol and repository require clean-room reproduction, dependency provenance, and controlled measurement boundaries.

## Consequences and compatibility

Scientific effect: none if build products and harness boundaries pass review. Compatibility effect: builds fail closed on missing/unrecorded dependencies and do not depend on network state.

## Verification and acceptance tests

Stage 3 must demonstrate network-disabled configure/build/test, dependency/license inventory, deterministic configuration, nonzero failures, and clean-environment recreation from tracked inputs.

## Rollback or supersession

A build-system or dependency-policy change requires a superseding ADR and equivalent offline/provenance/clean-room evidence. Changed measured binaries require requalification.

## Protocol-amendment assessment

No amendment is required.
