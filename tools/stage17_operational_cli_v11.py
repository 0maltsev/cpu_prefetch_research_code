#!/usr/bin/env python3
"""Fail-closed Stage 17 operational CLI with a D-124 no-predecessor-attestation
successor to `author-ext001`.

Repository definitions are immutable inputs.  Mutable operational records live
under a separate create-exclusive owner evidence root.  This tool never makes
up owner facts and never signs: it renders canonical unsigned bytes, verifies
detached signatures through the production admission path, and appends only a
fully validated journal successor.

This v11 successor is a byte-identical copy of `stage17_operational_cli_v10.py`
except for `author_ext001` and its `author-ext001` argparse wiring, which gain
an optional `--no-predecessor-attestation` alternative to the three blocker-
receipt flags per ADR-0124 (`PROPOSED`).  It is not wired into any accepted
runtime-closure policy; `stage17_operational_cli_v10.py` remains the sole
production entry point until a new policy successor accepts this file.
"""

from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import stat
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

import stage17_output_registry_v4 as output_registry
import stage17_exit_state_machine_v4 as exit_machine
import stage17_phase_controller_v9 as controller
import stage17_operational_semantics_v4 as semantics
import stage17_operational_semantics_v5 as semantics_v5
import stage17_pilot_candidate_artifact_v4 as pilot_artifact
import stage17_state_journal as base
import stage17_state_journal_v19 as journal_runtime


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


def hash_open_regular_file(descriptor: int, size_bytes: int) -> str:
    """Hash the exact file already selected by an open no-follow descriptor."""
    hasher = hashlib.sha256()
    offset = 0
    while offset < size_bytes:
        chunk = os.pread(
            descriptor, min(1024 * 1024, size_bytes - offset), offset
        )
        if not chunk:
            raise OperationalCliError("artifact changed during pinned read")
        hasher.update(chunk)
        offset += len(chunk)
    return hasher.hexdigest()


def validate_schema(root: pathlib.Path, relative: str,
                    document: dict[str, Any]) -> None:
    schema, _ = load_json(root / relative)
    Draft202012Validator.check_schema(schema)
    registry = Registry()
    if relative == (
            "config/schemas/stage17-operational-input-manifest-v4.schema.json"):
        artifact_relative = (
            "config/schemas/stage17-operational-artifact-v4.schema.json"
        )
        artifact_schema, _ = load_json(root / artifact_relative)
        resource = Resource.from_contents(artifact_schema)
        registry = registry.with_resource(
            "stage17-operational-artifact-v4.schema.json", resource
        ).with_resource(
            "urn:cpu-prefetch:stage17:operational-input-manifest:"
            "stage17-operational-artifact-v4.schema.json",
            resource,
        )
    errors = list(Draft202012Validator(
        schema, registry=registry, format_checker=FormatChecker()
    ).iter_errors(document))
    if errors:
        raise OperationalCliError(
            f"{relative} rejection: {errors[0].message}"
        )


def require_synthetic_test_bundle(repository_root: pathlib.Path) -> None:
    """Permit synthetic admission only from the separately classified bundle."""
    manifest, _ = load_json(repository_root / "BUNDLE_MANIFEST.json")
    if (manifest.get("bundle_profile") not in (
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v4",
            )
            or manifest.get("stage17_fixed_action_runtime", {}).get(
                "synthetic_test_only") is not True
            or manifest.get("pilot_authorized") is not False
            or manifest.get("confirmatory_authorized") is not False):
        raise OperationalCliError(
            "synthetic mode is unavailable outside the classified dry-run bundle"
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


def write_external_exclusive(destination: pathlib.Path, payload: bytes) -> None:
    """Create one durable caller-selected record without replacing bytes."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    parent = os.open(
        destination.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        _write_exclusive_at(parent, destination.name, payload)
        os.fsync(parent)
    finally:
        os.close(parent)


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


def materialize_admission_root(
    repository_root: pathlib.Path, evidence_root: pathlib.Path,
) -> pathlib.Path:
    """Create one private exact bundle snapshot with an append-only evidence leaf.

    The verified extracted bundle remains immutable.  Current v1 journal
    contracts use repository-relative evidence locators, so operational
    records are admitted from this separately rooted snapshot instead of
    mutating the release tree.  Definition bytes are made read-only before the
    function returns; only ``evidence/`` remains owner-writable.
    """
    source = repository_root.resolve()
    destination = evidence_root.resolve() / "admission-root"
    try:
        destination.relative_to(source)
    except ValueError:
        pass
    else:
        raise OperationalCliError("admission root cannot be nested in bundle root")
    if destination.exists() or destination.is_symlink():
        raise OperationalCliError("admission root already exists")
    if not (source / "BUNDLE_MANIFEST.json").is_file() or not (
            source / "SHA256SUMS").is_file():
        raise OperationalCliError("admission root requires a verified bundle root")
    for item in source.rglob("*"):
        if item.is_symlink():
            raise OperationalCliError("bundle contains a forbidden symlink")
    try:
        shutil.copytree(source, destination, symlinks=False)
        evidence = destination / "evidence"
        evidence.mkdir(mode=0o700)
        for item in sorted(destination.rglob("*"), reverse=True):
            if item == evidence or evidence in item.parents:
                continue
            if item.is_dir():
                item.chmod(0o500)
            elif item.is_file():
                executable = bool(item.stat().st_mode & 0o111)
                item.chmod(0o500 if executable else 0o400)
        destination.chmod(0o500)
    except BaseException:
        # A partial create-exclusive tree is a fail-closed retained blocker.
        # It is deliberately not deleted or reused automatically.
        raise
    manifest_payload = (source / "BUNDLE_MANIFEST.json").read_bytes()
    sums_payload = (source / "SHA256SUMS").read_bytes()
    record = {
        "schema_version": "cpu-prefetch-stage17-admission-root-binding/1",
        "source_bundle_root": str(source),
        "admission_root": str(destination),
        "bundle_manifest_size_bytes": len(manifest_payload),
        "bundle_manifest_sha256": digest(manifest_payload),
        "sha256s_size_bytes": len(sums_payload),
        "sha256s_sha256": digest(sums_payload),
        "definitions_read_only": True,
        "evidence_subtree": "evidence",
        "evidence_create_exclusive": True,
        "source_bundle_modified": False,
        "stage18_authority": False,
    }
    evidence_root_fd = _root_fd(evidence_root)
    manifests_fd = _subdir(evidence_root_fd, "manifests")
    try:
        _write_exclusive_at(
            manifests_fd, "stage17-admission-root-binding-v1.json",
            canonical(record),
        )
    finally:
        os.close(manifests_fd)
        os.close(evidence_root_fd)
    return destination


def initialize(
    repository_root: pathlib.Path, evidence_root: pathlib.Path, *,
    materialize_bundle: bool = False,
) -> tuple[pathlib.Path, pathlib.Path]:
    root_fd = _root_fd(evidence_root)
    try:
        for name in (
            "journal", "records", "receipts", "actions", "authorizations",
            "manifests",
        ):
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
    admission_root = (
        materialize_admission_root(repository_root, evidence_root)
        if materialize_bundle else repository_root
    )
    return (
        evidence_root / "journal/stage17-state-journal-000000.json",
        admission_root,
    )


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
    authorization_id: str, attempt_id: str, session_id: str,
    output_root: pathlib.Path,
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
        "schema_version": "cpu-prefetch-stage17-fixed-action-request/4",
        "request_id": request_id, "session_id": session_id,
        "action_id": action,
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
        "config/schemas/stage17-fixed-action-request-v4.schema.json", document,
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
    synthetic: bool = False,
) -> pathlib.Path:
    issued, expires = parse_utc(issued_at_utc), parse_utc(expires_at_utc)
    request, request_payload = load_json(request_path)
    validation = validate_journal(
        repository_root=repository_root, evidence_root=evidence_root,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        allow_synthetic=synthetic,
    )
    registry = output_registry.pin_registry(repository_root)
    definition = registry.action(request["action_id"])
    if request["action_id"] == "STAGE17-BLINDED-PILOT":
        plan = request["action_inputs"].get("pilot_plan")
        if not isinstance(plan, dict):
            raise OperationalCliError("pilot authorization requires the exact plan")
        repetitions = plan["repetitions_per_cell"]
        recovery_seconds = (plan["recovery"]["duration_ticks"] +
                            999_999_999_999) // 1_000_000_000_000
        session_max = 180 * 180 * repetitions + recovery_seconds * max(
            repetitions - 1, 0
        ) + 180
        deadline_policy = {
            "mode": "DURABLE_PILOT_SESSION",
            "per_run_max_wall_seconds": 180,
            "session_max_wall_seconds": session_max,
            "implicit_extension": False,
            "partial_session_completes": False,
        }
    else:
        session_max = 1800
        deadline_policy = {
            "mode": "ONE_SHOT_ACTION",
            "per_run_max_wall_seconds": 180,
            "session_max_wall_seconds": None,
            "implicit_extension": False,
            "partial_session_completes": False,
        }
    if not issued < expires or expires - issued > dt.timedelta(
            seconds=session_max):
        raise OperationalCliError(
            "authorization window is nonpositive or exceeds its fixed action bound"
        )
    ext2, ext3 = validation.resolutions["S17-EXT-002"], validation.resolutions[
        "S17-EXT-003"
    ]
    trust = ext3.semantic_context["trust"]["measurements"]
    if actor != trust["principal"] or reviewer != trust["reviewer_role"]:
        raise OperationalCliError("actor/reviewer differ from admitted trust")
    document = {
        "schema_version": "cpu-prefetch-stage17-phase-action-authorization/4",
        "authorization_id": request["authorization_id"],
        "session_id": request["session_id"],
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
        "deadline_policy": deadline_policy, "one_attempt": True,
        "retry_allowed": False, "stop_first": True,
        "retain_partial": True, "stage18_authority": False,
    }
    validate_schema(
        repository_root,
        "config/schemas/stage17-phase-action-authorization-v4.schema.json",
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
    synthetic: bool = False,
) -> None:
    prepared = controller.prepare_action(
        repository_root=repository_root,
        journal=latest_journal(evidence_root),
        journal_directory=evidence_root / "journal",
        operational_evidence_root=evidence_root,
        authorization_path=authorization, signature_path=signature,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        synthetic_test_only=synthetic,
    )
    if prepared.authorization_bytes != authorization.read_bytes():
        raise OperationalCliError("verified authorization bytes drifted")


def author_operational_manifest(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    input_id: str, manifest_id: str, artifact_specs: list[str],
    stand_id: str | None,
    destination: pathlib.Path, pilot_archive: pathlib.Path | None,
    pilot_sidecar: pathlib.Path | None,
    synthetic: bool = False,
) -> pathlib.Path:
    validation = validate_journal(
        repository_root=repository_root, evidence_root=evidence_root,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        allow_synthetic=synthetic,
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
        expected_schema = semantics_v5.ROLE_SCHEMA_v5.get(role, "UNKNOWN")
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
            artifact_sha256 = hash_open_regular_file(
                descriptor, metadata.st_size
            )
            current = os.fstat(descriptor)
            if ((current.st_dev, current.st_ino, current.st_size,
                 current.st_mtime_ns, current.st_ctime_ns) !=
                    (metadata.st_dev, metadata.st_ino, metadata.st_size,
                     metadata.st_mtime_ns, metadata.st_ctime_ns)):
                raise OperationalCliError(
                    f"artifact changed during pinned read: {path}"
                )
        finally:
            os.close(descriptor)
        if payload is not None and len(payload) != metadata.st_size:
            raise OperationalCliError(f"artifact changed during pinned read: {path}")
        schema_identity = None
        schema_binding = None
        if raw_observation:
            schema_identity = output_registry.RAW_SCHEMA
        elif role in semantics.LOGICAL_ENVELOPE_ROLES:
            assert payload is not None
            document = json.loads(payload)
            if not isinstance(document, dict):
                raise OperationalCliError(
                    f"logical envelope is not an object: {path}"
                )
            schema_identity = "2.0.0-pre.3"
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
            else "application/json" if (
                expected_schema is not None
                or role in semantics.LOGICAL_ENVELOPE_ROLES
            )
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
        "schema_version": "cpu-prefetch-stage17-operational-input-manifest/4",
        "manifest_id": manifest_id, "input_id": input_id, "stand_id": stand_id,
        "predecessor_resolutions": [
            _resolution_binding(validation.resolutions[item])
            for item in expected_predecessors
        ],
        "artifacts": artifacts, "synthetic_test_only": synthetic,
        "phase18_authority": False,
    }
    validate_schema(
        repository_root,
        "config/schemas/stage17-operational-input-manifest-v4.schema.json",
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
            pilot_artifact.VERIFIER_VERSION if input_id == "S17-EXT-006" else "4"
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
    secondary_custody_domain: str, contract_id: str,
    destination: pathlib.Path,
) -> pathlib.Path:
    """Verify actual release bytes and create the canonical EXT006 contract."""
    document = pilot_artifact.build_contract_v4(
        repository_root=repository_root, archive=archive, sidecar=sidecar,
        primary_custody_domain_id=primary_custody_domain,
        secondary_custody_domain_id=secondary_custody_domain,
        contract_id=contract_id,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    parent = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY |
                     os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        _write_exclusive_at(parent, destination.name, canonical(document))
    finally:
        os.close(parent)
    return destination


def _repository_binding(
    repository_root: pathlib.Path, path: pathlib.Path, *,
    schema_identity: str | None = None,
) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(repository_root.resolve())
    except ValueError as exception:
        raise OperationalCliError("repository binding is outside admission root") \
            from exception
    value = binding(resolved)
    value["path"] = relative.as_posix()
    if schema_identity is not None:
        value["schema_identity"] = schema_identity
    return value


def _openssh_ed25519_public_key(path: pathlib.Path) -> tuple[bytes, str]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 1
                or metadata.st_size > 16 * 1024):
            raise OperationalCliError("host public key is not a bounded regular file")
        payload = os.pread(descriptor, metadata.st_size + 1, 0)
    finally:
        os.close(descriptor)
    fields = payload.strip().split()
    if len(fields) < 2 or fields[0] != b"ssh-ed25519":
        raise OperationalCliError("host public key is not OpenSSH Ed25519")
    try:
        wire = base64.b64decode(fields[1], validate=True)
    except ValueError as exception:
        raise OperationalCliError("host public key base64 is malformed") from exception
    offset = 0

    def field() -> bytes:
        nonlocal offset
        if offset + 4 > len(wire):
            raise OperationalCliError("host public key wire blob is truncated")
        length = int.from_bytes(wire[offset:offset + 4], "big")
        offset += 4
        if offset + length > len(wire):
            raise OperationalCliError("host public key wire field is truncated")
        value = wire[offset:offset + length]
        offset += length
        return value

    if field() != b"ssh-ed25519" or len(field()) != 32 or offset != len(wire):
        raise OperationalCliError("host public key wire structure is invalid")
    fingerprint = "SHA256:" + base64.b64encode(
        hashlib.sha256(wire).digest()
    ).decode().rstrip("=")
    return wire, fingerprint


NO_PREDECESSOR_ATTESTATION_SCHEMA_IDENTITY = (
    "cpu-prefetch-stage17-preflight-no-predecessor-attestation/1"
)


def _no_predecessor_attestation_binding(path: pathlib.Path) -> dict[str, Any]:
    """Bind the real bytes of an owner-authored D-124 attestation record."""
    payload = path.read_bytes()
    return {
        "locator": str(path.resolve()), "size_bytes": len(payload),
        "sha256": digest(payload),
        "schema_identity": NO_PREDECESSOR_ATTESTATION_SCHEMA_IDENTITY,
    }


def author_ext001(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    stand_id: str, ssh_target: str, known_hosts_host: str,
    pinned_host_public_key: pathlib.Path, pinned_known_hosts: pathlib.Path,
    transport_identity: pathlib.Path, bundle_root_locator: pathlib.Path,
    pilot_archive: pathlib.Path, pilot_sidecar: pathlib.Path,
    capture_id: str, captured_at_utc: str, preflight_evidence_root: pathlib.Path,
    pre_marker_blocker: pathlib.Path | None = None,
    post_marker_blocker: pathlib.Path | None = None,
    action_revalidation_blocker: pathlib.Path | None = None,
    no_predecessor_attestation: pathlib.Path | None = None,
    actor: str, issued_at_utc: str, expires_at_utc: str,
    authorization_id: str, attempt_id: str, contract_id: str,
    envelope_id: str, destination_directory: pathlib.Path,
) -> pathlib.Path:
    """Create canonical S17-EXT-001 bytes from explicit owner inputs.

    Per ADR-0124, exactly one of the three blocker-receipt paths or
    `no_predecessor_attestation` must be supplied; this is also enforced by
    the CLI argument wiring before any file I/O, and re-checked here so the
    function is safe to call directly.
    """
    three_blockers_given = (
        pre_marker_blocker is not None or post_marker_blocker is not None
        or action_revalidation_blocker is not None
    )
    if no_predecessor_attestation is not None:
        if three_blockers_given:
            raise OperationalCliError(
                "EXT001 cannot combine a no-predecessor attestation with any "
                "blocker receipt"
            )
    elif not (
        pre_marker_blocker is not None and post_marker_blocker is not None
        and action_revalidation_blocker is not None
    ):
        raise OperationalCliError(
            "EXT001 requires either all three blocker receipts or exactly "
            "one no-predecessor attestation"
        )
    issued, expires = parse_utc(issued_at_utc), parse_utc(expires_at_utc)
    captured = parse_utc(captured_at_utc)
    if not issued <= captured < expires or expires <= issued:
        raise OperationalCliError("EXT001 issue/capture/expiry chronology is invalid")
    for label, value in (
        ("stand ID", stand_id), ("SSH target", ssh_target),
        ("known-hosts host", known_hosts_host), ("capture ID", capture_id),
        ("actor", actor), ("authorization ID", authorization_id),
        ("attempt ID", attempt_id), ("contract ID", contract_id),
        ("envelope ID", envelope_id),
    ):
        if not value or any(character in value for character in "\r\n\0"):
            raise OperationalCliError(f"EXT001 {label} is empty or unsafe")
    repository_evidence = repository_root.resolve() / "evidence"
    destination = destination_directory.resolve()
    if destination.parent != repository_evidence or repository_evidence.is_symlink():
        raise OperationalCliError(
            "EXT001 output must be one direct child of admission-root/evidence"
        )
    try:
        destination.mkdir(mode=0o700)
    except FileExistsError as exception:
        raise OperationalCliError("EXT001 output directory already exists") from exception
    wire, fingerprint = _openssh_ed25519_public_key(pinned_host_public_key)
    known_binding = streaming_binding(pinned_known_hosts)
    known_payload = pinned_known_hosts.read_bytes()
    encoded_wire = base64.b64encode(wire)
    expected_known = (
        known_hosts_host.encode() + b" ssh-ed25519 " + encoded_wire
    )
    lines = [line.split(b" #", 1)[0].strip() for line in known_payload.splitlines()]
    if expected_known not in lines:
        raise OperationalCliError("known-hosts bytes do not contain the exact host key")
    identity_binding = streaming_binding(transport_identity)
    identity_metadata = transport_identity.stat(follow_symlinks=False)
    if (identity_metadata.st_uid != os.geteuid()
            or stat.S_IMODE(identity_metadata.st_mode) & 0o077):
        raise OperationalCliError("transport identity must be owner-only")
    for label, path in (
        ("pilot archive", pilot_archive), ("pilot sidecar", pilot_sidecar),
        ("bundle root", bundle_root_locator),
    ):
        if not path.is_absolute() or not path.exists() or path.is_symlink():
            raise OperationalCliError(f"EXT001 {label} locator is unavailable")
    pinned_document = {
        "schema_version": "cpu-prefetch-stage17-pinned-host-key-evidence/1",
        "evidence_id": f"{capture_id}-PINNED-HOST-KEY",
        "stand_id": stand_id, "ssh_target": ssh_target,
        "algorithm": "ssh-ed25519",
        "public_key_base64": encoded_wire.decode(),
        "fingerprint_sha256": fingerprint,
        "source": "OWNER_PROVIDED_OUT_OF_BAND_PIN",
        "runtime_observation": False,
    }
    pinned_path = destination / "pinned-host-key-evidence-v1.json"
    write_external_exclusive(pinned_path, canonical(pinned_document))
    known_copy = destination / "pinned-known-hosts"
    write_external_exclusive(known_copy, known_payload)
    genesis, _ = load_json(
        evidence_root / "journal/stage17-state-journal-000000.json"
    )
    policy_path = repository_root / (
        "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v15.json"
    )
    policy, policy_payload = load_json(policy_path)
    catalog_path = repository_root / str(genesis["catalog"]["path"])
    catalog, _ = load_json(catalog_path)
    fixed_contract = catalog["fixed_evidence_contracts"][0]
    effective = {
        **policy["fixed_action_plan"],
        "schema_identity":
            "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/6",
    }
    successor = {
        **policy["successor_action_plan"],
        "schema_identity":
            "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/9",
    }
    limits = {
        "max_commands": 6, "max_wall_seconds": 180,
        "max_total_output_bytes": 6_291_456,
        "max_output_bytes_per_observation": 1_048_576,
        "timeout_seconds_per_observation": 30,
        "attempts_per_observation": 1, "retries": 0,
    }
    permissions = {
        "stand_read_only": True, "stand_mutation": False,
        "privileged_controls": False, "qualification": False,
        "calibration": False, "pilot_execution": False,
        "measurement": False, "stage18_authority": False,
    }
    using_attestation = no_predecessor_attestation is not None
    contract_schema_version = (
        "cpu-prefetch-stage17-read-only-preflight-supporting-contract/13"
        if using_attestation else
        "cpu-prefetch-stage17-read-only-preflight-supporting-contract/12"
    )
    contract_filename = (
        "supporting-contract-v13.json" if using_attestation
        else "supporting-contract-v12.json"
    )
    contract_schema_relative = (
        "config/schemas/stage17-read-only-preflight-supporting-contract-v13.schema.json"
        if using_attestation else
        "config/schemas/stage17-read-only-preflight-supporting-contract-v12.schema.json"
    )
    contract = {
        "schema_version": contract_schema_version,
        "contract_id": contract_id, "protocol_version": "2.0.0-pre.3",
        "fixed_action_plan": effective,
        "target": {
            "stand_id": stand_id, "ssh_target": ssh_target,
            "known_hosts_host": known_hosts_host,
            "pinned_host_key_evidence": _repository_binding(
                repository_root, pinned_path,
                schema_identity="cpu-prefetch-stage17-pinned-host-key-evidence/1",
            ),
            "pinned_known_hosts": _repository_binding(
                repository_root, known_copy
            ),
            "transport_identity": {
                "locator": str(transport_identity.resolve()),
                "size_bytes": identity_binding["size_bytes"],
                "sha256": identity_binding["sha256"],
            },
        },
        "pilot_candidate": {
            "contract": {
                "path": fixed_contract["path"],
                "size_bytes": fixed_contract["size_bytes"],
                "sha256": fixed_contract["sha256"],
                "schema_identity":
                    "cpu-prefetch-stage17-pilot-candidate-external-contract/1",
            },
            "archive_locator": str(pilot_archive.resolve()),
            "sidecar_locator": str(pilot_sidecar.resolve()),
            "bundle_root_locator": str(bundle_root_locator.resolve()),
        },
        "capture": {"capture_id": capture_id, "captured_at_utc": captured_at_utc},
        "evidence_root": str(preflight_evidence_root.resolve()),
        **(
            {
                "no_predecessor_attestation": _no_predecessor_attestation_binding(
                    no_predecessor_attestation
                ),
            }
            if using_attestation else
            {
                "pre_marker_predecessor": {
                    "locator": str(pre_marker_blocker.resolve()),
                    "size_bytes": pre_marker_blocker.stat().st_size,
                    "sha256": digest(pre_marker_blocker.read_bytes()),
                },
                "post_marker_predecessor": {
                    "locator": str(post_marker_blocker.resolve()),
                    "size_bytes": post_marker_blocker.stat().st_size,
                    "sha256": digest(post_marker_blocker.read_bytes()),
                },
                "action_revalidation_predecessor": {
                    "locator": str(action_revalidation_blocker.resolve()),
                    "size_bytes": action_revalidation_blocker.stat().st_size,
                    "sha256": digest(action_revalidation_blocker.read_bytes()),
                },
            }
        ),
        "prospective_local_action_identities": [
            {
                "identity_id": "STAGE17_READ_ONLY_PREFLIGHT_EXECUTOR",
                "role": "EXECUTOR",
                "execution_path": str(
                    repository_root / policy["implementations"]["executor"]["path"]
                ),
                "source_binding": policy["implementations"]["executor"],
            },
            {
                "identity_id": "STAGE17_READ_ONLY_PREFLIGHT_COLLECTOR",
                "role": "COLLECTOR",
                "execution_path": str(
                    repository_root / policy["implementations"]["collector"]["path"]
                ),
                "source_binding": policy["implementations"]["collector"],
            },
        ],
        "remote_runtime_identity_policy": {
            "source_input_id": "S17-EXT-002",
            "identity_classes": [
                "REMOTE_EXECUTABLE", "REMOTE_MODULE", "REMOTE_DEPENDENCY",
            ],
            "prospective_values_present": False,
        },
        "limits": limits,
        "stop_policy":
            "STOP_ON_FIRST_MISMATCH_NONZERO_EXIT_TIMEOUT_OR_OUTPUT_LIMIT",
        "retention_policy":
            "CREATE_EXCLUSIVE_APPEND_ONLY_RETAIN_SUCCESS_FAILURE_AND_PARTIAL_NO_DELETE",
        "authority_boundary": permissions,
    }
    contract_path = destination / contract_filename
    write_external_exclusive(contract_path, canonical(contract))
    contract_binding = _repository_binding(
        repository_root, contract_path, schema_identity=contract_schema_version,
    )
    observations = [
        "S17-RO-PREFLIGHT-001-TARGET-AND-TRANSPORT-IDENTITY",
        "S17-RO-PREFLIGHT-002-ARCHIVE-AND-SIDECAR-BYTE-VERIFICATION",
        "S17-RO-PREFLIGHT-003-BUNDLE-INTERNAL-VERIFICATION",
        "S17-RO-PREFLIGHT-004-NONPRIVILEGED-SELF-TESTS",
        "S17-RO-PREFLIGHT-005-RUNTIME-TOOL-IDENTITIES",
        "S17-RO-PREFLIGHT-006-READ-ONLY-PLATFORM-INVENTORY",
    ]
    authorization = {
        "schema_version":
            "cpu-prefetch-stage17-read-only-preflight-authorization/11",
        "authorization_id": authorization_id, "attempt_id": attempt_id,
        "input_id": "S17-EXT-001", "actor": actor,
        "issued_at_utc": issued_at_utc, "expires_at_utc": expires_at_utc,
        "authority_scope": "READ_ONLY_PREFLIGHT",
        "target_scope": (
            f"STAND_ID={stand_id};SSH_TARGET={ssh_target};"
            "SCOPE=READ_ONLY_PREFLIGHT;"
            "PLAN=STAGE17-READ-ONLY-PREFLIGHT-FIXED-ACTION-PLAN-v6"
        ),
        "target": {
            "stand_id": stand_id, "ssh_target": ssh_target,
            "known_hosts_host": known_hosts_host,
            "pinned_host_key_evidence_sha256":
                contract["target"]["pinned_host_key_evidence"]["sha256"],
            "pinned_known_hosts_sha256":
                contract["target"]["pinned_known_hosts"]["sha256"],
            "transport_identity_sha256": identity_binding["sha256"],
        },
        "frozen_observation_ids": observations,
        "fixed_action_plan": effective,
        "supporting_observation_contract": contract_binding,
        "evidence_root": str(preflight_evidence_root.resolve()),
        "limits": limits, "role_collapse_acknowledged": True,
        "independent_review_claimed": False, "permissions": permissions,
        "automatic_transition": False, "retry_allowed": False,
        "stage18_authority": False,
    }
    authorization_path = destination / "authorization-v11.json"
    write_external_exclusive(authorization_path, canonical(authorization))
    envelope = {
        "schema_version": "cpu-prefetch-stage17-operational-evidence-envelope/14",
        "envelope_id": envelope_id, "input_id": "S17-EXT-001",
        "predecessor": {
            "graph_sha256": genesis["graph"]["sha256"],
            "catalog_sha256": genesis["catalog"]["sha256"],
            "genesis_sha256": genesis["genesis"]["genesis_sha256"],
            "resolution_schema_identity":
                "cpu-prefetch-stage17-external-input-resolution/1",
            "resolution_schema_sha256":
                genesis["version_hashes"]["resolution_schema_sha256"],
            "semantic_policy_v13_sha256": digest((repository_root / (
                "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v13.json"
            )).read_bytes()),
            "adr_0123_sha256": digest((repository_root / (
                "docs/decisions/0123-stage17-action-revalidation-schema-binding.md"
            )).read_bytes()),
        },
        "semantic_policy": {
            "path": policy_path.relative_to(repository_root).as_posix(),
            "size_bytes": len(policy_payload), "sha256": digest(policy_payload),
        },
        "semantic_verifier": {
            "verifier_id": "STAGE17-S17-EXT-001-SEMANTIC-VERIFIER",
            "verifier_version": "14",
        },
        "authorization": _repository_binding(
            repository_root, authorization_path,
            schema_identity="cpu-prefetch-stage17-read-only-preflight-authorization/11",
        ),
        "supporting_contract": contract_binding,
        "effective_action_plan": effective,
        "successor_action_plan": successor,
        "runtime_implementations": policy["implementations"],
        "stage18_authority": False,
    }
    envelope_path = destination / "envelope-v14.json"
    validate_schema(repository_root, contract_schema_relative, contract)
    validate_schema(
        repository_root,
        "config/schemas/stage17-read-only-preflight-authorization-v11.schema.json",
        authorization,
    )
    validate_schema(
        repository_root,
        "config/schemas/stage17-operational-evidence-envelope-v14.schema.json",
        envelope,
    )
    write_external_exclusive(envelope_path, canonical(envelope))
    return envelope_path


def _authority_from_file(
    path: pathlib.Path, *, repository_root: pathlib.Path,
    evidence_root: pathlib.Path,
) -> dict[str, Any]:
    document, payload = load_json(path)
    try:
        evidence_path = path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        try:
            evidence_path = path.resolve().relative_to(
                evidence_root.resolve()
            ).as_posix()
        except ValueError:
            # Action output roots are deliberately distinct from the append-only
            # operational root.  Import exact admitted authorization bytes before
            # journaling so the resolution never points at a mutable external
            # pathname.
            name = f"authorization-{digest(payload)}.json"
            root_fd = _root_fd(evidence_root)
            try:
                authorization_fd = _subdir(root_fd, "authorizations")
                try:
                    _write_exclusive_at(authorization_fd, name, payload)
                finally:
                    os.close(authorization_fd)
            finally:
                os.close(root_fd)
            evidence_path = f"authorizations/{name}"
    return {
        "authorization_id": document["authorization_id"],
        "evidence_path": evidence_path,
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
            _authority_from_file(
                authorization_file, repository_root=repository_root,
                evidence_root=evidence_root,
            )
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
    parser.add_argument("--synthetic-test-only", action="store_true",
                        help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command", required=True)
    initialize_parser = subparsers.add_parser("init")
    initialize_parser.add_argument(
        "--materialize-admission-root", action="store_true",
        help="copy the verified bundle into a read-only private admission root",
    )
    subparsers.add_parser("status")
    subparsers.add_parser("journal-path")
    request = subparsers.add_parser("author-request")
    request.add_argument("--action", required=True)
    request.add_argument("--action-inputs", type=pathlib.Path, required=True)
    request.add_argument("--request-id", required=True)
    request.add_argument("--session-id", required=True)
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
    manifest.add_argument("--artifact", action="append", default=[])
    manifest.add_argument(
        "--artifact-stdin", action="store_true",
        help=("read newline-delimited ROLE:ARTIFACT_ID=/absolute/path specs "
              "from bounded stdin"),
    )
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
    ext006.add_argument("--contract-id", required=True)
    ext006.add_argument("--output", type=pathlib.Path, required=True)
    ext001 = subparsers.add_parser("author-ext001")
    ext001.add_argument("--stand-id", required=True)
    ext001.add_argument("--ssh-target", required=True)
    ext001.add_argument("--known-hosts-host", required=True)
    ext001.add_argument("--pinned-host-public-key", type=pathlib.Path, required=True)
    ext001.add_argument("--pinned-known-hosts", type=pathlib.Path, required=True)
    ext001.add_argument("--transport-identity", type=pathlib.Path, required=True)
    ext001.add_argument("--bundle-root-locator", type=pathlib.Path, required=True)
    ext001.add_argument("--capture-id", required=True)
    ext001.add_argument("--captured-at-utc", required=True)
    ext001.add_argument("--preflight-evidence-root", type=pathlib.Path,
                        required=True)
    ext001.add_argument("--pre-marker-blocker", type=pathlib.Path)
    ext001.add_argument("--post-marker-blocker", type=pathlib.Path)
    ext001.add_argument("--action-revalidation-blocker", type=pathlib.Path)
    ext001.add_argument(
        "--no-predecessor-attestation", type=pathlib.Path,
        help=(
            "D-124 no-predecessor attestation (ADR-0124, PROPOSED); mutually "
            "exclusive with --pre-marker-blocker/--post-marker-blocker/"
            "--action-revalidation-blocker"
        ),
    )
    ext001.add_argument("--actor", required=True)
    ext001.add_argument("--issued-at-utc", required=True)
    ext001.add_argument("--expires-at-utc", required=True)
    ext001.add_argument("--authorization-id", required=True)
    ext001.add_argument("--attempt-id", required=True)
    ext001.add_argument("--contract-id", required=True)
    ext001.add_argument("--envelope-id", required=True)
    ext001.add_argument("--output-directory", type=pathlib.Path, required=True)
    execute = subparsers.add_parser("execute-action")
    execute.add_argument("--authorization", type=pathlib.Path, required=True)
    execute.add_argument("--signature", type=pathlib.Path, required=True)
    completion = subparsers.add_parser("derive-stage17-completion")
    completion.add_argument("--pilot-output-root", type=pathlib.Path,
                            required=True)
    completion.add_argument("--output", type=pathlib.Path, required=True)
    readiness = subparsers.add_parser("prepare-phase18-readiness")
    readiness.add_argument("--stage17-completion", type=pathlib.Path,
                           required=True)
    readiness.add_argument("--created-at-utc", required=True)
    readiness.add_argument("--output", type=pathlib.Path, required=True)
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
        if arguments.synthetic_test_only:
            require_synthetic_test_bundle(root)
        if arguments.command == "init":
            result, admission_root = initialize(
                root, evidence,
                materialize_bundle=arguments.materialize_admission_root,
            )
            print(
                "stage17-operational: PASS "
                f"initialized={result} admission_root={admission_root}"
            )
        elif arguments.command == "status":
            value = validate_journal(
                repository_root=root, evidence_root=evidence,
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
                as_of_utc=dt.datetime.now(dt.timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                ),
                allow_synthetic=arguments.synthetic_test_only,
            )
            print(json.dumps({
                "current_state": value.current_state,
                "resolutions": value.resolution_count,
                "transitions": value.transition_count,
                "missing_inputs": list(value.missing_input_ids),
                "pilot_ready": value.pilot_ready,
            }, sort_keys=True))
        elif arguments.command == "journal-path":
            print(latest_journal(evidence))
        elif arguments.command == "author-request":
            result = author_request(
                repository_root=root, evidence_root=evidence,
                action=arguments.action,
                action_inputs_path=arguments.action_inputs,
                request_id=arguments.request_id,
                session_id=arguments.session_id,
                authorization_id=arguments.authorization_id,
                attempt_id=arguments.attempt_id,
                output_root=arguments.output_root.resolve(),
                destination=arguments.output.resolve(),
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
                synthetic=arguments.synthetic_test_only,
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
                synthetic=arguments.synthetic_test_only,
            )
            print(f"stage17-operational: PASS unsigned_authorization={result}")
        elif arguments.command == "verify-signature":
            verify_phase_signature(
                repository_root=root, evidence_root=evidence,
                authorization=arguments.authorization.resolve(),
                signature=arguments.signature.resolve(),
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
                synthetic=arguments.synthetic_test_only,
            )
            print("stage17-operational: PASS signature=VERIFIED action=NOT_EXECUTED")
        elif arguments.command == "author-manifest":
            artifact_specs = list(arguments.artifact)
            if arguments.artifact_stdin:
                raw_specs = sys.stdin.buffer.read(64 * 1024 * 1024 + 1)
                if len(raw_specs) > 64 * 1024 * 1024:
                    raise OperationalCliError("artifact stdin exceeds 64 MiB")
                try:
                    decoded_specs = raw_specs.decode("utf-8").splitlines()
                except UnicodeDecodeError as exception:
                    raise OperationalCliError(
                        "artifact stdin must be UTF-8"
                    ) from exception
                if len(decoded_specs) > 200_000:
                    raise OperationalCliError("artifact stdin has too many records")
                if any(not item for item in decoded_specs):
                    raise OperationalCliError("artifact stdin contains an empty record")
                artifact_specs.extend(decoded_specs)
            if not artifact_specs:
                raise OperationalCliError("at least one artifact is required")
            result = author_operational_manifest(
                repository_root=root, evidence_root=evidence,
                input_id=arguments.input_id, manifest_id=arguments.manifest_id,
                stand_id=arguments.stand_id,
                artifact_specs=artifact_specs,
                destination=arguments.output.resolve(),
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
                synthetic=arguments.synthetic_test_only,
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
                contract_id=arguments.contract_id,
                destination=arguments.output.resolve(),
            )
            print(f"stage17-operational: PASS ext006_contract={result}")
        elif arguments.command == "author-ext001":
            if arguments.pilot_archive is None or arguments.pilot_sidecar is None:
                raise OperationalCliError(
                    "EXT001 requires --pilot-archive and --pilot-sidecar"
                )
            three_blockers = (
                arguments.pre_marker_blocker, arguments.post_marker_blocker,
                arguments.action_revalidation_blocker,
            )
            attestation_given = arguments.no_predecessor_attestation is not None
            if attestation_given and any(
                value is not None for value in three_blockers
            ):
                raise OperationalCliError(
                    "EXT001 cannot combine --no-predecessor-attestation with "
                    "any blocker-receipt flag"
                )
            if not attestation_given and not all(
                value is not None for value in three_blockers
            ):
                raise OperationalCliError(
                    "EXT001 requires either all three blocker-receipt flags "
                    "or --no-predecessor-attestation"
                )
            result = author_ext001(
                repository_root=root, evidence_root=evidence,
                stand_id=arguments.stand_id, ssh_target=arguments.ssh_target,
                known_hosts_host=arguments.known_hosts_host,
                pinned_host_public_key=arguments.pinned_host_public_key.resolve(),
                pinned_known_hosts=arguments.pinned_known_hosts.resolve(),
                transport_identity=arguments.transport_identity.resolve(),
                bundle_root_locator=arguments.bundle_root_locator.resolve(),
                pilot_archive=arguments.pilot_archive.resolve(),
                pilot_sidecar=arguments.pilot_sidecar.resolve(),
                capture_id=arguments.capture_id,
                captured_at_utc=arguments.captured_at_utc,
                preflight_evidence_root=arguments.preflight_evidence_root.resolve(),
                pre_marker_blocker=(
                    arguments.pre_marker_blocker.resolve()
                    if arguments.pre_marker_blocker is not None else None
                ),
                post_marker_blocker=(
                    arguments.post_marker_blocker.resolve()
                    if arguments.post_marker_blocker is not None else None
                ),
                action_revalidation_blocker=(
                    arguments.action_revalidation_blocker.resolve()
                    if arguments.action_revalidation_blocker is not None else None
                ),
                no_predecessor_attestation=(
                    arguments.no_predecessor_attestation.resolve()
                    if arguments.no_predecessor_attestation is not None else None
                ),
                actor=arguments.actor, issued_at_utc=arguments.issued_at_utc,
                expires_at_utc=arguments.expires_at_utc,
                authorization_id=arguments.authorization_id,
                attempt_id=arguments.attempt_id, contract_id=arguments.contract_id,
                envelope_id=arguments.envelope_id,
                destination_directory=arguments.output_directory.resolve(),
            )
            print(f"stage17-operational: PASS ext001_envelope={result}")
        elif arguments.command == "execute-action":
            result = controller.execute_once(
                repository_root=root,
                journal=latest_journal(evidence),
                journal_directory=evidence / "journal",
                operational_evidence_root=evidence,
                authorization_path=arguments.authorization.resolve(),
                signature_path=arguments.signature.resolve(),
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
                synthetic_test_only=arguments.synthetic_test_only,
            )
            print(
                "stage17-operational: PASS action=COMPLETED "
                f"completion={result.completion_path}"
            )
        elif arguments.command == "derive-stage17-completion":
            value = validate_journal(
                repository_root=root, evidence_root=evidence,
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
                as_of_utc=dt.datetime.now(dt.timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                ),
                allow_synthetic=arguments.synthetic_test_only,
            )
            completion_context = exit_machine.validate_stage17_completion(
                repository_root=root, operational_validation=value,
                pilot_output_root=arguments.pilot_output_root.resolve(),
                synthetic_test_only=arguments.synthetic_test_only,
            )
            write_external_exclusive(
                arguments.output.resolve(), completion_context.payload
            )
            print(
                "stage17-operational: PASS stage17_completion="
                f"{arguments.output.resolve()}"
            )
        elif arguments.command == "prepare-phase18-readiness":
            created = arguments.created_at_utc
            parse_utc(created)
            completion_document, completion_payload = load_json(
                arguments.stage17_completion.resolve()
            )
            validate_schema(
                root, "config/schemas/stage17-completion-v4.schema.json",
                completion_document,
            )
            completion_context = exit_machine.Stage17CompletionContext(
                completion_document, completion_payload, {}
            )
            document = exit_machine.phase18_readiness(
                repository_root=root, completion=completion_context,
                trust=None, created_at_utc=created,
            )
            write_external_exclusive(
                arguments.output.resolve(), exit_machine.canonical(document)
            )
            print(
                "stage17-operational: PASS phase18_readiness="
                f"{arguments.output.resolve()} state="
                "BLOCKED_EXTERNAL_PHASE18_TRUST_REQUIRED"
            )
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
                allow_synthetic=arguments.synthetic_test_only,
            )
            print(f"stage17-operational: PASS resolution_journal={result}")
        else:
            result = append_transition(
                repository_root=root, evidence_root=evidence,
                actor=arguments.actor, timestamp_utc=arguments.timestamp_utc,
                pilot_archive=arguments.pilot_archive,
                pilot_sidecar=arguments.pilot_sidecar,
                allow_synthetic=arguments.synthetic_test_only,
            )
            print(f"stage17-operational: PASS transition_journal={result}")
    except BaseException as exception:
        print(f"stage17-operational: FAIL: {exception}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
