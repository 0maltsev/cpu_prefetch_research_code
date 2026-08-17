#!/usr/bin/env python3
"""Run clang-tidy with the exact compile database used by the build."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clang-tidy", required=True)
    parser.add_argument("--build-directory", required=True)
    parser.add_argument("files", nargs="+")
    arguments = parser.parse_args()

    build_directory = Path(arguments.build_directory)
    if not (build_directory / "compile_commands.json").is_file():
        print("static-analysis: compile_commands.json is missing", file=sys.stderr)
        return 1

    command = [
        arguments.clang_tidy,
        "-p",
        str(build_directory),
        "--warnings-as-errors=*",
        *arguments.files,
    ]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
