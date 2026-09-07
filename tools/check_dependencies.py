#!/usr/bin/env python3
"""Validate the tracked Stage 3 dependency and license inventory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = {
    "id",
    "version_rule",
    "observed_version",
    "source",
    "license",
    "purpose",
    "scope",
}


def main() -> int:
    inventory_path = Path(sys.argv[1])
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if inventory.get("schema_version") != "cpu-prefetch-dependencies/1":
        raise ValueError("unsupported dependency inventory schema")
    if inventory.get("repository_license") != "NO-LICENSE-GRANT":
        raise ValueError("repository license posture does not match ADR-0021")

    dependencies = inventory.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies:
        raise ValueError("dependencies must be a non-empty list")
    identifiers: set[str] = set()
    for dependency in dependencies:
        missing = REQUIRED - dependency.keys()
        if missing:
            raise ValueError(f"dependency record missing {sorted(missing)}: {dependency}")
        identifier = dependency["id"]
        if identifier in identifiers:
            raise ValueError(f"duplicate dependency id: {identifier}")
        identifiers.add(identifier)
        if not dependency["license"] or not dependency["source"].startswith("https://"):
            raise ValueError(f"invalid source/license for {identifier}")

    print(f"dependency-check: PASS ({len(dependencies)} recorded dependencies)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, IndexError, json.JSONDecodeError) as error:
        print(f"dependency-check: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
