#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v44 (ADR-0158).

Additive successor to `stage17_state_journal_v37.py`: the only change is
which semantic-verifier module the reassignment loop propagates to the
predecessor journal chain (`stage17_semantic_verifier_v44`, ADR-0158's
fix for `S17-EXT-001`'s own admission-time check, which -- independent
of every other chain this session already fixed -- still compared the
envelope's `semantic_policy` field against `stage17_semantic_verifier_
v39.py`'s own hardcoded `preflight` = `_v27` binding). Without this
file, `admit-resolution --input-id S17-EXT-001` stays rejected with
`S17-EXT-001 policy binding mismatch` for any journal whose `author-
ext001` already moved to `...policy-v28.json` (ADR-0157's own fix) --
exactly what burned `standv2-22`.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v44 as semantic
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
