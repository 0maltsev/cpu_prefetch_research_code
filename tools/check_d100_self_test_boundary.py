#!/usr/bin/env python3
"""Verify that synthetic proposal checks cannot consume external release bytes."""

from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

import check_d100_p4_r_c_decision as checker


class ArchiveBoundary(unittest.TestCase):
    def test_self_test_never_reads_archive_or_sidecar(self) -> None:
        record = checker.load(checker.RECORD_PATH)
        inputs = record["immutable_inputs"]
        external_paths = {
            checker.ROOT / inputs["archive_path"],
            checker.ROOT / inputs["archive_sidecar_path"],
        }
        original_hash = checker.sha256

        def guarded_hash(path: Path) -> str:
            if path in external_paths:
                raise AssertionError("self-test read external release bytes")
            return original_hash(path)

        with (patch.object(checker, "safe_archive_errors", side_effect=AssertionError(
                  "self-test invoked external archive inspection")),
              patch.object(checker, "sha256", side_effect=guarded_hash)):
            self.assertEqual(checker.semantic_errors(
                record, verify_external_archive=False), [])

    def test_default_integration_still_requires_real_archive(self) -> None:
        record = checker.load(checker.RECORD_PATH)
        with patch.object(checker, "safe_archive_errors", return_value=[
                "missing real archive sentinel"]) as validator:
            errors = checker.semantic_errors(record)
        self.assertIn("missing real archive sentinel", errors)
        validator.assert_called_once_with(
            checker.ROOT / record["immutable_inputs"]["archive_path"],
            record["immutable_inputs"]["archive_size"],
            record["immutable_inputs"]["archive_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
