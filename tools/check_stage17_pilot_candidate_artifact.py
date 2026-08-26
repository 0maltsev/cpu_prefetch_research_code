#!/usr/bin/env python3
"""Verify caller-supplied pilot-candidate archive and sidecar bytes."""

from __future__ import annotations

import argparse
import pathlib
import sys

from stage17_pilot_candidate_artifact import (
    ArtifactError,
    VERIFIER_ID,
    VERIFIER_VERSION,
    verify_pilot_candidate_artifact,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    ROOT / "config/stage17/stage17-pilot-candidate-external-contract-v1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=pathlib.Path, required=True)
    parser.add_argument("--sidecar", type=pathlib.Path, required=True)
    parser.add_argument("--contract", type=pathlib.Path, default=DEFAULT_CONTRACT)
    arguments = parser.parse_args()
    try:
        result = verify_pilot_candidate_artifact(
            repository_root=ROOT,
            contract_path=arguments.contract,
            archive=arguments.archive,
            sidecar=arguments.sidecar,
        )
    except (ArtifactError, OSError) as exception:
        print(f"stage17-pilot-candidate-artifact-check: FAIL: {exception}", file=sys.stderr)
        return 1
    print(
        "stage17-pilot-candidate-artifact-check: PASS "
        f"verifier={VERIFIER_ID}/{VERIFIER_VERSION} "
        f"archive_sha256={result.artifact_sha256} files={result.file_count} authority=NONE"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
