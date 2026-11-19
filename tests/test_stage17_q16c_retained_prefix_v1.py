"""D288 failed diagnostic: real eight-artifact custody and no science credit."""
from dataclasses import asdict
import hashlib
import pathlib
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from test_stage17_formal_archive_v1 import ArchiveFixture, codec_limit, digest
from test_stage17_formal_checkpoint_v1 import fixture as checkpoint_fixture
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_registry_v1 as registry
import stage17_formal_checkpoint_v1 as checkpoint
import stage17_q16c_retained_prefix_v1 as current
import stage17_q16c_execution_window_v3 as window
import types
import stage17_formal_archive_runtime_v1 as runtime
import stage17_q16c_archive_scope_v1 as images
import stage17_service_daycap_execution_v1 as daycap
from test_stage17_formal_archive_runtime_v1 import MODULES, image


class RetainedPrefixTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=pathlib.Path(__file__).resolve().parents[1]/"build")
        self.addCleanup(temporary.cleanup)
        self.base = pathlib.Path(temporary.name)
        self.f = ArchiveFixture(self.base)
        self.root = self.base / "program"
        self.family = "b" * 64
        self.scope = custody.ProgramStore.initialize(self.root, program_id="synthetic-program",
            storage_domain_id="synthetic-domain", prospective_admission_sha256="c" * 64)
        self.limits = custody.CustodyLimits(131072, 1024, 4096, 131072,
                                           time.monotonic_ns() + 60_000_000_000)
        self.store = custody.ProgramStore(self.root, scope_sha256=self.scope,
                                          family_id=self.family, limits=self.limits)
        self.store.__enter__()
        self.addCleanup(lambda: self.store.__exit__(None, None, None) if self.store._lock else None)
        working = self.store.prepare_family(self.family)
        final, self.capture, _ = checkpoint_fixture()
        final.update(action_id="Q16c",capture_ordinal=86,
                     native_complete=getattr(self, 'native_complete', False))
        final["native_result_after_cleanup"]["stop"]=14 if final['native_complete'] else 10
        self.final = final
        self.capture["ordinal"]=86
        self.sources, encoded = [], []
        for name in registry.capture_names("Q16c", 86):
            role = registry.role_profile("Q16c", name)
            data = b'{"synthetic_control":true}' if role.layout == "bytes" else b""
            phase = next((p for p in ("warmup", "measurement") if f"-{p}-" in name), None)
            run_id = self.capture[phase]["run_id"] if phase else None
            worker = next((w for w in ("producer", "consumer") if f"-{w}" in name), None)
            header, _ = self.f.header(data, role.layout)
            width = role.row_bytes(run_id)
            header.update(artifact_id=self.family + ":" + name, artifact_role=role.artifact_role,
                canonical_format=role.canonical_format, phase=phase, run_id=run_id, worker=worker,
                row_bytes=width, row_count=0 if width else None,
                block_size_bytes=8192 * width if width else archive.BYTE_BLOCK)
            (working / name).write_bytes(data)
            source = custody.SourceBinding(header["artifact_id"],
                custody.BoundFile(name, len(data), digest(data)),
                archive.PhysicalBinding(len(data), digest(data)), None)
            self.sources.append(source)
            encoded.append((header, role, self.f.encode(data, header)))
        final["artifacts"] = [asdict(s.expected) for s in self.sources]
        raw = archive.canonical(final)
        self.checkpoint = custody.BoundFile("formal-capture-86-final-checkpoint.json", len(raw), digest(raw))
        (working / self.checkpoint.file_name).write_bytes(raw)

        def verify(document, sources):
            # This fixture checks native receipt semantics; actual process
            # quiescence is covered by the separate real-worker channel tests.
            checkpoint.validate_checkpoint(document, action="Q16c", plan_sha256=self.family,
                                            capture=self.capture, sources=sources)

        self.store.begin_capture(self.checkpoint, tuple(self.sources), verify_checkpoint=verify)
        for source, (header, role, wire) in zip(self.sources, encoded, strict=True):
            stem = hashlib.sha256(source.artifact_id.encode()).hexdigest()
            staging = self.store.reserve_archive(source.artifact_id, staging_name=stem + ".staging",
                                                  maximum_archive_bytes=len(wire) + 4096)
            with staging.open("xb") as stream: stream.write(wire)
            with codec_limit():
                self.store.verify_and_publish(source.artifact_id, archive_name=stem + ".cpfa",
                    expected_header=header, role=role, physical=archive.PhysicalBinding(len(wire), digest(wire)),
                    profile=self.f.profile, limits=self.f.limits)
                self.store.release_working_copy(source.artifact_id, profile=self.f.profile, limits=self.f.limits)
        rows = []
        for source in self.sources:
            record = self.store._states[source.artifact_id]
            rows.append(dict(logical=asdict(source.expected), expected_logical=asdict(source.expected),
                failure_receipt=None, artifact_id=source.artifact_id,
                released_record=asdict(self.store.ledger_binding(record)),
                archive_name=record["payload"]["archive_name"], physical=record["payload"]["physical"]))
        self.document = dict(schema_version="cpu-prefetch-stage17-formal-archive-custody/1",
            program_scope_sha256=self.scope, plan_sha256=self.family, capture_ordinal=86,
            checkpoint=asdict(self.checkpoint), ledger_tip=asdict(self.store.ledger_binding()),
            artifacts=rows, status="ARCHIVED_AND_RELEASED", scientific_validity="NOT_ASSESSED",
            execution_authority=False)
        self.receipt = self.store.retain_custody_receipt("formal-capture-86-archive-custody.json",
                                                        archive.canonical(self.document))

    def diagnostic(self):
        fixed=dict(checkpoint=(self.checkpoint.size_bytes,self.checkpoint.sha256),
            custody=(self.receipt.size_bytes,self.receipt.sha256))
        with patch.object(current.incident,'FIXED',fixed),patch.object(current.incident.contract,'PARENT_SHA256',self.family):
            return current.verify_failed_custody(store=self.store,capture=self.capture,
                checkpoint_binding=asdict(self.checkpoint),receipt_binding=asdict(self.receipt),
                decoder_profile=self.f.profile,decoder_limits=self.f.limits)

    def test_real_failed_custody_remains_failed_and_original_scientific_gate_rejects_it(self):
        before={str(p.relative_to(self.root)):digest(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(custody.CustodyError,'native checkpoint completion'):
            registry.verify_capture_metadata(store=self.store,action='Q16c',capture=self.capture,
                checkpoint_binding=asdict(self.checkpoint),receipt_binding=asdict(self.receipt),
                decoder_profile=self.f.profile,decoder_limits=self.f.limits)
        result=self.diagnostic()
        self.assertFalse(result['native_complete']);self.assertTrue(result['retained_diagnostic_only'])
        self.assertFalse(result['inverse_readback_performed']);self.assertFalse(result['execution_authority'])
        self.assertEqual(result['scientific_validity'],'NOT_ASSESSED');self.assertEqual(len(result['artifacts']),8)
        after={str(p.relative_to(self.root)):digest(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_actual_corrupt_failed_archive_cannot_hide_behind_recorded_ledger_hash(self):
        path=self.root/'archives'/self.document['artifacts'][0]['archive_name']
        raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
        with self.assertRaises(archive.ArchiveError):self.diagnostic()

    def test_unknown_incident_binding_or_ordinal_does_not_reach_any_decoder(self):
        with self.assertRaises(current.incident.admission.AdmissionError):
            current.verify_failed_custody(store=self.store,capture=self.capture,
                checkpoint_binding=asdict(self.checkpoint),receipt_binding=asdict(self.receipt),
                decoder_profile=self.f.profile,decoder_limits=self.f.limits)

    def test_unknown_authority_is_rejected_before_private_retention_configuration(self):
        authority=self.base/'authority';authority.write_bytes(b'{}')
        with self.assertRaisesRegex(current.incident.admission.AdmissionError,'consumed original authority'):
            current.prepare_original(types.SimpleNamespace(),authorization_path=authority)


class PrivateRuntimeTests(unittest.TestCase):
    def fixture(self, *, complete):
        f = RetainedPrefixTests('runTest')
        f.native_complete = complete
        self.addCleanup(f.doCleanups)
        f.setUp()
        f.store.__exit__(None, None, None)
        source = f.base / 'private-runtime'
        source.mkdir()
        tools = pathlib.Path(__file__).resolve().parents[1] / 'tools'
        modules = (*MODULES, 'stage17_archive_metadata_fast_v1',
                   'stage17_archive_metadata_fast_v2', 'stage17_archive_canonical_fast_v1')
        for name in modules:
            shutil.copyfile(tools / (name + '.py'), source / (name + '.py'))
        # Same bounded-reader adapter as the stand, with independently imported
        # archive/custody dataclasses. No native helper or measured code needed.
        path = source / 'stage17_formal_archive_custody_v1.py'
        with path.open('ab') as stream:
            stream.write(b'\nfrom stage17_archive_metadata_fast_v2 import make_store_class as _private_store\n'
                         b'ProgramStore = _private_store(base=ProgramStore)\n')
        profile = runtime.RuntimeProfile(image(sys.executable), image(sys.executable), f.f.profile,
            tuple(runtime.ModuleBinding(name, image(source / (name + '.py'))) for name in modules))
        prefix = '_d273_archive_' + str(os.getpid()) + '_'
        self.addCleanup(lambda: [sys.modules.pop(name) for name in list(sys.modules) if name.startswith(prefix)])
        a, c = images.selected_archive_modules(profile, time.monotonic_ns() + 30 * 10**9)
        self.assertIsNot(a.PhysicalBinding, archive.PhysicalBinding)
        self.assertEqual(asdict(a.PhysicalBinding(1, 'a' * 64)), asdict(archive.PhysicalBinding(1, 'a' * 64)))
        f.store = c.ProgramStore(f.root, scope_sha256=f.scope, family_id=f.family,
                                limits=c.CustodyLimits(**asdict(f.limits)))
        f.store.__enter__()
        self.addCleanup(f.store.__exit__, None, None, None)
        return f, a, c

    def test_private_complete_capture_uses_native_binding_types(self):
        f, a, c = self.fixture(complete=True)
        with self.assertRaisesRegex(c.CustodyError, 'metadata binding differs'):
            registry.verify_capture_metadata(store=f.store, action='Q16c', capture=f.capture,
                checkpoint_binding=asdict(f.checkpoint), receipt_binding=asdict(f.receipt),
                decoder_profile=f.f.profile, decoder_limits=f.f.limits)
        verifier = current.make_capture_registry(a, c)
        result = verifier.verify_capture_metadata(store=f.store, action='Q16c', capture=f.capture,
            checkpoint_binding=asdict(f.checkpoint), receipt_binding=asdict(f.receipt),
            decoder_profile=a.DecoderProfile(**asdict(f.f.profile)),
            decoder_limits=a.DecodeLimits(**asdict(f.f.limits)))
        self.assertEqual(len(result['artifacts']), 8)
        self.assertFalse(result['inverse_readback_performed'])
        self.assertEqual(result['scientific_validity'], 'NOT_ASSESSED')
        self.assertIs(registry._bound.__globals__['custody'], custody)

    def test_private_failed_diagnostic_remains_excluded_from_complete_captures(self):
        f, a, c = self.fixture(complete=False)
        verifier = current.make_capture_registry(a, c)
        args = dict(store=f.store, capture=f.capture, checkpoint_binding=asdict(f.checkpoint),
                    receipt_binding=asdict(f.receipt), decoder_profile=a.DecoderProfile(**asdict(f.f.profile)),
                    decoder_limits=a.DecodeLimits(**asdict(f.f.limits)))
        with self.assertRaisesRegex(c.CustodyError, 'native checkpoint completion'):
            verifier.verify_capture_metadata(action='Q16c', **args)
        fixed = dict(checkpoint=(f.checkpoint.size_bytes, f.checkpoint.sha256),
                     custody=(f.receipt.size_bytes, f.receipt.sha256))
        with patch.object(current.incident, 'FIXED', fixed), \
                patch.object(current.incident.contract, 'PARENT_SHA256', f.family):
            result = current.verify_failed_custody(registry=verifier, **args)
        self.assertFalse(result['native_complete'])
        self.assertTrue(result['retained_diagnostic_only'])
        self.assertFalse(result['execution_authority'])

    def test_private_verifier_keeps_exact_metadata_archive_and_ledger_gates(self):
        f, a, c = self.fixture(complete=True)
        verifier = current.make_capture_registry(a, c)
        args = dict(store=f.store, action='Q16c', capture=f.capture,
                    checkpoint_binding=asdict(f.checkpoint), receipt_binding=asdict(f.receipt),
                    decoder_profile=a.DecoderProfile(**asdict(f.f.profile)),
                    decoder_limits=a.DecodeLimits(**asdict(f.f.limits)))
        before = {str(p.relative_to(f.root)): digest(p.read_bytes()) for p in f.root.rglob('*') if p.is_file()}
        verifier.verify_capture_metadata(**args)
        after = {str(p.relative_to(f.root)): digest(p.read_bytes()) for p in f.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        for field, wrong in (('sha256', '0' * 64), ('size_bytes', f.checkpoint.size_bytes + 1)):
            with self.subTest(field=field), self.assertRaisesRegex(c.CustodyError, 'metadata binding differs'):
                verifier.verify_capture_metadata(**{**args, 'checkpoint_binding': {
                    **args['checkpoint_binding'], field: wrong}})
        paths = (f.root / 'archives' / f.document['artifacts'][0]['archive_name'],
                 f.root / 'ledger' / f.document['artifacts'][0]['released_record']['file_name'])
        for path in paths:
            raw = path.read_bytes()
            try:
                path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
                with self.subTest(path=path.name), self.assertRaises((a.ArchiveError, c.CustodyError)):
                    verifier.verify_capture_metadata(**args)
            finally:
                path.write_bytes(raw)

    def test_suffix_inventory_uses_its_own_public_store_without_namespace_mixing(self):
        f = RetainedPrefixTests('runTest')
        f.native_complete = True
        self.addCleanup(f.doCleanups)
        f.setUp()
        output = daycap.make_output_registry()
        result = output._verified_inventory(store=f.store, plan=dict(action_id='Q16c',
            storage=dict(program_id='synthetic-program'), captures=[dict(capture=f.capture)]),
            extent=types.SimpleNamespace(captures=[types.SimpleNamespace(ordinal=86)]),
            report=dict(captures=[dict(checkpoint=asdict(f.checkpoint), archive_custody=asdict(f.receipt),
                artifacts=[asdict(s.expected) for s in f.sources])],
                native_results_after_cleanup=[f.final['native_result_after_cleanup']]),
            profile=types.SimpleNamespace(decoder=f.f.profile), decoder_limits=f.f.limits, metadata_only=True)
        self.assertEqual(len(result['captures']), 1)
        self.assertFalse(result['inverse_readback_performed'])

if __name__=='__main__':unittest.main()
