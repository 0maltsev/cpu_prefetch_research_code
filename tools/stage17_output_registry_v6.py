#!/usr/bin/env python3
"""Additive successor to `stage17_output_registry_v5.py`: fixes `_msr_map`'s
own hardcoded `{0, 1, 26}` CPU-set check (ADR-0172/0173's 06_55H-only
literal, independently reintroduced here -- a seventh such occurrence
found this session, after the C++ MSR backend (note 4), 22 schema files
(note 5), the session controller's own `_parse_prestate` (note 6), and
unrelated to `v5.py`'s own ADR-0161 `_validate_run_families` fix, which
this file leaves untouched).

`_msr_map` is reached from Q15-W's own output-admission check inside
`validate_worker_result` (the real worker's `restore_readback` vs the
admitted request's `prestate`), and from the Q16/pilot hardware-control
checks (out of this session's immediate scope, but sharing the same
helper). Rejecting a schema-valid `{0,1,8}` restore_readback/prestate
here would have failed a real Q15-W write to live 06_3EH hardware at
output-admission time -- caught by reading the code before the live
attempt, not by a failed run burning the one-shot authorization.

`validate_worker_result` and every other function in `v4` call `_msr_map`
as a bare name resolved against `v4`'s own module globals at call time
(the same free-variable-resolution rule `v5.py` itself already relies on
for its own, unrelated fix) -- so reassigning the shared `v4._msr_map`
here is sufficient; no caller needs to change, and this file does not
need to be imported "as output_registry" anywhere, only once, for its
import-time side effect, before any admission check runs.
"""

from __future__ import annotations

import stage17_output_registry_v5 as predecessor

OutputAdmissionError = predecessor.OutputAdmissionError
_base = predecessor.base

ACCEPTED_MSR_CPU_SETS: tuple[frozenset[int], ...] = (
    frozenset({0, 1, 26}),
    frozenset({0, 1, 8}),
)


def _msr_map(values: object) -> dict[int, str]:
    if not isinstance(values, list):
        raise OutputAdmissionError("MSR evidence is not an array")
    result: dict[int, str] = {}
    for item in values:
        if (not isinstance(item, dict) or set(item) != {
                "cpu", "complete_value_hex"}
                or item.get("cpu") in result):
            raise OutputAdmissionError("MSR evidence is malformed or duplicated")
        result[item["cpu"]] = item["complete_value_hex"]
    if frozenset(result) not in ACCEPTED_MSR_CPU_SETS:
        raise OutputAdmissionError(
            "MSR evidence does not cover an accepted CPU set"
        )
    return result


_base._msr_map = _msr_map
