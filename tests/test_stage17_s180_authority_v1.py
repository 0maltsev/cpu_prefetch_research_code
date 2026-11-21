"""Real SSHSIG verification with synthetic replay views; never launches a run."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage17_s180_authority_v1 as authority
import stage17_s180_plan_prepare_v1 as preparation
import stage17_formal_archive_runtime_v1 as runtime
from test_stage17_s180_plan_prepare_v1 import fixture


class AuthorityTests(unittest.TestCase):
    worker = None

    @classmethod
    def setUpClass(cls):
        identity = json.loads(subprocess.check_output(
            [str(cls.worker), "--stage17-s180-runtime-identity-v1"], timeout=30))
        image = runtime.ImageBinding(cls.worker, identity["size_bytes"], identity["sha256"])
        cls.plan, _ = preparation.prepare(fixture(identity["source_revision"]), worker=image,
            deadline_ns=time.monotonic_ns() + 60_000_000_000)
        cls.native = {key: identity[key] for key in ("role", "profile", "size_bytes", "sha256")}

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="s180-signature-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.key = self.root / "owner"
        subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)],
            check=True, capture_output=True, timeout=10)
        self.allowed = self.root / "allowed_signers"
        self.allowed.write_text('research-owner namespaces="cpu-prefetch-stage17" '
                                + self.key.with_suffix(".pub").read_text())
        trust = dict(measurements=dict(principal="research-owner", sshsig_namespace="cpu-prefetch-stage17",
            allowed_signers_path=str(self.allowed), allowed_signers_size_bytes=self.allowed.stat().st_size,
            allowed_signers_sha256=authority.sha(self.allowed.read_bytes())))
        self.resolutions = {f"S17-EXT-{i:03d}": SimpleNamespace(input_id=f"S17-EXT-{i:03d}",
            resolution_id=f"synthetic-resolution-{i}", sha256=hashlib.sha256(str(i).encode()).hexdigest(),
            semantic_context={}) for i in range(1, 10)}
        self.resolutions["S17-EXT-003"].semantic_context = dict(trust=trust)
        self.resolutions["S17-EXT-007"].sha256 = self.plan["blueprint"]["ext007_resolution"]["sha256"]
        self.resolutions["S17-EXT-007"].semantic_context = dict(data_provenance_accepted=True,
            legacy_statistical_freeze_satisfied=False)
        plan_hash = authority.sha(authority.archive.canonical(self.plan))
        output = self.root / "working" / plan_hash
        output.mkdir(parents=True, mode=0o700)
        st = output.stat()
        now = time.monotonic_ns()
        window = dict(boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            start_monotonic_ns=now, end_monotonic_ns=now + authority.DAY_NS)
        prerequisites = dict(calibration_freeze_sha256=self.plan["blueprint"]["calibration_freeze"]["sha256"],
            ext007_resolution_sha256=self.resolutions["S17-EXT-007"].sha256,
            ext008_resolution_sha256=self.resolutions["S17-EXT-008"].sha256,
            ext009_resolution_sha256=self.resolutions["S17-EXT-009"].sha256,
            qualification_sha256="a"*64, compatibility_sha256="b"*64, runtime_profile_sha256="c"*64)
        self.authorization = dict(schema_version=authority.SCHEMA, authorization_id="synthetic-owner-authorization",
            session_id="synthetic-session", request_id="synthetic-request", attempt_id="synthetic-attempt",
            stand_id=self.plan["blueprint"]["stand_id"], actor="research-owner",
            trust_context={"ext002_resolution": authority.binding(self.resolutions["S17-EXT-002"]),
                           "ext003_resolution": authority.binding(self.resolutions["S17-EXT-003"])},
            plan_sha256=plan_hash, runtime_binding=self.native,
            release_binding=dict(source_revision=self.plan["source_revision"], worker_sha256=self.native["sha256"]),
            prerequisite_bindings=prerequisites, evidence_root_binding=dict(absolute_path=str(output),
                device=st.st_dev, inode=st.st_ino), window_binding=window,
            issued_at_epoch_seconds=time.time_ns()//1_000_000_000-1,
            expires_at_epoch_seconds=time.time_ns()//1_000_000_000+86410,
            permission_scope=copy.deepcopy(authority.PERMISSIONS), synthetic_test_only=False, phase18_authority=False)
        self.plan_context = {key: copy.deepcopy(self.authorization[key]) for key in
            ("plan_sha256", "window_binding", "evidence_root_binding", "runtime_binding", "release_binding")}
        self.plan_context.update(scope_id=authority.PLAN_SCOPE, phase18_authority=False,
            **{k: prerequisites[k] for k in ("qualification_sha256", "compatibility_sha256", "runtime_profile_sha256")})
        self.resource_context = {key: copy.deepcopy(self.authorization[key]) for key in
            ("plan_sha256", "window_binding", "evidence_root_binding")}
        self.resource_context.update(scope_id=authority.RESOURCE_SCOPE, resource_admission_status="ADMITTED",
            phase18_authority=False)
        self.resolutions["S17-EXT-008"].semantic_context = self.plan_context
        self.resolutions["S17-EXT-009"].semantic_context = self.resource_context
        # This is explicitly a software fixture, not a real authenticated journal
        # or a new semantic-admission implementation. Generic readiness stays false.
        self.validation = SimpleNamespace(resolutions=self.resolutions, pilot_ready=False)

    def sign(self, document=None, *, key=None, namespace="cpu-prefetch-stage17"):
        raw = authority.archive.canonical(self.authorization if document is None else document)
        path = self.root / "authorization.json"
        path.write_bytes(raw)
        signature = Path(str(path) + ".sig")
        if signature.exists():
            signature.unlink()
        subprocess.run(["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(key or self.key),
            "-n", namespace, str(path)], check=True, capture_output=True, timeout=10)
        return raw, signature

    def verify(self, raw=None, signature=None, **changes):
        if raw is None:
            raw, signature = self.sign()
        return authority.verify_authorization(authorization_bytes=raw, signature_path=signature,
            plan=changes.get("plan", self.plan), validation=self.validation)

    def test_actual_signature_derives_exact_acyclic_native_request_without_launch_authority(self):
        raw, signature = self.sign()
        verified = self.verify(raw, signature)
        request = authority.archive.parse_json(verified.request_bytes)
        self.assertEqual(request["schema_version"], "cpu-prefetch-stage17-s180-session-request/1")
        self.assertEqual(request["plan"], self.plan)
        self.assertEqual(request["prerequisite_bindings"]["ext010_authorization_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(verified.request_sha256, hashlib.sha256(verified.request_bytes).hexdigest())
        self.assertNotIn("request_binding", self.authorization)
        for key in ("attempt_consumed", "launch_ready", "execution_authority", "phase18_authority"):
            self.assertIs(verified.proof()[key], False)
        self.authorization["session_id"] = "changed-after-verification"
        self.assertEqual(authority.archive.parse_json(verified.request_bytes)["session_id"], "synthetic-session")

    def test_changed_signed_bytes_wrong_key_and_wrong_namespace_reject(self):
        raw, signature = self.sign()
        changed = copy.deepcopy(self.authorization)
        changed["session_id"] = "unauthorized-session"
        with self.assertRaises(authority.signatures.ControllerError):
            self.verify(authority.archive.canonical(changed), signature)
        other = self.root / "other"
        subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(other)],
            check=True, capture_output=True, timeout=10)
        for key, namespace in ((other, "cpu-prefetch-stage17"), (self.key, "unrelated-namespace")):
            raw, signature = self.sign(key=key, namespace=namespace)
            with self.assertRaises(authority.signatures.ControllerError):
                self.verify(raw, signature)

    def test_authorization_cannot_select_trust_or_change_admitted_runtime_or_plan(self):
        changes = [("actor", "different-owner"), ("plan_sha256", "f"*64),
            ("runtime_binding", dict(self.native, sha256="f"*64)),
            ("trust_context", dict(self.authorization["trust_context"], extra="self-selected-trust"))]
        for key, value in changes:
            with self.subTest(key=key):
                changed = copy.deepcopy(self.authorization)
                changed[key] = value
                raw, signature = self.sign(changed)
                with self.assertRaises(authority.AuthorityError):
                    self.verify(raw, signature)
        changed = copy.deepcopy(self.plan)
        changed["captures"][0]["execution_budget"]["max_output_bytes"] += 1
        raw, signature = self.sign()
        with self.assertRaises(authority.AuthorityError):
            self.verify(raw, signature, plan=changed)

    def test_missing_or_legacy_scoped_predecessors_and_forged_qualification_credit_reject(self):
        for context, key, value in ((self.plan_context, "scope_id", "LEGACY-PILOT"),
            (self.resource_context, "resource_admission_status", "NOT_ASSESSED"),
            (self.plan_context, "qualification_sha256", "f"*64),
            (self.plan_context, "compatibility_sha256", "f"*64),
            (self.resource_context, "phase18_authority", True)):
            with self.subTest(key=key):
                original = context[key]
                context[key] = value
                try:
                    with self.assertRaises(authority.AuthorityError):
                        self.verify()
                finally:
                    context[key] = original
        saved = self.resolutions.pop("S17-EXT-009")
        try:
            with self.assertRaises(authority.AuthorityError):
                self.verify()
        finally:
            self.resolutions["S17-EXT-009"] = saved

    def test_retries_stage18_unknown_commands_and_synthetic_authority_reject(self):
        for key, value in (("phase18_authority", True), ("synthetic_test_only", True),
            ("argv", ["anything"]), ("request_binding", {"path": "/tmp/foreign"}),
            ("permission_scope", dict(authority.PERMISSIONS, automatic_retry=True))):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.authorization)
                changed[key] = value
                raw, signature = self.sign(changed)
                with self.assertRaises(authority.AuthorityError):
                    self.verify(raw, signature)

    def test_original_boot_day_window_and_expiry_cannot_be_replaced(self):
        for key, value in (("boot_id", "unrelated-boot"),
            ("end_monotonic_ns", self.authorization["window_binding"]["end_monotonic_ns"]+1),
            ("start_monotonic_ns", self.authorization["window_binding"]["end_monotonic_ns"])):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.authorization)
                changed["window_binding"][key] = value
                raw, signature = self.sign(changed)
                with self.assertRaises(authority.AuthorityError):
                    self.verify(raw, signature)
        for key, value in (("issued_at_epoch_seconds", time.time_ns()//1_000_000_000+60),
            ("expires_at_epoch_seconds", time.time_ns()//1_000_000_000+60)):
            changed = copy.deepcopy(self.authorization)
            changed[key] = value
            raw, signature = self.sign(changed)
            with self.assertRaises(authority.AuthorityError):
                self.verify(raw, signature)

    def test_exact_actual_ext010_replay_is_required_for_admitted_reentry(self):
        raw, signature = self.sign()
        args = dict(authorization_bytes=raw, signature_path=signature, plan=self.plan, validation=self.validation)
        with self.assertRaises(authority.AuthorityError):
            authority.verify_admitted_authorization(**args)
        context = dict(scope_id="D310-S180-FAMILY-AUTHORIZATION-v1", authorization_sha256=authority.sha(raw),
            authorization=copy.deepcopy(self.authorization), phase18_authority=False)
        self.resolutions["S17-EXT-010"] = SimpleNamespace(input_id="S17-EXT-010", semantic_context=context)
        self.assertEqual(authority.verify_admitted_authorization(**args).authorization_bytes, raw)
        context["authorization_sha256"] = "f"*64
        with self.assertRaises(authority.AuthorityError):
            authority.verify_admitted_authorization(**args)

    def test_noncanonical_duplicate_and_oversized_authorizations_reject(self):
        raw, signature = self.sign()
        for invalid in (raw+b"\n", b'{"schema_version":1,"schema_version":2}', b" "*(authority.LIMIT+1)):
            with self.subTest(size=len(invalid)):
                with self.assertRaises(authority.archive.ArchiveError):
                    self.verify(invalid, signature)

    def test_admitted_allowed_signers_bytes_and_safe_signature_files_are_required(self):
        raw, signature = self.sign()
        original = self.allowed.read_bytes()
        self.allowed.write_bytes(original + b"\n")
        with self.assertRaises(authority.signatures.ControllerError):
            self.verify(raw, signature)
        self.allowed.write_bytes(original)
        self.allowed.chmod(0o666)
        with self.assertRaises(authority.signatures.ControllerError):
            self.verify(raw, signature)
        self.allowed.chmod(0o600)
        alias = self.root / "signature-alias"
        alias.symlink_to(signature)
        with self.assertRaises(OSError):
            self.verify(raw, alias)

    def test_document_schema_agrees_with_the_signed_closed_contract(self):
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).resolve().parents[1] /
            "config/schemas/stage17-s180-authorization-v1.schema.json").read_bytes())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        validator.validate(self.authorization)
        changed = copy.deepcopy(self.authorization)
        changed["permission_scope"]["automatic_retry"] = True
        self.assertTrue(list(validator.iter_errors(changed)))

    def test_native_identity_grammar_rejects_signed_unlaunchable_ids(self):
        for value in ("x"*257, "foreign/path", "has whitespace", "non-ascii-\u00e9", "_leading-punctuation"):
            changed = copy.deepcopy(self.authorization)
            changed["request_id"] = value
            raw, signature = self.sign(changed)
            with self.assertRaises(authority.AuthorityError):
                self.verify(raw, signature)

    def test_real_directory_can_precede_resource_record_and_then_bind_signed_authority(self):
        import stage17_s180_archive_custody_v1 as storage
        import stage17_formal_archive_custody_v1 as custody
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="s180-authority-reservation-", dir=root / "build") as temporary:
            program = Path(temporary) / "program"
            scope = custody.ProgramStore.initialize(program, program_id="synthetic-s180",
                storage_domain_id="synthetic-disk", prospective_admission_sha256="e"*64)
            plan = copy.deepcopy(self.plan)
            plan["storage"]["program_scope_sha256"] = scope
            family = authority.sha(authority.archive.canonical(plan))
            limits = custody.CustodyLimits(131072, 1024, 4096, 131072, self.deadline())
            args = dict(scope_sha256=scope, family_id=family, limits=limits)
            with storage.ProgramStore(program, ext009_resolution_sha256=None, **args) as store:
                reserved = store.reserve_family()["document"]
                with self.assertRaises(custody.CustodyError):
                    store.prepare_family(family)
            # Replay views remain explicitly synthetic. The filesystem/ledger,
            # inode and SSHSIG operations in this integration are actual.
            for context in (self.plan_context, self.resource_context, self.authorization):
                context["plan_sha256"] = family
                context["evidence_root_binding"] = reserved["evidence_root_binding"]
            with storage.ProgramStore(program,
                    ext009_resolution_sha256=self.resolutions["S17-EXT-009"].sha256, **args) as store:
                store.bind_admission()
                store.prepare_family(family)
                raw, signature = self.sign()
                verified = self.verify(raw, signature, plan=plan)
                self.assertEqual(authority.archive.parse_json(verified.request_bytes)["plan"], plan)
                self.assertEqual(store.working.stat().st_ino,
                    self.authorization["evidence_root_binding"]["inode"])

    @staticmethod
    def deadline():
        return time.monotonic_ns()+30_000_000_000


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, required=True)
    args, rest = parser.parse_known_args()
    AuthorityTests.worker = args.worker.resolve()
    unittest.main(argv=[__file__, *rest])
