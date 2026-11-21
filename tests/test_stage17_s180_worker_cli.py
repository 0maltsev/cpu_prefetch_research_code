"""Actual production S180 identity and closed CLI; no execution authority."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class WorkerCliTests(unittest.TestCase):
    worker = None

    def test_actual_runtime_identity_matches_independent_binary_hash(self):
        result = subprocess.run([str(self.worker), "--stage17-s180-runtime-identity-v1"],
            capture_output=True, timeout=30, check=True)
        document = json.loads(result.stdout)
        self.assertEqual(document["role"], "STAGE17_S180_NATIVE_WORKER")
        self.assertEqual(document["profile"], "STAGE17-S180-NATIVE-WORKER-v1")
        self.assertEqual(document["sha256"], hashlib.sha256(self.worker.read_bytes()).hexdigest())
        self.assertEqual(document["size_bytes"], self.worker.stat().st_size)
        for name in ("synthetic_test_only", "execution_authority", "phase18_authority"):
            self.assertIs(document[name], False)

    def test_unsealed_inputs_fail_before_any_output(self):
        with tempfile.TemporaryDirectory(prefix="s180-cli-") as temporary:
            root = Path(temporary)
            for name in ("request", "context"):
                (root / name).write_bytes(b"{}")
            output = root / "output"
            output.mkdir(mode=0o700)
            descriptors = [os.open(root / "request", os.O_RDONLY), os.open(root / "context", os.O_RDONLY),
                           os.open(output, os.O_RDONLY | os.O_DIRECTORY)]
            try:
                result = subprocess.run([str(self.worker), "--execute-stage17-s180-session-v1",
                    "--request-fd", str(descriptors[0]), "--context-fd", str(descriptors[1]),
                    "--output-dir-fd", str(descriptors[2]), "--fixed-dispatch-end"],
                    pass_fds=descriptors, capture_output=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"immutable seals", result.stderr)
                self.assertEqual(list(output.iterdir()), [])
            finally:
                for descriptor in descriptors:
                    os.close(descriptor)

    def test_no_synthetic_or_plugin_cli_selector(self):
        for extra in ("--synthetic-test-only", "--backend=fake", "--plugin=anything"):
            result = subprocess.run([str(self.worker), "--execute-stage17-s180-session-v1", extra],
                capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"argv contract", result.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    args, rest = parser.parse_known_args()
    WorkerCliTests.worker = args.worker.resolve()
    unittest.main(argv=[__file__, *rest])
