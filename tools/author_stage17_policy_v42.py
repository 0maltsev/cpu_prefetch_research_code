#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v42 (ADR-0156).

Adds `tools/stage17_fixed_action_executor_v5.py` and `tools/stage17_
phase_controller_v15.py` to the pinned bindings and (transitively, via
`stage17_operational_cli_v11.py`'s own import moving there) the runtime
closure. Nothing about `S17-EXT-004`/`S17-EXT-006` manifest semantics
changes -- `verifier` (`stage17_semantic_verifier_v42`) delegates every
check but the policy-shape/required-file ones unchanged to `v41`. `ROOTS`
is a literal, updated tuple (not `predecessor.ROOTS`) for the same reason
every prior literal-`ROOTS` ADR in this chain gives: moving to a new
outer policy generation requires `stage17_state_journal_v36.py`'s own
`semantic` import to move too (`stage17_semantic_verifier_v42` now, not
`_v41`), and `stage17_operational_cli_v11.py`'s own `controller`/
`journal_runtime` imports move to `_v15`/`_v36` in place (matching this
file's own 27-commit history of in-place edits, each re-pinned by a new
policy generation -- unlike `stage17_fixed_action_executor_v4.py`/
`stage17_phase_controller_v14.py`, which stay byte-for-byte frozen and
gain fresh `_v5.py`/`_v15.py` successors instead, because a free
variable resolves against the module that *defines* it, not the module
that imports it, so editing them in place would silently change what
already-admitted resolutions' pinned hashes are supposed to guarantee).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v41 as predecessor
import stage17_semantic_verifier_v42 as verifier


ROOTS = (
    "stage17_state_journal_v36",
    "stage17_read_only_preflight_executor_v25",
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
    "docs/decisions/0156-stage17-fixed-action-kernel-thread-tolerance.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v41.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v42.schema.json",
    "tools/stage17_semantic_verifier_v42.py",
    "tools/stage17_state_journal_v36.py",
    "tools/stage17_phase_controller_v15.py",
    "tools/stage17_fixed_action_executor_v5.py",
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
            "cpu-prefetch-stage17-operational-evidence-admission-policy/42",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v42",
        "policy_version": "42",
        "predecessor": _BASE.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v41.json",
        ),
        "predecessor_status":
            "SUPERSEDED_ADDS_D156_FIXED_ACTION_KERNEL_THREAD_TOLERANCE_FIX",
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
            print("stage17-policy-v42: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v42: PASS")
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
        print(f"stage17-policy-v42: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
