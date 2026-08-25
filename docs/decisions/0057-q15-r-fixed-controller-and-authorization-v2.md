# ADR-0057: Use one fixed Q15-R controller and authorization-v2 graph

- Status: `ACCEPTED_FOR_REPOSITORY_LOCAL_IMPLEMENTATION_NO_AUTHORITY`
- Date: 2026-08-24
- Decision ID: D-057
- Classification: qualification controller and authorization-format engineering
- Decision owners: controller, platform, security, custody, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no scientific decision; specializes ADR-0051 and ADR-0054
- Lifecycle gate: before a controller-bearing clean release and Q15-R issuance

## Context and options

Q15-S3 contains the fixed components but intentionally has no production
command that starts the phase-spanning session and collectors. Ad-hoc shell
orchestration, runtime-selectable collection, one fixed controller, and stand
ineligibility were considered.

## Decision

Q15-R-P1 selects `Q15-R-STATIC-CONTROLLER-v1` and
`cpu-prefetch-q15-qualification-authorization/2`. The only production entry is
`cpu_prefetch_q15_controller --execute-q15-r` with one exact canonical signed
record. The controller executes the accepted graph in order, accepts no
scientific or arbitrary platform selector, retains partial evidence, never
retries, and leaves the same private mapping alive only for a separately
authorized Q15-W or expiry.

Scientific effect: none; only qualification evidence is acquired.
Compatibility effect: graph, controller binary/CLI, transport, canonical
records, and output contract are qualification identity.

## Authority and supersession

Q15-R-P1 authorizes repository-local implementation, fake tests, sanitizers,
code-generation audit, and non-authorizing setup artifacts only. It grants no
stand or execution authority. Any graph, transport, CLI, same-buffer, or
authorization-format change requires a new ADR, clean release, and
requalification; scientific changes require protocol review.
