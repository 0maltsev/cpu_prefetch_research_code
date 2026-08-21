#!/usr/bin/env python3
"""Fail-closed integrity and schema checks for the imported protocol snapshot."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import sys
from pathlib import Path

PROTOCOL_VERSION = "2.0.0-pre.1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    snapshot = root / "protocol" / PROTOCOL_VERSION
    manifest_path = snapshot / "IMPORT_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("protocol_version") != PROTOCOL_VERSION:
        fail("manifest protocol version differs from the checked snapshot")

    declared_paths: set[Path] = set()
    for artifact in manifest.get("artifacts", []):
        relative = Path(artifact["imported_relative_path"])
        path = root / relative
        declared_paths.add(relative)
        if not path.is_file():
            fail(f"missing imported artifact: {relative}")
        actual_size = path.stat().st_size
        if actual_size != artifact["file_size_bytes"]:
            fail(
                f"size mismatch for {relative}: {actual_size} != "
                f"{artifact['file_size_bytes']}"
            )
        actual_hash = sha256(path)
        if actual_hash != artifact["sha256"]:
            fail(f"SHA-256 mismatch for {relative}: {actual_hash}")

    actual_paths = {
        path.relative_to(root)
        for path in snapshot.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual_paths != declared_paths:
        missing = sorted(map(str, declared_paths - actual_paths))
        extra = sorted(map(str, actual_paths - declared_paths))
        fail(f"snapshot inventory mismatch; missing={missing}, extra={extra}")

    version_record = snapshot / "handoff" / "PROTOCOL_VERSION.md"
    text = version_record.read_text(encoding="utf-8")
    authoritative = {
        "paper/main.pdf": snapshot / "main.pdf",
        "EXPERIMENT_IMPLEMENTATION_SPEC.md": snapshot
        / "EXPERIMENT_IMPLEMENTATION_SPEC.md",
        "PROTOCOL_FREEZE_CHECKLIST.md": snapshot
        / "PROTOCOL_FREEZE_CHECKLIST.md",
        "AGENTS.md": snapshot / "PAPER_AGENTS.md",
    }
    current_section = text.split("## Current authoritative hashes", maxsplit=1)[1]
    for declared_name, path in authoritative.items():
        match = re.search(
            rf"\| `{re.escape(declared_name)}` \| `([0-9a-f]{{64}})` \|",
            current_section,
        )
        if match is None:
            fail(f"current authoritative hash is not declared for {declared_name}")
        if sha256(path) != match.group(1):
            fail(f"current authoritative hash mismatch for {declared_name}")

    try:
        from jsonschema import Draft202012Validator
    except ImportError as error:
        fail(f"jsonschema 4.26.x is required: {error}")

    required_python_packages = {
        "jsonschema": "4.26.0",
        "attrs": "26.1.0",
        "rpds-py": "2026.5.1",
        "referencing": "0.37.0",
        "jsonschema-specifications": "2025.9.1",
    }
    for package, expected_version in required_python_packages.items():
        actual_version = importlib.metadata.version(package)
        if actual_version != expected_version:
            fail(f"{package} {expected_version} required; found {actual_version}")

    schemas = sorted((snapshot / "handoff" / "schemas").glob("*.schema.json"))
    if len(schemas) != 7:
        fail(f"expected seven imported schemas, found {len(schemas)}")
    for schema_path in schemas:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            fail(f"{schema_path.name} does not declare Draft 2020-12")
        Draft202012Validator.check_schema(schema)

    implementation_schemas = sorted(
        (root / "config" / "schemas").glob("*.schema.json")
    )
    for schema_path in implementation_schemas:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            fail(f"{schema_path.name} does not declare Draft 2020-12")
        Draft202012Validator.check_schema(schema)

    print(
        f"protocol-check: PASS ({len(declared_paths)} artifacts, "
        f"4 authoritative hashes, {len(schemas)} imported and "
        f"{len(implementation_schemas)} implementation Draft 2020-12 schemas)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"protocol-check: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
