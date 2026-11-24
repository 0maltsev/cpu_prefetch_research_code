"""Fresh Q15 qualification of the seven-action release, unchanged session body."""
from __future__ import annotations

import stage17_phase_controller_v22 as phase_controller
import stage17_q15_session_controller_v16 as predecessor

# Rebind the same defining modules as v12, including the v10 execution body.
module = predecessor
while True:
    module.phase_controller = phase_controller
    if not hasattr(module, "predecessor"):
        break
    module = module.predecessor
import stage17_q15_session_controller_v10 as execution_body
import stage17_q15_session_controller_v2 as initial_body
execution_body.phase_controller = phase_controller
initial_body.phase_controller = phase_controller
main = predecessor.main
execute_session = predecessor.execute_session

if __name__ == "__main__":
    raise SystemExit(main())
