#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v53 (ADR-0175: a
second, PRFCHW-free software-prefetch mapping).

Additive successor to `stage17_state_journal_v46.py`: the only change
is which semantic-verifier module the reassignment loop propagates to
the predecessor journal chain (`stage17_semantic_verifier_v53`, which
retargets `S17-EXT-004`'s own manifest dispatch to `stage17_
operational_semantics_v11.verify_manifest_v11` and re-pins `src/
runner/stage17_fixed_action.cpp`'s changed bytes). No other admission
logic changes here; a fresh journal on the new fixed build still needs
`S17-EXT-001` bound to this generation to admit the changed file at
all.

Reuses `v41.py`'s own fix verbatim: walk the whole `.predecessor` chain
to its actual end instead of hardcoding a hop count that silently
drifts every time this chain grows by one additive successor.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v53 as semantic
import stage17_state_journal_v46 as predecessor

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
