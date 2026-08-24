#!/usr/bin/env python3
"""Validate the Q15-P0 MSR evidence contract without touching an MSR."""

from __future__ import annotations

import copy
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


MASK = 0xF
CPUS = (0, 1, 26)


def fixture(state: str = "H1") -> dict[str, Any]:
    prestates = (0x123456789ABCDEF0, 0xFEDCBA9876543210, 0x0F0F0F0F0F0F0F00)
    values = []
    for cpu, prestate in zip(CPUS, prestates, strict=True):
        requested = prestate if state == "H0" else prestate | MASK
        values.append(
            {
                "cpu": cpu,
                "prestate_hex": f"{prestate:016x}",
                "requested_hex": f"{requested:016x}",
                "apply_readback_hex": f"{requested:016x}",
                "restore_readback_hex": f"{prestate:016x}",
            }
        )
    return {
        "schema_version": "cpu-prefetch-hardware-prefetch-qualification/1",
        "protocol_version": "2.0.0-pre.2",
        "mapping_id": "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1",
        "artifact_id": f"SYNTHETIC-{state}",
        "stand_id": "SYNTHETIC-NOT-A-STAND",
        "binding_id": "SYNTHETIC-BINDING",
        "source_revision": "SYNTHETIC",
        "command_sha256": "0" * 64,
        "captured_at_utc": "2026-08-24T00:00:00Z",
        "execution_state": "COMPLETE",
        "requested_state": state,
        "cpu_family_hex": "06",
        "cpu_model_hex": "55",
        "msr_hex": "000001a4",
        "disable_mask_hex": "000000000000000f",
        "cpu_values": values,
        "regular_probe": {"artifact_id": "SYNTHETIC-REGULAR", "sha256": "1" * 64, "passed": True},
        "pointer_probe": {"artifact_id": "SYNTHETIC-POINTER", "sha256": "2" * 64, "passed": True},
        "applied": True,
        "verified": True,
        "restored": True,
        "quarantined": False,
        "eligible": True,
    }


def semantic_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    cpu_values = document.get("cpu_values", [])
    if sorted(item.get("cpu") for item in cpu_values) != list(CPUS):
        errors.append("CPUs 0, 1, and 26 must each appear exactly once")
    state = document.get("requested_state")
    for item in cpu_values:
        try:
            prestate = int(item["prestate_hex"], 16)
            requested = int(item["requested_hex"], 16)
            apply_readback = int(item["apply_readback_hex"], 16)
            restore_readback = int(item["restore_readback_hex"], 16)
        except (KeyError, TypeError, ValueError):
            continue
        expected = prestate if state == "H0" else prestate | MASK
        if requested != expected:
            errors.append("requested complete value violates the H0/H1 mapping")
        if requested & ~MASK != prestate & ~MASK:
            errors.append("undocumented bits 63:4 changed")
        if apply_readback != requested:
            errors.append("apply readback differs from requested complete value")
        if restore_readback != prestate:
            errors.append("restoration readback differs from complete prestate")
        if state == "H1" and requested == prestate:
            errors.append("H0/H1 collapse is ineligible")
    complete = document.get("execution_state") == "COMPLETE"
    eligible = (
        complete
        and document.get("applied") is True
        and document.get("verified") is True
        and document.get("restored") is True
        and document.get("quarantined") is False
        and document.get("regular_probe", {}).get("passed") is True
        and document.get("pointer_probe", {}).get("passed") is True
        and not errors
    )
    if document.get("eligible") is not eligible:
        errors.append("eligible does not equal the complete fail-closed gate")
    if document.get("quarantined") is (document.get("restored") is True):
        errors.append("quarantine must be the inverse of verified restoration")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "config/schemas/hardware-prefetch-qualification-v1.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    positives = [fixture("H0"), fixture("H1")]
    for document in positives:
        validator.validate(document)
        if errors := semantic_errors(document):
            print(f"hardware-prefetch-schema-check: FAIL positive: {errors}", file=sys.stderr)
            return 1

    negatives = []
    duplicate = copy.deepcopy(positives[1])
    duplicate["cpu_values"][2]["cpu"] = 1
    negatives.append(duplicate)
    high_bit = copy.deepcopy(positives[1])
    high_bit["cpu_values"][0]["requested_hex"] = "023456789abcdeff"
    negatives.append(high_bit)
    mismatch = copy.deepcopy(positives[1])
    mismatch["cpu_values"][0]["apply_readback_hex"] = "123456789abcdefe"
    negatives.append(mismatch)
    unrestored = copy.deepcopy(positives[1])
    unrestored["restored"] = False
    negatives.append(unrestored)
    failed_probe = copy.deepcopy(positives[1])
    failed_probe["pointer_probe"]["passed"] = False
    negatives.append(failed_probe)
    collapse = copy.deepcopy(positives[1])
    collapse["cpu_values"][0]["prestate_hex"] = collapse["cpu_values"][0]["requested_hex"]
    negatives.append(collapse)
    for index, document in enumerate(negatives):
        if not list(validator.iter_errors(document)) and not semantic_errors(document):
            print(f"hardware-prefetch-schema-check: FAIL negative {index} passed", file=sys.stderr)
            return 1
    print("hardware-prefetch-schema-check: PASS (2 synthetic positive, 6 negative, no MSR access)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
