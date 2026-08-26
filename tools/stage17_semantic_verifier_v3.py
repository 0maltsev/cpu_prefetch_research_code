#!/usr/bin/env python3
"""Production semantic verifier for Stage 17 S17-EXT-001 policy v3."""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import stat
from typing import Any

from jsonschema import Draft202012Validator


VERIFIER_ID = "STAGE17-S17-EXT-001-SEMANTIC-VERIFIER"
VERIFIER_VERSION = "3"
POLICY_V2_PATH = "config/stage17/stage17-operational-evidence-admission-policy-v2.json"
ADR_0106_PATH = "docs/decisions/0106-stage17-default-deny-semantic-evidence-admission.md"
ACTION_PLAN_PATH = "config/stage17/stage17-read-only-preflight-fixed-action-plan-v1.json"
EXECUTOR_PATH = "tools/stage17_read_only_preflight_executor_v1.py"
COLLECTOR_PATH = "tools/stage17_read_only_preflight_collector_v1.py"
AUTHORIZATION_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-authorization-v3.schema.json"
CONTRACT_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-supporting-contract-v3.schema.json"
ENVELOPE_SCHEMA_PATH = "config/schemas/stage17-operational-evidence-envelope-v3.schema.json"
PLAN_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-fixed-action-plan-v1.schema.json"
ATTEMPT_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-attempt-v1.schema.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-operational-evidence-admission-policy-v3.schema.json"
V3_SCHEMA_PATHS = (
    POLICY_SCHEMA_PATH,
    ENVELOPE_SCHEMA_PATH,
    AUTHORIZATION_SCHEMA_PATH,
    CONTRACT_SCHEMA_PATH,
    PLAN_SCHEMA_PATH,
    ATTEMPT_SCHEMA_PATH,
)
OBSERVATION_IDS = (
    "S17-RO-PREFLIGHT-001-TARGET-AND-TRANSPORT-IDENTITY",
    "S17-RO-PREFLIGHT-002-ARCHIVE-AND-SIDECAR-BYTE-VERIFICATION",
    "S17-RO-PREFLIGHT-003-BUNDLE-INTERNAL-VERIFICATION",
    "S17-RO-PREFLIGHT-004-NONPRIVILEGED-SELF-TESTS",
    "S17-RO-PREFLIGHT-005-RUNTIME-TOOL-IDENTITIES",
    "S17-RO-PREFLIGHT-006-READ-ONLY-PLATFORM-INVENTORY",
)
PERMISSIONS = {
    "stand_read_only": True,
    "stand_mutation": False,
    "privileged_controls": False,
    "qualification": False,
    "calibration": False,
    "pilot_execution": False,
    "measurement": False,
    "stage18_authority": False,
}
LIMITS = {
    "max_commands": 6,
    "max_wall_seconds": 180,
    "max_total_output_bytes": 6291456,
    "max_output_bytes_per_observation": 1048576,
    "timeout_seconds_per_observation": 30,
    "attempts_per_observation": 1,
    "retries": 0,
}
REMOTE_COMMAND = "/usr/bin/env -i LANG=C LC_ALL=C TZ=UTC0 /usr/bin/python3 -I -S -"
SAFE_SSH_TARGET = re.compile(r"^[A-Za-z0-9_.-]+@[A-Za-z0-9_.:-]+$")
SAFE_HOST = re.compile(r"^[A-Za-z0-9_.:-]+$")


class SemanticAdmissionError(ValueError):
    """Typed evidence does not prove the registered Stage 17 requirement."""


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise SemanticAdmissionError(f"JSON root is not an object: {path}")
    return document


def _repository_file(root: pathlib.Path, value: object) -> pathlib.Path:
    if not isinstance(value, str):
        raise SemanticAdmissionError("repository binding path is missing")
    relative = pathlib.PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise SemanticAdmissionError(f"unsafe repository binding path: {value}")
    current = root
    for part in relative.parts:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exception:
            raise SemanticAdmissionError(f"repository binding is absent: {value}") from exception
        if stat.S_ISLNK(metadata.st_mode):
            raise SemanticAdmissionError(f"repository binding contains symlink: {value}")
    if not stat.S_ISREG(os.lstat(current).st_mode):
        raise SemanticAdmissionError(f"repository binding is not a regular file: {value}")
    return current


def _validate_schema(
    root: pathlib.Path, document: dict[str, Any], schema_relative: str, label: str
) -> None:
    schema = _load_json(_repository_file(root, schema_relative))
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(document))
    if errors:
        first = errors[0]
        location = "/".join(str(item) for item in first.absolute_path)
        raise SemanticAdmissionError(f"{label} schema error at $/{location}: {first.message}")


def _binding(root: pathlib.Path, value: object, label: str) -> pathlib.Path:
    if not isinstance(value, dict):
        raise SemanticAdmissionError(f"{label} binding is missing")
    path = _repository_file(root, value.get("path"))
    if path.stat().st_size != value.get("size_bytes"):
        raise SemanticAdmissionError(f"{label} byte-count mismatch")
    if _sha256(path) != value.get("sha256"):
        raise SemanticAdmissionError(f"{label} SHA-256 mismatch")
    return path


def _binding_for(root: pathlib.Path, relative: str) -> dict[str, Any]:
    path = _repository_file(root, relative)
    return {"path": relative, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _parse_utc(value: object, label: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise SemanticAdmissionError(f"{label} is not explicit UTC")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exception:
        raise SemanticAdmissionError(f"{label} is invalid") from exception
    if parsed.tzinfo != dt.timezone.utc:
        raise SemanticAdmissionError(f"{label} is not UTC")
    return parsed


def _normalized_absolute(value: object, label: str) -> pathlib.Path:
    if not isinstance(value, str) or not value.startswith("/"):
        raise SemanticAdmissionError(f"{label} is not absolute")
    pure = pathlib.PurePosixPath(value)
    if str(pure) != value or ".." in pure.parts or "\x00" in value or "\n" in value:
        raise SemanticAdmissionError(f"{label} is not normalized")
    return pathlib.Path(value)


def _nonsymlink_components(path: pathlib.Path, label: str) -> None:
    current = pathlib.Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exception:
            raise SemanticAdmissionError(f"{label} is absent: {path}") from exception
        if stat.S_ISLNK(metadata.st_mode):
            raise SemanticAdmissionError(f"{label} contains symlink: {path}")


def _external_executable(path_value: object, expected: dict[str, Any], label: str) -> pathlib.Path:
    path = _normalized_absolute(path_value, label)
    _nonsymlink_components(path, label)
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o111 == 0:
        raise SemanticAdmissionError(f"{label} is not an executable regular file")
    if path.stat().st_size != expected["size_bytes"] or _sha256(path) != expected["sha256"]:
        raise SemanticAdmissionError(f"{label} bytes do not match repository implementation")
    return path


def _external_regular_file(path_value: object, label: str) -> pathlib.Path:
    path = _normalized_absolute(path_value, label)
    _nonsymlink_components(path, label)
    if not stat.S_ISREG(os.lstat(path).st_mode):
        raise SemanticAdmissionError(f"{label} is not a regular file")
    return path


def _safe_evidence_root(root: pathlib.Path, value: object) -> pathlib.Path:
    path = _normalized_absolute(value, "evidence root")
    _nonsymlink_components(path, "evidence root")
    if not stat.S_ISDIR(os.lstat(path).st_mode):
        raise SemanticAdmissionError("evidence root is not a directory")
    resolved = path.resolve()
    repository = root.resolve()
    forbidden = (pathlib.Path("/etc"), pathlib.Path("/proc"), pathlib.Path("/sys"))
    if resolved == repository or repository in resolved.parents:
        raise SemanticAdmissionError("evidence root is inside the repository")
    if resolved == pathlib.Path("/") or any(
        resolved == item or item in resolved.parents for item in forbidden
    ):
        raise SemanticAdmissionError("evidence root is a forbidden system path")
    return path


def _read_ssh_string(blob: bytes, offset: int, label: str) -> tuple[bytes, int]:
    if len(blob) - offset < 4:
        raise SemanticAdmissionError(f"OpenSSH Ed25519 blob truncates {label} length")
    size = int.from_bytes(blob[offset : offset + 4], "big")
    offset += 4
    end = offset + size
    if end > len(blob):
        raise SemanticAdmissionError(f"OpenSSH Ed25519 blob truncates {label}")
    return blob[offset:end], end


def validate_ed25519_wire_blob(encoded: object) -> tuple[bytes, str]:
    if not isinstance(encoded, str):
        raise SemanticAdmissionError("pinned host key is not base64")
    try:
        blob = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exception:
        raise SemanticAdmissionError("pinned host key is malformed base64") from exception
    key_type, offset = _read_ssh_string(blob, 0, "key type")
    key, offset = _read_ssh_string(blob, offset, "public key")
    if key_type != b"ssh-ed25519":
        raise SemanticAdmissionError("pinned host key wire type is not ssh-ed25519")
    if len(key) != 32:
        raise SemanticAdmissionError("pinned Ed25519 public key is not 32 bytes")
    if offset != len(blob):
        raise SemanticAdmissionError("pinned Ed25519 public key has trailing bytes")
    fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode(
        "ascii"
    ).rstrip("=")
    return blob, fingerprint


def verify_policy_v3(
    *,
    root: pathlib.Path,
    policy: dict[str, Any],
    graph_sha256: str,
    catalog_sha256: str,
    genesis_file_sha256: str,
    genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v3")
    predecessor = policy["predecessor"]
    expected_predecessor = {
        "policy_v2": _binding_for(root, POLICY_V2_PATH),
        "adr_0106": _binding_for(root, ADR_0106_PATH),
        "graph_sha256": graph_sha256,
        "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if predecessor != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v3 predecessor binding drifted")
    expected_schemas = [_binding_for(root, item) for item in V3_SCHEMA_PATHS]
    if policy.get("schema_bindings") != expected_schemas:
        raise SemanticAdmissionError("semantic policy v3 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v3 fixed action plan drifted")
    expected_implementations = {
        "semantic_verifier": _binding_for(root, "tools/stage17_semantic_verifier_v3.py"),
        "executor": _binding_for(root, EXECUTOR_PATH),
        "collector": _binding_for(root, COLLECTOR_PATH),
    }
    if policy.get("implementations") != expected_implementations:
        raise SemanticAdmissionError("semantic policy v3 implementation binding drifted")
    expected_ids = [f"S17-EXT-{index:03d}" for index in range(1, 11)]
    if [entry.get("input_id") for entry in policy.get("entries", [])] != expected_ids:
        raise SemanticAdmissionError("semantic policy v3 registry drifted")
    if policy["entries"][0] != {
        "input_id": "S17-EXT-001",
        "status": "IMPLEMENTED",
        "verifier_id": VERIFIER_ID,
        "verifier_version": VERIFIER_VERSION,
    }:
        raise SemanticAdmissionError("S17-EXT-001 policy registration drifted")
    for entry in policy["entries"][1:5] + policy["entries"][6:]:
        if entry.get("status") != "SEMANTIC_VERIFIER_NOT_IMPLEMENTED_FAIL_CLOSED":
            raise SemanticAdmissionError("unimplemented Stage 17 verifier became fail-open")


def _verify_action_plan(root: pathlib.Path, policy: dict[str, Any]) -> tuple[dict[str, Any], pathlib.Path]:
    plan_path = _binding(root, policy["fixed_action_plan"], "fixed action plan")
    plan = _load_json(plan_path)
    _validate_schema(root, plan, PLAN_SCHEMA_PATH, "fixed action plan")
    if plan.get("owner_command_bytes_allowed") is not False:
        raise SemanticAdmissionError("fixed action plan accepts owner command bytes")
    transport = plan.get("transport", {})
    if (
        transport.get("local_shell") is not False
        or transport.get("ssh_executable") != "/usr/bin/ssh"
        or transport.get("remote_command") != REMOTE_COMMAND
        or transport.get("attempts_per_observation") != 1
        or transport.get("retries") != 0
        or transport.get("stop_on_first_failure") is not True
    ):
        raise SemanticAdmissionError("fixed transport semantics drifted")
    observations = plan.get("observations", [])
    if tuple(item.get("observation_id") for item in observations) != OBSERVATION_IDS:
        raise SemanticAdmissionError("fixed observation action plan drifted")
    forbidden = plan.get("forbidden_semantics", {})
    if set(forbidden.values()) != {True} or plan.get("authority_boundary") != PERMISSIONS:
        raise SemanticAdmissionError("fixed action plan widened authority")
    executable_text = "\n".join(
        [transport["remote_command"], *transport.get("remote_argv", [])]
    )
    for token in ("/usr/bin/touch", "sudo", "|", "$(", ">", "<", ";"):
        if token in executable_text:
            raise SemanticAdmissionError("fixed action plan contains forbidden command semantics")
    return plan, plan_path


def _verify_known_host(
    root: pathlib.Path, target: dict[str, Any]
) -> tuple[pathlib.Path, pathlib.Path, bytes]:
    pinned_path = _binding(root, target["pinned_host_key_evidence"], "pinned host-key evidence")
    pinned = _load_json(pinned_path)
    _validate_schema(
        root,
        pinned,
        "config/schemas/stage17-pinned-host-key-evidence-v1.schema.json",
        "pinned host-key evidence",
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
    known_hosts_path = _binding(root, target["pinned_known_hosts"], "pinned known-hosts file")
    expected_line = (
        f"{target['known_hosts_host']} ssh-ed25519 "
        f"{base64.b64encode(blob).decode('ascii')}\n"
    ).encode("ascii")
    if known_hosts_path.read_bytes() != expected_line:
        raise SemanticAdmissionError("pinned known-hosts bytes do not match Ed25519 evidence")
    return pinned_path, known_hosts_path, blob


def _verify_contract_action_inputs(
    root: pathlib.Path,
    contract: dict[str, Any],
    policy: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    plan, plan_path = _verify_action_plan(root, policy)
    if contract.get("fixed_action_plan") != {
        **policy["fixed_action_plan"],
        "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/1",
    }:
        raise SemanticAdmissionError("supporting contract does not bind the fixed action plan")
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
    _external_regular_file(
        target.get("transport_identity_locator"), "transport identity locator"
    )

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
    archive = _normalized_absolute(contract["pilot_candidate"]["archive_locator"], "archive locator")
    sidecar = _normalized_absolute(contract["pilot_candidate"]["sidecar_locator"], "sidecar locator")
    bundle_root = _normalized_absolute(contract["pilot_candidate"]["bundle_root_locator"], "bundle root locator")
    if len({archive, sidecar, bundle_root}) != 3:
        raise SemanticAdmissionError("pilot candidate locators are not distinct")

    identities = contract["prospective_local_action_identities"]
    expected_identity = (
        ("STAGE17_READ_ONLY_PREFLIGHT_EXECUTOR", "EXECUTOR", "executor"),
        ("STAGE17_READ_ONLY_PREFLIGHT_COLLECTOR", "COLLECTOR", "collector"),
    )
    execution_paths: dict[str, pathlib.Path] = {}
    for identity, (identity_id, role, implementation_name) in zip(
        identities, expected_identity, strict=True
    ):
        if (identity.get("identity_id"), identity.get("role")) != (identity_id, role):
            raise SemanticAdmissionError("prospective action identity family drifted")
        expected_source = policy["implementations"][implementation_name]
        if identity.get("source_binding") != expected_source:
            raise SemanticAdmissionError("prospective action source binding drifted")
        _binding(root, expected_source, f"{role} source")
        execution_paths[role] = _external_executable(
            identity.get("execution_path"), expected_source, f"{role} execution path"
        )
    if contract.get("remote_runtime_identity_policy") != {
        "source_input_id": "S17-EXT-002",
        "identity_classes": ["REMOTE_EXECUTABLE", "REMOTE_MODULE", "REMOTE_DEPENDENCY"],
        "prospective_values_present": False,
    }:
        raise SemanticAdmissionError("remote runtime identities were fabricated prospectively")
    if contract.get("limits") != LIMITS:
        raise SemanticAdmissionError("fixed limits drifted")
    if contract.get("stop_policy") != "STOP_ON_FIRST_MISMATCH_NONZERO_EXIT_TIMEOUT_OR_OUTPUT_LIMIT":
        raise SemanticAdmissionError("stop-first policy drifted")
    if contract.get("retention_policy") != "CREATE_EXCLUSIVE_APPEND_ONLY_RETAIN_SUCCESS_FAILURE_AND_PARTIAL_NO_DELETE":
        raise SemanticAdmissionError("partial-retention policy drifted")
    if contract.get("authority_boundary") != PERMISSIONS:
        raise SemanticAdmissionError("supporting contract permission matrix widened")
    evidence_root = _safe_evidence_root(root, contract.get("evidence_root"))
    return {
        "plan": plan,
        "plan_path": plan_path,
        "pilot_contract": pilot,
        "pilot_contract_path": pilot_path,
        "pinned_path": pinned_path,
        "known_hosts_path": known_hosts_path,
        "execution_paths": execution_paths,
        "evidence_root": evidence_root,
        "archive_locator": archive,
        "sidecar_locator": sidecar,
        "bundle_root_locator": bundle_root,
    }


def verify_s17_ext_001_semantics_v3(
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
        if document.get("schema_version") == "cpu-prefetch-stage17-operational-evidence-envelope/3"
    ]
    if len(envelopes) != 1 or len(repository_documents) != 1:
        raise SemanticAdmissionError("S17-EXT-001 requires exactly one v3 semantic envelope")
    _, envelope = envelopes[0]
    _validate_schema(root, envelope, ENVELOPE_SCHEMA_PATH, "S17-EXT-001 envelope")
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
    predecessor = envelope["predecessor"]
    if predecessor != {
        "graph_sha256": graph_sha256,
        "catalog_sha256": catalog_sha256,
        "genesis_sha256": genesis_sha256,
        "resolution_schema_identity": "cpu-prefetch-stage17-external-input-resolution/1",
        "resolution_schema_sha256": resolution_schema_sha256,
        "semantic_policy_v2_sha256": policy["predecessor"]["policy_v2"]["sha256"],
        "adr_0106_sha256": policy["predecessor"]["adr_0106"]["sha256"],
    }:
        raise SemanticAdmissionError("S17-EXT-001 predecessor binding mismatch")
    expected_envelope_bindings = {
        "fixed_action_plan": {
            **policy["fixed_action_plan"],
            "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/1",
        },
        "executor_implementation": policy["implementations"]["executor"],
        "collector_implementation": policy["implementations"]["collector"],
    }
    for field, expected in expected_envelope_bindings.items():
        if envelope[field] != expected:
            raise SemanticAdmissionError(f"S17-EXT-001 {field} binding drifted")
        _binding(root, expected, f"S17-EXT-001 {field}")

    authorization_path = _binding(root, envelope["authorization"], "S17-EXT-001 authorization")
    if envelope["authorization"].get("schema_identity") != "cpu-prefetch-stage17-read-only-preflight-authorization/3":
        raise SemanticAdmissionError("S17-EXT-001 authorization schema identity mismatch")
    authorization = _load_json(authorization_path)
    _validate_schema(root, authorization, AUTHORIZATION_SCHEMA_PATH, "S17-EXT-001 authorization")
    contract_path = _binding(root, envelope["supporting_contract"], "S17-EXT-001 contract")
    if envelope["supporting_contract"].get("schema_identity") != "cpu-prefetch-stage17-read-only-preflight-supporting-contract/3":
        raise SemanticAdmissionError("S17-EXT-001 contract schema identity mismatch")
    contract = _load_json(contract_path)
    _validate_schema(root, contract, CONTRACT_SCHEMA_PATH, "S17-EXT-001 contract")
    if authorization["supporting_observation_contract"] != envelope["supporting_contract"]:
        raise SemanticAdmissionError("authorization does not byte/hash-bind supporting contract")
    if authorization["fixed_action_plan"] != envelope["fixed_action_plan"]:
        raise SemanticAdmissionError("authorization does not bind fixed action plan")

    verified = _verify_contract_action_inputs(root, contract, policy, catalog)
    target = contract["target"]
    expected_target = {
        "stand_id": target["stand_id"],
        "ssh_target": target["ssh_target"],
        "known_hosts_host": target["known_hosts_host"],
        "pinned_host_key_evidence_sha256": target["pinned_host_key_evidence"]["sha256"],
        "pinned_known_hosts_sha256": target["pinned_known_hosts"]["sha256"],
    }
    if authorization["target"] != expected_target:
        raise SemanticAdmissionError("authorization target mismatch")
    expected_scope = (
        f"STAND_ID={target['stand_id']};SSH_TARGET={target['ssh_target']};"
        "SCOPE=READ_ONLY_PREFLIGHT;PLAN=STAGE17-READ-ONLY-PREFLIGHT-FIXED-ACTION-PLAN-v1"
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


def reverify_action_inputs(root: pathlib.Path, context: dict[str, Any]) -> dict[str, Any]:
    """Re-read every prospective byte/path immediately before action readiness."""

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
        _binding(root, binding, f"action-time {name} implementation")
    _binding(root, policy["fixed_action_plan"], "action-time fixed action plan")
    for identity in contract["prospective_local_action_identities"]:
        role = identity["role"]
        _external_executable(identity["execution_path"], identity["source_binding"], f"action-time {role}")
    target = contract["target"]
    _, known_hosts_path, _ = _verify_known_host(root, target)
    _external_regular_file(
        target["transport_identity_locator"], "action-time transport identity locator"
    )
    evidence_root = _safe_evidence_root(root, contract["evidence_root"])
    marker_path = evidence_root / "stage17-read-only-preflight-attempt-v1.json"
    if os.path.lexists(marker_path):
        raise SemanticAdmissionError("one-shot preflight attempt has already begun")
    forbidden_existing = [
        evidence_root / "stage17-read-only-preflight-failure-v1.json",
        *[
            evidence_root / f"s17-ro-{index:03d}{suffix}"
            for index in range(1, 7)
            for suffix in (".stdout.bin", ".stderr.bin", ".receipt.json")
        ],
    ]
    if any(os.path.lexists(path) for path in forbidden_existing):
        raise SemanticAdmissionError("preflight output already exists without attempt marker")
    pilot = context["pilot_contract"]
    return {
        "attempt_id": _load_json(authorization_path)["attempt_id"],
        "authorization_id": _load_json(authorization_path)["authorization_id"],
        "authorization_sha256": _sha256(authorization_path),
        "evidence_root": str(evidence_root),
        "attempt_marker_path": str(marker_path),
        "ssh_target": target["ssh_target"],
        "known_hosts_path": str(known_hosts_path),
        "transport_identity_locator": target["transport_identity_locator"],
        "action_plan_sha256": policy["fixed_action_plan"]["sha256"],
        "observation_ids": list(OBSERVATION_IDS),
        "timeout_seconds": LIMITS["timeout_seconds_per_observation"],
        "max_output_bytes": LIMITS["max_output_bytes_per_observation"],
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
) -> dict[str, Any] | None:
    """Apply the policy-bound exact transition and one-shot action gate."""

    if current_state != "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT":
        return None
    if len(transition_documents) != 1 or len(transition_ids_and_hashes) != 1:
        return None
    transition = transition_documents[0]
    if (
        transition.get("sequence_number") != 1
        or transition.get("from_state") != "PREPARED"
        or transition.get("to_state") != "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT"
        or transition.get("authority_scope")
        != "READ_ONLY_PREFLIGHT_STATE_ADVANCE_ONLY"
        or transition.get("automatic_transition") is not False
        or transition.get("retry_allowed") is not False
        or transition.get("stage18_authority") is not False
    ):
        return None
    expected_resolution = {
        "input_id": "S17-EXT-001",
        "resolution_id": resolution_id,
        "sha256": resolution_sha256,
    }
    if transition.get("evidence_resolutions") != [expected_resolution]:
        return None
    expected_authorization = {
        "input_id": "S17-EXT-001",
        "resolution_id": resolution_id,
        "authorization_id": authorization.get("authorization_id"),
        "authority_scope": "READ_ONLY_PREFLIGHT",
    }
    if transition.get("authorizations") != [expected_authorization]:
        return None
    evaluation = _parse_utc(as_of_utc, "action evaluation time")
    issued = _parse_utc(authorization.get("issued_at_utc"), "authorization issue")
    expires = _parse_utc(authorization.get("expires_at_utc"), "authorization expiry")
    if not issued <= evaluation < expires:
        return None
    try:
        context = reverify_action_inputs(root, semantic_context)
    except SemanticAdmissionError:
        return None
    transition_id, transition_sha256 = transition_ids_and_hashes[0]
    context.update(
        {
            "resolution_id": resolution_id,
            "resolution_sha256": resolution_sha256,
            "transition_id": transition_id,
            "transition_sha256": transition_sha256,
        }
    )
    return context
