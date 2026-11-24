"""Fresh-read checks, allocation bounds and full replay parity; software only."""
from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import stage17_archive_metadata_fast_v1 as v1
import stage17_archive_metadata_fast_v2 as v2
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_v1 as archive
import test_stage17_formal_archive_custody_v1 as original_tests
from test_stage17_formal_archive_v1 import digest


@contextmanager
def read_probe(callback):
    """Observe/control the actual file read without replacing file checks."""
    original_fdopen = os.fdopen
    class Stream:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            self.stream.__enter__()
            return self
        def __exit__(self, *args):
            return self.stream.__exit__(*args)
        def fileno(self):
            return self.stream.fileno()
        def read(self, size):
            return callback(self.stream, size)
    with mock.patch.object(os, 'fdopen', side_effect=lambda *a, **kw: Stream(original_fdopen(*a, **kw))):
        yield


class BoundReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'parent' / 'child'
        self.directory.mkdir(parents=True)
        self.path = self.directory / 'record.json'
        self.data = b'{"value":123}'
        self.path.write_bytes(self.data)
        self.store = object.__new__(v2.make_store_class())
        self.binding = archive.PhysicalBinding(len(self.data), digest(self.data))

    def read(self, *, binding=True, maximum=1024**3):
        return self.store._read_bound(self.path, self.binding if binding else None, maximum)

    def test_reads_observed_size_plus_one_instead_of_gib_ceiling(self):
        requests = []
        def observe(stream, size):
            requests.append(size)
            # Observe the old GiB request without allocating its requested buffer.
            return stream.read(len(self.data) + 1)
        with read_probe(observe):
            original = object.__new__(custody.ProgramStore)
            self.assertEqual(original._read_bound(self.path, self.binding, 1024**3), self.data)
            self.assertEqual(self.read(), self.data)
        self.assertEqual(requests, [1024**3 + 1, len(self.data) + 1])

    def test_empty_exact_and_exceeded_maximum_and_wrong_bindings(self):
        self.assertEqual(self.read(maximum=len(self.data)), self.data)
        with self.assertRaisesRegex(custody.CustodyError, 'metadata byte bound'), \
                read_probe(lambda *_: self.fail('oversize file was read')):
            self.read(maximum=len(self.data) - 1)
        for binding in (archive.PhysicalBinding(len(self.data) + 1, digest(self.data)),
                        archive.PhysicalBinding(len(self.data), '0' * 64)):
            with self.subTest(binding=binding), self.assertRaisesRegex(custody.CustodyError, 'metadata binding differs'):
                self.store._read_bound(self.path, binding, len(self.data))
        self.path.write_bytes(b'')
        empty = archive.PhysicalBinding(0, digest(b''))
        self.assertEqual(self.store._read_bound(self.path, empty, 0), b'')

    def test_cached_ancestors_are_strings_and_every_read_restats_them(self):
        expected = [str(parent) for parent in reversed(self.path.parents)]
        with mock.patch.object(os, 'lstat', wraps=os.lstat) as lstat:
            for _ in range(3):
                self.assertEqual(self.read(), self.data)
        self.assertEqual([call.args[0] for call in lstat.call_args_list], expected * 3)
        cache = self.store._metadata_read_ancestor_strings
        self.assertEqual(cache, {str(self.directory): tuple(expected)})
        self.assertTrue(all(type(key) is str and all(type(p) is str for p in value)
                            for key, value in cache.items()))
        with mock.patch.object(Path, 'parents', new_callable=mock.PropertyMock,
                               side_effect=AssertionError('Path ancestry materialized')):
            self.assertEqual(self.read(), self.data)
        sibling = self.directory / 'sibling.json'
        sibling.write_bytes(self.data)
        self.assertEqual(self.store._read_bound(sibling, self.binding, 1024), self.data)
        self.assertEqual(len(cache), 1)
        other = object.__new__(v2.make_store_class())
        other._read_bound(self.path, self.binding, 1024)
        self.assertIsNot(cache, other._metadata_read_ancestor_strings)

    def test_normalized_parent_strings_match_original_path_behavior(self):
        unused = self.directory / 'unused'
        unused.mkdir()
        path = unused / '..' / self.path.name
        baseline = object.__new__(custody.ProgramStore)
        self.assertEqual(self.store._read_bound(path, self.binding, 1024),
                         baseline._read_bound(path, self.binding, 1024))
        self.assertEqual(set(self.store._metadata_read_ancestor_strings), {str(self.directory)})

    def test_warmed_cache_rejects_replaced_symlink_ancestor(self):
        self.read()
        moved = self.directory.with_name('moved')
        self.directory.rename(moved)
        self.directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(archive.ArchiveError, 'symlink path component'):
            self.read()

    def test_ordinary_ancestor_replacement_never_reuses_content_or_hash(self):
        self.read()
        self.directory.rename(self.directory.with_name('moved'))
        self.directory.mkdir()
        changed = b'x' * len(self.data)
        self.path.write_bytes(changed)
        with self.assertRaisesRegex(custody.CustodyError, 'metadata binding differs'):
            self.read()
        self.assertEqual(self.read(binding=False), changed)

    def test_final_symlink_missing_and_nonregular_errors_match_original(self):
        link = self.directory / 'link'
        link.symlink_to(self.path)
        fifo = self.directory / 'fifo'
        os.mkfifo(fifo)
        baseline = object.__new__(custody.ProgramStore)
        for path in (link, self.directory / 'missing', self.directory, fifo):
            outcomes = []
            for store in (baseline, self.store):
                try:
                    store._read_bound(path, None, 1024)
                except Exception as error:
                    outcomes.append((type(error), str(error)))
            self.assertEqual(len(outcomes), 2)
            self.assertEqual(*outcomes)

    def test_ancestor_lstat_error_semantics_match_original(self):
        baseline = object.__new__(custody.ProgramStore)
        for error in (OSError(errno.EACCES, 'injected ancestor denial'), ValueError('bad ancestor')):
            for store in (baseline, self.store):
                with self.subTest(error=error, store=type(store)), \
                        mock.patch.object(os, 'lstat', side_effect=error):
                    # The original Path.is_symlink/islink ignores these errors;
                    # opening and stable reads still check the real target.
                    self.assertEqual(store._read_bound(self.path, self.binding, 1024), self.data)

    def test_same_inode_mutation_with_restored_mtime_is_freshly_hashed(self):
        self.read()
        before = self.path.stat()
        self.path.write_bytes(b'x' * len(self.data))
        os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(self.path.stat().st_ino, before.st_ino)
        self.assertEqual(self.path.stat().st_mtime_ns, before.st_mtime_ns)
        with self.assertRaisesRegex(custody.CustodyError, 'metadata binding differs'):
            self.read()

    def test_growth_shrink_and_short_read_fail_length_check(self):
        for mode in ('grow', 'shrink', 'short'):
            self.path.write_bytes(self.data)
            def change(stream, size):
                if mode == 'grow':
                    with self.path.open('ab') as output:
                        output.write(b'growth')
                elif mode == 'shrink':
                    os.truncate(self.path, 1)
                raw = stream.read(size)
                return raw[:1] if mode == 'short' else raw
            with self.subTest(mode=mode), read_probe(change), \
                    self.assertRaisesRegex(custody.CustodyError, 'metadata read length'):
                self.read()

    def test_inplace_change_after_read_with_restored_mtime_fails_fd_stamp(self):
        before = self.path.stat()
        def change(stream, size):
            raw = stream.read(size)
            self.path.write_bytes(b'x' * len(self.data))
            os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
            return raw
        with read_probe(change), self.assertRaisesRegex(custody.CustodyError, 'metadata changed during read'):
            self.read()

    def test_path_replacement_after_final_fd_stat_fails_pathname_stamp(self):
        original_fstat = os.fstat
        calls = 0
        def replace_after_stat(fd):
            nonlocal calls
            st = original_fstat(fd)
            calls += 1
            if calls == 3:
                self.path.rename(self.directory / 'old')
                self.path.write_bytes(self.data)
            return st
        with mock.patch.object(os, 'fstat', side_effect=replace_after_stat), \
                self.assertRaisesRegex(custody.CustodyError, 'metadata changed during read'):
            self.read()

    def test_open_flags_and_all_post_open_failures_close_descriptor(self):
        original_open, original_fstat = os.open, os.fstat
        for mode in ('regular-check', 'fdopen', 'before-stamp', 'read', 'bound', 'nonregular',
                     'after-stamp', 'path-stamp', 'hash', 'length'):
            descriptors, flags = [], []
            def opened(path, options):
                fd = original_open(path, options)
                descriptors.append(fd)
                flags.append(options)
                return fd
            fstat_calls = 0
            def fstat(fd):
                nonlocal fstat_calls
                fstat_calls += 1
                if (mode == 'regular-check' or (mode == 'before-stamp' and fstat_calls == 2)
                        or (mode == 'after-stamp' and fstat_calls == 3)):
                    raise OSError(errno.EIO, 'injected fstat failure')
                return original_fstat(fd)
            with self.subTest(mode=mode), mock.patch.object(os, 'open', side_effect=opened), \
                    mock.patch.object(os, 'fstat', side_effect=fstat):
                if mode == 'fdopen':
                    with mock.patch.object(os, 'fdopen', side_effect=OSError(errno.ENOMEM, 'fdopen')), \
                            self.assertRaises(OSError):
                        self.read()
                elif mode == 'read':
                    def failed_read(*_):
                        raise OSError(errno.EIO, 'read')
                    with read_probe(failed_read), self.assertRaises(OSError):
                        self.read()
                elif mode == 'nonregular':
                    with self.assertRaisesRegex(archive.ArchiveError, 'not a regular file'):
                        self.store._read_bound(self.directory, None, 1024)
                elif mode == 'bound':
                    with self.assertRaisesRegex(custody.CustodyError, 'metadata byte bound'):
                        self.read(maximum=0)
                elif mode == 'path-stamp':
                    with mock.patch.object(Path, 'stat', side_effect=OSError(errno.EIO, 'path stamp')), \
                            self.assertRaises(OSError):
                        self.read()
                elif mode == 'hash':
                    with self.assertRaisesRegex(custody.CustodyError, 'metadata binding differs'):
                        self.store._read_bound(self.path, archive.PhysicalBinding(len(self.data), '0' * 64), 1024)
                elif mode == 'length':
                    with read_probe(lambda *_: b''), \
                            self.assertRaisesRegex(custody.CustodyError, 'metadata read length'):
                        self.read()
                else:
                    with self.assertRaises(OSError):
                        self.read()
            self.assertEqual(len(descriptors), 1)
            self.assertEqual(flags, [os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK])
            with self.assertRaises(OSError) as caught:
                original_fstat(descriptors[0])
            self.assertEqual(caught.exception.errno, errno.EBADF)
        with mock.patch.object(os, 'open', side_effect=OSError(errno.EACCES, 'open')), \
                mock.patch.object(os, 'close') as close, self.assertRaises(PermissionError):
            self.read()
        close.assert_not_called()


class FactoryAndReplayTests(unittest.TestCase):
    def test_original_factories_globals_and_methods_are_untouched(self):
        original_globals = dict(vars(custody))
        v1_globals = dict(vars(v1))
        original_members = dict(vars(custody.ProgramStore))
        base = v1.make_store_class()
        base_members, base_scope = dict(vars(base)), dict(base.__init__.__globals__)
        modules = dict(sys.modules)
        first, second = v2.make_store_class(base=base), v2.make_store_class(base=base)
        self.assertEqual(original_globals, vars(custody))
        self.assertEqual(v1_globals, vars(v1))
        self.assertEqual(original_members, vars(custody.ProgramStore))
        self.assertEqual(base_members, vars(base))
        self.assertEqual(base_scope, base.__init__.__globals__)
        self.assertEqual(modules, sys.modules)
        self.assertTrue(issubclass(first, base))
        self.assertIsNot(first.__init__.__globals__, second.__init__.__globals__)
        for name in ('_replay', '_apply', '_validate_transition', 'append', 'physical_accounting'):
            self.assertIs(getattr(first, name).__code__, getattr(base, name).__code__)
        self.assertIs(first._read_bound.__globals__, first.__init__.__globals__)
        self.assertIs(first.__init__.__globals__['ProgramStore'], first)

    def test_custom_inventory_survives_factory_composition(self):
        base = v1.make_store_class()
        scope = dict(base.__init__.__globals__)
        exec('def physical_accounting(self): return PhysicalUsage(11, 22, 33, 44)', scope)
        custom = type('SeparateInventory', (base,), {'physical_accounting': scope['physical_accounting']})
        result = v2.make_store_class(base=custom)
        self.assertEqual(object.__new__(result).physical_accounting(), custody.PhysicalUsage(11, 22, 33, 44))
        self.assertIs(result.physical_accounting.__code__, custom.physical_accounting.__code__)
        self.assertIs(result.physical_accounting.__globals__, result.__init__.__globals__)

    def test_full_replay_state_and_all_prefix_reads_match_original_and_v1(self):
        # Match the existing custody fixture's software-only capacity setup.
        capacity = types.SimpleNamespace(f_bavail=7_000_000_000_000, f_frsize=1, f_favail=100_000)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(os, 'statvfs', return_value=capacity):
            f = original_tests.CustodyFixture(tmp)
            fast_class = v2.make_store_class()
            def opened(cls):
                return cls(f.root, scope_sha256=f.scope, family_id=f.family, limits=f.limits)
            with opened(fast_class) as store:
                f.begin(store)
                f.reserve(store)
                f.publish(store)
                f.release(store)
                receipt = dict(schema_version='cpu-prefetch-stage17-formal-archive-custody/1',
                    program_scope_sha256=f.scope, plan_sha256=f.family, capture_ordinal=0,
                    checkpoint=vars(f.checkpoint), status='ARCHIVED_AND_RELEASED',
                    scientific_validity='NOT_ASSESSED', execution_authority=False)
                store.retain_custody_receipt('formal-capture-0-archive-custody.json', archive.canonical(receipt))
                store.record_failure(None, operation='synthetic-only', detail='retained evidence')
            fields = ('_sequence', '_previous', '_states', '_families', '_retained_receipts',
                      '_capture_pending', '_record_bindings', 'scope', '_checkpoint', '_sources',
                      '_verify_checkpoint', '_family_identity', '_directories', '_root_identity')
            baseline = None
            names = sorted((f.root / 'ledger').iterdir())
            for cls in (custody.ProgramStore, v1.make_store_class(), fast_class, fast_class):
                current = opened(cls)
                with mock.patch.object(current, '_read_bound', wraps=current._read_bound) as read:
                    with current:
                        state = {key: getattr(current, key) for key in fields}
                        if baseline is None:
                            baseline = state
                        self.assertEqual(state, baseline)
                        observed = [call.args[0] for call in read.call_args_list
                                    if call.args[0].parent == f.root / 'ledger']
                        self.assertEqual(observed, names)
                        for bound in current._record_bindings:
                            self.assertEqual(current.read_verified_record(bound)['sequence'], int(bound.file_name[:-5]))
            # A cached-ancestor store must still reparse and validate the prefix.
            path = names[0]
            original_bytes = path.read_bytes()
            document = archive.parse_json(original_bytes)
            document['previous_sha256'] = 'f' * 64
            path.write_bytes(archive.canonical(document))
            with self.assertRaisesRegex(custody.CustodyError, 'ledger chain differs'):
                with current:
                    self.fail('corrupt prefix accepted')
            path.write_bytes(original_bytes)
            (f.root / 'ledger' / f'{len(names):016d}.pending').write_bytes(b'partial')
            with self.assertRaisesRegex(custody.CustodyError, 'explicit recovery required'):
                with opened(fast_class):
                    self.fail('invalid ledger accepted')


if __name__ == '__main__':
    unittest.main()
