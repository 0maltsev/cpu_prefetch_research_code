"""Actual E26 failure reproduction and narrow D256 recovery invariants."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import shutil
import subprocess
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import stage17_state_journal_v55 as renewal
import stage17_daycap_administration_v2 as admin

FIXTURE = ROOT/'docs/evidence/stage17/D256-E26-REPAIR-20261115-01'


class RenewalTests(unittest.TestCase):
    def setUp(self):
        self.incident = json.loads((FIXTURE/'incident.json').read_bytes())['files']
        self.failed = self.incident['records/transition-003.json']['document']
        self.records = json.loads((FIXTURE/'resolutions.json').read_bytes())

    def test_actual_old_windows_do_not_overlap(self):
        rows = {v['input_id']: v for v in self.records.values()}
        preflight_end = renewal.support._parse_utc(rows['S17-EXT-001']['authorization']['expires_at_utc'])
        hardware_start = renewal.support._parse_utc(rows['S17-EXT-005']['authorization']['issued_at_utc'])
        self.assertGreater(hardware_start, preflight_end)
        self.assertEqual((hardware_start-preflight_end).total_seconds(), 63)

    def test_actual_original_transition_fails_the_unchanged_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory)
            (evidence/'records').mkdir()
            refs = []
            baseline = self.incident['journal/stage17-state-journal-000008.json']['document']
            # The first two committed transitions are unnecessary to reproduce
            # edge3's time gate; carry actual prefix bytes from the launch proof.
            # Build just the actual third-edge input as a one-edge graph.
            failed = copy.deepcopy(self.failed)
            failed.update(sequence_number=1, previous_transition_sha256='0'*64)
            raw = renewal.canonical(failed)
            (evidence/'records/transition.json').write_bytes(raw)
            resolutions = {}
            for value in self.records.values():
                resolutions[value['input_id']] = types.SimpleNamespace(
                    resolution_id=value['resolution_id'],
                    sha256=next(r['sha256'] for r in baseline['resolution_records']
                        if r['path'].endswith(next(k for k,v in self.records.items() if v is value))),
                    recorded_at_utc=renewal.support._parse_utc(value['recorded_at_utc']),
                    document=value)
            graph = json.loads((ROOT/'config/stage17/stage17-operational-graph-definition-v1.json').read_bytes())
            graph.update(initial_state=failed['from_state'], transitions=[graph['transitions'][2]])
            with self.assertRaisesRegex(renewal.JournalError, 'transition authority is future/expired'):
                renewal.core._transitions(repository_root=ROOT, evidence_root=evidence,
                    references=[dict(path='records/transition.json',sha256=renewal.sha(raw))],
                    graph=graph,graph_sha256=failed['graph_sha256'],catalog_sha256=failed['catalog_sha256'],
                    versions=failed['version_hashes'],genesis_sha256='0'*64,resolutions=resolutions)

    def test_incident_hashes_match_recorded_bytes(self):
        for role, (name, digest) in renewal.FIXED.items():
            self.assertEqual(self.incident[name]['sha256'], digest, role)

    def test_incident_requires_successful_measurements_and_cleanup(self):
        with patch.object(renewal, 'read', side_effect=lambda p:
                renewal.canonical(self.incident[str(p.relative_to(renewal.EVIDENCE))]['document'])), \
             patch.object(renewal, 'sha', side_effect=lambda raw:
                next(v['sha256'] for v in self.incident.values() if renewal.canonical(v['document']) == raw)):
            bindings, documents = renewal.incident()
            self.assertEqual(set(bindings),set(renewal.FIXED))
            self.assertTrue(documents['clocks']['both_pairs_passed'])
            self.incident['clock-qualification-v26-1/complete.json']['document']['both_pairs_passed'] = False
            with self.assertRaisesRegex(renewal.JournalError,'clock qualification failed'):
                renewal.incident()

    def test_exact_retained_incident_rejects_every_changed_or_missing_input(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence=Path(directory)/'evidence'
            shutil.copytree(FIXTURE/'qualification',evidence)
            with patch.object(renewal,'EVIDENCE',evidence):
                renewal.incident()
                for name,digest in renewal.FIXED.values():
                    p=evidence/name;raw=p.read_bytes()
                    for changed in (b'{}\n',None):
                        with self.subTest(name=name,changed=changed):
                            if changed is None:p.unlink()
                            else:p.write_bytes(changed)
                            with self.assertRaises((renewal.JournalError,FileNotFoundError)):
                                renewal.incident()
                            p.write_bytes(raw)

    def authority(self):
        expected = dict(authority_scope='E26_D256_ADMINISTRATIVE_TRANSITION_ONLY',
            execution_authority=False, phase18_authority=False, one_use=True)
        value = dict(expected,issued_at_utc='2026-11-15T20:00:00Z',expires_at_utc='2026-11-15T20:30:00Z')
        return expected, value

    def test_renewal_accepts_issue_boundary(self):
        expected,value=self.authority()
        renewal.validate_authority(value,expected,'2026-11-15T20:00:00Z')

    def test_renewal_rejects_expiry_boundary(self):
        expected,value=self.authority()
        with self.assertRaises(renewal.JournalError):renewal.validate_authority(value,expected,'2026-11-15T20:30:00Z')

    def test_renewal_rejects_future_issue(self):
        expected,value=self.authority()
        with self.assertRaises(renewal.JournalError):renewal.validate_authority(value,expected,'2026-11-15T19:59:59Z')

    def test_renewal_rejects_extended_window(self):
        expected,value=self.authority();value['expires_at_utc']='2026-11-15T20:31:00Z'
        with self.assertRaises(renewal.JournalError):renewal.validate_authority(value,expected,'2026-11-15T20:10:00Z')

    def test_renewal_rejects_execution_authority(self):
        expected,value=self.authority();value['execution_authority']=True
        with self.assertRaises(renewal.JournalError):renewal.validate_authority(value,expected,'2026-11-15T20:10:00Z')

    def test_renewal_rejects_extra_fields(self):
        expected,value=self.authority();value['retry_allowed']=True
        with self.assertRaises(renewal.JournalError):renewal.validate_authority(value,expected,'2026-11-15T20:10:00Z')

    def test_transition_preserves_original_edge_and_authority_references(self):
        before=copy.deepcopy(self.failed)
        result=renewal.make_transition(self.failed,{'path':'AUTH'},{'path':'SIG'},'2026-11-15T20:10:00Z')
        for key in before.keys()-{'schema_version','transition_id','timestamp_utc'}:
            self.assertEqual(result[key],before[key])
        self.assertEqual(self.failed,before)
        self.assertEqual(result['schema_version'],'cpu-prefetch-stage17-state-transition/2')

    def test_journal_keeps_all_original_resolutions_and_transitions(self):
        old=copy.deepcopy(self.incident['journal/stage17-state-journal-000008.json']['document'])
        result=renewal.make_journal(old,dict(path=renewal.TRANSITION_NAME,sha256='a'*64))
        self.assertEqual(result['resolution_records'],old['resolution_records'])
        self.assertEqual(result['transition_records'][:2],old['transition_records'])
        self.assertEqual(result['previous_journal'],dict(path=renewal.BASE_NAME,sha256=renewal.BASE_SHA))
        self.assertEqual(old['journal_sequence_number'],8)

    def test_exclusive_publication_cannot_replace_existing_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'consumption.json'
            renewal.write_exclusive(p,b'original')
            with self.assertRaises(FileExistsError):renewal.write_exclusive(p,b'replacement')
            self.assertEqual(p.read_bytes(),b'original')

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(renewal.JournalError):renewal.parse(b'{"one_use":true,"one_use":false}')

    def test_private_graph_selects_renewal_at_every_journal_boundary(self):
        original=renewal.predecessor.validate_operational_journal
        cli=admin.make_cli();controller=cli.controller
        self.assertIs(cli.journal,renewal)
        self.assertIs(controller.prepare_action.__globals__['journal_runtime'],renewal)
        self.assertIs(controller._v25._prepare_action.__globals__['journal_runtime'],renewal)
        self.assertIs(controller.activate.__globals__['journal_runtime'],renewal)
        for name in ('author_formal_request','author_formal_authorization','verify_formal_signature','execute_formal','prepare_formal_retention','admit_formal_retention'):
            self.assertIs(getattr(cli,name).__code__,getattr(admin.previous.original_cli,name).__code__)
        renewal.activate()
        self.assertIs(renewal.predecessor.validate_operational_journal,original)

    def test_complete_transition_checks_real_signature_and_consumption_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);evidence=root/'evidence';evidence.mkdir();(evidence/'records').mkdir()
            transaction=root/'transaction';transaction.mkdir()
            repository=root/'repository';repository.mkdir()
            failed=self.failed;baseline=self.incident[renewal.BASE_NAME]['document']
            expected,authority=self.authority()
            key=root/'software-only-key'
            subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],check=True,capture_output=True)
            allowed=root/'allowed';allowed.write_text('software-owner '+key.with_suffix('.pub').read_text())
            trust=dict(measurements=dict(principal='software-owner',sshsig_namespace='stage17-owner-acceptance',
                allowed_signers_path=str(allowed),allowed_signers_size_bytes=allowed.stat().st_size,
                allowed_signers_sha256=renewal.sha(allowed.read_bytes())))
            authpath=transaction/'authorization.json';authpath.write_bytes(renewal.canonical(authority))
            subprocess.run(['ssh-keygen','-Y','sign','-f',str(key),'-n','stage17-owner-acceptance',str(authpath)],check=True,capture_output=True)
            signature=Path(str(authpath)+'.sig');ab=renewal.binding(authpath);sb=renewal.binding(signature)
            stamp='2026-11-15T20:10:00Z'
            transition=renewal.make_transition(failed,ab,sb,stamp)
            p=evidence/renewal.TRANSITION_NAME;p.write_bytes(renewal.canonical(transition))
            ref=dict(path=renewal.TRANSITION_NAME,sha256=renewal.sha(p.read_bytes()))
            journal=renewal.canonical(renewal.make_journal(baseline,ref))
            receipt=renewal.transaction_receipt(ab,sb,renewal.binding(p),renewal.binding(evidence/renewal.NEXT_NAME,journal),stamp)
            marker=transaction/'consumption.json';marker.write_bytes(renewal.canonical(receipt))
            resolutions={f'S17-EXT-{i:03d}':types.SimpleNamespace(
                recorded_at_utc=renewal.support._parse_utc('2026-11-15T18:28:00Z'),semantic_context={'trust':trust}) for i in range(1,7)}
            args=dict(references=baseline['transition_records']+[ref],evidence_root=evidence,repository_root=repository,
                resolutions=resolutions,graph={'transitions':[{}, {}, failed]},graph_sha256=failed['graph_sha256'],
                catalog_sha256=failed['catalog_sha256'],versions=failed['version_hashes'])
            previous=types.SimpleNamespace(sha256=failed['previous_transition_sha256'])
            with patch.object(renewal,'EVIDENCE',evidence),patch.object(renewal,'REPOSITORY',repository), \
                 patch.object(renewal,'TRANSACTION',transaction),patch.object(renewal,'template',return_value=expected), \
                 patch.object(renewal,'incident',return_value=({},dict(journal=baseline,failed_transition=failed))), \
                 patch.object(renewal.core,'_transitions',side_effect=lambda **kw:('PREFLIGHT_ACCEPTED',[previous])):
                state,rows=renewal.transitions(**args)
                self.assertEqual(state,'READY_FOR_STAGE17_PHASE_AUTHORIZATION')
                self.assertEqual(len(rows),2)
                marker.unlink()
                with self.assertRaises((FileNotFoundError,renewal.JournalError)):renewal.transitions(**args)
                marker.write_bytes(renewal.canonical(receipt))
                raw=signature.read_bytes();signature.write_bytes(b'invalid signature')
                sb['size_bytes']=signature.stat().st_size;sb['sha256']=renewal.sha(signature.read_bytes())
                transition['recovery']['signature']=sb;p.write_bytes(renewal.canonical(transition));args['references'][-1]['sha256']=renewal.sha(p.read_bytes())
                with self.assertRaises(renewal.support.ControllerError):renewal.transitions(**args)


if __name__=='__main__':unittest.main()
