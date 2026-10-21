#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v52 (ADR-0173's
implementation note 4).

Re-pins `src/runner/stage17_fixed_action.cpp`'s changed hash after the fix
to `LinuxHardwarePrefetchMsrBackend`'s CPU whitelist, which now binds per
instance to the caller's own resolved mapping instead of a single hardcoded
06_55H-only constant. `ROOTS` is unchanged from `v51`'s own -- this change
touches no importable Python entry point at all, only the same single
already-tracked C++ source file's bytes (plus q15_msr.hpp/q15_msr.cpp,
which are outside this Python runtime closure).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v51 as predecessor
import stage17_semantic_verifier_v52 as verifier


ROOTS = predecessor.ROOTS

SUCCESSOR_BINDINGS = (
    "docs/decisions/0173-stage17-cpu-prefetch-v5-pair-identity.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v51.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v52.schema.json",
    "src/runner/stage17_fixed_action.cpp",
    "tools/stage17_semantic_verifier_v52.py",
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
            "cpu-prefetch-stage17-operational-evidence-admission-policy/52",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v52",
        "policy_version": "52",
        "predecessor": _BASE.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v51.json",
        ),
        "predecessor_status":
            "SUPERSEDED_ADDS_D173_Q15_MSR_WHITELIST_FIX",
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
            print("stage17-policy-v52: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v52: PASS")
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
        print(f"stage17-policy-v52: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
