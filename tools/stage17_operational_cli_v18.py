"""Current operational CLI and explicit signed v6 formal-family operations.

Authoring never signs. Custody admission never grants scientific validity,
execution authority or Stage 18 authority. Historical files remain unchanged.
"""
from __future__ import annotations
import argparse
import base64
import datetime as dt
import json
import os
import pathlib
import stat
import sys
import types
from typing import Any
import stage17_operational_cli_v15 as discovery_cli
import stage17_operational_cli_v11 as base
from stage17_operational_cli_v13 import (
    OperationalCliError, parse_utc, streaming_binding, write_external_exclusive,
    canonical, _repository_binding, digest, validate_schema,
    _openssh_ed25519_public_key, _no_predecessor_attestation_binding, load_json)
import stage17_phase_controller_v26 as controller
import stage17_phase_controller_v24 as discovery_controller
import stage17_read_only_preflight_executor_v32 as preflight_executor
import stage17_pilot_candidate_artifact_v12 as release
import stage17_operational_semantics_v16 as operational
import stage17_state_journal_v52 as journal
import stage17_output_registry_v12 as registry
import stage17_output_registry_v10 as discovery_registry
import stage17_fixed_action_executor_v10 as executor


def activate():
    preflight_executor.activate()
    controller.activate()
    base.journal_runtime = journal
    base.controller = controller
    base.semantics_v6 = types.SimpleNamespace(ROLE_SCHEMA_v6=operational.ROLE_SCHEMA_v16)
    base.pilot_artifact = types.SimpleNamespace(VERIFIER_ID=release.VERIFIER_ID,
        VERIFIER_VERSION=release.VERIFIER_VERSION, build_contract_v4=release.build_contract_v12)
    base.author_ext001 = author_ext001_v18


def author_ext001_v18(
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
        "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v32.json"
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
        "cpu-prefetch-stage17-read-only-preflight-supporting-contract/14"
        if using_attestation else
        "cpu-prefetch-stage17-read-only-preflight-supporting-contract/12"
    )
    contract_filename = (
        "supporting-contract-v14.json" if using_attestation
        else "supporting-contract-v12.json"
    )
    contract_schema_relative = (
        "config/schemas/stage17-read-only-preflight-supporting-contract-v14.schema.json"
        if using_attestation else
        "config/schemas/stage17-read-only-preflight-supporting-contract-v12.schema.json"
    )
    captured_pilot_identity: dict[str, Any] | None = None
    if using_attestation:
        archive_binding = streaming_binding(pilot_archive)
        sidecar_binding = streaming_binding(pilot_sidecar)
        manifest_path = bundle_root_locator / "BUNDLE_MANIFEST.json"
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise OperationalCliError("EXT001 bundle manifest is unavailable")
        manifest_sha256 = digest(manifest_path.read_bytes())
        inventory_path = bundle_root_locator / "SHA256SUMS"
        if not inventory_path.is_file() or inventory_path.is_symlink():
            raise OperationalCliError("EXT001 bundle checksum inventory is unavailable")
        internal_file_count = len(
            inventory_path.read_text(encoding="utf-8").splitlines()
        )
        captured_pilot_identity = {
            "archive_size_bytes": archive_binding["size_bytes"],
            "archive_sha256": archive_binding["sha256"],
            "sidecar_size_bytes": sidecar_binding["size_bytes"],
            "sidecar_sha256": sidecar_binding["sha256"],
            "manifest_sha256": manifest_sha256,
            "internal_file_count": internal_file_count,
        }
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
            **(captured_pilot_identity if captured_pilot_identity is not None else {}),
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


def _validation(repository_root, evidence_root, pilot_archive=None, pilot_sidecar=None, synthetic=False):
    activate()
    return journal.validate_operational_journal(repository_root=repository_root, evidence_root=evidence_root,
        latest_journal=base.latest_journal(evidence_root), journal_directory=evidence_root / "journal",
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        as_of_utc=controller.support._now(), allow_synthetic_test_evidence=synthetic)


def author_formal_request(*, action_id, repository_root, evidence_root, action_inputs_path, request_id,
                          authorization_id, attempt_id, session_id, output_root, destination,
                          pilot_archive=None, pilot_sidecar=None, synthetic=False):
    if action_id not in registry.FORMAL_ACTIONS:
        raise OperationalCliError("formal authoring accepts only Q16a/Q16b/Q16c")
    validation = _validation(repository_root, evidence_root, pilot_archive, pilot_sidecar, synthetic)
    pinned = registry.pin_registry(repository_root)
    definition = pinned.action(action_id)
    if validation.current_state != definition["required_state"]:
        raise OperationalCliError("formal state gate is not satisfied")
    runtime, release_binding, _ = controller.runtime_from_context(validation)
    inputs, _ = base.load_json(action_inputs_path)
    document = dict(schema_version="cpu-prefetch-stage17-fixed-action-request/6",
        request_id=request_id, session_id=session_id, action_id=action_id,
        stand_id=validation.resolutions["S17-EXT-002"].semantic_context["stand_id"],
        authorization_id=authorization_id, attempt_id=attempt_id, runtime_binding=runtime, release_binding=release_binding,
        evidence_root_binding=base._root_binding(output_root),
        predecessor_resolutions=[base._resolution_binding(validation.resolutions[key])
                                for key in definition["required_resolution_ids"]],
        action_inputs=inputs, synthetic_test_only=synthetic, phase18_authority=False)
    registry.validate_document(pinned, document, registry.schema_path("fixed-action-request"), "formal request")
    controller.validate_action_inputs(document, validation)
    write_external_exclusive(destination, registry.canonical(document))
    return destination


def author_formal_authorization(*, repository_root, evidence_root, request_path, actor, reviewer,
                               issued_at_utc, expires_at_utc, destination, pilot_archive=None,
                               pilot_sidecar=None, synthetic=False):
    validation = _validation(repository_root, evidence_root, pilot_archive, pilot_sidecar, synthetic)
    request, payload = load_json(request_path)
    pinned = registry.pin_registry(repository_root)
    registry.validate_document(pinned, request, registry.schema_path("fixed-action-request"), "formal request")
    if payload != registry.canonical(request):
        raise OperationalCliError("formal request bytes are not canonical")
    extent = controller.validate_action_inputs(request, validation)
    definition = pinned.action(request["action_id"])
    expected = [base._resolution_binding(validation.resolutions[key]) for key in definition["required_resolution_ids"]]
    runtime, release_binding, _ = controller.runtime_from_context(validation)
    trust = validation.resolutions["S17-EXT-003"].semantic_context["trust"]
    if (validation.current_state != definition["required_state"] or request["predecessor_resolutions"] != expected
            or request["runtime_binding"] != runtime or request["release_binding"] != release_binding
            or request["synthetic_test_only"] is not synthetic or request["stand_id"] != trust["subject_id"]
            or actor != trust["measurements"]["principal"] or reviewer != trust["measurements"]["reviewer_role"]):
        raise OperationalCliError("formal request state, lineage or admitted trust differs")
    if base._root_binding(pathlib.Path(request["evidence_root_binding"]["absolute_path"])) != request["evidence_root_binding"]:
        raise OperationalCliError("formal output root drifted before authoring")
    policy = controller.deadline_policy(extent)
    issued, expires = parse_utc(issued_at_utc), parse_utc(expires_at_utc)
    if not issued < expires or expires - issued > dt.timedelta(seconds=policy["session_max_wall_seconds"]):
        raise OperationalCliError("formal authority window exceeds finite session")
    document = dict(schema_version="cpu-prefetch-stage17-phase-action-authorization/6",
        authorization_id=request["authorization_id"], session_id=request["session_id"], action_id=request["action_id"],
        actor=actor, reviewer=reviewer, target=dict(stand_id=request["stand_id"]),
        issued_at_utc=issued_at_utc, expires_at_utc=expires_at_utc,
        trust_context=dict(ext002_resolution=expected[1], ext003_resolution=expected[2]),
        predecessor_resolutions=expected, fixed_action_definition_sha256=pinned.plan_sha256,
        request_binding=dict(path=str(request_path.resolve()), size_bytes=len(payload), sha256=registry.sha256(payload)),
        evidence_root_binding=request["evidence_root_binding"], permission_matrix=definition["permission_matrix"],
        deadline_policy=policy, one_attempt=True, retry_allowed=False, stop_first=True, retain_partial=True, stage18_authority=False)
    registry.validate_document(pinned, document, registry.schema_path("phase-action-authorization"), "formal authorization")
    write_external_exclusive(destination, registry.canonical(document))
    return destination


def _formal_authority(arguments):
    document, _ = load_json(arguments["authorization_path"])
    if document.get("schema_version") != "cpu-prefetch-stage17-phase-action-authorization/6":
        raise OperationalCliError("explicit formal operations require v6 authority")


def verify_formal_signature(**arguments):
    activate()
    _formal_authority(arguments)
    return controller.prepare_action(**arguments)


def execute_formal(**arguments):
    activate()
    _formal_authority(arguments)
    return controller.execute_once(**arguments)


def prepare_formal_retention(**arguments):
    activate()
    _formal_authority(arguments)
    return controller.prepare_retention(**arguments)


def _unbound_control(directory_fd, name):
    """Snapshot an executor receipt; lineage is checked against signed inputs."""
    fd, before = registry.base._open_output(directory_fd, name)
    try:
        if before.st_size > 64 * 1024**2:
            raise OperationalCliError("formal receipt exceeds bounded metadata size")
        payload = os.pread(fd, before.st_size + 1, 0)
        def identity(info):
            return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
        if (len(payload) != before.st_size or identity(before) != identity(os.fstat(fd))
                or identity(before) != identity(os.stat(name, dir_fd=directory_fd, follow_symlinks=False))):
            raise OperationalCliError("formal receipt changed while reading")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result: raise OperationalCliError("duplicate formal receipt key")
                result[key] = value
            return result
        return json.loads(payload, object_pairs_hook=unique,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    finally:
        os.close(fd)


def admit_formal_retention(prepared, output_root: pathlib.Path):
    """Readonly completed custody, including after expiry; never collection permission."""
    activate()
    if (prepared.request.get("schema_version") != "cpu-prefetch-stage17-fixed-action-request/6"
            or prepared.authorization.get("schema_version") != "cpu-prefetch-stage17-phase-action-authorization/6"):
        raise OperationalCliError("formal retention requires original v6 documents")
    extent = controller.contract.validate_plan(prepared.request["action_id"], prepared.request["action_inputs"]["plan"])
    directory_fd, identity = executor._componentwise_output_root(
        output_root, prepared.root, prepared.request["evidence_root_binding"])
    try:
        action = prepared.request["action_id"]
        token = action.lower()
        if executor._quarantine_present(directory_fd) or executor.predecessor._exists_at(
                directory_fd, f"stage17-{token}-failure-v6.json"):
            raise OperationalCliError("failed/quarantined action cannot admit completed retention")
        attempt = _unbound_control(directory_fd, f"stage17-{token}-attempt-v6.json")
        completion = _unbound_control(directory_fd, f"stage17-{token}-completion-v6.json")
        for family, document in (("phase-action-attempt", attempt), ("phase-action-completion", completion)):
            registry.validate_document(prepared.registry, document, registry.schema_path(family), family)
            if (document["action_id"] != action or document["attempt_id"] != prepared.request["attempt_id"]
                    or document["authorization_sha256"] != registry.sha256(prepared.authorization_bytes)
                    or document["request_sha256"] != registry.sha256(prepared.request_bytes)
                    or document["runtime_sha256"] != prepared.runtime["sha256"]):
                raise OperationalCliError("formal retention controller lineage differs")
        if (attempt["authorization_id"] != prepared.authorization["authorization_id"]
                or attempt["release_resolution_id"] != prepared.release["source_resolution_id"]
                or attempt["release_resolution_sha256"] != prepared.release["source_resolution_sha256"]
                or attempt["evidence_root_binding"] != prepared.request["evidence_root_binding"]):
            raise OperationalCliError("formal attempt authority/release/root differs")
        if completion["result"]["file_name"] != registry.RESULT_NAME:
            raise OperationalCliError("formal completion names a different result")
        result = registry.predecessor._bound_report(directory_fd, completion["result"],
            min(extent.declared.max_output_bytes, 64 * 1024**2))
        expected_readback = [dict(cpu=cpu, expected_hex=f"{value:016x}", observed_hex=f"{value:016x}", matches=True)
                             for cpu, value in executor.formal_prestate(prepared.request)]
        if (completion["live_restoration_readback"] != expected_readback
                or completion["restoration_verified"] is not True or completion["quarantined"] is not False
                or completion["leader_reaped"] is not True or completion["process_group_gone"] is not True):
            raise OperationalCliError("formal completion quiescence/restoration differs")
        observation = completion["resource_admission"]
        required_disk = extent.declared.required_free_disk_bytes
        if controller.is_archived(prepared.request):
            from stage17_formal_storage_budget_v1 import QUOTA, WORKSPACE, SCRATCH, RESERVE
            storage = prepared.request["action_inputs"]["plan"]["storage"]
            retained = observation.get("retained_program_bytes")
            if (type(retained) is not int or not 0 <= retained <= QUOTA
                    or observation.get("remaining_program_quota_bytes") != QUOTA - retained
                    or observation.get("program_scope_sha256") != storage["program_scope_sha256"]
                    or type(observation.get("capture_ordinal")) is not int
                    or observation["capture_ordinal"] != 0):
                raise OperationalCliError("formal shared-quota observation differs")
            required_disk = QUOTA - retained + WORKSPACE + SCRATCH + RESERVE
        if (observation["required_memory_bytes"] != extent.declared.memory_bytes
                or observation["required_free_disk_bytes"] != required_disk
                or observation["memory_available_bytes"] < extent.declared.memory_bytes
                or observation["filesystem_available_bytes"] < required_disk
                or observation["filesystem_device"] != os.fstat(directory_fd).st_dev
                or not parse_utc(attempt["started_at_utc"]) <= parse_utc(observation["observed_at_utc"]) <= parse_utc(completion["completed_at_utc"])):
            raise OperationalCliError("formal recorded resource admission differs from prospective budget")
        expected = [{key: item[key] for key in ("file_name", "size_bytes", "sha256")} for item in result["artifacts"]]
        if completion["artifact_bindings"] != expected:
            raise OperationalCliError("formal completion artifact bindings differ")
        checks = dict(registry=prepared.registry, directory_fd=directory_fd,
            result=result, request=prepared.request, authorization_sha256=registry.sha256(prepared.authorization_bytes),
            synthetic_test_only=prepared.request["synthetic_test_only"])
        if controller.is_archived(prepared.request):
            import time
            report = registry.verify_archived_formal_metadata(repository_root=prepared.root,
                archive_runtime_profile=prepared.archive_runtime_profile,
                deadline_ns=time.monotonic_ns() + extent.declared.watchdog_ns, **checks)
        else:
            report = registry.validate_worker_result(**checks)
        executor._verify_root_identity(directory_fd, identity)
        return report
    finally:
        os.close(directory_fd)


def _discovery_functions():
    """Private diagnostic globals; no edits to historical CLI dispatch objects."""
    def runtime(validation):
        profile = validation.resolutions["S17-EXT-006"].semantic_context.get("bundle_profile")
        if profile in {"STAGE17-PILOT-CANDIDATE-BUNDLE-v26", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"}:
            return controller.runtime_from_context(validation)
        return discovery_controller.runtime_from_context(validation)
    scope = dict(discovery_controller.validate_action_inputs.__globals__)
    scope["runtime_from_context"] = runtime
    validate = types.FunctionType(discovery_controller.validate_action_inputs.__code__, scope)
    facade = types.SimpleNamespace(journal_runtime=journal, support=controller.support,
        ControllerError=controller.ControllerError, runtime_from_context=runtime,
        validate_action_inputs=validate, deadline_policy=discovery_controller.deadline_policy,
        prepare_action=controller.prepare_action, execute_once=controller.execute_once)
    scope = dict(discovery_cli.__dict__)
    scope.update(controller=facade, registry=discovery_registry,
                 predecessor=types.SimpleNamespace(main=base.main))
    for name in ("_validation", "author_request", "author_authorization", "admit_retention", "main"):
        function = getattr(discovery_cli, name)
        scope[name] = types.FunctionType(function.__code__, scope, name, function.__defaults__, function.__closure__)
        scope[name].__kwdefaults__ = function.__kwdefaults__
    return scope


def author_request(**arguments):
    activate()
    return _discovery_functions()["author_request"](**arguments)


def author_authorization(**arguments):
    activate()
    return _discovery_functions()["author_authorization"](**arguments)


def admit_retention(prepared, output_root):
    activate()
    return _discovery_functions()["admit_retention"](prepared, output_root)


def main():
    activate()
    commands = {"author-formal-request", "author-formal-authorization", "verify-formal-signature",
                "execute-formal", "admit-formal-retention"}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        return _discovery_functions()["main"]()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(commands))
    for name in ("repository-root", "evidence-root"):
        parser.add_argument("--" + name, type=pathlib.Path, required=True)
    for name in ("pilot-archive", "pilot-sidecar", "action-inputs", "output-root", "output", "request", "authorization", "signature"):
        parser.add_argument("--" + name, type=pathlib.Path)
    parser.add_argument("--action", choices=sorted(registry.FORMAL_ACTIONS))
    for name in ("request-id", "authorization-id", "attempt-id", "session-id", "actor", "reviewer", "issued-at-utc", "expires-at-utc"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    def need(*names):
        for name in names:
            if getattr(args, name) is None: parser.error("required: --" + name.replace("_", "-"))
    common = dict(repository_root=args.repository_root.resolve(), evidence_root=args.evidence_root.resolve(),
                  pilot_archive=args.pilot_archive, pilot_sidecar=args.pilot_sidecar)
    if args.command == "author-formal-request":
        need("action", "action_inputs", "request_id", "authorization_id", "attempt_id", "session_id", "output_root", "output")
        author_formal_request(**common, action_id=args.action, action_inputs_path=args.action_inputs,
            request_id=args.request_id, authorization_id=args.authorization_id, attempt_id=args.attempt_id,
            session_id=args.session_id, output_root=args.output_root, destination=args.output)
    elif args.command == "author-formal-authorization":
        need("request", "actor", "reviewer", "issued_at_utc", "expires_at_utc", "output")
        author_formal_authorization(**common, request_path=args.request, actor=args.actor, reviewer=args.reviewer,
            issued_at_utc=args.issued_at_utc, expires_at_utc=args.expires_at_utc, destination=args.output)
    else:
        need("authorization", "signature")
        common.pop("evidence_root")
        common.update(journal=base.latest_journal(args.evidence_root), journal_directory=args.evidence_root / "journal",
            operational_evidence_root=args.evidence_root, authorization_path=args.authorization, signature_path=args.signature)
        if args.command == "execute-formal": execute_formal(**common)
        elif args.command == "verify-formal-signature": verify_formal_signature(**common)
        else:
            need("output_root")
            admit_formal_retention(prepare_formal_retention(**common), args.output_root)
    print("stage17-formal: PASS; no scientific validity or new authority")
    return 0


activate()

if __name__ == "__main__":
    raise SystemExit(main())
