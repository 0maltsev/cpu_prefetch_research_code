#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v36.

Additive successor to `stage17_state_journal_v31.py`: the only change is
which semantic-verifier module the reassignment loop propagates to the
predecessor journal chain. Policy v36 (ADR-0143) completes the phase-
controller/Q15-session-controller entrypoint bindings ADR-0142 left
untracked: `tools/stage17_phase_controller_v11.py`, `tools/stage17_q15_
session_controller_v7.py`, and `tools/stage17_q15_session_controller_
v8.py` are now pinned policy bindings, so a sealed bundle actually
carries them. Without this file, v36's fix is unreachable from real
`admit-resolution` calls, since v31 (and everything importing it) stays
hardcoded to v35 -- the same reachability gap class already found and
fixed for v20/v21 through v30/v31.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v36 as semantic
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
