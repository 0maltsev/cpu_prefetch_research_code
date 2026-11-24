"""D-204 Q15 session entry point; preserve the existing session execution."""
from __future__ import annotations

import stage17_q15_session_controller_v17 as predecessor
import stage17_phase_controller_v23 as phase_controller
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
