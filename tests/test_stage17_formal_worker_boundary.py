"""Real fd-only worker version dispatch; synthetic backend, no experiment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_stage17_formal_ring_plan_v1 import plan_fixture

WORKER = None


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class FormalWorkerBoundary(unittest.TestCase):
    def invoke(self, change=None, entry_version=6):
        plan = plan_fixture()
        runtime = {"role": "STAGE17_FIXED_ACTION_WORKER", "profile": "STAGE17-FIXED-ACTION-WORKER-v4",
                   "size_bytes": WORKER.stat().st_size, "sha256": hashlib.sha256(WORKER.read_bytes()).hexdigest()}
        request = {"schema_version": "cpu-prefetch-stage17-fixed-action-request/6",
                   "request_id": "request", "session_id": "session", "action_id": "Q16a",
                   "stand_id": "synthetic-stand", "authorization_id": "authorization", "attempt_id": "attempt",
                   "runtime_binding": runtime, "release_binding": {"worker_sha256": runtime["sha256"]}, "evidence_root_binding": {},
                   "predecessor_resolutions": [], "action_inputs": {"plan": plan},
                   "synthetic_test_only": True, "phase18_authority": False}
        now = int(time.time())
        context = {"schema_version": "cpu-prefetch-stage17-fixed-action-context/6",
                   "authorization_id": "authorization", "authorization_sha256": "b" * 64,
                   "request_id": "request", "request_sha256": "", "session_id": "session",
                   "attempt_id": "attempt", "action_id": "Q16a", "fixed_action_definition_sha256": "c" * 64,
                   "runtime_sha256": runtime["sha256"], "release_sha256": runtime["sha256"],
                   "predecessor_sha256s": [], "issued_at_epoch_seconds": now - 1,
                   "expires_at_epoch_seconds": now + 3600, "per_run_deadline_seconds": 11,
                   "session_deadline_seconds": plan["budget"]["watchdog_ns"] // 1_000_000_000,
                   "synthetic_test_only": True, "phase18_authority": False}
        if change:
            change(request, context)
        request_bytes = encoded(request)
        context["request_sha256"] = hashlib.sha256(request_bytes).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "output").mkdir()
            (root / "request").write_bytes(request_bytes)
            (root / "context").write_bytes(encoded(context))
            request_fd = os.open(root / "request", os.O_RDONLY)
            context_fd = os.open(root / "context", os.O_RDONLY)
            output_fd = os.open(root / "output", os.O_RDONLY | os.O_DIRECTORY)
            try:
                result = subprocess.run([str(WORKER), f"--execute-fixed-stage17-action-v{entry_version}",
                    request["action_id"], "--request-fd", str(request_fd), "--context-fd", str(context_fd),
                    "--output-dir-fd", str(output_fd), "--fixed-dispatch-end"],
                    pass_fds=(request_fd, context_fd, output_fd), capture_output=True, timeout=30)
            finally:
                for descriptor in (request_fd, context_fd, output_fd):
                    os.close(descriptor)
            outputs = {path.name: json.loads(path.read_bytes()) for path in (root / "output").iterdir()}
            return result, outputs

    def reject(self, change=None, entry_version=6):
        result, output = self.invoke(change, entry_version)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output, {}, result.stderr.decode())

    def test_v6_reaches_only_the_versioned_test_backend(self):
        result, output = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(set(output), {"stage17-action-result-v6.json", "software-formal-boundary.json"})
        result = output["stage17-action-result-v6.json"]
        self.assertEqual(result["schema_version"], "cpu-prefetch-stage17-phase-action-result/6")
        self.assertTrue(result["synthetic_test_only"])
        self.assertEqual(result["terminal_state"], "SOFTWARE_FORMAL_BOUNDARY_ONLY")

    def test_request_cannot_enter_legacy_or_diagnostic_dispatch(self):
        self.reject(entry_version=4)
        self.reject(entry_version=5)

    def test_v6_cannot_execute_q15_or_pilot(self):
        for action in ("Q15-R", "Q15-W", "STAGE17-BLINDED-PILOT", "Q16A-DURATION-DISCOVERY"):
            self.reject(lambda request, context: request.update(action_id=action))

    def test_deadlines_must_equal_prospective_family(self):
        for field in ("per_run_deadline_seconds", "session_deadline_seconds"):
            self.reject(lambda request, context: context.update({field: 180}))

    def test_current_authority_and_complete_family_are_required(self):
        self.reject(lambda request, context: context.update(expires_at_epoch_seconds=1))
        self.reject(lambda request, context: request["action_inputs"]["plan"]["captures"].pop())

    def test_runtime_and_synthetic_identity_are_verified(self):
        self.reject(lambda request, context: request["runtime_binding"].update(sha256="0" * 64))
        self.reject(lambda request, context: request.update(synthetic_test_only=False))
        self.reject(lambda request, context: context.update(synthetic_test_only=False))
        self.reject(lambda request, context: context.update(runtime_sha256="0" * 64))
        self.reject(lambda request, context: context.update(release_sha256="0" * 64))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    WORKER = args.worker.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
