#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v15."""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v15 as semantic
import stage17_state_journal_v12 as predecessor


predecessor.semantic = semantic
predecessor.SEMANTIC_POLICY_PATH = semantic.POLICY_PATH

SEMANTIC_POLICY_PATH = semantic.POLICY_PATH
SCHEMA_PATHS = predecessor.SCHEMA_PATHS
JournalError = predecessor.JournalError
ExternalInputResolution = predecessor.ExternalInputResolution
StateTransition = predecessor.StateTransition
OperationalJournalValidation = predecessor.OperationalJournalValidation


def validate_operational_journal(**arguments: Any) -> OperationalJournalValidation:
    return predecessor.validate_operational_journal(**arguments)


def checked_in_status(root: pathlib.Path) -> OperationalJournalValidation:
    repository = root.resolve()
    latest = repository / "config/stage17/journal/stage17-state-journal-000000.json"
    return validate_operational_journal(
        repository_root=repository,
        evidence_root=repository,
        latest_journal=latest,
        journal_directory=latest.parent,
    )
