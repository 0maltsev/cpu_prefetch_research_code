"""D-204 entry point: keep all actions on the current journal generation."""
from __future__ import annotations

import stage17_phase_controller_v22 as predecessor
import stage17_phase_controller_v18 as formal_prepare
import stage17_phase_controller_v4 as formal_body
import stage17_state_journal_v50 as journal_runtime

ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
support = predecessor.support
deadline_policy = predecessor.deadline_policy
runtime_from_context = predecessor.runtime_from_context
validate_action_inputs = predecessor.validate_action_inputs
_runtime_from_context = predecessor._runtime_from_context
_validate_action_inputs = predecessor._validate_action_inputs


def activate():
    journal_runtime.activate()
    predecessor.journal_runtime = journal_runtime
    formal_prepare.journal_runtime = journal_runtime
    formal_body.journal_runtime = journal_runtime


activate()


def prepare_action(**arguments):
    activate()
    return predecessor.prepare_action(**arguments)


def execute_once(**arguments):
    activate()
    return predecessor.execute_once(**arguments)


def main():
    activate()
    return predecessor.main()


if __name__ == "__main__":
    raise SystemExit(main())
