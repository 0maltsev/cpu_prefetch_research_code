# ADR-0003: Semantics-preserving queue adapters

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Data-plane architecture
- Decision owners: Repository owner; queue implementation owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2; provenance and atomic mapping still block queue implementation

## Context and scientific constraints

The protocol fixes distinct ring and linked-plus-recycler packages, linearization boundaries, one-attempt full behavior, memory-order intent, prefetch sites, and bounded-arena behavior. A common API must not normalize those differences.

## Options considered

1. One normalized queue abstraction that hides algorithm differences.
2. Separate drivers with duplicated scheduling and observation logic.
3. A narrow common behavioral seam with package semantics remaining visible and independently reviewed; static templates, separate binaries, or direct binding remain possible realizations.

## Decision

Adopt option 3 as the architecture. Adapters expose one-attempt enqueue/dequeue outcomes and boundary hooks but retain package-specific full, prefetch, recycler, memory-order, and linearization behavior. This ADR does not select source provenance, implementation mode, or static/dynamic binding mechanism; those require explicit acceptance and generated-code evidence before the data plane is implemented.

## Evidence

- Implementation-spec sections 4-7 and Appendix A.
- Explicit Stage 2 requirement that adapters not hide algorithm-specific semantics.

## Consequences and compatibility

Scientific effect: preserves treatment identity and timestamp meaning. Compatibility effect: every bound adapter needs its own semantic/refinement proof and generated-code evidence; an API-compatible replacement is insufficient if its behavior differs.

## Verification and acceptance tests

Model/refinement tests, boundary timestamp tests, full/recycler-exhaustion tests, generated-code checks, and negative fixtures for semantic normalization are required before queue acceptance. ADR-0012 supplies binding-specific checks.

## Rollback or supersession

ADR-0012 selects the binding mechanism; a later superseding ADR may refine it. Any normalization of protocol-fixed queue behavior requires a protocol amendment.

## Protocol-amendment assessment

No amendment is required.
