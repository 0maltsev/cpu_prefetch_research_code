#!/usr/bin/env python3
"""Qualify the checker against a real linked native worker and ELF mutants.

Usage: python tests/test_discovery_codegen.py --binary <release runner or native
link-anchor binary> --source-root .  No binary in this test is executed.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import check_discovery_codegen as checker


def file_offset(binary: bytes, address: int) -> int:
    if binary[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H",binary,18)[0] != 62:
        raise ValueError("test requires ELF64 little-endian x86-64")
    phoff = struct.unpack_from("<Q",binary,32)[0]
    size,count = struct.unpack_from("<HH",binary,54)
    for index in range(count):
        kind,_,offset,vaddr,_,filesz,_,_ = struct.unpack_from("<IIQQQQQQ",binary,phoff+index*size)
        if kind == 1 and vaddr <= address < vaddr+filesz:
            return offset+address-vaddr
    raise ValueError("instruction is not file-backed")


class DiscoveryCodegenTests(unittest.TestCase):
    binary: Path
    source_root: Path
    tools: dict[str,str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.original = cls.binary.read_bytes()
        cls.texts = {name:checker.disassemble(tool,cls.binary) for name,tool in cls.tools.items()}
        cls.proofs = {name:checker.inspect(text) for name,text in cls.texts.items()}
        cls.functions = checker.decode(cls.texts["GNU_OBJDUMP"])
        cls.producer = next(f for n,f in cls.functions.items() if "capture_discovery_producer_event<cpu_prefetch::timing::MonotonicRawClock, cpu_prefetch::calibration::CallerOwnedRingDemandTrace>" in n)
        cls.clock_call = next(i for i in cls.producer.instructions if checker.is_call(i) and i.target and checker.external_name(i.target) == "clock_gettime")

    def assert_mutant_rejected(self, address: int, replacement: bytes) -> None:
        mutated = bytearray(self.original)
        offset = file_offset(mutated,address)
        mutated[offset:offset+len(replacement)] = replacement
        with tempfile.TemporaryDirectory(prefix="discovery-elf-mutant-") as directory:
            binary = Path(directory)/"mutant"
            binary.write_bytes(mutated)
            for name,tool in self.tools.items():
                with self.subTest(disassembler=name):
                    with self.assertRaises(checker.AuditError):
                        checker.inspect(checker.disassemble(tool,binary))

    def redirect_call(self, fragment: str) -> None:
        target = next(f for n,f in self.functions.items() if fragment in n and "[clone" not in n)
        call = self.clock_call
        self.assertEqual(self.original[file_offset(self.original,call.address)],0xE8)
        displacement = target.instructions[0].address-call.address-5
        self.assert_mutant_rejected(call.address,b"\xe8"+struct.pack("<i",displacement))

    def test_actual_native_symbols_and_dual_brackets(self) -> None:
        for proof in self.proofs.values():
            self.assertEqual(len(proof["operations"]),4)
            for op in proof["operations"].values():
                self.assertIn("MappedDiscoveryRuntime",op["root"])
                self.assertIn("run_native_discovery_capture(",op["native_reference_path"][0])
                self.assertIn("run_discovery_session<",op["actual_session_caller"])
                self.assertEqual(set(op["external_calls"]),{"clock_gettime","memset","__stack_chk_fail"})
        for role in ("producer","consumer"):
            self.assertEqual(self.proofs["GNU_OBJDUMP"]["event_boundaries"][role]["witnesses"],
                             self.proofs["LLVM_OBJDUMP"]["event_boundaries"][role]["witnesses"])

    def test_binary_missing_clock_mutant(self) -> None:
        self.assert_mutant_rejected(self.clock_call.address,b"\x90"*5)

    def test_binary_prefetch_mutant(self) -> None:
        self.assert_mutant_rejected(self.clock_call.address,b"\x0f\x18\x08\x90\x90")

    def test_binary_locked_memory_mutant(self) -> None:
        self.assert_mutant_rejected(self.clock_call.address,b"\xf0\x83\x00\x00\x90")

    def test_binary_syscall_mutant(self) -> None:
        self.assert_mutant_rejected(self.clock_call.address,b"\x0f\x05\x90\x90\x90")

    def test_binary_indirect_call_mutant(self) -> None:
        self.assert_mutant_rejected(self.clock_call.address,b"\xff\xd0\x90\x90\x90")

    def test_binary_allocation_call_mutant(self) -> None:
        self.redirect_call("operator new(unsigned long)@plt")

    def test_binary_file_io_call_mutant(self) -> None:
        self.redirect_call("open@plt")

    def test_binary_parser_call_mutant(self) -> None:
        self.redirect_call("cpu_prefetch::protocol::json::parse(")

    def test_binary_missing_slot_load_mutant(self) -> None:
        witness=self.proofs["GNU_OBJDUMP"]["event_boundaries"]["producer"]["witnesses"]["slot_load"]
        address=int(next(iter(witness)),16)
        position=next(i for i,ins in enumerate(self.producer.instructions) if ins.address == address)
        length=self.producer.instructions[position+1].address-address
        self.assert_mutant_rejected(address,b"\x90"*length)

    def test_binary_missing_slot_publication_mutant(self) -> None:
        witness=self.proofs["GNU_OBJDUMP"]["event_boundaries"]["producer"]["witnesses"]["slot_store"]
        address=int(next(iter(witness)),16)
        position=next(i for i,ins in enumerate(self.producer.instructions) if ins.address == address)
        length=self.producer.instructions[position+1].address-address
        self.assert_mutant_rejected(address,b"\x90"*length)

    def test_probe_without_actual_native_path_is_not_authority(self) -> None:
        for text in self.texts.values():
            with self.assertRaises(checker.AuditError):
                checker.inspect(text.replace("run_native_discovery_capture(","unrelated_capture("))

    def test_unknown_external_logging_is_rejected(self) -> None:
        body=checker.Function("worker",(checker.Instruction(1,"call","2 <fprintf@plt>","fprintf@plt"),))
        with self.assertRaisesRegex(checker.AuditError,"unapproved external"):
            checker.closure({"worker":body},"worker")

    def test_llvm21_is_blocking(self) -> None:
        with mock.patch.object(subprocess,"run",return_value=subprocess.CompletedProcess([],0,"LLVM version 21.1.0\n","")):
            with self.assertRaisesRegex(checker.AuditError,"unaccepted"):
                checker.tool_version("llvm-objdump","LLVM_OBJDUMP")

    def test_report_contract_and_custody_mutants(self) -> None:
        with tempfile.TemporaryDirectory(prefix="discovery-report-") as directory:
            root=Path(directory)
            for relative in (*checker.SOURCE_EVIDENCE_PATHS,"tools/check_discovery_codegen.py"):
                target=root/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(self.source_root/relative,target)
            report={"schema_version":checker.SCHEMA,"binary_role":"ACTUAL_NATIVE_DISCOVERY_WORKER","status":"PASS","missing_tools":[],
                    "binary_sha256":checker.sha256(self.binary),"rule_set_sha256":checker.sha256(root/"tools/check_discovery_codegen.py"),
                    "source_evidence":{name:checker.sha256(root/name) for name in checker.SOURCE_EVIDENCE_PATHS},
                    "tools":{name:{**self.proofs[name],"version":checker.tool_version(tool,name),"full_disassembly_sha256":"a"*64} for name,tool in self.tools.items()}}
            checker.validate_report_bindings(report,binary=self.binary,source_root=root)
            for field,value in (("schema_version","wrong"),("binary_role","PROBE"),("status","FAIL"),("binary_sha256","0"*64),("rule_set_sha256","0"*64),("source_evidence",{}),("missing_tools",["LLVM_OBJDUMP"]),("tools",{})):
                changed=copy.deepcopy(report)
                changed[field]=value
                with self.subTest(field=field),self.assertRaises(checker.AuditError):
                    checker.validate_report_bindings(changed,binary=self.binary,source_root=root)
            changed=copy.deepcopy(report)
            changed["tools"]["LLVM_OBJDUMP"]["version"]="21.1.0"
            with self.assertRaises(checker.AuditError):
                checker.validate_report_bindings(changed,binary=self.binary,source_root=root)
            source=root/checker.SOURCE_EVIDENCE_PATHS[0]
            source.write_text(source.read_text()+"\n// drift\n")
            with self.assertRaises(checker.AuditError):
                checker.validate_report_bindings(report,binary=self.binary,source_root=root)

    def test_missing_secondary_cli_writes_blocking_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"report.json"
            result=checker.main(["--binary",str(self.binary),"--source-root",str(self.source_root),"--output",str(output),
                "--gnu-objdump",self.tools["GNU_OBJDUMP"],"--llvm-objdump",str(Path(directory)/"absent")])
            self.assertEqual(result,3)
            report=json.loads(output.read_text())
            self.assertEqual(report["status"],"BLOCKED_MISSING_TOOL")
            self.assertEqual(report["missing_tools"],["LLVM_OBJDUMP"])


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary",type=Path,required=True)
    parser.add_argument("--source-root",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--gnu-objdump",default="objdump")
    parser.add_argument("--llvm-objdump",default="llvm-objdump")
    args,remaining=parser.parse_known_args()
    DiscoveryCodegenTests.binary=args.binary
    DiscoveryCodegenTests.source_root=args.source_root
    DiscoveryCodegenTests.tools={"GNU_OBJDUMP":args.gnu_objdump,"LLVM_OBJDUMP":args.llvm_objdump}
    unittest.main(argv=[sys.argv[0],*remaining])


if __name__ == "__main__":
    main()
