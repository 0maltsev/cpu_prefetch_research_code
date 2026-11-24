#!/usr/bin/env python3
"""Policy-v15 Stage 17 operational CLI compatibility successor."""

from __future__ import annotations

import stage17_operational_cli_v6 as predecessor
import stage17_phase_controller_v5 as controller
import stage17_state_journal_v13 as journal_runtime


predecessor.controller = controller
predecessor.journal_runtime = journal_runtime


def main() -> int:
    return predecessor.main()


if __name__ == "__main__":
    raise SystemExit(main())
