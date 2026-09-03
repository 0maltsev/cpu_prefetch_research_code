# 0142. Stage 17 phase-controller journal reachability

Status: ACCEPTED

## Context

The first-ever real attempt to execute a dynamic Stage 17 action
(`Q15-R`, via `tools/stage17_q15_session_controller_v6.py --start`,
against a real, owner-signed authorization built from the real,
already-admitted fifteenth admission root) failed during local
preparation, before any worker process spawned and before any real
stand contact:

```
stage17-q15-session: FAIL: runtime_closure stage17_read_only_preflight_executor_v12 cannot be opened safely
```

Direct reproduction (calling `prepare_action` locally, no execution)
traced the real cause: `tools/stage17_phase_controller_v4.py`'s
`prepare_action` -- the one real implementation every later
`stage17_phase_controller_vN.py` re-exports unchanged all the way
through `v10` -- reads `journal_runtime` as a free variable resolved
against `v4.py`'s own module globals. That global was last set by
`stage17_phase_controller_v6.py` to `stage17_state_journal_v14`, and no
generation from `v7` through `v10` ever touched it again: `v7`'s own
reassignment loop only reaches its own predecessor's predecessor
(`v6`, `v5`), never `v4`; `v8` and `v9` each reassign exactly three
fixed `.predecessor` hops from themselves, which also never reaches
`v4`. Since `v14`'s own `validate_operational_journal` chains down to
`stage17_state_journal_v12.py`'s real `_policy()`, which reads
`semantic` as *its own* free variable -- and the only thing that ever
patches that variable is the reassignment loop inside the *current*
`stage17_state_journal_v31.py`, which is imported solely by
`stage17_operational_cli_v11.py` -- the phase-controller/Q15-session-
controller invocation path, run as its own separate process with its
own separate import graph, never triggers that patch. `v12`'s
`semantic` therefore stayed bound to whatever it was when `v16` (the
generation `v8`/`v9` actually import as `journal_runtime`) was written:
`stage17_semantic_verifier_v18`, whose own frozen runtime closure
references `tools/stage17_read_only_preflight_executor_v12.py` -- a
file correctly absent from the current bundle, since it was superseded
long ago and is not part of the current policy's own runtime closure.

This is the same reachability-gap class ADR-0130, ADR-0137, ADR-0139,
and ADR-0141 already established and fixed for the read-only-preflight
executor family -- but in a part of the codebase (the phase-controller/
Q15-session-controller pair) that had never been exercised for real
until this session's first genuine Q15-R attempt, so the gap had likely
existed since long before this session and was simply never caught.
No real stand contact occurred: the Q15-R output directory was still
empty when this was found, confirming the failure happened entirely
during local journal validation.

## Decision

Add `tools/stage17_phase_controller_v11.py`, importing
`stage17_state_journal_v31` (the current generation `cli_v11.py` itself
uses) directly as `journal_runtime`. Rather than repeat the fixed-hop-
count pattern that caused this gap, it adopts the more robust walk
`stage17_q15_session_controller_v6.py` already established for its own
`phase_controller` reassignment: walk `.predecessor` until a module has
none, reassigning `journal_runtime` at every step, so it structurally
cannot stop short of the real implementation regardless of how many
additive successors separate them in the future. `ControllerError`,
`PreparedAction`, `prepare_action`, `execute_once`, `main`,
`_runtime_from_context` (ADR-0127), and `_validate_action_inputs`
(ADR-0128) are all re-exported unchanged, since none of their logic is
touched by this fix.

Add `tools/stage17_q15_session_controller_v8.py` (`v7.py` already exists
in the repository -- a prior, unrelated additive successor re-exporting
`execute_session` -- so this fix builds on top of it as the next free
generation, not in place of it), importing this new
`stage17_phase_controller_v11` as `phase_controller` and applying the
identical walk-until-absent reassignment to the Q15-session-controller's
own ancestor chain (mirroring `v6`'s own pattern exactly, just pointed
at the new phase-controller generation). `execute_session` is re-exported
unchanged from `v2.py`, exactly as `v7.py` already established.

`stage17_operational_cli_v11.py`'s own `import stage17_phase_controller_
v10 as controller` moves to `v11`, keeping the CLI's own `author-
request`/`author-authorization` path on the same generation the session
controller now uses.

## Consequences

- A fresh Q15-R attempt requires a new authorization and a new owner
  signature -- the one built for the fifteenth admission was consumed by
  this real (locally-failed, no-stand-contact) attempt and is not
  reused, consistent with treating every one-shot authorization as spent
  once used for a real invocation, regardless of where it failed.
- `check_stage17_phase_controller_v11_journal_reachability.py` proves,
  against the real, already-admitted fifteenth admission root and the
  real (already-spent, but safe to reuse for local-validation-only
  testing -- `prepare_action` never executes anything or writes any
  marker) Q15-R authorization/signature, that `prepare_action` now
  succeeds where it previously raised the real "cannot be opened safely"
  error.
- The same class of gap could in principle still exist for the other
  fixed-phase actions (`Q15-W`, `Q16a/b/c`, `STAGE17-BLINDED-PILOT`),
  since `prepare_action` is shared code -- this fix closes it for all of
  them at once, since they all resolve through the same `journal_runtime`
  global.
