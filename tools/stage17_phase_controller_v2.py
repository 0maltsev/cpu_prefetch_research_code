#!/usr/bin/env python3
"""Production Stage 17 fixed-action authority controller v2.

The authorization references admitted trust and runtime contexts; it cannot
choose a signer, executable, command, argv, stdin, backend, or output name.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

import stage17_fixed_action_executor_v2 as executor
import stage17_openssh_parent_snapshot_v1 as snapshot_broker
import stage17_state_journal_v7 as journal_runtime


ROOT = pathlib.Path(__file__).resolve().parents[1]
ACTION_PLAN = pathlib.PurePosixPath("config/stage17/stage17-fixed-phase-actions-v2.json")
AUTH_SCHEMA = "config/schemas/stage17-phase-action-authorization-v2.schema.json"
REQUEST_SCHEMA = "config/schemas/stage17-fixed-action-request-v2.schema.json"
MAX_BOUND_INPUT_BYTES = 16 * 1024 * 1024


class ControllerError(RuntimeError):
    pass


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def _load(path: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    payload = path.read_bytes()
    document = json.loads(payload)
    if not isinstance(document, dict):
        raise ControllerError(f"JSON root is not an object: {path}")
    return document, payload


def _validate(root: pathlib.Path, relative: str, document: dict[str, Any], label: str) -> None:
    schema = json.loads((root / relative).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
        key=lambda item: tuple(item.path),
    )
    if errors:
        where = "/".join(str(item) for item in errors[0].path) or "<root>"
        raise ControllerError(f"{label} schema error at {where}: {errors[0].message}")


def _parse_utc(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ControllerError("authorization timestamp is not UTC")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exception:
        raise ControllerError("authorization timestamp is malformed") from exception
    return parsed


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _read_binding(binding: dict[str, Any], label: str, *, executable: bool = False) -> tuple[pathlib.Path, bytes]:
    path = pathlib.Path(str(binding.get("path", "")))
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid():
            raise ControllerError(f"{label} is not an owner regular file")
        if stat.S_IMODE(metadata.st_mode) & 0o022:
            raise ControllerError(f"{label} is group/world writable")
        if executable and stat.S_IMODE(metadata.st_mode) & 0o111 == 0:
            raise ControllerError(f"{label} is not executable")
        if metadata.st_size < 1 or metadata.st_size > MAX_BOUND_INPUT_BYTES:
            raise ControllerError(f"{label} exceeds its fixed size limit")
        if metadata.st_size != binding.get("size_bytes"):
            raise ControllerError(f"{label} size drifted")
        payload = os.pread(descriptor, metadata.st_size + 1, 0)
        if len(payload) != metadata.st_size or _sha(payload) != binding.get("sha256"):
            raise ControllerError(f"{label} bytes drifted")
        return path, payload
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_unbound_regular(path: pathlib.Path, label: str) -> bytes:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid():
            raise ControllerError(f"{label} is not an owner regular file")
        if stat.S_IMODE(metadata.st_mode) & 0o022:
            raise ControllerError(f"{label} is group/world writable")
        if metadata.st_size < 1 or metadata.st_size > MAX_BOUND_INPUT_BYTES:
            raise ControllerError(f"{label} exceeds its fixed size limit")
        payload = os.pread(descriptor, metadata.st_size + 1, 0)
        if len(payload) != metadata.st_size:
            raise ControllerError(f"{label} bytes changed during the exact read")
        return payload
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _pin_payload(payload: bytes, role: str) -> snapshot_broker.ParentSnapshot:
    descriptor: int | None = None
    try:
        descriptor = os.memfd_create(
            f"cpu-prefetch-stage17-{role.lower()}",
            int(getattr(os, "MFD_CLOEXEC", 0x0001))
            | int(getattr(os, "MFD_ALLOW_SEALING", 0x0002)),
        )
        os.fchmod(descriptor, 0o600)
        view = memoryview(payload)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise ControllerError(f"{role} snapshot write made no progress")
            view = view[count:]
        seal_names = snapshot_broker.REQUIRED_SEAL_NAMES
        seal_mask = sum(int(getattr(fcntl, name)) for name in seal_names)
        fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, seal_mask)
        if int(fcntl.fcntl(descriptor, fcntl.F_GET_SEALS)) & seal_mask != seal_mask:
            raise ControllerError(f"{role} snapshot sealing is incomplete")
        procfs = snapshot_broker.discover_procfs_identity()
        locator = f"/proc/{procfs.visible_pid}/fd/{descriptor}"
        result = snapshot_broker.ParentSnapshot(
            role=role,
            descriptor=descriptor,
            locator=locator,
            metadata={
                "role": role,
                "source_size_bytes": len(payload),
                "consumed_sha256": _sha(payload),
                "snapshot_size_bytes": len(payload),
                "snapshot_mechanism": snapshot_broker.MECHANISM,
                "verified_seals": list(seal_names),
                "procfs_visible_parent_pid": procfs.visible_pid,
                "private_bytes_recorded": False,
            },
        )
        snapshot_broker.verify_snapshot(result)
        descriptor = None
        return result
    except (AttributeError, OSError, snapshot_broker.SnapshotError) as exception:
        raise ControllerError(f"{role} could not be sealed for signature verification") from exception
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _verify_signature(authorization_bytes: bytes, signature: pathlib.Path,
                      trust: dict[str, Any]) -> None:
    measurements = trust.get("measurements")
    if not isinstance(measurements, dict):
        raise ControllerError("admitted trust context is malformed")
    binding = {
        "path": measurements.get("allowed_signers_path"),
        "size_bytes": measurements.get("allowed_signers_size_bytes"),
        "sha256": measurements.get("allowed_signers_sha256"),
    }
    _, allowed_payload = _read_binding(binding, "admitted allowed-signers")
    signature_payload = _read_unbound_regular(signature, "authorization signature")
    allowed_snapshot: snapshot_broker.ParentSnapshot | None = None
    signature_snapshot: snapshot_broker.ParentSnapshot | None = None
    try:
        allowed_snapshot = _pin_payload(allowed_payload, "STAGE17_ALLOWED_SIGNERS")
        signature_snapshot = _pin_payload(signature_payload, "STAGE17_AUTHORIZATION_SIGNATURE")
        result = subprocess.run(
            ["/usr/bin/ssh-keygen", "-Y", "verify", "-f", allowed_snapshot.locator,
             "-I", str(measurements.get("principal")), "-n",
             str(measurements.get("sshsig_namespace")), "-s",
             signature_snapshot.locator],
            input=authorization_bytes, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False, timeout=10,
        )
        snapshot_broker.verify_snapshot(allowed_snapshot)
        snapshot_broker.verify_snapshot(signature_snapshot)
    except (OSError, subprocess.SubprocessError,
            snapshot_broker.SnapshotError) as exception:
        raise ControllerError("authorization signature verification boundary failed") from exception
    finally:
        snapshot_broker.close_snapshots(allowed_snapshot, signature_snapshot)
    if result.returncode != 0:
        raise ControllerError("authorization signature is not rooted in admitted EXT002/EXT003 trust")


def _binding(resolution: Any) -> dict[str, str]:
    return {"input_id": resolution.input_id,
            "resolution_id": resolution.resolution_id, "sha256": resolution.sha256}


def _action_definition(root: pathlib.Path, action_id: str) -> tuple[dict[str, Any], bytes]:
    path = root / ACTION_PLAN
    document, payload = _load(path)
    _validate(root, "config/schemas/stage17-fixed-phase-actions-v2.schema.json",
              document, "fixed phase actions")
    matches = [item for item in document["actions"] if item["action_id"] == action_id]
    if len(matches) != 1:
        raise ControllerError("unknown fixed action")
    return matches[0], payload


def _runtime_from_context(action: str, validation: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    resolutions = validation.resolutions
    if action in {"Q15-R", "Q15-W"}:
        source = resolutions["S17-EXT-003"]
        context = source.semantic_context
        if not isinstance(context, dict) or not isinstance(context.get("runtime"), dict):
            raise ControllerError("EXT002/EXT003 accepted runtime context is absent")
        measurements = context["runtime"].get("measurements")
        if not isinstance(measurements, dict):
            raise ControllerError("accepted runtime measurements are absent")
        release = {
            "source_resolution_id": source.resolution_id,
            "source_resolution_sha256": source.sha256,
            "artifact_role": measurements["worker_role"],
            "runtime_profile": measurements["runtime_profile"],
            "worker_size_bytes": measurements["worker_size_bytes"],
            "worker_sha256": measurements["worker_sha256"],
        }
    else:
        source = resolutions["S17-EXT-006"]
        context = source.semantic_context
        if not isinstance(context, dict):
            raise ControllerError("EXT006 release context is absent")
        measurements = {
            "worker_path": context["release_artifact_path"],
            "worker_size_bytes": context["release_artifact_size_bytes"],
            "worker_sha256": context["release_artifact_sha256"],
            "worker_role": context["release_artifact_role"],
            "runtime_profile": context["runtime_profile"],
            "supported_actions": context["supported_actions"],
        }
        release = {
            "source_resolution_id": source.resolution_id,
            "source_resolution_sha256": source.sha256,
            "artifact_role": context["release_artifact_role"],
            "runtime_profile": context["runtime_profile"],
            "worker_size_bytes": context["release_artifact_size_bytes"],
            "worker_sha256": context["release_artifact_sha256"],
        }
    if measurements["worker_role"] != "STAGE17_FIXED_ACTION_WORKER" or measurements["runtime_profile"] != "STAGE17-FIXED-ACTION-WORKER-v2":
        raise ControllerError("admitted runtime role/profile is wrong")
    if tuple(measurements["supported_actions"]) != (
        "Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c", "STAGE17-BLINDED-PILOT"
    ) or action not in measurements["supported_actions"]:
        raise ControllerError("admitted runtime action surface drifted")
    runtime = {
        "role": measurements["worker_role"], "profile": measurements["runtime_profile"],
        "size_bytes": measurements["worker_size_bytes"], "sha256": measurements["worker_sha256"],
    }
    return {"path": measurements["worker_path"], **runtime}, release


def _validate_action_inputs(action: str, values: Any, *, root: pathlib.Path,
                            request: dict[str, Any], synthetic: bool,
                            authorization_sha256: str) -> None:
    if not isinstance(values, dict):
        raise ControllerError("fixed action inputs are not an object")
    if synthetic:
        if set(values) != {"fixture_nonce"} or not isinstance(values["fixture_nonce"], str) or not values["fixture_nonce"]:
            raise ControllerError("test-linked action input family drifted")
        return
    expected: dict[str, set[str]] = {
        "Q15-R": {"authorization_sha256", "qualification_id"},
        "Q15-W": {"authorization_sha256", "prestate", "probe_evidence"},
        "Q16a": {"capacity", "sample_count", "calibration_plan_sha256", "seed_id",
                  "seed_hex", "cache_line_bytes", "base_page_bytes",
                  "runner_admission", "runner_admission_sha256",
                  "runner_evidence_set_sha256"},
        "Q16b": {"capacity", "offered_count", "package", "d2_cache_lines",
                  "plan_sha256", "schedule_sha256", "run_id", "seed_id", "seed_hex",
                  "cache_line_bytes", "base_page_bytes", "runner_admission",
                  "runner_admission_sha256", "runner_evidence_set_sha256",
                  "schedule_deadline_ticks", "schedule_origin_ticks",
                  "schedule_horizon_ticks", "duration_ticks"},
        "Q16c": {"capacity", "offered_count", "package", "d2_cache_lines",
                  "plan_sha256", "schedule_sha256", "run_id", "seed_id", "seed_hex",
                  "cache_line_bytes", "base_page_bytes", "runner_admission",
                  "runner_admission_sha256", "runner_evidence_set_sha256",
                  "schedule_deadline_ticks", "schedule_origin_ticks",
                  "schedule_horizon_ticks", "duration_ticks"},
        "STAGE17-BLINDED-PILOT": {"capacity", "offered_count", "package",
                  "d2_cache_lines", "plan_sha256", "schedule_sha256", "run_id",
                  "seed_id", "seed_hex", "cache_line_bytes", "base_page_bytes",
                  "runner_admission", "runner_admission_sha256",
                  "runner_evidence_set_sha256", "schedule_deadline_ticks",
                  "schedule_origin_ticks", "schedule_horizon_ticks",
                  "duration_ticks"},
    }
    if set(values) != expected[action]:
        raise ControllerError("production fixed action input family is incomplete or expanded")
    if action in {"Q15-R", "Q15-W"} and values["authorization_sha256"] != authorization_sha256:
        raise ControllerError("fixed action input authorization hash drifted")
    for name in ("calibration_plan_sha256", "plan_sha256", "schedule_sha256",
                 "runner_admission_sha256"):
        if name in values and (not isinstance(values[name], str) or len(values[name]) != 64
                               or any(item not in "0123456789abcdef" for item in values[name])):
            raise ControllerError(f"{name} is not SHA-256")
    if "seed_hex" in values and (not isinstance(values["seed_hex"], str)
                                  or len(values["seed_hex"]) != 64
                                  or any(item not in "0123456789abcdef" for item in values["seed_hex"])):
        raise ControllerError("fixed action seed is malformed")
    for name in ("capacity", "sample_count", "offered_count", "d2_cache_lines",
                 "cache_line_bytes", "base_page_bytes"):
        if name in values and (not isinstance(values[name], int) or isinstance(values[name], bool)
                               or values[name] < 1):
            raise ControllerError(f"{name} is not a positive fixed integer")
    if "package" in values and values["package"] not in {"R0", "R1", "R2", "L0", "L1"}:
        raise ControllerError("fixed action package is unknown")
    if action in {"Q16a", "Q16b", "Q16c", "STAGE17-BLINDED-PILOT"}:
        admission = values["runner_admission"]
        if not isinstance(admission, dict):
            raise ControllerError("runner admission is not an object")
        _validate(root, "config/schemas/runner-admission-v3.schema.json",
                  admission, "sealed runner admission")
        admission_payload = _canonical(admission)
        if _sha(admission_payload) != values["runner_admission_sha256"]:
            raise ControllerError("runner admission canonical hash drifted")
        evidence_payload = _canonical(admission["evidence"])
        if _sha(evidence_payload) != values["runner_evidence_set_sha256"]:
            raise ControllerError("runner evidence-set hash drifted")
        if (admission["binary_sha256"] != request["runtime_binding"]["sha256"]
                or admission["stand_id"] != request["stand_id"]
                or admission["package"] != values.get("package", "R0")):
            raise ControllerError("runner admission differs from fixed runtime/stand/package")
        if action == "Q16a":
            return
        deadlines = values["schedule_deadline_ticks"]
        if (not isinstance(deadlines, list)
                or any(not isinstance(item, int) or isinstance(item, bool) or item < 0
                       for item in deadlines)
                or deadlines != sorted(deadlines)):
            raise ControllerError("frozen schedule deadlines are malformed")
        if action == "Q16b":
            if deadlines:
                raise ControllerError("continuous-ready service calibration has no open-loop deadlines")
            schedule_contract = {
                "schema_version": "cpu-prefetch-stage17-frozen-schedule/2",
                "arrival_family": "CONTINUOUS_READY",
                "duration_ticks": values["duration_ticks"],
                "maximum_attempts": values["offered_count"],
            }
        else:
            if (len(deadlines) != values["offered_count"]
                    or not deadlines or deadlines[-1] >= values["schedule_horizon_ticks"]):
                raise ControllerError("open-loop schedule count/horizon drifted")
            schedule_contract = {
                "schema_version": "cpu-prefetch-stage17-frozen-schedule/2",
                "arrival_family": "OPEN_LOOP_FROZEN",
                "deadline_ticks": deadlines,
                "origin_ticks": values["schedule_origin_ticks"],
                "horizon_ticks": values["schedule_horizon_ticks"],
            }
        if _sha(_canonical(schedule_contract)) != values["schedule_sha256"]:
            raise ControllerError("frozen schedule bytes/hash drifted")


def execute_once(
    *, repository_root: pathlib.Path, journal: pathlib.Path,
    journal_directory: pathlib.Path, authorization_path: pathlib.Path,
    signature_path: pathlib.Path, test_linked_worker: bool = False,
    pilot_archive: pathlib.Path | None = None,
    pilot_sidecar: pathlib.Path | None = None,
) -> executor.ExecutionOutcome:
    root = repository_root.resolve()
    authorization, authorization_bytes = _load(authorization_path)
    _validate(root, AUTH_SCHEMA, authorization, "phase authorization")
    action, plan_bytes = _action_definition(root, authorization["action_id"])
    if authorization["fixed_action_definition_sha256"] != _sha(plan_bytes):
        raise ControllerError("fixed-action definition binding drifted")
    if authorization["permission_matrix"] != action["permission_matrix"]:
        raise ControllerError("permission matrix drifted")

    # No caller time is accepted here.  The status-only path is in the journal
    # checker; execution always samples actual system UTC.
    actual_now = _now()
    validation = journal_runtime.validate_operational_journal(
        repository_root=root, latest_journal=journal,
        journal_directory=journal_directory, as_of_utc=actual_now,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        allow_synthetic_test_evidence=test_linked_worker,
    )
    required_ids = tuple(action["required_resolution_ids"])
    if any(item not in validation.resolutions for item in required_ids):
        raise ControllerError("fixed action predecessor resolution is absent")
    expected_state = action["required_state"]
    if validation.current_state != expected_state:
        raise ControllerError("fixed action state gate is not satisfied")
    sampled_time = _parse_utc(actual_now)
    if any(item.recorded_at_utc > sampled_time for item in validation.resolutions.values()) or any(
        item.timestamp_utc > sampled_time for item in validation.transitions
    ):
        raise ControllerError("admitted resolution/transition chronology is in the future")
    expected_predecessors = [_binding(validation.resolutions[item]) for item in required_ids]
    if authorization["predecessor_resolutions"] != expected_predecessors:
        raise ControllerError("authorization predecessor lineage drifted")
    authorization_resolution_id = action["authorization_resolution_id"]
    if authorization_resolution_id is not None:
        admitted_authority = validation.resolutions.get(authorization_resolution_id)
        if admitted_authority is None or not isinstance(admitted_authority.semantic_context, dict):
            raise ControllerError("fixed action authorization resolution is absent")
        authority_context = admitted_authority.semantic_context
        if (authority_context.get("authorization_sha256") != _sha(authorization_bytes)
                or pathlib.Path(authority_context.get("authorization_path", pathlib.Path())) != authorization_path.resolve()
                or authority_context.get("authorization") != authorization):
            raise ControllerError("executed authorization differs from admitted authorization bytes")
    trust_context = {
        "ext002_resolution": _binding(validation.resolutions["S17-EXT-002"]),
        "ext003_resolution": _binding(validation.resolutions["S17-EXT-003"]),
    }
    if authorization["trust_context"] != trust_context:
        raise ControllerError("authorization trust context is not exact admitted EXT002/EXT003")
    ext003_context = validation.resolutions["S17-EXT-003"].semantic_context
    if not isinstance(ext003_context, dict) or not isinstance(ext003_context.get("trust"), dict):
        raise ControllerError("admitted EXT003 trust context is absent")
    trust = ext003_context["trust"]
    measurements = trust.get("measurements", {})
    if authorization["actor"] != measurements.get("principal"):
        raise ControllerError("authorization actor differs from admitted signer principal")
    _verify_signature(authorization_bytes, signature_path, trust)

    issued, expires, sampled = (_parse_utc(authorization["issued_at_utc"]),
                                _parse_utc(authorization["expires_at_utc"]),
                                _parse_utc(actual_now))
    if not issued <= sampled < expires or expires - issued > dt.timedelta(seconds=1800):
        raise ControllerError("authorization is future, expired, or exceeds bounded lifetime")
    request_path, request_bytes = _read_binding(
        authorization["request_binding"], "fixed request"
    )
    request = json.loads(request_bytes)
    if not isinstance(request, dict):
        raise ControllerError("fixed request root is not an object")
    _validate(root, REQUEST_SCHEMA, request, "fixed request")
    if request["synthetic_test_only"] is not test_linked_worker:
        raise ControllerError("production/test-linked request classification mismatch")
    runtime_binding, release_binding = _runtime_from_context(authorization["action_id"], validation)
    if request["runtime_binding"] != {key: runtime_binding[key] for key in ("role", "profile", "size_bytes", "sha256")}:
        raise ControllerError("request runtime differs from admitted runtime")
    if request["release_binding"] != release_binding:
        raise ControllerError("request release binding differs from admitted release")
    if request["predecessor_resolutions"] != expected_predecessors:
        raise ControllerError("request predecessor lineage drifted")
    _validate_action_inputs(
        authorization["action_id"], request["action_inputs"],
        root=root, request=request,
        synthetic=test_linked_worker,
        authorization_sha256=_sha(authorization_bytes),
    )
    if (request["authorization_id"], request["action_id"],
        request["stand_id"]) != (authorization["authorization_id"],
                                  authorization["action_id"], authorization["target"]["stand_id"]):
        raise ControllerError("request authorization/action/target lineage drifted")
    if pathlib.Path(authorization["request_binding"]["path"]) != request_path:
        raise ControllerError("request pathname normalization drifted")
    worker_path = pathlib.Path(runtime_binding.pop("path"))
    return executor.execute_fixed_action(
        repository_root=root, authorization=authorization,
        authorization_bytes=authorization_bytes, request=request,
        request_bytes=request_bytes, worker_binding=runtime_binding,
        worker_path=worker_path, release_binding=release_binding,
        output_root=pathlib.Path(authorization["evidence_root"]),
        test_linked_worker=test_linked_worker,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--repository-root", type=pathlib.Path, required=True)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--journal-directory", type=pathlib.Path, required=True)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    parser.add_argument("--signature", type=pathlib.Path, required=True)
    parser.add_argument("--pilot-archive", type=pathlib.Path)
    parser.add_argument("--pilot-sidecar", type=pathlib.Path)
    arguments = parser.parse_args()
    try:
        execute_once(
            repository_root=arguments.repository_root, journal=arguments.journal,
            journal_directory=arguments.journal_directory,
            authorization_path=arguments.authorization,
            signature_path=arguments.signature,
            test_linked_worker=False,
            pilot_archive=arguments.pilot_archive,
            pilot_sidecar=arguments.pilot_sidecar,
        )
    except BaseException as exception:
        print(f"stage17-phase-controller-v2: FAIL: {exception}", file=sys.stderr)
        return 1
    print("stage17-phase-controller-v2: PASS action=COMPLETED authority=STAGE17_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
