#!/usr/bin/env python3
"""Strict dual-disassembler audit for the D-052/D-053 counted traversals."""

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


REGULAR: Final = "cpu_prefetch_q15_regular_counted_traversal"
POINTER: Final = "cpu_prefetch_q15_pointer_counted_traversal"
REGULAR_MUTANT: Final = "cpu_prefetch_q15_regular_counted_traversal_mutant"
POINTER_MUTANT: Final = "cpu_prefetch_q15_pointer_counted_traversal_mutant"
SYMBOL_LINE: Final = re.compile(r"^[0-9a-fA-F]+ <([^>]+)>:$")
INSTRUCTION_LINE: Final = re.compile(
    r"^\s*[0-9a-fA-F]+:\s+([a-zA-Z0-9_.]+)\s*(.*?)\s*$"
)


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
        raise RuntimeError(f"missing or empty disassembly symbol: {symbol}")
    return "\n".join(body)


def instructions(body: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for line in body.splitlines():
        match = INSTRUCTION_LINE.match(line)
        if match:
            result.append((match.group(1).lower(), match.group(2).lower()))
    if not result:
        raise RuntimeError("symbol contains no recognized instructions")
    return result


def memory_accesses(body: str) -> list[str]:
    result: list[str] = []
    for mnemonic, operands in instructions(body):
        padding = mnemonic.startswith("nop") or (
            mnemonic in {"data16", "cs"} and "nop" in operands
        )
        if (
            "(" in operands
            and not mnemonic.startswith("lea")
            and not padding
        ):
            result.append(f"{mnemonic} {operands}".strip())
    return result


def inspect_accepted(body: str, name: str) -> dict[str, object]:
    operations = instructions(body)
    forbidden = [
        mnemonic
        for mnemonic, _ in operations
        if mnemonic.startswith("call")
        or mnemonic.startswith("prefetch")
        or mnemonic in {"syscall", "sysenter", "int", "mfence", "lfence", "sfence"}
    ]
    if forbidden:
        raise RuntimeError(f"{name} contains forbidden operations: {forbidden}")
    accesses = memory_accesses(body)
    if len(accesses) != 1:
        raise RuntimeError(
            f"{name} must expose exactly one static demand-load instruction; "
            f"observed {accesses}"
        )
    return {
        "status": "PASS",
        "static_demand_load_instruction_count": 1,
        "forbidden_operation_count": 0,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }


def inspect_mutants(disassembly: str) -> dict[str, object]:
    regular = symbol_body(disassembly, REGULAR_MUTANT)
    pointer = symbol_body(disassembly, POINTER_MUTANT)
    regular_accesses = memory_accesses(regular)
    pointer_prefetches = [
        mnemonic
        for mnemonic, _ in instructions(pointer)
        if mnemonic.startswith("prefetch")
    ]
    if len(regular_accesses) != 2:
        raise RuntimeError(
            "regular negative mutant must expose exactly two demand-load instructions"
        )
    if len(pointer_prefetches) != 1:
        raise RuntimeError(
            "pointer negative mutant must expose exactly one forbidden prefetch"
        )
    return {
        "status": "EXPECTED_REJECTION",
        "regular_static_demand_load_instruction_count": len(regular_accesses),
        "pointer_prefetch_instruction_count": len(pointer_prefetches),
        "regular_body_sha256": hashlib.sha256(regular.encode("utf-8")).hexdigest(),
        "pointer_body_sha256": hashlib.sha256(pointer.encode("utf-8")).hexdigest(),
    }


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
    raise RuntimeError(f"unrecognized disassembler version output from {tool}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=pathlib.Path, required=True)
    parser.add_argument("--mutant", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--gnu-objdump", default="objdump")
    parser.add_argument("--llvm-objdump", default="llvm-objdump")
    args = parser.parse_args()

    selected_tools = {
        "GNU_OBJDUMP": shutil.which(args.gnu_objdump),
        "LLVM_OBJDUMP": shutil.which(args.llvm_objdump),
    }
    report: dict[str, object] = {
        "schema_version": "cpu-prefetch-q15-probe-codegen/1",
        "profile_id": "Q15-PROBE-IMPLEMENTATION-PROFILE-v1",
        "scope": "correctness-only; no PMU, timing, or performance observation",
        "binary": {"path": str(args.binary), "sha256": file_sha256(args.binary)},
        "mutant": {"path": str(args.mutant), "sha256": file_sha256(args.mutant)},
        "rule_set": {
            "path": str(pathlib.Path(__file__).resolve()),
            "sha256": file_sha256(pathlib.Path(__file__).resolve()),
        },
        "tools": {},
    }
    missing = [name for name, path in selected_tools.items() if path is None]
    try:
        for name, tool in selected_tools.items():
            if tool is None:
                report["tools"][name] = {"status": "UNAVAILABLE"}
                continue
            accepted = disassemble(tool, args.binary)
            mutant = disassemble(tool, args.mutant)
            report["tools"][name] = {
                "status": "PASS",
                "path": tool,
                "version": tool_version(tool),
                "regular": inspect_accepted(
                    symbol_body(accepted, REGULAR), "regular traversal"
                ),
                "pointer": inspect_accepted(
                    symbol_body(accepted, POINTER), "pointer traversal"
                ),
                "mutants": inspect_mutants(mutant),
            }
        report["status"] = "BLOCKED_MISSING_TOOL" if missing else "PASS"
        report["missing_tools"] = missing
    except RuntimeError as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"q15-probe-codegen-check: FAIL: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if missing:
        print(
            "q15-probe-codegen-check: BLOCKED: missing " + ", ".join(missing),
            file=sys.stderr,
        )
        return 3
    print(
        "q15-probe-codegen-check: PASS "
        "(two disassemblers, exact loads, forbidden-operation mutant)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
