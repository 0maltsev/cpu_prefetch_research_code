#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v24.

Additive successor to `stage17_state_journal_v19.py`: the only change is
which semantic-verifier module the reassignment loop propagates to the
predecessor journal chain. Policy v24 (ADR-0130) rebinds `S17-EXT-001`'s
resolution-time dispatch to the corrected preflight-plan chain (executor
v14, journal v18) instead of v15's frozen executor-v13 binding, fixing the
real journal-reachability defect found in `executor_v13.py`'s own
hardcoded `stage17_state_journal_v17` import. Without this file, v24's fix
is unreachable from real `admit-resolution` calls, since v18/v19 (and
everything importing them) stay hardcoded to v22/v23 -- the same
reachability gap class already found and fixed for v17/v19 and v18/v19.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v24 as semantic
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
