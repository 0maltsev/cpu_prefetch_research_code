#!/usr/bin/env python3
"""Audit Stage 8 timestamp machine code and source boundary placement."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Final


OPERATION_SYMBOLS: Final = (
    "cpu_prefetch_timing_read",
    "cpu_prefetch_timing_r0_enqueue",
    "cpu_prefetch_timing_r0_dequeue",
    "cpu_prefetch_timing_r1_enqueue",
    "cpu_prefetch_timing_r1_dequeue",
    "cpu_prefetch_timing_r2_enqueue",
    "cpu_prefetch_timing_r2_dequeue",
    "cpu_prefetch_timing_l0_enqueue",
    "cpu_prefetch_timing_l0_dequeue",
    "cpu_prefetch_timing_l1_enqueue",
    "cpu_prefetch_timing_l1_dequeue",
)
MUTANT_SYMBOLS: Final = {
    "cpu_prefetch_timing_syscall_mutant": re.compile(r"\bsyscall\b", re.I),
    "cpu_prefetch_timing_hardware_fence_mutant": re.compile(
        r"\b(?:lock|xchg|mfence|sfence)\b", re.I
    ),
    "cpu_prefetch_timing_direct_counter_mutant": re.compile(r"\brdtscp?\b", re.I),
}
FORBIDDEN_GOOD: Final = re.compile(
    r"\b(?:syscall|rdtsc|rdtscp|cpuid|mfence|sfence|lock)\b", re.I
)
FORBIDDEN_CALL: Final = re.compile(
    r"\b(?:operator new|malloc|calloc|realloc|free|__cxa_throw|"
    r"std::(?:cout|cerr)|printf|fprintf|fwrite|write@)",
    re.I,
)
SYMBOL_LINE: Final = re.compile(r"^[0-9a-fA-F]+ <(.*)>:$")
CALL_TARGET: Final = re.compile(r"\bcallq?\s+(?:0x)?[0-9a-fA-F]+\s+<(.+)>")


def file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def disassemble(tool: str, binary: pathlib.Path) -> str:
    completed = subprocess.run(
        [tool, "--disassemble", "--demangle", "--no-show-raw-insn", str(binary)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{tool} failed: {completed.stderr.strip()}")
    return completed.stdout.replace(str(binary), "<BINARY>")


def tool_version(tool: str) -> str:
    completed = subprocess.run(
        [tool, "--version"], check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{tool} --version failed")
    for line in completed.stdout.splitlines():
        gnu = re.fullmatch(r"GNU objdump \(GNU Binutils\) (.+)", line.strip())
        if gnu:
            return f"GNU Binutils {gnu.group(1)}"
        llvm = re.fullmatch(r"LLVM version (.+)", line.strip())
        if llvm:
            return f"LLVM {llvm.group(1)}"
    raise RuntimeError(f"unrecognized disassembler version from {tool}")


def symbol_body(disassembly: str, symbol: str) -> str:
    collecting = False
    body: list[str] = []
    for line in disassembly.splitlines():
        match = SYMBOL_LINE.match(line.strip())
        if match:
            if collecting:
                break
            collecting = match.group(1) == symbol
            continue
        if collecting:
            body.append(line)
    if not body:
        raise RuntimeError(f"missing or empty symbol: {symbol}")
    return "\n".join(body)


def operation_closure(disassembly: str, symbol: str) -> str:
    pending = [symbol]
    visited: set[str] = set()
    bodies: list[str] = []
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        body = symbol_body(disassembly, current)
        bodies.append(f"<{current}>\n{body}")
        for line in body.splitlines():
            target = CALL_TARGET.search(line)
            if target is None:
                continue
            called = target.group(1)
            if "+0x" in called:
                called = called.split("+0x", maxsplit=1)[0]
            if called.startswith("cpu_prefetch::queue::") and (
                "try_enqueue_with_boundary_observer" in called
                or "try_dequeue_with_boundary_observer" in called
            ):
                pending.append(called)
    return "\n".join(bodies)


def inspect_operations(disassembly: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for symbol in OPERATION_SYMBOLS:
        body = symbol_body(disassembly, symbol)
        closure = operation_closure(disassembly, symbol)
        forbidden = sorted(set(FORBIDDEN_GOOD.findall(closure)))
        if forbidden:
            raise RuntimeError(f"{symbol} has forbidden instructions: {forbidden}")
        if FORBIDDEN_CALL.search(closure):
            raise RuntimeError(f"{symbol} has a forbidden runtime call")
        if "clock_gettime" not in closure:
            raise RuntimeError(f"{symbol} does not retain the selected clock call")
        result[symbol] = {
            "status": "PASS",
            "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "operation_closure_sha256": hashlib.sha256(closure.encode()).hexdigest(),
            "selected_clock_call_present": True,
        }
    return result


def inspect_mutants(disassembly: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for symbol, rejection in MUTANT_SYMBOLS.items():
        body = symbol_body(disassembly, symbol)
        matches = sorted(set(rejection.findall(body)))
        if not matches:
            raise RuntimeError(f"negative mutant was not rejected: {symbol}")
        result[symbol] = {
            "status": "EXPECTED_REJECTION",
            "detected": matches,
            "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        }
    return result


def ordered(text: str, fragments: tuple[str, ...], name: str) -> None:
    position = -1
    for fragment in fragments:
        next_position = text.find(fragment, position + 1)
        if next_position < 0:
            raise RuntimeError(f"source audit {name} lacks: {fragment}")
        position = next_position


def inspect_sources(source_root: pathlib.Path) -> dict[str, object]:
    clock = source_root.joinpath("include/cpu_prefetch/timing/clock.hpp")
    ring = source_root.joinpath("include/cpu_prefetch/queue/ring_spsc.hpp")
    linked = source_root.joinpath("include/cpu_prefetch/queue/linked_spsc.hpp")
    capture = source_root.joinpath("include/cpu_prefetch/timing/capture.hpp")
    mutant = source_root.joinpath("tools/timing_codegen_mutant.cpp")
    paths = (clock, ring, linked, capture, mutant)
    contents = {path: path.read_text(encoding="utf-8") for path in paths}

    ordered(
        contents[clock],
        (
            "std::atomic_signal_fence(std::memory_order_seq_cst);",
            "::clock_gettime(CLOCK_MONOTONIC_RAW, &value)",
            "std::atomic_signal_fence(std::memory_order_seq_cst);",
        ),
        "clock compiler fences",
    )
    ordered(
        contents[ring],
        (
            "slot.load(std::memory_order_acquire)",
            "if (!boundary_observer.before_enqueue_publication())",
            "slot.store(event.get(), std::memory_order_release)",
        ),
        "ring p before release publication",
    )
    ordered(
        contents[ring],
        (
            "const auto* event = slot.load(std::memory_order_acquire)",
            "if (!boundary_observer.after_dequeue_observation())",
            "slot.store(nullptr, std::memory_order_release)",
        ),
        "ring q after acquire observation",
    )
    ordered(
        contents[linked],
        (
            "auto* node = recycler_slot.load(std::memory_order_acquire)",
            "if (!boundary_observer.before_enqueue_publication())",
            "producer_->tail->next.store(node, std::memory_order_release)",
        ),
        "linked p before release publication",
    )
    ordered(
        contents[linked],
        (
            "old_sentinel->next.load(std::memory_order_acquire)",
            "if (!boundary_observer.after_dequeue_observation())",
            "prefetch.successor_header(successor)",
            "recycler_slot.store(old_sentinel, std::memory_order_release)",
        ),
        "linked q before prefetch and reuse",
    )
    ordered(
        contents[capture],
        (
            "const auto handle_begin = clock.read();",
            "const auto selection = arena.select(logical_sequence);",
            "const auto lookup_completion = clock.read();",
            "const auto enqueue_invocation = clock.read();",
            "package.try_enqueue_with_boundary_observer(",
            "const auto attempt_completion = clock.read();",
        ),
        "producer capture sequence",
    )
    ordered(
        contents[capture],
        (
            "const auto dequeue_invocation = clock.read();",
            "package.try_dequeue_with_boundary_observer(boundary_observer)",
            "const auto dequeue_completion = clock.read();",
            "arena.access_and_mix(queue_result.result.event, consumer_state)",
            "const auto action_completion = clock.read();",
        ),
        "consumer capture sequence",
    )

    mutant_text = contents[mutant]
    mutant_rules = {
        "p_moved_after_publication": mutant_text.find("queue->try_enqueue(event)")
        < mutant_text.find("read_monotonic_raw_absolute()"),
        "q_moved_before_observation": mutant_text.rfind(
            "read_monotonic_raw_absolute()"
        )
        < mutant_text.rfind("queue->try_dequeue()"),
        "compiler_fences_removed":
            "cpu_prefetch_timing_no_compiler_fence_mutant" in mutant_text,
        "clock_id_changed":
            "clock_gettime(CLOCK_MONOTONIC, value)" in mutant_text,
        "syscall_forced": "SYS_clock_gettime" in mutant_text,
        "hardware_fence_added": "atomic_thread_fence" in mutant_text,
    }
    if not all(mutant_rules.values()):
        raise RuntimeError("one or more source-level timing mutants were not detected")
    return {
        "status": "PASS",
        "files": {str(path): file_sha256(path) for path in paths},
        "boundary_rules": "PASS",
        "negative_mutants": {
            name: "EXPECTED_REJECTION" for name in mutant_rules
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=pathlib.Path, required=True)
    parser.add_argument("--mutant", type=pathlib.Path, required=True)
    parser.add_argument("--source-root", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--gnu-objdump", default="objdump")
    parser.add_argument("--llvm-objdump", default="llvm-objdump")
    parser.add_argument("--allow-missing-secondary", action="store_true")
    args = parser.parse_args()

    report: dict[str, object] = {
        "schema_version": "cpu-prefetch-timing-codegen/1",
        "scope": "correctness-only; no latency or performance inference",
        "binary": {"path": str(args.binary), "sha256": file_sha256(args.binary)},
        "mutant": {"path": str(args.mutant), "sha256": file_sha256(args.mutant)},
        "rule_set_sha256": file_sha256(pathlib.Path(__file__).resolve()),
        "tools": {},
    }
    tools = {
        "GNU_OBJDUMP": shutil.which(args.gnu_objdump),
        "LLVM_OBJDUMP": shutil.which(args.llvm_objdump),
    }
    missing = [name for name, path in tools.items() if path is None]
    try:
        report["source_audit"] = inspect_sources(args.source_root)
        for name, tool in tools.items():
            if tool is None:
                report["tools"][name] = {"status": "UNAVAILABLE"}
                continue
            operations = disassemble(tool, args.binary)
            mutants = disassemble(tool, args.mutant)
            report["tools"][name] = {
                "status": "PASS",
                "path": tool,
                "version": tool_version(tool),
                "operations": inspect_operations(operations),
                "negative_mutants": inspect_mutants(mutants),
                "full_disassembly_sha256": hashlib.sha256(
                    operations.encode()
                ).hexdigest(),
            }
        report["status"] = "BLOCKED_MISSING_TOOL" if missing else "PASS"
        report["missing_tools"] = missing
    except (OSError, UnicodeError, RuntimeError) as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"timing-codegen-check: FAIL: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if missing:
        if args.allow_missing_secondary and missing == ["LLVM_OBJDUMP"]:
            print("timing-codegen-check: partial evidence retained")
            return 0
        print("timing-codegen-check: BLOCKED: " + ", ".join(missing), file=sys.stderr)
        return 3
    print("timing-codegen-check: PASS (11 operations, 6 source mutants, 3 machine mutants)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
