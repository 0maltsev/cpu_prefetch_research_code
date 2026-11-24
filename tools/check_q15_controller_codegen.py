#!/usr/bin/env python3
"""Dual-disassembler and source-contract audit of the fixed Q15-R graph."""

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


CONTROLLER_SYMBOL_PREFIX: Final = (
    "cpu_prefetch::qualification::execute_q15_r_controller("
)
MUTANT_SYMBOL: Final = "cpu_prefetch_q15_controller_retry_mutant"
SYMBOL_LINE: Final = re.compile(r"^[0-9a-fA-F]+ <([^>]+)>:$")
INSTRUCTION_LINE: Final = re.compile(
    r"^\s*[0-9a-fA-F]+:\s+([a-zA-Z0-9_.]+)\s*(.*?)\s*$"
)
EXPECTED_STEPS: Final = (
    "verify_authorization_and_release_bindings",
    "verify_role_and_negative_access_evidence",
    "create_private_same_buffer_session",
    "collect_fixed_msr_prestate_as_auditor",
    "collect_clock",
    "collect_atomic_layout",
    "collect_actual_cpu_migration",
    "collect_address_residency",
    "collect_software_prefetch_capability",
    "collect_storage_custody",
    "negative_access_check",
    "run_h0_regular_stream_probe",
    "run_h0_pointer_stream_probe",
    "seal_q15_r_evidence",
    "wait_for_separate_q15_w_or_expire_fail_closed",
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


def symbol_body(disassembly: str, prefix: str, *, exact: bool) -> str:
    collecting = False
    body: list[str] = []
    for line in disassembly.splitlines():
        match = SYMBOL_LINE.match(line.strip())
        if match:
            if collecting:
                break
            name = match.group(1)
            collecting = name == prefix if exact else (
                name.startswith(prefix)
                and "[clone" not in name
                and ".cold" not in name
            )
            continue
        if collecting:
            body.append(line)
    if not body:
        raise RuntimeError(f"missing or empty disassembly symbol: {prefix}")
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


def is_indirect_call(mnemonic: str, operands: str) -> bool:
    return mnemonic.startswith("call") and (
        operands.startswith("*")
        or re.match(r"^(?:qword ptr\s+)?\[", operands) is not None
    )


def inspect_controller(body: str, name: str) -> dict[str, object]:
    operations = instructions(body)
    syscalls = [
        mnemonic
        for mnemonic, _ in operations
        if mnemonic in {"syscall", "sysenter", "int"}
    ]
    indirect_calls = [
        operands
        for mnemonic, operands in operations
        if is_indirect_call(mnemonic, operands)
    ]
    if syscalls:
        raise RuntimeError(f"{name} contains direct system calls: {syscalls}")
    if len(indirect_calls) != 1:
        raise RuntimeError(
            f"{name} must contain exactly one virtual run_step call site; "
            f"observed={indirect_calls}"
        )
    return {
        "status": "PASS",
        "indirect_run_step_call_sites": 1,
        "direct_system_calls": 0,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }


def inspect_expected_rejection(body: str) -> dict[str, object]:
    try:
        inspect_controller(body, MUTANT_SYMBOL)
    except RuntimeError as error:
        if "virtual run_step call site" not in str(error):
            raise
        return {
            "status": "EXPECTED_REJECTION",
            "reason": str(error),
            "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        }
    raise RuntimeError("retry mutant unexpectedly passed")


def source_contract(source_root: pathlib.Path) -> dict[str, object]:
    header = source_root / "include/cpu_prefetch/qualification/q15_controller.hpp"
    source = source_root / "src/qualification/q15_controller.cpp"
    header_text = header.read_text(encoding="utf-8")
    source_text = source.read_text(encoding="utf-8")
    graph_match = re.search(
        r"kQ15RControllerGraph\{(?P<body>.*?)\n\};", header_text, re.DOTALL
    )
    if graph_match is None:
        raise RuntimeError("fixed graph definition is absent")
    observed_steps = tuple(
        re.findall(r"Q15RControllerStep::([a-z0-9_]+)", graph_match.group("body"))
    )
    if observed_steps != EXPECTED_STEPS:
        raise RuntimeError(f"fixed graph source drift: {observed_steps}")
    required_source_tokens = (
        "for (const auto step : kQ15RControllerGraph)",
        "auto result = operations.run_step(step, ticket);",
        "Q15RControllerState::failed_partial_retained",
        "Q15RControllerState::q15_r_sealed_waiting_for_q15_w",
        "Q15R-RESOURCE-LIMIT",
        "Q15R-OUTPUT-LIMIT",
    )
    if any(token not in source_text for token in required_source_tokens):
        raise RuntimeError("controller source contract token is absent")
    if source_text.count("operations.run_step(") != 1:
        raise RuntimeError("controller source contains a retry or extra operation site")
    return {
        "status": "PASS",
        "graph_steps": len(observed_steps),
        "run_step_source_sites": 1,
        "header": {"path": str(header), "sha256": file_sha256(header)},
        "source": {"path": str(source), "sha256": file_sha256(source)},
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
    parser.add_argument("--source-root", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--gnu-objdump", default="objdump")
    parser.add_argument("--llvm-objdump", default="llvm-objdump")
    args = parser.parse_args()

    tools = {
        "GNU_OBJDUMP": shutil.which(args.gnu_objdump),
        "LLVM_OBJDUMP": shutil.which(args.llvm_objdump),
    }
    report: dict[str, object] = {
        "schema_version": "cpu-prefetch-q15-controller-codegen/1",
        "profile_id": "Q15-R-STATIC-CONTROLLER-v1",
        "scope": (
            "fixed graph and no-retry controller structure only; fake backend, "
            "no stand access, qualification execution, or performance claim"
        ),
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
        report["source_contract"] = source_contract(args.source_root.resolve())
        for name, tool in tools.items():
            if tool is None:
                report["tools"][name] = {"status": "UNAVAILABLE"}
                continue
            accepted = disassemble(tool, args.binary)
            mutant = disassemble(tool, args.mutant)
            report["tools"][name] = {
                "status": "PASS",
                "path": tool,
                "version": tool_version(tool),
                "controller": inspect_controller(
                    symbol_body(accepted, CONTROLLER_SYMBOL_PREFIX, exact=False),
                    CONTROLLER_SYMBOL_PREFIX,
                ),
                "retry_mutant": inspect_expected_rejection(
                    symbol_body(mutant, MUTANT_SYMBOL, exact=True)
                ),
            }
        report["status"] = "BLOCKED_MISSING_TOOL" if missing else "PASS"
        report["missing_tools"] = missing
    except RuntimeError as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"q15-controller-codegen-check: FAIL: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if missing:
        print(
            "q15-controller-codegen-check: BLOCKED: missing " + ", ".join(missing),
            file=sys.stderr,
        )
        return 3
    print(
        "q15-controller-codegen-check: PASS "
        "(15 fixed steps, one run_step site, retry mutant rejected, two disassemblers)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
