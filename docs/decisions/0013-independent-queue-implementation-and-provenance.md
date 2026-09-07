# ADR-0013: Independent queue implementation and provenance

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Queue provenance / implementation mode
- Decision owners: Repository owner; provenance owner; queue owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2 mode; repository SPDX license still blocks production source; refinement evidence blocks Phase 5 acceptance

## Context and scientific constraints

The protocol requires each queue to identify the primary paper, official-artifact status, reuse/adaptation/independent mode, applicable reused-code license, semantic adaptations, memory mapping, claim boundary, and refinement evidence before source is implemented.

## Options considered

1. Reuse an exact official artifact unchanged.
2. Adapt licensed official source.
3. Independently implement from the cited Torquati report plus frozen protocol.

## Decision

Select option 3 for both Stage A queues. No FastFlow queue source may be imported, adapted, mechanically translated, or consulted as implementation text. Record the current author-maintained FastFlow project only as an official-artifact search result; do not claim it is the exact 2010 paper artifact. A future reuse/adaptation proposal requires a new ADR with exact artifact, immutable hash, applicable license, and semantic map.

The repository source-license SPDX identifier is not supplied by this ADR and remains the sole Stage 2 owner decision before production files may be created.

## Evidence

The repository owner accepted Q2 on 2026-08-17. The cited Torquati report is available from arXiv/University of Pisa. A current author-maintained FastFlow repository exists and states current licensing, but no immutable mapping to the exact historical paper artifact was established. No third-party queue code was downloaded or reused.

## Consequences and compatibility

Scientific effect: independent code must refine the protocol-declared algorithms and bounded adaptation exactly; independence grants no freedom to alter queue semantics. Compatibility effect: third-party queue ABI/source is absent, while clean-room notes, paper-to-source mapping, project license, and stronger refinement tests become mandatory.

## Verification and acceptance tests

Before queue source, record the repository SPDX license and clean-room procedure. Phase 5 requires source-to-paper/protocol mapping, semantic adaptation list, abstract FIFO/refinement histories, sanitizer/stress evidence, atomic proof, and provenance review showing no imported third-party queue code.

## Rollback or supersession

Reuse or adaptation requires a superseding provenance ADR before any source enters the repository. Queue semantic changes require protocol review and normally an amendment.

## Protocol-amendment assessment

No amendment is required for independent implementation of the fixed algorithms.
