#!/usr/bin/env python3
"""Validate Stage 11 implementation-owned records with Draft 2020-12."""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import subprocess
import tempfile

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


def must_reject(validator: Draft202012Validator, document: dict[str, object]) -> None:
    try:
        validator.validate(document)
    except ValidationError:
        return
    raise ValueError("negative Stage 11 schema fixture unexpectedly passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-generator", type=pathlib.Path, required=True)
    parser.add_argument("--source-root", type=pathlib.Path, required=True)
    args = parser.parse_args()
    schema_root = args.source_root / "config" / "schemas"

    with tempfile.TemporaryDirectory(prefix="cpu-prefetch-stage11-schema-") as directory:
        root = pathlib.Path(directory)
        subprocess.run([args.fixture_generator, root], check=True)
        cases = (
            ("phase-integrity-report-v2.schema.json", "integrity.json"),
            ("copy-ledger-record-v2.schema.json", "copy-ledger.json"),
        )
        validators: dict[str, Draft202012Validator] = {}
        documents: dict[str, dict[str, object]] = {}
        for schema_name, document_name in cases:
            schema = json.loads((schema_root / schema_name).read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema)
            document = json.loads((root / document_name).read_text(encoding="utf-8"))
            validator.validate(document)
            validators[document_name] = validator
            documents[document_name] = document

        bad_integrity = copy.deepcopy(documents["integrity.json"])
        bad_integrity["event_records_pre_checksum"]["value_hex"] = "0"
        must_reject(validators["integrity.json"], bad_integrity)

        missing_ledger_field = copy.deepcopy(documents["copy-ledger.json"])
        del missing_ledger_field["required_durable_copy_count"]
        must_reject(validators["copy-ledger.json"], missing_ledger_field)

        short_complete_ledger = copy.deepcopy(documents["copy-ledger.json"])
        short_complete_ledger["copies"].pop()
        must_reject(validators["copy-ledger.json"], short_complete_ledger)

        wrong_policy = copy.deepcopy(documents["copy-ledger.json"])
        wrong_policy["policy_id"] = "UNKNOWN"
        must_reject(validators["copy-ledger.json"], wrong_policy)

    print("storage-schema-check: PASS (2 positive, 4 negative Draft 2020-12 cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
