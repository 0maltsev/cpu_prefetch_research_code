#!/usr/bin/env python3
"""Audit Stage 6 hot-operation assembly without measuring performance."""

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
    "cpu_prefetch_consumer_record_action",
    "cpu_prefetch_r1_try_enqueue",
    "cpu_prefetch_r1_try_dequeue",
    "cpu_prefetch_r2_try_enqueue",
    "cpu_prefetch_r2_try_dequeue",
    "cpu_prefetch_l1_try_dequeue",
)
MUTANT_SYMBOL: Final = "cpu_prefetch_consumer_record_action_mutant"
FORBIDDEN_INSTRUCTION: Final = re.compile(
    r"\b(?:callq?|lock|mfence)\b|\bxchg\w*\s+[^\n]*\(", re.IGNORECASE
)
SYMBOL_LINE: Final = re.compile(r"^[0-9a-fA-F]+ <([^>]+)>:$")


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
    raise RuntimeError(f"unrecognized disassembler version output from {tool}")


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


def inspect_operations(disassembly: str) -> dict[str, object]:
    report: dict[str, object] = {}
    for symbol in OPERATION_SYMBOLS:
        body = symbol_body(disassembly, symbol)
        forbidden = sorted(set(FORBIDDEN_INSTRUCTION.findall(body)))
        if forbidden:
            raise RuntimeError(f"{symbol} contains forbidden instructions: {forbidden}")
        if re.search(r"\bmov", body, re.IGNORECASE) is None:
            raise RuntimeError(f"{symbol} has no demanded memory movement")
        if symbol == "cpu_prefetch_consumer_record_action":
            for instruction in (r"\bimul", r"\bshr", r"\bxor"):
                if re.search(instruction, body, re.IGNORECASE) is None:
                    raise RuntimeError(
                        f"consumer action lacks required operation matching {instruction}"
                    )
            if len(re.findall(r"\bimul", body, re.IGNORECASE)) < 2:
                raise RuntimeError("consumer action lacks both fixed multiplications")
        report[symbol] = {
            "status": "PASS",
            "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "forbidden_instruction_classes": [],
        }
    return report


def inspect_mutant(disassembly: str) -> dict[str, object]:
    body = symbol_body(disassembly, MUTANT_SYMBOL)
    detected = sorted(set(FORBIDDEN_INSTRUCTION.findall(body)))
    if not detected:
        raise RuntimeError("negative workload mutant was not rejected")
    return {
        "status": "EXPECTED_REJECTION",
        "detected_instruction_classes": detected,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=pathlib.Path, required=True)
    parser.add_argument("--mutant", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--gnu-objdump", default="objdump")
    parser.add_argument("--llvm-objdump", default="llvm-objdump")
    args = parser.parse_args()
    for path in (args.binary, args.mutant):
        if not path.is_file():
            print(f"workload-codegen-check: FAIL: missing {path}", file=sys.stderr)
            return 2

    tools = {
        "GNU_OBJDUMP": shutil.which(args.gnu_objdump),
        "LLVM_OBJDUMP": shutil.which(args.llvm_objdump),
    }
    report: dict[str, object] = {
        "schema_version": "cpu-prefetch-workload-codegen/1",
        "scope": "correctness-only; no timing or performance observation",
        "binary": {"path": str(args.binary), "sha256": file_sha256(args.binary)},
        "negative_mutant": {
            "path": str(args.mutant),
            "sha256": file_sha256(args.mutant),
        },
        "rule_set": {
            "path": str(pathlib.Path(__file__).resolve()),
            "sha256": file_sha256(pathlib.Path(__file__).resolve()),
        },
        "tools": {},
    }
    missing = [name for name, path in tools.items() if path is None]
    try:
        for name, tool in tools.items():
            if tool is None:
                report["tools"][name] = {"status": "UNAVAILABLE"}
                continue
            operation_text = disassemble(tool, args.binary)
            mutant_text = disassemble(tool, args.mutant)
            report["tools"][name] = {
                "status": "PASS",
                "path": tool,
                "version": tool_version(tool),
                "operations": inspect_operations(operation_text),
                "negative_mutant": inspect_mutant(mutant_text),
                "full_disassembly_sha256": hashlib.sha256(
                    operation_text.encode("utf-8")
                ).hexdigest(),
            }
        report["status"] = "BLOCKED_MISSING_TOOL" if missing else "PASS"
        report["missing_tools"] = missing
    except RuntimeError as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"workload-codegen-check: FAIL: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if missing:
        print(
            "workload-codegen-check: BLOCKED: missing " + ", ".join(missing),
            file=sys.stderr,
        )
        return 3
    print(
        "workload-codegen-check: PASS "
        "(two disassemblers, six operations, one mutant)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
