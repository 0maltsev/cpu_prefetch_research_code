#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v36.

Completes the phase-controller/Q15-session-controller entrypoint bindings
ADR-0142 left untracked (ADR-0143): pins `tools/stage17_phase_controller_
v11.py`, `tools/stage17_q15_session_controller_v7.py`, and `tools/
stage17_q15_session_controller_v8.py` as explicit policy bindings, so a
sealed bundle actually carries them into a materialized admission root.
Policy v35 and its entire bindings/runtime_closure remain byte-identical
and independently valid; this is purely an additive successor. Also
picks up `stage17_operational_cli_v11.py`'s own edited journal import
(v31 -> v32), transitively discovered the same way prior promotions
picked up its earlier wiring edits. `S17-EXT-001`'s own admission chain
(executor v22, journal v31->v32 lockstep only, preflight-plan policy v24)
is completely unaffected in logic.

`ROOTS` is `predecessor.ROOTS` (unchanged) because this ADR does not move
the read-only-preflight executor/journal generation itself -- it only
adds explicit bindings for files that are not, and were never, reachable
via the real Python import graph `discover_python_closure` walks. Unlike
ADR-0137/0139/0141, a literal updated `ROOTS` tuple is not needed here.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v35 as predecessor
import stage17_semantic_verifier_v36 as verifier


ROOTS = predecessor.ROOTS

SUCCESSOR_BINDINGS = (
    "docs/decisions/0143-stage17-phase-controller-entrypoint-bindings-completion.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v35.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v36.schema.json",
    "tools/stage17_semantic_verifier_v36.py",
    "tools/stage17_phase_controller_v11.py",
    "tools/stage17_q15_session_controller_v7.py",
    "tools/stage17_q15_session_controller_v8.py",
    "tools/stage17_state_journal_v32.py",
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
            "cpu-prefetch-stage17-operational-evidence-admission-policy/36",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v36",
        "policy_version": "36",
        "predecessor": _BASE.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v35.json",
        ),
        "predecessor_status":
            "SUPERSEDED_ADDS_D143_PHASE_CONTROLLER_ENTRYPOINT_BINDINGS_COMPLETION",
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
            print("stage17-policy-v36: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v36: PASS")
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
        print(f"stage17-policy-v36: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
