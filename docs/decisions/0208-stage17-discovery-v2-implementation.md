# ADR-0208: Versioned implementation of accepted D207 discovery

- Status: `ACCEPTED` — engineering application of explicit D207 approval
- Date: 2026-11-03
- Scientific authority: [D207](0207-stage17-ext007-discovery-duration-revision.md)
- Protocol snapshot: `2.0.0-pre.3/`, unchanged

The new plan/2 and D207 design identity select the approved 1/2/5-second grid.
The v1 selector, plan schema, contract and retained validator remain readable
under their original versions. Native parsing and cold layout description
provide explicit v2 entry points; the old entry points keep their old grid.
The full worker selects semantics by exact plan version and design identity,
never by guessing a duration. The new plan explicitly identifies D207 and
D206's stand-primary custody, with 30-million-attempt buffers in both phases.

Controller24, executor9, output registry10 and retained validator2 bind the
new plan and preserve the existing fixed-deadline, integrity, monitoring,
publication, restoration and no-retry gates. Native capture loops, raw codecs,
control/hardware records and retention-report layout do not change. Their
existing schema identities remain valid because the exact plan hash binds
the selected design. The seven-action runtime profile v4 and diagnostic
action envelope v5 likewise retain their existing structure and capability
surface; a newly qualified source-bound worker is still mandatory.

Policy57, preflight31, journal51, CLI17 and the new bundle profile provide an
explicit current admission path, preserving predecessor policy bytes. Current
entry points activate the current journal after historical import side effects.
The release verifier requires the successor's native v2 sizing capability.
No old release is inferred to support the amended design from its action list.

Verification must cover both grids, cross-version rejection, the distinction
between trace-capacity insufficiency and mandatory failure, signed lifecycle
lineage and restoration, retained count-only selection, policy/runtime closure,
native layout dispatch, relevant sanitizer matrices and strict release gates.
Synthetic checks contribute no empirical observations. Actual execution still
requires D207's finite scope and exact admitted authority; this engineering
record grants no additional invocation.
