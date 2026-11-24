"""Actual SSH signatures and byte custody with synthetic software provenance.

This fixture is deliberately not accepted-generator/empirical evidence. It
tests the receipt boundary against an independently supplied test trust root.
"""
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_source_receipts_v1 as current
import stage17_q16c_source_prepare_v1 as prep
from test_stage17_formal_scheduled_descriptive_v1 import plan_fixture

ROOT=Path(__file__).resolve().parents[1]


def bound(path):
    raw=path.read_bytes()
    return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def save(path, value):
    path.write_bytes(prep.canonical(value));return bound(path)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.bundle=self.root/'bundle';self.bundle.mkdir()
        self.output=self.root/'originals';self.output.mkdir()
        self.key=self.root/'test-key'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(self.key)],check=True)
        allowed=self.root/'allowed';allowed.write_text('synthetic-owner '+Path(str(self.key)+'.pub').read_text())
        a=bound(allowed)
        self.trust=dict(measurements=dict(allowed_signers_path=a['path'],allowed_signers_size_bytes=a['size_bytes'],
            allowed_signers_sha256=a['sha256'],principal='synthetic-owner',sshsig_namespace='synthetic-source-proof'))
        self.plan=plan_fixture();p=self.plan
        names=current.semantic.discover_python_closure(ROOT,('generate_schedule','stage17_q16c_schedule_provenance_v2'))
        names|={'protocol/2.0.0-pre.3/handoff/schemas/schedule.schema.json','config/schemas/schedule-derivation-v2.schema.json',
                'config/schemas/stage17-formal-scheduled-native-input-v2.schema.json'}
        closure={};index=[]
        basis_name='docs/evidence/stage17/Q16B-HANDOFF-20261117-01/descriptive-load-basis.json'
        for name in sorted(names|{basis_name}):
            path=self.bundle/name;path.parent.mkdir(exist_ok=True,parents=True);path.write_bytes((ROOT/name).read_bytes())
            b=bound(path);index.append(dict(b,path=name))
            if name in names:closure[name]=b
        inv=save(self.bundle/'BUNDLE_INVENTORY.json',dict(files=index))
        self.boot='00000000-0000-4000-8000-000000000000'
        release=dict(source_revision=p['source_revision'],inventory_sha256=inv['sha256'],archive_bundle_root=str(self.bundle))
        self.validation=NS(resolutions={'S17-EXT-003':NS(semantic_context=dict(trust=self.trust)),
            'S17-EXT-006':NS(semantic_context=release)})
        setup=dict(schema_version=prep.SETUP_SCHEMA,stand_id=p['stand_id'],boot_id=self.boot,bundle_root=str(self.bundle),
            source_revision=p['source_revision'],bundle_inventory_sha256=inv['sha256'],sources=[],execution_authority=False,phase18_authority=False)
        basis=json.loads((self.bundle/basis_name).read_bytes());rows=[];self.sources=[];self.registrations=[]
        for i in range(360):
            c=p['captures'][i//2]['capture'];s=c['schedules'][i%2];phase=('warmup','measurement')[i%2]
            d=self.output/f's{i:03d}';d.mkdir()
            binary=d/'original.u64be';binary.write_bytes(bytes(s['offered_count']*8));b=bound(binary)
            s['source_artifact']['sha256']=b['sha256'];identity=s['source_artifact']['artifact_id']
            envelope=save(d/'schedule.json',dict(schedule_sha256='a'*64,decoded_deadlines_sha256='b'*64))
            derivation=save(d/'derivation.json',dict(record_sha256='c'*64,record_id='derivation-'+str(i)))
            reg=dict(phase=phase,parent_namespace_id='synthetic-parent',**{k:s[k] for k in ('schedule_id','namespace_id','seed_id')})
            self.registrations.append(reg)
            row=dict(ordinal=i,binary=b,envelope=envelope,derivation=derivation,exit_code=0,leader_reaped=True)
            setup['sources'].append(dict(ordinal=i,capture_ordinal=i//2,phase=phase,load_level=c['load_level'],
                **{k:s[k] for k in ('schedule_id','namespace_id','seed_id','seed_hex')},parent_namespace_id='synthetic-parent',
                artifact_id=identity,artifact_uri='synthetic-source-'+str(i),derivation_record_id='derivation-'+str(i)))
            rate=Fraction(**basis['base_rates'][c['load_level']])/10**12
            provenance=dict(schema_version=current.provenance.SCHEMA_ID,phase=phase,**{k:s[k] for k in ('schedule_id','namespace_id','seed_id',
                'source_origin_ticks','source_horizon_ticks','offered_count')},parent_namespace_id='synthetic-parent',duration_ticks=c[phase+'_ns']*1000,
                scale_ordinal=0,load_level=c['load_level'],descriptive_load_basis_sha256=current.provenance.BASIS_SHA256,
                family_method_id='MATRIX-FULL-DESCRIPTIVE-SCREEN-v1',confidence_claim=None,accepted_generation_verified=True,
                execution_authority=False,phase18_authority=False,nominal_offered_rate=dict(numerator_events=rate.numerator,denominator_ticks=rate.denominator),
                schedule_sha256='a'*64,derivation_record_sha256='c'*64,decoded_deadlines_sha256='b'*64,artifact_uri='synthetic-source-'+str(i))
            for name,value,suffix in [('artifact_binding',b,''),('envelope_binding',envelope,':envelope'),('derivation_binding',derivation,':derivation')]:
                provenance[name]=dict(artifact_id=identity+suffix,size_bytes=value['size_bytes'],sha256=value['sha256'])
            row['provenance']=provenance;rows.append(row)
            self.sources.append(dict(artifact_id=identity,binding=b,envelope_binding=envelope,derivation_binding=derivation,parent_namespace_id='synthetic-parent'))
        start=time.monotonic_ns()
        self.record=dict(schema_version=current.SCHEMA,purpose=current.PURPOSE,protocol_version='2.0.0-pre.3',stand_id=p['stand_id'],boot_id=self.boot,
            software_source_revision=p['source_revision'],bundle_inventory_sha256=inv['sha256'],load_basis_sha256=current.provenance.BASIS_SHA256,
            source_root=str(self.output),source_closure=closure,source_setup=save(self.root/'setup.json',setup),started_monotonic_ns=start,
            completed_monotonic_ns=start+1,source_deadline_ns=start+current.SOURCE_CAP_NS,global_deadline_ns=start+current.DAY_NS,
            workers=32,all_workers_reaped=True,sources=rows,experimental_actions=0,execution_authority=False,phase18_authority=False)
        self.sign()

    def sign(self):
        path=self.output/'source-preparation.json';sig=Path(str(path)+'.sig')
        if sig.exists():sig.unlink()
        save(path,self.record)
        subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(self.key),'-n','synthetic-source-proof',str(path)],
            check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.proof=dict(manifest=bound(path),signature=bound(sig))
        for row in self.sources:row['source_preparation']=copy.deepcopy(self.proof)

    def validate(self):
        return current.validate(self.plan,self.sources,self.registrations,self.proof,validation=self.validation,
                                boot_id=self.boot,deadline_ns=time.monotonic_ns()+60*10**9)

    def test_actual_signature_complete_order_and_exact_current_bytes(self):
        record,bindings=self.validate();self.assertEqual(record,self.record)
        self.assertEqual(len(bindings),360);self.assertEqual(sum(b['size_bytes'] for b in bindings),7200)

    def test_changed_seed_cannot_hide_behind_same_seed_id_and_provenance(self):
        self.plan['captures'][0]['capture']['schedules'][0]['seed_hex']='f'*64
        with self.assertRaisesRegex(current.Error,'seed_hex'):self.validate()

    def test_current_original_corruption_and_incomplete_signed_family_rejected(self):
        path=Path(self.sources[0]['binding']['path']);path.write_bytes(b'x'*path.stat().st_size)
        with self.assertRaises(current.Error):self.validate()
        path.write_bytes(bytes(path.stat().st_size));self.record['sources'].pop();self.sign()
        with self.assertRaisesRegex(current.Error,'complete360'):self.validate()

    def test_wrong_signature_and_signed_clock_reset_rejected(self):
        self.trust['measurements']['principal']='foreign-owner'
        with self.assertRaises(current.controller.support.ControllerError):self.validate()
        self.trust['measurements']['principal']='synthetic-owner';self.record['global_deadline_ns']+=1;self.sign()
        with self.assertRaisesRegex(current.Error,'absolute24h'):self.validate()

    def test_accepted_code_change_or_signed_fake_reaping_rejected(self):
        path=self.bundle/'tools/generate_schedule.py';path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaises(current.Error):self.validate()
        path.write_bytes((ROOT/'tools/generate_schedule.py').read_bytes());self.record['sources'][1]['leader_reaped']=False;self.sign()
        with self.assertRaisesRegex(current.Error,'completion'):self.validate()


if __name__=='__main__':unittest.main()
