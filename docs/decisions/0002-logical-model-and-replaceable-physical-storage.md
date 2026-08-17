# ADR-0002: Logical model and replaceable physical storage

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Data architecture / compatibility
- Decision owners: Repository owner; implementation maintainer
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2; physical codec still blocks pilot readiness

## Context and scientific constraints

The imported schemas and data dictionary fix logical fields and relationships but deliberately leave the physical raw encoding open until its exact sizes and decoder behavior can be demonstrated.

## Options considered

1. Embed one physical row layout throughout the benchmark and analysis code.
2. Preserve a typed logical model behind replaceable physical codec and artifact-store interfaces.
3. Serialize schema-shaped documents directly in the timed loop.

## Decision

Adopt option 2. Producer, consumer, manifest, failure, access, and derived records retain the imported logical meaning. A codec maps fixed-capacity physical rows to that model, and an artifact store handles immutable envelopes and content identity. No physical binary, columnar, textual, endianness, compression, or copy choice is accepted by this ADR.

## Evidence

- Imported `DATA_DICTIONARY.md`, seven Draft 2020-12 schemas, and implementation-spec sections 16 and 20.
- Explicit Stage 2 requirement to preserve the logical model and keep physical encoding replaceable.

## Consequences and compatibility

Scientific effect: none; the logical observations remain fixed. Compatibility effect: every physical format needs an explicit version, exact decoder, fixtures, and a compatibility rule. The timed writer may use a fixed representation only after the physical-format decision is accepted.

## Verification and acceptance tests

Each future codec must round-trip boundary fixtures exactly, reject truncation/trailing rows/corruption, and reproduce logical records across supported toolchains. Capacity proofs use the selected physical size, not logical-field estimates.

## Rollback or supersession

A later ADR may select or add a codec without changing the logical interface. Changing a normative logical field or meaning requires a versioned protocol amendment.

## Protocol-amendment assessment

No amendment is required.
