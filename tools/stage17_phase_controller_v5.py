#!/usr/bin/env python3
"""Policy-v15 Stage 17 controller compatibility successor.

Controller v4 owns the accepted action semantics.  This successor changes only
the journal runtime used before action preparation and execution.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import stage17_phase_controller_v4 as predecessor
import stage17_state_journal_v13 as journal_runtime


predecessor.journal_runtime = journal_runtime

ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction


def prepare_action(**arguments: Any) -> PreparedAction:
    return predecessor.prepare_action(**arguments)


def execute_once(**arguments: Any):
    return predecessor.execute_once(**arguments)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--repository-root", type=pathlib.Path, required=True)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--journal-directory", type=pathlib.Path, required=True)
    parser.add_argument("--operational-evidence-root", type=pathlib.Path,
                        required=True)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    parser.add_argument("--signature", type=pathlib.Path, required=True)
    parser.add_argument("--pilot-archive", type=pathlib.Path)
    parser.add_argument("--pilot-sidecar", type=pathlib.Path)
    arguments = parser.parse_args()
    try:
        execute_once(
            repository_root=arguments.repository_root,
            journal=arguments.journal,
            journal_directory=arguments.journal_directory,
            operational_evidence_root=arguments.operational_evidence_root,
            authorization_path=arguments.authorization,
            signature_path=arguments.signature,
            pilot_archive=arguments.pilot_archive,
            pilot_sidecar=arguments.pilot_sidecar,
            synthetic_test_only=False,
        )
    except BaseException as exception:
        print(f"stage17-phase-controller-v5: FAIL: {exception}", file=sys.stderr)
        return 1
    print("stage17-phase-controller-v5: PASS action=COMPLETED authority=STAGE17_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
