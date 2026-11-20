"""Scoped EXT007 with actual report arithmetic, real signatures and strict gaps."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_descriptive_freeze_v1 as freeze
import stage17_operational_semantics_v18 as semantics
import stage17_semantic_verifier_v64 as semantic
import author_stage17_policy_v64 as policy_author
from test_stage17_descriptive_freeze_v1 import PATHS,binding


def save(p,value): p.write_bytes(freeze.canonical(value)); return binding(p)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.p = Path(self.tmp.name)
        self.sources = {k:binding(p) for k,p in PATHS.items()}
        self.predecessors = [dict(input_id=f'S17-EXT-{i:03d}',resolution_id=f'SOFTWARE-QUALIFICATION-FIXTURE-{i}',sha256=str(i)*64) for i in range(1,7)]
        actual = json.loads((ROOT/semantics.ACCEPTED_PATH).read_bytes())
        source,worker,inventory = actual['qualified_release']
        journal = save(self.p/'historical-journal.json',dict(resolution_records=[dict(sha256=p['sha256']) for p in self.predecessors]))
        packet = save(self.p/'packet.json',dict(administrative_source_revision=actual['publisher_source_revision']))
        code = {n:binding(ROOT/'tools'/n) for n in semantics.CODE_MEMBERS}
        proof = dict(schema_version='cpu-prefetch-stage17-descriptive-freeze-provenance/1',
            status='SIGNED_LINEAGE_CUSTODY_AND_REPORTS_VERIFIED',stand_id='CPU-PREFETCH-V5',boot_id=actual['boot_id'],
            source_records=self.sources,predecessor_resolutions=self.predecessors,qualified_source_revision=source,
            qualified_worker=dict(sha256=worker),qualified_inventory=dict(sha256=inventory),historical_journal=journal,
            archive_capture_count=94,q16c_completion=dict(report_hashes_verified=180,new_process_receipts_verified=94,raw_decoding_repeated=False),
            administrative_packet=packet,source_code_bindings=code,execution_authority=False,phase18_authority=False)
        proof_binding = save(self.p/'provenance.json',proof)
        self.value = freeze.build(record_id='SOFTWARE-FIXTURE-OF-ACTUAL-REPORTS',created_at_utc='2026-11-20T04:00:00Z',
            source_records=self.sources,provenance_record=proof_binding,predecessor_resolutions=self.predecessors)
        self.record = self.p/'freeze.json'; record_binding = save(self.record,self.value)
        self.key = self.p/'software-key'
        subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(self.key)],check=True)
        allowed = self.p/'allowed'; allowed.write_text('software-owner '+self.key.with_suffix('.pub').read_text())
        trust = dict(measurements=dict(principal='software-owner',sshsig_namespace='stage17-owner-acceptance',
            allowed_signers_path=str(allowed),allowed_signers_size_bytes=allowed.stat().st_size,
            allowed_signers_sha256=hashlib.sha256(allowed.read_bytes()).hexdigest()))
        subprocess.run(['ssh-keygen','-Y','sign','-f',str(self.key),'-n','stage17-owner-acceptance',str(self.record)],capture_output=True,check=True)
        self.resolutions = {p['input_id']:types.SimpleNamespace(resolution_id=p['resolution_id'],sha256=p['sha256'],
            semantic_context={}) for p in self.predecessors}
        for ordinal,resolution in enumerate(self.resolutions.values()):
            path = self.p/f'qualification-{ordinal}.json'; path.write_text('{}')
            resolution.path = path
        for key in ('S17-EXT-002','S17-EXT-004'): self.resolutions[key].semantic_context = dict(stand_id='CPU-PREFETCH-V5')
        self.resolutions['S17-EXT-003'].semantic_context = dict(trust=trust)
        self.resolutions['S17-EXT-006'].semantic_context = dict(source_revision=source,release_artifact_sha256=worker,inventory_sha256=inventory)
        accepted = dict(actual,freeze=[record_binding['size_bytes'],record_binding['sha256']],
            provenance=[proof_binding['size_bytes'],proof_binding['sha256']],historical_journal=[journal['size_bytes'],journal['sha256']])
        paths = [freeze.SCHEMA_PATH,semantics.MANIFEST_SCHEMA,'config/schemas/stage17-operational-artifact-v5.schema.json',
                 *('tools/'+n for n in semantics.CODE_MEMBERS)]
        self.pinned = {p:(ROOT/p).read_bytes() for p in paths}; self.pinned[semantics.ACCEPTED_PATH] = freeze.canonical(accepted)
        schema = binding(ROOT/freeze.SCHEMA_PATH); schema['path'] = freeze.SCHEMA_PATH
        signature = binding(Path(str(self.record)+'.sig'))
        self.manifest = dict(schema_version='cpu-prefetch-stage17-operational-input-manifest/5',
            manifest_id='SOFTWARE-DESCRIPTIVE-MANIFEST',input_id='S17-EXT-007',stand_id='CPU-PREFETCH-V5',
            predecessor_resolutions=self.predecessors,synthetic_test_only=False,phase18_authority=False,
            artifacts=[dict(artifact_id='SOFTWARE-DATA-RECORD',role='CALIBRATION_FREEZE',media_type='application/json',
                locator=self.record.name,size_bytes=record_binding['size_bytes'],sha256=record_binding['sha256'],
                schema_identity=freeze.SCHEMA,schema_binding=schema,lineage=[]),
                dict(artifact_id='SOFTWARE-DATA-SIGNATURE',role=semantics.SIGNATURE_ROLE,media_type='application/sshsig',
                    locator=Path(signature['path']).name,size_bytes=signature['size_bytes'],sha256=signature['sha256'],schema_identity=None,
                    schema_binding=None,lineage=[dict(id='SOFTWARE-DATA-RECORD',sha256=record_binding['sha256'])])])

    def verify(self,manifest=None):
        path = self.p/'manifest.json'; save(path,self.manifest if manifest is None else manifest)
        return semantics.verify_manifest_v18(repository_root=ROOT,manifest_path=path,admitted_resolutions=self.resolutions,
            expected_input_id='S17-EXT-007',allow_synthetic=False,pinned_repository_bytes=self.pinned)

    def test_real_signature_and_actual_report_arithmetic_admit_only_scoped_data(self):
        context = self.verify()
        self.assertTrue(context['data_provenance_accepted'])
        self.assertEqual(context['calibration_scope'],freeze.SCOPE)
        self.assertEqual(context['calibration_freeze']['original_report_count'],1008)
        self.assertFalse(context['legacy_statistical_freeze_satisfied'])
        self.assertFalse(context['pilot_execution_eligible'])
        self.assertFalse(context['phase18_authority'])

    def test_changed_qualified_release_or_predecessor_lineage_is_rejected(self):
        self.resolutions['S17-EXT-006'].semantic_context['source_revision'] = '0'*40
        with self.assertRaises(ValueError): self.verify()
        self.resolutions['S17-EXT-006'].semantic_context['source_revision'] = json.loads(self.pinned[semantics.ACCEPTED_PATH])['qualified_release'][0]
        bad = copy.deepcopy(self.manifest); bad['predecessor_resolutions'][0]['sha256'] = 'f'*64
        with self.assertRaises(ValueError): self.verify(bad)

    def test_signature_source_proof_and_schema_pins_are_mandatory(self):
        signature = Path(str(self.record)+'.sig'); raw = signature.read_bytes(); signature.write_bytes(raw.replace(b'A',b'B',1))
        # Update only the physical signature hash: real crypto must still reject.
        bad = copy.deepcopy(self.manifest); bad['artifacts'][1]['sha256'] = binding(signature)['sha256']
        with self.assertRaises(ValueError): self.verify(bad)
        signature.write_bytes(raw)
        table = self.pinned.pop(semantics.ACCEPTED_PATH)
        with self.assertRaises(ValueError): self.verify()
        self.pinned[semantics.ACCEPTED_PATH] = table
        self.pinned.pop('tools/prepare_stage17_descriptive_freeze_v1.py')
        with self.assertRaises(ValueError): self.verify()

    def test_extra_roles_wrong_input_or_signature_lineage_are_rejected(self):
        for change in ('extra','input','signature_lineage','synthetic'):
            bad = copy.deepcopy(self.manifest)
            if change == 'extra': bad['artifacts'].append(copy.deepcopy(bad['artifacts'][0]))
            elif change == 'input': bad['input_id'] = 'S17-EXT-008'
            elif change == 'signature_lineage': bad['artifacts'][1]['lineage'][0]['sha256'] = 'f'*64
            else: bad['synthetic_test_only'] = True
            with self.subTest(change=change),self.assertRaises(ValueError): self.verify(bad)

    def test_legacy_manifest_dispatch_remains_the_original_verifier(self):
        path = self.p/'legacy.json'; save(path,dict(schema_version='cpu-prefetch-stage17-operational-input-manifest/4'))
        with patch.object(semantics.predecessor,'verify_manifest_v17',return_value={'legacy':'unchanged'}) as prior:
            result = semantics.verify_manifest_v18(repository_root=ROOT,manifest_path=path,admitted_resolutions={},
                expected_input_id='S17-EXT-007',allow_synthetic=False,pinned_repository_bytes={})
            self.assertEqual(result,{'legacy':'unchanged'}); prior.assert_called_once()

    def test_scoped_data_cannot_authorize_pilot_inputs(self):
        admitted = {'S17-EXT-007':types.SimpleNamespace(semantic_context=dict(calibration_scope=freeze.SCOPE))}
        for key in ('S17-EXT-008','S17-EXT-009','S17-EXT-010'):
            with self.subTest(key=key),self.assertRaises(semantic.SemanticAdmissionError):
                semantic.verify_input(input_id=key,admitted_resolutions=admitted)


class PolicyTests(unittest.TestCase):
    def test_new_admission_entry_and_helpers_have_no_unresolved_global_names(self):
        import builtins,symtable
        names = ('admit_stage17_descriptive_freeze_v1','stage17_operational_semantics_v18',
                 'stage17_semantic_verifier_v64','stage17_state_journal_v61','author_stage17_policy_v64')
        for name in names:
            table = symtable.symtable((ROOT/'tools'/(name+'.py')).read_text(),name,'exec')
            defined = {s.get_name() for s in table.get_symbols() if s.is_assigned() or s.is_imported()}
            defined |= set(dir(builtins))|{'__file__','__name__','__package__'}
            missing = set()
            def walk(t):
                for s in t.get_symbols():
                    if s.is_referenced() and s.is_global() and s.get_name() not in defined: missing.add(s.get_name())
                for child in t.get_children(): walk(child)
            walk(table)
            with self.subTest(name=name): self.assertEqual(missing,set())

    def test_complete_policy_render_keeps_all_old_bindings_and_native_sources(self):
        new = policy_author.render(ROOT)
        old = json.loads((ROOT/semantic.predecessor.POLICY_PATH).read_bytes())
        for group in ('bindings','runtime_closure'):
            for key,value in old[group].items(): self.assertEqual(new[group][key],value)
        self.assertEqual(new['policy_version'],'64')
        self.assertTrue(all(p['verifier_version']=='64' for p in new['entries']))
        self.assertEqual(len(new['entries']),10)

    def test_journal_scope_is_private_and_does_not_rebind_previous_runtimes(self):
        import stage17_state_journal_v61 as current
        import stage17_state_journal_v60 as prior
        original = current.core.semantic
        new = current.activate(); old = prior.activate()
        self.assertIs(new._resolutions.__globals__['semantic'],semantic)
        self.assertIs(old._resolutions.__globals__['semantic'],semantic.predecessor)
        self.assertIs(current.core.semantic,original)

    def test_actual_append_cli_uses_the_new_private_journal_in_both_paths(self):
        import admit_stage17_descriptive_freeze_v1 as entry
        view = entry.cloning._clone_module(entry.original_cli,dict(journal_runtime=entry.journal))
        self.assertIs(view.append_resolution.__globals__['journal_runtime'],entry.journal)
        self.assertIs(view.validate_journal.__globals__['journal_runtime'],entry.journal)
        self.assertIs(view.append_resolution.__globals__['validate_journal'],view.validate_journal)


if __name__ == '__main__': unittest.main()
