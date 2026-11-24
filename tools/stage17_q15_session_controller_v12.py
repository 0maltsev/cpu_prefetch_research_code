#!/usr/bin/env python3
"""Policy-v27 Q15 session-controller successor actually completing the
real Q15 session failure-retention schema fix (ADR-0146, `ACCEPTED`).

`stage17_q15_session_controller_v11.py` (ADR-0145) bound `execute_
session = stage17_q15_session_controller_v10.execute_session` inside
its own file -- but `stage17_q15_session_controller_v2.py`'s own
`run_start` calls `execute_session(...)` as a bare name, resolved
against `v2.py`'s own module globals at call time, not against
whatever name any later generation binds in *its own* file. Two real
Q15-R sessions on the real stand, both after ADR-0145's bundle was
staged, proved this: the real measurement succeeded both times, but the
safe, expected Q15-W-timeout failure-retention record still failed with
the exact old, unfixed schema-rejection text, since `run_start` was
still calling `v2.py`'s own original, unfixed `execute_session`.

This file fixes that by patching `stage17_q15_session_controller_v2.
py`'s own `execute_session` global directly --
`_v2.execute_session = _v10.execute_session` -- the same "reassign the
attribute on the module that actually reads it" mechanism the
`phase_controller` walk-until-absent reassignment already relies on.
Continues that same walk unchanged, now pointed at `stage17_phase_
controller_v14.py`.
"""

import stage17_phase_controller_v14 as phase_controller
import stage17_q15_session_controller_v10 as _v10
import stage17_q15_session_controller_v2 as _v2
import stage17_q15_session_controller_v11 as predecessor

_v2.execute_session = _v10.execute_session

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
