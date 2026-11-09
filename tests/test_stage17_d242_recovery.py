"""D242 administrative software checks: no measured worker or stand invocation."""
import ast
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import stage17_state_journal_v53 as recovery
import stage17_d242_admin_packet as packet

EVIDENCE = ROOT/'docs/evidence/stage17/Q16A-PREFIX-COMPLETE-E25-20261109-01'


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='d242-software-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.expected = dict(policy_id=recovery.POLICY, boot_id=recovery.BOOT,
            qualified_source_revision=recovery.SOURCE, qualified_worker_sha256=recovery.WORKER,
            automatic_retries=0, one_use=True, execution_authority=False,
            target={'sequence_number':3, 'to_state':'READY_FOR_STAGE17_PHASE_AUTHORIZATION'},
            administrative_manifest={'sha256':'a'*64}, evidence_bindings={'sha256':'b'*64},
            predecessor_resolutions=[{'sha256':'c'*64}])
        self.authority = dict(self.expected, issued_at_utc='2026-11-09T10:00:00Z',
                              expires_at_utc='2026-11-09T10:30:00Z')

    def test_time_window_boundaries_and_historical_consumption(self):
        for time in ('2026-11-09T10:00:00Z', '2026-11-09T10:29:59.999999Z'):
            recovery.validate_authority(self.authority, self.expected, time)
        for time in ('2026-11-09T09:59:59Z', '2026-11-09T10:30:00Z', '2026-11-10T10:00:00Z'):
            with self.subTest(time=time), self.assertRaises(recovery.JournalError):
                recovery.validate_authority(self.authority, self.expected, time)
        # Historical validation deliberately uses the retained consumption time,
        # while author/commit independently require current UTC inside the window.
        with patch.object(recovery.support, '_now', return_value='2027-01-01T00:00:00Z'):
            recovery.validate_authority(self.authority, self.expected, '2026-11-09T10:01:00Z')

    def test_closed_scope_and_strict_types(self):
        mutants = {'policy_id':'unrelated', 'boot_id':'other', 'qualified_worker_sha256':'0'*64,
            'qualified_source_revision':'0'*40, 'automatic_retries':False, 'one_use':1,
            'execution_authority':True, 'target':{'sequence_number':4},
            'administrative_manifest':{}, 'evidence_bindings':{}, 'predecessor_resolutions':[]}
        for field, value in mutants.items():
            with self.subTest(field=field), self.assertRaises(recovery.JournalError):
                recovery.validate_authority(dict(self.authority, **{field:value}), self.expected, '2026-11-09T10:01:00Z')
        for change in ({'new_scope':True}, {'expires_at_utc':'2026-11-09T11:00:00Z'}):
            with self.assertRaises(recovery.JournalError):
                recovery.validate_authority(dict(self.authority, **change), self.expected, '2026-11-09T10:01:00Z')

    def test_real_incident_hashes_and_every_missing_or_changed_input(self):
        evidence = self.root/'evidence'
        shutil.copytree(EVIDENCE/'qualification', evidence)
        prefix = self.root/'prefix.json'
        shutil.copyfile(EVIDENCE/'accepted-prefix-manifest.json', prefix)
        with patch.object(recovery, 'EVIDENCE', evidence), patch.object(recovery, 'PREFIX_PATH', prefix):
            bindings, _ = recovery.incident()
            self.assertEqual(len(bindings), 7)
            paths = [evidence/name for name, _ in recovery.FIXED.values()]+[prefix]
            for path in paths:
                raw = path.read_bytes()
                for replacement in (b'{}\n', None):
                    with self.subTest(path=path.name, replacement=replacement):
                        if replacement is None: path.unlink()
                        else: path.write_bytes(replacement)
                        with self.assertRaises((recovery.JournalError, FileNotFoundError)):
                            recovery.incident()
                        path.write_bytes(raw)

    def test_exclusive_consumption_survives_replay_and_symlink(self):
        path = self.root/'consumption.json'
        recovery.write_exclusive(path, b'first\n')
        with self.assertRaises(FileExistsError): recovery.write_exclusive(path, b'second\n')
        self.assertEqual(path.read_bytes(), b'first\n')
        alias = self.root/'alias'; alias.symlink_to(path)
        with self.assertRaises(FileExistsError): recovery.write_exclusive(alias, b'second\n')
        with self.assertRaises(recovery.JournalError): recovery.read(alias)

    def test_bound_bytes_cannot_change(self):
        path = self.root/'input'; path.write_bytes(b'original')
        binding = recovery.binding(path)
        self.assertEqual(recovery.bound(binding), b'original')
        path.write_bytes(b'changed!')
        with self.assertRaises(recovery.JournalError): recovery.bound(binding)

    def test_original_candidate_is_not_rewritten(self):
        failed = json.loads((EVIDENCE/'qualification/records/transition-003.json').read_bytes())
        baseline = json.loads((EVIDENCE/'qualification/journal/stage17-state-journal-000008.json').read_bytes())
        original_failed, original_baseline = copy.deepcopy(failed), copy.deepcopy(baseline)
        transition = recovery.make_transition(failed, {'a':1}, {'s':2}, '2026-11-09T10:01:00Z')
        reference = dict(path=recovery.TRANSITION_NAME, sha256=recovery.sha(recovery.canonical(transition)))
        result = recovery.make_journal(baseline, reference)
        self.assertEqual(failed, original_failed); self.assertEqual(baseline, original_baseline)
        self.assertEqual(result['transition_records'][:-1], baseline['transition_records'])
        self.assertEqual(result['resolution_records'], baseline['resolution_records'])
        self.assertEqual(result['previous_journal'], dict(path=recovery.BASE_NAME, sha256=recovery.BASE_SHA))
        self.assertNotEqual(reference['path'], 'records/transition-003.json')
        with self.assertRaises(recovery.JournalError): recovery.make_journal(result, reference)

    def test_unrelated_and_original_failed_edges_delegate_unchanged(self):
        for refs in ([], [{'path':'a'}, {'path':'b'}], [{'path':'a'}, {'path':'b'}, {'path':'records/transition-003.json'}]):
            with patch.object(recovery.core, '_transitions', return_value='ORIGINAL') as original:
                self.assertEqual(recovery.transitions(references=refs), 'ORIGINAL')
                original.assert_called_once_with(references=refs)
        with patch.object(recovery, 'ORIGINAL_VALIDATE', return_value='ORIGINAL') as original:
            self.assertEqual(recovery.validate_operational_journal(evidence_root=self.root), 'ORIGINAL')
            original.assert_called_once()

    def test_live_boot_and_used_namespace_stop_before_validation(self):
        transaction = self.root/'transaction'; transaction.mkdir()
        with patch.object(recovery.os, 'geteuid', return_value=1000), patch.object(recovery, 'EVIDENCE', self.root), \
             patch.object(recovery, 'TRANSACTION', transaction), patch.object(recovery, 'ORIGINAL_VALIDATE') as original:
            with patch.object(Path, 'read_text', return_value='other-boot'):
                with self.assertRaisesRegex(recovery.JournalError, 'boot changed'): recovery.original_validation(None, None)
            (transaction/'consumption.json').write_text('{}')
            with patch.object(Path, 'read_text', return_value=recovery.BOOT):
                with self.assertRaisesRegex(recovery.JournalError, 'consumed or partial'): recovery.original_validation(None, None)
            original.assert_not_called()

    def test_duplicate_json_and_nonfinite_rejected(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with self.assertRaises(recovery.JournalError): recovery.parse(raw)

    def test_real_signature_verifies_only_exact_payload_and_signer(self):
        key = self.root/'software-key'
        subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)], check=True, capture_output=True)
        allowed = self.root/'allowed'; allowed.write_text('software-owner '+key.with_suffix('.pub').read_text())
        trust = dict(measurements=dict(principal='software-owner', sshsig_namespace='stage17-owner-acceptance',
            allowed_signers_path=str(allowed), allowed_signers_size_bytes=allowed.stat().st_size,
            allowed_signers_sha256=recovery.sha(allowed.read_bytes())))
        path = self.root/'authority.json'; raw = recovery.canonical(self.authority); path.write_bytes(raw)
        subprocess.run(['ssh-keygen','-Y','sign','-f',str(key),'-n','stage17-owner-acceptance',str(path)], check=True, capture_output=True)
        signature = Path(str(path)+'.sig')
        recovery.support._verify_signature(raw, signature, trust)
        with self.assertRaises(recovery.support.ControllerError): recovery.support._verify_signature(raw+b' ', signature, trust)
        trust['measurements']['principal'] = 'untrusted'
        with self.assertRaises(recovery.support.ControllerError): recovery.support._verify_signature(raw, signature, trust)

    def test_operator_adapter_only_adds_bootstrap_and_replaces_cli_path(self):
        original = ROOT/'docs/evidence/stage17/Q16A-PREFIX-VALIDATION-E25-20261108-01/operators'
        for name in packet.OPERATORS:
            raw = (original/name).read_bytes()
            adapted = packet.adapt(name, raw).decode()
            recovered = adapted.replace(packet.BOOTSTRAP, '', 1)
            if name == 'formal_launch.py':
                recovered = recovered.replace("str(Path(__file__).resolve().parent/'stage17_operational_cli_v19.py')",
                                              "str(Path(c['repository_root'])/'tools/stage17_operational_cli_v18.py')")
            self.assertEqual(recovered.encode(), raw)
            ast.parse(adapted)

    def test_complete_transition_and_receipt_with_real_signature(self):
        evidence = self.root/'evidence'; shutil.copytree(EVIDENCE/'qualification', evidence)
        transaction = self.root/'transaction'; transaction.mkdir()
        repository = self.root/'repository'; repository.mkdir()
        failed = json.loads((evidence/'records/transition-003.json').read_bytes())
        baseline = json.loads((evidence/recovery.BASE_NAME).read_bytes())
        key = self.root/'key'
        subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)], check=True, capture_output=True)
        allowed = self.root/'allowed'; allowed.write_text('software-owner '+key.with_suffix('.pub').read_text())
        trust = dict(measurements=dict(principal='software-owner', sshsig_namespace='stage17-owner-acceptance',
            allowed_signers_path=str(allowed), allowed_signers_size_bytes=allowed.stat().st_size,
            allowed_signers_sha256=recovery.sha(allowed.read_bytes())))
        authority = transaction/'authorization.json'; authority.write_bytes(recovery.canonical(self.authority))
        subprocess.run(['ssh-keygen','-Y','sign','-f',str(key),'-n','stage17-owner-acceptance',str(authority)], check=True, capture_output=True)
        ab = recovery.binding(authority); sb = recovery.binding(Path(str(authority)+'.sig'))
        stamp = '2026-11-09T10:01:00Z'
        transition = recovery.make_transition(failed, ab, sb, stamp)
        path = evidence/recovery.TRANSITION_NAME; path.write_bytes(recovery.canonical(transition))
        reference = dict(path=recovery.TRANSITION_NAME, sha256=recovery.sha(path.read_bytes()))
        journal = recovery.canonical(recovery.make_journal(baseline, reference))
        receipt = recovery.transaction_receipt(ab, sb, recovery.binding(path),
            recovery.binding(evidence/recovery.NEXT_NAME, journal), stamp)
        (transaction/'consumption.json').write_bytes(recovery.canonical(receipt))
        resolutions = {f'S17-EXT-{i:03d}':SimpleNamespace(recorded_at_utc=recovery.support._parse_utc('2026-11-09T07:18:00Z'),
            semantic_context={'trust':trust}) for i in range(1,7)}
        arguments = dict(references=baseline['transition_records']+[reference], evidence_root=evidence,
                         repository_root=repository, resolutions=resolutions,
                         graph={'transitions':[{}, {}, failed]}, graph_sha256=failed['graph_sha256'],
                         catalog_sha256=failed['catalog_sha256'], versions=failed['version_hashes'])
        previous = SimpleNamespace(sha256=failed['previous_transition_sha256'])
        with patch.object(recovery, 'EVIDENCE', evidence), patch.object(recovery, 'REPOSITORY', repository), \
             patch.object(recovery, 'TRANSACTION', transaction), patch.object(recovery, 'template', return_value=self.expected), \
             patch.object(recovery, 'incident', return_value=({}, {'journal':baseline, 'failed_transition':failed})), \
             patch.object(recovery.core, '_transitions', side_effect=lambda **kw: ('PREFLIGHT_ACCEPTED', [previous])):
            state, rows = recovery.transitions(**arguments)
            self.assertEqual(state, 'READY_FOR_STAGE17_PHASE_AUTHORIZATION'); self.assertEqual(len(rows), 2)
            (transaction/'consumption.json').unlink()
            with self.assertRaises(recovery.JournalError): recovery.transitions(**arguments)
            (transaction/'consumption.json').write_bytes(recovery.canonical(receipt))
            authority.write_bytes(recovery.canonical(dict(self.authority, execution_authority=True)))
            with self.assertRaises(recovery.JournalError): recovery.transitions(**arguments)


if __name__ == '__main__': unittest.main()
