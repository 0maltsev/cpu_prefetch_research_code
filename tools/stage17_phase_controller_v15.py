#!/usr/bin/env python3
"""Phase-controller successor rebinding fixed-action execution to
`stage17_fixed_action_executor_v5.py` (the ADR-0131-parity fix for the
`empty or nonpositive NSpgid` crash on a real host's kernel threads --
see that file's own docstring for the full root-cause account).

`execute_once` is defined once, in `stage17_phase_controller_v4.py`, and
every successor since (`v5` through `v14`) only ever re-exports it
(`execute_once = predecessor.execute_once`) rather than redefining it.
Because a function's free variables resolve against the module that
*defines* it, not the module that imports it (ADR-0126, ADR-0131), that
means `execute_once`'s call to `executor.execute_fixed_action` has always
resolved to `stage17_fixed_action_executor_v4`'s own module global no
matter which successor a caller imports -- monkey-patching `v4.executor`
from outside would silently change what actually runs without changing
`v4.py`'s own file bytes, undermining the exact guarantee the
`runtime_closure` hash-pin exists to provide. So, exactly as ADR-0131
did for the read-only-preflight chain, the only correct fix is a fresh
`execute_once` here, copied verbatim from `v4` except for which
`executor` module it closes over. `prepare_action` is untouched by this
bug (it never references `executor`) and stays a plain re-export.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import stage17_fixed_action_executor_v5 as executor
import stage17_phase_controller_v14 as predecessor


ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
prepare_action = predecessor.prepare_action
_runtime_from_context = predecessor._runtime_from_context
_validate_action_inputs = predecessor._validate_action_inputs


def execute_once(
    *, repository_root: pathlib.Path, journal: pathlib.Path,
    journal_directory: pathlib.Path, operational_evidence_root: pathlib.Path,
    authorization_path: pathlib.Path,
    signature_path: pathlib.Path, pilot_archive: pathlib.Path | None = None,
    pilot_sidecar: pathlib.Path | None = None,
    synthetic_test_only: bool = False,
) -> executor.ExecutionOutcome:
    prepared = prepare_action(
        repository_root=repository_root, journal=journal,
        journal_directory=journal_directory,
        operational_evidence_root=operational_evidence_root,
        authorization_path=authorization_path, signature_path=signature_path,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        synthetic_test_only=synthetic_test_only,
    )
    if prepared.authorization["action_id"] in {"Q15-R", "Q15-W"}:
        raise ControllerError(
            "Q15 actions require the phase-spanning session controller"
        )
    return executor.execute_fixed_action(
        repository_root=prepared.root, authorization=prepared.authorization,
        authorization_bytes=prepared.authorization_bytes,
        request=prepared.request, request_bytes=prepared.request_bytes,
        worker_binding=prepared.runtime, worker_path=prepared.worker_path,
        release_binding=prepared.release,
        output_root=pathlib.Path(
            prepared.request["evidence_root_binding"]["absolute_path"]
        ),
        synthetic_test_only=synthetic_test_only,
    )


def main() -> int:
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
        print(f"stage17-phase-controller-v15: FAIL: {exception}", file=sys.stderr)
        return 1
    print("stage17-phase-controller-v15: PASS action=COMPLETED authority=STAGE17_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
