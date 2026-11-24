#!/usr/bin/env python3
"""Phase-controller successor completing journal reachability a fourth
time (ADR-0146, `ACCEPTED`).

`stage17_phase_controller_v13.py` (ADR-0145) hardcoded `import stage17_
state_journal_v34 as journal_runtime` and walked `.predecessor` until
absent to propagate it down to `stage17_phase_controller_v4.py`'s own
real `prepare_action`/`execute_once` implementation. That import is
itself hardcoded to one specific journal generation, so moving
`cli_v11.py`'s own `journal_runtime` forward again (ADR-0146, to
`stage17_state_journal_v35`, folded into the same ADR as the real Q15
session `execute_session` wiring fix and its own bindings-completion)
leaves `v13` stranded exactly as `v9`-`v12` were before it. This file
repeats the identical walk-until-absent fix, now importing `stage17_
state_journal_v35.py` instead of `v34`.
"""

import stage17_phase_controller_v13 as predecessor
import stage17_state_journal_v35 as journal_runtime

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
