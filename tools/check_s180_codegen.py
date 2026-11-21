#!/usr/bin/env python3
"""Separate dual-disassembler audit for actual S180 and preserved formal workers.

No production code is rewritten or relabeled. The original formal classifier
predates PilotRuntimePolicy and classifies it as service. Positively identify
all20 pilot roots, audit them separately, and retain the complete42-root formal
analysis and all of its original machine-instruction mutants. This report is
not a legacy formal report and grants no execution authority.
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import check_formal_codegen as formal

machine, AuditError, Worker = formal.machine, formal.AuditError, formal.Worker
active_region, graph = formal.active_region, formal.graph
capture_anchor, tls_callback = formal.capture_anchor, formal.tls_callback
inspect_worker, TLS = formal.inspect_worker, formal.TLS
SCHEMA = "cpu-prefetch-stage17-s180-native-codegen/1"
SOURCE_PATHS = tuple(dict.fromkeys((*formal.SOURCE_PATHS,
    "include/cpu_prefetch/calibration/mapped_pilot_capture.hpp",
    "include/cpu_prefetch/calibration/mapped_pilot_data.hpp",
    "include/cpu_prefetch/calibration/native_pilot_capture.hpp",
    "src/calibration/native_pilot_capture.cpp",
    "include/cpu_prefetch/runner/stage17_s180_sources.hpp",
    "src/runner/stage17_s180_sources.cpp",
    "include/cpu_prefetch/runner/stage17_s180_session.hpp",
    "src/runner/stage17_s180_session.cpp",
    "src/runner/stage17_s180_native_session.cpp",
    "include/cpu_prefetch/runner/stage17_s180_input.hpp",
    "src/runner/stage17_s180_input.cpp",
    "include/cpu_prefetch/runner/stage17_s180_worker.hpp",
    "src/runner/stage17_s180_worker.cpp",
    "include/cpu_prefetch/runner/stage17_s180_channel_sink.hpp",
    "src/runner/stage17_s180_channel_sink.cpp",
    "include/cpu_prefetch/runner/stage17_s180_publication.hpp",
    "tools/runner_main.cpp")))
AGREEMENT_FIELDS = ("root_address", "active_addresses", "cold_boundary_addresses",
                    "prefetch_vector", "prefetch_witnesses")


def identity(name):
    if "PilotRuntimePolicy<" not in name:
        return None
    value = formal.identity(name)
    return replace(value, purpose="pilot") if value is not None else None


def expected_workers():
    return {Worker("pilot", package, mapping, role) for package in range(5)
            for mapping in ("retaining", "t0only") for role in ("producer", "consumer")}


def roots_for(functions):
    roots = {}
    for name in functions:
        worker = identity(name)
        if worker is not None:
            if worker in roots:
                raise AuditError("duplicate pilot worker identity")
            roots[worker] = name
    if set(roots) != expected_workers():
        raise AuditError(f"expected exact20 actual pilot workers, found{len(roots)}")
    return roots


def formal_view(functions):
    # Only positively classified pilot roots are excluded from the old root
    # classifier. All other functions/callees remain available for full audits.
    return {name: function for name, function in functions.items() if identity(name) is None}


def inspect_functions(functions):
    roots = roots_for(functions)
    legacy = formal.inspect_functions(formal_view(functions))
    entries = [name for name in functions if name.startswith(
        "cpu_prefetch::calibration::run_native_pilot_capture(")
        and "[clone" not in name and "(.cold)" not in name]
    if len(entries) != 1:
        raise AuditError("missing unique production native pilot entry")
    operations = {}
    for worker, root in sorted(roots.items()):
        result = inspect_worker(functions, root, worker)
        result["native_reference_path"] = machine.reference_path(functions, entries[0], root)
        operations[worker.key()] = result
    return dict(status="PASS", operations=operations, legacy_formal=legacy)


def negative_checks(functions: dict[str, machine.Function]) -> dict[str, str]:
    """Mutate decoded actual machine instructions, not replacement worker source."""
    roots = {identity(name): name for name in functions if identity(name) is not None}
    worker = Worker("pilot", 0, "t0only", "producer")
    root = roots[worker]
    region, _ = active_region(functions[root], functions)
    # Place mutants on a path that can still execute an event in this phase;
    # an abort-only exit is not a useful hidden-hot-observation mutant.
    edges = graph(functions[root])
    predecessors = {index: set() for index in region}
    for index in region:
        for destination in edges[index]:
            if destination in region:
                predecessors[destination].add(index)
    reaches_capture = {index for index in region if capture_anchor(functions[root].instructions[index])}
    pending = list(reaches_capture)
    while pending:
        for index in predecessors[pending.pop()]:
            if index not in reaches_capture:
                reaches_capture.add(index)
                pending.append(index)
    ordinary = next(index for index in sorted(reaches_capture)
                    if functions[root].instructions[index].mnemonic.startswith("mov"))
    original = functions[root].instructions[ordinary]
    results = {}

    def rejected(label: str, mutant: dict[str, machine.Function], selected: Worker = worker) -> None:
        try:
            inspect_worker(mutant, roots[selected], selected)
        except AuditError:
            results[label] = "REJECTED"
            return
        raise AuditError(f"negative mutant accepted: {label}")

    for label, instruction in (
        ("allocation", replace(original, mnemonic="call", operands="0 <malloc@plt>", target="malloc@plt")),
        ("indirect_call", replace(original, mnemonic="call", operands="*%rax", target=None)),
        ("direct_syscall", replace(original, mnemonic="syscall", operands="", target=None)),
        ("unregistered_atomic", replace(original, mnemonic="lock", operands="xadd %eax,(%rdi)", target=None)),
        ("hidden_hot_tls", replace(original, mnemonic="call", operands="0 <" + TLS + ")>", target=TLS + ")")),
    ):
        instructions = list(functions[root].instructions)
        instructions[ordinary] = instruction
        mutant = dict(functions)
        mutant[root] = replace(functions[root], instructions=tuple(instructions))
        rejected(label, mutant)
    _, cuts = active_region(functions[root], functions)
    cut = next(iter(cuts))
    tls_name = functions[root].instructions[cut].target
    primary_name = next(name for name in functions if "ProducerObservationStream::append(" in name)
    wrapper_name = "s180_codegen_hidden_capture_wrapper"
    address = max(instruction.address for function in functions.values() for instruction in function.instructions) + 16
    wrapper = machine.Function(wrapper_name, (
        machine.Instruction(address, "call", "0 <" + primary_name + ">", primary_name),
        machine.Instruction(address + 1, "ret", "", None)))
    instructions = list(functions[root].instructions)
    instructions[cut + 1] = replace(instructions[cut + 1], mnemonic="call",
                                    operands=hex(address) + " <" + wrapper_name + ">", target=wrapper_name)
    mutant = dict(functions)
    mutant[root] = replace(functions[root], instructions=tuple(instructions))
    mutant[wrapper_name] = wrapper
    rejected("capture_wrapper_after_cold_cut", mutant)
    for label, name in (("capture_inside_tls_cut", tls_name),
                        ("capture_inside_loader_callback", next(iter(tls_callback(functions[tls_name], functions))))):
        instructions = list(functions[name].instructions)
        index = next(index for index, instruction in enumerate(instructions) if instruction.mnemonic.startswith("mov"))
        instructions[index] = replace(instructions[index], mnemonic="call",
                                      operands="0 <" + primary_name + ">", target=primary_name)
        mutant = dict(functions)
        mutant[name] = replace(functions[name], instructions=tuple(instructions))
        rejected(label, mutant)
    instructions = list(functions[root].instructions)
    raw_definition = next(index for index in sorted(region)
                          if instructions[index].mnemonic in ("mov", "movl", "movq")
                          and len(machine.split_operands(instructions[index].operands)) == 2
                          and machine.register(machine.split_operands(instructions[index].operands)[1]) == "rdi"
                          and machine.immediate(machine.split_operands(instructions[index].operands)[0]) == 4)
    destination = machine.split_operands(instructions[raw_definition].operands)[1]
    instructions[raw_definition] = replace(instructions[raw_definition], operands="$1," + destination)
    mutant = dict(functions)
    mutant[root] = replace(functions[root], instructions=tuple(instructions))
    rejected("wrong_clock_domain", mutant)
    mutant = dict(functions)
    del mutant[root]
    try:
        inspect_functions(mutant)
    except AuditError:
        results["missing_native_worker"] = "REJECTED"
    else:
        raise AuditError("missing native worker mutant accepted")
    selected = Worker("pilot", 1, "retaining", "producer")
    report = inspect_worker(functions, roots[selected], selected)
    location = next((name, index) for name in report["reachable_internal_symbols"]
                    for index, instruction in enumerate(functions[name].instructions)
                    if instruction.mnemonic == "prefetchw")
    name, index = location
    instructions = list(functions[name].instructions)
    instructions[index] = replace(instructions[index], mnemonic="prefetcht0")
    mutant = dict(functions)
    mutant[name] = replace(functions[name], instructions=tuple(instructions))
    rejected("wrong_prefetch_intent", mutant, selected)
    # An extra actual prefetch instruction must not collapse to a set membership test.
    instructions = list(functions[name].instructions)
    spare = next(i for i, instruction in enumerate(instructions) if instruction.mnemonic.startswith("mov"))
    instructions[spare] = replace(instructions[spare], mnemonic="prefetchw", operands="(%rax)", target=None)
    mutant = dict(functions)
    mutant[name] = replace(functions[name], instructions=tuple(instructions))
    rejected("duplicate_prefetch", mutant, selected)
    return results


def rule_bindings(root):
    return {name: machine.sha256(root / "tools" / name) for name in
            ("check_s180_codegen.py", "check_formal_codegen.py", "check_discovery_codegen.py")}


def validate_report_bindings(report, *, binary, source_root, rule_root=None):
    rule_root = source_root if rule_root is None else rule_root
    if (type(report) is not dict or report.get("schema_version") != SCHEMA
            or report.get("status") != "PASS" or report.get("missing_tools") != []
            or report.get("execution_authority") is not False
            or report.get("phase18_authority") is not False):
        raise AuditError("S180 report identity/status/scope is not accepted")
    if (report.get("binary_sha256") != machine.sha256(binary)
            or report.get("rule_bindings") != rule_bindings(rule_root)
            or report.get("source_evidence") != {p: machine.sha256(source_root / p) for p in SOURCE_PATHS}):
        raise AuditError("S180 binary/rule/source binding changed")
    formal.validate_report_bindings(report.get("legacy_formal_report"), binary=binary, source_root=source_root)
    tools = report.get("tools")
    if type(tools) is not dict or set(tools) != {"GNU_OBJDUMP", "LLVM_OBJDUMP"}:
        raise AuditError("S180 requires exactly both disassemblers")
    expected = {worker.key(): worker for worker in expected_workers()}
    for kind, item in tools.items():
        if (type(item) is not dict or item.get("status") != "PASS"
                or type(item.get("version")) is not str or not item["version"]
                or (kind == "LLVM_OBJDUMP" and item["version"].split(".")[0] != "22")
                or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("disassembly_sha256", "")))
                or item.get("negative_checks") != {n: "REJECTED" for n in formal.NEGATIVE_CASES}):
            raise AuditError("S180 disassembler or actual mutant checks incomplete")
        legacy = report["legacy_formal_report"]["tools"][kind]
        if any(item.get(k) != legacy.get(k) for k in ("version", "path", "disassembly_sha256")):
            raise AuditError("formal and pilot audits did not consume the same disassembly")
        operations = item.get("operations")
        if type(operations) is not dict or set(operations) != set(expected):
            raise AuditError("S180 report requires exact20 actual pilot workers")
        for key, op in operations.items():
            if (type(op) is not dict or not op.get("root_address") or not op.get("active_addresses")
                    or not op.get("cold_boundary_addresses") or not op.get("raw_clock_call_sites")
                    or not op.get("native_reference_path") or op.get("prefetch_vector") != expected[key].vector()):
                raise AuditError("S180 native worker proof incomplete")
            path = op["native_reference_path"]
            if (type(path) is not list or not path[0].startswith(
                    "cpu_prefetch::calibration::run_native_pilot_capture(") or path[-1] != op.get("root")):
                raise AuditError("S180 actual native entry/reference path missing")
            if any(type(v) is not int for v in op["prefetch_vector"].values()):
                raise AuditError("S180 prefetch counts are not integers")
            clocks = op["raw_clock_call_sites"]
            if type(clocks) is not dict or any(type(sites) is not list or not sites for sites in clocks.values()):
                raise AuditError("S180 raw clock witnesses incomplete")
            witnesses = op.get("prefetch_witnesses")
            if (type(witnesses) is not list or any(type(w) is not list or len(w) != 2
                    or type(w[0]) is not int or w[0] < 0 or type(w[1]) is not str for w in witnesses)
                    or len({w[0] for w in witnesses}) != len(witnesses)
                    or dict(Counter(w[1] for w in witnesses)) != expected[key].vector()):
                raise AuditError("S180 prefetch machine witnesses incomplete")
    first, second = (tools[k]["operations"] for k in ("GNU_OBJDUMP", "LLVM_OBJDUMP"))
    for key in expected:
        for field in AGREEMENT_FIELDS:
            if first[key][field] != second[key][field]:
                raise AuditError("S180 disassemblers disagree")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gnu-objdump", default="objdump")
    parser.add_argument("--llvm-objdump", default="llvm-objdump")
    args = parser.parse_args(argv)
    report = dict(schema_version=SCHEMA, status="FAIL", tools={}, missing_tools=[],
        execution_authority=False, phase18_authority=False,
        scope="actual20 pilot plus42 preserved formal active closures; queue/timing gates remain mandatory")
    try:
        report.update(binary_sha256=machine.sha256(args.binary), rule_bindings=rule_bindings(Path(__file__).resolve().parents[1]),
            source_evidence={p: machine.sha256(args.source_root / p) for p in SOURCE_PATHS})
        legacy = dict(schema_version=formal.SCHEMA, status="PASS", tools={}, missing_tools=[],
            binary_sha256=report["binary_sha256"], rule_set_sha256=machine.sha256(Path(formal.__file__)),
            source_evidence={p: machine.sha256(args.source_root / p) for p in formal.SOURCE_PATHS})
        for kind, configured in (("GNU_OBJDUMP", args.gnu_objdump), ("LLVM_OBJDUMP", args.llvm_objdump)):
            tool = shutil.which(configured)
            if tool is None:
                report["missing_tools"].append(kind)
                continue
            version = machine.tool_version(tool, kind)
            text = machine.disassemble(tool, args.binary)
            functions = formal.decode(text)
            result = inspect_functions(functions)
            common = dict(path=tool, version=version, disassembly_sha256=hashlib.sha256(text.encode()).hexdigest())
            original = result.pop("legacy_formal")
            original.update(common, negative_checks=formal.negative_checks(formal_view(functions)))
            legacy["tools"][kind] = original
            result.update(common, negative_checks=negative_checks(functions))
            report["tools"][kind] = result
        if report["missing_tools"]:
            report["status"] = "BLOCKED_MISSING_TOOL"
        else:
            report.update(status="PASS", legacy_formal_report=legacy)
            # JSON-normalize tuple witnesses before applying the retained-report
            # validator that later package/admission consumers must also use.
            validate_report_bindings(json.loads(json.dumps(report)), binary=args.binary,
                source_root=args.source_root, rule_root=Path(__file__).resolve().parents[1])
    except (OSError, ValueError, AuditError, StopIteration, KeyError, TypeError, IndexError) as error:
        report.update(status="FAIL", error=str(error) or type(error).__name__)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("s180-codegen-check: " + report["status"] + (": " + report["error"] if "error" in report else ""))
    return 0 if report["status"] == "PASS" else 3 if report["missing_tools"] else 1


if __name__ == "__main__":
    sys.exit(main())
