"""D297 selects the original failed-family receipt without changing history."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import stage17_q16c_incident_metadata_v1 as current


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.incident = ROOT / 'docs/evidence/stage17/Q16C-D285-NATIVE-STOP-20261118-01/isolation-restoration.json'
        diagnostic = json.loads((ROOT / 'docs/evidence/stage17/Q16C-D295-PREPARATION-STOP-20261119-01/binding-diagnostic.json').read_bytes())
        self.wrong = diagnostic['restoration_binding']
        self.seed = dict(restoration=self.wrong, original_plan={'preserved': True}, decision='D288')

    def publish(self, root):
        path = root / 'q16c-continuation-recovery-1/restoration.json'
        path.parent.mkdir()
        path.write_bytes(self.incident.read_bytes())
        return path

    def test_actual_failure_binding_is_replaced_by_exact_incident_receipt_only(self):
        before = copy.deepcopy(self.seed)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = self.publish(root)
            clock = root / 'clock-qualification-v29-1/restoration.json'
            clock.parent.mkdir()
            clock.write_text('{"verified":true,"wrong_historical_receipt":true}')
            wrong_before = clock.read_bytes()
            result = current.corrected_seed(self.seed, root)
            self.assertEqual(result['restoration']['sha256'], current.RESTORATION_SHA)
            self.assertEqual(result['restoration']['size_bytes'], 842)
            self.assertEqual(result['restoration']['path'], str(receipt))
            self.assertEqual({k:v for k,v in result.items() if k != 'restoration'},
                             {k:v for k,v in before.items() if k != 'restoration'})
            self.assertEqual(self.seed, before)
            self.assertEqual(clock.read_bytes(), wrong_before)
            self.assertEqual(receipt.read_bytes(), self.incident.read_bytes())

    def test_missing_or_changed_incident_receipt_never_falls_back_to_clock_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = root / 'clock-qualification-v29-1/restoration.json'
            clock.parent.mkdir()
            clock.write_bytes(self.incident.read_bytes())
            with self.assertRaises(FileNotFoundError):
                current.corrected_seed(self.seed, root)
            receipt = self.publish(root)
            receipt.write_bytes(receipt.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'immutable original incident'):
                current.corrected_seed(self.seed, root)

    def test_symlink_receipt_is_rejected_even_when_bytes_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'q16c-continuation-recovery-1/restoration.json'
            path.parent.mkdir()
            path.symlink_to(self.incident)
            with self.assertRaisesRegex(ValueError, 'nonsymlink'):
                current.corrected_seed(self.seed, root)

    def test_bound_input_checks_the_same_bytes_it_returns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'metadata.json'
            path.write_bytes(b'{"original":true}')
            expected = current.binding(path)
            self.assertEqual(current.bound_bytes(expected), path.read_bytes())
            path.write_bytes(b'{"modified":true}')
            with self.assertRaisesRegex(ValueError, 'metadata binding differs'):
                current.bound_bytes(expected)

    def test_repaired_binding_agrees_with_unchanged_runtime_contract(self):
        import stage17_q16c_prefix_reuse_v1 as frozen
        self.assertEqual(frozen.FIXED['restoration'], (842, current.RESTORATION_SHA))
        self.assertNotEqual((self.wrong['size_bytes'], self.wrong['sha256']), frozen.FIXED['restoration'])

    def test_rehearsal_changes_only_incident_binding_and_separate_output_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / 'original'
            original.mkdir()
            self.publish(original)
            inventory = root / 'inventory.json'
            inventory.write_bytes(current.encode(dict(source_revision=current.SOURCE)))
            source = root / 'archive_source.py'
            source.write_bytes(b'# unchanged source\n')
            overlay = root / 'overlay.json'
            overlay.write_bytes(current.encode(dict(unchanged_archive=True,
                sources={'archive_source': current.binding(source)})))
            seed = root / 'seed.json'
            seed.write_bytes(current.encode(self.seed))
            recovery = root / 'd295-independent-recovery-1.json'
            recovery.write_bytes(current.encode(dict(verified=True, errors=[])))
            config = dict(source_revision=current.SOURCE, evidence_root=str(root),
                          execution_authority=False, phase18_authority=False,
                          incident_reuse_inputs=current.binding(seed), overlay=current.binding(overlay),
                          candidate_inventory=current.binding(inventory), packet_root='/original-packet',
                          output_root='/original-output', preserved_nested={'seed': 'unchanged'})
            path = root / 'original-configuration.json'
            path.write_bytes(current.encode(config))
            digest = current.binding(path)['sha256']
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            output = root / 'd297-software-preparation-test'
            with patch.object(current, 'EVIDENCE', root), patch.object(current, 'ORIGINAL', original), \
                    patch.object(current, 'CONFIGURATION_SHA', digest):
                result = current.prepare(path, output)
                changed = json.loads(current.bound_bytes(result['configuration']))
                self.assertEqual({k for k in config if config[k] != changed[k]},
                                 {'incident_reuse_inputs', 'packet_root', 'output_root', 'overlay'})
                actual_overlay = json.loads(current.bound_bytes(changed['overlay']))
                self.assertTrue(actual_overlay['unchanged_archive'])
                self.assertEqual(current.bound_bytes(actual_overlay['sources']['archive_source']), source.read_bytes())
                self.assertEqual(Path(actual_overlay['sources']['archive_source']['path']).parent, output / 'packet')
                self.assertFalse((output / 'constructed-output').exists())
                self.assertEqual(result['experiments_started'], 0)
                with self.assertRaisesRegex(ValueError, 'exclusive rehearsal output'):
                    current.prepare(path, output)
                with self.assertRaisesRegex(ValueError, 'separate software-only'):
                    current.prepare(path, root / 'other-output')
            for p, raw in before.items():
                self.assertEqual(p.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
