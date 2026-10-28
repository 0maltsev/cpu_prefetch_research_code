#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v53 (ADR-0175:
a second, PRFCHW-free software-prefetch mapping).

Re-pins `src/runner/stage17_fixed_action.cpp`'s changed bytes (the new
per-run software-prefetch mapping resolution/dispatch `package_capture`
now performs, and the mapping-id fix to `publish_q15_r`'s own
`Q15_R_SOFTWARE_PREFETCH_RAW` artifact) and adds `stage17_operational_
semantics_v11` to `ROOTS`, so its own bytes (and `qualification-
evidence-v3.schema.json`/`stage17-q15-r-software-prefetch-raw-v2.
schema.json`, reachable only through its own `verify_manifest_v11`
re-validating artifacts against them) are discovered and pinned into
this generation's runtime closure, matching the exact pattern `v8`
itself was added to `ROOTS` by an earlier generation.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v52 as predecessor
import stage17_semantic_verifier_v53 as verifier


ROOTS = tuple(predecessor.ROOTS) + ("stage17_operational_semantics_v11",)

SUCCESSOR_BINDINGS = (
    "docs/decisions/0175-stage17-cpu-prefetch-v5-software-prefetch-mapping-t0-only.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v52.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v53.schema.json",
    "src/runner/stage17_fixed_action.cpp",
    "tools/stage17_semantic_verifier_v53.py",
    "config/schemas/qualification-evidence-v3.schema.json",
    "config/schemas/stage17-q15-r-software-prefetch-raw-v2.schema.json",
    "config/schemas/stage17-fixed-phase-actions-v5.schema.json",
    "config/stage17/stage17-fixed-phase-actions-v5.json",
    "tools/stage17_output_registry_v7.py",
    "tools/stage17_state_journal_v47.py",
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
            "cpu-prefetch-stage17-operational-evidence-admission-policy/53",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v53",
        "policy_version": "53",
        "predecessor": _BASE.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v52.json",
        ),
        "predecessor_status":
            "SUPERSEDED_ADDS_D175_SOFTWARE_PREFETCH_T0_ONLY_MAPPING",
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
            print("stage17-policy-v53: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v53: PASS")
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
        print(f"stage17-policy-v53: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
