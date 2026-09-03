#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v34.

Additive successor to `stage17_state_journal_v29.py`: the only change is
which semantic-verifier module the reassignment loop propagates to the
predecessor journal chain. Policy v34 (ADR-0140) fixes S17-EXT-002's
preflight receipt-to-artifact pairing: real admission now resolves
through `stage17_operational_semantics_v7.verify_manifest_v7`, which
pairs each observation receipt to its stdout/stderr artifact by
`artifact_id` convention instead of a global hash-uniqueness search that
is false whenever two or more observations legitimately share identical
content. Without this file, v34's fix is unreachable from real `admit-
resolution` calls, since v29 (and everything importing it) stays
hardcoded to v33 -- the same reachability gap class already found and
fixed for v20/v21 through v28/v29.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v34 as semantic
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
