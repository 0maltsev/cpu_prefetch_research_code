"""Finite formal resource admission and explicit legacy-route separation."""
from pathlib import Path
from contextlib import ExitStack
import datetime as dt
import json
import os
import sys
import tempfile
import time
import subprocess
from types import SimpleNamespace
from unittest import mock
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage17_fixed_action_executor_v10 as executor
import stage17_phase_controller_v25 as controller


class FormalExecutorResources(unittest.TestCase):
    def extent(self):
        return SimpleNamespace(declared=SimpleNamespace(memory_bytes=1024, required_free_disk_bytes=8192))

    def observe(self, memory="MemAvailable: 2 kB\n", blocks=2):
        with mock.patch.object(Path, "read_text", return_value=memory), \
             mock.patch.object(executor.os, "fstatvfs", return_value=SimpleNamespace(f_bavail=blocks, f_frsize=4096)), \
             mock.patch.object(executor.os, "fstat", return_value=SimpleNamespace(st_dev=123)):
            return executor.live_resources(10, self.extent())

    def test_exact_available_bytes_and_unreserved_status_are_recorded(self):
        result = self.observe()
        self.assertEqual(result["memory_available_bytes"], 2048)
        self.assertEqual(result["filesystem_available_bytes"], 8192)
        self.assertEqual(result["filesystem_device"], 123)
        self.assertFalse(result["reservation_established"])

    def test_missing_ambiguous_or_insufficient_memory_rejects(self):
        for text in ("MemFree: 200 kB\n", "MemAvailable: 2 kB\nMemAvailable: 3 kB\n", "MemAvailable: 0 kB\n"):
            with self.assertRaises(executor.FixedActionExecutionError): self.observe(memory=text)

    def test_insufficient_disk_rejects(self):
        with self.assertRaises(executor.FixedActionExecutionError): self.observe(blocks=1)

    def test_historical_request_uses_predecessor_before_any_new_io(self):
        sentinel = object()
        request = {"schema_version": "cpu-prefetch-stage17-fixed-action-request/5"}
        with mock.patch.object(executor.previous, "execute_fixed_action", return_value=sentinel) as previous, \
             mock.patch.object(executor.contract, "validate_plan", side_effect=AssertionError("new formal parser used")):
            result = executor.execute_fixed_action(repository_root=Path.cwd(),
                authorization={"action_id": "Q16A-DURATION-DISCOVERY", "deadline_policy": {}},
                authorization_bytes=b"{}", request=request, request_bytes=b"{}", worker_binding={},
                worker_path=Path("/software-only"), release_binding={}, output_root=Path("/software-only"),
                synthetic_test_only=True)
            self.assertIs(result, sentinel)
            self.assertEqual(previous.call_args.kwargs["request"], request)

    def test_v6_cannot_delegate_a_nonformal_action(self):
        with mock.patch.object(executor.previous, "execute_fixed_action", side_effect=AssertionError("legacy route used")):
            with self.assertRaises(ValueError):
                executor.execute_fixed_action(repository_root=Path.cwd(),
                    authorization={"action_id": "Q15-R", "deadline_policy": {}}, authorization_bytes=b"{}",
                    request={"schema_version": "cpu-prefetch-stage17-fixed-action-request/6", "action_inputs": {"plan": {}}},
                    request_bytes=b"{}", worker_binding={}, worker_path=Path("/software-only"),
                    release_binding={}, output_root=Path("/software-only"), synthetic_test_only=True)


class FormalLifetime(unittest.TestCase):
    def test_real_supervisor_stops_worker_at_authority_expiry_with_cleanup_reserve(self):
        started = time.monotonic_ns()
        with self.assertRaises(executor.FixedActionExecutionError) as caught:
            executor._run_formal_worker(
                (sys.executable, "-c", "import time; time.sleep(30)"), (),
                global_deadline_ns=started + 30_000_000_000,
                monotonic_expiry_ns=started + 3_000_000_000,
                authority_guard=lambda: executor._utc_now())
        self.assertEqual(caught.exception.category, "WORKER_TIMEOUT")
        proof = caught.exception.cleanup_proof
        self.assertTrue(proof.leader_reaped)
        self.assertTrue(proof.process_group_gone)
        self.assertLess(time.monotonic_ns() - started, 5_000_000_000)

    def test_already_expired_cannot_spawn(self):
        # Exercise the real inherited guard/NO_PROCESS_CREATED failure path.
        runner_module = sys.modules[executor._run_worker.__module__]
        with mock.patch.object(runner_module.subprocess, "Popen") as spawn:
            with self.assertRaises(executor.FixedActionExecutionError) as caught:
                executor._run_formal_worker(("/never-spawn",), (),
                    global_deadline_ns=time.monotonic_ns() + 30_000_000_000,
                    monotonic_expiry_ns=time.monotonic_ns() - 1,
                    authority_guard=lambda: executor._utc_now())
            spawn.assert_not_called()
        self.assertEqual(caught.exception.category, "WORKER_START")
        self.assertTrue(caught.exception.cleanup_proof.leader_reaped)
        self.assertTrue(caught.exception.cleanup_proof.process_group_gone)

    def test_earlier_family_deadline_is_not_extended(self):
        now = time.monotonic_ns()
        with mock.patch.object(executor, "_run_worker", return_value="bounded") as run:
            result = executor._run_formal_worker(("unused",), (),
                global_deadline_ns=now + 10_000_000_000,
                monotonic_expiry_ns=now + 30_000_000_000,
                authority_guard=lambda: executor._utc_now())
        self.assertEqual(result, "bounded")
        self.assertEqual(run.call_args.kwargs["global_deadline_ns"], now + 10_000_000_000)


class FormalFailureRecovery(unittest.TestCase):
    def invoke_failure(self, proof, *, recovery_fails=False, return_transport=False):
        # Inject only the worker boundary and prerequisite setup; durable marker,
        # quarantine and failure writes and snapshot custody remain real.
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            if proof is not None and not hasattr(proof, "returncode"):
                proof = executor.predecessor.TransportOutcome(
                    -1, b"", b"", proof.leader_reaped, proof.process_group_gone, "SOFTWARE_TEST")
            root = Path(temporary)
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            info = os.fstat(fd)
            policy = dict(mode="BOUNDED_FORMAL_CALIBRATION_SESSION",
                per_run_max_wall_seconds=10, session_max_wall_seconds=30,
                implicit_extension=False, partial_session_completes=False)
            now = dt.datetime.now(dt.timezone.utc)
            timestamp = lambda value: value.isoformat().replace("+00:00", "Z")
            authorization = dict(action_id="Q16a", authorization_id="auth", deadline_policy=policy,
                issued_at_utc=timestamp(now - dt.timedelta(seconds=1)),
                expires_at_utc=timestamp(now + dt.timedelta(seconds=20)),
                fixed_action_definition_sha256="c"*64, evidence_root_binding={})
            request = dict(schema_version="cpu-prefetch-stage17-fixed-action-request/6",
                request_id="request", session_id="session", attempt_id="attempt",
                action_inputs={"plan": {}}, evidence_root_binding={}, predecessor_resolutions=[])
            release = dict(worker_sha256="a"*64, source_resolution_id="release", source_resolution_sha256="b"*64)
            pinned = SimpleNamespace(plan_sha256="c"*64, action=lambda action: {"requires_restoration": True})
            worker = SimpleNamespace(sha256="a"*64, locator="/never-execute", close=lambda: None)
            patches = (
                mock.patch.object(executor.contract, "validate_plan", return_value=object()),
                mock.patch.object(controller, "deadline_policy", return_value=policy),
                mock.patch.object(executor.output_registry, "pin_registry", return_value=pinned),
                mock.patch.object(executor, "formal_prestate", return_value=((0, 0),)),
                mock.patch.object(executor.predecessor, "_pin_worker", return_value=worker),
                mock.patch.object(executor, "_validate_schema"),
                mock.patch.object(executor, "_componentwise_output_root", return_value=(fd, (info.st_dev, info.st_ino))),
                mock.patch.object(executor, "live_resources", return_value={}),
            )
            for patch in patches: stack.enter_context(patch)
            recovery = stack.enter_context(mock.patch.object(executor.hardware_recovery, "restore",
                side_effect=RuntimeError("readback failed") if recovery_fails else None, return_value=[]))
            failure = executor.FixedActionExecutionError("INJECTED_WORKER_FAILURE", "software-only failure")
            if proof is not None: failure.cleanup_proof = proof
            if return_transport:
                stack.enter_context(mock.patch.object(executor, "_run_worker", return_value=proof))
            else:
                stack.enter_context(mock.patch.object(executor, "_run_worker", side_effect=failure))
            with self.assertRaises(executor.FixedActionExecutionError):
                executor.execute_fixed_action(repository_root=Path.cwd(), authorization=authorization,
                    authorization_bytes=executor.canonical(authorization), request=request,
                    request_bytes=executor.canonical(request), worker_binding={}, worker_path=Path("/never-execute"),
                    release_binding=release, output_root=root, synthetic_test_only=True)
            retained = json.loads((root / "stage17-q16a-failure-v6.json").read_bytes())
            schema = json.loads((Path.cwd() / "config/schemas/stage17-phase-action-failure-v6.schema.json").read_bytes())
            executor.output_registry.Draft202012Validator(schema).validate(retained)
            self.assertTrue((root / "stage17-q16a-attempt-v6.json").is_file())
            self.assertFalse((root / "stage17-q16a-completion-v6.json").exists())
            quarantined = (root / "stage17-stand-quarantine-v1.json").exists()
            return retained, recovery.call_count, quarantined

    def test_absent_or_incomplete_quiescence_never_restores_hardware(self):
        for proof in (None, SimpleNamespace(leader_reaped=False, process_group_gone=True),
                      SimpleNamespace(leader_reaped=True, process_group_gone=False)):
            with self.subTest(proof=proof):
                retained, calls, quarantine = self.invoke_failure(proof)
                self.assertEqual(calls, 0)
                self.assertTrue(quarantine)
                self.assertFalse(retained["restoration_verified"])
                self.assertIsNone(retained["recovery_readback"])
                self.assertFalse(retained["leader_reaped"] and retained["process_group_gone"])

    def test_returned_nonquiescent_transport_also_cannot_restore(self):
        proof = executor.predecessor.TransportOutcome(1, b"", b"", True, False, "SOFTWARE_TEST")
        retained, calls, quarantine = self.invoke_failure(proof, return_transport=True)
        self.assertEqual(calls, 0)
        self.assertTrue(quarantine)
        self.assertFalse(retained["process_group_gone"])

    def test_quiescent_failure_restores_and_retains_readback(self):
        retained, calls, quarantine = self.invoke_failure(SimpleNamespace(leader_reaped=True, process_group_gone=True))
        self.assertEqual(calls, 1)
        self.assertFalse(quarantine)
        self.assertTrue(retained["restoration_verified"])
        self.assertEqual(retained["recovery_readback"], [])

    def test_quiescent_recovery_failure_quarantines(self):
        retained, calls, quarantine = self.invoke_failure(
            SimpleNamespace(leader_reaped=True, process_group_gone=True), recovery_fails=True)
        self.assertEqual(calls, 1)
        self.assertTrue(quarantine)
        self.assertFalse(retained["restoration_verified"])


class FormalSignedProcess(unittest.TestCase):
    """Real signature/controller/sealed-FD process and custody, synthetic journal.

    The child emits empty software-only byte fixtures. It cannot establish raw
    reconciliation or scientific validity and is never a qualified native worker.
    """
    def prepare(self, *, fail=False):
        from test_stage17_phase_controller_v25 import FormalController
        fixture = FormalController()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root = fixture.root
        output = root / 'output'
        output.mkdir(mode=0o700)
        source_root = Path(__file__).resolve().parents[1]
        script = '''#!/usr/bin/python3
import fcntl, hashlib, json, os, sys
sys.path.insert(0, SOURCE_TOOLS)
import stage17_output_registry_v11 as r
assert sys.argv[1:3] == ['--execute-fixed-stage17-action-v6', 'Q16a']
assert sys.argv[3] == '--request-fd' and sys.argv[5] == '--context-fd'
assert sys.argv[7] == '--output-dir-fd' and sys.argv[9] == '--fixed-dispatch-end'
request_fd, context_fd, output_fd = (int(sys.argv[i]) for i in (4,6,8))
for fd in (request_fd, context_fd):
    assert fcntl.fcntl(fd, fcntl.F_GET_SEALS) & fcntl.F_SEAL_WRITE
def load(fd):
    return os.pread(fd, os.fstat(fd).st_size + 1, 0)
request_bytes = load(request_fd)
request, context = json.loads(request_bytes), json.loads(load(context_fd))
assert request['synthetic_test_only'] is context['synthetic_test_only'] is True
assert context['schema_version'] == 'cpu-prefetch-stage17-fixed-action-context/6'
assert context['request_sha256'] == r.sha256(request_bytes)
def write(name, payload):
    fd = os.open(name, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600, dir_fd=output_fd)
    try:
        view = memoryview(payload)
        while view:
            n = os.write(fd, view)
            assert n > 0
            view = view[n:]
        os.fsync(fd)
    finally: os.close(fd)
if FAIL_CHILD:
    write('partial-software-only.bin', b'synthetic failure prefix')
    sys.exit(7)
artifacts, retained = [], []
plan = request['action_inputs']['plan']
for capture in plan['captures']:
    ordinal = capture['capture']['ordinal']
    refs = []
    for name in r.capture_names('Q16a', ordinal):
        role, schema, media = r.artifact_identity('Q16a', name)
        payload = r.canonical({'software_fixture': True}) if media == 'application/json' else b''
        write(name, payload)
        item = dict(file_name=name, role=role, schema_identity=schema, media_type=media,
                    size_bytes=len(payload), sha256=r.sha256(payload))
        artifacts.append(item)
        refs.append({k:item[k] for k in ('file_name','size_bytes','sha256')})
    retained.append(dict(ordinal=ordinal, artifacts=refs, native_complete=True))
hardware = request['action_inputs']['hardware_control']
prestate = hardware['prestate']
report = dict(schema_version='cpu-prefetch-stage17-formal-retention-report/1', action_id='Q16a',
    plan_sha256=r.sha256(r.canonical(plan)), mapping_id=hardware['mapping_id'],
    whole_plots=[dict(state='H0',apply_readback=[],restore_readback=[],restoration_verified=True),
        dict(state='H1',apply_readback=[dict(cpu=row['cpu'],complete_value_hex=f"{int(row['complete_value_hex'],16)|15:016x}") for row in prestate],
             restore_readback=list(reversed(prestate)),restoration_verified=True)],
    native_results_after_cleanup=[{'software_fixture':True} for _ in retained], captures=retained,
    restoration_verified=True,mandatory_failure=False,scientific_validity='NOT_ASSESSED',
    execution_authority=False,phase18_authority=False)
payload = r.canonical(report)
write(r.REPORT_NAME,payload)
role,schema,media = r.artifact_identity('Q16a',r.REPORT_NAME)
artifacts.append(dict(file_name=r.REPORT_NAME,role=role,schema_identity=schema,media_type=media,
                      size_bytes=len(payload),sha256=r.sha256(payload)))
result = {k:request[k] for k in ('request_id','action_id','stand_id','authorization_id','attempt_id',
                                 'runtime_binding','release_binding','predecessor_resolutions')}
result.update(schema_version='cpu-prefetch-stage17-phase-action-result/6', result_id='software-result',
    request_sha256=r.sha256(request_bytes),authorization_sha256=context['authorization_sha256'],
    artifacts=artifacts,started_at_utc='2030-01-01T00:00:00Z',completed_at_utc='2030-01-01T00:00:01Z',
    duration_ns=1000000000,terminal_state='FORMAL_ARTIFACTS_RETAINED_UNASSESSED',
    restoration_verified=True,quarantined=False,synthetic_test_only=True,phase18_authority=False)
write(r.RESULT_NAME,r.canonical(result))
'''.replace('SOURCE_TOOLS', repr(str(source_root / 'tools'))).replace('FAIL_CHILD', repr(fail))
        worker = root / 'software-worker.py'
        worker.write_text(script)
        worker.chmod(0o500)
        fixture.context.update(release_artifact_path=str(worker), release_artifact_size_bytes=worker.stat().st_size,
                               release_artifact_sha256=executor.sha256(worker.read_bytes()))
        key = root / 'key'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],check=True,
                       capture_output=True,timeout=10)
        allowed = root / 'allowed-signers'
        allowed.write_text('software-owner ' + key.with_suffix('.pub').read_text())
        trust = dict(subject_id='synthetic-stand',measurements=dict(principal='software-owner',reviewer_role='OWNER',
            sshsig_namespace='stage17-owner-acceptance', allowed_signers_path=str(allowed),
            allowed_signers_size_bytes=allowed.stat().st_size, allowed_signers_sha256=executor.sha256(allowed.read_bytes())))
        for i in range(1,7):
            name = f'S17-EXT-{i:03d}'
            if name not in fixture.validation.resolutions:
                fixture.validation.resolutions[name] = SimpleNamespace(semantic_context={})
            row = fixture.validation.resolutions[name]
            row.input_id, row.resolution_id, row.sha256 = name, 'software-resolution-'+str(i), str(i)*64
        fixture.validation.resolutions['S17-EXT-003'].semantic_context = dict(trust=trust)
        fixture.validation.current_state = 'READY_FOR_STAGE17_PHASE_AUTHORIZATION'
        self.enterContext(mock.patch.object(controller.journal_runtime,'validate_operational_journal',return_value=fixture.validation))
        # Synthetic admission uses only the declared observation; no experiment
        # memory/disk capacity is claimed or reserved on the developer machine.
        self.enterContext(mock.patch.object(executor,'live_resources',side_effect=lambda fd, extent: dict(
            observed_at_utc=executor._utc_now(), memory_available_bytes=extent.declared.memory_bytes,
            filesystem_available_bytes=extent.declared.required_free_disk_bytes, filesystem_device=os.fstat(fd).st_dev,
            required_memory_bytes=extent.declared.memory_bytes,
            required_free_disk_bytes=extent.declared.required_free_disk_bytes, reservation_established=False)))
        pinned = executor.output_registry.pin_registry(source_root)
        definition = pinned.action('Q16a')
        expected = [controller.old._binding(fixture.validation.resolutions[name]) for name in definition['required_resolution_ids']]
        runtime, release, _ = controller.runtime_from_context(fixture.validation)
        info = output.stat()
        root_binding = dict(absolute_path=str(output),device=info.st_dev,inode=info.st_ino,owner_uid=info.st_uid,mode='0700')
        request = dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6',request_id='request',
            session_id='session',action_id='Q16a',stand_id='synthetic-stand',authorization_id='auth',attempt_id='attempt',
            runtime_binding=runtime,release_binding=release,evidence_root_binding=root_binding,
            predecessor_resolutions=expected,action_inputs=fixture.request['action_inputs'],synthetic_test_only=True,phase18_authority=False)
        request_path = root / 'request.json'
        request_path.write_bytes(executor.canonical(request))
        now = dt.datetime.now(dt.timezone.utc)
        timestamp = lambda value: value.isoformat(timespec='seconds').replace('+00:00','Z')
        authority = dict(schema_version='cpu-prefetch-stage17-phase-action-authorization/6',authorization_id='auth',
            session_id='session',action_id='Q16a',actor='software-owner',reviewer='OWNER',target={'stand_id':'synthetic-stand'},
            issued_at_utc=timestamp(now-dt.timedelta(seconds=1)),expires_at_utc=timestamp(now+dt.timedelta(seconds=120)),
            trust_context=dict(ext002_resolution=expected[1],ext003_resolution=expected[2]),
            predecessor_resolutions=expected,fixed_action_definition_sha256=pinned.plan_sha256,
            request_binding=dict(path=str(request_path),size_bytes=request_path.stat().st_size,sha256=executor.sha256(request_path.read_bytes())),
            evidence_root_binding=root_binding,permission_matrix=definition['permission_matrix'],
            deadline_policy=controller.deadline_policy(controller.contract.validate_plan('Q16a',fixture.plan)),
            one_attempt=True,retry_allowed=False,stop_first=True,retain_partial=True,stage18_authority=False)
        authority_path = root / 'authorization.json'
        authority_path.write_bytes(executor.canonical(authority))
        subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(key),'-n','stage17-owner-acceptance',str(authority_path)],
                       check=True,capture_output=True,timeout=10)
        arguments = dict(repository_root=source_root,operational_evidence_root=root,journal=root/'journal.json',
            journal_directory=root,authorization_path=authority_path,signature_path=Path(str(authority_path)+'.sig'),synthetic_test_only=True)
        return arguments, output

    def test_real_signed_child_complete_custody_then_replay_rejects(self):
        arguments, output = self.prepare()
        outcome = controller.execute_once(**arguments)
        self.assertTrue(outcome.completion['leader_reaped'])
        self.assertTrue(outcome.completion['process_group_gone'])
        self.assertTrue(outcome.completion['restoration_verified'])
        self.assertEqual(len(outcome.result['artifacts']),708*9+1)
        report = json.loads((output / executor.output_registry.REPORT_NAME).read_bytes())
        self.assertEqual(report['scientific_validity'],'NOT_ASSESSED')
        self.assertFalse(report['execution_authority'])
        self.assertTrue(outcome.result['synthetic_test_only'])
        with self.assertRaises(executor.FixedActionExecutionError) as caught:
            controller.execute_once(**arguments)
        self.assertEqual(caught.exception.category,'REPLAY')

    def test_real_signed_child_failure_retains_prefix_and_quiescent_recovery(self):
        arguments, output = self.prepare(fail=True)
        with self.assertRaises(executor.FixedActionExecutionError) as caught:
            controller.execute_once(**arguments)
        self.assertEqual(caught.exception.category,'WORKER_NONZERO')
        failure = json.loads((output/'stage17-q16a-failure-v6.json').read_bytes())
        self.assertTrue(failure['leader_reaped'] and failure['process_group_gone'])
        self.assertTrue(failure['restoration_verified'])
        self.assertTrue((output/'partial-software-only.bin').is_file())
        self.assertFalse((output/'stage17-q16a-completion-v6.json').exists())


if __name__ == "__main__": unittest.main()
