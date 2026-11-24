#!/usr/bin/env python3
"""Additive successor to `stage17_read_only_preflight_executor_v26.py`
(ADR-0166 follow-up): the only change is which semantic-verifier module
gets propagated onto `current_journal`'s own five-ancestor chain.

`v26.py` hardcoded this to `stage17_semantic_verifier_v45`, matching
policy v45 at the time it was written. Confirmed live, running the
real preflight executor locally against a fresh standv2-31 admission
root built from the new ADR-0166 bundle: `execute_once`'s own
`_prospective_validation` re-validates the admission root via
`current_journal.validate_operational_journal(...)`, which reached
`v45`'s stale binding for `src/runner/stage17_fixed_action.cpp` (ADR-
0166 changed that file again after ADR-0159/v45 already re-pinned it
once), raising the exact `bindings src__runner__stage17_fixed_
action_cpp file identity/size drifted` failure this comment predicts
for exactly this class of gap. Same monkey-patch technique as `v26.py`
itself, retargeting to `stage17_semantic_verifier_v46` (which only
differs from `v45` by that one re-pinned binding -- no other admission
logic changes).
"""

from __future__ import annotations

import stage17_read_only_preflight_executor_v26 as base
import stage17_semantic_verifier_v46 as _latest_semantic
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

EXECUTOR_ID = "STAGE17-READ-ONLY-PREFLIGHT-EXECUTOR-v27"
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
