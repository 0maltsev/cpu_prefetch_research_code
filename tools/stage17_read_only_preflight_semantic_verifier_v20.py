#!/usr/bin/env python3
"""Stage 17 S17-EXT-001 semantic-verifier successor binding the fixed
archive-and-sidecar observation's expected identity to the actually
captured pilot-candidate bundle instead of the frozen `S17-EXT-006`
reproducible-build baseline (ADR-0134, `PROPOSED`).

Unlike `v16`/`v17`/`v18`/`v19` (each a pure `IMPLEMENTATION_PATHS` rebind
that reused `evaluate_s17_ext_001_action_readiness_v15` and
`verify_s17_ext_001_semantics_v15`/`v18` unchanged), this module changes
real logic: `_reverify_current_action_inputs` builds the fixed
observation's `collector_context["archive_size_bytes"]` (and the other
five archive/sidecar/manifest identity fields) from
`semantic_context["pilot_contract"]` -- the static, catalog-pinned
`config/stage17/stage17-pilot-candidate-external-contract-v1.json`,
describing the very first pilot-candidate bundle this repository ever
sealed (5,582,257 bytes, 171 files) -- regardless of which bundle
generation was actually passed to `author-ext001`. Real evidence from
this session's sixth and seventh admissions (both against the real,
independently byte-verified `STAGE17-PILOT-CANDIDATE-BUNDLE-v11` archive,
9,850,147 bytes, matching on both the local machine and the real stand
before and after each failure) shows both real `--execute` attempts fail
identically and deterministically at
`S17-RO-PREFLIGHT-002-ARCHIVE-AND-SIDECAR-BYTE-VERIFICATION` with
`REMOTE_NONZERO_EXIT`/`archive size`, because the remote check always
expects the frozen v1 baseline's size, never the real staged archive's.

Because a function alias resolves free variables against the module it
was *defined* in, not the module it is *accessed* through, fixing this
requires fresh copies -- not aliases -- of `_reverify_current_action_
inputs` and `evaluate_s17_ext_001_action_readiness_v15` (renamed `_v20`
here), and of `verify_s17_ext_001_semantics_v15` (renamed `_v20`), since
all three read the archive-identity source directly. Every other
predecessor-evidence check (attestation/blocker classification, known-
hosts, transport identity, action-plan, runtime-closure, evidence-root
safety) is unchanged and reused via `immediate_predecessor` attribute
access, exactly as `v19` already established.

`config/schemas/stage17-read-only-preflight-supporting-contract-
v14.schema.json` is an additive successor to `v13`, adding required
`pilot_candidate.archive_size_bytes`/`archive_sha256`/`sidecar_size_
bytes`/`sidecar_sha256`/`manifest_sha256`/`internal_file_count` fields.
`tools/stage17_operational_cli_v11.py`'s `author_ext001` (edited in
place, per this repository's established precedent that no sealed
`S17-EXT-001` envelope pins `cli_v11.py`'s own bytes) now computes these
six values for real from the archive/sidecar/bundle-root paths actually
passed on the command line, for the no-predecessor-attestation branch
only -- the three-blocker-receipt branch is unchanged, still emits a v12
contract, and is out of scope for this fix (it has never been exercised
by any real admission this session and carries the identical latent
defect, left for a future ADR). `verify_s17_ext_001_semantics_v20`
therefore accepts only a `/14` contract, not `/12` or `/13`, and
independently re-verifies the captured archive/sidecar/manifest identity
against the real bytes at those locators (the same `_verify_external_
binding` pattern already used for blocker-receipt and attestation
bindings), rather than trusting `author_ext001`'s claimed values alone.
"""

from __future__ import annotations

import os
import pathlib
from typing import Any, Mapping

import stage17_read_only_preflight_semantic_verifier_v14 as base_v14
import stage17_read_only_preflight_semantic_verifier_v19 as immediate_predecessor
from stage17_semantic_verifier_v3 import (
    LIMITS, OBSERVATION_IDS, PERMISSIONS, SemanticAdmissionError,
    _binding, _binding_for, _load_json, _validate_schema, _sha256,
)
from stage17_semantic_verifier_v5 import _exact_second


predecessor = immediate_predecessor.predecessor

POLICY_PATH = "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v20.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v20.schema.json"
POLICY_V19_PATH = immediate_predecessor.POLICY_PATH
ADR_0134_PATH = "docs/decisions/0134-stage17-preflight-archive-identity-source.md"
EFFECTIVE_ACTION_PLAN_PATH = immediate_predecessor.EFFECTIVE_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_PATH = immediate_predecessor.SUCCESSOR_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_SCHEMA_PATH = (
    immediate_predecessor.SUCCESSOR_ACTION_PLAN_SCHEMA_PATH
)
SCHEMA_PATHS = immediate_predecessor.SCHEMA_PATHS
IMPLEMENTATION_PATHS = {
    **immediate_predecessor.IMPLEMENTATION_PATHS,
    "semantic_verifier": "tools/stage17_read_only_preflight_semantic_verifier_v20.py",
    "executor": "tools/stage17_read_only_preflight_executor_v18.py",
    "state_journal": "tools/stage17_state_journal_v24.py",
}
"""``semantic_verifier`` moves to this file itself for the first time
since `v15` (``v16``-``v19`` all kept it pointed at `v15.py`, since action-
time re-validation always loaded `current_semantic` = `v15` unchanged);
this ADR changes real revalidation logic, so `current_semantic` must now
load this file, matching its own runtime-identity record.
``process_group_supervisor`` and ``openssh_snapshot_broker`` stay at
`v19`'s inherited values (`v3.py`/`v5.py`); this ADR does not touch
process-group supervision or OpenSSH consumption at all."""

ENVELOPE_SCHEMA_PATH = immediate_predecessor.ENVELOPE_SCHEMA_PATH
AUTHORIZATION_SCHEMA_PATH = immediate_predecessor.AUTHORIZATION_SCHEMA_PATH
CONTRACT_V12_SCHEMA_PATH = immediate_predecessor.CONTRACT_V12_SCHEMA_PATH
CONTRACT_V13_SCHEMA_PATH = immediate_predecessor.CONTRACT_V13_SCHEMA_PATH
CONTRACT_V14_SCHEMA_PATH = (
    "config/schemas/stage17-read-only-preflight-supporting-contract-v14.schema.json"
)
NO_PREDECESSOR_ATTESTATION_SCHEMA_PATH = (
    immediate_predecessor.NO_PREDECESSOR_ATTESTATION_SCHEMA_PATH
)
NO_PREDECESSOR_ATTESTATION_SCHEMA_IDENTITY = (
    immediate_predecessor.NO_PREDECESSOR_ATTESTATION_SCHEMA_IDENTITY
)
VERIFIER_ID = immediate_predecessor.VERIFIER_ID
VERIFIER_VERSION = immediate_predecessor.VERIFIER_VERSION
"""Stays `"14"`, inherited unchanged: this is the stable `S17-EXT-001`
protocol identity string embedded in every envelope/policy entry, not
this file's own generation suffix -- `v15` through `v19` never bumped it
either, including `v15`'s own real addition of the whole D-124 attestation
branch, so `cli_v11.py`'s `author_ext001` (which hardcodes `"verifier_
version": "14"` when building the envelope) stays correct unchanged."""

ATTEMPT_SCHEMA_PATH = base_v14.ATTEMPT_SCHEMA_PATH
RECEIPT_SCHEMA_PATH = base_v14.RECEIPT_SCHEMA_PATH
FAILURE_SCHEMA_PATH = base_v14.FAILURE_SCHEMA_PATH
FAILURE_RETENTION_SCHEMA_PATH = base_v14.FAILURE_RETENTION_SCHEMA_PATH
COMPLETION_SCHEMA_PATH = base_v14.COMPLETION_SCHEMA_PATH
"""These five record-schema constants and ``POLICY_V13_PATH``/``ADR_0123_
PATH``/``_parse_utc`` below are read directly from ``v14.py``, the module
that actually defines them, rather than walked through the ``v15``-``v19``
attribute chain: `v15` itself never re-exports them as its own top-level
names (it only reads them via ``immediate_predecessor.NAME`` inline), and
`v16`-`v19` never touch them at all, so a hardcoded multi-hop chain from
`v20`'s own `immediate_predecessor` (`v19`) would raise ``AttributeError``
partway through. Importing the defining module directly is the same fix
this repository's own ``_find_base()`` policy-authoring helper already
established for the identical class of problem."""

_verify_pre_marker_predecessor = immediate_predecessor._verify_pre_marker_predecessor
_verify_post_marker_predecessor = immediate_predecessor._verify_post_marker_predecessor
_verify_action_revalidation_predecessor = (
    immediate_predecessor._verify_action_revalidation_predecessor
)
_verify_external_binding = immediate_predecessor._verify_external_binding
_verify_successor_plan = immediate_predecessor._verify_successor_plan
_verify_no_predecessor_attestation = immediate_predecessor._verify_no_predecessor_attestation
classify_predecessor_evidence = immediate_predecessor.classify_predecessor_evidence


def verify_policy_v20(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_file_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    """Faithful copy of predecessor ``verify_policy_v19``, retargeted at v20.

    Every check is identical; only the module-level bindings this function
    resolves against differ (v20's own ``POLICY_SCHEMA_PATH``,
    ``IMPLEMENTATION_PATHS`` binding executor v18/semantic verifier v20/
    state journal v24 instead of v17/v15/v23, and the ``policy_v19``/
    ``adr_0134`` predecessor keys instead of ``policy_v18``/``adr_0133``).
    """
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v20")
    expected_predecessor = {
        "policy_v19": _binding_for(root, POLICY_V19_PATH),
        "adr_0134": _binding_for(root, ADR_0134_PATH),
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if policy.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v20 predecessor binding drifted")
    if policy.get("schema_bindings") != [_binding_for(root, item) for item in SCHEMA_PATHS]:
        raise SemanticAdmissionError("semantic policy v20 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, EFFECTIVE_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v20 effective action plan drifted")
    if policy.get("successor_action_plan") != _binding_for(root, SUCCESSOR_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v20 successor action plan drifted")
    if policy.get("operational_contract") != _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"):
        raise SemanticAdmissionError("semantic policy v20 operational contract drifted")
    if policy.get("implementations") != {
        name: _binding_for(root, path) for name, path in IMPLEMENTATION_PATHS.items()
    }:
        raise SemanticAdmissionError("semantic policy v20 runtime closure drifted")
    expected_operational_implementations = {
        "semantic_admission": _binding_for(root, "tools/stage17_operational_semantics_v1.py"),
        "phase_controller": _binding_for(root, "tools/stage17_phase_controller_v1.py"),
        "exit_state_machine": _binding_for(root, "tools/stage17_exit_state_machine_v1.py"),
        "pid_namespace_supervisor": _binding_for(root, "tools/stage17_process_group_supervisor_v3.py"),
    }
    if policy.get("operational_implementations") != expected_operational_implementations:
        raise SemanticAdmissionError("semantic policy v20 operational runtime drifted")
    expected_operational_definitions = {
        "external_contract": _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"),
        "fixed_phase_actions": _binding_for(root, "config/stage17/stage17-fixed-phase-actions-v1.json"),
        "phase18_readiness_template": _binding_for(root, "config/stage17/phase18-readiness-template-v1.json"),
        "phase18_authorization_draft": _binding_for(root, "config/stage17/phase18-authorization-draft-v1.json"),
    }
    if policy.get("operational_definitions") != expected_operational_definitions:
        raise SemanticAdmissionError("semantic policy v20 operational definitions drifted")
    entries = policy.get("entries")
    expected = [
        {"input_id": f"S17-EXT-{index:03d}", "status": "IMPLEMENTED",
         "verifier_id": f"STAGE17-S17-EXT-{index:03d}-SEMANTIC-VERIFIER",
         "verifier_version": "9" if index == 1 else ("1" if index != 6 else "1")}
        for index in range(1, 11)
    ]
    expected[0]["verifier_id"] = VERIFIER_ID
    expected[0]["verifier_version"] = VERIFIER_VERSION
    expected[5]["verifier_id"] = "STAGE17-PILOT-CANDIDATE-EXTERNAL-VERIFIER"
    if entries != expected:
        raise SemanticAdmissionError("semantic policy v20 complete registry drifted")
    if policy.get("synthetic_bypass_available") is not False or policy.get("stage18_authority") is not False:
        raise SemanticAdmissionError("semantic policy v20 authority boundary drifted")


def _verify_captured_pilot_candidate_identity(pilot_candidate: Mapping[str, Any]) -> None:
    """Independently re-verify the captured archive/sidecar/manifest identity.

    `author_ext001` computes these six fields from the real bytes at
    authoring time; this re-derives them from the same locators at
    resolution time so a real admission can never rest on an unverified
    claim, mirroring the pattern already used for blocker-receipt and
    attestation bindings.
    """
    _verify_external_binding(
        {
            "locator": pilot_candidate.get("archive_locator"),
            "size_bytes": pilot_candidate.get("archive_size_bytes"),
            "sha256": pilot_candidate.get("archive_sha256"),
        },
        "pilot-candidate archive",
    )
    _verify_external_binding(
        {
            "locator": pilot_candidate.get("sidecar_locator"),
            "size_bytes": pilot_candidate.get("sidecar_size_bytes"),
            "sha256": pilot_candidate.get("sidecar_sha256"),
        },
        "pilot-candidate sidecar",
    )
    bundle_root = pathlib.Path(str(pilot_candidate.get("bundle_root_locator", "")))
    manifest_path = bundle_root / "BUNDLE_MANIFEST.json"
    if (not manifest_path.is_absolute() or manifest_path.is_symlink()
            or not manifest_path.is_file()
            or _sha256(manifest_path) != pilot_candidate.get("manifest_sha256")):
        raise SemanticAdmissionError("pilot-candidate manifest identity drifted")
    inventory_path = bundle_root / "SHA256SUMS"
    if (not inventory_path.is_absolute() or inventory_path.is_symlink()
            or not inventory_path.is_file()):
        raise SemanticAdmissionError("pilot-candidate checksum inventory is absent")
    if (len(inventory_path.read_text(encoding="utf-8").splitlines())
            != pilot_candidate.get("internal_file_count")):
        raise SemanticAdmissionError("pilot-candidate internal file count drifted")


def verify_s17_ext_001_semantics_v20(
    *, root: pathlib.Path, resolution: dict[str, Any],
    repository_documents: list[tuple[pathlib.Path, dict[str, Any]]],
    receipt_documents: list[dict[str, Any]], policy: dict[str, Any],
    policy_path: pathlib.Path, policy_sha256: str, policy_entry: dict[str, Any],
    graph_sha256: str, catalog_sha256: str, genesis_sha256: str,
    catalog: dict[str, Any], resolution_schema_sha256: str, **_: Any,
) -> dict[str, Any]:
    if receipt_documents:
        raise SemanticAdmissionError("S17-EXT-001 cannot use an external receipt")
    envelopes = [(path, document) for path, document in repository_documents if document.get("schema_version") == "cpu-prefetch-stage17-operational-evidence-envelope/14"]
    if len(envelopes) != 1 or len(repository_documents) != 1:
        raise SemanticAdmissionError("S17-EXT-001 requires exactly one v14 envelope")
    envelope_path, envelope = envelopes[0]
    _validate_schema(root, envelope, ENVELOPE_SCHEMA_PATH, "S17-EXT-001 v14 envelope")
    if envelope.get("semantic_policy") != {"path": policy_path.relative_to(root).as_posix(), "size_bytes": policy_path.stat().st_size, "sha256": policy_sha256}:
        raise SemanticAdmissionError("S17-EXT-001 policy binding mismatch")
    if envelope.get("semantic_verifier") != {"verifier_id": VERIFIER_ID, "verifier_version": VERIFIER_VERSION}:
        raise SemanticAdmissionError("S17-EXT-001 verifier identity mismatch")
    expected_predecessor = {
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_sha256": genesis_sha256,
        "resolution_schema_identity": "cpu-prefetch-stage17-external-input-resolution/1",
        "resolution_schema_sha256": resolution_schema_sha256,
        "semantic_policy_v13_sha256": _sha256(root / base_v14.POLICY_V13_PATH),
        "adr_0123_sha256": _sha256(root / base_v14.ADR_0123_PATH),
    }
    if envelope.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("S17-EXT-001 v14 predecessor binding drifted")
    if envelope.get("runtime_implementations") != policy.get("implementations"):
        raise SemanticAdmissionError("S17-EXT-001 runtime closure drifted")
    expected_effective = {**policy["fixed_action_plan"], "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/6"}
    expected_successor = {**policy["successor_action_plan"], "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/9"}
    if envelope.get("effective_action_plan") != expected_effective or envelope.get("successor_action_plan") != expected_successor:
        raise SemanticAdmissionError("S17-EXT-001 action plan binding drifted")
    _verify_successor_plan(root, policy)
    authorization_path = _binding(root, envelope["authorization"], "authorization")
    contract_path = _binding(root, envelope["supporting_contract"], "supporting contract")
    contract_schema_identity = envelope["supporting_contract"].get("schema_identity")
    if envelope["authorization"].get("schema_identity") != "cpu-prefetch-stage17-read-only-preflight-authorization/11":
        raise SemanticAdmissionError("S17-EXT-001 authorization schema drifted")
    if contract_schema_identity != "cpu-prefetch-stage17-read-only-preflight-supporting-contract/14":
        raise SemanticAdmissionError("S17-EXT-001 contract schema drifted")
    authorization, contract = _load_json(authorization_path), _load_json(contract_path)
    _validate_schema(root, authorization, AUTHORIZATION_SCHEMA_PATH, "authorization v11")
    _validate_schema(root, contract, CONTRACT_V14_SCHEMA_PATH, "supporting contract v14")
    if authorization.get("supporting_observation_contract") != envelope["supporting_contract"] or authorization.get("fixed_action_plan") != expected_effective:
        raise SemanticAdmissionError("authorization contract/effective-plan binding drifted")
    issued = _exact_second(authorization.get("issued_at_utc"), "authorization issued_at_utc")
    expires = _exact_second(authorization.get("expires_at_utc"), "authorization expires_at_utc")
    if expires <= issued:
        raise SemanticAdmissionError("authorization expiry must follow issue")
    verified = predecessor._verify_contract_action_inputs(root, contract, policy, catalog)
    _verify_captured_pilot_candidate_identity(contract["pilot_candidate"])
    has_attestation = classify_predecessor_evidence(contract) == "ATTESTATION"
    if has_attestation:
        attestation, _attestation_path = _verify_no_predecessor_attestation(
            root, contract["no_predecessor_attestation"]
        )
        verified["no_predecessor_attestation"] = dict(contract["no_predecessor_attestation"])
    else:
        blocker = contract.get("pre_marker_predecessor")
        if not isinstance(blocker, dict):
            raise SemanticAdmissionError("pre-marker predecessor blocker binding is absent")
        _verify_pre_marker_predecessor(root, blocker)
        verified["pre_marker_predecessor"] = dict(blocker)
        post_marker = contract.get("post_marker_predecessor")
        if not isinstance(post_marker, dict):
            raise SemanticAdmissionError("post-marker predecessor blocker binding is absent")
        _verify_post_marker_predecessor(root, post_marker)
        verified["post_marker_predecessor"] = dict(post_marker)
        action_revalidation = contract.get("action_revalidation_predecessor")
        if not isinstance(action_revalidation, dict):
            raise SemanticAdmissionError(
                "action-revalidation predecessor blocker binding is absent"
            )
        _verify_action_revalidation_predecessor(root, action_revalidation)
        verified["action_revalidation_predecessor"] = dict(action_revalidation)
    schema_by_path = {item["path"]: dict(item) for item in policy["schema_bindings"]}
    verified["record_schema_bindings"] = {
        "attempt": schema_by_path[ATTEMPT_SCHEMA_PATH],
        "receipt": schema_by_path[RECEIPT_SCHEMA_PATH],
        "failure": schema_by_path[FAILURE_SCHEMA_PATH],
        "failure_retention":
            schema_by_path[FAILURE_RETENTION_SCHEMA_PATH],
        "completion": schema_by_path[COMPLETION_SCHEMA_PATH],
    }
    verified["attempt_marker_name"] = "stage17-read-only-preflight-attempt-v10.json"
    verified["failure_name"] = "stage17-read-only-preflight-failure-v8.json"
    verified["failure_retention_name"] = (
        "stage17-read-only-preflight-failure-retention-v3.json"
    )
    verified["completion_name"] = "stage17-read-only-preflight-completion-v7.json"
    target = contract["target"]
    expected_target = {
        "stand_id": target["stand_id"], "ssh_target": target["ssh_target"],
        "known_hosts_host": target["known_hosts_host"],
        "pinned_host_key_evidence_sha256": target["pinned_host_key_evidence"]["sha256"],
        "pinned_known_hosts_sha256": target["pinned_known_hosts"]["sha256"],
        "transport_identity_sha256": target["transport_identity"]["sha256"],
    }
    if authorization.get("target") != expected_target or tuple(authorization.get("frozen_observation_ids", [])) != OBSERVATION_IDS:
        raise SemanticAdmissionError("authorization target/observation family drifted")
    expected_scope = (
        f"STAND_ID={target['stand_id']};SSH_TARGET={target['ssh_target']};"
        "SCOPE=READ_ONLY_PREFLIGHT;PLAN=STAGE17-READ-ONLY-PREFLIGHT-FIXED-ACTION-PLAN-v6"
    )
    if authorization.get("target_scope") != expected_scope or authorization.get("evidence_root") != contract.get("evidence_root"):
        raise SemanticAdmissionError("authorization target scope/evidence root drifted")
    if authorization.get("limits") != LIMITS or authorization.get("permissions") != PERMISSIONS:
        raise SemanticAdmissionError("authorization limits/permissions widened")
    if any((authorization.get("role_collapse_acknowledged") is not True, authorization.get("independent_review_claimed") is not False, authorization.get("automatic_transition") is not False, authorization.get("retry_allowed") is not False, authorization.get("stage18_authority") is not False)):
        raise SemanticAdmissionError("authorization governance boundary drifted")
    summary = resolution.get("authorization")
    if not isinstance(summary, dict):
        raise SemanticAdmissionError("resolution authorization summary is missing")
    for field in ("authorization_id", "issued_at_utc", "expires_at_utc", "authority_scope"):
        if summary.get(field) != authorization.get(field):
            raise SemanticAdmissionError(f"resolution authorization {field} mismatch")
    if summary.get("evidence_path") != authorization_path.relative_to(root).as_posix() or authorization.get("actor") != resolution.get("actor"):
        raise SemanticAdmissionError("resolution authorization path/actor mismatch")
    recorded = base_v14._parse_utc(
        resolution.get("recorded_at_utc"), "resolution time"
    )
    if not issued <= recorded < expires:
        raise SemanticAdmissionError("authorization is not valid at resolution time")
    return {"authorization": authorization, "context": {
        "authorization_path": authorization_path, "authorization_sha256": _sha256(authorization_path),
        "contract_path": contract_path, "contract_sha256": _sha256(contract_path),
        "contract": contract, "policy": policy, "policy_path": policy_path,
        "policy_sha256": policy_sha256, "manifest_id": envelope["envelope_id"],
        "manifest_path": str(envelope_path), "manifest_sha256": _sha256(envelope_path),
        "synthetic_test_only": envelope["envelope_id"].startswith("SYNTHETIC-"),
        **verified,
    }}


def _reverify_current_action_inputs_v20(
    root: pathlib.Path, semantic_context: dict[str, Any],
    runtime_identity_paths: dict[str, str] | None,
) -> dict[str, Any]:
    """A faithful copy of `v14`'s `_reverify_current_action_inputs`, changed
    only so `collector_context`'s archive/sidecar/manifest identity is read
    from the actually-captured `contract["pilot_candidate"]` fields instead
    of from `semantic_context["pilot_contract"]` (the frozen `S17-EXT-006`
    baseline). `pilot_candidate` is re-verified against real bytes on every
    call (`_verify_captured_pilot_candidate_identity`), the same defense-in-
    depth `verify_s17_ext_001_semantics_v20` already applies at resolution
    time, so action-time revalidation can never trust a stale claim either.
    """
    policy_path, contract_path, authorization_path = (
        semantic_context["policy_path"],
        semantic_context["contract_path"],
        semantic_context["authorization_path"],
    )
    for path, digest, label in (
        (policy_path, semantic_context["policy_sha256"], "semantic policy"),
        (contract_path, semantic_context["contract_sha256"], "supporting contract"),
        (authorization_path, semantic_context["authorization_sha256"], "authorization"),
    ):
        if _sha256(path) != digest:
            raise SemanticAdmissionError(f"action-time {label} drifted")
    policy, contract = _load_json(policy_path), _load_json(contract_path)
    for binding in policy["schema_bindings"]:
        _binding(root, binding, f"action-time schema {binding['path']}")
    for name, binding in policy["implementations"].items():
        _binding(root, binding, f"action-time {name}")
    plan, _ = predecessor._verify_action_plan(root, policy)
    runtime_hashes = predecessor._verify_loaded_runtime(
        policy=policy,
        contract=contract,
        runtime_identity_paths=runtime_identity_paths,
    )
    for identity in contract["prospective_local_action_identities"]:
        predecessor._external_executable(
            identity["execution_path"],
            identity["source_binding"],
            f"action-time {identity['role']}",
        )
    target = contract["target"]
    _, known_hosts_path, _ = predecessor._verify_known_host(root, target)
    transport_identity_path, transport_identity_binding = \
        predecessor._external_private_binding(
            target["transport_identity"], "action-time transport identity"
        )
    evidence_root, root_identity = predecessor._safe_evidence_root(
        root, contract["evidence_root"]
    )
    if root_identity != semantic_context["evidence_root_identity"]:
        raise SemanticAdmissionError("evidence root identity changed")
    fixed_names = [
        *(
            f"stage17-read-only-preflight-attempt-v{version}.json"
            for version in range(1, 11)
        ),
        *(
            f"stage17-read-only-preflight-failure-v{version}.json"
            for version in range(2, 9)
        ),
        *(
            f"stage17-read-only-preflight-failure-retention-v{version}.json"
            for version in range(1, 4)
        ),
        *(
            f"stage17-read-only-preflight-completion-v{version}.json"
            for version in range(1, 8)
        ),
    ]
    fixed_names.extend(
        f"s17-ro-{ordinal:03d}{suffix}"
        for ordinal in range(1, 7)
        for suffix in (
            ".stdout.bin",
            ".stderr.bin",
            ".receipt-v1.json",
            ".receipt-v2.json",
            ".receipt-v3.json",
            ".receipt-v4.json",
            ".receipt-v5.json",
            ".receipt-v6.json",
            ".receipt-v7.json",
        )
    )
    if any(os.path.lexists(evidence_root / name) for name in fixed_names):
        raise SemanticAdmissionError(
            "one-shot predecessor/current marker or output already exists"
        )
    schema_by_path = {item["path"]: dict(item) for item in policy["schema_bindings"]}
    action_plan_path = root / policy["fixed_action_plan"]["path"]
    pre_marker_file_bindings = [
        {
            "locator": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": digest,
        }
        for path, digest in (
            (policy_path, semantic_context["policy_sha256"]),
            (contract_path, semantic_context["contract_sha256"]),
            (authorization_path, semantic_context["authorization_sha256"]),
            (action_plan_path, policy["fixed_action_plan"]["sha256"]),
        )
    ]
    authorization = _load_json(authorization_path)
    pilot_candidate = contract["pilot_candidate"]
    _verify_captured_pilot_candidate_identity(pilot_candidate)
    return {
        "attempt_id": authorization["attempt_id"],
        "authorization_id": authorization["authorization_id"],
        "authorization_sha256": _sha256(authorization_path),
        "authorization": authorization,
        "evidence_root": str(evidence_root),
        "evidence_root_identity": root_identity,
        "attempt_marker_name": "stage17-read-only-preflight-attempt-v10.json",
        "failure_name": "stage17-read-only-preflight-failure-v8.json",
        "failure_retention_name":
            "stage17-read-only-preflight-failure-retention-v3.json",
        "completion_name": "stage17-read-only-preflight-completion-v7.json",
        "ssh_target": target["ssh_target"],
        "known_hosts_binding": {
            "locator": str(known_hosts_path),
            "size_bytes": target["pinned_known_hosts"]["size_bytes"],
            "sha256": target["pinned_known_hosts"]["sha256"],
        },
        "transport_identity_binding": {
            **transport_identity_binding,
            "locator": str(transport_identity_path),
        },
        "action_plan_sha256": policy["fixed_action_plan"]["sha256"],
        "runtime_implementation_hashes": runtime_hashes,
        "observation_ids": list(OBSERVATION_IDS),
        "fixed_ssh_argv_template": list(plan["transport"]["fixed_ssh_argv_template"]),
        "timeout_seconds": LIMITS["timeout_seconds_per_observation"],
        "max_output_bytes": LIMITS["max_output_bytes_per_observation"],
        "max_total_output_bytes": LIMITS["max_total_output_bytes"],
        "max_wall_seconds": LIMITS["max_wall_seconds"],
        "record_schema_bindings": {
            "attempt": schema_by_path[ATTEMPT_SCHEMA_PATH],
            "receipt": schema_by_path[RECEIPT_SCHEMA_PATH],
            "failure": schema_by_path[FAILURE_SCHEMA_PATH],
            "failure_retention": schema_by_path[FAILURE_RETENTION_SCHEMA_PATH],
            "completion": schema_by_path[COMPLETION_SCHEMA_PATH],
        },
        "pre_marker_file_bindings": pre_marker_file_bindings,
        "collector_context": {
            "archive_locator": pilot_candidate["archive_locator"],
            "sidecar_locator": pilot_candidate["sidecar_locator"],
            "bundle_root_locator": pilot_candidate["bundle_root_locator"],
            "capture_id": contract["capture"]["capture_id"],
            "captured_at_utc": contract["capture"]["captured_at_utc"],
            "archive_size_bytes": pilot_candidate["archive_size_bytes"],
            "archive_sha256": pilot_candidate["archive_sha256"],
            "sidecar_size_bytes": pilot_candidate["sidecar_size_bytes"],
            "sidecar_sha256": pilot_candidate["sidecar_sha256"],
            "manifest_sha256": pilot_candidate["manifest_sha256"],
            "internal_file_count": pilot_candidate["internal_file_count"],
        },
    }


def evaluate_s17_ext_001_action_readiness_v20(
    *, root: pathlib.Path, current_state: str,
    transition_documents: list[dict[str, Any]],
    transition_ids_and_hashes: list[tuple[str, str]], resolution_id: str,
    resolution_sha256: str, authorization: dict[str, Any],
    semantic_context: dict[str, Any], as_of_utc: str,
    runtime_identity_paths: dict[str, str] | None,
) -> dict[str, Any] | None:
    """A faithful copy of `v15`'s `evaluate_s17_ext_001_action_readiness_v15`,
    changed only to call `_reverify_current_action_inputs_v20` instead of
    `immediate_predecessor._reverify_current_action_inputs` (`v14`'s), so
    the corrected `collector_context` construction is actually reached at
    real action time, not just at resolution time.
    """
    if current_state != "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT" or len(transition_documents) != 1:
        return None
    transition = transition_documents[0]
    if transition.get("evidence_resolutions") != [{"input_id": "S17-EXT-001", "resolution_id": resolution_id, "sha256": resolution_sha256}]:
        return None
    if transition.get("authorizations") != [{"input_id": "S17-EXT-001", "resolution_id": resolution_id, "authorization_id": authorization.get("authorization_id"), "authority_scope": "READ_ONLY_PREFLIGHT"}]:
        return None
    evaluation = base_v14._parse_utc(as_of_utc, "action evaluation time")
    issued = _exact_second(authorization.get("issued_at_utc"), "authorization issue")
    expires = _exact_second(authorization.get("expires_at_utc"), "authorization expiry")
    if not issued <= evaluation < expires:
        return None
    try:
        action = _reverify_current_action_inputs_v20(
            root, semantic_context, runtime_identity_paths
        )
        _verify_successor_plan(root, semantic_context["policy"])
        contract = semantic_context["contract"]
        if classify_predecessor_evidence(contract) == "ATTESTATION":
            _, attestation_path = _verify_no_predecessor_attestation(
                root, contract["no_predecessor_attestation"]
            )
            extra_file_bindings = [{
                "locator": str(attestation_path),
                "size_bytes": attestation_path.stat().st_size,
                "sha256": _sha256(attestation_path),
            }]
        else:
            _, blocker_path = _verify_pre_marker_predecessor(
                root, contract["pre_marker_predecessor"]
            )
            _, post_marker_path = _verify_post_marker_predecessor(
                root, contract["post_marker_predecessor"]
            )
            _, action_revalidation_path = _verify_action_revalidation_predecessor(
                root, contract["action_revalidation_predecessor"],
            )
            extra_file_bindings = [
                {"locator": str(blocker_path), "size_bytes": blocker_path.stat().st_size, "sha256": _sha256(blocker_path)},
                {"locator": str(post_marker_path), "size_bytes": post_marker_path.stat().st_size, "sha256": _sha256(post_marker_path)},
                {"locator": str(action_revalidation_path), "size_bytes": action_revalidation_path.stat().st_size, "sha256": _sha256(action_revalidation_path)},
            ]
    except (KeyError, SemanticAdmissionError, OSError, ValueError):
        return None
    evidence_root = pathlib.Path(action["evidence_root"])
    if any(evidence_root.iterdir()):
        return None
    action["pre_marker_file_bindings"] = [
        *action["pre_marker_file_bindings"],
        *extra_file_bindings,
    ]
    transition_id, transition_sha256 = transition_ids_and_hashes[0]
    action.update({"resolution_id": resolution_id, "resolution_sha256": resolution_sha256, "transition_id": transition_id, "transition_sha256": transition_sha256})
    return action
