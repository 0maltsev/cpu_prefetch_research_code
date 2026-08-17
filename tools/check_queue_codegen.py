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
QUEUE_OPERATION_SYMBOLS: Final = {
    "TORQUATI_SPSC_RING_FIG3_V1": (
        "cpu_prefetch_ring_try_enqueue",
        "cpu_prefetch_ring_try_dequeue",
    ),
    "TORQUATI_DSPSC_FIFO_RECYCLER_FIG6_FIXED_ARENA_V1": (
        "cpu_prefetch_linked_try_enqueue",
        "cpu_prefetch_linked_try_dequeue",
    ),
}
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
    return completed.stdout.replace(str(binary), "<BINARY>")


def tool_version(tool: str) -> str:
    completed = subprocess.run(
        [tool, "--version"], check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{tool} --version failed: {completed.stderr.strip()}")
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    for line in lines:
        gnu_match = re.fullmatch(r"GNU objdump \(GNU Binutils\) (.+)", line)
        if gnu_match:
            return f"GNU Binutils {gnu_match.group(1)}"
        llvm_match = re.fullmatch(r"LLVM version (.+)", line)
        if llvm_match:
            return f"LLVM {llvm_match.group(1)}"
    raise RuntimeError(f"unrecognized disassembler version output from {tool}")


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


def require_object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RuntimeError(f"internal generated-code report field is not an object: {name}")
    return value


def validate_provenance(
    paths: list[pathlib.Path], report: dict[str, object]
) -> None:
    if len(paths) != 2 or len(set(paths)) != 2:
        raise RuntimeError("exactly two distinct queue provenance records are required")
    binary = require_object(report["binary"], "binary")
    mutant = require_object(report["negative_mutant"], "negative_mutant")
    tools = require_object(report["tools"], "tools")
    rule_set = require_object(report["rule_set"], "rule_set")
    gnu = require_object(tools["GNU_OBJDUMP"], "tools.GNU_OBJDUMP")
    llvm = require_object(tools["LLVM_OBJDUMP"], "tools.LLVM_OBJDUMP")
    common_expected = {
        "release_probe_sha256": binary["sha256"],
        "negative_mutant_sha256": mutant["sha256"],
        "rule_set_sha256": rule_set["sha256"],
        "gnu_objdump_version": gnu["version"],
        "llvm_objdump_version": llvm["version"],
        "gnu_full_disassembly_sha256": gnu["full_disassembly_sha256"],
        "llvm_full_disassembly_sha256": llvm["full_disassembly_sha256"],
    }
    for path in paths:
        try:
            root = json.loads(path.read_text(encoding="utf-8"))
            generated = root["generated_code_review"]
            evidence = generated["evidence"]
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
        ) as error:
            raise RuntimeError(f"invalid queue provenance record {path}: {error}") from error
        if generated.get("status") != "PASS":
            raise RuntimeError(f"queue provenance is not passing: {path}")
        if generated.get("gnu_objdump") != "PASS_WITH_NEGATIVE_MUTANT":
            raise RuntimeError(f"queue provenance lacks GNU pass: {path}")
        if generated.get("llvm_objdump") != "PASS_WITH_NEGATIVE_MUTANT":
            raise RuntimeError(f"queue provenance lacks LLVM pass: {path}")
        if generated.get("human_review") != "GNU_AND_LLVM_OPERATION_BODIES_REVIEWED":
            raise RuntimeError(f"queue provenance lacks dual human review: {path}")
        try:
            enqueue_symbol, dequeue_symbol = QUEUE_OPERATION_SYMBOLS[root["queue_id"]]
            gnu_operations = gnu["operations"]
            llvm_operations = llvm["operations"]
            expected = common_expected | {
                "gnu_try_enqueue_body_sha256": gnu_operations[enqueue_symbol][
                    "body_sha256"
                ],
                "gnu_try_dequeue_body_sha256": gnu_operations[dequeue_symbol][
                    "body_sha256"
                ],
                "llvm_try_enqueue_body_sha256": llvm_operations[enqueue_symbol][
                    "body_sha256"
                ],
                "llvm_try_dequeue_body_sha256": llvm_operations[dequeue_symbol][
                    "body_sha256"
                ],
            }
        except (KeyError, TypeError) as error:
            raise RuntimeError(f"unsupported queue/codegen operation map in {path}") from error
        for field, value in expected.items():
            if evidence.get(field) != value:
                raise RuntimeError(
                    f"queue provenance evidence mismatch for {path}:{field}"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=pathlib.Path, required=True)
    parser.add_argument("--mutant", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--gnu-objdump", default="objdump")
    parser.add_argument("--llvm-objdump", default="llvm-objdump")
    parser.add_argument(
        "--provenance", type=pathlib.Path, action="append", required=True
    )
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
        "rule_set": {
            "path": str(pathlib.Path(__file__).resolve()),
            "sha256": sha256(pathlib.Path(__file__).resolve()),
        },
        "provenance_records": [str(path) for path in args.provenance],
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
        if not missing:
            validate_provenance(args.provenance, report)
    except RuntimeError as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"queue-codegen-check: FAIL: {error}", file=sys.stderr)
        return 1

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
