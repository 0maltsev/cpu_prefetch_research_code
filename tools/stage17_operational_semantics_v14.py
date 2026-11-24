"""Admit diagnostic release receipts without changing predecessor semantics.

Reuse the existing artifact reader and EXT002/003 checks with private globals,
so the new role schema and release verifier cannot mutate old module dispatch.
All original function code and dependencies remain in the pinned closure.
"""
from __future__ import annotations

import types

import stage17_operational_semantics_v13 as predecessor
import stage17_operational_semantics_v11 as reader
import stage17_operational_semantics_v5 as release_checks
import stage17_pilot_candidate_artifact_v10 as release

OperationalSemanticError = predecessor.OperationalSemanticError
ROLE_SCHEMA_v14 = {**predecessor.ROLE_SCHEMA_v13,
    "RUNTIME_RELEASE_PROVENANCE": release.RUNTIME_RELEASE_PROVENANCE_SCHEMA}


def _read_artifacts(*arguments):
    read_globals = dict(reader._read_artifacts_v11.__globals__)
    read_globals["ROLE_SCHEMA_v11"] = ROLE_SCHEMA_v14
    return types.FunctionType(reader._read_artifacts_v11.__code__, read_globals)(*arguments)


def _verify_release(*arguments):
    release_globals = dict(release_checks._verify_extracted_release_v5.__globals__)
    release_globals["release_verifier"] = types.SimpleNamespace(
        ArtifactError=release.ArtifactError,
        verify_extracted_release_receipt_v6=release.verify_extracted_release_receipt_v10)
    return types.FunctionType(release_checks._verify_extracted_release_v5.__code__, release_globals)(*arguments)


def verify_manifest_v14(**arguments):
    if arguments["expected_input_id"] not in {"S17-EXT-002", "S17-EXT-003"}:
        return predecessor.verify_manifest_v13(**arguments)
    manifest, _ = reader.load(arguments["manifest_path"])
    if arguments["expected_input_id"] == "S17-EXT-002" and not any(
            item["role"] == "RUNTIME_RELEASE_PROVENANCE" and
            item["schema_identity"] == "cpu-prefetch-stage17-runtime-release-provenance/6"
            for item in manifest["artifacts"]):
        return predecessor.verify_manifest_v13(**arguments)
    manifest_globals = dict(reader.verify_manifest_v11.__globals__)
    manifest_globals.update(_read_artifacts_v11=_read_artifacts,
                            _verify_extracted_release_v5=_verify_release)
    verify = types.FunctionType(reader.verify_manifest_v11.__code__, manifest_globals)
    return verify(**arguments)
