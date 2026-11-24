#!/usr/bin/env python3
"""Additive successor to `stage17_read_only_preflight_executor_v27.py`
(ADR-0168 follow-up): the only change is which semantic-verifier module
gets propagated onto `current_journal`'s own five-ancestor chain.

`v27.py` hardcoded this to `stage17_semantic_verifier_v46`, matching
policy v46 at the time it was written. ADR-0168 changed
`src/runner/stage17_fixed_action.cpp` again (after ADR-0159/v45 and
ADR-0166/v46 already re-pinned it), so the same class of gap this
comment's predecessor predicted for itself recurs here. Same
monkey-patch technique as `v27.py` itself, retargeting to
`stage17_semantic_verifier_v47` (which only differs from `v46` by that
one re-pinned binding -- no other admission logic changes).
"""

from __future__ import annotations

import stage17_read_only_preflight_executor_v27 as base
import stage17_semantic_verifier_v47 as _latest_semantic
import stage17_state_journal_v36 as current_journal

for _ancestor in (
    current_journal.predecessor, current_journal.predecessor.predecessor,
    current_journal.predecessor.predecessor.predecessor,
    current_journal.predecessor.predecessor.predecessor.predecessor,
    current_journal.predecessor.predecessor.predecessor.predecessor.predecessor,
):
    _ancestor.semantic = _latest_semantic
    _ancestor.SEMANTIC_POLICY_PATH = _latest_semantic.POLICY_PATH
current_journal.semantic = _latest_semantic
current_journal.SEMANTIC_POLICY_PATH = _latest_semantic.POLICY_PATH

EXECUTOR_ID = "STAGE17-READ-ONLY-PREFLIGHT-EXECUTOR-v28"
base.EXECUTOR_ID = EXECUTOR_ID

import pathlib  # noqa: E402

_base_runtime_identity_paths = base.runtime_identity_paths


def runtime_identity_paths() -> dict[str, str]:
    paths = _base_runtime_identity_paths()
    paths["executor"] = str(pathlib.Path(__file__).resolve())
    return paths


base.runtime_identity_paths = runtime_identity_paths

ActionExecutionError = base.ActionExecutionError
execute_once = base.execute_once
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
