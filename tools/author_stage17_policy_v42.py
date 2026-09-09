#!/usr/bin/env python3
"""Reproducibly render or verify Stage 17 production policy v42.

Retargets `S17-EXT-006` to `tools/stage17_semantic_verifier_v42.py`'s own
`verify_s17_ext_006`, which reads the real `artifact_locator` receipt
field instead of the stale `contract_path` no real v2-schema receipt
ever carries (ADR-0155).

`ROOTS` is `v41`'s own tuple unchanged: this fix does not move any
orchestration-layer import binding (`stage17_state_journal_v35.py`'s own
`semantic` import moves to `_v42` via the same `journal_runtime`-style
in-place edit every prior generation used, but that alone does not
require adding a new root -- `stage17_semantic_verifier_v42` is
discovered transitively through `stage17_state_journal_v35` the same way
`_v41` already was).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

import author_stage17_policy_v41 as predecessor
import stage17_semantic_verifier_v42 as verifier


ROOTS = predecessor.ROOTS

SUCCESSOR_BINDINGS = (
    "docs/decisions/0155-stage17-ext006-receipt-field-fix.md",
    "config/stage17/stage17-operational-evidence-admission-policy-v41.json",
    "config/schemas/stage17-operational-evidence-admission-policy-v42.schema.json",
    "tools/stage17_semantic_verifier_v42.py",
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
            "SUPERSEDED_ADDS_D155_EXT006_RECEIPT_FIELD_FIX",
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
