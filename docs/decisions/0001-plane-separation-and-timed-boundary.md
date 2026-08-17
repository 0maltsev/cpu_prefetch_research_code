# ADR-0001: Plane separation and timed boundary

- Status: `ACCEPTED`
- Date: 2026-08-17
- Classification: Architecture / scientific-integrity preserving
- Decision owners: Repository owner; implementation maintainer
- Protocol version: `2.0.0-pre.1`
- Supersedes: None
- Lifecycle gate: Stage 2; required before Stage 3

## Context and scientific constraints

The protocol fixes timestamp boundaries and forbids unplanned allocation, blocking I/O, console logging, dynamic parsing, and analysis in the measurement loop. The Stage 2 task explicitly requires separate benchmark data-plane, experiment-controller, and offline-analysis planes.

## Options considered

1. Interleave measurement, orchestration, persistence, and analysis.
2. Three architectural planes with a closed prepared run image and immutable artifact handoff.

## Decision

Adopt option 2. The data plane owns only the protocol-defined producer and consumer work plus private fixed-capacity observation writes. Configuration/schema parsing, allocation, console logging, whole-artifact hashing, compression, reconciliation, and analysis occur before or after the timed horizon. This decision does not yet choose the executable/process topology.

## Evidence

- `EXPERIMENT_IMPLEMENTATION_SPEC.md` sections 6, 7, 12, 16, 19, and 20.
- `PROTOCOL_FREEZE_CHECKLIST.md` measurement-boundary and raw-data checks.
- Explicit architecture requirements in the Stage 2 task.

## Consequences and compatibility

Scientific effect: preserves fixed event/timestamp semantics and reduces observer work in the measured path; it changes no treatment or estimand. Compatibility effect: future modules must exchange a versioned prepared run image and immutable artifacts instead of making in-loop service calls. The separate recommendation about whether a generic benchmark framework may own the scientific control loop remains D-004/Q1 and is not accepted here.

## Verification and acceptance tests

Call-graph and generated-code checks must prove the timed allowlist. Negative tests must detect allocation, I/O, logging, parsing, and analysis reachable from the timed entry points. Queue-binding dispatch is governed separately by D-023 and Q2.

## Rollback or supersession

Only a later accepted ADR may refine plane deployment. Moving prohibited work into the timed loop requires a versioned protocol amendment before supersession.

## Protocol-amendment assessment

No amendment is required; this realizes explicit protocol constraints.
