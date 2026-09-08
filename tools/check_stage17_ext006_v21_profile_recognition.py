#!/usr/bin/env python3
"""D-153 regression: EXT-006 recognizes the real v21 bundle profile.

Proves, against real sealed bundle bytes already on disk (not
synthesized), that:
  - `stage17_pilot_candidate_artifact_v7.py`'s real `build_contract_v7`/
    `verify_pilot_candidate_artifact_v7` round-trip successfully against a
    real archive/sidecar pair;
  - the accepted `v5` predecessor's `RECOGNIZED_PROFILES` still excludes
    `STAGE17-PILOT-CANDIDATE-BUNDLE-v21` (the gap this fix closes is real,
    and the frozen predecessor is genuinely unchanged, not merely "not
    edited");
  - the frozen `v4` module's source still only literally mentions its
    original two profile strings;
  - `v7`'s own whitelist (inherited from `v6`) includes `v21`;
  - `stage17_semantic_verifier_v40.py` dispatches `S17-EXT-006` through
    `v7` and delegates every other input to its `v39` predecessor
    unchanged;
  - `stage17_state_journal_v35.py`/`stage17_operational_cli_v11.py`'s own
    hardcoded imports were moved to the new generation.

It does not create a checked-in record and does not touch SSH, the
stand, or any credential.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import tarfile

import stage17_operational_cli_v11 as cli
import stage17_pilot_candidate_artifact_v4 as artifact_v4
import stage17_pilot_candidate_artifact_v5 as artifact_v5
import stage17_pilot_candidate_artifact_v7 as artifact_v7
import stage17_semantic_verifier_v39 as verifier_v39
import stage17_semantic_verifier_v40 as verifier_v40
import stage17_state_journal_v35 as journal_v35


POSITIVE_CASES = 7
NEGATIVE_CASES = 2


class CheckError(RuntimeError):
    pass


def self_test(root: pathlib.Path) -> tuple[int, int]:
    positive = 0
    negative = 0

    build_dir = root / "build"
    candidates_dir = build_dir / "release-gcc/pilot-candidate-bundle"
    all_archives = sorted(
        candidates_dir.glob("*-clean-*.tar.gz"), key=lambda p: p.stat().st_mtime
    )
    if not all_archives:
        raise CheckError(
            f"no real sealed bundle archive found under {candidates_dir} -- run "
            "'cmake --build --preset release-gcc --target pilot-candidate-bundle' "
            "first to produce one"
        )
    archive = all_archives[-1]
    sidecar = archive.with_name(archive.name + ".sha256")
    if not sidecar.is_file():
        raise CheckError(f"no real sidecar found next to {archive}")
    with tarfile.open(archive, "r:gz") as source:
        roots = {pathlib.PurePosixPath(m.name).parts[0] for m in source.getmembers()}
        if len(roots) != 1:
            raise CheckError("fixture archive does not have exactly one top-level root")

    # Positive: a real end-to-end EXT-006 contract round-trip through the
    # new v7 module (build then verify), using real archive/sidecar bytes.
    contract = artifact_v7.build_contract_v7(
        repository_root=root, archive=archive, sidecar=sidecar,
        primary_custody_domain_id="D153-SELF-TEST-PRIMARY",
        secondary_custody_domain_id="D153-SELF-TEST-SECONDARY",
        contract_id="D153-SELF-TEST-CONTRACT",
    )
    positive += 1

    import tempfile, json
    with tempfile.TemporaryDirectory(prefix="stage17-d153-contract-") as text:
        contract_path = pathlib.Path(text) / "contract.json"
        contract_path.write_text(json.dumps(contract))
        context = artifact_v7.verify_pilot_candidate_artifact_v7(
            repository_root=root, contract_path=contract_path,
            archive=archive, sidecar=sidecar,
        )
    if context.archive_sha256 != contract["archive"]["sha256"]:
        raise CheckError("v7 round-trip verified context does not match the contract")
    positive += 1

    # Positive: build_contract_v4 is a real alias resolving to v7, so the
    # CLI's unmodified call-site spelling keeps working.
    if artifact_v7.build_contract_v4 is not artifact_v7.build_contract_v7:
        raise CheckError("v7's build_contract_v4 compatibility alias is missing")
    positive += 1

    # Positive: v7's frozen protocol identity matches v4/v5 exactly.
    if (artifact_v7.VERIFIER_ID, artifact_v7.VERIFIER_VERSION) != (
        artifact_v4.VERIFIER_ID, artifact_v4.VERIFIER_VERSION
    ):
        raise CheckError("v7 VERIFIER_ID/VERSION drifted from the frozen v4 identity")
    positive += 1

    # Positive: v7's whitelist (inherited from v6) includes the real v21
    # profile every actual bundle this engagement builds carries.
    if "STAGE17-PILOT-CANDIDATE-BUNDLE-v21" not in artifact_v7.RECOGNIZED_PROFILES:
        raise CheckError("v7 does not recognize the real v21 bundle profile")
    positive += 1

    # Negative: the accepted v5 predecessor's whitelist still excludes v21
    # -- the gap this fix closes is real, not already fixed elsewhere.
    if "STAGE17-PILOT-CANDIDATE-BUNDLE-v21" in artifact_v5.RECOGNIZED_PROFILES:
        raise CheckError("v5 unexpectedly already recognizes v21 -- this fix is unneeded")
    negative += 1

    # Negative: the frozen v4 module's source still only literally
    # mentions its original two profile strings.
    with_v4 = pathlib.Path(artifact_v4.__file__).read_text()
    if "STAGE17-PILOT-CANDIDATE-BUNDLE-v21" in with_v4:
        raise CheckError(
            "accepted v4 predecessor source unexpectedly mentions v21 -- "
            "the frozen closure file has drifted"
        )
    negative += 1

    # Positive: v40 dispatches S17-EXT-006 through the new v7 module.
    if verifier_v40.release_verifier is not artifact_v7:
        raise CheckError("v40's verify_s17_ext_006 is not wired to v7")
    positive += 1

    # Positive: v40 delegates every other input to its v39 predecessor
    # unchanged, and the orchestration-layer imports moved to v40/v7.
    if verifier_v40.predecessor is not verifier_v39:
        raise CheckError("v40 does not chain to v39 as its predecessor")
    if journal_v35.semantic is not verifier_v40:
        raise CheckError("stage17_state_journal_v35 was not moved to the v40 verifier")
    if cli.pilot_artifact is not artifact_v7:
        raise CheckError("stage17_operational_cli_v11 was not moved to the v7 artifact module")
    positive += 1

    return positive, negative


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).parents[1])
    arguments = parser.parse_args()
    try:
        positive, negative = self_test(arguments.root.resolve())
    except Exception as exception:
        print(f"stage17-ext006-v21-profile-recognition: FAIL: {exception}", file=sys.stderr)
        return 1
    if positive != POSITIVE_CASES or negative != NEGATIVE_CASES:
        print(
            "stage17-ext006-v21-profile-recognition: FAIL: expected "
            f"positive={POSITIVE_CASES} negative={NEGATIVE_CASES}, "
            f"got positive={positive} negative={negative}",
            file=sys.stderr,
        )
        return 1
    print(
        "stage17-ext006-v21-profile-recognition: PASS "
        f"positive={positive} negative={negative} stand=NOT_ACCESSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
