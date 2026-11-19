"""D288 prospective-input and operator I/O regression checks; no experiments."""
import copy
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16c_continuation_plan_v1 as plans
import stage17_q16c_continuation_operator_v1 as io
import stage17_q16c_continuation_recovery_v1 as recovery
import stage17_q16c_continuation_study_v1 as study
import stage17_q16c_prefix_operator_v1 as prefix


def actual_packet_constructor(evidence):
    """Load the exact deployed consumer body, without executing its imports/main.

    Constructor file reads, boot comparison and deadlines are real. Only native
    action methods are replaced by the sequence harness below.
    """
    fixture=ROOT/'tests/fixtures/stage17/d292-qualification-handoff'
    provenance=json.loads((fixture/'provenance.json').read_bytes())
    raw=(fixture/provenance['test_fixture']).read_bytes();binding=provenance['source_member']
    if len(raw)!=binding['size_bytes'] or hashlib.sha256(raw).hexdigest()!=binding['sha256']:
        raise AssertionError('actual deployed qualification consumer fixture differs')
    if binding['sha256']!='58845d94dbe52c3d69dd1a5c984611aea2f8667b2cb621028717d19368122025':
        raise AssertionError('unreviewed qualification consumer fixture')
    tree=ast.parse(raw,filename=str(fixture/provenance['test_fixture']))
    selected=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))
              and node.name in ('require','Packet')]
    if len(selected)!=2:raise AssertionError('actual packet constructor and require expected')
    scope=dict(__name__='actual_deployed_qualification_consumer',json=json,time=time,E=evidence)
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(fixture/provenance['test_fixture']),'exec'),scope)
    return scope['Packet']


class OperatorIO(unittest.TestCase):
    def test_exclusive_durable_publication_and_readback(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'record.json';b=io.save(path,dict(value='actual',execution_authority=False))
            self.assertEqual(io.document(b),dict(value='actual',execution_authority=False))
            with self.assertRaises(FileExistsError):io.save(path,dict(value='replacement'))
            self.assertEqual(io.document(b)['value'],'actual')

    def test_changed_bytes_fail_before_parse(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'record.json';b=io.save(path,dict(value=1))
            path.write_text('{"value":2}')
            with self.assertRaisesRegex(ValueError,'digest'):io.document(b)

    def test_fifo_and_symlink_cannot_block_or_be_accepted(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fifo=root/'fifo';os.mkfifo(fifo)
            b=dict(path=str(fifo),size_bytes=1,sha256='0'*64)
            for reader in (io.read,prefix.read):
                with self.assertRaises(ValueError):reader(b)
            target=root/'record';target.write_bytes(b'1');link=root/'link';link.symlink_to(target)
            b=dict(path=str(link),size_bytes=1,sha256=hashlib.sha256(b'1').hexdigest())
            for reader in (io.read,prefix.read):
                with self.assertRaisesRegex(ValueError,'nonsymlink'):reader(b)

    def test_process_reuse_and_zombie_are_not_live_owned_processes(self):
        h=type('H',(),dict(start_ticks=staticmethod(lambda pid:123)))
        for state,ticks,expected in (('S',123,True),('S',124,False),('Z',123,False),('X',123,False)):
            fields=[state]+['0']*18+['123']
            with patch.object(Path,'read_text',return_value='44 (a name with spaces) '+' '.join(fields)):
                self.assertEqual(recovery.live(h,44,ticks),expected)

    def test_exact_approved_role_ceilings_cover_42860_seconds(self):
        self.assertEqual(study.ROLES,dict(prefix=3600,qualification=7200,construct=1200,
            **{'sign-collect':24860},restoration=2400,suffix=3600))
        self.assertEqual(sum(study.ROLES.values()),42860)


class ActualProspectivePlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/stage17-q16c-d282/prospective-plan.json'
        if not parent.is_file():raise unittest.SkipTest('incident-bound original plan fixture not provisioned')
        cls.raw=parent.read_bytes();cls.parent=json.loads(cls.raw)
        cls.parent_binding=dict(path='/retained/original-plan.json',size_bytes=len(cls.raw),sha256=hashlib.sha256(cls.raw).hexdigest())
        cls.failure=dict(path='/retained/failure.json',size_bytes=plans.contract.FAILURE_SIZE,sha256=plans.contract.FAILURE_SHA256)
        cls.source='721d018908e0ada3373e577ff5b9aa3ed0095a64'

    def prospective(self):
        return plans.prospective(self.raw,parent_binding=self.parent_binding,failure_binding=self.failure,
            source_revision=self.source,implementation_profile_sha256=self.parent['storage']['implementation_profile_sha256'],
            monitor_path_replacements=[])

    def test_retains_only94_original_positions_with_all_scientific_inputs(self):
        actual=self.prospective()
        self.assertEqual(len(actual['captures']),94)
        self.assertEqual(actual['source_transport']['descriptor_count'],188)
        self.assertEqual(actual['budget']['watchdog_ns'],24860*10**9)
        self.assertEqual(actual['plan_id'],'CPU-PREFETCH-V5-V31-Q16C-PREFIX86-CONTINUATION-1')
        self.assertFalse(actual['execution_authority'])
        for local,(row,old) in enumerate(zip(actual['captures'],self.parent['captures'][86:],strict=True)):
            self.assertEqual(row['capture']['schedules'],old['capture']['schedules'])
            self.assertEqual(row['capture']['geometry'],old['capture']['geometry'])
            for phase,letter in (('warmup','W'),('measurement','M')):
                self.assertEqual(row['capture'][phase]['seed_hex'],old['capture'][phase]['seed_hex'])
                self.assertEqual(row['capture'][phase]['run_id'],f'C31{letter}{local+86:08d}')
                self.assertEqual(len(row['capture'][phase]['run_id']),len(old['capture'][phase]['run_id']))
            self.assertEqual(row['capture']['ordinal'],local)
            for key in ('warmup_ns','measurement_ns','package','rate_scale','budget'):
                if key in old['capture']:self.assertEqual(row['capture'][key],old['capture'][key])

    def test_parent_or_failed_incident_cannot_be_substituted(self):
        kwargs=dict(parent_binding=self.parent_binding,failure_binding=self.failure,source_revision=self.source,
            implementation_profile_sha256=self.parent['storage']['implementation_profile_sha256'],monitor_path_replacements=[])
        with self.assertRaisesRegex(ValueError,'exact original incident'):plans.prospective(self.raw+b'\n',**kwargs)
        kwargs['failure_binding']=dict(self.failure,sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'bound parent'):plans.prospective(self.raw,**kwargs)

    def test_original_source_or_alternative_identity_family_rejected(self):
        kwargs=dict(parent_binding=self.parent_binding,failure_binding=self.failure,
            implementation_profile_sha256=self.parent['storage']['implementation_profile_sha256'],monitor_path_replacements=[])
        with self.assertRaisesRegex(ValueError,'actual clean new'):plans.prospective(self.raw,source_revision=plans.contract.PARENT_SOURCE,**kwargs)
        with self.assertRaisesRegex(ValueError,'one approved fresh'):plans.prospective(self.raw,source_revision=self.source,id_prefix='EXTRA',**kwargs)

    def test_construct_rejects_input_changes_before_any_data_dependent_read(self):
        for key,change in (('captures',lambda v:v.pop()),('budget',lambda v:v.update(watchdog_ns=24861*10**9)),
                           ('source_transport',lambda v:v.update(descriptor_count=360))):
            with self.subTest(key=key):
                p=self.prospective();change(p[key])
                with self.assertRaisesRegex(ValueError,'frozen prospective inputs changed'):
                    plans.construct(p,self.raw,accepted_prefix_manifest={},compatibility_manifest={})

    def test_final_plan_requires_all86_valid_reports_and_matching_actual_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);p=self.prospective()
            def prefix_doc(valid=True):
                return dict(schema_version='cpu-prefetch-stage17-q16c-accepted-prefix86/1',parent_plan=self.parent_binding,
                    reused_capture_ordinals=list(range(86)),all_required_reports_valid=valid,compaction_control='UNRECORDED')
            a=io.save(d/'prefix.json',prefix_doc(False))
            b=io.save(d/'compat.json',dict(schema_version=plans.compatibility_contract.SCHEMA,
                parent_plan_sha256=plans.contract.PARENT_SHA256,current=dict(source_revision=self.source)))
            with self.assertRaisesRegex(ValueError,'actual complete accepted prefix'):
                plans.construct(p,self.raw,accepted_prefix_manifest=a,compatibility_manifest=b)
            a=io.save(d/'prefix-valid.json',prefix_doc())
            result=plans.construct(p,self.raw,accepted_prefix_manifest=a,compatibility_manifest=b)
            self.assertEqual(result['method_id'],'MATRIX-FULL-DESCRIPTIVE-CONTINUED-PLATFORM-STRATA-v1')
            self.assertEqual(len(result['captures']),94)
            self.assertEqual(result['continuation']['original_first_ordinal'],86)
            result['captures'][0]['capture']['warmup']['seed_hex']='0'*64
            self.assertNotEqual(result['captures'],p['captures'])


class IndependentRecovery(unittest.TestCase):
    def scenario(self, *, hold_native=False, root_alive=False, wrong_configuration=False):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        e=Path(tmp.name);root=e/'d292-study-1';root.mkdir()
        digest='a'*64
        io.save(root/'intent.json',dict(configuration_sha256='b'*64 if wrong_configuration else digest,
            supervisor_pid=99,supervisor_start_ticks=7))
        io.save(root/'owned-process-snapshot.json',dict(configuration_sha256=digest,owner_pid=12,owner_start_ticks=2,
            processes=[dict(pid=11,start_ticks=1),dict(pid=12,start_ticks=2)]))
        alive={11:1,12:2}
        if root_alive:alive[99]=7
        events=[]
        native=(10,'c'*64)
        def send(pid,ticks,sig,**kwargs):
            self.assertEqual(alive[pid],ticks)
            events.append((pid,sig.name))
            if pid!=11 or not hold_native or sig.name=='SIGKILL':alive.pop(pid)
        h=types.SimpleNamespace(descendants=lambda pid:{},executable_identity=lambda pid:native if pid==11 else (20,'d'*64),
            send_pidfd=send)
        c=dict(cgroup=str(e/'absent-cgroup'),native_images=[dict(size_bytes=native[0],sha256=native[1])],repository_root=str(ROOT))
        args=types.SimpleNamespace(configuration_sha256=digest)
        timer=iter(range(0,10**18,10**12))
        with patch.object(study,'E',e),patch.object(recovery.os,'geteuid',return_value=0),patch.object(recovery.os,'chown'),\
             patch.object(recovery,'live',side_effect=lambda core,pid,ticks:alive.get(pid)==ticks),\
             patch.object(recovery.time,'monotonic_ns',side_effect=lambda:next(timer)),patch.object(recovery.time,'sleep'):
            result=recovery.recover(args,c,h)
        return result,events,io.document(io.binding(e/'d292-independent-recovery-1.json'))

    def test_native_is_signalled_before_its_owner(self):
        result,events,retained=self.scenario()
        self.assertTrue(result['verified']);self.assertEqual(result,retained)
        self.assertEqual(events,[(11,'SIGTERM'),(12,'SIGTERM')])

    def test_forced_native_cleanup_never_claims_success(self):
        result,events,_=self.scenario(hold_native=True)
        self.assertFalse(result['verified'])
        self.assertEqual(events[:2],[(11,'SIGTERM'),(11,'SIGKILL')])
        self.assertEqual(events[-1],(12,'SIGTERM'))
        self.assertTrue(any('forced native' in e for e in result['errors']))

    def test_live_original_root_cannot_be_recovered_or_signalled(self):
        result,events,_=self.scenario(root_alive=True)
        self.assertFalse(result['verified']);self.assertEqual(events,[])

    def test_foreign_configuration_cannot_signal_processes(self):
        result,events,_=self.scenario(wrong_configuration=True)
        self.assertFalse(result['verified']);self.assertEqual(events,[])

    def test_real_pidfd_cleanup_and_dead_holder_lease_restoration(self):
        import importlib.util
        import os
        import subprocess
        import time
        import stage17_locked_compaction_guard_v1 as controls
        core=ROOT/'build/stage17-q16c-d282/collection-packet-3/original_supervisor.py'
        if not core.exists():self.skipTest('frozen ownership core not provisioned')
        spec=importlib.util.spec_from_file_location('d288_test_real_pidfd_core',core)
        h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
        with tempfile.TemporaryDirectory() as d:
            e=Path(d);root=e/'d292-study-1';root.mkdir();control=e/'software-control';control.write_text('1')
            lease=e/'software-lease';guard=e/'platform-guard-1'
            class Control:
                def boot(self):return Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                def read(self):return int(control.read_text())
                def write(self,value):control.write_text(str(value))
            # A short-lived real holder leaves a durable occupied lease.
            pid=os.fork()
            if pid==0:
                try:
                    controls.Guard(guard,deadline_ns=time.monotonic_ns()+30*10**9,control=Control(),lease=lease).__enter__()
                    os._exit(0)
                except BaseException:os._exit(1)
            _,status=os.waitpid(pid,0);self.assertEqual(os.waitstatus_to_exitcode(status),0)
            self.assertEqual(control.read_text(),'0');self.assertGreater(lease.stat().st_size,0)
            native=subprocess.Popen(['/usr/bin/sleep','20'],start_new_session=True)
            script=("import pathlib,time; p=pathlib.Path('/proc/"+str(native.pid)+"/stat'); "
                "\nfor i in range(100):\n"
                " try: s=p.read_text().rsplit(')',1)[1].split()[0]\n"
                " except FileNotFoundError: break\n"
                " if s in ('Z','X','x'): break\n"
                " time.sleep(.05)\n")
            owner=__import__('subprocess').Popen([sys.executable,'-B','-c',script],start_new_session=True)
            try:
                ticks={p.pid:h.start_ticks(p.pid) for p in (native,owner)}
                io.save(root/'intent.json',dict(configuration_sha256='a'*64,supervisor_pid=pid,supervisor_start_ticks=1))
                io.save(root/'owned-process-snapshot.json',dict(configuration_sha256='a'*64,owner_pid=owner.pid,
                    owner_start_ticks=ticks[owner.pid],processes=[dict(pid=p,start_ticks=t) for p,t in ticks.items()]))
                image=h.executable_identity(native.pid)
                c=dict(cgroup=str(e/'absent-cgroup'),native_images=[dict(size_bytes=image[0],sha256=image[1])],repository_root=str(ROOT))
                original=controls.recover
                with patch.object(study,'E',e),patch.object(recovery.os,'geteuid',return_value=0),patch.object(recovery.os,'chown'),\
                     patch.object(controls,'recover',side_effect=lambda path:original(path,control=Control(),lease=lease)):
                    result=recovery.recover(types.SimpleNamespace(configuration_sha256='a'*64),c,h)
                self.assertTrue(result['verified'],result)
                self.assertEqual(native.wait(timeout=3),-15)
                self.assertEqual(owner.wait(timeout=3),0)
                self.assertEqual(result['signalled_owner'],[])
                self.assertEqual(control.read_text(),'1');self.assertEqual(lease.stat().st_size,0)
                self.assertTrue((guard/'restoration.json').exists())
            finally:
                for process in (native,owner):
                    if process.poll() is None:process.kill()
                    process.wait(timeout=3)


class SupervisorSequence(unittest.TestCase):
    """Run the actual root orchestration against finite software collaborators.

    Nothing here supplies runtime admission or empirical evidence. The checks
    exercise phase order, failure stops and restoration boundaries directly.
    """
    def test_wrong_root_unit_cannot_start_the_approved_window(self):
        from contextlib import ExitStack
        import stage17_hardware_recovery_v1 as hardware
        with tempfile.TemporaryDirectory() as d,ExitStack() as stack:
            e=Path(d);c=dict(repository_root=str(ROOT),supervisor_unit='cpu-prefetch-d292-v31-1.service')
            h=types.SimpleNamespace(descendants=lambda pid:{},subreaper=lambda:None)
            args=types.SimpleNamespace(configuration_sha256='a'*64)
            original=Path.read_text
            def text(path,*a,**k):
                if str(path)=='/proc/meminfo':return 'MemAvailable: 250000000 kB\n'
                if str(path)=='/proc/self/cgroup':return '0::/outside.service\n'
                return original(path,*a,**k)
            stack.enter_context(patch.object(study,'E',e));stack.enter_context(patch.object(Path,'read_text',text))
            stack.enter_context(patch.object(study.os,'geteuid',return_value=0));stack.enter_context(patch.object(study.os,'chown'))
            stack.enter_context(patch.object(study.os,'sched_setaffinity'))
            stack.enter_context(patch.object(study.os,'statvfs',return_value=types.SimpleNamespace(f_bavail=10**15,f_frsize=1)))
            stack.enter_context(patch.object(hardware,'_read',return_value=0))
            sign=stack.enter_context(patch.object(study,'sign_window'))
            with self.assertRaisesRegex(ValueError,'outside its dedicated study unit'):study.run(args,c,h)
            sign.assert_not_called()

    def scenario(self,failure=None,*,real_packet=False,packet_boot='software-test-boot'):
        from contextlib import ExitStack
        import stage17_hardware_recovery_v1 as hardware
        import stage17_locked_compaction_guard_v1 as controls
        import stage17_q16c_compaction_integration_v2 as guarded
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        e=Path(tmp.name);events=[];out=e/'prepared';out.mkdir();packet=e/'operators';packet.mkdir()
        c=dict(repository_root=str(ROOT),evidence_root=str(e),output_root=str(out),cgroup=str(e/'absent-cgroup'),
            worker=dict(size_bytes=10,sha256='c'*64),qualification_packet=str(packet),qualification_inventory=dict(sha256='a'*64))
        io.save(packet/'finite-qualification-plan.json',dict(qualification_budget_seconds=7200,
            release=dict(boot_id=packet_boot),q15_quiescence_seconds=2100))
        args=types.SimpleNamespace(configuration=e/'configuration.json',configuration_sha256='b'*64)
        guard_states=[]
        class Guard:
            def __init__(self,path,**kwargs):self.root=path;self.intent=dict(observed_prestate=1);self.held=False;self.restored=False;self.control=self
            def __enter__(self):self.root.mkdir();self.held=True;guard_states.append(self);events.append('guard-acquire');return self
            def verify(self):self.assert_held();return dict(verified=True)
            def assert_held(self):assert self.held and not self.restored
            def read(self):return 1 if self.restored else 0
            def restore(self):events.append('guard-restore');self.restored=True
            def unlock(self):self.held=False;events.append('guard-unlock')
        qroot=e/'clock';qroot.mkdir()
        pre=dict(prestate=dict(root={},maintenance_before={}))
        def restore(_):io.save(qroot/'restoration.json',dict(verified=True));events.append('isolation-restore')
        clock=types.SimpleNamespace(Q=qroot,CG=e/'absent-cgroup',preparation=lambda:pre,root_state=lambda:{},restore=restore)
        consumer=actual_packet_constructor(e) if real_packet else object
        class Packet(consumer):
            def __init__(self,*args):
                if real_packet:
                    super().__init__(*args)
                    anchor=io.document(io.binding(e/'continuation-window-1.json'))
                    assert time.monotonic()<self.deadline<=anchor['qualification_deadline_monotonic_ns']/10**9
                    assert self.cleanup_seconds==2100 and self.session is None
            def step(self,name):events.append(name)
            def qualify(self,actual):
                events.append('qualification');guard_states[0].assert_held()
                if failure=='qualification':raise RuntimeError('qualification failed')
        qualification=types.SimpleNamespace(verify_packet=lambda *a,**k:dict(files=[]),Packet=Packet)
        class Process:
            pid=11
            def poll(self):return 1 if failure==self.role else 0
        class Owned:
            forced=[];leader_ticks=1
            def __init__(self,argv,log,native,protect_native):
                self.role=argv[argv.index('--role')+1];self.process=Process();self.process.role=self.role
                events.append(self.role)
                if self.role=='prefix':
                    p=e/'q16c-prefix-analysis-1';p.mkdir()
                    io.save(p/'accepted-prefix.json',dict(all_required_reports_valid=failure!='prefix-invalid',reused_capture_ordinals=list(range(86))))
                elif self.role=='sign-collect':
                    guard_states[0].assert_held();native=e/'working';native.mkdir()
                    request=io.save(out/'request.json',dict(attempt_id='a',evidence_root_binding=dict(absolute_path=str(native)),
                        action_inputs=dict(hardware_control=dict(prestate=[]))))
                    io.save(out/'prepared.json',dict(request=request,authorization=dict(sha256='a'*64)))
                    io.save(native/'stage17-q16c-completion-v6.json',dict(test_only=True))
                elif self.role=='suffix':
                    assert guard_states[0].restored and not guard_states[0].held
                    assert io.document(io.binding(e/'q16c-study-1/partition-restoration.json'))['verified']
                    p=e/'q16c-analysis-1';p.mkdir();io.save(p/'finalized.json',dict(status='ALL_180_VALID_DESCRIPTIVE_COMPLETE'))
            def wait(self,deadline):return self.process.poll()
            def stop(self,deadline):events.append('stop-'+self.role)
        h=types.SimpleNamespace(subreaper=lambda:None,descendants=lambda pid:{},start_ticks=lambda pid:1,OwnedProcess=Owned,
            Study=types.SimpleNamespace(bounded_restore=lambda state:state.restore()))
        def window(_):
            import time
            t=time.monotonic_ns();return dict(started_monotonic_ns=t,global_deadline_ns=t+86400*10**9,
                boot_id='software-test-boot')
        terminal=types.SimpleNamespace(restoration_status=lambda *a,**k:dict(executor_completed=True,hardware_restoration_verified=True))
        def hardware_restore(_):
            events.append('hardware-restore')
            if failure=='restoration':raise RuntimeError('restoration failed')
        c['terminal_reader']={}
        mem='MemAvailable: 250000000 kB\n';read_text=Path.read_text
        def text(path,*a,**k):return mem if str(path)=='/proc/meminfo' else read_text(path,*a,**k)
        with ExitStack() as stack:
            stack.enter_context(patch.object(study,'E',e));stack.enter_context(patch.object(study,'sign_window',side_effect=window))
            stack.enter_context(patch.object(study,'module',return_value=terminal))
            stack.enter_context(patch.object(study.os,'geteuid',return_value=0));stack.enter_context(patch.object(study.os,'chown'))
            stack.enter_context(patch.object(study.os,'sched_setaffinity'));stack.enter_context(patch.object(study.os,'statvfs',return_value=types.SimpleNamespace(f_bavail=10**15,f_frsize=1)))
            stack.enter_context(patch.object(Path,'read_text',text));stack.enter_context(patch.object(study.signal,'signal'))
            stack.enter_context(patch.object(hardware,'_read',return_value=0));stack.enter_context(patch.object(hardware,'restore',side_effect=hardware_restore))
            stack.enter_context(patch.object(hardware,'verify',return_value=[]));stack.enter_context(patch.object(controls,'Guard',Guard))
            stack.enter_context(patch.object(guarded,'export_witness',side_effect=lambda guard:({},__import__('os').open('/dev/null',0))))
            stack.enter_context(patch.dict(sys.modules,{'run_qualification_v31':qualification,'run_clock_qualification_v31':clock}))
            try:study.run(args,c,h)
            except (RuntimeError,ValueError):pass
        return events,io.document(io.binding(e/'d292-study-1/result.json'))

    def test_success_preserves_order_and_restores_before_suffix(self):
        events,result=self.scenario();self.assertTrue(result['success'],result)
        for first,second in (('prefix','guard-acquire'),('guard-acquire','qualification'),('qualification','construct'),
                             ('construct','sign-collect'),('sign-collect','hardware-restore'),('isolation-restore','guard-restore'),
                             ('guard-restore','guard-unlock'),('guard-unlock','suffix')):
            self.assertLess(events.index(first),events.index(second))

    def test_actual_packet_constructor_accepts_the_supervisors_published_handoff(self):
        events,result=self.scenario(real_packet=True)
        self.assertTrue(result['success'],result)
        self.assertEqual(events.count('qualification'),1)
        self.assertLess(events.index('qualification'),events.index('construct'))

    def test_actual_packet_constructor_rejects_foreign_boot_and_restores_before_any_action(self):
        events,result=self.scenario(real_packet=True,packet_boot='foreign-software-test-boot')
        self.assertFalse(result['success'])
        self.assertIn('global window boot changed',' '.join(result['errors']))
        self.assertNotIn('qualification',events);self.assertNotIn('construct',events)
        self.assertNotIn('sign-collect',events);self.assertIn('guard-restore',events)

    def test_preserved_failed_handoff_reproduces_the_actual_consumer_key_error(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            original=ROOT/'docs/evidence/stage17/Q16C-D292-PREFIX-VALIDATED-STOP-20261119-01/continuation-window-1.json'
            (root/'continuation-window-1.json').write_bytes(original.read_bytes())
            cls=actual_packet_constructor(root)
            with self.assertRaisesRegex(KeyError,'boot_id'):
                cls(dict(files=[]),dict(release=dict(boot_id='software-test-boot')))

    def test_invalid_prefix_stops_before_guard_or_qualification(self):
        events,result=self.scenario('prefix-invalid');self.assertFalse(result['success'])
        self.assertNotIn('guard-acquire',events);self.assertNotIn('qualification',events);self.assertNotIn('sign-collect',events)

    def test_qualification_failure_prevents_construction_and_collection(self):
        events,result=self.scenario('qualification');self.assertFalse(result['success'])
        self.assertNotIn('construct',events);self.assertNotIn('sign-collect',events);self.assertNotIn('suffix',events)
        self.assertIn('guard-restore',events)

    def test_collection_failure_stops_owner_then_restores_and_never_analyzes(self):
        events,result=self.scenario('sign-collect');self.assertFalse(result['success'])
        self.assertLess(events.index('stop-sign-collect'),events.index('hardware-restore'))
        self.assertNotIn('suffix',events)

    def test_failed_restoration_blocks_suffix(self):
        events,result=self.scenario('restoration');self.assertFalse(result['success']);self.assertNotIn('suffix',events)

    def test_suffix_failure_reaps_analysis_without_restart(self):
        events,result=self.scenario('suffix');self.assertFalse(result['success'])
        self.assertIn('stop-suffix',events);self.assertEqual(events.count('sign-collect'),1);self.assertEqual(events.count('suffix'),1)


if __name__=='__main__':unittest.main()
