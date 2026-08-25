#!/usr/bin/env python3
"""Validate the fixed-controller Q15-R v2 envelope without issuing authority."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


HASHES = tuple(str(index) * 64 for index in range(10))
FORBIDDEN_TOKENS = {"*", "latest", "current", "unresolved", "tbd"}
GRAPH = [
    "VERIFY_AUTHORIZATION_AND_RELEASE_BINDINGS",
    "VERIFY_ROLE_AND_NEGATIVE_ACCESS_EVIDENCE",
    "CREATE_PRIVATE_SAME_BUFFER_SESSION",
    "COLLECT_FIXED_MSR_PRESTATE_AS_AUDITOR",
    "COLLECT_CLOCK",
    "COLLECT_ATOMIC_LAYOUT",
    "COLLECT_ACTUAL_CPU_MIGRATION",
    "COLLECT_ADDRESS_RESIDENCY",
    "COLLECT_SOFTWARE_PREFETCH_CAPABILITY",
    "COLLECT_STORAGE_CUSTODY",
    "NEGATIVE_ACCESS_CHECK",
    "RUN_H0_REGULAR_STREAM_PROBE",
    "RUN_H0_POINTER_STREAM_PROBE",
    "SEAL_Q15_R_EVIDENCE",
    "WAIT_FOR_SEPARATE_Q15_W_OR_EXPIRE_FAIL_CLOSED",
]
STOPS = [
    "FIRST_AUTHORIZATION_OR_RELEASE_BINDING_MISMATCH",
    "FIRST_ROLE_OR_NEGATIVE_ACCESS_MISMATCH",
    "FIRST_PEER_CREDENTIAL_OR_TRANSPORT_MISMATCH",
    "FIRST_CLOCK_AFFINITY_NUMA_RESIDENCY_FAULT_PMU_OR_MSR_FAILURE",
    "FIRST_INTEGRITY_COUNT_CANONICALIZATION_HASH_OR_CUSTODY_FAILURE",
    "FIRST_LIMIT_EXPIRY_OR_DISCONNECT",
    "PRESERVE_PARTIAL_EVIDENCE_AND_NEVER_RETRY",
]


def artifact(identifier: str, digest: str) -> dict[str, str]:
    return {"artifact_id": identifier, "sha256": digest}


def canonical_core(core: dict[str, Any]) -> bytes:
    # The synthetic contract uses ASCII keys and exact integers, for which this
    # is byte-identical to the repository's JCS-I64-v1 canonicalizer.
    return json.dumps(
        core, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def positive() -> dict[str, Any]:
    controller_path = "/opt/cpu-prefetch/q15/bin/cpu_prefetch_q15_controller"
    core: dict[str, Any] = {
        "protocol_version": "2.0.0-pre.2",
        "authorization_id": "SYNTHETIC-Q15-R-V2-AUTHORIZATION",
        "authorization_version": "SYNTHETIC-v1",
        "phase": "Q15_R_READ_ONLY",
        "status": "AUTHORIZED",
        "issued_at_utc": "2026-08-24T12:00:00Z",
        "expires_at_utc": "2026-08-24T16:00:00Z",
        "stand_id": "XEON-CPU-FETCH",
        "binding_id": "SYNTHETIC-Q15-R-BINDING",
        "measurement_candidate": {
            "source_revision": "693f00b3878ed027dc09aea7916f149874fb12a1",
            "bundle_profile": "STAGE17-PILOT-CANDIDATE-BUNDLE-v1",
            "archive_sha256": "f94bb6922899caba24c26910bd1ba63018425d056fa5fd8282d1098415b8ace1",
            "runner_sha256": "8bf2577750872a7595e62797e6ef278607f3bd5308820e2c21cc957ff192c2c7",
            "runner_profile_id": "STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v3",
            "cpu_pair_selection_id": "XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1",
            "relax_mapping_id": "X86-PAUSE-ONE-PER-RELAX-SITE-v1",
            "software_prefetch_mapping_id": "X86-64-PREFETCHW-PREFETCHT0-v1",
            "hardware_prefetch_mapping_id": "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1",
        },
        "qualification_release": {
            "bundle_profile": "Q15-QUALIFICATION-TOOL-BUNDLE-v2",
            "bundle_sha256": HASHES[1],
            "source_revision": "synthetic-controller-release",
            "tool_binary_sha256": HASHES[2],
            "controller_binary_sha256": HASHES[3],
            "tool_profile_id": "Q15-FIXED-QUALIFICATION-TOOL-v1",
            "controller_profile_id": "Q15-R-STATIC-CONTROLLER-v1",
            "probe_contract_sha256": "c5a13646ea5e413239337e1b83b3162578c35591a54d6002f656a78acfd3d531",
            "dynamic_profile_sha256": "b25e3f10eae82cde0084c5907982ac0ae090d8de790656627f7760b614ebe08c",
            "controller_profile_sha256": HASHES[4],
        },
        "authorities": {
            "operator": "cpu-prefetch-q15-operator",
            "controller": "cpu-prefetch-q15-controller",
            "custodian": "cpu-prefetch-q15-custodian",
            "auditor": "cpu-prefetch-q15-auditor",
        },
        "controller_invocation": {
            "executable_path": controller_path,
            "executable_sha256": HASHES[3],
            "argv": [
                controller_path,
                "--execute-q15-r",
                "/var/lib/cpu-prefetch/q15-r/synthetic/authorization.json",
                "/var/lib/cpu-prefetch/q15-r/synthetic/authorization.sshsig",
            ],
        },
        "command_graph": GRAPH,
        "prerequisite_artifacts": [artifact("SYNTHETIC-PREREQUISITE", HASHES[5])],
        "limits": {
            "authorization_validity_seconds": 14400,
            "max_same_buffer_session_wall_seconds": 14400,
            "max_active_collection_wall_seconds": 1800,
            "external_start_watchdog_seconds": 60,
            "controller_start_poll_limit": 18_446_744_073_709_551_615,
            "worker_start_poll_limit": 18_446_744_073_709_551_615,
            "max_cpu_seconds": 7200,
            "max_output_bytes": 2_147_483_648,
            "max_artifact_count": 128,
            "frame_maximum_payload_bytes": 16_777_216,
            "primary_custody_quota_bytes": 4_294_967_296,
        },
        "storage_custody": {
            "primary_domain_id": "XEON-CPU-FETCH-MD3-Q15-CUSTODY",
            "secondary_domain_id": "DEVELOPMENT-REPOSITORY-Q15-CUSTODY",
            "output_root": "/var/lib/cpu-prefetch/q15-r",
            "append_only_policy_id": "Q15-PRIMARY-APPEND-ONLY-SEAL-THEN-TRANSFER-v1",
            "transfer_policy_id": "Q15-HASHED-SEALED-TRANSFER-WITH-RECEIPT-v1",
            "partial_artifact_policy_id": "Q15-RETAIN-PARTIAL-NEVER-PROMOTE-v1",
            "recovery_policy_id": "Q15-NO-OVERWRITE-NEW-ARTIFACT-ID-v1",
        },
        "phase_inputs": {
            "inventory_artifact": artifact("SYNTHETIC-INVENTORY", HASHES[1]),
            "topology_artifact": artifact("SYNTHETIC-TOPOLOGY", HASHES[2]),
            "storage_artifact": artifact("SYNTHETIC-STORAGE", HASHES[3]),
            "access_matrix_artifact": artifact("SYNTHETIC-ACCESS", HASHES[4]),
            "negative_access_evidence_artifact": artifact(
                "SYNTHETIC-NEGATIVE-ACCESS", HASHES[5]
            ),
            "start_barrier_policy_artifact": artifact(
                "SYNTHETIC-START-BARRIER", HASHES[6]
            ),
            "external_watchdog_policy_artifact": artifact(
                "SYNTHETIC-WATCHDOG", HASHES[7]
            ),
            "custody_policy_artifact": artifact("SYNTHETIC-CUSTODY", HASHES[8]),
            "transfer_receipt_contract_artifact": artifact(
                "SYNTHETIC-TRANSFER-RECEIPT", HASHES[9]
            ),
        },
        "stop_conditions": STOPS,
        "prohibitions": {
            "measurement_execution": False,
            "calibration_execution": False,
            "pilot_execution": False,
            "confirmatory_execution": False,
            "scientific_schedule_access": False,
            "scientific_namespace_access": False,
            "outcome_access": False,
            "outcome_driven_tuning": False,
            "top_up": False,
            "cell_repair": False,
            "hidden_retry": False,
            "q15_w_execution": False,
            "unlisted_target": False,
            "unlisted_privilege": False,
        },
        "signature_policy": {
            "canonicalization": "JCS-I64-v1",
            "scheme": "OPENSSH-SSHSIG-ED25519-SHA512-v1",
            "namespace": "cpu-prefetch-q15-authorization",
            "signer_id": "synthetic-q15-authorization-signer",
            "signer_key_fingerprint": "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        },
    }
    return {
        "schema_version": "cpu-prefetch-q15-qualification-authorization/2",
        "authorization_core": core,
        "authorization_core_sha256": hashlib.sha256(canonical_core(core)).hexdigest(),
        "detached_signature": artifact("SYNTHETIC-Q15-R-SIGNATURE", HASHES[7]),
        "independent_signature_verification": artifact(
            "SYNTHETIC-Q15-R-SIGNATURE-VERIFICATION", HASHES[8]
        ),
    }


def strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in strings(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in strings(child)]
    return []


def semantic_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    core = document.get("authorization_core", {})
    if document.get("authorization_core_sha256") != hashlib.sha256(
        canonical_core(core)
    ).hexdigest():
        errors.append("authorization core hash mismatch")
    try:
        issued = dt.datetime.fromisoformat(core["issued_at_utc"].replace("Z", "+00:00"))
        expires = dt.datetime.fromisoformat(
            core["expires_at_utc"].replace("Z", "+00:00")
        )
        if (expires - issued).total_seconds() != 14_400:
            errors.append("authorization validity must be exactly 14400 seconds")
    except (KeyError, TypeError, ValueError):
        errors.append("authorization timestamps must be parseable UTC values")

    invocation = core.get("controller_invocation", {})
    release = core.get("qualification_release", {})
    argv = invocation.get("argv", [])
    if argv and argv[0] != invocation.get("executable_path"):
        errors.append("argv[0] must equal the exact controller path")
    if invocation.get("executable_sha256") != release.get("controller_binary_sha256"):
        errors.append("controller invocation and release hashes must match")
    if tuple(core.get("command_graph", ())) != tuple(GRAPH):
        errors.append("controller graph drift")
    if tuple(core.get("stop_conditions", ())) != tuple(STOPS):
        errors.append("stop-condition drift")

    authorities = list(core.get("authorities", {}).values())
    if len(authorities) != 4 or len(set(authorities)) != 4:
        errors.append("four effective identities must be distinct")
    custody = core.get("storage_custody", {})
    if custody.get("primary_domain_id") == custody.get("secondary_domain_id"):
        errors.append("custody domains must differ")

    artifact_values: list[dict[str, str]] = []
    artifact_values.extend(core.get("prerequisite_artifacts", []))
    artifact_values.extend(core.get("phase_inputs", {}).values())
    artifact_values.extend(
        [
            document.get("detached_signature", {}),
            document.get("independent_signature_verification", {}),
        ]
    )
    artifact_ids = [item.get("artifact_id") for item in artifact_values]
    if len(artifact_ids) != len(set(artifact_ids)):
        errors.append("artifact IDs must be globally unique")
    if document.get("detached_signature", {}).get("artifact_id") == document.get(
        "independent_signature_verification", {}
    ).get("artifact_id"):
        errors.append("signature and independent verification artifacts must differ")

    for value in strings(document):
        normalized = value.casefold()
        if normalized in FORBIDDEN_TOKENS or any(
            token in normalized for token in ("<exact", "${", "../")
        ):
            errors.append("wildcard, placeholder, traversal, or unresolved token is forbidden")
            break
    return errors


def failures(
    validator: Draft202012Validator, document: dict[str, Any]
) -> list[str]:
    result = [error.message for error in validator.iter_errors(document)]
    result.extend(semantic_errors(document))
    return result


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    schema_root = root / "config/schemas"
    if not (schema_root / "q15-qualification-authorization-v2.schema.json").is_file():
        schema_root /= "implementation"
    schema = json.loads(
        (schema_root / "q15-qualification-authorization-v2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    good = positive()
    if errors := failures(validator, good):
        print(f"q15-authorization-v2-check: FAIL positive: {errors}", file=sys.stderr)
        return 1

    negatives: list[dict[str, Any]] = []
    mutations = (
        (lambda value: value["authorization_core"]["command_graph"].reverse(), True),
        lambda value: value["authorization_core"]["limits"].__setitem__(
            "external_start_watchdog_seconds", 0
        ),
        lambda value: value["authorization_core"]["authorities"].__setitem__(
            "auditor", "cpu-prefetch-q15-controller"
        ),
        lambda value: value["authorization_core"]["controller_invocation"][
            "argv"
        ].__setitem__(1, "--execute-q15-w"),
        lambda value: value["authorization_core"]["prohibitions"].__setitem__(
            "pilot_execution", True
        ),
        lambda value: value["authorization_core"]["storage_custody"].__setitem__(
            "secondary_domain_id", "XEON-CPU-FETCH-MD3-Q15-CUSTODY"
        ),
        lambda value: value.__setitem__("authorization_core_sha256", HASHES[9]),
        lambda value: value["authorization_core"].__setitem__(
            "expires_at_utc", "2026-08-24T15:59:59Z"
        ),
        lambda value: value["authorization_core"]["controller_invocation"].__setitem__(
            "executable_sha256", HASHES[9]
        ),
        lambda value: value["authorization_core"]["controller_invocation"][
            "argv"
        ].__setitem__(2, "latest"),
        lambda value: value.__setitem__(
            "independent_signature_verification", value["detached_signature"]
        ),
        lambda value: value["authorization_core"]["signature_policy"].__setitem__(
            "scheme", "OTHER"
        ),
    )
    normalized_mutations = [mutations[0], *[(item, True) for item in mutations[1:]]]
    normalized_mutations[6] = (normalized_mutations[6][0], False)
    for mutate, rehash in normalized_mutations:
        negative = copy.deepcopy(good)
        mutate(negative)
        if rehash:
            negative["authorization_core_sha256"] = hashlib.sha256(
                canonical_core(negative["authorization_core"])
            ).hexdigest()
        negatives.append(negative)
    for index, negative in enumerate(negatives):
        if not failures(validator, negative):
            print(
                f"q15-authorization-v2-check: FAIL negative {index} passed",
                file=sys.stderr,
            )
            return 1
    print(
        "q15-authorization-v2-check: PASS "
        "(1 synthetic envelope, 12 negative, no authorization issued)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
