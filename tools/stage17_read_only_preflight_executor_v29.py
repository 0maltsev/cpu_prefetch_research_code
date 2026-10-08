#!/usr/bin/env python3
"""Additive successor to `stage17_read_only_preflight_executor_v28.py`
(ADR-0168, follow-up): adds the one fix `v27.py`/`v28.py` themselves
never needed, because neither was ever meant to be the policy-approved
executor identity -- each was authored purely for its own import-time
side effect (retargeting `current_journal`'s ancestor `semantic`
binding forward, first to `stage17_semantic_verifier_v46`, then `_v47`),
always imported *alongside* `v26.py`, which remained the actual
`implementations.executor` binding in every preflight-admission-policy
generation through v28.

Preflight-admission-policy v29 (this session, ADR-0168 follow-up for
the *policy* layer) is the first policy generation to name a successor
past `v26.py` as `implementations.executor` at all -- confirmed live:
pointing it at `v28.py` directly and re-authoring `S17-EXT-001` against
it reached a real, no-stand-contact prospective-readiness check that
failed with `actual executor source path does not match policy role`,
because `runtime_identity_paths()["executor"]` still reports
`v26.py`'s own path (exactly matching `v26.py`'s own docstring warning
that `__file__` is "not a free variable that monkey-patching can
redirect" -- `v27.py`/`v28.py` never wrapped it the way `v26.py` did,
since neither needed to until now). This file is the missing wrapper,
built the identical way `v26.py` built its own: a fresh function,
defined here, whose own `__file__` correctly resolves to this file,
starting from the base result and overriding just the one
`"executor"` key every other entry already reads some *other* module's
own `.__file__` through (`current_journal.__file__`, `current_semantic.
__file__`, etc.), which already reflects the chain correctly.
"""

from __future__ import annotations

import pathlib

import stage17_read_only_preflight_executor_v28 as base

EXECUTOR_ID = "STAGE17-READ-ONLY-PREFLIGHT-EXECUTOR-v29"
base.EXECUTOR_ID = EXECUTOR_ID

# `execute_once`'s own free variable `runtime_identity_paths` resolves
# against whichever module actually *defines* `execute_once` --
# confirmed, by reading `execute_once.__module__`, to be `_v25.py`
# itself, not `base` (`_v28.py`) or any other successor in between.
# `_v26.py`'s own working fix patches that same `_v25.py` attribute
# directly for exactly this reason; patching `base.runtime_identity_
# paths` here (as this file's own first draft did) is a no-op against
# the real call path and was confirmed live to still report `_v26.py`'s
# own path.
import stage17_read_only_preflight_executor_v25 as _execute_once_owner

_base_runtime_identity_paths = _execute_once_owner.runtime_identity_paths


def runtime_identity_paths() -> dict[str, str]:
    paths = _base_runtime_identity_paths()
    paths["executor"] = str(pathlib.Path(__file__).resolve())
    return paths


_execute_once_owner.runtime_identity_paths = runtime_identity_paths

ActionExecutionError = base.ActionExecutionError
execute_once = base.execute_once
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
