#!/usr/bin/env python3
"""Policy-v17 Q15 session-controller successor."""

import stage17_phase_controller_v7 as phase_controller
import stage17_q15_session_controller_v4 as predecessor


predecessor.predecessor.predecessor.phase_controller = phase_controller
predecessor.predecessor.phase_controller = phase_controller
predecessor.phase_controller = phase_controller
main = predecessor.main


if __name__ == "__main__":
    raise SystemExit(main())
