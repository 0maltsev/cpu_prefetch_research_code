#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v39.

Additive successor to `stage17_state_journal_v34.py`: the only change is
which semantic-verifier module the reassignment loop propagates to the
predecessor journal chain. Policy v39 (ADR-0146) completes the executor
journal-reachability lockstep this same ADR's own outer-policy bindings-
completion move requires (the real Q15 session `execute_session` wiring
fix): `S17-EXT-001`'s dispatch now resolves through executor v25 (whose
only change is its own journal import moving here too) instead of v34's
frozen v24/v34 binding. Without this file, v39's fix is unreachable from
real `admit-resolution` calls, since v34 (and everything importing it)
stays hardcoded to v38 -- the same reachability gap class already found
and fixed for v20/v21 through v33/v34.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v40 as semantic
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
