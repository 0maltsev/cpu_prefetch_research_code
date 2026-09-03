# 0145. Stage 17 Q15 session failure-retention schema fix

Status: ACCEPTED

## Context

The first-ever real, complete Q15-R measurement on the real XEON-CPU-FETCH
stand succeeded (`H0_SEALED_WAITING_FOR_Q15_W`, real MSR prestate reads,
real regular-stream and pointer-dependent probe passes) and then, exactly
as designed, blocked waiting for a Q15-W continuation that was
deliberately never submitted. When that wait timed out -- the safe,
by-design outcome -- the session controller's own failure-retention path
itself failed:

```
stage17-q15-session: FAIL: primary=timed out; failure-retention=Q15
session failure record rejected: 'Q15_W_ADMISSION:SUPERVISOR_FALLBACK'
is not one of ['Q15_R_PRESTATE', 'Q15_R_WAIT', 'Q15_W_ADMISSION',
'Q15_W_MUTATION', 'Q15_W_RESTORE', 'RETENTION']
```

A real, earlier session (whose primary failure was itself an unexpected
worker exit, not the safe timeout) hit the identical class of failure at
a different stage: `'Q15_R_WAIT:SUPERVISOR_FALLBACK'`. Both real
occurrences trace to the same code: `stage17_q15_session_controller_
v2.py`'s `execute_session`, when the process-group supervisor's own
`cleanup_process_group` call ALSO raises while handling a primary
failure, builds the failure record's `failure_stage` by string-
concatenating `":SUPERVISOR_FALLBACK"` onto whatever `failure_stage`
already was. `stage17-q15-session-failure-v1.schema.json`'s own
`failure_stage` enum, however, only ever accepted the six bare stage
names -- never any suffixed variant -- so `_write_session_failure`'s own
schema validation rejects exactly the failure records this fallback
path exists to retain, in both the unexpected-worker-exit case and the
entirely safe, expected-timeout case. This is a general defect, not
specific to either scenario: it fires any time process-group cleanup
itself errors while handling a primary session failure, regardless of
which stage that primary failure occurred in. The real Q15-R measurement
data itself was unaffected in both cases -- it is written to disk before
this code path is ever reached -- but the failure record meant to
capture *why* the session ultimately failed was never durably retained.

## Decision

Add `tools/stage17_q15_session_controller_v10.py`, a full additive
successor to `v2.py` (which holds the real `execute_session`/
`_write_session_failure` implementation every later generation re-
exports unchanged) that keeps `failure_stage` a clean enum value always,
adding a new, independent `cleanup_error_occurred: bool` field to the
record instead of mutating the enum string. `config/schemas/stage17-q15-
session-failure-v2.schema.json` adds that field; `failure_stage`'s own
enum is unchanged. `execute_session`'s substantive logic is otherwise
byte-identical to `v2.py`'s.

Since `create_stand_bundle.py` only copies files the outer admission
policy's own bindings/runtime_closure list, and `v10.py` is (like every
prior `q15_session_controller` generation past `v6`) unreachable via the
real Python import graph, add `tools/stage17_q15_session_controller_
v11.py` as the new pinned dynamic-action entrypoint: it re-exports
`execute_session` from `v10` instead of `v2`, and continues the walk-
until-absent `phase_controller` reassignment `v9.py` already established,
now pointed at `stage17_phase_controller_v13.py`.

Moving the outer policy to reach `v10`/`v11` requires a fresh outer
policy generation, which requires `cli_v11.py`'s own `journal_runtime`
to move -- which has, every time so far (ADR-0130/0137/0139/0141/0144),
immediately stranded both the read-only-preflight executor family and
the phase-controller family's own hardcoded journal imports. Rather than
split this into a bindings-completion ADR followed by a separate
reachability-follow-up ADR (the ADR-0143/ADR-0144 pattern), this ADR
folds both concerns together: `author_stage17_policy_v38.py` uses a
literal, updated `ROOTS` tuple (moving the executor/journal generation
in the same step, not `predecessor.ROOTS`) and proactively pins the new
dynamic-action entrypoints via `SUCCESSOR_BINDINGS`, so no follow-up ADR
is needed this time. Add `tools/stage17_read_only_preflight_executor_
v24.py` (only change: journal import), `tools/stage17_read_only_
preflight_semantic_verifier_v26.py` (pure rebind), `tools/
author_stage17_read_only_preflight_policy_v26.py` and its schema, `tools/
stage17_semantic_verifier_v38.py` (re-intercepts `S17-EXT-001` via
`preflight_v26`, delegates everything else including `S17-EXT-002`
unchanged), `tools/author_stage17_policy_v38.py` and its schema, `tools/
stage17_state_journal_v34.py`, and `tools/stage17_phase_controller_
v13.py` (walk-until-absent, importing `stage17_state_journal_v34`).

`stage17_operational_cli_v11.py` moves `journal_runtime` to `v34`,
`controller` to `stage17_phase_controller_v13`, and the `author-ext001`
policy path to `v26.json`.

## Consequences

- A fresh Q15-R attempt needs a bundle reseal carrying this policy
  generation and the newly-pinned entrypoints, plus a new owner-signed
  authorization. The real, successful measurement already captured
  (session `XEON-CPU-FETCH-Q15R-SESSION-16E`) is retained regardless and
  does not need to be repeated for this fix's own sake; it is real,
  complete, real-stand evidence, independent of this bug.
- Every currently-retained real Q15 session failure record on disk
  (none successfully written yet, since every real attempt so far either
  fully succeeded or hit this exact schema rejection) will use schema
  `v2` going forward; no historical `v1` failure records exist to
  migrate.
- The same class of defect (a fallback/cleanup path building a value
  the schema was never updated to accept) is plausible elsewhere in the
  codebase; this ADR fixes only the one real, reproduced instance.
