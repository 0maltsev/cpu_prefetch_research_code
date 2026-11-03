"""Actual profile files with synthetic release contexts; no phase authority."""
import hashlib
import copy
import datetime as dt
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_stage17_phase_controller_v25 as historical_tests
from test_stage17_formal_plan_v2 import archived_fixture
from test_stage17_formal_archive_runtime_v1 import MODULES
from test_stage17_formal_archive_v1 import ArchiveFixture
import stage17_phase_controller_v26 as controller
import stage17_formal_archive_v1 as archive
import stage17_archive_bundle_profile_v1 as bundle_profile
import stage17_pilot_candidate_artifact_v12 as release
import stage17_semantic_verifier_v58 as semantic
import stage17_operational_cli_v18 as cli
import stage17_fixed_action_executor_v11 as executor
import stage17_formal_archive_custody_v1 as custody


class ArchiveControllerTests(unittest.TestCase):
    def setUp(self):
        self.original = historical_tests.FormalController()
        self.original.setUp()
        self.addCleanup(self.original.doCleanups)
        self.request = self.original.request
        self.request["schema_version"] = "cpu-prefetch-stage17-fixed-action-request/6"
        self.validation = self.original.validation
        self.plan = self.original.plan
        self.plan["schema_version"] = controller.plans.VERSION["Q16a"]
        defaults = archived_fixture("Q16a")
        self.plan["custody_policy_id"] = defaults["custody_policy_id"]
        self.plan["storage"] = defaults["storage"]
        storage = self.plan["storage"]
        storage["analysis_capture_workspace_bytes"] = 512 * 1024**2
        budget = self.plan["budget"]
        budget["memory_bytes"] += storage["codec_address_space_bytes"] + storage["broker_address_space_bytes"]
        budget["watchdog_ns"] += len(self.plan["captures"]) * storage["per_capture_archive_ns"]
        for key in ("analysis_scratch_bytes", "disk_reserve_bytes", "required_free_disk_bytes"):
            budget[key] = defaults["budget"][key]
        root = self.original.root / "bundle"
        (root / "tools").mkdir(parents=True)
        (root / "config/stage17").mkdir(parents=True)
        encoder = root / "software-fixture-encoder"
        encoder.write_bytes(b"software-only image; never executed or qualified")
        tools = Path(__file__).resolve().parents[1] / "tools"
        for name in MODULES:
            shutil.copyfile(tools / (name + ".py"), root / "tools" / (name + ".py"))

        def binding(path, location):
            path = path.resolve()
            return dict(location=location, path=str(path.relative_to(root if location == "bundle" else Path("/"))),
                        size_bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        decoder = ArchiveFixture(self.original.root).profile
        document = dict(schema_version="cpu-prefetch-formal-archive-implementation-profile/1",
            policy_id=archive.POLICY_ID, encoder=binding(encoder, "bundle"),
            python=binding(Path(sys.executable), "runtime"),
            zstd_library=binding(decoder.zstd_library_path, "runtime"),
            source_closure=[dict(module=name, image=binding(root / "tools" / (name + ".py"), "bundle"))
                            for name in MODULES],
            options=dict(zstd_version="1.5.7", compression_level=3, worker_threads=1, nbWorkers=0,
                         window_log=22, checksum_flag=1, content_size_flag=1, dictionary_id_flag=0))
        raw = archive.canonical(document)
        path = root / "config/stage17/formal-archive-implementation-profile-v1.json"
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        storage["implementation_profile_sha256"] = digest
        self.context = self.original.context
        self.context.update(archive_profile_binding=dict(path=bundle_profile.PROFILE_PATH, size_bytes=len(raw), sha256=digest),
                            archive_bundle_root=str(root), archive_runtime_root="/")
        self.original.namespace["plan_sha256"] = hashlib.sha256(archive.canonical(self.plan)).hexdigest()
        self.request["action_inputs"]["prerequisite_bindings"]["namespace_registry"] = self.original.write(
            "namespaces", self.original.namespace)

    def profile(self):
        return controller.qualified_archive_profile(self.request, self.validation,
                                                    deadline_ns=time.monotonic_ns() + 5_000_000_000)

    def test_complete_original_plan_and_actual_profile_admitted_without_execution(self):
        extent = controller.validate_action_inputs(self.request, self.validation)
        self.assertEqual(len(extent.captures), 708)
        self.assertFalse(extent.execution_authority)
        profile = self.profile()
        self.assertEqual(profile.decoder.implementation_profile_sha256,
                         self.plan["storage"]["implementation_profile_sha256"])

    def test_absent_or_unqualified_profile_has_no_host_fallback(self):
        for key in ("archive_profile_binding", "archive_bundle_root", "archive_runtime_root"):
            value = self.context.pop(key)
            with self.assertRaises(controller.ControllerError): self.profile()
            self.context[key] = value
        self.context["bundle_profile"] = "STAGE17-PILOT-CANDIDATE-BUNDLE-v25"
        with self.assertRaises(controller.ControllerError): self.profile()

    def test_signed_profile_original_bytes_and_local_closure_must_match(self):
        expected = self.plan["storage"]["implementation_profile_sha256"]
        self.plan["storage"]["implementation_profile_sha256"] = "0" * 64
        with self.assertRaises(controller.ControllerError): self.profile()
        self.plan["storage"]["implementation_profile_sha256"] = expected
        source = Path(self.context["archive_bundle_root"]) / "tools/check_canonical.py"
        source.write_bytes(source.read_bytes() + b"\n# mutated\n")
        with self.assertRaises(controller.ControllerError): self.profile()

    def test_profile_path_cannot_escape_qualified_bundle_or_extend_deadline(self):
        with self.assertRaises(controller.ControllerError):
            controller.qualified_archive_profile(self.request, self.validation, deadline_ns=1)
        self.context["archive_profile_binding"]["path"] = str(self.original.root / "foreign.json")
        with self.assertRaises(controller.ControllerError): self.profile()

    def test_archive_validator_does_not_mutate_historical_globals(self):
        original = controller.previous.contract.validate_plan
        namespace = dict(controller.previous.validate_action_inputs.__globals__)
        controller.validate_action_inputs(self.request, self.validation)
        self.assertIs(controller.previous.contract.validate_plan, original)
        self.assertEqual(namespace, controller.previous.validate_action_inputs.__globals__)


class ArchiveProducerIntegration(unittest.TestCase):
    """Real receipt/context, profile, CLI, SSHSIG and executor preparation.

    Only package qualification and the operational journal are synthetic input
    seams. Files, receipt revalidation, source closure, signature, sealed inputs
    and program ledger are real. Stop before the attempt marker/worker boundary;
    this is software verification and supplies no stand authority.
    """
    def setUp(self):
        helper = ArchiveControllerTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        self.helper = helper
        self.root = helper.original.root
        self.plan = helper.plan
        self.validation = helper.validation
        bundle = Path(helper.context['archive_bundle_root'])
        tools = Path(__file__).resolve().parents[1] / 'tools'
        self.repository = tools.parent
        # Use the actual production profile producer and its entire closure.
        for name in bundle_profile.local_source_closure(tools):
            shutil.copyfile(tools / (name + '.py'), bundle / 'tools' / (name + '.py'))
        for member, data in (
            (bundle_profile.ENCODER_PATH, b'software encoder; never executed'),
            ('BUNDLE_MANIFEST.json', b'software manifest'),
            ('SHA256SUMS', b'software checksum inventory'),
            ('SBOM.spdx.json', b'software SBOM'),
            ('BUNDLE_INVENTORY.json', b'software inventory'),
            ('validators/verify_stand_bundle.py', b'software verifier'),
            ('release/bin/cpu_prefetch_runner', b'#!/bin/sh\nexit 99\n')):
            path = bundle / member
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        worker = bundle / 'release/bin/cpu_prefetch_runner'
        worker.chmod(0o500)
        library = ArchiveFixture(self.root).profile.zstd_library_path
        (bundle / bundle_profile.ZSTD_PATH).parent.mkdir(parents=True)
        shutil.copyfile(library, bundle / bundle_profile.ZSTD_PATH)
        self.runtime_root = self.root / 'runtime'
        python = self.runtime_root / bundle_profile.PYTHON_PATH
        python.parent.mkdir(parents=True)
        shutil.copyfile(Path(sys.executable).resolve(), python)
        profile = bundle_profile.build_profile(bundle_root=bundle,
            runtime_root=self.runtime_root, window_log=22)
        profile_path = bundle / bundle_profile.PROFILE_PATH
        profile_path.write_bytes(bundle_profile.canonical(profile))
        self.plan['storage']['implementation_profile_sha256'] = self.sha(profile_path)
        def size(member): return (bundle / member).stat().st_size
        context = release.ExtractedReleaseContext(bundle_root=bundle,
            manifest_size_bytes=size('BUNDLE_MANIFEST.json'), manifest_sha256=self.sha(bundle / 'BUNDLE_MANIFEST.json'),
            source_revision=self.plan['source_revision'], worker_path=worker,
            worker_member_path='release/bin/cpu_prefetch_runner', worker_size_bytes=worker.stat().st_size,
            worker_sha256=self.sha(worker), worker_role='STAGE17_FIXED_ACTION_WORKER',
            runtime_profile='STAGE17-FIXED-ACTION-WORKER-v4', supported_actions=release.SUPPORTED_ACTIONS,
            bundle_profile='STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22', synthetic_test_only=True,
            sha256s_sha256=self.sha(bundle / 'SHA256SUMS'), sbom_sha256=self.sha(bundle / 'SBOM.spdx.json'),
            inventory_sha256=self.sha(bundle / 'BUNDLE_INVENTORY.json'),
            full_verifier_size_bytes=size('validators/verify_stand_bundle.py'),
            full_verifier_sha256=self.sha(bundle / 'validators/verify_stand_bundle.py'))
        self.enterContext(patch.object(release, 'verify_extracted_bundle_v12', return_value=context))
        receipt = release.build_extracted_release_receipt_v12(bundle_root=bundle,
            receipt_id='SOFTWARE-PRODUCER-RECEIPT', archive_runtime_root=self.runtime_root)
        qualified = release.ArchiveExtractedReleaseContext(**asdict(context), archive_runtime_provenance=receipt)
        for i in range(1, 7):
            name = f'S17-EXT-{i:03d}'
            row = self.validation.resolutions.setdefault(name, SimpleNamespace(semantic_context={}))
            row.input_id, row.resolution_id, row.sha256 = name, 'software-resolution-'+str(i), str(i)*64
        self.validation.current_state = 'READY_FOR_STAGE17_PHASE_AUTHORIZATION'
        self.validation.resolutions['S17-EXT-003'].semantic_context['release'] = qualified
        helper.context.update({name:getattr(context, name) for name in (
            'bundle_profile', 'manifest_sha256', 'manifest_size_bytes', 'source_revision',
            'sha256s_sha256', 'sbom_sha256', 'inventory_sha256')})
        helper.context.update(release_artifact_path=str(worker), release_artifact_size_bytes=worker.stat().st_size,
                              release_artifact_sha256=self.sha(worker))
        # Do not replace the producer's relative path with a fixture absolute path.
        helper.context.update(self.produce_context())
        self.assertEqual(helper.context['archive_profile_binding'], receipt['archive_profile_binding'])
        self.assertEqual(receipt['archive_profile_binding']['path'], bundle_profile.PROFILE_PATH)
        storage = self.plan['storage']
        program = self.root / 'program'
        storage['program_scope_sha256'] = custody.ProgramStore.initialize(program,
            program_id=storage['program_id'], storage_domain_id='software-domain',
            prospective_admission_sha256='e'*64)
        family = hashlib.sha256(archive.canonical(self.plan)).hexdigest()
        with patch.object(custody.os, 'statvfs', return_value=SimpleNamespace(f_bavail=10**13, f_frsize=1, f_favail=100000)), \
             custody.ProgramStore(program, scope_sha256=storage['program_scope_sha256'], family_id=family,
                limits=executor.custody_limits(storage, time.monotonic_ns()+60_000_000_000)) as store:
            self.output = store.prepare_family(family)
        helper.original.namespace['plan_sha256'] = family
        helper.request['action_inputs']['prerequisite_bindings']['namespace_registry'] = helper.original.write(
            'namespaces', helper.original.namespace)
        key = self.root / 'key'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],
                       check=True, capture_output=True, timeout=10)
        allowed = self.root / 'allowed-signers'
        allowed.write_text('software-owner '+key.with_suffix('.pub').read_text())
        self.validation.resolutions['S17-EXT-003'].semantic_context['trust'] = dict(subject_id='synthetic-stand',
            measurements=dict(principal='software-owner', reviewer_role='OWNER',
                sshsig_namespace='stage17-owner-acceptance', allowed_signers_path=str(allowed),
                allowed_signers_size_bytes=allowed.stat().st_size, allowed_signers_sha256=self.sha(allowed)))
        self.validation.resolutions['S17-EXT-002'].semantic_context['stand_id'] = 'synthetic-stand'
        (self.root / 'journal').mkdir()
        (self.root / 'journal/stage17-state-journal-000000.json').write_text('{}')
        self.enterContext(patch.object(cli.journal, 'validate_operational_journal', return_value=self.validation))
        self.inputs = self.root / 'inputs.json'
        self.inputs.write_bytes(cli.canonical(helper.request['action_inputs']))

    @staticmethod
    def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

    def produce_context(self):
        return semantic._qualified_archive_context(self.helper.context, root=self.repository,
                                                   admitted_resolutions=self.validation.resolutions)

    def author_request(self, name='request.json'):
        destination = self.root / name
        cli.author_formal_request(repository_root=self.repository, evidence_root=self.root, synthetic=True,
            action_id='Q16a', action_inputs_path=self.inputs, request_id='request', authorization_id='auth',
            attempt_id='attempt', session_id='session', output_root=self.output, destination=destination)
        return destination

    def test_producer_context_public_author_signature_and_executor_preparation(self):
        request_path = self.author_request()
        now = dt.datetime.now(dt.timezone.utc)
        stamp = lambda value:value.isoformat(timespec='seconds').replace('+00:00','Z')
        authorization = self.root / 'authorization.json'
        cli.author_formal_authorization(repository_root=self.repository, evidence_root=self.root,
            synthetic=True, request_path=request_path, actor='software-owner', reviewer='OWNER',
            issued_at_utc=stamp(now-dt.timedelta(seconds=1)), expires_at_utc=stamp(now+dt.timedelta(seconds=120)),
            destination=authorization)
        self.assertFalse(Path(str(authorization)+'.sig').exists())
        subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(self.root/'key'),'-n',
            'stage17-owner-acceptance',str(authorization)], check=True, capture_output=True, timeout=10)
        arguments = dict(repository_root=self.repository, operational_evidence_root=self.root,
            journal=self.root/'journal/stage17-state-journal-000000.json', journal_directory=self.root/'journal',
            authorization_path=authorization, signature_path=Path(str(authorization)+'.sig'), synthetic_test_only=True)
        prepared = cli.verify_formal_signature(**arguments)
        self.assertIsInstance(prepared, controller.PreparedArchiveAction)
        self.assertEqual(prepared.archive_runtime_profile.decoder.implementation_profile_sha256,
                         self.plan['storage']['implementation_profile_sha256'])
        self.assertEqual(prepared.archive_runtime_profile.python.path, self.runtime_root / bundle_profile.PYTHON_PATH)
        # Exercise the actual executor through sealed worker/request/context and
        # program-ledger admission; stop immediately before the attempt marker.
        class PreparationComplete(Exception): pass
        observations = []
        real_resources = executor.live_resources
        def resources(fd, extent, **kwargs):
            observations.append(real_resources(fd, extent, **kwargs))
            raise PreparationComplete()
        def capacity(fd, extent):
            return dict(observed_at_utc=executor.previous._utc_now(), memory_available_bytes=extent.declared.memory_bytes,
                filesystem_available_bytes=10**13, filesystem_device=os.fstat(fd).st_dev,
                required_memory_bytes=extent.declared.memory_bytes,
                required_free_disk_bytes=extent.declared.required_free_disk_bytes, reservation_established=False)
        with patch.object(executor.previous, 'live_resources', side_effect=capacity), \
             patch.object(executor.os, 'fstatvfs', return_value=SimpleNamespace(f_bavail=10**13, f_frsize=1, f_favail=100000)), \
             patch.object(executor, 'live_resources', side_effect=resources), \
             patch.object(executor, 'run_archived_worker', side_effect=AssertionError('worker must not start')) as worker:
            with self.assertRaises(PreparationComplete): cli.execute_formal(**arguments)
        worker.assert_not_called()
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]['program_scope_sha256'], self.plan['storage']['program_scope_sha256'])
        self.assertEqual(list(self.output.iterdir()), [])
        # Real signature verification must still reject changed authority bytes.
        document = json.loads(authorization.read_bytes()); document['actor'] = 'changed-owner'
        authorization.write_bytes(cli.canonical(document))
        with self.assertRaises(controller.ControllerError): cli.verify_formal_signature(**arguments)

    def test_producer_receipt_drift_and_member_aliases_reject_before_request(self):
        qualified = self.validation.resolutions['S17-EXT-003'].semantic_context['release']
        receipt = qualified.archive_runtime_provenance
        original = copy.deepcopy(receipt)
        try:
            receipt['archive_profile_binding']['sha256'] = '0'*64
            with self.assertRaises(semantic.SemanticAdmissionError): self.produce_context()
        finally:
            receipt.clear(); receipt.update(original)
        binding = self.helper.context['archive_profile_binding']
        for path in ('../'+bundle_profile.PROFILE_PATH, './'+bundle_profile.PROFILE_PATH,
                     str(Path(self.helper.context['archive_bundle_root']) / bundle_profile.PROFILE_PATH)):
            with self.subTest(path=path):
                binding['path'] = path
                with self.assertRaises(controller.ControllerError): self.author_request()
                self.assertFalse((self.root / 'request.json').exists())
        binding['path'] = bundle_profile.PROFILE_PATH
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
