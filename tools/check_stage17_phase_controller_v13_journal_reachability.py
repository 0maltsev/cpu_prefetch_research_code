#!/usr/bin/env python3
"""D-145 regression for the phase-controller journal-reachability fix,
completed a third time.

The real, reproduced gap this proves fixed: ADR-0142's `stage17_phase_
controller_v11.py` hardcodes `import stage17_state_journal_v31 as
journal_runtime` -- a specific generation, not "whatever `cli_v11.py`
currently uses". ADR-0144's own `stage17_phase_controller_v12.py`
repeated the fix pointed at `v33`; ADR-0145 moves `cli_v11.py`'s own
`journal_runtime` to `v34` (folded into the same ADR as a real Q15
session failure-retention schema fix and its own bindings-completion),
immediately stranding `v12` again: `check_stage17_phase_controller_
v12_journal_reachability.py` kept reporting `PASS` throughout, because
it only asserts `v12`'s own hardcoded value, not live consistency with
`cli_v11.py`. This regression proves the completed fix directly:
importing `stage17_q15_session_controller_v11` (the new entrypoint) must
resolve `phase_controller` to `stage17_phase_controller_v13`, whose own
walk-until-absent reassignment must set `stage17_phase_controller_v4.py`'s
own `journal_runtime` global to `stage17_state_journal_v34` -- the same
generation `stage17_operational_cli_v11.py` itself now uses -- and that
import must, as a side effect, patch `stage17_state_journal_v12.py`'s own
`semantic` global to the current `stage17_semantic_verifier_v38`.

It does not attempt a full synthetic Q15-R admission cycle, for the same
reason `check_stage17_phase_controller_v12_journal_reachability.py`
did not (see that file's own docstring).
"""

from __future__ import annotations

import argparse
import sys


class CheckError(RuntimeError):
    pass


def self_test() -> None:
    import stage17_q15_session_controller_v11 as q15

    if q15.phase_controller.__name__ != "stage17_phase_controller_v13":
        raise CheckError(
            "regression: stage17_q15_session_controller_v11 must bind "
            "phase_controller to stage17_phase_controller_v13"
        )
    import stage17_phase_controller_v4 as phase_controller_v4
    if phase_controller_v4.journal_runtime.__name__ != "stage17_state_journal_v34":
        raise CheckError(
            "regression: stage17_phase_controller_v13's reassignment must "
            "reach stage17_phase_controller_v4.py's own journal_runtime "
            "and set it to stage17_state_journal_v34"
        )
    import stage17_state_journal_v12 as state_journal_v12
    if state_journal_v12.semantic.__name__ != "stage17_semantic_verifier_v38":
        raise CheckError(
            "regression: importing stage17_state_journal_v34 (transitively, "
            "via stage17_phase_controller_v13) must patch stage17_state_"
            "journal_v12.py's own semantic to stage17_semantic_verifier_v38"
        )
    if str(state_journal_v12.SEMANTIC_POLICY_PATH) != (
        "config/stage17/stage17-operational-evidence-admission-policy-v38.json"
    ):
        raise CheckError(
            "regression: stage17_state_journal_v12's SEMANTIC_POLICY_PATH "
            "must resolve to the current admission policy v38"
        )
    import stage17_phase_controller_v13 as phase_controller_v13
    for name in (
        "ControllerError", "PreparedAction", "prepare_action", "execute_once",
        "main", "_runtime_from_context", "_validate_action_inputs",
    ):
        if not hasattr(phase_controller_v13, name):
            raise CheckError(
                f"regression: stage17_phase_controller_v13 must re-export {name}"
            )
    import stage17_phase_controller_v12 as phase_controller_v12
    if phase_controller_v13.prepare_action is not phase_controller_v12.prepare_action:
        raise CheckError(
            "regression: stage17_phase_controller_v13.prepare_action must be "
            "the same object as stage17_phase_controller_v12's own "
            "(re-exported unchanged, not a copy)"
        )
    if phase_controller_v13.prepare_action.__module__ not in {
        "stage17_phase_controller_v4", "stage17_phase_controller_v5",
    }:
        raise CheckError(
            "regression: stage17_phase_controller_v13.prepare_action must "
            "still resolve through v4's real implementation (via v5's "
            "delegating wrapper), not some other indirection"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    try:
        self_test()
    except Exception as exception:
        print(
            f"stage17-phase-controller-v13-journal-reachability: FAIL: {exception}",
            file=sys.stderr,
        )
        return 1
    print("stage17-phase-controller-v13-journal-reachability: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
