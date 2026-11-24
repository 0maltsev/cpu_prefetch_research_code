#!/usr/bin/env python3
"""Stage 17 pilot-candidate artifact successor fixing the real
`S17-EXT-002`/`S17-EXT-003` release-receipt verification call site to
recognize the current `STAGE17-PILOT-CANDIDATE-BUNDLE-v22` profile
(ADR-0159).

`v6.py`'s own `verify_extracted_release_receipt_v6` hardcodes
`config/schemas/stage17-runtime-release-provenance-v5.schema.json` --
whose `bundle_profile` enum stops at `STAGE17-PILOT-CANDIDATE-BUNDLE-v21`
and does not recognize `-v22` -- discovered live via a real standv2-30
`admit-resolution --input-id S17-EXT-002` failure ("runtime-release
receipt schema rejection: 'STAGE17-PILOT-CANDIDATE-BUNDLE-v22' is not
one of [...]"). This is a real, fourth v22-recognition gap, distinct
from the three `5e39f18` already fixed (which only widened
`RECOGNIZED_PROFILES`/`ROLE_SCHEMA_v5`/`artifact_v7.SCHEMA`, none of
which this call site actually consults) -- `stage17_operational_
semantics_v5.py`'s own `_verify_extracted_release_v5` (frozen, and
re-exported byte-identical through `v6`/`v7`/`v8` of `operational_
semantics`) calls `release_verifier.verify_extracted_release_receipt_v6`
directly, an attribute lookup on this module's own object at call time.

`v6.py`/`v7.py` are both already policy-pinned, so this is a new,
additive file rather than an edit to either. `verify_extracted_release_
receipt_v8` is a faithful copy of `v6`'s own function, changed only to
load `config/schemas/stage17-runtime-release-provenance-v6.schema.json`
(already used for this exact purpose by `ROLE_SCHEMA_v5`'s own
`RUNTIME_RELEASE_PROVENANCE` binding since `5e39f18` -- the schema
itself already recognizes `-v22`, only this one call site never got
pointed at it). Because `stage17_operational_semantics_v5.py` resolves
`release_verifier.verify_extracted_release_receipt_v6` dynamically
against `stage17_pilot_candidate_artifact_v6`'s own module object at
call time (not a name bound once at import time), monkey-patching that
attribute here -- the same technique `current_journal.semantic`/
`current_semantic` reassignment already uses throughout this codebase,
including in already-accepted files -- takes effect for every existing
caller (`v5`/`v6`/`v7`/`v8` of `operational_semantics` alike) without
needing to edit any of them.
"""

from __future__ import annotations

import pathlib
from typing import Any

from jsonschema import Draft202012Validator

import stage17_pilot_candidate_artifact_v6 as _v6_module
import stage17_pilot_candidate_artifact_v7 as predecessor

VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = predecessor.VERIFIER_VERSION
SCHEMA = predecessor.SCHEMA
SUPPORTED_ACTIONS = predecessor.SUPPORTED_ACTIONS

ArtifactError = predecessor.ArtifactError
ReleaseContext = predecessor.ReleaseContext
ExtractedReleaseContext = predecessor.ExtractedReleaseContext

sha256_bytes = predecessor.sha256_bytes
sha256_file = predecessor.sha256_file
_regular = predecessor._regular
_load_json = predecessor._load_json
_safe_extract = predecessor._safe_extract
_binding = predecessor._binding
_parse_sums = predecessor._parse_sums
_verify_inventory = predecessor._verify_inventory
_run_full_verifier = predecessor._run_full_verifier

RECOGNIZED_PROFILES = predecessor.RECOGNIZED_PROFILES
DRY_RUN_PROFILES = predecessor.DRY_RUN_PROFILES

verify_extracted_bundle_v6 = predecessor.verify_extracted_bundle_v6
build_contract_v7 = predecessor.build_contract_v7
build_contract_v4 = predecessor.build_contract_v4
verify_pilot_candidate_artifact_v7 = predecessor.verify_pilot_candidate_artifact_v7
build_extracted_release_receipt_v6 = _v6_module.build_extracted_release_receipt_v6

RUNTIME_RELEASE_PROVENANCE_SCHEMA = (
    "config/schemas/stage17-runtime-release-provenance-v6.schema.json"
)


def verify_extracted_release_receipt_v8(
    *, repository_root: pathlib.Path, receipt: dict[str, Any],
) -> ExtractedReleaseContext:
    schema = _load_json(repository_root / RUNTIME_RELEASE_PROVENANCE_SCHEMA)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(receipt))
    if errors:
        raise ArtifactError(
            f"runtime-release receipt schema rejection: {errors[0].message}"
        )
    context = verify_extracted_bundle_v6(pathlib.Path(receipt["bundle_root"]))
    expected = build_extracted_release_receipt_v6(
        bundle_root=context.bundle_root, receipt_id=receipt["receipt_id"]
    )
    if receipt != expected:
        raise ArtifactError("runtime-release receipt differs from verified bundle bytes")
    return context


_v6_module.verify_extracted_release_receipt_v6 = verify_extracted_release_receipt_v8
