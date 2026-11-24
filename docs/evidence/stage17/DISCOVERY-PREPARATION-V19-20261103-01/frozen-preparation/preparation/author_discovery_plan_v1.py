#!/usr/bin/env python3
"""Prep-only D178 authoring from retained v19 facts and readonly worker layout.

Never signs, admits, collects observations or executes a discovery action.
Output is a prospective plan, not an assertion of resource/rate sufficiency.
Invoke under the accepted offline runtime; --help describes required inputs.
All writes are exclusive, below the explicitly selected NEW output directory.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from check_canonical import canonicalize
import stage17_discovery_contract_v1 as contract
import stage17_phase_controller_v22 as controller
from stage17_q16a_discovery_v1 import CONTEXTS, required_captures
from jsonschema import Draft202012Validator

GIB = 1 << 30
MIB = 1 << 20
NS = 1_000_000_000
PREFIX = "CPU-PREFETCH-V5-V19-D178"
NAMESPACES = {"warmup": PREFIX + "-WARMUP-1", "measurement": PREFIX + "-MEASUREMENT-1"}
CAPACITIES = dict(L2_RESIDENT=1024, LLC_RESIDENT=131072, BEYOND_LLC=8388608)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def loads(data):
    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))


def load(path):
    return loads(path.read_bytes())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(document):
    return canonicalize(document).encode("utf-8")


def binding(artifact_id, payload):
    return dict(artifact_id=artifact_id, size_bytes=len(payload), sha256=sha(payload))


def file_binding(path):
    return dict(path=str(path.resolve()), size_bytes=path.stat().st_size,
                sha256=sha(path.read_bytes()))


def write(path, document):
    with path.open("xb") as stream:
        stream.write(canonical(document))


def identity(phase, ordinal):
    run_id = f"D178{'W' if phase == 'warmup' else 'M'}26N03{ordinal:02d}"
    require(len(run_id.encode("ascii")) == 12, "run ID length drift")
    namespace = NAMESPACES[phase]
    # Exact, recorded domain-separated UTF-8 seed label. No clock/random input.
    label = namespace + "/" + run_id
    return dict(run_id=run_id, seed_id=namespace + f"-SEED-{ordinal:02d}",
                seed_hex=sha(label.encode("ascii")), namespace_id=namespace)


def environment_sources(inventory):
    sources, excluded, seen = [], [], set()
    for item in inventory["files"]:
        path = item["path"]
        require(path not in seen and path.startswith("/") and "\0" not in path,
                "duplicate/invalid inventory path")
        seen.add(path)
        if "error" in item:
            excluded.append(dict(path=path, reason="INVENTORY_READ_ERROR", error=item["error"]))
            continue
        raw = item["text"].encode("utf-8", errors="strict")
        require(type(item["size_bytes"]) is int and
                (len(raw), sha(raw)) == (item["size_bytes"], item["sha256"]),
                "inventory exact bytes drift: " + path)
        if pathlib.PurePosixPath(path).name == "cgroup.procs":
            excluded.append(dict(path=path, reason="DYNAMIC_PROCESS_IDS_EXCLUDED_BY_PROSPECTIVE_PLAN"))
            continue
        capacity = 2 * MIB if path == "/proc/self/smaps" else (
            (max(4096, 4 * len(raw) + 4096) + 4095) // 4096 * 4096)
        sources.append(dict(path=path, byte_capacity=capacity, chunk_bytes=4096,
                            max_data_reads=capacity // 4096 + 16, requested=[True] * 6))
    require(any(s["path"] == "/proc/self/smaps" for s in sources), "readable smaps is required")
    return sorted(sources, key=lambda x: x["path"]), excluded


def check_manifest(root, path):
    document = load(path)
    require(document["synthetic_test_only"] is False, "synthetic qualification manifest")
    for item in document["artifacts"]:
        local = (root / item["locator"]).resolve(strict=True)
        require(local.is_relative_to(root), "manifest path escaped snapshot")
        payload = local.read_bytes()
        require((len(payload), sha(payload)) == (item["size_bytes"], item["sha256"]),
                "manifest artifact drift: " + item["role"])
    return document


def check_receipt(root, resolution, target):
    matches = []
    for entry in resolution["evidence"]:
        if entry["kind"] != "EXTERNAL_CUSTODY_RECEIPT":
            continue
        data = (root / entry["receipt_path"]).read_bytes()
        require((len(data), sha(data)) == (entry["receipt_size_bytes"], entry["receipt_sha256"]),
                "resolution receipt bytes drift")
        receipt = loads(data)
        if (receipt["artifact_size_bytes"], receipt["artifact_sha256"]) == (
                target.stat().st_size, sha(target.read_bytes())):
            matches.append(receipt)
    require(len(matches) == 1, "target not bound by exact resolution receipt")


def load_bound_model(path):
    spec = importlib.util.spec_from_file_location("d178_publication_bound_model", path)
    model = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = model
    spec.loader.exec_module(model)
    return model


def modeled_control(model, capture, resource, monitoring):
    """Parameterize existing symbolic serializer envelope; never allocate rows.

    Separate raw/metadata budgets deliberately do not borrow correlated savings.
    Integer maxima are type-width envelopes, not fabricated observations.
    """
    q = capture["geometry"]["capacity"]
    counts = [min(q, capture["budget"][p + "_attempt_capacity"]) + 1
              for p in ("warmup", "measurement")]
    require(capture["geometry"]["base_page_bytes"] == 4096,
            "existing symbolic page envelope requires verified 4096 base pages")
    doc = model.control(dict(layout=resource), counts)
    doc["arena"]["ordered_index_error"] = "ordered-index input must be a complete permutation"
    doc["arena"]["address_delta_error"] = "ordered-index input must be a complete permutation"
    preparations, samples = [], []
    for index, source in enumerate(monitoring["environment_sources"]):
        preparation = copy.deepcopy(model.ENV_PREP)
        preparation["plan"] = dict(path_bytes=list(source["path"].encode("utf-8")),
            **{k: source[k] for k in ("byte_capacity", "chunk_bytes", "max_data_reads", "requested")})
        preparations.append(preparation)
        sample = copy.deepcopy(model.ENV_SAMPLE)
        sample["raw_bytes"] = model.Repeat(255, source["byte_capacity"])
        sample["reads"] = model.Repeat(model.FILE_READ, source["max_data_reads"])
        samples.extend([sample] * 6)
    doc["environment_preparations"] = preparations
    doc["environment_samples"] = samples
    # These controls are explicitly selected, so the historical envelope's
    # thread/TLS shapes must match rather than silently undercounting a change.
    require((resource["tls_module_capacity"], resource["thread_stat_bytes"],
             resource["thread_status_bytes"], resource["thread_affinity_words"]) == (8, 4096, 4096, 4),
            "thread/TLS controls differ from symbolic envelope")
    metadata = model.size(doc)
    spool = sum(model.size(model.Repeat(model.CONSUMER, n)) for n in counts)
    return metadata, spool


def build(args):
    root = args.snapshot_root.resolve(strict=True)
    bundle = args.bundle_root.resolve(strict=True)
    destination = args.output_directory.resolve()
    require(not destination.exists(), "output directory must be NEW (no overwrites)")
    inventory = load(args.inventory)
    custody = load(args.pc_custody_preparation)
    require(custody["path"] == str(args.pc_custody_path.resolve()) and
            custody["available_bytes"] == args.pc_free_bytes and
            custody["probe"]["write_fsync_readback_verified"] is True,
            "PC custody record/path/free-space mismatch")
    sources, excluded = environment_sources(inventory)
    records = {}
    for path in sorted((root / "records").glob("resolution-*.json")):
        document = load(path)
        key = document["input_id"]
        require(key not in records and document["verification_result"] == "PASS", "duplicate/nonpassing resolution")
        records[key] = (path, document)
    require(set(records) == {f"S17-EXT-{i:03d}" for i in range(1, 7)}, "exact actual EXT001..006 required")
    release_path = root / "manifests/ext006-contract-1.json"
    release = load(release_path)
    check_receipt(root, records["S17-EXT-006"][1], release_path)
    worker = bundle / release["worker"]["member_path"]
    worker_bytes = worker.read_bytes()
    require((len(worker_bytes), sha(worker_bytes)) == (release["worker"]["size_bytes"], release["worker"]["sha256"]),
            "current release worker bytes differ")
    require(release["worker"]["member_path"] == "release/bin/cpu_prefetch_runner", "wrong worker role/path")
    anchor_path = root / "admission-root/evidence/ext001-v5-19/pinned-host-key-evidence-v1.json"
    anchor = load(anchor_path)
    trust = load(root / "ext002-authoring-1/ext002-trust-anchor.json")
    require(trust["measurements"]["stand_anchor_sha256"] == sha(anchor_path.read_bytes()),
            "stand anchor differs from retained admitted trust")
    qualification_path = root / "ext004-manifest-1.json"
    qualification = check_manifest(root, qualification_path)
    check_receipt(root, records["S17-EXT-004"][1], qualification_path)
    check_manifest(root, root / "ext005-manifest-1.json")
    check_receipt(root, records["S17-EXT-005"][1], root / "ext005-manifest-1.json")
    facts_path = root / "platform-facts-1.json"
    facts = load(facts_path)
    admitted_platform = load(root / "ext004-authoring-records-1/platform-manifest.json")
    require(all(facts[k] == admitted_platform[k] for k in ("cpu", "topology", "memory", "software", "clock")),
            "platform facts differ from manifest-bound qualification platform")
    platform_path = root / "platform-inventory-1.json"
    platform = load(platform_path)
    for name in ("topology_evidence", "cache_capacity_evidence"):
        b = facts[name]["snapshot"]
        require((platform_path.stat().st_size, sha(platform_path.read_bytes())) == (b["size_bytes"], b["sha256"]),
                "actual topology/cache inventory binding differs")
    cpus = {item["cpu"]: item for item in platform["cpus"]}
    topo = facts["topology_evidence"]
    page = facts["memory"]["base_page_bytes"]
    line = facts["cpu"]["cache_line_bytes"]
    require(facts["cpu"]["model"] == "06_3EH", "v19 hardware model differs")
    require(args.controller_cpu in cpus, "controller CPU absent from actual inventory")
    wrequest_path = root / "admission-root/evidence/q15w-fresh/request.json"
    wrequest = load(wrequest_path)
    wresult_path = root / "stage17-q15-w-result-v4.json"
    wresult = load(wresult_path)
    require(wresult["terminal_state"] == "Q15_W_RESTORED_COMPLETE" and
            wresult["restoration_verified"] is True and wresult["quarantined"] is False and
            wresult["synthetic_test_only"] is False, "actual restored Q15W is required")
    require(wresult["request_sha256"] == sha(wrequest_path.read_bytes()), "Q15W request binding differs")
    winputs = load(root / "q15w-action-inputs-1.json")
    require(winputs == wrequest["action_inputs"], "actual Q15W inputs differ")
    prestate = winputs["prestate"]
    rraw = load(root / "q15-r-output-v3.json")
    require(rraw["prestate"] == prestate and rraw["mapping_id"] == "INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1",
            "actual Q15R/Q15W mapping or prestate mismatch")
    hardware = dict(mapping_id="INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1",
                    q15_w_result_sha256=sha(wresult_path.read_bytes()), prestate=prestate)
    require(len(prestate) == 3, "existing symbolic MSR envelope requires actual three CPUs")
    controller.predecessor.registry.validate_hardware_control(hardware)
    require(anchor["stand_id"] == qualification["stand_id"] == wresult["stand_id"], "stand identities differ")
    model_path = ROOT / "build/ext007-runtime-20261101/discovery-publication-bound.py"
    model = load_bound_model(model_path)
    captures, resources, monitoring, layout_records, bounds = [], [], [], [], []
    destination.mkdir(parents=True)
    (destination / "layout-inputs").mkdir()
    (destination / "layouts").mkdir()
    for ordinal, key in enumerate(required_captures()):
        state, placement, working_set = CONTEXTS[key.context_ordinal]
        side = placement.lower()
        geometry = dict(producer_cpu=topo["producer_cpu"], consumer_cpu=topo[side + "_consumer_cpu"],
            producer_node=topo["producer_numa_node"], consumer_node=topo[side + "_consumer_numa_node"],
            shared_node=topo["producer_numa_node"], capacity=CAPACITIES[working_set],
            cache_line_bytes=line, base_page_bytes=page)
        for role in ("producer", "consumer"):
            actual = cpus[geometry[role + "_cpu"]]
            require(actual["node"] == geometry[role + "_node"], "actual CPU/node relationship differs")
            require((actual["package"], actual["core"]) !=
                    (cpus[args.controller_cpu]["package"], cpus[args.controller_cpu]["core"]),
                    "controller shares worker physical core")
        measurement_capacity = (1_000_000, 4_000_000, 5_000_000)[ordinal % 3]
        raw = 264 * (5_000_000 + measurement_capacity)  # 12-byte IDs -> 16-byte prefixes
        budget = dict(setup_ns=120 * NS, drain_ns=30 * NS, publication_ns=1800 * NS,
            cleanup_ns=120 * NS, watchdog_ns=2105 * NS + key.duration_ns,
            warmup_attempt_capacity=5_000_000, measurement_attempt_capacity=measurement_capacity,
            drain_attempt_capacity=geometry["capacity"] + 1, barrier_poll_limit=10**12,
            memory_bytes=224 * GIB, retained_output_bytes=raw,
            metadata_output_bytes=1, max_output_bytes=raw + 1)
        cap = dict(ordinal=ordinal, context_ordinal=key.context_ordinal, hardware_state=state,
            placement=placement, working_set_class=working_set, warmup_ns=5 * NS,
            measurement_ns=key.duration_ns, warmup=identity("warmup", ordinal),
            measurement=identity("measurement", ordinal),
            arena_seed=identity("measurement", ordinal),
            seed_use="ONE_PERSISTENT_ARENA_MEASUREMENT_SEED_WARMUP_RESERVED_NO_DRAWS",
            geometry=geometry, budget=budget)
        def stack(cpu):
            return dict(bytes=2 * MIB, verified_base_page_bytes=page,
                        owner_cpu=cpu, requested_node=cpus[cpu]["node"])
        # Zero sizes are ONLY ignored fields in the readonly describe input.
        # They never enter the completed plan/action inputs.
        resource = dict(ordinal=ordinal, workers=dict(producer_stack=stack(geometry["producer_cpu"]),
            consumer_stack=stack(geometry["consumer_cpu"])), controller_stack=stack(args.controller_cpu),
            core_bytes=0, monitor_bytes=0, total_mapping_bytes=0, region_bytes=[0] * 7,
            tls_module_capacity=8, thread_stat_bytes=4096, thread_status_bytes=4096,
            thread_affinity_words=4, initial_consumer_state=0)
        monitor = dict(ordinal=ordinal, during_first_page=[0] * 7, during_page_count=[1] * 7,
            during_offset_ticks=[2_500_000_000_000, key.duration_ns * 250],
            observer_wait_poll_limit=10**12, control_region_index=5,
            counter_limits=[[dict(minor_faults=None, major_faults=0, voluntary_switches=None,
                                  involuntary_switches=None) for _ in range(2)] for _ in range(2)],
            hardware_identity=dict(family=6, model=62), environment_sources=copy.deepcopy(sources))
        query = dict(capture=cap, resources=resource, monitoring=monitor,
                     hardware_prestate=[dict(cpu=v["cpu"], value=int(v["complete_value_hex"], 16)) for v in prestate])
        input_path = destination / "layout-inputs" / f"c{ordinal:02d}.json"
        write(input_path, query)
        command = [str(worker), "--describe-stage17-discovery-layout-v1", str(input_path)]
        process = subprocess.run(command, capture_output=True, timeout=120, check=False)
        (destination / "layouts" / f"c{ordinal:02d}.stderr").write_bytes(process.stderr)
        require(process.returncode == 0, "readonly layout failed: " + process.stderr.decode(errors="replace"))
        layout = loads(process.stdout)
        require(layout["schema_version"] == "cpu-prefetch-discovery-layout/1" and
                layout["execution_authority"] is False and layout["source_dirty"] is False and
                layout["source_revision"] == release["source_revision"] and
                layout["binary_sha256"] == release["worker"]["sha256"], "layout binary/source identity differs")
        for name in ("core_bytes", "monitor_bytes", "total_mapping_bytes", "region_bytes"):
            resource[name] = layout[name]
        require(all(type(v) is int and v > 0 for v in resource["region_bytes"]), "invalid actual layout")
        output_path = destination / "layouts" / f"c{ordinal:02d}.json"
        with output_path.open("xb") as stream:
            stream.write(process.stdout)
        metadata, spool = modeled_control(model, cap, resource, monitor)
        budget["metadata_output_bytes"] = metadata + MIB  # explicit additional finite margin
        budget["max_output_bytes"] = raw + budget["metadata_output_bytes"]
        bounds.append(dict(ordinal=ordinal, raw_upper_bytes=raw,
            modeled_control_upper_bytes=metadata, metadata_margin_bytes=MIB, drain_spool_upper_bytes=spool,
            native_mapping_bytes=resource["total_mapping_bytes"]))
        layout_records.append(dict(ordinal=ordinal, command=command, exit_code=process.returncode,
                                   input=file_binding(input_path), output=file_binding(output_path)))
        captures.append(cap); resources.append(resource); monitoring.append(monitor)
    require(sha(worker.read_bytes()) == release["worker"]["sha256"], "worker changed during layout queries")
    namespace = dict(schema_version="cpu-prefetch-stage17-discovery-namespace-registry/1",
        registry_id=PREFIX + "-NAMESPACES-1", diagnostic_only=True, execution_authority=False,
        warmup_namespace=NAMESPACES["warmup"], measurement_namespace=NAMESPACES["measurement"],
        seed_derivation="SHA256(ASCII(namespace_id + '/' + run_id)); lowercase hexadecimal",
        seed_use="ONE_PERSISTENT_ARENA_MEASUREMENT_SEED_WARMUP_RESERVED_NO_DRAWS",
        identities=[dict(phase=p, ordinal=c["ordinal"], **c[p]) for c in captures for p in NAMESPACES])
    all_ids = {v[k] for v in namespace["identities"] for k in ("run_id", "seed_id", "seed_hex", "namespace_id")}
    collisions, scanned = [], 0
    def strings(v):
        if isinstance(v, str):
            yield v
        elif isinstance(v, list):
            for child in v:
                yield from strings(child)
        elif isinstance(v, dict):
            for child in v.values():
                yield from strings(child)
    for path in sorted(root.rglob("*.json")):
        d = load(path); scanned += 1
        overlap = all_ids.intersection(strings(d))
        if overlap:
            collisions.append(dict(path=str(path), values=sorted(overlap)))
    require(not collisions, "new namespace/run/seed overlaps retained snapshot: " + str(collisions))
    document_specs = [
        ("stand", anchor["evidence_id"], anchor_path.read_bytes()),
        ("qualification", qualification["manifest_id"], qualification_path.read_bytes()),
        ("resource_plan", PREFIX + "-RESOURCES-1", canonical(dict(schema_version="cpu-prefetch-discovery-resources/1", captures=resources))),
        ("monitoring_plan", PREFIX + "-MONITORING-1", canonical(dict(schema_version="cpu-prefetch-discovery-monitoring/1", captures=monitoring))),
        ("namespace_registry", namespace["registry_id"], canonical(namespace))]
    bound_documents = []
    bindings = {}
    for name, artifact_id, payload in document_specs:
        bindings[name] = binding(artifact_id, payload)
        bound_documents.append(dict(artifact_id=artifact_id, document=loads(payload), utf8_bytes=payload.decode("utf-8")))
        with (destination / (name + ".json")).open("xb") as stream:
            stream.write(payload)
    dependencies = []
    for i in range(1, 7):
        key = f"S17-EXT-{i:03d}"; path, document = records[key]; payload = path.read_bytes()
        dependencies.append(dict(input_id=key, resolution=binding(document["resolution_id"], payload)))
        bound_documents.append(dict(artifact_id=document["resolution_id"], document=document, utf8_bytes=payload.decode("utf-8")))
    output = sum(c["budget"]["max_output_bytes"] for c in captures) + 16 * MIB
    scratch = max(v["drain_spool_upper_bytes"] for v in bounds)
    disk_needed = output + scratch + 10 * GIB
    require(args.pc_free_bytes >= disk_needed, "PC one-copy + max drain spool + 10GiB reserve does not fit")
    require(inventory["disk_available_bytes"] >= disk_needed, "stand storage does not fit")
    meminfo = next(v["text"] for v in inventory["files"] if v["path"] == "/proc/meminfo")
    memavailable = int(next(line.split()[1] for line in meminfo.splitlines() if line.startswith("MemAvailable:"))) * 1024
    require(memavailable >= (224 + 2 + 16) * GIB, "observed stand MemAvailable cannot cover worker+controller+16GiB reserve")
    plan = dict(schema_version=contract.PLAN_VERSION, protocol_version="2.0.0-pre.3",
        design_id="D178-Q16A-SETUP-DISCOVERY-v1", plan_id=PREFIX + "-PLAN-1", stand_id=anchor["stand_id"],
        source_revision=release["source_revision"], clean_source=True,
        release=binding(PREFIX + "-WORKER-1", worker_bytes), **bindings, dependencies=dependencies,
        warmup_namespace=NAMESPACES["warmup"], measurement_namespace=NAMESPACES["measurement"],
        minimum_observations={name: 100_000 for name in contract.SEQUENCES}, captures=captures,
        budget=dict(setup_ns=120 * NS, cleanup_ns=120 * NS,
            watchdog_ns=240 * NS + sum(c["budget"]["watchdog_ns"] for c in captures),
            controller_memory_bytes=2 * GIB, memory_budget_bytes=226 * GIB,
            metadata_output_bytes=16 * MIB, output_budget_bytes=output,
            custody_domains=[dict(domain_id=PREFIX + "-STAND-COPY1", copies=1, budget_bytes=output),
                            dict(domain_id=PREFIX + "-PC-COPY1", copies=1, budget_bytes=output)]),
        diagnostic_only=True, execution_authority=False, phase18_authority=False, retries=0)
    parsed = contract.validate_plan(plan)
    Draft202012Validator(load(ROOT / contract.SCHEMA_PATH)).validate(plan)
    native = [dict(ordinal=i, resources=r, monitoring=m) for i, (r, m) in enumerate(zip(resources, monitoring, strict=True))]
    inputs = dict(plan=plan, hardware_control=hardware, bound_documents=bound_documents, native_captures=native)
    controller._native_inputs(parsed, loads(document_specs[2][2]), loads(document_specs[3][2]), native)
    for b in list(bindings.values()) + [d["resolution"] for d in dependencies]:
        item = next(d for d in bound_documents if d["artifact_id"] == b["artifact_id"])
        require(binding(b["artifact_id"], item["utf8_bytes"].encode("utf-8")) == b, "bound bytes drift")
    provenance = dict(scope="PREP_ONLY_STRUCTURAL_VALIDATION_NOT_ADMISSION", execution_authority=False,
        source_revision_scope="CLEAN_RELEASE_REVISION_NOT_CURRENT_DOCUMENTATION_HEAD",
        inventory=file_binding(args.inventory), qualification_snapshot=str(root),
        release_contract=file_binding(release_path), platform_facts=file_binding(facts_path),
        platform_inventory=file_binding(platform_path), worker=file_binding(worker),
        publication_model=file_binding(model_path), layouts=layout_records,
        environment_source_count=len(sources), excluded_environment_sources=excluded,
        environmental_numeric_limits="UNFROZEN_LIMITS", disturbance_limits="UNFROZEN_LIMITS",
        namespace_scan=dict(scope="SUPPLIED_RETAINED_SNAPSHOT_JSON_ONLY", files=scanned, collisions=collisions),
        namespace_history_evidence=[file_binding(p) for p in args.namespace_history],
        pc_custody_preparation=file_binding(args.pc_custody_preparation),
        resource_controls=dict(worker_bytes=224 * GIB, controller_bytes=2 * GIB,
            stand_reserve_bytes=16 * GIB, disk_reserve_bytes=10 * GIB, stack_bytes=2 * MIB,
            tls_module_capacity=8, thread_stat_bytes=4096, thread_status_bytes=4096, affinity_words=4,
            initial_consumer_state=0, barrier_poll_limit=10**12, observer_wait_poll_limit=10**12),
        captures=bounds, study_output_budget_bytes=output, maximum_spool_bytes=scratch,
        one_copy_plus_spool_reserve_bytes=disk_needed, pc_free_bytes=args.pc_free_bytes,
        pc_custody_path=str(args.pc_custody_path.resolve()), stand_disk_available_bytes=inventory["disk_available_bytes"],
        stand_memavailable_bytes=memavailable, deadline_policy=controller.deadline_policy(parsed),
        limits=["Major-fault delta limit is prospectively zero; minor/context-switch limits are explicitly null/unenforced.",
            "No warmup event-rate or five-million-attempt sufficiency proof; early capacity is mandatory failure.",
            "Measurement capacity hit is retained INSUFFICIENT; mandatory controls remain required.",
            "Timeouts and memory limits are prospective controls, not observed completion/heap guarantees.",
            "Plan memory_bytes is not itself RLIMIT_AS enforcement; process limits/readbacks remain executor preparation.",
            "Publication envelope is the existing symbolic model parameterized to all source buffers; active/retained allocator heap remains separate review.",
            "Two retained custody copies across different machines, one max-capture drain spool and explicit reserve per filesystem; no archive duplicate budget.",
            "Readability/size inventory is historical non-atomic evidence; no prediction of live values, file growth or readiness.",
            "Existing CLI must independently re-admit current journal/trust/release and exact plan before owner signing."])
    write(destination / "plan.json", plan)
    write(destination / "action-inputs.json", inputs)
    write(destination / "preparation-provenance.json", provenance)
    print(json.dumps(dict(output_directory=str(destination), plan_sha256=parsed.sha256,
        captures=len(captures), environment_sources=len(sources),
        study_watchdog_seconds=parsed.budget.watchdog_ns / NS,
        disk_bytes=disk_needed, structural_validation="PASS", execution_authority=False), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot-root", "bundle-root", "inventory", "output-directory", "pc-custody-path", "pc-custody-preparation"):
        parser.add_argument("--" + name, type=pathlib.Path, required=True)
    parser.add_argument("--pc-free-bytes", type=int, required=True, help="Explicit fresh PC free-space observation")
    parser.add_argument("--controller-cpu", type=int, required=True, help="Prospective CPU, checked against observed topology")
    parser.add_argument("--namespace-history", action="append", type=pathlib.Path, default=[], help="Bound audit provenance; not whole-disk assurance")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
