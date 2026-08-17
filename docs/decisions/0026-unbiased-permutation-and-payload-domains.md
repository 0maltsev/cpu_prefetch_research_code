# ADR-0026: Unbiased permutation and payload domains

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Working-set order / deterministic payload construction
- Decision owners: Repository owner; reproducibility owner
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 6 implementation; accepted as Q5

## Context and scientific constraints

The protocol requires independent, treatment-blind permutations for the common
event arena and linked-node arena. It also requires immutable payloads generated
before warm-up and forbids outcome-dependent record selection. Modulo reduction
of arbitrary draws can bias Fisher-Yates choices.

## Options considered

1. Modulo-reduced Fisher-Yates.
2. Sorting by random keys.
3. Descending Fisher-Yates using unbiased 64-bit rejection sampling.

## Decision

Select option 3. For bound `n`, reject draws below `(-n) mod n` in unsigned
64-bit arithmetic, then use `draw mod n`. Fisher-Yates visits indices from the
last element to index one. Event-order and node-order streams use distinct
ADR-0025 purpose labels.

Physical event record `k` stores record index `k` and draw `k` from the separate
event-payload stream. The initial consumer state is draw zero from its own
purpose stream. Logical arrivals cycle the complete event-index permutation;
logical sequence and accepted ordinal remain distinct types and neither is
stored in a record.

## Evidence

- Owner acceptance of Q5 on 2026-08-17.
- Imported implementation specification Sections 3.1, 3.3, 4.1, and 11.1.
- ADR-0025 deterministic stream mapping.

## Consequences and compatibility

Scientific effect: order and payload bits are fixed prospectively and remain
independent of outcomes and package. Compatibility effect: shuffle direction,
rejection threshold, draw consumption, purpose labels, and complete golden
vectors form the algorithm identity. No concrete seed or platform capacity is
selected.

## Verification and acceptance tests

Golden orders, boundary bounds, generated-permutation bijection, deterministic
repeatability, stream-domain separation, repeated cyclic record indices, and
invalid capacity rejection are required across both compiler/library families.

## Rollback or supersession

Any draw-consumption or permutation change requires a new version and
prospective regeneration. Frozen orders and payloads are immutable.

## Protocol-amendment assessment

No amendment is required; this selects a conforming prospective generator
without changing the registered working-set semantics.
