#!/usr/bin/env python3
"""Regression proving stage17_output_registry_v6's `_msr_map` fix actually
works, and is actually wired into `validate_worker_result`'s own call
path (via the module-global reassignment onto the shared `v4` module),
not merely defined and never reached.

The real, reproduced gap this proves fixed: a real Q15-W worker run
against the 06_3EH/{0,1,8} mapping would produce a schema-valid
`restore_readback`/`prestate` pair for CPUs 0/1/8, but `v4`'s own
`_msr_map` (inherited unchanged through `v5.py`, whose own fix is
unrelated) hardcoded `if set(result) != {0, 1, 26}`, rejecting it with
"MSR evidence does not cover CPUs 0/1/26" at output-admission time --
after a real MSR write to live hardware, not before it.
"""

from __future__ import annotations

import argparse
import sys


class CheckError(RuntimeError):
    pass


def _msr(cpus: tuple[int, ...]) -> list[dict[str, object]]:
    return [{"cpu": cpu, "complete_value_hex": f"{index:016x}"}
            for index, cpu in enumerate(cpus)]


def self_test() -> None:
    import stage17_output_registry_v6 as fixed
    import stage17_output_registry_v4 as base

    if base._msr_map is not fixed._msr_map:
        raise CheckError(
            "regression: stage17_output_registry_v4's own _msr_map "
            "global -- the one validate_worker_result actually reads -- "
            "must be patched to v6's fixed function"
        )

    old_mapping = fixed._msr_map(_msr((0, 1, 26)))
    if old_mapping != {0: "0000000000000000", 1: "0000000000000001",
                       26: "0000000000000002"}:
        raise CheckError(
            f"regression: 06_55H's own {{0,1,26}} MSR evidence must still "
            f"parse correctly, got {old_mapping}"
        )

    new_mapping = fixed._msr_map(_msr((0, 1, 8)))
    if new_mapping != {0: "0000000000000000", 1: "0000000000000001",
                       8: "0000000000000002"}:
        raise CheckError(
            f"regression: ADR-0173's own {{0,1,8}} MSR evidence must now "
            f"parse correctly, got {new_mapping}"
        )

    for bad in (
        _msr((0, 1, 27)),  # neither registered mapping's own set
        _msr((0, 8)),      # wrong length
        _msr((0, 1, 8, 26)),  # union of both sets, not either one alone
    ):
        try:
            fixed._msr_map(bad)
        except fixed.OutputAdmissionError:
            continue
        raise CheckError(
            f"regression: genuinely malformed MSR evidence {bad} must "
            "still be rejected, not silently accepted by the widened check"
        )

    duplicate = _msr((0, 1, 8)) + [{"cpu": 0, "complete_value_hex": "0" * 16}]
    try:
        fixed._msr_map(duplicate)
    except fixed.OutputAdmissionError:
        pass
    else:
        raise CheckError(
            "regression: a duplicated cpu entry must still be rejected"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        self_test()
    except CheckError as exception:
        print(f"stage17-output-registry-v6-msr-map-check: FAIL: {exception}",
              file=sys.stderr)
        return 1
    print("stage17-output-registry-v6-msr-map-check: PASS "
          "(old mapping, new mapping, 3 negative, 1 duplicate)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
