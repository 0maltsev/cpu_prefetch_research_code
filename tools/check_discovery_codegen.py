#!/usr/bin/env python3
"""Fail-closed x86-64 GCC discovery-worker machine-code qualification.

The input is the packaged runner, not a replacement template probe. Four real
native session instantiations must have native-entry reference paths and actual
session callers. Cold preparation is outside their closures. A small, deliberately
restricted AT&T dataflow decoder tracks the SysV ring argument through registers
and spills to the actual slot load/store. CFG clock counts qualify the brackets;
unknown shapes fail, rather than substituting a source-order assertion.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

SCHEMA = "cpu-prefetch-discovery-codegen/1"
SOURCE_PATHS = (
    "src/calibration/native_discovery_capture.cpp",
    "include/cpu_prefetch/calibration/native_discovery_capture.hpp",
    "include/cpu_prefetch/calibration/discovery_capture.hpp",
    "include/cpu_prefetch/calibration/discovery_session.hpp",
    "include/cpu_prefetch/calibration/discovery_event_capture.hpp",
    "include/cpu_prefetch/calibration/discovery_ring_backend.hpp",
    "include/cpu_prefetch/calibration/mapped_discovery_runtime.hpp",
    "include/cpu_prefetch/calibration/mapped_discovery_preparation.hpp",
    "include/cpu_prefetch/calibration/caller_owned_trace.hpp",
    "include/cpu_prefetch/queue/ring_spsc.hpp",
    "include/cpu_prefetch/timing/clock.hpp",
    "src/timing/clock.cpp",
    "src/storage/raw_observations.cpp",
    "src/workload/records.cpp",
)
SOURCE_EVIDENCE_PATHS = SOURCE_PATHS
SYMBOL = re.compile(r"^([0-9a-fA-F]+) <(.+)>:$")
INSTRUCTION = re.compile(r"^\s*([0-9a-fA-F]+):\s+([a-zA-Z][a-zA-Z0-9_.]*)\s*(.*?)\s*$")
REFERENCE = re.compile(r"<(.+)>")
ALLOWED_EXTERNAL = {"clock_gettime", "memset", "memcpy", "memmove", "__stack_chk_fail"}
FORBIDDEN = re.compile(r"(?:prefetch|^(?:lock|syscall|sysenter|int|int3|rdtsc|rdtscp|cpuid|mfence|sfence|lfence)$)", re.I)
FORBIDDEN_NAME = re.compile(r"operator (?:new|delete)|malloc|calloc|realloc|\bfree\b|::parse|from_chars|::json::|printf|fprintf|fwrite|fputs|::cout|::cerr|pthread_|mutex|futex|filesystem|sched_yield|nanosleep|usleep",re.I)
CALLER_SAVED = ("rax", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11")


class AuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class Instruction:
    address: int
    mnemonic: str
    operands: str
    target: str | None


@dataclass(frozen=True)
class Function:
    name: str
    instructions: tuple[Instruction, ...]


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def symbol_base(name: str) -> str:
    return re.sub(r"\+0x[0-9a-fA-F]+$", "", name)


def decode(text: str) -> dict[str, Function]:
    functions: dict[str, list[Instruction]] = {}
    starts: dict[int, str] = {}
    reference_addresses: dict[int, int] = {}
    current = None
    for line in text.splitlines():
        label = SYMBOL.fullmatch(line.strip())
        if label:
            current = label[2]
            if current in functions:
                current += f" [address 0x{int(label[1],16):x}]"
            starts[int(label[1],16)] = current
            functions[current] = []
            continue
        match = INSTRUCTION.fullmatch(line)
        if current is None or not match:
            continue
        reference = REFERENCE.search(match[3])
        target_address = re.search(r"(?:0x)?([0-9a-fA-F]+)\s+<", match[3])
        if reference and target_address:
            offset = re.search(r"\+0x([0-9a-fA-F]+)$", reference[1])
            reference_addresses[int(match[1],16)] = int(target_address[1],16) - (int(offset[1],16) if offset else 0)
        operand = match[3].split("#", 1)[0].strip()
        functions[current].append(Instruction(int(match[1], 16), match[2].lower(), operand,
            symbol_base(reference[1]) if reference else None))
    if not functions:
        raise AuditError("no decoded functions")
    return {name: Function(name, tuple(Instruction(i.address,i.mnemonic,i.operands,
        starts.get(reference_addresses.get(i.address),i.target)) for i in items))
        for name, items in functions.items() if items}


def is_call(ins: Instruction) -> bool:
    return ins.mnemonic in ("call", "callq")


def is_jump(ins: Instruction) -> bool:
    return ins.mnemonic.startswith("j")


def external_name(name: str) -> str:
    return name.split("@", 1)[0]


def closure(functions: dict[str, Function], root: str) -> tuple[set[str], set[str]]:
    pending = [root]
    visited: set[str] = set()
    external: set[str] = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        if FORBIDDEN_NAME.search(name):
            raise AuditError(f"forbidden work in measured closure: {name}")
        for ins in functions[name].instructions:
            if FORBIDDEN.search(ins.mnemonic):
                raise AuditError(f"forbidden instruction {ins.mnemonic} in {name}")
            if ins.mnemonic.startswith("xchg"):
                args = split_operands(ins.operands)
                if len(args) != 2 or not all(arg.startswith("%") for arg in args):
                    raise AuditError(f"atomic exchange in {name}")
            if not (is_call(ins) or is_jump(ins)):
                continue
            if ins.target is None:
                raise AuditError(f"unresolved/indirect transfer in {name}: {ins}")
            if ins.target == name:
                continue
            if "@" in ins.target or ins.target not in functions:
                target = external_name(ins.target)
                if target not in ALLOWED_EXTERNAL:
                    raise AuditError(f"unapproved external transfer: {target}")
                external.add(target)
            else:
                pending.append(ins.target)
    return visited, external


def split_operands(value: str) -> list[str]:
    return [item.strip() for item in re.split(r",(?![^()]*\))", value)]


def register(value: str) -> str | None:
    if not value.startswith("%"):
        return None
    name = value[1:]
    aliases = {"eax":"rax", "ax":"rax", "al":"rax", "ah":"rax",
        "ebx":"rbx", "bx":"rbx", "bl":"rbx", "bh":"rbx",
        "ecx":"rcx", "cx":"rcx", "cl":"rcx", "ch":"rcx",
        "edx":"rdx", "dx":"rdx", "dl":"rdx", "dh":"rdx",
        "esi":"rsi", "si":"rsi", "sil":"rsi", "edi":"rdi", "di":"rdi", "dil":"rdi",
        "ebp":"rbp", "bp":"rbp", "bpl":"rbp", "esp":"rsp", "sp":"rsp", "spl":"rsp"}
    return aliases.get(name, re.sub(r"^(r\d+)[dwb]$", r"\1", name))


def immediate(value: str) -> int | None:
    try:
        return int(value.removeprefix("$"), 0)
    except ValueError:
        return None


def memory(value: str) -> tuple[int, str, str | None, int] | None:
    match = re.fullmatch(r"(-?(?:0x[0-9a-fA-F]+|[0-9]+))?\((%\w+)(?:,(%\w+)(?:,([1248]))?)?\)", value)
    if not match:
        return None
    return (int(match[1], 0) if match[1] else 0, register(match[2]),
            register(match[3]) if match[3] else None, int(match[4] or 1))


# Symbolic values: (kind, integer). Ring offsets are the accepted x86-64 SysV
# RingSpscQueue ABI: slots at 64, producer cursor at 72, consumer cursor at 80.
# Only a load derived from that actual argument and an indexed slot address is
# accepted. An ABI/compiler-shape change must update this checked rule set.
Value = tuple[str, int]


def address(value: str, registers: dict[str, Value]) -> Value | None:
    parsed = memory(value)
    if parsed is None:
        return None
    offset, base, index, scale = parsed
    source = registers.get(base)
    if source is None:
        return None
    if index is not None:
        if source == ("slots", 0) and registers.get(index) == ("position", 0) and scale == 8 and offset == 0:
            return ("slot", 0)
        return None
    return (source[0], source[1] + offset)


def value_of(value: str, regs: dict[str, Value], stack: dict[int, Value], role: str) -> Value | None:
    reg = register(value)
    if reg:
        if value != "%" + reg and "low:" + value in regs:
            return regs["low:" + value]
        result = regs.get(reg)
        if value != "%" + reg and result and result[0] == "constant":
            width = 32 if value.startswith("%e") or value.endswith("d") else 8 if value.endswith(("l","h","b")) else 16
            return ("constant", (result[1] >> (8 if value.endswith("h") else 0)) & ((1 << width)-1))
        return result if value == "%" + reg else None
    if value.startswith("$"):
        number = immediate(value)
        return None if number is None else ("constant", number)
    source = address(value, regs)
    if source is None:
        return None
    kind, offset = source
    if kind == "stack":
        return stack.get(offset)
    if source == ("ring", 64):
        return ("slots", 0)
    if source == ("ring", 72 if role == "producer" else 80):
        return ("cursor", 0)
    if source == ("cursor", 0):
        return ("position", 0)
    return None


def successors(function: Function, index: int, zero: bool | None = None) -> tuple[int, ...]:
    ins = function.instructions[index]
    following = (index + 1,) if index + 1 < len(function.instructions) else ()
    if ins.mnemonic.startswith("ret") or ins.mnemonic in ("ud2", "hlt"):
        return ()
    if not is_jump(ins):
        if is_call(ins) and ins.target and external_name(ins.target) == "__stack_chk_fail":
            return ()
        return following
    match = re.match(r"(?:0x)?([0-9a-fA-F]+)\s+<", ins.operands)
    if match is None:
        raise AuditError("indirect event control flow")
    target = int(match[1], 16)
    destinations = [i for i, item in enumerate(function.instructions) if item.address == target]
    if len(destinations) != 1:
        raise AuditError("event control flow leaves its audited function")
    if ins.mnemonic in ("jmp", "jmpq"):
        return (destinations[0],)
    if zero is not None and ins.mnemonic in ("je", "jz", "jne", "jnz"):
        taken = zero if ins.mnemonic in ("je", "jz") else not zero
        return (destinations[0],) if taken else following
    return (*following, destinations[0])


def is_clock(ins: Instruction) -> bool:
    return is_call(ins) and (ins.target == "cpu_prefetch::timing::MonotonicRawClock::read() const" or
                            (ins.target is not None and external_name(ins.target) == "clock_gettime"))


def verify_clock_arguments(function: Function) -> list[str]:
    clocks = [index for index,ins in enumerate(function.instructions) if is_call(ins) and
              ins.target is not None and external_name(ins.target) == "clock_gettime"]
    if not clocks:
        return []
    predecessors: dict[int, set[int]] = {index:set() for index in range(len(function.instructions))}
    for index in range(len(function.instructions)):
        for target in successors(function,index):
            predecessors[target].add(index)
    for clock in clocks:
        pending = list(predecessors[clock])
        seen = set()
        definitions = set()
        while pending:
            index = pending.pop()
            if index in seen:
                continue
            seen.add(index)
            ins = function.instructions[index]
            args = split_operands(ins.operands)
            if args and register(args[-1]) == "rdi" and not ins.mnemonic.startswith(("cmp","test")):
                if ins.mnemonic not in ("mov", "movl", "movq") or len(args) != 2 or immediate(args[0]) != 4:
                    raise AuditError("clock_gettime has non-RAW or unproved clock argument")
                definitions.add(index)
                continue
            if is_call(ins) or not predecessors[index]:
                raise AuditError("clock_gettime argument lacks dominating RAW definition")
            pending.extend(predecessors[index])
        if not definitions:
            raise AuditError("clock argument is unproved")
    return [hex(function.instructions[index].address) for index in clocks]


def event_brackets(function: Function, role: str) -> dict[str, object]:
    # Separate count contexts prevent false merging of pre/post-boundary paths.
    states: dict[tuple[int, int, str | None], tuple[dict[str, Value], dict[int, Value]]] = {
        (0, 0, None): ({"rdx": ("ring", 0), "rsp": ("stack", 0)}, {})}
    pending = deque([(0, 0, None)])
    witnesses: dict[str, dict[int, set[int]]] = {key: {} for key in ("slot_load", "slot_store", "select", "action")}
    clock_sites: set[int] = set()
    updates = 0
    while pending:
        index, clocks, obligation = pending.popleft()
        before_regs, before_stack = states[(index, clocks, obligation)]
        regs, stack = dict(before_regs), dict(before_stack)
        ins = function.instructions[index]
        if ins.mnemonic not in {"add","addq","call","callq","cmove","cmoveq","cmp","cmpb","cmpq","cmpl","cmpw",
                "jb","je","jmp","jne","jz","jnz","lea","leaq","mov","movaps","movb","movdqa","movdqu","movhps","movl","movq","movw","movups","movzbl","movzwl",
                "nop","nopl","nopw","pop","popq","push","pushq","pxor","rep","ret","retq","sub","subq","test","testb","testl","testq","testw","xor","xorl","xorq","xchg"}:
            raise AuditError(f"unsupported event instruction: {ins.mnemonic}")
        args = split_operands(ins.operands)
        destination = address(args[-1], regs) if args else None
        source = address(args[0], regs) if args else None
        def witness(kind: str) -> None:
            witnesses[kind].setdefault(ins.address, set()).add(clocks)
        if ins.mnemonic in ("mov", "movq") and len(args) == 2:
            if source == ("slot", 0) and register(args[1]):
                witness("slot_load")
                obligation = "slot_load"
            if destination == ("slot", 0):
                witness("slot_store")
                obligation = "slot_store"
                if role == "consumer" and value_of(args[0], regs, stack, role) != ("constant", 0):
                    raise AuditError("consumer slot release is not zero")
        if is_call(ins):
            if ins.target and "EventArena::select(" in ins.target:
                witness("select")
            if ins.target and "EventArena::access_and_mix(" in ins.target:
                witness("action")
            if is_clock(ins):
                if external_name(ins.target or "") == "clock_gettime" and regs.get("rdi") != ("constant", 4):
                    raise AuditError("event clock is not explicit CLOCK_MONOTONIC_RAW")
                clocks += 1
                obligation = None
                clock_sites.add(ins.address)
                if clocks > 7:
                    raise AuditError("event contains unexpected/repeated clock reads")
            for reg in CALLER_SAVED:
                regs.pop(reg, None)
                for key in list(regs):
                    if key.startswith("low:") and register(key[4:]) == reg:
                        regs.pop(key)
            regs.pop("zf", None)
            for key in list(regs):
                if key.startswith("eq:"):
                    regs.pop(key)
        elif ins.mnemonic.startswith("push"):
            if "rsp" in regs:
                regs["rsp"] = ("stack", regs["rsp"][1] - 8)
        elif ins.mnemonic.startswith("pop"):
            if "rsp" in regs:
                regs["rsp"] = ("stack", regs["rsp"][1] + 8)
            regs.pop(register(args[0]), None)
        elif ins.mnemonic == "rep":
            if "stos" not in ins.operands:
                raise AuditError("unsupported repeat instruction in event")
            if regs.get("rdi", (None,0))[0] == "stack":
                stack.clear()
            regs.pop("rdi",None)
            regs.pop("rcx",None)
        elif ins.mnemonic.startswith(("cmp", "test")) and len(args) == 2:
            lhs, rhs = (value_of(arg, regs, stack, role) for arg in args)
            regs.pop("zf", None)
            for key in list(regs):
                if key.startswith("eq:"):
                    regs.pop(key)
            if ins.mnemonic.startswith("test") and args[0] == args[1] and register(args[0]):
                regs["eq:"+args[0]] = ("constant",0)
            elif ins.mnemonic.startswith("cmp") and lhs is not None and lhs[0] == "constant" and register(args[1]):
                regs["eq:"+args[1]] = lhs
            if lhs is not None and rhs is not None and lhs[0] == rhs[0] == "constant":
                equal = lhs[1] == rhs[1] if ins.mnemonic.startswith("cmp") else (lhs[1] & rhs[1]) == 0
                regs["zf"] = ("constant", int(equal))
        elif len(args) >= 2:
            out = register(args[-1])
            result = None
            if ins.mnemonic in ("mov", "movq", "movl", "movabs", "movabsq"):
                result = value_of(args[0], regs, stack, role)
            elif ins.mnemonic in ("lea", "leaq"):
                result = address(args[0], regs)
            elif ins.mnemonic in ("sub", "subq", "add", "addq") and out == "rsp" and "rsp" in regs:
                amount = immediate(args[0])
                if amount is not None:
                    result = ("stack", regs["rsp"][1] + (-amount if ins.mnemonic.startswith("sub") else amount))
            elif ins.mnemonic in ("xor", "xorl", "xorq") and args[0] == args[1]:
                result = ("constant", 0)
            if ins.mnemonic.startswith(("sub", "add", "xor", "and", "or", "imul", "shl", "shr", "sar")):
                regs.pop("zf", None)
                for key in list(regs):
                    if key.startswith("eq:"):
                        regs.pop(key)
                if result == ("constant", 0):
                    regs["zf"] = ("constant", 1)
            if out:
                regs.pop(out, None)
                for key in list(regs):
                    if key.startswith("low:") and register(key[4:]) == out:
                        regs.pop(key)
                if result is not None:
                    regs[out] = result
            elif destination and destination[0] == "stack":
                start = destination[1]
                width = 16 if "xmm" in ins.operands else 32 if "ymm" in ins.operands else 8
                for key in list(stack):
                    if key < start + width and start < key + 8:
                        del stack[key]
                if result is not None:
                    stack[start] = result
        following = successors(function, index, bool(regs["zf"][1]) if "zf" in regs else None)
        if not following and obligation is not None:
            raise AuditError(f"{role} {obligation} can exit before its following clock")
        for next_index in following:
            next_regs = dict(regs)
            if ins.mnemonic in ("je", "jz", "jne", "jnz"):
                taken = next_index != index + 1
                equal = taken if ins.mnemonic in ("je", "jz") else not taken
                if equal:
                    for name,known in regs.items():
                        if name.startswith("eq:"):
                            operand = name[3:]
                            reg = register(operand)
                            next_regs[reg if operand == "%"+reg else "low:"+operand] = known
            key = (next_index, clocks, obligation)
            previous = states.get(key)
            if previous is None:
                merged = (next_regs, dict(stack))
            else:
                merged = ({k:v for k,v in previous[0].items() if next_regs.get(k) == v},
                          {k:v for k,v in previous[1].items() if stack.get(k) == v})
            if previous != merged:
                states[key] = merged
                pending.append(key)
                updates += 1
                if updates > 100000:
                    raise AuditError("event dataflow exceeds finite qualification bound")
    expected = {"slot_load": 4 if role == "producer" else 2,
                "slot_store": 6 if role == "producer" else 4,
                "select" if role == "producer" else "action": 1 if role == "producer" else 5}
    for name, count in expected.items():
        observed = witnesses[name]
        if len(observed) != 1 or next(iter(observed.values())) != {count}:
            raise AuditError(f"{role} {name} bracket mismatch: {observed}, expected one site after {count} clocks")
    # A witness discovered on one path is insufficient: its final joined
    # provenance must remain the ring slot on every incoming abstract state.
    for kind in ("slot_load","slot_store"):
        site=next(iter(witnesses[kind]))
        for (index,_,_), (regs,_) in states.items():
            ins=function.instructions[index]
            if ins.address == site:
                args=split_operands(ins.operands)
                operand=args[0] if kind == "slot_load" else args[-1]
                if address(operand,regs) != ("slot",0):
                    raise AuditError(f"{role} {kind} provenance is not established on every path")
    return {"status":"PASS", "abi":"X86_64_SYSV_RING_ARGUMENT_RDX_SLOTS64_CURSOR72_80",
            "clock_sites":[hex(n) for n in sorted(clock_sites)],
            "witnesses":{k:{hex(a):sorted(c) for a,c in v.items()} for k,v in witnesses.items()},
            "dataflow_states":len(states)}


def reference_path(functions: dict[str, Function], root: str, goal: str) -> list[str]:
    pending = deque([root])
    parents: dict[str, str | None] = {root: None}
    while pending:
        name = pending.popleft()
        if name == goal:
            path = [name]
            while parents[path[-1]] is not None:
                path.append(parents[path[-1]])
            return list(reversed(path))
        for ins in functions[name].instructions:
            if ins.target in functions and ins.target not in parents:
                parents[ins.target] = name
                pending.append(ins.target)
    raise AuditError("native entry has no machine-code reference path to measured worker")


def inspect(text: str) -> dict[str, object]:
    functions = decode(text)
    entries = [name for name in functions if name.startswith("cpu_prefetch::calibration::run_native_discovery_capture(") and "[clone" not in name and "(.cold)" not in name]
    if len(entries) != 1:
        raise AuditError("expected exactly one production native capture entry")
    roots = [name for name in functions if "capture_discovery_worker<" in name]
    if len(roots) != 4:
        raise AuditError(f"expected four actual measured workers, found {len(roots)}")
    operations = {}
    event_reports = {}
    for role_number, role in enumerate(("producer", "consumer")):
        for phase_number, phase in ((1,"warmup"),(2,"measurement")):
            matches = [name for name in roots if f"RingWorker){role_number}>" in name and
                       (f"{{lambda(unsigned long)#{phase_number}}}" in name or
                        ("::'lambda'(unsigned long)>" if phase_number == 1 else "::'lambda0'(unsigned long)>") in name) and
                       "MappedDiscoveryRuntime<cpu_prefetch::timing::MonotonicRawClock" in name and
                       "MappedDiscoveryThreads<cpu_prefetch::platform::LinuxOwnerMemoryOperations>" in name and
                       "(anonymous namespace)::Bridge" in name]
            if len(matches) != 1:
                raise AuditError(f"missing exact native {phase}/{role} instantiation")
            root = matches[0]
            graph, external = closure(functions, root)
            clock_arguments = {name:sites for name in sorted(graph) if (sites := verify_clock_arguments(functions[name]))}
            event = [name for name in graph if f"capture_discovery_{role}_event<cpu_prefetch::timing::MonotonicRawClock, cpu_prefetch::calibration::CallerOwnedRingDemandTrace>" in name]
            if len(event) != 1 or not any(f"{role.title()}ObservationStream::append(" in name for name in graph):
                raise AuditError("measured loop lacks actual event/primary writer closure")
            direct_callers = [name for name,fn in functions.items() if name not in graph and
                "run_discovery_session<" in name and f"RingWorker){role_number}>" in name and
                any(is_call(i) and i.target == root for i in fn.instructions)]
            if len(direct_callers) != 1:
                raise AuditError("measured loop lacks unique actual session caller")
            if not any(is_jump(i) and i.target == root and int(i.operands.split()[0].removeprefix("0x"),16) < i.address for i in functions[root].instructions):
                raise AuditError("worker has no measured iteration back edge")
            event_reports[role] = event_brackets(functions[event[0]], role)
            operations[f"{phase}_{role}"] = {"status":"PASS", "root":root,
                "root_address":hex(functions[root].instructions[0].address),
                "native_reference_path":reference_path(functions,entries[0],direct_callers[0]),
                "actual_session_caller":direct_callers[0], "event_symbol":event[0],
                "reachable_internal_symbols":sorted(graph), "external_calls":sorted(external),
                "raw_clock_call_sites":clock_arguments,
                "instruction_graph_sha256":hashlib.sha256(repr([functions[n] for n in sorted(graph)]).encode()).hexdigest()}
    return {"status":"PASS", "operations":operations, "event_boundaries":event_reports,
            "external_scope":"clock_gettime resolution qualified separately; bounded memory helpers; stack-check failure is a fatal-only exit"}


def disassemble(tool: str, binary: Path) -> str:
    result = subprocess.run([tool,"--disassemble","--demangle","--no-show-raw-insn",str(binary)],capture_output=True,text=True,check=False)
    if result.returncode:
        raise AuditError(f"disassembler failed: {tool}: {result.stderr.strip()}")
    return result.stdout


def tool_version(tool: str, kind: str) -> str:
    result = subprocess.run([tool,"--version"],capture_output=True,text=True,check=False)
    if result.returncode:
        raise AuditError("disassembler version query failed")
    match = re.search(r"GNU objdump \(GNU Binutils\) (\S+)" if kind == "GNU_OBJDUMP" else r"LLVM version (\S+)",result.stdout)
    if match is None or (kind == "LLVM_OBJDUMP" and match[1].split(".")[0] != "22"):
        raise AuditError(f"unaccepted {kind} version")
    return match[1]


def validate_report_bindings(report: dict[str, object], *, binary: Path, source_root: Path) -> None:
    """Verify exact release custody bindings; does not rerun disassembly."""
    if not isinstance(report,dict) or report.get("schema_version") != SCHEMA or report.get("binary_role") != "ACTUAL_NATIVE_DISCOVERY_WORKER" or report.get("status") != "PASS" or report.get("missing_tools") != []:
        raise AuditError("discovery report identity/status is not accepted")
    if report.get("binary_sha256") != sha256(binary) or report.get("rule_set_sha256") != sha256(source_root / "tools/check_discovery_codegen.py"):
        raise AuditError("discovery binary/rule binding changed")
    if report.get("source_evidence") != {path:sha256(source_root/path) for path in SOURCE_EVIDENCE_PATHS}:
        raise AuditError("discovery source evidence changed")
    evidence = report.get("tools")
    if not isinstance(evidence,dict) or set(evidence) != {"GNU_OBJDUMP","LLVM_OBJDUMP"}:
        raise AuditError("discovery requires exactly both disassemblers")
    for name, item in evidence.items():
        if not isinstance(item,dict) or item.get("status") != "PASS" or not isinstance(item.get("version"),str):
            raise AuditError("disassembler did not pass")
        if name == "LLVM_OBJDUMP" and item["version"].split(".")[0] != "22":
            raise AuditError("discovery requires LLVM22")
        if not re.fullmatch(r"[0-9a-f]{64}",str(item.get("full_disassembly_sha256",""))):
            raise AuditError("missing disassembly digest")
        operations = item.get("operations")
        if not isinstance(operations,dict) or set(operations) != {f"{phase}_{role}" for phase in ("warmup","measurement") for role in ("producer","consumer")}:
            raise AuditError("missing native worker operations")
        for operation in operations.values():
            if not isinstance(operation,dict) or operation.get("status") != "PASS" or not operation.get("native_reference_path") or not operation.get("raw_clock_call_sites"):
                raise AuditError("native worker proof incomplete")
        boundaries = item.get("event_boundaries")
        if not isinstance(boundaries,dict) or set(boundaries) != {"producer","consumer"} or any(not isinstance(v,dict) or v.get("status") != "PASS" for v in boundaries.values()):
            raise AuditError("missing event-boundary proof")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary",type=Path,required=True)
    parser.add_argument("--source-root",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--gnu-objdump",default="objdump")
    parser.add_argument("--llvm-objdump",default="llvm-objdump")
    args = parser.parse_args(argv)
    report = {"schema_version":SCHEMA,"binary_role":"ACTUAL_NATIVE_DISCOVERY_WORKER",
              "status":"FAIL","tools":{},"missing_tools":[]}
    try:
        report.update(binary_sha256=sha256(args.binary),rule_set_sha256=sha256(Path(__file__)),
                      source_evidence={name:sha256(args.source_root/name) for name in SOURCE_PATHS})
        for kind, configured in (("GNU_OBJDUMP",args.gnu_objdump),("LLVM_OBJDUMP",args.llvm_objdump)):
            tool = shutil.which(configured)
            if tool is None:
                report["missing_tools"].append(kind)
                report["tools"][kind] = {"status":"UNAVAILABLE"}
                continue
            version = tool_version(tool,kind)
            text = disassemble(tool,args.binary)
            report["tools"][kind] = {"status":"PASS","version":version,"path":tool,
                "full_disassembly_sha256":hashlib.sha256(text.encode()).hexdigest(), **inspect(text)}
        report["status"] = "BLOCKED_MISSING_TOOL" if report["missing_tools"] else "PASS"
        if report["status"] == "PASS":
            first,second = (report["tools"][name] for name in ("GNU_OBJDUMP","LLVM_OBJDUMP"))
            for role in ("producer","consumer"):
                if first["event_boundaries"][role]["witnesses"] != second["event_boundaries"][role]["witnesses"]:
                    raise AuditError("disassemblers disagree on event machine witnesses")
            for name in first["operations"]:
                if first["operations"][name]["root_address"] != second["operations"][name]["root_address"]:
                    raise AuditError("disassemblers disagree on worker entry addresses")
    except (OSError, AuditError, ValueError) as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(f"discovery-codegen-check: {report['status']}" + (f": {report['error']}" if "error" in report else ""))
    return 0 if report["status"] == "PASS" else 3 if report["missing_tools"] else 1


if __name__ == "__main__":
    sys.exit(main())
