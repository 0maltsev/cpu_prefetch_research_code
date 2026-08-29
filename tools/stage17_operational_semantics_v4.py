#!/usr/bin/env python3
"""Exact-byte, closed-role Stage 17 operational evidence admission v4.

The manifest never makes an artifact true.  It only locates immutable bytes.
Each JSON role is mapped to one repository-owned schema and then subjected to
role-specific lineage checks below.  Unknown roles and schemas fail closed.
"""

from __future__ import annotations

import collections
import copy
import datetime as dt
import hashlib
import json
import os
import pathlib
import stat
import subprocess
from dataclasses import dataclass
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

import stage17_output_registry_v4 as output_registry
import stage17_pilot_plan_v4 as pilot_plan_runtime
import stage17_pilot_candidate_artifact_v4 as release_verifier
import stage17_fixed_action_executor_v2 as snapshot_factory
import stage17_openssh_parent_snapshot_v1 as snapshot_broker


MANIFEST_SCHEMA = "config/schemas/stage17-operational-input-manifest-v4.schema.json"
ARTIFACT_SCHEMA = "config/schemas/stage17-operational-artifact-v4.schema.json"
TYPED_SCHEMA = "config/schemas/stage17-operational-typed-record-v4.schema.json"
AUTH_SCHEMA = "config/schemas/stage17-phase-action-authorization-v4.schema.json"
REQUEST_SCHEMA = "config/schemas/stage17-fixed-action-request-v4.schema.json"
ATTEMPT_SCHEMA = "config/schemas/stage17-phase-action-attempt-v4.schema.json"
RESULT_SCHEMA = "config/schemas/stage17-phase-action-result-v4.schema.json"
COMPLETION_SCHEMA = "config/schemas/stage17-phase-action-completion-v4.schema.json"
SUPPORTED_ACTIONS = (
    "Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c", "STAGE17-BLINDED-PILOT",
)


class OperationalSemanticError(ValueError):
    pass


_VALIDATOR_CACHE: dict[tuple[str, str, str], Draft202012Validator] = {}


@dataclass(frozen=True)
class Artifact:
    role: str
    path: pathlib.Path
    payload: bytes | None
    size_bytes: int
    sha256: str
    document: dict[str, Any] | None
    reference: dict[str, Any]


ROLE_SCHEMA: dict[str, str | None] = {
    "PREFLIGHT_ATTEMPT": "config/schemas/stage17-read-only-preflight-attempt-v7.schema.json",
    "PREFLIGHT_OBSERVATION_RECEIPT": "config/schemas/stage17-read-only-preflight-observation-receipt-v5.schema.json",
    "PREFLIGHT_COMPLETION": "config/schemas/stage17-read-only-preflight-completion-v5.schema.json",
    "PREFLIGHT_STDOUT": None,
    "PREFLIGHT_STDERR": None,
    "RUNTIME_WORKER_BINARY": None,
    "TRUST_ALLOWED_SIGNERS": None,
    "RUNTIME_RELEASE_PROVENANCE": "config/schemas/stage17-runtime-release-provenance-v4.schema.json",
    "RUNTIME_IDENTITY": TYPED_SCHEMA,
    "TRUST_ANCHOR": TYPED_SCHEMA,
    "OWNER_ACCEPTANCE": TYPED_SCHEMA,
    "QUALIFICATION_EVIDENCE": "config/schemas/qualification-evidence-v1.schema.json",
    "PLATFORM_MANIFEST": "protocol/2.0.0-pre.3/handoff/schemas/platform.schema.json",
    "HARDWARE_PREFETCH_QUALIFICATION": "config/schemas/hardware-prefetch-qualification-v1.schema.json",
    **{role: TYPED_SCHEMA for role in (
        "QUALIFICATION_NEAR_FAR", "QUALIFICATION_CLOCK",
        "QUALIFICATION_ATOMICS_LAYOUT", "QUALIFICATION_AFFINITY_MIGRATION",
        "QUALIFICATION_NUMA_PAGES", "QUALIFICATION_STORAGE_RECOVERY",
        "QUALIFICATION_HARDWARE_PREFETCH", "QUALIFICATION_STAND_PRESTATE",
        "QUALIFICATION_Q15_COLLECTOR", "STORAGE_BUDGET", "CUSTODY_DOMAIN",
        "COPY_LEDGER", "RECOVERY_TEST", "PILOT_PLATFORM_MEASUREMENTS",
    )},
    **{role: AUTH_SCHEMA for role in (
        "Q15_R_AUTHORIZATION", "Q15_W_AUTHORIZATION", "Q16A_AUTHORIZATION",
        "Q16B_AUTHORIZATION", "Q16C_AUTHORIZATION", "PILOT_AUTHORIZATION",
    )},
    **{role: REQUEST_SCHEMA for role in (
        "Q15_R_REQUEST", "Q15_W_REQUEST", "Q16A_REQUEST", "Q16B_REQUEST",
        "Q16C_REQUEST", "PILOT_REQUEST",
    )},
    **{role: ATTEMPT_SCHEMA for role in (
        "Q15_R_ATTEMPT", "Q15_W_ATTEMPT", "Q16A_ATTEMPT", "Q16B_ATTEMPT",
        "Q16C_ATTEMPT",
    )},
    **{role: RESULT_SCHEMA for role in (
        "Q15_R_RESULT", "Q15_W_RESULT", "Q16A_RESULT", "Q16B_RESULT",
        "Q16C_RESULT",
    )},
    **{role: COMPLETION_SCHEMA for role in (
        "Q15_R_COMPLETION", "Q15_W_COMPLETION", "Q16A_COMPLETION",
        "Q16B_COMPLETION", "Q16C_COMPLETION",
    )},
    "Q15_R_READ_ONLY_PRESTATE": "config/schemas/stage17-q15-r-output-v3.schema.json",
    "Q15_R_SESSION_WAITING": "config/schemas/stage17-q15-session-waiting-v1.schema.json",
    "Q15_W_TRANSACTION": "config/schemas/stage17-q15-w-output-v3.schema.json",
    "Q16A_RING_DISTANCE_CAPTURE": "config/schemas/stage17-q16a-output-v3.schema.json",
    "Q16A_RING_DEMAND_TRACE": "config/schemas/stage17-q16a-trace-v3.schema.json",
    "JOIN_AUDIT": "config/schemas/stage17-join-audit-v3.schema.json",
    "PAGE_RESIDENCY_PROVENANCE": "config/schemas/stage17-page-residency-v3.schema.json",
    "CALIBRATION_FREEZE": "config/schemas/calibration-freeze-v1.schema.json",
    "PILOT_PLAN_V4": "config/schemas/stage17-pilot-plan-v4.schema.json",
    "PILOT_SIGNATURE": None,
    "Q15_R_SIGNATURE": None,
    "Q15_W_SIGNATURE": None,
    "Q16A_SIGNATURE": None,
    "Q16B_SIGNATURE": None,
    "Q16C_SIGNATURE": None,
    "PRODUCER_RAW_OBSERVATIONS": None,
    "CONSUMER_RAW_OBSERVATIONS": None,
    "JOINED_RAW_OBSERVATIONS": None,
    # The imported envelopes and phase-integrity records are validated by the
    # C++ producer and exact reconciliation path; their cross-record fields are
    # checked against the result registry below.
    "PRODUCER_RAW_ENVELOPE": None,
    "CONSUMER_RAW_ENVELOPE": None,
    "JOINED_RAW_ENVELOPE": None,
    "PHASE_INTEGRITY": "config/schemas/phase-integrity-report-v2.schema.json",
    "Q16B_SERVICE_RATE_CAPTURE": "config/schemas/stage17-run-output-v3.schema.json",
    "Q16C_ZERO_LOSS_FEASIBILITY_CAPTURE": "config/schemas/stage17-run-output-v3.schema.json",
    "STAGE17_CALIBRATION_HARDWARE_STATE": "config/schemas/stage17-calibration-hardware-state-v1.schema.json",
    "STAGE17_PILOT_RUN_ATTEMPT": "config/schemas/stage17-pilot-run-attempt-v1.schema.json",
    "STAGE17_PILOT_RUN_COMPLETION": "config/schemas/stage17-pilot-run-completion-v1.schema.json",
    "STAGE17_PILOT_RUN_FAILURE": "config/schemas/stage17-pilot-run-failure-v1.schema.json",
    "STAGE17_PILOT_SESSION_COMPLETION": "config/schemas/stage17-pilot-session-completion-v1.schema.json",
    "STAGE17_PILOT_HARDWARE_STATE": "config/schemas/stage17-pilot-hardware-state-v2.schema.json",
    "STAGE17_BLINDED_PILOT_RUN": "config/schemas/stage17-run-output-v3.schema.json",
    "SEALED_PILOT_ARTIFACT_MANIFEST": "config/schemas/stage17-sealed-pilot-artifact-manifest-v4.schema.json",
}

SIGNATURE_ROLES = frozenset({
    "Q15_R_SIGNATURE", "Q15_W_SIGNATURE", "Q16A_SIGNATURE", "Q16B_SIGNATURE",
    "Q16C_SIGNATURE", "PILOT_SIGNATURE",
})
RAW_ROLES = frozenset({
    "PREFLIGHT_STDOUT", "PREFLIGHT_STDERR", "RUNTIME_WORKER_BINARY",
    "TRUST_ALLOWED_SIGNERS", "PRODUCER_RAW_OBSERVATIONS",
    "CONSUMER_RAW_OBSERVATIONS", "JOINED_RAW_OBSERVATIONS",
})
STREAMING_OBSERVATION_ROLES = frozenset({
    "PRODUCER_RAW_OBSERVATIONS", "CONSUMER_RAW_OBSERVATIONS",
    "JOINED_RAW_OBSERVATIONS",
})
LOGICAL_ENVELOPE_ROLES = frozenset({
    "PRODUCER_RAW_ENVELOPE", "CONSUMER_RAW_ENVELOPE", "JOINED_RAW_ENVELOPE",
})


MEASUREMENT_KEYS: dict[str, frozenset[str]] = {
    "RUNTIME_IDENTITY": frozenset({
        "bundle_profile", "source_revision", "bundle_manifest_sha256",
        "sha256s_sha256", "sbom_sha256", "inventory_sha256", "worker_path",
        "worker_size_bytes", "worker_sha256", "worker_role", "runtime_profile",
        "supported_actions", "full_bundle_verifier_sha256",
    }),
    "TRUST_ANCHOR": frozenset({
        "allowed_signers_path", "allowed_signers_size_bytes",
        "allowed_signers_sha256", "principal", "sshsig_namespace",
        "signer_role", "reviewer_role", "stand_anchor_sha256", "stand_id",
    }),
    "OWNER_ACCEPTANCE": frozenset({
        "ext002_resolution_id", "ext002_resolution_sha256",
        "runtime_record_sha256", "trust_record_sha256",
        "runtime_release_provenance_sha256", "distinct_auditor",
        "independent_review", "role_collapse_accepted",
    }),
    "PILOT_PLATFORM_MEASUREMENTS": frozenset({
        "platform_manifest_sha256", "q15_r_result_sha256",
        "topology_evidence", "cache_capacity_evidence",
    }),
    "QUALIFICATION_NEAR_FAR": frozenset({
        "near_producer_cpu", "near_consumer_cpu", "far_producer_cpu",
        "far_consumer_cpu", "topology_sha256",
    }),
    "QUALIFICATION_CLOCK": frozenset({
        "clock_id", "per_core_samples", "cross_core_samples",
        "maximum_regressions", "qualification_sha256",
    }),
    "QUALIFICATION_ATOMICS_LAYOUT": frozenset({
        "pointer_width", "pointer_alignment", "termination_width",
        "cache_line_bytes", "layout_sha256",
    }),
    "QUALIFICATION_AFFINITY_MIGRATION": frozenset({
        "producer_cpu", "consumer_cpu", "sample_count", "migration_count",
        "readback_sha256",
    }),
    "QUALIFICATION_NUMA_PAGES": frozenset({
        "region_count", "page_count", "wrong_node_pages", "residency_sha256",
    }),
    "QUALIFICATION_STORAGE_RECOVERY": frozenset({
        "capacity_bytes", "recovery_test_id", "recovery_artifact_sha256",
    }),
    "QUALIFICATION_HARDWARE_PREFETCH": frozenset({
        "mapping_id", "prestate_sha256", "readback_sha256",
        "restoration_sha256",
    }),
    "QUALIFICATION_STAND_PRESTATE": frozenset({
        "stand_id", "inventory_sha256", "capture_id",
    }),
    "QUALIFICATION_Q15_COLLECTOR": frozenset({
        "collector_count", "collector_manifest_sha256",
        "qualification_archive_sha256",
    }),
    "STORAGE_BUDGET": frozenset({
        "planned_bytes", "available_bytes", "temporary_copies",
        "durable_copies", "budget_formula_id", "pilot_plan_sha256",
    }),
    "CUSTODY_DOMAIN": frozenset({
        "domain_id", "locator", "owner_uid", "mode", "independent_domain_id",
    }),
    "COPY_LEDGER": frozenset({
        "source_locator", "source_sha256", "primary_copy_locator",
        "primary_copy_sha256", "secondary_copy_locator",
        "secondary_copy_sha256", "transfer_verified_at_utc",
    }),
    "RECOVERY_TEST": frozenset({
        "failure_fixture_locator", "failure_fixture_sha256", "restored_locator",
        "restored_sha256", "recovery_procedure_id", "result_code",
    }),
}


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load(path: pathlib.Path, payload: bytes | None = None) \
        -> tuple[dict[str, Any], bytes]:
    if payload is None:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 64 * 1024 * 1024:
                raise OperationalSemanticError(f"unsafe/unbounded JSON file: {path}")
            payload = os.pread(descriptor, metadata.st_size + 1, 0)
            if len(payload) != metadata.st_size:
                raise OperationalSemanticError(f"JSON bytes changed while read: {path}")
        finally:
            os.close(descriptor)
    document = json.loads(payload)
    if not isinstance(document, dict):
        raise OperationalSemanticError(f"JSON root is not an object: {path}")
    return document, payload


def _schema(root: pathlib.Path, relative: str,
            pinned: Mapping[str, bytes]) -> tuple[dict[str, Any], bytes]:
    payload = pinned.get(relative)
    if payload is None:
        raise OperationalSemanticError(f"schema is not policy-pinned: {relative}")
    return load(root / relative, payload)


def _validate(root: pathlib.Path, document: dict[str, Any], relative: str,
              label: str, pinned: Mapping[str, bytes]) -> None:
    schema, schema_payload = _schema(root, relative, pinned)
    artifact_payload = pinned.get(ARTIFACT_SCHEMA, b"") \
        if relative == MANIFEST_SCHEMA else b""
    key = (relative, sha(schema_payload), sha(artifact_payload))
    validator = _VALIDATOR_CACHE.get(key)
    if validator is None:
        Draft202012Validator.check_schema(schema)
        registry = Registry()
        if relative == MANIFEST_SCHEMA:
            artifact, _ = _schema(root, ARTIFACT_SCHEMA, pinned)
            resource = Resource.from_contents(artifact)
            registry = registry.with_resource(
                "stage17-operational-artifact-v4.schema.json", resource
            ).with_resource(
                "urn:cpu-prefetch:stage17:operational-input-manifest:stage17-operational-artifact-v4.schema.json",
                resource,
            )
        validator = Draft202012Validator(
            schema, registry=registry, format_checker=FormatChecker()
        )
        _VALIDATOR_CACHE[key] = validator
    errors = sorted(
        validator.iter_errors(document),
        key=lambda item: tuple(item.path),
    )
    if errors:
        where = "/".join(str(item) for item in errors[0].path) or "<root>"
        raise OperationalSemanticError(
            f"{label} schema error at {where}: {errors[0].message}"
        )


def _artifact_content(
    manifest_path: pathlib.Path, locator: Any, *, load: bool,
    expected_size: int,
) -> tuple[pathlib.Path, bytes | None, int, str]:
    if not isinstance(locator, str):
        raise OperationalSemanticError("artifact locator is absent")
    relative = pathlib.PurePosixPath(locator)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise OperationalSemanticError("artifact locator is not manifest-relative")
    descriptor = os.open(
        manifest_path.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        for index, part in enumerate(relative.parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
            if index + 1 < len(relative.parts):
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode)
                or metadata.st_size != expected_size
                or (load and metadata.st_size > 64 * 1024 * 1024)):
            raise OperationalSemanticError(
                "artifact size/type differs from its bounded contract"
            )
        digest = hashlib.sha256()
        chunks: list[bytes] | None = [] if load else None
        offset = 0
        while offset != metadata.st_size:
            chunk = os.pread(
                descriptor, min(1024 * 1024, metadata.st_size - offset), offset
            )
            if not chunk:
                raise OperationalSemanticError(
                    "artifact changed during streaming verification"
                )
            digest.update(chunk)
            if chunks is not None:
                chunks.append(chunk)
            offset += len(chunk)
        after = os.fstat(descriptor)
        if (after.st_dev, after.st_ino, after.st_size) != (
            metadata.st_dev, metadata.st_ino, metadata.st_size
        ):
            raise OperationalSemanticError(
                "artifact identity changed during streaming verification"
            )
        payload = b"".join(chunks) if chunks is not None else None
        return (
            manifest_path.parent.joinpath(*relative.parts), payload,
            metadata.st_size, digest.hexdigest(),
        )
    except OSError as exception:
        raise OperationalSemanticError("artifact locator cannot be opened safely") from exception
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _read_artifacts(root: pathlib.Path, manifest_path: pathlib.Path,
                    manifest: dict[str, Any],
                    pinned: Mapping[str, bytes]) -> list[Artifact]:
    result: list[Artifact] = []
    ids: set[str] = set()
    paths: set[pathlib.Path] = set()
    for reference in manifest["artifacts"]:
        role = reference["role"]
        if role not in ROLE_SCHEMA:
            raise OperationalSemanticError(f"unknown production artifact role: {role}")
        if reference["artifact_id"] in ids:
            raise OperationalSemanticError("duplicate artifact ID")
        ids.add(reference["artifact_id"])
        streaming = role in STREAMING_OBSERVATION_ROLES
        path, payload, size_bytes, artifact_sha256 = _artifact_content(
            manifest_path, reference["locator"], load=not streaming,
            expected_size=reference["size_bytes"],
        )
        if path in paths:
            raise OperationalSemanticError("duplicate artifact locator")
        paths.add(path)
        if artifact_sha256 != reference["sha256"]:
            raise OperationalSemanticError(f"artifact bytes drifted: {role}")
        expected_schema = ROLE_SCHEMA[role]
        document: dict[str, Any] | None = None
        if expected_schema is None:
            if role in LOGICAL_ENVELOPE_ROLES:
                if (reference["schema_identity"] != "2.0.0-pre.3"
                        or reference["schema_binding"] is not None
                        or reference["media_type"] != "application/json"):
                    raise OperationalSemanticError(
                        f"logical envelope contract drifted: {role}"
                    )
                assert payload is not None
                document = json.loads(payload)
                if not isinstance(document, dict):
                    raise OperationalSemanticError(
                        f"logical envelope JSON root drifted: {role}"
                    )
                result.append(Artifact(
                    role, path, payload, size_bytes, artifact_sha256,
                    document, reference,
                ))
                continue
            if streaming:
                if (reference["schema_identity"] != output_registry.RAW_SCHEMA
                        or reference["schema_binding"] is not None
                        or reference["media_type"] != "application/octet-stream"):
                    raise OperationalSemanticError(
                        f"raw observation physical contract drifted: {role}"
                    )
            elif (reference["schema_identity"] is not None
                  or reference["schema_binding"] is not None):
                raise OperationalSemanticError(f"untyped artifact claims a schema: {role}")
            expected_media = (
                "application/sshsig" if role in SIGNATURE_ROLES
                else "application/octet-stream"
            )
            if reference["media_type"] != expected_media:
                raise OperationalSemanticError(f"untyped artifact media drifted: {role}")
        else:
            schema_document, schema_payload = _schema(root, expected_schema, pinned)
            binding = {
                "path": expected_schema, "size_bytes": len(schema_payload),
                "sha256": sha(schema_payload),
            }
            if reference["schema_binding"] != binding:
                raise OperationalSemanticError(f"schema byte binding drifted: {role}")
            assert payload is not None
            document = json.loads(payload)
            if not isinstance(document, dict):
                raise OperationalSemanticError(f"JSON artifact root is not object: {role}")
            _validate(root, document, expected_schema, role, pinned)
            if reference["schema_identity"] != document.get("schema_version"):
                raise OperationalSemanticError(f"schema identity drifted: {role}")
            if expected_schema == TYPED_SCHEMA:
                if document["record_role"] != role:
                    raise OperationalSemanticError(f"typed record role mismatch: {role}")
                expected_keys = MEASUREMENT_KEYS[role]
                if frozenset(document["measurements"]) != expected_keys:
                    raise OperationalSemanticError(f"typed fact family drifted: {role}")
                if all(isinstance(item, bool) for item in document["measurements"].values()):
                    raise OperationalSemanticError(f"boolean-only impostor rejected: {role}")
        result.append(Artifact(
            role, path, payload, size_bytes, artifact_sha256,
            document, reference,
        ))
    return result


def _one(artifacts: list[Artifact], role: str) -> Artifact:
    matches = [item for item in artifacts if item.role == role]
    if len(matches) != 1:
        raise OperationalSemanticError(f"expected exactly one {role}")
    return matches[0]


def _parse_utc(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise OperationalSemanticError("authority timestamp is not UTC")
    try:
        return dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exception:
        raise OperationalSemanticError("authority timestamp is malformed") from exception


def _resolution_bindings(admitted: Mapping[str, Any],
                         ids: tuple[str, ...]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for input_id in ids:
        resolution = admitted.get(input_id)
        if resolution is None:
            raise OperationalSemanticError(f"missing predecessor: {input_id}")
        result.append({
            "input_id": input_id, "resolution_id": resolution.resolution_id,
            "sha256": resolution.sha256,
        })
    return result


def _artifact_index(artifacts: list[Artifact], admitted: Mapping[str, Any]) \
        -> dict[str, dict[str, Any]]:
    known = {
        item.reference["artifact_id"]: (item.size_bytes, item.sha256)
        for item in artifacts
    }
    for resolution in admitted.values():
        known[resolution.resolution_id] = (
            pathlib.Path(resolution.path).stat().st_size, resolution.sha256
        )
        context = resolution.semantic_context
        if isinstance(context, dict):
            for artifact_id, binding in context.get("artifact_index", {}).items():
                known.setdefault(
                    artifact_id, (binding["size_bytes"], binding["sha256"])
                )
    for artifact in artifacts:
        for lineage in artifact.reference["lineage"]:
            observed = known.get(lineage["id"])
            if observed is None or observed[1] != lineage["sha256"]:
                raise OperationalSemanticError(
                    f"unknown/drifted artifact lineage: {artifact.role}"
                )
        if artifact.document is not None and artifact.document.get(
            "schema_version"
        ) in {
            "cpu-prefetch-stage17-operational-typed-record/3",
            "cpu-prefetch-stage17-operational-typed-record/4",
        }:
            for source in artifact.document["source_bindings"]:
                if known.get(source["id"]) != (
                    source["size_bytes"], source["sha256"]
                ):
                    raise OperationalSemanticError(
                        f"typed source binding drifted: {artifact.role}"
                    )
    current_ids = {item.reference["artifact_id"] for item in artifacts}
    return {
        artifact_id: {"size_bytes": size, "sha256": digest}
        for artifact_id, (size, digest) in known.items()
        if artifact_id in current_ids
    }


def verify_sshsig(*, authorization: Artifact, signature: Artifact,
                  trust_record: dict[str, Any]) -> None:
    values = trust_record["measurements"]
    allowed = pathlib.Path(values["allowed_signers_path"])
    metadata = allowed.lstat()
    if (stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_mode & 0o022):
        raise OperationalSemanticError("admitted allowed-signers locator is unsafe")
    payload = allowed.read_bytes()
    if (len(payload), sha(payload)) != (
        values["allowed_signers_size_bytes"], values["allowed_signers_sha256"]
    ):
        raise OperationalSemanticError("admitted allowed-signers bytes drifted")
    allowed_snapshot = None
    signature_snapshot = None
    try:
        allowed_snapshot = snapshot_broker.pin_bound_input({
            "locator": str(allowed), "size_bytes": len(payload),
            "sha256": sha(payload),
        }, "STAGE17_ALLOWED_SIGNERS")
        signature_snapshot = snapshot_factory._pin_generated(
            signature.payload, "STAGE17_SSHSIG_SIGNATURE"
        )
        completed = subprocess.run(
            ["/usr/bin/ssh-keygen", "-Y", "verify", "-f",
             allowed_snapshot.locator, "-I", values["principal"], "-n",
             values["sshsig_namespace"], "-s", signature_snapshot.locator],
            input=authorization.payload, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False, timeout=10,
        )
    except (snapshot_broker.SnapshotError,
            snapshot_factory.FixedActionExecutionError) as exception:
        raise OperationalSemanticError(
            "SSHSIG trust/signature bytes could not be pinned"
        ) from exception
    finally:
        if signature_snapshot is not None:
            signature_snapshot.close()
        if allowed_snapshot is not None:
            allowed_snapshot.close()
    if completed.returncode != 0:
        raise OperationalSemanticError("detached SSHSIG is not rooted in EXT002/003")


def _verify_extracted_release(
    root: pathlib.Path, provenance: Artifact, runtime: Artifact,
    worker: Artifact,
) -> release_verifier.ExtractedReleaseContext:
    assert provenance.document is not None and runtime.document is not None
    try:
        context = release_verifier.verify_extracted_release_receipt_v4(
            repository_root=root, receipt=provenance.document
        )
    except release_verifier.ArtifactError as exception:
        raise OperationalSemanticError(str(exception)) from exception
    values = runtime.document["measurements"]
    expected = {
        "bundle_profile": context.bundle_profile,
        "source_revision": context.source_revision,
        "bundle_manifest_sha256": context.manifest_sha256,
        "sha256s_sha256": context.sha256s_sha256,
        "sbom_sha256": context.sbom_sha256,
        "inventory_sha256": context.inventory_sha256,
        "worker_path": str(context.worker_path),
        "worker_size_bytes": context.worker_size_bytes,
        "worker_sha256": context.worker_sha256,
        "worker_role": context.worker_role,
        "runtime_profile": context.runtime_profile,
        "supported_actions": list(context.supported_actions),
        "full_bundle_verifier_sha256": context.full_verifier_sha256,
    }
    if values != expected:
        raise OperationalSemanticError("runtime identity differs from clean release bytes")
    if (worker.path.resolve() != context.worker_path.resolve()
            or len(worker.payload) != context.worker_size_bytes
            or sha(worker.payload) != context.worker_sha256):
        raise OperationalSemanticError("observed worker differs from clean release worker")
    return context


ACTION_PREFIX = {
    "Q15-R": "Q15_R", "Q15-W": "Q15_W", "Q16a": "Q16A",
    "Q16b": "Q16B", "Q16c": "Q16C",
}


def _phase_family(
    *, root: pathlib.Path, artifacts: list[Artifact], action_id: str,
    trust: dict[str, Any], expected_predecessors: list[dict[str, str]],
    synthetic_test_only: bool,
) -> dict[str, Any]:
    prefix = ACTION_PREFIX[action_id]
    authorization = _one(artifacts, prefix + "_AUTHORIZATION")
    signature = _one(artifacts, prefix + "_SIGNATURE")
    request = _one(artifacts, prefix + "_REQUEST")
    attempt = _one(artifacts, prefix + "_ATTEMPT")
    result = _one(artifacts, prefix + "_RESULT")
    completion = None if action_id == "Q15-R" else _one(
        artifacts, prefix + "_COMPLETION"
    )
    waiting = _one(artifacts, "Q15_R_SESSION_WAITING") \
        if action_id == "Q15-R" else None
    typed = (authorization, request, attempt, result) + (
        (waiting,) if waiting is not None else (completion,)
    )
    assert all(item is not None and item.document is not None for item in typed)
    verify_sshsig(authorization=authorization, signature=signature,
                  trust_record=trust)
    auth, req, att, res = (
        item.document for item in (authorization, request, attempt, result)
    )
    comp = completion.document if completion is not None else None
    auth_hash, request_hash = sha(authorization.payload), sha(request.payload)
    if (auth["action_id"] != action_id or req["action_id"] != action_id
            or att["action_id"] != action_id or res["action_id"] != action_id
            or (comp is not None and comp["action_id"] != action_id)):
        raise OperationalSemanticError("phase action identity drifted")
    if (not _parse_utc(auth["issued_at_utc"]) < _parse_utc(auth["expires_at_utc"])
            or _parse_utc(auth["expires_at_utc"]) - _parse_utc(auth["issued_at_utc"])
            > dt.timedelta(seconds=1800)):
        raise OperationalSemanticError("phase authorization lifetime drifted")
    if (auth["predecessor_resolutions"] != expected_predecessors
            or req["predecessor_resolutions"] != expected_predecessors):
        raise OperationalSemanticError("phase predecessor lineage drifted")
    if auth["request_binding"] != {
        "path": str(request.path), "size_bytes": len(request.payload),
        "sha256": request_hash,
    }:
        raise OperationalSemanticError("authorization does not bind exact request bytes")
    if (req["authorization_id"] != auth["authorization_id"]
            or req["synthetic_test_only"] is not synthetic_test_only
            or att["authorization_sha256"] != auth_hash
            or att["request_sha256"] != request_hash
            or res["authorization_sha256"] != auth_hash
            or res["request_sha256"] != request_hash
            or res["attempt_id"] != att["attempt_id"]
            or (comp is not None and (
                comp["authorization_sha256"] != auth_hash
                or comp["request_sha256"] != request_hash
                or comp["attempt_id"] != att["attempt_id"]
                or not comp["leader_reaped"]
                or not comp["process_group_gone"]
            ))):
        raise OperationalSemanticError("phase attempt/result/completion lineage drifted")
    if waiting is not None:
        wait = waiting.document
        assert wait is not None
        if (wait["session_id"] != req["action_inputs"]["session_id"]
                or wait["q15_r_request_sha256"] != request_hash
                or wait["q15_r_result_sha256"] != sha(result.payload)
                or wait["state"] != "H0_SEALED_WAITING_FOR_Q15_W"
                or not wait["same_buffer_retained"]):
            raise OperationalSemanticError("Q15-R waiting/session lineage drifted")
    registry = output_registry.pin_registry(root)
    output_directory = result.path.parent
    descriptor = os.open(
        output_directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    try:
        output_registry.validate_worker_result(
            registry=registry, directory_fd=descriptor, result=res, request=req,
            authorization_sha256=auth_hash,
            synthetic_test_only=synthetic_test_only,
        )
    except output_registry.OutputAdmissionError as exception:
        raise OperationalSemanticError(str(exception)) from exception
    finally:
        os.close(descriptor)
    by_path: dict[pathlib.Path, Artifact] = {}
    for item in artifacts:
        if item.path in by_path:
            raise OperationalSemanticError("action manifest path is duplicated")
        by_path[item.path] = item
    for binding in res["artifacts"]:
        match = by_path.get(result.path.parent / binding["file_name"])
        if (match is None or match.role != binding["role"]
                or match.reference["size_bytes"] != binding["size_bytes"]
                or match.reference["sha256"] != binding["sha256"]
                or match.reference["schema_identity"]
                != binding["schema_identity"]):
            raise OperationalSemanticError(
                "action manifest does not list exact worker output: "
                f"action={action_id} file={binding['file_name']} "
                f"expected_role={binding['role']} "
                f"observed={match.reference if match is not None else None}"
            )
    if action_id == "Q15-W" and (
        not res["restoration_verified"] or res["quarantined"]
        or not comp["restoration_verified"]
    ):
        raise OperationalSemanticError("Q15-W lacks verified restoration")
    return {
        "authorization": auth, "authorization_path": authorization.path,
        "authorization_sha256": auth_hash, "request": req,
        "request_path": request.path, "request_sha256": request_hash,
        "attempt": att, "attempt_sha256": sha(attempt.payload),
        "result": res, "result_sha256": sha(result.payload),
        "completion": comp,
        "completion_sha256": sha(completion.payload) if completion else None,
        "waiting": waiting.document if waiting else None,
        "waiting_sha256": sha(waiting.payload) if waiting else None,
    }


EXPECTED_ROLES: dict[str, collections.Counter[str]] = {
    "S17-EXT-002": collections.Counter({
        "PREFLIGHT_ATTEMPT": 1, "PREFLIGHT_OBSERVATION_RECEIPT": 6,
        "PREFLIGHT_STDOUT": 6, "PREFLIGHT_STDERR": 6,
        "PREFLIGHT_COMPLETION": 1, "RUNTIME_IDENTITY": 1,
        "RUNTIME_WORKER_BINARY": 1, "RUNTIME_RELEASE_PROVENANCE": 1,
        "TRUST_ANCHOR": 1, "TRUST_ALLOWED_SIGNERS": 1,
    }),
    "S17-EXT-003": collections.Counter({"OWNER_ACCEPTANCE": 1}),
    "S17-EXT-004": collections.Counter({
        "Q15_R_AUTHORIZATION": 1, "Q15_R_SIGNATURE": 1,
        "Q15_R_REQUEST": 1, "Q15_R_ATTEMPT": 1, "Q15_R_RESULT": 1,
        "Q15_R_SESSION_WAITING": 1, "Q15_R_READ_ONLY_PRESTATE": 1,
        "QUALIFICATION_EVIDENCE": 5, "PLATFORM_MANIFEST": 1,
        "HARDWARE_PREFETCH_QUALIFICATION": 1,
        "PILOT_PLATFORM_MEASUREMENTS": 1,
    }),
    "S17-EXT-005": collections.Counter({
        "Q15_W_AUTHORIZATION": 1, "Q15_W_SIGNATURE": 1,
        "Q15_W_REQUEST": 1, "Q15_W_ATTEMPT": 1, "Q15_W_RESULT": 1,
        "Q15_W_COMPLETION": 1, "Q15_W_TRANSACTION": 1,
    }),
    "S17-EXT-007": collections.Counter({
        "Q16A_AUTHORIZATION": 1, "Q16A_SIGNATURE": 1, "Q16A_REQUEST": 1,
        "Q16A_ATTEMPT": 1, "Q16A_RESULT": 1, "Q16A_COMPLETION": 1,
        "Q16B_AUTHORIZATION": 1, "Q16B_SIGNATURE": 1, "Q16B_REQUEST": 1,
        "Q16B_ATTEMPT": 1, "Q16B_RESULT": 1, "Q16B_COMPLETION": 1,
        "Q16C_AUTHORIZATION": 1, "Q16C_SIGNATURE": 1,
        "Q16C_REQUEST": 1, "Q16C_ATTEMPT": 1, "Q16C_RESULT": 1,
        "Q16C_COMPLETION": 1, "CALIBRATION_FREEZE": 1,
    }),
    "S17-EXT-008": collections.Counter({"PILOT_PLAN_V4": 1}),
    "S17-EXT-009": collections.Counter({
        "STORAGE_BUDGET": 1, "CUSTODY_DOMAIN": 2, "COPY_LEDGER": 1,
        "RECOVERY_TEST": 1,
    }),
    "S17-EXT-010": collections.Counter({
        "PILOT_AUTHORIZATION": 1, "PILOT_SIGNATURE": 1, "PILOT_REQUEST": 1,
    }),
}


def _validate_preflight(
    artifacts: list[Artifact], ext1: Any,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    if not isinstance(ext1.semantic_context, dict):
        raise OperationalSemanticError("EXT002 lacks admitted EXT001 context")
    attempt = _one(artifacts, "PREFLIGHT_ATTEMPT").document
    completion = _one(artifacts, "PREFLIGHT_COMPLETION").document
    runtime = _one(artifacts, "RUNTIME_IDENTITY").document
    trust = _one(artifacts, "TRUST_ANCHOR").document
    assert attempt and completion and runtime and trust
    receipts = [
        item.document for item in artifacts
        if item.role == "PREFLIGHT_OBSERVATION_RECEIPT"
    ]
    if any(item is None for item in receipts):
        raise OperationalSemanticError("preflight receipt family is malformed")
    receipts.sort(key=lambda item: item["ordinal"])
    ids = [item["observation_id"] for item in receipts]
    expected_ids = list(
        ext1.semantic_context["authorization"]["frozen_observation_ids"]
        if "authorization" in ext1.semantic_context
        else ext1.authorization_document["frozen_observation_ids"]
    )
    if (ids != expected_ids or [item["ordinal"] for item in receipts] != list(range(1, 7))
            or any(item["returncode"] != 0 for item in receipts)
            or [item["observation_id"] for item in attempt["rendered_programs"]]
            != expected_ids
            or completion["completed_observation_ids"] != expected_ids
            or completion["receipt_sha256s"] != [
                sha(next(artifact.payload for artifact in artifacts
                         if artifact.document is item)) for item in receipts
            ]
            or not completion["all_leaders_reaped"]
            or not completion["all_process_groups_gone"]):
        raise OperationalSemanticError("preflight order/completeness/quiescence failed")
    if attempt["authorization_sha256"] != ext1.semantic_context["authorization_sha256"]:
        raise OperationalSemanticError("preflight attempt does not bind EXT001 authority")
    stdout = [item for item in artifacts if item.role == "PREFLIGHT_STDOUT"]
    stderr = [item for item in artifacts if item.role == "PREFLIGHT_STDERR"]
    for receipt in receipts:
        out = [item for item in stdout if sha(item.payload) == receipt["stdout_sha256"]
               and len(item.payload) == receipt["stdout_size_bytes"]]
        err = [item for item in stderr if sha(item.payload) == receipt["stderr_sha256"]
               and len(item.payload) == receipt["stderr_size_bytes"]]
        if len(out) != 1 or len(err) != 1:
            raise OperationalSemanticError(
                "preflight receipt does not bind exact stdout/stderr bytes"
            )
    return runtime, trust, ids


def _pilot_plan_core(plan: dict[str, Any]) -> dict[str, Any]:
    core = copy.deepcopy(plan)
    core.pop("plan_core_sha256", None)
    for cell in core.get("cells", []):
        for run in cell.get("runs", []):
            run.pop("runner_admission", None)
            run.pop("runner_admission_sha256", None)
            run.pop("runner_evidence_set_sha256", None)
    return core


def _schedule_hash(run: dict[str, Any], *, warmup: bool) -> str:
    prefix = "warmup_" if warmup else ""
    return sha(canonical({
        "schema_version": "cpu-prefetch-stage17-frozen-schedule/2",
        "arrival_family": "OPEN_LOOP_FROZEN",
        "deadline_ticks": run[prefix + "schedule_deadline_ticks"],
        "origin_ticks": run[prefix + "schedule_origin_ticks"],
        "horizon_ticks": run[prefix + "schedule_horizon_ticks"],
    }))


def _seed_derivation_hash(run: dict[str, Any]) -> str:
    return sha(canonical({
        "schema_version": "cpu-prefetch-stage17-pilot-seed-binding/1",
        "measurement_seed_id": run["seed_id"],
        "measurement_seed_hex": run["seed_hex"],
        "warmup_seed_id": run["warmup_seed_id"],
    }))


def _validate_pilot_plan(
    plan: dict[str, Any], *, stand_id: str, synthetic: bool,
    admitted_resolutions: Mapping[str, Any], pinned: Mapping[str, bytes],
) -> None:
    if plan["stand_id"] != stand_id or plan["synthetic_test_only"] is not synthetic:
        raise OperationalSemanticError("pilot plan stand/classification drifted")
    order = plan["whole_plot_order"]
    factors: set[tuple[str, str, str, str, str]] = set()
    ordinals: set[int] = set()
    run_ids: set[str] = set()
    repetitions = plan["repetitions_per_cell"]
    hardware = plan["hardware_control"]
    if plan["plan_core_sha256"] != sha(canonical(_pilot_plan_core(plan))):
        raise OperationalSemanticError("pilot core hash is not constructively derived")
    ext6 = admitted_resolutions["S17-EXT-006"].semantic_context
    if not isinstance(ext6, dict):
        raise OperationalSemanticError("pilot plan lacks admitted release context")
    known: dict[str, str] = {}
    for resolution in admitted_resolutions.values():
        known[resolution.resolution_id] = resolution.sha256
        if isinstance(resolution.semantic_context, dict):
            for artifact_id, binding in resolution.semantic_context.get(
                    "artifact_index", {}).items():
                if isinstance(binding, dict) and isinstance(binding.get("sha256"), str):
                    known[artifact_id] = binding["sha256"]
    expected_kinds = {
        "PROTOCOL_SNAPSHOT", "SOURCE_RELEASE", "RUN_PLAN",
        "WARMUP_SCHEDULE", "MEASUREMENT_SCHEDULE", "SEED_DERIVATION",
        "PLATFORM_INVENTORY", "PLATFORM_REQUEST", "PLATFORM_VERIFICATION",
        "HARDWARE_PREFETCH_MAPPING", "SOFTWARE_PREFETCH_MAPPING",
        "CLOCK_QUALIFICATION", "QUEUE_PROVENANCE", "RUNTIME_ATOMIC_LAYOUT",
        "ADDRESS_RESIDENCY", "STORAGE_BUDGET", "DURABILITY_DOMAINS",
        "CALIBRATION_FREEZE", "EXECUTION_LIMITS", "AUTHORITY_CUSTODY",
        "PHASE_EXECUTION_AUTHORIZATION",
    }
    common_families: dict[tuple[str, str, str, int], list[tuple[Any, ...]]] = {}
    if (hardware["mapping_id"] != "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1"
            or len(hardware["prestate"]) != 3
            or {item["cpu"] for item in hardware["prestate"]} != {0, 1, 26}):
        raise OperationalSemanticError("pilot hardware-control binding drifted")
    for index, cell in enumerate(plan["cells"]):
        expected_state = order[0 if index < 90 else 1]
        factor = (
            cell["package"], cell["hardware_state"], cell["placement"],
            cell["working_set_class"], cell["load_level"],
        )
        if (cell["hardware_state"] != expected_state
                or cell["cell_ordinal"] in ordinals or factor in factors
                or len(cell["runs"]) != repetitions):
            raise OperationalSemanticError("pilot Cartesian/whole-plot shape drifted")
        ordinals.add(cell["cell_ordinal"]); factors.add(factor)
        for repetition, run in enumerate(cell["runs"]):
            admission = run["runner_admission"]
            _validate(
                pathlib.Path("."), admission,
                "config/schemas/runner-admission-v3.schema.json",
                "pilot runner admission", pinned,
            )
            evidence = admission["evidence"]
            kinds = {item["kind"] for item in evidence}
            binding_ids = {item["binding_id"] for item in evidence}
            schedule_sha = _schedule_hash(run, warmup=False)
            warmup_schedule_sha = _schedule_hash(run, warmup=True)
            special = {
                "SOURCE_RELEASE": ext6["release_artifact_sha256"],
                "RUN_PLAN": plan["plan_core_sha256"],
                "WARMUP_SCHEDULE": warmup_schedule_sha,
                "MEASUREMENT_SCHEDULE": schedule_sha,
                "SEED_DERIVATION": _seed_derivation_hash(run),
            }
            for item in evidence:
                expected_sha = special.get(item["kind"], known.get(item["artifact_id"]))
                if expected_sha is None or item["sha256"] != expected_sha:
                    raise OperationalSemanticError(
                        "runner evidence is self-selected or not admitted"
                    )
            placement_cpus = {"NEAR": (0, 1), "FAR": (0, 26)}
            if (run["run_id"] in run_ids or run["package"] != cell["package"]
                    or run["cell_ordinal"] != cell["cell_ordinal"]
                    or run["repetition_ordinal"] != repetition
                    or run["hardware_state"] != cell["hardware_state"]
                    or run["placement"] != cell["placement"]
                    or run["working_set_class"] != cell["working_set_class"]
                    or run["load_level"] != cell["load_level"]
                    or "plan_sha256" in run
                    or kinds != expected_kinds or len(binding_ids) != 1
                    or admission["binding_id"] not in binding_ids
                    or admission["package"] != run["package"]
                    or admission["placement"] != run["placement"]
                    or (admission["producer_cpu"], admission["consumer_cpu"])
                    != placement_cpus[run["placement"]]
                    or admission["stand_id"] != stand_id
                    or admission["source_revision"] != ext6["source_revision"]
                    or admission["binary_sha256"]
                    != ext6["release_artifact_sha256"]
                    or run["runner_admission_sha256"] != sha(canonical(admission))
                    or run["runner_evidence_set_sha256"]
                    != sha(canonical(evidence))
                    or len(run["schedule_deadline_ticks"]) != run["offered_count"]
                    or run["schedule_deadline_ticks"] != sorted(run["schedule_deadline_ticks"])
                    or run["schedule_deadline_ticks"][-1] >= run["schedule_horizon_ticks"]
                    or len(run["warmup_schedule_deadline_ticks"]) < 1
                    or run["warmup_schedule_deadline_ticks"] != sorted(
                        run["warmup_schedule_deadline_ticks"]
                    )
                    or run["warmup_schedule_deadline_ticks"][-1]
                    >= run["warmup_schedule_horizon_ticks"]
                    or run["schedule_sha256"] != schedule_sha
                    or run["warmup_schedule_sha256"] != warmup_schedule_sha):
                raise OperationalSemanticError("pilot run/schedule family drifted")
            run_ids.add(run["run_id"])
            common_key = (
                run["placement"], run["working_set_class"], run["load_level"],
                repetition,
            )
            common_families.setdefault(common_key, []).append((
                run["seed_id"], run["seed_hex"], run["warmup_seed_id"],
                tuple(run["schedule_deadline_ticks"]), run["schedule_origin_ticks"],
                run["schedule_horizon_ticks"],
                tuple(run["warmup_schedule_deadline_ticks"]),
                run["warmup_schedule_origin_ticks"],
                run["warmup_schedule_horizon_ticks"], run["capacity"],
                run["shared_memory_node"], run["cache_line_bytes"],
                run["base_page_bytes"],
            ))
    if (ordinals != set(range(180)) or len(factors) != 180
            or len(run_ids) != 180 * repetitions):
        raise OperationalSemanticError("pilot plan is not the exact 180-cell product")
    if (len(common_families) != 18 * repetitions
            or any(len(values) != 10 or len(set(values)) != 1
                   for values in common_families.values())):
        raise OperationalSemanticError(
            "matched packages/states do not share one frozen schedule/mapping family"
        )


def verify_manifest_v4(
    *, repository_root: pathlib.Path, manifest_path: pathlib.Path,
    admitted_resolutions: Mapping[str, Any], expected_input_id: str,
    allow_synthetic: bool, pinned_repository_bytes: Mapping[str, bytes],
) -> dict[str, Any]:
    root = repository_root.resolve()
    manifest, payload = load(manifest_path)
    _validate(root, manifest, MANIFEST_SCHEMA, "operational manifest v4",
              pinned_repository_bytes)
    if (manifest["input_id"] != expected_input_id
            or expected_input_id not in EXPECTED_ROLES
            or manifest["synthetic_test_only"] is not allow_synthetic):
        raise OperationalSemanticError("manifest input/classification drifted")
    artifacts = _read_artifacts(root, manifest_path, manifest,
                                pinned_repository_bytes)
    observed_roles = collections.Counter(item.role for item in artifacts)
    expected_roles = EXPECTED_ROLES[expected_input_id].copy()
    if expected_input_id == "S17-EXT-007":
        for role in ("Q16A_RESULT", "Q16B_RESULT", "Q16C_RESULT"):
            result_artifact = _one(artifacts, role)
            assert result_artifact.document is not None
            expected_roles.update(
                binding["role"]
                for binding in result_artifact.document["artifacts"]
            )
    if observed_roles != expected_roles:
        raise OperationalSemanticError(f"{expected_input_id} exact role family drifted")
    ordinal = int(expected_input_id[-3:])
    predecessor_ids = tuple(
        f"S17-EXT-{index:03d}" for index in range(1, ordinal)
    )
    expected_predecessors = _resolution_bindings(admitted_resolutions, predecessor_ids)
    if manifest["predecessor_resolutions"] != expected_predecessors:
        raise OperationalSemanticError("manifest predecessor family drifted")
    index = _artifact_index(artifacts, admitted_resolutions)
    context: dict[str, Any] = {
        "manifest_id": manifest["manifest_id"], "manifest_path": manifest_path,
        "manifest_sha256": sha(payload), "stand_id": manifest["stand_id"],
        "synthetic_test_only": allow_synthetic, "artifact_index": index,
    }
    if expected_input_id == "S17-EXT-002":
        runtime, trust, observation_ids = _validate_preflight(
            artifacts, admitted_resolutions["S17-EXT-001"]
        )
        release_context = _verify_extracted_release(
            root, _one(artifacts, "RUNTIME_RELEASE_PROVENANCE"),
            _one(artifacts, "RUNTIME_IDENTITY"),
            _one(artifacts, "RUNTIME_WORKER_BINARY"),
        )
        signers = _one(artifacts, "TRUST_ALLOWED_SIGNERS")
        values = trust["measurements"]
        if (pathlib.Path(values["allowed_signers_path"]).resolve() != signers.path.resolve()
                or values["allowed_signers_size_bytes"] != len(signers.payload)
                or values["allowed_signers_sha256"] != sha(signers.payload)
                or values["stand_id"] != manifest["stand_id"]):
            raise OperationalSemanticError("EXT002 trust anchor bytes/stand drifted")
        context.update({
            "runtime": runtime, "trust": trust,
            "observation_ids": tuple(observation_ids),
            "release": release_context,
            "runtime_record_sha256": sha(_one(artifacts, "RUNTIME_IDENTITY").payload),
            "trust_record_sha256": sha(_one(artifacts, "TRUST_ANCHOR").payload),
            "runtime_release_provenance_sha256": sha(
                _one(artifacts, "RUNTIME_RELEASE_PROVENANCE").payload
            ),
        })
    elif expected_input_id == "S17-EXT-003":
        ext2 = admitted_resolutions["S17-EXT-002"]
        accepted = _one(artifacts, "OWNER_ACCEPTANCE").document
        assert accepted and isinstance(ext2.semantic_context, dict)
        values = accepted["measurements"]
        expected = {
            "ext002_resolution_id": ext2.resolution_id,
            "ext002_resolution_sha256": ext2.sha256,
            "runtime_record_sha256": ext2.semantic_context[
                "runtime_record_sha256"
            ],
            "trust_record_sha256": ext2.semantic_context["trust_record_sha256"],
            "runtime_release_provenance_sha256": ext2.semantic_context[
                "runtime_release_provenance_sha256"
            ],
            "distinct_auditor": False, "independent_review": False,
            "role_collapse_accepted": True,
        }
        if values != expected:
            raise OperationalSemanticError("EXT003 owner acceptance/role collapse drifted")
        context.update({"runtime": ext2.semantic_context["runtime"],
                        "trust": ext2.semantic_context["trust"],
                        "release": ext2.semantic_context["release"],
                        "owner_acceptance": accepted})
    elif expected_input_id == "S17-EXT-004":
        trust = admitted_resolutions["S17-EXT-003"].semantic_context["trust"]
        family = _phase_family(
            root=root, artifacts=artifacts, action_id="Q15-R", trust=trust,
            expected_predecessors=expected_predecessors[:3],
            synthetic_test_only=allow_synthetic,
        )
        evidence = [item.document for item in artifacts
                    if item.role == "QUALIFICATION_EVIDENCE"]
        kinds = {item["kind"] for item in evidence if item is not None}
        if (kinds != {"SELECTED_PAIR_CLOCK", "RUNTIME_ATOMIC_LAYOUT",
                      "ACTUAL_CPU_MIGRATION", "ADDRESS_RESIDENCY",
                      "SOFTWARE_PREFETCH_MAPPING"}
                or any(not item["eligible"] for item in evidence if item is not None)
                or any(item["stand_id"] != manifest["stand_id"]
                       for item in evidence if item is not None)):
            raise OperationalSemanticError("EXT004 qualification evidence is incomplete")
        platform = _one(artifacts, "PLATFORM_MANIFEST")
        pilot_platform = _one(
            artifacts, "PILOT_PLATFORM_MEASUREMENTS"
        ).document
        assert pilot_platform is not None
        measurements = pilot_platform["measurements"]
        if (pilot_platform["subject_id"] != manifest["stand_id"]
                or measurements["platform_manifest_sha256"]
                != sha(platform.payload)
                or measurements["q15_r_result_sha256"]
                != family["result_sha256"]):
            raise OperationalSemanticError(
                "EXT004 pilot platform measurements lack exact source lineage"
            )
        context.update({
            "q15_r": family, "qualification_evidence": evidence,
            "pilot_platform_measurements": measurements,
        })
    elif expected_input_id == "S17-EXT-005":
        trust = admitted_resolutions["S17-EXT-003"].semantic_context["trust"]
        family = _phase_family(
            root=root, artifacts=artifacts, action_id="Q15-W", trust=trust,
            expected_predecessors=expected_predecessors,
            synthetic_test_only=allow_synthetic,
        )
        q15r = admitted_resolutions["S17-EXT-004"].semantic_context["q15_r"]
        output = _one(artifacts, "Q15_W_TRANSACTION").document
        assert output
        if (output["q15_r_attempt_sha256"] != q15r["attempt_sha256"]
                or output["q15_r_result_sha256"] != q15r["result_sha256"]
                or not output["live_prestate_matches"]
                or not output["restoration_verified"]
                or output["quarantine_operation"] != {
                    "performed": False, "reason": "RESTORATION_VERIFIED"
                }):
            raise OperationalSemanticError("EXT005 Q15-R/live-prestate/restore lineage drifted")
        context.update({
            "q15_w": family,
            "authorization": family["authorization"],
            "authorization_sha256": family["authorization_sha256"],
        })
    elif expected_input_id == "S17-EXT-007":
        trust = admitted_resolutions["S17-EXT-003"].semantic_context["trust"]
        actions: dict[str, Any] = {}
        for action in ("Q16a", "Q16b", "Q16c"):
            actions[action] = _phase_family(
                root=root, artifacts=artifacts, action_id=action, trust=trust,
                expected_predecessors=expected_predecessors[:6],
                synthetic_test_only=allow_synthetic,
            )
        if (actions["Q16b"]["request"]["action_inputs"].get(
                "q16a_result_sha256") != actions["Q16a"]["result_sha256"]
                or actions["Q16c"]["request"]["action_inputs"].get(
                    "q16a_result_sha256") != actions["Q16a"]["result_sha256"]
                or actions["Q16c"]["request"]["action_inputs"].get(
                    "q16b_result_sha256") != actions["Q16b"]["result_sha256"]):
            raise OperationalSemanticError("Q16 action order/result lineage drifted")
        freeze = _one(artifacts, "CALIBRATION_FREEZE").document
        assert freeze
        source_hashes = {item["sha256"] for item in freeze["source_records"]}
        if (freeze["state"] != "FROZEN" or freeze["unresolved_inputs"]
                or not {actions[item]["result_sha256"] for item in actions}
                <= source_hashes):
            raise OperationalSemanticError("calibration freeze lacks exact Q16 results")
        context.update({"actions": actions, "calibration_freeze": freeze})
    elif expected_input_id == "S17-EXT-008":
        plan_artifact = _one(artifacts, "PILOT_PLAN_V4")
        assert plan_artifact.document
        try:
            pilot_plan_runtime.validate(
                plan_artifact.document, stand_id=manifest["stand_id"],
                synthetic_test_only=allow_synthetic,
                admitted_resolutions=admitted_resolutions,
                repository_root=repository_root,
            )
        except pilot_plan_runtime.PilotPlanError as exception:
            raise OperationalSemanticError(str(exception)) from exception
        context.update({"pilot_plan": plan_artifact.document,
                        "pilot_plan_path": plan_artifact.path,
                        "pilot_plan_sha256": sha(plan_artifact.payload)})
    elif expected_input_id == "S17-EXT-009":
        domains = [item.document for item in artifacts if item.role == "CUSTODY_DOMAIN"]
        ids = {item["measurements"]["domain_id"] for item in domains if item}
        if len(ids) != 2:
            raise OperationalSemanticError("EXT009 lacks two custody domains")
        for item in domains:
            assert item
            values = item["measurements"]
            path = pathlib.Path(values["locator"])
            metadata = path.lstat()
            if (values["independent_domain_id"] not in ids
                    or values["independent_domain_id"] == values["domain_id"]
                    or stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode)
                    or metadata.st_uid != values["owner_uid"]
                    or f"{stat.S_IMODE(metadata.st_mode):04o}" != values["mode"]):
                raise OperationalSemanticError("custody domain identity drifted")
        budget = _one(artifacts, "STORAGE_BUDGET").document
        assert budget
        values = budget["measurements"]
        if (values["planned_bytes"] > values["available_bytes"]
                or values["durable_copies"] < 2
                or values["pilot_plan_sha256"] != admitted_resolutions[
                    "S17-EXT-008"
                ].semantic_context["pilot_plan_sha256"]):
            raise OperationalSemanticError("storage budget is insufficient/unbound")
        context["storage_ready"] = True
    elif expected_input_id == "S17-EXT-010":
        authorization = _one(artifacts, "PILOT_AUTHORIZATION")
        signature = _one(artifacts, "PILOT_SIGNATURE")
        request = _one(artifacts, "PILOT_REQUEST")
        assert authorization.document and request.document
        trust = admitted_resolutions["S17-EXT-003"].semantic_context["trust"]
        verify_sshsig(authorization=authorization, signature=signature,
                      trust_record=trust)
        auth, req = authorization.document, request.document
        if (auth["action_id"] != "STAGE17-BLINDED-PILOT"
                or auth["predecessor_resolutions"] != expected_predecessors
                or req["predecessor_resolutions"] != expected_predecessors
                or auth["request_binding"] != {
                    "path": str(request.path), "size_bytes": len(request.payload),
                    "sha256": sha(request.payload),
                }
                or req["action_inputs"] != {
                    "plan_sha256": admitted_resolutions[
                        "S17-EXT-008"
                    ].semantic_context["pilot_plan_sha256"],
                    "pilot_plan": admitted_resolutions[
                        "S17-EXT-008"
                    ].semantic_context["pilot_plan"],
                }):
            raise OperationalSemanticError("EXT010 exact pilot scope/plan drifted")
        context.update({
            "authorization": auth, "authorization_path": authorization.path,
            "authorization_sha256": sha(authorization.payload), "request": req,
            "request_path": request.path, "request_sha256": sha(request.payload),
        })
    return context
