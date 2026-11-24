#!/usr/bin/env python3
"""Fail-closed Stage 17 operational authoring/admission CLI.

Repository definitions are immutable inputs.  Mutable operational records live
under a separate create-exclusive owner evidence root.  This tool never makes
up owner facts and never signs: it renders canonical unsigned bytes, verifies
detached signatures through the production admission path, and appends only a
fully validated journal successor.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import pathlib
import stat
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

import stage17_output_registry_v3 as output_registry
import stage17_phase_controller_v3 as controller
import stage17_operational_semantics_v3 as semantics
import stage17_pilot_candidate_artifact_v3 as pilot_artifact
import stage17_state_journal as base
import stage17_state_journal_v9 as journal_runtime


class OperationalCliError(RuntimeError):
    pass


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def parse_utc(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except (TypeError, ValueError) as exception:
        raise OperationalCliError("timestamp must be exact UTC") from exception
    if not value.endswith("Z") or parsed.tzinfo is None:
        raise OperationalCliError("timestamp must be exact UTC")
    return parsed


def load_json(path: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 64 * 1024 * 1024:
            raise OperationalCliError(f"not a bounded regular file: {path}")
        payload = os.pread(descriptor, metadata.st_size + 1, 0)
    finally:
        os.close(descriptor)
    if len(payload) != metadata.st_size:
        raise OperationalCliError(f"file changed during pinned read: {path}")
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exception:
        raise OperationalCliError(f"invalid JSON: {path}") from exception
    if not isinstance(document, dict):
        raise OperationalCliError(f"JSON root is not an object: {path}")
    return document, payload


def binding(path: pathlib.Path) -> dict[str, Any]:
    if path.suffix == ".json":
        _, payload = load_json(path)
    else:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 64 * 1024 * 1024:
                raise OperationalCliError(f"not a bounded regular file: {path}")
            payload = os.pread(descriptor, metadata.st_size + 1, 0)
        finally:
            os.close(descriptor)
        if len(payload) != metadata.st_size:
            raise OperationalCliError(f"file changed during pinned read: {path}")
    return {"path": str(path), "size_bytes": len(payload), "sha256": digest(payload)}


def streaming_binding(path: pathlib.Path) -> dict[str, Any]:
    """Bind arbitrary-size immutable artifact bytes through one no-follow fd."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise OperationalCliError(f"not a regular file: {path}")
        hasher = hashlib.sha256()
        offset = 0
        while offset < metadata.st_size:
            chunk = os.pread(descriptor, min(1024 * 1024,
                                             metadata.st_size - offset), offset)
            if not chunk:
                raise OperationalCliError(f"file changed during pinned read: {path}")
            hasher.update(chunk)
            offset += len(chunk)
        current = os.fstat(descriptor)
        if ((current.st_dev, current.st_ino, current.st_size,
             current.st_mtime_ns, current.st_ctime_ns) !=
                (metadata.st_dev, metadata.st_ino, metadata.st_size,
                 metadata.st_mtime_ns, metadata.st_ctime_ns)):
            raise OperationalCliError(f"file changed during pinned read: {path}")
    finally:
        os.close(descriptor)
    return {"path": str(path), "size_bytes": metadata.st_size,
            "sha256": hasher.hexdigest()}


def validate_schema(root: pathlib.Path, relative: str,
                    document: dict[str, Any]) -> None:
    schema, _ = load_json(root / relative)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(
        schema, format_checker=FormatChecker()
    ).iter_errors(document))
    if errors:
        raise OperationalCliError(
            f"{relative} rejection: {errors[0].message}"
        )


def _root_fd(path: pathlib.Path) -> int:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                         os.O_CLOEXEC)
    metadata = os.fstat(descriptor)
    if (metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o700):
        os.close(descriptor)
        raise OperationalCliError("operational evidence root must be owner mode 0700")
    return descriptor


def _mkdir_at(parent: int, name: str) -> None:
    try:
        os.mkdir(name, 0o700, dir_fd=parent)
    except FileExistsError:
        descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                             os.O_CLOEXEC, dir_fd=parent)
        try:
            metadata = os.fstat(descriptor)
            if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
                raise OperationalCliError(f"unsafe operational directory: {name}")
        finally:
            os.close(descriptor)


def _write_exclusive_at(parent: int, name: str, payload: bytes,
                        mode: int = 0o600) -> None:
    descriptor = os.open(
        name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW |
        os.O_CLOEXEC, mode, dir_fd=parent,
    )
    try:
        view = memoryview(payload)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise OperationalCliError("create-exclusive write stalled")
            view = view[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(parent)


def _subdir(root_fd: int, name: str) -> int:
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                   os.O_CLOEXEC, dir_fd=root_fd)


def latest_journal(evidence_root: pathlib.Path) -> pathlib.Path:
    candidates = sorted((evidence_root / "journal").glob(
        "stage17-state-journal-[0-9][0-9][0-9][0-9][0-9][0-9].json"
    ))
    if not candidates:
        raise OperationalCliError("operational journal has not been initialized")
    return candidates[-1]


def initialize(repository_root: pathlib.Path, evidence_root: pathlib.Path) -> pathlib.Path:
    root_fd = _root_fd(evidence_root)
    try:
        for name in ("journal", "records", "receipts", "actions", "manifests"):
            _mkdir_at(root_fd, name)
        journal_fd = _subdir(root_fd, "journal")
        try:
            genesis = (repository_root /
                "config/stage17/journal/stage17-state-journal-000000.json").read_bytes()
            _write_exclusive_at(
                journal_fd, "stage17-state-journal-000000.json", genesis
            )
        finally:
            os.close(journal_fd)
    finally:
        os.close(root_fd)
    return evidence_root / "journal/stage17-state-journal-000000.json"


def validate_journal(*, repository_root: pathlib.Path,
                     evidence_root: pathlib.Path,
                     pilot_archive: pathlib.Path | None,
                     pilot_sidecar: pathlib.Path | None,
                     as_of_utc: str | None = None,
                     allow_synthetic: bool = False) \
        -> journal_runtime.OperationalJournalValidation:
    latest = latest_journal(evidence_root)
    return journal_runtime.validate_operational_journal(
        repository_root=repository_root, evidence_root=evidence_root,
        latest_journal=latest, journal_directory=evidence_root / "journal",
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        as_of_utc=as_of_utc,
        allow_synthetic_test_evidence=allow_synthetic,
    )


def _root_binding(path: pathlib.Path) -> dict[str, Any]:
    descriptor = _root_fd(path)
    try:
        metadata = os.fstat(descriptor)
        return {
            "absolute_path": str(path.resolve()), "device": metadata.st_dev,
            "inode": metadata.st_ino, "owner_uid": metadata.st_uid,
            "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
        }
    finally:
        os.close(descriptor)


def _resolution_binding(item: Any) -> dict[str, str]:
    return {"input_id": item.input_id, "resolution_id": item.resolution_id,
            "sha256": item.sha256}


def author_request(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    action: str, action_inputs_path: pathlib.Path, request_id: str,
    authorization_id: str, attempt_id: str, output_root: pathlib.Path,
    destination: pathlib.Path, pilot_archive: pathlib.Path | None,
    pilot_sidecar: pathlib.Path | None, synthetic: bool = False,
) -> pathlib.Path:
    validation = validate_journal(
        repository_root=repository_root, evidence_root=evidence_root,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        allow_synthetic=synthetic,
    )
    registry = output_registry.pin_registry(repository_root)
    definition = registry.action(action)
    if validation.current_state != definition["required_state"]:
        raise OperationalCliError("action state gate is not satisfied")
    required = tuple(definition["required_resolution_ids"])
    if any(item not in validation.resolutions for item in required):
        raise OperationalCliError("action predecessor resolution is absent")
    runtime, release = controller._runtime_from_context(action, validation)
    worker_path = runtime.pop("path")
    del worker_path
    action_inputs, _ = load_json(action_inputs_path)
    document = {
        "schema_version": "cpu-prefetch-stage17-fixed-action-request/3",
        "request_id": request_id, "action_id": action,
        "stand_id": validation.resolutions[
            "S17-EXT-002"
        ].semantic_context["stand_id"],
        "authorization_id": authorization_id, "attempt_id": attempt_id,
        "runtime_binding": runtime, "release_binding": release,
        "evidence_root_binding": _root_binding(output_root),
        "predecessor_resolutions": [
            _resolution_binding(validation.resolutions[item]) for item in required
        ],
        "action_inputs": action_inputs,
        "synthetic_test_only": synthetic, "phase18_authority": False,
    }
    validate_schema(
        repository_root,
        "config/schemas/stage17-fixed-action-request-v3.schema.json", document,
    )
    controller._validate_action_inputs(
        action=action, request=document, validation=validation,
        synthetic_test_only=synthetic,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    parent = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY |
                     os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        _write_exclusive_at(parent, destination.name, canonical(document))
    finally:
        os.close(parent)
    return destination


def author_authorization(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    request_path: pathlib.Path, actor: str, reviewer: str,
    issued_at_utc: str, expires_at_utc: str, destination: pathlib.Path,
    pilot_archive: pathlib.Path | None, pilot_sidecar: pathlib.Path | None,
) -> pathlib.Path:
    issued, expires = parse_utc(issued_at_utc), parse_utc(expires_at_utc)
    if not issued < expires or expires - issued > dt.timedelta(seconds=1800):
        raise OperationalCliError("authorization window must be positive and <=1800s")
    request, request_payload = load_json(request_path)
    validation = validate_journal(
        repository_root=repository_root, evidence_root=evidence_root,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
    )
    registry = output_registry.pin_registry(repository_root)
    definition = registry.action(request["action_id"])
    ext2, ext3 = validation.resolutions["S17-EXT-002"], validation.resolutions[
        "S17-EXT-003"
    ]
    trust = ext3.semantic_context["trust"]["measurements"]
    if actor != trust["principal"] or reviewer != trust["reviewer_role"]:
        raise OperationalCliError("actor/reviewer differ from admitted trust")
    document = {
        "schema_version": "cpu-prefetch-stage17-phase-action-authorization/3",
        "authorization_id": request["authorization_id"],
        "action_id": request["action_id"], "actor": actor,
        "reviewer": reviewer, "target": {"stand_id": request["stand_id"]},
        "issued_at_utc": issued_at_utc, "expires_at_utc": expires_at_utc,
        "trust_context": {
            "ext002_resolution": _resolution_binding(ext2),
            "ext003_resolution": _resolution_binding(ext3),
        },
        "predecessor_resolutions": request["predecessor_resolutions"],
        "fixed_action_definition_sha256": registry.plan_sha256,
        "request_binding": {
            "path": str(request_path), "size_bytes": len(request_payload),
            "sha256": digest(request_payload),
        },
        "evidence_root_binding": request["evidence_root_binding"],
        "permission_matrix": definition["permission_matrix"],
        "max_wall_seconds": 180, "one_attempt": True,
        "retry_allowed": False, "stop_first": True,
        "retain_partial": True, "stage18_authority": False,
    }
    validate_schema(
        repository_root,
        "config/schemas/stage17-phase-action-authorization-v3.schema.json",
        document,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    parent = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY |
                     os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        _write_exclusive_at(parent, destination.name, canonical(document))
    finally:
        os.close(parent)
    return destination


def verify_phase_signature(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    authorization: pathlib.Path, signature: pathlib.Path,
    pilot_archive: pathlib.Path | None, pilot_sidecar: pathlib.Path | None,
) -> None:
    prepared = controller.prepare_action(
        repository_root=repository_root,
        journal=latest_journal(evidence_root),
        journal_directory=evidence_root / "journal",
        operational_evidence_root=evidence_root,
        authorization_path=authorization, signature_path=signature,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        synthetic_test_only=False,
    )
    if prepared.authorization_bytes != authorization.read_bytes():
        raise OperationalCliError("verified authorization bytes drifted")


def author_operational_manifest(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    input_id: str, manifest_id: str, artifact_specs: list[str],
    stand_id: str | None,
    destination: pathlib.Path, pilot_archive: pathlib.Path | None,
    pilot_sidecar: pathlib.Path | None,
) -> pathlib.Path:
    validation = validate_journal(
        repository_root=repository_root, evidence_root=evidence_root,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
    )
    ordinal = int(input_id[-3:])
    expected_predecessors = [f"S17-EXT-{index:03d}" for index in range(1, ordinal)]
    if any(item not in validation.resolutions for item in expected_predecessors):
        raise OperationalCliError("manifest predecessor resolution is absent")
    parent = destination.parent.resolve()
    artifacts = []
    for spec in artifact_specs:
        try:
            role_and_id, path_text = spec.split("=", 1)
            role, artifact_id = role_and_id.split(":", 1)
        except ValueError as exception:
            raise OperationalCliError(
                "artifact must be ROLE:ARTIFACT_ID=/absolute/path"
            ) from exception
        if not artifact_id or any(character not in
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in artifact_id):
            raise OperationalCliError("artifact ID has unsafe characters")
        path = pathlib.Path(path_text).resolve()
        try:
            locator = path.relative_to(parent).as_posix()
        except ValueError as exception:
            raise OperationalCliError("manifest artifact is outside its directory") from exception
        expected_schema = semantics.ROLE_SCHEMA.get(role, "UNKNOWN")
        if expected_schema == "UNKNOWN":
            raise OperationalCliError(f"unknown production artifact role: {role}")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise OperationalCliError(f"artifact is not regular: {path}")
            raw_observation = role in semantics.STREAMING_OBSERVATION_ROLES
            payload = None if raw_observation else os.pread(
                descriptor, metadata.st_size + 1, 0
            )
            artifact_sha256 = semantics._hash_fd(descriptor, metadata.st_size)
        finally:
            os.close(descriptor)
        if payload is not None and len(payload) != metadata.st_size:
            raise OperationalCliError(f"artifact changed during pinned read: {path}")
        schema_identity = None
        schema_binding = None
        if raw_observation:
            schema_identity = output_registry.RAW_SCHEMA
        elif expected_schema is not None:
            assert payload is not None
            document = json.loads(payload)
            if not isinstance(document, dict):
                raise OperationalCliError(f"typed artifact is not an object: {path}")
            validate_schema(repository_root, expected_schema, document)
            schema_identity = document["schema_version"]
            schema_binding = binding(repository_root / expected_schema)
            schema_binding["path"] = expected_schema
        media = (
            "application/sshsig" if role in semantics.SIGNATURE_ROLES
            else "application/json" if expected_schema is not None
            else "application/octet-stream"
        )
        artifacts.append({
            "artifact_id": artifact_id, "role": role,
            "media_type": media, "locator": locator,
            "size_bytes": metadata.st_size, "sha256": artifact_sha256,
            "schema_identity": schema_identity, "schema_binding": schema_binding,
            "lineage": [],
        })
    by_role = {item["role"]: item for item in artifacts}
    for signature_role in semantics.SIGNATURE_ROLES:
        signature = by_role.get(signature_role)
        if signature is None:
            continue
        authorization_role = signature_role.replace("SIGNATURE", "AUTHORIZATION")
        authorization = by_role.get(authorization_role)
        if authorization is None:
            raise OperationalCliError("signature artifact has no authorization")
        signature["lineage"] = [{
            "id": authorization["artifact_id"],
            "sha256": authorization["sha256"],
        }]
    ext2 = validation.resolutions.get("S17-EXT-002")
    admitted_stand_id = (
        ext2.semantic_context["stand_id"]
        if ext2 is not None and isinstance(ext2.semantic_context, dict) else None
    )
    if input_id == "S17-EXT-002":
        if not stand_id:
            raise OperationalCliError("EXT002 requires owner-supplied --stand-id")
    elif admitted_stand_id is None:
        raise OperationalCliError("EXT002 stand identity has not been admitted")
    elif stand_id is not None and stand_id != admitted_stand_id:
        raise OperationalCliError("owner-supplied stand ID differs from EXT002")
    else:
        stand_id = admitted_stand_id
    document = {
        "schema_version": "cpu-prefetch-stage17-operational-input-manifest/3",
        "manifest_id": manifest_id, "input_id": input_id, "stand_id": stand_id,
        "predecessor_resolutions": [
            _resolution_binding(validation.resolutions[item])
            for item in expected_predecessors
        ],
        "artifacts": artifacts, "synthetic_test_only": False,
        "phase18_authority": False,
    }
    validate_schema(
        repository_root,
        "config/schemas/stage17-operational-input-manifest-v3.schema.json",
        document,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    parent_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY |
                        os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        _write_exclusive_at(parent_fd, destination.name, canonical(document))
    finally:
        os.close(parent_fd)
    return destination


def author_custody_receipt(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    input_id: str, artifact: pathlib.Path, sidecars: list[pathlib.Path],
    contract: pathlib.Path, custody_domain: str, destination: pathlib.Path,
) -> pathlib.Path:
    contract_relative = contract.resolve().relative_to(evidence_root.resolve())
    _, contract_payload = load_json(contract)
    artifact_binding = streaming_binding(artifact)
    document = {
        "schema_version": "cpu-prefetch-stage17-external-custody-receipt/2",
        "receipt_id": f"{input_id}-CUSTODY-RECEIPT",
        "artifact_locator": str(artifact.resolve()),
        "artifact_size_bytes": artifact_binding["size_bytes"],
        "artifact_sha256": artifact_binding["sha256"],
        "sidecars": [{
            "locator": str(item.resolve()),
            "size_bytes": sidecar_binding["size_bytes"],
            "sha256": sidecar_binding["sha256"],
        } for item in sidecars
          for sidecar_binding in (streaming_binding(item),)],
        "custody_domain_id": custody_domain,
        "verifier_id": (
            pilot_artifact.VERIFIER_ID if input_id == "S17-EXT-006"
            else "STAGE17-OPERATIONAL-MANIFEST-VERIFIER"
        ),
        "verifier_version": (
            pilot_artifact.VERIFIER_VERSION if input_id == "S17-EXT-006" else "3"
        ),
        "verification_result": "PASS",
        "verified_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z"),
        "contract": {
            "locator": contract_relative.as_posix(),
            "size_bytes": len(contract_payload),
            "sha256": digest(contract_payload),
            "scope": "OPERATIONAL_EVIDENCE_ROOT",
        },
        "phase18_authority": False,
    }
    destination_relative = destination.resolve().relative_to(evidence_root.resolve())
    if destination_relative.parts[0] != "receipts":
        raise OperationalCliError("custody receipt must be under evidence-root/receipts")
    parent = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY |
                     os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        _write_exclusive_at(parent, destination.name, canonical(document))
    finally:
        os.close(parent)
    return destination


def author_ext006_contract(
    *, repository_root: pathlib.Path, archive: pathlib.Path,
    sidecar: pathlib.Path, primary_custody_domain: str,
    secondary_custody_domain: str, destination: pathlib.Path,
) -> pathlib.Path:
    """Verify actual release bytes and create the canonical EXT006 contract."""
    document = pilot_artifact.build_contract_v3(
        repository_root=repository_root, archive=archive, sidecar=sidecar,
        primary_custody_domain_id=primary_custody_domain,
        secondary_custody_domain_id=secondary_custody_domain,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    parent = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY |
                     os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        _write_exclusive_at(parent, destination.name, canonical(document))
    finally:
        os.close(parent)
    return destination


def _authority_from_file(path: pathlib.Path) -> dict[str, Any]:
    document, _ = load_json(path)
    return {
        "authorization_id": document["authorization_id"],
        "issued_at_utc": document["issued_at_utc"],
        "expires_at_utc": document["expires_at_utc"],
        "authority_scope": (
            "READ_ONLY_PREFLIGHT" if document.get("input_id") == "S17-EXT-001"
            else "PRIVILEGED_QUALIFICATION_CONTROL" if document.get("action_id")
            == "Q15-W"
            else "STAGE17_PILOT_PHASE_ONLY" if document.get("action_id") ==
            "STAGE17-BLINDED-PILOT" else document.get("action_id")
        ),
    }


def append_resolution(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    input_id: str, actor: str, recorded_at_utc: str,
    repository_evidence: list[pathlib.Path], receipt_evidence: list[pathlib.Path],
    authorization_file: pathlib.Path | None,
    pilot_archive: pathlib.Path | None, pilot_sidecar: pathlib.Path | None,
    allow_synthetic: bool = False,
) -> pathlib.Path:
    parse_utc(recorded_at_utc)
    previous = validate_journal(
        repository_root=repository_root, evidence_root=evidence_root,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        allow_synthetic=allow_synthetic,
    )
    if input_id in previous.resolutions:
        raise OperationalCliError("input already has an immutable resolution")
    latest_path = latest_journal(evidence_root)
    latest, latest_payload = load_json(latest_path)
    sequence = len(latest["resolution_records"]) + 1
    evidence: list[dict[str, Any]] = []
    for path in repository_evidence:
        try:
            relative = path.resolve().relative_to(repository_root.resolve())
        except ValueError as exception:
            raise OperationalCliError("repository evidence is outside repository") from exception
        _, payload = load_json(path)
        evidence.append({
            "kind": "REPOSITORY_FILE", "path": relative.as_posix(),
            "size_bytes": len(payload), "sha256": digest(payload),
        })
    for path in receipt_evidence:
        try:
            relative = path.resolve().relative_to(evidence_root.resolve())
        except ValueError as exception:
            raise OperationalCliError("receipt is outside operational evidence root") from exception
        _, payload = load_json(path)
        evidence.append({
            "kind": "EXTERNAL_CUSTODY_RECEIPT",
            "receipt_path": relative.as_posix(),
            "receipt_size_bytes": len(payload), "receipt_sha256": digest(payload),
        })
    document = {
        "schema_version": "cpu-prefetch-stage17-external-input-resolution/1",
        "resolution_id": f"{input_id}-RESOLUTION-{sequence:03d}",
        "sequence_number": sequence, "input_id": input_id, "actor": actor,
        "recorded_at_utc": recorded_at_utc,
        "graph_sha256": latest["graph"]["sha256"],
        "catalog_sha256": latest["catalog"]["sha256"],
        "version_hashes": latest["version_hashes"], "evidence": evidence,
        "authorization": (
            _authority_from_file(authorization_file)
            if authorization_file is not None else None
        ),
        "verification_result": "PASS", "automatic_resolution": False,
        "retry_authority": False, "stage18_authority": False,
    }
    validate_schema(
        repository_root,
        "config/schemas/stage17-external-input-resolution-v1.schema.json",
        document,
    )
    root_fd = _root_fd(evidence_root)
    records_fd = _subdir(root_fd, "records")
    journals_fd = _subdir(root_fd, "journal")
    try:
        record_name = f"resolution-{sequence:03d}-{input_id.lower()}.json"
        record_payload = canonical(document)
        _write_exclusive_at(records_fd, record_name, record_payload)
        candidate = copy.deepcopy(latest)
        candidate["journal_sequence_number"] += 1
        candidate["previous_journal"] = {
            "path": latest_path.relative_to(evidence_root).as_posix(),
            "sha256": digest(latest_payload),
        }
        candidate["resolution_records"].append({
            "path": f"records/{record_name}", "sha256": digest(record_payload),
        })
        candidate_name = (
            f"stage17-state-journal-{candidate['journal_sequence_number']:06d}.json"
        )
        candidate_payload = canonical(candidate)
        staging = evidence_root / "journal" / (candidate_name + ".candidate")
        _write_exclusive_at(journals_fd, staging.name, candidate_payload)
        journal_runtime.validate_operational_journal(
            repository_root=repository_root, evidence_root=evidence_root,
            latest_journal=staging, journal_directory=evidence_root / "journal",
            pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
            as_of_utc=recorded_at_utc,
            allow_synthetic_test_evidence=allow_synthetic,
        )
        _write_exclusive_at(journals_fd, candidate_name, candidate_payload)
    finally:
        os.close(journals_fd); os.close(records_fd); os.close(root_fd)
    return evidence_root / "journal" / candidate_name


def append_transition(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    actor: str, timestamp_utc: str, pilot_archive: pathlib.Path | None,
    pilot_sidecar: pathlib.Path | None, allow_synthetic: bool = False,
) -> pathlib.Path:
    parse_utc(timestamp_utc)
    validation = validate_journal(
        repository_root=repository_root, evidence_root=evidence_root,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        allow_synthetic=allow_synthetic,
    )
    latest_path = latest_journal(evidence_root)
    latest, latest_payload = load_json(latest_path)
    graph, _ = load_json(
        repository_root / "config/stage17/stage17-operational-graph-definition-v1.json"
    )
    sequence = validation.transition_count + 1
    if sequence > len(graph["transitions"]):
        raise OperationalCliError("finite Stage 17 transition graph is complete")
    edge = graph["transitions"][sequence - 1]
    resolutions = validation.resolutions
    if any(item not in resolutions for item in edge["required_input_ids"]):
        raise OperationalCliError("transition evidence is incomplete")
    previous_transition = (
        validation.transitions[-1].sha256 if validation.transitions
        else latest["genesis"]["genesis_sha256"]
    )
    authorizations = []
    for input_id in edge["authorization_input_ids"]:
        summary = resolutions[input_id].document["authorization"]
        authorizations.append({
            "input_id": input_id,
            "resolution_id": resolutions[input_id].resolution_id,
            "authorization_id": summary["authorization_id"],
            "authority_scope": summary["authority_scope"],
        })
    document = {
        "schema_version": "cpu-prefetch-stage17-state-transition/1",
        "transition_id": f"STAGE17-TRANSITION-{sequence:03d}",
        "sequence_number": sequence, "from_state": edge["from_state"],
        "to_state": edge["to_state"],
        "previous_transition_sha256": previous_transition, "actor": actor,
        "timestamp_utc": timestamp_utc,
        "evidence_resolutions": [
            _resolution_binding(resolutions[item])
            for item in edge["required_input_ids"]
        ],
        "authorizations": authorizations,
        "graph_sha256": latest["graph"]["sha256"],
        "catalog_sha256": latest["catalog"]["sha256"],
        "version_hashes": latest["version_hashes"],
        "authority_scope": edge["authority_scope"],
        "automatic_transition": False, "retry_allowed": False,
        "stage18_authority": False,
    }
    validate_schema(
        repository_root, "config/schemas/stage17-state-transition-v1.schema.json",
        document,
    )
    root_fd = _root_fd(evidence_root)
    records_fd = _subdir(root_fd, "records")
    journals_fd = _subdir(root_fd, "journal")
    try:
        record_name = f"transition-{sequence:03d}.json"
        record_payload = canonical(document)
        _write_exclusive_at(records_fd, record_name, record_payload)
        candidate = copy.deepcopy(latest)
        candidate["journal_sequence_number"] += 1
        candidate["previous_journal"] = {
            "path": latest_path.relative_to(evidence_root).as_posix(),
            "sha256": digest(latest_payload),
        }
        candidate["transition_records"].append({
            "path": f"records/{record_name}", "sha256": digest(record_payload),
        })
        candidate_name = (
            f"stage17-state-journal-{candidate['journal_sequence_number']:06d}.json"
        )
        candidate_payload = canonical(candidate)
        staging = evidence_root / "journal" / (candidate_name + ".candidate")
        _write_exclusive_at(journals_fd, staging.name, candidate_payload)
        journal_runtime.validate_operational_journal(
            repository_root=repository_root, evidence_root=evidence_root,
            latest_journal=staging, journal_directory=evidence_root / "journal",
            pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
            as_of_utc=timestamp_utc,
            allow_synthetic_test_evidence=allow_synthetic,
        )
        _write_exclusive_at(journals_fd, candidate_name, candidate_payload)
    finally:
        os.close(journals_fd); os.close(records_fd); os.close(root_fd)
    return evidence_root / "journal" / candidate_name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=pathlib.Path, required=True)
    parser.add_argument("--evidence-root", type=pathlib.Path, required=True)
    parser.add_argument("--pilot-archive", type=pathlib.Path)
    parser.add_argument("--pilot-sidecar", type=pathlib.Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    subparsers.add_parser("status")
    request = subparsers.add_parser("author-request")
    request.add_argument("--action", required=True)
    request.add_argument("--action-inputs", type=pathlib.Path, required=True)
    request.add_argument("--request-id", required=True)
    request.add_argument("--authorization-id", required=True)
    request.add_argument("--attempt-id", required=True)
    request.add_argument("--output-root", type=pathlib.Path, required=True)
    request.add_argument("--output", type=pathlib.Path, required=True)
    authorization = subparsers.add_parser("author-authorization")
    authorization.add_argument("--request", type=pathlib.Path, required=True)
    authorization.add_argument("--actor", required=True)
    authorization.add_argument("--reviewer", required=True)
    authorization.add_argument("--issued-at-utc", required=True)
    authorization.add_argument("--expires-at-utc", required=True)
    authorization.add_argument("--output", type=pathlib.Path, required=True)
    signature = subparsers.add_parser("verify-signature")
    signature.add_argument("--authorization", type=pathlib.Path, required=True)
    signature.add_argument("--signature", type=pathlib.Path, required=True)
    manifest = subparsers.add_parser("author-manifest")
    manifest.add_argument("--input-id", required=True)
    manifest.add_argument("--manifest-id", required=True)
    manifest.add_argument("--stand-id")
    manifest.add_argument("--artifact", action="append", default=[], required=True)
    manifest.add_argument("--output", type=pathlib.Path, required=True)
    custody = subparsers.add_parser("author-custody-receipt")
    custody.add_argument("--input-id", required=True)
    custody.add_argument("--artifact", type=pathlib.Path, required=True)
    custody.add_argument("--sidecar", type=pathlib.Path, action="append", default=[])
    custody.add_argument("--contract", type=pathlib.Path, required=True)
    custody.add_argument("--custody-domain", required=True)
    custody.add_argument("--output", type=pathlib.Path, required=True)
    ext006 = subparsers.add_parser("author-ext006-contract")
    ext006.add_argument("--primary-custody-domain", required=True)
    ext006.add_argument("--secondary-custody-domain", required=True)
    ext006.add_argument("--output", type=pathlib.Path, required=True)
    resolution = subparsers.add_parser("admit-resolution")
    resolution.add_argument("--input-id", required=True)
    resolution.add_argument("--actor", required=True)
    resolution.add_argument("--recorded-at-utc", required=True)
    resolution.add_argument("--repository-evidence", type=pathlib.Path,
                            action="append", default=[])
    resolution.add_argument("--receipt-evidence", type=pathlib.Path,
                            action="append", default=[])
    resolution.add_argument("--authorization-file", type=pathlib.Path)
    transition = subparsers.add_parser("append-transition")
    transition.add_argument("--actor", required=True)
    transition.add_argument("--timestamp-utc", required=True)
    arguments = parser.parse_args()
    root = arguments.repository_root.resolve()
    evidence = arguments.evidence_root.resolve()
    try:
        if arguments.command == "init":
            result = initialize(root, evidence)
            print(f"stage17-operational: PASS initialized={result}")
        elif arguments.command == "status":
            value = validate_journal(
                repository_root=root, evidence_root=evidence,
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
                as_of_utc=dt.datetime.now(dt.timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                ),
            )
            print(json.dumps({
                "current_state": value.current_state,
                "resolutions": value.resolution_count,
                "transitions": value.transition_count,
                "missing_inputs": list(value.missing_input_ids),
                "pilot_ready": value.pilot_ready,
            }, sort_keys=True))
        elif arguments.command == "author-request":
            result = author_request(
                repository_root=root, evidence_root=evidence,
                action=arguments.action,
                action_inputs_path=arguments.action_inputs,
                request_id=arguments.request_id,
                authorization_id=arguments.authorization_id,
                attempt_id=arguments.attempt_id,
                output_root=arguments.output_root.resolve(),
                destination=arguments.output.resolve(),
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
            )
            print(f"stage17-operational: PASS unsigned_request={result}")
        elif arguments.command == "author-authorization":
            result = author_authorization(
                repository_root=root, evidence_root=evidence,
                request_path=arguments.request.resolve(), actor=arguments.actor,
                reviewer=arguments.reviewer,
                issued_at_utc=arguments.issued_at_utc,
                expires_at_utc=arguments.expires_at_utc,
                destination=arguments.output.resolve(),
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
            )
            print(f"stage17-operational: PASS unsigned_authorization={result}")
        elif arguments.command == "verify-signature":
            verify_phase_signature(
                repository_root=root, evidence_root=evidence,
                authorization=arguments.authorization.resolve(),
                signature=arguments.signature.resolve(),
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
            )
            print("stage17-operational: PASS signature=VERIFIED action=NOT_EXECUTED")
        elif arguments.command == "author-manifest":
            result = author_operational_manifest(
                repository_root=root, evidence_root=evidence,
                input_id=arguments.input_id, manifest_id=arguments.manifest_id,
                stand_id=arguments.stand_id,
                artifact_specs=arguments.artifact,
                destination=arguments.output.resolve(),
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
            )
            print(f"stage17-operational: PASS manifest={result}")
        elif arguments.command == "author-custody-receipt":
            result = author_custody_receipt(
                repository_root=root, evidence_root=evidence,
                input_id=arguments.input_id,
                artifact=arguments.artifact.resolve(),
                sidecars=[item.resolve() for item in arguments.sidecar],
                contract=arguments.contract.resolve(),
                custody_domain=arguments.custody_domain,
                destination=arguments.output.resolve(),
            )
            print(f"stage17-operational: PASS custody_receipt={result}")
        elif arguments.command == "author-ext006-contract":
            if arguments.pilot_archive is None or arguments.pilot_sidecar is None:
                raise OperationalCliError(
                    "EXT006 contract requires --pilot-archive and --pilot-sidecar"
                )
            result = author_ext006_contract(
                repository_root=root,
                archive=arguments.pilot_archive.resolve(),
                sidecar=arguments.pilot_sidecar.resolve(),
                primary_custody_domain=arguments.primary_custody_domain,
                secondary_custody_domain=arguments.secondary_custody_domain,
                destination=arguments.output.resolve(),
            )
            print(f"stage17-operational: PASS ext006_contract={result}")
        elif arguments.command == "admit-resolution":
            result = append_resolution(
                repository_root=root, evidence_root=evidence,
                input_id=arguments.input_id, actor=arguments.actor,
                recorded_at_utc=arguments.recorded_at_utc,
                repository_evidence=[item.resolve() for item in arguments.repository_evidence],
                receipt_evidence=[item.resolve() for item in arguments.receipt_evidence],
                authorization_file=(arguments.authorization_file.resolve()
                                    if arguments.authorization_file else None),
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
            )
            print(f"stage17-operational: PASS resolution_journal={result}")
        else:
            result = append_transition(
                repository_root=root, evidence_root=evidence,
                actor=arguments.actor, timestamp_utc=arguments.timestamp_utc,
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
            )
            print(f"stage17-operational: PASS transition_journal={result}")
    except BaseException as exception:
        print(f"stage17-operational: FAIL: {exception}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
