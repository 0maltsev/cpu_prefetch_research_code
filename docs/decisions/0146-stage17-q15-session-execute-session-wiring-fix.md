# 0146. Stage 17 Q15 session `execute_session` wiring fix

Status: ACCEPTED

## Context

Two real Q15-R sessions on the real stand, both after ADR-0145 was
accepted and its bundle staged, hit the *exact same* schema rejection
ADR-0145 was meant to fix:

```
stage17-q15-session: FAIL: primary=timed out; failure-retention=Q15
session failure record rejected: 'Q15_W_ADMISSION:SUPERVISOR_FALLBACK'
is not one of ['Q15_R_PRESTATE', 'Q15_R_WAIT', 'Q15_W_ADMISSION',
'Q15_W_MUTATION', 'Q15_W_RESTORE', 'RETENTION']
```

The real Q15-R measurement itself succeeded both times; only the
failure-retention record, for the safe, expected Q15-W timeout, still
failed to write -- with the old, unfixed `v1` schema's own error text,
proving the fix genuinely never ran.

Root cause: `stage17_q15_session_controller_v2.py`'s own `run_start`
calls `execute_session(q15_r=prepared, wait_for_q15_w=wait_for_q15_w)`
as a bare name. Python resolves that name against `v2.py`'s own module
globals at call time -- not against whatever name any later generation
happens to bind in *its own* file. `stage17_q15_session_controller_
v11.py`'s `execute_session = _v10.execute_session` line only created a
new top-level attribute on `v11.py` itself; nothing calls
`stage17_q15_session_controller_v11.execute_session` directly (the real
execute script invokes `v11.py --start`, which resolves to `predecessor.
main` -> ... -> `v2.main` -> `run_start`, and `run_start` is defined,
and calls `execute_session`, entirely inside `v2.py`). This is the same
"free variables resolve against the *defining* module, not the
*accessing* one" lesson this session has already hit for other
attributes (e.g. the preflight-policy aliasing gap ADR-0139 fixed) --
just missed here. The regression this session wrote to prove the fix
(`check_stage17_q15_session_controller_v11_phase_controller_binding.py`)
only asserted `stage17_q15_session_controller_v11.execute_session is
stage17_q15_session_controller_v10.execute_session` -- true, and
irrelevant to whether `run_start` ever reaches it.

## Decision

Add `tools/stage17_q15_session_controller_v12.py`. Unlike every prior
generation in this family, it does not merely bind a new local
`execute_session` name -- it patches `stage17_q15_session_controller_
v2.py`'s own `execute_session` module global directly:
`_v2.execute_session = _v10.execute_session` (`_v10` being `stage17_
q15_session_controller_v10.py`, ADR-0145's real fix). This is the exact
same "reassign the attribute on the module that actually reads it"
mechanism the `phase_controller` walk-until-absent reassignment already
relies on -- `run_start`'s own bare-name lookup of `execute_session`
happens inside `v2.py`, so only mutating `v2.py`'s own global (not
creating a same-named attribute somewhere else) can change what it
calls. `v12.py` continues the `phase_controller` walk-until-absent
reassignment unchanged, now pointed at `stage17_phase_controller_
v14.py` (the fresh generation this ADR's own outer-policy move
requires, for the same recurring reason ADR-0142/0144/0145 already
established).

Since no bundle has ever shipped `v12.py`, this ADR again folds the
resulting bindings-completion and executor/phase-controller journal-
reachability lockstep into the same generation (`v25`/`v14`, outer
policy `v39`/preflight-policy `v27`), applying the ADR-0143/0144/0145
lesson proactively. Add `tools/stage17_read_only_preflight_executor_
v25.py`, `tools/stage17_read_only_preflight_semantic_verifier_v27.py`,
`tools/author_stage17_read_only_preflight_policy_v27.py` and its
schema, `tools/stage17_semantic_verifier_v39.py`, `tools/
author_stage17_policy_v39.py` and its schema, and `tools/stage17_state_
journal_v35.py`.

`stage17_operational_cli_v11.py` moves `journal_runtime` to `v35`,
`controller` to `stage17_phase_controller_v14`, and the `author-ext001`
policy path to `v27.json`.

`tools/check_stage17_q15_session_execute_session_wiring_v12.py` proves
the actual, previously-missing fact: after importing `v12`, `stage17_
q15_session_controller_v2.execute_session is stage17_q15_session_
controller_v10.execute_session` -- i.e. that `v2.py`'s own global,
the one `run_start` actually reads, was really patched. It also proves
`v11.py`'s own binding was insufficient by asserting the negative
(`v2.execute_session is not v11.execute_session`'s own separately-bound
copy) would not by itself have been enough.

## Consequences

- A fresh Q15-R attempt needs a bundle reseal carrying this policy
  generation, plus a new owner-signed authorization. Both real
  measurements already captured (sessions `-16E` and `-17`) are
  retained regardless and do not need to be repeated for this fix's own
  sake.
- This is the second real defect found only by an actual, real
  invocation on the real stand, in a code path (`execute_session`'s own
  wiring) no synthetic or unit-level check had exercised end-to-end
  before. `check_stage17_q15_session_execute_session_wiring_v12.py`
  closes that specific gap; other similarly-wired indirections elsewhere
  in the codebase are not audited by this ADR.
