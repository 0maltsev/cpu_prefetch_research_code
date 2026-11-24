"""D-204 operational journal; explicit activation after legacy imports."""
from __future__ import annotations

import pathlib

import stage17_state_journal_v49 as predecessor
import stage17_semantic_verifier_v56 as semantic

SEMANTIC_POLICY_PATH = semantic.POLICY_PATH
SCHEMA_PATHS = predecessor.SCHEMA_PATHS
JournalError = predecessor.JournalError
ExternalInputResolution = predecessor.ExternalInputResolution
StateTransition = predecessor.StateTransition
OperationalJournalValidation = predecessor.OperationalJournalValidation


def activate():
    """Install this entry point after all historical import side effects."""
    module = predecessor
    while True:
        module.semantic = semantic
        module.SEMANTIC_POLICY_PATH = SEMANTIC_POLICY_PATH
        if not hasattr(module, "predecessor"):
            break
        module = module.predecessor


activate()


def validate_operational_journal(**arguments):
    activate()
    return predecessor.validate_operational_journal(**arguments)


def checked_in_status(root: pathlib.Path):
    latest = root.resolve() / "config/stage17/journal/stage17-state-journal-000000.json"
    return validate_operational_journal(repository_root=root.resolve(),
        evidence_root=root.resolve(), latest_journal=latest, journal_directory=latest.parent)
