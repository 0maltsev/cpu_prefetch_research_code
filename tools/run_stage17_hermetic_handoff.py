#!/usr/bin/env python3
"""Run the complete test-only Stage 17 handoff from an extracted bundle.

The command authors every synthetic record in a temporary evidence root via
the production schemas and semantic validators.  It never writes the bundled
checked-in journal and never grants stand or Phase 18 authority.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
import tempfile

import stage17_pilot_candidate_artifact_v3 as pilot_artifact


def _run(command: list[str], *, root: pathlib.Path, timeout: int) -> None:
    completed = subprocess.run(
        command, cwd=root, stdin=subprocess.DEVNULL, check=False,
        timeout=timeout,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"hermetic handoff command failed ({completed.returncode}): "
            + " ".join(command)
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-archive", type=pathlib.Path)
    parser.add_argument("--pilot-sidecar", type=pathlib.Path)
    parser.add_argument("--bundle-directory", type=pathlib.Path)
    parser.add_argument("--bundle-root", type=pathlib.Path,
                        default=pathlib.Path.cwd())
    arguments = parser.parse_args()
    root = arguments.bundle_root.resolve()
    if arguments.bundle_directory is not None:
        if arguments.pilot_archive is not None or arguments.pilot_sidecar is not None:
            parser.error("use either --bundle-directory or archive/sidecar")
        candidates = sorted(arguments.bundle_directory.resolve().glob("*.tar.gz"))
        if len(candidates) != 1:
            parser.error("bundle directory must contain exactly one .tar.gz")
        archive = candidates[0]
        sidecar = archive.with_suffix(archive.suffix + ".sha256")
    else:
        if arguments.pilot_archive is None or arguments.pilot_sidecar is None:
            parser.error("archive and sidecar are both required")
        archive = arguments.pilot_archive.resolve()
        sidecar = arguments.pilot_sidecar.resolve()
    temporary: tempfile.TemporaryDirectory | None = None
    try:
        if not (root / "BUNDLE_MANIFEST.json").is_file():
            temporary = tempfile.TemporaryDirectory(
                prefix="stage17-hermetic-bundle-extract-"
            )
            root = pilot_artifact._safe_extract(
                archive, pathlib.Path(temporary.name)
            )
        worker = root / "release/bin/cpu_prefetch_runner"
        no_result = root / "release/bin/cpu_prefetch_stage17_no_result_worker"
        required = (
            root / "validators/verify_stand_bundle.py",
            root / "tools/check_stage17_fixed_action_production.py",
            worker, no_result, archive, sidecar,
        )
        if any(not item.is_file() or item.is_symlink() for item in required):
            raise RuntimeError(
                "bundle, archive, sidecar, worker, or verifier is absent"
            )
        _run(
            [sys.executable, "-B", "validators/verify_stand_bundle.py",
             "--root", str(root)], root=root, timeout=180,
        )
        _run(
            [sys.executable, "-B",
             "tools/check_stage17_fixed_action_production.py", "--self-test",
             "--worker", str(worker),
             "--no-result-worker", str(no_result),
             "--bundle-archive", str(archive),
             "--bundle-sidecar", str(sidecar)],
            root=root, timeout=1800,
        )
    except (OSError, subprocess.SubprocessError, RuntimeError) as exception:
        print(f"stage17-hermetic-handoff: FAIL: {exception}", file=sys.stderr)
        return 1
    finally:
        if temporary is not None:
            temporary.cleanup()
    print(
        "stage17-hermetic-handoff: PASS workflow=10-resolutions/3-transitions/"
        "pilot/seal/completion evidence_root=TEMPORARY synthetic=true "
        "checked_in_journal=UNCHANGED stand=NOT_ACCESSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
