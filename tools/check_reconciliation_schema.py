#!/usr/bin/env python3
"""Validate the implementation-owned Stage 12 join-audit contract."""

from __future__ import annotations

import argparse
import copy
import json
import pathlib

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


ZERO_SHA256 = "0" * 64


def artifact(name: str) -> dict[str, str]:
    return {"artifact_id": name, "sha256": ZERO_SHA256}


def must_reject(validator: Draft202012Validator, document: dict[str, object]) -> None:
    try:
        validator.validate(document)
    except ValidationError:
        return
    raise ValueError("negative Stage 12 schema fixture unexpectedly passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=pathlib.Path, required=True)
    args = parser.parse_args()
    schema_path = (
        args.source_root / "config" / "schemas" / "join-audit-v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    passed: dict[str, object] = {
        "schema_version": "cpu-prefetch-join-audit/1",
        "protocol_version": "2.0.0-pre.2",
        "run_id": "synthetic-run",
        "join_status": "PASSED",
        "producer_rows": 2,
        "accepted_rows": 1,
        "full_rows": 1,
        "consumer_rows": 1,
        "source_artifacts": [artifact("producer"), artifact("consumer")],
        "issues": [],
        "joined_artifact": artifact("joined"),
        "record_sha256": ZERO_SHA256,
    }
    failed = copy.deepcopy(passed)
    failed["join_status"] = "FAILED"
    failed["issues"] = [
        {
            "failure_class": "consumer_count",
            "category": "COUNT_MISMATCH",
            "path": "$/consumer_rows",
            "rule_id": "REC-CONSUMER-COUNT",
            "message": "synthetic mismatch",
        }
    ]
    failed["joined_artifact"] = None
    validator.validate(passed)
    validator.validate(failed)

    passed_without_joined = copy.deepcopy(passed)
    passed_without_joined["joined_artifact"] = None
    must_reject(validator, passed_without_joined)

    failed_without_issue = copy.deepcopy(failed)
    failed_without_issue["issues"] = []
    must_reject(validator, failed_without_issue)

    wrong_version = copy.deepcopy(passed)
    wrong_version["protocol_version"] = "2.0.0-pre.1"
    must_reject(validator, wrong_version)

    malformed_hash = copy.deepcopy(passed)
    malformed_hash["record_sha256"] = "not-a-sha256"
    must_reject(validator, malformed_hash)

    extra_field = copy.deepcopy(passed)
    extra_field["scientific_interpretation"] = "invented"
    must_reject(validator, extra_field)

    print("reconciliation-schema-check: PASS (2 positive, 5 negative Draft 2020-12 cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
