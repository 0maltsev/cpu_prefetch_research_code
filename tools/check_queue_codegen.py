#!/usr/bin/env python3
"""Inspect queue-operation machine code without executing a benchmark."""

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
    "cpu_prefetch_ring_try_enqueue",
    "cpu_prefetch_ring_try_dequeue",
    "cpu_prefetch_linked_try_enqueue",
    "cpu_prefetch_linked_try_dequeue",
)
MUTANT_SYMBOL: Final = "cpu_prefetch_ring_try_enqueue_mutant"
FORBIDDEN_INSTRUCTION: Final = re.compile(
    r"\b(?:callq?|lock|xchg|mfence)\b", re.IGNORECASE
)
SYMBOL_LINE: Final = re.compile(r"^[0-9a-fA-F]+ <([^>]+)>:$")


def sha256(path: pathlib.Path) -> str:
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
        raise RuntimeError(
            f"{tool} failed for {binary}: {completed.stderr.strip()}"
        )
    return completed.stdout


def symbol_body(disassembly: str, symbol: str) -> str:
    lines = disassembly.splitlines()
    collecting = False
    body: list[str] = []
    for line in lines:
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


def inspect_operations(disassembly: str) -> dict[str, dict[str, object]]:
    report: dict[str, dict[str, object]] = {}
    for symbol in OPERATION_SYMBOLS:
        body = symbol_body(disassembly, symbol)
        forbidden = sorted(set(FORBIDDEN_INSTRUCTION.findall(body)))
        if forbidden:
            raise RuntimeError(
                f"{symbol} contains forbidden instruction classes: {forbidden}"
            )
        if re.search(r"\bmov", body, re.IGNORECASE) is None:
            raise RuntimeError(f"{symbol} has no recognized memory movement")
        report[symbol] = {
            "status": "PASS",
            "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "forbidden_instruction_classes": [],
        }
    return report


def inspect_mutant(disassembly: str) -> dict[str, object]:
    body = symbol_body(disassembly, MUTANT_SYMBOL)
    forbidden = sorted(set(FORBIDDEN_INSTRUCTION.findall(body)))
    if not forbidden:
        raise RuntimeError(
            "negative generated-code mutant was not rejected by the instruction rule"
        )
    return {
        "status": "EXPECTED_REJECTION",
        "detected_instruction_classes": forbidden,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=pathlib.Path, required=True)
    parser.add_argument("--mutant", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--gnu-objdump", default="objdump")
    parser.add_argument("--llvm-objdump", default="llvm-objdump")
    parser.add_argument("--allow-missing-secondary", action="store_true")
    args = parser.parse_args()

    for path in (args.binary, args.mutant):
        if not path.is_file():
            print(f"queue-codegen-check: FAIL: missing binary: {path}", file=sys.stderr)
            return 2

    tools = {
        "GNU_OBJDUMP": shutil.which(args.gnu_objdump),
        "LLVM_OBJDUMP": shutil.which(args.llvm_objdump),
    }
    report: dict[str, object] = {
        "schema_version": "cpu-prefetch-queue-codegen/1",
        "scope": "correctness-only; no timing or performance observation",
        "binary": {
            "path": str(args.binary),
            "sha256": sha256(args.binary),
        },
        "negative_mutant": {
            "path": str(args.mutant),
            "sha256": sha256(args.mutant),
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
                "operations": inspect_operations(operation_text),
                "negative_mutant": inspect_mutant(mutant_text),
                "full_disassembly_sha256": hashlib.sha256(
                    operation_text.encode("utf-8")
                ).hexdigest(),
            }
    except RuntimeError as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"queue-codegen-check: FAIL: {error}", file=sys.stderr)
        return 1

    report["status"] = "BLOCKED_MISSING_TOOL" if missing else "PASS"
    report["missing_tools"] = missing
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if missing:
        message = "queue-codegen-check: BLOCKED: missing " + ", ".join(missing)
        if args.allow_missing_secondary and missing == ["LLVM_OBJDUMP"]:
            print(message + " (partial report retained)")
            return 0
        print(message, file=sys.stderr)
        return 3
    print("queue-codegen-check: PASS (two disassemblers, four operations, one mutant)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
