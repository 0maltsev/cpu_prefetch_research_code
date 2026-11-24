"""Diagnostic author/verify/execute/retention entry points; never signs.

Legacy CLI commands delegate unchanged to v14. Diagnostic calls require the
same admitted journal/trust/release plus exact bounded signed authority.
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import os
import sys
import types
import stage17_pilot_candidate_artifact_v9 as release
import stage17_operational_semantics_v13 as operational

import stage17_operational_cli_v14 as predecessor
import stage17_operational_cli_v11 as base
import stage17_phase_controller_v22 as controller
import stage17_output_registry_v9 as registry


# Prospective CLI dispatch follows the existing versioned-entrypoint convention.
# The old executables/files retain their original dispatch when invoked alone.
base.controller = controller
base.journal_runtime = controller.journal_runtime
base.semantics_v6 = types.SimpleNamespace(ROLE_SCHEMA_v6=operational.ROLE_SCHEMA_v13)
base.pilot_artifact = types.SimpleNamespace(
    VERIFIER_ID=release.VERIFIER_ID, VERIFIER_VERSION=release.VERIFIER_VERSION,
    build_contract_v4=release.build_contract_v9)


def _validation(repository_root, evidence_root, pilot_archive=None, pilot_sidecar=None, synthetic=False):
    return controller.journal_runtime.validate_operational_journal(
        repository_root=repository_root, evidence_root=evidence_root,
        latest_journal=base.latest_journal(evidence_root), journal_directory=evidence_root / "journal",
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        as_of_utc=controller.support._now(), allow_synthetic_test_evidence=synthetic)


def author_request(*, repository_root, evidence_root, action_inputs_path, request_id,
                   authorization_id, attempt_id, session_id, output_root, destination,
                   pilot_archive=None, pilot_sidecar=None, synthetic=False):
    validation = _validation(repository_root, evidence_root, pilot_archive, pilot_sidecar, synthetic)
    pinned = registry.pin_registry(repository_root)
    definition = pinned.action(registry.ACTION)
    if validation.current_state != definition["required_state"]:
        raise controller.ControllerError("diagnostic state gate is not satisfied")
    runtime, release, _ = controller.runtime_from_context(validation)
    inputs, _ = base.load_json(action_inputs_path)
    document = {"schema_version": "cpu-prefetch-stage17-fixed-action-request/5",
        "request_id": request_id, "session_id": session_id, "action_id": registry.ACTION,
        "stand_id": validation.resolutions["S17-EXT-002"].semantic_context["stand_id"],
        "authorization_id": authorization_id, "attempt_id": attempt_id,
        "runtime_binding": runtime, "release_binding": release,
        "evidence_root_binding": base._root_binding(output_root),
        "predecessor_resolutions": [base._resolution_binding(validation.resolutions[key])
                                   for key in definition["required_resolution_ids"]],
        "action_inputs": inputs, "synthetic_test_only": synthetic, "phase18_authority": False}
    registry.validate_document(pinned, document, registry.schema_path("fixed-action-request"), "diagnostic request")
    controller.validate_action_inputs(document, validation)
    base.write_external_exclusive(destination, registry.canonical(document))
    return destination


def author_authorization(*, repository_root, evidence_root, request_path, actor, reviewer,
                         issued_at_utc, expires_at_utc, destination, pilot_archive=None,
                         pilot_sidecar=None, synthetic=False):
    validation = _validation(repository_root, evidence_root, pilot_archive, pilot_sidecar, synthetic)
    request, payload = base.load_json(request_path)
    pinned = registry.pin_registry(repository_root)
    registry.validate_document(pinned, request, registry.schema_path("fixed-action-request"), "diagnostic request")
    if payload != registry.canonical(request):
        raise controller.ControllerError("request bytes are not canonical")
    plan = controller.validate_action_inputs(request, validation)
    definition = pinned.action(registry.ACTION)
    expected = [base._resolution_binding(validation.resolutions[key]) for key in definition["required_resolution_ids"]]
    runtime, release, _ = controller.runtime_from_context(validation)
    if (validation.current_state != definition["required_state"]
            or request["predecessor_resolutions"] != expected
            or request["runtime_binding"] != runtime or request["release_binding"] != release
            or request["synthetic_test_only"] is not synthetic):
        raise controller.ControllerError("request admission drifted before authoring")
    trust = validation.resolutions["S17-EXT-003"].semantic_context["trust"]
    if actor != trust["measurements"]["principal"] or reviewer != trust["measurements"]["reviewer_role"]:
        raise controller.ControllerError("actor/reviewer differ from admitted trust")
    policy = controller.deadline_policy(plan)
    issued, expires = base.parse_utc(issued_at_utc), base.parse_utc(expires_at_utc)
    if not issued < expires or expires - issued > dt.timedelta(seconds=policy["session_max_wall_seconds"]):
        raise controller.ControllerError("diagnostic authority window exceeds finite session")
    document = {"schema_version": "cpu-prefetch-stage17-phase-action-authorization/5",
        "authorization_id": request["authorization_id"], "session_id": request["session_id"],
        "action_id": registry.ACTION, "actor": actor, "reviewer": reviewer,
        "target": {"stand_id": request["stand_id"]}, "issued_at_utc": issued_at_utc,
        "expires_at_utc": expires_at_utc, "trust_context": {
            "ext002_resolution": expected[1], "ext003_resolution": expected[2]},
        "predecessor_resolutions": expected, "fixed_action_definition_sha256": pinned.plan_sha256,
        "request_binding": {"path": str(request_path), "size_bytes": len(payload), "sha256": registry.sha256(payload)},
        "evidence_root_binding": request["evidence_root_binding"], "permission_matrix": definition["permission_matrix"],
        "deadline_policy": policy, "one_attempt": True, "retry_allowed": False,
        "stop_first": True, "retain_partial": True, "stage18_authority": False}
    registry.validate_document(pinned, document, registry.schema_path("phase-action-authorization"), "diagnostic authorization")
    base.write_external_exclusive(destination, registry.canonical(document))
    return destination


def admit_retention(prepared, output_root: pathlib.Path):
    """Verify completed custody only; no EXT007 resolution or selection credit."""
    directory_fd = os.open(output_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        if base._root_binding(output_root) != prepared.request["evidence_root_binding"]:
            raise controller.ControllerError("retention root differs from signed request")
        token = registry.ACTION.lower().replace("-", "_")
        def load(name):
            fd, metadata = registry.base._open_output(directory_fd, name)
            os.close(fd)
            return registry.base._json_output(directory_fd, name, metadata.st_size)
        attempt = load(f"stage17-{token}-attempt-v5.json")
        completion = load(f"stage17-{token}-completion-v5.json")
        result = load(registry.RESULT_NAME)
        for family, doc in (("phase-action-attempt", attempt), ("phase-action-completion", completion)):
            registry.validate_document(prepared.registry, doc, registry.schema_path(family), family)
            if (doc["attempt_id"] != prepared.request["attempt_id"]
                    or doc["authorization_sha256"] != registry.sha256(prepared.authorization_bytes)
                    or doc["request_sha256"] != registry.sha256(prepared.request_bytes)
                    or doc["runtime_sha256"] != prepared.runtime["sha256"]):
                raise controller.ControllerError("retention controller lineage differs")
        registry._stream(directory_fd, completion["result"], prepared.request["action_inputs"]["plan"]["budget"]["output_budget_bytes"])
        if completion["result"]["file_name"] != registry.RESULT_NAME:
            raise controller.ControllerError("completion names a different result")
        from stage17_fixed_action_executor_v8 import diagnostic_prestate
        expected_readback = [{"cpu": cpu, "expected_hex": f"{value:016x}",
                              "observed_hex": f"{value:016x}", "matches": True}
                             for cpu, value in diagnostic_prestate(prepared.request)]
        if completion["live_restoration_readback"] != expected_readback:
            raise controller.ControllerError("retention live restoration differs from sealed prestate")
        if (attempt["release_resolution_id"] != prepared.release["source_resolution_id"]
                or attempt["release_resolution_sha256"] != prepared.release["source_resolution_sha256"]
                or attempt["evidence_root_binding"] != prepared.request["evidence_root_binding"]):
            raise controller.ControllerError("retention attempt release/root differs")
        expected = [{key: item[key] for key in ("file_name", "size_bytes", "sha256")} for item in result["artifacts"]]
        if (completion["artifact_bindings"] != expected or not completion["restoration_verified"]
                or completion["quarantined"] or not completion["live_restoration_readback"]):
            raise controller.ControllerError("retention completion artifacts/restoration differ")
        return registry.validate_worker_result(registry=prepared.registry, directory_fd=directory_fd,
            result=result, request=prepared.request, authorization_sha256=registry.sha256(prepared.authorization_bytes),
            synthetic_test_only=prepared.request["synthetic_test_only"])
    finally:
        os.close(directory_fd)


def main():
    commands = {"author-discovery-request", "author-discovery-authorization",
                "verify-discovery-signature", "execute-discovery", "admit-discovery-retention"}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        return predecessor.main()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(commands))
    for name in ("repository-root", "evidence-root"):
        parser.add_argument("--" + name, type=pathlib.Path, required=True)
    for name in ("pilot-archive", "pilot-sidecar", "action-inputs", "output-root", "output", "request", "authorization", "signature"):
        parser.add_argument("--" + name, type=pathlib.Path)
    for name in ("request-id", "authorization-id", "attempt-id", "session-id", "actor", "reviewer", "issued-at-utc", "expires-at-utc"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    def need(*names):
        for name in names:
            if getattr(args, name) is None:
                parser.error("required: --" + name.replace("_", "-"))
    common = dict(repository_root=args.repository_root.resolve(), evidence_root=args.evidence_root.resolve(),
                  pilot_archive=args.pilot_archive, pilot_sidecar=args.pilot_sidecar)
    if args.command == "author-discovery-request":
        need("action_inputs", "request_id", "authorization_id", "attempt_id", "session_id", "output_root", "output")
        author_request(**common, action_inputs_path=args.action_inputs, request_id=args.request_id,
            authorization_id=args.authorization_id, attempt_id=args.attempt_id, session_id=args.session_id,
            output_root=args.output_root, destination=args.output)
    elif args.command == "author-discovery-authorization":
        need("request", "actor", "reviewer", "issued_at_utc", "expires_at_utc", "output")
        author_authorization(**common, request_path=args.request, actor=args.actor, reviewer=args.reviewer,
            issued_at_utc=args.issued_at_utc, expires_at_utc=args.expires_at_utc, destination=args.output)
    else:
        need("authorization", "signature")
        common.pop("evidence_root")
        common.update(journal=base.latest_journal(args.evidence_root), journal_directory=args.evidence_root / "journal",
                      operational_evidence_root=args.evidence_root, authorization_path=args.authorization, signature_path=args.signature)
        if args.command == "execute-discovery":
            controller.execute_once(**common)
        else:
            prepared = controller.prepare_action(**common)
            if args.command == "admit-discovery-retention":
                need("output_root")
                admit_retention(prepared, args.output_root)
    print("stage17-discovery: PASS; no formal calibration credit or new authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
