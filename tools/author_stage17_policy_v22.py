#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v22.

Adds real `S17-EXT-006` bundle-profile recognition (ADR-0128, `PROPOSED`/
owner-review pending): `stage17_pilot_candidate_artifact_v5.py`'s
broadened profile whitelist, wired through a new `S17-EXT-006` dispatch
override in `stage17_semantic_verifier_v22.py`, so a real `S17-EXT-006`
transaction can admit a `STAGE17-PILOT-CANDIDATE-BUNDLE-v5`/`v6` archive.
Policy v21 and its entire bindings/runtime_closure remain byte-identical
and independently valid; this is purely an additive successor.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v21 as predecessor
import stage17_semantic_verifier_v22 as verifier


ROOTS = (
    "stage17_state_journal_v18",
    "stage17_read_only_preflight_executor_v13",
    "stage17_phase_controller_v9",
    "stage17_q15_session_controller_v6",
    "stage17_operational_cli_v11",
    "stage17_pilot_candidate_artifact_v5",
    "stage17_operational_semantics_v4",
    "stage17_exit_state_machine_v4",
)

SUCCESSOR_BINDINGS = (
    "docs/decisions/0128-stage17-pilot-candidate-artifact-profile-recognition.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v21.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v22.schema.json",
    "tools/stage17_semantic_verifier_v22.py",
    "tools/stage17_pilot_candidate_artifact_v5.py",
    "tools/stage17_state_journal_v18.py",
)

_BASE = (
    predecessor.predecessor.predecessor.predecessor.predecessor
    .predecessor.predecessor.predecessor
)


def render(root: pathlib.Path) -> dict[str, object]:
    policy = predecessor.render(root)
    policy.update({
        "schema_version":
            "cpu-prefetch-stage17-operational-evidence-admission-policy/22",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v22",
        "policy_version": "22",
        "predecessor": _BASE.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v21.json",
        ),
        "predecessor_status":
            "SUPERSEDED_ADDS_D128_PILOT_CANDIDATE_PROFILE_RECOGNITION",
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
            print("stage17-policy-v22: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v22: PASS")
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
        print(f"stage17-policy-v22: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
