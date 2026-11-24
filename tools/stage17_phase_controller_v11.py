#!/usr/bin/env python3
"""Stage 17 phase-controller successor completing journal reachability
(ADR-0142, `ACCEPTED`).

The first-ever real attempt to execute a dynamic Stage 17 action
(`Q15-R`) failed during local preparation with `runtime_closure
stage17_read_only_preflight_executor_v12 cannot be opened safely`.
`prepare_action` (the one real implementation, defined in
`stage17_phase_controller_v4.py` and re-exported unchanged through
`v10`) resolves `journal_runtime` as a free variable against `v4.py`'s
own module globals. That global was last set by
`stage17_phase_controller_v6.py` to `stage17_state_journal_v14`; no
generation from `v7` through `v10` ever reassigned it again -- their own
fixed-hop-count reassignment loops (`predecessor`, `predecessor.
predecessor`, `predecessor.predecessor.predecessor`) never reach `v4`
from where they are invoked. Since `v14` chains down to `stage17_state_
journal_v12.py`'s real `_policy()`, which reads `semantic` as *its own*
free variable, and the only thing that ever patches that variable is
the reassignment loop inside the *current* `stage17_state_journal_
v31.py` -- imported solely by `stage17_operational_cli_v11.py` -- the
phase-controller/Q15-session-controller invocation path (run as its own
separate process) never triggered that patch. `v12`'s `semantic` stayed
bound to whatever it was when `v16` (what `v8`/`v9` actually import as
`journal_runtime`) was written: `stage17_semantic_verifier_v18`, whose
own frozen runtime closure references a long-superseded executor file
correctly absent from the current bundle.

This file imports `stage17_state_journal_v31` (the same generation
`cli_v11.py` itself uses) directly as `journal_runtime`. Rather than
repeat the fixed-hop-count pattern that caused this gap, it adopts the
more robust walk `stage17_q15_session_controller_v6.py` already
established for its own `phase_controller` reassignment: walk
`.predecessor` until a module has none, reassigning `journal_runtime`
at every step, so it structurally cannot stop short of the real
implementation (`v4`) regardless of how many additive successors
separate them in the future -- the exact class of mistake this file
fixes. `ControllerError`, `PreparedAction`, `prepare_action`,
`execute_once`, `main`, `_runtime_from_context` (ADR-0127), and
`_validate_action_inputs` (ADR-0128) are all re-exported unchanged,
since none of their logic is touched by this fix.
"""

from __future__ import annotations

import stage17_phase_controller_v10 as predecessor
import stage17_state_journal_v31 as journal_runtime


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


if __name__ == "__main__":
    raise SystemExit(main())
