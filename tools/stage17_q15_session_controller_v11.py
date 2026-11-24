#!/usr/bin/env python3
"""Policy-v26 Q15 session-controller successor pinning the real Q15
session failure-retention schema fix and completing journal reachability
a third time (ADR-0145, `ACCEPTED`).

Points `execute_session` at `stage17_q15_session_controller_v10.py`
(the real fix: `failure_stage` stays a clean enum value always, with a
new, independent `cleanup_error_occurred: bool` field instead of the
`":SUPERVISOR_FALLBACK"` string-concatenation `v2.py` used, which the
`stage17-q15-session-failure-v1.schema.json` enum never accepted --
see `v10.py`'s own docstring). Points `phase_controller` at `stage17_
phase_controller_v13.py`, the generation that reassigns `journal_
runtime` all the way down to `stage17_phase_controller_v4.py`'s own
real `prepare_action`/`execute_once` implementation, now bound to
`stage17_state_journal_v34`. Reuses `v9`'s own walk-until-absent
reassignment pattern unchanged -- it was already the more robust
approach; this file just points it at the new phase-controller
generation and the new `execute_session` implementation.
"""

import stage17_phase_controller_v13 as phase_controller
import stage17_q15_session_controller_v10 as _v10
import stage17_q15_session_controller_v9 as predecessor


module = predecessor
for _ in range(5):
    module.phase_controller = phase_controller
    if not hasattr(module, "predecessor"):
        break
    module = module.predecessor

main = predecessor.main
execute_session = _v10.execute_session


if __name__ == "__main__":
    raise SystemExit(main())
