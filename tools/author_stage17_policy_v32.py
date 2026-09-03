#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v32.

Completes the S17-EXT-002 manifest schema-binding ADR-0136 left
incomplete (ADR-0138): pins the three real preflight record schemas
(`stage17-read-only-preflight-attempt-v10.schema.json`,
`-observation-receipt-v7.schema.json`, `-completion-v7.schema.json`)
`stage17_operational_semantics_v6.ROLE_SCHEMA_v6` has required since
ADR-0136, but which policy v30/v31's own `bindings` never pinned. Policy
v31 and its entire bindings/runtime_closure remain byte-identical and
independently valid; this is purely an additive successor with no
Python-code changes at all.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v31 as predecessor
import stage17_semantic_verifier_v32 as verifier


ROOTS = predecessor.ROOTS

SUCCESSOR_BINDINGS = (
    "docs/decisions/0138-stage17-ext002-manifest-schema-binding-completion.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v31.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v32.schema.json",
    "tools/stage17_semantic_verifier_v32.py",
    "config/schemas/stage17-read-only-preflight-attempt-v10.schema.json",
    "config/schemas/stage17-read-only-preflight-observation-receipt-v7.schema.json",
    "config/schemas/stage17-read-only-preflight-completion-v7.schema.json",
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
            "cpu-prefetch-stage17-operational-evidence-admission-policy/32",
        "policy_id": "STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v32",
        "policy_version": "32",
        "predecessor": _BASE.binding(
            root,
            "config/stage17/stage17-operational-evidence-admission-policy-v31.json",
        ),
        "predecessor_status":
            "SUPERSEDED_ADDS_D138_EXT002_MANIFEST_SCHEMA_BINDING_COMPLETION",
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
            print("stage17-policy-v32: FAIL: generated policy bytes drifted",
                  file=sys.stderr)
            return 1
        print("stage17-policy-v32: PASS")
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
        print(f"stage17-policy-v32: PASS written={destination}")
        return 0
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
