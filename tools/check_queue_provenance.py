#!/usr/bin/env python3
"""Fail-closed validation for mandatory Stage A queue provenance records."""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
from typing import Any, Final


ROOT: Final = pathlib.Path(__file__).resolve().parents[1]
RECORD_DIR: Final = ROOT / "config" / "queue-provenance"
EXPECTED_RECORDS: Final = {"ring-spsc.json", "linked-spsc.json"}
SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


def fail(message: str) -> None:
    raise ValueError(message)


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path}: expected object")
    return value


def require_nonempty(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        fail(f"{path}: expected nonempty string")
    return value


def require_nonempty_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        fail(f"{path}: expected nonempty list")
    return value


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_record(path: pathlib.Path) -> str:
    try:
        root = require_object(json.loads(path.read_text(encoding="utf-8")), path.name)
    except json.JSONDecodeError as error:
        fail(f"{path.name}: invalid JSON: {error}")

    if root.get("schema_version") != "cpu-prefetch-queue-provenance/1":
        fail(f"{path.name}.schema_version: unsupported value")
    if root.get("protocol_version") != "2.0.0-pre.1":
        fail(f"{path.name}.protocol_version: must be 2.0.0-pre.1")
    queue_id = require_nonempty(root.get("queue_id"), f"{path.name}.queue_id")

    algorithm = require_object(root.get("canonical_algorithm"), "canonical_algorithm")
    for field in ("paper", "section", "figure"):
        require_nonempty(algorithm.get(field), f"canonical_algorithm.{field}")
    require_nonempty_list(
        algorithm.get("canonical_identifiers"),
        "canonical_algorithm.canonical_identifiers",
    )

    artifact = require_object(root.get("official_artifact"), "official_artifact")
    if (
        artifact.get("status")
        != "CURRENT_OFFICIAL_PROJECT_FOUND_EXACT_PAPER_ARTIFACT_UNRESOLVED"
    ):
        fail(f"{path.name}.official_artifact.status: evidence drift")
    if artifact.get("consulted_or_used_as_implementation_text") is not False:
        fail(f"{path.name}: independent mode forbids artifact implementation use")

    source = require_object(root.get("source_and_license"), "source_and_license")
    expected_source_values = {
        "implementation_mode": "INDEPENDENT_IMPLEMENTATION",
        "reused_or_adapted_code": "NONE",
        "reused_code_license": "NOT_APPLICABLE_NO_CODE_REUSED",
        "repository_source_license": "NO-LICENSE-GRANT",
    }
    for field, expected in expected_source_values.items():
        if source.get(field) != expected:
            fail(f"{path.name}.source_and_license.{field}: expected {expected}")

    implementation_files = require_nonempty_list(
        source.get("implementation_files"), "source_and_license.implementation_files"
    )
    seen: set[str] = set()
    for index, raw_entry in enumerate(implementation_files):
        entry = require_object(raw_entry, f"implementation_files[{index}]")
        relative = require_nonempty(entry.get("path"), f"implementation_files[{index}].path")
        if relative in seen:
            fail(f"{path.name}: duplicate implementation path {relative}")
        seen.add(relative)
        if "fastflow" in relative.casefold():
            fail(f"{path.name}: FastFlow source path is prohibited")
        source_path = ROOT / relative
        if not source_path.is_file() or ROOT not in source_path.resolve().parents:
            fail(f"{path.name}: missing or escaping implementation path {relative}")
        recorded_hash = require_nonempty(
            entry.get("sha256"), f"implementation_files[{index}].sha256"
        )
        if SHA256.fullmatch(recorded_hash) is None:
            fail(f"{path.name}: malformed source SHA-256 for {relative}")
        actual_hash = digest(source_path)
        if actual_hash != recorded_hash:
            fail(
                f"{path.name}: source SHA-256 mismatch for {relative}: "
                f"expected {recorded_hash}, got {actual_hash}"
            )
        source_text = source_path.read_text(encoding="utf-8")
        if "fastflow" in source_text.casefold():
            fail(f"{path.name}: prohibited FastFlow implementation reference in {relative}")

    for field in ("semantic_adaptations", "memory_order_mapping"):
        require_nonempty_list(root.get(field), f"{path.name}.{field}")
    atomic = require_object(root.get("atomic_and_alignment"), "atomic_and_alignment")
    if atomic.get("compile_time_lock_free_required") is not True:
        fail(f"{path.name}: compile-time lock-free requirement missing")
    if atomic.get("runtime_lock_free_required") is not True:
        fail(f"{path.name}: runtime lock-free requirement missing")
    claims = require_object(root.get("claim_boundary"), "claim_boundary")
    for field in ("linearizability", "wait_free", "lock_free", "excluded"):
        require_nonempty(claims.get(field), f"claim_boundary.{field}")
    require_nonempty(root.get("refinement_record"), "refinement_record")
    correctness = require_object(
        root.get("correctness_evidence"), "correctness_evidence"
    )
    require_nonempty_list(correctness.get("test_targets"), "correctness.test_targets")
    require_nonempty_list(correctness.get("coverage"), "correctness.coverage")
    for matrix in ("gcc_libstdcxx", "clang_libcxx"):
        result = require_object(correctness.get(matrix), f"correctness.{matrix}")
        if result.get("unit_property_stress") != "PASS":
            fail(f"{path.name}: {matrix} queue tests are not passing")
        for sanitizer in ("asan_ubsan", "tsan"):
            if result.get(sanitizer) != "PASS_ZERO_FINDINGS":
                fail(f"{path.name}: {matrix} {sanitizer} evidence is not passing")
    if correctness.get("eligible_stand_runtime_lock_free_probe") != "REQUIRED_LATER":
        fail(f"{path.name}: eligible-stand lock-free evidence was invented")

    generated = require_object(
        root.get("generated_code_review"), "generated_code_review"
    )
    status = generated.get("status")
    if status == "PASS":
        if generated.get("gnu_objdump") != "PASS_WITH_NEGATIVE_MUTANT":
            fail(f"{path.name}: GNU evidence missing from passing codegen record")
        if generated.get("llvm_objdump") != "PASS_WITH_NEGATIVE_MUTANT":
            fail(f"{path.name}: LLVM evidence missing from passing codegen record")
        if generated.get("human_review") != "GNU_AND_LLVM_OPERATION_BODIES_REVIEWED":
            fail(f"{path.name}: dual-disassembler human review is not recorded")
        evidence = require_object(
            generated.get("evidence"), "generated_code_review.evidence"
        )
        for field in (
            "release_probe_sha256",
            "negative_mutant_sha256",
            "rule_set_sha256",
            "gnu_try_enqueue_body_sha256",
            "gnu_try_dequeue_body_sha256",
            "llvm_try_enqueue_body_sha256",
            "llvm_try_dequeue_body_sha256",
            "gnu_full_disassembly_sha256",
            "llvm_full_disassembly_sha256",
        ):
            value = require_nonempty(evidence.get(field), f"codegen.evidence.{field}")
            if SHA256.fullmatch(value) is None:
                fail(f"{path.name}: malformed generated-code SHA-256 for {field}")
        for field in ("gnu_objdump_version", "llvm_objdump_version"):
            require_nonempty(evidence.get(field), f"codegen.evidence.{field}")
    elif status == "BLOCKED_MISSING_LLVM_OBJDUMP":
        if generated.get("llvm_objdump") != "UNAVAILABLE":
            fail(f"{path.name}: blocked codegen state is inconsistent")
    else:
        fail(f"{path.name}.generated_code_review.status: unsupported value")

    return queue_id


def main() -> int:
    try:
        actual = {path.name for path in RECORD_DIR.glob("*.json")}
        if actual != EXPECTED_RECORDS:
            fail(
                f"queue provenance inventory mismatch: expected {sorted(EXPECTED_RECORDS)}, "
                f"got {sorted(actual)}"
            )
        if any((ROOT / name).exists() for name in ("LICENSE", "LICENSE.txt", "LICENSE.md")):
            fail("repository license file contradicts ADR-0021")
        identifiers = [check_record(RECORD_DIR / name) for name in sorted(actual)]
        if len(set(identifiers)) != len(identifiers):
            fail("queue_id values must be unique")
    except (OSError, UnicodeError, ValueError) as error:
        print(f"queue-provenance-check: FAIL: {error}", file=sys.stderr)
        return 1
    print("queue-provenance-check: PASS (2 independent no-source-reuse records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
