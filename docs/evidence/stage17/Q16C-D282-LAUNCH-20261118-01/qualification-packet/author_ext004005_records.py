#!/usr/bin/env python3
"""Local preparation helper; main runs only after actual captures exist.

No capture, signing, hardware access or admission. Uses existing semantic checks.
EXT004 accepts five existing-tool envelopes and observed platform facts explicitly.
"""
import argparse
import json
from pathlib import Path
from author_fresh_qualification_records import Context, read, write, binding, typed, require

KINDS = ("RUNTIME_ATOMIC_LAYOUT", "ACTUAL_CPU_MIGRATION", "ADDRESS_RESIDENCY",
         "SOFTWARE_PREFETCH_MAPPING", "SELECTED_PAIR_CLOCK")


def load(path):
    return json.loads(read(path))


def family(ctx, action):
    tag = "q15r" if action == "Q15-R" else "q15w"
    directory = ctx.root / "evidence" / (tag + "-fresh")
    request_path = directory / "request.json"
    request = load(request_path)
    require(request["action_id"] == action, "wrong action request")
    output = Path(request["evidence_root_binding"]["absolute_path"]).resolve(strict=True)
    require(output.is_relative_to(ctx.evidence), "output outside fresh evidence root")
    prefix = action.replace("-", "_")
    result_path = output / ("stage17-" + action.lower() + "-result-v4.json")
    result = load(result_path)
    require(result["action_id"] == action and result["attempt_id"] == request["attempt_id"],
            "result action/attempt differs")
    require(result["request_sha256"] == binding("REQUEST", request_path)["sha256"],
            "result request binding differs")
    paths = {
        prefix + "_REQUEST": request_path,
        prefix + "_AUTHORIZATION": directory / "authorization.json",
        prefix + "_SIGNATURE": directory / "authorization.json.sig",
        prefix + "_ATTEMPT": output / ("stage17-" + prefix.lower() + "-attempt-v4.json"),
        prefix + "_RESULT": result_path,
    }
    if action == "Q15-R":
        paths["Q15_R_SESSION_WAITING"] = output / "stage17-q15-session-waiting-v1.json"
    else:
        paths["Q15_W_COMPLETION"] = output / "stage17-q15_w-completion-v4.json"
    for item in result["artifacts"]:
        role = item["role"]
        require(role not in paths, "duplicate result role")
        path = (output / item["file_name"]).resolve(strict=True)
        require(path.parent == output, "result artifact escaped output root")
        observed = binding(role, path)
        require((observed["sha256"], observed["size_bytes"])
                == (item["sha256"], item["size_bytes"]), "result raw artifact drift")
        paths[role] = path
    return request, result, paths


def artifact_id(ctx, number, role):
    return ctx.prefix + "-EXT" + number + "-" + role.replace("_", "-")


def specs(ctx, number, paths):
    return [role + ":" + artifact_id(ctx, number, role) + "=" + str(path)
            for role, path in paths.items()]


def h0_record(ctx, request, result, raw, raw_path):
    # Existing ADR0150's H0 preserve/no-write convention, lines1727-1744.
    # These fields do NOT assert a measured H1 apply/restore transaction.
    require(raw["read_only"] is True and raw["complete"] is True, "incomplete/non-readonly Q15-R")
    require(raw["session_id"] == request["session_id"], "raw session differs")
    schema = load(ctx.root / "config/schemas/hardware-prefetch-qualification-v1.schema.json")
    properties = schema["properties"]
    require(raw["mapping_id"] in properties["mapping_id"]["enum"], "mapping unregistered")
    def probe(name):
        observation = raw[name]
        passed = (observation["cpu_verified"] and observation["residency_verified"]
                  and observation["integrity_verified"] and observation["minor_faults"] == 0
                  and observation["major_faults"] == 0)
        require(passed, "Q15-R probe failed")
        return {"artifact_id": artifact_id(ctx, "004", "Q15_R_READ_ONLY_PRESTATE"),
                "sha256": binding("RAW", raw_path)["sha256"], "passed": passed}
    return dict(schema_version=properties["schema_version"]["const"],
        protocol_version=properties["protocol_version"]["const"], mapping_id=raw["mapping_id"],
        artifact_id=artifact_id(ctx, "004", "HARDWARE_PREFETCH_QUALIFICATION"),
        stand_id=result["stand_id"], binding_id=request["request_id"],
        source_revision=ctx.need("S17-EXT-003").semantic_context["release"].source_revision,
        command_sha256=result["request_sha256"], captured_at_utc=result["completed_at_utc"],
        execution_state="COMPLETE", requested_state="H0", cpu_family_hex=format(raw["cpu_family"], "02x"),
        cpu_model_hex=format(raw["cpu_model"], "02x"), msr_hex=properties["msr_hex"]["const"],
        disable_mask_hex=properties["disable_mask_hex"]["const"],
        cpu_values=[dict(cpu=item["cpu"], prestate_hex=item["complete_value_hex"],
            requested_hex=item["complete_value_hex"], apply_readback_hex=item["complete_value_hex"],
            restore_readback_hex=item["complete_value_hex"]) for item in raw["prestate"]],
        regular_probe=probe("regular_probe"), pointer_probe=probe("pointer_probe"),
        applied=False, verified=True, restored=True, quarantined=False, eligible=True)


def ext004(ctx):
    ctx.need("S17-EXT-006")
    require("S17-EXT-004" not in ctx.validation.resolutions, "EXT004 already admitted")
    request, result, paths = family(ctx, "Q15-R")
    require(result["terminal_state"] == "Q15_R_READ_ONLY_COMPLETE" and not result["quarantined"],
            "Q15-R did not complete")
    facts = load(ctx.args.platform_facts)
    require(set(facts) == {"cpu", "topology", "memory", "software", "clock",
                          "topology_evidence", "cache_capacity_evidence"}, "platform facts fields differ")
    # This is a required observed input, not a prefilled historical template.
    output = ctx.evidence / "ext004-authoring-records-1"
    output.mkdir(mode=0o700)
    write(output / "platform-facts-input.json", read(ctx.args.platform_facts))
    raw_path = paths["Q15_R_READ_ONLY_PRESTATE"]
    raw = load(raw_path)
    atomic = load(paths["Q15_R_ATOMIC_LAYOUT_RAW"])
    residency = load(paths["Q15_R_ADDRESS_RESIDENCY_RAW"])
    require(facts["cpu"]["model"] == "%02X_%02XH" % (raw["cpu_family"], raw["cpu_model"]),
            "platform model differs from actual Q15 CPUID")
    require(facts["cpu"]["cache_line_bytes"] == atomic["cache_line_bytes"]
            and facts["cpu"]["atomic_width_bits"] == 8 * atomic["pointer_atomic_width_bytes"]
            and facts["cpu"]["atomic_alignment_bytes"] == atomic["pointer_atomic_alignment_bytes"],
            "platform atomic facts differ from raw")
    require(facts["memory"]["base_page_bytes"] == request["action_inputs"]["probe_platform_binding"]["verified_base_page_bytes"]
            and facts["memory"]["residency_verification_method"] == residency["mechanism_id"],
            "platform memory facts differ from actual Q15 binding/raw")
    platform = {key: facts[key] for key in ("cpu", "topology", "memory", "software", "clock")}
    platform.update(schema_version="2.0.0-pre.3", protocol_version="2.0.0-pre.3",
        platform_id=result["stand_id"], record_sha256=binding("RESULT", paths["Q15_R_RESULT"])["sha256"],
        hardware_prefetch_states=[dict(requested=state, verified=verified,
            readback_artifact_id=artifact_id(ctx, "004", "Q15_R_READ_ONLY_PRESTATE"),
            behavioral_probe_artifact_id=artifact_id(ctx, "004", "Q15_R_READ_ONLY_PRESTATE"),
            privileged_authority_id=request["authorization_id"] if state == "H0" else "NONE")
            for state, verified in (("H0", "VERIFIED_DEFAULT"), ("H1", "UNKNOWN"))])
    paths["PLATFORM_MANIFEST"] = output / "platform-manifest.json"
    write(paths["PLATFORM_MANIFEST"], platform)
    paths["HARDWARE_PREFETCH_QUALIFICATION"] = output / "hardware-prefetch-qualification.json"
    write(paths["HARDWARE_PREFETCH_QUALIFICATION"], h0_record(ctx, request, result, raw, raw_path))
    measurements = {key: facts[key] for key in ("topology_evidence", "cache_capacity_evidence")}
    measurements.update(platform_manifest_sha256=binding("PLATFORM", paths["PLATFORM_MANIFEST"])["sha256"],
                        q15_r_result_sha256=binding("RESULT", paths["Q15_R_RESULT"])["sha256"])
    paths["PILOT_PLATFORM_MEASUREMENTS"] = output / "pilot-platform-measurements.json"
    write(paths["PILOT_PLATFORM_MEASUREMENTS"], typed("PILOT_PLATFORM_MEASUREMENTS",
        artifact_id(ctx, "004", "PILOT_PLATFORM_MEASUREMENTS"), measurements,
        [binding(artifact_id(ctx, "004", role), paths[role])
         for role in ("PLATFORM_MANIFEST", "Q15_R_RESULT")]))
    entries = specs(ctx, "004", paths)
    for kind in KINDS:
        path = (ctx.args.qualification_directory / (kind + ".json")).resolve(strict=True)
        envelope = load(path)
        require(envelope["kind"] == kind and envelope["eligible"] is True, "qualification incomplete")
        raw_roles = {"RUNTIME_ATOMIC_LAYOUT": "Q15_R_ATOMIC_LAYOUT_RAW",
                     "ACTUAL_CPU_MIGRATION": "Q15_R_CPU_MIGRATION_RAW",
                     "ADDRESS_RESIDENCY": "Q15_R_ADDRESS_RESIDENCY_RAW",
                     "SOFTWARE_PREFETCH_MAPPING": "Q15_R_SOFTWARE_PREFETCH_RAW"}
        if kind in raw_roles:
            role = raw_roles[kind]
            require(envelope["sources"] == [{"artifact_id": artifact_id(ctx, "004", role),
                "sha256": binding("RAW", paths[role])["sha256"]}], "envelope raw source differs")
            require(envelope["binary_sha256"] == result["runtime_binding"]["sha256"]
                    and envelope["source_revision"] == ctx.need("S17-EXT-003").semantic_context["release"].source_revision
                    and envelope["captured_at_utc"] == result["completed_at_utc"],
                    "envelope belongs to a different release/capture")
        entries.append("QUALIFICATION_EVIDENCE:" + envelope["artifact_id"] + "=" + str(path))
    manifest = ctx.evidence / "ext004-manifest-1.json"
    ctx.manifest("004", manifest, entries)
    ctx.custody("004", manifest)


def ext005(ctx):
    ctx.need("S17-EXT-004")
    require("S17-EXT-005" not in ctx.validation.resolutions, "EXT005 already admitted")
    _, _, paths = family(ctx, "Q15-W")
    manifest = ctx.evidence / "ext005-manifest-1.json"
    ctx.manifest("005", manifest, specs(ctx, "005", paths))
    ctx.custody("005", manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("ext004", "ext005"))
    for name in ("repository-root", "evidence-root", "bundle-root", "pilot-archive", "pilot-sidecar"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--id-prefix", required=True)
    parser.add_argument("--platform-facts", type=Path)
    parser.add_argument("--qualification-directory", type=Path)
    args = parser.parse_args()
    if args.command == "ext004":
        require(args.platform_facts is not None and args.qualification_directory is not None,
                "actual platform facts and five existing-tool envelopes required")
    ctx = Context(args)
    {"ext004": ext004, "ext005": ext005}[args.command](ctx)
    print("AUTHORING ONLY: no capture/signature/admission/hardware operation")


if __name__ == "__main__":
    main()
