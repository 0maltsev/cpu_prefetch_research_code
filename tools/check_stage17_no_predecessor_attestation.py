#!/usr/bin/env python3
"""D-124 regression for the no-predecessor-attestation evidentiary branch.

Covers: schema self-validation, the authoring tool's real-byte hashing and
create-exclusive behavior, the v15 verifier's attestation and mixing/absence
checks, and the v13 supporting-contract schema's exclusive `oneOf` branch.
ADR-0124 remains `PROPOSED`; nothing here authors a real S17-EXT-001 record
or touches the checked-in journal.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

from jsonschema import Draft202012Validator

import author_stage17_no_predecessor_attestation_v1 as author
import stage17_read_only_preflight_semantic_verifier_v15 as verifier


POSITIVE_CASES = 5
NEGATIVE_CASES = 9


class _Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _author(search_evidence: pathlib.Path, output: pathlib.Path, *,
            attestation_id: str = "SYNTHETIC-D124-ATTESTATION-01",
            actor: str = "synthetic-test-actor",
            schema_identity: str = "SYNTHETIC-D124-SEARCH-EVIDENCE/1") -> dict:
    document = author.build(_Args(
        attestation_id=attestation_id, actor=actor,
        search_evidence=search_evidence,
        search_evidence_schema_identity=schema_identity,
    ))
    schema = json.loads(author.SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(document))
    if errors:
        raise AssertionError(f"authored document failed its own schema: {errors[0].message}")
    author.write_exclusive(output, author.canonical(document))
    return document


def self_test(root: pathlib.Path) -> None:
    with tempfile.TemporaryDirectory(prefix="stage17-d124-") as text:
        temporary = pathlib.Path(text)

        # --- positive: real search-evidence bytes, valid attestation ---
        search_evidence = temporary / "search-evidence.txt"
        search_evidence.write_text(
            "SYNTHETIC-D124-SEARCH-RECORD: repository git history, "
            "/tmp, /var/tmp, /opt, /srv, /root, and every local "
            "cpu_prefetch/cpu-prefetch checkout were searched; no real "
            "D-120/D-121/D-123 predecessor evidence was found.\n"
        )
        attestation_path = temporary / "attestation.json"
        document = _author(search_evidence, attestation_path)
        if document["declaration"] != "NO_REAL_PREDECESSOR_EVIDENCE_FOUND":
            raise AssertionError("attestation declaration drifted")

        binding = {
            "locator": str(attestation_path), "size_bytes": attestation_path.stat().st_size,
            "sha256": verifier._sha256(attestation_path),
            "schema_identity": verifier.NO_PREDECESSOR_ATTESTATION_SCHEMA_IDENTITY,
        }
        verified, verified_path = verifier._verify_no_predecessor_attestation(root, binding)
        if verified_path != attestation_path or verified["actor"] != "synthetic-test-actor":
            raise AssertionError("valid attestation was not accepted")

        # --- negative: missing search-evidence file ---
        missing = temporary / "does-not-exist.txt"
        try:
            _author(missing, temporary / "out-missing.json")
        except Exception:
            pass
        else:
            raise AssertionError("authoring tool accepted a missing search-evidence file")

        # --- negative: empty search-evidence file ---
        empty = temporary / "empty.txt"
        empty.write_bytes(b"")
        try:
            _author(empty, temporary / "out-empty.json")
        except author.AttestationError:
            pass
        else:
            raise AssertionError("authoring tool accepted an empty search-evidence file")

        # --- negative: create-exclusive output cannot be overwritten ---
        duplicate_output = temporary / "duplicate.json"
        _author(search_evidence, duplicate_output)
        try:
            _author(search_evidence, duplicate_output)
        except FileExistsError:
            pass
        else:
            raise AssertionError("authoring tool overwrote an existing output file")

        # --- negative: forged/content-mismatched search_evidence binding ---
        forged_binding = dict(binding)
        forged = dict(document)
        forged["search_evidence"] = {**document["search_evidence"], "sha256": "0" * 64}
        forged_path = temporary / "forged-attestation.json"
        forged_path.write_text(author.canonical(forged).decode())
        forged_record_binding = {
            "locator": str(forged_path), "size_bytes": forged_path.stat().st_size,
            "sha256": verifier._sha256(forged_path),
            "schema_identity": verifier.NO_PREDECESSOR_ATTESTATION_SCHEMA_IDENTITY,
        }
        try:
            verifier._verify_no_predecessor_attestation(root, forged_record_binding)
        except verifier.SemanticAdmissionError:
            pass
        else:
            raise AssertionError("a forged search_evidence sha256 was accepted")

        # --- negative: attestation record bytes drifted from its own binding ---
        drifted_binding = dict(binding)
        drifted_binding["sha256"] = "1" * 64
        try:
            verifier._verify_no_predecessor_attestation(root, drifted_binding)
        except verifier.SemanticAdmissionError:
            pass
        else:
            raise AssertionError("a drifted attestation-record binding was accepted")

        # --- classify_predecessor_evidence: pure branch logic ---
        real_looking_blocker = {
            "locator": str(temporary / "SYNTHETIC-real-looking-blocker.json"),
            "size_bytes": 1, "sha256": "2" * 64,
        }
        (temporary / "SYNTHETIC-real-looking-blocker.json").write_text(
            '{"synthetic_test_only": true, "note": "SYNTHETIC fixture, never real evidence"}\n'
        )
        if verifier.classify_predecessor_evidence(
            {"no_predecessor_attestation": binding}
        ) != "ATTESTATION":
            raise AssertionError("attestation-only contract misclassified")
        if verifier.classify_predecessor_evidence(
            {"pre_marker_predecessor": real_looking_blocker,
             "post_marker_predecessor": real_looking_blocker,
             "action_revalidation_predecessor": real_looking_blocker}
        ) != "BLOCKERS":
            raise AssertionError("three-blocker contract misclassified")
        try:
            verifier.classify_predecessor_evidence({})
        except verifier.SemanticAdmissionError:
            pass
        else:
            raise AssertionError("a contract with neither branch was accepted")
        try:
            # Synthetic fixture: an attestation submitted alongside a blocker
            # binding that stands in for "real predecessor evidence actually
            # present" for this fixture's namespace -- never real evidence.
            verifier.classify_predecessor_evidence({
                "no_predecessor_attestation": binding,
                "pre_marker_predecessor": real_looking_blocker,
            })
        except verifier.SemanticAdmissionError:
            pass
        else:
            raise AssertionError(
                "an attestation combined with present blocker-receipt evidence "
                "was accepted"
            )

    # --- v13 supporting-contract schema: exclusive oneOf ---
    contract_schema = json.loads(
        (root / "config/schemas/stage17-read-only-preflight-supporting-contract-v13.schema.json")
        .read_text()
    )
    Draft202012Validator.check_schema(contract_schema)
    base = _minimal_v13_contract()
    pred = {"locator": "/p", "size_bytes": 1, "sha256": "0" * 64}
    att = {"locator": "/a", "size_bytes": 1, "sha256": "0" * 64,
           "schema_identity": verifier.NO_PREDECESSOR_ATTESTATION_SCHEMA_IDENTITY}

    def _valid(document: dict) -> bool:
        return not list(Draft202012Validator(contract_schema).iter_errors(document))

    three = dict(base, pre_marker_predecessor=pred, post_marker_predecessor=pred,
                 action_revalidation_predecessor=pred)
    attestation_only = dict(base, no_predecessor_attestation=att)
    both = dict(three, no_predecessor_attestation=att)
    neither = dict(base)
    partial = dict(base, pre_marker_predecessor=pred)

    if not _valid(three):
        raise AssertionError("v13 schema rejected the valid three-blocker branch")
    if not _valid(attestation_only):
        raise AssertionError("v13 schema rejected the valid attestation-only branch")
    if _valid(both):
        raise AssertionError("v13 schema accepted both branches at once")
    if _valid(neither):
        raise AssertionError("v13 schema accepted neither branch")
    if _valid(partial):
        raise AssertionError("v13 schema accepted a partial blocker set with no attestation")

    # --- CLI v11 argument-level exclusivity, before any file I/O ---
    cli = root / "tools/stage17_operational_cli_v11.py"
    nonexistent_evidence_root = "/nonexistent-stage17-d124-evidence-root-check"

    def _run(*extra_args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(cli),
             "--repository-root", str(root),
             "--evidence-root", nonexistent_evidence_root,
             "--pilot-archive", "/nonexistent-g", "--pilot-sidecar", "/nonexistent-h",
             "author-ext001",
             "--stand-id", "x", "--ssh-target", "x", "--known-hosts-host", "x",
             "--pinned-host-public-key", "/nonexistent-a",
             "--pinned-known-hosts", "/nonexistent-b",
             "--transport-identity", "/nonexistent-c",
             "--bundle-root-locator", "/nonexistent-d",
             "--capture-id", "x", "--captured-at-utc", "2030-01-01T00:00:00Z",
             "--preflight-evidence-root", "/nonexistent-e",
             "--actor", "x", "--issued-at-utc", "2030-01-01T00:00:00Z",
             "--expires-at-utc", "2030-01-01T00:00:01Z",
             "--authorization-id", "x", "--attempt-id", "x", "--contract-id", "x",
             "--envelope-id", "x", "--output-directory", "/nonexistent-f",
             *extra_args],
            capture_output=True, text=True, timeout=30,
        )

    neither_result = _run()
    if (neither_result.returncode == 0
            or "requires either all three blocker-receipt flags" not in neither_result.stderr):
        raise AssertionError(
            f"CLI v11 did not reject a run with neither branch before file I/O: "
            f"{neither_result.stderr!r}"
        )
    both_result = _run(
        "--pre-marker-blocker", "/nonexistent-i",
        "--post-marker-blocker", "/nonexistent-j",
        "--action-revalidation-blocker", "/nonexistent-k",
        "--no-predecessor-attestation", "/nonexistent-l",
    )
    if (both_result.returncode == 0
            or "cannot combine --no-predecessor-attestation" not in both_result.stderr):
        raise AssertionError(
            f"CLI v11 did not reject combining both branches before file I/O: "
            f"{both_result.stderr!r}"
        )
    three_result = _run(
        "--pre-marker-blocker", "/nonexistent-i",
        "--post-marker-blocker", "/nonexistent-j",
        "--action-revalidation-blocker", "/nonexistent-k",
    )
    if ("requires either all three blocker-receipt flags" in three_result.stderr
            or "cannot combine --no-predecessor-attestation" in three_result.stderr):
        raise AssertionError(
            "CLI v11 rejected a well-formed three-blocker invocation at the "
            f"exclusivity gate: {three_result.stderr!r}"
        )


def _minimal_v13_contract() -> dict:
    return {
        "schema_version": "cpu-prefetch-stage17-read-only-preflight-supporting-contract/13",
        "contract_id": "x", "protocol_version": "2.0.0-pre.3",
        "fixed_action_plan": {
            "path": "a", "size_bytes": 1, "sha256": "0" * 64,
            "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/6",
        },
        "target": {
            "stand_id": "s", "ssh_target": "t", "known_hosts_host": "h",
            "pinned_host_key_evidence": {
                "path": "a", "size_bytes": 1, "sha256": "0" * 64,
                "schema_identity": "cpu-prefetch-stage17-pinned-host-key-evidence/1",
            },
            "pinned_known_hosts": {"path": "a", "size_bytes": 1, "sha256": "0" * 64},
            "transport_identity": {"locator": "/a", "size_bytes": 1, "sha256": "0" * 64},
        },
        "pilot_candidate": {
            "contract": {
                "path": "a", "size_bytes": 1, "sha256": "0" * 64,
                "schema_identity": "cpu-prefetch-stage17-pilot-candidate-external-contract/1",
            },
            "archive_locator": "/a", "sidecar_locator": "/a", "bundle_root_locator": "/a",
        },
        "capture": {"capture_id": "c", "captured_at_utc": "2026-01-01T00:00:00Z"},
        "evidence_root": "/e",
        "prospective_local_action_identities": [
            {"identity_id": "STAGE17_READ_ONLY_PREFLIGHT_EXECUTOR", "role": "EXECUTOR",
             "execution_path": "/x",
             "source_binding": {"path": "a", "size_bytes": 1, "sha256": "0" * 64}},
            {"identity_id": "STAGE17_READ_ONLY_PREFLIGHT_COLLECTOR", "role": "COLLECTOR",
             "execution_path": "/y",
             "source_binding": {"path": "a", "size_bytes": 1, "sha256": "0" * 64}},
        ],
        "remote_runtime_identity_policy": {
            "source_input_id": "S17-EXT-002",
            "identity_classes": ["REMOTE_EXECUTABLE", "REMOTE_MODULE", "REMOTE_DEPENDENCY"],
            "prospective_values_present": False,
        },
        "limits": {
            "max_commands": 6, "max_wall_seconds": 180, "max_total_output_bytes": 6291456,
            "max_output_bytes_per_observation": 1048576, "timeout_seconds_per_observation": 30,
            "attempts_per_observation": 1, "retries": 0,
        },
        "stop_policy": "STOP_ON_FIRST_MISMATCH_NONZERO_EXIT_TIMEOUT_OR_OUTPUT_LIMIT",
        "retention_policy":
            "CREATE_EXCLUSIVE_APPEND_ONLY_RETAIN_SUCCESS_FAILURE_AND_PARTIAL_NO_DELETE",
        "authority_boundary": {
            "stand_read_only": True, "stand_mutation": False, "privileged_controls": False,
            "qualification": False, "calibration": False, "pilot_execution": False,
            "measurement": False, "stage18_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).parents[1])
    arguments = parser.parse_args()
    if not arguments.self_test:
        parser.error("--self-test is required")
    self_test(arguments.root.resolve())
    print(f"stage17-no-predecessor-attestation: PASS positive={POSITIVE_CASES} "
          f"negative={NEGATIVE_CASES} stand=NOT_ACCESSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
