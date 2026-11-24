#!/usr/bin/env python3
"""Validate accepted Q15-R-P4-D records and local no-authority implementation."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator

from validate_q15_r_prestate import seal_synthetic_artifact, validate_document


DECISIONS = ("D-066", "D-067", "D-068", "D-069", "D-070")
INPUTS = (
    "@ALLOWED_SIGNERS_SOURCE@",
    "@OPERATIONAL_RELEASE_ROOT@",
    "@SECONDARY_CUSTODY_ROOT@",
    "CURRENT_STAND_PRESTATE_ARTIFACT_ID_AND_SHA256",
    "ACTUAL_ALLOWED_SIGNERS_ARTIFACT_ID_SHA256_AND_ED25519_FINGERPRINT",
)
COMMAND_IDS = tuple(f"P4R-{index:03d}" for index in range(1, 26))
CONTRACT_SHA256 = "4123735a940da144e00247957d0210216cde4bf19fbdbea0378b52dab2161b87"
ACCEPTANCE_SHA256 = "1645c2a7fb356272afbf9377b99784e307f54f8a7df5fbb09f46d70edae3c521"
EXPECTED_FILES = {
    "config/q15/q15-r-external-input-acquisition-decision-input-v1.json": (
        "779b098d58535e853218dea4580354b2dde224922df2e3516748b4920046d67b"
    ),
    "docs/Q15_R_EXTERNAL_INPUT_ACQUISITION_DECISION_BUNDLE.md": (
        "aa01eb0a5efe8112c3f075ade9b344495c667d3dd5ed3cee5d0c6ef025217c06"
    ),
    "config/q15/q15-r-stand-prestate-collector-contract-v1.json": CONTRACT_SHA256,
    "config/q15/q15-r-p4-d-acceptance-v1.json": ACCEPTANCE_SHA256,
}
ALLOWED_EXECUTABLES = {
    "/usr/bin/df",
    "/usr/bin/findmnt",
    "/usr/bin/getent",
    "/usr/bin/hostname",
    "/usr/bin/sha256sum",
    "/usr/bin/stat",
    "/usr/bin/uname",
}


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def schema_errors(
    root: pathlib.Path, document_name: str, schema_name: str
) -> list[str]:
    document = load(root / document_name)
    schema = load(root / schema_name)
    Draft202012Validator.check_schema(schema)
    return [item.message for item in Draft202012Validator(schema).iter_errors(document)]


def contract_errors(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    execution = contract.get("execution_contract", {})
    expected_limits = {
        "maximum_command_count": 25,
        "maximum_stdout_bytes_per_command": 1_048_576,
        "maximum_stderr_bytes_per_command": 1_048_576,
        "maximum_total_captured_bytes": 16_777_216,
        "maximum_artifact_bytes": 67_108_864,
        "per_command_timeout_seconds": 30,
        "external_total_watchdog_seconds": 900,
        "retry_count": 0,
        "continue_after_failure": False,
        "partial_artifact_required": True,
    }
    if any(execution.get(name) != value for name, value in expected_limits.items()):
        errors.append("collector bounds, stop, partial, or retry contract drifted")
    if execution.get("fixed_environment") != ["LANG=C", "LC_ALL=C", "TZ=UTC0"]:
        errors.append("collector environment must be exact and not inherited")
    commands = contract.get("commands", [])
    if tuple(item.get("id") for item in commands) != COMMAND_IDS:
        errors.append("collector command IDs must be exact, unique, and ordered")
    for command in commands:
        argv = command.get("argv", [])
        if not argv or argv[0] not in ALLOWED_EXECUTABLES:
            errors.append(f"unapproved collector executable: {argv[:1]}")
        if any("@" in item for item in argv):
            errors.append(f"collector command contains an unresolved token: {command.get('id')}")
        if argv and argv[0] in {"/bin/sh", "/usr/bin/env"}:
            errors.append(f"collector command uses shell/environment dispatch: {command.get('id')}")
    boundary = contract.get("authority_boundary", {})
    true_fields = {name for name, value in boundary.items() if value is True}
    if true_fields != {"repository_local_implementation_authorized"}:
        errors.append("collector contract grants authority beyond local implementation")
    artifact = contract.get("artifact_contract", {})
    if artifact.get("sidecar_created_by_collector") is not False or artifact.get(
        "sidecar_required_by_authorized_custody_workflow"
    ) is not True:
        errors.append("collector/custody sidecar boundary drifted")
    return errors


def acceptance_errors(acceptance: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    decisions = acceptance.get("accepted_decisions", [])
    if tuple(item.get("decision_id") for item in decisions) != DECISIONS:
        errors.append("Q15-R-P4-D acceptance must bind D-066 through D-070 in order")
    literals = acceptance.get("remaining_literal_values", [])
    if tuple(item.get("name") for item in literals) != INPUTS:
        errors.append("acceptance must retain the exact five external inputs")
    if any(item.get("state") != "UNRESOLVED" or item.get("value") is not None for item in literals):
        errors.append("method acceptance cannot fabricate a literal external value")
    boundary = acceptance.get("authority_boundary", {})
    true_fields = {name for name, value in boundary.items() if value is True}
    if true_fields != {
        "repository_local_collector_implementation_authorized",
        "repository_local_schema_fake_negative_sanitizer_verification_authorized",
        "clean_no_authority_packaging_authorized",
        "q15_r_p4_r_preparation_authorized",
        "q15_r_p4_k_preparation_authorized",
    }:
        errors.append("Q15-R-P4-D authority is wider or narrower than accepted")
    if acceptance.get("collector_contract_binding", {}).get("sha256") != CONTRACT_SHA256:
        errors.append("acceptance does not bind the frozen collector contract")
    return errors


def preparation_errors(document: dict[str, Any], phase: str) -> list[str]:
    errors: list[str] = []
    unresolved = document.get("unresolved_inputs", [])
    if len(unresolved) != 8 or any(item.get("value") is not None for item in unresolved):
        errors.append(f"{phase} must retain eight unresolved input groups")
    future = document.get("future_authorization", {})
    if future.get("status") != "NOT_ISSUED" or any(
        value is not None for name, value in future.items() if name != "status"
    ):
        errors.append(f"{phase} silently issues an authorization")
    boundary = document.get("authority_boundary", {})
    true_fields = {name for name, value in boundary.items() if value is True}
    if true_fields != {"repository_local_preparation_authorized"}:
        errors.append(f"{phase} grants authority beyond repository-local preparation")
    binding = document.get("acceptance_binding", {})
    if binding.get("sha256") != ACCEPTANCE_SHA256:
        errors.append(f"{phase} acceptance binding drifted")
    return errors


def artifact_fixture(contract: dict[str, Any], complete: bool) -> dict[str, Any]:
    commands = contract["commands"] if complete else contract["commands"][:3]
    observations = []
    for index, command in enumerate(commands):
        accepted = complete or index + 1 < len(commands)
        observations.append(
            {
                "accepted": accepted,
                "argv": command["argv"],
                "command_id": command["id"],
                "ended_at_utc": f"2026-08-25T00:00:00.{2 * index + 1:09d}Z",
                "exit_code": 0 if accepted else 9,
                "launched": True,
                "observation_kind": command["observation_kind"],
                "output_limit_exceeded": False,
                "spawn_error": 0,
                "started_at_utc": f"2026-08-25T00:00:00.{2 * index:09d}Z",
                "stderr_hex": "",
                "stdout_hex": "76616c75650a",
                "terminating_signal": None,
                "timed_out": False,
            }
        )
    return {
        "artifact_hash_profile": "Q15-R-PRESTATE-JCS-I64-ZEROSELF-SHA256-v1",
        "artifact_sha256": "a" * 64,
        "authorization_sha256": "b" * 64,
        "canonicalization": "JCS-I64-v1",
        "capture_id": "SYNTHETIC-P4R-CAPTURE",
        "collector_binary_sha256": "c" * 64,
        "collector_contract_id": "Q15-R-STAND-PRESTATE-COLLECTOR-CONTRACT-v1",
        "collector_contract_sha256": CONTRACT_SHA256,
        "completion_state": "COMPLETE" if complete else "PARTIAL_FAILED",
        "failed_command_id": None if complete else commands[-1]["id"],
        "failure_category": None if complete else "UNEXPECTED_EXIT_CODE",
        "observations": observations,
        "protocol_version": "2.0.0-pre.2",
        "schema_version": "cpu-prefetch-q15-r-stand-prestate/1",
        "selected_release_archive_sha256": (
            "8e8ad6d781b2bffadcfc10cf3b12d5666c7a1d4c7d7e291d7318a19503e6ab01"
        ),
        "source_revision": "d" * 40,
        "stand_id": "XEON-CPU-FETCH",
    }


def artifact_errors(document: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    observations = document.get("observations", [])
    expected = contract["commands"][: len(observations)]
    if [item.get("command_id") for item in observations] != [item["id"] for item in expected]:
        errors.append("artifact command prefix/order mismatch")
    if any(
        item.get("argv") != command["argv"]
        or item.get("observation_kind") != command["observation_kind"]
        for item, command in zip(observations, expected, strict=True)
    ):
        errors.append("artifact argv or observation kind mismatch")
    if document.get("completion_state") == "COMPLETE":
        if len(observations) != 25 or not all(item.get("accepted") for item in observations):
            errors.append("complete artifact is not a complete accepted command set")
        if document.get("failed_command_id") is not None or document.get("failure_category") is not None:
            errors.append("complete artifact carries failure state")
    else:
        if not observations or observations[-1].get("accepted") is not False:
            errors.append("partial artifact must end at its failed command")
        if document.get("failed_command_id") != observations[-1].get("command_id"):
            errors.append("partial artifact failed-command binding mismatch")
        if any(item.get("accepted") is not True for item in observations[:-1]):
            errors.append("partial artifact continued after an earlier failure")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    errors: list[str] = []
    documents = (
        ("config/q15/q15-r-stand-prestate-collector-contract-v1.json", "config/schemas/q15-r-stand-prestate-collector-contract-v1.schema.json"),
        ("config/q15/q15-r-p4-d-acceptance-v1.json", "config/schemas/q15-r-p4-d-acceptance-v1.schema.json"),
        ("config/q15/q15-r-p4-r.preparation.json", "config/schemas/q15-r-p4-r-preparation-v1.schema.json"),
        ("config/q15/q15-r-p4-k.preparation.json", "config/schemas/q15-r-p4-k-preparation-v1.schema.json"),
    )
    for document, schema in documents:
        errors.extend(schema_errors(root, document, schema))
    for relative, expected in EXPECTED_FILES.items():
        path = root / relative
        if not path.is_file() or sha256(path) != expected:
            errors.append(f"immutable or accepted binding mismatch: {relative}")

    contract = load(root / documents[0][0])
    acceptance = load(root / documents[1][0])
    read_preparation = load(root / documents[2][0])
    key_preparation = load(root / documents[3][0])
    errors.extend(contract_errors(contract))
    errors.extend(acceptance_errors(acceptance))
    errors.extend(preparation_errors(read_preparation, "Q15-R-P4-R"))
    errors.extend(preparation_errors(key_preparation, "Q15-R-P4-K"))
    if tuple(read_preparation.get("internal_command_ids", [])) != COMMAND_IDS:
        errors.append("Q15-R-P4-R command binding drifted")

    artifact_schema = load(root / "config/schemas/q15-r-stand-prestate-v1.schema.json")
    Draft202012Validator.check_schema(artifact_schema)
    artifact_validator = Draft202012Validator(artifact_schema)
    positives = [artifact_fixture(contract, True), artifact_fixture(contract, False)]
    for fixture in positives:
        raw = seal_synthetic_artifact(fixture)
        errors.extend(item.message for item in artifact_validator.iter_errors(fixture))
        errors.extend(artifact_errors(fixture, contract))
        errors.extend(
            validate_document(
                fixture, raw, contract, CONTRACT_SHA256, artifact_schema
            )
        )

    for decision in DECISIONS:
        number = decision.removeprefix("D-")
        matches = list((root / "docs/decisions").glob(f"0{number}-*.md"))
        if len(matches) != 1 or f"Decision ID: {decision}" not in matches[0].read_text(encoding="utf-8"):
            errors.append(f"accepted material decision lacks exactly one ADR: {decision}")

    source = (root / "src/qualification/q15_prestate.cpp").read_text(encoding="utf-8")
    cli = (root / "tools/q15_prestate_collector_main.cpp").read_text(encoding="utf-8")
    validator_source = (root / "tools/validate_q15_r_prestate.py").read_text(
        encoding="utf-8"
    )
    required_source = ("::posix_spawn", "O_CLOEXEC", "O_NONBLOCK", "SIGKILL", "canonical_and_hash")
    if any(token not in source for token in required_source):
        errors.append("collector source misses a required fixed execution/integrity seam")
    if any(token in source + cli for token in ("std::system(", "::system(", "popen(")):
        errors.append("collector source introduces shell execution")
    if "zero_self_canonical" not in validator_source or "strict=False" not in validator_source:
        errors.append("offline prestate validator is not bound to hash and exact-prefix rules")

    negatives: list[tuple[dict[str, Any], str]] = []
    mutant = copy.deepcopy(acceptance)
    mutant["remaining_literal_values"][0]["value"] = "/invented"
    negatives.append((mutant, "acceptance"))
    mutant = copy.deepcopy(acceptance)
    mutant["authority_boundary"]["stand_access_authorized"] = True
    negatives.append((mutant, "acceptance"))
    mutant = copy.deepcopy(contract)
    mutant["execution_contract"]["retry_count"] = 1
    negatives.append((mutant, "contract"))
    mutant = copy.deepcopy(contract)
    mutant["commands"][0]["argv"] = ["/bin/sh", "-c", "id"]
    negatives.append((mutant, "contract"))
    mutant = copy.deepcopy(contract)
    mutant["commands"].pop()
    negatives.append((mutant, "contract"))
    mutant = copy.deepcopy(read_preparation)
    mutant["authority_boundary"]["stand_access_authorized"] = True
    negatives.append((mutant, "read"))
    mutant = copy.deepcopy(read_preparation)
    mutant["future_authorization"]["status"] = "ISSUED"
    negatives.append((mutant, "read"))
    mutant = copy.deepcopy(read_preparation)
    mutant["unresolved_inputs"][0]["value"] = "latest"
    negatives.append((mutant, "read"))
    mutant = copy.deepcopy(key_preparation)
    mutant["authority_boundary"]["key_generation_authorized"] = True
    negatives.append((mutant, "key"))
    mutant = copy.deepcopy(key_preparation)
    mutant["future_authorization"]["status"] = "ISSUED"
    negatives.append((mutant, "key"))
    mutant = copy.deepcopy(positives[0])
    mutant["observations"][1], mutant["observations"][2] = mutant["observations"][2], mutant["observations"][1]
    negatives.append((mutant, "artifact"))
    mutant = copy.deepcopy(positives[1])
    mutant["observations"][-1]["accepted"] = True
    negatives.append((mutant, "artifact"))

    for index, (mutant, kind) in enumerate(negatives):
        if kind == "acceptance":
            mutant_errors = acceptance_errors(mutant)
        elif kind == "contract":
            mutant_errors = contract_errors(mutant)
        elif kind == "read":
            mutant_errors = preparation_errors(mutant, "Q15-R-P4-R")
        elif kind == "key":
            mutant_errors = preparation_errors(mutant, "Q15-R-P4-K")
        else:
            mutant_errors = [item.message for item in artifact_validator.iter_errors(mutant)]
            mutant_errors.extend(artifact_errors(mutant, contract))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for item in errors:
            print(f"q15-r-p4-d-implementation-check: FAIL: {item}", file=sys.stderr)
        return 1
    print(
        "q15-r-p4-d-implementation-check: PASS "
        "(D-066..D-070 accepted, 25 commands, 2 synthetic artifacts, "
        "12 negative, P4-R/P4-K unissued, authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
