"""Synthetic byte/read-ledger tests; no hardware or empirical evidence."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage17_discovery_environment_v1 as environment


def call(value: int, error: int = 0) -> dict:
    return {"return_value": value, "error_number": error}


def read(offset: int, count: int, actual: int, error: int = 0) -> dict:
    return {"offset": offset, "requested_bytes": count, "observed": call(actual, error)}


def vma(begin: int, end: int, *, locked: int | None = None,
        kernel_page: int = 4096, mmu_page: int = 4096, huge: int = 0) -> bytes:
    size = end - begin
    locked = size if locked is None else locked
    # Software fixture geometry only; production requires caller's verified page.
    return (f"{begin:x}-{end:x} rw-p 00000000 00:00 0".encode() + b" /test/\xff\rname\n" +
            f"Size: {size // 1024} kB\nKernelPageSize: {kernel_page // 1024} kB\n"
            f"MMUPageSize: {mmu_page // 1024} kB\nAnonHugePages: {huge // 1024} kB\n"
            f"Locked: {locked // 1024} kB\nVmFlags: rd wr mr mw me lo \n".encode())


def sample(raw: bytes, plan: dict, source: int, group: int) -> dict:
    result = {"source_index": source, "group_index": group, "attempted": True,
              "stop": environment.SAMPLE_COMPLETE, "captured_bytes": len(raw),
              "byte_capacity": plan["byte_capacity"], "read_capacity": plan["max_data_reads"],
              "data_reads": 0, "raw_bytes": list(raw), "reads": [],
              "eof_probe": {"offset": 0, "requested_bytes": 0, "observed": None},
              "probe_byte": None}
    offset = 0
    for _ in range(plan["max_data_reads"]):
        requested = min(plan["chunk_bytes"], plan["byte_capacity"] - offset)
        actual = min(requested, len(raw) - offset)
        result["reads"].append(read(offset, requested, actual))
        offset += actual
        if actual == 0 or offset == plan["byte_capacity"]:
            break
    result["data_reads"] = len(result["reads"])
    if result["reads"][-1]["observed"]["return_value"] != 0:
        result["eof_probe"] = read(offset, 1, 0)
    return result


def fixture() -> tuple[dict, list[dict], list[dict]]:
    regions = [{"address": 0x10000 + index * 0x2000, "bytes": 4096,
                "expected_node": index % 2} for index in range(7)]
    raw = b"".join(vma(row["address"], row["address"] + row["bytes"]) for row in regions)
    plans = [{"path": "/proc/self/smaps", "byte_capacity": 65536,
              "chunk_bytes": 1024, "max_data_reads": 128, "requested": [True] * 6},
             {"path_bytes": list(b"/sys/test/\xffsensor"), "byte_capacity": 16,
              "chunk_bytes": 8, "max_data_reads": 4, "requested": [True] * 6}]
    preparations = []
    for index, plan in enumerate(plans):
        normalized = copy.deepcopy(plan)
        if "path" in normalized:
            normalized["path_bytes"] = list(normalized.pop("path").encode())
        preparations.append({"attempted": True, "released": True,
                             "stop": environment.PREPARATION_READY,
                             "open": call(10 + index), "close": call(0), "plan": normalized})
    control = {"schema_version": environment.CONTROL_VERSION,
               "regions": copy.deepcopy(regions), "environment_group_order": list(environment.GROUP_ORDER),
               "environment_preparations": preparations,
               "environment_samples": [sample(raw if source == 0 else b"\xff\x00\n", plan, source, group)
                                       for source, plan in enumerate(plans) for group in range(6)]}
    return control, plans, regions


class EnvironmentEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.control, self.plans, self.regions = fixture()

    def validate(self) -> dict:
        return environment.validate_environment(self.control, self.plans, self.regions, base_page_bytes=4096)

    def replace_smaps(self, raw: bytes, group: int = 0) -> None:
        self.control["environment_samples"][group] = sample(raw, self.plans[0], 0, group)

    def test_complete_delivery_page_policy_and_raw_limits_are_separate(self) -> None:
        report = self.validate()
        self.assertEqual(report["status"], "VERIFIED_DELIVERY_AND_PAGE_POLICY")
        self.assertEqual(report["environmental_limits"], "UNFROZEN_LIMITS")
        self.assertEqual(report["scientific_validity"], "NOT_ASSESSED")
        self.assertFalse(report["execution_authority"])
        self.assertEqual(len(report["smaps_groups"]), 6)
        self.assertTrue(all(len(group["regions"]) == 7 for group in report["smaps_groups"]))
        self.assertEqual(report["sources"][1]["path_bytes"], list(b"/sys/test/\xffsensor"))
        self.assertEqual(report["sources"][1]["groups"][0]["captured_bytes"], 3)
        self.assertEqual(report["sources"][1]["groups"][0]["sha256"],
                         hashlib.sha256(b"\xff\x00\n").hexdigest())

    def test_independent_input_geometry_is_required(self) -> None:
        self.regions[0]["bytes"] = 8192
        with self.assertRaisesRegex(environment.EnvironmentEvidenceError, "geometry"):
            self.validate()

    def test_exact_six_groups_and_source_identities(self) -> None:
        mutants = (
            lambda c: c["environment_samples"].pop(),
            lambda c: c["environment_samples"].append(copy.deepcopy(c["environment_samples"][0])),
            lambda c: c["environment_samples"][0].update(group_index=1),
            lambda c: c["environment_samples"][6].update(source_index=0),
            lambda c: c["environment_preparations"][0]["plan"].update(path_bytes=list(b"/proc/self/maps")),
            lambda c: c["environment_preparations"][0]["plan"].update(chunk_bytes=512),
            lambda c: c["environment_preparations"][0]["plan"]["path_bytes"].__setitem__(0, True),
            lambda c: c["environment_group_order"].reverse(),
        )
        original = copy.deepcopy(self.control)
        for mutate in mutants:
            with self.subTest(mutate=mutate):
                self.control = copy.deepcopy(original)
                mutate(self.control)
                with self.assertRaises(environment.EnvironmentEvidenceError):
                    self.validate()

    def test_smaps_mandatory_in_all_six_groups(self) -> None:
        self.plans[0]["requested"][1] = False
        with self.assertRaisesRegex(environment.EnvironmentEvidenceError, "smaps is mandatory"):
            self.validate()
        self.plans[0]["requested"][1] = True
        self.plans[0]["path"] = "/proc/self/smaps_rollup"
        with self.assertRaisesRegex(environment.EnvironmentEvidenceError, "including /proc/self/smaps"):
            self.validate()

    def test_open_close_and_preparation_failures(self) -> None:
        for key, value in (("attempted", False), ("released", False), ("stop", 3),
                           ("open", call(-1, 13)), ("close", call(-1, 4)),
                           ("close", None), ("close", call(1)), ("open", call(True))):
            with self.subTest(key=key, value=value):
                self.control, self.plans, self.regions = fixture()
                self.control["environment_preparations"][0][key] = value
                with self.assertRaises(environment.EnvironmentEvidenceError):
                    self.validate()

    def test_complete_stop_cannot_hide_failed_or_fabricated_reads(self) -> None:
        changes = (
            lambda s: s["reads"][0].update(offset=1),
            lambda s: s["reads"][0].update(requested_bytes=1023),
            lambda s: s["reads"][0].update(observed=call(-1, 4)),
            lambda s: s["reads"][0].update(observed=call(1025)),
            lambda s: s["reads"][0].update(observed=call(0)),
            lambda s: s.update(captured_bytes=s["captured_bytes"] - 1),
            lambda s: s["raw_bytes"].__setitem__(0, 256),
            lambda s: s["raw_bytes"].__setitem__(0, False),
            lambda s: s.update(raw_bytes=None),
            lambda s: s.update(data_reads=0),
            lambda s: s.update(stop=10),
            lambda s: s.update(attempted=False),
            lambda s: s.update(probe_byte=0),
        )
        for mutate in changes:
            with self.subTest(mutate=mutate):
                self.control, self.plans, self.regions = fixture()
                mutate(self.control["environment_samples"][0])
                with self.assertRaises(environment.EnvironmentEvidenceError):
                    self.validate()

    def test_exact_capacity_requires_successful_eof_probe(self) -> None:
        raw = bytes(self.control["environment_samples"][0]["raw_bytes"])
        self.plans[0].update(byte_capacity=len(raw), chunk_bytes=len(raw), max_data_reads=1)
        self.control["environment_preparations"][0]["plan"].update(byte_capacity=len(raw), chunk_bytes=len(raw), max_data_reads=1)
        for group in range(6):
            self.replace_smaps(raw, group)
        self.validate()
        for probe in (read(len(raw), 1, 1), read(len(raw), 1, -1, 5), read(len(raw) + 1, 1, 0),
                      {"offset": 0, "requested_bytes": 0, "observed": None}):
            with self.subTest(probe=probe):
                self.control["environment_samples"][0]["eof_probe"] = probe
                with self.assertRaises(environment.EnvironmentEvidenceError):
                    self.validate()

    def test_premature_probe_is_not_a_complete_capture(self) -> None:
        s = self.control["environment_samples"][6]
        s["reads"].pop()
        s["data_reads"] -= 1
        s["eof_probe"] = read(3, 1, 0)
        with self.assertRaisesRegex(environment.EnvironmentEvidenceError, "premature"):
            self.validate()

    def test_short_reads_advance_actual_offsets_and_read_budget_probe(self) -> None:
        s = self.control["environment_samples"][6]
        s.update(reads=[read(0, 8, 2), read(2, 8, 1), read(3, 8, 0)], data_reads=3)
        self.validate()
        self.plans[1]["max_data_reads"] = 2
        self.control["environment_preparations"][1]["plan"]["max_data_reads"] = 2
        for row in self.control["environment_samples"][6:]:
            row["read_capacity"] = 2
        s["reads"].pop()
        s.update(data_reads=2, eof_probe=read(3, 1, 0))
        self.validate()
        s.update(eof_probe=read(3, 1, 1), probe_byte=255)
        with self.assertRaises(environment.EnvironmentEvidenceError):
            self.validate()

    def test_unrequested_groups_must_have_no_reads_or_values(self) -> None:
        self.plans[1]["requested"][1] = False
        self.control["environment_preparations"][1]["plan"]["requested"][1] = False
        s = self.control["environment_samples"][7]
        s.update(attempted=False, stop=0, captured_bytes=0, data_reads=0, raw_bytes=None, reads=[])
        self.validate()
        s.update(attempted=True, stop=5, raw_bytes=[])
        self.validate()
        s.update(raw_bytes=[0], captured_bytes=1)
        with self.assertRaises(environment.EnvironmentEvidenceError):
            self.validate()

    def test_empty_sensor_eof_does_not_become_numeric_zero(self) -> None:
        self.control["environment_samples"][6] = sample(b"", self.plans[1], 1, 0)
        report = self.validate()
        self.assertEqual(report["sources"][1]["groups"][0]["captured_bytes"], 0)
        self.assertEqual(report["environmental_limits"], "UNFROZEN_LIMITS")

    def test_missing_malformed_duplicate_and_truncated_smaps(self) -> None:
        raw = bytes(self.control["environment_samples"][0]["raw_bytes"])
        mutations = (b"", raw[:-1], raw.replace(b"KernelPageSize: 4 kB\n", b"", 1),
                     raw.replace(b"Size: 4 kB\n", b"Size: 4 kB\nSize: 4 kB\n", 1),
                     raw.replace(b"Locked: 4 kB", b"Locked: -4 kB", 1),
                     raw.replace(b"KernelPageSize: 4 kB", b"KernelPageSize: 4096 B", 1),
                     raw.rsplit(b"VmFlags:", 1)[0], raw.replace(b"Size: 4 kB", b"Size: 8 kB", 1),
                     raw.replace(b" rw-p ", b" xxxx ", 1), raw + b"unexpected\n")
        for changed in mutations:
            with self.subTest(raw=changed[:80]):
                self.replace_smaps(changed)
                with self.assertRaises(environment.EnvironmentEvidenceError):
                    self.validate()

    def test_page_size_huge_pages_and_unlocked_vma_are_rejected(self) -> None:
        original = bytes(self.control["environment_samples"][0]["raw_bytes"])
        for changed in (original.replace(b"KernelPageSize: 4", b"KernelPageSize: 2048", 1),
                        original.replace(b"MMUPageSize: 4", b"MMUPageSize: 8", 1),
                        original.replace(b"AnonHugePages: 0", b"AnonHugePages: 4", 1),
                        original.replace(b"Locked: 4", b"Locked: 0", 1),
                        original.replace(b"Locked: 4", b"FilePmdMapped: 4 kB\nLocked: 4", 1)):
            with self.subTest():
                self.replace_smaps(changed)
                with self.assertRaises(environment.EnvironmentEvidenceError):
                    self.validate()

    def test_missing_last_region_and_overlapping_smaps_vmas(self) -> None:
        raw = b"".join(vma(r["address"], r["address"] + r["bytes"]) for r in self.regions[:-1])
        self.replace_smaps(raw)
        with self.assertRaisesRegex(environment.EnvironmentEvidenceError, "missing full"):
            self.validate()
        raw = vma(0x10000, 0x13000) + vma(0x12000, 0x14000)
        self.replace_smaps(raw)
        with self.assertRaisesRegex(environment.EnvironmentEvidenceError, "overlapping"):
            self.validate()

    def test_partial_vma_requires_entire_vma_locked(self) -> None:
        tail = b"".join(vma(r["address"], r["address"] + r["bytes"]) for r in self.regions[1:])
        self.replace_smaps(vma(0xF000, 0x11000, locked=4096) + tail)
        with self.assertRaisesRegex(environment.EnvironmentEvidenceError, "full VMA coverage"):
            self.validate()
        self.replace_smaps(vma(0xF000, 0x11000, locked=8192) + tail)
        report = self.validate()
        witness = report["smaps_groups"][0]["regions"][0]["coverage"][0]
        self.assertEqual(witness["covered_begin"], 0x10000)
        self.assertEqual(witness["locked_bytes"], 8192)

    def test_region_split_across_vmas_and_gap_detection(self) -> None:
        self.regions[0]["bytes"] = 8192
        self.control["regions"][0]["bytes"] = 8192
        raw = vma(0x10000, 0x11000) + vma(0x11000, 0x12000)
        raw += b"".join(vma(r["address"], r["address"] + r["bytes"]) for r in self.regions[1:])
        for group in range(6):
            self.replace_smaps(raw, group)
        self.assertEqual(len(self.validate()["smaps_groups"][0]["regions"][0]["coverage"]), 2)
        self.replace_smaps(raw.replace(vma(0x11000, 0x12000), b""))
        with self.assertRaises(environment.EnvironmentEvidenceError):
            self.validate()

    def test_boolean_geometry_duplicate_sources_and_overflow_are_rejected(self) -> None:
        for bad_page in (True, 0, 4095, 1 << 64):
            with self.subTest(page=bad_page), self.assertRaises(environment.EnvironmentEvidenceError):
                environment.validate_environment(self.control, self.plans, self.regions, base_page_bytes=bad_page)
        self.plans.append(copy.deepcopy(self.plans[0]))
        with self.assertRaisesRegex(environment.EnvironmentEvidenceError, "unique"):
            self.validate()

    def test_oversized_smaps_numbers_have_typed_errors(self) -> None:
        raw = bytes(self.control["environment_samples"][0]["raw_bytes"])
        for changed in (raw.replace(b"Locked: 4", b"Locked: " + b"9" * 5000, 1),
                        raw.replace(b"Locked: 4", b"Locked: 18014398509481984", 1),
                        raw.replace(b"10000-11000", b"1" * 40 + b"-" + b"2" * 40, 1)):
            with self.subTest():
                self.replace_smaps(changed)
                with self.assertRaises(environment.EnvironmentEvidenceError):
                    self.validate()

    def test_subpage_vma_boundaries_do_not_prove_base_page_mapping(self) -> None:
        tail = b"".join(vma(r["address"], r["address"] + r["bytes"]) for r in self.regions[1:])
        self.replace_smaps(vma(0xFC00, 0x10C00) + vma(0x10C00, 0x11C00) + tail)
        with self.assertRaisesRegex(environment.EnvironmentEvidenceError, "unaligned"):
            self.validate()

    def test_json_roundtrip_preserves_64_bit_addresses_exactly(self) -> None:
        # Synthetic integer precision proof, not an assertion of mapped hardware.
        for row in self.regions:
            row["address"] += 1 << 55
        self.control["regions"] = copy.deepcopy(self.regions)
        raw = b"".join(vma(r["address"], r["address"] + r["bytes"]) for r in self.regions)
        for group in range(6):
            self.replace_smaps(raw, group)
        self.control = json.loads(json.dumps(self.control))
        report = json.loads(json.dumps(self.validate()))
        witnesses = report["smaps_groups"][0]["regions"]
        for row, witness in zip(self.regions, witnesses):
            self.assertEqual(witness["coverage"][0]["vma_begin"], row["address"])
            self.assertEqual(witness["coverage"][0]["vma_end"], row["address"] + row["bytes"])


if __name__ == "__main__":
    unittest.main()
