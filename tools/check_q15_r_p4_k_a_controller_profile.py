#!/usr/bin/env python3
"""Validate the generic no-authority P4-K-A controller implementation profile."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


PROFILE_SHA256 = "0ceafd80200ba62584532e035a4c2a21015c2b56f75d0ebbfdffbd7f3b945875"
ACCEPTANCE_SHA256 = "c68e1b9427df9306a53cac590dfe268862fa528ef5bf665bf0002972cf77ffaf"
ADR_SHA256 = "c36be63168e5584d540a031a24d2e593aa7eca5c3554177052970153de631892"
IMPLEMENTATION = (
    (
        "include/cpu_prefetch/qualification/p4_k_a_controller.hpp",
        "634d61a221ba730066c06cde04ebba7266847917032ee04799255e91145d3112",
    ),
    (
        "src/qualification/p4_k_a_controller.cpp",
        "bb3075b523e82cf1c435f7ae98e1a656ac64b83c1a12bd325bd77496c7cb46b8",
    ),
    (
        "tests/p4_k_a_controller_test.cpp",
        "ed0f5a66e8bb4f4caeb887f64a7e4f938da6c72083a43f7d94c2ccf23eef7459",
    ),
)
GRAPH = (
    "VERIFY_SIGNED_AUTHORIZATION_AND_BOOTSTRAP_TRUST",
    "VERIFY_OFFLINE_ENVIRONMENT_TOOLCHAIN_AND_NETWORK_STATE",
    "VERIFY_CUSTODY_AND_CREATE_EXCLUSIVE_PUBLIC_OUTPUTS",
    "GENERATE_ENCRYPTED_ED25519_PRIVATE_KEY_ONCE",
    "EXTRACT_ED25519_PUBLIC_KEY_ONCE",
    "DERIVE_ED25519_FINGERPRINT_ONCE",
    "CONSTRUCT_CANONICAL_ALLOWED_SIGNERS_ONCE",
    "CAPTURE_NONSECRET_CUSTODY_RECEIPT",
    "SEAL_COMPLETE_OR_PARTIAL_PUBLIC_EVIDENCE",
    "STOP_FOR_SEPARATE_P4_K_R",
)


def synthetic_admission() -> dict[str, Any]:
    hashes = [f"{digit}" * 64 for digit in "012"]
    return {
        "schema_version": "cpu-prefetch-q15-r-p4-k-a-controller-admission/1",
        "protocol_version": "2.0.0-pre.2",
        "controller_profile_id": "Q15-R-P4-K-A-FIXED-CEREMONY-CONTROLLER-v1",
        "gate_id": "Q15-R-P4-K-A",
        "status": "AUTHORIZED",
        "source_revision": "synthetic-clean-source",
        "controller_binary_sha256": hashes[0],
        "binding_id": "synthetic-binding",
        "authorization_id": "synthetic-authorization",
        "authorization_core_sha256": hashes[1],
        "issued_at_utc": "2026-08-25T00:00:00Z",
        "expires_at_utc": "2026-08-25T00:30:00Z",
        "detached_signature_artifact_id": "synthetic-signature",
        "detached_signature_sha256": hashes[2],
        "signature_verification_artifact_id": "synthetic-verification",
        "signature_verification_sha256": hashes[0],
        "signature_scheme": "OPENSSH-SSHSIG-ED25519-SHA512-v1",
        "signature_namespace": "cpu-prefetch-q15-authorization",
        "authorization_principal": "cpu-prefetch-q15-authorization",
        "bootstrap_signer_fingerprint": "SHA256:SYNTHETIC",
        "bootstrap_trust_artifact_id": "synthetic-bootstrap-trust",
        "bootstrap_trust_sha256": hashes[1],
        "auditor_review_artifact_id": "synthetic-auditor-review",
        "auditor_review_sha256": hashes[2],
        "offline_environment_artifact_id": "synthetic-environment",
        "offline_environment_sha256": hashes[0],
        "toolchain_artifact_id": "synthetic-toolchain",
        "toolchain_sha256": hashes[1],
        "custody_artifact_id": "synthetic-custody",
        "custody_sha256": hashes[2],
        "public_export_transaction_id": "synthetic-public-export",
        "public_export_root": "/synthetic/offline/public",
        "key_generation_tool_path": "/usr/bin/ssh-keygen",
        "key_generation_argv": ["/usr/bin/ssh-keygen", "-t", "ed25519"],
        "public_extraction_tool_path": "/usr/bin/ssh-keygen",
        "public_extraction_argv": ["/usr/bin/ssh-keygen", "-y"],
        "fixed_environment": [
            {"name": "LANG", "value": "C"},
            {"name": "PATH", "value": "/usr/bin"},
        ],
        "secret_input": {"kind": "UNCAPTURED_CONTROLLING_TTY", "descriptor": None},
        "limits": {
            "maximum_wall_seconds": 600,
            "maximum_stdout_bytes": 4096,
            "maximum_stderr_bytes": 4096,
            "maximum_public_artifact_count": 32,
        },
        "command_graph": list(GRAPH),
        "action_attempt_count": 1,
        "retry_count": 0,
        "network_unavailable_verified": True,
        "public_export_outside_repository_and_stand_verified": True,
        "create_exclusive_public_outputs": True,
        "overwrite_repair_cleanup_allowed": False,
        "stop_before_p4_k_r": True,
        "automatic_continuation_allowed": False,
    }


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_errors(root: pathlib.Path, profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lineage = profile.get("lineage", {})
    acceptance_path = root / str(lineage.get("p4_k_a_policy_acceptance_path", ""))
    if (
        lineage.get("p4_k_a_policy_acceptance_sha256") != ACCEPTANCE_SHA256
        or not acceptance_path.is_file()
        or sha256(acceptance_path) != ACCEPTANCE_SHA256
    ):
        errors.append("controller profile must bind the immutable P4-K-A-D acceptance")
    acceptance = load(acceptance_path) if acceptance_path.is_file() else {}
    bootstrap = acceptance.get("bootstrap_trust_disposition", {})
    if (
        bootstrap.get("qualifying_bootstrap_signer_evidence_exists") is not False
        or bootstrap.get("bootstrap_signer_or_trust_evidence_supplied") is not False
        or bootstrap.get("p4_k_a_issuance_state") != "BLOCKED"
    ):
        errors.append("controller implementation must preserve the absent-bootstrap block")

    observed = tuple(
        (item.get("path"), item.get("sha256"))
        for item in profile.get("implementation", [])
    )
    if observed != IMPLEMENTATION:
        errors.append("implementation paths and hashes must be exact and ordered")
    for path_text, expected_hash in IMPLEMENTATION:
        path = root / path_text
        if not path.is_file() or sha256(path) != expected_hash:
            errors.append(f"implementation hash mismatch: {path_text}")
    if tuple(profile.get("command_graph", [])) != GRAPH:
        errors.append("fixed P4-K-A controller graph drifted")

    boundary = profile.get("authority_boundary", {})
    enabled = {
        name for name, value in boundary.items() if name.endswith("_authorized") and value
    }
    if enabled != {
        "repository_local_generic_controller_schema_test_and_documentation_implementation_authorized"
    }:
        errors.append("controller profile widens authority beyond repository-local work")
    external = profile.get("external_evidence_state", {})
    if any(external.values()):
        errors.append("generic implementation cannot claim any external evidence or action")

    template = load(root / "config/q15/q15-r-p4-k-a.authorization-template-v1.json")
    if len(template.get("unresolved_inputs", [])) != 7 or any(
        item.get("value") is not None for item in template.get("unresolved_inputs", [])
    ):
        errors.append("P4-K-A template must retain seven null inputs")
    if any(
        item.get("value") is not None for item in template.get("prospective_outputs", [])
    ):
        errors.append("P4-K-A template must retain all prospective outputs as null")

    source = (root / "src/qualification/p4_k_a_controller.cpp").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "std::system",
        "popen(",
        "fork(",
        "execve(",
        "ifstream",
        "ofstream",
        "<filesystem>",
        "<unistd.h>",
    )
    if any(token in source for token in forbidden):
        errors.append("generic controller source contains an OS execution or file-I/O seam")

    adr_path = root / "docs/decisions/0086-q15-r-p4-k-a-generic-controller-implementation.md"
    if not adr_path.is_file() or sha256(adr_path) != ADR_SHA256:
        errors.append("ADR-0086 hash mismatch")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    path = root / "config/q15/q15-r-p4-k-a-controller-profile-v1.json"
    profile = load(path)
    schema = load(
        root / "config/schemas/q15-r-p4-k-a-controller-profile-v1.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(profile)]
    errors.extend(semantic_errors(root, profile))
    if sha256(path) != PROFILE_SHA256:
        errors.append("P4-K-A controller profile bytes drifted")

    admission_schema = load(
        root / "config/schemas/q15-r-p4-k-a-controller-admission-v1.schema.json"
    )
    Draft202012Validator.check_schema(admission_schema)
    admission_validator = Draft202012Validator(admission_schema)
    admission = synthetic_admission()
    if list(admission_validator.iter_errors(admission)):
        errors.append("synthetic complete admission must satisfy the strict schema")
    admission_negatives: list[dict[str, Any]] = []
    for field, value in (
        ("status", "PREPARED"),
        ("retry_count", 1),
        ("automatic_continuation_allowed", True),
        ("key_generation_tool_path", "/bin/sh"),
    ):
        mutant = copy.deepcopy(admission)
        mutant[field] = value
        admission_negatives.append(mutant)
    secret = copy.deepcopy(admission)
    secret["fixed_environment"].append({"name": "PASSPHRASE", "value": "secret"})
    admission_negatives.append(secret)
    descriptor = copy.deepcopy(admission)
    descriptor["secret_input"] = {"kind": "DEDICATED_DESCRIPTOR", "descriptor": 2}
    admission_negatives.append(descriptor)
    for index, mutant in enumerate(admission_negatives):
        if not list(admission_validator.iter_errors(mutant)):
            errors.append(f"admission-schema negative mutation {index} passed")

    negatives: list[dict[str, Any]] = []
    for field in (
        "offline_environment_access_or_inventory_authorized",
        "bootstrap_governance_root_establishment_authorized_by_this_record",
        "key_read_generation_import_copy_fingerprint_or_use_authorized",
        "public_export_path_or_artifact_creation_authorized",
        "signing_or_issuance_authorized",
        "p4_k_a_authorized",
        "stand_access_authorized",
        "calibration_pilot_measurement_or_confirmatory_authorized",
    ):
        mutant = copy.deepcopy(profile)
        mutant["authority_boundary"][field] = True
        negatives.append(mutant)
    bootstrap = copy.deepcopy(profile)
    bootstrap["external_evidence_state"]["bootstrap_root_established"] = True
    negatives.append(bootstrap)
    action = copy.deepcopy(profile)
    action["external_evidence_state"]["key_or_public_artifact_created"] = True
    negatives.append(action)
    graph = copy.deepcopy(profile)
    graph["command_graph"][0], graph["command_graph"][1] = (
        graph["command_graph"][1],
        graph["command_graph"][0],
    )
    negatives.append(graph)
    retry = copy.deepcopy(profile)
    retry["fixed_controller_contract"]["retry_count"] = 1
    negatives.append(retry)
    shell = copy.deepcopy(profile)
    shell["fixed_controller_contract"]["process_mode"] = "SHELL"
    negatives.append(shell)
    source = copy.deepcopy(profile)
    source["implementation"][1]["sha256"] = "0" * 64
    negatives.append(source)

    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(f"q15-r-p4-k-a-controller-profile-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "q15-r-p4-k-a-controller-profile-check: PASS "
        "(10 fixed steps, 14 profile + 6 admission negative, 7 inputs null, "
        "OS/key/trust/stand authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
