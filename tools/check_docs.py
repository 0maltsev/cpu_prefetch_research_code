#!/usr/bin/env python3
"""Check repository-local Markdown links without network access."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    checked = 0

    markdown_files = sorted(
        path
        for path in root.rglob("*.md")
        if ".git" not in path.parts and "build" not in path.parts
    )
    for document in markdown_files:
        text = document.read_text(encoding="utf-8")
        for match in LINK.finditer(text):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", maxsplit=1)[0]
            if not target:
                continue
            checked += 1
            resolved = (document.parent / unquote(target)).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                failures.append(f"{document.relative_to(root)}: link escapes repository: {target}")
                continue
            if not resolved.exists():
                failures.append(f"{document.relative_to(root)}: missing target: {target}")

    if failures:
        for failure in failures:
            print(f"document-check: {failure}", file=sys.stderr)
        return 1
    print(f"document-check: PASS ({len(markdown_files)} files, {checked} local links)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
