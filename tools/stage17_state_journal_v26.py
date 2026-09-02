#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v30.

Additive successor to `stage17_state_journal_v25.py`: the only change is
which semantic-verifier module the reassignment loop propagates to the
predecessor journal chain. Policy v30 (ADR-0136) corrects real `S17-EXT-
002` admission's stale preflight record schema versions (`PREFLIGHT_
ATTEMPT`/`PREFLIGHT_OBSERVATION_RECEIPT`/`PREFLIGHT_COMPLETION` pinned to
the frozen `-v7`/`-v5`/`-v5` schemas instead of the real executor's
current `-v10`/`-v7`/`-v7` output) instead of v25's frozen v29 binding.
Without this file, v30's fix is unreachable from real `admit-resolution`
calls, since v25 (and everything importing it) stays hardcoded to v29 --
the same reachability gap class already found and fixed for v20/v21
through v24/v25.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v30 as semantic
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
