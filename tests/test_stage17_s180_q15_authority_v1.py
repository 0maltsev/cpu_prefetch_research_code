"""Actual SSHSIG and immutable request contracts; explicitly synthetic facts.

No stand package, hardware, clocks, output inode or original journal is admitted
by these test contexts. The verifier is not an execution entry point.
"""
import copy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_q15_authority_v1 as q15


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='s180-q15-signature-');self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.counter=0;self.key=self.root/'owner'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(self.key)],
            check=True,capture_output=True,timeout=10)
        allowed=self.root/'allowed_signers';allowed.write_text('research-owner namespaces="cpu-prefetch-stage17" '
            +self.key.with_suffix('.pub').read_text())
        trust=dict(measurements=dict(principal='research-owner',sshsig_namespace='cpu-prefetch-stage17',
            allowed_signers_path=str(allowed),allowed_signers_size_bytes=allowed.stat().st_size,
            allowed_signers_sha256=hashlib.sha256(allowed.read_bytes()).hexdigest()))
        rows={f'S17-EXT-{i:03d}':SimpleNamespace(input_id=f'S17-EXT-{i:03d}',resolution_id=f'software-original-{i}',
            sha256=hashlib.sha256(str(i).encode()).hexdigest(),semantic_context={}) for i in range(1,8)}
        rows['S17-EXT-002'].semantic_context=dict(stand_id='SOFTWARE-STAND')
        rows['S17-EXT-003'].semantic_context=dict(trust=trust,runtime=dict(measurements=dict(
            worker_path='/software/older/runner',worker_role=q15.ROLE,runtime_profile=q15.PROFILE,
            worker_size_bytes=12345,worker_sha256='e'*64,
            supported_actions=['Q15-R','Q15-W','Q16a','Q16b','Q16c','STAGE17-BLINDED-PILOT'])))
        rows['S17-EXT-007'].semantic_context=dict(data_provenance_accepted=True,legacy_statistical_freeze_satisfied=False)
        self.base=SimpleNamespace(resolutions=rows);self.original=copy.deepcopy(rows)
        now=time.monotonic_ns();window=dict(boot_id=q15.environment._boot(),start_monotonic_ns=now-1000000,
            end_monotonic_ns=now-1000000+q15.pilot.DAY_NS)
        runtime=dict(role=q15.ROLE,profile=q15.PROFILE,sha256=q15.resources.NATIVE_SHA,size_bytes=q15.resources.NATIVE_SIZE)
        release=dict(source_resolution_id=q15.RELEASE_ID,source_resolution_sha256='b'*64,
            artifact_role=q15.ROLE,runtime_profile=q15.PROFILE,worker_size_bytes=runtime['size_bytes'],
            worker_sha256=runtime['sha256'],source_revision=q15.environment.NATIVE_REVISION)
        self.context=dict(schema_version=q15.CONTEXT_SCHEMA,plan_sha256='a'*64,window_binding=window,
            qualification_started_monotonic_ns=now,qualification_deadline_monotonic_ns=now+300*10**9,
            evidence_root_binding=dict(absolute_path=str(q15.ROOT),device=1,inode=2,owner_uid=0,mode='0700'),runtime_binding=runtime,
            release_binding=release,session_id='software-q15-session',qualification_id='software-qualification',
            stand_id='SOFTWARE-STAND',action_id='Q15-R',phase18_authority=False,
            action_inputs=dict(qualification_id='software-qualification',attempt_id='software-Q15-R-attempt',
                session_id='software-q15-session',probe_platform_binding=dict(cpu=0,numa_node=0,
                    verified_local_llc_bytes=25*1024**2,verified_base_page_bytes=4096)))

    def document(self,context=None):
        context=self.context if context is None else context
        rows=[q15.pilot.binding(self.base.resolutions[f'S17-EXT-{i:03d}']) for i in range(1,8)]
        return dict(**{k:copy.deepcopy(context[k]) for k in q15.COMMON},schema_version=q15.SCHEMA,
            authorization_id='software-'+context['action_id']+'-auth',request_id='software-'+context['action_id']+'-request',
            attempt_id='software-'+context['action_id']+'-attempt',actor='research-owner',
            trust_context=dict(ext002_resolution=rows[1],ext003_resolution=rows[2]),base_resolutions=rows,
            issued_at_epoch_seconds=time.time_ns()//10**9-1,expires_at_epoch_seconds=time.time_ns()//10**9+400,
            permission_scope=copy.deepcopy(q15.PERMISSIONS),synthetic_test_only=False,phase18_authority=False)

    def sign(self,value,*,key=None,namespace='cpu-prefetch-stage17'):
        self.counter+=1;path=self.root/f'authorization-{self.counter}.json';raw=q15.archive.canonical(value)
        path.write_bytes(raw)
        subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(key or self.key),'-n',namespace,str(path)],
            check=True,capture_output=True,timeout=10)
        return raw,Path(str(path)+'.sig')

    def verify(self,document=None,context=None,**changes):
        raw,sig=self.sign(self.document(context) if document is None else document,**changes)
        return q15.verify_authorization(authorization_bytes=raw,signature_path=sig,
            qualification_context=self.context if context is None else context,base_validation=self.base)

    def write_context(self):
        value=copy.deepcopy(self.context);value['action_id']='Q15-W'
        value['action_inputs']=dict(q15_r_attempt_sha256='c'*64,q15_r_result_sha256='d'*64,
            session_id=value['session_id'],prestate=[dict(cpu=cpu,complete_value_hex='0000010000000000') for cpu in (0,1,8)])
        return value

    def test_read_signature_builds_current_native_request_without_rewriting_originals(self):
        verified=self.verify();request=verified.request()
        self.assertEqual(request['schema_version'],'cpu-prefetch-stage17-fixed-action-request/4')
        self.assertEqual(request['runtime_binding']['sha256'],q15.resources.NATIVE_SHA)
        self.assertEqual(request['release_binding']['source_resolution_id'],q15.RELEASE_ID)
        self.assertNotEqual(request['release_binding']['source_resolution_sha256'],self.base.resolutions['S17-EXT-003'].sha256)
        self.assertNotIn('source_revision',request['release_binding'])
        self.assertEqual({k:vars(v) for k,v in self.base.resolutions.items()},{k:vars(v) for k,v in self.original.items()})
        for k in ('execution_authority','attempt_consumed','qualified_parent_replay_performed','full_qualification'):
            self.assertFalse(verified.proof()[k])

    def test_legacy_runtime_selection_remains_bound_to_its_original_image(self):
        from stage17_phase_controller_v4 import _runtime_from_context
        before,_=_runtime_from_context('Q15-R',self.base)
        current=self.verify().request()['runtime_binding']
        after,_=_runtime_from_context('Q15-R',self.base)
        self.assertEqual(before,after);self.assertEqual(after['sha256'],'e'*64)
        self.assertNotEqual(current['sha256'],after['sha256'])

    def test_native_carrier_matches_original_result_validator_serialization(self):
        import stage17_output_registry_v4 as original
        verified=self.verify();request=verified.request()
        self.assertEqual(verified.request_bytes,original.canonical(request))

    def test_both_requests_satisfy_the_existing_compiled_entry_schema(self):
        from jsonschema import Draft202012Validator
        root=Path(__file__).resolve().parents[1]
        schema=json.loads((root/'config/schemas/stage17-fixed-action-request-v4.schema.json').read_bytes())
        for context in (self.context,self.write_context()):
            verified=self.verify(context=context)
            request=verified.request()
            Draft202012Validator(schema).validate(request)
            native=verified.native_context(fixed_action_definition_sha256='f'*64)
            ctx=json.loads((root/'config/schemas/stage17-fixed-action-context-v4.schema.json').read_bytes())
            Draft202012Validator(ctx).validate(native)
            self.assertEqual(native['request_sha256'],hashlib.sha256(verified.request_bytes).hexdigest())
            self.assertEqual(native['authorization_sha256'],hashlib.sha256(verified.authorization_bytes).hexdigest())
            self.assertEqual(native['per_run_deadline_seconds'],180)

    def test_versioned_signed_schema_accepts_both_actions_and_rejects_extra_authority(self):
        from jsonschema import Draft202012Validator
        root=Path(__file__).resolve().parents[1]
        schema=json.loads((root/'config/schemas/stage17-s180-q15-authorization-v1.schema.json').read_bytes())
        validator=Draft202012Validator(schema)
        for context in (self.context,self.write_context()):
            doc=self.document(context);validator.validate(doc)
            for change in (lambda x:x.update(argv=['arbitrary']),lambda x:x.update(phase18_authority=True),
                lambda x:x['runtime_binding'].update(sha256='f'*64),
                lambda x:x['permission_scope'].update(automatic_retry=True)):
                wrong=copy.deepcopy(doc);change(wrong)
                self.assertFalse(validator.is_valid(wrong))

    def test_separately_signed_write_binds_complete_read_lineage_and_full_original_bits(self):
        context=self.write_context();verified=self.verify(context=context)
        request=verified.request()
        self.assertEqual(request['action_inputs'],context['action_inputs'])
        read=self.document();raw,sig=self.sign(read)
        with self.assertRaises(q15.pilot.AuthorityError):
            q15.verify_authorization(authorization_bytes=raw,signature_path=sig,qualification_context=context,base_validation=self.base)

    def test_wrong_owner_key_namespace_and_changed_signed_bytes_reject(self):
        other=self.root/'other'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(other)],check=True,capture_output=True,timeout=10)
        for changes in (dict(key=other),dict(namespace='foreign-namespace')):
            with self.assertRaises(q15.pilot.signatures.ControllerError):self.verify(**changes)
        value=self.document();raw,sig=self.sign(value);value['authorization_id']='changed'
        with self.assertRaises(q15.pilot.signatures.ControllerError):
            q15.verify_authorization(authorization_bytes=q15.archive.canonical(value),signature_path=sig,
                qualification_context=self.context,base_validation=self.base)

    def test_signed_input_cannot_choose_live_context_or_owner_trust(self):
        for key,value in [('plan_sha256','f'*64),('actor','different-owner'),('session_id','other-session'),
            ('trust_context',{}),('evidence_root_binding',dict(self.context['evidence_root_binding'],inode=99))]:
            document=self.document();document[key]=value
            with self.assertRaises(q15.pilot.AuthorityError):self.verify(document)

    def test_permissions_extra_fields_and_wrong_action_cannot_expand_scope(self):
        for key in q15.PERMISSIONS:
            doc=self.document();doc['permission_scope'][key]=2 if type(q15.PERMISSIONS[key]) is int else not q15.PERMISSIONS[key]
            with self.assertRaises(q15.pilot.AuthorityError):self.verify(doc)
        for key in ('argv','backend','key_path','request_binding'):
            doc=self.document();doc[key]='caller-selected'
            with self.assertRaises(q15.pilot.AuthorityError):self.verify(doc)
        context=copy.deepcopy(self.context);context['action_id']='Q16b'
        with self.assertRaises(q15.pilot.AuthorityError):self.verify(context=context)

    def test_changed_current_runtime_or_legacy_release_alias_rejects_even_when_signed(self):
        for section,key,value in [('runtime_binding','size_bytes',1),('runtime_binding','sha256','f'*64),
            ('release_binding','source_revision','1'*40),('release_binding','source_resolution_id','software-original-3')]:
            ctx=copy.deepcopy(self.context);ctx[section][key]=value
            with self.assertRaises(q15.pilot.AuthorityError):self.verify(context=ctx)

    def test_wrong_platform_cpu_page_and_unknown_llc_never_get_default_values(self):
        for key,value in [('cpu',26),('cpu',False),('numa_node',1),('verified_base_page_bytes',65536),
            ('verified_local_llc_bytes',0),('verified_local_llc_bytes',True),('verified_local_llc_bytes',4097)]:
            ctx=copy.deepcopy(self.context);ctx['action_inputs']['probe_platform_binding'][key]=value
            with self.assertRaises((q15.pilot.AuthorityError,q15.archive.ArchiveError)):self.verify(context=ctx)

    def test_write_prestate_order_bits_shape_and_same_buffer_are_required(self):
        for change in (lambda x:x['prestate'][2].update(cpu=26),lambda x:x['prestate'][0].update(complete_value_hex='0000010000000001'),
            lambda x:x['prestate'].pop(),lambda x:x.update(session_id='other-buffer'),
            lambda x:x.update(q15_r_result_sha256='invalid')):
            ctx=self.write_context();change(ctx['action_inputs'])
            with self.assertRaises((q15.pilot.AuthorityError,q15.archive.ArchiveError)):self.verify(context=ctx)
        doc=self.document(self.write_context());doc['action_inputs']['q15_r_result_sha256']='f'*64
        with self.assertRaises(q15.pilot.AuthorityError):self.verify(doc,context=self.write_context())

    def test_original_window_and_qualification_start_deadline_cannot_reset(self):
        for change in (lambda x:x['window_binding'].update(boot_id='wrong-boot'),
            lambda x:x.update(qualification_started_monotonic_ns=time.monotonic_ns()+100*10**9),
            lambda x:x.update(qualification_deadline_monotonic_ns=x['qualification_started_monotonic_ns']+1801*10**9),
            lambda x:x.update(qualification_deadline_monotonic_ns=time.monotonic_ns()-1),
            lambda x:x['window_binding'].update(end_monotonic_ns=x['window_binding']['end_monotonic_ns']+1)):
            ctx=copy.deepcopy(self.context);change(ctx)
            with self.assertRaises(q15.pilot.AuthorityError):self.verify(context=ctx)
        for key,value in [('issued_at_epoch_seconds',time.time_ns()//10**9+10),('expires_at_epoch_seconds',time.time_ns()//10**9+2)]:
            doc=self.document();doc[key]=value
            with self.assertRaises(q15.pilot.AuthorityError):self.verify(doc)

    def test_original_seven_stand_and_descriptive_scope_are_required(self):
        for change in (lambda:self.base.resolutions.pop('S17-EXT-006'),
            lambda:self.base.resolutions['S17-EXT-002'].semantic_context.update(stand_id='another-stand'),
            lambda:self.base.resolutions['S17-EXT-007'].semantic_context.update(legacy_statistical_freeze_satisfied=True),
            lambda:setattr(self.base.resolutions['S17-EXT-001'],'input_id','S17-EXT-002')):
            original=copy.deepcopy(self.base.resolutions);doc=self.document();change()
            with self.assertRaises(q15.pilot.AuthorityError):self.verify(doc)
            self.base.resolutions=original

    def test_returned_bytes_are_immutable_and_input_mutation_cannot_change_them(self):
        doc=self.document();verified=self.verify(doc);before=verified.request_bytes
        doc['action_inputs']['probe_platform_binding']['verified_local_llc_bytes']=4096
        self.context['session_id']='modified'
        self.assertEqual(before,verified.request_bytes)
        with self.assertRaises(FrozenInstanceError):verified.request_bytes=b'{}'

    def test_root_protection_and_native_r_attempt_cannot_drift(self):
        for key,value in [('absolute_path','/tmp/foreign'),('device',0),('inode',0),('owner_uid',1000),('mode','0777')]:
            context=copy.deepcopy(self.context);context['evidence_root_binding'][key]=value
            with self.assertRaises((q15.pilot.AuthorityError,q15.archive.ArchiveError)):self.verify(context=context)
        doc=self.document();doc['attempt_id']='different-read-attempt'
        with self.assertRaises(q15.pilot.AuthorityError):self.verify(doc)


if __name__=='__main__':unittest.main()
