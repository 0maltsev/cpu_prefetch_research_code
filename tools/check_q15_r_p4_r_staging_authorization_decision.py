#!/usr/bin/env python3
"""Validate the proposed no-authority Q15-R-P4-R staging decision bundle."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import sys
import tarfile
from typing import Any

from jsonschema import Draft202012Validator


DECISION_IDS = ("D-072", "D-073", "D-074", "D-075")
UNRESOLVED_INPUTS = (
    "EXPLICIT_D072_D075_OWNER_ACCEPTANCE",
    "PINNED_SSH_HOST_KEY_AND_BOOTSTRAP_TRANSPORT_CREDENTIAL_EVIDENCE",
    "P4_K_ALLOWED_SIGNERS_FINGERPRINT_AND_OFF_STAND_CUSTODY_EVIDENCE",
    "LITERAL_ISSUE_AND_EXPIRY_UTC_INSTANTS",
    "CANONICAL_AUTHORIZATION_SHA256_AND_DETACHED_SIGNATURE_SHA256",
    "FRESH_Q15_R_P4_R_I_IDENTITY_ARTIFACT_AND_REVIEW_HASHES",
    "DIRECT_FIXED_ARGV_TRANSPORT_AND_INDEPENDENT_REVIEW_EVIDENCE",
)
ARCHIVE_NAME = (
    "cpu-prefetch-q15-qualification-tool-2.0.0-"
    "34da95d-clean-5fc75063e1d1.tar.gz"
)
ARCHIVE_SHA256 = "f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a"
ARCHIVE_BYTES = 4_642_298
TOP_LEVEL = "cpu-prefetch-q15-qualification-tool-2.0.0-34da95d-clean-5fc75063e1d1"
CAPTURE_ID = "Q15-R-P4-R-XEON-CPU-FETCH-20260825-01"
TRANSACTION_ROOT = f"/root/cpu-prefetch-q15-r-p4-r/{CAPTURE_ID}"
CUSTODY_ROOT = (
    "/home/omaltsev/research/cpu_prefetch_research_code/docs/evidence/"
    f"stage17/{CAPTURE_ID}"
)
EXPECTED_HASHES = {
    "config/q15/q15-r-p4-e-acceptance-v1.json": (
        "b4eec39ab9a5e760cf011ad79b5c2e416755ba40f2af1769033852e735dfd1f0"
    ),
    "config/q15/q15-r-p4-r.preparation-v2.json": (
        "f8c63d1f95d69c6a9562cfec6d2635757c9dbba80137d68fdedf56bd189b6ba4"
    ),
    "config/q15/q15-r-p4-k.preparation.json": (
        "c56ae3dc74142d244e448b9a6f638960f0cce1eb1a9e7a106fea90a4bcf55e0f"
    ),
    (
        "docs/evidence/stage16/STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02/"
        "STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02.json"
    ): "f8c6adbac92a9b163c45f71138946f3672eab7391fa27800fd909e028bc73087",
}
EXPECTED_PATHS = {
    "local_archive_source": (
        "/home/omaltsev/research/cpu_prefetch_research_code/build/release-gcc/"
        f"q15-qualification-tool-bundle/{ARCHIVE_NAME}"
    ),
    "local_sidecar_source": (
        "/home/omaltsev/research/cpu_prefetch_research_code/build/release-gcc/"
        f"q15-qualification-tool-bundle/{ARCHIVE_NAME}.sha256"
    ),
    "stand_transaction_root": TRANSACTION_ROOT,
    "stand_incoming_root": f"{TRANSACTION_ROOT}/incoming",
    "stand_archive": f"{TRANSACTION_ROOT}/incoming/{ARCHIVE_NAME}",
    "stand_sidecar": f"{TRANSACTION_ROOT}/incoming/{ARCHIVE_NAME}.sha256",
    "stand_extraction_parent": f"{TRANSACTION_ROOT}/release",
    "collector_release_root": f"{TRANSACTION_ROOT}/release/{TOP_LEVEL}",
    "collector_executable": (
        f"{TRANSACTION_ROOT}/release/{TOP_LEVEL}/release/bin/"
        "cpu_prefetch_q15_prestate_collector"
    ),
    "custody_root": CUSTODY_ROOT,
    "identity_artifact": (
        f"{CUSTODY_ROOT}/Q15-R-P4-R-IDENTITY-XEON-CPU-FETCH-20260825-01.json"
    ),
    "identity_sidecar": (
        f"{CUSTODY_ROOT}/Q15-R-P4-R-IDENTITY-XEON-CPU-FETCH-20260825-01.json.sha256"
    ),
    "collector_stdout": f"{CUSTODY_ROOT}/{CAPTURE_ID}.json",
    "collector_stderr": f"{CUSTODY_ROOT}/{CAPTURE_ID}.stderr.bin",
    "collector_sidecar": f"{CUSTODY_ROOT}/{CAPTURE_ID}.json.sha256",
    "transfer_receipt": f"{CUSTODY_ROOT}/{CAPTURE_ID}.transfer-receipt.json",
    "independent_review": f"{CUSTODY_ROOT}/{CAPTURE_ID}.independent-review.json",
    "authorization_record": (
        "/home/omaltsev/research/cpu_prefetch_research_code/config/q15/"
        "q15-r-p4-r-authorization-20260825-01.json"
    ),
    "detached_signature": (
        "/home/omaltsev/research/cpu_prefetch_research_code/config/q15/"
        "q15-r-p4-r-authorization-20260825-01.json.sshsig"
    ),
}
EXPECTED_ACCEPTANCE = (
    "Q15-R-P4-F — accept D-072 through D-075 in the exact Q15-R-P4-R staging "
    "and read-only stand-prestate authorization decision bundle, bound to "
    "governance commit f30036e31acc8ae036f2f31086d493eeb30db9d7 and immutable "
    "v3 archive SHA-256 "
    "f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a. "
    "Accept the exact create-exclusive stand staging tree, fixed capture and "
    "development-custody paths, cpu-prefetch-q15-operator named authority, "
    "nonrenewable 1800-second UTC policy, accepted OpenSSH SSHSIG profile with "
    "distinct auditor review, and split P4-R-I identity then P4-R-C one-shot "
    "staging/collection graph with stop-retain-no-delete rollback. Authorize "
    "repository-local creation and verification of acceptance, ADR, and "
    "still-unissued successor authorization templates only. Do not access or "
    "modify the stand, create paths, transfer or extract artifacts, "
    "execute self-tests or the collector on the stand, create/import/copy/use "
    "keys, sign or issue P4-R-I/P4-R-C/P4-K/Q15-R/Q15-W, perform platform "
    "controls, calibrate, pilot, measure, or perform confirmatory work. Every "
    "external-input, signature, and execution phase requires a later separate "
    "exact approval."
)


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_errors(root: pathlib.Path, document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lineage = document.get("lineage", {})
    if lineage.get("repository_commit") != "f30036e31acc8ae036f2f31086d493eeb30db9d7":
        errors.append("proposal must remain bound to governance commit f30036e")
    if lineage.get("collector_release_archive_sha256") != ARCHIVE_SHA256:
        errors.append("proposal must remain bound to the exact immutable v3 archive")
    if lineage.get("reference_inventory_role") != (
        "STALE_REFERENCE_ONLY_NOT_FRESH_EXECUTION_AUTHORITY"
    ):
        errors.append("Stage 16 inventory cannot become fresh execution authority")
    lineage_bindings = {
        lineage.get("p4_e_acceptance_path"): lineage.get("p4_e_acceptance_sha256"),
        lineage.get("p4_r_preparation_path"): lineage.get("p4_r_preparation_sha256"),
        lineage.get("p4_k_preparation_path"): lineage.get("p4_k_preparation_sha256"),
        lineage.get("reference_inventory_path"): lineage.get(
            "reference_inventory_sha256"
        ),
    }
    if lineage_bindings != EXPECTED_HASHES:
        errors.append("lineage paths or hashes drifted")
    for relative, expected in EXPECTED_HASHES.items():
        path = root / relative
        if not path.is_file() or sha256(path) != expected:
            errors.append(f"immutable lineage artifact mismatch: {relative}")

    decisions = document.get("decisions", [])
    if tuple(item.get("decision_id") for item in decisions) != DECISION_IDS:
        errors.append("D-072 through D-075 must be exact, unique, and ordered")
    if any(not str(item.get("state", "")).startswith("PROPOSED_") for item in decisions):
        errors.append("no proposed decision may be recorded as accepted")

    transaction = document.get("candidate_transaction", {})
    if transaction.get("capture_id") != CAPTURE_ID:
        errors.append("capture identity drifted")
    paths = transaction.get("proposed_paths", {})
    if paths.get("state") != "PROPOSED_NOT_SELECTED_OR_CREATED":
        errors.append("literal candidates cannot be marked selected or created")
    actual_paths = {name: paths.get(name) for name in EXPECTED_PATHS}
    if actual_paths != EXPECTED_PATHS:
        errors.append("one or more proposed literal paths drifted")
    if any(
        str(paths.get(name, "")).startswith("/var/lib/cpu-prefetch/q15-r")
        for name in (
            "stand_transaction_root",
            "stand_incoming_root",
            "stand_archive",
            "stand_sidecar",
            "stand_extraction_parent",
            "collector_release_root",
            "collector_executable",
        )
    ):
        errors.append("P4-R staging cannot preselect the future operational root")

    endpoint = transaction.get("stand_endpoint", {})
    if (
        endpoint.get("host_key_fingerprint") is not None
        or endpoint.get("host_key_state")
        != "UNRESOLVED_MANDATORY_BEFORE_FIRST_STAND_ACCESS"
    ):
        errors.append("SSH host-key evidence cannot be fabricated by preparation")
    principals = transaction.get("principal_contract", {})
    required_principals = (
        principals.get("named_authority_principal"),
        principals.get("custody_principal"),
        principals.get("independent_review_principal"),
    )
    if required_principals != (
        "cpu-prefetch-q15-operator",
        "cpu-prefetch-q15-custodian",
        "cpu-prefetch-q15-auditor",
    ):
        errors.append("accepted logical principals drifted")
    if len(set(required_principals)) != 3 or principals.get(
        "root_or_ssh_access_is_authority"
    ) is not False:
        errors.append("transport, authority, custody, and review cannot collapse")

    validity = transaction.get("validity_policy", {})
    if (
        validity.get("issued_at_utc") is not None
        or validity.get("expires_at_utc") is not None
        or validity.get("exact_validity_seconds") != 1800
        or validity.get("external_collector_watchdog_seconds") != 900
        or validity.get("renewal_allowed") is not False
        or validity.get("reuse_allowed") is not False
    ):
        errors.append("UTC validity policy must remain unissued, single-use, and exact")

    signature = transaction.get("signature_and_review_contract", {})
    if any(
        signature.get(field) is not None
        for field in (
            "authorization_sha256",
            "signer_key_fingerprint",
            "detached_signature_sha256",
            "independent_review_sha256",
        )
    ):
        errors.append("signature, key, and review evidence cannot be fabricated")
    if signature.get("p4_k_dependency_state") != (
        "UNRESOLVED_BLOCKS_SIGNATURE_AND_ISSUANCE"
    ):
        errors.append("P4-K must remain a hard dependency for signature and issuance")

    identity = transaction.get("fresh_identity_authorization", {})
    collection = transaction.get("staging_collection_authorization", {})
    if (
        identity.get("gate_id") != "Q15-R-P4-R-I"
        or collection.get("gate_id") != "Q15-R-P4-R-C"
        or identity.get("state") != "NOT_ISSUED_SEPARATE_EXPLICIT_APPROVAL_REQUIRED"
        or collection.get("state")
        != "NOT_ISSUED_SEPARATE_EXPLICIT_APPROVAL_REQUIRED"
        or identity.get("automatic_continuation_to_staging") is not False
        or identity.get("stop_after_identity_capture") is not True
        or collection.get("required_identity_predecessor_sha256") is not None
    ):
        errors.append("P4-R-I and P4-R-C must remain separate, unissued, and hash-gated")
    if any(
        identity.get(field) is not False
        for field in (
            "mutation_authorized",
            "transfer_authorized",
            "collector_execution_authorized",
        )
    ):
        errors.append("P4-R-I must remain read-only and non-collecting")
    output = identity.get("required_output", {})
    if any(
        output.get(field) is not None
        for field in (
            "artifact_sha256",
            "ssh_host_key_fingerprint",
            "independent_review_sha256",
        )
    ):
        errors.append("fresh identity output must remain unresolved before execution")

    invocation = collection.get("collector_invocation", {})
    expected_argv = [
        EXPECTED_PATHS["collector_executable"],
        "--collect",
        "@AUTHORIZATION_SHA256_FROM_ISSUED_Q15_R_P4_R_C@",
        "4716e1dfc2e65fd61dce1ea54a70fd876a0b4322b69d9ad1fde5c67a65c48a57",
        "4123735a940da144e00247957d0210216cde4bf19fbdbea0378b52dab2161b87",
        CAPTURE_ID,
    ]
    if invocation.get("argv") != expected_argv:
        errors.append("collector invocation path or fixed argv drifted")
    if (
        invocation.get("shell") is not False
        or invocation.get("glob") is not False
        or invocation.get("inherited_environment") is not False
        or invocation.get("stdout_destination") != EXPECTED_PATHS["collector_stdout"]
        or invocation.get("stderr_destination") != EXPECTED_PATHS["collector_stderr"]
        or invocation.get("transport_evidence_state")
        != "UNRESOLVED_BLOCKS_EXECUTION"
    ):
        errors.append("collector launch/capture boundary drifted or was prematurely resolved")
    if (
        collection.get("create_exclusive") is not True
        or collection.get("overwrite_allowed") is not False
        or collection.get("symlink_allowed") is not False
        or collection.get("activation_link_allowed") is not False
        or collection.get("archive_transfer_count") != 1
        or collection.get("collector_attempt_count") != 1
        or collection.get("retry_count") != 0
    ):
        errors.append("staging and collection must be create-exclusive and one-shot")

    transfer = transaction.get("transfer_and_verification_contract", {})
    if (
        transfer.get("archive_transfer_source_sha256") != ARCHIVE_SHA256
        or transfer.get("archive_transfer_bytes") != ARCHIVE_BYTES
        or len(transfer.get("ordered_actions", [])) != 13
        or transfer.get("per_command_timeout_seconds") != 30
        or transfer.get("external_total_watchdog_seconds") != 900
        or transfer.get("partial_preservation_required") is not True
        or transfer.get("promotion_or_activation_authorized") is not False
    ):
        errors.append("transfer, verification, or limit contract drifted")
    rollback = transaction.get("rollback_contract", {})
    if any(
        rollback.get(field) is not False
        for field in (
            "delete_authorized",
            "overwrite_authorized",
            "rename_or_reuse_authorized",
            "automatic_cleanup_authorized",
            "operational_release_or_setup_touched",
        )
    ) or rollback.get("future_cleanup_requires_separate_exact_authorization") is not True:
        errors.append("rollback must stop and retain without delete, reuse, or cleanup")
    if len(transaction.get("stop_conditions", [])) != 11:
        errors.append("the exact eleven stop-condition groups are mandatory")

    unresolved = document.get("unresolved_inputs", [])
    if tuple(item.get("name") for item in unresolved) != UNRESOLVED_INPUTS:
        errors.append("the seven unresolved prerequisite groups must be exact and ordered")
    if any(
        item.get("state") != "UNRESOLVED" or item.get("value") is not None
        for item in unresolved
    ):
        errors.append("external evidence cannot be defaulted or fabricated")

    effect = document.get("acceptance_effect", {})
    if effect.get("literal_candidate_paths_selected_if_accepted") is not True:
        errors.append("acceptance must prospectively select the exact literal candidates")
    if effect.get("repository_local_successor_templates_authorized_if_accepted") is not True:
        errors.append("acceptance must authorize only repository-local successor templates")
    if any(
        value is True
        for name, value in effect.items()
        if name.endswith("_authorized_if_accepted")
        and name != "repository_local_successor_templates_authorized_if_accepted"
    ):
        errors.append("decision acceptance cannot become operational authority")
    boundary = document.get("authority_boundary", {})
    true_boundary = {name for name, value in boundary.items() if value is True}
    if true_boundary != {"repository_local_decision_bundle_preparation_authorized"}:
        errors.append("proposal widens current authority beyond local preparation")
    if document.get("exact_acceptance_statement") != EXPECTED_ACCEPTANCE:
        errors.append("the offered exact acceptance statement drifted")

    p4_r = load(root / "config/q15/q15-r-p4-r.preparation-v2.json")
    if len(p4_r.get("remaining_required_inputs", [])) != 7 or any(
        item.get("state") != "UNRESOLVED" or item.get("value") is not None
        for item in p4_r.get("remaining_required_inputs", [])
    ):
        errors.append("P4-R v2 must retain all seven unresolved inputs")
    p4_k = load(root / "config/q15/q15-r-p4-k.preparation.json")
    if len(p4_k.get("unresolved_inputs", [])) != 8 or any(
        item.get("value") is not None for item in p4_k.get("unresolved_inputs", [])
    ):
        errors.append("P4-K must remain byte-preserved with eight unresolved inputs")
    return errors


def archive_errors(archive_path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    sidecar = archive_path.with_name(f"{archive_path.name}.sha256")
    if archive_path.name != ARCHIVE_NAME:
        errors.append("archive path does not name the selected v3 archive")
    if not archive_path.is_file():
        return errors + ["selected v3 archive is missing"]
    if archive_path.stat().st_size != ARCHIVE_BYTES or sha256(archive_path) != ARCHIVE_SHA256:
        errors.append("selected v3 archive size or SHA-256 mismatch")
    expected_sidecar = f"{ARCHIVE_SHA256}  {ARCHIVE_NAME}\n"
    if not sidecar.is_file() or sidecar.read_text(encoding="utf-8") != expected_sidecar:
        errors.append("selected v3 archive sidecar is missing or mismatched")
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = archive.getmembers()
            if not members:
                errors.append("selected v3 archive is empty")
            for member in members:
                path = pathlib.PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not path.parts
                    or path.parts[0] != TOP_LEVEL
                    or member.islnk()
                    or member.issym()
                    or member.isdev()
                    or member.isfifo()
                ):
                    errors.append(f"unsafe or unexpected archive member: {member.name}")
                    break
    except (OSError, tarfile.TarError) as error:
        errors.append(f"cannot inspect selected v3 archive: {error}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-path", type=pathlib.Path)
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    document = load(
        root
        / "config/q15/q15-r-p4-r-staging-authorization-decision-input-v1.json"
    )
    schema = load(
        root
        / "config/schemas/q15-r-p4-r-staging-authorization-decision-input-v1.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(document)]
    errors.extend(semantic_errors(root, document))
    if args.archive_path is not None:
        errors.extend(archive_errors(args.archive_path))

    negatives: list[dict[str, Any]] = []
    authority = copy.deepcopy(document)
    authority["authority_boundary"]["stand_access_authorized"] = True
    negatives.append(authority)
    accepted = copy.deepcopy(document)
    accepted["decisions"][0]["state"] = "ACCEPTED"
    negatives.append(accepted)
    release_drift = copy.deepcopy(document)
    release_drift["lineage"]["collector_release_archive_sha256"] = "0" * 64
    negatives.append(release_drift)
    path_drift = copy.deepcopy(document)
    path_drift["candidate_transaction"]["proposed_paths"]["stand_transaction_root"] = (
        "/var/lib/cpu-prefetch/q15-r/invented"
    )
    negatives.append(path_drift)
    root_authority = copy.deepcopy(document)
    root_authority["candidate_transaction"]["principal_contract"][
        "root_or_ssh_access_is_authority"
    ] = True
    negatives.append(root_authority)
    validity = copy.deepcopy(document)
    validity["candidate_transaction"]["validity_policy"]["exact_validity_seconds"] = 3600
    negatives.append(validity)
    collapsed = copy.deepcopy(document)
    collapsed["candidate_transaction"]["fresh_identity_authorization"][
        "automatic_continuation_to_staging"
    ] = True
    negatives.append(collapsed)
    retry = copy.deepcopy(document)
    retry["candidate_transaction"]["staging_collection_authorization"]["retry_count"] = 1
    negatives.append(retry)
    invocation = copy.deepcopy(document)
    invocation["candidate_transaction"]["staging_collection_authorization"][
        "collector_invocation"
    ]["argv"][0] = "/unapproved/collector"
    negatives.append(invocation)
    fabricated_signature = copy.deepcopy(document)
    fabricated_signature["candidate_transaction"]["signature_and_review_contract"][
        "authorization_sha256"
    ] = "0" * 64
    negatives.append(fabricated_signature)
    deleting = copy.deepcopy(document)
    deleting["candidate_transaction"]["rollback_contract"]["delete_authorized"] = True
    negatives.append(deleting)
    effect = copy.deepcopy(document)
    effect["acceptance_effect"]["stand_access_authorized_if_accepted"] = True
    negatives.append(effect)
    missing_stop = copy.deepcopy(document)
    missing_stop["candidate_transaction"]["stop_conditions"].pop()
    negatives.append(missing_stop)
    lineage = copy.deepcopy(document)
    lineage["lineage"]["p4_r_preparation_sha256"] = "0" * 64
    negatives.append(lineage)
    capture_path = copy.deepcopy(document)
    capture_path["candidate_transaction"]["proposed_paths"]["collector_stdout"] = (
        "/tmp/invented.json"
    )
    negatives.append(capture_path)

    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(
                f"q15-r-p4-r-staging-authorization-decision-check: FAIL: {error}",
                file=sys.stderr,
            )
        return 1
    archive_suffix = " + exact local archive" if args.archive_path is not None else ""
    print(
        "q15-r-p4-r-staging-authorization-decision-check: PASS "
        f"(D-072..D-075 proposed, split I/C gates unissued, 7 unresolved, "
        f"15 negative{archive_suffix}, authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
