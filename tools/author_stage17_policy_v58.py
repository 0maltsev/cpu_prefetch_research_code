"""Render the D231 preflight32/operational58 closure; grants no authority."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import author_stage17_policy_v57 as predecessor
import stage17_semantic_verifier_v58 as verifier
import stage17_read_only_preflight_semantic_verifier_v32 as preflight

_BASE = predecessor._BASE
ROOTS = (*predecessor.ROOTS,
    "stage17_operational_cli_v18", "stage17_phase_controller_v25",
    "stage17_q15_session_controller_v20", "stage17_state_journal_v52",
    "stage17_semantic_verifier_v58", "stage17_read_only_preflight_executor_v32",
    "stage17_read_only_preflight_semantic_verifier_v32",
    "stage17_pilot_candidate_artifact_v12", "stage17_operational_semantics_v16",
    "stage17_formal_plan_v1", "stage17_formal_calibration_v1",
    "stage17_q16a_capture_validation_v1", "stage17_formal_service_capture_validation_v1",
    "stage17_q16c_schedule_provenance_v1", "stage17_output_registry_v11",
    "stage17_fixed_action_executor_v10", "stage17_phase_controller_v26",
    "stage17_fixed_action_executor_v11", "stage17_output_registry_v12",
    "stage17_operational_semantics_v17", "stage17_calibration_export_v2",
    "stage17_formal_archive_broker_v1")
SUCCESSOR_BINDINGS = (
    preflight.POLICY_PATH, preflight.POLICY_SCHEMA_PATH, preflight.ADR_0231_PATH,
    verifier.POLICY_SCHEMA.as_posix(), predecessor.verifier.POLICY_PATH.as_posix(),
    "tools/author_stage17_policy_v58.py",
    "config/schemas/stage17-pilot-candidate-external-contract-v10.schema.json",
    "config/schemas/stage17-runtime-release-provenance-v10.schema.json",
    "config/stage17/stage17-fixed-phase-actions-v8.json",
    "config/schemas/stage17-fixed-phase-actions-v8.schema.json",
    "config/schemas/stage17-formal-retention-report-v1.schema.json",
    *("config/schemas/stage17-" + family + "-v6.schema.json" for family in (
        "fixed-action-request", "fixed-action-context", "phase-action-authorization",
        "phase-action-result", "phase-action-attempt", "phase-action-failure", "phase-action-completion")),
    *("config/schemas/stage17-formal-" + kind + "-" + boundary + "-v1.schema.json"
      for kind in ("ring", "service", "scheduled") for boundary in ("plan", "native-input")),
    "tools/check_formal_codegen.py", "tools/formal_codegen_probe.cpp",
    "tools/stage17_archive_encoder_main.cpp",
    "config/schemas/stage17-formal-retention-report-v2.schema.json",
    "config/schemas/stage17-formal-archive-header-v1.schema.json",
    "config/schemas/stage17-formal-archive-encoder-plan-v1.schema.json",
    "config/schemas/stage17-calibration-freeze-v1.schema.json",
    *("config/schemas/stage17-formal-" + kind + "-plan-v2.schema.json"
      for kind in ("ring", "service", "scheduled")),
    *("docs/evidence/stage17/FORMAL-STORAGE-D233-PROPOSAL-20261103-01/" + name
      for name in ("proposal.md", "owner-acceptance.json", "acceptance-inventory.json")))


def render_preflight(root):
    root = root.resolve()
    policy = json.loads((root / preflight.POLICY_V31_PATH).read_bytes())
    policy.update(schema_version="cpu-prefetch-stage17-read-only-preflight-evidence-admission-policy/32",
        policy_id="STAGE17-READ-ONLY-PREFLIGHT-EVIDENCE-ADMISSION-POLICY-v32", policy_version="32")
    policy["predecessor"] = {key: value for key, value in policy["predecessor"].items()
                             if key not in {"policy_v30", "adr_0208"}}
    policy["predecessor"].update(policy_v31=_BASE.binding(root, preflight.POLICY_V31_PATH),
                                adr_0231=_BASE.binding(root, preflight.ADR_0231_PATH))
    policy["implementations"] = {key: _BASE.binding(root, path)
                                for key, path in preflight.IMPLEMENTATION_PATHS.items()}
    policy["operational_implementations"] = {
        key: _BASE.binding(root, value["path"])
        for key, value in policy["operational_implementations"].items()}
    return policy


def render(root):
    root = root.resolve()
    policy = predecessor.render(root)
    policy.update(schema_version="cpu-prefetch-stage17-operational-evidence-admission-policy/58",
        policy_id="STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v58", policy_version="58",
        predecessor=_BASE.binding(root, predecessor.verifier.POLICY_PATH.as_posix()),
        predecessor_status="SUPERSEDED_REBINDS_D231_PERSISTENT_FORMAL",
        runtime_import_roots=list(ROOTS), runtime_closure={
            pathlib.PurePosixPath(path).stem: _BASE.binding(root, path)
            for path in sorted(verifier.discover_python_closure(root, ROOTS))},
        entries=[dict(input_id=key, status="IMPLEMENTED", verifier_id=verifier.VERIFIER_ID,
                      verifier_version=verifier.VERIFIER_VERSION) for key in verifier.INPUT_IDS])
    paths = set(SUCCESSOR_BINDINGS) | set(verifier.FORMAL_DECISIONS) | set(verifier.ACCEPTANCE_BINDINGS)
    # Native implementation and accepted methods must be pinned, including new
    # files absent from the predecessor authoring template.
    for directory in ("include/cpu_prefetch/calibration", "src/calibration",
                      "include/cpu_prefetch/runner", "src/runner", "include/cpu_prefetch/storage", "src/storage"):
        paths.update(p.relative_to(root).as_posix() for p in (root / directory).rglob("*")
                     if p.is_file() and p.suffix in {".hpp", ".cpp"})
    for path in sorted(paths):
        policy["bindings"][path.replace("/", "__").replace(".", "_")] = _BASE.binding(root, path)
    return policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = preflight.POLICY_PATH if args.preflight else verifier.POLICY_PATH
    payload = _BASE.canonical((render_preflight if args.preflight else render)(args.root))
    if args.check:
        if not (args.root / path).is_file() or (args.root / path).read_bytes() != payload:
            print("stage17-policy-v58: FAIL generated bytes differ: " + str(path), file=sys.stderr)
            return 1
        print("stage17-policy-v58: PASS " + str(path))
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
