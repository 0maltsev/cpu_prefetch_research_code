#!/usr/bin/env python3
"""Policy-v18 Stage 17 phase-controller successor."""

from __future__ import annotations

import stage17_phase_controller_v7 as predecessor
import stage17_state_journal_v16 as journal_runtime


for module in (predecessor, predecessor.predecessor, predecessor.predecessor.predecessor):
    module.journal_runtime = journal_runtime

ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
prepare_action = predecessor.prepare_action
execute_once = predecessor.execute_once
main = predecessor.main


if __name__ == "__main__":
    raise SystemExit(main())
