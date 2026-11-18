#!/usr/bin/env python3
"""Operator-only cold preparation. Never runs qualification, MSR I/O or signing.

snapshot reads public local procfs/sysfs and retains raw readbacks. build-facts
reads existing compiler/report/ELF evidence. compose reads actual Q15 artifacts.
All outputs are exclusive. No remote execution, source changes or journal writes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
from author_fresh_qualification_records import read, write, require, utc, size_bytes


def load(path):
    return json.loads(read(path))


def bound(path):
    data = read(path)
    return dict(path=str(path), size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def cpulist(text):
    result = set()
    require(bool(text.strip()), "empty CPU list")
    for item in text.strip().split(","):
        require(re.fullmatch(r"[0-9]+(?:-[0-9]+)?", item) is not None, "invalid CPU list")
        parts = [int(x) for x in item.split("-")]
        first, last = parts[0], parts[-1]
        require(first <= last < 65536, "CPU list out of finite parsing bounds")
        result.update(range(first, last + 1))
    return sorted(result)


def snapshot(args):
    observations, errors = {}, []
    def observed(path):
        try:
            with path.open("rb") as stream:
                data = stream.read(2 * 1024 * 1024 + 1)
            require(len(data) <= 2 * 1024 * 1024, "public readback exceeds bounded input")
            text = data.decode("utf-8", errors="strict")
            observations[str(path)] = text
            return text.strip()
        except (OSError, ValueError) as exc:
            errors.append(dict(path=str(path), error=str(exc)))
            raise
    started = utc()
    try:
        online = cpulist(observed(Path("/sys/devices/system/cpu/online")))
        nodes = cpulist(observed(Path("/sys/devices/system/node/online")))
        observed(Path("/proc/cpuinfo"))
        cpus = []
        for cpu in online:
            root = Path("/sys/devices/system/cpu") / ("cpu" + str(cpu))
            node_paths = sorted(root.glob("node[0-9]*"))
            require(len(node_paths) == 1, "CPU NUMA node is not unique")
            caches = []
            for directory in sorted((root / "cache").glob("index[0-9]*")):
                caches.append({key: observed(directory / key) for key in
                    ("level", "type", "size", "shared_cpu_list", "coherency_line_size")})
            require(bool(caches), "CPU cache inventory missing")
            cpus.append(dict(cpu=cpu, node=int(node_paths[0].name[4:]),
                node_symlink=str(node_paths[0]), node_resolved=str(node_paths[0].resolve(strict=True)),
                package=int(observed(root / "topology/physical_package_id")),
                core=int(observed(root / "topology/core_id")),
                siblings=cpulist(observed(root / "topology/thread_siblings_list")), caches=caches))
        require(cpulist(observed(Path("/sys/devices/system/cpu/online"))) == online,
                "online CPUs changed during non-atomic inventory")
        result = dict(complete=True, online=online, nodes=nodes, cpus=cpus,
                      uname=dict(zip(os.uname()._fields, os.uname())) if hasattr(os.uname(), "_fields")
                      else dict(sysname=os.uname().sysname, nodename=os.uname().nodename,
                                release=os.uname().release, version=os.uname().version,
                                machine=os.uname().machine), page_bytes=os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError) as exc:
        if not errors:
            errors.append(dict(error=str(exc)))
        result = dict(complete=False)
    result.update(started_at_utc=started, completed_at_utc=utc(), observations=observations,
                  errors=errors, observation_atomic=False)
    write(args.output, result)
    require(result["complete"], "inventory incomplete; partial readbacks retained")


def build_facts(args):
    bundle = args.bundle_root.resolve(strict=True)
    manifest = load(bundle / "BUNDLE_MANIFEST.json")
    revision = manifest["source_archive"]["source_revision"]
    require(manifest["source_archive"]["source_dirty"] is False, "dirty release")
    codegen = load(args.codegen_facts)
    require(codegen["source_revision"] == revision, "codegen revision differs")
    for flag in ("gcc_codegen_passed", "clang_codegen_passed", "gnu_objdump_passed", "llvm_objdump_passed"):
        require(codegen[flag] is True, "missing passing codegen evidence: " + flag)
    require(len(codegen["reports"]) == 4, "expected four codegen reports")
    evidence = [bound(args.codegen_facts), bound(bundle / "BUNDLE_MANIFEST.json")]
    metadata = {}
    seen = set()
    for reference in codegen["reports"]:
        compiler = reference["compiler"]["id"]
        require(compiler in ("GNU", "Clang"), "unknown compiler")
        build = args.gcc_build if compiler == "GNU" else args.clang_build
        prefix = "gcc-" if compiler == "GNU" else "clang-libcxx-"
        require(reference["file_name"].startswith(prefix), "compiler report filename differs")
        name = reference["file_name"][len(prefix):]
        require(name in ("software_prefetch_mapping_codegen_report.json", "runner_combined_codegen_report.json"),
                "unknown codegen report kind")
        require((compiler, name) not in seen, "duplicate compiler/report")
        seen.add((compiler, name))
        path = build / name
        proof = bound(path)
        require((proof["size_bytes"], proof["sha256"]) == (reference["size_bytes"], reference["sha256"]),
                "actual report differs from bound codegen facts")
        document = load(path)
        require(document["status"] == "PASS" and not document.get("missing_tools"), "codegen report failed")
        for tool in ("GNU_OBJDUMP", "LLVM_OBJDUMP"):
            require(document["tools"][tool]["status"] == "PASS", "disassembler did not pass")
        if name == "runner_combined_codegen_report.json":
            require("X86-64-PREFETCHT0-ONLY-v1" in document["software_prefetch_mapping_ids"], "T0-only mapping absent")
        meta_path = build / "generated/version_metadata.json"
        meta = load(meta_path)
        require(meta["source_revision"] == revision and meta["source_dirty"] is False
                and meta["compiler"] == reference["compiler"] and meta["build_type"] == "Release",
                "compiler metadata differs from exact release")
        metadata[compiler] = meta
        evidence.extend((proof, bound(meta_path), bound(build / "CMakeCache.txt")))
    require(len(seen) == 4, "missing compiler/report combination")
    emitter = bundle / codegen["emitter"]["path"]
    require(bound(emitter)["sha256"] == codegen["emitter"]["sha256"], "release emitter differs")
    evidence.append(bound(emitter))
    worker = bundle / manifest["stage17_fixed_action_runtime"]["member_path"]
    worker_binding = bound(worker)
    require(worker_binding["sha256"] == manifest["stage17_fixed_action_runtime"]["sha256"], "worker differs")
    ninja_path = args.gcc_build / "build.ninja"
    ninja = read(ninja_path).decode()
    blocks = [block for block in ninja.split("\n\n") if block.startswith("build ")
              and "stage17_fixed_action.cpp.o:" in block.splitlines()[0]]
    require(len(blocks) == 1, "worker compile rule is not unique")
    flag_lines = [line.split(" = ", 1)[1] for line in blocks[0].splitlines() if line.startswith("  FLAGS = ")]
    require(len(flag_lines) == 1, "missing worker compile flags")
    flags = shlex.split(flag_lines[0])
    require("-std=c++20" in flags and metadata["GNU"]["language_standard"] == "C++20", "language mismatch")
    # readelf reads ELF data; it does not execute or load the worker.
    elf = {}
    for name, arguments in (("comment", ["-p", ".comment"]), ("dynamic", ["-d"])):
        completed = subprocess.run(["readelf", *arguments, str(worker)], capture_output=True, check=False)
        require(completed.returncode == 0, "readelf failed: " + name)
        elf[name] = dict(argv=completed.args, returncode=completed.returncode,
                         stdout=completed.stdout.decode(), stderr=completed.stderr.decode())
    version = metadata["GNU"]["compiler"]["version"]
    require("GCC:" in elf["comment"]["stdout"] and version in elf["comment"]["stdout"], "ELF compiler differs")
    require("[libstdc++.so." in elf["dynamic"]["stdout"], "ELF library differs")
    require(metadata["GNU"]["standard_library"] == "libstdc++", "build library differs")
    evidence.extend((bound(ninja_path), worker_binding))
    write(args.output, dict(source_revision=revision, worker=worker_binding, codegen_facts=codegen,
        compiler="GNU " + version, standard_library="libstdc++", language_standard="C++20",
        flags=flags, link_mode="dynamic", evidence=evidence, elf_readbacks=elf, recorded_at_utc=utc()))


def cpuinfo_records(text):
    records = {}
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
        fields = {key.strip(): value.strip() for key, value in fields.items()}
        if "processor" in fields:
            number = int(fields["processor"])
            require(number not in records, "duplicate CPU info record")
            records[number] = fields
    return records


def verify_clock(clock, near, revision):
    require(clock["kind"] == "SELECTED_PAIR_CLOCK" and clock["eligible"] is True
            and [clock["producer_cpu"], clock["consumer_cpu"]] == near
            and clock["source_revision"] == revision, "clock qualification differs or failed")


def compose(args):
    from author_fresh_qualification_records_v2 import Context
    from jsonschema import Draft202012Validator
    ctx = Context(args)
    release = ctx.need("S17-EXT-003").semantic_context["release"]
    ctx.need("S17-EXT-006")
    request, result = load(args.request), load(args.result)
    require(request["action_id"] == result["action_id"] == "Q15-R"
            and request["attempt_id"] == result["attempt_id"]
            and result["request_sha256"] == bound(args.request)["sha256"]
            and result["terminal_state"] == "Q15_R_READ_ONLY_COMPLETE", "Q15-R lineage/completion differs")
    output_root = Path(request["evidence_root_binding"]["absolute_path"]).resolve(strict=True)
    require(output_root.is_relative_to(ctx.evidence), "Q15 output outside evidence root")
    raws, sources = {}, [bound(args.request), bound(args.result), bound(args.snapshot), bound(args.build_facts), bound(args.clock_envelope)]
    for item in result["artifacts"]:
        path = (output_root / item["file_name"]).resolve(strict=True)
        require(path.parent == output_root and item["role"] not in raws, "unsafe/duplicate raw artifact")
        proof = bound(path)
        require((proof["size_bytes"], proof["sha256"]) == (item["size_bytes"], item["sha256"]), "raw artifact drift")
        document = load(path)
        schema_path = ctx.operational.ROLE_SCHEMA_v16[item["role"]]
        Draft202012Validator(json.loads(ctx.pinned[schema_path])).validate(document)
        raws[item["role"]] = document
        sources.append(proof)
    raw, atomic, residency = (raws[key] for key in
        ("Q15_R_READ_ONLY_PRESTATE", "Q15_R_ATOMIC_LAYOUT_RAW", "Q15_R_ADDRESS_RESIDENCY_RAW"))
    require(raw["session_id"] == request["session_id"], "raw session differs")
    inventory, build, clock = load(args.snapshot), load(args.build_facts), load(args.clock_envelope)
    require(inventory["complete"] and not inventory["errors"], "inventory incomplete")
    require(build["source_revision"] == release.source_revision
            and build["worker"]["sha256"] == result["runtime_binding"]["sha256"] == release.worker_sha256,
            "build facts differ from admitted worker")
    cpus = {item["cpu"]: item for item in inventory["cpus"]}
    info = cpuinfo_records(inventory["observations"]["/proc/cpuinfo"])
    near, far = args.near_cpus, args.far_cpus
    require(near[0] == far[0] and len(set(near + far)) == 3, "declared pair geometry differs")
    require(set(near + far) == {item["cpu"] for item in raw["prestate"]}, "pairs differ from actual control CPUs")
    p, n, f = (cpus[cpu] for cpu in (near[0], near[1], far[1]))
    require((p["package"], p["core"]) != (n["package"], n["core"])
            and p["package"] == n["package"] and p["node"] == n["node"]
            and p["package"] != f["package"] and p["node"] != f["node"], "observed pair topology differs")
    for cpu in set(near + far):
        require(int(info[cpu]["cpu family"]) == raw["cpu_family"] and int(info[cpu]["model"]) == raw["cpu_model"],
                "inventory CPU model differs from Q15 CPUID")
    verify_clock(clock, near, release.source_revision)
    probe = request["action_inputs"]["probe_platform_binding"]
    require(inventory["page_bytes"] == probe["verified_base_page_bytes"]
            and cpus[probe["cpu"]]["node"] == probe["numa_node"], "probe platform differs")
    def llc(cpu):
        entries = [cache for cache in cpus[cpu]["caches"] if cache["level"] == "3" and cache["type"] == "Unified"]
        require(len(entries) == 1, "LLC inventory not unique")
        return entries[0]
    require(size_bytes(llc(probe["cpu"])["size"]) == probe["verified_local_llc_bytes"], "probe LLC differs")
    require(set(cpulist(llc(near[0])["shared_cpu_list"])) == set(cpulist(llc(near[1])["shared_cpu_list"]))
            and not set(cpulist(llc(near[0])["shared_cpu_list"])) & set(cpulist(llc(far[1])["shared_cpu_list"])),
            "declared near/far LLC domains differ")
    require(all(int(cache["coherency_line_size"]) == atomic["cache_line_bytes"]
                for cpu in set(near + far) for cache in cpus[cpu]["caches"]), "cache lines differ from raw")
    selected = info[near[0]]
    facts = dict(cpu=dict(vendor=selected["vendor_id"], model="%02X_%02XH" % (raw["cpu_family"], raw["cpu_model"]),
        stepping=selected["stepping"], microcode=selected["microcode"], cache_line_bytes=atomic["cache_line_bytes"],
        atomic_width_bits=8 * atomic["pointer_atomic_width_bytes"], atomic_alignment_bytes=atomic["pointer_atomic_alignment_bytes"]),
        topology=dict(sockets=len({item["package"] for item in cpus.values()}), numa_nodes=len(inventory["nodes"]),
            physical_cores=len({(item["package"], item["core"]) for item in cpus.values()}),
            smt_enabled=any(len(set(item["siblings"]) & set(inventory["online"])) > 1 for item in cpus.values()),
            cache_domains=sorted({llc(cpu)["shared_cpu_list"] for cpu in cpus}), near_core_pair=near, far_core_pair=far),
        memory=dict(population="MMAP_PRIVATE_ANONYMOUS_MPOL_BIND_MADV_NOHUGEPAGE_THEN_SINGLETON_VERIFIED_FIRST_TOUCH",
            base_page_bytes=inventory["page_bytes"], residency_verification_method=residency["mechanism_id"]),
        software=dict(operating_system=inventory["uname"]["sysname"], kernel=inventory["uname"]["release"],
            **{key: build[key] for key in ("compiler", "standard_library", "language_standard", "flags", "link_mode")}),
        clock=dict(source="CLOCK_MONOTONIC_RAW", time_unit="PICOSECONDS",
            conversion_record_id="NO_SEPARATE_RECORD_MONOTONIC_RAW_ORIGIN_SUBTRACT_THEN_NS_TIMES_1000",
            serialization_record_id="NO_SEPARATE_RECORD_ATOMIC_SIGNAL_FENCE_AROUND_CLOCK_GETTIME",
            acceptance_record_id=clock["artifact_id"]),
        topology_evidence=dict(snapshot=bound(args.snapshot), scope="ONLINE_CPU_INVENTORY_NONATOMIC",
            producer_cpu=near[0], producer_numa_node=p["node"], near_consumer_cpu=near[1], near_consumer_numa_node=n["node"],
            far_consumer_cpu=far[1], far_consumer_numa_node=f["node"]),
        cache_capacity_evidence=dict(snapshot=bound(args.snapshot), per_cpu=[dict(cpu=cpu,
            caches=[dict(cache, size_bytes=size_bytes(cache["size"])) for cache in cpus[cpu]["caches"]]) for cpu in sorted(set(near + far))]))
    schema = json.loads(ctx.pinned["protocol/2.0.0-pre.3/handoff/schemas/platform.schema.json"])
    for key in ("cpu", "topology", "memory", "software", "clock"):
        Draft202012Validator(schema["properties"][key]).validate(facts[key])
    write(args.provenance_output, dict(recorded_at_utc=utc(), sources=sources,
        codegen_facts=build["codegen_facts"], clock_semantics="relative_picoseconds=(absolute_ns-origin_ns)*1000; no separate serialization capture",
        population_scope="Source-defined successful Q15 probe preparation, not strict smaps proof or all worker mappings",
        inventory_atomic=False, topology_scope="online CPUs only"))
    write(args.output, facts)
    print("PLATFORM_FACTS_SCHEMA_AND_LINEAGE_PASS", args.output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--output", type=Path, required=True)
    build = sub.add_parser("build-facts")
    for name in ("bundle-root", "gcc-build", "clang-build", "codegen-facts", "output"):
        build.add_argument("--" + name, type=Path, required=True)
    comp = sub.add_parser("compose")
    for name in ("repository-root", "evidence-root", "bundle-root", "pilot-archive", "pilot-sidecar",
                 "request", "result", "snapshot", "build-facts", "clock-envelope", "output", "provenance-output"):
        comp.add_argument("--" + name, type=Path, required=True)
    comp.add_argument("--id-prefix", required=True)
    comp.add_argument("--near-cpus", type=int, nargs=2, required=True)
    comp.add_argument("--far-cpus", type=int, nargs=2, required=True)
    args = parser.parse_args()
    {"snapshot": snapshot, "build-facts": build_facts, "compose": compose}[args.command](args)


if __name__ == "__main__":
    main()
