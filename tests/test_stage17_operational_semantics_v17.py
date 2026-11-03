"""D239 real local signatures for receipt linkage, never production freeze mocks."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import stage17_operational_semantics_v17 as current


def encoded(value):
    return current.strict.calibration.canonical(value)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class SignedReceipts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='d239-signed-receipts-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        cls.key = cls.directory / 'key'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(cls.key)],
                       check=True,capture_output=True,timeout=15)
        allowed = cls.directory / 'allowed-signers'
        raw = ('software-fixture ' + cls.key.with_suffix('.pub').read_text()).encode()
        allowed.write_bytes(raw);allowed.chmod(0o600)
        cls.trust = dict(measurements=dict(allowed_signers_path=str(allowed),allowed_signers_size_bytes=len(raw),
            allowed_signers_sha256=digest(raw),principal='software-fixture',sshsig_namespace='d239-software-only'))
        cls.predecessors = [dict(input_id=key,resolution_id='original-'+key,sha256=hex(i+1)[2:]*64)
                            for i,key in enumerate(current.PREDECESSORS)]
        cls.extent = SimpleNamespace(declared=SimpleNamespace(watchdog_ns=100_000_000_000,
            cleanup_ns=2_000_000_000,memory_bytes=1000,required_free_disk_bytes=2000),
            captures=[SimpleNamespace(declared=SimpleNamespace(watchdog_ns=10_000_000_000))])

    def setUp(self):
        self.output = Path(tempfile.mkdtemp(dir=self.directory))
        self.output.chmod(0o700)

    def chain(self, changes=None):
        changes = changes or {}
        result = []
        def change(role, doc):
            if role in changes:changes[role](doc)
            return doc
        def artifact(role, payload, document=None, path=None):
            path = path or self.output / (role.lower()+'.json')
            path.write_bytes(payload)
            obj = current.reader.Artifact('Q16A_'+role,path,payload,len(payload),digest(payload),document,
                dict(artifact_id=role,lineage=[]))
            result.append(obj)
            return obj
        def write(role, doc):
            doc = change(role,copy.deepcopy(doc))
            return artifact(role,encoded(doc),doc)
        metadata = self.output.stat()
        root = dict(absolute_path=str(self.output),device=metadata.st_dev,inode=metadata.st_ino,
                    owner_uid=metadata.st_uid,mode='0700')
        prestate = [dict(cpu=cpu,complete_value_hex='0000000000000000') for cpu in (0,1,8)]
        runtime = dict(sha256='a'*64,size_bytes=123,role='STAGE17_FIXED_ACTION_WORKER',profile='STAGE17-FIXED-ACTION-WORKER-v4')
        release = dict(source_resolution_id=self.predecessors[-1]['resolution_id'],source_resolution_sha256=self.predecessors[-1]['sha256'],
            artifact_role=runtime['role'],runtime_profile=runtime['profile'],worker_size_bytes=123,worker_sha256=runtime['sha256'])
        req = write('REQUEST',dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6',
            action_id='Q16a',request_id='request',authorization_id='authorization',session_id='session',
            attempt_id='attempt',stand_id='software-stand',predecessor_resolutions=self.predecessors,
            runtime_binding=runtime,release_binding=release,evidence_root_binding=root,
            synthetic_test_only=True,phase18_authority=False,
            action_inputs=dict(hardware_control=dict(prestate=prestate))))
        auth = write('AUTHORIZATION',dict(schema_version='cpu-prefetch-stage17-phase-action-authorization/6',
            action_id='Q16a',authorization_id='authorization',session_id='session',target=dict(stand_id='software-stand'),
            actor='software-fixture',reviewer='software-reviewer',
            trust_context=dict(ext002_resolution=self.predecessors[1],ext003_resolution=self.predecessors[2]),
            fixed_action_definition_sha256='c'*64,
            permission_matrix=dict(read_only_observation=True,privileged_controls=True,calibration=True,
                pilot_execution=False,measurement=False,phase18=False),
            one_attempt=True,retry_allowed=False,stop_first=True,retain_partial=True,
            request_binding=dict(path=str(req.path),size_bytes=req.size_bytes,sha256=req.sha256),
            predecessor_resolutions=self.predecessors,evidence_root_binding=root,
            issued_at_utc='2026-01-01T00:00:00Z',expires_at_utc='2026-01-01T00:01:40Z',
            deadline_policy=current.existing_controller.deadline_policy(self.extent),stage18_authority=False))
        signature_path = Path(str(auth.path)+'.sig')
        if signature_path.exists():signature_path.unlink()
        subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-n','d239-software-only','-f',str(self.key),str(auth.path)],
                       check=True,capture_output=True,timeout=15)
        artifact('SIGNATURE',signature_path.read_bytes(),path=signature_path)
        shared = dict(action_id='Q16a',attempt_id='attempt',authorization_sha256=auth.sha256,
                      request_sha256=req.sha256,phase18_authority=False)
        write('ATTEMPT',dict(shared,schema_version='cpu-prefetch-stage17-phase-action-attempt/6',
            authorization_id='authorization',runtime_sha256=runtime['sha256'],
            release_resolution_id=release['source_resolution_id'],release_resolution_sha256=release['source_resolution_sha256'],
            evidence_root_binding=root,started_at_utc='2026-01-01T00:00:01Z',one_attempt=True,retries=0,marker_durable=True))
        res = write('RESULT',dict(shared,schema_version='cpu-prefetch-stage17-phase-action-result/6',
            result_id='result',started_at_utc='2026-01-01T00:00:02Z',completed_at_utc='2026-01-01T00:00:04Z',
            duration_ns=2_000_000_000,terminal_state='FORMAL_ARTIFACTS_RETAINED_UNASSESSED',
            request_id='request',authorization_id='authorization',stand_id='software-stand',
            runtime_binding=runtime,release_binding=release,predecessor_resolutions=self.predecessors,
            synthetic_test_only=True,restoration_verified=True,quarantined=False,
            artifacts=[dict(file_name='retained.json',size_bytes=3,sha256='b'*64,role='SOFTWARE_FIXTURE',
                            schema_identity='software-only/1',media_type='application/json')]))
        write('COMPLETION',dict(shared,schema_version='cpu-prefetch-stage17-phase-action-completion/6',
            completion_id='attempt:completion',runtime_sha256=runtime['sha256'],
            result=dict(file_name=res.path.name,size_bytes=res.size_bytes,sha256=res.sha256),
            artifact_bindings=[{k:row[k] for k in ('file_name','size_bytes','sha256')} for row in res.document['artifacts']],
            leader_reaped=True,process_group_gone=True,
            restoration_verified=True,quarantined=False,live_restoration_readback=[dict(cpu=row['cpu'],
                expected_hex=row['complete_value_hex'],observed_hex=row['complete_value_hex'],matches=True) for row in prestate],
            completed_at_utc='2026-01-01T00:00:05Z',resource_admission=dict(
                memory_available_bytes=10000,filesystem_available_bytes=20000,filesystem_device=metadata.st_dev,
                required_memory_bytes=1000,required_free_disk_bytes=2000,reservation_established=False,
                observed_at_utc='2026-01-01T00:00:02Z')))
        return result

    def verify(self, artifacts):
        return current._receipts(artifacts=artifacts,action_id='Q16a',trust=self.trust,
            expected_predecessors=self.predecessors,extent=self.extent,allow_synthetic=True)

    def test_real_signature_original_past_time_receipts_reconcile_without_now_authority(self):
        artifacts = self.chain()
        result = self.verify(artifacts)
        self.assertEqual(result['request_sha256'],next(a.sha256 for a in artifacts if a.role=='Q16A_REQUEST'))
        self.assertEqual(result['completion']['completed_at_utc'],'2026-01-01T00:00:05Z')
        self.assertNotIn('calibration_freeze',result)

    def test_signed_hash_identity_and_physical_receipt_mutants(self):
        mutants = (
            ('AUTHORIZATION',lambda d:d['request_binding'].update(sha256='f'*64)),
            ('ATTEMPT',lambda d:d.update(runtime_sha256='f'*64)),
            ('ATTEMPT',lambda d:d.update(request_sha256='f'*64)),
            ('ATTEMPT',lambda d:d.update(release_resolution_sha256='f'*64)),
            ('ATTEMPT',lambda d:d.update(marker_durable=False)),
            ('ATTEMPT',lambda d:d.update(retries=True)),
            ('RESULT',lambda d:d.update(attempt_id='other')),
            ('RESULT',lambda d:d.update(stand_id='other')),
            ('RESULT',lambda d:d.update(synthetic_test_only=False)),
            ('COMPLETION',lambda d:d['result'].update(sha256='f'*64)),
            ('COMPLETION',lambda d:d.update(artifact_bindings=[])),
            ('COMPLETION',lambda d:d.update(phase18_authority=True)),
        )
        for role, mutate in mutants:
            with self.subTest(role=role,mutate=mutate):
                with self.assertRaises(current.OperationalSemanticError):self.verify(self.chain({role:mutate}))

    def test_restore_quiescence_time_and_resource_mutants(self):
        mutants = (
            ('RESULT',lambda d:d.update(restoration_verified=False)),
            ('COMPLETION',lambda d:d.update(quarantined=True)),
            ('COMPLETION',lambda d:d.update(leader_reaped=False)),
            ('COMPLETION',lambda d:d.update(process_group_gone=False)),
            ('COMPLETION',lambda d:d['live_restoration_readback'][1].update(observed_hex='000000000000000f')),
            ('COMPLETION',lambda d:d['live_restoration_readback'][1].update(expected_hex='000000000000000f')),
            ('COMPLETION',lambda d:d['live_restoration_readback'][1].update(matches=False)),
            ('COMPLETION',lambda d:d['live_restoration_readback'][1].update(cpu=0)),
            ('COMPLETION',lambda d:d.update(live_restoration_readback=[])),
            ('ATTEMPT',lambda d:d.update(started_at_utc='2025-12-31T23:59:59Z')),
            ('COMPLETION',lambda d:d.update(completed_at_utc='2026-01-01T00:00:00Z')),
            ('COMPLETION',lambda d:d.update(completed_at_utc='2026-01-01T00:01:41Z')),
            ('RESULT',lambda d:d.update(started_at_utc='2026-01-01T00:00:00Z')),
            ('RESULT',lambda d:d.update(completed_at_utc='2026-01-01T00:00:06Z')),
            ('RESULT',lambda d:d.update(duration_ns=100_000_000_001)),
            ('COMPLETION',lambda d:d['resource_admission'].update(memory_available_bytes=999)),
            ('COMPLETION',lambda d:d['resource_admission'].update(required_free_disk_bytes=1)),
            ('COMPLETION',lambda d:d['resource_admission'].update(reservation_established=True)),
        )
        for role, mutate in mutants:
            with self.subTest(role=role,mutate=mutate):
                with self.assertRaises(current.OperationalSemanticError):self.verify(self.chain({role:mutate}))

    def test_signature_original_bytes_and_duplicate_roles_fail(self):
        artifacts = self.chain(); signature=next(a for a in artifacts if a.role=='Q16A_SIGNATURE')
        signature.path.write_bytes(b'not-an-SSHSIG')
        with self.assertRaises(current.OperationalSemanticError):self.verify(artifacts)
        artifacts = self.chain(); authorization=next(a for a in artifacts if a.role=='Q16A_AUTHORIZATION')
        authorization.path.write_bytes(authorization.payload+b'\n')
        with self.assertRaises(current.OperationalSemanticError):self.verify(artifacts)
        artifacts = self.chain()
        with self.assertRaises(current.OperationalSemanticError):self.verify(artifacts+[artifacts[0]])

    def test_actual_sshsig_namespace_and_receipt_schema_field_names(self):
        artifacts=self.chain()
        trust=copy.deepcopy(self.trust);trust['measurements']['sshsig_namespace']='another-namespace'
        with self.assertRaisesRegex(current.OperationalSemanticError,'SSHSIG'):
            current._receipts(artifacts=artifacts,action_id='Q16a',trust=trust,
                expected_predecessors=self.predecessors,extent=self.extent,allow_synthetic=True)
        families=dict(AUTHORIZATION='phase-action-authorization',REQUEST='fixed-action-request',
            ATTEMPT='phase-action-attempt',RESULT='phase-action-result',COMPLETION='phase-action-completion')
        for artifact in artifacts:
            role=artifact.role.removeprefix('Q16A_')
            if role=='SIGNATURE':continue
            schema=json.loads((ROOT/('config/schemas/stage17-'+families[role]+'-v6.schema.json')).read_text())
            Draft202012Validator(schema,format_checker=FormatChecker()).validate(artifact.document)


    def archived_chain(self, mutate=None, retained=1_000_000_000_000):
        storage = dict(program_scope_sha256='d'*64, archive_quota_bytes=6_000_000_000_000,
            workspace_bytes=512*1024**3, analysis_scratch_bytes=256*1024**3, disk_reserve_bytes=16*1024**3)
        self.extent = copy.deepcopy(type(self).extent)
        self.extent.declared.required_free_disk_bytes = (
            storage['archive_quota_bytes'] + storage['workspace_bytes']
            + storage['analysis_scratch_bytes'] + storage['disk_reserve_bytes'])
        def request(doc):
            doc['action_inputs']['plan'] = dict(schema_version=current.plans.VERSION['Q16a'], storage=storage)
        def completion(doc):
            resources = doc['resource_admission']
            remaining_disk = self.extent.declared.required_free_disk_bytes - retained
            resources.update(program_scope_sha256=storage['program_scope_sha256'],
                retained_program_bytes=retained,
                remaining_program_quota_bytes=storage['archive_quota_bytes']-retained,
                capture_ordinal=0, required_free_disk_bytes=remaining_disk,
                filesystem_available_bytes=remaining_disk)
            if mutate is not None: mutate(resources)
        return self.chain({'REQUEST': request, 'COMPLETION': completion})

    def test_signed_shared_quota_later_family_admission_uses_remaining_bytes(self):
        for retained in (0, 1_000_000_000_000, 6_000_000_000_000):
            artifacts = self.archived_chain(retained=retained)
            result = self.verify(artifacts)
            resources = result['completion']['resource_admission']
            self.assertEqual(resources['remaining_program_quota_bytes'], 6_000_000_000_000-retained)
            self.assertEqual(resources['required_free_disk_bytes'],
                             self.extent.declared.required_free_disk_bytes-retained)
            schema = json.loads((ROOT/'config/schemas/stage17-phase-action-completion-v6.schema.json').read_text())
            Draft202012Validator(schema, format_checker=FormatChecker()).validate(result['completion'])

    def test_shared_quota_scope_counts_and_initial_boundary_mutants_reject(self):
        mutations = [lambda r:r.pop('program_scope_sha256'),
            lambda r:r.update(program_scope_sha256='f'*64),
            lambda r:r.update(retained_program_bytes=True),
            lambda r:r.update(retained_program_bytes=-1),
            lambda r:r.update(retained_program_bytes=6_000_000_000_001),
            lambda r:r.update(remaining_program_quota_bytes=0),
            lambda r:r.update(remaining_program_quota_bytes=True),
            lambda r:r.update(capture_ordinal=1),
            lambda r:r.update(capture_ordinal=True),
            lambda r:r.update(required_free_disk_bytes=self.extent.declared.required_free_disk_bytes),
            lambda r:r.update(filesystem_available_bytes=r['required_free_disk_bytes']-1)]
        for field in ('retained_program_bytes','remaining_program_quota_bytes','capture_ordinal'):
            mutations.append(lambda r, field=field:r.pop(field))
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(current.OperationalSemanticError):
                self.verify(self.archived_chain(mutate))


class ClosedDispatch(unittest.TestCase):
    def test_actual_program_root_and_exact_scope_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            program=Path(directory);program.chmod(0o700)
            phase=program/'working'/('d'*64);phase.mkdir(parents=True,mode=0o700)
            def binding(path):
                st=path.stat()
                return dict(absolute_path=str(path),device=st.st_dev,inode=st.st_ino,owner_uid=st.st_uid,mode='0700')
            storage=dict(program_id='fixed-program',implementation_profile_sha256='a'*64,program_scope_sha256='b'*64)
            request=dict(evidence_root_binding=binding(phase),action_inputs=dict(plan=dict(storage=storage)))
            original=dict(scope_bindings=dict(storage,phase_root_binding=binding(phase),program_root_binding=binding(program),
                                               ledger_head=dict(sequence_number=3,sha256='c'*64)))
            current._archive_scope(original,request,ROOT)
            for mutate in (lambda s:s.update(program_id='different'),
                           lambda s:s.update(implementation_profile_sha256='f'*64),
                           lambda s:s.update(program_scope_sha256='f'*64),
                           lambda s:s['phase_root_binding'].update(inode=1),
                           lambda s:s['program_root_binding'].update(inode=1),
                           lambda s:s['ledger_head'].update(sequence_number=True),
                           lambda s:s['ledger_head'].update(sha256='c'*64+'\n')):
                report=copy.deepcopy(original);mutate(report['scope_bindings'])
                with self.assertRaises((current.OperationalSemanticError,current.roots.FixedActionExecutionError,
                                        current.strict.ExportError)):
                    current._archive_scope(report,request,ROOT)
            program.chmod(0o755)
            with self.assertRaises(current.roots.FixedActionExecutionError):current._archive_scope(original,request,ROOT)

    def test_missing_dependency_cannot_admit_or_fallback(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(current.OperationalSemanticError,'dependency unavailable'):
                current._dependencies(root,{})

    def test_unpinned_dependency_is_not_imported(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'tools';path.mkdir()
            (path/'stage17_output_registry_v12.py').write_text('# test missing pin\n')
            with patch.object(current.importlib,'import_module') as load:
                with self.assertRaisesRegex(current.OperationalSemanticError,'not policy-pinned'):
                    current._dependencies(root,{})
                load.assert_not_called()

    def test_absent_required_verifier_rejects_even_pinned_file(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'tools';path.mkdir()
            file=path/'stage17_output_registry_v12.py';file.write_text('# no verifier\n')
            with patch.object(current.importlib,'import_module',return_value=SimpleNamespace(__file__=str(file))):
                with self.assertRaisesRegex(current.OperationalSemanticError,'verifier unavailable'):
                    current._dependencies(root,{'tools/stage17_output_registry_v12.py':file.read_bytes()})

    def test_historical_hashes_and_no_pending_ext007(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'journal.json';raw=b'{"historical":"test"}';path.write_bytes(raw)
            resolutions={key:SimpleNamespace(resolution_id=key+'-original',sha256='a'*64) for key in current.PREDECESSORS}
            prepared=SimpleNamespace(validation=SimpleNamespace(resolutions=copy.deepcopy(resolutions),latest_journal_sha256=digest(raw)))
            current._historical(prepared,resolutions,path)
            prepared.validation.resolutions['S17-EXT-003'].sha256='b'*64
            with self.assertRaisesRegex(current.OperationalSemanticError,'hashes differ'):current._historical(prepared,resolutions,path)
            prepared.validation.resolutions=copy.deepcopy(resolutions)
            prepared.validation.resolutions['S17-EXT-007']=SimpleNamespace()
            with self.assertRaisesRegex(current.OperationalSemanticError,'exactly through EXT006'):current._historical(prepared,resolutions,path)
            prepared.validation.resolutions=copy.deepcopy(resolutions);path.write_bytes(raw+b'\n')
            with self.assertRaisesRegex(current.OperationalSemanticError,'journal bytes differ'):current._historical(prepared,resolutions,path)

    def test_legacy_dispatch_exact_and_new_route_has_no_mocked_production_success(self):
        sentinel=object()
        with patch.object(current.predecessor,'verify_manifest_v16',return_value=sentinel) as old:
            args=dict(expected_input_id='S17-EXT-004',opaque='unchanged')
            self.assertIs(current.verify_manifest_v17(**args),sentinel);old.assert_called_once_with(**args)
        with patch.object(current.reader,'load',return_value=({'artifacts':[]},b'{}')):
            with patch.object(current.predecessor,'verify_manifest_v16',return_value=sentinel) as old:
                args=dict(expected_input_id='S17-EXT-007',manifest_path=Path('unused'))
                self.assertIs(current.verify_manifest_v17(**args),sentinel);old.assert_called_once_with(**args)
        document={'artifacts':[dict(role='Q16A_REQUEST',schema_identity='cpu-prefetch-stage17-fixed-action-request/6')]}
        with patch.object(current.reader,'load',return_value=(document,b'{}')):
            with patch.object(current.reader,'_validate'),patch.object(current,'_dependencies',return_value=(None,None)):
                with self.assertRaisesRegex(current.OperationalSemanticError,'bounded actual'):
                    current.verify_manifest_v17(expected_input_id='S17-EXT-007',manifest_path=Path('unused'),
                        repository_root=ROOT,pinned_repository_bytes={})


if __name__=='__main__':
    unittest.main(verbosity=2)
