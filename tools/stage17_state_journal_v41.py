#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v47 (ADR-0168).

Additive successor to `stage17_state_journal_v40.py`: the only change
is which semantic-verifier module the reassignment loop propagates to
the predecessor journal chain (`stage17_semantic_verifier_v47`,
ADR-0168's fix re-pinning `src/runner/stage17_fixed_action.cpp`'s
changed hash a third time, after ADR-0159/v45 and ADR-0166/v46 already
re-pinned it). No admission logic changes here; a fresh journal on the
new pilot-candidate build still needs `S17-EXT-001` bound to this
generation to admit the changed file at all.

`v40`'s own loop hardcoded a 5-hop span (`_v16` through 4 more
`.predecessor` hops) starting from `predecessor.predecessor`, which at
`v40`'s own generation happened to land exactly on the module that
owns `_policy`/the `semantic` global it consults
(`stage17_state_journal_v12.py`). Copying that same 5-hop pattern here
shifts by one -- this module's own `predecessor.predecessor` starts
one level shallower (`v39` itself, not `v16`) -- and silently misses
`v12`, reproducing exactly the `bindings ...
src__runner__stage17_fixed_action_cpp file identity/size drifted`
failure this chain exists to prevent (confirmed live: a real
`admit-resolution` attempt failed this way, traced by hand to `v12`'s
un-patched `semantic` global still pointing at `v46`). Fixed by
walking the whole `.predecessor` chain to its actual end instead of
hardcoding a hop count that silently drifts every time this chain
grows by one additive successor -- re-assigning `module.semantic` is
idempotent, last write wins, so patching every reachable ancestor
(even ones that turn out not to consult it) is always safe.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v47 as semantic
import stage17_state_journal_v40 as predecessor

_module = predecessor.predecessor
while True:
    _module.semantic = semantic
    _module.SEMANTIC_POLICY_PATH = semantic.POLICY_PATH
    if not hasattr(_module, "predecessor"):
        break
    _module = _module.predecessor

SEMANTIC_POLICY_PATH = semantic.POLICY_PATH
SCHEMA_PATHS = predecessor.SCHEMA_PATHS
JournalError = predecessor.JournalError
ExternalInputResolution = predecessor.ExternalInputResolution
StateTransition = predecessor.StateTransition
OperationalJournalValidation = predecessor.OperationalJournalValidation


def validate_operational_journal(**arguments: Any) -> OperationalJournalValidation:
    return predecessor.validate_operational_journal(**arguments)


def checked_in_status(root: pathlib.Path) -> OperationalJournalValidation:
    latest = root.resolve() / "config/stage17/journal/stage17-state-journal-000000.json"
    return validate_operational_journal(
        repository_root=root.resolve(), evidence_root=root.resolve(),
        latest_journal=latest, journal_directory=latest.parent,
    )
