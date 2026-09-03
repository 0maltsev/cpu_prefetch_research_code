#!/usr/bin/env python3
"""D-142 regression for the phase-controller/Q15-session-controller
journal-reachability fix.

The real, reproduced bug this proves fixed: `stage17_phase_controller_
v4.py`'s real `prepare_action` resolves `journal_runtime` as a free
variable against its own module globals. That global was last set by
`stage17_phase_controller_v6.py` (to `stage17_state_journal_v14`) and no
generation from `v7` through `v10` ever reassigned it again -- their own
fixed-hop-count reassignment loops never reach `v4`. This left the
entire phase-controller/Q15-session-controller invocation path (its own
separate process, its own separate import graph from
`stage17_operational_cli_v11.py`) permanently pinned to a years-stale
semantic-verifier generation, discovered only by this session's
first-ever real `Q15-R` attempt, which failed locally (no stand
contact) with "runtime_closure stage17_read_only_preflight_executor_v12
cannot be opened safely" -- `v18`'s own frozen runtime closure
referencing a long-superseded executor file correctly absent from the
current bundle.

This regression proves the structural fix directly: importing
`stage17_q15_session_controller_v8` (the new entrypoint) must resolve
`phase_controller` to `stage17_phase_controller_v11`, whose own walk-
until-absent reassignment must set `stage17_phase_controller_v4.py`'s
own `journal_runtime` global to `stage17_state_journal_v31` -- the same
generation `stage17_operational_cli_v11.py` itself uses -- and that
import must, as a side effect, patch `stage17_state_journal_v12.py`'s
own `semantic` global to the current `stage17_semantic_verifier_v35`
(proving `v31`'s own reassignment loop actually ran, not just that some
variable happens to be named correctly).

It does not attempt a full synthetic Q15-R admission cycle: `prepare_
action`'s own cross-checks for `Q15-R` require real, admitted
`S17-EXT-001`/`S17-EXT-002`/`S17-EXT-003` resolutions with a real
SSHSIG-verified trust anchor, and building that synthetically from
scratch (unlike the read-only-preflight executor's own attestation
fixture) is a materially larger undertaking than this narrow
reachability fix warrants. The fix was additionally verified directly
against the real, already-admitted evidence during this session: a real,
non-mutating `prepare_action(...)` call (no execution, no stand
contact) against the real fifteenth admission root and the real,
already-signed `Q15-R` authorization succeeded where it previously
raised the exact real error above -- see ADR-0142's own text.
"""

from __future__ import annotations

import argparse
import sys


class CheckError(RuntimeError):
    pass


def self_test() -> None:
    import stage17_q15_session_controller_v8 as q15

    if q15.phase_controller.__name__ != "stage17_phase_controller_v11":
        raise CheckError(
            "regression: stage17_q15_session_controller_v8 must bind "
            "phase_controller to stage17_phase_controller_v11"
        )
    import stage17_phase_controller_v4 as phase_controller_v4
    if phase_controller_v4.journal_runtime.__name__ != "stage17_state_journal_v31":
        raise CheckError(
            "regression: stage17_phase_controller_v11's reassignment must "
            "reach stage17_phase_controller_v4.py's own journal_runtime "
            "and set it to stage17_state_journal_v31"
        )
    import stage17_state_journal_v12 as state_journal_v12
    if state_journal_v12.semantic.__name__ != "stage17_semantic_verifier_v35":
        raise CheckError(
            "regression: importing stage17_state_journal_v31 (transitively, "
            "via stage17_phase_controller_v11) must patch stage17_state_"
            "journal_v12.py's own semantic to stage17_semantic_verifier_v35"
        )
    if str(state_journal_v12.SEMANTIC_POLICY_PATH) != (
        "config/stage17/stage17-operational-evidence-admission-policy-v35.json"
    ):
        raise CheckError(
            "regression: stage17_state_journal_v12's SEMANTIC_POLICY_PATH "
            "must resolve to the current admission policy v35"
        )
    import stage17_phase_controller_v11 as phase_controller_v11
    for name in (
        "ControllerError", "PreparedAction", "prepare_action", "execute_once",
        "main", "_runtime_from_context", "_validate_action_inputs",
    ):
        if not hasattr(phase_controller_v11, name):
            raise CheckError(
                f"regression: stage17_phase_controller_v11 must re-export {name}"
            )
    import stage17_phase_controller_v10 as phase_controller_v10
    if phase_controller_v11.prepare_action is not phase_controller_v10.prepare_action:
        raise CheckError(
            "regression: stage17_phase_controller_v11.prepare_action must be "
            "the same object as stage17_phase_controller_v10's own "
            "(re-exported unchanged, not a copy)"
        )
    # `prepare_action_v11` chains v11 -> v10 -> ... -> v6 (plain aliases) ->
    # v5 (a thin wrapper calling `predecessor.prepare_action(**arguments)`,
    # not a plain alias) -> v4's real implementation. Its `__module__` is
    # therefore `stage17_phase_controller_v5`, not `_v4` -- that wrapper
    # still resolves `predecessor.prepare_action` fresh on every call, so it
    # always reaches v4's real, current implementation regardless. What
    # matters for this fix is proven above: v4's own `journal_runtime`
    # global (the free variable its real body actually reads) now resolves
    # to `stage17_state_journal_v31`.
    if phase_controller_v11.prepare_action.__module__ not in {
        "stage17_phase_controller_v4", "stage17_phase_controller_v5",
    }:
        raise CheckError(
            "regression: stage17_phase_controller_v11.prepare_action must "
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
            f"stage17-phase-controller-v11-journal-reachability: FAIL: {exception}",
            file=sys.stderr,
        )
        return 1
    print("stage17-phase-controller-v11-journal-reachability: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
