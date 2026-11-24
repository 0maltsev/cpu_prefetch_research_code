#!/usr/bin/env python3
"""Regression for the external operational-journal preflight boundary."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile


POSITIVE_CASES = 2
NEGATIVE_CASES = 3


class CheckError(RuntimeError):
    pass


def run(command: list[str], *, cwd: pathlib.Path | None = None,
        expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if result.returncode != expected:
        raise CheckError(
            f"command returned {result.returncode}, expected {expected}: "
            f"{' '.join(command)}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def cli(
    python: str, repository: pathlib.Path, evidence: pathlib.Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return run([
        python, "-B", str(repository / "tools/stage17_operational_cli_v5.py"),
        "--repository-root", str(repository),
        "--evidence-root", str(evidence),
        *arguments,
    ])


def exact_second(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def self_test(root: pathlib.Path) -> None:
    python = sys.executable
    for executable in ("ssh-keygen",):
        if shutil.which(executable) is None:
            raise CheckError(f"required local executable is absent: {executable}")
    with tempfile.TemporaryDirectory(prefix="stage17-external-journal-") as text:
        temporary = pathlib.Path(text)
        source_bundle = temporary / "source-bundle"
        shutil.copytree(
            root,
            source_bundle,
            symlinks=False,
            ignore=shutil.ignore_patterns(
                ".git", "build", "build-*", "__pycache__", ".pytest_cache",
                "evidence",
            ),
        )
        (source_bundle / "BUNDLE_MANIFEST.json").write_text(
            '{"bundle_profile":"SYNTHETIC-EXTERNAL-JOURNAL-REGRESSION"}\n',
            encoding="ascii",
        )
        (source_bundle / "SHA256SUMS").write_text(
            "synthetic regression fixture; not release evidence\n", encoding="ascii"
        )
        evidence = temporary / "operational"
        evidence.mkdir(mode=0o700)
        preflight = temporary / "preflight"
        preflight.mkdir(mode=0o700)
        bundle = temporary / "bundle"
        bundle.mkdir(mode=0o700)
        archive = temporary / "candidate.tar.gz"
        sidecar = temporary / "candidate.tar.gz.sha256"
        archive.write_bytes(b"synthetic-candidate-bytes\n")
        sidecar.write_text("0" * 64 + "  candidate.tar.gz\n", encoding="ascii")

        identity = temporary / "identity"
        run([
            "ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(identity),
        ])
        public = identity.with_suffix(".pub")
        public_fields = public.read_text(encoding="ascii").split()
        known_hosts = temporary / "known_hosts"
        known_hosts.write_text(
            f"synthetic.invalid {public_fields[0]} {public_fields[1]}\n",
            encoding="ascii",
        )

        cli(
            python, source_bundle, evidence,
            "init", "--materialize-admission-root",
        )
        admission = evidence / "admission-root"
        issued = dt.datetime(2030, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
        recorded = issued + dt.timedelta(seconds=1)
        transitioned = issued + dt.timedelta(seconds=2)
        evaluated = issued + dt.timedelta(seconds=3)
        expires = issued + dt.timedelta(minutes=30)
        output = admission / "evidence/ext001-v10"
        cli(
            python, admission, evidence, "--pilot-archive", str(archive),
            "--pilot-sidecar", str(sidecar), "author-ext001",
            "--stand-id", "SYNTHETIC-STAND",
            "--ssh-target", "synthetic@synthetic.invalid",
            "--known-hosts-host", "synthetic.invalid",
            "--pinned-host-public-key", str(public),
            "--pinned-known-hosts", str(known_hosts),
            "--transport-identity", str(identity),
            "--bundle-root-locator", str(bundle),
            "--capture-id", "SYNTHETIC-EXTERNAL-JOURNAL-CAPTURE",
            "--captured-at-utc", exact_second(recorded),
            "--preflight-evidence-root", str(preflight),
            "--actor", "synthetic-owner",
            "--issued-at-utc", exact_second(issued),
            "--expires-at-utc", exact_second(expires),
            "--authorization-id", "SYNTHETIC-EXT001-AUTH",
            "--attempt-id", "SYNTHETIC-EXT001-ATTEMPT",
            "--contract-id", "SYNTHETIC-EXT001-CONTRACT",
            "--envelope-id", "SYNTHETIC-EXT001-ENVELOPE",
            "--output-directory", str(output),
        )
        cli(
            python, admission, evidence, "--pilot-archive", str(archive),
            "--pilot-sidecar", str(sidecar), "admit-resolution",
            "--input-id", "S17-EXT-001", "--actor", "synthetic-owner",
            "--recorded-at-utc", exact_second(recorded),
            "--repository-evidence", str(output / "envelope-v10.json"),
            "--authorization-file", str(output / "authorization-v9.json"),
        )
        cli(
            python, admission, evidence, "--pilot-archive", str(archive),
            "--pilot-sidecar", str(sidecar), "append-transition",
            "--actor", "synthetic-owner",
            "--timestamp-utc", exact_second(transitioned),
        )
        journal = evidence / "journal/stage17-state-journal-000002.json"
        code = """
import hashlib, pathlib, sys
sys.path.insert(0, str(pathlib.Path(%r) / 'tools'))
import stage17_read_only_preflight_executor_v8 as executor
validation = executor._prospective_validation(
    repository_root=pathlib.Path(%r), latest_journal=pathlib.Path(%r),
    journal_directory=pathlib.Path(%r), actual_utc=%r)
assert validation.current_state == 'AUTHORIZED_FOR_READ_ONLY_PREFLIGHT'
assert validation.action_ready and validation.action_context is not None
assert validation.action_context['runtime_implementation_hashes']['executor'] == hashlib.sha256(pathlib.Path(executor.__file__).read_bytes()).hexdigest()
print('successor-external-journal: PASS')
""" % (str(admission), str(admission), str(journal), str(journal.parent), exact_second(evaluated))
        current = run(
            [python, "-B", "-c", code], cwd=admission,
        )
        if "successor-external-journal: PASS" not in current.stdout:
            raise CheckError("successor did not accept the external journal")

        predecessor_code = """
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(%r) / 'tools'))
import stage17_read_only_preflight_executor_v7 as executor
try:
    executor._prospective_validation(
        repository_root=pathlib.Path(%r), latest_journal=pathlib.Path(%r),
        journal_directory=pathlib.Path(%r), actual_utc=%r)
except Exception as exception:
    assert 'outside repository root' in str(exception)
    print('predecessor-characterization: PASS')
else:
    raise AssertionError('predecessor unexpectedly accepted external journal')
""" % (str(admission), str(admission), str(journal), str(journal.parent), exact_second(evaluated))
        predecessor_result = run(
            [python, "-B", "-c", predecessor_code], cwd=admission,
        )
        if "predecessor-characterization: PASS" not in predecessor_result.stdout:
            raise CheckError("predecessor defect was not characterized")

        outside = temporary / "outside-journal.json"
        outside.write_bytes(journal.read_bytes())
        cross_root_code = """
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(%r) / 'tools'))
import stage17_read_only_preflight_executor_v8 as executor
try:
    executor._prospective_validation(
        repository_root=pathlib.Path(%r), latest_journal=pathlib.Path(%r),
        journal_directory=pathlib.Path(%r), actual_utc=%r)
except Exception as exception:
    assert 'outside the operational evidence root' in str(exception)
    print('cross-root-rejection: PASS')
else:
    raise AssertionError('cross-root journal was accepted')
""" % (str(admission), str(admission), str(outside), str(journal.parent), exact_second(evaluated))
        cross_root = run([python, "-B", "-c", cross_root_code], cwd=admission)
        if "cross-root-rejection: PASS" not in cross_root.stdout:
            raise CheckError("cross-root journal was not rejected")
        if any(preflight.iterdir()):
            raise CheckError("prospective validation created one-shot evidence")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.add_argument(
        "--root", type=pathlib.Path, default=pathlib.Path(__file__).parents[1]
    )
    arguments = parser.parse_args()
    try:
        self_test(arguments.root.resolve())
    except (CheckError, OSError, ValueError) as exception:
        print(f"stage17-external-journal-preflight: FAIL: {exception}", file=sys.stderr)
        return 1
    print(
        "stage17-external-journal-preflight: PASS "
        f"positive={POSITIVE_CASES} negative={NEGATIVE_CASES} transport=0 marker=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
