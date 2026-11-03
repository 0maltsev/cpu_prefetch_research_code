"""Checkpoint identity and actual process-observation checks, software only."""
import copy
import os
import pathlib
import select
import subprocess
import sys
import time
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import stage17_formal_checkpoint_v1 as checkpoint


def fixture():
    capture = dict(ordinal=0, warmup=dict(run_id="warmup"),
                   measurement=dict(run_id="measurement"), hardware_state="H0")
    sources = tuple(SimpleNamespace(expected=SimpleNamespace(
        file_name=name, size_bytes=0, sha256="a" * 64))
        for name in checkpoint.capture_names("Q16a", 0))
    mapping = dict(cleanup_attempted=True, unlock=dict(return_value=0, error_number=0),
                   unmap=dict(return_value=0, error_number=0))
    stack = dict(mapping, thread=dict(create=0, join=0))
    final = dict(stop=14, session=None, clock_origin=None, core_mapping=copy.deepcopy(mapping),
        monitor_mapping=copy.deepcopy(mapping), controller_stack=copy.deepcopy(stack),
        worker_mappings=[copy.deepcopy(mapping) for _ in range(3)],
        worker_stacks=[copy.deepcopy(stack) for _ in range(2)],
        publication_attempted=True, publication_succeeded=True)
    document = dict(schema_version=checkpoint.SCHEMA, action_id="Q16a", plan_sha256="b" * 64,
        capture_ordinal=0, capture_identity=dict(warmup_run_id="warmup",
            measurement_run_id="measurement", hardware_state="H0"),
        native_result_after_cleanup=final, artifacts=[vars(s.expected) for s in sources],
        native_complete=True, scientific_validity="NOT_ASSESSED", execution_authority=False)
    return document, capture, sources


class CheckpointTests(unittest.TestCase):
    def validate(self, document, capture, sources):
        return checkpoint.validate_checkpoint(document, action="Q16a", plan_sha256="b" * 64,
                                              capture=capture, sources=sources)

    def test_bound_complete_receipt_is_not_scientific_credit(self):
        document, capture, sources = fixture()
        self.assertIsNone(self.validate(document, capture, sources))
        document["scientific_validity"] = "VALID"
        with self.assertRaises(checkpoint.ArchiveError): self.validate(document, capture, sources)

    def test_native_failures_retained_without_successful_cleanup_claim(self):
        document, capture, sources = fixture()
        document["native_complete"] = False
        document["native_result_after_cleanup"]["stop"] = 12
        document["native_result_after_cleanup"]["worker_stacks"][0]["thread"]["join"] = 3
        self.validate(document, capture, sources)
        document["native_complete"] = True
        with self.assertRaises(checkpoint.ArchiveError): self.validate(document, capture, sources)

    def test_completed_cleanup_join_or_memory_failure_rejected(self):
        for mutate in (lambda n: n["controller_stack"]["thread"].update(join=1),
                       lambda n: n["worker_mappings"][0].update(cleanup_attempted=False),
                       lambda n: n["core_mapping"]["unmap"].update(return_value=-1),
                       lambda n: n.update(worker_stacks=[])):
            document, capture, sources = fixture()
            mutate(document["native_result_after_cleanup"])
            with self.assertRaises(checkpoint.ArchiveError): self.validate(document, capture, sources)

    def test_wrong_plan_run_source_order_and_partial_completion_rejected(self):
        for mutate in (lambda d: d.update(plan_sha256="c" * 64),
                       lambda d: d["capture_identity"].update(measurement_run_id="foreign"),
                       lambda d: d.update(capture_ordinal=True),
                       lambda d: d["artifacts"].reverse()):
            document, capture, sources = fixture()
            mutate(document)
            with self.assertRaises(checkpoint.ArchiveError): self.validate(document, capture, sources)
        document, capture, sources = fixture()
        document["artifacts"].pop()
        with self.assertRaises(checkpoint.ArchiveError): self.validate(document, capture, sources[:-1])

    def child(self, threaded=False):
        script = "import sys\n"
        if threaded:
            script += "import threading\ne=threading.Event()\nt=threading.Thread(target=e.wait,daemon=True)\nt.start()\n"
        script += "print('ready',flush=True)\nsys.stdin.buffer.read(1)\n"
        process = subprocess.Popen([sys.executable, "-B", "-c", script],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=3)
        self.addCleanup(cleanup)
        self.assertEqual(process.stdout.readline(), b"ready\n")
        return process

    def test_actual_parked_single_thread_worker_and_exit_detection(self):
        process = self.child()
        worker = checkpoint.PinnedWorker(process.pid)
        self.addCleanup(worker.close)
        observed = worker.observe_quiescence()
        self.assertEqual(observed["task_ids"], [process.pid])
        self.assertEqual(observed["child_pids"], [])
        self.assertFalse(observed["measurement_authority"])
        process.communicate(b"x", timeout=3)
        with self.assertRaises(checkpoint.ArchiveError): worker.observe_quiescence()

    def test_actual_remaining_native_thread_is_rejected(self):
        process = self.child(threaded=True)
        worker = checkpoint.PinnedWorker(process.pid)
        self.addCleanup(worker.close)
        with self.assertRaisesRegex(checkpoint.ArchiveError, "threads"):
            worker.observe_quiescence()

    def test_real_pidfd_accepts_running_to_sleeping_transition(self):
        # The child remains runnable until pidfd_open's test hook parks it.
        script = """import os, time
os.set_blocking(0, False)
print('running', flush=True)
deadline = time.monotonic() + 5
while time.monotonic() < deadline:
    try:
        if os.read(0, 1):
            break
    except BlockingIOError:
        pass
else:
    raise RuntimeError('parent did not park child')
os.set_blocking(0, True)
print('parked', flush=True)
os.read(0, 1)
"""
        process = subprocess.Popen([sys.executable, "-B", "-c", script],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=3)
        self.addCleanup(cleanup)
        self.assertTrue(select.select([process.stdout], [], [], 3)[0])
        self.assertEqual(process.stdout.readline(), b"running\n")
        real_open, real_identity = os.pidfd_open, checkpoint._identity
        identities = []
        def identity(pid):
            result = real_identity(pid)
            identities.append(result)
            return result
        def park_after_open(pid, flags):
            descriptor = real_open(pid, flags)
            try:
                process.stdin.write(b"p")
                process.stdin.flush()
                self.assertTrue(select.select([process.stdout], [], [], 3)[0])
                self.assertEqual(process.stdout.readline(), b"parked\n")
                deadline = time.monotonic() + 1
                while real_identity(pid)[0] != "S":
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(0.001)
                return descriptor
            except BaseException:
                os.close(descriptor)
                raise
        with mock.patch.object(checkpoint, "_identity", side_effect=identity), \
                mock.patch.object(checkpoint.os, "pidfd_open", side_effect=park_after_open):
            worker = checkpoint.PinnedWorker(process.pid)
        self.addCleanup(worker.close)
        self.assertEqual([item[0] for item in identities[:2]], ["R", "S"])
        self.assertEqual(identities[0][1], identities[1][1])
        self.assertEqual(worker.observe_quiescence()["task_ids"], [process.pid])

    def test_start_tick_change_still_rejects_and_closes_real_pidfd(self):
        process = self.child()
        state, ticks = checkpoint._identity(process.pid)
        real_open = os.pidfd_open
        descriptors = []
        def opened(pid, flags):
            descriptor = real_open(pid, flags)
            descriptors.append(descriptor)
            return descriptor
        with mock.patch.object(checkpoint, "_identity", side_effect=[
                (state, ticks), (state, ticks + 1)]), \
                mock.patch.object(checkpoint.os, "pidfd_open", side_effect=opened):
            with self.assertRaisesRegex(checkpoint.ArchiveError, "identity changed"):
                checkpoint.PinnedWorker(process.pid)
        self.assertEqual(len(descriptors), 1)
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])


if __name__ == "__main__":
    unittest.main()
