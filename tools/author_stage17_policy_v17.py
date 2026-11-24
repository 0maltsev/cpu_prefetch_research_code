#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v17."""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v16 as predecessor
import stage17_semantic_verifier_v17 as verifier


ROOTS = (
    "stage17_state_journal_v15",
    "stage17_read_only_preflight_executor_v11",
    "stage17_phase_controller_v7",
    "stage17_q15_session_controller_v5",
    "stage17_operational_cli_v9",
    "stage17_pilot_candidate_artifact_v4",
    "stage17_operational_semantics_v4",
    "stage17_exit_state_machine_v4",
)

SUCCESSOR_BINDINGS = (
    "docs/decisions/0122-stage17-preflight-terminal-compatibility.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v16.json",
    "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v13.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v17.schema.json",
    "config/schemas/stage17-preflight-post-marker-blocker-v1.schema.json",
    "tools/stage17_openssh_parent_snapshot_v2.py",
    "tools/stage17_semantic_verifier_v17.py",
    "tools/stage17_state_journal_v15.py",
    "tools/stage17_phase_controller_v7.py",
    "tools/stage17_q15_session_controller_v5.py",
    "tools/stage17_operational_cli_v9.py",
    "tools/author_stage17_post_marker_blocker_v1.py",
)


def render(root: pathlib.Path) -> dict[str, object]:
    policy = predecessor.render(root)
    policy.update({
        "schema_version":
            "cpu-prefetch-stage17-operational-evidence-admission-policy/17",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v17",
        "policy_version": "17",
        "predecessor": predecessor.predecessor.predecessor.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v16.json",
        ),
        "predecessor_status":
            "SUPERSEDED_POST_MARKER_TERMINAL_CONTRACT_INCOMPATIBLE",
        "runtime_import_roots": list(ROOTS),
        "runtime_closure": {
            pathlib.PurePosixPath(path).stem:
                predecessor.predecessor.predecessor.binding(root, path)
            for path in sorted(verifier.discover_python_closure(root, ROOTS))
        },
        "entries": [{"input_id": input_id, "status": "IMPLEMENTED",
                     "verifier_id": verifier.VERIFIER_ID,
                     "verifier_version": verifier.VERIFIER_VERSION}
                    for input_id in verifier.INPUT_IDS],
    })
    bindings = dict(policy["bindings"])
    for path in SUCCESSOR_BINDINGS:
        bindings[path.replace("/", "__").replace(".", "_")] = \
            predecessor.predecessor.predecessor.binding(root, path)
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
    payload = predecessor.predecessor.predecessor.canonical(render(root))
    destination = root / verifier.POLICY_PATH
    if arguments.check:
        if not destination.is_file() or destination.read_bytes() != payload:
            print("stage17-policy-v17: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v17: PASS")
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
        print(f"stage17-policy-v17: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
