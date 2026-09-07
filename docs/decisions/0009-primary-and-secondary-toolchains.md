# ADR-0009: Primary and secondary toolchains

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Compiler / standard-library compatibility
- Decision owners: Repository owner; build owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2 families; exact pins and flags due in Stage 3

## Context and scientific constraints

Compiler and standard-library selection affects atomics, ABI, sanitizer availability, and measured generated code. One matrix must produce the eventual frozen measurement build while an independent matrix detects compiler-sensitive defects.

## Options considered

1. GCC with libstdc++ only.
2. Clang with libc++ only.
3. GCC/libstdc++ primary plus Clang/libc++ secondary.
4. Mixed standard-library object linkage.

## Decision

Use GCC 16.x with libstdc++ as primary and Clang 22.x with libc++ as secondary. Do not mix C++ objects built against the two standard libraries in one executable. Stage 3 pins exact patch versions, linker, flags, presets, and dependency ABI; only one later frozen release matrix may produce empirical measurements.

## Evidence

The repository owner accepted Q1 on 2026-08-17. The development environment exposes GCC 16.1.1 and Clang 22.1.6, while official toolchain documentation provides C++20 and sanitizer capability subject to clean probes.

## Consequences and compatibility

Scientific effect: the secondary matrix provides correctness evidence, not an additional treatment. Compatibility effect: C++ ABI artifacts do not cross the standard-library boundary; persisted artifact formats do.

## Verification and acceptance tests

Stage 3 must pass clean C++20, standard-library identity, linker, sanitizer, atomic, warning, and minimal dependency probes in both matrices and record exact versions/hashes.

## Rollback or supersession

Toolchain-family changes require a superseding ADR and full clean-room, sanitizer, generated-code, atomic, artifact, and correctness requalification.

## Protocol-amendment assessment

No amendment is required; empirical use still requires a prospectively frozen build.
