"""Real bounded file reads; explicit kernel/qualification/package test doubles."""
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_platform_v1 as platform
import test_stage17_s180_environment_v1 as hardware_tests
import s180_compaction_fixture


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.hardware=hardware_tests.EnvironmentTests();self.hardware.setUp();self.addCleanup(self.hardware.doCleanups)
        self.io=self.hardware.io();self.io.__enter__();self.addCleanup(self.io.close)
        self.archive,self.env,self.qp,self.compat=platform._modules()
        for row in self.hardware.plan['captures']:
            row['monitoring']['environment_sources']=[dict(path=str(self.env.CG/name)) for name in
                ('cpuset.cpus','cpuset.cpus.effective','cpuset.cpus.exclusive','cpuset.cpus.partition','cpuset.mems.effective')]
        self.blueprint=self.hardware.plan['blueprint'];self.static=copy.deepcopy(platform._request()['requested_static_platform'])
        self.tree=self.hardware.root/'kernel';self.tree.mkdir();self.kernel_paths=set()
        def put(name,value):
            self.kernel_paths.add(name)
            path=self.tree/name.lstrip('/');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value+'\n')
        self.put=put;put('/proc/sys/kernel/random/boot_id',self.hardware.window['boot_id'])
        put('/sys/devices/system/cpu/online','0-31')
        cpuinfo=[]
        def cpus(values):return ','.join(map(str,values))
        for row in self.static['cpus']:
            cpu=row['cpu'];root=f'/sys/devices/system/cpu/cpu{cpu}'
            cpuinfo.append('\n'.join(f'{k}: {v}' for k,v in dict(processor=cpu,vendor_id=row['vendor'],
                **{'cpu family':row['family']},model=row['model'],microcode=row['microcode'],flags=' '.join(row['flags'])).items()))
            for name,value in dict(physical_package_id=row['package_id'],core_id=row['core_id'],
                    thread_siblings_list=cpus(row['thread_siblings']),core_siblings_list=cpus(row['package_cpus'])).items():
                put(root+'/topology/'+name,str(value))
            for level,cache in row['caches'].items():
                for name,value in dict(level=level,type='Unified',size=str(cache['size_bytes']//1024)+'K',
                        coherency_line_size=cache['cache_line_bytes'],shared_cpu_list=cpus(cache['shared_cpus'])).items():
                    put(root+'/cache/index'+level+'/'+name,str(value))
            for name,value in row['frequency_policy'].items():put(root+'/cpufreq/'+name,str(value))
        put('/proc/cpuinfo','\n\n'.join(cpuinfo))
        for row in self.static['nodes']:
            root=f"/sys/devices/system/node/node{row['node']}"
            put(root+'/cpulist',cpus(row['cpus']));put(root+'/distance',' '.join(map(str,row['distances'])))
        put('/proc/self/mountinfo','1 0 0:1 / / rw - rootfs rootfs rw')
        controls=self.static['controls'];put('/proc/sys/kernel/numa_balancing',str(controls['numa_balancing']))
        put('/sys/kernel/mm/transparent_hugepage/enabled','always ['+controls['thp_enabled']+'] never')
        put('/sys/kernel/mm/transparent_hugepage/defrag','always ['+controls['thp_defrag']+'] never')
        put('/sys/devices/system/clocksource/clocksource0/current_clocksource',controls['clocksource'])
        real_open=os.open
        def opened(path,flags,*args,**kwargs):
            if str(path) in self.kernel_paths:path=self.tree/str(path).lstrip('/')
            return real_open(path,flags,*args,**kwargs)
        self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(platform.os,'open',side_effect=opened))
        self.snapshot=self.observe();self.request=platform.request_from_observation(self.snapshot,stand_id=self.blueprint['stand_id'])
        self.stack.enter_context(mock.patch.object(platform,'_request',side_effect=lambda:copy.deepcopy(self.request)))
        start=time.monotonic_ns();self.hardware.window=dict(boot_id=self.snapshot['boot_id'],
            start_monotonic_ns=start,end_monotonic_ns=start+self.env.planning.DAY_NS)
        import stage17_s180_compaction_v1 as compaction
        self.hardware.plan=compaction.monitored_plan(self.hardware.plan)
        self.hardware.sha=self.env.planning.sha(self.hardware.plan);self.owner=self.hardware.guard()
        s180_compaction_fixture.attach(self,self.owner,self.hardware.root)
        self.qualified=object.__new__(self.qp._VerifiedEvidence)
        self.qualified.owner=SimpleNamespace(prepared=SimpleNamespace(owner=self.owner),proof=lambda **kw:dict(
            plan_sha256=self.hardware.sha,stand_id=self.blueprint['stand_id']))
        self.software=object.__new__(self.compat._VerifiedCompatibility)
        self.base=SimpleNamespace(resolutions={'S17-EXT-002':SimpleNamespace(semantic_context=dict(stand_id=self.blueprint['stand_id']))})
        self.bindings=[dict(input_id=f'S17-EXT-{i:03d}',
            resolution_id=f'explicit-software-ancestor-{i}',sha256=hashlib.sha256(str(i).encode()).hexdigest()) for i in range(1,8)]
        self.qual_proof=dict(plan_sha256=self.hardware.sha,base_resolutions=copy.deepcopy(self.bindings),
            dynamic_qualification_verified=True,measurement_runtime_binding=dict(sha256=self.qp.q15.compaction.NATIVE_SHA,
                size_bytes=self.qp.q15.compaction.NATIVE_SIZE),qualification_sha256='a'*64,window_binding=self.hardware.window)
        self.software_proof=dict(base_resolutions=copy.deepcopy(self.bindings),software_compatibility_verified=True,
            current_source_revision=self.env.NATIVE_REVISION,files=[])
        for row in self.compat._review()['libraries']:
            if row['library'] in ('queue','workload'):
                for side in ('original','current'):
                    self.software_proof['files'].append(dict(row[side],path='/software/'+side+'/'+Path(row[side]['path']).name))
        # These external producers have their own real-process/D340 integration
        # suites. Only their readiness boundary is doubled here; no stand proof.
        self.stack.enter_context(mock.patch.object(self.qualified,'proof',side_effect=lambda **kw:copy.deepcopy(self.qual_proof)))
        self.stack.enter_context(mock.patch.object(self.software,'proof',side_effect=lambda **kw:copy.deepcopy(self.software_proof)))

    def observe(self):return platform.observe(deadline_ns=time.monotonic_ns()+30*10**9)

    def assess(self,snapshot=None,request=None):
        return platform.assess(snapshot or self.snapshot,blueprint=self.blueprint,platform_request=request or self.request)

    def verify(self,**changes):
        args=dict(plan=self.hardware.plan,environment_owner=self.owner,qualification_owner=self.qualified,
            compatibility_owner=self.software,base_validation=self.base,deadline_ns=time.monotonic_ns()+30*10**9)
        args.update(changes);return platform.verify_platform(**args)

    def test_collector_reads_real_fixture_bytes_and_records_actual_controls(self):
        snapshot=self.observe();self.assertEqual(len(snapshot['kernel_readings']),85)
        self.assertEqual(snapshot['static_platform'],self.static)
        self.assertEqual(snapshot['static_platform']['controls']['numa_balancing'],1)
        self.assertEqual(snapshot['static_platform']['controls']['thp_enabled'],'madvise')
        for row in snapshot['kernel_readings']:
            raw=(self.tree/row['path'].lstrip('/')).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256']);self.assertEqual(len(raw),row['size_bytes'])
        self.assertFalse(snapshot['qualification_performed']);self.assertFalse(snapshot['execution_authority'])

    def test_all_six_full_footprint_boundaries_match_without_merging_calibration(self):
        derived=self.assess();self.assertEqual([r['verified_geometry']['capacity'] for r in derived['contexts']],
            [512,65536,1048576]*2)
        self.assertEqual(derived['contexts'][0]['footprint']['linked_full_bytes'],69952)
        for key in ('instantaneous_residency_guaranteed','remote_llc_added','calibration_platform_strata_merged'):
            self.assertIs(derived[key],False)

    def test_requested_and_actual_controls_are_distinct_and_drift_rejects(self):
        snapshot=copy.deepcopy(self.snapshot);snapshot['static_platform']['controls']['numa_balancing']=0
        with self.assertRaisesRegex(platform.PlatformError,'requested and actual'):self.assess(snapshot)
        self.assertEqual(self.request['requested_static_platform']['controls']['numa_balancing'],1)

    def test_invalid_physical_topology_cache_or_numa_does_not_pass_with_matching_request(self):
        mutations=[lambda s:s.update(base_page_bytes=8192),lambda s:s.update(online_cpus=[0,1,8]),
            lambda s:s['cpus'][1].update(core_id=s['cpus'][0]['core_id']),
            lambda s:s['cpus'][3].update(thread_siblings=[8,25]),
            lambda s:s['cpus'][3].update(model=85),lambda s:s['nodes'][0]['cpus'].append(8),
            lambda s:(s['nodes'][0]['cpus'].remove(16),s['nodes'][1]['cpus'].append(16)),
            lambda s:s['nodes'][1].update(distances=[1,10]),
            lambda s:s['cpus'][0]['caches']['2'].update(shared_cpus=[0,1,16,17]),
            lambda s:s['cpus'][1]['caches']['3'].update(size_bytes=2**30),
            lambda s:s['cpus'][3]['caches']['3'].update(shared_cpus=s['cpus'][0]['package_cpus']),
            lambda s:s.update(resctrl_mounted=True),lambda s:s['cpus'][0]['flags'].append('cat_l3')]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                snapshot=copy.deepcopy(self.snapshot);mutation(snapshot['static_platform'])
                request=platform.request_from_observation(snapshot,stand_id=self.blueprint['stand_id'])
                with self.assertRaises(platform.PlatformError):self.assess(snapshot,request)

    def test_actual_cache_that_changes_selection_cannot_change_the_frozen_matrix(self):
        snapshot=copy.deepcopy(self.snapshot)
        for row in snapshot['static_platform']['cpus']:row['caches']['2']['size_bytes']=1024**2
        request=platform.request_from_observation(snapshot,stand_id=self.blueprint['stand_id'])
        with self.assertRaisesRegex(platform.PlatformError,'frozen requested capacity'):self.assess(snapshot,request)

    def test_collector_rejects_missing_symlinked_or_oversized_kernel_data(self):
        path=self.tree/'sys/devices/system/cpu/cpu0/cache/index2/size';raw=path.read_bytes();path.unlink()
        with self.assertRaises(FileNotFoundError):self.observe()
        target=self.hardware.root/'outside';target.write_bytes(raw);path.symlink_to(target)
        with self.assertRaises(OSError):self.observe()
        path.unlink();path.write_bytes(b'x'*4097)
        with self.assertRaisesRegex(platform.PlatformError,'byte bound'):self.observe()

    def test_collector_rejects_changed_boot_and_expired_or_unbounded_lease(self):
        real_read=os.read;boot_reads=0
        def changing(fd,size):
            nonlocal boot_reads
            data=real_read(fd,size)
            if data.strip()==self.hardware.window['boot_id'].encode():
                boot_reads+=1
                if boot_reads==2:return b'other-boot\n'
            return data
        with mock.patch.object(platform.os,'read',side_effect=changing):
            with self.assertRaisesRegex(platform.PlatformError,'boot changed'):self.observe()
        for deadline in (time.monotonic_ns()-1,time.monotonic_ns()+121*10**9):
            with self.assertRaises(platform.PlatformError):platform.observe(deadline_ns=deadline)

    def test_numeric_cpu_and_policy_parsers_reject_ambiguous_values(self):
        for value in ('','0,,1','1-0','0,0','4096','0,1-2,2'):
            with self.assertRaises(platform.PlatformError):platform._cpus(value)
        for value in ('01','-1','1.0',str(2**64)):
            with self.assertRaises(platform.PlatformError):platform._number(value)
        for value in ('always madvise never','[always] [never]'):
            with self.assertRaises(platform.PlatformError):platform._selected(value)

    def test_owned_gate_rechecks_live_inputs_and_keeps_original_report_stable(self):
        owner=self.verify();original=owner.report();first=json.loads(original)
        proof=owner.proof(plan_sha256=self.hardware.sha)
        self.assertTrue(proof['current_geometry_and_regime_verified'])
        self.assertFalse(proof['full_platform_inventory_verified'])
        self.assertEqual(proof['platform_evidence_sha256'],hashlib.sha256(original).hexdigest())
        self.assertEqual(owner.report(),original)
        self.assertGreater(proof['observation']['completed_monotonic_ns'],first['observation']['completed_monotonic_ns'])
        self.assertLess(len(original),platform.MAX_REPORT_BYTES)
        for key in ('full_ext008_admission','execution_authority','phase18_authority'):self.assertIs(proof[key],False)
        self.assertEqual(proof['base_resolutions'],self.bindings)
        self.assertTrue(self.hardware.restore(self.owner)['hardware_restoration_verified'])

    def test_changed_control_latches_restoration_even_if_original_bytes_return(self):
        owner=self.verify();path='/proc/sys/kernel/numa_balancing';self.put(path,'0')
        with self.assertRaisesRegex(platform.PlatformError,'requested and actual'):owner.proof(plan_sha256=self.hardware.sha)
        self.put(path,'1')
        with self.assertRaisesRegex(platform.PlatformError,'failed'):owner.proof(plan_sha256=self.hardware.sha)
        self.assertTrue(self.owner._qualification_failed)

    def test_changed_actual_msr_prestate_or_producer_ancestry_rejects(self):
        self.hardware.set_value(8,1)
        with self.assertRaisesRegex(self.env.EnvironmentError,'MSR prestate'):self.verify()
        self.assertTrue(self.owner._qualification_failed)

    def test_unrelated_qualification_environment_or_release_ancestry_rejects(self):
        self.qualified.owner.prepared.owner=object()
        with self.assertRaisesRegex(platform.PlatformError,'another environment'):self.verify()
        self.qualified.owner.prepared.owner=self.owner;self.owner._qualification_failed=False
        self.software_proof['base_resolutions'][0]['sha256']='0'*64
        with self.assertRaisesRegex(platform.PlatformError,'ancestry'):self.verify()

    def test_unqualified_images_and_self_reported_prerequisites_do_not_admit(self):
        for key in ('environment_owner','qualification_owner','compatibility_owner'):
            with self.assertRaisesRegex(platform.PlatformError,'actual owned'):self.verify(**{key:{'PASS':True}})
        self.qual_proof['measurement_runtime_binding']['sha256']='0'*64
        with self.assertRaisesRegex(platform.PlatformError,'native differs'):self.verify()

    def test_prospective_request_must_precede_the_original_operational_window(self):
        self.request['observed_completed_monotonic_ns']=self.hardware.window['start_monotonic_ns']
        with self.assertRaisesRegex(platform.PlatformError,'window boundary'):self.verify()

    def test_retained_footprint_requires_both_original_and_current_actual_library_bindings(self):
        self.software_proof['files'][0]['sha256']='0'*64
        with self.assertRaisesRegex(platform.PlatformError,'footprint queue/workload ABI'):self.verify()

    def test_failed_fixed_request_preparation_latches_the_active_environment(self):
        with mock.patch.object(platform,'_request',side_effect=platform.PlatformError('changed fixed request')):
            with self.assertRaisesRegex(platform.PlatformError,'changed fixed request'):self.verify()
        self.assertTrue(self.owner._qualification_failed)

    def test_original_admitted_stand_must_match_current_qualified_stand(self):
        self.base.resolutions['S17-EXT-002'].semantic_context['stand_id']='another-stand'
        with self.assertRaisesRegex(platform.PlatformError,'stand identity differs'):self.verify()

    def test_wrong_plan_latches_without_extending_lease(self):
        owner=self.verify()
        with self.assertRaisesRegex(platform.PlatformError,'original platform plan'):owner.proof(plan_sha256='f'*64)
        self.assertTrue(self.owner._qualification_failed)

    def test_expired_metadata_lease_cannot_be_used_again(self):
        owner=self.verify();owner.deadline=time.monotonic_ns()-1
        with self.assertRaisesRegex(platform.PlatformError,'metadata deadline'):owner.proof(plan_sha256=self.hardware.sha)
        self.assertTrue(self.owner._qualification_failed)


class FixedInputTests(unittest.TestCase):
    def test_actual_prospective_request_and_retained_footprint_are_pinned(self):
        request=platform._request();self.assertEqual(request['stand_id'],'CPU-PREFETCH-V5')
        self.assertEqual(request['requested_static_platform']['controls']['numa_balancing'],1)
        self.assertEqual(platform._footprints()['conditional_selected'],[512,65536,1048576])

    def test_report_cannot_construct_the_owned_gate(self):
        with self.assertRaisesRegex(platform.PlatformError,'actual live'):
            platform._VerifiedPlatform(token=object(),plan={},request={},environment_owner=None,qualification_owner=None,
                compatibility_owner=None,base=None,deadline=0)

    def test_altered_prospective_request_is_rejected_before_any_platform_action(self):
        original=Path(platform.__file__).resolve().parents[1]/platform.REQUEST
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'changed-request.json';path.write_bytes(original.read_bytes()+b' ')
            with mock.patch.object(platform,'REQUEST',str(path)):
                with self.assertRaisesRegex(platform.PlatformError,'exact prospective platform request'):platform._request()


if __name__=='__main__':unittest.main()
