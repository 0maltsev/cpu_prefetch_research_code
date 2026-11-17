"""Metadata compatibility gate; synthetic qualification boundary, real bound reads."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_q16a_q16c_descriptive_handoff_v1 as current
import test_stage17_q16a_daycap_handoff_v1 as old
from test_stage17_formal_scheduled_descriptive_v1 import plan_fixture


class Q16cQ16aReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='q16c-reuse-software-')
        self.addCleanup(self.temp.cleanup)
        with mock.patch.object(old, 'current', current):
            self.e = old.Evidence(Path(self.temp.name), plan_fixture())
        self.e.proof['scope']['decision'] = 'D270'
        self.refresh()

    def refresh(self):
        e = self.e
        for side, (root, index, _) in e.releases.items():
            for name in current.REVIEWED_COLD_SOURCES:
                path = Path(root) / name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((current.daycap.ROOT / name).read_bytes() if side == 'current' else name.encode())
                index[name] = dict(old.binding(path), path=name)
            worker = e.proof[side]['worker']
            with mock.patch.object(old, 'current', current): report = old.strict_report(Path(root), worker)
            path = Path(root) / 'build-provenance/formal_codegen_report.json'
            rb = old.save(path, report); index['build-provenance/formal_codegen_report.json'] = dict(rb, path='build-provenance/formal_codegen_report.json')
            e.proof[side]['formal_codegen'] = rb
            inv = old.save(Path(root) / 'BUNDLE_INVENTORY.json', dict(files=list(index.values())))
            e.proof[side]['bundle_inventory'] = inv
            e.contexts[side]['inventory_sha256'] = inv['sha256']
            e.releases[side] = root, index, report
        names = current.admission._source_names(e.releases['current'][1])
        e.proof['source_comparisons'] = [dict(relative_path=name,
            **{side: dict(e.releases[side][1][name], path=str(Path(e.releases[side][0]) / name))
               for side in ('original', 'current')}) for name in sorted(names)]

    def consume(self):
        e = self.e; real = current._release
        def release(side, context, reader, source):
            return e.releases['original'] if source == current.original.SOURCE else real(side, context, reader, source)
        proof = old.save(e.root / 'compatibility.json', e.proof)
        with mock.patch.object(current.original, 'consume', return_value=e.result), \
             mock.patch.object(current, '_release', side_effect=release):
            return current.consume(e.document, validation=e.validation, plan=e.plan,
                selected_duration_ns=1_000_000_000, original_validation=e.original_validation,
                original_plan=e.original_plan, compatibility=proof, original_boot_id=e.boot, boot_id=e.boot)

    def test_full180_setting_handoff_preserves_old_result_and_current_actual_bytes(self):
        before = copy.deepcopy(self.e.result)
        self.assertIs(self.consume(), self.e.result)
        self.assertEqual(self.e.result, before)
        self.assertEqual(len(self.e.plan['captures']), 180)
        for flag in ('execution_authority', 'phase18_authority', 'family_validity_established'):
            self.assertFalse(self.e.result[flag])

    def test_cold_source_hashes_are_exact_and_no_hot_source_exception_exists(self):
        self.assertEqual(len(current.REVIEWED_COLD_SOURCES), 5)
        for name, digest in current.REVIEWED_COLD_SOURCES.items():
            self.assertEqual(hashlib.sha256((current.daycap.ROOT / name).read_bytes()).hexdigest(), digest)
        for name in ('src/runner/stage17_fixed_action.cpp', 'include/cpu_prefetch/extra_dependency.hpp'):
            e = self.e; root, index, report = e.releases['current']
            path = Path(root) / name; before = path.read_bytes(); path.write_bytes(before + b' changed')
            index[name] = dict(old.binding(path), path=name)
            e.proof['current']['bundle_inventory'] = old.save(Path(root) / 'BUNDLE_INVENTORY.json', dict(files=list(index.values())))
            e.contexts['current']['inventory_sha256'] = e.proof['current']['bundle_inventory']['sha256']
            row = next(r for r in e.proof['source_comparisons'] if r['relative_path'] == name)
            row['current'] = old.binding(path)
            with self.subTest(name=name), self.assertRaises(current.Error): self.consume()
            path.write_bytes(before); self.refresh()

    def test_missing_dependency_or_wrong_scope_blocks_reuse(self):
        self.e.proof['source_comparisons'].pop()
        with self.assertRaises(current.Error): self.consume()
        self.refresh(); self.e.proof['scope']['decision'] = 'D254'
        with self.assertRaises(current.Error): self.consume()


if __name__ == '__main__': unittest.main()
