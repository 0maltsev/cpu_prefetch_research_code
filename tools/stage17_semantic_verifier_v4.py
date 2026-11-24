#!/usr/bin/env python3
"""Fail-closed Stage 17 S17-EXT-001 semantic verifier, policy version 4."""

from __future__ import annotations

import base64
import os
import pathlib
import re
import stat
from typing import Any

from stage17_read_only_preflight_collector_v2 import validate_exact_second_utc
from stage17_semantic_verifier_v3 import (
    LIMITS,
    OBSERVATION_IDS,
    PERMISSIONS,
    SAFE_HOST,
    SAFE_SSH_TARGET,
    SemanticAdmissionError,
    _binding,
    _binding_for,
    _external_regular_file,
    _load_json,
    _normalized_absolute,
    _parse_utc,
    _repository_file,
    _sha256,
    _validate_schema,
    _nonsymlink_components,
    validate_ed25519_wire_blob,
)


VERIFIER_ID = "STAGE17-S17-EXT-001-SEMANTIC-VERIFIER"
VERIFIER_VERSION = "4"
POLICY_V3_PATH = "config/stage17/stage17-operational-evidence-admission-policy-v3.json"
ADR_0107_PATH = "docs/decisions/0107-stage17-fixed-read-only-action-semantics.md"
ADR_0108_PATH = "docs/decisions/0108-stage17-one-shot-runtime-and-durability-boundary.md"
ACTION_PLAN_PATH = "config/stage17/stage17-read-only-preflight-fixed-action-plan-v2.json"
EXECUTOR_PATH = "tools/stage17_read_only_preflight_executor_v2.py"
COLLECTOR_PATH = "tools/stage17_read_only_preflight_collector_v2.py"
STATE_JOURNAL_PATH = "tools/stage17_state_journal.py"
VERIFIER_V3_HELPER_PATH = "tools/stage17_semantic_verifier_v3.py"
COLLECTOR_V1_HELPER_PATH = "tools/stage17_read_only_preflight_collector_v1.py"
PILOT_VERIFIER_PATH = "tools/stage17_pilot_candidate_artifact.py"
AUTHORIZATION_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-authorization-v4.schema.json"
CONTRACT_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-supporting-contract-v4.schema.json"
ENVELOPE_SCHEMA_PATH = "config/schemas/stage17-operational-evidence-envelope-v4.schema.json"
PLAN_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-fixed-action-plan-v2.schema.json"
ATTEMPT_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-attempt-v2.schema.json"
RECEIPT_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-observation-receipt-v1.schema.json"
FAILURE_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-failure-v2.schema.json"
COMPLETION_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-completion-v1.schema.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-operational-evidence-admission-policy-v4.schema.json"
V4_SCHEMA_PATHS = (
    POLICY_SCHEMA_PATH,
    ENVELOPE_SCHEMA_PATH,
    AUTHORIZATION_SCHEMA_PATH,
    CONTRACT_SCHEMA_PATH,
    PLAN_SCHEMA_PATH,
    ATTEMPT_SCHEMA_PATH,
    RECEIPT_SCHEMA_PATH,
    FAILURE_SCHEMA_PATH,
    COMPLETION_SCHEMA_PATH,
)
IMPLEMENTATION_PATHS = {
    "semantic_verifier": "tools/stage17_semantic_verifier_v4.py",
    "executor": EXECUTOR_PATH,
    "collector": COLLECTOR_PATH,
    "state_journal": STATE_JOURNAL_PATH,
    "semantic_verifier_v3_helper": VERIFIER_V3_HELPER_PATH,
    "collector_v1_helper": COLLECTOR_V1_HELPER_PATH,
    "pilot_candidate_verifier": PILOT_VERIFIER_PATH,
}
REMOTE_COMMAND = "/usr/bin/env -i LANG=C LC_ALL=C TZ=UTC0 /usr/bin/python3 -I -S -"
OPENSSH_LITERAL_PATH = re.compile(r"^/[A-Za-z0-9._/+@-]+$")
ATTEMPT_NAME = "stage17-read-only-preflight-attempt-v2.json"
FAILURE_NAME = "stage17-read-only-preflight-failure-v2.json"
COMPLETION_NAME = "stage17-read-only-preflight-completion-v1.json"


def _external_executable(
    path_value: object, expected: dict[str, Any], label: str
) -> pathlib.Path:
    path = _normalized_absolute(path_value, label)
    _nonsymlink_components(path, label)
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o111 == 0:
        raise SemanticAdmissionError(f"{label} is not an executable regular file")
    if metadata.st_size != expected["size_bytes"] or _sha256(path) != expected["sha256"]:
        raise SemanticAdmissionError(f"{label} bytes do not match policy binding")
    return path


def _openssh_literal_path(path: pathlib.Path, label: str) -> pathlib.Path:
    value = str(path)
    if OPENSSH_LITERAL_PATH.fullmatch(value) is None:
        raise SemanticAdmissionError(
            f"{label} contains OpenSSH expansion or configuration characters"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise SemanticAdmissionError(f"{label} contains control characters")
    return path


def _safe_evidence_root(root: pathlib.Path, value: object) -> tuple[pathlib.Path, dict[str, int]]:
    path = _normalized_absolute(value, "evidence root")
    _nonsymlink_components(path, "evidence root")
    metadata = os.lstat(path)
    if not stat.S_ISDIR(metadata.st_mode):
        raise SemanticAdmissionError("evidence root is not a directory")
    if metadata.st_uid != os.geteuid():
        raise SemanticAdmissionError("evidence root is not owned by the executing owner")
    if stat.S_IMODE(metadata.st_mode) & 0o022:
        raise SemanticAdmissionError("evidence root is group/other writable")
    resolved = path.resolve()
    repository = root.resolve()
    forbidden = (pathlib.Path("/etc"), pathlib.Path("/proc"), pathlib.Path("/sys"))
    if resolved == repository or repository in resolved.parents:
        raise SemanticAdmissionError("evidence root is inside the repository")
    if resolved == pathlib.Path("/") or any(
        resolved == item or item in resolved.parents for item in forbidden
    ):
        raise SemanticAdmissionError("evidence root is a forbidden system path")
    return path, {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "uid": metadata.st_uid,
        "mode": stat.S_IMODE(metadata.st_mode),
    }


def verify_policy_v4(
    *,
    root: pathlib.Path,
    policy: dict[str, Any],
    graph_sha256: str,
    catalog_sha256: str,
    genesis_file_sha256: str,
    genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v4")
    expected_predecessor = {
        "policy_v3": _binding_for(root, POLICY_V3_PATH),
        "adr_0107": _binding_for(root, ADR_0107_PATH),
        "adr_0108": _binding_for(root, ADR_0108_PATH),
        "graph_sha256": graph_sha256,
        "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if policy.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v4 predecessor binding drifted")
    if policy.get("schema_bindings") != [
        _binding_for(root, item) for item in V4_SCHEMA_PATHS
    ]:
        raise SemanticAdmissionError("semantic policy v4 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v4 action-plan binding drifted")
    expected_implementations = {
        name: _binding_for(root, relative)
        for name, relative in IMPLEMENTATION_PATHS.items()
    }
    if policy.get("implementations") != expected_implementations:
        raise SemanticAdmissionError("semantic policy v4 runtime binding drifted")
    expected_ids = [f"S17-EXT-{index:03d}" for index in range(1, 11)]
    entries = policy.get("entries", [])
    if [entry.get("input_id") for entry in entries] != expected_ids:
        raise SemanticAdmissionError("semantic policy v4 registry drifted")
    if entries[0] != {
        "input_id": "S17-EXT-001",
        "status": "IMPLEMENTED",
        "verifier_id": VERIFIER_ID,
        "verifier_version": VERIFIER_VERSION,
    }:
        raise SemanticAdmissionError("S17-EXT-001 v4 registration drifted")
    for entry in entries[1:5] + entries[6:]:
        if entry.get("status") != "SEMANTIC_VERIFIER_NOT_IMPLEMENTED_FAIL_CLOSED":
            raise SemanticAdmissionError("unimplemented Stage 17 verifier became fail-open")


def _verify_action_plan(
    root: pathlib.Path, policy: dict[str, Any]
) -> tuple[dict[str, Any], pathlib.Path]:
    path = _binding(root, policy["fixed_action_plan"], "fixed action plan v2")
    plan = _load_json(path)
    _validate_schema(root, plan, PLAN_SCHEMA_PATH, "fixed action plan v2")
    if plan.get("predecessor") != _binding_for(
        root, "config/stage17/stage17-read-only-preflight-fixed-action-plan-v1.json"
    ):
        raise SemanticAdmissionError("fixed action plan v2 predecessor drifted")
    transport = plan.get("transport", {})
    if (
        plan.get("owner_command_bytes_allowed") is not False
        or transport.get("local_shell") is not False
        or transport.get("ssh_executable") != "/usr/bin/ssh"
        or transport.get("remote_command") != REMOTE_COMMAND
        or transport.get("attempts_per_observation") != 1
        or transport.get("retries") != 0
        or transport.get("stop_on_first_failure") is not True
        or transport.get("global_monotonic_deadline_seconds") != 180
    ):
        raise SemanticAdmissionError("fixed action plan v2 transport drifted")
    observations = plan.get("observations", [])
    if tuple(item.get("observation_id") for item in observations) != OBSERVATION_IDS:
        raise SemanticAdmissionError("fixed observation family drifted")
    if [item.get("ordinal") for item in observations] != list(range(1, 7)):
        raise SemanticAdmissionError("fixed observation ordinals drifted")
    if set(plan.get("forbidden_semantics", {}).values()) != {True}:
        raise SemanticAdmissionError("fixed action plan v2 lost a prohibition")
    if plan.get("authority_boundary") != PERMISSIONS:
        raise SemanticAdmissionError("fixed action plan v2 widened authority")
    names = plan.get("evidence_root_policy", {})
    if (
        names.get("attempt_marker_relative_path") != ATTEMPT_NAME
        or names.get("failure_relative_path") != FAILURE_NAME
        or names.get("completion_relative_path") != COMPLETION_NAME
    ):
        raise SemanticAdmissionError("fixed durable record names drifted")
    return plan, path


def _verify_known_host(
    root: pathlib.Path, target: dict[str, Any]
) -> tuple[pathlib.Path, pathlib.Path, bytes]:
    pinned_path = _binding(root, target["pinned_host_key_evidence"], "pinned host key")
    pinned = _load_json(pinned_path)
    _validate_schema(
        root,
        pinned,
        "config/schemas/stage17-pinned-host-key-evidence-v1.schema.json",
        "pinned host key",
    )
    if (
        pinned.get("stand_id") != target["stand_id"]
        or pinned.get("ssh_target") != target["ssh_target"]
        or pinned.get("algorithm") != "ssh-ed25519"
    ):
        raise SemanticAdmissionError("pinned host-key target or algorithm mismatch")
    blob, fingerprint = validate_ed25519_wire_blob(pinned.get("public_key_base64"))
    if pinned.get("fingerprint_sha256") != fingerprint:
        raise SemanticAdmissionError("pinned host-key fingerprint mismatch")
    known_hosts = _binding(root, target["pinned_known_hosts"], "pinned known-hosts")
    _openssh_literal_path(known_hosts, "pinned known-hosts path")
    expected = (
        f"{target['known_hosts_host']} ssh-ed25519 "
        f"{base64.b64encode(blob).decode('ascii')}\n"
    ).encode("ascii")
    if known_hosts.read_bytes() != expected:
        raise SemanticAdmissionError("pinned known-hosts bytes mismatch")
    return pinned_path, known_hosts, blob


def _verify_contract_action_inputs(
    root: pathlib.Path,
    contract: dict[str, Any],
    policy: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    plan, plan_path = _verify_action_plan(root, policy)
    expected_plan = {
        **policy["fixed_action_plan"],
        "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/2",
    }
    if contract.get("fixed_action_plan") != expected_plan:
        raise SemanticAdmissionError("supporting contract action-plan binding mismatch")
    target = contract["target"]
    stand_id = target.get("stand_id")
    ssh_target = target.get("ssh_target")
    known_host = target.get("known_hosts_host")
    if not isinstance(stand_id, str) or not stand_id or stand_id != stand_id.strip():
        raise SemanticAdmissionError("stand ID is not exact")
    if not isinstance(ssh_target, str) or SAFE_SSH_TARGET.fullmatch(ssh_target) is None:
        raise SemanticAdmissionError("SSH target is not a fixed user@host token")
    if not isinstance(known_host, str) or SAFE_HOST.fullmatch(known_host) is None:
        raise SemanticAdmissionError("known-hosts host is not a fixed host token")
    if ssh_target.rsplit("@", 1)[1] != known_host:
        raise SemanticAdmissionError("SSH target and known-hosts host mismatch")
    pinned_path, known_hosts_path, _ = _verify_known_host(root, target)
    transport_identity = _external_regular_file(
        target.get("transport_identity_locator"), "transport identity"
    )
    _openssh_literal_path(transport_identity, "transport identity path")

    fixed_contract = catalog["fixed_evidence_contracts"][0]
    expected_pilot = {
        "path": fixed_contract["path"],
        "size_bytes": fixed_contract["size_bytes"],
        "sha256": fixed_contract["sha256"],
        "schema_identity": "cpu-prefetch-stage17-pilot-candidate-external-contract/1",
    }
    if contract["pilot_candidate"]["contract"] != expected_pilot:
        raise SemanticAdmissionError("pilot-candidate contract binding mismatch")
    pilot_path = _binding(root, expected_pilot, "pilot-candidate contract")
    pilot = _load_json(pilot_path)
    archive = _normalized_absolute(
        contract["pilot_candidate"]["archive_locator"], "archive locator"
    )
    sidecar = _normalized_absolute(
        contract["pilot_candidate"]["sidecar_locator"], "sidecar locator"
    )
    bundle_root = _normalized_absolute(
        contract["pilot_candidate"]["bundle_root_locator"], "bundle root locator"
    )
    if len({archive, sidecar, bundle_root}) != 3:
        raise SemanticAdmissionError("pilot-candidate locators are not distinct")
    try:
        validate_exact_second_utc(contract["capture"].get("captured_at_utc"))
    except ValueError as exception:
        raise SemanticAdmissionError(str(exception)) from exception

    expected_identity = (
        ("STAGE17_READ_ONLY_PREFLIGHT_EXECUTOR", "EXECUTOR", "executor"),
        ("STAGE17_READ_ONLY_PREFLIGHT_COLLECTOR", "COLLECTOR", "collector"),
    )
    execution_paths: dict[str, pathlib.Path] = {}
    for identity, (identity_id, role, implementation_name) in zip(
        contract["prospective_local_action_identities"], expected_identity, strict=True
    ):
        if (identity.get("identity_id"), identity.get("role")) != (identity_id, role):
            raise SemanticAdmissionError("prospective action identity family drifted")
        expected_source = policy["implementations"][implementation_name]
        if identity.get("source_binding") != expected_source:
            raise SemanticAdmissionError("prospective action source binding drifted")
        execution_paths[role] = _external_executable(
            identity.get("execution_path"), expected_source, f"{role} execution path"
        )
    if contract.get("remote_runtime_identity_policy") != {
        "source_input_id": "S17-EXT-002",
        "identity_classes": ["REMOTE_EXECUTABLE", "REMOTE_MODULE", "REMOTE_DEPENDENCY"],
        "prospective_values_present": False,
    }:
        raise SemanticAdmissionError("remote runtime identities were fabricated")
    if contract.get("limits") != LIMITS:
        raise SemanticAdmissionError("fixed limits drifted")
    if contract.get("stop_policy") != "STOP_ON_FIRST_MISMATCH_NONZERO_EXIT_TIMEOUT_OR_OUTPUT_LIMIT":
        raise SemanticAdmissionError("stop-first policy drifted")
    if contract.get("retention_policy") != "CREATE_EXCLUSIVE_APPEND_ONLY_RETAIN_SUCCESS_FAILURE_AND_PARTIAL_NO_DELETE":
        raise SemanticAdmissionError("partial-retention policy drifted")
    if contract.get("authority_boundary") != PERMISSIONS:
        raise SemanticAdmissionError("supporting contract permission matrix widened")
    evidence_root, evidence_root_identity = _safe_evidence_root(
        root, contract.get("evidence_root")
    )
    return {
        "plan": plan,
        "plan_path": plan_path,
        "pilot_contract": pilot,
        "pilot_contract_path": pilot_path,
        "pinned_path": pinned_path,
        "known_hosts_path": known_hosts_path,
        "execution_paths": execution_paths,
        "evidence_root": evidence_root,
        "evidence_root_identity": evidence_root_identity,
        "archive_locator": archive,
        "sidecar_locator": sidecar,
        "bundle_root_locator": bundle_root,
    }


def verify_s17_ext_001_semantics_v4(
    *,
    root: pathlib.Path,
    resolution: dict[str, Any],
    repository_documents: list[tuple[pathlib.Path, dict[str, Any]]],
    receipt_documents: list[dict[str, Any]],
    policy: dict[str, Any],
    policy_path: pathlib.Path,
    policy_sha256: str,
    policy_entry: dict[str, Any],
    graph_sha256: str,
    catalog_sha256: str,
    genesis_sha256: str,
    catalog: dict[str, Any],
    resolution_schema_sha256: str,
    **_: Any,
) -> dict[str, Any]:
    if receipt_documents:
        raise SemanticAdmissionError("S17-EXT-001 cannot use external receipts")
    envelopes = [
        (path, document)
        for path, document in repository_documents
        if document.get("schema_version")
        == "cpu-prefetch-stage17-operational-evidence-envelope/4"
    ]
    if len(envelopes) != 1 or len(repository_documents) != 1:
        raise SemanticAdmissionError("S17-EXT-001 requires exactly one v4 envelope")
    _, envelope = envelopes[0]
    _validate_schema(root, envelope, ENVELOPE_SCHEMA_PATH, "S17-EXT-001 v4 envelope")
    if envelope["semantic_policy"] != {
        "path": policy_path.relative_to(root).as_posix(),
        "size_bytes": policy_path.stat().st_size,
        "sha256": policy_sha256,
    }:
        raise SemanticAdmissionError("S17-EXT-001 policy binding mismatch")
    if envelope["semantic_verifier"] != {
        "verifier_id": policy_entry["verifier_id"],
        "verifier_version": policy_entry["verifier_version"],
    }:
        raise SemanticAdmissionError("S17-EXT-001 verifier identity mismatch")
    if envelope["predecessor"] != {
        "graph_sha256": graph_sha256,
        "catalog_sha256": catalog_sha256,
        "genesis_sha256": genesis_sha256,
        "resolution_schema_identity": "cpu-prefetch-stage17-external-input-resolution/1",
        "resolution_schema_sha256": resolution_schema_sha256,
        "semantic_policy_v3_sha256": policy["predecessor"]["policy_v3"]["sha256"],
        "adr_0107_sha256": policy["predecessor"]["adr_0107"]["sha256"],
        "adr_0108_sha256": policy["predecessor"]["adr_0108"]["sha256"],
    }:
        raise SemanticAdmissionError("S17-EXT-001 predecessor binding mismatch")
    expected_plan = {
        **policy["fixed_action_plan"],
        "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/2",
    }
    if envelope["fixed_action_plan"] != expected_plan:
        raise SemanticAdmissionError("S17-EXT-001 fixed plan binding drifted")
    if envelope["runtime_implementations"] != policy["implementations"]:
        raise SemanticAdmissionError("S17-EXT-001 runtime closure binding drifted")

    authorization_path = _binding(root, envelope["authorization"], "authorization")
    if envelope["authorization"].get("schema_identity") != "cpu-prefetch-stage17-read-only-preflight-authorization/4":
        raise SemanticAdmissionError("authorization schema identity mismatch")
    authorization = _load_json(authorization_path)
    _validate_schema(root, authorization, AUTHORIZATION_SCHEMA_PATH, "authorization v4")
    contract_path = _binding(root, envelope["supporting_contract"], "supporting contract")
    if envelope["supporting_contract"].get("schema_identity") != "cpu-prefetch-stage17-read-only-preflight-supporting-contract/4":
        raise SemanticAdmissionError("supporting-contract schema identity mismatch")
    contract = _load_json(contract_path)
    _validate_schema(root, contract, CONTRACT_SCHEMA_PATH, "supporting contract v4")
    if authorization["supporting_observation_contract"] != envelope["supporting_contract"]:
        raise SemanticAdmissionError("authorization does not bind supporting contract")
    if authorization["fixed_action_plan"] != expected_plan:
        raise SemanticAdmissionError("authorization does not bind action plan v2")

    verified = _verify_contract_action_inputs(root, contract, policy, catalog)
    target = contract["target"]
    if authorization["target"] != {
        "stand_id": target["stand_id"],
        "ssh_target": target["ssh_target"],
        "known_hosts_host": target["known_hosts_host"],
        "pinned_host_key_evidence_sha256": target["pinned_host_key_evidence"]["sha256"],
        "pinned_known_hosts_sha256": target["pinned_known_hosts"]["sha256"],
    }:
        raise SemanticAdmissionError("authorization target mismatch")
    expected_scope = (
        f"STAND_ID={target['stand_id']};SSH_TARGET={target['ssh_target']};"
        "SCOPE=READ_ONLY_PREFLIGHT;PLAN=STAGE17-READ-ONLY-PREFLIGHT-FIXED-ACTION-PLAN-v2"
    )
    if authorization["target_scope"] != expected_scope:
        raise SemanticAdmissionError("authorization target scope mismatch")
    if tuple(authorization["frozen_observation_ids"]) != OBSERVATION_IDS:
        raise SemanticAdmissionError("authorization observation family drifted")
    if authorization["evidence_root"] != contract["evidence_root"]:
        raise SemanticAdmissionError("authorization evidence root mismatch")
    if authorization["limits"] != LIMITS or authorization["permissions"] != PERMISSIONS:
        raise SemanticAdmissionError("authorization limits or permissions widened")
    if (
        authorization["role_collapse_acknowledged"] is not True
        or authorization["independent_review_claimed"] is not False
        or authorization["automatic_transition"] is not False
        or authorization["retry_allowed"] is not False
        or authorization["stage18_authority"] is not False
    ):
        raise SemanticAdmissionError("authorization governance boundary drifted")
    for field in ("authorization_id", "attempt_id", "actor"):
        if not isinstance(authorization.get(field), str) or not authorization[field].strip():
            raise SemanticAdmissionError(f"authorization {field} is missing")
    summary = resolution.get("authorization")
    if not isinstance(summary, dict):
        raise SemanticAdmissionError("resolution authorization summary is missing")
    for field in ("authorization_id", "issued_at_utc", "expires_at_utc", "authority_scope"):
        if summary.get(field) != authorization.get(field):
            raise SemanticAdmissionError(f"resolution authorization {field} mismatch")
    if summary.get("evidence_path") != authorization_path.relative_to(root).as_posix():
        raise SemanticAdmissionError("resolution authorization path mismatch")
    if authorization["actor"] != resolution.get("actor"):
        raise SemanticAdmissionError("authorization actor mismatch")
    issued = _parse_utc(authorization["issued_at_utc"], "authorization issue")
    expires = _parse_utc(authorization["expires_at_utc"], "authorization expiry")
    recorded = _parse_utc(resolution.get("recorded_at_utc"), "resolution time")
    if not issued <= recorded < expires:
        raise SemanticAdmissionError("authorization is not valid at resolution time")
    return {
        "authorization": authorization,
        "context": {
            "authorization_path": authorization_path,
            "authorization_sha256": _sha256(authorization_path),
            "contract_path": contract_path,
            "contract_sha256": _sha256(contract_path),
            "contract": contract,
            "policy": policy,
            "policy_path": policy_path,
            "policy_sha256": policy_sha256,
            **verified,
        },
    }


def _verify_loaded_runtime(
    *,
    policy: dict[str, Any],
    contract: dict[str, Any],
    runtime_identity_paths: dict[str, str] | None,
) -> dict[str, str]:
    if runtime_identity_paths is None or set(runtime_identity_paths) != set(
        policy["implementations"]
    ):
        raise SemanticAdmissionError("complete actual runtime identity context is required")
    actual: dict[str, pathlib.Path] = {}
    executor_parent: pathlib.Path | None = None
    hashes: dict[str, str] = {}
    for name, expected in policy["implementations"].items():
        path = _normalized_absolute(runtime_identity_paths[name], f"actual {name}")
        _nonsymlink_components(path, f"actual {name}")
        metadata = os.lstat(path)
        if not stat.S_ISREG(metadata.st_mode):
            raise SemanticAdmissionError(f"actual {name} is not a regular source file")
        if path.name != pathlib.PurePosixPath(expected["path"]).name:
            raise SemanticAdmissionError(f"actual {name} source path does not match policy role")
        digest = _sha256(path)
        if metadata.st_size != expected["size_bytes"] or digest != expected["sha256"]:
            raise SemanticAdmissionError(f"actual {name} bytes do not match policy binding")
        resolved = path.resolve()
        actual[name] = resolved
        hashes[name] = digest
        if name == "executor":
            executor_parent = resolved.parent
    if executor_parent is None or any(path.parent != executor_parent for path in actual.values()):
        raise SemanticAdmissionError("loaded runtime closure is not one exact tool directory")
    approved = {
        identity["role"]: pathlib.Path(identity["execution_path"]).resolve()
        for identity in contract["prospective_local_action_identities"]
    }
    if approved != {"EXECUTOR": actual["executor"], "COLLECTOR": actual["collector"]}:
        raise SemanticAdmissionError("approved and actually loaded executor/collector paths differ")
    return hashes


def reverify_action_inputs(
    root: pathlib.Path,
    context: dict[str, Any],
    runtime_identity_paths: dict[str, str] | None,
) -> dict[str, Any]:
    policy_path = context["policy_path"]
    if _sha256(policy_path) != context["policy_sha256"]:
        raise SemanticAdmissionError("action-time semantic policy drifted")
    contract_path = context["contract_path"]
    if _sha256(contract_path) != context["contract_sha256"]:
        raise SemanticAdmissionError("action-time supporting contract drifted")
    authorization_path = context["authorization_path"]
    if _sha256(authorization_path) != context["authorization_sha256"]:
        raise SemanticAdmissionError("action-time authorization drifted")
    policy = _load_json(policy_path)
    contract = _load_json(contract_path)
    for name, binding in policy["implementations"].items():
        _binding(root, binding, f"action-time {name}")
    _binding(root, policy["fixed_action_plan"], "action-time fixed plan")
    runtime_hashes = _verify_loaded_runtime(
        policy=policy,
        contract=contract,
        runtime_identity_paths=runtime_identity_paths,
    )
    for identity in contract["prospective_local_action_identities"]:
        _external_executable(
            identity["execution_path"], identity["source_binding"], f"action-time {identity['role']}"
        )
    target = contract["target"]
    _, known_hosts_path, _ = _verify_known_host(root, target)
    transport_identity = _external_regular_file(
        target["transport_identity_locator"], "action-time transport identity"
    )
    _openssh_literal_path(transport_identity, "action-time transport identity path")
    evidence_root, root_identity = _safe_evidence_root(root, contract["evidence_root"])
    if root_identity != context["evidence_root_identity"]:
        raise SemanticAdmissionError("evidence root identity changed")
    fixed_names = [ATTEMPT_NAME, FAILURE_NAME, COMPLETION_NAME]
    fixed_names.extend(
        f"s17-ro-{ordinal:03d}{suffix}"
        for ordinal in range(1, 7)
        for suffix in (".stdout.bin", ".stderr.bin", ".receipt-v1.json")
    )
    if any(os.path.lexists(evidence_root / name) for name in fixed_names):
        raise SemanticAdmissionError("one-shot marker or output already exists")
    pilot = context["pilot_contract"]
    return {
        "attempt_id": _load_json(authorization_path)["attempt_id"],
        "authorization_id": _load_json(authorization_path)["authorization_id"],
        "authorization_sha256": _sha256(authorization_path),
        "authorization": _load_json(authorization_path),
        "evidence_root": str(evidence_root),
        "evidence_root_identity": root_identity,
        "attempt_marker_name": ATTEMPT_NAME,
        "failure_name": FAILURE_NAME,
        "completion_name": COMPLETION_NAME,
        "ssh_target": target["ssh_target"],
        "known_hosts_path": str(known_hosts_path),
        "transport_identity_locator": str(transport_identity),
        "action_plan_sha256": policy["fixed_action_plan"]["sha256"],
        "runtime_implementation_hashes": runtime_hashes,
        "observation_ids": list(OBSERVATION_IDS),
        "fixed_ssh_argv_template": list(context["plan"]["transport"]["fixed_ssh_argv_template"]),
        "timeout_seconds": LIMITS["timeout_seconds_per_observation"],
        "max_output_bytes": LIMITS["max_output_bytes_per_observation"],
        "max_total_output_bytes": LIMITS["max_total_output_bytes"],
        "max_wall_seconds": LIMITS["max_wall_seconds"],
        "record_schema_paths": {
            "attempt": str(root / ATTEMPT_SCHEMA_PATH),
            "receipt": str(root / RECEIPT_SCHEMA_PATH),
            "failure": str(root / FAILURE_SCHEMA_PATH),
            "completion": str(root / COMPLETION_SCHEMA_PATH),
        },
        "collector_context": {
            "archive_locator": contract["pilot_candidate"]["archive_locator"],
            "sidecar_locator": contract["pilot_candidate"]["sidecar_locator"],
            "bundle_root_locator": contract["pilot_candidate"]["bundle_root_locator"],
            "capture_id": contract["capture"]["capture_id"],
            "captured_at_utc": contract["capture"]["captured_at_utc"],
            "archive_size_bytes": pilot["archive"]["size_bytes"],
            "archive_sha256": pilot["archive"]["sha256"],
            "sidecar_size_bytes": pilot["sidecar"]["size_bytes"],
            "sidecar_sha256": pilot["sidecar"]["sha256"],
            "manifest_sha256": pilot["release_identity"]["manifest_sha256"],
            "internal_file_count": pilot["release_identity"]["file_count"],
        },
    }


def evaluate_s17_ext_001_action_readiness(
    *,
    root: pathlib.Path,
    current_state: str,
    transition_documents: list[dict[str, Any]],
    transition_ids_and_hashes: list[tuple[str, str]],
    resolution_id: str,
    resolution_sha256: str,
    authorization: dict[str, Any],
    semantic_context: dict[str, Any],
    as_of_utc: str,
    runtime_identity_paths: dict[str, str] | None,
) -> dict[str, Any] | None:
    if current_state != "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT":
        return None
    if len(transition_documents) != 1 or len(transition_ids_and_hashes) != 1:
        return None
    transition = transition_documents[0]
    if (
        transition.get("sequence_number") != 1
        or transition.get("from_state") != "PREPARED"
        or transition.get("to_state") != "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT"
        or transition.get("authority_scope") != "READ_ONLY_PREFLIGHT_STATE_ADVANCE_ONLY"
        or transition.get("automatic_transition") is not False
        or transition.get("retry_allowed") is not False
        or transition.get("stage18_authority") is not False
    ):
        return None
    if transition.get("evidence_resolutions") != [{
        "input_id": "S17-EXT-001", "resolution_id": resolution_id, "sha256": resolution_sha256
    }]:
        return None
    if transition.get("authorizations") != [{
        "input_id": "S17-EXT-001",
        "resolution_id": resolution_id,
        "authorization_id": authorization.get("authorization_id"),
        "authority_scope": "READ_ONLY_PREFLIGHT",
    }]:
        return None
    evaluation = _parse_utc(as_of_utc, "action evaluation time")
    issued = _parse_utc(authorization.get("issued_at_utc"), "authorization issue")
    expires = _parse_utc(authorization.get("expires_at_utc"), "authorization expiry")
    if not issued <= evaluation < expires:
        return None
    try:
        action = reverify_action_inputs(root, semantic_context, runtime_identity_paths)
    except (SemanticAdmissionError, ValueError):
        return None
    transition_id, transition_sha256 = transition_ids_and_hashes[0]
    action.update({
        "resolution_id": resolution_id,
        "resolution_sha256": resolution_sha256,
        "transition_id": transition_id,
        "transition_sha256": transition_sha256,
    })
    return action
