#!/usr/bin/env python3
"""Validate one immutable Q15-R prestate artifact without touching the stand."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator

from check_canonical import canonicalize


CONTRACT_ID = "Q15-R-STAND-PRESTATE-COLLECTOR-CONTRACT-v1"
ARTIFACT_SCHEMA_VERSION = "cpu-prefetch-q15-r-stand-prestate/1"
HASH_PROFILE = "Q15-R-PRESTATE-JCS-I64-ZEROSELF-SHA256-v1"
SELECTED_RELEASE_SHA256 = (
    "8e8ad6d781b2bffadcfc10cf3b12d5666c7a1d4c7d7e291d7318a19503e6ab01"
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def load_unique_json(path: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    document = json.loads(
        raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs
    )
    if not isinstance(document, dict):
        raise ValueError("artifact root must be an object")
    return document, raw


def zero_self_canonical(document: dict[str, Any]) -> bytes:
    zeroed = copy.deepcopy(document)
    zeroed["artifact_sha256"] = "0" * 64
    return canonicalize(zeroed).encode("utf-8")


def seal_synthetic_artifact(document: dict[str, Any]) -> bytes:
    """Seal a synthetic fixture for repository tests; never acquires evidence."""
    document["artifact_sha256"] = sha256_bytes(zero_self_canonical(document))
    return canonicalize(document).encode("utf-8")


def _expected_failure(
    observation: dict[str, Any], accepted_codes: list[int], total_exceeded: bool
) -> tuple[bool, str | None]:
    if observation.get("launched") is not True:
        return False, "SPAWN_FAILURE"
    if observation.get("timed_out") is True:
        return False, "COMMAND_TIMEOUT"
    if observation.get("output_limit_exceeded") is True:
        return False, "COMMAND_OUTPUT_LIMIT"
    if total_exceeded:
        return False, "TOTAL_OUTPUT_LIMIT"
    if observation.get("spawn_error") != 0:
        return False, "CAPTURE_FAILURE"
    if observation.get("terminating_signal") is not None:
        return False, "COMMAND_SIGNAL"
    if observation.get("exit_code") is None:
        return False, "MISSING_EXIT_STATUS"
    if observation.get("exit_code") not in accepted_codes:
        return False, "UNEXPECTED_EXIT_CODE"
    return True, None


def semantic_errors(
    document: dict[str, Any], contract: dict[str, Any], contract_sha256: str
) -> list[str]:
    errors: list[str] = []
    if document.get("collector_contract_id") != CONTRACT_ID:
        errors.append("collector contract ID mismatch")
    if document.get("collector_contract_sha256") != contract_sha256:
        errors.append("collector contract SHA-256 mismatch")
    if document.get("selected_release_archive_sha256") != SELECTED_RELEASE_SHA256:
        errors.append("selected D-065 release SHA-256 mismatch")
    if document.get("artifact_hash_profile") != HASH_PROFILE:
        errors.append("artifact hash profile mismatch")
    if document.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        errors.append("artifact schema version mismatch")

    commands = contract.get("commands", [])
    observations = document.get("observations", [])
    if not isinstance(observations, list) or not 1 <= len(observations) <= len(commands):
        return errors + ["observation count is outside the fixed command contract"]

    limits = contract.get("execution_contract", {})
    total = 0
    final_failure: str | None = None
    for index, (observation, command) in enumerate(
        zip(observations, commands, strict=False)
    ):
        if not isinstance(observation, dict):
            errors.append(f"observation {index} is not an object")
            continue
        if (
            observation.get("command_id") != command.get("id")
            or observation.get("observation_kind") != command.get("observation_kind")
            or observation.get("argv") != command.get("argv")
        ):
            errors.append(f"observation {index} is not the exact command prefix")
        try:
            stdout_size = len(bytes.fromhex(observation.get("stdout_hex", "")))
            stderr_size = len(bytes.fromhex(observation.get("stderr_hex", "")))
        except (TypeError, ValueError):
            errors.append(f"observation {index} output is not whole-byte hex")
            stdout_size = stderr_size = 0
        if stdout_size > limits.get("maximum_stdout_bytes_per_command", -1) or (
            stderr_size > limits.get("maximum_stderr_bytes_per_command", -1)
        ):
            errors.append(f"observation {index} exceeds a per-command output bound")
        addition = stdout_size + stderr_size
        total_limit = limits.get("maximum_total_captured_bytes", -1)
        total_exceeded = addition > total_limit - min(total_limit, total)
        if not total_exceeded:
            total += addition
        expected_accepted, failure = _expected_failure(
            observation, command.get("accepted_exit_codes", []), total_exceeded
        )
        if observation.get("accepted") is not expected_accepted:
            errors.append(f"observation {index} accepted flag is forged")
        if index + 1 < len(observations) and not expected_accepted:
            errors.append(f"observation {index} violates stop-first failure")
        if index + 1 == len(observations):
            final_failure = failure

    complete = document.get("completion_state") == "COMPLETE"
    if complete:
        if len(observations) != len(commands) or final_failure is not None:
            errors.append("COMPLETE does not contain every accepted command")
        if document.get("failed_command_id") is not None or document.get(
            "failure_category"
        ) is not None:
            errors.append("COMPLETE carries failure fields")
    else:
        if final_failure is None:
            errors.append("PARTIAL_FAILED does not end with a failure")
        if document.get("failed_command_id") != observations[-1].get("command_id"):
            errors.append("partial failed-command ID mismatch")
        if document.get("failure_category") != final_failure:
            errors.append("partial failure category mismatch")
    return errors


def validate_document(
    document: dict[str, Any],
    raw: bytes,
    contract: dict[str, Any],
    contract_sha256: str,
    schema: dict[str, Any],
) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(document)]
    try:
        canonical = canonicalize(document).encode("utf-8")
        if raw != canonical:
            errors.append("artifact bytes are not exact JCS-I64-v1 canonical bytes")
        expected_hash = sha256_bytes(zero_self_canonical(document))
        if document.get("artifact_sha256") != expected_hash:
            errors.append("zero-self artifact SHA-256 mismatch")
    except (TypeError, ValueError) as error:
        errors.append(f"canonicalization failure: {error}")
    errors.extend(semantic_errors(document, contract, contract_sha256))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=pathlib.Path, required=True)
    parser.add_argument("--contract", type=pathlib.Path, required=True)
    parser.add_argument("--schema", type=pathlib.Path, required=True)
    args = parser.parse_args()

    document, raw = load_unique_json(args.artifact)
    contract, _ = load_unique_json(args.contract)
    schema, _ = load_unique_json(args.schema)
    Draft202012Validator.check_schema(schema)
    errors = validate_document(
        document, raw, contract, sha256_file(args.contract), schema
    )
    if errors:
        for error in errors:
            print(f"q15-r-prestate-validator: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "q15-r-prestate-validator: PASS "
        f"artifact_sha256={document['artifact_sha256']} "
        f"completion={document['completion_state']} "
        f"observations={len(document['observations'])}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError, KeyError) as error:
        print(f"q15-r-prestate-validator: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
