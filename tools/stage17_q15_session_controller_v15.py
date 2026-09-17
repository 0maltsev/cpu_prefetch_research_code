#!/usr/bin/env python3
"""Real Q15 session-controller successor fixing a real, pre-existing gap
in the `phase_controller` propagation chain (ADR-0169).

`v12.py`/`v13.py` each walk `predecessor.predecessor...` reassigning
`module.phase_controller` for a fixed hop count (5, then 6), matching
their own generation's ancestor depth at the time each was written --
but neither ever reaches `stage17_q15_session_controller_v1.py`, which
sits 5 more hops past where `v13.py`'s own 6-hop walk stops (v12 -> v11
-> v9 -> v8 -> v7 -> v6, never v5/v4/v3/v2/v1). `v1.py`'s own
`run_start`/`run_continue` call `phase_controller.prepare_action(...)`
as a bare module-global lookup resolved against `v1.py`'s own,
never-patched import (`stage17_phase_controller_v3`, whose `AUTH_SCHEMA`
is the old `stage17-phase-action-authorization-v3.schema.json` --
missing `deadline_policy`/`session_id`). Real, reproduced: a real Q15-R
`--start` invocation through the full v14 generation failed schema
validation with exactly `Additional properties are not allowed
('deadline_policy', 'session_id' were unexpected)`, confirming `v1.py`
was still validating against the old v3 schema despite every later
generation supposedly being current -- the exact same class of gap
already fixed once today in `stage17_state_journal_v41.py`'s own
ancestor walk.

Fixed the same way: walk the whole `predecessor` chain to its actual
end instead of a hardcoded hop count, so this stays correct regardless
of how many more additive successors this chain grows by.
"""

from __future__ import annotations

import stage17_q15_session_controller_v14 as predecessor

_module = predecessor
while True:
    _module.phase_controller = predecessor.phase_controller
    if not hasattr(_module, "predecessor"):
        break
    _module = _module.predecessor

main = predecessor.main
execute_session = predecessor.execute_session


if __name__ == "__main__":
    raise SystemExit(main())
