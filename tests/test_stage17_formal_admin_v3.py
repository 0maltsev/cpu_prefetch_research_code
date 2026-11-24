"""Actual bounded source files; never activates a stand or formal action."""
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_formal_admin_v3 as admin


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.document = dict(schema_version=admin.SCHEMA, source_revision='a' * 40,
            qualified_worker_unchanged=True, execution_authority=False, files=[])
        for name in sorted(admin.REQUIRED):
            raw = b'"""software-only test source"""\n'
            (self.root / name).write_bytes(raw)
            self.document['files'].append(dict(name=name, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))

    def freeze(self, raw=None):
        raw = json.dumps(self.document).encode() if raw is None else raw
        (self.root / 'manifest.json').write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def test_complete_packet_accepted_as_source_only(self):
        self.assertEqual(admin.verify_packet(self.root, self.freeze()), self.document)

    def test_rehashed_manifest_does_not_hide_member_change(self):
        digest = self.freeze()
        (self.root / self.document['files'][0]['name']).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            admin.verify_packet(self.root, digest)

    def test_missing_closure_duplicate_member_and_path_escape_rejected(self):
        original = list(self.document['files'])
        for rows in (original[:-1], original + [original[0]], [dict(original[0], name='../outside'), *original[1:]]):
            self.document['files'] = rows
            with self.assertRaises(ValueError):
                admin.verify_packet(self.root, self.freeze())

    def test_wrong_manifest_authority_duplicate_json_and_symlink_rejected(self):
        self.freeze()
        with self.assertRaises(ValueError):
            admin.verify_packet(self.root, '0' * 64)
        self.document['execution_authority'] = True
        with self.assertRaises(ValueError):
            admin.verify_packet(self.root, self.freeze())
        self.document['execution_authority'] = False
        with self.assertRaises(ValueError):
            admin.verify_packet(self.root, self.freeze(b'{"files":[],"files":[]}'))
        name = self.document['files'][0]['name']
        source = self.root / name
        original = self.root / 'original'
        source.rename(original)
        source.symlink_to(original)
        with self.assertRaises(ValueError):
            admin.verify_packet(self.root, self.freeze())

    def test_descriptor_and_new_source_are_mandatory_and_finitely_bounded(self):
        original = list(self.document['files'])
        for name in admin.REQUIRED:
            self.document['files'] = [row for row in original if row['name'] != name]
            with self.subTest(name=name), self.assertRaises(ValueError):
                admin.verify_packet(self.root, self.freeze())
        self.document['files'] = original
        descriptor = next(row for row in original if row['name'] == admin.DESCRIPTOR)
        raw = b' ' * (admin.MAX_DESCRIPTOR + 1)
        (self.root / admin.DESCRIPTOR).write_bytes(raw)
        descriptor.update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        with self.assertRaisesRegex(ValueError, 'descriptor size bound'):
            admin.verify_packet(self.root, self.freeze())


class VerifiedImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.name = 'software_source_fixture_v3'
        self.addCleanup(lambda: sys.modules.pop(self.name, None))
        self.addCleanup(lambda: admin._LOADED.pop(self.name, None))

    def test_matching_file_path_does_not_authenticate_a_cached_callback(self):
        path = self.root / 'validate_suffix.py'
        path.write_text('def modules(c): return "verified"\n')
        fake = types.ModuleType('validate_suffix')
        fake.__file__ = str(path)
        fake.modules = lambda c: 'unverified'
        with patch.dict(sys.modules, {'validate_suffix': fake}):
            with self.assertRaises(ValueError):
                admin.reject_foreign_cache(self.root)
            with self.assertRaises(ValueError):
                admin.load_verified_source('validate_suffix', path, path.read_bytes())

    def test_compiles_authenticated_bytes_instead_of_reopening_changed_path(self):
        path = self.root / 'source.py'
        verified = b'def value(): return 7\n'
        path.write_text('def value(): return 999\n')
        module = admin.load_verified_source(self.name, path, verified)
        self.assertEqual(module.value(), 7)
        admin.check_verified_modules()
        # Trusted reentry is stable; another module merely claiming its locator
        # is rejected after activation as well as before it.
        with patch.dict(sys.modules, {self.name: types.ModuleType(self.name)}):
            with self.assertRaises(ValueError):
                admin.check_verified_modules()

    def test_post_activation_code_or_import_replacement_rejected(self):
        module = admin.load_verified_source(self.name, self.root / 'source.py',
            b'import json\ndef value(): return 7\n')
        original = module.value.__code__
        module.value.__code__ = (lambda: 999).__code__
        with self.assertRaises(ValueError):
            admin.check_verified_modules()
        module.value.__code__ = original
        module.json = types.ModuleType('json')
        with self.assertRaises(ValueError):
            admin.check_verified_modules()

    def test_imported_function_alias_cannot_replace_verified_controller_gate(self):
        module = admin.load_verified_source(self.name, self.root / 'source.py',
            b'from json import dumps as prior_gate\ndef value(): return prior_gate(7)\n')
        self.assertEqual(module.value(), '7')
        module.prior_gate = lambda value: 'unchecked'
        with self.assertRaisesRegex(ValueError, 'verified function replaced'):
            admin.check_verified_modules()


class ActivationTests(unittest.TestCase):
    """Real loader in fresh interpreters, software-only bootstrap/CLI sources.

    No stand admission is claimed: the fixture isolates the source-loader trust
    boundary from unavailable stand credentials and original release files.
    Controller tests separately exercise the actual preserved input gates.
    """
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet = self.root / 'packet'
        self.packet.mkdir()
        evidence = self.root / 'evidence'
        original = evidence / 'offline-suffix-operators-1'
        original.mkdir(parents=True)
        bootstrap = b'calls = 0\ndef config(path, sha): return {}\ndef modules(config):\n global calls\n calls += 1\n'
        (original / 'validate_suffix.py').write_bytes(bootstrap)
        self.bootstrap_sha = hashlib.sha256(bootstrap).hexdigest()
        sources = {name: b'SOFTWARE_ONLY = True\n' for name in admin.REQUIRED}
        sources['stage17_formal_admin_v3.py'] = Path(admin.__file__).read_bytes()
        sources[admin.DESCRIPTOR] = b'{"software_fixture":true,"source_revision":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'
        sources['stage17_archive_overlay_v1.py'] = b'''calls = []
def configure_verified_descriptor(raw, root):
    calls.append((raw, root))
'''
        sources['stage17_phase_controller_v28.py'] = b'''import stage17_phase_controller_v27
import stage17_archive_overlay_v1
'''
        sources['stage17_operational_cli_v21.py'] = b'''import stage17_operational_cli_v20
import stage17_phase_controller_v28
def main(): return 17
'''
        document = dict(schema_version=admin.SCHEMA, source_revision='a' * 40,
            qualified_worker_unchanged=True, execution_authority=False, files=[])
        for name, raw in sources.items():
            (self.packet / name).write_bytes(raw)
            document['files'].append(dict(name=name, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        raw = json.dumps(document).encode()
        (self.packet / 'manifest.json').write_bytes(raw)
        self.sha = hashlib.sha256(raw).hexdigest()

    def run_case(self, body):
        script = '''import hashlib, importlib.util, json, os, sys, types
from pathlib import Path
from unittest.mock import patch
root = Path(sys.argv[1])
packet = root / 'packet'
spec = importlib.util.spec_from_file_location('stage17_formal_admin_v3', packet / 'stage17_formal_admin_v3.py')
admin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = admin
spec.loader.exec_module(admin)
admin.EVIDENCE = root / 'evidence'
admin.BOOT = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
admin.BOOTSTRAP_SHA = sys.argv[2]
digest = sys.argv[3]
with patch.object(os, 'getuid', return_value=1000), patch.object(os, 'geteuid', return_value=1000):
'''
        script += '\n'.join('    ' + line for line in body.splitlines()) + '\n'
        result = subprocess.run([sys.executable, '-B', '-c', script, str(self.root), self.bootstrap_sha, self.sha],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dependency_order_exact_descriptor_bytes_and_bootstrap_once_on_reentry(self):
        self.run_case('''first = admin.activate_packet(digest)
second = admin.activate_packet(digest)
assert first is second is sys.modules['stage17_operational_cli_v21']
assert sys.modules['validate_suffix'].calls == 1
overlay = sys.modules['stage17_archive_overlay_v1']
assert overlay.calls == [(b'{"software_fixture":true,"source_revision":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}', packet)] * 2
assert first.stage17_phase_controller_v28.stage17_archive_overlay_v1 is overlay
assert all(name in admin._LOADED for name in admin.DEPENDENCIES)
assert 'stage17_archive_inverse_native_v1' not in sys.modules
assert 'stage17_archive_inverse_image_v1' not in sys.modules
''')

    def test_actual_controller_cli_chain_survives_accepted_activation_and_reentry(self):
        # Original-closure qualification is a software-only bootstrap seam;
        # every new controller/CLI/handoff body is the real repository source.
        tools = Path(admin.__file__).parent
        document = json.loads((self.packet / 'manifest.json').read_bytes())
        for name in ('stage17_q16a_handoff_v1', 'stage17_phase_controller_v27',
                     'stage17_operational_cli_v20', 'stage17_phase_controller_v28',
                     'stage17_operational_cli_v21'):
            raw = (tools / (name + '.py')).read_bytes()
            (self.packet / (name + '.py')).write_bytes(raw)
            row = next(row for row in document['files'] if row['name'] == name + '.py')
            row.update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        raw = json.dumps(document).encode()
        (self.packet / 'manifest.json').write_bytes(raw)
        self.sha = hashlib.sha256(raw).hexdigest()
        bootstrap = ('calls = 0\ndef config(path, sha): return {}\ndef modules(config):\n'
            ' global calls\n calls += 1\n import sys\n'
            f' sys.path.insert(0, {str(tools)!r})\n'
            ' import stage17_phase_controller_v26\n'
            ' import stage17_operational_cli_v18, stage17_operational_cli_v19\n'
            ' import stage17_state_journal_v53\n').encode()
        (self.root / 'evidence/offline-suffix-operators-1/validate_suffix.py').write_bytes(bootstrap)
        self.bootstrap_sha = hashlib.sha256(bootstrap).hexdigest()
        self.run_case('''cli = admin.activate_packet(digest)
for _ in range(2):
    cli.activate()
    assert admin.activate_packet(digest) is cli
    scope = cli.formal_functions()
    for name in cli.FUNCTIONS:
        assert scope[name].__globals__['controller'] is sys.modules['stage17_phase_controller_v28']
assert sys.modules['validate_suffix'].calls == 1
assert cli.recovery is sys.modules['stage17_state_journal_v53']
''')

    def test_public_dispatch_configures_descriptor_and_reuses_bootstrap(self):
        self.run_case('''for _ in range(2):
    sys.argv = ['entry', '--packet-manifest-sha256', digest, 'execute-formal']
    assert admin.main() == 17
    assert sys.argv[1:] == ['execute-formal']
assert sys.modules['validate_suffix'].calls == 1
assert sys.modules['stage17_archive_overlay_v1'].calls == [(b'{"software_fixture":true,"source_revision":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}', packet)] * 2
''')

    def test_manifest_bound_descriptor_from_different_revision_rejected_before_overlay(self):
        # The descriptor still matches its manifest hash: revision equality is
        # an additional binding, not another physical-integrity test.
        document = json.loads((self.packet / 'manifest.json').read_bytes())
        raw = json.dumps(dict(source_revision='b' * 40)).encode()
        (self.packet / admin.DESCRIPTOR).write_bytes(raw)
        row = next(row for row in document['files'] if row['name'] == admin.DESCRIPTOR)
        row.update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        raw = json.dumps(document).encode()
        (self.packet / 'manifest.json').write_bytes(raw)
        self.sha = hashlib.sha256(raw).hexdigest()
        self.run_case('''try: admin.activate_packet(digest)
except ValueError as error: assert 'descriptor source revision differs from packet' in str(error)
else: raise AssertionError('different descriptor source revision admitted')
assert sys.modules['stage17_archive_overlay_v1'].calls == []
assert admin._ACTIVE is None
''')

    def test_configuration_receives_verified_bytes_without_path_reread(self):
        self.run_case('''# Change the on-disk locator only after verified_member has
# captured the exact descriptor bytes, at the overlay's genuine API boundary.
admin.activate_packet(digest)
overlay = sys.modules['stage17_archive_overlay_v1']
original = overlay.configure_verified_descriptor
# Exercise the verified handoff directly: replacing overlay functions during
# activate_packet itself must remain forbidden by identity checks.
raw = admin.verified_member(packet, admin.verify_packet(packet, digest), admin.DESCRIPTOR)
(packet / admin.DESCRIPTOR).write_bytes(b'{"unverified":true}')
original(raw, packet)
assert overlay.calls[-1] == (b'{"software_fixture":true,"source_revision":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}', packet)
try: admin.activate_packet(digest)
except ValueError: pass
else: raise AssertionError('changed path accepted on reentry')
''')

    def test_descriptor_changed_between_packet_verification_and_configuration_is_rejected(self):
        self.run_case('''# Mutate after the final stat of the first authenticated read.
# This preserves the loaded administration function/code identities.
reads = [0]
original_stat = Path.stat
def raced_stat(path, *args, **kwargs):
    value = original_stat(path, *args, **kwargs)
    if path == packet / admin.DESCRIPTOR and not kwargs.get('follow_symlinks', True):
        reads[0] += 1
        if reads[0] == 1:
            path.write_bytes(b'{"unverified":true}')
    return value
with patch.object(Path, 'stat', raced_stat):
    try: admin.activate_packet(digest)
    except ValueError as error: assert 'source changed before use' in str(error)
    else: raise AssertionError('unchecked descriptor consumed')
assert sys.modules['stage17_archive_overlay_v1'].calls == []
''')

    def test_reentry_rejects_changed_descriptor_before_dispatch(self):
        self.run_case('''admin.activate_packet(digest)
(packet / admin.DESCRIPTOR).write_bytes(b'{"unverified":true}')
try: admin.activate_packet(digest)
except ValueError as error: assert 'packet source differs' in str(error)
else: raise AssertionError('reentry accepted changed descriptor')
assert len(sys.modules['stage17_archive_overlay_v1'].calls) == 1
''')

    def test_foreign_cached_entrypoint_rejected_even_with_matching_file(self):
        self.run_case('''fake = types.ModuleType('stage17_operational_cli_v21')
fake.__file__ = str(packet / 'stage17_operational_cli_v21.py')
fake.main = lambda: 999
sys.modules[fake.__name__] = fake
try: admin.activate_packet(digest)
except ValueError as error: assert 'unverified project cache' in str(error)
else: raise AssertionError('foreign cached CLI accepted')
assert 'validate_suffix' not in sys.modules
''')

    def test_trusted_reentry_rejects_function_code_and_import_poison(self):
        self.run_case('''cli = admin.activate_packet(digest)
saved = cli.main.__code__
cli.main.__code__ = (lambda: 999).__code__
try: admin.activate_packet(digest)
except ValueError as error: assert 'verified function replaced' in str(error)
else: raise AssertionError('code poison accepted')
cli.main.__code__ = saved
cli.stage17_phase_controller_v28 = types.ModuleType('stage17_phase_controller_v28')
try: admin.activate_packet(digest)
except ValueError as error: assert 'verified import replaced' in str(error)
else: raise AssertionError('import poison accepted')
''')

    def test_entrypoint_code_poison_rejected_before_bootstrap(self):
        self.run_case('''admin.verified_member.__code__ = (lambda *a: b'unchecked').__code__
try: admin.activate_packet(digest)
except ValueError as error: assert 'entrypoint function replaced' in str(error)
else: raise AssertionError('entrypoint poison accepted')
assert 'validate_suffix' not in sys.modules
''')


if __name__ == '__main__':
    unittest.main()
