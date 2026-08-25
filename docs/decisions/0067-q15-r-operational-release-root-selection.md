# ADR-0067: Select the operational release root only from fresh prestate

- Status: `ACCEPTED_METHOD_LITERAL_VALUE_UNRESOLVED`
- Decision ID: D-067
- Accepted by: Q15-R-P4-D on 2026-08-25
- Classification: platform and release engineering
- Owners: platform, release, and controller owners
- Lifecycle gate: after fresh read-only prestate and before transfer/install
- Supersedes: no path; constrains the unresolved ADR-0065 installation input

## Decision

Select one absolute content-addressed stand path only after fresh read-only
prestate proves its parent filesystem, ownership/permissions, and collision
state. The literal path remains null. A mutable path, repository/runbook
default, or inferred platform path is rejected.

Evidence is D-065's exact release identity, the immutable no-overwrite rule,
and the unresolved operational-root token. Scientific effect is none unless
bytes drift, which is forbidden. Compatibility effect is exact: the literal
root and every resolved controller/library path become setup and authorization
identity.

## Authority and supersession

Q15-R-P4-D does not select, create, transfer to, or install into a path.
Selection requires fresh evidence and later owner action. A different path or
release requires a new clean release/path decision and prospective
verification; an issued authorization is never retargeted.
