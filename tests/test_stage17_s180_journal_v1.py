"""Real signed/durable journal tests with explicitly synthetic semantic facts."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage17_s180_journal_v1 as journal
import stage17_s180_authority_v1 as authority
import test_stage17_s180_authority_v1 as fixtures


ERRORS = (journal.JournalError, authority.AuthorityError, authority.signatures.ControllerError,
          journal.archive.ArchiveError, journal.readers.AdmissionError, OSError)


class JournalTests(unittest.TestCase):
    worker = None

    @classmethod
    def setUpClass(cls):
        fixtures.AuthorityTests.worker = cls.worker
        fixtures.AuthorityTests.setUpClass()

    def setUp(self):
        self.f = fixtures.AuthorityTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root / "scoped-journal"
        self.base = SimpleNamespace(resolutions={k:copy.deepcopy(v) for k,v in self.f.resolutions.items()
            if int(k[-3:]) <= 7}, latest_journal_sha256=authority.sha(b"software-only-base-journal"))
        self.base.resolutions['S17-EXT-007'].semantic_context['calibration_scope']=journal.CALIBRATION_SCOPE
        self.policy = authority.sha(Path(__file__).read_bytes())
        self.calls = []
        self.fail = None
        self.counter = 0
        self.original_base = copy.deepcopy(self.base.resolutions)
        with self.make_initialized():
            pass

    def semantic(self, input_id, payload, view, *, for_execution):
        self.calls.append((input_id, for_execution))
        # A software-only provider, not an actual source/platform/resource
        # verifier. Journal bytes cannot select it or substitute their context.
        if input_id == self.fail or payload != {"fact": input_id}:
            raise journal.JournalError("synthetic independent semantic rejection")
        self.assertFalse(view.pilot_ready)
        self.assertFalse(view.execution_authority)
        return copy.deepcopy(self.f.plan_context if input_id == "S17-EXT-008" else self.f.resource_context)

    def make(self, **changes):
        args = dict(base_validation=self.base, plan=self.f.plan, semantic_policy_sha256=self.policy,
            semantic_replay=self.semantic, synthetic_test_only=True)
        args.update(changes)
        return journal.ScopedJournal(self.root, **args)

    def make_initialized(self):
        obj = self.make()
        obj.initialize()
        return obj

    def bind(self, path):
        raw = path.read_bytes()
        return dict(path=str(path), size_bytes=len(raw), sha256=authority.sha(raw))

    def sign(self, raw, *, key=None, namespace="cpu-prefetch-stage17"):
        self.counter += 1
        path = self.f.root / f"signed-record-{self.counter}.json"
        path.write_bytes(raw)
        subprocess.run(["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(key or self.f.key),
            "-n", namespace, str(path)], check=True, capture_output=True, timeout=10)
        return dict(record_binding=self.bind(path), signature_binding=self.bind(Path(str(path)+".sig")))

    def add(self, obj, number):
        input_id = f"S17-EXT-{number:03d}"
        if number == 10:
            view = obj.inspect()
            for i in (8,9):
                self.f.authorization["prerequisite_bindings"][f"ext{i:03d}_resolution_sha256"] = view.resolutions[f"S17-EXT-{i:03d}"].sha256
            raw, signature = self.f.sign()
            payload = dict(authorization=self.bind(self.f.root / "authorization.json"), signature=self.bind(signature))
        else:
            payload = dict(fact=input_id)
        raw = obj.prepare_record(input_id=input_id, resolution_id=f"software-scoped-{number}", payload=payload)
        return obj.append(**self.sign(raw))

    def full(self, obj):
        for number in (8,9,10):
            view = self.add(obj, number)
        return view

    def inventory(self):
        return {p.name:p.read_bytes() for p in self.root.iterdir()}

    def test_real_signed_full_chain_preserves_original_seven_and_never_grants_execution(self):
        with self.make() as obj:
            self.assertEqual(obj.inspect().generation, 0)
            view = self.full(obj)
            self.assertTrue(view.scoped_inputs_complete)
            self.assertEqual(set(view.resolutions), {f"S17-EXT-{i:03d}" for i in range(1,11)})
            for i in range(1,8):
                key = f"S17-EXT-{i:03d}"
                self.assertEqual(vars(view.resolutions[key]), vars(self.original_base[key]))
            for name in ("pilot_ready", "execution_authority", "phase18_authority"):
                self.assertIs(getattr(view,name), False)
            changed = view.resolutions
            changed["S17-EXT-008"].semantic_context["qualification_sha256"] = "f"*64
            self.assertNotEqual(obj.inspect().resolutions["S17-EXT-008"].semantic_context["qualification_sha256"], "f"*64)
            original = self.inventory()
            with self.assertRaises(journal.JournalError):
                self.add(obj, 10)
            self.assertEqual(self.inventory(), original)
        with self.make() as obj:
            self.assertTrue(obj.inspect().scoped_inputs_complete)
        self.assertEqual({k:vars(v) for k,v in self.base.resolutions.items()},
            {k:vars(v) for k,v in self.original_base.items()})

    def test_semantic_replay_is_mandatory_and_boolean_or_self_asserted_results_reject(self):
        with self.assertRaises(journal.JournalError):
            self.make(semantic_replay=None)
        with self.make(semantic_replay=lambda *a,**k:True) as obj:
            before = self.inventory()
            with self.assertRaises(journal.JournalError):
                obj.prepare_record(input_id="S17-EXT-008", resolution_id="software-8", payload={})
            self.assertEqual(self.inventory(), before)
        with self.make() as obj:
            with self.assertRaises(journal.JournalError):
                obj.prepare_record(input_id="S17-EXT-008", resolution_id="software-8",
                    payload={"semantic_context":self.f.plan_context})

    def test_wrong_signature_key_namespace_or_changed_bytes_publish_nothing(self):
        other = self.f.root / "foreign-key"
        subprocess.run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(other)],
            check=True, capture_output=True, timeout=10)
        with self.make() as obj:
            raw = obj.prepare_record(input_id="S17-EXT-008", resolution_id="software-8", payload={"fact":"S17-EXT-008"})
            before = self.inventory()
            for key, namespace in ((other,"cpu-prefetch-stage17"),(self.f.key,"unrelated")):
                with self.assertRaises(ERRORS):
                    obj.append(**self.sign(raw,key=key,namespace=namespace))
                self.assertEqual(self.inventory(), before)
            args = self.sign(raw)
            path = Path(args["record_binding"]["path"])
            doc = journal.archive.parse_json(raw);doc["resolution_id"]="foreign-resolution"
            path.write_bytes(journal.archive.canonical(doc));args["record_binding"]=self.bind(path)
            with self.assertRaises(ERRORS):
                obj.append(**args)
            self.assertEqual(self.inventory(), before)

    def test_order_anchor_scope_and_chronology_mutants_reject_before_publication(self):
        with self.make() as obj:
            raw = obj.prepare_record(input_id="S17-EXT-008", resolution_id="software-8", payload={"fact":"S17-EXT-008"})
            before = self.inventory()
            for key,value in (("input_id","S17-EXT-009"),("anchor_sha256","f"*64),
                ("previous_scoped_record_sha256","f"*64),("phase18_authority",True),
                ("synthetic_test_only",False),("recorded_at_unix_ns",time.time_ns()+10**12)):
                doc = journal.archive.parse_json(raw);doc[key]=value
                with self.subTest(key=key), self.assertRaises(ERRORS):
                    obj.append(**self.sign(journal.archive.canonical(doc)))
                self.assertEqual(self.inventory(),before)

    def test_semantic_failure_or_changed_independent_result_cannot_be_signed_into_readiness(self):
        with self.make() as obj:
            raw = obj.prepare_record(input_id="S17-EXT-008", resolution_id="software-8", payload={"fact":"S17-EXT-008"})
            args=self.sign(raw);before=self.inventory()
            self.f.plan_context["qualification_sha256"]="f"*64
            with self.assertRaises(journal.JournalError):obj.append(**args)
            self.assertEqual(self.inventory(),before)
            self.f.plan_context["qualification_sha256"]="a"*64
            self.add(obj,8)
            raw=obj.prepare_record(input_id="S17-EXT-009",resolution_id="software-9",payload={"fact":"S17-EXT-009"})
            args=self.sign(raw);before=self.inventory();self.fail="S17-EXT-009"
            with self.assertRaises(journal.JournalError):obj.append(**args)
            self.assertEqual(self.inventory(),before)

    def test_prefix_snapshot_signature_and_record_tampering_are_detected(self):
        with self.make() as obj:
            self.add(obj,8)
            for name in ("record-008.json","record-008.sig","journal-1.json"):
                path=self.root/name;original=path.read_bytes()
                try:
                    path.write_bytes(original[:-1]+bytes([original[-1]^1]))
                    with self.subTest(name=name),self.assertRaises(ERRORS):obj.inspect()
                finally:path.write_bytes(original)
            self.assertEqual(obj.inspect().generation,1)

    def test_partial_publication_is_preserved_and_blocks_adoption_or_retry(self):
        with self.make() as obj:
            raw=obj.prepare_record(input_id="S17-EXT-008",resolution_id="software-8",payload={"fact":"S17-EXT-008"})
            args=self.sign(raw);write=obj._write_new
            def fail_signature(name,data):
                if name.endswith('.sig'):raise OSError('synthetic publication interruption')
                return write(name,data)
            with mock.patch.object(obj,"_write_new",side_effect=fail_signature):
                with self.assertRaises(OSError):obj.append(**args)
            self.assertEqual((self.root/'record-008.json').read_bytes(),raw)
            with self.assertRaises(journal.JournalError):obj.inspect()
            with self.assertRaises(journal.JournalError):obj.append(**args)
        with self.assertRaises(journal.JournalError):
            with self.make():pass
        with self.assertRaises(FileExistsError):self.make().initialize()

    def test_foreign_anchor_semantic_policy_or_fixture_promotion_rejects(self):
        foreign=copy.deepcopy(self.base);foreign.latest_journal_sha256='f'*64
        for changes in ({'base_validation':foreign},{'semantic_policy_sha256':'f'*64},{'synthetic_test_only':False}):
            with self.subTest(changes=list(changes)),self.assertRaises(journal.JournalError):
                with self.make(**changes):pass

    def test_lock_deadline_read_bound_and_root_replacement_fail_closed(self):
        with self.make() as obj:
            with self.assertRaises(BlockingIOError):
                with self.make():pass
            deadline=obj._deadline_ns;obj._deadline_ns=0
            with self.assertRaises(journal.JournalError):obj.inspect()
            obj._deadline_ns=deadline
            total=obj._read_bytes;obj._read_bytes=journal.MAX_READ_BYTES
            with self.assertRaises(journal.JournalError):obj.inspect()
            obj._read_bytes=total
            old=self.root.with_name('original-held-journal');self.root.rename(old);self.root.mkdir(mode=0o700)
            with self.assertRaises(journal.JournalError):obj.inspect()

    def test_historical_signature_replay_survives_expiry_but_live_replay_rejects(self):
        with self.make() as obj:
            self.full(obj)
            future=time.time_ns()+2*authority.DAY_NS
            with mock.patch.object(authority.time,'time_ns',return_value=future):
                view=obj.inspect()
                self.assertTrue(view.scoped_inputs_complete)
                self.assertFalse(view.execution_authority)
                with self.assertRaises(authority.AuthorityError):obj.inspect(for_execution=True)
            raw=(self.f.root/'authorization.json').read_bytes()
            proof=authority.verify_historical_authorization(authorization_bytes=raw,
                signature_path=self.f.root/'authorization.json.sig',plan=self.f.plan,validation=view)
            self.assertNotIn('request_bytes',proof)
            self.assertIs(proof['current_window_checked'],False)
            self.assertIs(proof['execution_authority'],False)

    def test_lock_inode_replacement_and_nonobject_payload_reject(self):
        with self.make() as obj:
            before=self.inventory()
            with self.assertRaisesRegex(journal.JournalError,'payload must be an object'):
                obj.prepare_record(input_id='S17-EXT-008',resolution_id='software-8',payload=[])
            self.assertEqual(self.inventory(),before)
            (self.root/'journal.lock').rename(self.root/'original-lock')
            (self.root/'journal.lock').touch(mode=0o600)
            with self.assertRaisesRegex(journal.JournalError,'held journal lock changed'):
                obj.inspect()

    def test_inflight_anchor_or_inventory_change_is_detected_before_return(self):
        with self.make() as obj:
            self.add(obj,8)
            original=authority.signatures._verify_signature
            path=self.root/'journal-0.json';raw=path.read_bytes()
            def mutate_after_signature(*args):
                original(*args)
                doc=journal.archive.parse_json(raw);doc['semantic_policy_sha256']='f'*64
                path.write_bytes(journal.archive.canonical(doc))
            try:
                with mock.patch.object(authority.signatures,'_verify_signature',side_effect=mutate_after_signature):
                    with self.assertRaisesRegex(journal.JournalError,'changed before replay completed'):
                        obj.inspect()
            finally:path.write_bytes(raw)
            def add_orphan_after_signature(*args):
                original(*args)
                (self.root/'unexpected-object').write_bytes(b'software-only')
            with mock.patch.object(authority.signatures,'_verify_signature',side_effect=add_orphan_after_signature):
                with self.assertRaises(journal.JournalError):obj.inspect()

    def test_regressed_record_time_and_unsigned_context_substitution_reject(self):
        with self.make() as obj:
            self.add(obj,8)
            raw=obj.prepare_record(input_id='S17-EXT-009',resolution_id='software-9',payload={'fact':'S17-EXT-009'})
            doc=journal.archive.parse_json(raw)
            before=self.inventory()
            earlier=journal.archive.parse_json((self.root/'record-008.json').read_bytes())['recorded_at_unix_ns']-1
            for key,value in (('recorded_at_unix_ns',earlier),('semantic_context_sha256','f'*64)):
                changed=copy.deepcopy(doc);changed[key]=value
                with self.assertRaises(journal.JournalError):obj.append(**self.sign(journal.archive.canonical(changed)))
                self.assertEqual(self.inventory(),before)

    def test_base_adapter_forces_actual_time_policy_and_nonsynthetic_replay(self):
        locators={key:Path('/software-only') for key in ('repository_root','evidence_root','latest_journal',
            'journal_directory','pilot_archive','pilot_sidecar')}
        kwargs=dict(plan=self.f.plan,semantic_policy_sha256=self.policy,semantic_replay=self.semantic)
        with mock.patch('stage17_state_journal_v62.validate_operational_journal',return_value=self.base) as replay:
            obj=journal.from_authenticated_base(self.root,base_replay_arguments=locators,**kwargs)
            self.assertIs(obj.mode,False)
            self.assertIs(replay.call_args.kwargs['allow_synthetic_test_evidence'],False)
            self.assertTrue(replay.call_args.kwargs['as_of_utc'].endswith('Z'))
            with self.assertRaises(authority.AuthorityError):
                journal.from_authenticated_base(self.root,
                    base_replay_arguments=dict(locators,allow_synthetic_test_evidence=True),**kwargs)
            self.assertEqual(replay.call_count,1)
        absent=copy.deepcopy(self.base);absent.resolutions.pop('S17-EXT-007')
        with self.assertRaises(journal.JournalError):self.make(base_validation=absent)

    def test_legacy_descriptive_pilot_rejection_is_preserved(self):
        import stage17_semantic_verifier_v65 as legacy
        with self.make() as obj:
            view=self.full(obj)
            for number in (8,9,10):
                with self.assertRaisesRegex(legacy.SemanticAdmissionError,'descriptive EXT007 grants no legacy pilot'):
                    legacy.verify_input(input_id=f'S17-EXT-{number:03d}',admitted_resolutions=view.resolutions)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',type=Path,required=True)
    args,rest=parser.parse_known_args()
    JournalTests.worker=args.worker.resolve()
    unittest.main(argv=[__file__,*rest])
