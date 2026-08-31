#!/usr/bin/env python3
"""Policy-v15 Q15 session-controller compatibility successor."""

from __future__ import annotations

import stage17_phase_controller_v5 as phase_controller
import stage17_q15_session_controller_v2 as predecessor


predecessor.phase_controller = phase_controller


def main() -> int:
    return predecessor.main()


if __name__ == "__main__":
    raise SystemExit(main())
