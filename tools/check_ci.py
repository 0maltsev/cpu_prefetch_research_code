#!/usr/bin/env python3
"""Check that CI uses pinned actions and documented local entry points."""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHECKOUT = "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"
REQUIRED_COMMANDS = (
    "cmake --preset dev-gcc",
    "cmake --build --preset dev-gcc",
    "ctest --preset dev-gcc",
    "cmake --build --preset dev-gcc --target schema-fixture-check",
    "cmake --build --preset dev-gcc --target canonical-check",
    "cmake --preset dev-clang-libcxx",
    "cmake --build --preset release-gcc --target package",
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    readme = (root / "README.md").read_text(encoding="utf-8")

    action_uses = re.findall(r"^\s*uses:\s*(\S+)", workflow, flags=re.MULTILINE)
    if not action_uses or any(action != CHECKOUT for action in action_uses):
        raise ValueError(f"every CI action must be the pinned checkout commit: {action_uses}")
    for command in REQUIRED_COMMANDS:
        if command not in workflow:
            raise ValueError(f"CI is missing command: {command}")
        if command not in readme:
            raise ValueError(f"README is missing CI command: {command}")
    if "FetchContent" in workflow or "apt-get" in workflow or "pacman" in workflow:
        raise ValueError("CI must use pre-provisioned dependencies")

    print(f"ci-check: PASS ({len(action_uses)} pinned action uses)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"ci-check: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
