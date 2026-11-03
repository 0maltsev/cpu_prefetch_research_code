#!/usr/bin/env python3
"""Audit actual formal native active-phase code under both disassemblers.

Cold preparation and parked reset stay outside the active region. Each exit cut
must be unable to reach another capture before the next start-barrier arrival.
This gate qualifies active call closures, clock arguments and exact static
prefetch vectors. Existing queue/timing gates and semantic tests remain required;
this gate does not independently prove event-slot timestamp dataflow.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import check_discovery_codegen as machine

AuditError = machine.AuditError
SCHEMA = "cpu-prefetch-formal-native-codegen/1"
SOURCE_PATHS = (
    # Cold dispatch/publication dependencies: identity binding only; hot rules unchanged.
    "include/cpu_prefetch/runner/stage17_archive_channel.hpp",
    "src/runner/stage17_archive_channel.cpp",
    "include/cpu_prefetch/runner/stage17_formal_checkpoint.hpp",
    "src/runner/stage17_formal_checkpoint.cpp",
    "include/cpu_prefetch/runner/stage17_schedule_source.hpp",
    "src/runner/stage17_schedule_source.cpp",
    "include/cpu_prefetch/runner/stage17_fixed_action.hpp",
    "src/runner/stage17_fixed_action.cpp",
    "include/cpu_prefetch/runner/stage17_formal_family.hpp",
    "src/runner/stage17_formal_family.cpp",
    "include/cpu_prefetch/calibration/formal_ring_session.hpp",
    "include/cpu_prefetch/calibration/formal_service_session.hpp",
    "include/cpu_prefetch/calibration/service_session.hpp",
    "include/cpu_prefetch/calibration/scheduled_session.hpp",
    "include/cpu_prefetch/calibration/detail/scheduled_session_impl.hpp",
    "include/cpu_prefetch/calibration/detail/native_service_envelope.hpp",
    "include/cpu_prefetch/calibration/detail/native_capture_monitor.hpp",
    "include/cpu_prefetch/calibration/mapped_formal_ring_runtime.hpp",
    "include/cpu_prefetch/calibration/mapped_formal_ring_preparation.hpp",
    "include/cpu_prefetch/calibration/mapped_formal_service_preparation.hpp",
    "include/cpu_prefetch/calibration/mapped_formal_scheduled_preparation.hpp",
    "include/cpu_prefetch/calibration/mapped_formal_scheduled_runtime.hpp",
    "include/cpu_prefetch/calibration/native_formal_ring_capture.hpp",
    "include/cpu_prefetch/calibration/native_formal_service_capture.hpp",
    "include/cpu_prefetch/calibration/native_formal_scheduled_capture.hpp",
    "include/cpu_prefetch/calibration/native_capture_plan.hpp",
    "include/cpu_prefetch/calibration/formal_service_plan.hpp",
    "include/cpu_prefetch/calibration/formal_scheduled_plan.hpp",
    "include/cpu_prefetch/calibration/discovery_event_capture.hpp",
    "include/cpu_prefetch/calibration/discovery_capture.hpp",
    "include/cpu_prefetch/calibration/ring_demand_window.hpp",
    "include/cpu_prefetch/runner/software_prefetch.hpp",
    "include/cpu_prefetch/workload/packages.hpp",
    "include/cpu_prefetch/timing/capture.hpp",
    "include/cpu_prefetch/timing/clock.hpp",
    "include/cpu_prefetch/lifecycle/runtime.hpp",
    "include/cpu_prefetch/storage/raw_observations.hpp",
    "include/cpu_prefetch/platform/thread_tls.hpp",
    "src/platform/thread_tls.cpp",
    "include/cpu_prefetch/queue/ring_spsc.hpp",
    "include/cpu_prefetch/queue/linked_spsc.hpp",
    "src/calibration/native_formal_ring_capture.cpp",
    "src/calibration/native_formal_service_capture.cpp",
    "src/calibration/native_formal_scheduled_capture.cpp",
    "src/calibration/service_session.cpp",
    "src/calibration/scheduled_session.cpp",
    "src/calibration/ring_demand_window.cpp",
    "src/lifecycle/runtime.cpp",
    "src/storage/raw_observations.cpp",
    "src/timing/clock.cpp",
    "src/queue/linked_spsc.cpp",
    "src/workload/records.cpp",
    "tools/check_discovery_codegen.py",
    "tools/formal_codegen_probe.cpp",
)
ROLE = re.compile(r"::operator\(\)<\(cpu_prefetch::calibration::RingWorker\)([01])>\(\) const")
PACKAGE = re.compile(r"QueuePackage\)([0-4])")
WINDOW = "cpu_prefetch::calibration::service_window("
ARRIVE = "cpu_prefetch::lifecycle::WorkerStartBarrier::arrive("
TLS = "cpu_prefetch::platform::observe_thread_tls("
FORBIDDEN_INSTRUCTION = re.compile(r"^(?:syscall|sysenter|int|int3|rdtsc|rdtscp|cpuid|mfence|sfence|lfence)$")


@dataclass(frozen=True, order=True)
class Worker:
    purpose: str
    package: int
    mapping: str
    role: str

    def key(self) -> str:
        return f"{self.purpose}/{self.package}/{self.mapping}/{self.role}"

    def vector(self) -> dict[str, int]:
        if self.purpose == "ring":
            return {}
        if self.role == "producer" and self.package in (1, 2):
            return {"prefetchw" if self.mapping == "retaining" else "prefetcht0": 1}
        if self.role == "consumer" and self.package in (1, 2, 4):
            return {"prefetcht0": 1}
        return {}


def decode(text: str) -> dict[str, machine.Function]:
    functions = machine.decode(text)
    result = {}
    for name, function in functions.items():
        instructions = []
        index = 0
        while index < len(function.instructions):
            instruction = function.instructions[index]
            # LLVM 22 prints LOCK as a separate one-byte prefix line. GNU prints
            # prefix+opcode together. Preserve the actual instruction start.
            if instruction.mnemonic == "lock" and not instruction.operands:
                if index + 1 == len(function.instructions):
                    raise AuditError("truncated lock prefix")
                following = function.instructions[index + 1]
                if following.address != instruction.address + 1 or following.target is not None:
                    raise AuditError("unsupported split lock instruction")
                instruction = replace(instruction, operands=following.mnemonic + " " + following.operands)
                index += 1
            instructions.append(instruction)
            index += 1
        result[name] = replace(function, instructions=tuple(instructions))
    return result


def identity(name: str) -> Worker | None:
    if "[clone" in name or "(.cold)" in name or not ROLE.search(name):
        return None
    if "run_service_session<" not in name and "run_scheduled_session<" not in name:
        return None
    if "MonotonicRawClock" not in name or "MappedServiceRuntime<" not in name:
        return None
    if "FormalRingRuntimePolicy" in name:
        purpose, package, mapping = "ring", 0, "none"
    else:
        purpose = "scheduled" if "FormalScheduledRuntimePolicy<" in name else "service"
        found = PACKAGE.search(name)
        if found is None:
            raise AuditError("unregistered worker package")
        package = int(found[1])
        if "X86RetainingPrefetchEmitter" in name:
            mapping = "retaining"
        elif "X86PrefetchT0OnlyEmitter" in name:
            mapping = "t0only"
        else:
            raise AuditError("unregistered worker emitter")
    return Worker(purpose, package, mapping, "producer" if ROLE.search(name)[1] == "0" else "consumer")


def expected_workers() -> set[Worker]:
    return {Worker("ring", 0, "none", role) for role in ("producer", "consumer")} | {
        Worker(purpose, package, mapping, role)
        for purpose in ("service", "scheduled") for package in range(5)
        for mapping in ("retaining", "t0only") for role in ("producer", "consumer")
    }


def graph(function: machine.Function) -> list[tuple[int, ...]]:
    """Intraprocedural CFG. Escaping/indirect transfers are audited separately."""
    instructions = function.instructions
    positions = {instruction.address: index for index, instruction in enumerate(instructions)}
    if len(positions) != len(instructions):
        raise AuditError("duplicate instruction address")
    result = []
    for index, instruction in enumerate(instructions):
        following = (index + 1,) if index + 1 < len(instructions) else ()
        if instruction.mnemonic.startswith("ret") or instruction.mnemonic in ("ud2", "hlt"):
            edges = ()
        elif machine.is_jump(instruction):
            target = re.match(r"(?:0x)?([0-9a-fA-F]+)\s+<", instruction.operands)
            destination = positions.get(int(target[1], 16)) if target else None
            edges = (() if destination is None else (destination,))
            if instruction.mnemonic not in ("jmp", "jmpq"):
                edges += following
        elif machine.is_call(instruction) and instruction.target and machine.external_name(instruction.target) == "__stack_chk_fail":
            edges = ()
        else:
            edges = following
        result.append(edges)
    return result


def capture_anchor(instruction: machine.Instruction) -> bool:
    target = instruction.target or ""
    return machine.is_call(instruction) and any(part in target for part in (
        "ObservationStream::append(", "capture_due_producer_attempt<", "capture_dequeue_poll<"))


def tls_callback(function: machine.Function,
                 functions: dict[str, machine.Function]) -> set[str]:
    callbacks = set()
    predecessors = [set() for _ in function.instructions]
    for index, destinations in enumerate(graph(function)):
        for destination in destinations:
            predecessors[destination].add(index)
    calls = [index for index, instruction in enumerate(function.instructions)
             if machine.is_call(instruction) and instruction.target is not None
             and machine.external_name(instruction.target) == "dl_iterate_phdr"]
    for call in calls:
        pending, seen, definitions = list(predecessors[call]), {call}, set()
        definition_indices = set()
        while pending:
            index = pending.pop()
            if index in seen:
                continue
            seen.add(index)
            instruction = function.instructions[index]
            arguments = machine.split_operands(instruction.operands)
            if arguments and machine.register(arguments[-1]) == "rdi" and not instruction.mnemonic.startswith(("cmp", "test")):
                if instruction.mnemonic not in ("lea", "leaq") or instruction.target is None or not instruction.target.startswith("cpu_prefetch::platform::(anonymous namespace)::Walk::visit("):
                    raise AuditError("TLS loader callback is not the proved bounded collector")
                definitions.add(instruction.target)
                definition_indices.add(index)
                continue
            if machine.is_call(instruction) or not predecessors[index]:
                raise AuditError("TLS callback argument lacks dominating definition")
            pending.extend(predecessors[index])
        if not definitions:
            raise AuditError("TLS callback argument is unproved")
        protected = {function.instructions[index].address for index in seen - definition_indices}
        for name, other in functions.items():
            if name == function.name:
                continue
            for instruction in other.instructions:
                if not (machine.is_call(instruction) or machine.is_jump(instruction)):
                    continue
                destination = re.match(r"(?:0x)?([0-9a-fA-F]+)\s+<", instruction.operands)
                if destination and int(destination[1], 16) in protected:
                    raise AuditError("external entry bypasses TLS callback definition")
        callbacks.update(definitions)
    return callbacks


def tail_exit_safe(functions: dict[str, machine.Function], target: str | None,
                   root: str, *, tls_reset: bool = False) -> bool:
    pending, seen = [target], set()
    while pending:
        name = pending.pop()
        if name is None or name == root:
            return False
        if name in seen:
            continue
        seen.add(name)
        if "@" in name or name not in functions:
            # These fixed C ABI leaf routines do not call user capture code.
            allowed = machine.ALLOWED_EXTERNAL | {"memcmp"}
            if tls_reset:
                allowed |= {"syscall", "__errno_location", "dl_iterate_phdr"}
            if machine.external_name(name) in allowed:
                continue
            return False
        if tls_reset:
            pending.extend(tls_callback(functions[name], functions))
        for instruction in functions[name].instructions:
            if capture_anchor(instruction):
                return False
            if machine.is_call(instruction) or machine.is_jump(instruction):
                if instruction.target != name:
                    pending.append(instruction.target)
    return True


def active_region(function: machine.Function, functions: dict[str, machine.Function]) -> tuple[set[int], set[int]]:
    instructions = function.instructions
    edges = graph(function)
    starts = [index for index, instruction in enumerate(instructions)
              if machine.is_call(instruction) and (instruction.target or "").startswith(WINDOW)]
    arrivals = {index for index, instruction in enumerate(instructions)
                if machine.is_call(instruction) and (instruction.target or "").startswith(ARRIVE)}
    if len(starts) != 1 or len(arrivals) != 1:
        raise AuditError("worker lacks unique phase window/start-barrier boundary")
    boundaries = arrivals | {index for index, instruction in enumerate(instructions)
                            if machine.is_call(instruction) and (instruction.target or "").startswith(TLS)}
    region, cuts = set(), set()
    pending = list(edges[starts[0]])
    while pending:
        index = pending.pop()
        if index in region or index in cuts:
            continue
        if index in boundaries:
            cuts.add(index)
            continue
        region.add(index)
        pending.extend(edges[index])
    if len(cuts) != 1 or not (instructions[next(iter(cuts))].target or "").startswith(TLS):
        raise AuditError("unsupported owner-reset boundary shape")
    if not region or not any(capture_anchor(instructions[index]) for index in region):
        raise AuditError("active region has no actual capture/primary writer")
    for cut in cuts:
        if cut in arrivals:
            continue
        if not tail_exit_safe(functions, instructions[cut].target, function.name, tls_reset=True):
            raise AuditError("cold TLS cut callee can hide capture or unclassified work")
        pending, visited = list(edges[cut]), set()
        while pending:
            index = pending.pop()
            if index in visited or index in arrivals:
                continue
            visited.add(index)
            if capture_anchor(instructions[index]):
                raise AuditError("cold boundary hides another capture before a fresh barrier")
            instruction = instructions[index]
            if (machine.is_call(instruction) or machine.is_jump(instruction)) and instruction.target != function.name:
                if not tail_exit_safe(functions, instruction.target, function.name):
                    raise AuditError("unclassified call/transfer after cold boundary")
            pending.extend(edges[index])
    return region, cuts


def verify_raw_clocks(function: machine.Function,
                      functions: dict[str, machine.Function]) -> list[str]:
    instructions = function.instructions
    clocks = [index for index, instruction in enumerate(instructions)
              if machine.is_call(instruction) and instruction.target is not None
              and machine.external_name(instruction.target) == "clock_gettime"]
    if not clocks:
        return []
    predecessors = [set() for _ in instructions]
    for index, destinations in enumerate(graph(function)):
        for destination in destinations:
            predecessors[destination].add(index)
    external_entries = set()
    addresses = {instruction.address for instruction in instructions}
    for name, other in functions.items():
        if name == function.name:
            continue
        for instruction in other.instructions:
            if not (machine.is_call(instruction) or machine.is_jump(instruction)):
                continue
            destination = re.match(r"(?:0x)?([0-9a-fA-F]+)\s+<", instruction.operands)
            if destination and int(destination[1], 16) in addresses:
                external_entries.add(int(destination[1], 16))
    for clock in clocks:
        pending, seen, definitions = list(predecessors[clock]), {clock}, set()
        while pending:
            index = pending.pop()
            if index in seen:
                continue
            seen.add(index)
            instruction = instructions[index]
            arguments = machine.split_operands(instruction.operands)
            if arguments and machine.register(arguments[-1]) == "rdi" and not instruction.mnemonic.startswith(("cmp", "test")):
                if instruction.mnemonic not in ("mov", "movl", "movq") or len(arguments) != 2 or machine.immediate(arguments[0]) != 4:
                    raise AuditError("clock argument is not proved CLOCK_MONOTONIC_RAW")
                definitions.add(index)
                continue
            if machine.is_call(instruction) or not predecessors[index]:
                raise AuditError("raw clock argument lacks dominating definition")
            pending.extend(predecessors[index])
        if not definitions or any(instructions[index].address in external_entries for index in seen - definitions):
            raise AuditError("external entry bypasses raw clock argument definition")
    return [hex(instructions[index].address) for index in clocks]


def inspect_worker(functions: dict[str, machine.Function], root: str, worker: Worker) -> dict[str, object]:
    function = functions[root]
    region, cuts = active_region(function, functions)
    pending = []
    visited: set[str] = set()
    external: set[str] = set()
    vectors: Counter[str] = Counter()
    clock_sites: dict[str, list[str]] = {}
    witnesses: list[tuple[int, str]] = []
    control_atomics: list[dict[str, str]] = []

    def examine(name: str, instructions: tuple[machine.Instruction, ...], native_root: bool) -> None:
        if machine.FORBIDDEN_NAME.search(name):
            raise AuditError(f"forbidden active work: {name}")
        for instruction in instructions:
            mnemonic = instruction.mnemonic
            if mnemonic.startswith("prefetch"):
                vectors[mnemonic] += 1
                witnesses.append((instruction.address, mnemonic))
            if FORBIDDEN_INSTRUCTION.fullmatch(mnemonic):
                raise AuditError(f"forbidden active instruction: {mnemonic}")
            # The region includes D210/D219 phase-completion and failure control
            # updates. This gate reports these permitted worker-root forms; it
            # does not prove their memory-object identity. The separate queue
            # gate remains mandatory, and operation callees cannot contain locks.
            if mnemonic == "lock":
                expected_mask = "1" if worker.role == "producer" else "2"
                completion = re.match(r"orl? \$(?:0x)?" + expected_mask + r",", instruction.operands)
                failure = re.match(r"cmpxchg[bwlq]?\s", instruction.operands)
                if not native_root or not (completion or failure):
                    raise AuditError(f"unregistered locked active instruction: {instruction}")
                control_atomics.append({"address": hex(instruction.address),
                                        "operands": instruction.operands})
            if not (machine.is_call(instruction) or machine.is_jump(instruction)):
                continue
            target = instruction.target
            if target is None:
                raise AuditError("unresolved/indirect active transfer")
            if target == name:
                continue
            if "@" in target or target not in functions:
                target = machine.external_name(target)
                if target not in machine.ALLOWED_EXTERNAL:
                    raise AuditError(f"unapproved active external transfer: {target}")
                external.add(target)
            else:
                pending.append(target)
        if any(machine.is_clock(instruction) for instruction in instructions):
            # The full containing function supplies argument-definition context.
            clock_sites[name] = verify_raw_clocks(functions[name], functions)

    examine(root, tuple(function.instructions[index] for index in sorted(region)), True)
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        if name == root:
            raise AuditError("active operation recursively reenters cold worker")
        visited.add(name)
        examine(name, functions[name].instructions, False)
    if dict(vectors) != worker.vector():
        raise AuditError(f"wrong active prefetch vector for {worker.key()}: {dict(vectors)}")
    if not clock_sites:
        raise AuditError("active closure lacks verified raw-clock calls")
    primary = worker.role.title() + "ObservationStream::append("
    if not any(primary in name for name in visited):
        raise AuditError("active closure lacks actual primary writer")
    if worker.purpose == "ring" and not any("RingDemandStream::append(" in name for name in visited):
        raise AuditError("formal ring closure lacks actual raw demand writer")
    return {
        "root": root, "root_address": hex(function.instructions[0].address),
        "active_addresses": [hex(function.instructions[index].address) for index in sorted(region)],
        "cold_boundary_addresses": [hex(function.instructions[index].address) for index in sorted(cuts)],
        "reachable_internal_symbols": sorted(visited), "external_calls": sorted(external),
        "prefetch_vector": dict(vectors), "prefetch_witnesses": sorted(witnesses),
        "raw_clock_call_sites": clock_sites,
        "worker_control_atomic_forms": control_atomics,
    }


def inspect_functions(functions: dict[str, machine.Function]) -> dict[str, object]:
    roots: dict[Worker, str] = {}
    for name in functions:
        worker = identity(name)
        if worker is not None:
            if worker in roots:
                raise AuditError("duplicate formal worker identity")
            roots[worker] = name
    if set(roots) != expected_workers():
        raise AuditError(f"expected exact 42 formal workers, found {len(roots)}")
    entries = {}
    for purpose in ("ring", "service", "scheduled"):
        matches = [name for name in functions if name.startswith(
            f"cpu_prefetch::calibration::run_native_formal_{purpose}_capture(")
            and "[clone" not in name and "(.cold)" not in name]
        if len(matches) != 1:
            raise AuditError("missing unique production native entry")
        entries[purpose] = matches[0]
    operations = {}
    for worker, root in sorted(roots.items()):
        result = inspect_worker(functions, root, worker)
        result["native_reference_path"] = machine.reference_path(functions, entries[worker.purpose], root)
        operations[worker.key()] = result
    return {"status": "PASS", "operations": operations}


def negative_checks(functions: dict[str, machine.Function]) -> dict[str, str]:
    """Mutate decoded actual machine instructions, not replacement worker source."""
    roots = {identity(name): name for name in functions if identity(name) is not None}
    worker = Worker("ring", 0, "none", "producer")
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
    wrapper_name = "formal_codegen_hidden_capture_wrapper"
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
    selected = Worker("service", 1, "retaining", "producer")
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



NEGATIVE_CASES = frozenset((
    "allocation", "indirect_call", "direct_syscall", "unregistered_atomic",
    "hidden_hot_tls", "capture_wrapper_after_cold_cut", "capture_inside_tls_cut",
    "capture_inside_loader_callback", "wrong_clock_domain", "missing_native_worker",
    "wrong_prefetch_intent", "duplicate_prefetch",
))


def validate_report_bindings(report: dict[str, object], *, binary: Path,
                             source_root: Path) -> None:
    """Check retained report custody against the packaged worker and source bytes.

    This validates a prior dual-disassembler report; it does not rerun disassembly.
    """
    if (not isinstance(report, dict) or report.get("schema_version") != SCHEMA
            or report.get("status") != "PASS" or report.get("missing_tools") != []):
        raise AuditError("formal report identity/status is not accepted")
    if (report.get("binary_sha256") != machine.sha256(binary)
            or report.get("rule_set_sha256") != machine.sha256(source_root / "tools/check_formal_codegen.py")):
        raise AuditError("formal binary/rule binding changed")
    if report.get("source_evidence") != {name: machine.sha256(source_root / name) for name in SOURCE_PATHS}:
        raise AuditError("formal source evidence changed")
    tools = report.get("tools")
    if not isinstance(tools, dict) or set(tools) != {"GNU_OBJDUMP", "LLVM_OBJDUMP"}:
        raise AuditError("formal report requires exactly both disassemblers")
    expected = {worker.key(): worker for worker in expected_workers()}
    for kind, item in tools.items():
        if (not isinstance(item, dict) or item.get("status") != "PASS"
                or not isinstance(item.get("version"), str)
                or not item["version"]):
            raise AuditError("formal disassembler did not pass")
        if kind == "LLVM_OBJDUMP" and item["version"].split(".")[0] != "22":
            raise AuditError("formal report requires LLVM22")
        if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("disassembly_sha256", ""))):
            raise AuditError("formal disassembly digest missing")
        if item.get("negative_checks") != {name: "REJECTED" for name in NEGATIVE_CASES}:
            raise AuditError("formal negative checks incomplete")
        operations = item.get("operations")
        if not isinstance(operations, dict) or set(operations) != set(expected):
            raise AuditError("formal report requires exact 42 native workers")
        for key, operation in operations.items():
            if (not isinstance(operation, dict) or not operation.get("native_reference_path")
                    or not operation.get("raw_clock_call_sites")
                    or not operation.get("root_address")
                    or not operation.get("active_addresses")
                    or not operation.get("cold_boundary_addresses")
                    or operation.get("prefetch_vector") != expected[key].vector()
                    or not isinstance(operation.get("prefetch_witnesses"), list)):
                raise AuditError("formal native worker proof incomplete")
            if any(type(value) is not int for value in operation["prefetch_vector"].values()):
                raise AuditError("formal prefetch counts are not integers")
            clocks = operation["raw_clock_call_sites"]
            if (not isinstance(clocks, dict) or any(not isinstance(sites, list) or not sites
                    for sites in clocks.values())):
                raise AuditError("formal raw-clock witnesses incomplete")
            witnesses = operation["prefetch_witnesses"]
            if (any(not isinstance(witness, list) or len(witness) != 2
                    or type(witness[0]) is not int or witness[0] < 0
                    or not isinstance(witness[1], str) for witness in witnesses)
                    or len({witness[0] for witness in witnesses}) != len(witnesses)
                    or dict(Counter(witness[1] for witness in witnesses)) != expected[key].vector()):
                raise AuditError("formal prefetch machine witnesses incomplete")
    first, second = (tools[k]["operations"] for k in ("GNU_OBJDUMP", "LLVM_OBJDUMP"))
    for key in expected:
        for field in ("root_address", "active_addresses", "cold_boundary_addresses",
                      "prefetch_vector", "prefetch_witnesses"):
            if first[key][field] != second[key][field]:
                raise AuditError("formal disassemblers disagree")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gnu-objdump", default="objdump")
    parser.add_argument("--llvm-objdump", default="llvm-objdump")
    args = parser.parse_args(argv)
    report = {"schema_version": SCHEMA, "status": "FAIL", "tools": {}, "missing_tools": [],
              "scope": "actual native active phase closures; existing queue/timing gates remain mandatory"}
    try:
        report.update(binary_sha256=machine.sha256(args.binary), rule_set_sha256=machine.sha256(Path(__file__)),
                      source_evidence={name: machine.sha256(args.source_root / name) for name in SOURCE_PATHS})
        for kind, configured in (("GNU_OBJDUMP", args.gnu_objdump), ("LLVM_OBJDUMP", args.llvm_objdump)):
            tool = shutil.which(configured)
            if tool is None:
                report["missing_tools"].append(kind)
                continue
            version = machine.tool_version(tool, kind)
            text = machine.disassemble(tool, args.binary)
            functions = decode(text)
            result = inspect_functions(functions)
            result.update(path=tool, version=version,
                          disassembly_sha256=hashlib.sha256(text.encode()).hexdigest(),
                          negative_checks=negative_checks(functions))
            report["tools"][kind] = result
        if report["missing_tools"]:
            report["status"] = "BLOCKED_MISSING_TOOL"
        else:
            first, second = (report["tools"][kind]["operations"] for kind in ("GNU_OBJDUMP", "LLVM_OBJDUMP"))
            for key in first:
                for field in ("root_address", "active_addresses", "cold_boundary_addresses", "prefetch_vector", "prefetch_witnesses"):
                    if first[key][field] != second[key][field]:
                        raise AuditError(f"disassemblers disagree: {key}/{field}")
            report["status"] = "PASS"
    except (OSError, ValueError, AuditError, StopIteration) as error:
        report["error"] = str(error) or type(error).__name__
        report["status"] = "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"formal-codegen-check: {report['status']}" + (f": {report['error']}" if "error" in report else ""))
    return 0 if report["status"] == "PASS" else 3 if report["missing_tools"] else 1


if __name__ == "__main__":
    sys.exit(main())
