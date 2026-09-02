#!/usr/bin/env python3
"""Stage 17 operational-evidence successor recognizing newer pilot-candidate
bundle profiles for real S17-EXT-002 admission (ADR-0129).

`tools/stage17_operational_semantics_v4.py`'s `verify_manifest_v4` (part of
the frozen, accepted `v18` closure) calls `_verify_extracted_release` for
its `S17-EXT-002` branch, which calls `release_verifier.verify_extracted_
release_receipt_v4` -- confirmed to internally call the same frozen,
narrow `verify_extracted_bundle_v4` whitelist ADR-0128 already fixed for
the separate `S17-EXT-006` call site. This is a new, additive successor:
`v4` and its entire accepted closure are untouched.

`_verify_extracted_release_v5` is a faithful copy of `_verify_extracted_
release`, retargeted to call `stage17_pilot_candidate_artifact_v6.verify_
extracted_release_receipt_v6` (built on `v5`'s already-broadened profile
whitelist) instead of the frozen `_v4` module's. `verify_manifest_v5` is a
faithful copy of the full `verify_manifest_v4` body -- confirmed by exact
programmatic extraction, not manual retyping -- with only its
`S17-EXT-002` branch's call retargeted to `_verify_extracted_release_v5`;
every other branch (`S17-EXT-003` through `S17-EXT-010`) is byte-identical
to the predecessor, since only the `S17-EXT-002` branch was confirmed
(by searching the full function body) to reference the release verifier
at all.
"""

from __future__ import annotations

import collections
import pathlib
import stat
from typing import Any, Mapping

import stage17_operational_semantics_v4 as predecessor
import stage17_pilot_candidate_artifact_v6 as release_verifier


EXPECTED_ROLES = predecessor.EXPECTED_ROLES
MANIFEST_SCHEMA = predecessor.MANIFEST_SCHEMA
OperationalSemanticError = predecessor.OperationalSemanticError
_artifact_index = predecessor._artifact_index
_one = predecessor._one
_phase_family = predecessor._phase_family
_read_artifacts = predecessor._read_artifacts
_resolution_bindings = predecessor._resolution_bindings
_validate = predecessor._validate
_validate_preflight = predecessor._validate_preflight
load = predecessor.load
pilot_plan_runtime = predecessor.pilot_plan_runtime
sha = predecessor.sha
verify_sshsig = predecessor.verify_sshsig


def _verify_extracted_release_v5(
    root: pathlib.Path, provenance: "predecessor.Artifact", runtime: "predecessor.Artifact",
    worker: "predecessor.Artifact",
) -> release_verifier.ExtractedReleaseContext:
    assert provenance.document is not None and runtime.document is not None
    try:
        context = release_verifier.verify_extracted_release_receipt_v6(
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


def verify_manifest_v5(
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
