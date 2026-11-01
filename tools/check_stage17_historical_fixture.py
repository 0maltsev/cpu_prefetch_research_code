#!/usr/bin/env python3
"""Run frozen policy-18 regression checks in their complete source context.

This checks historical compatibility only. Current operational qualification
must independently validate a current policy against the current source root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
REVISION = "05035cec1d1c1c88a08e9012996e5a6e4ccfd2a5"
CHECKERS = {
    "successor": "check_stage17_operational_successor.py",
    "journal": "check_stage17_state_journal.py",
    "preflight": "check_stage17_external_journal_preflight.py",
    "preflight-v2": "check_stage17_external_journal_preflight_v2.py",
}
PRESERVATION = "config/stage17/d099-d108-preservation-manifest-v1.json"
TEMPLATES = (
    "docs/decisions/0104-stage17-pilot-operational-governance-successor.md",
    "config/stage17/stage17-operational-authorization-successor-v1.json",
    "config/stage17/stage17-external-input-checklist-v1.json",
    PRESERVATION,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regular(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise ValueError(f"unsafe historical input path: {relative}")
    path = root
    for part in pure.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f"symlink in historical input path: {relative}")
    if not path.is_file():
        raise ValueError(f"historical input is not a regular file: {relative}")
    return path


def verify_preserved_inputs(current: Path, snapshot: Path) -> None:
    # Running an old snapshot must not conceal drift in preserved current bytes.
    for relative in TEMPLATES:
        if digest(regular(current, relative)) != digest(regular(snapshot, relative)):
            raise ValueError(f"preserved template drift: {relative}")
    manifest = json.loads(regular(snapshot, PRESERVATION).read_text())
    for binding in manifest["tracked_artifacts"]:
        if digest(regular(current, binding["path"])) != binding["sha256"]:
            raise ValueError(f"preserved artifact drift: {binding['path']}")


def materialize(destination: Path) -> None:
    # Git validates object identities. No network, checkout, or index mutation.
    with tempfile.TemporaryFile() as archive:
        subprocess.run(
            ["git", "-C", str(ROOT), "archive", "--format=tar", REVISION],
            check=True, stdout=archive, stdin=subprocess.DEVNULL, timeout=60,
        )
        archive.seek(0)
        with tarfile.open(fileobj=archive, mode="r:") as source:
            for member in source.getmembers():
                pure = PurePosixPath(member.name)
                if (pure.is_absolute() or not pure.parts or ".." in pure.parts
                        or not (member.isfile() or member.isdir())):
                    raise ValueError(f"unsafe historical source member: {member.name}")
            source.extractall(destination, filter="data")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checker", choices=CHECKERS)
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix="stage17-policy18-") as temporary:
            snapshot = Path(temporary) / "source"
            materialize(snapshot)
            verify_preserved_inputs(ROOT, snapshot)
            git_dir = subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", "--absolute-git-dir"],
                check=True, text=True, stdout=subprocess.PIPE, timeout=10,
            ).stdout.strip()
            environment = dict(os.environ)
            # The old preservation test reads an exact historical Git object.
            # It does not use the current worktree as its source/schema root.
            environment["GIT_DIR"] = git_dir
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            completed = subprocess.run(
                [sys.executable, "-B", str(snapshot / "tools" / CHECKERS[args.checker]),
                 "--self-test"],
                cwd=snapshot, env=environment, stdin=subprocess.DEVNULL,
                check=True, timeout=240, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
    except (OSError, ValueError, KeyError, tarfile.TarError,
            subprocess.SubprocessError) as error:
        print(f"stage17-historical-fixture: FAIL: {error}", file=sys.stderr)
        return 1
    # CTest's PASS_REGULAR_EXPRESSION can override an ordinary nonzero exit.
    # Publish no child success text until replay and temporary cleanup succeed.
    print(completed.stdout, end="")
    print(completed.stderr, end="", file=sys.stderr)
    print(f"stage17-historical-fixture: PASS revision={REVISION} "
          "preserved_current_inputs=VERIFIED current_policy_qualified=false authority=NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
