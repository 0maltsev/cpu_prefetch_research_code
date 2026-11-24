#!/usr/bin/env python3
"""Stage 17 operational-evidence successor correcting S17-EXT-002's
preflight receipt-to-artifact pairing (ADR-0140).

`tools/stage17_operational_semantics_v4.py`'s `_validate_preflight`
(never touched by `v5.py`/`v6.py`, both of which only overrode
`_read_artifacts`/`ROLE_SCHEMA`) pairs each observation receipt to its
`PREFLIGHT_STDOUT`/`PREFLIGHT_STDERR` artifact by searching the *entire*
stdout/stderr artifact pool for the one entry whose hash+size matches the
receipt's declared value, then requires that search to find *exactly
one* match. This is the real, reproduced failure this fixes: a genuinely
successful real preflight run (the fourteenth real admission, evidence
root `stage17-operational-evidence-14`) produces six byte-identical
empty `stderr` files -- one per observation, all clean, all zero bytes
-- so the "exactly one match" search finds all six for every receipt and
`admit-resolution --input-id S17-EXT-002` unconditionally fails with
"preflight receipt does not bind exact stdout/stderr bytes", regardless
of how genuinely correct the underlying evidence is. This was never
caught before because no real `S17-EXT-002` admission had ever reached
this specific check until ADR-0138/ADR-0139 cleared the schema-pinning
and journal-reachability gaps blocking it.

`_validate_preflight_v7` is a fresh copy of the predecessor's function
(confirmed by exact extraction), changed only in how the stdout/stderr
pairing works: instead of a global hash-uniqueness search, each
`PREFLIGHT_STDOUT`/`PREFLIGHT_STDERR` artifact's own `artifact_id` is
now required to equal `f"{observation_id}-STDOUT"`/`f"{observation_id}-
STDERR"` -- an unambiguous, per-observation identifier real `author-
manifest` callers must follow going forward -- and the found artifact's
actual bytes are then verified against the receipt's declared hash/size,
preserving the original integrity check while removing the false
uniqueness assumption. `verify_manifest_v7` is a fresh copy of `v6`'s
complete body (confirmed by exact extraction), changed only to call
`_validate_preflight_v7`; every other branch (S17-EXT-003 through
S17-EXT-010) is byte-identical, since none of them touch preflight
receipt pairing. `_read_artifacts_v6`/`ROLE_SCHEMA_v6` are reused
unmodified via re-export -- aliases, not fresh copies, since neither
reads a free variable this fix changes.
"""

from __future__ import annotations

import collections
import pathlib
import stat
from typing import Any, Mapping

import stage17_operational_semantics_v6 as predecessor


Artifact = predecessor.Artifact
EXPECTED_ROLES = predecessor.EXPECTED_ROLES
LOGICAL_ENVELOPE_ROLES = predecessor.LOGICAL_ENVELOPE_ROLES
MANIFEST_SCHEMA = predecessor.MANIFEST_SCHEMA
MEASUREMENT_KEYS = predecessor.MEASUREMENT_KEYS
OperationalSemanticError = predecessor.OperationalSemanticError
SIGNATURE_ROLES = predecessor.SIGNATURE_ROLES
STREAMING_OBSERVATION_ROLES = predecessor.STREAMING_OBSERVATION_ROLES
TYPED_SCHEMA = predecessor.TYPED_SCHEMA
ROLE_SCHEMA_v6 = predecessor.ROLE_SCHEMA_v6
_read_artifacts_v6 = predecessor._read_artifacts_v6
_artifact_content = predecessor._artifact_content
_artifact_index = predecessor._artifact_index
_one = predecessor._one
_phase_family = predecessor._phase_family
_resolution_bindings = predecessor._resolution_bindings
_schema = predecessor._schema
_validate = predecessor._validate
load = predecessor.load
output_registry = predecessor.output_registry
pilot_plan_runtime = predecessor.pilot_plan_runtime
sha = predecessor.sha
verify_sshsig = predecessor.verify_sshsig
_verify_extracted_release_v5 = predecessor._verify_extracted_release_v5


def _validate_preflight_v7(
    artifacts: list[Artifact], ext1: Any,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Faithful copy of predecessor `_validate_preflight`, changed only in
    how each observation receipt is paired to its own stdout/stderr
    artifact -- see this module's own docstring for why.
    """
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
    stdout_by_id = {
        item.reference["artifact_id"]: item for item in artifacts
        if item.role == "PREFLIGHT_STDOUT"
    }
    stderr_by_id = {
        item.reference["artifact_id"]: item for item in artifacts
        if item.role == "PREFLIGHT_STDERR"
    }
    for receipt in receipts:
        out = stdout_by_id.get(f"{receipt['observation_id']}-STDOUT")
        err = stderr_by_id.get(f"{receipt['observation_id']}-STDERR")
        if (out is None or err is None
                or sha(out.payload) != receipt["stdout_sha256"]
                or len(out.payload) != receipt["stdout_size_bytes"]
                or sha(err.payload) != receipt["stderr_sha256"]
                or len(err.payload) != receipt["stderr_size_bytes"]):
            raise OperationalSemanticError(
                "preflight receipt does not bind exact stdout/stderr bytes"
            )
    return runtime, trust, ids


def verify_manifest_v7(
    *, repository_root: pathlib.Path, manifest_path: pathlib.Path,
    admitted_resolutions: Mapping[str, Any], expected_input_id: str,
    allow_synthetic: bool, pinned_repository_bytes: Mapping[str, bytes],
) -> dict[str, Any]:
    """Faithful copy of predecessor `verify_manifest_v6`'s complete body,
    changed only to call `_validate_preflight_v7` instead of `_validate_
    preflight`. Every branch for S17-EXT-003 through S17-EXT-010 is
    otherwise byte-identical, since only preflight receipt pairing
    depends on the fix this ADR makes.
    """
    root = repository_root.resolve()
    manifest, payload = load(manifest_path)
    _validate(root, manifest, MANIFEST_SCHEMA, "operational manifest v4",
              pinned_repository_bytes)
    if (manifest["input_id"] != expected_input_id
            or expected_input_id not in EXPECTED_ROLES
            or manifest["synthetic_test_only"] is not allow_synthetic):
        raise OperationalSemanticError("manifest input/classification drifted")
    artifacts = _read_artifacts_v6(root, manifest_path, manifest,
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
        runtime, trust, observation_ids = _validate_preflight_v7(
            artifacts, admitted_resolutions["S17-EXT-001"]
        )
        release_context = _verify_extracted_release_v5(
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
