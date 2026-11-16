"""Completed actual metadata, exact arithmetic and unchanged statistical boundary."""
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16b_handoff_v1 as handoff
import prepare_stage17_q16b_handoff_v1 as publisher


def fixture():
    done=ROOT/'docs/evidence/stage17/Q16B-D268-COMPLETE-20261117-01'
    paths=dict(completion=done/'study-result.json',analysis=done/'analysis-complete.json',
        composition=done/'calibration-validation.json',
        plan=ROOT/'docs/evidence/stage17/D268-COLLECTION-20261116-01/plan.json',
        parent_plan=ROOT/'docs/evidence/stage17/D266-RESUMED-ADMISSION-20261116-01/original-parent-plan.json',
        geometry=ROOT/'docs/evidence/stage17/Q16B-HANDOFF-20261117-01/native-geometry.json')
    document=dict(schema_version=handoff.SCHEMA,execution_authority=False,phase18_authority=False)
    for name,path in paths.items():
        raw=path.read_bytes();document[name]=dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    context=dict(source_revision=handoff.SOURCE,inventory_sha256=handoff.INVENTORY,
                 release_artifact_sha256=handoff.WORKER,archive_bundle_root='/synthetic-qualified-root',
                 release_artifact_path='/synthetic-qualified-root/release/bin/cpu_prefetch_runner')
    platform=dict(stand_id='CPU-PREFETCH-V5',pilot_platform_measurements=dict(platform_manifest_sha256=handoff.PLATFORM))
    validation=SimpleNamespace(resolutions={
        'S17-EXT-006':SimpleNamespace(semantic_context=context),
        'S17-EXT-004':SimpleNamespace(semantic_context=platform)})
    return document,validation


class HandoffTests(unittest.TestCase):
    def setUp(self):self.document,self.validation=fixture()
    def consume(self):return handoff.consume(self.document,validation=self.validation,selected_duration_ns=1_000_000_000)

    def test_actual_original120_result_and_full_outcomes_remain_unchanged(self):
        result=self.consume();original=json.loads(Path(self.document['composition']['path']).read_bytes())
        self.assertEqual(result,original)
        self.assertEqual(len(result['run_sources']),120)
        self.assertEqual([p['planned_captures'] for p in result['source_populations']],[17,103])
        self.assertEqual(result['status'],'DESCRIPTIVE');self.assertFalse(result['tolerance_guarantee'])
        self.assertFalse(result['report_provenance_authenticated']);self.assertFalse(result['execution_authority'])
        self.assertEqual(result['derived_result']['measurement_zero_loss_gate'],'FAIL')
        self.assertEqual(result['derived_result']['warmup_zero_loss_gate'],'FAIL')
        self.assertEqual(sum(r['summary']['full_counts'][1]>0 for r in result['run_sources']),20)
        self.assertEqual(handoff.mathematics.MINIMUM_VALID_RUNS,59)

    def test_exact_planning_rates_have_no_confidence_or_execution_claim(self):
        result=self.consume();basis=handoff.load_basis(result)
        self.assertEqual(basis['mu_ref_observed_min'],dict(numerator=1670571,denominator=1))
        for name,factor in [('L025',Fraction(1,4)),('L050',Fraction(1,2)),('L075',Fraction(3,4))]:
            self.assertEqual(Fraction(**basis['base_rates'][name]),1670571*factor)
        self.assertIsNone(basis['confidence_claim']);self.assertFalse(basis['execution_authority'])
        self.assertEqual(result['derived_result'].get('mu_ref'),None)

    def test_rebound_changed_artifacts_cannot_replace_audited_originals(self):
        with tempfile.TemporaryDirectory() as name:
            for key in handoff.ACCEPTED:
                original=self.document[key];raw=Path(original['path']).read_bytes()+b' '
                path=Path(name)/key;path.write_bytes(raw)
                self.document[key]=dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                with self.subTest(key=key),self.assertRaises(handoff.Error):self.consume()
                self.document[key]=original

    def test_exact_relocated_durable_copies_are_accepted_but_symlinks_are_not(self):
        with tempfile.TemporaryDirectory() as name:
            for key in handoff.ACCEPTED:
                path=Path(name)/key;path.write_bytes(Path(self.document[key]['path']).read_bytes());self.document[key]['path']=str(path)
            self.assertEqual(self.consume()['status'],'DESCRIPTIVE')
            original=Path(self.document['composition']['path']);alias=Path(name)/'alias';alias.symlink_to(original)
            self.document['composition']['path']=str(alias)
            with self.assertRaises(handoff.Error):self.consume()

    def test_wrong_qualified_source_inventory_worker_or_location_rejected(self):
        original=copy.deepcopy(self.validation)
        for field in ('source_revision','inventory_sha256','release_artifact_sha256','release_artifact_path'):
            self.validation=copy.deepcopy(original);self.validation.resolutions['S17-EXT-006'].semantic_context[field]='different'
            with self.subTest(field=field),self.assertRaises(handoff.Error):self.consume()

    def test_wrong_platform_stand_duration_or_promoted_authority_rejected(self):
        original=copy.deepcopy(self.validation)
        for field in ('stand_id','pilot_platform_measurements'):
            self.validation=copy.deepcopy(original);self.validation.resolutions['S17-EXT-004'].semantic_context[field]='different' if field=='stand_id' else dict(platform_manifest_sha256='0'*64)
            with self.subTest(field=field),self.assertRaises(handoff.Error):self.consume()
        self.validation=original
        with self.assertRaises(handoff.Error):handoff.consume(self.document,validation=original,selected_duration_ns=2_000_000_000)
        self.document['execution_authority']=True
        with self.assertRaises(handoff.Error):self.consume()

    def test_basis_cannot_rebind_an_arbitrary_minimum_to_audited_hash(self):
        result=self.consume();result['derived_result']['min_mu_ref']['numerator']+=1
        with self.assertRaises(handoff.Error):handoff.load_basis(result)


class PublisherTests(unittest.TestCase):
    def test_bound_bytes_reject_modification_and_symlink(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'metadata';path.write_bytes(b'{"captures":120}')
            bound=publisher.binding(path);self.assertEqual(publisher.read(bound),path.read_bytes())
            path.write_bytes(b'{"captures":121}')
            with self.assertRaises(ValueError):publisher.read(bound)
            alias=path.parent/'alias';alias.symlink_to(path)
            with self.assertRaises(ValueError):publisher.read(dict(bound,path=str(alias)))

    def test_exclusive_publication_never_overwrites_prior_result(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'receipt';bound=publisher.save(path,dict(execution_authority=False))
            self.assertEqual(publisher.read(bound),b'{"execution_authority":false}\n')
            with self.assertRaises(FileExistsError):publisher.save(path,dict(execution_authority=True))


if __name__=='__main__':unittest.main()
