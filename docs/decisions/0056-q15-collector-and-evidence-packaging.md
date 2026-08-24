# ADR-0056: Package seven fixed Q15 collectors with distinct evidence

- Status: `ACCEPTED_AND_IMPLEMENTED_REPOSITORY_LOCAL_NO_AUTHORITY`
- Date: 2026-08-24
- Decision ID: D-056
- Classification: qualification tooling, evidence, and least privilege
- Decision owners: platform, timing, queue, compiler, security, custody, and
  audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no accepted decision
- Lifecycle gate: before a clean qualification-tool release and Q15-R

## Context and options

D-052 freezes seven collector IDs and separate acceptance rules. Options were
unrelated helpers/ad-hoc output, a general runtime-selectable collector, fixed
components in the separate Q15 tool, or reuse of the measurement runner.

## Decision

Select fixed components in the separate `cpu_prefetch_q15_tool`, exactly as
specified in the [Q15-S3 bundle](../Q15_DYNAMIC_IMPLEMENTATION_DECISION_BUNDLE.md).
All seven IDs remain separate canonical evidence kinds. Sharing a release
binary cannot merge their rules or let a caller manufacture eligibility with
`passed=true` inputs. CPU/residency observations come from the concrete
operation; atomic/layout and software-prefetch evidence inspect the linked
profiles; MSR readback remains an independent auditor operation.

Evidence is emitted as `Q15-CANONICAL-U32BE-LENGTH-PREFIXED-FRAME-v1` frames
(one unsigned 32-bit big-endian length and exact JCS-I64-v1 payload) to
authorization-bound external
custody. Q15-W creates new artifacts referencing sealed Q15-R hashes. Partial
frames/failures remain incomplete and cannot become eligible evidence. The
tool has no scientific schedule, namespace, outcome, calibration, pilot,
measurement, analysis, or confirmatory command.

## Evidence and effects

Evidence is ADR-0051, D-052, existing canonical evidence infrastructure, and
explicit Q15-S3 acceptance. Scientific effect is none. Binary/command,
collector/evidence schema, linked layout/codegen reports, frame protocol, and
partial-failure grammar are compatibility identity.

## Verification and supersession

Fake tests pass all seven distinct collectors, caller-assertion rejection,
canonical framing, partial failures, and no-authority packaging. The linked
tool self-test verifies the exact seven-component registry.
Changing packaging, observation source, canonicalization, or partial semantics
requires a new ADR, clean bundle, and requalification. Scientific changes
require protocol review.
