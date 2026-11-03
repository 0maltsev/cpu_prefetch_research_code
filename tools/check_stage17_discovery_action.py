"""Synthetic signed discovery lifecycle; no live qualification or experiment."""
from __future__ import annotations

import copy
import contextlib
import io
import sys
import datetime as dt
import fcntl
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import tarfile
import types
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
import check_stage17_discovery_contract as fixtures
import stage17_discovery_contract_v1 as contract
import stage17_output_registry_v9 as registry
import stage17_phase_controller_v22 as controller
import stage17_operational_cli_v15 as cli
import stage17_fixed_action_executor_v8 as executor
import stage17_pilot_candidate_artifact_v9 as release
import stage17_semantic_verifier_v55 as semantic
import stage17_operational_semantics_v13 as operational

ROOT = pathlib.Path(__file__).resolve().parents[1]
NATIVE_WORKER = None


def bound(name, document):
    payload = registry.canonical(document)
    return dict(artifact_id=name, size_bytes=len(payload), sha256=registry.sha256(payload))


def native_documents(plan):
    resources, monitoring = [], []
    for cap in plan['captures']:
        g = cap['geometry']
        def stack(cpu, node):
            return dict(bytes=2*1024*1024, verified_base_page_bytes=4096,
                        owner_cpu=cpu, requested_node=node)
        sizes = [32768, 4096, 4096, 2*1024*1024, 2*1024*1024, 4096, 2*1024*1024]
        resources.append(dict(ordinal=cap['ordinal'], workers=dict(
            producer_stack=stack(g['producer_cpu'], g['producer_node']),
            consumer_stack=stack(g['consumer_cpu'], g['consumer_node'])),
            controller_stack=stack(2, 0), core_bytes=4096, monitor_bytes=4096,
            total_mapping_bytes=sum(sizes)+4096+3*4096, region_bytes=sizes,
            tls_module_capacity=8, thread_stat_bytes=4096, thread_status_bytes=4096,
            thread_affinity_words=4, initial_consumer_state=17))
        monitoring.append(dict(ordinal=cap['ordinal'], during_first_page=[0]*7,
            during_page_count=[1]*7, during_offset_ticks=[1000000]*2,
            observer_wait_poll_limit=1000000, control_region_index=5,
            counter_limits=[[dict(minor_faults=None, major_faults=0,
                voluntary_switches=None, involuntary_switches=None) for _ in range(2)] for _ in range(2)],
            hardware_identity=dict(family=6, model=62), environment_sources=[]))
    return (dict(schema_version='cpu-prefetch-discovery-resources/1', captures=resources),
            dict(schema_version='cpu-prefetch-discovery-monitoring/1', captures=monitoring))


class DiscoveryActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='discovery-action-test-')
        self.addCleanup(self.temp.cleanup)
        self.directory = pathlib.Path(self.temp.name)
        self.output = self.directory/'output'; self.output.mkdir(mode=0o700)
        self.evidence = self.directory/'evidence'; (self.evidence/'journal').mkdir(parents=True)
        self.journal = self.evidence/'journal/stage17-state-journal-000000.json'
        self.journal.write_text('{}')
        self.worker = self.directory/'worker'; shutil.copyfile('/usr/bin/true', self.worker); self.worker.chmod(0o500)
        self.plan = fixtures.fixture()
        self.plan['release'] = dict(artifact_id='worker', size_bytes=self.worker.stat().st_size,
                                   sha256=registry.sha256(self.worker.read_bytes()))
        resources, monitoring = native_documents(self.plan)
        docs = {name: {'synthetic': name} for name in ('stand', 'qualification', 'namespace_registry')}
        docs.update(resource_plan=resources, monitoring_plan=monitoring)
        for name, doc in docs.items():
            self.plan[name] = bound(name, doc)
        self.resolutions = {}
        for dep in self.plan['dependencies']:
            name = dep['resolution']['artifact_id']; doc = {'synthetic': name}
            docs[name] = doc; dep['resolution'] = bound(name, doc)
            self.resolutions[dep['input_id']] = types.SimpleNamespace(input_id=dep['input_id'],
                resolution_id=name, sha256=dep['resolution']['sha256'], semantic_context={})
        self.key = self.directory/'key'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(self.key)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        allowed = self.directory/'allowed-signers'
        allowed.write_text('synthetic-owner '+self.key.with_suffix('.pub').read_text())
        self.trust = dict(subject_id=self.plan['stand_id'], measurements=dict(
            principal='synthetic-owner',reviewer_role='OWNER',sshsig_namespace='stage17-owner-acceptance',
            stand_anchor_sha256=self.plan['stand']['sha256'],allowed_signers_path=str(allowed),
            allowed_signers_size_bytes=allowed.stat().st_size, allowed_signers_sha256=registry.sha256(allowed.read_bytes())))
        self.resolutions['S17-EXT-002'].semantic_context = dict(stand_id=self.plan['stand_id'])
        self.resolutions['S17-EXT-003'].semantic_context = dict(trust=self.trust)
        control = dict(mapping_id='INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1', q15_w_result_sha256='b'*64,
                       prestate=[dict(cpu=cpu,complete_value_hex='0000000000000000') for cpu in (0,1,8)])
        self.resolutions['S17-EXT-004'].semantic_context = dict(manifest_sha256=self.plan['qualification']['sha256'],
            hardware_mapping=dict(mapping_id=control['mapping_id'],prestate=control['prestate']))
        self.resolutions['S17-EXT-005'].semantic_context = dict(q15_w=dict(result_sha256='b'*64,
            request=dict(action_inputs=dict(prestate=control['prestate']))))
        self.resolutions['S17-EXT-006'].semantic_context = dict(supported_actions=list(release.SUPPORTED_ACTIONS),
            release_artifact_role='STAGE17_FIXED_ACTION_WORKER',runtime_profile='STAGE17-FIXED-ACTION-WORKER-v4',
            release_artifact_size_bytes=self.plan['release']['size_bytes'],release_artifact_sha256=self.plan['release']['sha256'],
            release_artifact_path=str(self.worker),source_revision=self.plan['source_revision'])
        self.inputs = dict(plan=self.plan,hardware_control=control,
            bound_documents=[dict(artifact_id=name,document=doc,utf8_bytes=registry.canonical(doc).decode()) for name,doc in docs.items()],
            native_captures=[dict(ordinal=i,resources=r,monitoring=m) for i,(r,m) in enumerate(
                zip(resources['captures'],monitoring['captures'],strict=True))])
        self.validation = types.SimpleNamespace(current_state='READY_FOR_STAGE17_PHASE_AUTHORIZATION',resolutions=self.resolutions)
        patcher = patch.object(controller.journal_runtime,'validate_operational_journal',return_value=self.validation)
        patcher.start(); self.addCleanup(patcher.stop)
        self.request_path = self.directory/'request.json'; self.auth_path = self.directory/'authorization.json'
        self.arguments = dict(repository_root=ROOT,operational_evidence_root=self.evidence,journal=self.journal,
            journal_directory=self.journal.parent,authorization_path=self.auth_path,
            signature_path=pathlib.Path(str(self.auth_path)+'.sig'),synthetic_test_only=True)

    def author(self):
        path = self.directory/'inputs.json'; path.write_bytes(registry.canonical(self.inputs))
        cli.author_request(repository_root=ROOT,evidence_root=self.evidence,action_inputs_path=path,
            request_id='request-1',authorization_id='authorization-1',attempt_id='attempt-1',session_id='session-1',
            output_root=self.output,destination=self.request_path,synthetic=True)
        now = dt.datetime.now(dt.timezone.utc)
        utc = lambda value: value.isoformat(timespec='seconds').replace('+00:00','Z')
        cli.author_authorization(repository_root=ROOT,evidence_root=self.evidence,request_path=self.request_path,
            actor='synthetic-owner',reviewer='OWNER',issued_at_utc=utc(now-dt.timedelta(seconds=1)),
            expires_at_utc=utc(now+dt.timedelta(seconds=250)),destination=self.auth_path,synthetic=True)
        self.sign()
        return controller.prepare_action(**self.arguments)

    def sign(self):
        self.arguments['signature_path'].unlink(missing_ok=True)
        subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(self.key),'-n','stage17-owner-acceptance',str(self.auth_path)],
                       check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

    def publish(self, prepared, argv, fds, *, global_deadline_ns, authority_guard):
        authority_guard()
        self.assertEqual(argv[1:3], ('--execute-fixed-stage17-action-v5',registry.ACTION))
        for fd in fds[:2]:
            self.assertTrue(fcntl.fcntl(fd,fcntl.F_GET_SEALS)&fcntl.F_SEAL_WRITE)
        self.assertEqual(os.pread(fds[0],len(prepared.request_bytes)+1,0),prepared.request_bytes)
        context = json.loads(os.pread(fds[1],1000000,0))
        self.assertEqual(context['session_deadline_seconds'],257)
        self.assertEqual(context['per_run_deadline_seconds'],11)
        artifacts = []
        def write(name, payload):
            (self.output/name).write_bytes(payload)
            role,schema,media = registry.artifact_identity(name)
            item = dict(file_name=name,size_bytes=len(payload),sha256=registry.sha256(payload),
                        role=role,schema_identity=schema,media_type=media)
            artifacts.append(item)
            return {k:item[k] for k in ('file_name','size_bytes','sha256')}
        captures = []
        for cap in self.plan['captures']:
            bindings = [write(name,b'{}\n' if name.endswith('.json') else b'') for name in registry.capture_names(cap['ordinal'])]
            captures.append(dict(ordinal=cap['ordinal'],warmup_run_id=cap['warmup']['run_id'],
                measurement_run_id=cap['measurement']['run_id'],artifacts=bindings,native_stop='trace_capacity',
                native_validity='INSUFFICIENT',failure_reasons=[]))
        hardware = write('studyhardware.json',b'{}\n')
        report = dict(schema_version='cpu-prefetch-stage17-discovery-retention-report/1',
            plan_sha256=contract.validate_plan(self.plan).sha256,captures=captures,hardware_state=hardware,
            diagnostic_only=True,scientific_validity='NOT_ASSESSED',eligible_for_duration_selection=False,
            formal_runs_contributed=0,execution_authority=False)
        write(registry.REPORT_NAME,registry.canonical(report))
        result = {key:prepared.request[key] for key in ('request_id','action_id','stand_id','authorization_id',
            'attempt_id','runtime_binding','release_binding','predecessor_resolutions','synthetic_test_only','phase18_authority')}
        result.update(schema_version='cpu-prefetch-stage17-phase-action-result/5',result_id='result-1',
            request_sha256=registry.sha256(prepared.request_bytes),authorization_sha256=registry.sha256(prepared.authorization_bytes),
            artifacts=artifacts,started_at_utc=controller.support._now(),completed_at_utc=controller.support._now(),
            duration_ns=1,terminal_state='DIAGNOSTIC_ARTIFACTS_RETAINED_UNASSESSED',restoration_verified=True,quarantined=False)
        (self.output/registry.RESULT_NAME).write_bytes(registry.canonical(result))
        return executor.predecessor.TransportOutcome(0,b'',b'',True,True,'SYNTHETIC_ALREADY_QUIESCENT')

    def run_mock(self, prepared, mutate=None):
        def worker(*args,**kwargs):
            result=self.publish(prepared,*args,**kwargs)
            if mutate: mutate()
            return result
        with patch.object(executor,'_run_worker',side_effect=worker):
            return controller.execute_once(**self.arguments)

    def test_signed_fd_lifecycle_retains_without_scientific_credit(self):
        prepared=self.author(); outcome=self.run_mock(prepared)
        report=cli.admit_retention(prepared,self.output)
        self.assertFalse(report['eligible_for_duration_selection'])
        self.assertEqual(len(report['captures']),36)
        self.assertTrue(outcome.completion['restoration_verified'])
        with self.assertRaisesRegex(executor.FixedActionExecutionError,'marker exists'):
            self.run_mock(prepared)

    def test_signature_and_expiry_fail_before_worker(self):
        self.author(); doc=json.loads(self.auth_path.read_bytes());doc['actor']='intruder'
        self.auth_path.write_bytes(registry.canonical(doc))
        with self.assertRaises(controller.ControllerError): controller.prepare_action(**self.arguments)
        doc['actor']='synthetic-owner'
        expiration=dt.datetime.fromisoformat(doc['expires_at_utc'].replace('Z','+00:00'))+dt.timedelta(seconds=1)
        doc['expires_at_utc']=expiration.isoformat(timespec='seconds').replace('+00:00','Z')
        self.auth_path.write_bytes(registry.canonical(doc))
        with self.assertRaisesRegex(controller.support.ControllerError,'signature'):
            controller.prepare_action(**self.arguments)
        doc['expires_at_utc']='2001-01-01T00:01:00Z';doc['issued_at_utc']='2001-01-01T00:00:00Z'
        self.auth_path.write_bytes(registry.canonical(doc));self.sign()
        with self.assertRaisesRegex(controller.ControllerError,'deadline'): controller.prepare_action(**self.arguments)
        self.assertEqual(list(self.output.iterdir()),[])

    def test_bound_document_and_native_drift(self):
        prepared=self.author()
        for field in ('bound_documents','native_captures'):
            with self.subTest(field=field):
                doc=copy.deepcopy(prepared.request)
                if field=='bound_documents': doc['action_inputs'][field][0]['document']['drift']=True
                else: doc['action_inputs'][field][0]['resources']['thread_stat_bytes']+=1
                with self.assertRaises(controller.ControllerError): controller.validate_action_inputs(doc,self.validation)

    def test_worker_hash_drift(self):
        self.author();self.worker.chmod(0o700);self.worker.write_bytes(b'changed')
        with self.assertRaises(controller.support.ControllerError): controller.prepare_action(**self.arguments)

    def test_mandatory_failure_retains_partial_and_no_completion(self):
        prepared=self.author()
        def bad():
            path=self.output/registry.REPORT_NAME; report=json.loads(path.read_bytes())
            report['captures'][0]['native_validity']='MANDATORY_FAILURE'; report['captures'][0]['failure_reasons']=['mandatory gate']
            payload=registry.canonical(report);path.write_bytes(payload)
            result_path=self.output/registry.RESULT_NAME;result=json.loads(result_path.read_bytes())
            item=next(a for a in result['artifacts'] if a['file_name']==registry.REPORT_NAME)
            item.update(size_bytes=len(payload),sha256=registry.sha256(payload));result_path.write_bytes(registry.canonical(result))
        with self.assertRaisesRegex(executor.FixedActionExecutionError,'diagnostic retention report'): self.run_mock(prepared,bad)
        self.assertTrue(list(self.output.glob('*failure-v5.json')))
        self.assertFalse(list(self.output.glob('*completion-v5.json')))
        self.assertTrue((self.output/'discovery-c00-control.json').exists())

    def test_retention_detects_bytes_and_live_readback_drift(self):
        prepared=self.author();self.run_mock(prepared)
        control=self.output/'discovery-c00-control.json';payload=control.read_bytes();control.write_bytes(b'changed')
        with self.assertRaises(registry.OutputAdmissionError):cli.admit_retention(prepared,self.output)
        control.write_bytes(payload)
        path=next(self.output.glob('*completion-v5.json'));doc=json.loads(path.read_bytes())
        doc['live_restoration_readback'][0]['observed_hex']='0000000000000001';path.write_bytes(registry.canonical(doc))
        with self.assertRaisesRegex(controller.ControllerError,'live restoration'):cli.admit_retention(prepared,self.output)

    def test_retention_stop_validity_pairs_are_exact(self):
        prepared=self.author();self.run_mock(prepared)
        report=json.loads((self.output/registry.REPORT_NAME).read_bytes())
        schema=json.loads((ROOT/registry.REPORT_SCHEMA).read_bytes())
        validator=Draft202012Validator(schema)
        accepted={('complete','VALID'),('complete','INSUFFICIENT'),('trace_capacity','INSUFFICIENT')}
        for stop in ('complete','trace_capacity','warmup_failure','unknown'):
            for validity in ('VALID','INSUFFICIENT','MANDATORY_FAILURE'):
                with self.subTest(stop=stop,validity=validity):
                    report['captures'][0].update(native_stop=stop,native_validity=validity)
                    self.assertEqual(validator.is_valid(report),(stop,validity) in accepted)

    def test_trace_capacity_valid_rejected_by_actual_admission(self):
        prepared=self.author()
        def bad():
            path=self.output/registry.REPORT_NAME;report=json.loads(path.read_bytes())
            report['captures'][0]['native_validity']='VALID'
            payload=registry.canonical(report);path.write_bytes(payload)
            result_path=self.output/registry.RESULT_NAME;result=json.loads(result_path.read_bytes())
            item=next(a for a in result['artifacts'] if a['file_name']==registry.REPORT_NAME)
            item.update(size_bytes=len(payload),sha256=registry.sha256(payload))
            result_path.write_bytes(registry.canonical(result))
        with self.assertRaisesRegex(executor.FixedActionExecutionError,'diagnostic retention report'):
            self.run_mock(prepared,bad)
        self.assertFalse(list(self.output.glob('*completion-v5.json')))

    def test_environment_storage_is_explicit_and_bounded_by_monitor_arena(self):
        resources,monitoring=native_documents(self.plan)
        source=dict(path='/synthetic/status',byte_capacity=128,chunk_bytes=64,
                    max_data_reads=2,requested=[True,False,False,False,False,False])
        monitoring['captures'][0]['environment_sources']=[source]
        def validate():
            native=[dict(ordinal=i,resources=r,monitoring=m) for i,(r,m) in enumerate(
                zip(resources['captures'],monitoring['captures'],strict=True))]
            controller._native_inputs(contract.validate_plan(self.plan),resources,monitoring,native)
        validate()
        for changes in (dict(byte_capacity=1000),dict(byte_capacity=2**64-1),
                        dict(max_data_reads=2**64-1),dict(chunk_bytes=129),
                        dict(path='relative'),dict(path='/bad\0path'),
                        dict(requested=[False]*6),dict(requested=[1]*6)):
            with self.subTest(changes=changes):
                monitoring['captures'][0]['environment_sources']=[dict(source,**changes)]
                with self.assertRaises((controller.ControllerError,contract.ContractError)):validate()
        monitoring['captures'][0]['environment_sources']=[source,copy.deepcopy(source)]
        with self.assertRaisesRegex(controller.ControllerError,'unique'):validate()
        del monitoring['captures'][0]['environment_sources']
        with self.assertRaises(contract.ContractError):validate()

    def test_six_action_release_is_not_diagnostic_authority(self):
        self.resolutions['S17-EXT-006'].semantic_context['supported_actions'].pop()
        with self.assertRaisesRegex(controller.ControllerError,'exact diagnostic'):controller.runtime_from_context(self.validation)

    def test_budget_reserves_supervisor_cleanup(self):
        plan=copy.deepcopy(self.plan);plan['budget']['cleanup_ns']=1
        with self.assertRaisesRegex(controller.ControllerError,'two-second'):controller.deadline_policy(contract.validate_plan(plan))

    def test_original_no_newline_binding_and_duplicate_rejection(self):
        item=self.inputs['bound_documents'][0]
        item['utf8_bytes']=item['utf8_bytes'].rstrip('\n')
        payload=item['utf8_bytes'].encode()
        self.plan['stand'].update(size_bytes=len(payload),sha256=registry.sha256(payload))
        self.trust['measurements']['stand_anchor_sha256']=self.plan['stand']['sha256']
        prepared=self.author()
        bad=copy.deepcopy(prepared.request)
        bad['action_inputs']['bound_documents'][0]['utf8_bytes']='{"synthetic":"stand","synthetic":"stand"}'
        with self.assertRaisesRegex(controller.ControllerError,'duplicate key'):
            controller.validate_action_inputs(bad,self.validation)

    def test_formal_runtime_adapter_retains_identity(self):
        for count in (6,7):
            self.resolutions['S17-EXT-006'].semantic_context['supported_actions']=list(release.SUPPORTED_ACTIONS[:count])
            runtime, binding=controller._runtime_from_context('Q16a',self.validation)
            self.assertEqual(runtime['sha256'],self.plan['release']['sha256'])
            self.assertEqual(binding['worker_sha256'],runtime['sha256'])
        self.resolutions['S17-EXT-006'].semantic_context['supported_actions'].append('UNAUTHORIZED')
        with self.assertRaises(controller.ControllerError):controller._runtime_from_context('Q16a',self.validation)


class DiagnosticReleaseTests(unittest.TestCase):
    """Archive/schema/identity wiring with only native identity/full verifier mocked.

    These tests do not qualify a release; main must run the actual full bundle
    verifier and actual seven-action ELF against a clean source revision.
    """
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='discovery-release-test-');self.addCleanup(self.temp.cleanup)
        self.directory=pathlib.Path(self.temp.name);self.bundle=self.directory/'bundle';self.bundle.mkdir()
        self.worker=self.bundle/'release/bin/cpu_prefetch_runner';self.worker.parent.mkdir(parents=True)
        self.worker.write_bytes(b'\x7fELF--execute-fixed-stage17-action-v4 --execute-fixed-stage17-action-v5 STAGE17-FIXED-ACTION-WORKER-v4')
        verifier=self.bundle/'validators/verify_stand_bundle.py';verifier.parent.mkdir();verifier.write_bytes(b'# test boundary only\n')
        (self.bundle/'SBOM.spdx.json').write_bytes(b'{}\n')
        self.manifest=dict(bundle_profile='STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19',
            source_archive=dict(source_revision='a'*40),pilot_authorized=False,confirmatory_authorized=False,
            dynamic_qualification_authorized=False,stage17_fixed_action_runtime=dict(
                member_path='release/bin/cpu_prefetch_runner',size_bytes=self.worker.stat().st_size,
                sha256=registry.sha256(self.worker.read_bytes()),role='STAGE17_FIXED_ACTION_WORKER',
                runtime_profile='STAGE17-FIXED-ACTION-WORKER-v4',supported_actions=list(release.SUPPORTED_ACTIONS),synthetic_test_only=True))
        self.identity=dict(binary_sha256=registry.sha256(self.worker.read_bytes()),protocol_version='2.0.0-pre.3',
            role='STAGE17_FIXED_ACTION_WORKER',runtime_profile='STAGE17-FIXED-ACTION-WORKER-v4',source_dirty=False,
            source_revision='a'*40,supported_actions=list(release.SUPPORTED_ACTIONS),synthetic_test_only=True)
        self.seal()
        self.archive=self.directory/'bundle.tar.gz'
        with tarfile.open(self.archive,'w:gz') as archive:
            for path in sorted(self.bundle.rglob('*')):
                if path.is_file():archive.add(path,arcname='bundle/'+path.relative_to(self.bundle).as_posix())
        self.sidecar=self.directory/'bundle.tar.gz.sha256'
        self.sidecar.write_text(registry.sha256(self.archive.read_bytes())+'  '+self.archive.name+'\n')
        patcher=patch.object(release,'_run_full_verifier');self.full=patcher.start();self.addCleanup(patcher.stop)
        patcher=patch.object(release.subprocess,'run',side_effect=lambda *a,**kw: types.SimpleNamespace(
            returncode=0,stdout=registry.canonical(self.identity),stderr=b''))
        patcher.start();self.addCleanup(patcher.stop)

    def seal(self):
        (self.bundle/'BUNDLE_MANIFEST.json').write_bytes(registry.canonical(self.manifest))
        files=[p for p in self.bundle.rglob('*') if p.is_file() and p.name not in ('SHA256SUMS','BUNDLE_INVENTORY.json')]
        inventory=dict(schema_version='cpu-prefetch-stand-bundle-inventory/1',files=[dict(path=p.relative_to(self.bundle).as_posix(),
            size_bytes=p.stat().st_size,sha256=registry.sha256(p.read_bytes())) for p in files])
        inventory_path=self.bundle/'BUNDLE_INVENTORY.json';inventory_path.write_bytes(registry.canonical(inventory));files.append(inventory_path)
        (self.bundle/'SHA256SUMS').write_text(''.join(registry.sha256(p.read_bytes())+'  '+p.relative_to(self.bundle).as_posix()+'\n' for p in files))

    def contract(self):
        document=release.build_contract_v9(repository_root=ROOT,archive=self.archive,sidecar=self.sidecar,
            primary_custody_domain_id='test-a',secondary_custody_domain_id='test-b',contract_id='test-contract')
        path=self.directory/'contract.json';path.write_bytes(registry.canonical(document));return document,path

    def test_seven_action_archive_ext006_and_predecessor_mismatch(self):
        document,path=self.contract()
        context=release.verify_pilot_candidate_artifact_v9(repository_root=ROOT,contract_path=path,archive=self.archive,sidecar=self.sidecar)
        self.assertEqual(context.supported_actions,release.SUPPORTED_ACTIONS)
        self.assertTrue(self.full.called)
        extracted=release.verify_extracted_bundle_v9(self.bundle)
        ext3=types.SimpleNamespace(semantic_context={'release':extracted})
        args=dict(root=ROOT,receipt_documents=[dict(verifier_id=release.VERIFIER_ID,verifier_version='5',artifact_locator=str(path))],
            admitted_resolutions={'S17-EXT-003':ext3},pilot_archive=self.archive,pilot_sidecar=self.sidecar,allow_synthetic=True)
        admitted=semantic.verify_input(input_id='S17-EXT-006',**args)
        self.assertEqual(admitted['context']['supported_actions'],list(release.SUPPORTED_ACTIONS))
        import dataclasses
        ext3.semantic_context['release']=dataclasses.replace(extracted,worker_sha256='f'*64)
        with self.assertRaisesRegex(semantic.SemanticAdmissionError,'differs from EXT002/003'):
            semantic.verify_input(input_id='S17-EXT-006',**args)
        document['worker']['supported_actions'].pop();path.write_bytes(registry.canonical(document))
        with self.assertRaisesRegex(release.ArtifactError,'schema rejection'):
            release.verify_pilot_candidate_artifact_v9(repository_root=ROOT,contract_path=path,archive=self.archive,sidecar=self.sidecar)

    def test_ext002_provenance_schema_and_clean_release_binding(self):
        receipt=release.build_extracted_release_receipt_v9(bundle_root=self.bundle,receipt_id='test-receipt')
        context=release.verify_extracted_release_receipt_v9(repository_root=ROOT,receipt=receipt)
        path=self.directory/'provenance.json';payload=registry.canonical(receipt);path.write_bytes(payload)
        schema=(ROOT/release.RUNTIME_RELEASE_PROVENANCE_SCHEMA).read_bytes()
        reference=dict(role='RUNTIME_RELEASE_PROVENANCE',artifact_id='provenance',locator=path.name,
            size_bytes=len(payload),sha256=registry.sha256(payload),schema_identity=receipt['schema_version'],media_type='application/json',
            schema_binding=dict(path=release.RUNTIME_RELEASE_PROVENANCE_SCHEMA,size_bytes=len(schema),sha256=registry.sha256(schema)))
        artifacts=operational._read_artifacts(ROOT,self.directory/'manifest.json',{'artifacts':[reference]},
            {release.RUNTIME_RELEASE_PROVENANCE_SCHEMA:schema})
        values=dict(bundle_profile=context.bundle_profile,source_revision=context.source_revision,
            bundle_manifest_sha256=context.manifest_sha256,sha256s_sha256=context.sha256s_sha256,
            sbom_sha256=context.sbom_sha256,inventory_sha256=context.inventory_sha256,worker_path=str(context.worker_path),
            worker_size_bytes=context.worker_size_bytes,worker_sha256=context.worker_sha256,worker_role=context.worker_role,
            runtime_profile=context.runtime_profile,supported_actions=list(context.supported_actions),
            full_bundle_verifier_sha256=context.full_verifier_sha256)
        runtime=types.SimpleNamespace(document={'measurements':values})
        worker=types.SimpleNamespace(path=self.worker,payload=self.worker.read_bytes())
        self.assertEqual(operational._verify_release(ROOT,artifacts[0],runtime,worker),context)
        values['supported_actions'].pop()
        with self.assertRaisesRegex(operational.OperationalSemanticError,'identity differs'):
            operational._verify_release(ROOT,artifacts[0],runtime,worker)

    def test_full_verifier_and_dirty_native_identity_rejected(self):
        self.full.side_effect=release.ArtifactError('full verifier failed')
        with self.assertRaisesRegex(release.ArtifactError,'full verifier'):release.verify_extracted_bundle_v9(self.bundle)
        self.full.side_effect=None;self.identity['source_dirty']=True
        with self.assertRaisesRegex(release.ArtifactError,'runtime identity'):release.verify_extracted_bundle_v9(self.bundle)

    def test_old_contract_dispatch_remains_predecessor(self):
        path=self.directory/'old-contract.json';path.write_text('{"schema_version":"cpu-prefetch-stage17-pilot-candidate-external-contract/4"}')
        with patch.object(release.predecessor,'verify_pilot_candidate_artifact_v7',return_value='old') as previous:
            self.assertEqual(release.verify_pilot_candidate_artifact_v9(contract_path=path),'old')
            previous.assert_called_once()

    def test_bundle_verifier_new_and_legacy_surfaces(self):
        import verify_stand_bundle as bundle_verifier
        original_payload=self.worker.read_bytes()
        for profile,actions,new_marker in (
                ('STAGE17-PILOT-CANDIDATE-BUNDLE-v22',release.SUPPORTED_ACTIONS[:6],False),
                ('STAGE17-PILOT-CANDIDATE-BUNDLE-v23',release.SUPPORTED_ACTIONS,True),
                ('STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19',release.SUPPORTED_ACTIONS,True)):
            with self.subTest(profile=profile):
                payload=b'\x7fELF--execute-fixed-stage17-action-v4 STAGE17-FIXED-ACTION-WORKER-v4 --execute-stage17-pilot-session-v1 '+b' '.join(a.encode() for a in actions)
                if new_marker: payload+=b' --execute-fixed-stage17-action-v5'
                self.worker.write_bytes(payload)
                synthetic='HERMETIC' in profile
                self.identity.update(binary_sha256=registry.sha256(payload),supported_actions=list(actions),synthetic_test_only=synthetic)
                self.manifest['bundle_profile']=profile
                self.manifest['stage17_fixed_action_runtime'].update(size_bytes=len(payload),sha256=registry.sha256(payload),supported_actions=list(actions),synthetic_test_only=synthetic)
                self.manifest.update(schema_version='cpu-prefetch-pilot-candidate-bundle/14',protocol_version='2.0.0-pre.3',
                    readiness_state='RELEASE_INPUT_READY_FOR_Q15_PREPARATION',measurement_execution_command_present=False,
                    debug_symbol_strategy='UNSTRIPPED_RELEASE_BINARIES_WITH_EXACT_BUILD_PROVENANCE',software_prefetch_mapping_id='X86-64-PREFETCHT0-ONLY-v1')
                path=self.bundle/'config/examples/stage16-stand-inputs.example.json';path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('{"authoritative":false,"required_external_inputs":{}}')
                self.seal();error=io.StringIO()
                with patch.object(sys,'argv',['verify_stand_bundle.py','--root',str(self.bundle)]),contextlib.redirect_stderr(error):
                    self.assertEqual(bundle_verifier.main(),1) # Deliberately unqualified small fixture.
                failures=error.getvalue()
                self.assertNotIn('unknown bundle profile',failures)
                self.assertNotIn('wrong protocol version',failures)
                self.assertNotIn('runtime binding is invalid',failures)
                self.assertNotIn('lacks fixed dispatcher',failures)
                self.assertNotIn('runtime identity/provenance is invalid',failures)
                self.assertIn('controller identity is invalid',failures)


class DiagnosticPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import author_stage17_policy_v55 as author
        cls.author=author
        cls.closure=semantic.discover_python_closure(ROOT,author.ROOTS)
        cls.policy=dict(runtime_import_roots=author.ROOTS,bindings={
            'profile':author._BASE.binding(ROOT,registry.PLAN_PATH)},
            runtime_closure={pathlib.PurePosixPath(p).stem:author._BASE.binding(ROOT,p) for p in sorted(cls.closure)})

    def test_actual_projection_archive_and_isolated_imports(self):
        import create_stand_bundle as packager
        import verify_stand_bundle as verifier
        with tempfile.TemporaryDirectory(prefix='diagnostic-projection-') as temporary:
            root=pathlib.Path(temporary);stage=root/'stage';stage.mkdir()
            copied=packager.copy_policy_bound_files(ROOT,stage,self.policy)
            self.assertEqual(len(copied),len(self.closure)+1)
            archive=root/'projection.tar.gz'
            packager.deterministic_tar(archive,[(stage/p,'bundle/'+p) for p in self.closure]+[(stage/registry.PLAN_PATH,'bundle/'+registry.PLAN_PATH)])
            extracted=release._safe_extract(archive,root/'unpacked')
            for p in self.closure:
                self.assertEqual((extracted/p).read_bytes(),(ROOT/p).read_bytes())
            self.assertEqual(verifier.diagnostic_runtime_closure_errors(extracted,self.policy),[])
            # Missing historical imports and non-stage17 helpers both fail closed.
            for name in ('stage17_phase_controller_v2','check_canonical'):
                path=extracted/'tools'/(name+'.py');payload=path.read_bytes();path.unlink()
                self.assertTrue(verifier.diagnostic_runtime_closure_errors(extracted,self.policy))
                path.write_bytes(payload)
            # The packager refuses stale source hashes before it seals a projection.
            bad=copy.deepcopy(self.policy);bad['runtime_closure']['check_canonical']['sha256']='f'*64
            with self.assertRaisesRegex(ValueError,'binding drifted'):
                packager.copy_policy_bound_files(ROOT,root/'bad',bad)

    def test_source_headers_and_schema_versions_are_explicit(self):
        paths=self.author.native_source_closure(ROOT)
        for expected in ('src/calibration/native_discovery_capture.cpp','src/runner/stage17_discovery_action.cpp',
            'src/runner/stage17_discovery_publication.cpp','include/cpu_prefetch/calibration/mapped_discovery_runtime.hpp',
            'include/cpu_prefetch/platform/thread_monitor.hpp','src/queue/linked_spsc.cpp'):
            self.assertIn(expected,paths)
        self.assertIn('tools/check_canonical.py',self.closure)
        self.assertIn('tools/stage17_q15_session_controller_v17.py',self.closure)
        for module in ('stage17_discovery_validation_v1','stage17_discovery_environment_v1'):
            self.assertIn('tools/'+module+'.py',self.closure)
        for path in ('tools/check_stage17_discovery_validation.py','tests/test_stage17_discovery_environment.py',
                     'docs/decisions/0203-caller-owned-linked-queue-storage.md','tests/queue_linked_storage_test.cpp',
                     'config/queue-provenance/linked-spsc.json'):
            self.assertIn(path,self.author.SUCCESSOR_BINDINGS)
        self.assertIn(release.RUNTIME_RELEASE_PROVENANCE_SCHEMA,self.author.SUCCESSOR_BINDINGS)

    def test_packager_requires_actual_binary_dual_tools_and_source_hashes(self):
        import check_discovery_codegen as codegen
        import create_stand_bundle as packager
        # Binding-contract unit fixture only; this does not qualify machine code.
        with tempfile.TemporaryDirectory(prefix='discovery-codegen-binding-') as temporary:
            directory=pathlib.Path(temporary);binary=directory/'worker';binary.write_bytes(b'synthetic worker bytes')
            operation=dict(status='PASS',native_reference_path=['synthetic-native'],raw_clock_call_sites={'synthetic':[1]})
            tools={name:dict(status='PASS',version=version,full_disassembly_sha256='c'*64,
                operations={phase+'_'+role:copy.deepcopy(operation) for phase in ('warmup','measurement') for role in ('producer','consumer')},
                event_boundaries={role:{'status':'PASS'} for role in ('producer','consumer')})
                for name,version in (('GNU_OBJDUMP','2.46'),('LLVM_OBJDUMP','22.1.6'))}
            report=dict(schema_version=codegen.SCHEMA,binary_role='ACTUAL_NATIVE_DISCOVERY_WORKER',status='PASS',missing_tools=[],
                binary_sha256=codegen.sha256(binary),rule_set_sha256=codegen.sha256(ROOT/'tools/check_discovery_codegen.py'),
                source_evidence={p:codegen.sha256(ROOT/p) for p in codegen.SOURCE_EVIDENCE_PATHS},tools=tools)
            path=directory/'discovery_codegen_report.json';path.write_bytes(registry.canonical(report))
            packager.verify_discovery_codegen_report(ROOT,binary,path)
            for mutation in ('binary','source','llvm','missing','operation'):
                bad=copy.deepcopy(report)
                if mutation=='binary':bad['binary_sha256']='f'*64
                elif mutation=='source':bad['source_evidence'].pop(next(iter(bad['source_evidence'])))
                elif mutation=='llvm':bad['tools']['LLVM_OBJDUMP']['version']='21.0.0'
                elif mutation=='missing':bad['tools'].pop('LLVM_OBJDUMP')
                else:bad['tools']['GNU_OBJDUMP']['operations'].pop('measurement_consumer')
                path.write_bytes(registry.canonical(bad))
                with self.subTest(mutation=mutation),self.assertRaises(codegen.AuditError):
                    packager.verify_discovery_codegen_report(ROOT,binary,path)


class NativeDiscoveryActionTests(unittest.TestCase):
    """Actual C++ dispatcher and process transport; synthetic backend is link-only."""
    author = DiscoveryActionTests.author
    sign = DiscoveryActionTests.sign

    def setUp(self):
        if NATIVE_WORKER is None:
            self.skipTest('pass --worker to exercise the actual C++ fd pipeline')
        DiscoveryActionTests.setUp(self)
        self.worker.unlink()
        shutil.copyfile(NATIVE_WORKER,self.worker);self.worker.chmod(0o500)
        digest=registry.sha256(self.worker.read_bytes());size=self.worker.stat().st_size
        self.plan['release'].update(size_bytes=size,sha256=digest)
        self.resolutions['S17-EXT-006'].semantic_context.update(
            release_artifact_size_bytes=size,release_artifact_sha256=digest)

    def test_actual_signed_cpp_fd_pipeline_and_retention(self):
        prepared=self.author()
        outcome=controller.execute_once(**self.arguments)
        retained=cli.admit_retention(prepared,self.output)
        self.assertEqual(len(outcome.result['artifacts']),254)
        self.assertTrue(all(c['native_validity']=='INSUFFICIENT' for c in retained['captures']))
        self.assertEqual(retained['scientific_validity'],'NOT_ASSESSED')
        self.assertFalse(retained['eligible_for_duration_selection'])
        # Native output is real binary data, not the empty mock retention fixture.
        self.assertGreater((self.output/'discovery-c00-warmup-producer.bin').stat().st_size,0)
        self.assertEqual((self.output/'discovery-c00-warmup-demand.bin').stat().st_size,64)

    def reject_context(self,kind):
        self.author()
        native_run=executor._run_worker
        def altered(argv,fds,**kwargs):
            args=list(argv);fds=list(fds);snapshot=None
            try:
                if kind=='v4':args[1]='--execute-fixed-stage17-action-v4'
                else:
                    context=json.loads(os.pread(fds[1],1000000,0))
                    if kind=='expired':
                        context['issued_at_epoch_seconds']=1;context['expires_at_epoch_seconds']=2
                    elif kind=='deadline':context['per_run_deadline_seconds']=180
                    elif kind=='schema':context['schema_version']='cpu-prefetch-stage17-fixed-action-context/4'
                    snapshot=executor.predecessor._pin_generated(registry.canonical(context),'FIXED_ACTION_CONTEXT_V5')
                    fds[1]=snapshot.descriptor;args[6]=str(snapshot.descriptor)
                return native_run(tuple(args),tuple(fds),**kwargs)
            finally:
                executor.snapshot_broker.close_snapshots(snapshot)
        with patch.object(executor,'_run_worker',side_effect=altered):
            with self.assertRaises(executor.FixedActionExecutionError):controller.execute_once(**self.arguments)
        self.assertFalse(list(self.output.glob('discovery-*')))
        self.assertFalse(list(self.output.glob('*completion-v5.json')))
        self.assertTrue(list(self.output.glob('*failure-v5.json')))

    def test_actual_cpp_rejects_v4_dispatch(self):self.reject_context('v4')
    def test_actual_cpp_rejects_expired_context(self):self.reject_context('expired')
    def test_actual_cpp_rejects_deadline_mismatch(self):self.reject_context('deadline')
    def test_actual_cpp_rejects_context_v4(self):self.reject_context('schema')


if __name__=='__main__':
    if '--worker' in sys.argv:
        index=sys.argv.index('--worker')
        NATIVE_WORKER=pathlib.Path(sys.argv[index+1]).resolve()
        del sys.argv[index:index+2]
        if not NATIVE_WORKER.is_file():raise SystemExit('native worker path is absent')
    unittest.main()
