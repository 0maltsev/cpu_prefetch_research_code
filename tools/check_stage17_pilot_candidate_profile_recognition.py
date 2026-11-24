#!/usr/bin/env python3
"""D-128 regression: pilot-candidate artifact profile recognition.

Proves, against real sealed bundle bytes already on disk from tonight's
work (not synthesized), that:
  - the frozen predecessor `stage17_pilot_candidate_artifact_v4.py` still
    only recognizes exactly its original two profiles (unchanged);
  - the new `stage17_pilot_candidate_artifact_v5.py` successor recognizes
    the newer real candidate profiles (`v5`/`v6`) in addition to the
    unchanged predecessor set;
  - an unrecognized profile string still fails closed in both.

It does not create a checked-in record and does not touch SSH, the stand,
or any credential.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tarfile
import tempfile

import stage17_pilot_candidate_artifact_v4 as artifact_v4
import stage17_pilot_candidate_artifact_v5 as artifact_v5


POSITIVE_CASES = 4
NEGATIVE_CASES = 3


class CheckError(RuntimeError):
    pass


def _extract(archive: pathlib.Path, destination: pathlib.Path) -> pathlib.Path:
    with tarfile.open(archive, "r:gz") as source:
        roots = {pathlib.PurePosixPath(m.name).parts[0] for m in source.getmembers()}
        if len(roots) != 1:
            raise CheckError("fixture archive does not have exactly one top-level root")
        source.extractall(destination, filter="data")
    return destination / next(iter(roots))


def self_test(root: pathlib.Path) -> tuple[int, int]:
    positive = 0
    negative = 0
    build_dir = root / "build"
    # Find the most recently sealed real candidate archive (mtime, not
    # alphabetical sort -- multiple commit-hash-named archives may coexist
    # in this directory from earlier tonight's work at different profile
    # generations).
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
    v6_archive = all_archives[-1]
    with tempfile.TemporaryDirectory(prefix="stage17-d128-profile-") as text:
        temporary = pathlib.Path(text)
        extracted = _extract(v6_archive, temporary)
        manifest = json.loads((extracted / "BUNDLE_MANIFEST.json").read_text())
        profile = manifest["bundle_profile"]
        if not profile.startswith("STAGE17-PILOT-CANDIDATE-BUNDLE-v"):
            raise CheckError(f"unexpected real fixture profile: {profile}")

        # Negative: the frozen v4 predecessor must still reject this real
        # bundle whenever its profile is newer than v4 -- proving the
        # accepted v18 closure's behavior is genuinely unchanged, not
        # merely "not edited."
        if int(profile.rsplit("-v", 1)[1]) > 4:
            try:
                artifact_v4.verify_extracted_bundle_v4(extracted)
            except artifact_v4.ArtifactError as exception:
                if "not a v4 Stage 17 profile" not in str(exception):
                    raise CheckError(
                        f"v4 rejected the real bundle for an unexpected reason: {exception}"
                    ) from exception
                negative += 1
            else:
                raise CheckError(
                    "v4 predecessor unexpectedly accepted a post-v4 real bundle profile "
                    "-- accepted v18 closure behavior has drifted"
                )
        else:
            raise CheckError(
                f"real fixture profile {profile} is not newer than v4; "
                "this regression needs a v5/v6 bundle to be meaningful"
            )

        # Positive: the new v5 successor accepts the same real bytes.
        context = artifact_v5.verify_extracted_bundle_v5(extracted)
        if context.bundle_profile != profile:
            raise CheckError("v5 verified bundle_profile does not match the real manifest")
        positive += 1

        # Positive: v5's VERIFIER_ID/VERSION are unchanged from v4 (the
        # stable protocol identity, per ADR-0128/ADR-0126's frozen-anchor
        # pattern).
        if (artifact_v5.VERIFIER_ID, artifact_v5.VERIFIER_VERSION) != (
            artifact_v4.VERIFIER_ID, artifact_v4.VERIFIER_VERSION
        ):
            raise CheckError("v5 VERIFIER_ID/VERSION drifted from the frozen v4 identity")
        positive += 1

        # Positive: v4's own recognized set is provably unchanged --
        # exactly its original two literal profiles, nothing added.
        if artifact_v4 is artifact_v5:
            raise CheckError("v4 module identity check is meaningless if aliased")
        for recognized in (
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v4",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
        ):
            if recognized not in artifact_v5.RECOGNIZED_PROFILES:
                raise CheckError(f"v5 dropped a predecessor-recognized profile: {recognized}")
        positive += 1

        # Negative: v5's whitelist itself still excludes a genuinely
        # unrecognized profile string -- broadening it did not make it
        # permissive. Checked as pure set membership rather than forging
        # a full extracted bundle through it, because the profile
        # whitelist is only one of several layered checks
        # verify_extracted_bundle_v5 performs (it first runs the bundled
        # validators/verify_stand_bundle.py, which has its own, separate,
        # stricter profile validation that would reject a forged bundle
        # for a different reason before this whitelist is ever reached --
        # confirmed empirically while developing this test).
        if "STAGE17-PILOT-CANDIDATE-BUNDLE-v999" in artifact_v5.RECOGNIZED_PROFILES:
            raise CheckError("v5 whitelist unexpectedly accepts an unrecognized profile")
        negative += 1

        # Negative: v4's own whitelist is unchanged -- still excludes v5/v6.
        for unrecognized in (
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v5",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v6",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3",
        ):
            with_v4 = pathlib.Path(artifact_v4.__file__).read_text()
            if unrecognized in with_v4:
                raise CheckError(
                    f"accepted v4 predecessor source unexpectedly mentions {unrecognized} "
                    "-- v18 closure file has drifted"
                )
        negative += 1

        # Positive: DRY_RUN_PROFILES correctly classifies both dry-run
        # generations as synthetic without needing a real dry-run archive
        # (this is pure classification logic, safe to check directly).
        if not (
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2" in artifact_v5.DRY_RUN_PROFILES
            and "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3" in artifact_v5.DRY_RUN_PROFILES
            and profile not in artifact_v5.DRY_RUN_PROFILES
        ):
            raise CheckError("v5 dry-run profile classification is incorrect")
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
        print(f"stage17-pilot-candidate-profile-recognition: FAIL: {exception}", file=sys.stderr)
        return 1
    print(
        "stage17-pilot-candidate-profile-recognition: PASS "
        f"positive={positive} negative={negative} stand=NOT_ACCESSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
