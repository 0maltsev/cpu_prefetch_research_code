#!/usr/bin/env python3
"""Audit D-047's mapping or the separately selected ADR-0175 T0-only mapping.

Mirrors check_runner_codegen.py's dual-disassembler probe/mutant pattern
(one compiler's binary, checked with both objdump tools). The compiler
axis (gcc_codegen_passed vs. clang_codegen_passed) comes from invoking
this script once per compiler preset's build of the same source, exactly
as tools/check_ci.py already does for runner-relax-codegen-check.
"""

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


PRODUCER_SYMBOL: Final = "cpu_prefetch_software_prefetch_ring_producer_write"
CONSUMER_SYMBOL: Final = "cpu_prefetch_software_prefetch_ring_consumer_read"
SUCCESSOR_SYMBOL: Final = "cpu_prefetch_software_prefetch_successor_header"
PRODUCER_MUTANT_SYMBOL: Final = "cpu_prefetch_software_prefetch_ring_producer_write_mutant"
CONSUMER_MUTANT_SYMBOL: Final = "cpu_prefetch_software_prefetch_ring_consumer_read_mutant"
SYMBOL_LINE: Final = re.compile(r"^[0-9a-fA-F]+ <([^>]+)>:$")
PREFETCH_MNEMONICS: Final = (
    "prefetchw",
    "prefetcht0",
    "prefetcht1",
    "prefetcht2",
    "prefetchnta",
)
ORIGINAL_MAPPING: Final = "X86-64-PREFETCHW-PREFETCHT0-v1"
T0_MAPPING: Final = "X86-64-PREFETCHT0-ONLY-v1"
T0_SYMBOLS: Final = {
    "ring_producer_write": "cpu_prefetch_software_prefetch_t0_ring_producer_write",
    "ring_consumer_read": "cpu_prefetch_software_prefetch_t0_ring_consumer_read",
    "successor_header": "cpu_prefetch_software_prefetch_t0_successor_header",
}
T0_MUTANTS: Final = tuple("cpu_prefetch_software_prefetch_t0_" + suffix for suffix in (
    "producer_wrong", "consumer_wrong", "successor_wrong", "duplicate", "missing"))
T0_SOURCES: Final = (
    "include/cpu_prefetch/runner/software_prefetch.hpp",
    "tools/software_prefetch_mapping_codegen_probe.cpp",
    "tools/software_prefetch_mapping_codegen_mutant.cpp",
    "tools/check_software_prefetch_mapping_codegen.py",
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


def mnemonic_counts(body: str) -> dict[str, int]:
    return {
        mnemonic: len(re.findall(rf"\b{mnemonic}\b", body, re.IGNORECASE))
        for mnemonic in PREFETCH_MNEMONICS
    }


def require_exactly_one(body: str, symbol: str, expected: str) -> dict[str, object]:
    counts = mnemonic_counts(body)
    others = {m: c for m, c in counts.items() if m != expected and c != 0}
    if counts[expected] != 1 or others:
        raise RuntimeError(
            f"{symbol}: expected exactly one {expected} and no other prefetch "
            f"mnemonic, observed {counts}"
        )
    return {
        "status": "PASS",
        "instruction": expected.upper(),
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }


def inspect_probe(disassembly: str) -> dict[str, object]:
    return {
        "ring_producer_write": require_exactly_one(
            symbol_body(disassembly, PRODUCER_SYMBOL), PRODUCER_SYMBOL, "prefetchw"
        ),
        "ring_consumer_read": require_exactly_one(
            symbol_body(disassembly, CONSUMER_SYMBOL), CONSUMER_SYMBOL, "prefetcht0"
        ),
        "successor_header": require_exactly_one(
            symbol_body(disassembly, SUCCESSOR_SYMBOL), SUCCESSOR_SYMBOL, "prefetcht0"
        ),
    }


def inspect_mutant(disassembly: str) -> dict[str, object]:
    return {
        "ring_producer_write_mutant": require_exactly_one(
            symbol_body(disassembly, PRODUCER_MUTANT_SYMBOL),
            PRODUCER_MUTANT_SYMBOL,
            "prefetcht0",
        ),
        "ring_consumer_read_mutant": require_exactly_one(
            symbol_body(disassembly, CONSUMER_MUTANT_SYMBOL),
            CONSUMER_MUTANT_SYMBOL,
            "prefetchw",
        ),
    }


def inspect_t0_probe(disassembly: str) -> dict[str, object]:
    return {role: require_exactly_one(symbol_body(disassembly, symbol), symbol, "prefetcht0")
            for role, symbol in T0_SYMBOLS.items()}


def inspect_t0_mutants(disassembly: str) -> dict[str, object]:
    result = {}
    for symbol in T0_MUTANTS:
        body = symbol_body(disassembly, symbol)
        try:
            require_exactly_one(body, symbol, "prefetcht0")
        except RuntimeError:
            result[symbol] = {"status": "REJECTED", "counts": mnemonic_counts(body),
                              "body_sha256": hashlib.sha256(body.encode()).hexdigest()}
        else:
            raise RuntimeError("T0 mutant unexpectedly accepted: " + symbol)
    return result


def validate_t0_report(report: dict, *, binary: pathlib.Path, mutant: pathlib.Path,
                       source_root: pathlib.Path) -> None:
    """Replay retained software bindings; caller authenticates the report/builds.

    Does not establish compiler identity, report authenticity, full native
    call-graph coverage, stand capability or qualification permission.
    """
    if (report["schema_version"] != "cpu-prefetch-software-prefetch-mapping-codegen/1"
            or report["mapping_id"] != T0_MAPPING or report["status"] != "PASS"
            or report["missing_tools"] != [] or set(report["tools"]) != {"GNU_OBJDUMP", "LLVM_OBJDUMP"}):
        raise RuntimeError("complete T0 dual-disassembler report required")
    for name, path in (("binary", binary), ("mutant", mutant)):
        if report[name]["sha256"] != file_sha256(path):
            raise RuntimeError("actual T0 " + name + " bytes differ")
    if report["source_evidence"] != {p: file_sha256(source_root / p) for p in T0_SOURCES}:
        raise RuntimeError("actual T0 source/rule bytes differ")
    if report["rule_set"]["sha256"] != file_sha256(source_root / T0_SOURCES[-1]):
        raise RuntimeError("actual T0 audit rule differs")
    for kind, tool in report["tools"].items():
        if (tool["status"] != "PASS" or (kind == "LLVM_OBJDUMP" and not tool["version"].startswith("LLVM 22."))
                or (kind == "GNU_OBJDUMP" and not tool["version"].startswith("GNU Binutils "))
                or set(tool["mapping"]) != set(T0_SYMBOLS) or set(tool["mutant"]) != set(T0_MUTANTS)):
            raise RuntimeError("T0 tool/site/mutant family differs")
        for row in tool["mapping"].values():
            if row["status"] != "PASS" or row["instruction"] != "PREFETCHT0":
                raise RuntimeError("T0 physical mapping differs")
        for row in tool["mutant"].values():
            if (set(row["counts"]) != set(PREFETCH_MNEMONICS)
                    or any(type(v) is not int or v < 0 for v in row["counts"].values())):
                raise RuntimeError("T0 mutant count vector differs")
            if row["status"] != "REJECTED" or (row["counts"]["prefetcht0"] == 1
                    and all(v == 0 for k, v in row["counts"].items() if k != "prefetcht0")):
                raise RuntimeError("T0 rejected mutant differs")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=pathlib.Path, required=True)
    parser.add_argument("--mutant", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--gnu-objdump", default="objdump")
    parser.add_argument("--llvm-objdump", default="llvm-objdump")
    parser.add_argument("--mapping-id", choices=(ORIGINAL_MAPPING, T0_MAPPING), default=ORIGINAL_MAPPING)
    parser.add_argument("--source-root", type=pathlib.Path)
    args = parser.parse_args()
    if args.mapping_id == T0_MAPPING and args.source_root is None:
        parser.error("T0 mapping requires --source-root for actual emitter/probe/rule bindings")

    tools = {
        "GNU_OBJDUMP": shutil.which(args.gnu_objdump),
        "LLVM_OBJDUMP": shutil.which(args.llvm_objdump),
    }
    report: dict[str, object] = {
        "schema_version": "cpu-prefetch-software-prefetch-mapping-codegen/1",
        "scope": "correctness-only; no timing or performance observation",
        "mapping_id": args.mapping_id,
        "binary": {"path": str(args.binary), "sha256": file_sha256(args.binary)},
        "mutant": {"path": str(args.mutant), "sha256": file_sha256(args.mutant)},
        "rule_set": {
            "path": str(pathlib.Path(__file__).resolve()),
            "sha256": file_sha256(pathlib.Path(__file__).resolve()),
        },
        "tools": {},
    }
    if args.mapping_id == T0_MAPPING:
        report["source_evidence"] = {p: file_sha256(args.source_root / p) for p in T0_SOURCES}
    missing = [name for name, path in tools.items() if path is None]
    try:
        for name, tool in tools.items():
            if tool is None:
                report["tools"][name] = {"status": "UNAVAILABLE"}
                continue
            probe = disassemble(tool, args.binary)
            mutant = disassemble(tool, args.mutant)
            version = tool_version(tool)
            if args.mapping_id == T0_MAPPING and name == "LLVM_OBJDUMP" and not version.startswith("LLVM 22."):
                raise RuntimeError("T0 audit requires accepted LLVM 22")
            report["tools"][name] = {
                "status": "PASS",
                "path": tool,
                "version": version,
                "mapping": inspect_t0_probe(probe) if args.mapping_id == T0_MAPPING else inspect_probe(probe),
                "mutant": inspect_t0_mutants(mutant) if args.mapping_id == T0_MAPPING else inspect_mutant(mutant),
            }
        report["status"] = "BLOCKED_MISSING_TOOL" if missing else "PASS"
        report["missing_tools"] = missing
        if args.mapping_id == T0_MAPPING and not missing:
            validate_t0_report(report, binary=args.binary, mutant=args.mutant, source_root=args.source_root)
    except RuntimeError as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"software-prefetch-mapping-codegen-check: FAIL: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if missing:
        print(
            "software-prefetch-mapping-codegen-check: BLOCKED: missing "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 3
    print(
        "software-prefetch-mapping-codegen-check: PASS "
        f"(two disassemblers, three mapped sites, {5 if args.mapping_id == T0_MAPPING else 2} mutants)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
