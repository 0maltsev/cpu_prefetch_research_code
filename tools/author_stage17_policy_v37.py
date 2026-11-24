#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v37.

Completes the executor journal-reachability lockstep ADR-0143 missed
(ADR-0144): resolution-time `S17-EXT-001` admission now dispatches
through `stage17_read_only_preflight_semantic_verifier_v25.py`, which
rebinds `implementations.executor` to `stage17_read_only_preflight_
executor_v23.py` (whose only change is its own journal import moving
too) -- the same generation `stage17_operational_cli_v11.py` itself now
uses via `stage17_state_journal_v32.py`. Policy v36 and its entire
bindings/runtime_closure remain byte-identical and independently valid;
this is purely an additive successor. Also picks up `stage17_operational_
cli_v11.py`'s own edited journal import (v32 stays; see below) and
`author-ext001` policy path (v24.json -> v25.json), and its own edited
`controller` import (`stage17_phase_controller_v11` -> `v12`), fixing the
same reachability gap ADR-0142 fixed once already for the phase-
controller family, now recurring because this ADR's own journal move
would otherwise strand `phase_controller_v11.py`'s hardcoded `v31`
journal import a second time. `S17-EXT-002`'s own admission chain
(ADR-0136/ADR-0138/ADR-0140) is completely unaffected.

`ROOTS` is a literal, updated tuple (not `predecessor.ROOTS`) because
this ADR moves the executor/journal generation, exactly as `v31.py`
(ADR-0137), `v33.py` (ADR-0139), and `v35.py` (ADR-0141) themselves
needed literal, updated `ROOTS` tuples rather than an inherited one --
`discover_python_closure` walks real Python `import` statements from
these roots, and `IMPLEMENTATION_PATHS`' string references alone (in the
preflight-plan policy) are not themselves import edges. The `stage17_
phase_controller_v9`/`stage17_q15_session_controller_v6` root entries
themselves stay unchanged, matching every prior literal-`ROOTS` ADR --
`stage17_phase_controller_v12.py` and `stage17_q15_session_controller_
v9.py` are pinned explicitly via `SUCCESSOR_BINDINGS` instead (ADR-0143's
own fix for this exact reachability class, applied proactively here so
this ADR does not reopen the gap it just closed).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v36 as predecessor
import stage17_semantic_verifier_v37 as verifier


ROOTS = (
    "stage17_state_journal_v32",
    "stage17_read_only_preflight_executor_v23",
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
    "docs/decisions/0144-stage17-executor-and-phase-controller-journal-reachability-followup-4.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v36.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v37.schema.json",
    "tools/stage17_semantic_verifier_v37.py",
    "tools/stage17_read_only_preflight_executor_v23.py",
    "tools/stage17_read_only_preflight_semantic_verifier_v25.py",
    "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v25.schema.json",
    "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v25.json",
    "tools/stage17_state_journal_v32.py",
    "tools/stage17_phase_controller_v12.py",
    "tools/stage17_q15_session_controller_v9.py",
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
            "cpu-prefetch-stage17-operational-evidence-admission-policy/37",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v37",
        "policy_version": "37",
        "predecessor": _BASE.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v36.json",
        ),
        "predecessor_status":
            "SUPERSEDED_ADDS_D144_EXECUTOR_AND_PHASE_CONTROLLER_JOURNAL_REACHABILITY_FOLLOWUP_4",
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
            print("stage17-policy-v37: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v37: PASS")
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
        print(f"stage17-policy-v37: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
