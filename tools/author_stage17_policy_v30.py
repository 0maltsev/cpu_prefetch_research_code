#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v30.

Fixes the real, reproduced schema-rejection failure that stopped the
very first real `S17-EXT-002` manifest ever attempted from being
authored at all: `PREFLIGHT_ATTEMPT`/`PREFLIGHT_OBSERVATION_RECEIPT`/
`PREFLIGHT_COMPLETION` were pinned to the frozen `-v7`/`-v5`/`-v5`
record schemas instead of the real executor's current `-v10`/`-v7`/`-v7`
output (ADR-0136): resolution-time `S17-EXT-002` admission now dispatches
through `stage17_operational_semantics_v6.py`'s `verify_manifest_v6` --
the same generation `stage17_operational_cli_v11.py`'s `author-manifest`
itself now uses via `stage17_state_journal_v26.py`. Policy v29 and its
entire bindings/runtime_closure remain byte-identical and independently
valid; this is purely an additive successor. Also picks up `stage17_
operational_cli_v11.py`'s own edited journal import (v25 -> v26) and
`ROLE_SCHEMA_v6` reference at its `author-manifest` call site,
transitively discovered the same way prior promotions picked up its
earlier wiring edits. `S17-EXT-001`'s own admission chain (executor v19,
collector v3, preflight-plan policy v21) is completely unaffected.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v29 as predecessor
import stage17_semantic_verifier_v30 as verifier


ROOTS = (
    "stage17_state_journal_v26",
    "stage17_read_only_preflight_executor_v19",
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
    "docs/decisions/0136-stage17-ext002-preflight-role-schema-versions.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v29.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v30.schema.json",
    "tools/stage17_semantic_verifier_v30.py",
    "tools/stage17_operational_semantics_v6.py",
    "tools/stage17_state_journal_v26.py",
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
            "cpu-prefetch-stage17-operational-evidence-admission-policy/30",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v30",
        "policy_version": "30",
        "predecessor": _BASE.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v29.json",
        ),
        "predecessor_status":
            "SUPERSEDED_ADDS_D136_EXT002_PREFLIGHT_ROLE_SCHEMA_VERSIONS",
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
            print("stage17-policy-v30: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v30: PASS")
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
        print(f"stage17-policy-v30: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
