# ADR-0007: C++20 implementation language

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Language / data-plane implementation
- Decision owners: Repository owner; implementation owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2; required before Stage 3

## Context and scientific constraints

The implementation must express the protocol's release/acquire mappings, fixed-capacity ownership, alignment, exact integer data, and inspectable generated code without adding runtime work to the measured path.

## Options considered

1. C++20.
2. Rust with an explicitly reviewed unsafe/atomic boundary.
3. C with platform/compiler atomics and more manual infrastructure.

## Decision

Use C++20 for the benchmark data plane and controller-facing implementation core. Offline artifact consumers may use other languages only through the versioned artifact contract. This ADR does not select exact compiler versions or prove target atomic lock freedom.

## Evidence

The repository owner accepted Q1 on 2026-08-17. The C++20 atomic model expresses the required release/acquire relationships, and the candidate GCC/Clang toolchains provide the required language and sanitizer capability for Stage 3 probes.

## Consequences and compatibility

Scientific effect: none if the protocol mapping and generated-code gates pass. Compatibility effect: production C++ requires C++20; external tools consume versioned artifacts rather than C++ ABI objects.

## Verification and acceptance tests

Stage 3 must compile strict C++20 probes under both accepted toolchain matrices, reject unapproved extensions in portable core code, and establish sanitizer and atomic capabilities before dependent work.

## Rollback or supersession

A later ADR may add or replace an implementation language only with complete atomic, artifact, generated-code, sanitizer, and clean-room equivalence evidence.

## Protocol-amendment assessment

No amendment is required; the language realizes rather than changes protocol behavior.
