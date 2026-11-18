#!/usr/bin/env python3
"""D281 policy62/preflight35 qualification CLI, preserving all signed gates."""
from stage17_operational_cli_daycap_v2 import (Any, OperationalCliError,
    _no_predecessor_attestation_binding, _openssh_ed25519_public_key, _repository_binding,
    base64, canonical, digest, load_json, os, parse_utc, pathlib, stat, streaming_binding,
    validate_schema, write_external_exclusive)
import stage17_operational_cli_daycap_v2 as previous
import stage17_phase_controller_daycap_v4 as controller
import stage17_read_only_preflight_executor_v36 as preflight
import stage17_state_journal_v59 as journal
import stage17_phase_controller_daycap_v1 as cloning

_base = cloning._clone_module(previous.base, {})
_VIEW = cloning._clone_module(previous,
    {'controller': controller, 'preflight_executor': preflight, 'journal': journal, 'base': _base})

def __getattr__(name): return getattr(_VIEW, name)
def activate(): return _VIEW.activate()
def main(): return _VIEW.main()


def author_ext001_daycap_v4(
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
        "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v36.json"
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

# Only the nested policy binding changes in this static EXT001 authoring body.
author_ext001_daycap_v1 = author_ext001_daycap_v4
_VIEW.author_ext001_daycap_v1 = author_ext001_daycap_v4
_VIEW.main.__globals__['author_ext001_daycap_v1'] = author_ext001_daycap_v4
activate()
# A namespace copy owns a distinct attribute dictionary. Bind the six ordinary
# CLI globals in the copied function scope as well; changing namespace attributes
# alone would leave main()/authoring routed to the historical policy.
_base.main.__globals__.update({name: getattr(_base, name) for name in (
    'journal_runtime', 'controller', 'semantics_v6', 'pilot_artifact', 'author_ext001')})
if __name__ == '__main__': raise SystemExit(main())
