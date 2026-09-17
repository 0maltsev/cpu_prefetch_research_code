#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v47 (ADR-0168).

Additive successor to `stage17_state_journal_v40.py`: the only change
is which semantic-verifier module the reassignment loop propagates to
the predecessor journal chain (`stage17_semantic_verifier_v47`,
ADR-0168's fix re-pinning `src/runner/stage17_fixed_action.cpp`'s
changed hash a third time, after ADR-0159/v45 and ADR-0166/v46 already
re-pinned it). No admission logic changes here; a fresh journal on the
new pilot-candidate build still needs `S17-EXT-001` bound to this
generation to admit the changed file at all. Patches the exact same
five ancestor modules `v40`'s own loop already reached -- re-assigning
`module.semantic` a third time is idempotent, last write wins.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v47 as semantic
import stage17_state_journal_v40 as predecessor

_v16 = predecessor.predecessor

for module in (
    _v16, _v16.predecessor, _v16.predecessor.predecessor,
    _v16.predecessor.predecessor.predecessor,
    _v16.predecessor.predecessor.predecessor.predecessor,
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
