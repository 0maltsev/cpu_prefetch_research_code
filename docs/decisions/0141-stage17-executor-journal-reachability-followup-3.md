# 0141. Stage 17 executor journal-reachability follow-up (3)

Status: ACCEPTED

## Context

ADR-0140 advanced `cli_v11.py`'s own `journal_runtime` to `stage17_state_
journal_v30` (importing `stage17_semantic_verifier_v34`) to reach its
S17-EXT-002 preflight receipt-pairing fix. Exactly as ADR-0130, ADR-0137,
and ADR-0139 already established for this class of change, this left
`stage17_read_only_preflight_executor_v21.py`'s own `current_journal`
import pinned to `stage17_state_journal_v29` (importing `stage17_
semantic_verifier_v33`). Caught locally via a real regression-test
failure (`check_stage17_executor_v21_action_readiness.py --self-test`,
which exercises the executor's current wiring directly against the live
tree), not via any stand contact.

This recurs every time `cli_v11.py`'s `journal_runtime` moves, regardless
of which admission path (`S17-EXT-001` or, as here, `S17-EXT-002`)
triggered the move, because `_policy()` re-verifies every one of a
journal generation's pinned bindings' *live* bytes on every real
validation, and `cli_v11.py` is itself always one of those bindings.

## Decision

Add `stage17_read_only_preflight_executor_v22.py`, a byte-for-byte copy
of `v21` except its own `import stage17_state_journal_v31 as
current_journal` (was `v29`) and `EXECUTOR_ID` bump -- `v31` is this same
ADR's own new journal generation, so the executor and `cli_v11.py` land
on the identical final journal generation once this ADR's implementation
completes, exactly as `v21`/`v29` matched at the end of ADR-0139's own
implementation (the off-by-one lesson ADR-0139 itself learned the hard
way: point directly at the final generation, not an intermediate one).
`current_semantic` stays `stage17_read_only_preflight_semantic_verifier_
v20` directly (unchanged, no real logic change); the collector stays
`v3`.

Add `stage17_read_only_preflight_semantic_verifier_v24.py`, a pure
`IMPLEMENTATION_PATHS` rebind of `v23`: `executor` -> `v22.py`,
`state_journal` -> `v31.py`; `collector`/`process_group_supervisor`/
`openssh_snapshot_broker`/`semantic_verifier` keep `v23`'s own inherited
values. `evaluate_s17_ext_001_action_readiness_v20` re-exported
unchanged; `verify_s17_ext_001_semantics_v24` is a deliberate alias of
`v23`'s own `verify_s17_ext_001_semantics_v23`; `verify_policy_v24` is a
fresh copy.

Add `stage17_semantic_verifier_v35.py`, re-intercepting `S17-EXT-001`
(delegating to `preflight_v24`) while `S17-EXT-002` and everything else
delegates unchanged to `predecessor.verify_input` (`v34`, ADR-0140's own
fix, untouched by this follow-up). `stage17_state_journal_v31.py` moves
the semantic import to `v35`; `cli_v11.py`'s `journal_runtime` moves to
`v31` and its `author-ext001` policy-path literal moves to the new
preflight-plan policy `v24.json`.

## Consequences

- `check_stage17_executor_v21_action_readiness.py` is re-pinned via `git
  archive` to the historical commit where `cli_v11.py`'s own `journal_
  runtime`/`author-ext001` policy path genuinely match what executor v21/
  semantic verifier v23 themselves hardcode (the commit accepting
  ADR-0138/ADR-0139), and `check_stage17_executor_v22_action_readiness.py`
  is added exercising the live wiring in its place.
- This fix requires no bundle reseal by itself, but since S17-EXT-002's
  own admission is still blocked on the manifest re-authoring ADR-0140
  requires, both land together before the next real admission attempt.
