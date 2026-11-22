"""Real accepted-generator/filesystem tests with a synthetic source-bank fixture.

Only the fixture's frozen-blueprint fingerprint is patched: it uses disjoint
SOFTWARE namespaces and tiny rates. No prospective research source is generated.
The unpatched original blueprint is checked separately without source generation.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage17_s180_source_provenance_v1 as source
import stage17_s180_checkpoint_v1 as constants
from test_stage17_s180_plan_prepare_v1 import fixture

ERRORS = (source.SourceError, source.archive.ArchiveError, source.planning.PlanError,
          source.metadata.ScheduleProvenanceError, OSError)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="s180-source-software-template-")
        cls.root = Path(cls.temp.name)
        cls.original = fixture("34247cedab4abe4b44732daae8fdac1700eccffd")
        cls.original["schema_version"] = source.planning.PLAN
        del cls.original["source_count_basis"]
        cls.plan = json.loads(json.dumps(cls.original).replace("CPU-PREFETCH-V5-D310-S180-1", "SOFTWARE-S180-SOURCE"))
        blueprint = cls.plan["blueprint"]
        blueprint["master_seed_hex"] = "11"*32
        for row in blueprint["captures"]:
            row["nominal_rate"]["numerator"] = {"L025":5,"L050":7,"L075":9}[row["load_level"]]
            row["nominal_rate"]["denominator"] = 1
        cls.fingerprint = source.planning.sha(blueprint)
        cls.seed = "SOFTWARE-S180-SOURCE-SEED"
        cls.records = []
        cls.generated = []
        with mock.patch.object(source.planning,"BLUEPRINT_SHA256",cls.fingerprint):
            expected = source.expected_sources(cls.plan,seed_id=cls.seed)
        for i,e in enumerate(expected):
            rate=e["nominal_offered_rate"]
            spec=source.generator.ScheduleSpec(e["schedule_id"],e["schedule_kind"],e["namespace_id"],
                e["parent_namespace_id"],e["seed_id"],f"SOFTWARE-DERIVATION-{i}",bytes.fromhex(e["master_seed_hex"]),
                e["origin_ticks"],e["horizon_ticks"],rate["numerator_events"],rate["denominator_ticks"],
                e["source_artifact"]["artifact_id"],f"source-{i}.bin")
            generated=source.generator.generate_schedule(spec)
            cls.generated.append((spec,generated))
            record={key:e[key] for key in ("placement","working_set_class","load_level","phase")}
            for name,identity,raw in (("binary",spec.artifact_id,generated.artifact_bytes),
                ("envelope",f"SOFTWARE-ENVELOPE-{i}",generated.envelope_bytes),
                ("derivation",f"SOFTWARE-DERIVATION-ARTIFACT-{i}",generated.derivation_record_bytes)):
                path=cls.root/f"source-{i}-{name}"
                path.write_bytes(raw)
                record[name]=dict(path=str(path),artifact_id=identity,size_bytes=len(raw),sha256=digest(raw))
            cls.records.append(record)
            cls.update_plan(cls.plan,record,len(generated.deadlines),generated.artifact_sha256)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @staticmethod
    def update_plan(plan,record,count,sha):
        rows=sorted(plan["blueprint"]["captures"],key=lambda r:r["execution_ordinal"])
        for row,entry in zip(rows,plan["captures"],strict=True):
            if all(row[k]==record[k] for k in ("placement","working_set_class","load_level")):
                p=entry["phases"][0 if record["phase"]=="warmup" else 1]
                p["offered_count"]=count
                p["producer_attempt_limit"]=max(p["producer_attempt_limit"],count,1)
                p["source_artifact"]["sha256"]=sha

    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="s180-source-software-")
        self.addCleanup(temp.cleanup)
        self.directory=Path(temp.name)/"bank"
        shutil.copytree(self.root,self.directory)
        self.p=copy.deepcopy(self.plan)
        self.r=copy.deepcopy(self.records)
        for record in self.r:
            for name in ("binary","envelope","derivation"):
                record[name]["path"]=str(self.directory/Path(record[name]["path"]).name)
        patch=mock.patch.object(source.planning,"BLUEPRINT_SHA256",self.fingerprint)
        patch.start();self.addCleanup(patch.stop)

    def verify(self,**changes):
        args=dict(plan=self.p,seed_id=self.seed,records=self.r,maximum_source_bytes=1024**2,
                  deadline_ns=time.monotonic_ns()+30_000_000_000)
        args.update(changes)
        return source.verify_source_bank(**args)

    def rewrite(self,binding,raw):
        Path(binding["path"]).write_bytes(raw)
        binding.update(size_bytes=len(raw),sha256=digest(raw))

    def metadata(self,record,kind,mutate):
        binding=record[kind]
        doc=json.loads(Path(binding["path"]).read_bytes());mutate(doc)
        field="schedule_sha256" if kind=="envelope" else "record_sha256"
        doc[field]="0"*64;doc[field]=digest(source.archive.canonical(doc))
        self.rewrite(binding,source.archive.canonical(doc)+b"\n")

    def test_all36_original_sources_use_real_generator_and_leave_inputs_unchanged(self):
        before={p.name:p.read_bytes() for p in self.directory.iterdir()}
        report=self.verify(records=list(reversed(self.r)))
        self.assertEqual(report["source_count"],36)
        self.assertTrue(report["accepted_generation_verified"])
        self.assertEqual(report["original_source_bytes"],sum(r["binary"]["size_bytes"] for r in self.r))
        self.assertEqual({r["schedule_kind"] for r in report["sources"]},{"PILOT","WARMUP"})
        for key in ("namespace_freshness_verified","resource_admission_performed","execution_authority","phase18_authority"):
            self.assertIs(report[key],False)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.directory.iterdir()})

    def test_actual_frozen_blueprint_rates_namespaces_and_pairing_without_generation(self):
        with mock.patch.object(source.planning,"BLUEPRINT_SHA256",constants.BLUEPRINT_SHA256):
            original=copy.deepcopy(self.original)
            expected=source.expected_sources(original,seed_id="prospective-identity-only")
            self.assertEqual(len(expected),36)
            self.assertEqual({e["parent_namespace_id"] for e in expected},{"CPU-PREFETCH-V5-D310-S180-1/PILOT"})
            self.assertEqual({(e["nominal_offered_rate"]["numerator_events"],e["nominal_offered_rate"]["denominator_ticks"])
                for e in expected},{(1670571,4*10**12),(1670571,2*10**12),(5011713,4*10**12)})
            original["blueprint"]["captures"][0]["measurement_ns"]+=1
            with self.assertRaises(source.planning.PlanError):source.expected_sources(original,seed_id=self.seed)

    def test_missing_duplicate_foreign_or_extra_record_rejects(self):
        candidates=[self.r[:-1],[*self.r[:-1],copy.deepcopy(self.r[0])]]
        foreign=copy.deepcopy(self.r);foreign[0]["placement"]="FOREIGN";candidates.append(foreign)
        extra=copy.deepcopy(self.r);extra[0]["deadline_ticks"]=[];candidates.append(extra)
        alias=copy.deepcopy(self.r);alias[1]["envelope"]["artifact_id"]=alias[0]["envelope"]["artifact_id"];candidates.append(alias)
        for records in candidates:
            with self.subTest(case=candidates.index(records)),self.assertRaises(ERRORS):self.verify(records=records)

    def test_sizing_ceiling_unknown_binding_and_changed_common_sources_reject(self):
        for change in (lambda p:p.update(schema_version=source.planning.SIZING),
            lambda p:p.update(source_count_basis="PROSPECTIVE_UPPER_CEILINGS"),
            lambda p:p["captures"][0]["phases"][0].update(source_artifact=None),
            lambda p:p["captures"][0]["phases"][0].update(offered_count=1)):
            plan=copy.deepcopy(self.p);change(plan)
            with self.assertRaises(ERRORS):self.verify(plan=plan)

    def test_calibration_role_foreign_namespace_rate_horizon_and_seed_reject(self):
        for kind,key,value in (("envelope","schedule_kind","CALIBRATION"),
            ("envelope","namespace_id","SOFTWARE-FOREIGN/PILOT"),
            ("envelope","nominal_offered_rate",dict(numerator_events=1,denominator_ticks=1)),
            ("envelope","horizon_ticks",1),("derivation","seed_id","SOFTWARE-FOREIGN-SEED"),
            ("derivation","parent_namespace_id","SOFTWARE-FOREIGN/PILOT"),
            ("derivation","derived_key_u32be_hex","0"*16)):
            binding=self.r[0][kind];before=copy.deepcopy(binding);raw=Path(binding["path"]).read_bytes()
            try:
                self.metadata(self.r[0],kind,lambda d:d.update({key:value}))
                with self.subTest(key=key),self.assertRaises(ERRORS):self.verify()
            finally:
                Path(binding["path"]).write_bytes(raw);binding.clear();binding.update(before)

    def test_self_consistent_hash_forgery_still_fails_independent_generation(self):
        record=self.r[0];raw=Path(record["binary"]["path"]).read_bytes()
        self.assertGreater(len(raw),0)
        raw=bytes(8)+raw[8:]
        self.rewrite(record["binary"],raw)
        self.update_plan(self.p,record,len(raw)//8,digest(raw))
        self.metadata(record,"envelope",lambda d:d["deadline_storage"].update(artifact_sha256=digest(raw)))
        with self.assertRaisesRegex(source.SourceError,"accepted-generated deadline differs"):self.verify()

    def test_fully_rehashed_truncated_stream_cannot_hide_next_in_window_arrival(self):
        record=self.r[0];spec,generated=self.generated[0]
        self.assertGreater(len(generated.deadlines),1)
        kept=generated.deadlines[:-1];raw=generated.artifact_bytes[:-8]
        self.rewrite(record["binary"],raw)
        self.update_plan(self.p,record,len(kept),digest(raw))
        def truncate(d):
            d["offered_count"]=len(kept)
            d["decoded_deadlines_sha256"]=source.generator._decoded_hash(spec,kept)
            d["deadline_storage"].update(row_count=len(kept),byte_count=len(raw),artifact_sha256=digest(raw))
        self.metadata(record,"envelope",truncate)
        with self.assertRaisesRegex(source.SourceError,"omits generated in-window arrivals"):self.verify()

    def test_unsafe_symlink_and_wrong_size_sources_reject(self):
        binding=self.r[0]["binary"];path=Path(binding["path"]);original=path.read_bytes()
        path.chmod(0o666)
        with self.assertRaisesRegex(source.SourceError,"unsafe"):self.verify()
        path.chmod(0o600)
        moved=path.with_suffix(".saved");path.rename(moved);path.symlink_to(moved)
        with self.assertRaisesRegex(source.SourceError,"nonsymlink"):self.verify()
        path.unlink();moved.rename(path)
        path.write_bytes(original+b"x")
        with self.assertRaisesRegex(source.SourceError,"wrong-sized"):self.verify()

    def test_noninteger_metadata_wrong_original_and_decoded_hash_reject(self):
        binding=self.r[0]["envelope"];original=Path(binding["path"]).read_bytes();saved=copy.deepcopy(binding)
        for key,value in (("offered_count",True),("origin_ticks",0.0),("decoded_deadlines_sha256","f"*64)):
            try:
                if type(value) is float:
                    doc=json.loads(original);doc[key]=value
                    self.rewrite(binding,json.dumps(doc).encode())
                else:
                    self.metadata(self.r[0],"envelope",lambda d:d.update({key:value}))
                with self.subTest(key=key),self.assertRaises(source.SourceError):self.verify()
            finally:
                Path(binding["path"]).write_bytes(original);binding.clear();binding.update(saved)
        binding["sha256"]="f"*64
        with self.assertRaises(source.SourceError):self.verify()

    def test_integral_float_control_is_rejected_before_canonical_normalization(self):
        self.p["budget"]["memory_bytes"]=float(self.p["budget"]["memory_bytes"])
        with self.assertRaisesRegex(source.SourceError,"floating-point source control"):self.verify()

    def test_physical_alias_and_deadline_expiry_during_regeneration_reject(self):
        second=Path(self.r[1]["envelope"]["path"]);original=second.read_bytes()
        second.unlink();second.hardlink_to(Path(self.r[0]["envelope"]["path"]))
        self.r[1]["envelope"].update(size_bytes=self.r[0]["envelope"]["size_bytes"],sha256=self.r[0]["envelope"]["sha256"])
        with self.assertRaisesRegex(source.SourceError,"inode reused"):self.verify()
        second.unlink();second.write_bytes(original)
        self.r[1]["envelope"].update(size_bytes=len(original),sha256=digest(original))
        real=source.generator._advance_cumulative;now=0
        def expire(*args):
            nonlocal now
            result=real(*args);now=1000
            return result
        with mock.patch.object(source.time,"monotonic_ns",side_effect=lambda:now), \
             mock.patch.object(source.generator,"_advance_cumulative",side_effect=expire):
            with self.assertRaisesRegex(source.SourceError,"deadline expired"):self.verify(deadline_ns=500)

    def test_verified_report_does_not_alias_input_bindings(self):
        report=self.verify()
        self.r[0]["binary"]["sha256"]="f"*64
        self.assertNotEqual(report["sources"][0]["binary"]["sha256"],"f"*64)

    def test_independently_valid_sources_cannot_alias_derivation_record_identity(self):
        first=json.loads(Path(self.r[0]["derivation"]["path"]).read_bytes())["record_id"]
        self.metadata(self.r[1],"derivation",lambda d:d.update(record_id=first))
        self.metadata(self.r[1],"envelope",lambda d:d["rng"].update(derivation_record_id=first))
        with self.assertRaisesRegex(source.SourceError,"derivation record identity reused"):self.verify()

    def test_budget_deadline_and_midflight_original_mutation_reject(self):
        for changes in (dict(maximum_source_bytes=1),dict(deadline_ns=0),dict(seed_id="SOFTWARE-FOREIGN-SEED")):
            with self.assertRaises(ERRORS):self.verify(**changes)
        original=source._verify_one;count=0;path=Path(self.r[0]["envelope"]["path"])
        def mutate(*args):
            nonlocal count
            result=original(*args);count+=1
            if count==2:path.write_bytes(path.read_bytes()+b" ")
            return result
        with mock.patch.object(source,"_verify_one",side_effect=mutate):
            with self.assertRaisesRegex(source.SourceError,"changed during bank verification"):self.verify()


if __name__ == "__main__":
    unittest.main()
