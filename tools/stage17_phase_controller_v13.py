#!/usr/bin/env python3
"""Phase-controller successor completing journal reachability a third
time (ADR-0145, `ACCEPTED`).

`stage17_phase_controller_v12.py` (ADR-0144) hardcoded `import stage17_
state_journal_v33 as journal_runtime` and walked `.predecessor` until
absent to propagate it down to `stage17_phase_controller_v4.py`'s own
real `prepare_action`/`execute_once` implementation. That import is
itself hardcoded to one specific journal generation, so moving
`cli_v11.py`'s own `journal_runtime` forward again (ADR-0145, to
`stage17_state_journal_v34`, folded into the same ADR as a real Q15
session failure-retention schema fix and its own bindings-completion)
leaves `v12` stranded exactly as `v9`/`v10`/`v11` were before it. This
file repeats the identical walk-until-absent fix, now importing
`stage17_state_journal_v34.py` instead of `v33`.
"""

import stage17_phase_controller_v12 as predecessor
import stage17_state_journal_v34 as journal_runtime

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
