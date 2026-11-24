#!/usr/bin/env python3
"""D-146 regression proving the real Q15 session `execute_session`
wiring bug is actually fixed, not just aliased.

The real, reproduced gap this proves fixed: `stage17_q15_session_
controller_v2.py`'s own `run_start` calls `execute_session(...)` as a
bare name, resolved against `v2.py`'s own module globals at call time.
`stage17_q15_session_controller_v11.py` (ADR-0145) only bound a new
`execute_session` attribute in *its own* file -- which nothing calls,
since the real `--start` entrypoint resolves through `predecessor.main`
down to `v2.py`'s own `run_start`. Two real Q15-R sessions on the real
stand proved this concretely: the failure-retention record still failed
with the exact old, unfixed schema-rejection text after ADR-0145's
bundle was staged.

This regression checks the fact that actually matters:
`stage17_q15_session_controller_v2.execute_session` -- the name
`run_start` really reads -- must itself become `stage17_q15_session_
controller_v10.execute_session` (ADR-0145's real fix) after importing
`stage17_q15_session_controller_v12`. It does not accept `v11.py`'s own
local binding as sufficient, and asserts directly that `v2.py`'s global
was truly mutated in place, not merely shadowed.
"""

from __future__ import annotations

import argparse
import sys


class CheckError(RuntimeError):
    pass


def self_test() -> None:
    import stage17_q15_session_controller_v12 as q15
    import stage17_q15_session_controller_v10 as v10
    import stage17_q15_session_controller_v2 as v2

    if v2.execute_session is not v10.execute_session:
        raise CheckError(
            "regression: stage17_q15_session_controller_v2's own "
            "execute_session global -- the one run_start actually reads "
            "-- must be patched to stage17_q15_session_controller_v10's "
            "real fix. v11.py's own local rebind was not sufficient; "
            "this is the exact real bug two real Q15-R sessions on the "
            "real stand reproduced."
        )
    if q15.phase_controller.__name__ != "stage17_phase_controller_v14":
        raise CheckError(
            "regression: stage17_q15_session_controller_v12 must bind "
            "phase_controller to stage17_phase_controller_v14"
        )
    import stage17_phase_controller_v4 as phase_controller_v4
    if phase_controller_v4.journal_runtime.__name__ != "stage17_state_journal_v35":
        raise CheckError(
            "regression: stage17_phase_controller_v14's reassignment must "
            "reach stage17_phase_controller_v4.py's own journal_runtime "
            "and set it to stage17_state_journal_v35"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    try:
        self_test()
    except Exception as exception:
        print(
            f"stage17-q15-session-execute-session-wiring-v12: FAIL: {exception}",
            file=sys.stderr,
        )
        return 1
    print("stage17-q15-session-execute-session-wiring-v12: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
