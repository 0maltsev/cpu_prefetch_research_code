#!/usr/bin/env python3
"""Fail-closed integrity and schema checks for every protocol snapshot."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import sys
from pathlib import Path

PROTOCOL_VERSIONS = ("2.0.0-pre.1", "2.0.0-pre.2")
CURRENT_PROTOCOL_VERSION = "2.0.0-pre.2"


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

    total_artifacts = 0
    total_schemas = 0
    total_authoritative = 0
    for protocol_version in PROTOCOL_VERSIONS:
        snapshot = root / "protocol" / protocol_version
        manifest_path = snapshot / "IMPORT_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        if manifest.get("protocol_version") != protocol_version:
            fail(f"{protocol_version}: manifest version differs from its snapshot")
        if manifest.get("verification_result") != "PASS":
            fail(f"{protocol_version}: manifest is not verified PASS")
        if protocol_version == CURRENT_PROTOCOL_VERSION:
            authorization = manifest.get("authorization", {})
            if authorization.get("decision_id") != "D-031" or authorization.get(
                "approval_ids"
            ) != ["Q10", "Q11"]:
                fail("current snapshot lacks the exact D-031 Q10/Q11 authorization")

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
            fail(
                f"{protocol_version}: snapshot inventory mismatch; "
                f"missing={missing}, extra={extra}"
            )

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
        current_section = text.split(
            "## Current authoritative hashes", maxsplit=1
        )[1]
        for declared_name, path in authoritative.items():
            match = re.search(
                rf"\| `{re.escape(declared_name)}` \| `([0-9a-f]{{64}})` \|",
                current_section,
            )
            if match is None:
                fail(
                    f"{protocol_version}: current authoritative hash is not "
                    f"declared for {declared_name}"
                )
            if sha256(path) != match.group(1):
                fail(
                    f"{protocol_version}: current authoritative hash mismatch "
                    f"for {declared_name}"
                )

        schemas = sorted(
            (snapshot / "handoff" / "schemas").glob("*.schema.json")
        )
        if len(schemas) != 7:
            fail(
                f"{protocol_version}: expected seven imported schemas, "
                f"found {len(schemas)}"
            )
        for schema_path in schemas:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                fail(f"{schema_path.name} does not declare Draft 2020-12")
            if f"/{protocol_version}/" not in schema.get("$id", ""):
                fail(f"{schema_path.name} has the wrong protocol-version schema ID")
            Draft202012Validator.check_schema(schema)
        total_artifacts += len(declared_paths)
        total_schemas += len(schemas)
        total_authoritative += len(authoritative)

    implementation_schemas = sorted(
        (root / "config" / "schemas").glob("*.schema.json")
    )
    for schema_path in implementation_schemas:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            fail(f"{schema_path.name} does not declare Draft 2020-12")
        Draft202012Validator.check_schema(schema)

    print(
        f"protocol-check: PASS ({len(PROTOCOL_VERSIONS)} snapshots, "
        f"{total_artifacts} artifacts, {total_authoritative} authoritative hashes, "
        f"{total_schemas} imported and "
        f"{len(implementation_schemas)} implementation Draft 2020-12 schemas)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"protocol-check: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
