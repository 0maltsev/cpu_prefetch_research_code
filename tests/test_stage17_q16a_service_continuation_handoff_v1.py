"""Real /4 handoff reads/semantics; synthetic old release boundary only."""
import copy
import hashlib
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16a_service_continuation_handoff_v1 as current
import stage17_q16a_daycap_handoff_v1 as original
import test_stage17_q16a_daycap_handoff_v1 as fixtures
from test_stage17_formal_service_continuation_v1 import parent_fixture,continuation_fixture
from test_stage17_q16a_handoff_v1 import fixture as retained_fixture


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.view=current.make_handoff()
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with mock.patch.object(fixtures,'current',self.view):
            self.evidence=fixtures.Evidence(pathlib.Path(self.temp.name),continuation_fixture(parent_fixture()))

    def consume(self):
        e=self.evidence;view=self.view
        binding=fixtures.save(e.root/'compatibility.json',e.proof)
        real=view._release
        def release(side,context,reader,source):
            if source==view.original.SOURCE:return e.releases['original']
            return real(side,context,reader,source)
        with mock.patch.object(view.original,'consume',return_value=e.result) as old:
            with mock.patch.dict(view.consume.__globals__,{'_release':release}):
                result=view.consume(e.document,validation=e.validation,plan=e.plan,
                    selected_duration_ns=1_000_000_000,original_validation=e.original_validation,
                    original_plan=e.original_plan,compatibility=binding,original_boot_id=e.boot,boot_id=e.boot)
            old.assert_called_once_with(e.document,validation=e.original_validation,
                plan=e.original_plan,selected_duration_ns=1_000_000_000)
        return result

    def test_actual_103_plan_preserves_original_result_and_checks_current_real_bundle(self):
        before=copy.deepcopy((self.evidence.plan,self.evidence.result))
        self.assertIs(self.consume(),self.evidence.result)
        self.assertEqual(before,(self.evidence.plan,self.evidence.result))
        self.assertEqual(len(self.evidence.plan['captures']),103)

    def test_historical_globals_and_function_bodies_remain_unchanged(self):
        self.assertEqual(original.COLD_SHA256,'6d18ae41bd0a51d173ea98a53b9e88f13a245efd296f8d4e0a6a4558915d2951')
        self.assertNotEqual(original.SCHEMA,self.view.SCHEMA)
        self.assertIs(self.view.consume.__code__,original.consume.__code__)
        self.assertIs(self.view._platforms.__code__,original._platforms.__code__)
        self.assertEqual(current.COLD_SHA256,hashlib.sha256((ROOT/original.COLD_SOURCE).read_bytes()).hexdigest())

    def test_120_plan_relabel_cannot_select_continuation_consumer(self):
        self.evidence.plan['schema_version']='cpu-prefetch-stage17-formal-service-plan/3'
        self.evidence.proof['plan']=fixtures.save(self.evidence.root/'plan.json',self.evidence.plan)
        with self.assertRaises(self.view.Error):self.consume()

    def test_prefix_omission_cannot_hide_in_q16a_compatibility(self):
        self.evidence.plan['captures'].pop()
        self.evidence.proof['plan']=fixtures.save(self.evidence.root/'plan.json',self.evidence.plan)
        with self.assertRaises(self.view.Error):self.consume()

    def test_original_source_or_current_release_relabel_rejected(self):
        self.evidence.proof['current']['worker']['sha256']='0'*64
        with self.assertRaises(self.view.Error):self.consume()

    def test_omitted_measured_dependency_rejected(self):
        self.evidence.proof['source_comparisons'].pop()
        with self.assertRaises(self.view.Error):self.consume()

    def test_boot_mismatch_rejected(self):
        self.evidence.proof['scope']['boot_id']='0'*36
        with self.assertRaises(self.view.Error):self.consume()

    def test_real_completed708_consumer_runs_before_new_metadata(self):
        document,validation,plan=retained_fixture()
        expected=original.original.consume(document,validation=validation,plan=plan,
                                            selected_duration_ns=1_000_000_000)
        self.assertEqual(len(expected['run_sources']),708)
        with mock.patch.object(original.original,'consume',wraps=original.original.consume) as call:
            with self.assertRaises(self.view.Error):
                self.view.consume(document,validation=object(),plan=object(),selected_duration_ns=1_000_000_000,
                    original_validation=validation,original_plan=plan,compatibility={},original_boot_id='unused',boot_id='unused')
            call.assert_called_once_with(document,validation=validation,plan=plan,selected_duration_ns=1_000_000_000)


if __name__=='__main__':unittest.main()
