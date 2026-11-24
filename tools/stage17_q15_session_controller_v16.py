#!/usr/bin/env python3
"""Real Q15 session-controller successor fixing a fifth, independent
hardcoding of the 06_55H-only CPU set (ADR-0173's implementation note
6): `stage17_q15_session_controller_v10.py`'s own `_parse_prestate`
re-validates the real worker's own, already-schema-valid
`q15-r-output-v3.json` against a hardcoded module constant
`Q15_CPUS = (0, 1, 26)`, positionally zipped against the worker's
reported `prestate` array.

A real, live Q15-R attempt against the 06_3EH/{0,1,8} mapping (ADR-
0172/0173, after every prior C++/schema hardcoding in this chain was
already fixed) completed the full worker sequence again -- real MSR
prestate read on CPUs 0, 1, and 8, real H0 probes, a schema-valid
`cpu_model: 62`/`mapping_id: "INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1"`
output -- and was rejected one layer further up than the schema
check this same chain hit before: the session controller's own
`execute_session` (inherited unchanged through v11-v15) calls
`_parse_prestate(q15_r_output["prestate"])`, which still compares each
entry's `cpu` against the old `Q15_CPUS` tuple positionally and raises
"Q15-R complete prestate is malformed" the moment index 2 is `8`
instead of the hardcoded `26`.

`_parse_prestate` is a direct, shared function reference
(`stage17_q15_session_controller_v14.py:78`: `_parse_prestate =
_v10._parse_prestate`), not a copy -- so this generation does not
rewrite `execute_session` (a ~150-line function unrelated to this one
check) just to change one call. Instead it defines a corrected
`_parse_prestate` accepting either registered mapping's CPU set
(`(0, 1, 26)` or `(0, 1, 8)`) as a valid positional template, and
reassigns the *module global* `stage17_q15_session_controller_v14.
_parse_prestate` to it after import -- `execute_session`'s own body
resolves that name as a global in `v14`'s namespace at call time, so
this takes effect without touching `execute_session` itself. Same
technique `v15.py` itself already uses for `phase_controller`.
"""

from __future__ import annotations

import stage17_q15_session_controller_v15 as predecessor
import stage17_q15_session_controller_v14 as _v14
import stage17_q15_session_controller_v10 as _v10

Q15SessionError = _v10.Q15SessionError

# Both currently-registered hardware-prefetch mappings' own accepted
# CPU sets (platform.hpp's kHardwarePrefetchControlCpus / V5), in the
# same fixed positional order the real worker always reports prestate
# in. Exactly one of these must match in full; a worker output naming
# any other CPU set, or a genuinely malformed shape, is still rejected.
Q15_CPU_SETS: tuple[tuple[int, int, int], ...] = ((0, 1, 26), (0, 1, 8))


def _parse_prestate(values: object) -> tuple[tuple[int, int], ...]:
    if not isinstance(values, list):
        raise Q15SessionError("Q15-R complete prestate is absent")
    for candidate_cpus in Q15_CPU_SETS:
        if len(values) != len(candidate_cpus):
            continue
        parsed: list[tuple[int, int]] = []
        matched = True
        for expected_cpu, item in zip(candidate_cpus, values, strict=True):
            if (not isinstance(item, dict) or item.get("cpu") != expected_cpu
                    or not isinstance(item.get("complete_value_hex"), str)
                    or len(item["complete_value_hex"]) != 16):
                matched = False
                break
            try:
                value = int(item["complete_value_hex"], 16)
            except ValueError:
                matched = False
                break
            parsed.append((expected_cpu, value))
        if matched:
            return tuple(parsed)
    raise Q15SessionError("Q15-R complete prestate is malformed")


_v14._parse_prestate = _parse_prestate

main = predecessor.main
execute_session = predecessor.execute_session


if __name__ == "__main__":
    raise SystemExit(main())
