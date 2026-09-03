# 0144. Stage 17 executor and phase-controller journal reachability follow-up 4

Status: ACCEPTED

## Context

ADR-0143's own `cli_v11.py` edit (`journal_runtime` v31 -> v32, to reach
the new bindings-completion policy v36) reopened the same reachability
gap class ADR-0130/0137/0139/0141 already closed four times for the
read-only-preflight executor family, confirmed by a real regression-test
failure (`check_stage17_executor_v22_action_readiness.py`, run against
the live, edited tree, before any stand contact): `stage17_read_only_
preflight_executor_v22.py`'s own `import stage17_state_journal_v31 as
current_journal` stayed pinned to `v31`, so `prepare_action`'s executor-
side validation (`executor_v22 -> journal_v31 -> semantic_v35 ->
policy-v35.json`) and `cli_v11.py`'s own admission-time validation
(`journal_v32 -> semantic_v36 -> policy-v36.json`) diverged onto two
different policy generations entirely.

ADR-0142 additionally proved the phase-controller family carries an
identical hardcoded-import gap (`stage17_phase_controller_v11.py`'s own
`import stage17_state_journal_v31 as journal_runtime`), and that fix is
equally vulnerable to the same v31 -> v32 move: `check_stage17_phase_
controller_v11_journal_reachability.py` continues to report `PASS` after
ADR-0143 only because it asserts `stage17_phase_controller_v4.journal_
runtime.__name__ == 'stage17_state_journal_v31'` -- the exact value `v11`
itself hardcodes, not whatever `cli_v11.py` currently uses. Both families
need a companion generation in the same change, or this ADR's own
`cli_v11.py` edit would reopen the phase-controller gap it took ADR-0142
to close, defeating the purpose.

## Decision

Add `tools/stage17_read_only_preflight_executor_v23.py` (only change:
`import stage17_state_journal_v32 as current_journal`, `EXECUTOR_ID` ->
`v23`), `tools/stage17_read_only_preflight_semantic_verifier_v25.py`
(pure rebind: `IMPLEMENTATION_PATHS["executor"]` -> `v23.py`, `["state_
journal"]` -> `v32.py`), `tools/stage17_semantic_verifier_v37.py`
(re-intercepts `S17-EXT-001` via `preflight_v25`, delegates everything
else to `predecessor` (`v36`, unaffected including `S17-EXT-002`)),
`tools/author_stage17_read_only_preflight_policy_v25.py` and its schema,
`tools/author_stage17_policy_v37.py` and its schema (outer policy,
literal `ROOTS` since the executor generation moves, exactly as ADR-0137/
0139/0141 needed), and `tools/stage17_state_journal_v33.py`.

Add `tools/stage17_phase_controller_v12.py`, repeating ADR-0142's own
walk-until-absent fix, now importing `stage17_state_journal_v33` instead
of `v31`. Add `tools/stage17_q15_session_controller_v9.py`, pointing
`phase_controller` at `v12` via the same reassignment pattern `v8.py`
already established.

Unlike ADR-0143, `author_stage17_policy_v37.py`'s `SUCCESSOR_BINDINGS`
pins `tools/stage17_phase_controller_v12.py` and `tools/stage17_q15_
session_controller_v9.py` explicitly and proactively, applying ADR-0143's
own lesson immediately rather than waiting to discover the same missing-
binding failure a second time.

`stage17_operational_cli_v11.py` moves `journal_runtime` to `v33`,
`controller` to `stage17_phase_controller_v12`, and the `author-ext001`
policy path to `v25.json`.

## Consequences

- A fresh Q15-R attempt needs a bundle reseal carrying this policy
  generation and both newly-pinned entrypoint generations, plus a new
  owner-signed authorization -- none has been consumed by this purely
  local, evidence-inspection-driven fix.
- While implementing this ADR, a further, distinct question was raised
  about `stage17_q15_session_controller_v8.py`'s own fixed-hop-count
  `phase_controller` reassignment loop (inherited unchanged from `v7.py`)
  possibly falling one hop short of reaching `stage17_q15_session_
  controller_v2.py` itself, unlike `v6.py`'s and `v7.py`'s own loops at
  their respective chain depths. Direct, real (non-mutating) inspection
  shows this is harmless in practice, though not for the reason first
  guessed: `v2.py`'s own `phase_controller` global is not stuck at its
  original `stage17_phase_controller_v4` import -- it was already
  repointed to `stage17_phase_controller_v10` by an earlier generation's
  reassignment before this session began, and this ADR's own `v12`
  reassignment loop (like `v11`'s before it) walks and patches
  `journal_runtime` directly onto *every* module in the `v4`-`v12` chain,
  `v10` included, not only `v4` itself. So regardless of which specific
  generation name `v2.phase_controller` happens to reference, that exact
  module's own `journal_runtime` attribute is independently, directly
  kept current. Confirmed directly: `stage17_q15_session_controller_v2.
  phase_controller.journal_runtime.__name__ == stage17_phase_controller_
  v4.journal_runtime.__name__ == "stage17_state_journal_v33"` after this
  ADR's changes, even though `v2.phase_controller is not stage17_phase_
  controller_v4`. `tools/check_stage17_q15_session_controller_v9_phase_
  controller_binding.py` proves this directly rather than leaving it as
  an untested assumption.
