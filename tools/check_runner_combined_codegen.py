#!/usr/bin/env python3
"""Audit Q14 combined observation operations without measuring performance."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys


OPERATIONS = tuple(
    f"cpu_prefetch_combined_{package}_{role}"
    for package in ("r0", "r1", "r2", "l0", "l1")
    for role in ("producer", "consumer")
)
MUTANT = "cpu_prefetch_combined_forbidden_mutant"
WRONG_WRITE_MUTANT = "cpu_prefetch_combined_wrong_write_prefetch_mutant"
WRONG_READ_MUTANT = "cpu_prefetch_combined_wrong_read_prefetch_mutant"
DUPLICATE_READ_MUTANT = "cpu_prefetch_combined_duplicate_read_prefetch_mutant"
SYMBOL_LINE = re.compile(r"^[0-9a-fA-F]+ <(.+)>:$")
CALL_TARGET = re.compile(r"\bcallq?\b[^<]*<(.+)>", re.I)
PREFETCH_INSTRUCTION = re.compile(
    r"\b(prefetchw|prefetchwt1|prefetchnta|prefetcht0|prefetcht1|prefetcht2)\b",
    re.I,
)
FORBIDDEN = re.compile(
    r"(?:operator new|malloc|calloc|realloc|fwrite|fprintf|printf|iostream|"
    r"filesystem|compress|sched_yield|nanosleep|usleep|pthread_mutex)",
    re.I,
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tool_version(tool: str) -> str:
    result = subprocess.run(
        [tool, "--version"], check=False, capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(f"{tool} --version failed")
    for line in result.stdout.splitlines():
        gnu = re.fullmatch(r"GNU objdump \(GNU Binutils\) (.+)", line.strip())
        llvm = re.fullmatch(r"LLVM version (.+)", line.strip())
        if gnu:
            return f"GNU Binutils {gnu.group(1)}"
        if llvm:
            return f"LLVM {llvm.group(1)}"
    raise RuntimeError(f"unrecognized disassembler version: {tool}")


def disassemble(tool: str, binary: pathlib.Path) -> str:
    result = subprocess.run(
        [tool, "--disassemble", "--demangle", "--no-show-raw-insn", str(binary)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(f"{tool} failed: {result.stderr.strip()}")
    return result.stdout.replace(str(binary), "<BINARY>")


def bodies(disassembly: str) -> dict[str, str]:
    output: dict[str, list[str]] = {}
    current: str | None = None
    for line in disassembly.splitlines():
        match = SYMBOL_LINE.match(line.strip())
        if match:
            current = match.group(1)
            output.setdefault(current, [])
        elif current is not None:
            output[current].append(line)
    return {name: "\n".join(lines) for name, lines in output.items() if lines}


def find_symbol(symbols: dict[str, str], marker: str) -> str:
    exact = [name for name in symbols if name == marker]
    matches = exact or [name for name in symbols if marker in name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one symbol for {marker}, found {matches}")
    return matches[0]


def reachable(symbols: dict[str, str], root: str) -> tuple[set[str], list[str]]:
    pending = [root]
    visited: set[str] = set()
    external: list[str] = []
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        for target in CALL_TARGET.findall(symbols[current]):
            internal = target in symbols
            if internal and (
                "cpu_prefetch" in target
                or "cpu_prefetch::" in target
                or "ObservationStream::append" in target
                or "EventArena::" in target
                or "MonotonicRawClock::" in target
            ):
                pending.append(target)
            else:
                external.append(target)
    return visited, external


def expected_prefetches(operation: str) -> list[str]:
    if operation in (
        "cpu_prefetch_combined_r1_producer",
        "cpu_prefetch_combined_r2_producer",
    ):
        return ["prefetchw"]
    if operation in (
        "cpu_prefetch_combined_r1_consumer",
        "cpu_prefetch_combined_r2_consumer",
        "cpu_prefetch_combined_l1_consumer",
    ):
        return ["prefetcht0"]
    return []


def validate_prefetches(text: str, expected: list[str], name: str) -> list[str]:
    observed = [match.lower() for match in PREFETCH_INSTRUCTION.findall(text)]
    if observed != expected:
        raise RuntimeError(
            f"{name} software-prefetch mapping mismatch: "
            f"expected={expected}, observed={observed}"
        )
    return observed


def inspect(disassembly: str) -> dict[str, object]:
    symbols = bodies(disassembly)
    report: dict[str, object] = {}
    for marker in OPERATIONS:
        root = find_symbol(symbols, marker)
        graph, external = reachable(symbols, root)
        text = "\n".join(symbols[name] for name in sorted(graph))
        forbidden = sorted(
            {value for value in [*graph, *external] if FORBIDDEN.search(value)}
        )
        if forbidden:
            raise RuntimeError(f"{marker} reaches forbidden operations: {forbidden}")
        expected = expected_prefetches(marker)
        observed = validate_prefetches(text, expected, marker)
        report[marker] = {
            "status": "PASS",
            "reachable_internal_symbols": sorted(graph),
            "external_calls": sorted(set(external)),
            "expected_prefetch_instructions": expected,
            "observed_prefetch_instructions": observed,
            "call_graph_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "forbidden_operations": [],
        }
    return report


def inspect_mutant(disassembly: str) -> dict[str, object]:
    symbols = bodies(disassembly)
    root = find_symbol(symbols, MUTANT)
    graph, external = reachable(symbols, root)
    detected = sorted(
        {value for value in [*graph, *external] if FORBIDDEN.search(value)}
    )
    if not detected:
        raise RuntimeError("forbidden-work mutant was not rejected")
    prefetch_mutants = (
        (WRONG_WRITE_MUTANT, ["prefetchw"]),
        (WRONG_READ_MUTANT, ["prefetcht0"]),
        (DUPLICATE_READ_MUTANT, ["prefetcht0"]),
    )
    rejected: dict[str, str] = {}
    for marker, expected in prefetch_mutants:
        symbol = find_symbol(symbols, marker)
        try:
            validate_prefetches(symbols[symbol], expected, marker)
        except RuntimeError as error:
            rejected[marker] = str(error)
        else:
            raise RuntimeError(f"software-prefetch mutant was not rejected: {marker}")
    return {
        "status": "EXPECTED_REJECTION",
        "forbidden_work_detected": detected,
        "prefetch_mapping_rejections": rejected,
    }


def ordered(text: str, fragments: tuple[str, ...], name: str) -> None:
    position = -1
    for fragment in fragments:
        next_position = text.find(fragment, position + 1)
        if next_position < 0:
            raise RuntimeError(f"source audit {name} lacks: {fragment}")
        position = next_position


def inspect_sources(root: pathlib.Path) -> dict[str, object]:
    emitter = root / "include/cpu_prefetch/runner/software_prefetch.hpp"
    packages = root / "include/cpu_prefetch/workload/packages.hpp"
    linked = root / "include/cpu_prefetch/queue/linked_spsc.hpp"
    emitter_text = emitter.read_text(encoding="utf-8")
    package_text = packages.read_text(encoding="utf-8")
    linked_text = linked.read_text(encoding="utf-8")
    if emitter_text.count('asm volatile("prefetchw %0"') != 1:
        raise RuntimeError("source audit requires exactly one PREFETCHW emitter")
    if emitter_text.count('asm volatile("prefetcht0 %0"') != 2:
        raise RuntimeError("source audit requires exactly two PREFETCHT0 emitters")
    if '"memory"' in emitter_text:
        raise RuntimeError("software-prefetch emitter must not add a compiler fence")
    if package_text.count(
        "emitter_.ring_producer_write(queue_.producer_slot_target(distance_.slots()))"
    ) != 4:
        raise RuntimeError("ring producer target/site count drift")
    if package_text.count(
        "emitter_.ring_consumer_read(queue_.consumer_slot_target(distance_.slots()))"
    ) != 4:
        raise RuntimeError("ring consumer target/site count drift")
    ordered(
        linked_text,
        (
            "auto* successor = old_sentinel->next.load(std::memory_order_acquire)",
            "if (!boundary_observer.after_dequeue_observation())",
            "prefetch.successor_header(successor)",
            "const auto* event = successor->event",
        ),
        "linked successor acquire/prefetch/demand",
    )
    return {
        "status": "PASS",
        "mapping_id": "X86-64-PREFETCHW-PREFETCHT0-v1",
        "emitter_sha256": sha256(emitter),
        "packages_sha256": sha256(packages),
        "linked_queue_sha256": sha256(linked),
    }


def source_evidence(root: pathlib.Path) -> dict[str, str]:
    relative_paths = (
        "include/cpu_prefetch/lifecycle/executor.hpp",
        "include/cpu_prefetch/queue/linked_spsc.hpp",
        "include/cpu_prefetch/queue/ring_spsc.hpp",
        "include/cpu_prefetch/storage/capture_backend.hpp",
        "include/cpu_prefetch/timing/capture.hpp",
        "include/cpu_prefetch/runner/software_prefetch.hpp",
        "include/cpu_prefetch/workload/packages.hpp",
        "src/storage/raw_observations.cpp",
        "tools/runner_combined_codegen_probe.cpp",
        "tools/runner_combined_codegen_mutant.cpp",
    )
    return {path: sha256(root / path) for path in relative_paths}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=pathlib.Path, required=True)
    parser.add_argument("--mutant", type=pathlib.Path, required=True)
    parser.add_argument("--source-root", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--gnu-objdump", default="objdump")
    parser.add_argument("--llvm-objdump", default="llvm-objdump")
    args = parser.parse_args()
    tools = {
        "GNU_OBJDUMP": shutil.which(args.gnu_objdump),
        "LLVM_OBJDUMP": shutil.which(args.llvm_objdump),
    }
    missing = [name for name, path in tools.items() if path is None]
    report: dict[str, object] = {
        "schema_version": "cpu-prefetch-runner-combined-codegen/2",
        "scope": "correctness-only; no performance observation",
        "software_prefetch_mapping_id": "X86-64-PREFETCHW-PREFETCHT0-v1",
        "binary_sha256": sha256(args.binary),
        "mutant_sha256": sha256(args.mutant),
        "rule_set_sha256": sha256(pathlib.Path(__file__).resolve()),
        "source_evidence": source_evidence(args.source_root),
        "tools": {},
    }
    try:
        report["source_contract"] = inspect_sources(args.source_root)
        for name, tool in tools.items():
            if tool is None:
                report["tools"][name] = {"status": "UNAVAILABLE"}  # type: ignore[index]
                continue
            normal = disassemble(tool, args.binary)
            mutant = disassemble(tool, args.mutant)
            report["tools"][name] = {  # type: ignore[index]
                "status": "PASS",
                "path": tool,
                "version": tool_version(tool),
                "operations": inspect(normal),
                "negative_mutant": inspect_mutant(mutant),
                "full_disassembly_sha256": hashlib.sha256(normal.encode()).hexdigest(),
            }
        report["missing_tools"] = missing
        report["status"] = "BLOCKED_MISSING_TOOL" if missing else "PASS"
    except (OSError, RuntimeError) as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(f"runner-combined-codegen-check: FAIL: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    if missing:
        print(
            "runner-combined-codegen-check: BLOCKED: missing " + ", ".join(missing),
            file=sys.stderr,
        )
        return 3
    print(
        "runner-combined-codegen-check: PASS "
        "(two disassemblers, 10 operations, exact D-047 mapping, four mutants)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
