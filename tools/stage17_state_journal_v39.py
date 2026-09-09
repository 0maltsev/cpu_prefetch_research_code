#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v45 (ADR-0159).

Additive successor to `stage17_state_journal_v38.py`: the only change
is which semantic-verifier module the reassignment loop propagates to
the predecessor journal chain (`stage17_semantic_verifier_v45`, ADR-
0159's fix for the fixed-action worker's compiled request-size bound).
No admission logic changes here -- policy v45 only re-pins `src/runner/
stage17_fixed_action.cpp`'s changed hash; a fresh journal on the new
pilot-candidate build still needs `S17-EXT-001` bound to this
generation to admit the changed file at all.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v45 as semantic
import stage17_state_journal_v16 as predecessor


for module in (
    predecessor, predecessor.predecessor,
    predecessor.predecessor.predecessor,
    predecessor.predecessor.predecessor.predecessor,
    predecessor.predecessor.predecessor.predecessor.predecessor,
):
    module.semantic = semantic
    module.SEMANTIC_POLICY_PATH = semantic.POLICY_PATH

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
