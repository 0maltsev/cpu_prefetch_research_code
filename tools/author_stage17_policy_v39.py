#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v39.

Fixes the real Q15 session `execute_session` wiring bug ADR-0145 left
in place (ADR-0146): two real Q15-R sessions on the real stand, both
after ADR-0145's bundle was staged, hit the exact same failure-
retention schema rejection ADR-0145 was meant to fix, because `stage17_
q15_session_controller_v11.py` only bound a new `execute_session`
attribute in its own file -- `run_start` (defined in `v2.py`) calls
`execute_session(...)` as a bare name, resolved against `v2.py`'s own
module globals, not against any later generation's own binding.
`stage17_q15_session_controller_v12.py` fixes this by patching `v2.py`'s
own `execute_session` global directly.

Since `create_stand_bundle.py` only copies files this policy's own
bindings/runtime_closure list, and no prior policy generation has ever
tracked `v12.py`, this generation also pins it directly, applying the
ADR-0143 lesson proactively rather than discovering the gap on the next
real Q15-R attempt.

`ROOTS` is a literal, updated tuple (not `predecessor.ROOTS`) because
moving to a new outer policy generation requires `cli_v11.py`'s own
`journal_runtime` to move too (to reach this generation's own semantic
verifier), which has, every time so far (ADR-0130/0137/0139/0141/0144/
0145), immediately stranded the read-only-preflight executor family's
own hardcoded journal import -- so this ADR folds that lockstep move
directly in, rather than leaving it for a separate follow-up ADR. The
`stage17_phase_controller_v9`/`stage17_q15_session_controller_v6` root
entries themselves stay unchanged, matching every prior literal-`ROOTS`
ADR -- the new dynamic-action entrypoint is pinned explicitly via
`SUCCESSOR_BINDINGS` instead.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v38 as predecessor
import stage17_semantic_verifier_v39 as verifier


ROOTS = (
    "stage17_state_journal_v35",
    "stage17_read_only_preflight_executor_v25",
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
    "docs/decisions/0146-stage17-q15-session-execute-session-wiring-fix.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v38.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v39.schema.json",
    "tools/stage17_semantic_verifier_v39.py",
    "tools/stage17_read_only_preflight_executor_v25.py",
    "tools/stage17_read_only_preflight_semantic_verifier_v27.py",
    "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v27.schema.json",
    "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v27.json",
    "tools/stage17_state_journal_v35.py",
    "tools/stage17_phase_controller_v14.py",
    "tools/stage17_q15_session_controller_v12.py",
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
            "cpu-prefetch-stage17-operational-evidence-admission-policy/39",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v39",
        "policy_version": "39",
        "predecessor": _BASE.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v38.json",
        ),
        "predecessor_status":
            "SUPERSEDED_ADDS_D146_Q15_SESSION_EXECUTE_SESSION_WIRING_FIX",
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
            print("stage17-policy-v39: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v39: PASS")
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
        print(f"stage17-policy-v39: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
