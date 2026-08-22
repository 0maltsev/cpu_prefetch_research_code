#!/usr/bin/env python3
"""Audit the Q13 one-PAUSE relax mapping without measuring performance."""

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


RELAX_SYMBOL: Final = "cpu_prefetch_runner_relax_once"
MUTANT_SYMBOL: Final = "cpu_prefetch_runner_relax_mutant"
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


def pause_count(body: str) -> int:
    return len(re.findall(r"\bpause\b", body, re.IGNORECASE))


def inspect_probe(disassembly: str) -> dict[str, object]:
    body = symbol_body(disassembly, RELAX_SYMBOL)
    if pause_count(body) != 1:
        raise RuntimeError("accepted relax site does not contain exactly one PAUSE")
    forbidden = re.findall(
        r"\b(?:callq?|syscall|mfence|lfence|sfence)\b", body, re.IGNORECASE
    )
    if forbidden:
        raise RuntimeError(f"accepted relax site contains forbidden operations: {forbidden}")
    return {
        "status": "PASS",
        "pause_count": 1,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }


def inspect_mutant(disassembly: str) -> dict[str, object]:
    body = symbol_body(disassembly, MUTANT_SYMBOL)
    scheduler_calls = re.findall(
        r"\bcallq?\b[^\n]*\bsched_yield(?:@plt)?\b", body, re.IGNORECASE
    )
    count = pause_count(body)
    if count != 2 or len(scheduler_calls) != 1:
        raise RuntimeError(
            "negative relax mutant must expose exactly two PAUSE instructions "
            "and exactly one sched_yield call"
        )
    return {
        "status": "EXPECTED_REJECTION",
        "pause_count": count,
        "scheduler_call_count": len(scheduler_calls),
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

    tools = {
        "GNU_OBJDUMP": shutil.which(args.gnu_objdump),
        "LLVM_OBJDUMP": shutil.which(args.llvm_objdump),
    }
    report: dict[str, object] = {
        "schema_version": "cpu-prefetch-runner-relax-codegen/1",
        "scope": "correctness-only; no timing or performance observation",
        "mapping_id": "X86-PAUSE-ONE-PER-RELAX-SITE-v1",
        "binary": {"path": str(args.binary), "sha256": file_sha256(args.binary)},
        "mutant": {"path": str(args.mutant), "sha256": file_sha256(args.mutant)},
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
            probe = disassemble(tool, args.binary)
            mutant = disassemble(tool, args.mutant)
            report["tools"][name] = {
                "status": "PASS",
                "path": tool,
                "version": tool_version(tool),
                "relax": inspect_probe(probe),
                "mutant": inspect_mutant(mutant),
            }
        report["status"] = "BLOCKED_MISSING_TOOL" if missing else "PASS"
        report["missing_tools"] = missing
    except RuntimeError as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"runner-relax-codegen-check: FAIL: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if missing:
        print(
            "runner-relax-codegen-check: BLOCKED: missing " + ", ".join(missing),
            file=sys.stderr,
        )
        return 3
    print("runner-relax-codegen-check: PASS (two disassemblers, one PAUSE, mutant)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
