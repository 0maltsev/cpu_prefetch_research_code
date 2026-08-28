#!/usr/bin/env python3
"""Reproducibly render or verify the Stage 17 production policy v11."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
from typing import Any

import stage17_semantic_verifier_v11 as verifier
import stage17_state_journal as journal


ROOTS = (
    "stage17_state_journal_v9",
    "stage17_phase_controller_v3",
    "stage17_q15_session_controller_v1",
    "stage17_pilot_candidate_artifact_v3",
    "stage17_operational_semantics_v3",
    "stage17_exit_state_machine_v3",
)

BINDING_PATHS = (
    "docs/decisions/0115-stage17-production-pilot-and-handoff-boundary.md",
    "config/stage17/stage17-fixed-phase-actions-v3.json",
    "config/stage17/stage17-operational-evidence-admission-policy-v10.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v11.schema.json",
    "config/schemas/stage17-external-custody-receipt-v2.schema.json",
    "config/schemas/stage17-read-only-preflight-attempt-v7.schema.json",
    "config/schemas/stage17-read-only-preflight-observation-receipt-v5.schema.json",
    "config/schemas/stage17-read-only-preflight-completion-v5.schema.json",
    "config/schemas/stage17-operational-input-manifest-v3.schema.json",
    "config/schemas/stage17-operational-artifact-v3.schema.json",
    "config/schemas/stage17-operational-typed-record-v3.schema.json",
    "config/schemas/stage17-phase-action-authorization-v3.schema.json",
    "config/schemas/stage17-fixed-action-request-v3.schema.json",
    "config/schemas/stage17-fixed-action-context-v3.schema.json",
    "config/schemas/stage17-phase-action-attempt-v3.schema.json",
    "config/schemas/stage17-phase-action-result-v3.schema.json",
    "config/schemas/stage17-phase-action-failure-v3.schema.json",
    "config/schemas/stage17-phase-action-completion-v3.schema.json",
    "config/schemas/stage17-fixed-phase-actions-v3.schema.json",
    "config/schemas/stage17-runtime-release-provenance-v3.schema.json",
    "config/schemas/stage17-pilot-candidate-external-contract-v3.schema.json",
    "config/schemas/stage17-q15-r-output-v3.schema.json",
    "config/schemas/stage17-q15-w-output-v3.schema.json",
    "config/schemas/stage17-q15-session-waiting-v1.schema.json",
    "config/schemas/stage17-q15-session-failure-v1.schema.json",
    "config/schemas/stage17-q16a-output-v3.schema.json",
    "config/schemas/stage17-q16a-trace-v3.schema.json",
    "config/schemas/stage17-run-output-v3.schema.json",
    "config/schemas/stage17-join-audit-v3.schema.json",
    "config/schemas/stage17-page-residency-v3.schema.json",
    "config/schemas/stage17-calibration-hardware-state-v1.schema.json",
    "config/schemas/stage17-pilot-hardware-state-v1.schema.json",
    "config/schemas/stage17-pilot-plan-v3.schema.json",
    "config/schemas/stage17-sealed-pilot-artifact-manifest-v3.schema.json",
    "config/schemas/stage17-completion-v3.schema.json",
    "config/schemas/phase18-trust-enrollment-v3.schema.json",
    "config/schemas/phase18-readiness-v3.schema.json",
    "config/schemas/phase18-authorization-v3.schema.json",
    "config/schemas/runner-admission-v3.schema.json",
    "config/schemas/calibration-freeze-v1.schema.json",
    "config/schemas/phase-integrity-report-v1.schema.json",
    "config/schemas/qualification-evidence-v1.schema.json",
    "config/schemas/hardware-prefetch-qualification-v1.schema.json",
    "protocol/2.0.0-pre.2/handoff/schemas/platform.schema.json",
    "include/cpu_prefetch/runner/stage17_fixed_action.hpp",
    "src/runner/stage17_fixed_action.cpp",
    "tools/runner_main.cpp",
    "tools/stage17_test_worker_main.cpp",
    "tools/stage17_operational_cli.py",
)


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def binding(root: pathlib.Path, relative: str) -> dict[str, Any]:
    path = root / relative
    payload = path.read_bytes()
    return {
        "path": relative,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def render(root: pathlib.Path) -> dict[str, Any]:
    closure = verifier.discover_python_closure(root, ROOTS)
    graph_path = root / "config/stage17/stage17-operational-graph-definition-v1.json"
    catalog_path = root / "config/stage17/stage17-external-input-catalog-v1.json"
    genesis = json.loads(
        (root / "config/stage17/journal/stage17-state-journal-000000.json").read_text()
    )
    predecessor = binding(
        root, "config/stage17/stage17-operational-evidence-admission-policy-v10.json"
    )
    return {
        "schema_version": "cpu-prefetch-stage17-operational-evidence-admission-policy/11",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v11",
        "policy_version": "11",
        "protocol_version": "2.0.0-pre.2",
        "predecessor": predecessor,
        "predecessor_status": "REJECTED_INCOMPLETE_PRODUCTION_BOUNDARY",
        "graph_sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "genesis_record_sha256": genesis["genesis"]["genesis_sha256"],
        "resolution_schema_sha256": journal.version_hashes(root)[
            "resolution_schema_sha256"
        ],
        "bindings": {
            path.replace("/", "__").replace(".", "_"): binding(root, path)
            for path in BINDING_PATHS
        },
        "runtime_import_roots": list(ROOTS),
        "runtime_closure": {
            pathlib.PurePosixPath(path).stem: binding(root, path)
            for path in sorted(closure)
        },
        "entries": [
            {
                "input_id": input_id,
                "status": "IMPLEMENTED",
                "verifier_id": verifier.VERIFIER_ID,
                "verifier_version": verifier.VERIFIER_VERSION,
            }
            for input_id in verifier.INPUT_IDS
        ],
        "admission_contract": {
            "closed_role_schema_registry": True,
            "actual_json_schema_validation": True,
            "exact_artifact_bytes_rehashed": True,
            "clean_release_provenance_required": True,
            "generic_payload_sufficient": False,
            "boolean_only_claim_sufficient": False,
            "self_selected_trust_root": False,
            "fixed_worker_snapshot": True,
            "pinned_schema_bytes": True,
            "streaming_raw_verification": True,
            "typed_result_required": True,
            "synthetic_resolves_checked_in_state": False,
        },
        "checked_in_state": {
            "current_state": "PREPARED",
            "resolutions": 0,
            "transitions": 0,
            "action_ready": False,
            "pilot_ready": False,
            "stand": "NOT_ACCESSED",
        },
        "stage18_authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).parents[1])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    payload = canonical(render(root))
    if arguments.check and arguments.write:
        parser.error("--check and --write are mutually exclusive")
    if arguments.check:
        current = root / verifier.POLICY_PATH
        if not current.is_file() or current.read_bytes() != payload:
            print("stage17-policy-v11: FAIL: generated policy bytes drifted", file=sys.stderr)
            return 1
        print("stage17-policy-v11: PASS")
        return 0
    if arguments.write:
        destination = root / verifier.POLICY_PATH
        temporary = destination.with_name(destination.name + ".tmp")
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o644,
        )
        try:
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, destination)
        directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        print(f"stage17-policy-v11: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
