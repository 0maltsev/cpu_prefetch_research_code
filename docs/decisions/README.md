# Architecture Decision Records

Use an ADR for every engineering decision that can affect scientific interpretation, reproducibility, compatibility, data identity, the measured path, or a lifecycle gate. Recommendations in `docs/IMPLEMENTATION_DECISIONS.md` are not decisions until an approved ADR records them.

## Naming and status

Name records `NNNN-short-title.md`. Never rewrite the history of an accepted decision. If a decision changes, add a new ADR that supersedes the old one and identify whether a protocol amendment is also required.

Allowed statuses are `PROPOSED`, `ACCEPTED`, `REJECTED`, and `SUPERSEDED`. Only `ACCEPTED` freezes a choice.

## Template

```text
# ADR-NNNN: Title

- Status:
- Date:
- Decision owners:
- Protocol version:
- Supersedes:
- Lifecycle gate:

## Context and scientific constraints
## Options considered
## Decision
## Evidence
## Consequences and compatibility
## Verification and acceptance tests
## Rollback or supersession
## Protocol-amendment assessment
```

An ADR must not use confirmatory outcomes to settle an open decision. If the choice changes a protocol-fixed behavior, stop implementation and obtain a versioned protocol amendment first.

## Index

| ADR | Status | Decision |
|---|---|---|
| [ADR-0001](0001-plane-separation-and-timed-boundary.md) | `ACCEPTED` | Separate the benchmark data plane, experiment controller, and offline analysis; keep non-measurement work outside the timed loop. |
| [ADR-0002](0002-logical-model-and-replaceable-physical-storage.md) | `ACCEPTED` | Preserve the imported logical data model behind replaceable codec and storage interfaces. |
| [ADR-0003](0003-semantics-preserving-queue-adapters.md) | `ACCEPTED` | Use queue adapters without erasing algorithm-specific semantics. |
| [ADR-0004](0004-artifact-versioning-and-compatibility.md) | `ACCEPTED` | Version physical formats and reject unknown or incompatible artifacts. |
| [ADR-0005](0005-append-only-partial-failure-lifecycle.md) | `ACCEPTED` | Make append-only artifacts and partial failures first-class. |
| [ADR-0006](0006-structural-and-semantic-validation.md) | `ACCEPTED` | Separate Draft 2020-12 structural validation from cross-record semantic validation. |

Open recommendations are deliberately kept in `docs/IMPLEMENTATION_DECISIONS.md` and `docs/DECISIONS_REQUIRED.md`; they do not become frozen merely by being documented.
