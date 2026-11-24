#!/usr/bin/env python3
"""Software-only checks for the formal machine-code audit boundary."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_formal_codegen as gate

I = gate.machine.Instruction
F = gate.machine.Function


class FormalCodegenTest(unittest.TestCase):
    def test_split_lock_prefix_normalizes_exact_instruction_start(self):
        gnu = gate.decode("100 <worker>:\n 100: lock cmpxchgb %cl,(%rax)\n 103: ret\n")
        llvm = gate.decode("100 <worker>:\n 100: lock\n 101: cmpxchgb %cl,(%rax)\n 103: ret\n")
        self.assertEqual(gnu, llvm)

    def test_truncated_or_noncontiguous_lock_prefix_rejected(self):
        for value in ("100 <worker>:\n 100: lock\n", "100 <worker>:\n 100: lock\n 102: orl $1,(%rax)\n"):
            with self.assertRaises(gate.AuditError):
                gate.decode(value)

    def test_exact_package_vectors_distinguish_emitter_and_role(self):
        self.assertEqual(len(gate.expected_workers()), 42)
        for purpose in ("service", "scheduled"):
            for package in range(5):
                for mapping in ("retaining", "t0only"):
                    expected = ({"prefetchw" if mapping == "retaining" else "prefetcht0": 1}
                                if package in (1, 2) else {})
                    self.assertEqual(gate.Worker(purpose, package, mapping, "producer").vector(), expected)
                    self.assertEqual(gate.Worker(purpose, package, mapping, "consumer").vector(),
                                     {"prefetcht0": 1} if package in (1, 2, 4) else {})

    def test_missing_native_workers_rejected(self):
        with self.assertRaises(gate.AuditError):
            gate.inspect_functions({"unrelated": F("unrelated", (I(1, "ret", "", None),))})

    @staticmethod
    def worker(early_tls=False):
        items = [I(0x100, "call", "400 <arrive>", gate.ARRIVE + ")"),
                 I(0x105, "call", "500 <window>", gate.WINDOW + ")"),
                 I(0x110, "mov", "$4,%edi", None),
                 I(0x115, "call", "600 <clock_gettime@plt>", "clock_gettime@plt"),
                 I(0x120, "call", "700 <append>", "ProducerObservationStream::append()"),
                 I(0x125, "call", "800 <tls>", gate.TLS + ")"),
                 I(0x130, "jmp", "100 <worker>", "worker")]
        if early_tls:
            items[2] = I(0x110, "call", "800 <tls>", gate.TLS + ")")
            items.insert(2, I(0x108, "call", "700 <append>", "ProducerObservationStream::append()"))
        return F("worker", tuple(items))

    def test_parked_reset_boundary_requires_fresh_barrier_before_next_event(self):
        function = self.worker()
        region, cuts = gate.active_region(function, {function.name: function, gate.TLS + ")": F(gate.TLS + ")", (I(0x800, "ret", "", None),))})
        self.assertEqual(region, {2, 3, 4})
        self.assertEqual(cuts, {5})

    def test_cold_label_cannot_hide_io_before_same_phase_capture(self):
        function = self.worker(early_tls=True)
        with self.assertRaisesRegex(gate.AuditError, "hides another capture"):
            gate.active_region(function, {function.name: function, gate.TLS + ")": F(gate.TLS + ")", (I(0x800, "ret", "", None),))})

    def test_cold_cut_cannot_hide_capture_inside_called_wrapper(self):
        function = self.worker()
        instructions = list(function.instructions)
        instructions.insert(-1, I(0x128, "call", "900 <wrapper>", "wrapper"))
        function = F("worker", tuple(instructions))
        wrapper = F("wrapper", (I(0x900, "call", "700 <append>",
                                  "ProducerObservationStream::append()"),
                                I(0x905, "ret", "", None)))
        with self.assertRaisesRegex(gate.AuditError, "unclassified call"):
            gate.active_region(function, {"worker": function, "wrapper": wrapper, gate.TLS + ")": F(gate.TLS + ")", (I(0x800, "ret", "", None),))})

    def test_tls_cut_callee_itself_cannot_hide_capture(self):
        function = self.worker()
        tls = F(gate.TLS + ")", (I(0x800, "call", "700 <append>",
                                   "ProducerObservationStream::append()"),
                                I(0x805, "ret", "", None)))
        with self.assertRaisesRegex(gate.AuditError, "cut callee"):
            gate.active_region(function, {"worker": function, tls.name: tls})

    def test_external_entry_cannot_bypass_loader_callback_definition(self):
        name = "cpu_prefetch::platform::(anonymous namespace)::Walk::visit()"
        function = F("tls", (I(0x100, "lea", "0(%rip),%rdi", name),
                             I(0x105, "call", "500 <dl_iterate_phdr@plt>", "dl_iterate_phdr@plt"),
                             I(0x110, "ret", "", None)))
        functions = {"tls": function, name: F(name, (I(0x500, "ret", "", None),))}
        self.assertEqual(gate.tls_callback(function, functions), {name})
        functions["external"] = F("external", (I(0x200, "jmp", "105 <tls+0x5>", "tls"),))
        with self.assertRaisesRegex(gate.AuditError, "external entry"):
            gate.tls_callback(function, functions)

    def test_raw_clock_argument_must_be_dominating_and_actual_raw_id(self):
        for argument, succeeds in (("$4,%edi", True), ("$1,%edi", False)):
            function = F("clock", (I(0x100, "mov", argument, None),
                I(0x105, "call", "500 <clock_gettime@plt>", "clock_gettime@plt"), I(0x110, "ret", "", None)))
            if succeeds:
                self.assertEqual(gate.verify_raw_clocks(function, {"clock": function}), ["0x105"])
            else:
                with self.assertRaises(gate.AuditError):
                    gate.verify_raw_clocks(function, {"clock": function})

    def test_cross_function_entry_cannot_bypass_raw_argument_definition(self):
        function = F("clock", (I(0x100, "mov", "$4,%edi", None),
            I(0x105, "call", "500 <clock_gettime@plt>", "clock_gettime@plt"), I(0x110, "ret", "", None)))
        external = F("external", (I(0x200, "jmp", "105 <clock+0x5>", "clock"),))
        with self.assertRaisesRegex(gate.AuditError, "external entry"):
            gate.verify_raw_clocks(function, {"clock": function, "external": external})


if __name__ == "__main__":
    unittest.main()
