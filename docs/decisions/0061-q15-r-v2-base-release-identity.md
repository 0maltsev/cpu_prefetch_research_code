# ADR-0061: Bind the clean v2 base release as prerequisite evidence only

- Status: `ACCEPTED_NO_EXECUTION_AUTHORITY`
- Date: 2026-08-25
- Decision ID: D-061
- Classification: clean no-authority release identity
- Decision owners: build, controller, security, and audit owners
- Protocol version: `2.0.0-pre.2`
- Supersedes: no decision; specializes ADR-0057
- Lifecycle gate: before an operational-adapter release or stand setup

## Decision

Bind commit `a75bcdd0367d79f8ee0496c55edda74311c9ef7d` and clean
`Q15-QUALIFICATION-TOOL-BUNDLE-v2` archive SHA-256
`48c460b008790e3b73aefbda94cacddaeb3c842622ca5bac5c763e50515ae035`
as immutable prerequisite evidence. The archive remains authority `NONE`; it is
not the future operational-adapter release and possession never authorizes
stand setup or Q15-R.

The accepted proposal and its release inventory provide the exact source,
archive, sidecar, manifest, SBOM, binary, and code-generation hashes. Any byte,
build, dependency, profile, or authority-boundary drift requires a new clean
release identity and full verification. No protocol amendment is required
because this decision changes no scientific behavior.
