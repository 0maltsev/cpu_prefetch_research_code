#!/usr/bin/env python3
"""Additive successor to `stage17_read_only_preflight_executor_v25.py`
(ADR-0156, follow-up): the only change is which state-journal generation
this file's own `current_journal` binding resolves to.

`execute_once`'s own `_prospective_validation` re-validates `S17-EXT-001`
on every real preflight run, via `current_journal.validate_operational_
journal(...)`. `v25.py` hardcodes `current_journal` to `stage17_state_
journal_v35`, whose own `semantic` binding is `stage17_semantic_verifier_
v41` -- so this re-validation checks the admission root's files against
policy-v41's stale bindings (in particular `tools/stage17_operational_
cli_v11.py`'s pre-ADR-0156 hash) even when the admission root has been
freshly patched to ADR-0156's own policy-v42 shape, raising `bindings
tools__stage17_operational_cli_v11_py bytes drifted` -- a real, first-
time-observed reachability gap: no journal before `standv2-21` had ever
patched `cli_v11.py` after ADR-0131's original preflight-chain fix, so
this specific re-validation path had never been exercised against a
patched admission root before.

This file monkey-patches `current_journal` onto `v25`'s own module
object rather than copying `_prospective_validation`/`execute_once`'s
bodies, using the exact same technique `stage17_state_journal_v36.py`
itself already uses for its own `semantic` binding (and `stage17_phase_
controller_v14.py` for `journal_runtime`): a function's free variables
resolve against its own module's `__globals__` dict, looked up fresh on
every call, not a snapshot taken at def-time -- so reassigning `v25.
current_journal` here is enough, and is safe precisely because the
`runtime_closure` hash-pin only ever verifies file bytes on disk, never
in-memory attribute state, matching what the already-accepted `semantic`/
`journal_runtime` walks already rely on. `EXECUTOR_ID` updates to `v26`.

`runtime_identity_paths()` needs one more, different kind of fix: its
own `"executor"` entry reports `str(pathlib.Path(__file__).resolve())`,
and `__file__` is not a free variable that monkey-patching can redirect
-- it is set once, permanently, to whichever file the code defining the
function was actually loaded from (`v25.py`), regardless of any
attribute reassignment on that module afterward. Confirmed for real:
`base.runtime_identity_paths()["executor"]` still reported `_v25.py`'s
own path even after the `current_journal` monkey-patch above. So this
one entry is fixed by wrapping, not patching -- a fresh function,
defined here in `v26.py`, whose own `__file__` correctly resolves to
this file, that starts from the base result and overrides just that one
key. Confirmed by reading its body directly: no other entry in the
returned dict reads a bare `__file__`; every other key already reads
some *other* module's own `.__file__` attribute (`current_journal.
__file__`, `current_semantic.__file__`, etc.), which already reflects
the monkey-patch correctly.
"""

from __future__ import annotations

import pathlib

import stage17_read_only_preflight_executor_v25 as base
import stage17_state_journal_v36 as current_journal

base.current_journal = current_journal

EXECUTOR_ID = "STAGE17-READ-ONLY-PREFLIGHT-EXECUTOR-v26"
base.EXECUTOR_ID = EXECUTOR_ID


_base_runtime_identity_paths = base.runtime_identity_paths


def runtime_identity_paths() -> dict[str, str]:
    paths = _base_runtime_identity_paths()
    paths["executor"] = str(pathlib.Path(__file__).resolve())
    return paths


base.runtime_identity_paths = runtime_identity_paths

ActionExecutionError = base.ActionExecutionError
execute_once = base.execute_once
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
