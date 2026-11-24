#!/usr/bin/env python3
"""Operator preparation only: exclusive typed records, no signing/admission/MSR I/O.

Run as the evidence owner. Uses ONLY the supplied admission root's CLI17,
release11 and operational15 implementation. Never import a legacy /tmp patch.
Each subcommand is a separate authoring step; main admits its output afterward.
"""
import argparse
import base64
import datetime
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import stat
import sys

PRINCIPAL = "maltsev.oiu@phystech.edu"
PUBLIC_FINGERPRINT = "SHA256:xfZMSZ4y67oGXkOvif318D6L1pi+vvlhUmNAxwxBxpU"
NAMESPACE = "stage17-owner-acceptance"
STAND = "CPU-PREFETCH-V5"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(document):
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def read(path, maximum=16777216):
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= maximum, "not a bounded regular input")
        chunks = []
        remaining = before.st_size + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)
        data = b"".join(chunks)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                and len(data) == before.st_size, "input changed while read")
        return data
    finally:
        os.close(fd)


def write(path, payload):
    data = payload if isinstance(payload, bytes) else canonical(payload)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        view = memoryview(data)
        while view:
            count = os.write(fd, view)
            require(count > 0, "exclusive output write stalled")
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def binding(identifier, path):
    data = read(path)
    return {"id": identifier, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def typed(role, identifier, measurements, sources):
    return {
        "schema_version": "cpu-prefetch-stage17-operational-typed-record/4",
        "record_id": identifier, "record_role": role, "subject_id": STAND,
        "source_bindings": sources, "measurements": measurements,
        "outcome": "VERIFIED", "recorded_at_utc": utc(),
        "synthetic_test_only": False, "phase18_authority": False,
    }


def runtime_measurements(provenance):
    p = provenance
    w = p["worker"]
    return {
        "bundle_profile": p["bundle_profile"], "source_revision": p["source_revision"],
        "bundle_manifest_sha256": p["bundle_manifest"]["sha256"],
        "sha256s_sha256": p["sha256s"]["sha256"],
        "sbom_sha256": p["sbom"]["sha256"], "inventory_sha256": p["inventory"]["sha256"],
        "worker_path": str(Path(p["bundle_root"]) / w["path"]),
        "worker_size_bytes": w["size_bytes"], "worker_sha256": w["sha256"],
        "worker_role": w["role"], "runtime_profile": w["runtime_profile"],
        "supported_actions": w["supported_actions"],
        "full_bundle_verifier_sha256": p["full_bundle_verifier"]["sha256"],
    }


def check_signers(data):
    lines = [line.split() for line in data.decode("ascii").splitlines() if line.strip() and not line.startswith("#")]
    require(len(lines) == 1 and len(lines[0]) == 3, "unexpected trusted allowed-signers shape")
    principal, algorithm, encoded = lines[0]
    require(principal == PRINCIPAL and algorithm == "ssh-ed25519", "trusted principal/key type differs")
    wire = base64.b64decode(encoded, validate=True)
    observed = "SHA256:" + base64.b64encode(hashlib.sha256(wire).digest()).decode().rstrip("=")
    require(observed == PUBLIC_FINGERPRINT, "public signer differs from existing admitted identity")


class Context:
    def __init__(self, args):
        self.args = args
        self.root = args.repository_root.resolve(strict=True)
        self.evidence = args.evidence_root.resolve(strict=True)
        self.bundle = args.bundle_root.resolve(strict=True)
        require(self.root == self.evidence / "admission-root", "use fresh private admission root")
        require(self.bundle.is_relative_to(self.evidence), "release extraction must remain within fresh evidence root")
        for path in (self.root, self.evidence, self.bundle):
            require(path.stat().st_uid == os.geteuid(), "run authoring as actual evidence owner")
        require(stat.S_IMODE(self.evidence.stat().st_mode) == 0o700, "evidence root must be 0700")
        self.prefix = args.id_prefix
        require(re.fullmatch("[A-Z0-9-]+", self.prefix) is not None, "unsafe artifact ID prefix")
        sys.path.insert(0, str(self.root / "tools"))
        entry = importlib.import_module("stage17_operational_cli_daycap_v4")
        entry.activate()
        self.base = entry.base
        self.release = importlib.import_module("stage17_pilot_candidate_artifact_v12")
        self.operational = importlib.import_module("stage17_operational_semantics_v16")
        for module in (entry, self.base, self.release, self.operational):
            require(Path(module.__file__).resolve().is_relative_to(self.root), "module escaped supplied admission root")
        self.common = dict(repository_root=self.root, evidence_root=self.evidence,
                           pilot_archive=args.pilot_archive.resolve(strict=True),
                           pilot_sidecar=args.pilot_sidecar.resolve(strict=True))
        self.validation = self.base.validate_journal(**self.common)

    def need(self, key):
        require(key in self.validation.resolutions, "missing admitted " + key)
        return self.validation.resolutions[key]

    def manifest(self, number, destination, specs):
        input_id = "S17-EXT-" + number
        self.base.author_operational_manifest(**self.common, input_id=input_id,
            manifest_id=self.prefix + "-EXT" + number + "-MANIFEST-1",
            artifact_specs=specs, stand_id=STAND, destination=destination)
        # Independent existing semantic checks before an informational custody receipt.
        self.operational.verify_manifest_v16(
            repository_root=self.root, manifest_path=destination,
            admitted_resolutions=self.validation.resolutions, expected_input_id=input_id,
            allow_synthetic=False, pinned_repository_bytes={})

    def custody(self, number, artifact):
        destination = self.evidence / "receipts" / ("ext" + number + "-custody-receipt-1.json")
        self.base.author_custody_receipt(
            repository_root=self.root, evidence_root=self.evidence,
            input_id="S17-EXT-" + number, artifact=artifact, sidecars=[],
            contract=self.root / "config/stage17/stage17-operational-input-external-contract-v2.json",
            custody_domain="CPU-PREFETCH-V5-OPERATIONAL", destination=destination)
        print(destination)


def archive_provenance(ctx):
    require(getattr(ctx.args, "archive_runtime_root", None) == Path("/"),
            "explicit actual stand archive-runtime-root / required")
    return ctx.release.build_extracted_release_receipt_v12(
        bundle_root=ctx.bundle, receipt_id=ctx.prefix + "-EXT002-PROVENANCE-1",
        archive_runtime_root=ctx.args.archive_runtime_root)


def ext002(ctx):
    ext1 = ctx.need("S17-EXT-001")
    require("S17-EXT-002" not in ctx.validation.resolutions, "EXT002 already admitted")
    contract = ext1.semantic_context["contract"]
    preflight = Path(contract["evidence_root"]).resolve(strict=True)
    require(preflight.is_relative_to(ctx.evidence), "preflight belongs to a different evidence root")
    require(Path(contract["pilot_candidate"]["bundle_root_locator"]).resolve() == ctx.bundle,
            "bundle differs from admitted preflight")
    output = ctx.evidence / "ext002-authoring-1"
    require(not output.exists(), "EXT002 authoring output already exists; retain it")
    trusted = json.loads(read(ctx.args.trusted_record))
    old = trusted["measurements"]
    require((old["principal"], old["signer_role"], old["reviewer_role"], old["sshsig_namespace"], old["stand_id"])
            == (PRINCIPAL, "OWNER", "OWNER", NAMESPACE, STAND), "historical trust fields differ")
    signers = read(Path(old["allowed_signers_path"]))
    require(len(signers) == old["allowed_signers_size_bytes"]
            and hashlib.sha256(signers).hexdigest() == old["allowed_signers_sha256"], "historical public trust bytes drifted")
    check_signers(signers)
    # Existing verifier recomputes release/inventory/code identity. No old release values copied.
    provenance = archive_provenance(ctx)
    require(provenance["synthetic_test_only"] is False, "synthetic release cannot author real evidence")
    # Ensure actual new observations and quiescence exist before authoring VERIFIED records.
    completion = json.loads(read(preflight / "stage17-read-only-preflight-completion-v7.json"))
    require(completion["all_leaders_reaped"] and completion["all_process_groups_gone"],
            "preflight quiescence absent")
    require(len(completion["completed_observation_ids"]) == 6, "preflight incomplete")
    for i in range(1, 7):
        receipt = json.loads(read(preflight / ("s17-ro-%03d.receipt-v7.json" % i)))
        require(receipt["ordinal"] == i and receipt["returncode"] == 0, "preflight observation failed")
        for stream in ("stdout", "stderr"):
            data = read(preflight / ("s17-ro-%03d.%s.bin" % (i, stream)))
            require(len(data) == receipt[stream + "_size_bytes"]
                    and hashlib.sha256(data).hexdigest() == receipt[stream + "_sha256"],
                    "preflight observation bytes differ")
    output.mkdir(mode=0o700)
    p = output / "ext002-runtime-release-provenance.json"
    write(p, provenance)
    signer_path = output / "ext002-allowed-signers"
    write(signer_path, signers)
    runtime_path = output / "ext002-runtime-identity.json"
    worker = ctx.bundle / provenance["worker"]["path"]
    # Worker bytes and size were checked by the existing release verifier.
    worker_source = {"id": "RUNTIME-WORKER-1", "size_bytes": provenance["worker"]["size_bytes"],
                     "sha256": provenance["worker"]["sha256"]}
    write(runtime_path, typed("RUNTIME_IDENTITY", ctx.prefix + "-EXT002-RUNTIME-1",
        runtime_measurements(provenance), [binding("RUNTIME-PROVENANCE-1", p), worker_source]))
    trust_path = output / "ext002-trust-anchor.json"
    trust_values = {key: old[key] for key in ("principal", "signer_role", "reviewer_role", "sshsig_namespace", "stand_id")}
    trust_values.update(
        allowed_signers_path=str(signer_path), allowed_signers_size_bytes=len(signers),
        allowed_signers_sha256=hashlib.sha256(signers).hexdigest(),
        stand_anchor_sha256=contract["target"]["pinned_host_key_evidence"]["sha256"])
    write(trust_path, typed("TRUST_ANCHOR", ctx.prefix + "-EXT002-TRUST-1",
                           trust_values, [binding("TRUST-SIGNERS-1", signer_path)]))
    specs = [
        "PREFLIGHT_ATTEMPT:EXT002-PREFLIGHT-ATTEMPT-1=" + str(preflight / "stage17-read-only-preflight-attempt-v10.json"),
        "PREFLIGHT_COMPLETION:EXT002-PREFLIGHT-COMPLETION-1=" + str(preflight / "stage17-read-only-preflight-completion-v7.json"),
        "RUNTIME_IDENTITY:EXT002-RUNTIME-IDENTITY-1=" + str(runtime_path),
        "RUNTIME_RELEASE_PROVENANCE:RUNTIME-PROVENANCE-1=" + str(p),
        "RUNTIME_WORKER_BINARY:RUNTIME-WORKER-1=" + str(worker),
        "TRUST_ANCHOR:EXT002-TRUST-ANCHOR-1=" + str(trust_path),
        "TRUST_ALLOWED_SIGNERS:TRUST-SIGNERS-1=" + str(signer_path),
    ]
    for i in range(1, 7):
        path = preflight / ("s17-ro-%03d.receipt-v7.json" % i)
        document = json.loads(read(path))
        specs.append("PREFLIGHT_OBSERVATION_RECEIPT:EXT002-PREFLIGHT-RECEIPT-%d=%s" % (i, path))
        for stream in ("stdout", "stderr"):
            specs.append("PREFLIGHT_%s:%s-%s=%s" % (
                stream.upper(), document["observation_id"], stream.upper(),
                preflight / ("s17-ro-%03d.%s.bin" % (i, stream))))
    manifest = ctx.evidence / "ext002-manifest-1.json"
    ctx.manifest("002", manifest, specs)
    ctx.custody("002", manifest)


def ext003(ctx):
    ext2 = ctx.need("S17-EXT-002")
    require("S17-EXT-003" not in ctx.validation.resolutions, "EXT003 already admitted")
    directory = ctx.root / "evidence" / "ext003-fresh"
    directory.mkdir(mode=0o700)
    facts = ext2.semantic_context
    values = {key: facts[key] for key in (
        "runtime_record_sha256", "trust_record_sha256", "runtime_release_provenance_sha256")}
    values.update(ext002_resolution_id=ext2.resolution_id, ext002_resolution_sha256=ext2.sha256,
                  distinct_auditor=False, independent_review=False, role_collapse_accepted=True)
    source = binding(ext2.resolution_id, ext2.path)
    require(source["sha256"] == ext2.sha256, "EXT002 resolution drift")
    path = directory / "ext003-owner-acceptance.json"
    write(path, typed("OWNER_ACCEPTANCE", ctx.prefix + "-EXT003-ACCEPTANCE-1", values, [source]))
    manifest = directory / "ext003-manifest-1.json"
    ctx.manifest("003", manifest, ["OWNER_ACCEPTANCE:EXT003-OWNER-ACCEPTANCE-1=" + str(path)])
    print(manifest)


def ext006(ctx):
    ctx.need("S17-EXT-003")
    require("S17-EXT-006" not in ctx.validation.resolutions, "EXT006 already admitted; do not append another")
    path = ctx.evidence / "manifests" / "ext006-contract-1.json"
    ctx.base.author_ext006_contract(
        repository_root=ctx.root, archive=ctx.common["pilot_archive"], sidecar=ctx.common["pilot_sidecar"],
        primary_custody_domain="CPU-PREFETCH-V5-RELEASE-PRIMARY",
        secondary_custody_domain="CPU-PREFETCH-V5-RELEASE-SECONDARY",
        contract_id=ctx.prefix + "-EXT006-CONTRACT-1", destination=path)
    ctx.custody("006", path)


def size_bytes(text):
    match = re.fullmatch(r"([0-9]+)([KMG]?)", text.strip())
    require(match is not None, "unrecognized sysfs cache size")
    return int(match[1]) * {"": 1, "K": 1024, "M": 1048576, "G": 1073741824}[match[2]]


def q15r(ctx):
    ctx.need("S17-EXT-003")
    ctx.need("S17-EXT-006")
    require(ctx.args.probe_cpu == 0, "this existing qualification recipe selects accepted CPU0")
    cpu_root = Path("/sys/devices/system/cpu/cpu0")
    nodes = sorted(cpu_root.glob("node[0-9]*"))
    require(len(nodes) == 1, "CPU0 node readback is not unique")
    cache = []
    raw = {}
    for directory in sorted((cpu_root / "cache").glob("index*")):
        level = (directory / "level").read_text().strip()
        kind = (directory / "type").read_text().strip()
        if level == "3" and kind == "Unified":
            text = (directory / "size").read_text()
            cache.append(size_bytes(text))
            raw[str(directory / "size")] = text
            raw[str(directory / "level")] = level
            raw[str(directory / "type")] = kind
    require(len(cache) == 1, "CPU0 unified LLC readback is not unique")
    node = int(nodes[0].name[4:])
    page = os.sysconf("SC_PAGE_SIZE")
    require(node == 0 and page == 4096, "observed CPU0 placement/page size differs from accepted Q15 binding")
    binding_values = {"cpu": 0, "numa_node": node,
                      "verified_base_page_bytes": page, "verified_local_llc_bytes": cache[0]}
    document = {"qualification_id": ctx.prefix + "-Q15R-QUAL-1",
                "attempt_id": ctx.prefix + "-Q15R-ATTEMPT-1",
                "session_id": ctx.prefix + "-Q15-SESSION-1",
                "probe_platform_binding": binding_values}
    readback = {"recorded_at_utc": utc(), "cpu_node_symlink": str(nodes[0]),
                "cpu_node_resolved": str(nodes[0].resolve()), "sysconf_page_size": page,
                "raw_sysfs": raw, "derived_binding": binding_values}
    for name in ("q15-probe-binding-readback.json", "q15r-action-inputs-1.json"):
        require(not (ctx.evidence / name).exists(), "Q15-R input/readback already exists")
    write(ctx.evidence / "q15-probe-binding-readback.json", readback)
    path = ctx.evidence / "q15r-action-inputs-1.json"
    write(path, document)
    print(path)


def bound_artifact(manifest_path, manifest, role):
    matches = [item for item in manifest["artifacts"] if item["role"] == role]
    require(len(matches) == 1, "admitted role missing or duplicate: " + role)
    item = matches[0]
    path = (manifest_path.parent / item["locator"]).resolve(strict=True)
    require(path.is_relative_to(manifest_path.parent.resolve()), "artifact escaped manifest directory")
    data = read(path)
    require(len(data) == item["size_bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"],
            "admitted artifact bytes drifted: " + role)
    return json.loads(data), hashlib.sha256(data).hexdigest()


def q15w(ctx):
    ext4 = ctx.need("S17-EXT-004")
    path = Path(ext4.semantic_context["manifest_path"])
    data = read(path)
    require(hashlib.sha256(data).hexdigest() == ext4.semantic_context["manifest_sha256"], "EXT004 manifest drift")
    manifest = json.loads(data)
    request, _ = bound_artifact(path, manifest, "Q15_R_REQUEST")
    attempt, attempt_hash = bound_artifact(path, manifest, "Q15_R_ATTEMPT")
    result, result_hash = bound_artifact(path, manifest, "Q15_R_RESULT")
    prestate, _ = bound_artifact(path, manifest, "Q15_R_READ_ONLY_PRESTATE")
    session = request["session_id"]
    require(request["action_inputs"]["session_id"] == session, "Q15-R session identity differs")
    require(attempt["attempt_id"] == request["attempt_id"], "Q15-R attempt differs")
    require(result["action_id"] == "Q15-R", "result is not Q15-R")
    document = {"session_id": session, "q15_r_attempt_sha256": attempt_hash,
                "q15_r_result_sha256": result_hash, "prestate": prestate["prestate"]}
    destination = ctx.evidence / "q15w-action-inputs-1.json"
    write(destination, document)
    print(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("ext002", "ext003", "ext006", "q15r-inputs", "q15w-inputs"))
    for name in ("repository-root", "evidence-root", "bundle-root", "pilot-archive", "pilot-sidecar"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--id-prefix", required=True)
    parser.add_argument("--archive-runtime-root", type=Path)
    parser.add_argument("--trusted-record", type=Path)
    parser.add_argument("--probe-cpu", type=int)
    args = parser.parse_args()
    if args.command == "ext002":
        require(args.trusted_record is not None, "--trusted-record required")
    context = Context(args)
    {"ext002": ext002, "ext003": ext003, "ext006": ext006,
     "q15r-inputs": q15r, "q15w-inputs": q15w}[args.command](context)
    print("AUTHORING ONLY: no signature, journal admission, qualification or MSR operation performed")


if __name__ == "__main__":
    main()
