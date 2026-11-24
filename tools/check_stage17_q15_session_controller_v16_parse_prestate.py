#!/usr/bin/env python3
"""Regression proving stage17_q15_session_controller_v16's _parse_prestate
fix actually works, and is actually wired into execute_session's own
call path, not merely defined and never reached.

The real, reproduced gap this proves fixed: a real Q15-R worker run
against the 06_3EH/{0,1,8} mapping produced a schema-valid
q15-r-output-v3.json (cpu_model=62, prestate CPUs 0/1/8), but the
session controller's own execute_session (inherited unchanged from
v14 through v15) called the old v10._parse_prestate, which rejected it
with "Q15-R complete prestate is malformed" because its own hardcoded
Q15_CPUS = (0, 1, 26) never matched index 2's real value of 8.
"""

from __future__ import annotations

import argparse
import sys


class CheckError(RuntimeError):
    pass


def _prestate(cpus: tuple[int, ...]) -> list[dict[str, object]]:
    return [{"cpu": cpu, "complete_value_hex": f"{index:016x}"}
            for index, cpu in enumerate(cpus)]


def self_test() -> None:
    import stage17_q15_session_controller_v16 as q15
    import stage17_q15_session_controller_v14 as v14

    if v14._parse_prestate is not q15._parse_prestate:
        raise CheckError(
            "regression: stage17_q15_session_controller_v14's own "
            "_parse_prestate global -- the one execute_session actually "
            "reads -- must be patched to v16's fixed function"
        )

    old_mapping = q15._parse_prestate(_prestate((0, 1, 26)))
    if old_mapping != ((0, 0), (1, 1), (26, 2)):
        raise CheckError(
            f"regression: 06_55H's own {{0,1,26}} prestate must still parse "
            f"correctly, got {old_mapping}"
        )

    new_mapping = q15._parse_prestate(_prestate((0, 1, 8)))
    if new_mapping != ((0, 0), (1, 1), (8, 2)):
        raise CheckError(
            f"regression: ADR-0173's own {{0,1,8}} prestate must now parse "
            f"correctly, got {new_mapping}"
        )

    for bad in (
        _prestate((0, 1, 27)),  # neither registered mapping's own set
        _prestate((0, 8, 1)),  # right CPUs, wrong order
        _prestate((0, 1)),  # wrong length
    ):
        try:
            q15._parse_prestate(bad)
        except q15.Q15SessionError:
            continue
        raise CheckError(
            f"regression: genuinely malformed prestate {bad} must still be "
            "rejected, not silently accepted by the widened check"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        self_test()
    except CheckError as exception:
        print(f"q15-session-controller-v16-parse-prestate-check: FAIL: {exception}",
              file=sys.stderr)
        return 1
    print("q15-session-controller-v16-parse-prestate-check: PASS "
          "(old mapping, new mapping, 3 negative)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
