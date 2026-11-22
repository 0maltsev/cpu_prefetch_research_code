"""Actual sealed S180 broker/codecs and parked worker; synthetic data only."""
from __future__ import annotations
import argparse
import ast
import copy
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import resource
import struct
import subprocess
import sys
import tempfile
import time
import unittest

from test_stage17_formal_archive_v1 import ArchiveFixture, digest
from test_stage17_formal_archive_runtime_v1 import image, TOOLS
from test_stage17_s180_checkpoint_v1 import fixture
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_runtime_v1 as runtime
import stage17_formal_archive_v1 as archive
import stage17_s180_archive_broker_v1 as broker
import stage17_s180_archive_custody_v1 as store_module
import stage17_s180_checkpoint_v1 as contract
import stage17_s180_archive_channel_v1 as channel
import stage17_s180_archive_registry_v1 as registry
import stage17_process_group_supervisor_v3 as supervisor
from stage17_formal_checkpoint_v1 import PinnedWorker


def qualified_closure():
    pending = ["stage17_s180_archive_broker_v1", "stage17_formal_archive_runtime_v1"]
    found = {}
    while pending:
        name = pending.pop()
        if name in found:
            continue
        path = TOOLS / (name + ".py")
        found[name] = runtime.ModuleBinding(name, image(path))
        for node in ast.walk(ast.parse(path.read_bytes())):
            names = ([entry.name.split(".")[0] for entry in node.names] if isinstance(node, ast.Import)
                     else [node.module.split(".")[0]] if isinstance(node, ast.ImportFrom) and node.module else [])
            pending.extend(n for n in names if (TOOLS / (n + ".py")).is_file() and n not in found)
    return tuple(found[n] for n in sorted(found))


class S180BrokerTests(unittest.TestCase):
    encoder = None
    channel_fixture = None
    reserve_before_admission = False

    def setUp(self):
        if self.encoder is None:
            self.skipTest("requires actual compiled encoder")
        temp = tempfile.TemporaryDirectory(prefix="s180-custody-", dir=TOOLS.parent / "build")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        codec = ArchiveFixture(self.base).profile
        self.profile = runtime.RuntimeProfile(image(self.encoder), image(sys.executable),
            replace(codec, encoder_sha256=image(self.encoder).sha256), qualified_closure())
        self.deadline = time.monotonic_ns() + 90_000_000_000
        self.limits = runtime.RuntimeLimits(2*1024**3, 2*1024**3, 2*1024**2, 131072, 131072,
            2_000_000_000, self.deadline, self.deadline, 24)
        self.custody_limits = custody.CustodyLimits(131072, 4096, 8192, 131072, self.deadline)
        self.root = self.base / "program"
        self.scope = custody.ProgramStore.initialize(self.root, program_id="synthetic-s180", storage_domain_id="synthetic-disk",
            prospective_admission_sha256="a"*64)
        blueprint = json.loads((TOOLS.parent / "config/stage17/d310-s180-blueprint-v1.json").read_bytes())
        order = sorted(blueprint["captures"], key=lambda row: row["execution_ordinal"])
        plan = dict(schema_version="cpu-prefetch-stage17-s180-session-plan/1", blueprint=blueprint,
            captures=[dict(execution_ordinal=i, cell_ordinal=row["cell_ordinal"],
                execution_budget=dict(max_output_bytes=4*1024**2,archive_ns=90_000_000_000)) for i, row in enumerate(order)],
            storage=dict(pilot_policy_id="D310-S180-LOSSLESS-STAND-PRIMARY-v1", approval_sha256=contract.APPROVAL_SHA256,
                program_id="synthetic-s180", program_scope_sha256=self.scope,
                implementation_profile_sha256=self.profile.decoder.implementation_profile_sha256,
                archive_staging_bytes=4*1024**2))
        plan=self.configure_plan(plan)
        self.request = dict(schema_version="cpu-prefetch-stage17-s180-session-request/1", session_id="software-only-s180", plan=plan,
            prerequisite_bindings=dict(ext009_resolution_sha256="a"*64))
        self.family = digest(archive.canonical(plan))
        if self.reserve_before_admission:
            with self.store(ext009_resolution_sha256=None) as store:
                self.directory_reservation = store.reserve_family()
            with self.store() as store:
                store.bind_admission()
                self.working = store.prepare_family(self.family)
        else:
            with self.store() as store:
                self.working = store.prepare_family(self.family)
        self.original_scope = (self.root / "scope.json").read_bytes()
        self.document, _ = fixture()
        self.document.update(plan_sha256=self.family, program_scope_sha256=self.scope)
        row = order[0]
        self.originals = {}
        self.document["artifacts"] = []
        for name in contract.capture_names(0):
            role = contract.role_profile(0, name)
            phase = "warmup" if "-warmup-" in name else "measurement" if "-measurement-" in name else None
            run = row["warmup_run_id" if phase == "warmup" else "run_id"] if phase else None
            width = role.row_bytes(run)
            if role.layout in ("producer", "consumer"):
                encoded = run.encode()
                prefix = struct.pack("<I", len(encoded)) + encoded
                prefix += bytes((-len(prefix)) % 8)
                data = prefix + struct.pack("<"+"Q"*((width-len(prefix))//8), *range((width-len(prefix))//8))
            elif width:
                data = struct.pack("<3Q", 1, 1, 256)
            else:
                data = archive.canonical(dict(synthetic_test_only=True, scientific_validity="NOT_ASSESSED"))
            (self.working / name).write_bytes(data)
            self.originals[name] = data
            r, fmt, media = contract.artifact_identity(0, name)
            self.document["artifacts"].append(dict(role=r, schema_identity=fmt, media_type=media,
                file_name=name, size_bytes=len(data), sha256=digest(data)))
        self.write_checkpoint()

    def configure_plan(self,plan):
        return plan

    def store(self, **changes):
        args = dict(scope_sha256=self.scope, family_id=self.family, limits=self.custody_limits,
                    ext009_resolution_sha256="a"*64)
        args.update(changes)
        return store_module.ProgramStore(self.root, **args)

    def write_checkpoint(self):
        raw = archive.canonical(self.document)
        name = "s180-e0-checkpoint.json"
        (self.working / name).write_bytes(raw)
        self.checkpoint = custody.BoundFile(name, len(raw), digest(raw))

    def verify_metadata(self, store, receipt):
        return registry.verify_capture_metadata(store=store, capture=broker.capture_contract(self.request, 0),
            checkpoint_binding=asdict(self.checkpoint), receipt_binding=asdict(receipt),
            decoder_profile=self.profile.decoder,
            decoder_limits=archive.DecodeLimits(32768, 4*1024**2, 4*1024**2, 8*1024**2,
                4*1024**2, 100, 1<<22, self.deadline))

    def live(self):
        lease = supervisor.SupervisorLease()
        lease.enter()
        process = subprocess.Popen([sys.executable, "-B", "-c", "import os;os.read(0,1)"], stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        worker = PinnedWorker(process.pid)
        try:
            before = resource.getrlimit(resource.RLIMIT_AS)
            with broker.ArchiveBrokerClient(profile=self.profile, limits=self.limits,
                    identity_model=lease.identity_model, native_worker=worker) as client:
                outcome = client.archive_capture(program_root=self.root, scope_sha256=self.scope, family_id=self.family,
                    custody_limits=self.custody_limits, request_document=self.request, capture_ordinal=0, checkpoint=self.checkpoint)
                self.assertEqual(client.actual_processes, 25)
            self.assertEqual(resource.getrlimit(resource.RLIMIT_AS), before)
            self.assertIsNone(process.poll())
            worker.observe_quiescence()
            return outcome
        finally:
            process.stdin.close()
            proof = supervisor.cleanup_process_group(process, force_stop=False,
                leader_wait_deadline_ns=time.monotonic_ns()+2_000_000_000, global_deadline_ns=self.deadline,
                identity_model=lease.identity_model)
            worker.close()
            lease.close()
            self.assertTrue(proof.leader_reaped and proof.process_group_gone)

    def test_actual_broker_reconstructs_all_eight_sources_and_preserves_shared_quota(self):
        outcome = self.live()
        self.assertEqual(outcome.status, "ARCHIVED_AND_RELEASED")
        self.assertEqual(outcome.receipt.file_name, "s180-e0-archive-custody.json")
        receipt = json.loads((self.working / outcome.receipt.file_name).read_bytes())
        self.assertEqual(receipt["schema_version"], contract.CUSTODY_SCHEMA)
        self.assertEqual(len(receipt["artifacts"]), 8)
        self.assertFalse(receipt["execution_authority"])
        self.assertEqual((self.root / "scope.json").read_bytes(), self.original_scope)
        with self.store() as store:
            store.prepare_family(self.family)
            extension = json.loads((store.root / "metadata" / receipt["storage_extension"]["file_name"]).read_bytes())
            self.assertEqual(extension["shared_program_quota_bytes"], 6_000_000_000_000)
            self.assertEqual(extension["approval_sha256"], contract.APPROVAL_SHA256)
            self.assertFalse(extension["independent_raw_backup"])
            registration = store.read_verified_record(outcome.receipt_ledger_record)
            self.assertEqual(registration["kind"], "CUSTODY_RECEIPT")
            metadata = self.verify_metadata(store, outcome.receipt)
            self.assertTrue(metadata["continuation_allowed"])
            self.assertFalse(metadata["inverse_readback_performed"])
            for entry in receipt["artifacts"]:
                self.assertFalse((self.working / entry["logical"]["file_name"]).exists())
                released = store.read_verified_record(custody.BoundFile(**entry["released_record"]))["payload"]
                offline = runtime.RetainedReadbackLimits(**{key: value for key, value in vars(self.limits).items()
                    if key != "authority_expiry_monotonic_ns"})
                with broker.base.RetainedReadbackClient(profile=self.profile, limits=replace(offline, max_children=1)) as reader:
                    proof = reader.readback(store.root / "archives" / entry["archive_name"],
                        expected_header=released["header"], role=archive.RoleProfile(**released["role"]),
                        physical=archive.PhysicalBinding(**entry["physical"]), profile=self.profile.decoder,
                        limits=archive.DecodeLimits(32768, 4*1024**2, 4*1024**2, 8*1024**2, 1024**2, 100, 1<<22, self.deadline))
                self.assertEqual(proof.canonical.sha256, digest(self.originals[entry["logical"]["file_name"]]))
            path = self.working / outcome.receipt.file_name
            original_receipt = path.read_bytes()
            for mutate in (lambda r: r.update(execution_ordinal=False),
                           lambda r: r.update(storage_extension=dict(r["storage_extension"], sha256="e"*64)),
                           lambda r: r["artifacts"][0].update(released_record=r["ledger_tip"]),
                           lambda r: r["artifacts"].pop(),
                           lambda r: r.update(unexpected=True)):
                changed = copy.deepcopy(receipt)
                mutate(changed)
                raw = archive.canonical(changed)
                try:
                    path.write_bytes(raw)
                    with self.assertRaises(archive.ArchiveError):
                        self.verify_metadata(store, custody.BoundFile(path.name, len(raw), digest(raw)))
                finally:
                    path.write_bytes(original_receipt)
            physical = store.root / "archives" / receipt["artifacts"][0]["archive_name"]
            raw = physical.read_bytes()
            try:
                physical.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
                with self.assertRaises(archive.ArchiveError): self.verify_metadata(store, outcome.receipt)
            finally:
                physical.write_bytes(raw)

    def test_failed_native_capture_is_archived_as_failed_evidence(self):
        self.document["native_complete"] = False
        self.document["native_result_after_private_cleanup"]["stop"] = 12
        self.write_checkpoint()
        outcome = self.live()
        self.assertEqual(outcome.status, "ARCHIVED_FAILED_EVIDENCE")
        self.assertTrue(all(not (self.working / n).exists() for n in self.originals))

    def test_live_private_mapping_blocks_codecs_and_preserves_original_files(self):
        self.document["native_complete"] = False
        final = self.document["native_result_after_private_cleanup"]
        final["stop"] = 12
        final["core_mapping"]["mapping"] = dict(address=4096, error_number=0)  # Synthetic token.
        final["core_mapping"]["unmap"]["return_value"] = -1
        self.write_checkpoint()
        with self.assertRaises(broker.base.BrokerError):
            self.live()
        self.assertTrue(all((self.working / n).read_bytes() == data for n, data in self.originals.items()))

    def test_one_family_extension_cannot_be_reused_or_adopted_by_legacy(self):
        with custody.ProgramStore(self.root, scope_sha256=self.scope, family_id=self.family, limits=self.custody_limits) as store:
            with self.assertRaises(custody.CustodyError): store.prepare_family(self.family)
        with self.store(family_id="e"*64) as store:
            with self.assertRaises(custody.CustodyError): store.prepare_family("e"*64)
        with self.store(ext009_resolution_sha256="f"*64) as store:
            with self.assertRaises(custody.CustodyError): store.prepare_family(self.family)

    def test_frozen_order_and_profile_scope_drift_reject_before_broker(self):
        for mutate in (lambda r: r["plan"]["captures"].reverse(),
                       lambda r: r["plan"]["storage"].update(approval_sha256="f"*64),
                       lambda r: r["plan"]["blueprint"].update(repetitions_per_setting=3)):
            request = copy.deepcopy(self.request)
            mutate(request)
            with self.assertRaises(archive.ArchiveError): broker.capture_contract(request, 0)

    def native_exchange(self, *, successful):
        if self.channel_fixture is None:
            self.fail("requires compiled native channel fixture")
        lease = supervisor.SupervisorLease()
        lease.enter()
        parent, child = channel.create_channel()
        directory_fd = os.open(self.working, os.O_RDONLY | os.O_DIRECTORY)
        process = None
        worker = None
        cleaned = False
        try:
            request_hash = digest(archive.canonical(self.request))
            process = subprocess.Popen([str(self.channel_fixture), str(child.fileno()), str(directory_fd),
                request_hash, self.scope, str(self.deadline)], pass_fds=(child.fileno(), directory_fd),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            child.close()
            worker = PinnedWorker(process.pid)
            driver = channel.ArchiveChannel(parent, worker=worker, directory_fd=directory_fd,
                request_sha256=request_hash, program_scope_sha256=self.scope, captures=180,
                maximum_checkpoint_bytes=131072, maximum_custody_receipt_bytes=131072,
                maximum_archive_ns=90_000_000_000, session_id=self.request["session_id"], plan_sha256=self.family)
            pending = driver.receive(deadline_ns=self.deadline)
            self.assertEqual(pending.binding, asdict(self.checkpoint))
            with broker.ArchiveBrokerClient(profile=self.profile, limits=self.limits,
                    identity_model=lease.identity_model, native_worker=worker) as client:
                outcome = client.archive_capture(program_root=self.root, scope_sha256=self.scope, family_id=self.family,
                    custody_limits=self.custody_limits, request_document=self.request, capture_ordinal=0, checkpoint=self.checkpoint)
                self.assertEqual(client.actual_processes, 1 + 3 * len(self.document["artifacts"]))
            self.assertTrue(outcome.cleanup.leader_reaped and outcome.cleanup.process_group_gone)
            self.assertFalse(outcome.cleanup.cleanup_deadline_overrun)
            worker.observe_quiescence()
            with self.store() as store:
                store.prepare_family(self.family)
                proof = registry.verify_capture_metadata(store=store, capture=broker.capture_contract(self.request, 0),
                    checkpoint_binding=pending.binding, receipt_binding=asdict(outcome.receipt),
                    decoder_profile=self.profile.decoder,
                    decoder_limits=archive.DecodeLimits(32768, 4*1024**2, 4*1024**2, 8*1024**2,
                        4*1024**2, 100, 1<<22, self.deadline))
                self.assertEqual(proof["continuation_allowed"], successful)
                self.assertFalse(proof["inverse_readback_performed"])
                self.assertEqual(len(proof["artifacts"]), len(self.document["artifacts"]))
            # Actual child/ledger/header/hash checks all precede ACK.
            self.assertIsNone(process.poll())
            driver.acknowledge(asdict(outcome.receipt), deadline_ns=self.deadline)
            cleanup = supervisor.cleanup_process_group(process, force_stop=False,
                leader_wait_deadline_ns=time.monotonic_ns()+2_000_000_000, global_deadline_ns=self.deadline,
                identity_model=lease.identity_model)
            cleaned = True
            self.assertTrue(cleanup.leader_reaped and cleanup.process_group_gone)
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0 if successful else 2, stderr)
            self.assertEqual(json.loads(stdout), dict(accepted=successful))
            self.assertEqual(driver.stopped, not successful)
            self.assertEqual(driver.ordinal, 1)
        finally:
            child.close()
            parent.close()
            os.close(directory_fd)
            try:
                if process is not None and not cleaned:
                    proof = supervisor.cleanup_process_group(process, force_stop=True,
                        leader_wait_deadline_ns=time.monotonic_ns()+2_000_000_000, global_deadline_ns=self.deadline,
                        identity_model=lease.identity_model)
                    self.assertTrue(proof.leader_reaped and proof.process_group_gone)
            finally:
                if process is not None:
                    if process.stdout: process.stdout.close()
                    if process.stderr: process.stderr.close()
                if worker is not None: worker.close()
                lease.close()

    def test_actual_native_channel_broker_ledger_and_success_ack(self):
        self.native_exchange(successful=True)

    def test_actual_native_channel_retains_failed_evidence_and_rejects_continuation(self):
        self.document["native_complete"] = False
        self.document["native_result_after_private_cleanup"]["stop"] = 12
        self.write_checkpoint()
        self.native_exchange(successful=False)

    def test_actual_native_partial_prefix_preserves_unlisted_files_and_stops(self):
        self.document["native_complete"] = False
        self.document["native_result_after_private_cleanup"]["stop"] = 12
        self.document["artifacts"] = self.document["artifacts"][:2]
        self.write_checkpoint()
        self.native_exchange(successful=False)
        for name in contract.capture_names(0)[2:]:
            self.assertEqual((self.working / name).read_bytes(), self.originals[name])

    def test_actual_native_source_discrepancy_preserved_without_continuation(self):
        name = contract.capture_names(0)[0]
        raw = self.originals[name]
        (self.working / name).write_bytes(raw[:-1])
        self.native_exchange(successful=False)


class ReservedS180BrokerTests(S180BrokerTests):
    reserve_before_admission = True

    def test_changed_admission_blocks_retained_custody_verification(self):
        outcome = self.live()
        path = self.root / "metadata" / f"s180-admission-{self.family}.json"
        original = path.read_bytes()
        with self.store() as store:
            store.prepare_family(self.family)
            try:
                path.write_bytes(original.replace(b'a'*64, b'f'*64))
                with self.assertRaisesRegex(custody.CustodyError, "storage admission absent.*EXT009"):
                    self.verify_metadata(store, outcome.receipt)
            finally:
                path.write_bytes(original)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--encoder", type=Path, required=True)
    p.add_argument("--channel-fixture", type=Path, required=True)
    args, rest = p.parse_known_args()
    S180BrokerTests.encoder = args.encoder.resolve()
    S180BrokerTests.channel_fixture = args.channel_fixture.resolve()
    unittest.main(argv=[sys.argv[0], *rest])
