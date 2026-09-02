# ADR-0130: Stage 17 executor journal reachability

- **Status:** `PROPOSED`
- **Decision ID:** D-130
- **Classification:** implementation correctness, latent defect in already-
  accepted-adjacent code, action-time journal binding
- **Owner:** repository/platform/security/pilot owner
- **Gate:** before any real `S17-EXT-001` read-only preflight action can
  execute

## Context

During the first real (non-hermetic) attempt to execute the read-only
preflight after a genuinely admitted `S17-EXT-001` resolution and
transition, `tools/stage17_read_only_preflight_executor_v13.py --execute`
failed before any network activity, with:
`runtime_closure stage17_read_only_preflight_executor_v12 cannot be
opened safely`. The real journal was confirmed unaffected: no marker was
created, the preflight output root remained empty, and
`AUTHORIZED_FOR_READ_ONLY_PREFLIGHT` with 1 resolution/1 transition was
unchanged before and after the failed attempt.

The root cause was traced directly, not assumed:
`stage17_read_only_preflight_executor_v13.py` imports `stage17_state_
journal_v17 as current_journal` for its own action-time journal
revalidation. `stage17_state_journal_v17.py` is bound to `stage17_
semantic_verifier_v19`, whose `POLICY_PATH` is `config/stage17/stage17-
operational-evidence-admission-policy-v19.json` -- a policy version built
during ADR-0125, *before* ADR-0126 created executor `v13` and fixed its
semantic action-readiness logic. Policy `v19`'s own `required` closure set
still lists `tools/stage17_read_only_preflight_executor_v12.py`, which is
what the failing check tried and failed to verify.

This produced a real split: `admit-resolution`/`append-transition` (via
`stage17_operational_cli_v11.py`) go through `journal_v18` -> policy `v22`
(the currently promoted chain, confirmed by `stage17-operational-
successor-check`), so resolution-time admission correctly succeeded
tonight. But the executor's own, separate, hardcoded journal import was
never bumped through any of the later promotions (`v17`->`v18`->`v19`->
`v20`->`v21`->`v22`->`v23`), because each promotion checked the CLI's own
wiring and the executor's *semantic* correctness, but not the executor's
*own* journal reference -- a distinct static import nobody had reason to
revisit until a real action-time execution actually reached it.

## Decision

Add `tools/stage17_read_only_preflight_executor_v14.py` as an additive
successor to `stage17_read_only_preflight_executor_v13.py`, identical in
every respect except its `current_journal` import moves from `stage17_
state_journal_v17` to `stage17_state_journal_v20` -- the journal module
`stage17_operational_cli_v11.py` itself uses (`v11.py`'s own `journal_
runtime` import was, in the course of this same fix, itself moved from
`v19` to `v20` once it needed to pick up `S17-EXT-001`'s corrected
dispatch below, so `v14` targets that same final generation rather than
the intermediate `v18` first tried), so resolution-time and action-time
validation are on the same chain generation, avoiding exactly the class
of mismatch ADR-0126 already identified and fixed once for the `v16`->
`v17` case. `current_semantic` (`stage17_read_only_preflight_semantic_
verifier_v15`) and the call-site function name (`evaluate_s17_ext_001_
action_readiness_v15`) are unchanged, since that logic was already
verified correct by ADR-0126; only the journal reference moves.
`EXECUTOR_ID` updates to `v14` to accurately self-identify, matching the
established convention.

The preflight-plan policy (`config/stage17/stage17-read-only-preflight-
evidence-admission-policy-v15.json`) binds `IMPLEMENTATION_PATHS
["executor"]` to `v13`; a new preflight-plan policy successor (`v16`)
updates this, and `IMPLEMENTATION_PATHS["state_journal"]`, to `v14`/
`v20`. `IMPLEMENTATION_PATHS["semantic_verifier"]` deliberately keeps
`v15`'s own self-reference (`stage17_read_only_preflight_semantic_
verifier_v15.py`) rather than pointing at the new `v16` module itself:
`_verify_loaded_runtime` strictly name-matches each `implementations`
entry against what is actually resident at that role at action time, and
since `current_semantic` stays `v15` (per the previous paragraph), `v15.py`
-- not `v16.py` -- is what is actually loaded there. `v16.py` exists only
to hold new policy/ADR path constants for admission-time dispatch, verified
empirically against a fresh synthetic admission by `check_stage17_
executor_v14_action_readiness.py`. A new operational-policy successor
(`v24`, via a new outer registry module `stage17_semantic_verifier_v24.py`
and journal `stage17_state_journal_v20.py`) binds the new executor's and
new preflight-plan policy's real hashes, and `cli_v11.py`'s own
`author-ext001` implementation is repointed from the `v15.json` preflight
policy to `v16.json` so any *new* real `S17-EXT-001` admission binds the
corrected chain -- following the exact same additive, non-promoting
pattern established since ADR-0124: sealing a new successor does not
itself make it the policy `stage17-operational-successor-check` reports
as current, and does not grant any stand, execution, Q15, or pilot
authority by itself. `stage17_read_only_preflight_executor_v13.py` and its
entire accepted-adjacent closure are untouched; `v14` is additive only.
`stage17_operational_cli_v11.py` itself is not part of that accepted-
adjacent closure (no real sealed `S17-EXT-001` evidence pins its bytes,
only the preflight-plan policy's own `implementations` entries do) and has
been edited in place before, in this same session, for the same class of
wiring update -- consistent with established practice, not a departure
from the additive-only rule that governs the evidentiary chain itself.

## Effects

Verified directly against `_verify_loaded_runtime`
(`tools/stage17_semantic_verifier_v4.py:503`): action-time revalidation
re-reads the preflight-plan policy from disk by the exact path recorded in
the real, already-sealed resolution's envelope
(`semantic_policy.sha256` pins policy `v15.json` byte-for-byte), and
strictly name-matches the live executor file against that policy's
`implementations.executor.path`, which is permanently `stage17_read_only_
preflight_executor_v13.py`. Because policy `v15.json` and `executor_v13.py`
are both hash-pinned by that real, already-admitted resolution, **the real
resolution admitted tonight can only ever be executed by `executor_v13.py`'s
exact, unmodified bytes** -- the same bytes that contain the journal defect.
Editing `v13.py` in place to fix the defect is not an option (it would
invalidate the real sealed resolution's own pinned hashes), and no new
executor successor can satisfy that resolution's fixed `implementations`
binding. Consequently, `v14`/the new preflight-plan policy successor do
**not** make tonight's already-admitted resolution executable; that
resolution is permanently stuck. Reaching a real, executable preflight
requires admitting a **second, fresh** real `S17-EXT-001` resolution
against the corrected `v14`/policy-successor chain, following the same
`author-ext001` -> `admit-resolution` -> `append-transition` sequence used
for the first real admission tonight, then retrying execution against that
second resolution. No scientific design, transport mechanics, credential
handling, or SSH/fixed six-observation action plan changes -- only which
journal module and preflight-policy generation the executor's own
action-time revalidation consults, and the fact that a fresh admission is
required to use it. This does not authorize any stand action beyond
`READ_ONLY_PREFLIGHT` scope, the same scope the first real resolution was
already authorized under.

## Verification and supersession

Acceptance requires: a regression proving `v13` and its own action-time
behavior are completely unaffected and importable/usable exactly as
before -- `check_stage17_executor_v13_action_readiness.py` now pins its own
isolated fixture bundle back to the `v15`/`v19` generation before exercising
it, decoupling that regression from `cli_v11.py`'s current default so it
keeps proving `v13` specifically, and passes unchanged; confirmation via
`git diff` that no file in any previously accepted or accepted-adjacent
closure changed (verified: only `cli_v11.py` and `check_stage17_executor_
v13_action_readiness.py` are modified in place, both outside that closure,
alongside eleven new additive files); a dry-run import trace proving `v14.
current_journal.semantic` resolves to the same policy generation `stage17_
operational_cli_v11.py` itself uses; and a new positive regression,
`check_stage17_executor_v14_action_readiness.py`, proving a *fresh*
synthetic `S17-EXT-001` admission built through the repository's current
`author-ext001`/`admit-resolution`/`append-transition` wiring resolves
action-readiness correctly end to end through the `v14`/`v20`/`v16`/`v24`
chain, for both predecessor-evidence branches. The original failure
(`runtime_closure stage17_read_only_preflight_executor_v12 cannot be opened
safely`) was reproduced empirically, read-only and off the real journal
under `/home/omaltsev/stage17-owner-evidence/`, before this fix; the fix
was verified the same way, against the same real journal, before any real
retry was attempted. Any later change to which journal generation the
executor consults requires another prospective successor under the same
standard applied since ADR-0108.
