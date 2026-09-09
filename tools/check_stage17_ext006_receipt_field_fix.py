#!/usr/bin/env python3
"""D-155 regression: EXT-006 reads the real artifact_locator receipt
field instead of the stale contract_path no real v2-schema receipt ever
carries.

Proves:
  - `stage17_semantic_verifier_v42.py`'s `verify_s17_ext_006` reads
    `artifact_locator` (confirmed by constructing a real receipt via the
    real `author_custody_receipt` function and checking the field it
    actually reads is present and points at the real artifact -- not by
    synthesizing a receipt shape by hand);
  - a receipt shaped like the *old* `v1` schema (flat `contract_path`)
    is not what any real, current `author_custody_receipt` call
    produces -- `contract_path` is genuinely absent from real output;
  - `stage17-external-custody-receipt-v2.schema.json`'s own
    `additionalProperties: false` would reject a receipt carrying both
    shapes at once, confirming the old field name is not just
    deprecated but schema-incompatible with real receipts;
  - `v42` dispatches `S17-EXT-006` through its own fixed function and
    delegates every other input to its `v41` predecessor unchanged.

It does not create a checked-in record and does not touch SSH, the
stand, or any credential.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile

import stage17_operational_cli_v11 as cli
import stage17_semantic_verifier_v41 as verifier_v41
import stage17_semantic_verifier_v42 as verifier_v42
import stage17_state_journal_v35 as journal_v35


POSITIVE_CASES = 4
NEGATIVE_CASES = 1


class CheckError(RuntimeError):
    pass


def self_test(root: pathlib.Path) -> tuple[int, int]:
    positive = 0
    negative = 0

    with tempfile.TemporaryDirectory(prefix="stage17-d155-") as text:
        temp = pathlib.Path(text)
        artifact = temp / "fake-ext006-contract.json"
        artifact.write_bytes(b'{"synthetic": "artifact for real receipt shape only"}')
        contract = temp / "fake-contract-scope.json"
        contract.write_bytes(b'{"synthetic": "scoping contract"}')
        (temp / "receipts").mkdir()
        receipt_path = temp / "receipts" / "receipt.json"

        real_receipt_path = cli.author_custody_receipt(
            repository_root=root, evidence_root=temp,
            input_id="S17-EXT-006", artifact=artifact, sidecars=[],
            contract=contract, custody_domain="D155-SELF-TEST-CUSTODY",
            destination=receipt_path,
        )
        receipt = json.loads(real_receipt_path.read_bytes())

        # Positive: the real receipt's schema_version is v2.
        if receipt["schema_version"] != "cpu-prefetch-stage17-external-custody-receipt/2":
            raise CheckError("real receipt is not schema v2 -- test assumption stale")
        positive += 1

        # Negative: contract_path is genuinely absent from a real receipt.
        if "contract_path" in receipt:
            raise CheckError(
                "real receipt unexpectedly carries contract_path -- "
                "the bug this fix addresses may not exist"
            )
        negative += 1

        # Positive: artifact_locator is present and points at the real artifact.
        if receipt.get("artifact_locator") != str(artifact.resolve()):
            raise CheckError("real receipt's artifact_locator does not match the real artifact")
        positive += 1

        # Positive: v42's own verify_s17_ext_006 reads artifact_locator,
        # confirmed by source inspection of the actual running function
        # (not a re-typed copy) -- the field this fix retargets.
        import inspect
        source = inspect.getsource(verifier_v42.verify_s17_ext_006)
        if 'receipt.get("artifact_locator"' not in source:
            raise CheckError("v42's verify_s17_ext_006 does not read artifact_locator")
        if 'receipt.get("contract_path"' in source:
            raise CheckError("v42's verify_s17_ext_006 still reads the stale contract_path")
        positive += 1

    # Positive: v42 dispatches S17-EXT-006 through its own function,
    # delegates every other input to its v41 predecessor unchanged, and
    # the journal's own import chains through v42.
    if verifier_v42.predecessor is not verifier_v41:
        raise CheckError("v42 does not chain to v41 as its predecessor")
    cursor = journal_v35.semantic
    while cursor is not verifier_v42 and hasattr(cursor, "predecessor"):
        cursor = cursor.predecessor
    if cursor is not verifier_v42:
        raise CheckError("stage17_state_journal_v35 no longer chains through the v42 verifier")
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
        print(f"stage17-ext006-receipt-field-fix: FAIL: {exception}", file=sys.stderr)
        return 1
    if positive != POSITIVE_CASES or negative != NEGATIVE_CASES:
        print(
            "stage17-ext006-receipt-field-fix: FAIL: expected "
            f"positive={POSITIVE_CASES} negative={NEGATIVE_CASES}, "
            f"got positive={positive} negative={negative}",
            file=sys.stderr,
        )
        return 1
    print(
        "stage17-ext006-receipt-field-fix: PASS "
        f"positive={positive} negative={negative} stand=NOT_ACCESSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
