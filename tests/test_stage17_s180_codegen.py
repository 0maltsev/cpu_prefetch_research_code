"""Retained bindings/membership checks against an actual dual-disassembler report."""
import argparse
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_s180_codegen as audit


class CodegenTests(unittest.TestCase):
    report = None
    arguments = None

    def check(self, document):
        audit.validate_report_bindings(document, **self.arguments)

    def reject(self, edit):
        document = copy.deepcopy(self.report)
        edit(document)
        with self.assertRaises(audit.AuditError):
            self.check(document)

    def test_actual_report_contains_both_complete_families_and_actual_mutants(self):
        self.check(self.report)
        for kind in ("GNU_OBJDUMP", "LLVM_OBJDUMP"):
            self.assertEqual(len(self.report["tools"][kind]["operations"]), 20)
            self.assertEqual(len(self.report["legacy_formal_report"]["tools"][kind]["operations"]), 42)
            self.assertEqual(set(self.report["tools"][kind]["negative_checks"]), audit.formal.NEGATIVE_CASES)

    def test_actual_pilot_symbols_reproduce_old_classifier_collision_and_partition_exactly(self):
        operations = self.report["tools"]["GNU_OBJDUMP"]["operations"]
        old = self.report["legacy_formal_report"]["tools"]["GNU_OBJDUMP"]["operations"]
        for key, op in operations.items():
            self.assertEqual(audit.identity(op["root"]).key(), key)
            legacy = audit.formal.identity(op["root"])
            self.assertEqual(legacy.purpose, "service")
            self.assertIn(legacy.key(), old)
        for op in old.values():
            self.assertIsNone(audit.identity(op["root"]))

    def test_binary_rule_and_source_drift_reject(self):
        self.reject(lambda r: r.update(binary_sha256="f"*64))
        for field in ("rule_bindings", "source_evidence"):
            self.reject(lambda r, f=field: r[f].update({next(iter(r[f])): "f"*64}))

    def test_missing_worker_wrong_intent_duplicate_witness_and_disconnected_entry_reject(self):
        for kind in ("GNU_OBJDUMP", "LLVM_OBJDUMP"):
            def remove(r):
                ops = r["tools"][kind]["operations"]
                del ops[next(iter(ops))]
            self.reject(remove)
            for field, value in (("prefetch_vector", {"prefetchw": 999}),
                ("prefetch_witnesses", [[1, "prefetchw"], [1, "prefetchw"]]),
                ("native_reference_path", ["unrelated_entry", "unrelated_root"]),
                ("raw_clock_call_sites", {})):
                self.reject(lambda r, f=field, v=value: next(iter(
                    r["tools"][kind]["operations"].values())).update({f: v}))

    def test_legacy_proof_and_negative_mutants_cannot_be_omitted(self):
        self.reject(lambda r: r["legacy_formal_report"]["tools"]["GNU_OBJDUMP"]["operations"].clear())
        self.reject(lambda r: r["legacy_formal_report"]["tools"]["LLVM_OBJDUMP"]["negative_checks"].clear())
        self.reject(lambda r: r["tools"]["GNU_OBJDUMP"]["negative_checks"].clear())
        self.reject(lambda r: r["tools"]["GNU_OBJDUMP"].update(disassembly_sha256="f"*64))

    def test_missing_disassembler_wrong_llvm_and_authority_widening_reject(self):
        self.reject(lambda r: r["tools"].pop("LLVM_OBJDUMP"))
        self.reject(lambda r: r["tools"]["LLVM_OBJDUMP"].update(version="21.1.0"))
        self.reject(lambda r: r.update(execution_authority=True))
        self.reject(lambda r: r.update(phase18_authority=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--rule-root", type=Path)
    args, rest = parser.parse_known_args()
    CodegenTests.report = json.loads(args.report.read_bytes())
    CodegenTests.arguments = dict(binary=args.binary, source_root=args.source_root,
        rule_root=args.rule_root or args.source_root)
    unittest.main(argv=[__file__, *rest])
