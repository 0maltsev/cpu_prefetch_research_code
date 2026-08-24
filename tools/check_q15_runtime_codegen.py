#!/usr/bin/env python3
"""Dual-disassembler audit of the D-055 counter-enabled call boundary."""

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


REGULAR: Final = "cpu_prefetch_q15_regular_counted_region"
POINTER: Final = "cpu_prefetch_q15_pointer_counted_region"
REGULAR_TRAVERSAL: Final = "cpu_prefetch_q15_regular_counted_traversal"
POINTER_TRAVERSAL: Final = "cpu_prefetch_q15_pointer_counted_traversal"
REGULAR_MUTANT: Final = "cpu_prefetch_q15_regular_counted_region_mutant"
POINTER_MUTANT: Final = "cpu_prefetch_q15_pointer_counted_region_mutant"
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


def inspect_region(body: str, name: str, traversal: str) -> dict[str, object]:
    operations = instructions(body)
    forbidden = [
        mnemonic
        for mnemonic, _ in operations
        if mnemonic.startswith("prefetch")
        or mnemonic in {"syscall", "sysenter", "int", "mfence", "lfence", "sfence"}
    ]
    if forbidden:
        raise RuntimeError(f"{name} contains forbidden operations: {forbidden}")
    calls = [
        (index, operands)
        for index, (mnemonic, operands) in enumerate(operations)
        if mnemonic.startswith("call")
    ]
    traversal_calls = [item for item in calls if traversal in item[1]]
    if len(calls) != 3 or len(traversal_calls) != 1:
        raise RuntimeError(
            f"{name} must contain exactly enable/traversal/disable calls; "
            f"observed calls={calls} traversal_calls={traversal_calls}"
        )
    traversal_position = traversal_calls[0][0]
    if not (calls[0][0] < traversal_position < calls[2][0]):
        raise RuntimeError(f"{name} traversal is outside enable/disable call order")
    if "*" not in calls[0][1] or "*" not in calls[2][1]:
        raise RuntimeError(f"{name} enable/disable must remain fakeable virtual calls")
    return {
        "status": "PASS",
        "call_count": len(calls),
        "traversal_call_count": len(traversal_calls),
        "forbidden_operation_count": 0,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }


def inspect_expected_rejection(body: str, name: str, traversal: str) -> dict[str, object]:
    try:
        inspect_region(body, name, traversal)
    except RuntimeError as error:
        return {
            "status": "EXPECTED_REJECTION",
            "reason": str(error),
            "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        }
    raise RuntimeError(f"negative mutant unexpectedly passed: {name}")


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
        "schema_version": "cpu-prefetch-q15-runtime-codegen/1",
        "profile_id": "Q15-DYNAMIC-IMPLEMENTATION-PROFILE-v1",
        "scope": "counter-boundary correctness only; no PMU execution or performance claim",
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
                "regular": inspect_region(
                    symbol_body(accepted, REGULAR), REGULAR, REGULAR_TRAVERSAL
                ),
                "pointer": inspect_region(
                    symbol_body(accepted, POINTER), POINTER, POINTER_TRAVERSAL
                ),
                "mutant_regular": inspect_expected_rejection(
                    symbol_body(mutant, REGULAR_MUTANT),
                    REGULAR_MUTANT,
                    REGULAR_TRAVERSAL,
                ),
                "mutant_pointer": inspect_expected_rejection(
                    symbol_body(mutant, POINTER_MUTANT),
                    POINTER_MUTANT,
                    POINTER_TRAVERSAL,
                ),
            }
        report["status"] = "BLOCKED_MISSING_TOOL" if missing else "PASS"
        report["missing_tools"] = missing
    except RuntimeError as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"q15-runtime-codegen-check: FAIL: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if missing:
        print(
            "q15-runtime-codegen-check: BLOCKED: missing " + ", ".join(missing),
            file=sys.stderr,
        )
        return 3
    print(
        "q15-runtime-codegen-check: PASS "
        "(two disassemblers, exact counter boundary, two rejected mutants)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
