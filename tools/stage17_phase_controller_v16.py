#!/usr/bin/env python3
"""Phase-controller successor fixing `prepare_action`'s own stale
`journal_runtime` binding (reached via `verify-signature`/`execute-action`,
both of which call `stage17_phase_controller_v4.py`'s own `prepare_action`
body -- the only place it is actually defined, per the same free-
variable-resolves-against-the-defining-module rule `v15.py`'s own
docstring already documents for `execute_once`/`executor`).

`stage17_phase_controller_v14.py` (ADR-0146) walked `journal_runtime =
stage17_state_journal_v35` down its own `.predecessor` chain to
`v4.py`. `v15.py` (this file's own predecessor) never repeats that walk,
so `v4.journal_runtime` has stayed frozen at `v35` ever since --
discovered live via a real standv2-30 need to call `verify-signature`
for Q15-R, after `cli_v11.py`'s own *separate* `journal_runtime` name
(used directly by `admit-resolution`/`status`/etc., not via this phase-
controller chain at all) was already independently bumped to
`stage17_state_journal_v39` and confirmed correct. `v39` already binds
its own `.semantic` directly to `stage17_semantic_verifier_v45` (no
further in-memory patching needed, unlike `v35`/`v36`), so re-pointing
`v4.journal_runtime` at the same `v39` module cli_v11.py's own direct
calls already use keeps both paths consistent.
"""

from __future__ import annotations

import stage17_phase_controller_v15 as predecessor
import stage17_state_journal_v39 as journal_runtime

module = predecessor
while True:
    module.journal_runtime = journal_runtime
    if not hasattr(module, "predecessor"):
        break
    module = module.predecessor

ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
prepare_action = predecessor.prepare_action
_runtime_from_context = predecessor._runtime_from_context
_validate_action_inputs = predecessor._validate_action_inputs
execute_once = predecessor.execute_once
main = predecessor.main


if __name__ == "__main__":
    raise SystemExit(main())
