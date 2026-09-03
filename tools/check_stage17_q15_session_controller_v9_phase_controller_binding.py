#!/usr/bin/env python3
"""D-144 regression proving `stage17_q15_session_controller_v2.py`'s own
`execute_session` reaches the current `journal_runtime` regardless of
`stage17_q15_session_controller_v8.py`'s own fixed-hop-count reassignment
loop (inherited unchanged from `v7.py`) falling one hop short of
patching `v2.py`'s `phase_controller` global directly to the newest
generation.

Real, direct inspection (this session, ADR-0144) found `v2.phase_
controller` is bound to `stage17_phase_controller_v10`, not `stage17_
phase_controller_v4` -- repointed there by an earlier generation's own
reassignment, before the fixed-hop-count pattern the `v6`/`v7`/`v8`
family later adopted. This regression proves that binding is still safe:
`stage17_phase_controller_v12`'s own walk-until-absent reassignment
(ADR-0144) patches `journal_runtime` directly onto *every* module in the
`v4`-`v12` phase-controller chain, `v10` included -- not only the final
`v4` target -- so `v2.phase_controller.journal_runtime` and `stage17_
phase_controller_v4.journal_runtime` always agree, independent of which
specific generation `v2.phase_controller` happens to reference. It does
not assert `v2.phase_controller is stage17_phase_controller_v12`
(that would be false, and is not required for correctness) -- only that
whichever module it is bound to carries the current journal.
"""

from __future__ import annotations

import argparse
import sys


class CheckError(RuntimeError):
    pass


def self_test() -> None:
    import stage17_q15_session_controller_v9  # noqa: F401  (runs the reassignment)
    import stage17_q15_session_controller_v2 as v2
    import stage17_phase_controller_v4 as phase_controller_v4

    if not hasattr(v2.phase_controller, "journal_runtime"):
        raise CheckError(
            "regression: stage17_q15_session_controller_v2's own "
            "phase_controller binding must carry a journal_runtime "
            "attribute"
        )
    if v2.phase_controller.journal_runtime.__name__ != "stage17_state_journal_v33":
        raise CheckError(
            "regression: stage17_q15_session_controller_v2's own "
            "phase_controller.journal_runtime must resolve to "
            "stage17_state_journal_v33, matching stage17_phase_"
            "controller_v4.journal_runtime, regardless of which exact "
            "phase-controller generation v2.phase_controller references"
        )
    if (v2.phase_controller.journal_runtime.__name__
            != phase_controller_v4.journal_runtime.__name__):
        raise CheckError(
            "regression: stage17_q15_session_controller_v2.phase_"
            "controller.journal_runtime must agree with stage17_phase_"
            "controller_v4.journal_runtime"
        )
    if v2.phase_controller.prepare_action.__module__ not in {
        "stage17_phase_controller_v4", "stage17_phase_controller_v5",
    }:
        raise CheckError(
            "regression: stage17_q15_session_controller_v2.phase_"
            "controller.prepare_action must still resolve through v4's "
            "real implementation (via v5's delegating wrapper)"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    try:
        self_test()
    except Exception as exception:
        print(
            "stage17-q15-session-controller-v9-phase-controller-binding: "
            f"FAIL: {exception}",
            file=sys.stderr,
        )
        return 1
    print("stage17-q15-session-controller-v9-phase-controller-binding: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
