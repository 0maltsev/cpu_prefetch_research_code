"""D298 keeps the original clock, source and scientific functions unchanged."""
import ast
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
from contextlib import ExitStack

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16c_qualified_continuation_v1 as current


def functions(raw):
    return {n.name:n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)}


class RenderTests(unittest.TestCase):
    def test_actual_isolation_binding_shape_is_read_as_bound_metadata(self):
        import prepare_stage17_q16c_qualified_continuation_v1 as prepare
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'isolation.json';path.write_bytes(b'{"evidence_root":"original"}')
            expected=prepare.binding(path)
            self.assertEqual(prepare.document(expected),prepare.document(path))
            path.write_bytes(b'{"evidence_root":"modified"}')
            with self.assertRaisesRegex(ValueError,'bound metadata differs'):prepare.document(expected)

    def test_journal_admission_is_explicitly_under_the_actual_evidence_owner(self):
        functions_=functions(Path(current.__file__).read_bytes())
        owner=ast.get_source_segment(Path(current.__file__).read_text(),functions_['owner_journal'])
        self.assertIn('os.getresuid() == (1000,)*3',owner)
        self.assertIn('return owner_metadata',owner)
        metadata=ast.get_source_segment(Path(current.__file__).read_text(),functions_['owner_metadata'])
        self.assertIn('cli._validation',metadata)
        self.assertIn('_verify_signature',metadata)
        root=ast.get_source_segment(Path(current.__file__).read_text(),functions_['admit'])
        self.assertNotIn('cli._validation',root)
        self.assertIn("'--reuid=1000','--regid=1000','--clear-groups'",root)
        self.assertNotIn('_verify_signature',root)
        self.assertIn("accepted['configuration_sha256'] == args.configuration_sha256",root)

    def test_only_observation_and_restoration_paths_change_in_scientific_operator(self):
        name='stage17_q16c_continuation_operator_v1.py'
        raw=(ROOT/'tools'/name).read_bytes();new=current.render(name,raw).decode()
        for old,replaced in [('platform-guard-1/witness.json','platform-guard-d298-1/witness.json'),
                             ('platform-observations-1','platform-observations-d298-1'),
                             ('q16c-study-1/partition-restoration.json','q16c-study-d298-1/partition-restoration.json')]:
            new=new.replace(replaced,old)
        new=new.replace(".isoformat(timespec='seconds')",'.isoformat()')
        new=new.replace('# The immutable authorization schema requires whole UTC seconds; floor conservatively.',
                        '# Subsecond issue precision prevents losing a full second by truncation.')
        self.assertEqual(new.encode(),raw)

    def test_actual_authorization_expressions_match_pinned_schema_without_extending_lifetime(self):
        import jsonschema
        name='stage17_q16c_continuation_operator_v1.py'
        original=ast.parse((ROOT/'tools'/name).read_bytes())
        repaired=ast.parse(current.render(name,(ROOT/'tools'/name).read_bytes()))
        schema=json.loads((ROOT/'config/schemas/stage17-phase-action-authorization-v6.schema.json').read_bytes())
        utc=jsonschema.Draft202012Validator(schema['$defs']['utc'])
        def values(tree,now):
            calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                   and n.func.attr=='author_formal_authorization']
            self.assertEqual(len(calls),1)
            return {k.arg:eval(compile(ast.Expression(k.value),'actual-authorization-expression','eval'),dict(now=now,dt=dt))
                    for k in calls[0].keywords if k.arg in ('issued_at_utc','expires_at_utc')}
        for fraction in (0,1,956026,999999):
            now=dt.datetime(2026,11,19,20,12,33,fraction,tzinfo=dt.timezone.utc)
            before=values(original,now);after=values(repaired,now)
            for value in after.values():utc.validate(value)
            if fraction:
                with self.assertRaises(jsonschema.ValidationError):utc.validate(before['expires_at_utc'])
            issued=dt.datetime.fromisoformat(after['issued_at_utc']);expires=dt.datetime.fromisoformat(after['expires_at_utc'])
            self.assertEqual((expires-issued).total_seconds(),24860)
            self.assertLessEqual(expires,now+dt.timedelta(seconds=24860))

    def test_recovery_uses_identical_cleanup_code_with_distinct_evidence_paths(self):
        name='stage17_q16c_continuation_recovery_v1.py';raw=(ROOT/'tools'/name).read_bytes()
        new=current.render(name,raw).decode()
        for old,replaced in [('d295-study-1','d298-study-1'),('q16c-study-1','q16c-study-d298-1'),
                             ('platform-guard-1','platform-guard-d298-1'),
                             ('cpu-prefetch-d295-v32-1.service','cpu-prefetch-d298-v32-1.service'),
                             ('d295-independent-recovery-1.json','d298-independent-recovery-1.json'),
                             ('isolation-preparation-v32-1/prospective-prestate.json','isolation-preparation-v32-d298-1/prospective-prestate.json')]:
            new=new.replace(replaced,old)
        self.assertEqual(new.encode(),raw)

    def test_rearm_driver_cannot_start_a_window_qualification_or_constructor(self):
        name='stage17_q16c_continuation_study_v1.py'
        raw=(ROOT/'tools'/name).read_bytes();out=current.render(name,raw);f=functions(out)
        calls=[n for n in ast.walk(f['run']) if isinstance(n,ast.Call)]
        self.assertFalse(any(isinstance(n.func,ast.Name) and n.func.id=='sign_window' for n in calls))
        commands=[n.args[0].value for n in calls if isinstance(n.func,ast.Name) and n.func.id=='command']
        self.assertEqual(sorted(commands),['sign-collect','suffix'])
        self.assertFalse(any(isinstance(n.func,ast.Attribute) and n.func.attr in ('qualify','capture','step') for n in calls))
        namespace={};exec(compile(ast.Module(body=[f['sign_window']],type_ignores=[]),'window-disabled','exec'),namespace)
        with self.assertRaisesRegex(ValueError,'forbids a new window'):namespace['sign_window']({})
        old=functions(raw)
        for name in ['module','online','owner']:
            before=ast.dump(old[name]);after=ast.dump(f[name]).replace('d298-study-1','d295-study-1')
            self.assertEqual(before,after,name)
        run=ast.get_source_segment(out.decode(),f['run'])
        self.assertIn('complete=min(resume.DEADLINE,start+resume.ENVELOPE)',run)
        self.assertIn('start+600*NS',run)
        self.assertIn('clock.ISO.prepare',run)
        self.assertLess(run.index('resume.admit'),run.index('guard=controls.Guard'))
        self.assertLess(run.index('bounded_restore'),run.index("command('suffix'"))

    def test_changed_frozen_source_is_rejected(self):
        for name in current.FROZEN:
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'exact frozen'):
                current.render(name,(ROOT/'tools'/name).read_bytes()+b'\n')

    def test_original_full_envelope_and_strict_cutoff(self):
        self.assertEqual(current.ENVELOPE,31460*10**9)
        cutoff=current.DEADLINE-current.ENVELOPE
        current.check_time(cutoff-1)
        for value in (cutoff,cutoff+1,current.DEADLINE,0,True):
            with self.subTest(value=value),self.assertRaises(ValueError):current.check_time(value)

    def test_actual_owner_acceptance_matches_exact_proposal_and_has_no_new_day(self):
        p=ROOT/'docs/decisions/0298-q16c-qualified-same-window-continuation-proposal.md'
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),current.PROPOSAL_SHA)
        a=json.loads((ROOT/'docs/evidence/stage17/Q16C-D298-ACCEPTED-20261119-01/owner-acceptance.json').read_bytes())
        self.assertEqual(a['owner_message'],'continue');self.assertEqual(a['new_execution_windows'],0)
        self.assertFalse(a['repeat_qualification']);self.assertEqual(a['original_deadline_monotonic_ns'],current.DEADLINE)
        current.validate_acceptance(a)
        for key,value in [('owner_message','approve'),('new_execution_windows',1),('manual_continuations',2),
                          ('repeat_qualification',True),('repeat_completed_raw_validations',True),
                          ('maximum_remaining_seconds',31461),('remaining_capture_count',93),
                          ('original_deadline_monotonic_ns',current.DEADLINE+1),('new_execution_windows',False)]:
            bad=dict(a,**{key:value})
            with self.subTest(key=key,value=value),self.assertRaisesRegex(ValueError,'actual owner approval'):
                current.validate_acceptance(bad)

    def test_isolation_adapter_has_only_the_exact_qualified_source_and_fresh_receipt_paths(self):
        raw=current.render_isolation();ast.parse(raw)
        self.assertIn(b'bc3880139caa1ac1a0880babfee52335749c870c5f6df402b1a1cdcfc2218018',raw)
        self.assertIn(b'isolation-preparation-v32-d298-1',raw)
        self.assertIn(b'clock-rearm-d298-1',raw)
        self.assertIn(b"name in ('main','capture')",raw)


class SequenceTests(unittest.TestCase):
    def scenario(self, failure=None):
        import stage17_q16c_continuation_operator_v1 as io
        import stage17_hardware_recovery_v1 as hardware
        import stage17_locked_compaction_guard_v1 as controls
        import stage17_q16c_compaction_integration_v2 as integration
        raw=current.render('stage17_q16c_continuation_study_v1.py',
                           (ROOT/'tools/stage17_q16c_continuation_study_v1.py').read_bytes())
        study=types.ModuleType('test_d298_root');study.__file__='/software-only/driver.py'
        exec(compile(raw,study.__file__,'exec'),study.__dict__)
        events=[]
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            e=Path(directory);out=e/'output';out.mkdir()
            args=types.SimpleNamespace(configuration=e/'configuration.json',configuration_sha256='b'*64)
            cfg=dict(repository_root=str(ROOT),evidence_root=str(e),output_root=str(out),
                     cgroup=str(e/'absent-cgroup'),worker=dict(size_bytes=10,sha256='c'*64),
                     clock_adapter={},terminal_reader={},prior_qualification={},window_proof={'manifest':{}})
            q=e/'clock-rearm-d298-1';isolation=e/'isolation-preparation';isolation.mkdir()
            pre=dict(prestate=dict(root={},maintenance_before={}))
            held=[]
            class Guard:
                def __init__(self,path,**kwargs):self.root=path;self.intent={'observed_prestate':1};self.restored=False;self.control=self
                def __enter__(self):self.root.mkdir();held.append(self);events.append('guard');return self
                def verify(self):assert not self.restored
                def read(self):return 1 if self.restored else 0
                def restore(self):self.restored=True;events.append('guard-restored')
                def unlock(self):events.append('guard-unlocked')
            def prepare(_):
                events.append('isolation')
                if failure=='rearm':raise ValueError('rearm failed')
                io.save(isolation/'prospective-prestate.json',pre);return pre
            def restore(_):
                events.append('isolation-restored')
                if failure=='restoration':raise ValueError('restore failed')
                io.save(q/'restoration.json',dict(verified=True))
            clock=types.SimpleNamespace(Q=q,CG=e/'absent-cgroup',BINDINGS={'isolation_config':{'evidence_root':str(isolation)}},
                ISO=types.SimpleNamespace(prepare=prepare,verify_remaining_lifetime=lambda *a:None),
                retain=io.save,isolated_state=lambda:{'partition':{'cgroup.procs':''}},
                preparation=lambda:pre,root_state=lambda:{},restore=restore)
            class Process:
                pid=11
                def poll(self):return 1 if failure==self.role else 0
            class Owned:
                forced=[];leader_ticks=1
                def __init__(self,argv,log,native,protect_native):
                    self.role=argv[argv.index('--role')+1];self.process=Process();self.process.role=self.role;events.append(self.role)
                    if self.role=='sign-collect':
                        assert not held[0].restored
                        native=e/'native';native.mkdir()
                        request=io.save(out/'request.json',dict(attempt_id='a',evidence_root_binding={'absolute_path':str(native)},
                            action_inputs={'hardware_control':{'prestate':[]}}))
                        io.save(out/'prepared.json',dict(request=request,authorization={'sha256':'a'*64}))
                        io.save(native/'stage17-q16c-completion-v6.json',{'test_only':True})
                    elif self.role=='suffix':
                        assert held[0].restored and 'guard-unlocked' in events
                        assert io.document(io.binding(e/'q16c-study-d298-1/partition-restoration.json'))['verified']
                        analysis=e/'q16c-analysis-1';analysis.mkdir()
                        io.save(analysis/'finalized.json',{'status':'ALL_180_VALID_DESCRIPTIVE_COMPLETE'})
                def wait(self,deadline):return self.process.poll()
                def stop(self,deadline):events.append('stop-'+self.role)
            h=types.SimpleNamespace(subreaper=lambda:None,descendants=lambda p:{},start_ticks=lambda p:1,
                OwnedProcess=Owned,Study=types.SimpleNamespace(bounded_restore=lambda state:state.restore()))
            terminal=types.SimpleNamespace(restoration_status=lambda *a,**k:dict(executor_completed=True,hardware_restoration_verified=True))
            t=time.monotonic_ns();record={'started_monotonic_ns':t,'global_deadline_ns':t+86400*10**9}
            def admit(*a):events.append('admission');return record
            real_text=Path.read_text
            stack.enter_context(patch.object(study,'E',e));stack.enter_context(patch.object(current,'DEADLINE',t+39380*10**9))
            stack.enter_context(patch.object(current,'check_time'));stack.enter_context(patch.object(current,'admit',side_effect=admit))
            stack.enter_context(patch.object(study,'module',side_effect=lambda name,b:clock if name=='d298_rearm_isolation' else terminal))
            stack.enter_context(patch.object(study.os,'geteuid',return_value=0));stack.enter_context(patch.object(study.os,'chown'))
            stack.enter_context(patch.object(study.os,'sched_setaffinity'))
            stack.enter_context(patch.object(study.os,'statvfs',return_value=types.SimpleNamespace(f_bavail=10**15,f_frsize=1)))
            stack.enter_context(patch.object(Path,'read_text',lambda p,*a,**k:'MemAvailable: 250000000 kB\n' if str(p)=='/proc/meminfo' else real_text(p,*a,**k)))
            stack.enter_context(patch.object(study.signal,'signal'))
            stack.enter_context(patch.object(hardware,'_read',return_value=0));stack.enter_context(patch.object(hardware,'verify',return_value=[]))
            stack.enter_context(patch.object(hardware,'restore',side_effect=lambda _:events.append('hardware-restored')))
            stack.enter_context(patch.object(controls,'Guard',Guard))
            stack.enter_context(patch.object(integration,'export_witness',side_effect=lambda guard:({},__import__('os').open('/dev/null',0))))
            try:study.run(args,cfg,h)
            except ValueError:pass
            result=io.document(io.binding(e/'d298-study-1/result.json'))
        return events,result

    def test_success_rearms_once_restores_before_analysis_and_never_requalifies(self):
        events,result=self.scenario();self.assertTrue(result['success'],result)
        self.assertEqual(events,['admission','guard','isolation','sign-collect','hardware-restored',
                                 'isolation-restored','guard-restored','guard-unlocked','suffix'])

    def test_rearm_failure_prevents_collection_and_attempts_restoration(self):
        events,result=self.scenario('rearm');self.assertFalse(result['success'])
        self.assertNotIn('sign-collect',events);self.assertNotIn('suffix',events);self.assertIn('guard-restored',events)

    def test_collection_failure_stops_and_restores_without_suffix(self):
        events,result=self.scenario('sign-collect');self.assertFalse(result['success'])
        self.assertIn('stop-sign-collect',events);self.assertIn('isolation-restored',events);self.assertNotIn('suffix',events)

    def test_restoration_failure_is_retained_and_blocks_analysis(self):
        events,result=self.scenario('restoration');self.assertFalse(result['success'])
        self.assertNotIn('suffix',events);self.assertIn('restoration',str(result['errors']))


if __name__=='__main__':unittest.main()
