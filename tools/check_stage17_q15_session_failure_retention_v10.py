#!/usr/bin/env python3
"""D-145 regression proving the real Q15 session failure-retention
schema fix: `stage17_q15_session_controller_v10.py`'s own
`_write_session_failure` must succeed when `cleanup_error_occurred=True`
-- the exact real, reproduced scenario that failed twice on the real
stand (`'Q15_R_WAIT:SUPERVISOR_FALLBACK'` and `'Q15_W_ADMISSION:
SUPERVISOR_FALLBACK'`, neither of which `stage17-q15-session-failure-
v1.schema.json`'s own `failure_stage` enum ever accepted).

This calls `_write_session_failure` directly with a minimal, synthetic
`q15_r`/cause/cleanup context -- it does not spawn a real worker, open
SSH, or touch real hardware. It proves two things: (1) the record is
successfully written and independently re-validates against
`stage17-q15-session-failure-v2.schema.json`, with `failure_stage` kept
as a clean enum value (`"Q15_W_ADMISSION"`, no suffix) and a new,
independent `cleanup_error_occurred: true` field instead; and (2) the
same call against `stage17_q15_session_controller_v2.py`'s own,
unfixed `_write_session_failure` -- called the way `execute_session`
itself calls it, string-concatenating `":SUPERVISOR_FALLBACK"` onto the
stage -- still reproduces the real, historical schema rejection,
confirming this regression is actually exercising the real bug and not
a strawman.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import tempfile
from types import SimpleNamespace


class CheckError(RuntimeError):
    pass


def _prepared_action(root: pathlib.Path) -> SimpleNamespace:
    return SimpleNamespace(
        root=root,
        request={
            "action_inputs": {"session_id": "SYNTHETIC-D145-SESSION"},
            "attempt_id": "SYNTHETIC-D145-Q15R-ATTEMPT",
        },
    )


def self_test(root: pathlib.Path) -> None:
    import stage17_q15_session_controller_v10 as fixed
    import stage17_q15_session_controller_v2 as unfixed

    cause = TimeoutError("timed out")

    with tempfile.TemporaryDirectory(prefix="stage17-d145-retention-") as text:
        directory = pathlib.Path(text)
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fixed._write_session_failure(
                directory_fd=directory_fd,
                q15_r=_prepared_action(root),
                q15_w=None,
                stage="Q15_W_ADMISSION",
                cleanup_error_occurred=True,
                cause=cause, cleanup=None,
                quarantine_sha256=None, supervisor_restore=None,
            )
        except Exception as exception:
            raise CheckError(
                f"regression: v10's fixed _write_session_failure must "
                f"succeed with cleanup_error_occurred=True, got: {exception}"
            ) from exception

        written = directory / "stage17-q15-session-failure-v2.json"
        if not written.is_file():
            raise CheckError(
                "regression: v10 must write stage17-q15-session-failure-v2.json"
            )
        import json
        from jsonschema import Draft202012Validator
        record = json.loads(written.read_bytes())
        if record["failure_stage"] != "Q15_W_ADMISSION":
            raise CheckError(
                "regression: failure_stage must stay a clean enum value, "
                f"got: {record['failure_stage']!r}"
            )
        if record["cleanup_error_occurred"] is not True:
            raise CheckError(
                "regression: cleanup_error_occurred must be true"
            )
        schema_path = root / "config/schemas/stage17-q15-session-failure-v2.schema.json"
        schema = json.loads(schema_path.read_bytes())
        errors = list(Draft202012Validator(schema).iter_errors(record))
        if errors:
            raise CheckError(
                f"regression: written record must validate cleanly against "
                f"v2 schema, got: {errors[0].message}"
            )

    with tempfile.TemporaryDirectory(prefix="stage17-d145-retention-old-") as text:
        directory = pathlib.Path(text)
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            unfixed._write_session_failure(
                directory_fd=directory_fd,
                q15_r=_prepared_action(root),
                q15_w=None,
                stage="Q15_W_ADMISSION" + ":SUPERVISOR_FALLBACK",
                cause=cause, cleanup=None,
                quarantine_sha256=None, supervisor_restore=None,
            )
        except unfixed.Q15SessionError as exception:
            if "rejected" not in str(exception):
                raise CheckError(
                    "regression: v2's own unfixed path must fail with a "
                    f"schema-rejection message, got: {exception}"
                ) from exception
        else:
            raise CheckError(
                "regression: v2's own unfixed _write_session_failure must "
                "still reproduce the real historical schema rejection when "
                "called the way execute_session calls it -- if this no "
                "longer fails, this regression is not exercising the real "
                "bug any more"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).parents[1])
    arguments = parser.parse_args()
    try:
        self_test(arguments.root.resolve())
    except Exception as exception:
        print(
            f"stage17-q15-session-failure-retention-v10: FAIL: {exception}",
            file=sys.stderr,
        )
        return 1
    print("stage17-q15-session-failure-retention-v10: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
