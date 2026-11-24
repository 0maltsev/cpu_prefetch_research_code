#!/usr/bin/env python3
"""Policy-v18 Q15 session-controller successor."""

import stage17_phase_controller_v8 as phase_controller
import stage17_q15_session_controller_v5 as predecessor


module = predecessor
for _ in range(5):
    module.phase_controller = phase_controller
    if not hasattr(module, "predecessor"):
        break
    module = module.predecessor

main = predecessor.main


if __name__ == "__main__":
    raise SystemExit(main())
