#!/usr/bin/env python3
"""Phase-controller successor completing journal reachability a second
time (ADR-0144, `ACCEPTED`).

`stage17_phase_controller_v11.py` (ADR-0142) fixed the phase-controller
family's reachability gap by hardcoding `import stage17_state_journal_v31
as journal_runtime` and walking `.predecessor` until absent to propagate
it down to `stage17_phase_controller_v4.py`'s own real `prepare_action`/
`execute_once` implementation. That import is itself hardcoded to one
specific journal generation, so moving `cli_v11.py`'s own `journal_
runtime` forward again (ADR-0143, to `stage17_state_journal_v32`) leaves
`v11` stranded exactly as `v9`/`v10` were before it -- proven by this
session's own `check_stage17_phase_controller_v11_journal_reachability.py`
continuing to report `PASS` after ADR-0143 only because it asserts
against `v11`'s own hardcoded import, not against whatever `cli_v11.py`
currently uses. This file repeats the identical walk-until-absent fix,
now importing `stage17_state_journal_v33.py` (ADR-0144's own new journal
generation, reached in lockstep with `stage17_read_only_preflight_
executor_v23.py`'s own journal move) instead of `v31`.
"""

import stage17_phase_controller_v11 as predecessor
import stage17_state_journal_v33 as journal_runtime

module = predecessor
while True:
    module.journal_runtime = journal_runtime
    if not hasattr(module, "predecessor"):
        break
    module = module.predecessor

ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
prepare_action = predecessor.prepare_action
execute_once = predecessor.execute_once
main = predecessor.main
_runtime_from_context = predecessor._runtime_from_context
_validate_action_inputs = predecessor._validate_action_inputs
