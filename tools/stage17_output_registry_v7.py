#!/usr/bin/env python3
"""Additive successor to `stage17_output_registry_v6.py`: re-pins `v4`'s own
`PLAN_PATH`/`PLAN_SCHEMA_PATH` to `stage17-fixed-phase-actions-v5.json` (ADR-
0175's PRFCHW-free software-prefetch mapping bumped `Q15_R_SOFTWARE_PREFETCH_
RAW`'s own `schema_identity`/`schema_path` from `/1` to `/2`, since
`publish_q15_r` now emits that schema version and a real, non-hardcoded
`mapping_id`). `v6.py`'s own `_msr_map` fix is unrelated and left untouched.

Confirmed live: a real Q15-R session on `cpu-prefetch-v5` under the *old*
registry (still pinned to the `/1` identity) wrote a genuinely correct
`q15-r-software-prefetch-raw-v1.json` (`mapping_id: "X86-64-PREFETCHT0-ONLY-
v1"`, `schema_version: ".../2"`), then failed at `OutputAdmissionError:
"fixed action output set differs from registry"` when the session controller
cross-checked the worker's real output set against `v4`'s still-`/1`
`definition["outputs"]` entry -- the measurement itself was never wrong, only
this registry's own expectation was stale.

`pin_registry` resolves `PLAN_PATH`/`PLAN_SCHEMA_PATH` as bare names against
`v4`'s own module globals at call time (the same free-variable-resolution
rule `v5.py`/`v6.py` already rely on for their own, unrelated fixes) -- so
reassigning them on the shared `v4` module here is sufficient; no caller
needs to change, and this file does not need to be imported "as
output_registry" anywhere, only once, for its import-time side effect,
before any admission check runs.
"""

from __future__ import annotations

import pathlib

import stage17_output_registry_v6 as predecessor

OutputAdmissionError = predecessor.OutputAdmissionError
_base = predecessor._base

_base.PLAN_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-fixed-phase-actions-v5.json"
)
_base.PLAN_SCHEMA_PATH = pathlib.PurePosixPath(
    "config/schemas/stage17-fixed-phase-actions-v5.schema.json"
)
