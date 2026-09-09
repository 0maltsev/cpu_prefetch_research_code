#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v43 (ADR-0157).

Moves the `stage17_read_only_preflight_executor` root from `_v25` to
`_v26` (ADR-0156's own fix, which `v42`'s own `ROOTS` never actually
reached, because `cli_v11.py` never imports the preflight executor
directly -- the shell-invoked entry point is a separate root for exactly
this reason). Adds the new preflight-plan-policy chain (`_v28.py`
semantic verifier, its `...policy-v28.json`/`.schema.json`, and this
ADR's own doc) to `SUCCESSOR_BINDINGS`. `v42.json` stays byte-for-byte
frozen: it was used, however briefly, by standv2-21's own admitted
`S17-EXT-001`. `ROOTS` also moves `stage17_state_journal_v36` to `_v37`
(this file's own `journal_runtime` successor, importing `stage17_
semantic_verifier_v43`), mirroring exactly the `v41`->`v42` cascade
pattern this same chain already used for ADR-0156.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v42 as predecessor
import stage17_semantic_verifier_v43 as verifier


ROOTS = (
    "stage17_state_journal_v37",
    "stage17_read_only_preflight_executor_v26",
    "stage17_process_group_supervisor_v3",
    "stage17_openssh_parent_snapshot_v5",
    "stage17_phase_controller_v15",
    "stage17_q15_session_controller_v6",
    "stage17_operational_cli_v11",
    "stage17_pilot_candidate_artifact_v6",
    "stage17_pilot_candidate_artifact_v7",
    "stage17_operational_semantics_v6",
    "stage17_operational_semantics_v7",
    "stage17_operational_semantics_v8",
    "stage17_exit_state_machine_v4",
)

SUCCESSOR_BINDINGS = (
    "docs/decisions/0157-stage17-preflight-plan-policy-kernel-thread-tolerance-follow-up.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v42.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v43.schema.json",
    "tools/stage17_semantic_verifier_v43.py",
    "tools/stage17_state_journal_v37.py",
    "tools/stage17_read_only_preflight_semantic_verifier_v28.py",
    "tools/author_stage17_read_only_preflight_policy_v28.py",
    "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v28.schema.json",
    "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v28.json",
    "tools/stage17_read_only_preflight_executor_v26.py",
    "tools/stage17_operational_cli_v11.py",
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
            "cpu-prefetch-stage17-operational-evidence-admission-policy/43",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v43",
        "policy_version": "43",
        "predecessor": _BASE.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v42.json",
        ),
        "predecessor_status":
            "SUPERSEDED_ADDS_D157_PREFLIGHT_PLAN_POLICY_FOLLOW_UP_FIX",
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
            print("stage17-policy-v43: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v43: PASS")
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
        print(f"stage17-policy-v43: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
