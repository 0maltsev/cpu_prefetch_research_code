#!/usr/bin/env python3
"""Validate split Q15-R/Q15-W contracts without issuing authority."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


HASH = "0" * 64
CPUS = (0, 1, 26)
R_KINDS = {
    "READ_FIXED_MSR_VALUES",
    "COLLECT_CLOCK",
    "COLLECT_ATOMIC_LAYOUT",
    "COLLECT_ACTUAL_CPU_MIGRATION",
    "COLLECT_ADDRESS_RESIDENCY",
    "COLLECT_SOFTWARE_PREFETCH_CAPABILITY",
    "COLLECT_STORAGE_CUSTODY",
    "NEGATIVE_ACCESS_CHECK",
    "REGULAR_STREAM_PROBE",
    "POINTER_STREAM_PROBE",
}
W_KINDS = {
    "APPLY_H1_CPU",
    "INDEPENDENT_READBACK_H1_CPU",
    "REGULAR_STREAM_PROBE",
    "POINTER_STREAM_PROBE",
    "RESTORE_H0_CPU",
    "INDEPENDENT_RESTORE_READBACK_CPU",
}
FORBIDDEN_TOKENS = {"*", "latest", "current", "unresolved", "tbd"}


def artifact(name: str, digest: str = HASH) -> dict[str, str]:
    return {"artifact_id": name, "sha256": digest}


def command(
    kind: str,
    suffix: str,
    *,
    role: str = "CONTROLLER",
    privilege: str = "NONPRIVILEGED",
    target: str = "QUALIFICATION-ONLY",
    mutating: bool = False,
    inverse: str | None = None,
    readback: str | None = None,
) -> dict[str, Any]:
    command_id = f"SYNTHETIC-{kind}-{suffix}"
    return {
        "command_id": command_id,
        "kind": kind,
        "executable_sha256": HASH,
        "argv": ["/synthetic/q15-tool", f"--{kind.casefold().replace('_', '-')}"],
        "role": role,
        "privilege": privilege,
        "exact_target": target,
        "mutating": mutating,
        "inverse_command_id": inverse,
        "independent_readback_command_id": readback,
        "output_artifact_id": f"{command_id}-OUTPUT",
    }


def common(phase: str) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_version": "cpu-prefetch-q15-qualification-authorization/1",
        "protocol_version": "2.0.0-pre.2",
        "authorization_id": f"SYNTHETIC-{phase}-AUTHORIZATION",
        "authorization_version": "SYNTHETIC-v1",
        "phase": phase,
        "status": "AUTHORIZED",
        "issued_at_utc": "2026-08-24T00:00:00Z",
        "expires_at_utc": "2026-08-24T01:00:00Z",
        "stand_id": "SYNTHETIC-STAND",
        "binding_id": "SYNTHETIC-Q15-BINDING",
        "measurement_candidate": {
            "bundle_profile": "STAGE17-PILOT-CANDIDATE-BUNDLE-v1",
            "archive_sha256": HASH,
            "source_revision": "0123456789abcdef",
            "runner_sha256": HASH,
            "runner_profile_id": "STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v3",
            "cpu_pair_selection_id": "XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1",
            "relax_mapping_id": "X86-PAUSE-ONE-PER-RELAX-SITE-v1",
            "software_prefetch_mapping_id": "X86-64-PREFETCHW-PREFETCHT0-v1",
            "hardware_prefetch_mapping_id": "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1",
        },
        "qualification_tool": {
            "bundle_profile": "Q15-QUALIFICATION-TOOL-BUNDLE-v1",
            "bundle_sha256": HASH,
            "source_revision": "0123456789abcdef",
            "binary_sha256": HASH,
            "tool_profile_id": "Q15-FIXED-QUALIFICATION-TOOL-v1",
        },
        "prerequisite_artifacts": [artifact("SYNTHETIC-PREREQUISITE")],
        "authorities": {
            "operator": "SYNTHETIC-OPERATOR",
            "controller": "SYNTHETIC-CONTROLLER",
            "custodian": "SYNTHETIC-CUSTODIAN",
            "auditor": "SYNTHETIC-AUDITOR",
        },
        "limits": {
            "max_wall_seconds": 1,
            "max_output_bytes": 1,
            "max_artifact_count": 1,
            "max_cpu_seconds": 1,
        },
        "storage_custody": {
            "primary_domain_id": "SYNTHETIC-PRIMARY",
            "secondary_domain_id": "SYNTHETIC-SECONDARY",
            "output_root": "/synthetic/q15/output",
            "append_only_policy_id": "SYNTHETIC-APPEND-ONLY",
            "transfer_policy_id": "SYNTHETIC-TRANSFER",
            "partial_artifact_policy_id": "SYNTHETIC-PARTIAL",
            "recovery_policy_id": "SYNTHETIC-RECOVERY",
            "quota_bytes": 1,
        },
        "stop_conditions": ["SYNTHETIC-STOP-ON-FIRST-MISMATCH"],
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
            "later_phase_execution": False,
            "unlisted_target": False,
            "unlisted_privilege": False,
        },
        "detached_signature": {
            "scheme": "SYNTHETIC-SCHEME",
            "signer_id": "SYNTHETIC-SIGNER",
            "artifact_id": "SYNTHETIC-SIGNATURE",
            "sha256": HASH,
        },
    }
    return value


def q15_r() -> dict[str, Any]:
    value = common("Q15_R_READ_ONLY")
    commands = [
        command("READ_FIXED_MSR_VALUES", "ALL", role="AUDITOR", privilege="READ_ONLY_PRIVILEGED", target="CPUS:0,1,26;MSR:000001a4"),
        *(command(kind, "ONE") for kind in sorted(R_KINDS - {"READ_FIXED_MSR_VALUES"})),
    ]
    value["permitted_commands"] = commands
    value["phase_inputs"] = {
        "input_kind": "Q15_R_INPUTS",
        "inventory_artifact": artifact("SYNTHETIC-INVENTORY"),
        "topology_artifact": artifact("SYNTHETIC-TOPOLOGY"),
        "access_matrix_artifact": artifact("SYNTHETIC-ACCESS-MATRIX"),
        "start_barrier_policy_artifact": artifact("SYNTHETIC-START-BARRIER"),
        "external_watchdog_policy_artifact": artifact("SYNTHETIC-WATCHDOG"),
    }
    return value


def q15_w() -> dict[str, Any]:
    value = common("Q15_W_APPLY_PROBE_RESTORE")
    commands: list[dict[str, Any]] = []
    for cpu in CPUS:
        apply_id = f"SYNTHETIC-APPLY_H1_CPU-{cpu}"
        read_id = f"SYNTHETIC-INDEPENDENT_READBACK_H1_CPU-{cpu}"
        restore_id = f"SYNTHETIC-RESTORE_H0_CPU-{cpu}"
        restore_read_id = f"SYNTHETIC-INDEPENDENT_RESTORE_READBACK_CPU-{cpu}"
        commands.extend(
            [
                command("APPLY_H1_CPU", str(cpu), role="OPERATOR", privilege="WRITE_PRIVILEGED", target=f"CPU:{cpu};MSR:000001a4", mutating=True, inverse=restore_id, readback=read_id),
                command("INDEPENDENT_READBACK_H1_CPU", str(cpu), role="AUDITOR", privilege="READ_ONLY_PRIVILEGED", target=f"CPU:{cpu};MSR:000001a4"),
                command("RESTORE_H0_CPU", str(cpu), role="OPERATOR", privilege="WRITE_PRIVILEGED", target=f"CPU:{cpu};MSR:000001a4", mutating=True, readback=restore_read_id),
                command("INDEPENDENT_RESTORE_READBACK_CPU", str(cpu), role="AUDITOR", privilege="READ_ONLY_PRIVILEGED", target=f"CPU:{cpu};MSR:000001a4"),
            ]
        )
    commands.extend(
        [
            command("REGULAR_STREAM_PROBE", "H1"),
            command("POINTER_STREAM_PROBE", "H1"),
        ]
    )
    value["permitted_commands"] = commands
    prestates = (0x123456789ABCDEF0, 0xFEDCBA9876543210, 0x0F0F0F0F0F0F0F00)
    value["phase_inputs"] = {
        "input_kind": "Q15_W_INPUTS",
        "q15_r_authorization": artifact("SYNTHETIC-Q15-R-AUTHORIZATION", "1" * 64),
        "q15_r_evidence_set": artifact("SYNTHETIC-Q15-R-EVIDENCE", "2" * 64),
        "prestates": [
            {
                "cpu": cpu,
                "prestate_hex": f"{prestate:016x}",
                "h1_requested_hex": f"{prestate | 0xF:016x}",
            }
            for cpu, prestate in zip(CPUS, prestates, strict=True)
        ],
        "regular_probe_definition": artifact("SYNTHETIC-REGULAR-DEFINITION", "3" * 64),
        "pointer_probe_definition": artifact("SYNTHETIC-POINTER-DEFINITION", "4" * 64),
        "apply_order": [0, 1, 26],
        "restore_order": [26, 1, 0],
        "quarantine_policy_id": "SYNTHETIC-QUARANTINE",
    }
    return value


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
    try:
        issued = dt.datetime.fromisoformat(document["issued_at_utc"].replace("Z", "+00:00"))
        expires = dt.datetime.fromisoformat(document["expires_at_utc"].replace("Z", "+00:00"))
        if expires <= issued:
            errors.append("expiry must follow issuance")
    except (KeyError, TypeError, ValueError):
        errors.append("timestamps must be parseable UTC values")

    authorities = list(document.get("authorities", {}).values())
    if len(authorities) != len(set(authorities)):
        errors.append("four operational identities must be distinct")
    custody = document.get("storage_custody", {})
    if custody.get("primary_domain_id") == custody.get("secondary_domain_id"):
        errors.append("custody domains must be distinct")
    if custody.get("output_root") == "/":
        errors.append("filesystem root cannot be an output root")
    if any(value.casefold() in FORBIDDEN_TOKENS for value in strings(document)):
        errors.append("wildcard/latest/current/unresolved/TBD token is forbidden")

    commands = document.get("permitted_commands", [])
    command_ids = [item.get("command_id") for item in commands]
    output_ids = [item.get("output_artifact_id") for item in commands]
    if len(command_ids) != len(set(command_ids)) or len(output_ids) != len(set(output_ids)):
        errors.append("command and output IDs must be unique")
    command_map = {item.get("command_id"): item for item in commands}
    phase = document.get("phase")
    kinds = {item.get("kind") for item in commands}
    inputs = document.get("phase_inputs", {})

    if phase == "Q15_R_READ_ONLY":
        if inputs.get("input_kind") != "Q15_R_INPUTS" or kinds != R_KINDS:
            errors.append("Q15-R requires the exact read-only evidence-kind set")
        if any(item.get("mutating") or item.get("privilege") == "WRITE_PRIVILEGED" for item in commands):
            errors.append("Q15-R cannot mutate or hold write privilege")
        if any(item.get("inverse_command_id") is not None for item in commands):
            errors.append("Q15-R cannot contain inverse mutation commands")
    elif phase == "Q15_W_APPLY_PROBE_RESTORE":
        if inputs.get("input_kind") != "Q15_W_INPUTS" or kinds != W_KINDS:
            errors.append("Q15-W requires the exact apply/readback/probe/restore kind set")
        prestates = inputs.get("prestates", [])
        if sorted(item.get("cpu") for item in prestates) != list(CPUS):
            errors.append("Q15-W requires one prestate for CPUs 0, 1, and 26")
        for item in prestates:
            try:
                prestate = int(item["prestate_hex"], 16)
                requested = int(item["h1_requested_hex"], 16)
                if requested != prestate | 0xF or requested == prestate:
                    errors.append("Q15-W prestate/request violates the exact H1 rule")
            except (KeyError, TypeError, ValueError):
                pass
        apply_order = inputs.get("apply_order", [])
        restore_order = inputs.get("restore_order", [])
        if sorted(apply_order) != list(CPUS) or restore_order != list(reversed(apply_order)):
            errors.append("Q15-W restore order must reverse one exact apply permutation")
        for kind in ("APPLY_H1_CPU", "INDEPENDENT_READBACK_H1_CPU", "RESTORE_H0_CPU", "INDEPENDENT_RESTORE_READBACK_CPU"):
            targets = sorted(item.get("exact_target") for item in commands if item.get("kind") == kind)
            expected = sorted(f"CPU:{cpu};MSR:000001a4" for cpu in CPUS)
            if targets != expected:
                errors.append(f"{kind} must target each fixed CPU exactly once")
        for item in commands:
            kind = item.get("kind")
            if kind in {"APPLY_H1_CPU", "RESTORE_H0_CPU"}:
                if not item.get("mutating") or item.get("role") != "OPERATOR" or item.get("privilege") != "WRITE_PRIVILEGED":
                    errors.append("Q15-W mutation must be an operator write command")
            elif item.get("mutating"):
                errors.append("only apply/restore commands may mutate")
            if kind == "APPLY_H1_CPU":
                inverse = command_map.get(item.get("inverse_command_id"))
                readback = command_map.get(item.get("independent_readback_command_id"))
                if inverse is None or inverse.get("kind") != "RESTORE_H0_CPU" or inverse.get("exact_target") != item.get("exact_target"):
                    errors.append("each apply command needs its exact inverse")
                if readback is None or readback.get("kind") != "INDEPENDENT_READBACK_H1_CPU" or readback.get("role") != "AUDITOR" or readback.get("exact_target") != item.get("exact_target"):
                    errors.append("each apply command needs auditor readback")
            if kind == "RESTORE_H0_CPU":
                readback = command_map.get(item.get("independent_readback_command_id"))
                if readback is None or readback.get("kind") != "INDEPENDENT_RESTORE_READBACK_CPU" or readback.get("role") != "AUDITOR" or readback.get("exact_target") != item.get("exact_target"):
                    errors.append("each restore command needs auditor readback")
    else:
        errors.append("unknown Q15 phase")
    return errors


def errors(validator: Draft202012Validator, document: dict[str, Any]) -> list[str]:
    result = [error.message for error in validator.iter_errors(document)]
    result.extend(semantic_errors(document))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", type=pathlib.Path)
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    schema_root = root / "config/schemas"
    if not (schema_root / "q15-qualification-authorization-v1.schema.json").is_file():
        schema_root /= "implementation"
    schema = json.loads((schema_root / "q15-qualification-authorization-v1.schema.json").read_text(encoding="utf-8"))
    preparation_schema = json.loads((schema_root / "q15-authorization-preparation-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator.check_schema(preparation_schema)
    validator = Draft202012Validator(schema)
    preparation_validator = Draft202012Validator(preparation_schema)

    if args.document is not None:
        try:
            document = json.loads(args.document.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"q15-authorization-check: FAIL: {error}", file=sys.stderr)
            return 1
        validation = errors(validator, document)
        if validation:
            for failure in validation:
                print(f"q15-authorization-check: FAIL: {failure}", file=sys.stderr)
            return 1
        print(f"q15-authorization-check: PASS phase={document['phase']} authority=VALIDATED_NOT_ISSUED")
        return 0

    positives = [q15_r(), q15_w()]
    for document in positives:
        if failures := errors(validator, document):
            print(f"q15-authorization-check: FAIL positive: {failures}", file=sys.stderr)
            return 1

    negatives: list[dict[str, Any]] = []
    mutation_in_r = copy.deepcopy(positives[0])
    mutation_in_r["permitted_commands"][0]["mutating"] = True
    negatives.append(mutation_in_r)
    overlap = copy.deepcopy(positives[0])
    overlap["authorities"]["auditor"] = overlap["authorities"]["operator"]
    negatives.append(overlap)
    wildcard = copy.deepcopy(positives[0])
    wildcard["permitted_commands"][0]["exact_target"] = "*"
    negatives.append(wildcard)
    no_q15_r = copy.deepcopy(positives[1])
    del no_q15_r["phase_inputs"]["q15_r_evidence_set"]
    negatives.append(no_q15_r)
    bad_prestate = copy.deepcopy(positives[1])
    bad_prestate["phase_inputs"]["prestates"][0]["h1_requested_hex"] = "123456789abcdefe"
    negatives.append(bad_prestate)
    wrong_restore = copy.deepcopy(positives[1])
    wrong_restore["phase_inputs"]["restore_order"] = [0, 1, 26]
    negatives.append(wrong_restore)
    missing_readback = copy.deepcopy(positives[1])
    missing_readback["permitted_commands"][0]["independent_readback_command_id"] = None
    negatives.append(missing_readback)
    probe_removed = copy.deepcopy(positives[1])
    probe_removed["permitted_commands"] = [item for item in probe_removed["permitted_commands"] if item["kind"] != "POINTER_STREAM_PROBE"]
    negatives.append(probe_removed)
    pilot = copy.deepcopy(positives[1])
    pilot["prohibitions"]["pilot_execution"] = True
    negatives.append(pilot)
    same_domain = copy.deepcopy(positives[0])
    same_domain["storage_custody"]["secondary_domain_id"] = same_domain["storage_custody"]["primary_domain_id"]
    negatives.append(same_domain)
    for index, document in enumerate(negatives):
        if not errors(validator, document):
            print(f"q15-authorization-check: FAIL negative {index} passed", file=sys.stderr)
            return 1

    preparations = [
        json.loads((root / "config/q15/q15-r.preparation.json").read_text(encoding="utf-8")),
        json.loads((root / "config/q15/q15-w.preparation.json").read_text(encoding="utf-8")),
    ]
    contract_path = root / "config/q15/q15-probe-collector-contract-v1.json"
    contract_hash = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    for document in preparations:
        preparation_validator.validate(document)
        known = document["known_inputs"]
        if (
            known.get("probe_collector_contract_id")
            != "Q15-PROBE-COLLECTOR-CONTRACT-v1"
            or known.get("probe_collector_contract_sha256") != contract_hash
        ):
            print(
                "q15-authorization-check: FAIL preparation contract binding",
                file=sys.stderr,
            )
            return 1
        if not list(validator.iter_errors(document)):
            print("q15-authorization-check: FAIL preparation validated as authority", file=sys.stderr)
            return 1
    authority_preparation = copy.deepcopy(preparations[0])
    authority_preparation["authority_issued"] = True
    if not list(preparation_validator.iter_errors(authority_preparation)):
        print("q15-authorization-check: FAIL authority-bearing preparation passed", file=sys.stderr)
        return 1
    print("q15-authorization-check: PASS (2 synthetic authorizations, 10 negative, 2 blocked preparations, no authority issued)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
