#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v38.

Fixes a real Q15 session failure-retention schema defect (ADR-0145):
`stage17_q15_session_controller_v2.py`'s own `execute_session` built a
failure record's `failure_stage` by string-concatenating
`":SUPERVISOR_FALLBACK"` onto the enum value whenever process-group
cleanup itself also failed while handling a primary session failure --
but `stage17-q15-session-failure-v1.schema.json`'s own enum never
accepted any suffixed variant, so exactly the failure records that
fallback path exists to retain were always rejected. `stage17_q15_
session_controller_v10.py` fixes this with a clean enum plus a new,
independent `cleanup_error_occurred: bool` field
(`stage17-q15-session-failure-v2.schema.json`).

Since `create_stand_bundle.py` only copies files this policy's own
bindings/runtime_closure list, and no prior policy generation has ever
tracked the dynamic-action entrypoints beyond `stage17_phase_controller_
v12.py`/`stage17_q15_session_controller_v9.py` (ADR-0144), this
generation also pins the new entrypoints (`v13`/`v10`/`v11`) and the new
schema directly, applying the ADR-0143 lesson proactively rather than
discovering the gap on the next real Q15-R attempt.

`ROOTS` is a literal, updated tuple (not `predecessor.ROOTS`) because
moving to a new outer policy generation requires `cli_v11.py`'s own
`journal_runtime` to move too (to reach this generation's own semantic
verifier), which has, every time so far (ADR-0130/0137/0139/0141/0144),
immediately stranded the read-only-preflight executor family's own
hardcoded journal import -- so this ADR folds that lockstep move
directly in, rather than leaving it for a separate follow-up ADR the
way ADR-0143/ADR-0144 did. The `stage17_phase_controller_v9`/`stage17_
q15_session_controller_v6` root entries themselves stay unchanged,
matching every prior literal-`ROOTS` ADR -- the new dynamic-action
entrypoints are pinned explicitly via `SUCCESSOR_BINDINGS` instead.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v37 as predecessor
import stage17_semantic_verifier_v38 as verifier


ROOTS = (
    "stage17_state_journal_v34",
    "stage17_read_only_preflight_executor_v24",
    "stage17_process_group_supervisor_v3",
    "stage17_openssh_parent_snapshot_v5",
    "stage17_phase_controller_v9",
    "stage17_q15_session_controller_v6",
    "stage17_operational_cli_v11",
    "stage17_pilot_candidate_artifact_v6",
    "stage17_operational_semantics_v6",
    "stage17_exit_state_machine_v4",
)

SUCCESSOR_BINDINGS = (
    "docs/decisions/0145-stage17-q15-session-failure-retention-schema-fix.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v37.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v38.schema.json",
    "config/schemas/stage17-q15-session-failure-v2.schema.json",
    "tools/stage17_semantic_verifier_v38.py",
    "tools/stage17_read_only_preflight_executor_v24.py",
    "tools/stage17_read_only_preflight_semantic_verifier_v26.py",
    "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v26.schema.json",
    "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v26.json",
    "tools/stage17_state_journal_v34.py",
    "tools/stage17_phase_controller_v13.py",
    "tools/stage17_q15_session_controller_v10.py",
    "tools/stage17_q15_session_controller_v11.py",
)

def _find_base(module: object) -> object:
    """Walk the additive `predecessor` chain to the module defining
    `canonical`/`binding`, rather than hardcoding a hop count that shifts
    by one every time this authoring-script chain itself grows by one
    additive successor."""
    while not hasattr(module, "canonical"):
        module = module.predecessor
    return module


_BASE = _find_base(predecessor)


def render(root: pathlib.Path) -> dict[str, object]:
    policy = predecessor.render(root)
    policy.update({
        "schema_version":
            "cpu-prefetch-stage17-operational-evidence-admission-policy/38",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v38",
        "policy_version": "38",
        "predecessor": _BASE.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v37.json",
        ),
        "predecessor_status":
            "SUPERSEDED_ADDS_D145_Q15_SESSION_FAILURE_RETENTION_SCHEMA_FIX",
        "runtime_import_roots": list(ROOTS),
        "runtime_closure": {
            pathlib.PurePosixPath(path).stem: _BASE.binding(root, path)
            for path in sorted(verifier.discover_python_closure(root, ROOTS))
        },
        "entries": [
            {"input_id": input_id, "status": "IMPLEMENTED",
             "verifier_id": verifier.VERIFIER_ID,
             "verifier_version": verifier.VERIFIER_VERSION}
            for input_id in verifier.INPUT_IDS
        ],
    })
    bindings = dict(policy["bindings"])
    for path in SUCCESSOR_BINDINGS:
        bindings[path.replace("/", "__").replace(".", "_")] = _BASE.binding(root, path)
    policy["bindings"] = bindings
    return policy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path,
                        default=pathlib.Path(__file__).parents[1])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    if arguments.check and arguments.write:
        parser.error("--check and --write are mutually exclusive")
    root = arguments.root.resolve()
    canonical = _BASE.canonical
    payload = canonical(render(root))
    destination = root / verifier.POLICY_PATH
    if arguments.check:
        if not destination.is_file() or destination.read_bytes() != payload:
            print("stage17-policy-v38: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v38: PASS")
        return 0
    if arguments.write:
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
        print(f"stage17-policy-v38: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
