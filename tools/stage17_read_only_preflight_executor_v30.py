#!/usr/bin/env python3
"""D-204: the policy30 executor uses policy56 before prospective admission."""
from __future__ import annotations

import pathlib

# Load all predecessor side effects before selecting the current journal.
import stage17_read_only_preflight_executor_v29 as predecessor
import stage17_read_only_preflight_executor_v25 as owner
import stage17_state_journal_v50 as current_journal

EXECUTOR_ID = "STAGE17-READ-ONLY-PREFLIGHT-EXECUTOR-v30"
_previous_identity_paths = owner.runtime_identity_paths


def runtime_identity_paths():
    paths = _previous_identity_paths()
    paths["executor"] = str(pathlib.Path(__file__).resolve())
    paths["state_journal"] = str(pathlib.Path(current_journal.__file__).resolve())
    return paths


def activate():
    current_journal.activate()
    owner.current_journal = current_journal
    owner.EXECUTOR_ID = EXECUTOR_ID
    owner.runtime_identity_paths = runtime_identity_paths


activate()
ActionExecutionError = predecessor.ActionExecutionError


def execute_once(**arguments):
    activate()
    return predecessor.execute_once(**arguments)


def main():
    activate()
    return predecessor.main()


if __name__ == "__main__":
    raise SystemExit(main())
