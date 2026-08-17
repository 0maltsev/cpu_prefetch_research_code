#!/usr/bin/env python3
"""Reject host-specific or unsafe numeric flags from release compile commands."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

FORBIDDEN = {"-march=native", "-mtune=native", "-Ofast", "-ffast-math"}


def main() -> int:
    database_path = Path(sys.argv[1])
    commands = json.loads(database_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    for entry in commands:
        arguments = entry.get("arguments")
        if arguments is None:
            arguments = shlex.split(entry["command"])
        present = sorted(FORBIDDEN.intersection(arguments))
        if present:
            failures.append(f"{entry['file']}: {', '.join(present)}")
    if failures:
        for failure in failures:
            print(f"release-policy-check: forbidden flags: {failure}", file=sys.stderr)
        return 1
    print(f"release-policy-check: PASS ({len(commands)} compile commands)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
