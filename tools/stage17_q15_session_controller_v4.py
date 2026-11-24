#!/usr/bin/env python3
"""Policy-v16 Q15 session-controller successor."""

import stage17_phase_controller_v6 as phase_controller
import stage17_q15_session_controller_v3 as predecessor

predecessor.predecessor.phase_controller = phase_controller
main = predecessor.main

if __name__ == "__main__":
    raise SystemExit(main())
