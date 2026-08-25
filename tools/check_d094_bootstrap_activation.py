#!/usr/bin/env python3
"""Validate D-094 activation and the still-unissued P4-K-A successor."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator


FINGERPRINT = "SHA256:JuRM4SuWL9C1xvOes9z+CAKZV1rvel27VZ/+qiuVNs0"
EXPECTED_UNRESOLVED = (
    "EXACT_OFFLINE_CEREMONY_AND_PUBLIC_EXTRACTION_TOOL_IDS_VERSIONS_SHA256_AND_FIXED_ARGV",
    "CREATE_EXCLUSIVE_PUBLIC_ARTIFACT_IDS_AND_ABSOLUTE_SOURCE_PATHS",
    "OFFLINE_CUSTODY_CONTROL_AND_CEREMONY_ENVIRONMENT_EVIDENCE_ID_AND_SHA256",
    "LITERAL_ISSUE_AND_EXPIRY_UTC_INSTANTS",
    "CANONICAL_AUTHORIZATION_SHA256_AND_DETACHED_SIGNATURE_SHA256",
    "DISTINCT_AUDITOR_PRE_EXECUTION_REVIEW_ARTIFACT_ID_AND_SHA256",
)


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schema_errors(instance: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    Draft202012Validator.check_schema(schema)
    return [item.message for item in Draft202012Validator(schema).iter_errors(instance)]


def binding_errors(root: pathlib.Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lineage = record.get("lineage", {})
    pairs = (
        ("decision_adr_path", "decision_adr_sha256"),
        ("d093_evidence_path", "d093_evidence_sha256"),
        ("d093_lifecycle_policy_path", "d093_lifecycle_policy_sha256"),
        ("predecessor_policy_path", "predecessor_policy_sha256"),
        ("activation_authorization_path", "activation_authorization_sha256"),
        ("predecessor_template_path", "predecessor_template_sha256"),
        ("policy_acceptance_path", "policy_acceptance_sha256"),
        ("active_lifecycle_state_path", "active_lifecycle_state_sha256"),
    )
    for path_name, hash_name in pairs:
        if path_name not in lineage:
            continue
        path = root / str(lineage[path_name])
        if not path.is_file() or sha256(path) != lineage.get(hash_name):
            errors.append(f"lineage mismatch: {path_name}")
    return errors


def semantic_errors(
    root: pathlib.Path,
    activation: dict[str, Any],
    lifecycle: dict[str, Any],
    successor: dict[str, Any],
) -> list[str]:
    errors = binding_errors(root, activation)
    errors.extend(binding_errors(root, lifecycle))
    errors.extend(binding_errors(root, successor))
    exact_root = activation.get("exact_root", {})
    transition = activation.get("transition", {})
    if (
        exact_root.get("fingerprint") != FINGERPRINT
        or transition.get("from") != "CREATED"
        or transition.get("to") != "ACTIVE"
        or transition.get("private_key_read_hashed_copied_or_used") is not False
        or transition.get("signature_created") is not False
        or transition.get("automatic_p4_k_a_continuation") is not False
    ):
        errors.append("activation identity, transition, or no-use boundary mismatch")
    activation_boundary = activation.get("authority_boundary", {})
    activation_true = {
        name for name, value in activation_boundary.items() if value is True
    }
    if activation_true != {
        "repository_local_activation_record_authorized",
        "repository_local_p4_k_a_successor_preparation_authorized",
    }:
        errors.append("activation authority exceeds record/preparation scope")

    if (
        lifecycle.get("fingerprint") != FINGERPRINT
        or lifecycle.get("current_root_state") != "ACTIVE"
        or [item.get("sequence") for item in lifecycle.get("history", [])] != [1, 2]
        or lifecycle.get("history", [{}])[-1].get("from") != "CREATED"
        or lifecycle.get("history", [{}])[-1].get("to") != "ACTIVE"
    ):
        errors.append("append-only CREATED-to-ACTIVE history mismatch")
    lifecycle_boundary = lifecycle.get("authority_boundary", {})
    lifecycle_true = {
        name for name, value in lifecycle_boundary.items() if value is True
    }
    if lifecycle_true != {"root_is_eligible_for_future_separately_authorized_signing"}:
        errors.append("active state was confused with current signing/action authority")

    predecessor = load(root / "config/q15/q15-r-p4-k-a.authorization-template-v1.json")
    if successor.get("fixed_action_contract") != predecessor.get(
        "fixed_action_contract"
    ):
        errors.append("successor changed the target-key action contract")
    if successor.get("prospective_outputs") != predecessor.get("prospective_outputs"):
        errors.append("successor fabricated or changed a prospective output")
    if successor.get("rollback") != predecessor.get("rollback"):
        errors.append("successor changed rollback/failure governance")
    old_gate = copy.deepcopy(predecessor.get("gate", {}))
    new_gate = copy.deepcopy(successor.get("gate", {}))
    old_gate["bootstrap_authorization_signer_fingerprint"] = FINGERPRINT
    old_gate["bootstrap_authorization_trust_evidence_sha256"] = sha256(
        root / "config/q15/q15-r-bootstrap-root-lifecycle-state-v2.json"
    )
    if new_gate != old_gate:
        errors.append("successor changed a gate field other than exact bootstrap trust")

    unresolved = successor.get("unresolved_inputs", [])
    if tuple(item.get("name") for item in unresolved) != EXPECTED_UNRESOLVED:
        errors.append("successor must retain exactly six unresolved inputs in order")
    if any(item.get("value") is not None for item in unresolved):
        errors.append("successor fabricated a remaining P4-K-A input")
    resolved = successor.get("resolved_input_groups", [])
    if (
        len(resolved) != 1
        or resolved[0].get("name")
        != "BOOTSTRAP_AUTHORIZATION_SIGNER_FINGERPRINT_AND_TRUST_EVIDENCE_SHA256"
        or resolved[0].get("value", {}).get("fingerprint") != FINGERPRINT
        or resolved[0].get("value", {}).get("active_lifecycle_state_sha256")
        != sha256(root / "config/q15/q15-r-bootstrap-root-lifecycle-state-v2.json")
    ):
        errors.append("successor may resolve only exact active bootstrap trust")
    successor_boundary = successor.get("authority_boundary", {})
    successor_true = {
        name for name, value in successor_boundary.items() if value is True
    }
    if successor_true != {
        "repository_local_successor_preparation_authorized",
        "bootstrap_root_active",
    }:
        errors.append("P4-K-A successor grants signing, key, stand, or experiment authority")
    return errors


def negative_cases(
    activation: dict[str, Any],
    lifecycle: dict[str, Any],
    successor: dict[str, Any],
) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    result = []
    for target, section, field, value in (
        ("activation", "exact_root", "fingerprint", "SHA256:wrong"),
        ("activation", "transition", "from", "ACTIVE"),
        ("activation", "transition", "signature_created", True),
        ("activation", "authority_boundary", "root_signing_authorized", True),
        ("lifecycle", "authority_boundary", "current_signing_action_authorized", True),
        ("lifecycle", "authority_boundary", "p4_k_a_or_p4_k_r_execution_authorized", True),
        ("successor", "authority_boundary", "p4_k_a_authorized", True),
        ("successor", "authority_boundary", "key_read_generation_import_copy_fingerprint_or_use_authorized", True),
    ):
        copies = [copy.deepcopy(activation), copy.deepcopy(lifecycle), copy.deepcopy(successor)]
        index = {"activation": 0, "lifecycle": 1, "successor": 2}[target]
        copies[index][section][field] = value
        result.append((copies[0], copies[1], copies[2]))
    fabricated = [copy.deepcopy(activation), copy.deepcopy(lifecycle), copy.deepcopy(successor)]
    fabricated[2]["unresolved_inputs"][0]["value"] = {"invented": True}
    result.append((fabricated[0], fabricated[1], fabricated[2]))
    issued = [copy.deepcopy(activation), copy.deepcopy(lifecycle), copy.deepcopy(successor)]
    issued[2]["gate"]["authorization_id"] = "PREMATURE"
    result.append((issued[0], issued[1], issued[2]))
    lineage = [copy.deepcopy(activation), copy.deepcopy(lifecycle), copy.deepcopy(successor)]
    lineage[1]["lineage"]["activation_authorization_sha256"] = "0" * 64
    result.append((lineage[0], lineage[1], lineage[2]))
    missing = [copy.deepcopy(activation), copy.deepcopy(lifecycle), copy.deepcopy(successor)]
    missing[2]["unresolved_inputs"].pop()
    result.append((missing[0], missing[1], missing[2]))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-external",
        action="store_true",
        help="also rerun the D-093 read-only public/private-metadata verifier",
    )
    arguments = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    paths = (
        root / "config/q15/q15-r-bootstrap-root-d094-activation-authorization-v1.json",
        root / "config/q15/q15-r-bootstrap-root-lifecycle-state-v2.json",
        root / "config/q15/q15-r-p4-k-a.authorization-template-v2.json",
    )
    schema_paths = (
        root / "config/schemas/q15-r-bootstrap-root-d094-activation-authorization-v1.schema.json",
        root / "config/schemas/q15-r-bootstrap-root-lifecycle-state-v2.schema.json",
        root / "config/schemas/q15-r-p4-k-a-authorization-template-v2.schema.json",
    )
    records = tuple(load(path) for path in paths)
    schemas = tuple(load(path) for path in schema_paths)
    errors: list[str] = []
    for record, schema in zip(records, schemas, strict=True):
        errors.extend(schema_errors(record, schema))
    errors.extend(semantic_errors(root, *records))

    validators = tuple(Draft202012Validator(schema) for schema in schemas)
    for index, mutant in enumerate(negative_cases(*records)):
        rejected: list[Any] = []
        for value, validator in zip(mutant, validators, strict=True):
            rejected.extend(validator.iter_errors(value))
        rejected.extend(semantic_errors(root, *mutant))
        if not rejected:
            errors.append(f"negative mutation {index} passed")

    if arguments.verify_external:
        external = subprocess.run(
            [sys.executable, str(root / "tools/verify_d093_bootstrap_evidence.py")],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if external.returncode != 0:
            errors.append(f"external D-093 verifier failed: {external.stderr.strip()}")
        else:
            summary = json.loads(external.stdout)
            if summary.get("fingerprint") != FINGERPRINT:
                errors.append("external public fingerprint differs from active root")

    if errors:
        for error in errors:
            print(f"d094-bootstrap-activation-check: FAIL: {error}", file=sys.stderr)
        return 1
    external_scope = " + external public/private-metadata evidence" if arguments.verify_external else ""
    print(
        "d094-bootstrap-activation-check: PASS "
        f"(CREATED->ACTIVE, bootstrap input 1/7 resolved, 6 remain, "
        f"12 negative{external_scope}, signing/P4-K/stand/pilot authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
