"""Independent D231 policy/entry-point checks; no authority or stand access.

Draft checked-in policies may be stale. Render once in memory, then use a
private copy of their source-bound closure and fresh nested preflight bytes.
"""
import copy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import author_stage17_policy_v58 as author
import stage17_semantic_verifier_v58 as semantic
import stage17_read_only_preflight_semantic_verifier_v32 as preflight
import stage17_state_journal_v52 as journal
import stage17_state_journal as initial_journal
import stage17_pilot_candidate_artifact_v12 as release
import test_stage17_archive_bundle_profile_v1 as profile_fixture


class QualifiedArchiveContext(unittest.TestCase):
    """Real receipt/profile/runtime byte checks; synthetic bundle-verifier seam.

    No executable is run or qualified by this software-only fixture.
    """

    def setUp(self):
        fixture = profile_fixture.ProfileTests('test_exact_bytes_and_explicit_relocated_runtime')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        bundle = fixture.bundle
        members = ('BUNDLE_MANIFEST.json', 'SHA256SUMS', 'SBOM.spdx.json',
                   'BUNDLE_INVENTORY.json', 'release/bin/cpu_prefetch_runner',
                   'validators/verify_stand_bundle.py')
        for member in members:
            path = bundle / member
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('synthetic nonexecuted ' + member).encode())
        def size(member):return (bundle / member).stat().st_size
        def sha(member):return hashlib.sha256((bundle / member).read_bytes()).hexdigest()
        worker = 'release/bin/cpu_prefetch_runner'
        verifier = 'validators/verify_stand_bundle.py'
        context = release.ExtractedReleaseContext(
            bundle_root=bundle, manifest_size_bytes=size('BUNDLE_MANIFEST.json'),
            manifest_sha256=sha('BUNDLE_MANIFEST.json'), source_revision='a'*40,
            worker_path=bundle / worker, worker_member_path=worker,
            worker_size_bytes=size(worker), worker_sha256=sha(worker),
            worker_role='STAGE17_FIXED_ACTION_WORKER',
            runtime_profile='STAGE17-FIXED-ACTION-WORKER-v4',
            supported_actions=release.SUPPORTED_ACTIONS,
            bundle_profile='STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22', synthetic_test_only=True,
            sha256s_sha256=sha('SHA256SUMS'), sbom_sha256=sha('SBOM.spdx.json'),
            inventory_sha256=sha('BUNDLE_INVENTORY.json'),
            full_verifier_size_bytes=size(verifier), full_verifier_sha256=sha(verifier))
        bundle_check = patch.object(release, 'verify_extracted_bundle_v12', return_value=context)
        bundle_check.start()
        self.addCleanup(bundle_check.stop)
        self.receipt = release.build_extracted_release_receipt_v12(
            bundle_root=bundle, receipt_id='SYNTHETIC-ARCHIVE-RECEIPT',
            archive_runtime_root=fixture.runtime)
        self.qualified = release.ArchiveExtractedReleaseContext(
            **asdict(context), archive_runtime_provenance=copy.deepcopy(self.receipt))
        self.ext006 = {name:getattr(context, name) for name in (
            'bundle_profile', 'manifest_sha256', 'manifest_size_bytes', 'source_revision',
            'sha256s_sha256', 'sbom_sha256', 'inventory_sha256')}

    def verify(self, *, qualified=None, ext006=None):
        return semantic._qualified_archive_context(
            self.ext006 if ext006 is None else ext006, root=ROOT,
            admitted_resolutions={'S17-EXT-003':SimpleNamespace(semantic_context={
                'release':self.qualified if qualified is None else qualified})})

    def test_actual_profile_and_runtime_bytes_bound_to_both_releases(self):
        self.assertEqual(self.verify(), {
            'archive_profile_binding':profile_fixture.profile.binding(
                self.fixture.bundle, profile_fixture.profile.PROFILE_PATH),
            'archive_bundle_root':str(self.fixture.bundle),
            'archive_runtime_root':str(self.fixture.runtime)})

    def test_missing_original_ext003_provenance_rejects(self):
        for value in (None, False, []):
            with self.subTest(value=value), self.assertRaisesRegex(
                    semantic.SemanticAdmissionError, 'original archive-runtime receipt'):
                self.verify(qualified=replace(self.qualified, archive_runtime_provenance=value))

    def test_each_ext006_identity_missing_or_changed_rejects(self):
        for name, value in self.ext006.items():
            for missing in (False, True):
                changed = dict(self.ext006)
                if missing:del changed[name]
                else:changed[name] = value + 1 if isinstance(value, int) else value + '-changed'
                with self.subTest(name=name, missing=missing), self.assertRaisesRegex(
                        semantic.SemanticAdmissionError, 'differs from EXT003'):
                    self.verify(ext006=changed)

    def test_original_receipt_missing_or_changed_bindings_reject(self):
        for name in ('archive_profile_binding', 'archive_bundle_root', 'archive_runtime_root'):
            for missing in (False, True):
                receipt = copy.deepcopy(self.receipt)
                if missing:del receipt[name]
                elif name == 'archive_profile_binding':receipt[name]['sha256'] = '0'*64
                else:receipt[name] += '-changed'
                with self.subTest(name=name, missing=missing), self.assertRaises(
                        semantic.SemanticAdmissionError):
                    self.verify(qualified=replace(self.qualified, archive_runtime_provenance=receipt))

    def test_changed_qualified_worker_identity_rejects(self):
        with self.assertRaisesRegex(semantic.SemanticAdmissionError, 'release identity mismatch'):
            self.verify(qualified=replace(self.qualified, worker_sha256='0'*64))

    def test_changed_actual_runtime_or_profile_bytes_reject(self):
        for path in (self.fixture.runtime / profile_fixture.profile.PYTHON_PATH,
                     self.fixture.bundle / profile_fixture.profile.PROFILE_PATH):
            original = path.read_bytes()
            try:
                path.write_bytes(original + b'changed')
                with self.subTest(path=path), self.assertRaises(semantic.SemanticAdmissionError):
                    self.verify()
            finally:path.write_bytes(original)

    def test_direct_author_import_in_fresh_interpreter(self):
        result = subprocess.run([sys.executable, '-B', '-c',
            'import sys; sys.path.insert(0,sys.argv[1]); import author_stage17_policy_v58; '
            'print("DIRECT_AUTHOR_IMPORT_PASS")', str(ROOT / 'tools')],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), 'DIRECT_AUTHOR_IMPORT_PASS')


class FormalPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='formal-policy-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.policy = author.render(ROOT)
        cls.nested = author.render_preflight(ROOT)
        paths = {item['path'] for group in ('bindings','runtime_closure')
                 for item in cls.policy[group].values()}
        def referenced_files(value):
            if isinstance(value,dict):
                path = value.get('path')
                if isinstance(path,str) and not Path(path).is_absolute() and '..' not in Path(path).parts:
                    if (ROOT / path).is_file():paths.add(path)
                for item in value.values():referenced_files(item)
            elif isinstance(value,list):
                for item in value:referenced_files(item)
        referenced_files(cls.nested)
        paths.update(initial_journal.LEGACY_TEMPLATE_PATHS.values())
        for path in (ROOT / 'config/stage17').glob('*.json'):
            referenced_files(json.loads(path.read_bytes()))
        # Include the unchanged genesis/config tree for a real journal check.
        shutil.copytree(ROOT / 'config', cls.root / 'config')
        for relative in paths:
            destination = cls.root / relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT / relative,destination)
        (cls.root / preflight.POLICY_PATH).write_bytes(author._BASE.canonical(cls.nested))
        # Equivalent to rendering operational58 after writing preflight32, while
        # avoiding another full predecessor rendering and never writing ROOT.
        for item in cls.policy['bindings'].values():
            if item['path'] == preflight.POLICY_PATH:
                item.update(author._BASE.binding(cls.root,preflight.POLICY_PATH))
        (cls.root / semantic.POLICY_PATH).write_bytes(author._BASE.canonical(cls.policy))
        cls.policy_args = {key:cls.policy[key] for key in ('graph_sha256','catalog_sha256',
            'genesis_record_sha256','resolution_schema_sha256')}
        cls.preflight_args = {key:cls.nested['predecessor'][key] for key in (
            'graph_sha256','catalog_sha256','genesis_file_sha256','genesis_record_sha256','resolution_schema_sha256')}

    def verify(self, document):
        semantic.verify_policy_v58(root=self.root,policy=document,**self.policy_args)

    def test_fresh_source_hashes_and_both_policies_verify(self):
        for group in ('bindings','runtime_closure'):
            for binding in self.policy[group].values():
                payload = (self.root / binding['path']).read_bytes()
                self.assertEqual(len(payload),binding['size_bytes'],binding['path'])
                self.assertEqual(hashlib.sha256(payload).hexdigest(),binding['sha256'],binding['path'])
        self.verify(self.policy)
        preflight.verify_policy_v32(root=self.root,policy=self.nested,**self.preflight_args)
        closure = {row['path'] for row in self.policy['runtime_closure'].values()}
        for name in ('stage17_operational_cli_v18','stage17_phase_controller_v25','stage17_fixed_action_executor_v10',
                     'stage17_output_registry_v11','stage17_formal_calibration_v1','stage17_formal_service_capture_validation_v1',
                     'stage17_q16c_schedule_provenance_v1','stage17_q15_session_controller_v20',
                     'stage17_read_only_preflight_executor_v32','stage17_state_journal_v52'):
            self.assertIn('tools/'+name+'.py',closure)

    def test_missing_formal_runtime_and_changed_hash_reject(self):
        changed = copy.deepcopy(self.policy)
        changed['runtime_closure'].pop('stage17_formal_service_capture_validation_v1')
        with self.assertRaises(semantic.SemanticAdmissionError):self.verify(changed)
        changed = copy.deepcopy(self.policy)
        changed['runtime_closure']['stage17_fixed_action_executor_v10']['sha256'] = '0'*64
        with self.assertRaises(semantic.SemanticAdmissionError):self.verify(changed)

    def test_missing_scientific_method_bindings_reject(self):
        for path in ('docs/decisions/0211-stage17-q16b-completion-interval.md',
                     'docs/decisions/0212-stage17-q16a-demand-window.md'):
            with self.subTest(path=path):
                changed = copy.deepcopy(self.policy)
                keys = [key for key,row in changed['bindings'].items() if row['path']==path]
                self.assertTrue(keys,'renderer omitted required method '+path)
                for key in keys:del changed['bindings'][key]
                with self.assertRaises(semantic.SemanticAdmissionError):self.verify(changed)

    def test_missing_formal_schema_and_old_verifier_reject(self):
        changed = copy.deepcopy(self.policy)
        path = 'config/schemas/stage17-formal-scheduled-plan-v1.schema.json'
        changed['bindings'] = {key:row for key,row in changed['bindings'].items() if row['path']!=path}
        with self.assertRaises(semantic.SemanticAdmissionError):self.verify(changed)
        changed = copy.deepcopy(self.policy)
        changed['entries'][0]['verifier_version'] = '57'
        with self.assertRaises(semantic.SemanticAdmissionError):self.verify(changed)

    def test_missing_native_formal_source_binding_rejects(self):
        changed = copy.deepcopy(self.policy)
        path = 'src/calibration/native_formal_scheduled_capture.cpp'
        keys = [key for key,row in changed['bindings'].items() if row['path']==path]
        self.assertTrue(keys,'renderer omitted native formal source')
        for key in keys:del changed['bindings'][key]
        with self.assertRaises(semantic.SemanticAdmissionError):self.verify(changed)

    def test_missing_owner_acceptance_binding_rejects(self):
        changed = copy.deepcopy(self.policy)
        paths = [path for path in semantic.ACCEPTANCE_BINDINGS if path.endswith('/owner-acceptance.json')]
        self.assertEqual(len(paths),2)
        removed = paths[0]
        keys = [key for key,row in changed['bindings'].items() if row['path']==removed]
        self.assertTrue(keys,'renderer omitted owner acceptance')
        for key in keys:del changed['bindings'][key]
        with self.assertRaises(semantic.SemanticAdmissionError):self.verify(changed)

    def test_missing_d233_storage_owner_acceptance_binding_rejects(self):
        changed = copy.deepcopy(self.policy)
        path = 'docs/evidence/stage17/FORMAL-STORAGE-D233-PROPOSAL-20261103-01/owner-acceptance.json'
        keys = [key for key,row in changed['bindings'].items() if row['path']==path]
        self.assertTrue(keys, 'renderer omitted D233 storage owner acceptance')
        for key in keys:del changed['bindings'][key]
        with self.assertRaises(semantic.SemanticAdmissionError):self.verify(changed)

    def test_preflight_old_journal_and_executor_bindings_reject(self):
        for key,path in (('state_journal','tools/stage17_state_journal_v51.py'),
                         ('executor','tools/stage17_read_only_preflight_executor_v31.py')):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.nested)
                changed['implementations'][key] = author._BASE.binding(self.root,path)
                with self.assertRaises(preflight.SemanticAdmissionError):
                    preflight.verify_policy_v32(root=self.root,policy=changed,**self.preflight_args)

    def test_real_genesis_is_prepared_without_execution_readiness(self):
        validation = journal.checked_in_status(self.root)
        self.assertEqual(validation.current_state,'PREPARED')
        self.assertFalse(validation.pilot_ready)
        self.assertEqual(validation.resolution_count,0)
        self.assertEqual(validation.transition_count,0)
        self.assertFalse(validation.resolved_input_ids)
        self.assertEqual(len(validation.missing_input_ids),10)

    def test_fresh_import_orders_dispatch_current_entries_before_any_action(self):
        code = r'''
import importlib,json,pathlib,sys,types
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(sys.argv[1])/'tools'))
for name in json.loads(sys.argv[2]):importlib.import_module(name)
import stage17_operational_cli_v18 as cli
import stage17_read_only_preflight_executor_v32 as executor
import stage17_q15_session_controller_v20 as session
import stage17_state_journal_v12 as dispatch
import stage17_read_only_preflight_executor_v31 as old_executor
import stage17_q15_session_controller_v19 as old_session
old_executor.activate();old_session.activate()
cli.activate()
assert str(cli.base.journal_runtime.SEMANTIC_POLICY_PATH).endswith('-v58.json')
assert cli.base.controller.__name__=='stage17_phase_controller_v26'
old_executor.activate()
def observe(**arguments):
    assert executor.owner.EXECUTOR_ID.endswith('-v32')
    assert executor.owner.current_journal.__name__=='stage17_state_journal_v52'
    assert executor.owner.runtime_identity_paths()['state_journal'].endswith('stage17_state_journal_v52.py')
    assert dispatch.semantic.__name__=='stage17_semantic_verifier_v58'
    return types.SimpleNamespace(action_ready=False,action_context=None)
with patch.object(executor.owner,'_prospective_validation',side_effect=observe) as seen, \
     patch.object(executor.owner,'_prepare_action',side_effect=AssertionError('must not prepare')):
    try:executor.execute_once(repository_root=pathlib.Path(sys.argv[1]),latest_journal=pathlib.Path('unused'),journal_directory=pathlib.Path('unused'))
    except executor.ActionExecutionError as error:assert 'not prospectively action-ready' in str(error)
    else:raise AssertionError('blocked preflight executed')
    assert seen.call_count==1
old_session.activate()
try:session.execute_session(q15_r=types.SimpleNamespace(authorization={'action_id':'Q16a'}),wait_for_q15_w=lambda:None)
except session.execution_body.Q15SessionError as error:assert 'requires Q15-R' in str(error)
else:raise AssertionError('wrong session action accepted')
assert session.execution_body.phase_controller.__name__=='stage17_phase_controller_v25'
assert session.initial_body.phase_controller.__name__=='stage17_phase_controller_v25'
assert dispatch.semantic.__name__=='stage17_semantic_verifier_v58'
print('CURRENT_DISPATCH_NO_EXECUTION')
'''
        orders = (
            ['stage17_operational_cli_v17','stage17_read_only_preflight_executor_v31','stage17_q15_session_controller_v19'],
            ['stage17_operational_cli_v18','stage17_q15_session_controller_v20','stage17_read_only_preflight_executor_v30','stage17_operational_cli_v16'],
            ['stage17_read_only_preflight_executor_v32','stage17_operational_cli_v15','stage17_state_journal_v50','stage17_q15_session_controller_v18'],
        )
        for order in orders:
            with self.subTest(order=order):
                result = subprocess.run([sys.executable,'-B','-c',code,str(self.root),json.dumps(order)],
                    capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(result.stdout.strip(),'CURRENT_DISPATCH_NO_EXECUTION')


if __name__ == '__main__':unittest.main()
