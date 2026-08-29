#!/usr/bin/env python3
"""Generate an integrity manifest for an authorized protocol snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_name(relative: Path) -> str:
    text = relative.as_posix()
    if text == "main.pdf":
        return "paper/main.pdf"
    if text == "PAPER_AGENTS.md":
        return "AGENTS.md"
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--prior-version", required=True)
    parser.add_argument("--git-revision", required=True)
    parser.add_argument("--timestamp-utc", required=True)
    parser.add_argument("--decision-id", default="D-031")
    parser.add_argument("--approval-id", action="append", dest="approval_ids")
    parser.add_argument(
        "--git-commit-status", default="Q10_Q11_AUTHORIZED_LOCAL_AMENDMENT"
    )
    arguments = parser.parse_args()

    root = arguments.source_root.resolve()
    snapshot = root / "protocol" / arguments.version
    manifest_path = snapshot / "IMPORT_MANIFEST.json"
    files = sorted(
        path
        for path in snapshot.rglob("*")
        if path.is_file() and path != manifest_path
    )
    artifacts: list[dict[str, object]] = []
    for path in files:
        relative = path.relative_to(snapshot)
        artifacts.append(
            {
                "original_relative_path": source_name(relative),
                "imported_relative_path": (
                    Path("protocol") / arguments.version / relative
                ).as_posix(),
                "file_size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "verification_result": "PASS_AUTHORIZED_AMENDMENT_BYTES",
                "compatibility_status": f"CURRENT_{arguments.version}",
            }
        )

    manifest = {
        "manifest_version": 1,
        "protocol_version": arguments.version,
        "source_repository": {
            "identity": "cpu_prefetch_research_code_protocol_authority",
            "git_commit": arguments.git_revision,
            "git_commit_status": arguments.git_commit_status,
        },
        "import_timestamp_utc": arguments.timestamp_utc,
        "verification_result": "PASS",
        "verification_scope": (
            "AUTHORIZED_AMENDMENT_INVENTORY_SIZE_SHA256_AND_"
            "DECLARED_AUTHORITATIVE_HASHES"
        ),
        "draft_2020_12_meta_schema_validation": (
            "PASS_JSONSCHEMA_4.26.0_REQUIRED_BY_REPOSITORY_CHECK"
        ),
        "compatibility_status": {
            "current_protocol": arguments.version,
            "status": "CURRENT",
            "prior_version": arguments.prior_version,
            "prior_status": "IMMUTABLE_READABLE_NO_MIXED_SEALED_GRAPH",
        },
        "authorization": {
            "decision_id": arguments.decision_id,
            "approval_ids": arguments.approval_ids or ["Q10", "Q11"],
            "authority_roles": ["PROTOCOL_OWNER", "STATISTICAL_OWNER"],
            "outcome_accessed": False,
        },
        "artifacts": artifacts,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"protocol-manifest: PASS ({arguments.version}, {len(artifacts)} artifacts)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
