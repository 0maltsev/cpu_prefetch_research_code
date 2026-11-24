#!/usr/bin/env python3
"""D-204 real CLI admission and fresh-process preflight binding regression.

Synthetic local fixtures only: no SSH, transport, marker, or hardware execution.
"""
from __future__ import annotations
import argparse
import contextlib
import io
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import tarfile
import types
import unittest
from unittest.mock import patch
import stage17_pilot_candidate_artifact_v10 as release
import stage17_operational_semantics_v14 as operational
import stage17_semantic_verifier_v56 as semantic
import stage17_output_registry_v9 as registry

ROOT = pathlib.Path(__file__).resolve().parents[1]
from typing import Any
import author_stage17_no_predecessor_attestation_v1 as attestation_tool

class CheckError(RuntimeError):
    pass

def run(command: list[str], *, cwd: pathlib.Path | None = None,
        expected: int = 0) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command, cwd=cwd, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if completed.returncode != expected:
        raise CheckError(
            f"command returned {completed.returncode}, expected {expected}: "
            f"{' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed

def exact_second(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")

def create_attestation_evidence(temporary: pathlib.Path) -> pathlib.Path:
    search_evidence = temporary / "d133-search-evidence.txt"
    search_evidence.write_text(
        "synthetic D-133 regression fixture; not real search evidence\n",
        encoding="ascii",
    )
    output = temporary / "no-predecessor-attestation.json"
    completed = run([
        sys.executable, "-B", str(pathlib.Path(attestation_tool.__file__)),
        "--attestation-id", "SYNTHETIC-D133-ATTESTATION",
        "--actor", "synthetic-owner",
        "--search-evidence", str(search_evidence),
        "--search-evidence-schema-identity",
        "cpu-prefetch-stage17-d120-d121-d123-search-record/1",
        "--output", str(output),
    ])
    assert "PASS" in completed.stdout
    return output

def cli(python: str, repository: pathlib.Path, evidence: pathlib.Path,
        *arguments: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    return run([
        python, "-B", str(repository / "tools/stage17_operational_cli_v16.py"),
        "--repository-root", str(repository), "--evidence-root", str(evidence),
        *arguments,
    ], expected=expected)

def run_branch(root: pathlib.Path, source_bundle: pathlib.Path, *,
               branch: str, output_subdir: str) -> dict[str, Any]:
    python = sys.executable
    with tempfile.TemporaryDirectory(prefix=f"stage17-d146-{branch.lower()}-") as text:
        temporary = pathlib.Path(text)
        evidence = temporary / "operational"
        evidence.mkdir(mode=0o700)
        preflight = temporary / "preflight-output"
        preflight.mkdir(mode=0o700)
        bundle_root = temporary / "remote-bundle-root"
        bundle_root.mkdir(mode=0o700)
        (bundle_root / "BUNDLE_MANIFEST.json").write_text(
            '{"bundle_profile":"SYNTHETIC-D146-CAPTURED-BUNDLE"}\n', encoding="ascii",
        )
        (bundle_root / "SHA256SUMS").write_text(
            "synthetic-inventory-line-1\nsynthetic-inventory-line-2\n", encoding="ascii",
        )
        archive = temporary / "candidate.tar.gz"
        sidecar = temporary / "candidate.tar.gz.sha256"
        archive.write_bytes(b"synthetic candidate archive\n")
        sidecar.write_text("0" * 64 + "  candidate.tar.gz\n", encoding="ascii")
        identity = temporary / "identity"
        run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(identity)])
        identity.chmod(0o600)
        public = identity.with_suffix(".pub")
        public_fields = public.read_text(encoding="ascii").split()
        known_hosts = temporary / "known_hosts"
        known_hosts.write_text(
            f"synthetic.invalid {public_fields[0]} {public_fields[1]}\n",
            encoding="ascii",
        )
        initialized = cli(
            python, source_bundle, evidence, "init", "--materialize-admission-root",
        )
        marker = "admission_root="
        admission = pathlib.Path(initialized.stdout.split(marker, 1)[1].strip())
        issued = dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)
        recorded = issued + dt.timedelta(seconds=4)
        transition_time = issued + dt.timedelta(seconds=5)
        evaluated = issued + dt.timedelta(seconds=6)
        expires = issued + dt.timedelta(minutes=30)
        output = admission / output_subdir
        base_args = [
            "--stand-id", "SYNTHETIC-STAND", "--ssh-target", "synthetic@synthetic.invalid",
            "--known-hosts-host", "synthetic.invalid",
            "--pinned-host-public-key", str(public),
            "--pinned-known-hosts", str(known_hosts),
            "--transport-identity", str(identity),
            "--bundle-root-locator", str(bundle_root),
            "--capture-id", f"SYNTHETIC-D146-{branch}-CAPTURE",
            "--captured-at-utc", exact_second(recorded),
            "--preflight-evidence-root", str(preflight),
        ]
        attestation = create_attestation_evidence(temporary)
        base_args += ["--no-predecessor-attestation", str(attestation)]
        base_args += [
            "--actor", "synthetic-owner",
            "--issued-at-utc", exact_second(issued),
            "--expires-at-utc", exact_second(expires),
            "--authorization-id", f"SYNTHETIC-EXT001-D146-{branch}-AUTH",
            "--attempt-id", f"SYNTHETIC-EXT001-D146-{branch}-ATTEMPT",
            "--contract-id", f"SYNTHETIC-EXT001-D146-{branch}-CONTRACT",
            "--envelope-id", f"SYNTHETIC-EXT001-D146-{branch}-ENVELOPE",
            "--output-directory", str(output),
        ]
        cli(python, admission, evidence, "--pilot-archive", str(archive),
            "--pilot-sidecar", str(sidecar), "author-ext001", *base_args)
        cli(
            python, admission, evidence, "--pilot-archive", str(archive),
            "--pilot-sidecar", str(sidecar), "admit-resolution",
            "--input-id", "S17-EXT-001", "--actor", "synthetic-owner",
            "--recorded-at-utc", exact_second(recorded),
            "--repository-evidence", str(output / "envelope-v14.json"),
            "--authorization-file", str(output / "authorization-v11.json"),
        )
        cli(
            python, admission, evidence, "--pilot-archive", str(archive),
            "--pilot-sidecar", str(sidecar), "append-transition",
            "--actor", "synthetic-owner", "--timestamp-utc", exact_second(transition_time),
        )
        latest = evidence / "journal/stage17-state-journal-000002.json"
        code = """
import importlib, json, pathlib, sys
root, latest = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path.insert(0, str(root / 'tools'))
for name in json.loads(sys.argv[4]):
    importlib.import_module(name)
import stage17_operational_cli_v16 as cli
import stage17_read_only_preflight_executor_v30 as executor
import stage17_q15_session_controller_v18 as session
import stage17_state_journal_v12 as dispatch
# Each real entry point reselects the current generation after legacy imports.
cli.activate(); executor.activate(); session.activate()
assert dispatch.semantic.__name__ == 'stage17_semantic_verifier_v56'
assert executor.owner.current_journal.__name__ == 'stage17_state_journal_v50'
assert session.execution_body.phase_controller.__name__ == 'stage17_phase_controller_v23'
assert cli.predecessor.controller.__name__ == 'stage17_phase_controller_v23'
assert cli.predecessor.controller.formal_prepare.journal_runtime.__name__ == 'stage17_state_journal_v50'
validation = executor.owner._prospective_validation(
    repository_root=root, latest_journal=latest,
    journal_directory=latest.parent, actual_utc=sys.argv[3])
assert validation.current_state == 'AUTHORIZED_FOR_READ_ONLY_PREFLIGHT'
assert validation.resolution_count == 1 and validation.transition_count == 1
assert validation.action_ready and validation.action_context is not None
paths = executor.runtime_identity_paths()
assert paths['executor'] == str(root/'tools/stage17_read_only_preflight_executor_v30.py')
assert paths['state_journal'] == str(root/'tools/stage17_state_journal_v50.py')
bindings = validation.action_context['pre_marker_file_bindings']
print(json.dumps({'extra_binding_count':1,'total_binding_count':len(bindings)}))
"""
        orders = [
            ["stage17_operational_cli_v16", "stage17_read_only_preflight_executor_v30",
             "stage17_q15_session_controller_v17", "stage17_fixed_action_executor_v8", "stage17_q15_session_controller_v18"],
            ["stage17_read_only_preflight_executor_v30", "stage17_q15_session_controller_v17",
             "stage17_operational_cli_v16", "stage17_phase_controller_v22"],
            ["stage17_q15_session_controller_v17", "stage17_operational_cli_v16",
             "stage17_read_only_preflight_executor_v29", "stage17_q15_session_controller_v18"],
        ]
        for order in orders:
            completed = run([python, "-I", "-B", "-c", code, str(admission), str(latest),
                             exact_second(evaluated), json.dumps(order)], cwd=admission)
        legacy_code = """
import pathlib,sys
root=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(root/'tools'))
import stage17_read_only_preflight_executor_v29
import stage17_read_only_preflight_executor_v25 as owner
owner._prospective_validation(repository_root=root,latest_journal=pathlib.Path(sys.argv[2]),
    journal_directory=pathlib.Path(sys.argv[2]).parent,actual_utc=sys.argv[3])
"""
        legacy = subprocess.run([python, "-I", "-B", "-c", legacy_code, str(admission),
            str(latest), exact_second(evaluated)], capture_output=True, text=True, check=False)
        if legacy.returncode == 0 or "drifted" not in legacy.stderr:
            raise CheckError("legacy executor did not reproduce the policy drift: " + legacy.stderr)
        # Expired authority and a source-binding mutation must still fail closed.
        expired = subprocess.run([python, "-I", "-B", "-c", code, str(admission), str(latest),
            exact_second(expires + dt.timedelta(seconds=1)), json.dumps(orders[0])],
            capture_output=True, text=True, check=False)
        if expired.returncode == 0:
            raise CheckError("expired prospective authority accepted")
        changed = admission / "tools/stage17_read_only_preflight_executor_v30.py"
        changed.chmod(0o644)
        changed.write_bytes(changed.read_bytes() + b"\n# synthetic integrity mutant\n")
        drifted = subprocess.run([python, "-I", "-B", "-c", code, str(admission), str(latest),
            exact_second(evaluated), json.dumps(orders[0])], capture_output=True, text=True, check=False)
        if drifted.returncode == 0 or "drifted" not in drifted.stderr:
            raise CheckError("source drift did not fail closed: " + drifted.stderr)
        result = json.loads(completed.stdout)
        expected_count = 1 if branch == "ATTESTATION" else 3
        if result["extra_binding_count"] != expected_count:
            raise CheckError(
                f"{branch}: expected {expected_count} extra file bindings, "
                f"got {result['extra_binding_count']}"
            )
        if any(preflight.iterdir()):
            raise CheckError(f"{branch}: action-readiness evaluation created preflight evidence")
        return result

class SuccessorReleaseTests(unittest.TestCase):
    """Archive/schema/identity wiring with only native identity/full verifier mocked.

    These tests do not qualify a release; main must run the actual full bundle
    verifier and actual seven-action ELF against a clean source revision.
    """
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='discovery-release-test-');self.addCleanup(self.temp.cleanup)
        self.directory=pathlib.Path(self.temp.name);self.bundle=self.directory/'bundle';self.bundle.mkdir()
        self.worker=self.bundle/'release/bin/cpu_prefetch_runner';self.worker.parent.mkdir(parents=True)
        self.worker.write_bytes(b'\x7fELF--execute-fixed-stage17-action-v4 --execute-fixed-stage17-action-v5 STAGE17-FIXED-ACTION-WORKER-v4')
        verifier=self.bundle/'validators/verify_stand_bundle.py';verifier.parent.mkdir();verifier.write_bytes(b'# test boundary only\n')
        (self.bundle/'SBOM.spdx.json').write_bytes(b'{}\n')
        self.manifest=dict(bundle_profile='STAGE17-HERMETIC-DRY-RUN-BUNDLE-v20',
            source_archive=dict(source_revision='a'*40),pilot_authorized=False,confirmatory_authorized=False,
            dynamic_qualification_authorized=False,stage17_fixed_action_runtime=dict(
                member_path='release/bin/cpu_prefetch_runner',size_bytes=self.worker.stat().st_size,
                sha256=registry.sha256(self.worker.read_bytes()),role='STAGE17_FIXED_ACTION_WORKER',
                runtime_profile='STAGE17-FIXED-ACTION-WORKER-v4',supported_actions=list(release.SUPPORTED_ACTIONS),synthetic_test_only=True))
        self.identity=dict(binary_sha256=registry.sha256(self.worker.read_bytes()),protocol_version='2.0.0-pre.3',
            role='STAGE17_FIXED_ACTION_WORKER',runtime_profile='STAGE17-FIXED-ACTION-WORKER-v4',source_dirty=False,
            source_revision='a'*40,supported_actions=list(release.SUPPORTED_ACTIONS),synthetic_test_only=True)
        self.seal()
        self.archive=self.directory/'bundle.tar.gz'
        with tarfile.open(self.archive,'w:gz') as archive:
            for path in sorted(self.bundle.rglob('*')):
                if path.is_file():archive.add(path,arcname='bundle/'+path.relative_to(self.bundle).as_posix())
        self.sidecar=self.directory/'bundle.tar.gz.sha256'
        self.sidecar.write_text(registry.sha256(self.archive.read_bytes())+'  '+self.archive.name+'\n')
        patcher=patch.object(release,'_run_full_verifier');self.full=patcher.start();self.addCleanup(patcher.stop)
        patcher=patch.object(release.subprocess,'run',side_effect=lambda *a,**kw: types.SimpleNamespace(
            returncode=0,stdout=registry.canonical(self.identity),stderr=b''))
        patcher.start();self.addCleanup(patcher.stop)

    def seal(self):
        (self.bundle/'BUNDLE_MANIFEST.json').write_bytes(registry.canonical(self.manifest))
        files=[p for p in self.bundle.rglob('*') if p.is_file() and p.name not in ('SHA256SUMS','BUNDLE_INVENTORY.json')]
        inventory=dict(schema_version='cpu-prefetch-stand-bundle-inventory/1',files=[dict(path=p.relative_to(self.bundle).as_posix(),
            size_bytes=p.stat().st_size,sha256=registry.sha256(p.read_bytes())) for p in files])
        inventory_path=self.bundle/'BUNDLE_INVENTORY.json';inventory_path.write_bytes(registry.canonical(inventory));files.append(inventory_path)
        (self.bundle/'SHA256SUMS').write_text(''.join(registry.sha256(p.read_bytes())+'  '+p.relative_to(self.bundle).as_posix()+'\n' for p in files))

    def contract(self):
        document=release.build_contract_v10(repository_root=ROOT,archive=self.archive,sidecar=self.sidecar,
            primary_custody_domain_id='test-a',secondary_custody_domain_id='test-b',contract_id='test-contract')
        path=self.directory/'contract.json';path.write_bytes(registry.canonical(document));return document,path

    def test_seven_action_archive_ext006_and_predecessor_mismatch(self):
        document,path=self.contract()
        context=release.verify_pilot_candidate_artifact_v10(repository_root=ROOT,contract_path=path,archive=self.archive,sidecar=self.sidecar)
        self.assertEqual(context.supported_actions,release.SUPPORTED_ACTIONS)
        self.assertTrue(self.full.called)
        extracted=release.verify_extracted_bundle_v10(self.bundle)
        ext3=types.SimpleNamespace(semantic_context={'release':extracted})
        args=dict(root=ROOT,receipt_documents=[dict(verifier_id=release.VERIFIER_ID,verifier_version='5',artifact_locator=str(path))],
            admitted_resolutions={'S17-EXT-003':ext3},pilot_archive=self.archive,pilot_sidecar=self.sidecar,allow_synthetic=True)
        admitted=semantic.verify_input(input_id='S17-EXT-006',**args)
        self.assertEqual(admitted['context']['supported_actions'],list(release.SUPPORTED_ACTIONS))
        import dataclasses
        ext3.semantic_context['release']=dataclasses.replace(extracted,worker_sha256='f'*64)
        with self.assertRaisesRegex(semantic.SemanticAdmissionError,'differs from EXT002/003'):
            semantic.verify_input(input_id='S17-EXT-006',**args)
        document['worker']['supported_actions'].pop();path.write_bytes(registry.canonical(document))
        with self.assertRaisesRegex(release.ArtifactError,'schema rejection'):
            release.verify_pilot_candidate_artifact_v10(repository_root=ROOT,contract_path=path,archive=self.archive,sidecar=self.sidecar)

    def test_ext002_provenance_schema_and_clean_release_binding(self):
        receipt=release.build_extracted_release_receipt_v10(bundle_root=self.bundle,receipt_id='test-receipt')
        context=release.verify_extracted_release_receipt_v10(repository_root=ROOT,receipt=receipt)
        path=self.directory/'provenance.json';payload=registry.canonical(receipt);path.write_bytes(payload)
        schema=(ROOT/release.RUNTIME_RELEASE_PROVENANCE_SCHEMA).read_bytes()
        reference=dict(role='RUNTIME_RELEASE_PROVENANCE',artifact_id='provenance',locator=path.name,
            size_bytes=len(payload),sha256=registry.sha256(payload),schema_identity=receipt['schema_version'],media_type='application/json',
            schema_binding=dict(path=release.RUNTIME_RELEASE_PROVENANCE_SCHEMA,size_bytes=len(schema),sha256=registry.sha256(schema)))
        artifacts=operational._read_artifacts(ROOT,self.directory/'manifest.json',{'artifacts':[reference]},
            {release.RUNTIME_RELEASE_PROVENANCE_SCHEMA:schema})
        values=dict(bundle_profile=context.bundle_profile,source_revision=context.source_revision,
            bundle_manifest_sha256=context.manifest_sha256,sha256s_sha256=context.sha256s_sha256,
            sbom_sha256=context.sbom_sha256,inventory_sha256=context.inventory_sha256,worker_path=str(context.worker_path),
            worker_size_bytes=context.worker_size_bytes,worker_sha256=context.worker_sha256,worker_role=context.worker_role,
            runtime_profile=context.runtime_profile,supported_actions=list(context.supported_actions),
            full_bundle_verifier_sha256=context.full_verifier_sha256)
        runtime=types.SimpleNamespace(document={'measurements':values})
        worker=types.SimpleNamespace(path=self.worker,payload=self.worker.read_bytes())
        self.assertEqual(operational._verify_release(ROOT,artifacts[0],runtime,worker),context)
        values['supported_actions'].pop()
        with self.assertRaisesRegex(operational.OperationalSemanticError,'identity differs'):
            operational._verify_release(ROOT,artifacts[0],runtime,worker)

    def test_full_verifier_and_dirty_native_identity_rejected(self):
        self.full.side_effect=release.ArtifactError('full verifier failed')
        with self.assertRaisesRegex(release.ArtifactError,'full verifier'):release.verify_extracted_bundle_v10(self.bundle)
        self.full.side_effect=None;self.identity['source_dirty']=True
        with self.assertRaisesRegex(release.ArtifactError,'runtime identity'):release.verify_extracted_bundle_v10(self.bundle)

    def test_old_contract_dispatch_remains_predecessor(self):
        path=self.directory/'old-contract.json';path.write_text('{"schema_version":"cpu-prefetch-stage17-pilot-candidate-external-contract/4"}')
        with patch.object(release.predecessor,'verify_pilot_candidate_artifact_v9',return_value='old') as previous:
            self.assertEqual(release.verify_pilot_candidate_artifact_v10(contract_path=path),'old')
            previous.assert_called_once()

    def test_bundle_verifier_new_and_legacy_surfaces(self):
        import verify_stand_bundle as bundle_verifier
        original_payload=self.worker.read_bytes()
        for profile,actions,new_marker in (
                ('STAGE17-PILOT-CANDIDATE-BUNDLE-v22',release.SUPPORTED_ACTIONS[:6],False),
                ('STAGE17-PILOT-CANDIDATE-BUNDLE-v23',release.SUPPORTED_ACTIONS,True),
                ('STAGE17-PILOT-CANDIDATE-BUNDLE-v24',release.SUPPORTED_ACTIONS,True),
                ('STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19',release.SUPPORTED_ACTIONS,True),
                ('STAGE17-HERMETIC-DRY-RUN-BUNDLE-v20',release.SUPPORTED_ACTIONS,True)):
            with self.subTest(profile=profile):
                payload=b'\x7fELF--execute-fixed-stage17-action-v4 STAGE17-FIXED-ACTION-WORKER-v4 --execute-stage17-pilot-session-v1 '+b' '.join(a.encode() for a in actions)
                if new_marker: payload+=b' --execute-fixed-stage17-action-v5'
                self.worker.write_bytes(payload)
                synthetic='HERMETIC' in profile
                self.identity.update(binary_sha256=registry.sha256(payload),supported_actions=list(actions),synthetic_test_only=synthetic)
                self.manifest['bundle_profile']=profile
                self.manifest['stage17_fixed_action_runtime'].update(size_bytes=len(payload),sha256=registry.sha256(payload),supported_actions=list(actions),synthetic_test_only=synthetic)
                self.manifest.update(schema_version='cpu-prefetch-pilot-candidate-bundle/14',protocol_version='2.0.0-pre.3',
                    readiness_state='RELEASE_INPUT_READY_FOR_Q15_PREPARATION',measurement_execution_command_present=False,
                    debug_symbol_strategy='UNSTRIPPED_RELEASE_BINARIES_WITH_EXACT_BUILD_PROVENANCE',software_prefetch_mapping_id='X86-64-PREFETCHT0-ONLY-v1')
                path=self.bundle/'config/examples/stage16-stand-inputs.example.json';path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('{"authoritative":false,"required_external_inputs":{}}')
                self.seal();error=io.StringIO()
                with patch.object(sys,'argv',['verify_stand_bundle.py','--root',str(self.bundle)]),contextlib.redirect_stderr(error):
                    self.assertEqual(bundle_verifier.main(),1) # Deliberately unqualified small fixture.
                failures=error.getvalue()
                self.assertNotIn('unknown bundle profile',failures)
                self.assertNotIn('wrong protocol version',failures)
                self.assertNotIn('runtime binding is invalid',failures)
                self.assertNotIn('lacks fixed dispatcher',failures)
                self.assertNotIn('runtime identity/provenance is invalid',failures)
                self.assertIn('controller identity is invalid',failures)

def self_test(root):
    results = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(SuccessorReleaseTests))
    if not results.wasSuccessful():
        raise CheckError("release successor unit checks failed")
    import author_stage17_policy_v56 as author
    from create_stand_bundle import copy_policy_bound_files
    from verify_stand_bundle import diagnostic_runtime_closure_errors
    with tempfile.TemporaryDirectory(prefix="stage17-d204-") as temp:
        projected = pathlib.Path(temp) / "source"
        shutil.copytree(root, projected, ignore=shutil.ignore_patterns(
            ".git", ".agents", ".codex", "build", "build-*", "__pycache__", ".pytest_cache", "evidence"))
        nested = author.render_preflight(projected)
        (projected / author.preflight.POLICY_PATH).write_bytes(author._BASE.canonical(nested))
        policy = author.render(projected)
        (projected / author.verifier.POLICY_PATH).write_bytes(author._BASE.canonical(policy))
        # Packaged source projection has only authenticated runtime paths.
        package = pathlib.Path(temp) / "projection"
        package.mkdir()
        copy_policy_bound_files(projected, package, policy)
        failures = diagnostic_runtime_closure_errors(package, policy)
        if failures:
            raise CheckError("\n".join(failures))
        (projected / "BUNDLE_MANIFEST.json").write_text(
            '{"bundle_profile":"SYNTHETIC-D204-REGRESSION"}\n')
        (projected / "SHA256SUMS").write_text("synthetic fixture only\n")
        run_branch(root, projected, branch="ATTESTATION", output_subdir="evidence/ext001-d204")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        self_test(args.root.resolve())
    except Exception as exception:
        print("stage17-preflight-successor: FAIL " + str(exception), file=sys.stderr)
        return 1
    print("stage17-preflight-successor: PASS CLI author/admit/transition; 3 import orders; expiry/source negatives; isolated closure; transport=0 marker=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
