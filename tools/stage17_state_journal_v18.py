#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v22.

Additive successor to `stage17_state_journal_v17.py`: the only change is
which semantic-verifier module the reassignment loop propagates to the
predecessor journal chain. Policy v19 (bound by v17) only overrides
`S17-EXT-001` dispatch; policy v22 (ADR-0128) additionally overrides
`S17-EXT-006` dispatch so newer pilot-candidate bundle profiles admit
correctly. Without this file, v22's `S17-EXT-006` fix is unreachable
from real `admit-resolution` calls, since v17 (and everything importing
it) stays hardcoded to v19.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v22 as semantic
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
