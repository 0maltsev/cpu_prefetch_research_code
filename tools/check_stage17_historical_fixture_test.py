#!/usr/bin/env python3
"""Exercise preservation failures without modifying repository evidence."""

from __future__ import annotations

import hashlib
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_stage17_historical_fixture as fixture


class PreservedCurrentInputs(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.current = Path(self.temporary.name) / "current"
        self.snapshot = Path(self.temporary.name) / "snapshot"
        self.record = "config/q15/retained-evidence.json"
        contents = b'{"retained":true}\n'
        manifest = json.dumps({"tracked_artifacts": [{
            "path": self.record,
            "sha256": hashlib.sha256(contents).hexdigest(),
        }]}).encode()
        for root in (self.current, self.snapshot):
            for relative in (*fixture.TEMPLATES, self.record):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(manifest if relative == fixture.PRESERVATION else contents)

    def test_accepts_preserved_current_bytes(self) -> None:
        fixture.verify_preserved_inputs(self.current, self.snapshot)

    def test_rejects_current_template_drift(self) -> None:
        (self.current / fixture.TEMPLATES[0]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "preserved template drift"):
            fixture.verify_preserved_inputs(self.current, self.snapshot)

    def test_rejects_current_preserved_record_drift(self) -> None:
        (self.current / self.record).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "preserved artifact drift"):
            fixture.verify_preserved_inputs(self.current, self.snapshot)

    def test_rejects_missing_current_record(self) -> None:
        (self.current / self.record).unlink()
        with self.assertRaisesRegex(ValueError, "not a regular file"):
            fixture.verify_preserved_inputs(self.current, self.snapshot)

    def test_rejects_symlink_even_to_matching_bytes(self) -> None:
        path = self.current / self.record
        path.unlink()
        path.symlink_to(self.snapshot / self.record)
        with self.assertRaisesRegex(ValueError, "symlink"):
            fixture.verify_preserved_inputs(self.current, self.snapshot)

    def test_child_failure_cannot_publish_a_ctest_success_pattern(self) -> None:
        def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            if command[0] == "git":
                return subprocess.CompletedProcess(command, 0, stdout="/unused/git\n")
            raise subprocess.CalledProcessError(
                1, command, output="stage17-state-journal-check: PASS stale success\n"
            )

        output = io.StringIO()
        errors = io.StringIO()
        with (patch.object(fixture, "ROOT", self.current),
              patch.object(fixture, "materialize", side_effect=lambda destination:
                           shutil.copytree(self.snapshot, destination)),
              patch.object(fixture.subprocess, "run", side_effect=run),
              patch.object(fixture.sys, "argv", ["checker", "journal"]),
              contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors)):
            self.assertEqual(fixture.main(), 1)
        self.assertNotIn("PASS", output.getvalue())
        self.assertIn("FAIL", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
