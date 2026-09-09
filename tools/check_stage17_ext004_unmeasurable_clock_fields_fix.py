#!/usr/bin/env python3
"""D-154 regression: EXT-004 no longer requires unmeasurable clock fields.

Proves, against a real invocation of the real tool (not synthesized
JSON), that:
  - `cpu_prefetch_q15_qualification_evidence_tool --kind SELECTED_PAIR_
    CLOCK` no longer requires (or accepts) `--traced-call-count`/
    `--traced-syscall-count`/`--before-block-repeat`;
  - the real envelope it produces validates against the new `v2` schema
    and does not carry any of the three removed fields;
  - the same envelope, if it *did* still carry those fields (as every
    real `S17-EXT-004` admission before this fix did), would be rejected
    by the new schema's `additionalProperties: false`;
  - `stage17_operational_semantics_v8.py`'s `ROLE_SCHEMA_v8` retargets
    only `QUALIFICATION_EVIDENCE`, nothing else;
  - `stage17_semantic_verifier_v41.py` dispatches `S17-EXT-004` through
    `operational_semantics_v8` and delegates every other input to its
    `v40` predecessor unchanged;
  - `stage17_state_journal_v35.py`'s own hardcoded import was moved to
    the new generation.

It does not create a checked-in record and does not touch SSH, the
stand, or any credential. The raw clock-pair fixture used here is
locally constructed (this check has no access to the stand's own real,
shared raw measurement file) but matches the real, accepted schema
(`stage17-q15-clock-pair-raw-v1`) exactly, and the tool invocation
itself is real -- not a synthesized envelope.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

import stage17_operational_semantics_v6 as operational_v6
import stage17_operational_semantics_v8 as operational_v8
import stage17_semantic_verifier_v40 as verifier_v40
import stage17_semantic_verifier_v41 as verifier_v41
import stage17_state_journal_v35 as journal_v35


POSITIVE_CASES = 7
NEGATIVE_CASES = 2


class CheckError(RuntimeError):
    pass


def self_test(root: pathlib.Path) -> tuple[int, int]:
    positive = 0
    negative = 0

    tool = root / "build/release-gcc/cpu_prefetch_q15_qualification_evidence_tool"
    if not tool.is_file():
        raise CheckError(
            f"real tool binary not found at {tool} -- build "
            "cpu_prefetch_q15_qualification_evidence_tool first"
        )

    with tempfile.TemporaryDirectory(prefix="stage17-d154-") as text:
        temp = pathlib.Path(text)
        raw_path = temp / "raw.json"
        raw_path.write_text(json.dumps({
            "schema_version": "cpu-prefetch-stage17-q15-clock-pair-raw/1",
            "pair": "near",
            "producer_cpu": 0,
            "consumer_cpu": 1,
            "producer_prime_read_count": 100000,
            "consumer_prime_read_count": 100000,
            "producer_delta_count": 10000000,
            "consumer_delta_count": 10000000,
            "producer_to_consumer_window_count": 3,
            "consumer_to_producer_window_count": 3,
            "exchanges_per_window": 100000,
            "producer_per_core_passed": True,
            "consumer_per_core_passed": True,
            "cross_core_passed": True,
        }))
        output_path = temp / "envelope.json"

        # Positive: the real tool, invoked for real, with no
        # --traced-call-count/--traced-syscall-count/--before-block-repeat
        # flags at all, still succeeds.
        completed = subprocess.run(
            [str(tool), "--kind", "SELECTED_PAIR_CLOCK",
             "--raw", str(raw_path), "--output", str(output_path),
             "--artifact-id", "D154-SELF-TEST-ARTIFACT",
             "--stand-id", "D154-SELF-TEST-STAND",
             "--binding-id", "D154-SELF-TEST-BINDING",
             "--source-revision", "0" * 40,
             "--binary-sha256", "0" * 64,
             "--captured-at-utc", "2026-09-09T00:00:00Z",
             "--worker-pair", "near",
             "--source-artifact-id", "D154-SELF-TEST-RAW-SOURCE"],
            capture_output=True, text=True, check=False,
        )
        if completed.returncode != 0:
            raise CheckError(
                f"real tool invocation failed: {completed.stderr.strip()}"
            )
        positive += 1

        envelope = json.loads(output_path.read_text())
        if envelope["schema_version"] != "cpu-prefetch-qualification-evidence/2":
            raise CheckError("real envelope does not claim the new v2 schema_version")
        positive += 1
        if envelope["eligible"] is not True:
            raise CheckError("real envelope with genuinely valid counts is not eligible")
        positive += 1
        for removed in ("traced_call_count", "traced_syscall_count",
                        "before_block_repeat"):
            if removed in envelope["details"]:
                raise CheckError(f"real envelope still carries removed field: {removed}")
        positive += 1

        from jsonschema import Draft202012Validator
        schema_v2 = json.loads(
            (root / "config/schemas/qualification-evidence-v2.schema.json").read_text()
        )
        errors = list(Draft202012Validator(schema_v2).iter_errors(envelope))
        if errors:
            raise CheckError(f"real envelope rejected by v2 schema: {errors[0].message}")
        positive += 1

        # Negative: refusing to accept the CLI flags this fix removed --
        # confirms the tool genuinely dropped them, not just stopped
        # requiring them.
        completed = subprocess.run(
            [str(tool), "--kind", "SELECTED_PAIR_CLOCK",
             "--raw", str(raw_path), "--output", str(temp / "should-not-exist.json"),
             "--artifact-id", "D154-SELF-TEST-ARTIFACT-2",
             "--stand-id", "D154-SELF-TEST-STAND",
             "--binding-id", "D154-SELF-TEST-BINDING",
             "--source-revision", "0" * 40,
             "--binary-sha256", "0" * 64,
             "--captured-at-utc", "2026-09-09T00:00:00Z",
             "--worker-pair", "near",
             "--source-artifact-id", "D154-SELF-TEST-RAW-SOURCE",
             "--before-block-repeat", "true"],
            capture_output=True, text=True, check=False,
        )
        if completed.returncode == 0:
            raise CheckError("tool unexpectedly accepted a removed flag")
        negative += 1

        # Negative: a v1-shaped envelope (still carrying the three removed
        # fields, matching every real admission before this fix) is
        # rejected by the new v2 schema's additionalProperties: false.
        v1_shaped = dict(envelope)
        v1_shaped["details"] = {
            **envelope["details"],
            "traced_call_count": 10000000,
            "traced_syscall_count": 0,
            "before_block_repeat": True,
        }
        v1_shaped["schema_version"] = "cpu-prefetch-qualification-evidence/2"
        errors = list(Draft202012Validator(schema_v2).iter_errors(v1_shaped))
        if not errors:
            raise CheckError(
                "v2 schema unexpectedly accepted a v1-shaped envelope with the "
                "removed fields still present"
            )
        negative += 1

    # Positive: ROLE_SCHEMA_v8 retargets only QUALIFICATION_EVIDENCE.
    only_diff = {
        key for key in operational_v8.ROLE_SCHEMA_v8
        if operational_v8.ROLE_SCHEMA_v8[key] != operational_v6.ROLE_SCHEMA_v6.get(key)
    }
    if only_diff != {"QUALIFICATION_EVIDENCE"}:
        raise CheckError(f"ROLE_SCHEMA_v8 changed more than QUALIFICATION_EVIDENCE: {only_diff}")
    if operational_v8.ROLE_SCHEMA_v8["QUALIFICATION_EVIDENCE"] != (
        "config/schemas/qualification-evidence-v2.schema.json"
    ):
        raise CheckError("ROLE_SCHEMA_v8 does not point QUALIFICATION_EVIDENCE at v2")
    positive += 1

    # Positive: v41 dispatches S17-EXT-004 through operational_semantics_v8,
    # delegates every other input to its v40 predecessor unchanged, and the
    # journal's own import moved to v41.
    if verifier_v41.operational is not operational_v8:
        raise CheckError("v41's verify_operational_manifest_v8 is not wired to operational_v8")
    if verifier_v41.predecessor is not verifier_v40:
        raise CheckError("v41 does not chain to v40 as its predecessor")
    if journal_v35.semantic is not verifier_v41:
        raise CheckError("stage17_state_journal_v35 was not moved to the v41 verifier")
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
        print(f"stage17-ext004-unmeasurable-clock-fields-fix: FAIL: {exception}", file=sys.stderr)
        return 1
    if positive != POSITIVE_CASES or negative != NEGATIVE_CASES:
        print(
            "stage17-ext004-unmeasurable-clock-fields-fix: FAIL: expected "
            f"positive={POSITIVE_CASES} negative={NEGATIVE_CASES}, "
            f"got positive={positive} negative={negative}",
            file=sys.stderr,
        )
        return 1
    print(
        "stage17-ext004-unmeasurable-clock-fields-fix: PASS "
        f"positive={positive} negative={negative} stand=NOT_ACCESSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
