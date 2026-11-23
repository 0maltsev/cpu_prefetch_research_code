"""Actual cold native/layout and locked store tests; platform fixtures are not science."""
import argparse
import copy
import ctypes
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import struct
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_resource_admission_v1 as gate
from test_stage17_s180_plan_prepare_v1 import fixture
import test_stage17_s180_environment_v1 as environment_tests
import test_stage17_s180_archive_broker_v1 as broker_tests
import stage17_s180_compaction_v1 as compaction
import s180_compaction_fixture


class ResourceTests(unittest.TestCase):
    worker=None

    @classmethod
    def setUpClass(cls):
        raw=cls.worker.read_bytes();cls.image=gate.runtime.ImageBinding(cls.worker,len(raw),hashlib.sha256(raw).hexdigest())
        cls.revision=json.loads(subprocess.check_output([str(cls.worker),'--stage17-s180-runtime-identity-v1']))['source_revision']
        sizing=fixture(cls.revision)
        for entry in sizing['captures']:
            entry['monitoring']['environment_sources']=[dict(path=str(gate.environment.CG/name),byte_capacity=8192,
                chunk_bytes=4096,max_data_reads=18,requested=[True]*6) for name in ('cpuset.cpus','cpuset.cpus.effective',
                'cpuset.cpus.exclusive','cpuset.cpus.partition','cpuset.mems.effective')]
        sizing=compaction.monitored_plan(sizing)
        sizing['budget'].update(memory_bytes=64*gate.GIB,max_output_bytes=2*1024**4)
        cls.lib=ctypes.CDLL(str(Path(os.environ.get('STAGE17_TEST_ZSTD_LIBRARY','/usr/lib64/libzstd.so.1.5.7')).resolve()))
        cls.lib.ZSTD_compressBound.argtypes=[ctypes.c_size_t];cls.lib.ZSTD_compressBound.restype=ctypes.c_size_t
        first=gate.planning.native_layouts(sizing,worker=cls.image,deadline_ns=time.monotonic_ns()+30*10**9)
        bounded,_=gate.prospective.bound_packet(sizing,first,compress_bound=cls.lib.ZSTD_compressBound)
        cls.plan,_=gate.planning.prepare(bounded,worker=cls.image,deadline_ns=time.monotonic_ns()+30*10**9)
        cls.report=gate.planning.native_layouts(bounded,worker=cls.image,deadline_ns=time.monotonic_ns()+30*10**9)
        cls.envelope,cls.process,cls.timing=gate._arithmetic(cls.plan,cls.report,compress_bound=cls.lib.ZSTD_compressBound)

    def setUp(self):
        self.plan=copy.deepcopy(self.__class__.plan)
        self.limits=gate.launcher.LaunchLimits(64*gate.GIB,64*gate.GIB,2*1024**4,1024,16384,10*10**9,7200*10**9)
        self.custody=gate.custody.CustodyLimits(131072,500000,500000,2*1024**2,time.monotonic_ns()+120*10**9)
        self.observed=dict(base_page_bytes=4096,memory_available_bytes=256*gate.GIB,memory_ancestors=[],
            rlimit_as=[4*gate.GIB,-1],rlimit_memlock=[8388608,64*gate.GIB],rlimit_nofile=[1024,1024],highest_observed_fd=100)
        self.unrelated=dict(reserved_bytes=compaction.METADATA_RESERVE_BYTES+4*1024**2,
            reserved_inodes=compaction.METADATA_RESERVE_INODES+40,declaration_sha256='d'*64,
            workspace_committed_bytes=0,scratch_committed_bytes=0)

    def test_all_retained_joined_outputs_are_reserved_in_workspace(self):
        analysis=gate.prospective.analysis_output_envelope(self.plan)
        rows=sorted(self.plan['blueprint']['captures'],key=lambda r:r['execution_ordinal'])
        expected=0
        for row,entry in zip(rows,self.plan['captures'],strict=True):
            for i,phase in enumerate(entry['phases']):
                run=row['warmup_run_id' if i==0 else 'run_id']
                # Independent physical record equation:24 U64 fields after
                # length-prefixed UTF-8 run identity, rounded to whole words.
                row_bytes=((4+len(run.encode('utf-8'))+7)//8)*8+24*8
                expected+=phase['offered_count']*row_bytes
        self.assertEqual(analysis['joined_logical_bytes_upper'],expected)
        self.assertEqual(analysis['captures'],180)
        self.assertGreaterEqual(analysis['required_inodes'],180*18)
        self.assertFalse(analysis['resource_admission_performed'])
        self.assertEqual(sum(r['maximum_output_bytes'] for r in analysis['capture_bounds']),
            analysis['workspace_bytes_upper'])
        space,_,_=gate.capacity_plan(self.plan,self.envelope,self.custody,
            workspace_committed_bytes=0,scratch_committed_bytes=0)
        self.assertGreaterEqual(space.control_and_final_bytes,expected)

    def test_joined_output_and_old_workspace_scratch_cannot_exceed_policy(self):
        analysis=gate.prospective.analysis_output_envelope(self.plan)
        space,_,_=gate.capacity_plan(self.plan,self.envelope,self.custody,
            workspace_committed_bytes=0,scratch_committed_bytes=0)
        snapshot=gate.custody.CapacitySnapshot(10**13,1000000,0,0,0,0)
        gate.custody.check_capacity(snapshot,space)
        used=space.canonical_capture_bytes+space.control_and_final_bytes+space.publication_staging_bytes+space.archive_staging_bytes
        old_work=gate.custody.WORKSPACE-used+1
        bad,_,_=gate.capacity_plan(self.plan,self.envelope,self.custody,
            workspace_committed_bytes=old_work,scratch_committed_bytes=0)
        with self.assertRaisesRegex(gate.custody.CustodyError,'workspace'):
            gate.custody.check_capacity(snapshot,bad)
        bad,_,_=gate.capacity_plan(self.plan,self.envelope,self.custody,
            workspace_committed_bytes=0,scratch_committed_bytes=gate.custody.SCRATCH-space.analysis_spool_bytes+1)
        with self.assertRaisesRegex(gate.custody.CustodyError,'spool'):
            gate.custody.check_capacity(snapshot,bad)
        # Isolate precisely the old omission: everything except joined output
        # fits W, but retaining every analysis result takes it over W by1 byte.
        baseline=gate.custody.WORKSPACE-analysis['workspace_bytes_upper']+1
        envelope=dict(self.envelope,maximum_capture_workspace_bytes=baseline//2)
        altered=dict(self.plan,budget=dict(self.plan['budget'],final_metadata_bytes=baseline%2),
            storage=dict(self.plan['storage'],archive_staging_bytes=0))
        bad,_,_=gate.capacity_plan(altered,envelope,self.custody,
            workspace_committed_bytes=0,scratch_committed_bytes=0)
        with self.assertRaisesRegex(gate.custody.CustodyError,'workspace'):
            gate.custody.check_capacity(snapshot,bad)

    def test_analysis_reservation_requires_original_order_and_explicit_usage(self):
        changed=copy.deepcopy(self.plan);changed['captures'][0],changed['captures'][1]=changed['captures'][1],changed['captures'][0]
        with self.assertRaises((gate.prospective.ResourcePlanError,gate.planning.PlanError)):
            gate.prospective.analysis_output_envelope(changed)
        for key in ('workspace_committed_bytes','scratch_committed_bytes'):
            values=dict(workspace_committed_bytes=0,scratch_committed_bytes=0);values[key]=-1
            with self.assertRaises(gate.archive.ArchiveError):
                gate.capacity_plan(self.plan,self.envelope,self.custody,**values)
        root,_=self.store_fixture()
        old=dict(self.unrelated);del old['workspace_committed_bytes'];del old['scratch_committed_bytes']
        with self.assertRaisesRegex(gate.ResourceError,'explicit other workspace and scratch'):
            self.storage(root,unrelated=old)
        with self.assertRaisesRegex(gate.custody.CustodyError,'workspace'):
            self.storage(root,unrelated=dict(self.unrelated,workspace_committed_bytes=gate.custody.WORKSPACE))

    def assess(self,observed=None):
        gate.assess_platform(self.observed if observed is None else observed,process_envelope=self.process,native_limits=self.limits)

    def test_actual_native_layout_and_complete_exact_count_bounds(self):
        self.assertEqual(len(self.report['captures']),180)
        self.assertEqual(self.process['native_resource_minima']['retained_source_vector_bytes'],36*4*8)
        self.assertEqual(self.envelope['count_ceiling_method'],'EXACT-DECLARED-ORIGINAL-SOURCE-COUNTS-v1')
        self.assess()
        self.assertLessEqual(self.timing['total_declared_stage_caps_ns'],gate.planning.DAY_NS)

    def test_wrong_layout_foreign_report_and_insufficient_bound_reject(self):
        for mutate in (lambda p:p['captures'][0]['expected_layout'].update(total_mapping_bytes=1),
            lambda p:p['captures'][0]['execution_budget'].update(max_output_bytes=1),
            lambda p:p['storage'].update(archive_staging_bytes=1)):
            changed=copy.deepcopy(self.plan);mutate(changed)
            # Query its actual cold input where possible; either native contract
            # rejection or independent resource comparison must block it.
            with self.assertRaises((gate.ResourceError,gate.planning.PlanError)):
                report=gate.planning.native_layouts(gate._sizing(changed),worker=self.image,
                    deadline_ns=time.monotonic_ns()+30*10**9)
                gate._arithmetic(changed,report,compress_bound=self.lib.ZSTD_compressBound)
        report=copy.deepcopy(self.report);report['sizing_plan_sha256']='f'*64
        with self.assertRaises(gate.ResourceError):gate._arithmetic(self.plan,report,compress_bound=self.lib.ZSTD_compressBound)

    def test_physical_memory_and_every_finite_ancestor_are_required(self):
        bad=copy.deepcopy(self.observed);bad['memory_available_bytes']=1
        with self.assertRaisesRegex(gate.ResourceError,'physical available'):self.assess(bad)
        bad=copy.deepcopy(self.observed);bad['memory_ancestors']=[dict(path='software-parent',maximum_bytes=1,current_bytes=0)]
        with self.assertRaisesRegex(gate.ResourceError,'finite memory ancestor'):self.assess(bad)
        bad['memory_ancestors']=[dict(path='software-parent',maximum_bytes=None,current_bytes=0)]
        self.assess(bad)

    def test_parent_limit_lock_inheritance_fd_and_geometry_fail_closed(self):
        for key,value in (('rlimit_as',[-1,-1]),('rlimit_as',[8*gate.GIB,-1]),
            ('rlimit_memlock',[8388608,8388608]),('rlimit_nofile',[64,64]),
            ('highest_observed_fd',1020),('base_page_bytes',8192)):
            bad=copy.deepcopy(self.observed);bad[key]=value
            with self.assertRaises(gate.ResourceError):self.assess(bad)

    def test_actual_platform_observation_is_read_only_and_keeps_requested_state_separate(self):
        before=gate.resource.getrlimit(gate.resource.RLIMIT_AS)
        actual=gate.platform_observation()
        self.assertEqual(actual['pid'],os.getpid());self.assertGreater(actual['memory_available_bytes'],0)
        self.assertEqual(gate.resource.getrlimit(gate.resource.RLIMIT_AS),before)
        self.assertNotIn('resource_admission_status',actual)

    def store_fixture(self):
        temp=tempfile.TemporaryDirectory(prefix='s180-resource-store-',dir=Path(__file__).resolve().parents[1]/'build')
        self.addCleanup(temp.cleanup);root=Path(temp.name)/'program'
        scope=gate.custody.ProgramStore.initialize(root,program_id=self.plan['storage']['program_id'],
            storage_domain_id='software-filesystem',prospective_admission_sha256='a'*64)
        self.plan['storage']['program_scope_sha256']=scope
        family=gate.planning.sha(self.plan)
        with gate.stores.ProgramStore(root,scope_sha256=scope,family_id=family,limits=self.custody,
            ext009_resolution_sha256=None) as store:store.reserve_family()
        return root,family

    def storage(self,root,limits=None,unrelated=None,free=None):
        fs=SimpleNamespace(f_bavail=10**13 if free is None else free,f_frsize=1,f_favail=1000000)
        with mock.patch.object(gate.os,'statvfs',return_value=fs):
            return gate._storage(self.plan,self.envelope,limits or self.custody,root,unrelated or self.unrelated)

    def test_real_locked_reservation_and_unchanged_ledger(self):
        root,family=self.store_fixture();before={p.name:p.read_bytes() for p in (root/'ledger').iterdir()}
        result=self.storage(root)
        self.assertEqual(result['evidence_root_binding']['inode'],(root/'working'/family).stat().st_ino)
        self.assertEqual(result['ledger_records'],1);self.assertEqual(result['prospective_ledger_records'],9016)
        self.assertEqual(before,{p.name:p.read_bytes() for p in (root/'ledger').iterdir()})
        self.assertFalse((root/'metadata'/('s180-admission-'+family+'.json')).exists())

    def test_future_ledger_inventory_full_family_quota_and_free_space(self):
        root,_=self.store_fixture()
        for limits in (replace(self.custody,max_ledger_records=10),replace(self.custody,max_inventory_files=10)):
            with self.assertRaises((gate.ResourceError,gate.custody.CustodyError)):self.storage(root,limits=limits)
        with self.assertRaises(gate.custody.CustodyError):self.storage(root,free=1)
        with self.assertRaises(gate.custody.CustodyError):
            self.storage(root,unrelated=dict(self.unrelated,reserved_bytes=10**13))
        original=self.envelope
        with mock.patch.dict(self.envelope,archive_family_upper_bytes=gate.custody.PROGRAM_QUOTA):
            with self.assertRaisesRegex(gate.ResourceError,'complete family'):self.storage(root)

    def test_consumed_attempt_or_native_evidence_blocks_admission(self):
        root,family=self.store_fixture();marker=root/'metadata'/gate.parent._attempt_name(family)
        marker.write_text('retained interrupted attempt')
        with self.assertRaisesRegex(gate.ResourceError,'already consumed'):self.storage(root)
        marker.unlink();(root/'working'/family/'s180-session-entry.json').write_text('retained original')
        with self.assertRaisesRegex(gate.ResourceError,'predates resource'):self.storage(root)

    def test_live_handle_cannot_be_constructed_from_a_report_or_fake_owner(self):
        with self.assertRaisesRegex(gate.ResourceError,'actual owned'):
            gate.verify_resources(plan=self.plan,environment_owner={},source_owner={},worker=self.image,
                archive_profile={},program_root=Path('/unused'),native_limits=self.limits,custody_limits=self.custody,
                unrelated_reservations=self.unrelated,deadline_ns=time.monotonic_ns()+10**9,programme_owner=None)
        with self.assertRaisesRegex(gate.ResourceError,'only actual resource'):
            gate._VerifiedResources(token=object(),plan={},environment_owner=None,source_owner=None,worker=None,
                archive_profile=None,program_root='/unused',native_limits=None,custody_limits=None,deadline=1,
                envelope=None,process=None,timing=None,initial=None,unrelated_reservations=None)

    def live_fixture(self):
        """Real owned descriptor/store/codec flow with explicit software hardware.

        Private source construction supplies tiny software bytes, not accepted
        generator credit. The production API has no fixture/backend selector.
        Frozen-image constants are patched only for portable dev-image coverage.
        """
        hardware=environment_tests.EnvironmentTests();hardware.setUp();self.addCleanup(hardware.doCleanups)
        for entry in self.plan['captures']:
            for row in entry['monitoring']['environment_sources']:
                if '/cpuset.' in row['path']:row['path']=str(hardware.cg/Path(row['path']).name)
        root=hardware.root
        codec=broker_tests.ArchiveFixture(root).profile
        image=broker_tests.image
        profile=gate.runtime.RuntimeProfile(image(self.worker),image(sys.executable),
            replace(codec,encoder_sha256=image(self.worker).sha256),broker_tests.qualified_closure())
        # No encoder command runs in admission. This software image is hashed
        # independently, while real codec compressBound runs from the pinned library.
        self.plan['storage']['implementation_profile_sha256']=profile.decoder.implementation_profile_sha256
        self.plan,_=gate.planning.prepare(gate._sizing(self.plan),worker=self.image,deadline_ns=time.monotonic_ns()+30*10**9)
        program,family=self.store_fixture()
        environment=gate.environment._PreparedEnvironment(token=gate.environment._TOKEN,plan=self.plan,
            window=hardware.window,core=hardware.core,preparation=hardware.pre,devices=hardware.devices,
            affinity=hardware.affinity,command_state=dict(deadline=hardware.window['end_monotonic_ns']))
        groups,order=gate.planning.source_groups(gate._sizing(self.plan));bindings=[];raw=struct.pack('>4Q',1,2,2,3)
        for key in order:
            for phase in groups[key]:
                fd=gate.runtime._sealed_input(raw,'software-resource-source')
                bindings.append(dict(descriptor=fd,size_bytes=len(raw),artifact_id=phase['source_artifact']['artifact_id'],
                    canonical_sha256=hashlib.sha256(raw).hexdigest()))
        source=gate.sources._VerifiedSources(token=gate.sources._TOKEN,report=dict(plan_sha256=family),bindings=bindings,
            originals={},maximum_vector_bytes=4096,valid_until_ns=hardware.window['end_monotonic_ns'],
            maximum_loading_ns=self.plan['budget']['setup_ns'])
        self.addCleanup(lambda:None if source._closed else source._close())
        io=hardware.io();self.addCleanup(io.close);io.__enter__()
        s180_compaction_fixture.attach(self,environment,root)
        for name,value in (('NATIVE_SHA',self.image.sha256),('NATIVE_SIZE',self.image.size_bytes)):
            patch=mock.patch.object(gate,name,value);patch.start();self.addCleanup(patch.stop)
        patch=mock.patch.object(gate.environment,'NATIVE_REVISION',self.revision);patch.start();self.addCleanup(patch.stop)
        observed=dict(self.observed,boot_id=hardware.window['boot_id'])
        platform=mock.patch.object(gate,'platform_observation',side_effect=lambda:copy.deepcopy(observed))
        platform.start();self.addCleanup(platform.stop)
        fs=mock.patch.object(gate.os,'statvfs',return_value=SimpleNamespace(f_bavail=10**13,f_frsize=1,f_favail=1000000))
        fs.start();self.addCleanup(fs.stop)
        programme=self.enterContext(gate.admission_custody.own_programme(plan=self.plan,window_binding=hardware.window,
            program_root=program,custody_limits=self.custody,deadline_ns=self.custody.deadline_ns,
            preparation_deadline_ns=self.custody.deadline_ns))
        owner=gate.verify_resources(plan=self.plan,environment_owner=environment,source_owner=source,worker=self.image,
            archive_profile=profile,program_root=program,native_limits=self.limits,custody_limits=self.custody,
            unrelated_reservations=self.unrelated,deadline_ns=min(self.custody.deadline_ns,time.monotonic_ns()+60*10**9),
            programme_owner=programme)
        prior=dict(scope_id=gate.authority.PLAN_SCOPE,plan_sha256=family,window_binding=hardware.window,
            evidence_root_binding=dict(absolute_path=str(program/'working'/family),device=program.stat().st_dev,
                inode=(program/'working'/family).stat().st_ino),
            runtime_binding=dict(role=gate.authority.ROLE,profile=gate.authority.PROFILE,sha256=self.image.sha256,size_bytes=self.image.size_bytes),
            release_binding=dict(source_revision=self.revision,worker_sha256=self.image.sha256),phase18_authority=False)
        resolutions={f'S17-EXT-{i:03d}':SimpleNamespace(semantic_context={}) for i in range(1,9)}
        resolutions['S17-EXT-008'].semantic_context=prior
        view=gate.journal.JournalView(resolutions,'a'*64,1,False)
        payload=dict(resource_proof_sha256=hashlib.sha256(owner.report()).hexdigest())
        return owner,payload,view,source,environment,observed

    def test_live_original_transaction_rechecks_sources_storage_and_returns_only_scoped_context(self):
        owner,payload,view,source,environment,observed=self.live_fixture()
        context=owner('S17-EXT-009',payload,view,for_execution=True)
        self.assertEqual(context['resource_admission_status'],'ADMITTED')
        self.assertEqual(context['scope_id'],gate.authority.RESOURCE_SCOPE)
        self.assertFalse(context['phase18_authority']);self.assertFalse(environment._entry_used)
        self.assertFalse(json.loads(owner.report())['execution_authority'])
        source._close()
        with self.assertRaises(gate.sources.SourcesError):owner('S17-EXT-009',payload,view,for_execution=True)

    def test_changed_live_memory_latches_failure_even_if_memory_recovers(self):
        owner,payload,view,source,environment,observed=self.live_fixture()
        observed['memory_available_bytes']=1
        with self.assertRaisesRegex(gate.ResourceError,'physical available'):
            owner('S17-EXT-009',payload,view,for_execution=True)
        observed['memory_available_bytes']=256*gate.GIB
        with self.assertRaisesRegex(gate.ResourceError,'no automatic retry'):
            owner('S17-EXT-009',payload,view,for_execution=True)

    def test_q15_external_metadata_cannot_be_omitted_from_admission(self):
        self.unrelated.update(reserved_bytes=compaction.METADATA_RESERVE_BYTES,
            reserved_inodes=compaction.METADATA_RESERVE_INODES)
        with self.assertRaisesRegex(gate.ResourceError,'recovery/Q15 metadata'):self.live_fixture()

    def test_foreign_evidence_and_prior_binding_cannot_admit_or_supply_historical_context(self):
        owner,payload,view,_,_,_=self.live_fixture()
        with self.assertRaisesRegex(gate.ResourceError,'historical replay requires'):
            owner('S17-EXT-009',payload,view,for_execution=False)
        with self.assertRaisesRegex(gate.ResourceError,'evidence binding'):
            owner('S17-EXT-009',dict(resource_proof_sha256='f'*64),view,for_execution=True)
        view._resolutions['S17-EXT-008'].semantic_context['plan_sha256']='f'*64
        with self.assertRaisesRegex(gate.ResourceError,'qualified plan/resource'):
            owner('S17-EXT-009',payload,view,for_execution=True)

    def test_original_deadline_is_not_renewed_by_semantic_replay(self):
        owner,payload,view,_,_,_=self.live_fixture();original=json.loads(owner.report())
        context=owner('S17-EXT-009',payload,view,for_execution=True)
        owner._deadline=time.monotonic_ns()-1
        with self.assertRaisesRegex(gate.ResourceError,'original resource deadline'):
            owner('S17-EXT-009',payload,view,for_execution=True)
        self.assertEqual(json.loads(owner.report()),original)
        self.assertEqual(owner('S17-EXT-009',payload,view,for_execution=False),context)
        with self.assertRaisesRegex(gate.ResourceError,'no automatic retry'):
            owner('S17-EXT-009',payload,view,for_execution=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',type=Path,required=True)
    args,rest=parser.parse_known_args();ResourceTests.worker=args.worker.resolve();unittest.main(argv=[sys.argv[0],*rest])
