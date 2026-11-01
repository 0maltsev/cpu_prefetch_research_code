# ADR-0185: Preserve the complete source context of historical policy tests

- Status: `ACCEPTED`
- Date: 2026-11-02
- Decision ID: D-185
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: local regression-test fixture selection; no operational authority

The restored accepted runtime reproduces four legacy policy-18 regression
failures. Their original policy binds schema/source bytes from its historical
tree. Later accepted engineering changes widened a current schema, so replaying
the old policy against today's root fails its expected hash gate. Running the
unchanged historical checkers against complete Git snapshot
`05035cec1d1c1c88a08e9012996e5a6e4ccfd2a5` passes all original assertions.

Use that exact snapshot as the four historical tests' source/schema fixture.
Materialize it with local `git archive` into a temporary directory; reject
unsafe paths or special/link entries. Execute only one of four fixed checker
names with its original `--self-test`. Preserve their positive/negative cases
and CTest expected output. The historical Git-object preservation assertion
still reads the real local object database.

Before executing a snapshot test, compare the current immutable templates and
every current D099–D108 preserved artifact with the historical definitions and
their exact recorded hashes. Thus materializing an old tree cannot hide
current preserved-record drift. Do not rewrite old policies, hashes, schemas,
source snapshots, or checkers to make them qualify against today's source.

These tests establish historical compatibility only. They do not qualify the
current source or v54, migrate the stand journal, replace the independent
current-policy check, or authorize an action. A prospective successor must bind
the repaired source and completed implementation before current qualification.
The separate D-100 external archive requirement remains unchanged.

Verify all four original checkers through the harness and demonstrate that a
changed/missing/symlinked preserved current input fails before replay. Record
the actual results and retain the original full-suite failures until CTest
integration and a fresh full run pass.

The harness publishes original success output only after the child exits
successfully and temporary-directory cleanup succeeds. This prevents CTest's
existing `PASS_REGULAR_EXPRESSION` settings from accepting partial success text
from a failed child. A regression injects that exact failure and requires no
success output. All four historical checkers and six preservation/failure
cases pass; their five CTest entries pass in the isolated accepted runtime.
