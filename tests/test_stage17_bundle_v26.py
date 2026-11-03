"""Release-custody successor wiring; synthetic files grant no qualification."""
from pathlib import Path
import contextlib
import copy
import io
import json
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import check_stage17_discovery_policy_v2 as legacy
import stage17_pilot_candidate_artifact_v12 as release
import check_formal_codegen as gate
import create_stand_bundle as creator
import verify_stand_bundle as verifier
import stage17_archive_bundle_profile_v1 as archive_profile


class FormalRelease(unittest.TestCase):
    seal = legacy.SuccessorReleaseTests.seal

    def setUp(self):
        legacy.SuccessorReleaseTests.setUp(self)
        self.manifest['bundle_profile'] = 'STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22'
        self.worker.write_bytes(self.worker.read_bytes() + b' --execute-fixed-stage17-action-v6')
        self.runtime_root = self.directory / 'accepted-runtime'
        for root, name, data in (
            (self.runtime_root, archive_profile.PYTHON_PATH, b'qualified-synthetic-python'),
            (self.bundle, archive_profile.ENCODER_PATH, b'synthetic-encoder'),
            (self.bundle, archive_profile.ZSTD_PATH, b'synthetic-zstd'),
            *((self.bundle, 'tools/' + module + '.py', b'VALUE = 1\n')
              for module in archive_profile.ROOT_MODULES)):
            member = root / name; member.parent.mkdir(parents=True, exist_ok=True); member.write_bytes(data)
        profile = archive_profile.build_profile(bundle_root=self.bundle,
            runtime_root=self.runtime_root, window_log=22)
        member = self.bundle / archive_profile.PROFILE_PATH
        member.parent.mkdir(parents=True, exist_ok=True); member.write_bytes(archive_profile.canonical(profile))
        self.refresh_worker()
        p = patch.object(release, '_run_full_verifier')
        self.full = p.start(); self.addCleanup(p.stop)
        self.archive.unlink()
        with tarfile.open(self.archive, 'w:gz') as archive:
            for path in sorted(self.bundle.rglob('*')):
                if path.is_file(): archive.add(path, arcname='bundle/' + path.relative_to(self.bundle).as_posix())
        self.sidecar.write_text(release.sha256_file(self.archive) + '  ' + self.archive.name + '\n')

    def refresh_worker(self):
        self.manifest['stage17_fixed_action_runtime'].update(size_bytes=self.worker.stat().st_size,
            sha256=release.sha256_file(self.worker))
        self.identity['binary_sha256'] = release.sha256_file(self.worker)
        self.seal()

    def test_archive_contract_and_receipt_successor_identities(self):
        document = release.build_contract_v12(repository_root=ROOT, archive=self.archive, sidecar=self.sidecar,
            primary_custody_domain_id='first', secondary_custody_domain_id='second', contract_id='software')
        self.assertEqual(document['schema_version'], 'cpu-prefetch-stage17-pilot-candidate-external-contract/6')
        path = self.directory / 'contract.json'; path.write_text(json.dumps(document))
        context = release.verify_pilot_candidate_artifact_v12(repository_root=ROOT, contract_path=path,
            archive=self.archive, sidecar=self.sidecar)
        self.assertEqual(context.supported_actions, release.SUPPORTED_ACTIONS)
        receipt = release.build_extracted_release_receipt_v12(bundle_root=self.bundle, receipt_id='software', archive_runtime_root=self.runtime_root)
        self.assertEqual(receipt['schema_version'], 'cpu-prefetch-stage17-runtime-release-provenance/7')
        self.assertEqual(release.VERIFIER_VERSION, '7')
        observed = release.verify_extracted_release_receipt_v12(repository_root=ROOT, receipt=receipt)
        self.assertIsInstance(observed, release.ArchiveExtractedReleaseContext)
        self.assertEqual(observed.archive_runtime_provenance, receipt)
        self.assertIsNot(observed.archive_runtime_provenance, receipt)
        self.assertTrue(self.full.called)
        fields = release.qualified_archive_context_v12(repository_root=ROOT,
            receipt=receipt, release_context=context)
        self.assertEqual(fields['archive_runtime_root'], str(self.runtime_root))
        with self.assertRaisesRegex(release.ArtifactError, 'explicit archive_runtime_root'):
            release.build_extracted_release_receipt_v12(bundle_root=self.bundle, receipt_id='missing')
        bad = copy.copy(context)
        from dataclasses import replace
        bad = replace(bad, manifest_sha256='0'*64)
        with self.assertRaisesRegex(release.ArtifactError, 'EXT006/EXT003'):
            release.qualified_archive_context_v12(repository_root=ROOT, receipt=receipt, release_context=bad)
        changed = copy.deepcopy(receipt); changed['archive_runtime_root'] = str(self.directory)
        with self.assertRaises((release.ArtifactError, OSError)):
            release.verify_extracted_release_receipt_v12(repository_root=ROOT, receipt=changed)
        for version in ('5', '7'):
            document['schema_version'] = 'cpu-prefetch-stage17-pilot-candidate-external-contract/' + version
            path.write_text(json.dumps(document))
            with self.assertRaisesRegex(release.ArtifactError, 'schema rejection'):
                release.verify_pilot_candidate_artifact_v12(repository_root=ROOT, contract_path=path,
                    archive=self.archive, sidecar=self.sidecar)

    def test_both_dispatchers_and_discovery_v2_are_required(self):
        original = self.worker.read_bytes()
        for token in (b'--execute-fixed-stage17-action-v6', b'--execute-fixed-stage17-action-v5',
                      b'--describe-stage17-discovery-layout-v2'):
            with self.subTest(token=token):
                self.worker.write_bytes(original.replace(token, b'absent')); self.refresh_worker()
                with self.assertRaisesRegex(release.ArtifactError, 'lacks the fixed dispatcher'):
                    release.verify_extracted_bundle_v12(self.bundle)

    def test_full_verifier_failure_and_source_dirty_fail_closed(self):
        self.full.side_effect = release.ArtifactError('full verifier rejected')
        with self.assertRaisesRegex(release.ArtifactError, 'full verifier rejected'):
            release.verify_extracted_bundle_v12(self.bundle)
        self.full.side_effect = None
        self.identity['source_dirty'] = True
        with self.assertRaisesRegex(release.ArtifactError, 'clean release provenance'):
            release.verify_extracted_bundle_v12(self.bundle)

    def test_historical_three_entrypoints_delegate_without_relabel(self):
        self.manifest['bundle_profile'] = 'STAGE17-PILOT-CANDIDATE-BUNDLE-v25'; self.seal()
        path = self.directory / 'old.json'; path.write_text(json.dumps({'manifest': {'bundle_profile': self.manifest['bundle_profile']}}))
        for name, arguments in (
            ('verify_extracted_bundle', {'bundle_root': self.bundle}),
            ('verify_pilot_candidate_artifact', {'contract_path': path}),
            ('verify_extracted_release_receipt', {'receipt': {'bundle_profile': self.manifest['bundle_profile']}})):
            with patch.object(release.predecessor, name + '_v11', return_value='historical') as old:
                self.assertEqual(getattr(release, name + '_v12')(**arguments), 'historical')
                old.assert_called_once()

    def test_full_verifier_recognizes_profiles_and_requires_eighth_gate(self):
        payload = self.worker.read_bytes() + b' --execute-stage17-pilot-session-v1 ' + b' '.join(a.encode() for a in release.SUPPORTED_ACTIONS)
        for profile, synthetic, formal in (('STAGE17-PILOT-CANDIDATE-BUNDLE-v26', False, True),
                ('STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22', True, True),
                ('STAGE17-PILOT-CANDIDATE-BUNDLE-v25', False, False)):
            self.worker.write_bytes(payload if formal else payload.replace(b'--execute-fixed-stage17-action-v6', b''))
            self.manifest.update(bundle_profile=profile, schema_version='cpu-prefetch-pilot-candidate-bundle/14',
                protocol_version='2.0.0-pre.3', readiness_state='RELEASE_INPUT_READY_FOR_Q15_PREPARATION',
                measurement_execution_command_present=False,
                debug_symbol_strategy='UNSTRIPPED_RELEASE_BINARIES_WITH_EXACT_BUILD_PROVENANCE',
                software_prefetch_mapping_id='X86-64-PREFETCHT0-ONLY-v1')
            self.manifest['stage17_fixed_action_runtime']['synthetic_test_only'] = synthetic
            self.identity['synthetic_test_only'] = synthetic
            self.refresh_worker()
            path = self.bundle / 'config/examples/stage16-stand-inputs.example.json'; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"authoritative":false,"required_external_inputs":{}}'); self.seal()
            output = io.StringIO()
            with patch.object(sys, 'argv', ['verify', '--root', str(self.bundle)]), contextlib.redirect_stderr(output):
                self.assertEqual(verifier.main(), 1)  # This fixture deliberately has no qualified release.
            failures = output.getvalue()
            for absent in ('unknown bundle profile', 'wrong protocol version', 'runtime binding is invalid', 'lacks fixed dispatcher'):
                self.assertNotIn(absent, failures)
            self.assertEqual('misses codegen report formal_codegen_report.json' in failures, formal)
            self.assertIn('misses codegen report discovery_codegen_report.json', failures)

    def test_production_cannot_substitute_hermetic_native_report_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            args=['create', '--source-root', temporary, '--build-dir', temporary,
                  '--output-dir', str(Path(temporary)/'out'), '--profile', 'stage17-pilot-candidate',
                  '--native-codegen-report-dir', temporary]
            with patch.object(sys, 'argv', args), patch.object(creator, 'git', return_value=''):
                with self.assertRaisesRegex(ValueError, 'restricted to the hermetic profile'):
                    creator.main()

    def test_creator_has_eight_gates_and_successor_profiles(self):
        self.assertEqual(creator.STAGE17_PROFILE, 'STAGE17-PILOT-CANDIDATE-BUNDLE-v26')
        self.assertEqual(creator.STAGE17_DRY_RUN_PROFILE, 'STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22')
        self.assertEqual(len(creator.STAGE17_CODEGEN_INPUTS), 8)
        self.assertEqual(creator.STAGE17_CODEGEN_INPUTS['formal_codegen_report.json'],
            ('cpu_prefetch_runner', 'check_formal_codegen.py'))


class FormalReportBinding(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in (*gate.SOURCE_PATHS, 'tools/check_formal_codegen.py'):
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(name)
        self.binary = self.root / 'worker'; self.binary.write_bytes(b'software-only-ELF-placeholder')
        ops = {worker.key(): {'root_address': '0x1', 'active_addresses': ['0x2'],
            'cold_boundary_addresses': ['0x3'], 'native_reference_path': ['entry', 'worker'],
            'raw_clock_call_sites': {'worker': ['0x2']}, 'prefetch_vector': worker.vector(),
            'prefetch_witnesses': [[16, name] for name in worker.vector()]} for worker in gate.expected_workers()}
        tool = dict(status='PASS', version='22.1.6', disassembly_sha256='a'*64, operations=ops,
            negative_checks={name:'REJECTED' for name in gate.NEGATIVE_CASES})
        self.report = dict(schema_version=gate.SCHEMA, status='PASS', missing_tools=[],
            binary_sha256=release.sha256_file(self.binary), rule_set_sha256=release.sha256_file(self.root/'tools/check_formal_codegen.py'),
            source_evidence={name:release.sha256_file(self.root/name) for name in gate.SOURCE_PATHS},
            tools={name:copy.deepcopy(tool) for name in ('GNU_OBJDUMP','LLVM_OBJDUMP')})

    def verify(self, report=None):
        gate.validate_report_bindings(self.report if report is None else report, binary=self.binary, source_root=self.root)

    def test_exact_bindings_pass(self): self.verify()

    def test_worker_checker_and_source_drift_rejected(self):
        for path in (self.binary, self.root/'tools/check_formal_codegen.py', self.root/gate.SOURCE_PATHS[0]):
            original = path.read_bytes(); path.write_bytes(original+b'drift')
            with self.assertRaises(gate.AuditError): self.verify()
            path.write_bytes(original)

    def test_missing_tools_workers_mutants_and_cross_tool_witnesses_reject(self):
        for mutant in ('tool','worker','negative','version','digest','clock','vector','boolean_vector','witness','status'):
            r=copy.deepcopy(self.report); llvm=r['tools']['LLVM_OBJDUMP']; key=next(iter(llvm['operations']));op=llvm['operations'][key]
            if mutant=='tool': del r['tools']['GNU_OBJDUMP']
            elif mutant=='worker': del llvm['operations'][key]
            elif mutant=='negative': llvm['negative_checks'].pop('hidden_hot_tls')
            elif mutant=='version': llvm['version']='21.1'
            elif mutant=='digest': llvm['disassembly_sha256']='invalid'
            elif mutant=='clock': op['raw_clock_call_sites']={}
            elif mutant=='vector': op['prefetch_vector']={'invented':1}
            elif mutant=='boolean_vector':
                selected=next(v for v in llvm['operations'].values() if v['prefetch_vector'])
                selected['prefetch_vector']={k:True for k in selected['prefetch_vector']}
            elif mutant=='witness': op['active_addresses']=['0x4']
            else: r['status']='FAIL'
            with self.subTest(mutant=mutant), self.assertRaises(gate.AuditError): self.verify(r)

if __name__ == '__main__': unittest.main()
