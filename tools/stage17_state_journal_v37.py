#!/usr/bin/env python3
"""Stage 17 journal runtime bound to semantic policy v43 (ADR-0157).

Additive successor to `stage17_state_journal_v36.py`: the only change is
which semantic-verifier module the reassignment loop propagates to the
predecessor journal chain (`stage17_semantic_verifier_v43`, ADR-0157's
preflight-plan-policy follow-up fix). Without this file, `S17-EXT-001`'s
handler (reached via the `semantic` attribute this loop monkey-patches
onto its ancestors, the same established mechanism `v20` through `v36`
already use) stays bound to `v42`'s policy-v42-shaped expectations, and
a fresh journal authoring `S17-EXT-001` against the new `...policy-
v43.json` would be rejected by `verify_policy_v14`'s stale required-file
checks.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_semantic_verifier_v43 as semantic
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
