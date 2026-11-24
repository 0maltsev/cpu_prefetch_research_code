"""Journal runtime bound to calibration policy v55."""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v55 as semantic
import stage17_state_journal_v48 as predecessor

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
