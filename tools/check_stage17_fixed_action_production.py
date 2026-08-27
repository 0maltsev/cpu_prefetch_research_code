#!/usr/bin/env python3
"""Hermetic Stage 17B admission and compiled fixed-dispatch integration.

The fixture uses disposable SSHSIG keys, temporary typed artifacts, the real
policy-v10 journal runtime, controller v2, sealed snapshots, and the separately
linked C++ test worker.  It opens no socket and grants no real authority.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Callable
from unittest import mock

import check_stage17_complete_operational_admission as legacy
import stage17_operational_semantics_v2 as semantics
import stage17_exit_state_machine_v2 as exit_machine
import stage17_phase_controller_v1 as rejected_controller
import stage17_phase_controller_v2 as controller
import stage17_semantic_verifier_v10 as semantic_registry
import stage17_state_journal_v7 as journal


ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTHON = pathlib.Path(sys.executable)
OBSERVATIONS = (
    "STAND_PRESTATE", "RUNTIME_EXECUTABLES", "CLOCK_CAPABILITY",
    "AFFINITY_NUMA", "STORAGE_RECOVERY", "HARDWARE_PREFETCH_CONTROL",
)


class CheckError(RuntimeError):
    pass


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: pathlib.Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(document))


def schema_binding(root: pathlib.Path, relative: str) -> dict[str, Any]:
    path = root / relative
    return {"path": relative, "size_bytes": path.stat().st_size, "sha256": digest(path)}


class Fixture:
    def __init__(self, temporary: pathlib.Path, worker: pathlib.Path) -> None:
        # Move legacy timestamps into the already elapsed day while retaining
        # its immutable exact-second test contracts.
        fixture_epoch = dt.datetime.now(dt.timezone.utc).replace(microsecond=0) - dt.timedelta(minutes=23)
        legacy.BASE_TIME = fixture_epoch.date().isoformat()
        legacy.utc = lambda minute: (fixture_epoch + dt.timedelta(minutes=minute)).isoformat().replace("+00:00", "Z")
        self.builder = legacy.Builder(temporary)
        self.root, self.external = self.builder.root, self.builder.external
        # Policy v10 binds the actual C++ worker closure in addition to the
        # Python/schema closure copied by the legacy synthetic builder.
        shutil.copytree(ROOT / "src", self.root / "src", symlinks=True)
        shutil.copytree(ROOT / "include", self.root / "include", symlinks=True)
        self.worker = self.external / "observed-cpu-prefetch-stage17-test-worker"
        shutil.copyfile(worker, self.worker)
        self.worker.chmod(0o700)
        self.allowed = self.external / "observed-allowed-signers"
        shutil.copyfile(self.builder.allowed_signers, self.allowed)
        self.allowed.chmod(0o600)
        self.external_contract = self.root / "config/stage17/stage17-operational-input-external-contract-v2.json"
        self.positive_actions = 0

    def source(self, artifact_id: str, path: pathlib.Path) -> dict[str, Any]:
        return {"id": artifact_id, "size_bytes": path.stat().st_size, "sha256": digest(path)}

    def typed(
        self, directory: pathlib.Path, artifact_id: str, role: str,
        measurements: dict[str, Any], sources: list[dict[str, Any]],
        outcome: str = "COMPLETE",
    ) -> pathlib.Path:
        path = directory / f"{artifact_id.lower()}.json"
        write(path, {
            "schema_version": "cpu-prefetch-stage17-operational-typed-record/2",
            "record_id": artifact_id, "record_role": role,
            "subject_id": "SYNTHETIC-STAGE17-TEST-ONLY",
            "source_bindings": sources, "measurements": measurements,
            "outcome": outcome, "recorded_at_utc": legacy.utc(3),
            "synthetic_test_only": True, "phase18_authority": False,
        })
        return path

    def artifact(
        self, manifest_dir: pathlib.Path, artifact_id: str, role: str,
        path: pathlib.Path, *, schema: str | None = None,
        lineage: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        try:
            locator = path.relative_to(manifest_dir).as_posix()
        except ValueError as exception:
            raise CheckError("fixture artifact is not under its manifest directory") from exception
        document = json.loads(path.read_text()) if schema else None
        return {
            "artifact_id": artifact_id, "role": role,
            "media_type": "application/json" if schema else "application/octet-stream",
            "locator": locator, "size_bytes": path.stat().st_size, "sha256": digest(path),
            "schema_identity": document["schema_version"] if document else None,
            "schema_binding": schema_binding(self.root, schema) if schema else None,
            "lineage": lineage or [],
        }

    def manifest(
        self, input_id: str, directory: pathlib.Path,
        artifacts: list[dict[str, Any]], predecessors: list[dict[str, str]],
    ) -> pathlib.Path:
        path = directory / f"{input_id.lower()}-manifest-v2.json"
        write(path, {
            "schema_version": "cpu-prefetch-stage17-operational-input-manifest/2",
            "manifest_id": f"SYNTHETIC-{input_id}-MANIFEST-v2-TEST-ONLY",
            "input_id": input_id, "protocol_version": "2.0.0-pre.2",
            "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
            "predecessor_resolutions": predecessors, "artifacts": artifacts,
            "synthetic_test_only": True, "authority_expansion": False,
            "phase18_authority": False,
        })
        return path

    def receipt(self, input_id: str, artifact: pathlib.Path, *,
                contract: pathlib.Path | None = None,
                sidecars: list[pathlib.Path] | None = None,
                verifier_id: str = "STAGE17-OPERATIONAL-MANIFEST-VERIFIER",
                verifier_version: str = "2") -> dict[str, Any]:
        return self.builder.external_receipt(
            input_id, artifact, contract_path=contract or self.external_contract,
            sidecars=sidecars, verifier_id=verifier_id,
            verifier_version=verifier_version,
        )

    def add(self, input_id: str, evidence: list[dict[str, Any]],
            authorization: dict[str, Any] | None = None) -> None:
        self.builder.add_resolution(input_id, evidence, authorization, {})

    def predecessors(self, stop: int) -> list[dict[str, str]]:
        return self.builder.predecessor_bindings(stop)

    def ext001(self) -> None:
        self.builder.ext001()
        self.builder.add_transition()

    def ext002(self) -> None:
        ext1_validation = journal.validate_operational_journal(
            repository_root=self.root,
            latest_journal=self.builder.latest_path.relative_to(self.root),
            journal_directory=self.root / "config/stage17/journal",
            allow_synthetic_test_evidence=True,
        )
        ext1_context = ext1_validation.resolutions["S17-EXT-001"].semantic_context
        if not isinstance(ext1_context, dict):
            raise CheckError("synthetic EXT001 semantic context is absent")
        ext1_target = ext1_context["contract"]["target"]
        directory = self.external / "ext002"
        directory.mkdir(mode=0o700)
        worker = directory / "cpu_prefetch_stage17_test_worker"
        signers = directory / "allowed_signers"
        shutil.copyfile(self.worker, worker); worker.chmod(0o700)
        shutil.copyfile(self.allowed, signers); signers.chmod(0o600)
        artifacts = [
            self.artifact(directory, "EXT002-WORKER", "RUNTIME_WORKER_BINARY", worker),
            self.artifact(directory, "EXT002-SIGNERS", "TRUST_ALLOWED_SIGNERS", signers),
        ]
        runtime = self.typed(directory, "EXT002-RUNTIME", "RUNTIME_IDENTITY", {
            "worker_path": str(worker), "worker_size_bytes": worker.stat().st_size,
            "worker_sha256": digest(worker), "worker_role": "STAGE17_FIXED_ACTION_WORKER",
            "runtime_profile": "STAGE17-FIXED-ACTION-WORKER-v2",
            "supported_actions": ["Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c", "STAGE17-BLINDED-PILOT"],
        }, [self.source("EXT002-WORKER", worker)])
        trust = self.typed(directory, "EXT002-TRUST", "TRUST_ANCHOR", {
            "allowed_signers_path": str(signers), "allowed_signers_size_bytes": signers.stat().st_size,
            "allowed_signers_sha256": digest(signers), "principal": "synthetic-stage17-owner",
            "sshsig_namespace": "cpu-prefetch-stage17-fixed-action-test-v2",
            "signer_role": "OWNER_OPERATOR_CUSTODIAN", "reviewer_role": "OWNER_AUDITOR_COLLAPSED",
            "stand_anchor_sha256": ext1_target["pinned_host_key_evidence"]["sha256"],
        }, [self.source("EXT002-SIGNERS", signers)])
        artifacts.extend((
            self.artifact(directory, "EXT002-RUNTIME", "RUNTIME_IDENTITY", runtime,
                          schema=semantics.TYPED_SCHEMA),
            self.artifact(directory, "EXT002-TRUST", "TRUST_ANCHOR", trust,
                          schema=semantics.TYPED_SCHEMA),
        ))
        attempt = self.typed(directory, "EXT002-ATTEMPT", "PREFLIGHT_ATTEMPT", {
            "authorization_sha256": ext1_context["authorization_sha256"],
            "observation_ids": list(OBSERVATIONS),
            "one_attempt": True, "retries": 0,
        }, [self.source("EXT002-WORKER", worker)])
        artifacts.append(self.artifact(directory, "EXT002-ATTEMPT", "PREFLIGHT_ATTEMPT", attempt, schema=semantics.TYPED_SCHEMA))
        receipt_paths = []
        for ordinal, observation in enumerate(OBSERVATIONS, 1):
            stdout = directory / f"observation-{ordinal:02d}.stdout"
            stderr = directory / f"observation-{ordinal:02d}.stderr"
            stdout.write_bytes(canonical({"observation_id": observation, "synthetic_test_only": True}))
            stderr.write_bytes(b"\n")
            stdout_id, stderr_id = f"EXT002-STDOUT-{ordinal}", f"EXT002-STDERR-{ordinal}"
            artifacts.extend((self.artifact(directory, stdout_id, "PREFLIGHT_STDOUT", stdout),
                              self.artifact(directory, stderr_id, "PREFLIGHT_STDERR", stderr)))
            receipt = self.typed(directory, f"EXT002-RECEIPT-{ordinal}", "PREFLIGHT_OBSERVATION_RECEIPT", {
                "ordinal": ordinal, "observation_id": observation,
                "stdout_sha256": digest(stdout), "stderr_sha256": digest(stderr),
                "runtime_sha256": digest(worker), "returncode": 0,
            }, [self.source(stdout_id, stdout), self.source(stderr_id, stderr), self.source("EXT002-WORKER", worker)])
            receipt_paths.append(receipt)
            artifacts.append(self.artifact(directory, f"EXT002-RECEIPT-{ordinal}", "PREFLIGHT_OBSERVATION_RECEIPT", receipt, schema=semantics.TYPED_SCHEMA))
        completion = self.typed(directory, "EXT002-COMPLETION", "PREFLIGHT_COMPLETION", {
            "attempt_sha256": digest(attempt),
            "ordered_receipt_sha256s": [digest(item) for item in receipt_paths],
            "observation_ids": list(OBSERVATIONS), "leader_reaped": True,
            "process_group_gone": True,
        }, [self.source(f"EXT002-RECEIPT-{index}", path) for index, path in enumerate(receipt_paths, 1)])
        artifacts.append(self.artifact(directory, "EXT002-COMPLETION", "PREFLIGHT_COMPLETION", completion, schema=semantics.TYPED_SCHEMA))
        manifest = self.manifest("S17-EXT-002", directory, artifacts, self.predecessors(1))
        self.add("S17-EXT-002", [self.receipt("S17-EXT-002", manifest)])

    def ext003(self) -> None:
        directory = self.root / "evidence/ext003-v2"
        directory.mkdir(parents=True)
        ext2_path, ext2_doc, ext2_sha = self.builder.resolutions["S17-EXT-002"]
        ext2_manifest = self.external / "ext002/s17-ext-002-manifest-v2.json"
        ext2 = json.loads(ext2_manifest.read_text())
        index = {item["artifact_id"]: item for item in ext2["artifacts"]}
        acceptance = self.typed(directory, "EXT003-ACCEPTANCE", "OWNER_ACCEPTANCE", {
            "ext002_resolution_id": ext2_doc["resolution_id"], "ext002_resolution_sha256": ext2_sha,
            "runtime_record_sha256": index["EXT002-RUNTIME"]["sha256"],
            "trust_record_sha256": index["EXT002-TRUST"]["sha256"],
            "distinct_auditor": False, "independent_review": False,
            "role_collapse_accepted": True,
        }, [self.source(ext2_doc["resolution_id"], ext2_path),
            {"id": "EXT002-RUNTIME", "size_bytes": index["EXT002-RUNTIME"]["size_bytes"], "sha256": index["EXT002-RUNTIME"]["sha256"]},
            {"id": "EXT002-TRUST", "size_bytes": index["EXT002-TRUST"]["size_bytes"], "sha256": index["EXT002-TRUST"]["sha256"]}], outcome="ACCEPTED")
        manifest = self.manifest("S17-EXT-003", directory, [
            self.artifact(directory, "EXT003-ACCEPTANCE", "OWNER_ACCEPTANCE", acceptance, schema=semantics.TYPED_SCHEMA)
        ], self.predecessors(2))
        self.add("S17-EXT-003", [self.builder.repository_evidence(manifest)])
        self.builder.add_transition()

    def ext004(self) -> None:
        directory = self.external / "ext004"; directory.mkdir(mode=0o700)
        keys = {
            "QUALIFICATION_NEAR_FAR": {"near_producer_cpu": 0, "near_consumer_cpu": 1, "far_producer_cpu": 0, "far_consumer_cpu": 26},
            "QUALIFICATION_CLOCK": {"clock_id": "SYNTHETIC-CLOCK", "per_core_samples": 8, "cross_core_samples": 8, "maximum_regressions": 0},
            "QUALIFICATION_ATOMICS_LAYOUT": {"pointer_width": 8, "pointer_alignment": 8, "termination_width": 4, "cache_line_bytes": 64},
            "QUALIFICATION_AFFINITY_MIGRATION": {"producer_cpu": 0, "consumer_cpu": 1, "sample_count": 8, "migration_count": 0},
            "QUALIFICATION_NUMA_PAGES": {"region_count": 3, "page_count": 64, "wrong_node_pages": 0},
            "QUALIFICATION_STORAGE_RECOVERY": {"capacity_bytes": 1048576, "recovery_test_id": "SYNTHETIC"},
            "QUALIFICATION_HARDWARE_PREFETCH": {"mapping_id": "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1"},
            "QUALIFICATION_STAND_PRESTATE": {"stand_id": "SYNTHETIC-STAND-NOT-ACCESSED", "capture_id": "SYNTHETIC"},
            "QUALIFICATION_Q15_COLLECTOR": {"collector_count": 6},
        }
        hash_fields = {
            "QUALIFICATION_NEAR_FAR": ("topology_sha256",),
            "QUALIFICATION_CLOCK": ("qualification_sha256",),
            "QUALIFICATION_ATOMICS_LAYOUT": ("layout_sha256",),
            "QUALIFICATION_AFFINITY_MIGRATION": ("readback_sha256",),
            "QUALIFICATION_NUMA_PAGES": ("residency_sha256",),
            "QUALIFICATION_STORAGE_RECOVERY": ("recovery_artifact_sha256",),
            "QUALIFICATION_HARDWARE_PREFETCH": ("prestate_sha256", "readback_sha256", "restoration_sha256"),
            "QUALIFICATION_STAND_PRESTATE": ("inventory_sha256",),
            "QUALIFICATION_Q15_COLLECTOR": ("collector_manifest_sha256", "qualification_archive_sha256"),
        }
        predecessor_path, predecessor_doc, _ = self.builder.resolutions["S17-EXT-003"]
        artifacts = []
        for role, values in keys.items():
            artifact_id = "EXT004-" + role
            bindings = [self.source(predecessor_doc["resolution_id"], predecessor_path)]
            for field in hash_fields[role]:
                source_id = f"{artifact_id}-{field.upper()}"
                source = directory / f"{source_id.lower()}.bin"
                source.write_bytes(canonical({"synthetic_test_only": True,
                                              "role": role, "field": field}))
                values[field] = digest(source)
                bindings.append(self.source(source_id, source))
                artifacts.append(self.artifact(directory, source_id,
                                               "QUALIFICATION_SOURCE", source))
            path = self.typed(directory, artifact_id, role, values,
                              bindings,
                              outcome="VERIFIED")
            artifacts.append(self.artifact(directory, artifact_id, role, path, schema=semantics.TYPED_SCHEMA))
        manifest = self.manifest("S17-EXT-004", directory, artifacts, self.predecessors(3))
        self.add("S17-EXT-004", [self.receipt("S17-EXT-004", manifest)])

    def _sign(self, path: pathlib.Path) -> pathlib.Path:
        result = subprocess.run(
            ["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(self.builder.signing_key),
             "-n", "cpu-prefetch-stage17-fixed-action-test-v2", str(path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=10,
        )
        signature = pathlib.Path(str(path) + ".sig")
        if result.returncode != 0 or not signature.is_file():
            raise CheckError("synthetic phase authorization signing failed")
        return signature

    def action(self, action_id: str, required: int,
               directory: pathlib.Path | None = None) -> dict[str, Any]:
        directory = directory or self.external / ("action-" + action_id.lower().replace("-", "_"))
        directory.mkdir(mode=0o700)
        validation = journal.validate_operational_journal(
            repository_root=self.root,
            latest_journal=self.builder.latest_path.relative_to(self.root),
            journal_directory=self.root / "config/stage17/journal",
            pilot_archive=self.builder.pilot_archive,
            pilot_sidecar=self.builder.pilot_sidecar,
            allow_synthetic_test_evidence=True,
        )
        action_plan = json.loads((self.root / controller.ACTION_PLAN).read_text())
        definition = next(item for item in action_plan["actions"] if item["action_id"] == action_id)
        predecessors = [
            {"input_id": item, "resolution_id": validation.resolutions[item].resolution_id,
             "sha256": validation.resolutions[item].sha256}
            for item in definition["required_resolution_ids"]
        ]
        runtime, release = controller._runtime_from_context(action_id, validation)
        request = {
            "schema_version": "cpu-prefetch-stage17-fixed-action-request/2",
            "request_id": f"SYNTHETIC-{action_id}-REQUEST-v2",
            "action_id": action_id, "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
            "authorization_id": f"SYNTHETIC-{action_id}-AUTH-v2",
            "attempt_id": f"SYNTHETIC-{action_id}-ATTEMPT-v2",
            "runtime_binding": {key: runtime[key] for key in ("role", "profile", "size_bytes", "sha256")},
            "release_binding": release, "predecessor_resolutions": predecessors,
            "action_inputs": {"fixture_nonce": f"{action_id}-compiled-dispatch"},
            "synthetic_test_only": True, "phase18_authority": False,
        }
        request_path = directory / "request-v2.json"; write(request_path, request)
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        ext2, ext3 = validation.resolutions["S17-EXT-002"], validation.resolutions["S17-EXT-003"]
        authorization = {
            "schema_version": "cpu-prefetch-stage17-phase-action-authorization/2",
            "authorization_id": request["authorization_id"], "action_id": action_id,
            "actor": "synthetic-stage17-owner",
            "target": {"stand_id": "SYNTHETIC-STAND-NOT-ACCESSED"},
            "issued_at_utc": (now - dt.timedelta(seconds=10)).isoformat().replace("+00:00", "Z"),
            "expires_at_utc": (now + dt.timedelta(seconds=300)).isoformat().replace("+00:00", "Z"),
            "trust_context": {"ext002_resolution": {"input_id": ext2.input_id, "resolution_id": ext2.resolution_id, "sha256": ext2.sha256}, "ext003_resolution": {"input_id": ext3.input_id, "resolution_id": ext3.resolution_id, "sha256": ext3.sha256}},
            "predecessor_resolutions": predecessors,
            "fixed_action_definition_sha256": digest(self.root / controller.ACTION_PLAN),
            "request_binding": {"path": str(request_path), "size_bytes": request_path.stat().st_size, "sha256": digest(request_path)},
            "evidence_root": str(directory), "permission_matrix": definition["permission_matrix"],
            "max_wall_seconds": 180, "one_attempt": True, "retry_allowed": False,
            "stop_first": True, "retain_partial": True, "stage18_authority": False,
        }
        authorization_path = directory / "authorization-v2.json"; write(authorization_path, authorization)
        signature = self._sign(authorization_path)
        outcome = controller.execute_once(
            repository_root=self.root,
            journal=self.builder.latest_path.relative_to(self.root),
            journal_directory=self.root / "config/stage17/journal",
            authorization_path=authorization_path, signature_path=signature,
            test_linked_worker=True,
            pilot_archive=self.builder.pilot_archive,
            pilot_sidecar=self.builder.pilot_sidecar,
        )
        self.positive_actions += 1
        return {"directory": directory, "authorization": authorization_path,
                "signature": signature, "request": request_path,
                "attempt": outcome.attempt_path, "result": outcome.result_path,
                "completion": outcome.completion_path, "result_document": outcome.result}

    def ext005(self) -> None:
        action = self.action("Q15-W", 4)
        directory = action["directory"]
        role_paths = {
            "PHASE_ACTION_AUTHORIZATION": action["authorization"],
            "AUTHORIZATION_SIGNATURE": action["signature"],
            "PHASE_ACTION_REQUEST": action["request"],
            "PHASE_ACTION_ATTEMPT": action["attempt"],
            "PHASE_ACTION_RESULT": action["result"],
            "PHASE_ACTION_COMPLETION": action["completion"],
        }
        schema_for = {
            "PHASE_ACTION_AUTHORIZATION": semantics.AUTH_SCHEMA,
            "PHASE_ACTION_REQUEST": semantics.REQUEST_SCHEMA,
            "PHASE_ACTION_ATTEMPT": semantics.ATTEMPT_SCHEMA,
            "PHASE_ACTION_RESULT": semantics.RESULT_SCHEMA,
            "PHASE_ACTION_COMPLETION": semantics.COMPLETION_SCHEMA,
        }
        artifacts = []
        for role, path in role_paths.items():
            artifact_id = "EXT005-" + role
            lineage = []
            if role == "AUTHORIZATION_SIGNATURE":
                lineage = [{"id": "EXT005-PHASE_ACTION_AUTHORIZATION", "sha256": digest(action["authorization"])}]
            artifacts.append(self.artifact(directory, artifact_id, role, path,
                                           schema=schema_for.get(role), lineage=lineage))
        manifest = self.manifest("S17-EXT-005", directory, artifacts, self.predecessors(4))
        index = self.root / "evidence/ext005-mixed-index.json"
        write(index, {"schema_version": "cpu-prefetch-stage17-mixed-evidence-index/2",
                      "input_id": "S17-EXT-005", "manifest_sha256": digest(manifest),
                      "synthetic_test_only": True, "phase18_authority": False})
        auth = json.loads(action["authorization"].read_text())
        summary = {"authorization_id": auth["authorization_id"],
                   "evidence_path": str(action["authorization"]),
                   "issued_at_utc": auth["issued_at_utc"],
                   "expires_at_utc": auth["expires_at_utc"],
                   "authority_scope": "PRIVILEGED_QUALIFICATION_CONTROL"}
        self.add("S17-EXT-005", [self.builder.repository_evidence(index),
                                  self.receipt("S17-EXT-005", manifest)], summary)

    def ext006(self) -> None:
        directory = self.external / "ext006"; directory.mkdir(mode=0o700)
        source_revision = "d" * 40
        top = directory / "bundle-tree"; top.mkdir()
        worker_member = top / "release/bin/cpu_prefetch_runner"; worker_member.parent.mkdir(parents=True)
        shutil.copyfile(self.external / "ext002/cpu_prefetch_stage17_test_worker", worker_member)
        manifest = top / "BUNDLE_MANIFEST.json"
        write(manifest, {"bundle_profile": "STAGE17-PILOT-CANDIDATE-BUNDLE-v2",
                         "source_archive": {"source_revision": source_revision},
                         "stage17_fixed_action_runtime": {"member_path": "release/bin/cpu_prefetch_runner", "size_bytes": worker_member.stat().st_size, "sha256": digest(worker_member), "role": "STAGE17_FIXED_ACTION_WORKER", "runtime_profile": "STAGE17-FIXED-ACTION-WORKER-v2", "supported_actions": ["Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c", "STAGE17-BLINDED-PILOT"]},
                         "pilot_authorized": False, "confirmatory_authorized": False,
                         "dynamic_qualification_authorized": False})
        archive = directory / "pilot-candidate-v2.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(top, arcname="candidate")
        sidecar = directory / "pilot-candidate-v2.tar.gz.sha256"
        sidecar.write_text(f"{digest(archive)}  {archive.name}\n", encoding="ascii")
        contract = self.root / "config/stage17/synthetic-pilot-candidate-contract-v2.json"
        write(contract, {"schema_version": "cpu-prefetch-stage17-pilot-candidate-external-contract/2", "contract_id": "SYNTHETIC-EXT006-v2-TEST-ONLY", "protocol_version": "2.0.0-pre.2", "source_revision": source_revision, "archive": {"filename": archive.name, "size_bytes": archive.stat().st_size, "sha256": digest(archive)}, "sidecar": {"filename": sidecar.name, "size_bytes": sidecar.stat().st_size, "sha256": digest(sidecar), "exact_ascii": sidecar.read_text()}, "manifest": {"member_path": "BUNDLE_MANIFEST.json", "size_bytes": manifest.stat().st_size, "sha256": digest(manifest), "bundle_profile": "STAGE17-PILOT-CANDIDATE-BUNDLE-v2"}, "worker": {"member_path": "release/bin/cpu_prefetch_runner", "size_bytes": worker_member.stat().st_size, "sha256": digest(worker_member), "role": "STAGE17_FIXED_ACTION_WORKER", "runtime_profile": "STAGE17-FIXED-ACTION-WORKER-v2", "supported_actions": ["Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c", "STAGE17-BLINDED-PILOT"]}, "custody": {"archive_locator": str(archive), "sidecar_locator": str(sidecar), "manifest_locator": "candidate/BUNDLE_MANIFEST.json", "primary_domain_id": "SYNTHETIC-CUSTODY-A", "secondary_domain_id": "SYNTHETIC-CUSTODY-B", "integration_verifier_version": "2"}, "authority_boundary": {"stand_access": False, "qualification": False, "calibration": False, "pilot": False, "phase18": False}})
        receipt = self.receipt("S17-EXT-006", archive, contract=contract,
                               sidecars=[sidecar],
                               verifier_id="STAGE17-PILOT-CANDIDATE-EXTERNAL-VERIFIER",
                               verifier_version="2")
        self.add("S17-EXT-006", [receipt])
        self.builder.pilot_archive, self.builder.pilot_sidecar = archive, sidecar
        self.builder.add_transition()

    def ext007(self) -> None:
        directory = self.external / "ext007"; directory.mkdir(mode=0o700)
        artifacts = []
        results: dict[str, str] = {}
        for token, action_id in (("Q16A", "Q16a"), ("Q16B", "Q16b"), ("Q16C", "Q16c")):
            action_directory = directory / token.lower()
            action = self.action(action_id, 6, action_directory)
            prefix = f"CALIBRATION_{token}"
            mapping = {
                f"{prefix}_AUTHORIZATION": action["authorization"],
                "AUTHORIZATION_SIGNATURE": action["signature"],
                f"{prefix}_REQUEST": action["request"], f"{prefix}_ATTEMPT": action["attempt"],
                f"{prefix}_RESULT": action["result"], f"{prefix}_COMPLETION": action["completion"],
            }
            schema_for = {f"{prefix}_AUTHORIZATION": semantics.AUTH_SCHEMA,
                          f"{prefix}_REQUEST": semantics.REQUEST_SCHEMA,
                          f"{prefix}_ATTEMPT": semantics.ATTEMPT_SCHEMA,
                          f"{prefix}_RESULT": semantics.RESULT_SCHEMA,
                          f"{prefix}_COMPLETION": semantics.COMPLETION_SCHEMA}
            for role, source in mapping.items():
                artifact_id = f"EXT007-{token}-{role}"
                lineage = []
                if role == "AUTHORIZATION_SIGNATURE":
                    lineage = [{"id": f"EXT007-{token}-{prefix}_AUTHORIZATION", "sha256": digest(action["authorization"])}]
                artifacts.append(self.artifact(directory, artifact_id, role, source,
                                               schema=schema_for.get(role), lineage=lineage))
            results[action_id] = digest(action["result"])
        predecessor = self.builder.resolutions["S17-EXT-006"]
        freeze = self.typed(directory, "EXT007-FREEZE", "CALIBRATION_FREEZE", {
            "q16a_result_sha256": results["Q16a"], "q16b_result_sha256": results["Q16b"],
            "q16c_result_sha256": results["Q16c"], "mu_ref": {"numerator": 1, "denominator": 1},
            "distance_context_count": 6, "zero_loss_bound": {"numerator": 0, "denominator": 1},
        }, [self.source(predecessor[1]["resolution_id"], predecessor[0])], outcome="FROZEN")
        artifacts.append(self.artifact(directory, "EXT007-FREEZE", "CALIBRATION_FREEZE", freeze, schema=semantics.TYPED_SCHEMA))
        manifest = self.manifest("S17-EXT-007", directory, artifacts, self.predecessors(6))
        self.add("S17-EXT-007", [self.receipt("S17-EXT-007", manifest)])

    def ext008(self) -> None:
        directory = self.root / "evidence/ext008-v2"; directory.mkdir(parents=True)
        predecessor = self.builder.resolutions["S17-EXT-007"]
        validation = journal.validate_operational_journal(
            repository_root=self.root,
            latest_journal=self.builder.latest_path.relative_to(self.root),
            journal_directory=self.root / "config/stage17/journal",
            pilot_archive=self.builder.pilot_archive,
            pilot_sidecar=self.builder.pilot_sidecar,
            allow_synthetic_test_evidence=True,
        )
        known = [
            (artifact_id, binding["sha256"])
            for resolution in validation.resolutions.values()
            for artifact_id, binding in resolution.semantic_context.get("artifact_index", {}).items()
        ]
        if len(known) < 21:
            raise CheckError("synthetic admitted evidence set is unexpectedly incomplete")
        evidence_kinds = [
            "PROTOCOL_SNAPSHOT", "SOURCE_RELEASE", "RUN_PLAN", "WARMUP_SCHEDULE",
            "MEASUREMENT_SCHEDULE", "SEED_DERIVATION", "PLATFORM_INVENTORY",
            "PLATFORM_REQUEST", "PLATFORM_VERIFICATION", "HARDWARE_PREFETCH_MAPPING",
            "SOFTWARE_PREFETCH_MAPPING", "CLOCK_QUALIFICATION", "QUEUE_PROVENANCE",
            "RUNTIME_ATOMIC_LAYOUT", "ADDRESS_RESIDENCY", "STORAGE_BUDGET",
            "DURABILITY_DOMAINS", "CALIBRATION_FREEZE", "EXECUTION_LIMITS",
            "AUTHORITY_CUSTODY", "PHASE_EXECUTION_AUTHORIZATION",
        ]
        binding_id = "SYNTHETIC-PILOT-RUNNER-BINDING"
        runner_evidence = [
            {"kind": kind, "artifact_id": artifact_id,
             "path": f"admitted-context/{artifact_id}", "sha256": artifact_sha,
             "binding_id": binding_id, "immutable": True, "eligible": True}
            for kind, (artifact_id, artifact_sha) in zip(evidence_kinds, known[:21])
        ]
        runner_admission = {
            "schema_version": "cpu-prefetch-runner-admission/3",
            "protocol_version": "2.0.0-pre.2",
            "runner_profile_id": "STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v3",
            "cpu_pair_selection_id": "XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1",
            "relax_mapping_id": "X86-PAUSE-ONE-PER-RELAX-SITE-v1",
            "source_revision": "SYNTHETIC-TEST-ONLY",
            "binary_sha256": validation.resolutions["S17-EXT-006"].semantic_context["release_artifact_sha256"],
            "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED", "binding_id": binding_id,
            "package": "R0", "placement": "NEAR", "producer_cpu": 0,
            "consumer_cpu": 1,
            "execution_limits": {"controller_start_poll_limit": 1000000,
                                 "worker_start_poll_limit": 1000000},
            "evidence": runner_evidence,
        }
        admission_path = directory / "runner-admission-v3.json"
        write(admission_path, runner_admission)
        schedule_document = {
            "schema_version": "cpu-prefetch-stage17-frozen-schedule/2",
            "arrival_family": "OPEN_LOOP_FROZEN",
            "deadline_ticks": list(range(16)), "origin_ticks": 0,
            "horizon_ticks": 1000,
        }
        schedule_path = directory / "pilot-schedule-v2.json"
        write(schedule_path, schedule_document)
        admission_source = {"id": "EXT008-RUNNER-ADMISSION",
                            "size_bytes": admission_path.stat().st_size,
                            "sha256": digest(admission_path)}
        schedule_source = {"id": "EXT008-SCHEDULE",
                           "size_bytes": schedule_path.stat().st_size,
                           "sha256": digest(schedule_path)}
        plan = self.typed(directory, "EXT008-PLAN", "PILOT_PLAN", {
            "run_ids": ["SYNTHETIC-PILOT-RUN-001"], "schedule_sha256s": [digest(schedule_path)],
            "seed_ids": ["SYNTHETIC-PILOT-SEED"], "master_seed_hexes": ["0" * 64],
            "horizons": [1000], "capacities": [64], "offered_counts": [16],
            "packages": ["R0"], "d2_cache_lines": [2],
            "cache_line_bytes": 64, "base_page_bytes": 4096,
            "runner_admission_sha256s": [digest(admission_path)],
            "runner_admission_artifact_ids": ["EXT008-RUNNER-ADMISSION"],
            "runner_evidence_set_sha256s": [hashlib.sha256(canonical(runner_evidence)).hexdigest()],
            "schedule_artifact_ids": ["EXT008-SCHEDULE"],
            "treatment_blind_labels": ["BLIND-A"], "stop_rules": ["STOP_FIRST_FAILURE"],
            "resource_limits": [{"max_wall_seconds": 180}],
            "artifact_names": ["stage17-blinded-pilot-output-v2.json"],
            "predecessor_resolution_sha256s": [self.builder.resolutions[f"S17-EXT-{i:03d}"][2] for i in range(1, 8)],
        }, [self.source(predecessor[1]["resolution_id"], predecessor[0]),
            admission_source, schedule_source], outcome="FROZEN")
        manifest = self.manifest("S17-EXT-008", directory, [
            self.artifact(directory, "EXT008-PLAN", "PILOT_PLAN", plan,
                          schema=semantics.TYPED_SCHEMA),
            self.artifact(directory, "EXT008-RUNNER-ADMISSION", "RUNNER_ADMISSION",
                          admission_path, schema=semantics.RUNNER_ADMISSION_SCHEMA),
            self.artifact(directory, "EXT008-SCHEDULE", "PILOT_SCHEDULE",
                          schedule_path, schema=semantics.SCHEDULE_SCHEMA),
        ], self.predecessors(7))
        self.add("S17-EXT-008", [self.builder.repository_evidence(manifest)])

    def ext009(self) -> None:
        directory = self.external / "ext009"; directory.mkdir(mode=0o700)
        predecessor = self.builder.resolutions["S17-EXT-008"]
        common = [self.source(predecessor[1]["resolution_id"], predecessor[0])]
        domain_a, domain_b = directory / "custody-a", directory / "custody-b"
        domain_a.mkdir(mode=0o700); domain_b.mkdir(mode=0o700)
        source = directory / "source-copy.bin"; source.write_bytes(b"synthetic-custody-copy")
        primary, secondary = domain_a / "pilot-copy.bin", domain_b / "pilot-copy.bin"
        shutil.copyfile(source, primary); shutil.copyfile(source, secondary)
        failure_fixture = directory / "recovery-failure.bin"
        restored = directory / "recovery-restored.bin"
        failure_fixture.write_bytes(b"synthetic-recovery")
        shutil.copyfile(failure_fixture, restored)
        records = [
            ("EXT009-BUDGET", "STORAGE_BUDGET", {"planned_bytes": 1024, "available_bytes": 4096, "temporary_copies": 1, "durable_copies": 2, "budget_formula_id": "STAGE11-BUDGET-v1"}),
            ("EXT009-CUSTODY-A", "CUSTODY_DOMAIN", {"domain_id": "A", "locator": str(domain_a), "owner_uid": os.getuid(), "mode": "0700", "independent_domain_id": "B"}),
            ("EXT009-CUSTODY-B", "CUSTODY_DOMAIN", {"domain_id": "B", "locator": str(domain_b), "owner_uid": os.getuid(), "mode": "0700", "independent_domain_id": "A"}),
            ("EXT009-LEDGER", "COPY_LEDGER", {"source_locator": str(source), "source_sha256": digest(source), "primary_copy_locator": str(primary), "primary_copy_sha256": digest(primary), "secondary_copy_locator": str(secondary), "secondary_copy_sha256": digest(secondary), "transfer_verified_at_utc": legacy.utc(4)}),
            ("EXT009-RECOVERY", "RECOVERY_TEST", {"failure_fixture_locator": str(failure_fixture), "failure_fixture_sha256": digest(failure_fixture), "restored_locator": str(restored), "restored_sha256": digest(restored), "recovery_procedure_id": "SYNTHETIC-RECOVERY", "result_code": "PASS"}),
        ]
        artifacts = []
        for artifact_id, role, values in records:
            path = self.typed(directory, artifact_id, role, values, common, outcome="VERIFIED")
            artifacts.append(self.artifact(directory, artifact_id, role, path, schema=semantics.TYPED_SCHEMA))
        manifest = self.manifest("S17-EXT-009", directory, artifacts, self.predecessors(8))
        index = self.root / "evidence/ext009-mixed-index.json"
        write(index, {"schema_version": "cpu-prefetch-stage17-mixed-evidence-index/2", "input_id": "S17-EXT-009", "manifest_sha256": digest(manifest), "synthetic_test_only": True, "phase18_authority": False})
        self.add("S17-EXT-009", [self.builder.repository_evidence(index), self.receipt("S17-EXT-009", manifest)])

    def ext010(self) -> None:
        directory = self.root / "evidence/ext010-v2"; directory.mkdir(parents=True)
        validation = journal.validate_operational_journal(repository_root=self.root, latest_journal=self.builder.latest_path.relative_to(self.root), journal_directory=self.root / "config/stage17/journal", pilot_archive=self.builder.pilot_archive, pilot_sidecar=self.builder.pilot_sidecar, allow_synthetic_test_evidence=True)
        definition = next(item for item in json.loads((self.root / controller.ACTION_PLAN).read_text())["actions"] if item["action_id"] == "STAGE17-BLINDED-PILOT")
        predecessors = [{"input_id": item, "resolution_id": validation.resolutions[item].resolution_id, "sha256": validation.resolutions[item].sha256} for item in definition["required_resolution_ids"]]
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        request_placeholder = directory / "pilot-request-v2.json"
        pilot_output = self.external / "future-pilot-output"
        pilot_output.mkdir(mode=0o700)
        # EXT010 authorizes the later request family; it binds the exact frozen
        # plan and run set without executing it during local closure.
        plan = validation.resolutions["S17-EXT-008"].semantic_context["pilot_plan"]
        request = {"schema_version": "cpu-prefetch-stage17-fixed-action-request/2", "request_id": "SYNTHETIC-PILOT-REQUEST", "action_id": "STAGE17-BLINDED-PILOT", "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED", "authorization_id": "SYNTHETIC-PILOT-AUTH", "attempt_id": "SYNTHETIC-PILOT-ATTEMPT", "runtime_binding": {"role": "STAGE17_FIXED_ACTION_WORKER", "profile": "STAGE17-FIXED-ACTION-WORKER-v2", "size_bytes": validation.resolutions["S17-EXT-006"].semantic_context["release_artifact_size_bytes"], "sha256": validation.resolutions["S17-EXT-006"].semantic_context["release_artifact_sha256"]}, "release_binding": {"source_resolution_id": validation.resolutions["S17-EXT-006"].resolution_id, "source_resolution_sha256": validation.resolutions["S17-EXT-006"].sha256, "artifact_role": "STAGE17_FIXED_ACTION_WORKER", "runtime_profile": "STAGE17-FIXED-ACTION-WORKER-v2", "worker_size_bytes": validation.resolutions["S17-EXT-006"].semantic_context["release_artifact_size_bytes"], "worker_sha256": validation.resolutions["S17-EXT-006"].semantic_context["release_artifact_sha256"]}, "predecessor_resolutions": predecessors, "action_inputs": {"fixture_nonce": "pilot-future-execution"}, "synthetic_test_only": True, "phase18_authority": False}
        write(request_placeholder, request)
        ext2, ext3 = validation.resolutions["S17-EXT-002"], validation.resolutions["S17-EXT-003"]
        authorization = {"schema_version": "cpu-prefetch-stage17-phase-action-authorization/2", "authorization_id": "SYNTHETIC-PILOT-AUTH", "action_id": "STAGE17-BLINDED-PILOT", "actor": "synthetic-stage17-owner", "target": {"stand_id": "SYNTHETIC-STAND-NOT-ACCESSED"}, "issued_at_utc": (now - dt.timedelta(seconds=10)).isoformat().replace("+00:00", "Z"), "expires_at_utc": (now + dt.timedelta(seconds=300)).isoformat().replace("+00:00", "Z"), "trust_context": {"ext002_resolution": {"input_id": ext2.input_id, "resolution_id": ext2.resolution_id, "sha256": ext2.sha256}, "ext003_resolution": {"input_id": ext3.input_id, "resolution_id": ext3.resolution_id, "sha256": ext3.sha256}}, "predecessor_resolutions": predecessors, "fixed_action_definition_sha256": digest(self.root / controller.ACTION_PLAN), "request_binding": {"path": str(request_placeholder), "size_bytes": request_placeholder.stat().st_size, "sha256": digest(request_placeholder)}, "evidence_root": str(pilot_output), "permission_matrix": definition["permission_matrix"], "max_wall_seconds": 180, "one_attempt": True, "retry_allowed": False, "stop_first": True, "retain_partial": True, "stage18_authority": False}
        auth = directory / "pilot-authorization-v2.json"; write(auth, authorization)
        signature = self._sign(auth)
        auth_artifact = self.artifact(directory, "EXT010-AUTH", "PILOT_AUTHORIZATION", auth, schema=semantics.AUTH_SCHEMA)
        request_artifact = self.artifact(directory, "EXT010-REQUEST", "PILOT_REQUEST",
                                         request_placeholder,
                                         schema=semantics.REQUEST_SCHEMA)
        sig_artifact = self.artifact(directory, "EXT010-SIGNATURE", "AUTHORIZATION_SIGNATURE", signature, lineage=[{"id": "EXT010-AUTH", "sha256": digest(auth)}])
        manifest = self.manifest("S17-EXT-010", directory,
                                 [auth_artifact, request_artifact, sig_artifact],
                                 self.predecessors(9))
        summary = {"authorization_id": authorization["authorization_id"], "evidence_path": auth.relative_to(self.root).as_posix(), "issued_at_utc": authorization["issued_at_utc"], "expires_at_utc": authorization["expires_at_utc"], "authority_scope": "STAGE17_PILOT_PHASE_ONLY"}
        self.add("S17-EXT-010", [self.builder.repository_evidence(manifest)], summary)

    def execute_pilot(self) -> dict[str, Any]:
        directory = self.root / "evidence/ext010-v2"
        outcome = controller.execute_once(
            repository_root=self.root,
            journal=self.builder.latest_path.relative_to(self.root),
            journal_directory=self.root / "config/stage17/journal",
            authorization_path=directory / "pilot-authorization-v2.json",
            signature_path=directory / "pilot-authorization-v2.json.sig",
            test_linked_worker=True,
            pilot_archive=self.builder.pilot_archive,
            pilot_sidecar=self.builder.pilot_sidecar,
        )
        self.positive_actions += 1
        return {
            "authorization": directory / "pilot-authorization-v2.json",
            "attempt": outcome.attempt_path, "result": outcome.result_path,
            "completion": outcome.completion_path, "result_document": outcome.result,
        }

    def build(self) -> journal.OperationalJournalValidation:
        self.ext001(); self.ext002(); self.ext003(); self.ext004(); self.ext005(); self.ext006()
        self.ext007(); self.ext008(); self.ext009(); self.ext010()
        return journal.validate_operational_journal(repository_root=self.root, latest_journal=self.builder.latest_path.relative_to(self.root), journal_directory=self.root / "config/stage17/journal", pilot_archive=self.builder.pilot_archive, pilot_sidecar=self.builder.pilot_sidecar, as_of_utc=dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"), allow_synthetic_test_evidence=True)


def expect_failure(label: str, action: Callable[[], Any]) -> None:
    try:
        action()
    except BaseException:
        print(f"stage17-fixed-production: PASS negative={label}")
        return
    raise CheckError(f"negative fixture was admitted: {label}")


def file_binding(path: pathlib.Path) -> dict[str, Any]:
    return {"path": str(path), "size_bytes": path.stat().st_size,
            "sha256": digest(path)}


def exercise_exit_and_phase18(
    fixture: Fixture, validation: journal.OperationalJournalValidation,
    pilot: dict[str, Any],
) -> tuple[int, int]:
    directory = fixture.external / "stage17-exit-v2"
    directory.mkdir(mode=0o700)
    records: list[pathlib.Path] = []
    record_hashes: dict[str, str] = {}
    previous = exit_machine.EXIT_GENESIS_SHA256
    sequence = 0
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)

    def append(kind: str, sources: list[pathlib.Path], payload: dict[str, Any]) -> pathlib.Path:
        nonlocal previous, sequence
        sequence += 1
        path = directory / f"record-{sequence:02d}-{kind.lower().replace('_', '-')}.json"
        write(path, {
            "schema_version": "cpu-prefetch-stage17-exit-record/2",
            "record_id": f"SYNTHETIC-{kind}-{sequence:02d}",
            "record_type": kind, "sequence_number": sequence,
            "previous_record_sha256": previous,
            "created_at_utc": (now + dt.timedelta(seconds=sequence)).isoformat().replace("+00:00", "Z"),
            "actor": "synthetic-stage17-owner", "synthetic_test_only": True,
            "source_bindings": [file_binding(item) for item in sources],
            "payload": payload, "automatic_transition": False,
            "retry_authority": False, "phase18_authority": False,
        })
        previous = digest(path)
        record_hashes[kind] = previous
        records.append(path)
        return path

    def transition(from_state: str, to_state: str,
                   required: list[tuple[str, pathlib.Path]]) -> None:
        append("STATE_TRANSITION", [item[1] for item in required], {
            "from_state": from_state, "to_state": to_state,
            "evidence_record_types": [item[0] for item in required],
        })

    authority = append("PILOT_AUTHORITY_ADMISSION", [pilot["authorization"]], {
        "authorization_sha256": digest(pilot["authorization"]),
        "resolution_id": validation.resolutions["S17-EXT-010"].resolution_id,
        "resolution_sha256": validation.resolutions["S17-EXT-010"].sha256,
    })
    transition("READY_FOR_STAGE17_PHASE_AUTHORIZATION", "PILOT_AUTHORIZED",
               [("PILOT_AUTHORITY_ADMISSION", authority)])
    attempt = append("PILOT_ATTEMPT", [pilot["attempt"]], {
        "attempt_sha256": digest(pilot["attempt"]),
    })
    result = append("PILOT_ACTION_RESULT", [pilot["result"]], {
        "result_sha256": digest(pilot["result"]),
    })
    completion = append("PILOT_CONTROLLER_COMPLETION", [pilot["completion"]], {
        "completion_sha256": digest(pilot["completion"]),
    })
    transition("PILOT_AUTHORIZED", "PILOT_EXECUTED", [
        ("PILOT_ATTEMPT", attempt), ("PILOT_ACTION_RESULT", result),
        ("PILOT_CONTROLLER_COMPLETION", completion),
    ])
    sealed = append("SEALED_PILOT_ARTIFACT_MANIFEST", [pilot["result"], pilot["completion"]], {
        "pilot_result_sha256": record_hashes["PILOT_ACTION_RESULT"],
        "controller_completion_sha256": record_hashes["PILOT_CONTROLLER_COMPLETION"],
        "sealed": True,
    })
    freeze = append("TREATMENT_BLIND_FREEZE", [pilot["result"]], {
        "treatment_blind": True, "confirmatory_outcomes_accessed": False,
    })
    transition("PILOT_EXECUTED", "PILOT_EVIDENCE_SEALED", [
        ("SEALED_PILOT_ARTIFACT_MANIFEST", sealed),
        ("TREATMENT_BLIND_FREEZE", freeze),
    ])
    roles = append("ROLE_SEPARATION_DECLARATION", [sealed], {
        "role_collapse": "OWNER_OPERATOR_CUSTODIAN_AUDITOR",
        "independent_review": False, "accepted_for_stage17_pilot": True,
        "phase18_role_separation_unmodified": True,
    })
    statement = append("STAGE17_COMPLETION_STATEMENT", [fixture.builder.latest_path], {
        "admitted_resolutions": [
            {"input_id": item.input_id, "resolution_id": item.resolution_id,
             "sha256": item.sha256}
            for item in validation.resolutions.values()
        ],
        "pilot_evidence_sealed": True, "phase18_authority": False,
    })
    transition("PILOT_EVIDENCE_SEALED", "STAGE17_COMPLETE", [
        ("ROLE_SEPARATION_DECLARATION", roles),
        ("STAGE17_COMPLETION_STATEMENT", statement),
    ])
    readiness = append("PHASE18_READINESS_REPORT", [statement], {
        "stage17_completion_sha256": digest(statement),
        "status": "AUTHORIZATION_REQUIRED_SEPARATELY",
    })
    draft = append("PHASE18_AUTHORIZATION_DRAFT", [readiness], {
        "issued": False, "authorization_id": None,
        "stand_values": None, "stage17_authority_reuse_allowed": False,
    })
    transition("STAGE17_COMPLETE", "PHASE18_HANDOFF_PREPARED", [
        ("PHASE18_READINESS_REPORT", readiness),
        ("PHASE18_AUTHORIZATION_DRAFT", draft),
    ])
    exit_journal = directory / "stage17-exit-journal-v2.json"
    write(exit_journal, {
        "schema_version": "cpu-prefetch-stage17-exit-journal/2",
        "journal_id": "SYNTHETIC-STAGE17-EXIT-v2",
        "initial_state": "READY_FOR_STAGE17_PHASE_AUTHORIZATION",
        "operational_journal_sha256": validation.latest_journal_sha256,
        "record_references": [file_binding(item) for item in records],
        "current_state_claim": "PHASE18_HANDOFF_PREPARED",
        "synthetic_test_only": True, "phase18_authority": False,
    })
    exit_validation = exit_machine.validate_exit_journal_v2(
        repository_root=fixture.root, journal_path=exit_journal,
        operational_validation=validation, allow_synthetic=True,
    )
    if not exit_validation.stage17_complete or not exit_validation.phase18_handoff_prepared:
        raise CheckError("typed Stage 17 exit did not reach handoff preparation")

    phase = fixture.external / "phase18-v2"
    phase.mkdir(mode=0o700)
    key = phase / "phase18-signer"
    subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, check=True, timeout=10)
    public = pathlib.Path(str(key) + ".pub").read_text().strip()
    allowed = phase / "allowed-signers"
    allowed.write_text(f"synthetic-phase18-owner {public}\n", encoding="ascii")
    trust = {
        "schema_version": "cpu-prefetch-phase18-trust-context/2",
        "trust_context_id": "SYNTHETIC-PHASE18-TRUST-TEST-ONLY",
        "allowed_signers": file_binding(allowed),
        "principal": "synthetic-phase18-owner",
        "sshsig_namespace": "cpu-prefetch-phase18-access-test-v2",
        "signer_role": "SYNTHETIC-PHASE18-SIGNER",
        "reviewer_role": "SYNTHETIC-PHASE18-REVIEWER",
        "independent_from_stage17_authority": True,
    }
    trust_path = phase / "phase18-trust-context-v2.json"
    write(trust_path, trust)
    trust_sha = digest(trust_path)
    readiness_report = phase / "phase18-readiness-report-v2.json"
    write(readiness_report, {
        "schema_version": "cpu-prefetch-phase18-readiness-report/2",
        "issued": True, "report_id": "SYNTHETIC-PHASE18-READINESS-TEST-ONLY",
        "stage17_completion_sha256": digest(statement),
        "sealed_pilot_manifest_sha256": digest(sealed),
        "treatment_blind_freeze_sha256": digest(freeze),
        "independent_trust_context": file_binding(trust_path),
        "state": "READY_FOR_SEPARATE_PHASE18_AUTHORIZATION",
        "blockers": ["SEPARATE_PHASE18_AUTHORIZATION_REQUIRED"],
        "phase18_authority": False,
    })
    phase_auth = phase / "phase18-authorization-v2.json"
    write(phase_auth, {
        "schema_version": "cpu-prefetch-phase18-authorization/2",
        "authorization_id": "SYNTHETIC-PHASE18-AUTH-TEST-ONLY",
        "actor": "synthetic-phase18-owner",
        "issued_at_utc": (now - dt.timedelta(seconds=10)).isoformat().replace("+00:00", "Z"),
        "expires_at_utc": (now + dt.timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        "trust_context_id": trust["trust_context_id"],
        "trust_context_sha256": trust_sha,
        "stage17_completion_sha256": digest(statement),
        "phase18_readiness_sha256": digest(readiness_report),
        "allowed_chronology": list(exit_machine.PHASE18_STATES),
        "authority_scope": "PHASE18_ACCESS_TRANSITION_ONLY",
        "stage17_authority_reuse_allowed": False,
        "automatic_transition": False, "retry_allowed": False,
    })
    signed = subprocess.run(
        ["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(key), "-n",
         trust["sshsig_namespace"], str(phase_auth)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=10,
    )
    signature = pathlib.Path(str(phase_auth) + ".sig")
    if signed.returncode != 0 or not signature.is_file():
        raise CheckError("synthetic independent Phase 18 signing failed")
    phase_evidence = phase / "synthetic-sealed-evidence.json"
    write(phase_evidence, {"synthetic_test_only": True, "sealed": True})
    transitions = []
    prior = exit_machine.PHASE18_GENESIS_SHA256
    auth_sha = digest(phase_auth)
    for index, (source, target) in enumerate(zip(exit_machine.PHASE18_STATES,
                                                 exit_machine.PHASE18_STATES[1:]), 1):
        transition_document = {
            "sequence_number": index, "from_state": source, "to_state": target,
            "previous_transition_sha256": prior,
            "authorization_sha256": auth_sha,
            "evidence": [file_binding(phase_evidence)],
            "actor": "synthetic-phase18-owner",
            "timestamp_utc": (now + dt.timedelta(seconds=index)).isoformat().replace("+00:00", "Z"),
            "authority_scope": "PHASE18_ACCESS_TRANSITION_ONLY",
            "stage17_authority_used": False, "automatic_transition": False,
        }
        transitions.append(transition_document)
        prior = hashlib.sha256(exit_machine.canonical(transition_document)).hexdigest()
    phase_journal = phase / "phase18-access-journal-v2.json"
    phase_document = {
        "schema_version": "cpu-prefetch-phase18-access-journal/2",
        "journal_id": "SYNTHETIC-PHASE18-JOURNAL-v2",
        "authorization": file_binding(phase_auth),
        "signature": file_binding(signature),
        "trust_context_id": trust["trust_context_id"],
        "trust_context_sha256": trust_sha, "synthetic_test_only": True,
        "transitions": transitions, "current_state_claim": "ARCHIVED",
    }
    write(phase_journal, phase_document)
    actual = now.isoformat().replace("+00:00", "Z")
    if exit_machine.validate_phase18_access_journal_v2(
        repository_root=fixture.root, journal_path=phase_journal,
        readiness_report_path=readiness_report, actual_utc=actual,
        allow_synthetic=True,
    ) != "ARCHIVED":
        raise CheckError("Phase 18 chronology did not validate")

    negative = 0
    original_signature = signature.read_bytes()
    signature.write_bytes(b"UNSIGNED\n")
    expect_failure("phase18_unsigned_authority", lambda: exit_machine.validate_phase18_access_journal_v2(
        repository_root=fixture.root, journal_path=phase_journal,
        readiness_report_path=readiness_report, actual_utc=actual,
        allow_synthetic=True)); negative += 1
    signature.write_bytes(original_signature)
    expect_failure("phase18_expired_authority", lambda: exit_machine.validate_phase18_access_journal_v2(
        repository_root=fixture.root, journal_path=phase_journal,
        readiness_report_path=readiness_report,
        actual_utc=(now + dt.timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        allow_synthetic=True)); negative += 1
    original_trust = trust_path.read_bytes()
    self_rooted = copy.deepcopy(trust)
    self_rooted["trust_context_id"] = "SELF-ROOTED-UNADMITTED"
    write(trust_path, self_rooted)
    expect_failure("phase18_self_rooted_authority", lambda: exit_machine.validate_phase18_access_journal_v2(
        repository_root=fixture.root, journal_path=phase_journal,
        readiness_report_path=readiness_report, actual_utc=actual,
        allow_synthetic=True)); negative += 1
    trust_path.write_bytes(original_trust)
    original_phase_journal = phase_journal.read_bytes()
    stage17_reuse = json.loads(original_phase_journal)
    stage17_reuse["transitions"][0]["stage17_authority_used"] = True
    write(phase_journal, stage17_reuse)
    expect_failure("phase18_stage17_authority_reuse", lambda: exit_machine.validate_phase18_access_journal_v2(
        repository_root=fixture.root, journal_path=phase_journal,
        readiness_report_path=readiness_report, actual_utc=actual,
        allow_synthetic=True)); negative += 1
    phase_journal.write_bytes(original_phase_journal)
    return 2, negative


def self_test(worker: pathlib.Path, no_result_worker: pathlib.Path) -> tuple[int, int]:
    positive = 0; negative = 0
    with tempfile.TemporaryDirectory(prefix="stage17-fixed-production-") as temporary:
        fixture = Fixture(pathlib.Path(temporary), worker)
        # Predecessor must refuse before even parsing caller-controlled files.
        expect_failure("controller_v1_rejected_fail_open_predecessor", lambda: rejected_controller.execute_once(repository_root=ROOT, journal=pathlib.Path("missing"), journal_directory=pathlib.Path("missing"), authorization_path=pathlib.Path("missing"), signature_path=pathlib.Path("missing")))
        negative += 1
        fixture.ext001(); fixture.ext002(); fixture.ext003(); fixture.ext004()
        q15r = fixture.action("Q15-R", 3)
        if not q15r["result_document"]["synthetic_test_only"]:
            raise CheckError("compiled test-linked dispatcher classification drifted")
        positive += 1
        fixture.ext005(); fixture.ext006(); fixture.ext007(); fixture.ext008(); fixture.ext009(); fixture.ext010()
        validation = journal.validate_operational_journal(repository_root=fixture.root, latest_journal=fixture.builder.latest_path.relative_to(fixture.root), journal_directory=fixture.root / "config/stage17/journal", pilot_archive=fixture.builder.pilot_archive, pilot_sidecar=fixture.builder.pilot_sidecar, as_of_utc=dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"), allow_synthetic_test_evidence=True)
        if (validation.current_state, validation.resolution_count, validation.transition_count, validation.pilot_ready) != ("READY_FOR_STAGE17_PHASE_AUTHORIZATION", 10, 3, True):
            raise CheckError("ten-input/three-transition semantic projection failed")
        positive += 1
        pilot = fixture.execute_pilot()
        if pilot["result_document"]["action_id"] != "STAGE17-BLINDED-PILOT":
            raise CheckError("compiled dispatcher did not execute the admitted pilot action")
        validation = journal.validate_operational_journal(repository_root=fixture.root, latest_journal=fixture.builder.latest_path.relative_to(fixture.root), journal_directory=fixture.root / "config/stage17/journal", pilot_archive=fixture.builder.pilot_archive, pilot_sidecar=fixture.builder.pilot_sidecar, as_of_utc=dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"), allow_synthetic_test_evidence=True)
        exit_positive, exit_negative = exercise_exit_and_phase18(fixture, validation, pilot)
        positive += exit_positive
        negative += exit_negative
        if fixture.positive_actions != 6:  # all six closed dispatcher actions
            raise CheckError("compiled dispatcher did not execute all six fixed actions")
        positive += fixture.positive_actions

        unrelated_key = fixture.external / "unrelated-self-rooted-signer"
        subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(unrelated_key)],
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=True, timeout=10)
        self_rooted_auth = fixture.external / "self-rooted-authorization-v2.json"
        shutil.copyfile(q15r["authorization"], self_rooted_auth)
        subprocess.run(["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(unrelated_key),
                        "-n", "cpu-prefetch-stage17-fixed-action-test-v2",
                        str(self_rooted_auth)], stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=True, timeout=10)
        expect_failure("self_signed_unrelated_allowed_signers", lambda: controller.execute_once(
            repository_root=fixture.root,
            journal=fixture.builder.latest_path.relative_to(fixture.root),
            journal_directory=fixture.root / "config/stage17/journal",
            authorization_path=self_rooted_auth,
            signature_path=pathlib.Path(str(self_rooted_auth) + ".sig"),
            test_linked_worker=True,
            pilot_archive=fixture.builder.pilot_archive,
            pilot_sidecar=fixture.builder.pilot_sidecar)); negative += 1

        # Self-rooting cannot reach marker: replace admitted trust references
        # in a fresh authorization with an unrelated resolution identity.
        bad = copy.deepcopy(json.loads(q15r["authorization"].read_text()))
        bad["trust_context"]["ext003_resolution"]["sha256"] = "f" * 64
        bad_path = fixture.external / "self-rooted-authorization.json"; write(bad_path, bad)
        bad_sig = fixture._sign(bad_path)
        expect_failure("self_selected_trust_context", lambda: controller.execute_once(repository_root=fixture.root, journal=fixture.builder.latest_path.relative_to(fixture.root), journal_directory=fixture.root / "config/stage17/journal", authorization_path=bad_path, signature_path=bad_sig, test_linked_worker=True))
        negative += 1

        wrong_request_document = json.loads(q15r["request"].read_text())
        wrong_request_document["action_id"] = "Q16a"
        wrong_request_document["authorization_id"] = "SYNTHETIC-WRONG-ACTION-AUTH"
        wrong_request_path = fixture.external / "wrong-action-request-v2.json"
        write(wrong_request_path, wrong_request_document)
        wrong_authorization = json.loads(q15r["authorization"].read_text())
        wrong_authorization["authorization_id"] = "SYNTHETIC-WRONG-ACTION-AUTH"
        wrong_authorization["request_binding"] = {
            "path": str(wrong_request_path),
            "size_bytes": wrong_request_path.stat().st_size,
            "sha256": digest(wrong_request_path),
        }
        wrong_authorization["evidence_root"] = str(fixture.external / "wrong-action-output")
        pathlib.Path(wrong_authorization["evidence_root"]).mkdir(mode=0o700)
        wrong_authorization_path = fixture.external / "wrong-action-authorization-v2.json"
        write(wrong_authorization_path, wrong_authorization)
        wrong_authorization_signature = fixture._sign(wrong_authorization_path)
        expect_failure("authorization_request_action_drift", lambda: controller.execute_once(
            repository_root=fixture.root,
            journal=fixture.builder.latest_path.relative_to(fixture.root),
            journal_directory=fixture.root / "config/stage17/journal",
            authorization_path=wrong_authorization_path,
            signature_path=wrong_authorization_signature,
            test_linked_worker=True,
            pilot_archive=fixture.builder.pilot_archive,
            pilot_sidecar=fixture.builder.pilot_sidecar))
        negative += 1

        # An arbitrary executable is rejected from admitted runtime context,
        # independently of a valid signature.
        shell = fixture.external / "arbitrary-shell-worker"; shell.write_text("#!/bin/sh\nexit 0\n"); shell.chmod(0o700)
        ext2_manifest = fixture.external / "ext002/s17-ext-002-manifest-v2.json"
        original = ext2_manifest.read_bytes()
        document = json.loads(original)
        worker_ref = next(item for item in document["artifacts"] if item["role"] == "RUNTIME_WORKER_BINARY")
        worker_ref["size_bytes"], worker_ref["sha256"] = shell.stat().st_size, digest(shell)
        write(ext2_manifest, document)
        expect_failure("signed_arbitrary_shell_worker", lambda: journal.validate_operational_journal(repository_root=fixture.root, latest_journal=fixture.builder.latest_path.relative_to(fixture.root), journal_directory=fixture.root / "config/stage17/journal", pilot_archive=fixture.builder.pilot_archive, pilot_sidecar=fixture.builder.pilot_sidecar, allow_synthetic_test_evidence=True))
        ext2_manifest.write_bytes(original); negative += 1

        # Boolean-only typed impostor and unknown schema identity are closed.
        plan_path = fixture.root / "evidence/ext008-v2/ext008-plan.json"
        original_plan = plan_path.read_bytes(); plan_doc = json.loads(original_plan)
        plan_doc["measurements"] = {"eligible": True}
        write(plan_path, plan_doc)
        expect_failure("boolean_only_typed_impostor", lambda: journal.validate_operational_journal(repository_root=fixture.root, latest_journal=fixture.builder.latest_path.relative_to(fixture.root), journal_directory=fixture.root / "config/stage17/journal", pilot_archive=fixture.builder.pilot_archive, pilot_sidecar=fixture.builder.pilot_sidecar, allow_synthetic_test_evidence=True))
        plan_path.write_bytes(original_plan); negative += 1
        manifest_path = fixture.root / "evidence/ext008-v2/s17-ext-008-manifest-v2.json"
        original_manifest = manifest_path.read_bytes(); manifest_doc = json.loads(original_manifest)
        manifest_doc["artifacts"][0]["schema_identity"] = "unknown/schema/999"
        write(manifest_path, manifest_doc)
        expect_failure("unknown_schema_identity", lambda: semantics.verify_manifest_v2(repository_root=fixture.root, manifest_path=manifest_path, admitted_resolutions=validation.resolutions, expected_input_id="S17-EXT-008", allow_synthetic=True))
        manifest_path.write_bytes(original_manifest); negative += 1

        # EXT006 must prove the observed Q15 runtime is exactly the archive
        # member; a contract-selected different worker is not a release.
        contract_path = fixture.root / "config/stage17/synthetic-pilot-candidate-contract-v2.json"
        original_contract = contract_path.read_bytes()
        contract_document = json.loads(original_contract)
        contract_document["worker"]["sha256"] = "f" * 64
        write(contract_path, contract_document)
        expect_failure("wrong_ext006_release_worker", lambda: journal.validate_operational_journal(
            repository_root=fixture.root,
            latest_journal=fixture.builder.latest_path.relative_to(fixture.root),
            journal_directory=fixture.root / "config/stage17/journal",
            pilot_archive=fixture.builder.pilot_archive,
            pilot_sidecar=fixture.builder.pilot_sidecar,
            allow_synthetic_test_evidence=True))
        contract_path.write_bytes(original_contract); negative += 1

        # EXT002 trust is not a free-standing claim: the observed stand anchor,
        # target, and action attempt must remain bound to the admitted EXT001
        # target and authorization bytes even if every outer hash is updated.
        ext2_manifest = fixture.external / "ext002/s17-ext-002-manifest-v2.json"
        ext2_trust = fixture.external / "ext002/ext002-trust.json"
        saved_ext2_manifest, saved_ext2_trust = (
            ext2_manifest.read_bytes(), ext2_trust.read_bytes()
        )
        trust_document = json.loads(saved_ext2_trust)
        trust_document["measurements"]["stand_anchor_sha256"] = "f" * 64
        write(ext2_trust, trust_document)
        ext2_manifest_document = json.loads(saved_ext2_manifest)
        trust_reference = next(
            item for item in ext2_manifest_document["artifacts"]
            if item["artifact_id"] == "EXT002-TRUST"
        )
        trust_reference.update({
            "size_bytes": ext2_trust.stat().st_size,
            "sha256": digest(ext2_trust),
        })
        write(ext2_manifest, ext2_manifest_document)
        expect_failure(
            "preflight_trust_anchor_not_bound_to_ext001",
            lambda: semantics.verify_manifest_v2(
                repository_root=fixture.root,
                manifest_path=ext2_manifest,
                admitted_resolutions={
                    "S17-EXT-001": validation.resolutions["S17-EXT-001"]
                },
                expected_input_id="S17-EXT-002",
                allow_synthetic=True,
            ),
        )
        ext2_manifest.write_bytes(saved_ext2_manifest)
        ext2_trust.write_bytes(saved_ext2_trust)
        negative += 1

        # EXT004 cannot replace a raw qualification source while preserving a
        # stale derived measurement digest, even when every outer manifest and
        # source-binding hash is made internally consistent.
        ext4_manifest = fixture.external / "ext004/s17-ext-004-manifest-v2.json"
        ext4_saved = ext4_manifest.read_bytes()
        ext4_document = json.loads(ext4_saved)
        source_reference = next(item for item in ext4_document["artifacts"]
                                if item["role"] == "QUALIFICATION_SOURCE")
        source_path = ext4_manifest.parent / source_reference["locator"]
        source_saved = source_path.read_bytes()
        source_path.write_bytes(source_saved + b"drift")
        source_reference.update({"size_bytes": source_path.stat().st_size,
                                 "sha256": digest(source_path)})
        record_reference = next(
            item for item in ext4_document["artifacts"]
            if item["role"] != "QUALIFICATION_SOURCE"
            and any(binding["id"] == source_reference["artifact_id"]
                    for binding in json.loads(
                        (ext4_manifest.parent / item["locator"]).read_text()
                    )["source_bindings"])
        )
        record_path = ext4_manifest.parent / record_reference["locator"]
        record_saved = record_path.read_bytes()
        record_document = json.loads(record_saved)
        next(binding for binding in record_document["source_bindings"]
             if binding["id"] == source_reference["artifact_id"])["sha256"] = digest(source_path)
        write(record_path, record_document)
        record_reference.update({"size_bytes": record_path.stat().st_size,
                                 "sha256": digest(record_path)})
        write(ext4_manifest, ext4_document)
        expect_failure("qualification_source_claim_drift", lambda: semantics.verify_manifest_v2(
            repository_root=fixture.root, manifest_path=ext4_manifest,
            admitted_resolutions={key: value for key, value in validation.resolutions.items()
                                  if key < "S17-EXT-004"},
            expected_input_id="S17-EXT-004", allow_synthetic=True))
        ext4_manifest.write_bytes(ext4_saved); source_path.write_bytes(source_saved)
        record_path.write_bytes(record_saved); negative += 1

        ext9_manifest = fixture.external / "ext009/s17-ext-009-manifest-v2.json"
        secondary_copy = fixture.external / "ext009/custody-b/pilot-copy.bin"
        secondary_saved = secondary_copy.read_bytes()
        secondary_copy.write_bytes(b"custody-drift")
        expect_failure("custody_copy_byte_drift", lambda: semantics.verify_manifest_v2(
            repository_root=fixture.root, manifest_path=ext9_manifest,
            admitted_resolutions={key: value for key, value in validation.resolutions.items()
                                  if key < "S17-EXT-009"},
            expected_input_id="S17-EXT-009", allow_synthetic=True))
        secondary_copy.write_bytes(secondary_saved); negative += 1

        # A schema-valid Q15-W result that no longer proves restoration remains
        # inadmissible even when its outer manifest hashes are recomputed.
        ext5_manifest = fixture.external / "action-q15_w/s17-ext-005-manifest-v2.json"
        ext5_result = fixture.external / "action-q15_w/stage17-action-result-v2.json"
        ext5_completion = fixture.external / "action-q15_w/stage17-q15_w-completion-v2.json"
        saved_ext5 = (ext5_manifest.read_bytes(), ext5_result.read_bytes(),
                      ext5_completion.read_bytes())
        result_document = json.loads(saved_ext5[1]); result_document["restoration_verified"] = False
        write(ext5_result, result_document)
        completion_document = json.loads(saved_ext5[2])
        completion_document["restoration_verified"] = False
        completion_document["result"] = {
            "file_name": ext5_result.name,
            "size_bytes": ext5_result.stat().st_size,
            "sha256": digest(ext5_result),
        }
        write(ext5_completion, completion_document)
        manifest_document = json.loads(saved_ext5[0])
        for reference in manifest_document["artifacts"]:
            if reference["locator"] == ext5_result.name:
                reference.update({"size_bytes": ext5_result.stat().st_size,
                                  "sha256": digest(ext5_result)})
            if reference["locator"] == ext5_completion.name:
                reference.update({"size_bytes": ext5_completion.stat().st_size,
                                  "sha256": digest(ext5_completion)})
        write(ext5_manifest, manifest_document)
        expect_failure("q15w_restoration_not_proven", lambda: semantics.verify_manifest_v2(
            repository_root=fixture.root, manifest_path=ext5_manifest,
            admitted_resolutions={key: value for key, value in validation.resolutions.items()
                                  if key < "S17-EXT-005"},
            expected_input_id="S17-EXT-005", allow_synthetic=True))
        ext5_manifest.write_bytes(saved_ext5[0]); ext5_result.write_bytes(saved_ext5[1])
        ext5_completion.write_bytes(saved_ext5[2]); negative += 1

        # The current policy is part of authority, so an entrypoint drift is a
        # pre-marker failure rather than a caller-selectable worker surface.
        plan_file = fixture.root / controller.ACTION_PLAN
        original_action_plan = plan_file.read_bytes()
        drifted_plan = json.loads(original_action_plan)
        drifted_plan["execution_policy"]["entrypoint"] = "--arbitrary-entrypoint"
        write(plan_file, drifted_plan)
        expect_failure("fixed_action_plan_entrypoint_drift", lambda: journal.validate_operational_journal(
            repository_root=fixture.root,
            latest_journal=fixture.builder.latest_path.relative_to(fixture.root),
            journal_directory=fixture.root / "config/stage17/journal",
            pilot_archive=fixture.builder.pilot_archive,
            pilot_sidecar=fixture.builder.pilot_sidecar,
            allow_synthetic_test_evidence=True))
        plan_file.write_bytes(original_action_plan); negative += 1

        policy_document = json.loads(
            (fixture.root / semantic_registry.POLICY_PATH).read_text()
        )
        policy_document["runtime_closure_keys"].remove("state_journal_base")
        policy_document["runtime_closure"].pop("state_journal_base")
        expect_failure(
            "runtime_closure_key_omission",
            lambda: semantic_registry.verify_policy_v10(
                root=fixture.root,
                policy=policy_document,
                graph_sha256=policy_document["graph_sha256"],
                catalog_sha256=policy_document["catalog_sha256"],
                genesis_record_sha256=policy_document["genesis_record_sha256"],
                resolution_schema_sha256=policy_document[
                    "resolution_schema_sha256"
                ],
            ),
        )
        negative += 1

    for mode in ("atomic_replacement", "in_place_mutation"):
        with tempfile.TemporaryDirectory(prefix=f"stage17-fixed-{mode}-") as temporary:
            exact = Fixture(pathlib.Path(temporary), worker)
            exact.ext001(); exact.ext002(); exact.ext003(); exact.ext004()
            original_run = controller.executor._run_worker
            request_path = exact.external / "action-q15_r/request-v2.json"
            worker_path = exact.external / "ext002/cpu_prefetch_stage17_test_worker"
            schema_path = exact.root / "config/schemas/stage17-action-output-v2.schema.json"
            calls = 0

            def mutate_then_run(*args: Any, **kwargs: Any) -> Any:
                nonlocal calls
                calls += 1
                if mode == "atomic_replacement":
                    replacement = worker_path.with_name("replacement-worker")
                    replacement.write_bytes(b"#!/bin/sh\nexit 97\n")
                    replacement.chmod(0o700)
                    os.replace(replacement, worker_path)
                    replacement_request = request_path.with_name("replacement-request")
                    replacement_request.write_bytes(b"{}\n")
                    os.replace(replacement_request, request_path)
                    replacement_schema = schema_path.with_name("replacement-output-schema")
                    replacement_schema.write_bytes(b"{}\n")
                    os.replace(replacement_schema, schema_path)
                else:
                    worker_path.write_bytes(b"X" * worker_path.stat().st_size)
                    request_path.write_bytes(b"Y" * request_path.stat().st_size)
                    schema_path.write_bytes(b"Z" * schema_path.stat().st_size)
                return original_run(*args, **kwargs)

            with mock.patch.object(controller.executor, "_run_worker",
                                   side_effect=mutate_then_run):
                exact_result = exact.action("Q15-R", 3)
            if calls != 1 or exact_result["result_document"]["action_id"] != "Q15-R":
                raise CheckError(f"exact-byte {mode} did not use sealed snapshots")
            positive += 1

    with tempfile.TemporaryDirectory(prefix="stage17-fixed-no-result-") as temporary:
        broken = Fixture(pathlib.Path(temporary), no_result_worker)
        broken.ext001(); broken.ext002(); broken.ext003(); broken.ext004()
        expect_failure("exit_zero_without_typed_result",
                       lambda: broken.action("Q15-R", 3))
        failure = broken.external / "action-q15_r/stage17-q15_r-failure-v2.json"
        if not failure.is_file() or json.loads(failure.read_text())["failure_category"] != "RESULT_MISSING":
            raise CheckError("rc=0 missing-result failure was not retained")
        negative += 1
    with tempfile.TemporaryDirectory(prefix="stage17-fixed-cross-version-") as temporary:
        replay = Fixture(pathlib.Path(temporary), worker)
        replay.ext001(); replay.ext002(); replay.ext003(); replay.ext004()
        output = replay.external / "action-q15_r"; output.mkdir(mode=0o700)
        (output / "stage17-q15_r-attempt-v1.json").write_text("{}\n", encoding="utf-8")
        expect_failure("cross_version_attempt_marker_replay",
                       lambda: replay.action("Q15-R", 3, directory=output))
        negative += 1
    with tempfile.TemporaryDirectory(prefix="stage17-fixed-malformed-result-") as temporary:
        malformed = Fixture(pathlib.Path(temporary), worker)
        malformed.ext001(); malformed.ext002(); malformed.ext003(); malformed.ext004()
        original_transport = controller.executor._run_worker

        def corrupt_result(*args: Any, **kwargs: Any) -> Any:
            outcome = original_transport(*args, **kwargs)
            output_fd = args[0][-2]
            descriptor = os.open("stage17-action-result-v2.json", os.O_WRONLY | os.O_TRUNC,
                                 dir_fd=int(output_fd))
            try:
                os.write(descriptor, b"{malformed-result\n")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            return outcome

        with mock.patch.object(controller.executor, "_run_worker",
                               side_effect=corrupt_result):
            expect_failure("malformed_typed_result",
                           lambda: malformed.action("Q15-R", 3))
        negative += 1
    return positive, negative


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.add_argument("--worker", type=pathlib.Path, required=True)
    parser.add_argument("--no-result-worker", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        positive, negative = self_test(args.worker.resolve(),
                                       args.no_result_worker.resolve())
    except BaseException as exception:
        print(f"stage17-fixed-production: FAIL: {exception}", file=sys.stderr)
        return 1
    print(f"stage17-fixed-production: PASS positive={positive} negative={negative} compiled_dispatch=true state_gate_mock=false stand=NOT_ACCESSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
