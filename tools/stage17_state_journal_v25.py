#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v29.

Additive successor to `stage17_state_journal_v24.py`: the only change is
which semantic-verifier module the reassignment loop propagates to the
predecessor journal chain. Policy v29 (ADR-0135) rebinds `S17-EXT-001`'s
resolution-time dispatch to the corrected preflight-plan chain (executor
v19, collector v3) instead of v24's frozen executor-v18/collector-v2
binding, fixing the real, reproduced `REMOTE_NONZERO_EXIT`/`runtime file`
failure caused by rejecting `/usr/bin/python3`/`sha256sum`/`uname`
outright for being symlinks, which they ordinarily are on real hosts.
Without this file, v29's fix is unreachable from real `admit-resolution`
calls, since v24 (and everything importing it) stays hardcoded to v28 --
the same reachability gap class already found and fixed for v20/v21,
v21/v22, v22/v23, and v23/v24.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v29 as semantic
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
