"""D272 fresh-source Q15 entry point; preserve the existing session execution.

The phase controller uses the fresh policy61 journal, never D242 recovery.
"""
from __future__ import annotations

import stage17_q15_session_controller_v19 as predecessor
import stage17_phase_controller_daycap_v3 as phase_controller
import stage17_q15_session_controller_v10 as execution_body
import stage17_q15_session_controller_v2 as initial_body


def activate():
    phase_controller.activate()
    module = predecessor
    while True:
        module.phase_controller = phase_controller
        if not hasattr(module, "predecessor"):
            break
        module = module.predecessor
    execution_body.phase_controller = phase_controller
    initial_body.phase_controller = phase_controller


activate()


def execute_session(**arguments):
    activate()
    return predecessor.execute_session(**arguments)


def main():
    activate()
    return predecessor.main()


if __name__ == "__main__":
    raise SystemExit(main())
