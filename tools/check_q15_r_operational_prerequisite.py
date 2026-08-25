#!/usr/bin/env python3
"""Validate the proposed, non-authorizing Q15-R operational-prerequisite bundle."""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import pathlib
import sys
import tarfile
from typing import Any

from jsonschema import Draft202012Validator


EXPECTED_DECISIONS = ("D-061", "D-062", "D-063", "D-064")
EXPECTED_PRINCIPALS = (
    "cpu-prefetch-q15-operator",
    "cpu-prefetch-q15-controller",
    "cpu-prefetch-q15-custodian",
    "cpu-prefetch-q15-auditor",
)
EXPECTED_PLACEHOLDERS = {
    "@ALLOWED_SIGNERS_SOURCE@",
    "@OPERATIONAL_RELEASE_ROOT@",
    "@SECONDARY_CUSTODY_ROOT@",
}
EXPECTED_ALLOW = {
    ("cpu-prefetch-q15-controller", "@OPERATIONAL_RELEASE_ROOT@/bin/cpu_prefetch_q15_controller"),
    ("cpu-prefetch-q15-auditor", "/etc/cpu-prefetch/q15/allowed_signers"),
    ("cpu-prefetch-q15-controller", "/var/lib/cpu-prefetch/q15-r/controller-staging"),
    ("cpu-prefetch-q15-custodian", "/var/lib/cpu-prefetch/q15-r/sealed"),
    ("cpu-prefetch-q15-custodian", "/var/lib/cpu-prefetch/q15-r/receipts"),
    ("cpu-prefetch-q15-auditor", "/var/lib/cpu-prefetch/q15-r/audit"),
}
SETUP_EXECUTABLES = {
    "/usr/bin/getent",
    "/usr/bin/install",
    "/usr/sbin/groupadd",
    "/usr/sbin/useradd",
    "/usr/sbin/usermod",
}
FORBIDDEN_EXECUTABLES = {
    "apt",
    "apt-get",
    "bash",
    "chmod -R",
    "curl",
    "groupdel",
    "msr-tools",
    "perf",
    "rm",
    "rmdir",
    "scp",
    "setcap",
    "sh",
    "ssh",
    "sudo",
    "userdel",
    "wget",
}
EXPECTED_RELEASE = {
    "archive_name": "cpu-prefetch-q15-qualification-tool-2.0.0-a75bcdd-clean-b4438745f3ca.tar.gz",
    "archive_sha256": "48c460b008790e3b73aefbda94cacddaeb3c842622ca5bac5c763e50515ae035",
    "archive_size_bytes": 4_247_166,
    "bundle_profile": "Q15-QUALIFICATION-TOOL-BUNDLE-v2",
    "controller_binary_sha256": "36607f03669d194b22d37bc6652e92fe8486ab0ef4964ef5217ad73d18d15cf1",
    "controller_codegen_report_sha256": "7fc0d36b0e095df9a5e4563dd48d02c7a3acf4718f8816a87f2e137af43942ca",
    "internal_file_count": 118,
    "manifest_sha256": "90f01cd1be57d844f532d0b9f5612179aa9436a44ba353e3aeda724d10704030",
    "q15_tool_binary_sha256": "ba93d6384eb536654ccdfa94dc4b52c0cfde9408b9d79ef902ea6e3749548d15",
    "sbom_sha256": "c1b915f082ce3b6a1c916c7bef1d17e008d0dede623ec8aa927dbe868dd3f537",
    "sidecar_name": "cpu-prefetch-q15-qualification-tool-2.0.0-a75bcdd-clean-b4438745f3ca.tar.gz.sha256",
    "sidecar_sha256": "9c7dee2e07c49e51af8b3e922e8295ecce959dfe53deed4d3604e59722655505",
    "source_archive_sha256": "b4438745f3ca5a461a456ea7200970b41893572869866bf40a5d58da4c18d2c7",
    "source_commit": "a75bcdd0367d79f8ee0496c55edda74311c9ef7d",
    "source_dirty": False,
    "verification_state": "VERIFIED_LOCAL_NO_AUTHORITY",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def decision_map(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item.get("decision_id", ""): item
        for item in document.get("decisions", [])
        if isinstance(item, dict)
    }


def all_argv(document: dict[str, Any]) -> list[list[str]]:
    result: list[list[str]] = []
    result.extend(
        command.get("argv", [])
        for command in document.get("setup_transaction", {}).get("commands", [])
    )
    result.extend(
        command.get("argv", [])
        for command in document.get("rollback_contract", {}).get("commands", [])
    )
    result.extend(
        probe.get("argv", [])
        for probe in document.get("negative_access_matrix", {}).get("probes", [])
    )
    result.append(document.get("trust_anchor_contract", {}).get("verification_command_template", []))
    return result


def semantic_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if tuple(document.get("decision_ids", ())) != EXPECTED_DECISIONS:
        errors.append("decision IDs must be exactly D-061 through D-064")
    decisions = decision_map(document)
    if tuple(decisions) != EXPECTED_DECISIONS:
        errors.append("decision records must be unique and ordered D-061 through D-064")
    for decision_id, decision in decisions.items():
        if decision.get("selected_option") is not None:
            errors.append(f"{decision_id} must remain unselected before owner approval")
        if decision.get("state") != "PROPOSED_AWAITING_EXPLICIT_APPROVAL":
            errors.append(f"{decision_id} must remain proposed")

    boundary = document.get("authority_boundary", {})
    for field, value in boundary.items():
        if field == "repository_local_preparation_authorized":
            if value is not True:
                errors.append("repository-local preparation must be the only true authority")
        elif value is not False:
            errors.append(f"{field} must remain false")

    release = document.get("release_evidence", {})
    if release != EXPECTED_RELEASE:
        errors.append("clean v2 release identity drift")

    trust = document.get("trust_anchor_contract", {})
    if trust.get("adapter_implemented") is not False:
        errors.append("operational adapter must remain unimplemented in this bundle")
    if trust.get("future_clean_operational_release_required") is not True:
        errors.append("a future clean operational release must remain mandatory")
    if trust.get("private_key_permitted_on_stand") is not False:
        errors.append("the authorization private key cannot be placed on the stand")
    if trust.get("controller_can_read_allowed_signers") is not False:
        errors.append("the controller cannot read the auditor-owned trust anchor")
    if trust.get("signer_fingerprint") is not None:
        errors.append("signer fingerprint cannot be fabricated before key evidence")
    if trust.get("signature_scheme") != "OPENSSH-SSHSIG-ED25519-SHA512-v1":
        errors.append("signature scheme drift")
    if trust.get("signature_namespace") != "cpu-prefetch-q15-authorization":
        errors.append("signature namespace drift")
    verification = trust.get("verification_command_template", [])
    if verification[:3] != ["/usr/bin/ssh-keygen", "-Y", "verify"]:
        errors.append("trust verification must use the fixed OpenSSH SSHSIG command")
    if "@DETACHED_SIGNATURE_PATH@" not in verification:
        errors.append("trust verification command must retain the unresolved signature path")

    custody = document.get("custody_contract", {})
    primary = custody.get("primary", {})
    secondary = custody.get("secondary", {})
    if primary.get("domain_id") == secondary.get("domain_id"):
        errors.append("primary and secondary custody domains must differ")
    if primary.get("actual_device_and_mount_verified") is not False:
        errors.append("historical /dev/md3 evidence cannot be promoted to current verification")
    if secondary.get("proposed_root") is not None:
        errors.append("secondary custody root must remain unresolved")
    if secondary.get("actual_host_mount_owner_mode_quota_verified") is not False:
        errors.append("secondary custody facts cannot be fabricated")

    placeholders = {item.get("name") for item in document.get("placeholders", [])}
    if placeholders != EXPECTED_PLACEHOLDERS:
        errors.append("the setup placeholder set must be exact")

    setup = document.get("setup_transaction", {})
    if setup.get("executed") is not False or setup.get("requires_separate_setup_authorization") is not True:
        errors.append("setup must remain unexecuted and separately authorized")
    commands = setup.get("commands", [])
    if [item.get("id") for item in commands] != [f"SETUP-{index:03d}" for index in range(1, 21)]:
        errors.append("setup command IDs/order must be exactly SETUP-001 through SETUP-020")
    for command in commands:
        argv = command.get("argv", [])
        if not argv or argv[0] not in SETUP_EXECUTABLES:
            errors.append(f"unapproved setup executable in {command.get('id')}")
        if command.get("executed") is not False:
            errors.append(f"{command.get('id')} cannot claim execution")
        if command.get("phase") == "PRESTATE" and command.get("mutation") is not False:
            errors.append(f"{command.get('id')} prestate command cannot mutate")
        if command.get("phase") == "APPLY" and command.get("mutation") is not True:
            errors.append(f"{command.get('id')} apply command must be marked mutating")
        if command.get("phase") == "APPLY" and command.get("expected_exit_codes") != [0]:
            errors.append(f"{command.get('id')} apply command must accept only exit zero")

    for argv in all_argv(document):
        if not isinstance(argv, list) or not argv:
            errors.append("every proposed operation must be a nonempty argv array")
            continue
        executable = pathlib.PurePosixPath(argv[0]).name
        if executable in FORBIDDEN_EXECUTABLES or any(token in {";", "&&", "||", "|", ">", ">>"} for token in argv):
            errors.append(f"shell, network, package, delete, or privilege operation is forbidden: {argv}")
        if "--execute-q15-r" in argv or "--execute-q15-w" in argv:
            errors.append("decision preparation cannot contain a Q15 execution command")

    probes = document.get("negative_access_matrix", {}).get("probes", [])
    expected_ids = [f"NA-{index:03d}" for index in range(1, 25)]
    if [probe.get("id") for probe in probes] != expected_ids:
        errors.append("access probes must be exactly NA-001 through NA-024")
    observed_pairs: set[tuple[str, str]] = set()
    deny_count = 0
    for probe in probes:
        argv = probe.get("argv", [])
        principal = probe.get("principal")
        if len(argv) != 7 or argv[:2] != ["/usr/sbin/runuser", "--user"] or argv[2] != principal or argv[3:5] != ["--", "/usr/bin/test"]:
            errors.append(f"malformed effective-access probe {probe.get('id')}")
            continue
        pair = (principal, argv[-1])
        if pair in observed_pairs:
            errors.append(f"duplicate access pair {pair}")
        observed_pairs.add(pair)
        expected = "ALLOW" if pair in EXPECTED_ALLOW else "DENY"
        if probe.get("expected") != expected:
            errors.append(f"access expectation drift for {pair}")
        if expected == "DENY":
            deny_count += 1
    expected_targets = {target for _, target in EXPECTED_ALLOW}
    expected_pairs = {(principal, target) for principal in EXPECTED_PRINCIPALS for target in expected_targets}
    if observed_pairs != expected_pairs or deny_count != 18:
        errors.append("access matrix must cover four roles by six targets with exactly 18 denials")

    rollback = document.get("rollback_contract", {})
    if rollback.get("deletion_prohibited") is not True or rollback.get("evidence_retained") is not True:
        errors.append("rollback must quarantine without deleting evidence")
    if rollback.get("full_prestate_restoration_claimed") is not False:
        errors.append("quarantine rollback cannot claim full prestate restoration")
    rollback_commands = rollback.get("commands", [])
    if [item.get("id") for item in rollback_commands] != [f"RB-{index:03d}" for index in range(1, 11)]:
        errors.append("rollback command IDs/order must be exactly RB-001 through RB-010")
    if any(pathlib.PurePosixPath(item.get("argv", [""])[0]).name not in {"chmod", "usermod"} for item in rollback_commands):
        errors.append("rollback may only lock or quarantine")

    unresolved = document.get("unresolved_before_setup_authorization", [])
    required_words = ("operational-adapter", "Ed25519", "secondary", "prestate", "authority", "quarantine")
    if any(not any(word in item for item in unresolved) for word in required_words):
        errors.append("setup blocker list is incomplete")
    return errors


def artifact_errors(directory: pathlib.Path, release: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    archive = directory / release["archive_name"]
    sidecar = directory / release["sidecar_name"]
    if not archive.is_file() or not sidecar.is_file():
        return ["bound archive or sidecar is missing"]
    if archive.stat().st_size != release["archive_size_bytes"] or sha256(archive) != release["archive_sha256"]:
        errors.append("bound archive size or SHA-256 mismatch")
    if sha256(sidecar) != release["sidecar_sha256"]:
        errors.append("bound sidecar SHA-256 mismatch")
    expected_sidecar = f"{release['archive_sha256']}  {release['archive_name']}\n"
    if sidecar.read_text(encoding="utf-8") != expected_sidecar:
        errors.append("bound sidecar content mismatch")

    top = release["archive_name"].removesuffix(".tar.gz")
    wanted = {
        "BUNDLE_MANIFEST.json": release["manifest_sha256"],
        "SBOM.spdx.json": release["sbom_sha256"],
        "build-provenance/q15_controller_codegen_report.json": release["controller_codegen_report_sha256"],
        "release/bin/cpu_prefetch_q15_controller": release["controller_binary_sha256"],
        "release/bin/cpu_prefetch_q15_tool": release["q15_tool_binary_sha256"],
        f"source/cpu-prefetch-source-{release['source_commit'][:7]}-clean.tar.gz": release["source_archive_sha256"],
    }
    extracted: dict[str, bytes] = {}
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            for relative in [*wanted, "SHA256SUMS"]:
                member = bundle.getmember(f"{top}/{relative}")
                stream = bundle.extractfile(member)
                if stream is None:
                    errors.append(f"bound archive member cannot be read: {relative}")
                else:
                    extracted[relative] = stream.read()
    except (KeyError, OSError, tarfile.TarError) as error:
        return [*errors, f"bound archive cannot be inspected: {error}"]
    for relative, expected_hash in wanted.items():
        data = extracted.get(relative)
        if data is None or sha256_bytes(data) != expected_hash:
            errors.append(f"bound archive member hash mismatch: {relative}")
    sums = extracted.get("SHA256SUMS", b"").decode("utf-8").splitlines()
    if len(sums) != release["internal_file_count"]:
        errors.append("bound archive internal inventory count mismatch")
    try:
        manifest = json.load(io.BytesIO(extracted["BUNDLE_MANIFEST.json"]))
    except (KeyError, json.JSONDecodeError) as error:
        errors.append(f"bound manifest cannot be decoded: {error}")
    else:
        if manifest.get("bundle_profile") != release["bundle_profile"]:
            errors.append("bound manifest profile mismatch")
        source = manifest.get("source_archive", {})
        if source.get("source_revision") != release["source_commit"] or source.get("source_dirty") is not False:
            errors.append("bound manifest source identity mismatch")
        authority_fields = [field for field, value in manifest.items() if field.endswith("_authorized") and value is not False]
        if authority_fields or manifest.get("measurement_execution_command_present") is not False:
            errors.append("bound manifest grants authority or contains measurement execution")
    return errors


def validate(validator: Draft202012Validator, document: dict[str, Any]) -> list[str]:
    failures = [error.message for error in validator.iter_errors(document)]
    failures.extend(semantic_errors(document))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", type=pathlib.Path)
    parser.add_argument("--release-artifact-dir", type=pathlib.Path)
    arguments = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    schema_path = root / "config/schemas/q15-r-operational-prerequisite-decision-input-v1.schema.json"
    document_path = arguments.document or root / "config/q15/q15-r-operational-prerequisite-decision-input-v1.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        document = json.loads(document_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"q15-r-operational-prerequisite-check: FAIL: {error}", file=sys.stderr)
        return 1
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    if failures := validate(validator, document):
        for failure in failures:
            print(f"q15-r-operational-prerequisite-check: FAIL: {failure}", file=sys.stderr)
        return 1
    if arguments.release_artifact_dir is not None:
        if failures := artifact_errors(arguments.release_artifact_dir, document["release_evidence"]):
            for failure in failures:
                print(f"q15-r-operational-prerequisite-check: FAIL: {failure}", file=sys.stderr)
            return 1

    negatives: list[dict[str, Any]] = []
    authority = copy.deepcopy(document)
    authority["authority_boundary"]["stand_access_authorized"] = True
    negatives.append(authority)
    accepted = copy.deepcopy(document)
    accepted["decisions"][0]["selected_option"] = "silently accepted"
    negatives.append(accepted)
    drift = copy.deepcopy(document)
    drift["release_evidence"]["archive_sha256"] = "0" * 64
    negatives.append(drift)
    private_key = copy.deepcopy(document)
    private_key["trust_anchor_contract"]["private_key_permitted_on_stand"] = True
    negatives.append(private_key)
    delete = copy.deepcopy(document)
    delete["rollback_contract"]["commands"][0]["argv"] = ["/usr/bin/rm", "-f", "/evidence"]
    negatives.append(delete)
    access = copy.deepcopy(document)
    access["negative_access_matrix"]["probes"][0]["expected"] = "ALLOW"
    negatives.append(access)
    for index, negative in enumerate(negatives):
        if not validate(validator, negative):
            print(
                f"q15-r-operational-prerequisite-check: FAIL: negative {index} passed",
                file=sys.stderr,
            )
            return 1
    artifact_state = "release-artifact-verified" if arguments.release_artifact_dir else "record-only"
    print(
        "q15-r-operational-prerequisite-check: PASS "
        f"(D-061..D-064 proposed, 20 setup argv, 24 access probes/18 deny, 10 rollback argv, 6 negative, {artifact_state}, authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
