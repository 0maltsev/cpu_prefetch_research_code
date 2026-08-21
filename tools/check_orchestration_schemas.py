#!/usr/bin/env python3
"""Draft 2020-12 conformance fixtures for Stage 14 imported contracts."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

import check_protocol_fixtures as fixtures


def expect_valid(
    validator: Draft202012Validator, instance: dict[str, Any], name: str
) -> None:
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        raise RuntimeError(f"{name}: expected valid; first error: {errors[0].message}")


def expect_invalid(
    validator: Draft202012Validator, instance: dict[str, Any], name: str
) -> None:
    if not list(validator.iter_errors(instance)):
        raise RuntimeError(f"{name}: expected schema rejection")


def changed(value: dict[str, Any], **updates: Any) -> dict[str, Any]:
    result = copy.deepcopy(value)
    result.update(updates)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    fixtures.VERSION = "2.0.0-pre.2"
    schema_dir = args.source_root / "protocol/2.0.0-pre.2/handoff/schemas"
    validators: dict[str, Draft202012Validator] = {}
    for name in ("block-plan.schema.json", "freeze-record.schema.json"):
        schema = json.loads((schema_dir / name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validators[name] = Draft202012Validator(
            schema, format_checker=FormatChecker()
        )

    block_validator = validators["block-plan.schema.json"]
    freeze_validator = validators["freeze-record.schema.json"]
    positives: list[tuple[Draft202012Validator, dict[str, Any], str]] = [
        (block_validator, fixtures.block_plan(), "original complete block"),
        (block_validator, fixtures.block_plan(True), "replacement complete block"),
    ]
    positives.extend(
        (freeze_validator, fixtures.freeze_record(kind), kind)
        for kind in (
            "PROTOCOL_FREEZE",
            "SELECTION_FREEZE",
            "VALIDATION_UNSEAL",
            "H3_EVALUATED",
            "H1H2_RELEASED",
            "REPLACEMENT_AUTHORIZATION",
            "AMENDMENT",
        )
    )
    for validator, instance, name in positives:
        expect_valid(validator, instance, name)

    missing_cell = fixtures.block_plan()
    missing_cell["cells"].pop()
    duplicate_plot = changed(fixtures.block_plan(), whole_plot_order=["H0", "H0"])
    incomplete_lineage = fixtures.block_plan(True)
    incomplete_lineage["replacement_lineage"] = None
    path_id = changed(fixtures.block_plan(), block_id="blocks/original")
    # Path-shaped identities are intentionally beyond JSON Schema and must pass
    # here; the Stage14 semantic validator rejects them.
    expect_valid(block_validator, path_id, "schema-only path-shaped identity")

    missing_context = fixtures.freeze_record("SELECTION_FREEZE")
    del missing_context["h3_selections"][fixtures.CONTEXTS[0]]
    duplicate_alias = fixtures.freeze_record("SELECTION_FREEZE")
    duplicate_alias["h3_selections"]["UNREGISTERED_CONTEXT"] = {
        "package": "R0",
        "requested_hardware_state": "H0",
    }
    missing_hash = fixtures.freeze_record("VALIDATION_UNSEAL")
    del missing_hash["selection_record_ref"]["sha256"]
    empty_affected = changed(
        fixtures.freeze_record("VALIDATION_UNSEAL"), affected_block_ids=[]
    )
    wrong_authority = copy.deepcopy(fixtures.freeze_record("H3_EVALUATED"))
    wrong_authority["authority"]["role"] = "VALIDATION_CUSTODIAN"
    cell_replacement = copy.deepcopy(fixtures.freeze_record("REPLACEMENT_AUTHORIZATION"))
    cell_replacement["replacement"]["cell_ordinal"] = 1
    empty_amendment = changed(fixtures.freeze_record("AMENDMENT"), affected_documents=[])
    negatives = (
        (block_validator, missing_cell, "missing cell"),
        (block_validator, duplicate_plot, "duplicate whole plot"),
        (block_validator, incomplete_lineage, "incomplete replacement lineage"),
        (freeze_validator, missing_context, "missing stable H3 context"),
        (freeze_validator, duplicate_alias, "unregistered H3 context"),
        (freeze_validator, missing_hash, "unseal missing selection hash"),
        (freeze_validator, empty_affected, "empty mandatory affected blocks"),
        (freeze_validator, wrong_authority, "wrong sealing authority"),
        (freeze_validator, cell_replacement, "forbidden cell replacement"),
        (freeze_validator, empty_amendment, "empty amendment impact"),
    )
    for validator, instance, name in negatives:
        expect_invalid(validator, instance, name)

    print(
        "PASS: Stage 14 imported schema fixtures "
        f"({len(positives)} positive, {len(negatives)} negative; "
        "path identity delegated to semantic validation)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
