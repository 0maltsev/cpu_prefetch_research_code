#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v25.

Additive successor to `stage17_state_journal_v20.py`: the only change is
which semantic-verifier module the reassignment loop propagates to the
predecessor journal chain. Policy v25 (ADR-0131) rebinds `S17-EXT-001`'s
resolution-time dispatch to the corrected preflight-plan chain (executor
v15, process-group supervisor v3, openssh snapshot broker v3) instead of
v16's frozen executor-v14/supervisor-v2 binding, fixing the real,
reproduced crash when a full `/proc` scan reaches a kernel thread.
Without this file, v25's fix is unreachable from real `admit-resolution`
calls, since v20 (and everything importing it) stays hardcoded to v24 --
the same reachability gap class already found and fixed for v18/v19 and
v19/v20.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v25 as semantic
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
