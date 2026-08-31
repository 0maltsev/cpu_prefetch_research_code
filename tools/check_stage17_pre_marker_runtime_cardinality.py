#!/usr/bin/env python3
"""D-121 regression for the pre-marker runtime-cardinality boundary."""

from __future__ import annotations

import argparse
import json
import pathlib
import tempfile

from jsonschema import Draft202012Validator

import author_stage17_pre_marker_blocker_v1 as author
import stage17_read_only_preflight_semantic_verifier_v12 as verifier


POSITIVE_CASES = 4
NEGATIVE_CASES = 5


def _runtime_validator(schema: dict[str, object]) -> Draft202012Validator:
    return Draft202012Validator({
        "$defs": schema["$defs"],
        **schema["properties"]["runtime_implementation_hashes"],
    })


def _rejected(validator: Draft202012Validator, document: object) -> bool:
    return bool(list(validator.iter_errors(document)))


def self_test(root: pathlib.Path) -> None:
    old_schema = json.loads((root / verifier.predecessor.ATTEMPT_SCHEMA_PATH).read_text())
    new_schema = json.loads((root / verifier.ATTEMPT_SCHEMA_PATH).read_text())
    old = _runtime_validator(old_schema)
    new = _runtime_validator(new_schema)
    exact = {name: "a" * 64 for name in verifier.IMPLEMENTATION_PATHS}
    if len(exact) != 20 or _rejected(new, exact):
        raise AssertionError("v8 did not accept the exact policy-v12 runtime set")
    policy = json.loads((root / verifier.POLICY_PATH).read_text())
    if set(policy["implementations"]) != set(exact):
        raise AssertionError("policy and attempt runtime key sets differ")
    old_19 = {f"runtime_{index:02d}": "b" * 64 for index in range(19)}
    if not _rejected(old, old_19):
        raise AssertionError("v7 cardinality defect was not reproduced")

    with tempfile.TemporaryDirectory(prefix="stage17-d121-") as text:
        temporary = pathlib.Path(text)
        journal = temporary / "journal.json"
        authorization = temporary / "authorization.json"
        output = temporary / "old-output"
        output.mkdir(mode=0o700)
        journal.write_text('{"preserved":"journal"}\n')
        authorization.write_text('{"preserved":"authorization"}\n')
        blocker = author.render(
            blocker_id="SYNTHETIC-D121-BLOCKER",
            recorded_at_utc="2030-01-01T00:00:00Z",
            transaction_id="SYNTHETIC-D120-TRANSACTION",
            journal=journal, authorization=authorization, output_root=output,
        )
        blocker_path = temporary / "blocker.json"
        blocker_path.write_text(json.dumps(blocker, sort_keys=True,
                                           separators=(",", ":")) + "\n")
        binding = {"locator": str(blocker_path),
                   "size_bytes": blocker_path.stat().st_size,
                   "sha256": verifier._sha256(blocker_path)}
        verified, verified_path = verifier._verify_pre_marker_predecessor(
            root, binding
        )
        if verified["transport_started"] or verified_path != blocker_path:
            raise AssertionError("typed blocker verification drifted")

        missing = dict(exact)
        missing.pop(next(iter(missing)))
        extra = {**exact, "unregistered": "c" * 64}
        malformed = {**exact, next(iter(exact)): "not-a-sha256"}
        if not all((_rejected(new, missing), _rejected(new, extra),
                    _rejected(new, malformed))):
            raise AssertionError("v8 accepted missing/extra/malformed runtime identity")
        (output / "unexpected-marker").write_text("must block\n")
        try:
            verifier._verify_pre_marker_predecessor(root, binding)
        except verifier.SemanticAdmissionError:
            pass
        else:
            raise AssertionError("nonempty predecessor output root was accepted")
        (output / "unexpected-marker").unlink()
        journal.write_text('{"drifted":true}\n')
        try:
            verifier._verify_pre_marker_predecessor(root, binding)
        except verifier.SemanticAdmissionError:
            pass
        else:
            raise AssertionError("drifted predecessor journal bytes were accepted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--root", type=pathlib.Path,
                        default=pathlib.Path(__file__).parents[1])
    arguments = parser.parse_args()
    if not arguments.self_test:
        parser.error("--self-test is required")
    self_test(arguments.root.resolve())
    print(f"stage17-pre-marker-runtime-cardinality: PASS positive={POSITIVE_CASES} "
          f"negative={NEGATIVE_CASES} stand=NOT_ACCESSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
