#!/usr/bin/env python3
"""Stage 17 operational-evidence successor dropping S17-EXT-004's
QUALIFICATION_EVIDENCE requirement for evidence nothing in this codebase
can honestly measure (ADR-0154).

`tools/stage17_operational_semantics_v4.py`'s `ROLE_SCHEMA` (never
retargeted for this role by any successor through `v7`) pins
`QUALIFICATION_EVIDENCE` to `config/schemas/qualification-evidence-v1.
schema.json`, whose `clock_details` requires `traced_call_count`/
`traced_syscall_count`/`before_block_repeat`. `tools/q15_qualification_
evidence_tool_main.cpp` (the only real tool that produces this envelope)
has always refused to default or invent those three fields, by design --
its own top comment says so -- because no VDSO call/syscall tracer or
post-measurement block-repeat timestamp capture exists anywhere in this
codebase to produce them for real. That refusal worked exactly as
intended: every real `S17-EXT-004` admission this engagement ever made
(`standv2-5` through `standv2-14`) was produced by hand-typing plausible
values past the tool's CLI flags instead, since the schema left no other
way to satisfy it. `SelectedPairClockInput` and the tool's CLI no longer
carry those three fields at all (ADR-0154's own C++ change); `config/
schemas/qualification-evidence-v2.schema.json` is the matching schema
successor, with `clock_details` dropping them from both `required` and
`properties`. Eligibility for `SELECTED_PAIR_CLOCK` now depends only on
the prime/delta counts, window counts, and per-core/cross-core evaluator
results -- all real, honestly measurable facts.

`ROLE_SCHEMA_v8` is `v6`'s own table with only `QUALIFICATION_EVIDENCE`
retargeted. `_read_artifacts_v8` is a fresh copy of `_read_artifacts_v6`
(confirmed by exact extraction, not manual retyping), broadened only to
resolve roles through `ROLE_SCHEMA_v8` instead of `v6`'s frozen table --
the same free-variable-resolves-via-defining-module reason `v6`'s own
`_read_artifacts_v6` needed a fresh copy over `v5`'s. `verify_manifest_v8`
is a fresh copy of the complete `verify_manifest_v7` body (confirmed by
exact extraction), changed only to call `_read_artifacts_v8`; every
branch for `S17-EXT-002` through `S17-EXT-010` is otherwise byte-
identical, since only artifact reading itself depends on the retargeted
table. `_validate_preflight_v7` is reused unmodified via re-export -- an
alias, not a fresh copy, since its body reads no free variable this fix
changes.

This does not affect `S17-EXT-005`'s own already-real `standv2-14`
admission directly, but that admission's own `predecessor_resolutions`
chain depended on an `S17-EXT-004` resolution admitted under the old,
now-recognized-as-unsatisfiable schema -- see ADR-0154 for the full
history and why a fresh journal is required to admit a real, honest
`S17-EXT-004` for the first time.
"""

from __future__ import annotations

import collections
import json
import pathlib
import stat
from typing import Any, Mapping

import stage17_operational_semantics_v7 as predecessor


Artifact = predecessor.Artifact
EXPECTED_ROLES = predecessor.EXPECTED_ROLES
LOGICAL_ENVELOPE_ROLES = predecessor.LOGICAL_ENVELOPE_ROLES
MANIFEST_SCHEMA = predecessor.MANIFEST_SCHEMA
MEASUREMENT_KEYS = predecessor.MEASUREMENT_KEYS
OperationalSemanticError = predecessor.OperationalSemanticError
SIGNATURE_ROLES = predecessor.SIGNATURE_ROLES
STREAMING_OBSERVATION_ROLES = predecessor.STREAMING_OBSERVATION_ROLES
TYPED_SCHEMA = predecessor.TYPED_SCHEMA
_artifact_content = predecessor._artifact_content
_artifact_index = predecessor._artifact_index
_one = predecessor._one
_phase_family = predecessor._phase_family
_resolution_bindings = predecessor._resolution_bindings
_schema = predecessor._schema
_validate = predecessor._validate
_validate_preflight_v7 = predecessor._validate_preflight_v7
load = predecessor.load
output_registry = predecessor.output_registry
pilot_plan_runtime = predecessor.pilot_plan_runtime
sha = predecessor.sha
verify_sshsig = predecessor.verify_sshsig
_verify_extracted_release_v5 = predecessor._verify_extracted_release_v5

ROLE_SCHEMA_v8: dict[str, str | None] = {
    **predecessor.ROLE_SCHEMA_v6,
    "QUALIFICATION_EVIDENCE": "config/schemas/qualification-evidence-v2.schema.json",
}


def _read_artifacts_v8(root: pathlib.Path, manifest_path: pathlib.Path,
                       manifest: dict[str, Any],
                       pinned: Mapping[str, bytes]) -> list[Artifact]:
    """Faithful copy of predecessor `_read_artifacts_v6`, broadened only to
    resolve roles through this module's own `ROLE_SCHEMA_v8` instead of
    `v6`'s frozen table. Every other check is byte-identical to the
    predecessor.
    """
    result: list[Artifact] = []
    ids: set[str] = set()
    paths: set[pathlib.Path] = set()
    for reference in manifest["artifacts"]:
        role = reference["role"]
        if role not in ROLE_SCHEMA_v8:
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
        expected_schema = ROLE_SCHEMA_v8[role]
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


def verify_manifest_v8(
    *, repository_root: pathlib.Path, manifest_path: pathlib.Path,
    admitted_resolutions: Mapping[str, Any], expected_input_id: str,
    allow_synthetic: bool, pinned_repository_bytes: Mapping[str, bytes],
) -> dict[str, Any]:
    """Faithful copy of predecessor `verify_manifest_v7`'s complete body,
    changed only to call `_read_artifacts_v8` instead of `_read_artifacts_
    v6`. Every branch for S17-EXT-002 through S17-EXT-010 is otherwise
    byte-identical, since only artifact reading itself depends on the
    retargeted table.
    """
    root = repository_root.resolve()
    manifest, payload = load(manifest_path)
    _validate(root, manifest, MANIFEST_SCHEMA, "operational manifest v4",
              pinned_repository_bytes)
    if (manifest["input_id"] != expected_input_id
            or expected_input_id not in EXPECTED_ROLES
            or manifest["synthetic_test_only"] is not allow_synthetic):
        raise OperationalSemanticError("manifest input/classification drifted")
    artifacts = _read_artifacts_v8(root, manifest_path, manifest,
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
