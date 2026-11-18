"""D286 control lifetime, failed entry, owner death and exact recovery checks."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_locked_compaction_guard_v1 as guard


class Control:
    def __init__(self, value=1):
        self.value = value
        self.boot_id = 'test-boot'
        self.writes = []
        self.ignore = None
        self.raise_after_write = None

    def boot(self):
        return self.boot_id

    def read(self):
        return self.value

    def write(self, value):
        self.writes.append(value)
        if self.ignore != value:
            self.value = value
        if self.raise_after_write == value:
            raise OSError('write failed after effect')


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.control = Control()
        self.lease = self.root / 'lease'

    def make(self, name='evidence', **kwargs):
        return guard.Guard(self.root / name, control=self.control, lease=self.lease,
                           deadline_ns=kwargs.get('deadline_ns', time.monotonic_ns() + 10**9))

    def document(self, name):
        return json.loads((self.root / 'evidence' / name).read_bytes())

    def test_exact_prestate_is_durable_before_mutation_and_restored(self):
        original = self.control.write

        def write(value):
            if value == 0:
                self.assertEqual(self.document('intent.json')['observed_prestate'], 1)
                self.assertTrue(self.lease.read_bytes())
            original(value)

        with patch.object(self.control, 'write', write):
            with self.make() as held:
                self.assertEqual(held.verify(), dict(requested_value=0, observed_value=0, verified=True))
                self.assertEqual(self.document('prepared.json')['observed_value'], 0)
        self.assertEqual(self.control.writes, [0, 1])
        self.assertEqual(self.control.value, 1)
        self.assertEqual(self.lease.read_bytes(), b'')
        self.assertTrue(self.document('restoration.json')['verified'])

    def test_already_disabled_prestate_stays_disabled(self):
        self.control.value = 0
        with self.make() as held:
            held.verify()
        self.assertEqual(self.control.writes, [])
        self.assertEqual(self.document('restoration.json')['requested_value'], 0)

    def test_explicit_recovery_is_idempotent_only_with_actual_restoration(self):
        with self.make():
            pass
        writes = list(self.control.writes)
        report = guard.recover(self.root / 'evidence', control=self.control, lease=self.lease)
        self.assertTrue(report['verified'])
        self.assertEqual(self.control.writes, writes)
        self.control.value = 0
        with self.assertRaisesRegex(RuntimeError, 'no verified prior restoration'):
            guard.recover(self.root / 'evidence', control=self.control, lease=self.lease)
        self.assertEqual(self.control.writes, writes)

    def test_exception_and_system_exit_restore_exact_control(self):
        for index, error in enumerate((RuntimeError('worker failed'), SystemExit(3))):
            with self.subTest(error=error), self.assertRaises(type(error)):
                with self.make('failure' + str(index)):
                    raise error
            self.assertEqual(self.control.value, 1)
            self.assertEqual(self.lease.read_bytes(), b'')

    def test_failed_write_after_effect_restores_during_failed_entry(self):
        self.control.raise_after_write = 0
        with self.assertRaisesRegex(OSError, 'after effect'):
            with self.make():
                self.fail('must not enter a failed preparation')
        self.assertEqual(self.control.writes, [0, 1])
        self.assertEqual(self.control.value, 1)
        self.assertTrue(self.document('restoration.json')['verified'])

    def test_requested_control_without_actual_readback_cannot_enter(self):
        self.control.ignore = 0
        with self.assertRaisesRegex(RuntimeError, 'became enabled'):
            with self.make():
                self.fail('request is not verified state')
        self.assertEqual(self.control.value, 1)
        self.assertEqual(self.lease.read_bytes(), b'')

    def test_failed_prepared_publication_restores(self):
        publish = guard.publish

        def fail_prepared(path, value):
            if path.name == 'prepared.json':
                raise OSError('publication failed')
            publish(path, value)

        with patch.object(guard, 'publish', fail_prepared), self.assertRaises(OSError):
            with self.make():
                self.fail('failed publication must stop')
        self.assertEqual(self.control.value, 1)
        self.assertTrue(self.document('restoration.json')['verified'])

    def test_failed_restore_retains_occupied_lease_and_allows_explicit_recovery(self):
        with self.assertRaisesRegex(RuntimeError, 'restoration failed'):
            with self.make():
                self.control.ignore = 1
        self.assertEqual(self.control.value, 0)
        self.assertTrue(self.lease.read_bytes())
        self.assertFalse((self.root / 'evidence/restoration.json').exists())
        with self.assertRaisesRegex(RuntimeError, 'unrestored prior lease'):
            with self.make('new'):
                self.fail('no implicit retry')
        self.control.ignore = None
        report = guard.recover(self.root / 'evidence', control=self.control, lease=self.lease)
        self.assertTrue(report['verified'])
        self.assertEqual(self.control.value, 1)
        self.assertEqual(self.lease.read_bytes(), b'')

    def test_owner_death_requires_exact_explicit_recovery(self):
        held = self.make().__enter__()
        held.unlock()  # Model process death without running its finally block.
        with self.assertRaisesRegex(RuntimeError, 'unrestored prior lease'):
            with self.make('new'):
                self.fail('must not erase original recovery state')
        original = (self.root / 'evidence/intent.json').read_bytes()
        wrong = json.loads(original)
        wrong['observed_prestate'] = 0
        (self.root / 'evidence/intent.json').write_bytes(guard.canonical(wrong))
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            guard.recover(self.root / 'evidence', control=self.control, lease=self.lease)
        self.assertEqual(self.control.value, 0)
        (self.root / 'evidence/intent.json').write_bytes(original)
        guard.recover(self.root / 'evidence', control=self.control, lease=self.lease)
        self.assertEqual(self.control.value, 1)

    def test_second_owner_and_recovery_cannot_override_live_holder(self):
        with self.make():
            with self.assertRaises(BlockingIOError):
                with self.make('second'):
                    self.fail('one owner only')
            with self.assertRaises(BlockingIOError):
                guard.recover(self.root / 'evidence', control=self.control, lease=self.lease)
            self.assertEqual(self.control.value, 0)

    def test_drift_is_rejected_and_original_value_restored(self):
        with self.assertRaisesRegex(RuntimeError, 'became enabled'):
            with self.make() as held:
                self.control.value = 1
                held.verify()
        self.assertEqual(self.control.value, 1)

    def test_expiry_blocks_entry_and_does_not_block_restoration(self):
        with self.assertRaisesRegex(RuntimeError, 'deadline expired'):
            self.make(deadline_ns=0).__enter__()
        self.assertEqual(self.control.writes, [])
        with self.assertRaisesRegex(RuntimeError, 'deadline expired'):
            with self.make() as held:
                held.deadline_ns = 0
                held.verify()
        self.assertEqual(self.control.value, 1)
        self.assertTrue(self.document('restoration.json')['verified'])

    def test_cross_boot_restore_is_refused_with_original_lease_preserved(self):
        held = self.make().__enter__()
        held.unlock()
        self.control.boot_id = 'other-boot'
        with self.assertRaisesRegex(RuntimeError, 'across boots'):
            guard.recover(self.root / 'evidence', control=self.control, lease=self.lease)
        self.assertEqual(self.control.value, 0)
        self.assertTrue(self.lease.read_bytes())

    def test_existing_evidence_and_symlink_lease_are_not_overwritten(self):
        (self.root / 'evidence').mkdir()
        with self.assertRaises(FileExistsError):
            self.make().__enter__()
        self.assertEqual(self.control.writes, [])
        target = self.root / 'target'
        target.write_text('preserve')
        self.lease.unlink()
        self.lease.symlink_to(target)
        with self.assertRaises(OSError):
            self.make('new').__enter__()
        self.assertEqual(target.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
