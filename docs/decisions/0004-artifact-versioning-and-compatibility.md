# ADR-0004: Artifact versioning and compatibility

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Artifact identity / compatibility
- Decision owners: Repository owner; data-format owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2; concrete formats remain pre-pilot work

## Context and scientific constraints

Append-only raw sources, exact cross-record identities, versioned schemas, and independently reproducible validation require readers to know which semantics and bytes they are interpreting.

## Options considered

1. Infer format from filenames or row sizes.
2. One unversioned format that evolves in place.
3. Explicit protocol-schema version, artifact-kind version, physical-format version, algorithm-suite identifiers, and declared compatibility.

## Decision

Adopt option 3. Readers reject unknown major versions and unknown algorithm/format identifiers. Additive backward-compatible changes require an explicit compatibility declaration and fixtures; incompatible changes use a new version and converter that emits a new derived artifact while retaining the source. Artifact IDs are immutable and never reused for changed bytes.

## Evidence

- Imported protocol version record, data dictionary, schemas, access/sealing protocol, and implementation-spec section 20.
- Explicit Stage 2 artifact-versioning requirement.

## Consequences and compatibility

Scientific effect: prevents silent reinterpretation; no estimand changes. Compatibility effect: producers and consumers negotiate documented versions, converters are provenance-bearing transformations, and unsupported data fail closed.

## Verification and acceptance tests

Golden current-version fixtures, rejected-future-version fixtures, converter lineage tests, byte-change/ID-change tests, and cross-tool decoding are required.

## Rollback or supersession

This policy may be tightened by a later ADR. Relaxing fail-closed interpretation needs an explicit compatibility and scientific-impact review.

## Protocol-amendment assessment

No amendment is required unless logical scientific meaning changes.
