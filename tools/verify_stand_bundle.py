#!/usr/bin/env python3
"""Verify a cleanly extracted Stage 16 stand bundle without mutating the host."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    checksum_path = root / "SHA256SUMS"
    manifest_path = root / "BUNDLE_MANIFEST.json"
    failures: list[str] = []
    declared: set[pathlib.Path] = set()

    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected, relative_text = line.split("  ", maxsplit=1)
        relative = pathlib.Path(relative_text)
        declared.add(relative)
        path = root / relative
        if not path.is_file():
            failures.append(f"missing declared file: {relative}")
        elif sha256(path) != expected:
            failures.append(f"SHA-256 mismatch: {relative}")

    actual = {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and path != checksum_path
    }
    if actual != declared:
        failures.append(
            "inventory mismatch: missing="
            f"{sorted(map(str, declared - actual))} extra={sorted(map(str, actual - declared))}"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "cpu-prefetch-stand-bundle/1":
        failures.append("unknown bundle schema")
    if manifest.get("protocol_version") != "2.0.0-pre.2":
        failures.append("wrong protocol version")
    if manifest.get("readiness_state") != "READY_FOR_STAND_PREFLIGHT":
        failures.append("bundle is not scoped to stand preflight")
    if manifest.get("pilot_authorized") is not False:
        failures.append("bundle must explicitly prohibit pilot execution")
    if manifest.get("confirmatory_authorized") is not False:
        failures.append("bundle must explicitly prohibit confirmatory execution")

    example = json.loads(
        (root / "config" / "examples" / "stage16-stand-inputs.example.json").read_text(
            encoding="utf-8"
        )
    )
    if example.get("authoritative") is not False or any(
        value is not None for value in example["required_external_inputs"].values()
    ):
        failures.append("nonauthoritative example embeds a frozen-looking value")

    if failures:
        for failure in failures:
            print(f"stand-bundle-check: FAIL: {failure}", file=sys.stderr)
        return 1
    print(
        "stand-bundle-check: PASS "
        f"({len(declared)} files, protocol 2.0.0-pre.2, pilot prohibited)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
