#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v26.

Fixes the real, reproduced attempt-marker schema rejection when a pinned
input's own `snapshot_mechanism` metadata still reported the frozen `v1`
identity instead of the `v2` identity the attempt schema has required
since `v9` (ADR-0132): resolution-time `S17-EXT-001` admission now
dispatches through `stage17_read_only_preflight_semantic_verifier_v18.py`,
which rebinds `implementations.executor` to `stage17_read_only_preflight_
executor_v16.py` and `implementations.openssh_snapshot_broker` to
`stage17_openssh_parent_snapshot_v4.py` -- the same generation `stage17_
operational_cli_v11.py` itself now uses via `stage17_state_journal_v22.py`.
Policy v25 and its entire bindings/runtime_closure remain byte-identical
and independently valid; this is purely an additive successor. Also picks
up `stage17_operational_cli_v11.py`'s own edited journal import (v21 ->
v22) and `author-ext001` policy path (v17.json -> v18.json), transitively
discovered the same way prior promotions picked up its earlier wiring
edits.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v25 as predecessor
import stage17_semantic_verifier_v26 as verifier


ROOTS = (
    "stage17_state_journal_v22",
    "stage17_read_only_preflight_executor_v16",
    "stage17_process_group_supervisor_v3",
    "stage17_openssh_parent_snapshot_v4",
    "stage17_phase_controller_v9",
    "stage17_q15_session_controller_v6",
    "stage17_operational_cli_v11",
    "stage17_pilot_candidate_artifact_v6",
    "stage17_operational_semantics_v5",
    "stage17_exit_state_machine_v4",
)

SUCCESSOR_BINDINGS = (
    "docs/decisions/0132-stage17-openssh-snapshot-mechanism-identity.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v25.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v26.schema.json",
    "tools/stage17_semantic_verifier_v26.py",
    "tools/stage17_read_only_preflight_executor_v16.py",
    "tools/stage17_openssh_parent_snapshot_v4.py",
    "tools/stage17_read_only_preflight_semantic_verifier_v18.py",
    "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v18.schema.json",
    "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v18.json",
    "tools/stage17_state_journal_v22.py",
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
            "cpu-prefetch-stage17-operational-evidence-admission-policy/26",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v26",
        "policy_version": "26",
        "predecessor": _BASE.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v25.json",
        ),
        "predecessor_status":
            "SUPERSEDED_ADDS_D132_OPENSSH_SNAPSHOT_MECHANISM_IDENTITY",
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
            print("stage17-policy-v26: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v26: PASS")
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
        print(f"stage17-policy-v26: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
