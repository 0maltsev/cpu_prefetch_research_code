"""Bounded metadata-only tests; no namespace registration or source generation."""
from dataclasses import replace
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_namespace_audit_v1 as audit

ROOT=Path(__file__).resolve().parents[1]


class NamespaceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='s180-namespace-software-')
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.local=self.root/'repo';self.local.mkdir()
        (self.local/'AGENTS.md').write_text('software fixture')
        self.metadata=self.local/'docs/evidence';self.metadata.mkdir(parents=True)
        self.stand=self.root/'stage17-owner-evidence';self.stand.mkdir()
        self.context=self.stand/'local-authoring-software-1';self.context.mkdir()
        self.receipts=self.context/'receipts';self.receipts.mkdir()
        self.bp=json.loads((ROOT/'config/stage17/d310-s180-blueprint-v1.json').read_bytes())
        self.identities=audit.planned_identities(self.bp)
        self.plan=dict(schema_version='cpu-prefetch-stage17-formal-software-plan/1',action_id='Q16c',captures=[])
        self.plan_sha=audit.sha(self.plan)
        self.save(self.metadata/'history.json',self.plan)
        self.save(self.receipts/'history.json',self.plan)
        # Only mandatory historical-plan pins are replaced for these isolated
        # software histories. The actual S180 blueprint pin is never patched.
        patch=mock.patch.object(audit,'REQUIRED_PLANS',(self.plan_sha,));patch.start();self.addCleanup(patch.stop)

    @staticmethod
    def save(path,value):path.write_bytes(audit.public.canonical(value))

    def run_audit(self,mode='local',**kw):
        return audit.audit(mode,self.local if mode=='local' else self.stand,self.bp,**kw)

    def matcher(self):return audit.Matcher(self.bp,audit.public.Limits())

    def test_exact_registry_covers_all_shared_streams_and360_distinct_phase_runs(self):
        d=self.identities
        self.assertEqual(len(d['sources']),36)
        groups=d['namespaces']
        self.assertEqual([len(groups[k]) for k in ('arena','node_order','schedule','ordering')],[6,6,36,3])
        self.assertEqual(len({n for values in groups.values() for n in values}),51)
        self.assertEqual(len({r[k] for r in d['runs'] for k in ('measurement_run_id','warmup_run_id')}),360)
        self.assertEqual(len({r[k] for r in d['sources'] for k in ('artifact_id','envelope_artifact_id','derivation_artifact_id')}),108)
        self.assertEqual({r['seed_id'] for r in d['sources']},{d['master_seed']['seed_id']})
        self.assertEqual(d['master_seed']['seed_hex'],self.bp['master_seed_hex'])
        for key in ('registration_performed','source_generation_performed','execution_authority','phase18_authority'):
            self.assertIs(d[key],False)

    def test_changed_blueprint_or_seed_cannot_select_different_audit_targets(self):
        for mutate in (lambda b:b.update(master_seed_hex='0'*64),
            lambda b:b['captures'][0].update(measurement_ns=1),lambda b:b.update(blueprint_id='different')):
            b=copy.deepcopy(self.bp);mutate(b)
            with self.assertRaisesRegex(ValueError,'exact frozen'):audit.planned_identities(b)

    def test_embedded_namespaces_run_ids_seed_ids_and_escaped_keys_are_collisions(self):
        tokens=[self.identities['namespace_root'],self.identities['runs'][0]['warmup_run_id'],
            self.identities['master_seed']['seed_id'],self.identities['sources'][0]['derivation_record_id']]
        for token in tokens:
            escaped=''.join('\\u%04x'%ord(c) for c in token)
            for raw in (json.dumps({'text':'prefix '+token+' suffix'}).encode(),
                ('{"'+escaped+'":true}').encode(),json.dumps({'nested':'{"value":"'+escaped+'"}'}).encode()):
                with self.subTest(token=token):self.assertTrue(self.matcher().inspect(raw)[0])

    def test_numeric_master_seed_in_all_supported_representations_is_a_collision(self):
        seed=self.bp['master_seed_hex'];number=int(seed,16)
        for value in (number,str(number),seed.upper(),'0x'+seed.upper(),{'nested':[number]}):
            found,_=self.matcher().inspect(json.dumps(dict(value=value)).encode())
            self.assertIn('numeric_seed:'+seed,found)
        self.assertFalse(self.matcher().inspect(b'{"boolean":true,"unrelated":1234}')[0])

    def test_local_and_all_stand_contexts_are_scanned_without_caller_exclusions(self):
        self.assertEqual(self.run_audit()['status'],'PASS_SCOPED_HISTORY_AUDIT')
        second=self.stand/'local-authoring-software-2';second.mkdir();(second/'actions').mkdir()
        self.save(second/'actions/consumed.json',dict(namespace=self.identities['namespace_root'],unused=True))
        result=self.run_audit('stand')
        self.assertEqual(result['status'],'FAIL');self.assertEqual(len(result['matches']),1)
        self.assertEqual(result['own_prospective_exclusions'],[])
        with self.assertRaises(TypeError):audit.audit('stand',self.stand,self.bp,exclusions=[str(second)])

    def test_jsonl_and_nested_preparation_history_are_included(self):
        prep=self.context/'q16c-configuration-software';prep.mkdir()
        (prep/'history.jsonl').write_text(json.dumps({'ok':True})+'\n'+json.dumps({'seed':self.bp['master_seed_hex']})+'\n')
        self.assertEqual(self.run_audit('stand')['status'],'FAIL')
        local=self.local/'build/stage17-q16c-software';local.mkdir(parents=True)
        self.save(local/'history.json',dict(namespace=self.identities['namespace_root']))
        self.assertEqual(self.run_audit()['status'],'FAIL')

    def test_raw_payload_trees_are_never_entered_or_read(self):
        for parent in (self.metadata,self.receipts):
            raw=parent/'raw';raw.mkdir();self.save(raw/'observations.json',dict(namespace=self.identities['namespace_root']))
        original=audit.public.read_metadata;paths=[]
        def read(path,maximum):paths.append(path);return original(path,maximum)
        with mock.patch.object(audit.public,'read_metadata',side_effect=read):
            for mode in ('local','stand'):
                result=self.run_audit(mode)
                self.assertEqual(result['status'],'PASS_SCOPED_HISTORY_AUDIT')
                self.assertTrue(any(e['reason']=='RAW_PAYLOAD_TREE_NOT_ENTERED' for e in result['excluded']))
        self.assertFalse(any('raw' in p.parts for p in paths))

    def test_every_observed_archive_family_requires_its_full_original_plan(self):
        other=dict(schema_version='cpu-prefetch-stage17-formal-software-plan/2',action_id='Q16a',captures=[])
        sha=audit.sha(other)
        self.save(self.metadata/'family.json',dict(schema_version=audit.LEDGER_SCHEMA,kind='FAMILY',payload=dict(family_id=sha)))
        result=self.run_audit();self.assertEqual(result['status'],'FAIL')
        self.assertIn(sha,result['required_history_plan_sha256'])
        self.save(self.metadata/'other-plan.json',other)
        self.assertEqual(self.run_audit()['status'],'PASS_SCOPED_HISTORY_AUDIT')

    def test_missing_required_history_malformed_json_and_symlinks_fail_closed(self):
        history=self.metadata/'history.json';raw=history.read_bytes();history.unlink()
        self.save(self.metadata/'not-a-plan.json',{'ok':True})
        self.assertEqual(self.run_audit()['status'],'FAIL');history.write_bytes(raw)
        bad=self.metadata/'bad.json';bad.write_bytes(b'{"duplicate":1,"duplicate":2}')
        self.assertEqual(self.run_audit()['status'],'FAIL');bad.unlink()
        bad.symlink_to(history)
        self.assertEqual(self.run_audit()['status'],'FAIL')

    def test_file_byte_node_depth_and_deadline_limits_are_hard_stops(self):
        self.save(self.metadata/'other.json',{'ok':True})
        for limits in (replace(audit.public.Limits(),max_files=1),replace(audit.public.Limits(),max_total_bytes=1),
            replace(audit.public.Limits(),max_json_nodes=1),replace(audit.public.Limits(),max_depth=0),
            replace(audit.public.Limits(),wall_seconds=0)):
            with self.subTest(limits=limits):self.assertEqual(self.run_audit(limits=limits)['status'],'FAIL')
        matcher=self.matcher();matcher.deadline=0
        with self.assertRaisesRegex(ValueError,'deadline'):matcher.inspect(b'{"ok":true}')

    def test_context_and_root_bounds_cannot_be_bypassed(self):
        with self.assertRaises(ValueError):self.run_audit('stand',limits=replace(audit.public.Limits(),max_contexts=0))
        extra=self.local/'build/stage17-q16c-history';extra.mkdir(parents=True)
        with self.assertRaises(ValueError):self.run_audit(limits=replace(audit.public.Limits(),max_roots=1))

    def test_changed_metadata_or_inventory_during_audit_is_rejected(self):
        original=audit.public.read_metadata
        for kind in ('file','directory'):
            extra=self.metadata/'new-file.json';extra.unlink(missing_ok=True)
            self.save(self.metadata/'history.json',self.plan)
            def read(path,maximum):
                raw=original(path,maximum)
                if path.name=='history.json':
                    if kind=='file':path.write_bytes(raw+b' ')
                    else:self.save(extra,{'ok':True})
                return raw
            with mock.patch.object(audit.public,'read_metadata',side_effect=read):
                with self.subTest(kind=kind):self.assertEqual(self.run_audit()['status'],'FAIL')

    def test_malformed_family_and_unknown_mode_cannot_report_success(self):
        self.save(self.metadata/'bad-family.json',dict(schema_version=audit.LEDGER_SCHEMA,kind='FAMILY',payload={}))
        self.assertEqual(self.run_audit()['status'],'FAIL')
        with self.assertRaises(ValueError):audit.audit('unrecognized',self.local,self.bp)

    def test_only_exact_legacy_stdout_wrapper_is_fully_inspected(self):
        path=self.metadata/'legacy-diagnostic.json'
        raw=(ROOT/'docs/evidence/stage17/PILOT-D325-NAMESPACES-20261122-01/legacy-prequalification-stdout.txt').read_bytes()
        path.write_bytes(raw)
        report=self.run_audit()
        self.assertEqual(report['status'],'PASS_SCOPED_HISTORY_AUDIT')
        self.assertEqual(report['accepted_legacy_stdout_wrappers'],[dict(path=str(path),sha256=audit.LEGACY_STDOUT_SHA256,
            format='EXACT-Q16C-PREQUALIFICATION-JSON-PLUS-SCRATCH-COUNT-v1',full_original_bytes_inspected=True)])
        for changed in (raw.replace(b'scratch_roots 10',b'scratch_roots 11'),
            raw+self.identities['namespace_root'].encode(),raw.replace(b'262144647168',b'262144647169')):
            path.write_bytes(changed)
            self.assertEqual(self.run_audit()['status'],'FAIL')


if __name__=='__main__':unittest.main()
