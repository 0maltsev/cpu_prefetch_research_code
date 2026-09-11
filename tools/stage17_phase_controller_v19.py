#!/usr/bin/env python3
"""Phase-controller successor completing ADR-0161: chains `stage17_
fixed_action_executor_v7.py`'s combined ADR-0160+ADR-0161 executor
fix into the real `execute-action` call path, alongside `stage17_
phase_controller_v18.py`'s own already-verified ADR-0160 `prepare_
action` fix (unchanged by this ADR).

`execute_once` (defined once, in `v15.py`, re-exported unchanged
through `v17.py`/`v18.py`) reaches the fixed-action executor via its
own module-level `executor` name, bound once at `v15.py`'s own import
time to the real `stage17_fixed_action_executor_v5` module object.
`v7.py`'s own import chain (v6 -> v5's `execute_fixed_action`
attribute; v5-registry -> v4's `_validate_run_families` attribute)
patches that same module object's attributes directly, so importing
`v7.py` anywhere before real execution is sufficient -- no rebinding
of `v15.py`'s own `executor` name is needed, the same "no further
rebinding needed" property `v6.py`'s own docstring already
established for the executor half of this chain.
"""

from __future__ import annotations

import stage17_fixed_action_executor_v7  # noqa: F401 -- ADR-0160+ADR-0161 executor chain
import stage17_phase_controller_v18 as predecessor

ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
prepare_action = predecessor.prepare_action
_runtime_from_context = predecessor._runtime_from_context
_validate_action_inputs = predecessor._validate_action_inputs
execute_once = predecessor.execute_once
main = predecessor.main


if __name__ == "__main__":
    raise SystemExit(main())
