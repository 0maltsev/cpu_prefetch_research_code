#!/usr/bin/env python3
"""Policy-v22 Q15 session-controller successor completing journal
reachability (ADR-0142, `ACCEPTED`).

Points `phase_controller` at `stage17_phase_controller_v11.py`, the
generation that finally reassigns `journal_runtime` all the way down to
`stage17_phase_controller_v4.py`'s own real `prepare_action`/
`execute_once` implementation (see that file's own docstring for the
real, reproduced `Q15-R` failure this completes the fix for). Reuses
`v6`'s own walk-until-absent reassignment pattern unchanged -- it was
already the more robust approach; this file just points it at the new
phase-controller generation. `execute_session` is re-exported unchanged
from `v2.py` exactly as `v7.py` already established it (see that file's
own docstring); this file changes only which `phase_controller` its own
reassignment loop points every successor's `phase_controller` global at.
"""

import stage17_phase_controller_v11 as phase_controller
import stage17_q15_session_controller_v2 as _v2
import stage17_q15_session_controller_v7 as predecessor


module = predecessor
for _ in range(5):
    module.phase_controller = phase_controller
    if not hasattr(module, "predecessor"):
        break
    module = module.predecessor

main = predecessor.main
execute_session = _v2.execute_session


if __name__ == "__main__":
    raise SystemExit(main())
