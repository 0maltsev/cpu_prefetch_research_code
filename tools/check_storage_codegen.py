#!/usr/bin/env python3
"""Audit Stage 11 raw append bodies without observing performance."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys


SYMBOL_MARKERS = (
    "ProducerObservationStream::append(",
    "ConsumerObservationStream::append(",
)
MUTANT_SYMBOL = "cpu_prefetch_storage_append_mutant"
SYMBOL_LINE = re.compile(r"^[0-9a-fA-F]+ <([^>]+)>:$")
FORBIDDEN = re.compile(r"\b(?:lock|mfence|syscall)\b|\bxchg\w*\s+[^\n]*\(", re.I)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_evidence(root: pathlib.Path) -> dict[str, object]:
    paths = (
        root / "include/cpu_prefetch/storage/raw_observations.hpp",
        root / "src/storage/raw_observations.cpp",
        root / "tools/storage_codegen_probe.cpp",
        root / "tools/storage_codegen_mutant.cpp",
    )
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing storage code-generation sources: {missing}")
    return {
        "status": "PASS",
        "files": {str(path.relative_to(root)): sha256(path) for path in paths},
    }


def tool_version(tool: str) -> str:
    result = subprocess.run([tool, "--version"], check=False, capture_output=True,
                            text=True)
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
        check=False, capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError(f"{tool} failed: {result.stderr.strip()}")
    return result.stdout.replace(str(binary), "<BINARY>")


def symbol_body(disassembly: str, marker: str) -> tuple[str, str]:
    collecting = False
    selected = ""
    body: list[str] = []
    for line in disassembly.splitlines():
        match = SYMBOL_LINE.match(line.strip())
        if match:
            if collecting:
                break
            selected = match.group(1)
            collecting = marker in selected
            continue
        if collecting:
            body.append(line)
    if not body:
        raise RuntimeError(f"missing disassembly symbol matching {marker}")
    return selected, "\n".join(body)


def inspect(disassembly: str) -> dict[str, object]:
    report: dict[str, object] = {}
    for marker in SYMBOL_MARKERS:
        symbol, body = symbol_body(disassembly, marker)
        detected = sorted(set(match.group(0) for match in FORBIDDEN.finditer(body)))
        forbidden_calls = [
            line.strip() for line in body.splitlines()
            if re.search(r"\bcallq?\b", line, re.I) and "__stack_chk_fail" not in line
        ]
        detected.extend(forbidden_calls)
        if detected:
            raise RuntimeError(f"{symbol} contains forbidden operations: {detected}")
        if re.search(r"\bmov", body, re.I) is None:
            raise RuntimeError(f"{symbol} has no physical row/control stores")
        report[symbol] = {
            "status": "PASS",
            "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "forbidden_operations": [],
            "allowed_fail_closed_calls": ["__stack_chk_fail"]
            if "__stack_chk_fail" in body else [],
        }
    return report


def inspect_mutant(disassembly: str) -> dict[str, object]:
    _, body = symbol_body(disassembly, MUTANT_SYMBOL)
    detected = sorted(set(match.group(0) for match in FORBIDDEN.finditer(body)))
    detected.extend(line.strip() for line in body.splitlines()
                    if re.search(r"\bcallq?\b", line, re.I))
    if not detected:
        raise RuntimeError("negative storage call-injection mutant was not rejected")
    return {"status": "EXPECTED_REJECTION", "detected": detected}


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
    tools = {"GNU_OBJDUMP": shutil.which(args.gnu_objdump),
             "LLVM_OBJDUMP": shutil.which(args.llvm_objdump)}
    report: dict[str, object] = {
        "schema_version": "cpu-prefetch-storage-codegen/1",
        "scope": "correctness-only; no performance observation",
        "binary": {"path": str(args.binary), "sha256": sha256(args.binary)},
        "mutant": {"path": str(args.mutant), "sha256": sha256(args.mutant)},
        "rule_set_sha256": sha256(pathlib.Path(__file__).resolve()),
        "tools": {},
    }
    missing = [name for name, path in tools.items() if path is None]
    try:
        report["source_evidence"] = source_evidence(args.source_root)
        for name, tool in tools.items():
            if tool is None:
                report["tools"][name] = {"status": "UNAVAILABLE"}
                continue
            normal = disassemble(tool, args.binary)
            mutant = disassemble(tool, args.mutant)
            report["tools"][name] = {
                "status": "PASS",
                "path": tool,
                "version": tool_version(tool),
                "append_bodies": inspect(normal),
                "negative_mutant": inspect_mutant(mutant),
                "full_disassembly_sha256": hashlib.sha256(normal.encode()).hexdigest(),
            }
        report["status"] = "PASS" if not missing else "BLOCKED_MISSING_TOOL"
        report["missing_tools"] = missing
    except RuntimeError as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(f"storage-codegen-check: FAIL: {error}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    if missing and not args.allow_missing_secondary:
        print("storage-codegen-check: BLOCKED: missing " + ", ".join(missing),
              file=sys.stderr)
        return 3
    print("storage-codegen-check: PASS " +
          ("(partial tool evidence)" if missing else "(two disassemblers, two append bodies, one mutant)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
